"""Opt-in Google Jobs API adapter; credentials never enter persisted evidence."""
import os
import re
from datetime import datetime, timedelta, timezone

import requests

from job_finder.scrapers.base import canonical_url, clean_text, parse_date
from job_finder.scrapers.common import SourceError


def posted_date(value, now=None):
    value = clean_text(value)
    absolute = parse_date(value)
    if absolute:
        return absolute.isoformat()
    match = re.fullmatch(r"(\d+)\s+(minute|hour|day|week)s? ago", value.lower())
    if match:
        scale = {"minute": 60, "hour": 3600, "day": 86400, "week": 604800}[match[2]]
        return ((now or datetime.now(timezone.utc)) - timedelta(seconds=int(match[1]) * scale)).isoformat()
    return ""


def result_row(item):
    links = [option.get("link") for option in item.get("apply_options", []) if isinstance(option, dict)]
    links.append(item.get("share_link"))
    url = ""
    for link in links:
        try:
            url = canonical_url(link)
            break
        except ValueError:
            continue
    if not url or not clean_text(item.get("title")):
        raise ValueError("Missing Google job identity")
    extensions = item.get("detected_extensions") or {}
    if not isinstance(extensions, dict):
        extensions = {}
    return {"id": clean_text(item.get("job_id")) or url, "job_url": url,
        "job_url_direct": url if links and url != item.get("share_link") else "",
        "title": clean_text(item.get("title")), "company": clean_text(item.get("company_name")),
        "location": clean_text(item.get("location")), "description": clean_text(item.get("description")),
        "is_remote": True if extensions.get("work_from_home") is True else None,
        "date_posted": posted_date(extensions.get("posted_at")),
        "job_type": clean_text(extensions.get("schedule_type"))}


def run_google_api(kwargs, timeout):
    key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not key:
        raise SourceError("unsupported", "missing_serpapi_key")
    try:
        response = requests.get("https://serpapi.com/search.json", params={"engine": "google_jobs",
            "q": kwargs.get("google_search_term") or kwargs["search_term"], "api_key": key},
            timeout=(5, min(20, timeout)), allow_redirects=False)
    except requests.Timeout as exc:
        raise SourceError("timed_out", "google_api_timeout") from exc
    except requests.RequestException as exc:
        raise SourceError("failed", "google_api_request_failed") from exc
    if response.status_code in {401, 403, 429}:
        raise SourceError("blocked", "google_api_auth_or_quota")
    if response.status_code != 200:
        raise SourceError("failed", "google_api_http_error")
    if len(response.content) > 5_000_000:
        raise SourceError("parse_failed", "google_api_response_too_large")
    try:
        payload = response.json()
        if (not isinstance(payload, dict) or payload.get("error")
                or payload.get("search_metadata", {}).get("status") != "Success"
                or not isinstance(payload.get("jobs_results"), list)):
            raise ValueError("Unverified Google API response")
        rows, invalid = [], 0
        for item in payload["jobs_results"][:kwargs["results_wanted"]]:
            try:
                rows.append(result_row(item))
            except (ValueError, TypeError, AttributeError):
                invalid += 1
        return {"rows": rows, "warnings": ["google_api_invalid_rows"] if invalid else []}
    except (ValueError, TypeError, AttributeError) as exc:
        raise SourceError("parse_failed", "google_api_invalid_response") from exc
