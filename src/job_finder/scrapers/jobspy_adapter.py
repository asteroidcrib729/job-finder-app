"""Source-specific, budgeted JobSpy discovery. Queries never establish job facts."""
import hashlib
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone

from job_finder.configuration.paths import BASE_DIR
from job_finder.scrapers.base import (
    Job,
    canonical_url,
    clean_text,
    optional_bool,
    optional_number,
    parse_date,
)
from job_finder.scrapers.cache import attempt_due, query_due
from job_finder.scrapers.common import QueryOutcome, SourceError, SourceResult
from job_finder.scrapers.google_api import run_google_api
from job_finder.scrapers.linkedin_details import enrich_linkedin_jobs
from job_finder.scrapers.serpapi_budget import SerpApiBudget
from job_finder.storage.enrichment import QUEUE_KEY

logger = logging.getLogger(__name__)


def run_query(kwargs, timeout):
    try:
        completed = subprocess.run([sys.executable, "-m", "job_finder.scrapers.jobspy_worker"],
            input=json.dumps(kwargs), capture_output=True, text=True, encoding="utf-8",
            cwd=BASE_DIR, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SourceError("timed_out", "query_deadline") from exc
    if completed.returncode:
        raise SourceError("failed", "worker_failed")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as exc:
        raise SourceError("parse_failed", "invalid_worker_output") from exc
    if payload.get("error"):
        raise SourceError("failed", payload["error"])
    return payload


def build_query(config, track, keyword, site, offset=0, hours=None):
    options = config["jobspy"]
    hours = hours or options["hours_old"]
    kwargs = {"site_name": [site], "search_term": keyword,
              "location": track["location"] or None, "is_remote": track["remote"],
              "country_indeed": track["country_indeed"], "results_wanted": options["results_wanted"],
              "offset": offset, "description_format": "markdown", "verbose": 1}
    # Indeed ignores remote filtering when hours_old is also supplied.
    if site != "indeed" or not track["remote"]:
        kwargs["hours_old"] = hours
    if site == "linkedin":
        # Current JobSpy ignores LinkedIn's is_remote option. Query intent is
        # expressed as a keyword; eligibility still comes only from the listing.
        kwargs.pop("is_remote", None)
        if track["remote"]:
            kwargs["search_term"] = keyword + " remote"
        kwargs["fetch_description"] = False
    if site == "google":
        target = f"near {track['location']}" if track["location"] else "worldwide Pakistan eligible"
        freshness = "since yesterday" if hours <= 24 else "in the last week" if hours <= 168 else "in the last month"
        kwargs["google_search_term"] = f"{keyword} jobs {target} {'remote' if track['remote'] else ''} {freshness}".strip()
    return kwargs


def row_to_job(row, site, track, query_id):
    description = clean_text(row.get("description"))
    application = clean_text(row.get("job_url_direct"))
    if application:
        try:
            application = canonical_url(application)
        except ValueError:
            application = ""
    salary_source = clean_text(row.get("salary_source"))
    currency = clean_text(row.get("currency"))
    # JobSpy can infer a default currency. Retain this uncertainty instead of promising USD.
    salary_evidence = "disclosed" if salary_source == "direct_data" else "inferred" if currency else "unknown"
    reported_remote = optional_bool(row.get("is_remote"))
    if site == "linkedin" and reported_remote is False:
        # JobSpy infers False from a card that simply does not mention remote.
        # Such absence must not contradict an explicit remote description later.
        reported_remote = None
    return Job(
        title=clean_text(row.get("title")), company=clean_text(row.get("company")),
        location=clean_text(row.get("location")), url=clean_text(row.get("job_url")),
        platform=site.capitalize(), description=description, source_id=clean_text(row.get("id")),
        application_url=application, is_remote=reported_remote,
        posted_at=clean_text(row.get("date_posted")), date_source="source",
        description_status="full" if description else "missing",
        job_level=clean_text(row.get("job_level")), job_type=clean_text(row.get("job_type")),
        salary_min=optional_number(row.get("min_amount")), salary_max=optional_number(row.get("max_amount")),
        salary_currency=currency, salary_interval=clean_text(row.get("interval")), salary_source=salary_evidence,
        query_id=query_id, search_track=track["id"], active_status="unknown")


def fetch_jobspy_jobs(config, discovery=None, runner=None, detail_fetcher=None, sleep=None, api_budget=None):
    result = SourceResult("JobSpy")
    options = config["jobspy"]
    if not options["enabled"]:
        result.report.skipped = True
        return result
    runner = runner or run_query
    discovery = discovery or {}
    start = time.monotonic()
    failed_by_site = {}
    attempted = 0
    api_attempts = 0
    budget = api_budget or (SerpApiBudget(options) if options["google_provider"] == "serpapi" else None)
    # Rotate tracks/sites inside each keyword so a budget does not starve remote/local.
    plans = [(keyword, track, site) for keyword in config["search_keywords"]
             for track in config["search_tracks"] for site in track["sites"]
             if site != "google" or options["google_mode"] == "enabled"]
    # Least recently successful queries get their turn if a run exhausts its budget.
    def identity(plan):
        keyword, track, site = plan
        if site == "linkedin" and track["remote"]:
            keyword += " remote"
        prefix = "serpapi:" if site == "google" and options["google_provider"] == "serpapi" else "jobspy:"
        return prefix + hashlib.sha256(f"{site}|{track}|{keyword}".encode()).hexdigest()[:16]
    plans.sort(key=lambda plan: discovery.get(identity(plan), {}).get("last_success", ""))
    google_track = next((track for track in config["search_tracks"] if "google" in track["sites"]), None)
    probe_key = "probe:google" if options["google_provider"] == "jobspy" else "probe:google:serpapi"
    if options["google_mode"] == "probe" and google_track:
        if attempt_due(discovery, probe_key, options["google_probe_interval_hours"]):
            # One probe after normal searches; it cannot consume their budget.
            plans.append((config["search_keywords"][0], google_track, "google"))
        else:
            result.report.notes.append("google_probe_not_due")
    elif options["google_mode"] == "disabled" and google_track:
        result.report.notes.append("google_disabled")
    for plan in plans:
        if attempted >= options["max_queries"] or options["max_seconds"] - (time.monotonic() - start) < 5:
            result.report.notes.append("query_budget_exhausted")
            break
        keyword, track, site = plan
        probe = site == "google" and options["google_mode"] == "probe"
        phase = "probe" if probe else "search"
        query_id = probe_key if probe else identity(plan)
        use_api = site == "google" and options["google_provider"] == "serpapi"
        if use_api and api_attempts >= options["google_api_max_queries"]:
            result.report.notes.append("google_api_budget_exhausted")
            continue
        previous_result = discovery.get(query_id, {})
        low_yield = previous_result.get("qualified") == 0 and previous_result.get("review") == 0
        interval = max(options["interval_hours"], options["low_yield_interval_hours"]) if low_yield else options["interval_hours"]
        if not probe and not query_due(discovery, query_id, interval):
            result.report.notes.append(query_id + ":not_due")
            continue
        if failed_by_site.get(site, 0) >= 3:
            continue
        query_complete = True
        successful_update = None
        query_seen = set()
        for page in range(options["max_pages"]):
            remaining = options.get("max_seconds", 900) - (time.monotonic() - start)
            if attempted >= options["max_queries"] or remaining < 5:
                result.report.notes.append("query_budget_exhausted")
                query_complete = False
                break
            attempted += 1
            if probe:
                result.updates[query_id] = {**discovery.get(query_id, {}),
                    "last_attempt": datetime.now(timezone.utc).isoformat()}
            before = time.monotonic()
            previous = parse_date(discovery.get(query_id, {}).get("last_success"))
            hours = options["hours_old"]
            if previous:
                elapsed = (datetime.now(timezone.utc) - previous).total_seconds() / 3600
                hours = min(720, max(hours, int(elapsed + 24)))
            kwargs = build_query(config, track, keyword, site, page * options["results_wanted"], hours)
            if probe:
                kwargs["results_wanted"] = min(5, options["results_wanted"])
            logger.info("JobSpy %s %s: %s (page %d)", site, track["id"], keyword, page + 1)
            try:
                if use_api:
                    api_attempts += 1
                payload = run_google_api(kwargs, min(options["query_timeout"], remaining), budget=budget) if use_api else (
                    runner(kwargs, min(options["query_timeout"], remaining)))
                rows = payload["rows"]
                if not isinstance(rows, list):
                    raise SourceError("parse_failed", "rows_not_list")
                warnings = list(payload.get("warnings", []))
                if "unsupported_option" in warnings:
                    result.report.notes.append(site + ":unsupported_option")
                    warnings.remove("unsupported_option")
                if rows and "google_jobs_cursor_missing" in warnings:
                    # JobSpy also emits this warning for a valid single results page.
                    result.report.notes.append("google_initial_page_only")
                    warnings = [code for code in warnings if code != "google_jobs_cursor_missing"]
                converted, invalid = [], 0
                for row in rows:
                    try:
                        converted.append(row_to_job(row, site, track, query_id))
                    except (ValueError, TypeError, AttributeError):
                        invalid += 1
                distinct = [job for job in converted if job.job_id not in query_seen]
                query_seen.update(job.job_id for job in converted)
                result.extend(converted)
                # Unknown warnings remain visible, but are not circuit-breaker
                # evidence of a failed search when usable listings were returned.
                status = "partial" if warnings or invalid else "success" if rows else "valid_empty"
                if not rows and warnings == ["google_jobs_cursor_missing"]:
                    status = "unverified"
                result.report.queries.append(QueryOutcome(query_id, status, len(rows), len(converted), invalid,
                    round(time.monotonic() - before, 2), ",".join(warnings), site, track["id"], phase,
                    backend="serpapi" if use_api else "jobspy"))
                if warnings:
                    logger.warning("JobSpy %s %s: %s", site, track["id"], ",".join(warnings))
                if not converted and set(warnings) & {"blocked", "timed_out", "upstream_error", "google_no_job_data"}:
                    failed_by_site[site] = failed_by_site.get(site, 0) + 1
                else:
                    failed_by_site[site] = 0
                if status in {"success", "valid_empty"}:
                    successful_update = {"last_success": datetime.now(timezone.utc).isoformat(),
                        "raw": len(rows), "unique": len(distinct)}
                else:
                    query_complete = False
                if probe or use_api or not distinct or len(rows) < options["results_wanted"]:
                    break
            except SourceError as exc:
                if probe and exc.reason == "missing_serpapi_key":
                    result.updates.pop(query_id, None)
                if probe and exc.reason.startswith("serpapi_"):
                    result.updates.pop(query_id, None)
                query_complete = False
                if use_api and exc.reason in {"serpapi_minimum_interval", "serpapi_rolling_budget_exhausted",
                        "serpapi_credit_reserve_reached", "serpapi_hourly_limit", "serpapi_run_budget_exhausted"}:
                    # Expected policy skips remain visible in quota telemetry;
                    # they are not failed searches or provider-outage evidence.
                    result.report.notes.append(exc.reason)
                    break
                result.report.queries.append(QueryOutcome(query_id, exc.status,
                    duration_seconds=round(time.monotonic() - before, 2), reason=exc.reason,
                    site=site, search_track=track["id"], phase=phase, backend="serpapi" if use_api else "jobspy"))
                failed_by_site[site] = failed_by_site.get(site, 0) + 1
                break
        if query_complete and successful_update:
            result.updates.setdefault(query_id, {}).update(successful_update)
    if failed_by_site and any(count >= 3 for count in failed_by_site.values()):
        result.report.notes.append("source_paused_after_repeated_failures")
    if options["linkedin_fetch_description"] and (any(job.platform == "Linkedin" for job in result) or QUEUE_KEY in discovery):
        enrich_linkedin_jobs(result, config, discovery, fetcher=detail_fetcher, sleep=sleep)
    if budget is not None:
        result.report.quota = dict(budget.status)
    result.report.skipped = not result.report.queries
    return result
