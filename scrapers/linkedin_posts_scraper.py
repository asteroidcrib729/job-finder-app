"""Recruiter announcements are review leads, not verified single vacancies."""
import re
import time
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from scrapers.base import Job, canonical_url, clean_text, utc_now
from scrapers.common import SourceError, SourceResult, QueryOutcome, get_public, host_allowed
from scrapers.cache import DetailCache, query_due, query_key
from scrapers.post_roles import split_post_roles
from scrapers.structured import jsonld_objects

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"


def valid_post_url(url):
    return host_allowed(url, ("linkedin.com",)) and any(
        urlsplit(url).path.startswith(path) for path in ("/posts/", "/feed/update/"))


def inspect_post(url, timeout=8):
    if not valid_post_url(url):
        raise SourceError("unsupported", "not_linkedin_post")
    response = get_public(url, ("linkedin.com",), timeout=timeout)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(" ", strip=True)
    if any(marker in text.lower() for marker in ("this post was deleted", "post not found")):
        return {"status": "closed", "text": "", "posted_at": ""}
    posted = ""
    content = ""
    for data in jsonld_objects(soup):
        if data.get("@type") in ("SocialMediaPosting", "Article"):
            content = clean_text(data.get("articleBody"))
            posted = clean_text(data.get("datePublished"))
            break
    if not content:
        node = soup.select_one(".attributed-text-segment-list__content, .share-update-card__update-text")
        content = node.get_text("\n", strip=True) if node else ""
    return {"status": "active" if content else "unverified", "text": content, "posted_at": posted}


def is_post_active_and_recent(url, text=""):
    """Compatibility check; unknown publication dates cannot be called recent."""
    from datetime import datetime, timezone
    from scrapers.base import parse_date
    try:
        post = inspect_post(url)
    except SourceError:
        return False
    date = parse_date(post["posted_at"])
    return bool(post["status"] == "active" and date and 0 <= (datetime.now(timezone.utc) - date).days <= 30)


def fetch_linkedin_plain_posts(config, discovery=None):
    result = SourceResult("LinkedIn Post")
    options = config["linkedin_posts"]
    if not options["enabled"]:
        result.report.skipped = True
        return result
    discovery = discovery or {}
    queries = [query for query in options["queries"] if query_due(
        discovery, query_key("posts", query), options["interval_hours"])]
    cache = DetailCache(discovery, "posts", options["detail_cache_hours"])
    if not queries:
        result.report.skipped = True
        result.report.notes.append("queries_not_due")
        cache.publish(result)
        return result
    try:
        from ddgs import DDGS
    except ImportError:
        result.report.queries.append(QueryOutcome("posts", "unsupported", reason="ddgs_missing"))
        return result
    checked, seen, blocked = 0, set(), False
    with DDGS(timeout=options["timeout"]) as search:
        for query in queries:
            before = time.monotonic()
            query_id = query_key("posts", query)
            try:
                rows = list(search.text(query, timelimit="m", max_results=options["max_results"],
                                        backend=",".join(options["search_backends"])))
                invalid, ignored, count, incomplete = 0, 0, 0, False
                for row in rows:
                    if not isinstance(row, dict):
                        invalid += 1
                        continue
                    url = clean_text(row.get("href"))
                    if not valid_post_url(url):
                        ignored += 1
                        continue
                    url = canonical_url(url)
                    if url in seen:
                        continue
                    seen.add(url)
                    title = clean_text(row.get("title")).replace(" | LinkedIn", "")
                    snippet = clean_text(row.get("body"))
                    post = cache.get(url)
                    if post and (post.get("status") not in {"active", "closed"} or
                                 not all(isinstance(post.get(key), str) for key in ("text", "posted_at"))):
                        cache.discard(url)
                        post = None
                    cached = post is not None
                    post = post or {"status": "unverified", "text": "", "posted_at": ""}
                    if not cached and not blocked and checked < options["max_checks"]:
                        checked += 1
                        try:
                            post = inspect_post(url, options["timeout"])
                            if post["status"] in {"active", "closed"}:
                                cache.put(url, post)
                        except SourceError as exc:
                            post["status"] = "closed" if exc.status == "closed" else "unverified"
                            result.report.notes.append("post_" + exc.status)
                            blocked = exc.status == "blocked"
                            cache.discard(url)
                    incomplete = incomplete or post["status"] == "unverified"
                    text = post["text"] or snippet
                    # Only explicitly stated location; the query is not evidence.
                    location = ""
                    for city in ("Karachi", "Lahore", "Islamabad", "Hyderabad", "Rawalpindi"):
                        if re.search(r"\b" + city + r"\b", text + " " + title, re.I):
                            location = city + ", Pakistan"
                            break
                    emails = re.findall(EMAIL_REGEX, post["text"])
                    emails = [email for email in emails if not email.endswith(("@example.com", "@domain.com"))]
                    try:
                        result.append(Job(title=title or "Recruiter hiring announcement",
                            company="", location=location, url=url, platform="LinkedIn Post",
                            description=text, description_status="full" if post["text"] else "snippet",
                            kind="lead", posted_at=post["posted_at"], date_source="post_metadata",
                            active_status=post["status"], recruiter_email=emails[0] if emails else "",
                            query_id=query_id, search_track="recruiter_leads",
                            evidence_warnings=["cached_post"] if cached else []))
                        count += 1
                    except ValueError:
                        invalid += 1
                if ignored:
                    result.report.notes.append(f"ignored_non_post_results:{ignored}")
                result.report.queries.append(QueryOutcome(query_id, "partial" if invalid or incomplete else "success" if count else "valid_empty",
                    len(rows), count, invalid, round(time.monotonic() - before, 2),
                    "unverified_posts" if incomplete else ""))
                if not invalid and not incomplete:
                    result.updates[query_id] = {"last_success": utc_now(), "unique": count}
            except Exception as exc:
                # Classify known provider errors without logging raw URLs or challenge tokens.
                from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException
                status, reason = "failed", type(exc).__name__
                if isinstance(exc, RatelimitException):
                    status, reason = "blocked", "search_rate_limited"
                elif isinstance(exc, TimeoutException):
                    status, reason = "timed_out", "search_timeout"
                elif isinstance(exc, DDGSException):
                    reason = "search_providers_unavailable"
                result.report.queries.append(QueryOutcome(query_id, status,
                    duration_seconds=round(time.monotonic() - before, 2), reason=reason))
    result[:] = [role for post in result for role in split_post_roles(post)]
    cache.publish(result)
    return result
