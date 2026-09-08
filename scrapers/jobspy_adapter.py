"""Source-specific, budgeted JobSpy discovery. Queries never establish job facts."""
import hashlib
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from scrapers.base import Job, clean_text, optional_bool, optional_number, parse_date, canonical_url
from scrapers.common import SourceError, SourceResult, QueryOutcome
from scrapers.cache import query_due

logger = logging.getLogger(__name__)


def run_query(kwargs, timeout):
    try:
        completed = subprocess.run([sys.executable, "-m", "scrapers.jobspy_worker"],
            input=json.dumps(kwargs), capture_output=True, text=True, encoding="utf-8",
            cwd=Path(__file__).resolve().parent.parent, timeout=timeout)
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
        kwargs["linkedin_fetch_description"] = options["linkedin_fetch_description"]
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
    return Job(
        title=clean_text(row.get("title")), company=clean_text(row.get("company")),
        location=clean_text(row.get("location")), url=clean_text(row.get("job_url")),
        platform=site.capitalize(), description=description, source_id=clean_text(row.get("id")),
        application_url=application, is_remote=optional_bool(row.get("is_remote")),
        posted_at=clean_text(row.get("date_posted")), date_source="source",
        description_status="full" if description else "missing",
        job_level=clean_text(row.get("job_level")), job_type=clean_text(row.get("job_type")),
        salary_min=optional_number(row.get("min_amount")), salary_max=optional_number(row.get("max_amount")),
        salary_currency=currency, salary_interval=clean_text(row.get("interval")), salary_source=salary_evidence,
        query_id=query_id, search_track=track["id"], active_status="unknown")


def fetch_jobspy_jobs(config, discovery=None, runner=None):
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
    # Rotate tracks/sites inside each keyword so a budget does not starve remote/local.
    plans = [(keyword, track, site) for keyword in config["search_keywords"]
             for track in config["search_tracks"] for site in track["sites"]]
    # Least recently successful queries get their turn if a run exhausts its budget.
    def identity(plan):
        keyword, track, site = plan
        return "jobspy:" + hashlib.sha256(f"{site}|{track}|{keyword}".encode()).hexdigest()[:16]
    plans.sort(key=lambda plan: discovery.get(identity(plan), {}).get("last_success", ""))
    for plan in plans:
        keyword, track, site = plan
        query_id = identity(plan)
        previous_result = discovery.get(query_id, {})
        low_yield = previous_result.get("qualified") == 0 and previous_result.get("review") == 0
        interval = max(options["interval_hours"], options["low_yield_interval_hours"]) if low_yield else options["interval_hours"]
        if not query_due(discovery, query_id, interval):
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
                return result
            attempted += 1
            before = time.monotonic()
            previous = parse_date(discovery.get(query_id, {}).get("last_success"))
            hours = options["hours_old"]
            if previous:
                elapsed = (datetime.now(timezone.utc) - previous).total_seconds() / 3600
                hours = min(720, max(hours, int(elapsed + 24)))
            kwargs = build_query(config, track, keyword, site, page * options["results_wanted"], hours)
            logger.info("JobSpy %s %s: %s (page %d)", site, track["id"], keyword, page + 1)
            try:
                payload = runner(kwargs, min(options["query_timeout"], remaining))
                rows = payload["rows"]
                if not isinstance(rows, list):
                    raise SourceError("parse_failed", "rows_not_list")
                warnings = payload.get("warnings", [])
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
                status = "partial" if warnings or invalid else "success" if rows else "valid_empty"
                if not rows and warnings == ["google_jobs_cursor_missing"]:
                    status = "unverified"
                result.report.queries.append(QueryOutcome(query_id, status, len(rows), len(converted), invalid,
                    round(time.monotonic() - before, 2), ",".join(warnings), site, track["id"]))
                if warnings:
                    logger.warning("JobSpy %s %s: %s", site, track["id"], ",".join(warnings))
                if warnings:
                    failed_by_site[site] = failed_by_site.get(site, 0) + 1
                else:
                    failed_by_site[site] = 0
                if status in {"success", "valid_empty"}:
                    successful_update = {"last_success": datetime.now(timezone.utc).isoformat(),
                        "raw": len(rows), "unique": len(distinct)}
                else:
                    query_complete = False
                if not distinct or len(rows) < options["results_wanted"]:
                    break
            except SourceError as exc:
                query_complete = False
                result.report.queries.append(QueryOutcome(query_id, exc.status,
                    duration_seconds=round(time.monotonic() - before, 2), reason=exc.reason,
                    site=site, search_track=track["id"]))
                failed_by_site[site] = failed_by_site.get(site, 0) + 1
                break
        if query_complete and successful_update:
            result.updates[query_id] = successful_update
    if failed_by_site and any(count >= 3 for count in failed_by_site.values()):
        result.report.notes.append("source_paused_after_repeated_failures")
    result.report.skipped = not result.report.queries
    return result
