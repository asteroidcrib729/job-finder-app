"""Paced public LinkedIn details, independent of vacancy search availability."""
import re
import time

from bs4 import BeautifulSoup

from job_finder.scrapers.base import Job, clean_text
from job_finder.scrapers.cache import DetailCache, attempt_due
from job_finder.scrapers.common import QueryOutcome, SourceError, get_public, host_allowed
from job_finder.scrapers.descriptions import description_text, plain_description
from job_finder.scrapers.employer_details import fetch_employer_detail, posting
from job_finder.scrapers.enrichment_queue import EnrichmentQueue
from job_finder.scrapers.structured import jsonld_objects

COOLDOWN_KEY = "attempt:linkedin_details"


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    for data in jsonld_objects(soup):
        if data.get("@type") == "JobPosting" and data.get("description"):
            description = plain_description(clean_text(data["description"]))
            return {"description": description}
    node = soup.select_one(".show-more-less-html__markup")
    if node is None or not node.get_text(strip=True):
        raise SourceError("parse_failed", "linkedin_description_missing")
    # Newlines preserve requirement boundaries used by the qualification parser.
    return {"description": description_text(node)}


def fetch_detail(url, timeout):
    if not host_allowed(url, ("linkedin.com",)) or not re.search(r"/jobs/view/\d+$", url):
        raise SourceError("unsupported", "not_linkedin_vacancy")
    return parse_detail(get_public(url, ("linkedin.com",), timeout=timeout, attempts=1).text)


def apply_detail(job, payload, cached=False):
    if not isinstance(payload, dict) or not isinstance(payload.get("description"), str) or not payload["description"].strip():
        raise SourceError("parse_failed", "linkedin_description_missing")
    values = job.to_dict()
    description = payload["description"]
    # Normalize cache entries produced by earlier parser revisions too.
    if re.search(r"<br\b|&(?:amp;)?lt;", description, re.I):
        description = plain_description(description)
    values.update(description=description, description_status="full", work_mode="unknown")
    source_url = payload.get("source_url")
    if source_url and source_url != job.application_url:
        raise SourceError("parse_failed", "cached_employer_identity_changed")
    if source_url and source_url == job.application_url and posting(source_url):
        values["source_urls"] = list(dict.fromkeys([*job.source_urls, source_url]))
    enriched = Job.from_dict(values)
    if cached:
        enriched.evidence_warnings.append("cached_description")
    # Preserve current card identity, location, dates and other source fields.
    return enriched


def enrich_linkedin_jobs(result, config, discovery, fetcher=None, sleep=None, employer_fetcher=None, now=None):
    options = config["jobspy"]
    fetcher, sleep = fetcher or fetch_detail, sleep or time.sleep
    employer_fetcher = employer_fetcher or fetch_employer_detail
    queue = EnrichmentQueue(result, config, discovery, now=now)
    cache = DetailCache(discovery, "linkedin", options["linkedin_detail_cache_hours"], now=queue.now)
    for key, entry in list(queue.entries.items()):
        if entry["status"] != "pending":
            continue
        job = Job.from_dict(entry["job"])
        payload = cache.get(job.url)
        if payload:
            try:
                queue.completed(key, apply_detail(job, payload, cached=True), cached=True)
            except SourceError:
                cache.discard(job.url)
    if queue.metrics["cache_hits"]:
        result.report.queries.append(QueryOutcome("linkedin-cache", "success", converted=queue.metrics["cache_hits"],
            site="linkedin", phase="cache"))
    linkedin_paused = not attempt_due(discovery, COOLDOWN_KEY, options["linkedin_detail_retry_hours"], now=queue.now)
    if linkedin_paused and queue.entries:
        result.report.notes.append("linkedin_details_cooling_down")
        result.report.queries.append(QueryOutcome(COOLDOWN_KEY, "unverified", reason="detail_cooldown",
            site="linkedin", phase="cooldown"))
    started, attempted, successful, failures, trouble = time.monotonic(), 0, 0, 0, False
    for key in queue.ready():
        job = Job.from_dict(queue.entries[key]["job"])
        identity = posting(job.application_url) if options["employer_fallback_enabled"] else None
        if linkedin_paused and not identity:
            continue
        last_status, made_attempt, completed, closed = "failed", False, False, False
        employer_key = ""
        for service in ("linkedin", "employer"):
            if service == "linkedin" and linkedin_paused:
                continue
            if service == "employer":
                if not identity:
                    continue
                employer_key = "attempt:employer:" + identity[0]
                if not attempt_due({**discovery, **result.updates}, employer_key,
                        options["linkedin_detail_retry_hours"], now=queue.now):
                    continue
            if attempted >= queue.limit:
                result.report.notes.append("linkedin_detail_budget_exhausted")
                break
            delay = queue.delay if attempted else 0
            remaining = options["linkedin_detail_max_seconds"] - (time.monotonic() - started)
            if remaining < delay + options["linkedin_detail_timeout"] + 5:
                result.report.notes.append("linkedin_detail_deadline")
                break
            if delay:
                sleep(delay)
            if not made_attempt:
                queue.attempted(key)
                made_attempt = True
            attempted += 1
            before = time.monotonic()
            status, reason, converted = "success", "", 0
            try:
                payload = fetcher(job.url, options["linkedin_detail_timeout"]) if service == "linkedin" else (
                    employer_fetcher(job, options["linkedin_detail_timeout"]))
                enriched = apply_detail(job, payload)
                cache.put(job.url, {"description": enriched.description, "source_url": payload.get("source_url", "")})
                queue.completed(key, enriched)
                successful += 1
                converted, completed = 1, True
                if service == "linkedin":
                    failures = 0
            except SourceError as exc:
                status, reason = exc.status, exc.reason
                last_status = status
                closed = closed or status == "closed"
                cache.discard(job.url)
                if service == "linkedin":
                    failures = 0 if status == "closed" else failures + 1
                    trouble = trouble or status in {"blocked", "timed_out"} or failures >= 3
                    if status == "blocked" or (status != "closed" and failures >= 3):
                        linkedin_paused = True
                        result.updates[COOLDOWN_KEY] = {"last_attempt": queue.stamp, "reason": status}
                elif status in {"blocked", "timed_out"}:
                    result.updates[employer_key] = {"last_attempt": queue.stamp, "reason": status}
            result.report.queries.append(QueryOutcome(f"linkedin-detail:{job.job_id}:{service}", status,
                converted=converted, duration_seconds=round(time.monotonic() - before, 2), reason=reason,
                site="linkedin", search_track=job.search_track, phase="detail", backend=service))
            if service == "employer":
                queue.metrics["fallback_requests"] += 1
            if completed:
                break
        if made_attempt and not completed:
            queue.failed(key, "closed" if closed else last_status)
        if attempted >= queue.limit or "linkedin_detail_deadline" in result.report.notes:
            if queue.entries and attempted >= queue.limit:
                result.report.notes.append("linkedin_detail_budget_exhausted")
            break
    queue.publish(attempted, successful, trouble)
    cache.publish(result)
