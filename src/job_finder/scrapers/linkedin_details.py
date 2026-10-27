"""Paced public LinkedIn details, independent of vacancy search availability."""
import re
import time
from collections import defaultdict, deque

from bs4 import BeautifulSoup

from job_finder.scrapers.base import Job, clean_text, utc_now
from job_finder.scrapers.cache import DetailCache, attempt_due
from job_finder.scrapers.common import QueryOutcome, SourceError, get_public, host_allowed
from job_finder.scrapers.structured import jsonld_objects

COOLDOWN_KEY = "attempt:linkedin_details"


def description_text(node):
    """Keep paragraph/list boundaries without splitting inline requirements."""
    for tag in node.find_all(["script", "style"]):
        tag.decompose()
    for tag in node.find_all("br"):
        tag.replace_with("\n")
    for tag in node.find_all(["p", "li", "div", "h1", "h2", "h3", "h4"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
    return "\n".join(re.sub(r"[ \t\r\f\v]+", " ", line).strip()
        for line in node.get_text(" ").splitlines() if line.strip())


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    for data in jsonld_objects(soup):
        if data.get("@type") == "JobPosting" and data.get("description"):
            description = description_text(BeautifulSoup(clean_text(data["description"]), "html.parser"))
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
    values.update(description=payload["description"], description_status="full", work_mode="unknown")
    enriched = Job.from_dict(values)
    if cached:
        enriched.evidence_warnings.append("cached_description")
    # Preserve current card identity, location, dates and other source fields.
    return enriched


def enrich_linkedin_jobs(result, config, discovery, fetcher=None, sleep=None):
    options = config["jobspy"]
    fetcher, sleep = fetcher or fetch_detail, sleep or time.sleep
    cache = DetailCache(discovery, "linkedin", options["linkedin_detail_cache_hours"])
    queue = defaultdict(deque)
    by_url = defaultdict(list)
    for index, job in enumerate(result):
        if job.platform.lower() != "linkedin" or job.description_status == "full":
            continue
        by_url[job.url].append(index)
    # Favor software/junior titles, then share the bounded queue across tracks.
    ordered = sorted(by_url, key=lambda url: bool(re.search(
        r"\b(?:senior|lead|principal|manager|director)\b", result[by_url[url][0]].title, re.I)))
    for url in ordered:
        job = result[by_url[url][0]]
        payload = cache.get(url)
        if payload:
            try:
                for index in by_url[url]:
                    result[index] = apply_detail(result[index], payload, cached=True)
                continue
            except SourceError:
                cache.discard(url)
        queue[job.search_track].append(url)
    paused = not attempt_due(discovery, COOLDOWN_KEY, options["linkedin_detail_retry_hours"])
    if paused:
        result.report.notes.append("linkedin_details_cooling_down")
        if queue:
            result.report.queries.append(QueryOutcome(COOLDOWN_KEY, "unverified",
                reason="detail_cooldown", site="linkedin", phase="cooldown"))
    started, attempted, failures = time.monotonic(), 0, 0
    while queue and not paused:
        for track in list(queue):
            if attempted >= options["linkedin_max_details"]:
                result.report.notes.append("linkedin_detail_budget_exhausted")
                paused = True
                break
            remaining = options["linkedin_detail_max_seconds"] - (time.monotonic() - started)
            delay = options["linkedin_detail_delay"] if attempted else 0
            if remaining < delay + options["linkedin_detail_timeout"] + 5:
                result.report.notes.append("linkedin_detail_deadline")
                paused = True
                break
            if delay:
                sleep(delay)
            url = queue[track].popleft()
            if not queue[track]:
                del queue[track]
            attempted += 1
            before = time.monotonic()
            status, reason, converted = "success", "", 0
            try:
                payload = fetcher(url, options["linkedin_detail_timeout"])
                for index in by_url[url]:
                    result[index] = apply_detail(result[index], payload)
                cache.put(url, {"description": payload["description"]})
                converted = 1
                failures = 0
            except SourceError as exc:
                status, reason = exc.status, exc.reason
                failures = 0 if status == "closed" else failures + 1
                cache.discard(url)
                for index in by_url[url]:
                    result[index].description_status = "fetch_failed"
                    if status == "closed":
                        result[index].active_status = "closed"
                if status == "blocked" or (status != "closed" and failures >= 3):
                    paused = True
                    result.updates[COOLDOWN_KEY] = {"last_attempt": utc_now(), "reason": status}
            result.report.queries.append(QueryOutcome("linkedin-detail:" + result[by_url[url][0]].job_id,
                status, converted=converted, duration_seconds=round(time.monotonic() - before, 2),
                reason=reason, site="linkedin", search_track=track, phase="detail"))
            if paused:
                break
    cache.publish(result)
