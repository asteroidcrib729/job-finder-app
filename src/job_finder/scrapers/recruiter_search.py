"""Bounded backend fallback with sanitized, individual search outcomes."""
import logging
import re
import time
from contextlib import contextmanager

from job_finder.scrapers.base import utc_now
from job_finder.scrapers.cache import attempt_due
from job_finder.scrapers.common import QueryOutcome


@contextmanager
def quiet_search_logs():
    """Provider exceptions can contain challenge URLs; emit classified codes only."""
    logger = logging.getLogger("ddgs")
    previous = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        yield
    finally:
        logger.setLevel(previous)


def classify_search_error(exc):
    from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException
    text = str(exc).lower()
    if isinstance(exc, RatelimitException) or re.search(r"\b(?:403|429|captcha)\b", text):
        return "blocked", "search_rate_limited"
    if isinstance(exc, TimeoutException) or "timed out" in text or "timeout" in text:
        return "timed_out", "search_timeout"
    if isinstance(exc, DDGSException):
        if text.strip().rstrip(".") == "no results found":
            # This library also uses this exception when backends return no
            # parseable results. It cannot establish a genuinely empty search.
            return "unverified", "search_no_results_unconfirmed"
        return "failed", "search_provider_error"
    return "failed", "search_unexpected_error"


def simplified_query(query):
    site = re.search(r"site:[^\s]+", query)
    place = next((value for value in ("Karachi", "Remote") if value.lower() in query.lower()), "")
    skill = next((value for value in ("React", "Python", "Node", "Next.js") if value.lower() in query.lower()), "software")
    return " ".join(filter(None, [site[0] if site else "site:linkedin.com/posts", place, skill, "hiring"]))


def search_posts(search, query, options, result, discovery, budget, attempt_limit=None, backend_offset=0):
    """Return rows plus whether provider discovery was actually verified."""
    variants = list(dict.fromkeys([query, simplified_query(query)]))
    backends = list(options["search_backends"])
    backends.sort(key=lambda backend: discovery.get("health:posts:" + backend, {}).get("last_success", ""), reverse=True)
    offset = backend_offset % len(backends)
    backends = backends[offset:] + backends[:offset]
    used_here = 0
    confirmed_empty = False
    for backend in backends:
        for variant_index, variant in enumerate(variants):
            key = "attempt:posts:" + backend
            state = {**discovery, **result.updates}
            if not attempt_due(state, key, options["retry_hours"]):
                result.report.notes.append(backend + ":search_cooldown")
                continue
            if budget["used"] >= options["max_search_attempts"]:
                result.report.notes.append("post_search_budget_exhausted")
                return [], confirmed_empty
            if attempt_limit is not None and used_here >= attempt_limit:
                result.report.notes.append("post_query_budget_exhausted")
                return [], confirmed_empty
            budget["used"] += 1
            used_here += 1
            before = time.monotonic()
            try:
                # Date filtering differs between search engines. A relaxed
                # fallback still requires locally checked post date evidence.
                rows = list(search.text(variant, timelimit=None if variant_index else "m",
                    max_results=options["max_results"], backend=backend))
                status, reason = ("success", "") if rows else ("valid_empty", "")
            except Exception as exc:
                rows = []
                status, reason = classify_search_error(exc)
                if status in {"blocked", "timed_out", "failed"}:
                    result.updates[key] = {"last_attempt": utc_now(), "reason": reason}
            result.report.queries.append(QueryOutcome(
                f"posts-search:{budget['used']}", status, raw=len(rows),
                duration_seconds=round(time.monotonic() - before, 2), reason=reason,
                phase="discovery", backend=backend))
            if variant_index:
                result.report.notes.append(backend + ":simplified_query")
            if rows:
                result.updates["health:posts:" + backend] = {"last_success": utc_now()}
                return rows, True
            confirmed_empty = confirmed_empty or status == "valid_empty"
    return [], confirmed_empty
