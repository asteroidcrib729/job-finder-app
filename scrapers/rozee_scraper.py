"""Rozee structured data and conservative HTML fallback; city is never invented."""
import time
import re
import json
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from scrapers.base import Job, merge_jobs, clean_text, utc_now
from scrapers.common import SourceError, SourceResult, QueryOutcome, get_public, host_allowed
from scrapers.structured import jsonld_objects, job_from_schema, plain_html
from scrapers.cache import DetailCache, query_due, query_key

DOMAINS = ("rozee.pk",)


def bootstrap_response(html):
    """Public React bootstrap, verified 2026-09-07; decode JSON, never execute JS."""
    match = re.search(r"\b(?:var|let|const)\s+apResp\s*=\s*", html)
    if not match:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(html[match.end():])
        response = data["response"]
        if not isinstance(response.get("jobs"), dict):
            raise ValueError("Invalid jobs structure")
        return response
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SourceError("parse_failed", "invalid_bootstrap_data") from exc


def job_from_bootstrap(row):
    description = plain_html(row.get("description_raw"))
    experience = clean_text(row.get("experience_text"))
    if experience and experience.lower() not in {"fresh", "fresh graduate", "not required"}:
        description += "\nRequired experience: " + experience + "."
    city = row.get("city", "")
    if isinstance(city, list):
        city = "; ".join(city)
    country = clean_text(row.get("country"))
    link = row.get("rozeePermaLink") or row.get("permaLink")
    if not link:
        raise ValueError("Missing permalink")
    url = urljoin("https://www.rozee.pk/", link)
    if not host_allowed(url, DOMAINS):
        raise ValueError("Unexpected listing host")
    return Job(title=row["title"], company=row.get("company_name", row.get("company", "")),
        location=", ".join(filter(None, [clean_text(city), country])), url=url, platform="Rozee.pk",
        source_id=clean_text(row.get("jid")), description=description or clean_text(row.get("description")),
        description_status="full" if row.get("description_raw") else "snippet",
        posted_at=row.get("created_at", ""), expires_at=row.get("applyBy", ""), date_source="bootstrap_created_at",
        job_type=row.get("type", ""), active_status="active",
        # Only display-public salary fields; do not expose Hide/search-index fields.
        salary_min=row.get("salaryN_exact"), salary_max=row.get("salaryT_exact"),
        salary_text=clean_text(row.get("salaryTHide_exact_g")),
        salary_currency=clean_text(row.get("currency_unit")) if row.get("salaryT_exact") else "",
        salary_source="disclosed" if row.get("salaryT_exact") else "unknown")


def parse_rozee(html, url):
    bootstrap = bootstrap_response(html)
    if bootstrap is not None:
        jobs, invalid = [], 0
        for bucket in bootstrap["jobs"].values():
            if not isinstance(bucket, list):
                invalid += 1
                continue
            for row in bucket:
                try:
                    jobs.append(job_from_bootstrap(row))
                except (TypeError, ValueError, KeyError, AttributeError):
                    invalid += 1
        return merge_jobs(jobs), invalid
    soup = BeautifulSoup(html, "html.parser")
    jobs, invalid = [], 0
    for data in jsonld_objects(soup):
        types = data.get("@type", [])
        if "JobPosting" not in (types if isinstance(types, list) else [types]):
            continue
        try:
            job = job_from_schema(data, url, "Rozee.pk")
            if not host_allowed(job.url, DOMAINS):
                raise ValueError("Unexpected listing host")
            jobs.append(job)
        except (TypeError, ValueError, AttributeError):
            invalid += 1
    if jobs:
        return jobs, invalid
    # These selectors are a fallback, not proof of current live compatibility.
    for card in soup.select(".job, .s-box"):
        anchor = card.select_one("a.jtitle[href], .jtitle a[href], h3 a[href]")
        if anchor is None:
            continue
        link = urljoin(url, anchor.get("href", ""))
        if not host_allowed(link, DOMAINS):
            invalid += 1
            continue
        def value(selector):
            element = card.select_one(selector)
            return element.get_text(" ", strip=True) if element else ""
        date = card.select_one("time[datetime]")
        try:
            jobs.append(Job(title=anchor.get_text(" ", strip=True),
                company=value(".cname, .company-name, .comp-name"),
                location=value(".location, .job-location, .jloc"), url=link, platform="Rozee.pk",
                description=value(".description, .job-description, .jdesc"),
                description_status="snippet", posted_at=date.get("datetime", "") if date else "",
                date_source="card" if date else "unknown"))
        except ValueError:
            invalid += 1
    return merge_jobs(jobs), invalid


def next_offset(bootstrap, current):
    if not bootstrap:
        return None
    pagination = bootstrap.get("pagination", {})
    if not isinstance(pagination, dict) or not isinstance(pagination.get("list", []), list):
        raise SourceError("parse_failed", "invalid_pagination")
    for item in pagination.get("list", []):
        if not isinstance(item, dict):
            raise SourceError("parse_failed", "invalid_pagination")
        if str(item.get("lang", "")).lower() == "next":
            offset = item.get("fpn")
            if type(offset) is not int or offset <= current or offset > 10000:
                raise SourceError("parse_failed", "invalid_next_offset")
            return offset
    return None


def fetch_rozee_jobs(config, discovery=None):
    result = SourceResult("Rozee.pk")
    options = config["local_scrapers"]
    if not options["rozee_enabled"]:
        result.report.skipped = True
        return result
    discovery = discovery or {}
    cache = DetailCache(discovery, "rozee", options["detail_cache_hours"])
    details, checked = 0, set()
    keywords = sorted(options["keywords"], key=lambda keyword: discovery.get(
        query_key("rozee", keyword), {}).get("last_success", ""))
    blocked = False
    for keyword in keywords[:options["max_queries"]]:
        query_id = query_key("rozee", keyword)
        if not query_due(discovery, query_id, options["interval_hours"]):
            result.report.notes.append(query_id + ":not_due")
            continue
        # Current public city mapping: Karachi=1184. Still validate each listing.
        base_url = "https://www.rozee.pk/job/jsearch/q/" + quote(keyword.replace(" ", "-"), safe="") + "/fc/1184"
        offset, query_seen, complete = 0, set(), True
        for page_index in range(options["max_pages"]):
            url = base_url + (f"/fpn/{offset}" if offset else "")
            started = time.monotonic()
            try:
                response = get_public(url, DOMAINS, timeout=options["timeout"])
                jobs, invalid = parse_rozee(response.text, url)
                bootstrap = bootstrap_response(response.text)
                explicit_empty = bootstrap is not None and bootstrap.get("numFound") == 0
                if not jobs and not explicit_empty and not any(text in response.text.lower() for text in ("no jobs found", "no results found", "0 jobs found")):
                    raise SourceError("parse_failed", "expected_listing_markup_missing")
                fresh = [job for job in jobs if job.job_id not in query_seen]
                detail_failed = False
                query_seen.update(job.job_id for job in jobs)
                for index, job in enumerate(fresh):
                    job.query_id, job.search_track = query_id, "karachi_local"
                    if job.description_status == "full":
                        continue
                    payload = cache.get(job.url)
                    if payload:
                        try:
                            enriched = Job.from_dict(payload)
                            # Current listing fields take precedence; cache supplies only description.
                            if enriched.url != job.url or enriched.description_status != "full":
                                raise ValueError("Invalid cached detail")
                            job.description, job.description_status = enriched.description, "full"
                            job.evidence_warnings.append("cached_description")
                            continue
                        except (ValueError, TypeError, AttributeError):
                            cache.discard(job.url)
                    if blocked or job.url in checked or details >= options["max_details"]:
                        continue
                    checked.add(job.url)
                    details += 1
                    try:
                        detail = get_public(job.url, DOMAINS, timeout=options["timeout"])
                        enriched, _ = parse_rozee(detail.text, job.url)
                        matching = next((item for item in enriched if item.url == job.url and item.description_status == "full"), None)
                        if matching:
                            matching.aliases.extend(job.aliases)
                            matching.query_id, matching.search_track = query_id, "karachi_local"
                            fresh[index] = matching
                            cache.put(job.url, matching.to_dict())
                        else:
                            job.description_status = "fetch_failed"
                            complete = False
                            detail_failed = True
                            result.report.notes.append("detail_expected_description_missing")
                    except SourceError as exc:
                        job.active_status = "closed" if exc.status == "closed" else "unverified"
                        job.description_status = "fetch_failed"
                        cache.discard(job.url)
                        result.report.notes.append("detail_" + exc.status)
                        complete = False
                        detail_failed = True
                        blocked = exc.status == "blocked"
                result.extend(fresh)
                repeated = bool(jobs) and not fresh
                status = "partial" if invalid or repeated or detail_failed else "success" if jobs else "valid_empty"
                result.report.queries.append(QueryOutcome(query_id + f":{offset}", status,
                    len(jobs), len(fresh), invalid, round(time.monotonic() - started, 2),
                    "repeated_page" if repeated else ""))
                complete = complete and not invalid and not repeated
                if not jobs or repeated or blocked:
                    break
                following = next_offset(bootstrap, offset)
                if following is None:
                    break
                if page_index + 1 == options["max_pages"]:
                    result.report.notes.append(query_id + ":page_budget_reached")
                offset = following
            except SourceError as exc:
                complete = False
                result.report.queries.append(QueryOutcome(query_id + f":{offset}", exc.status,
                    duration_seconds=round(time.monotonic() - started, 2), reason=exc.reason))
                blocked = exc.status == "blocked"
                break
        if complete:
            result.updates[query_id] = {"last_success": utc_now(), "unique": len(query_seen)}
        if blocked:
            break
    cache.publish(result)
    result.report.skipped = not result.report.queries
    return result
