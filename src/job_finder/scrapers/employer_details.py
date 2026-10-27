"""Exact public employer-posting fallback; never discover or guess a company URL."""
import re
from urllib.parse import urlsplit

from job_finder.scrapers.base import canonical_url, normalized
from job_finder.scrapers.common import SourceError, get_public
from job_finder.scrapers.descriptions import plain_description


def posting(application_url):
    try:
        parts = urlsplit(canonical_url(application_url))
    except ValueError:
        return None
    match = re.fullmatch(r"/([A-Za-z0-9_-]+)/jobs/([0-9]+)", parts.path)
    if parts.hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and match:
        return "greenhouse", match[1], match[2]
    match = re.fullmatch(r"/([A-Za-z0-9_-]+)/([A-Za-z0-9-]{10,80})", parts.path)
    if parts.hostname == "jobs.lever.co" and match:
        return "lever", match[1], match[2]
    return None


def same_title(left, right):
    return re.sub(r"[^a-z0-9]+", " ", normalized(left)).strip() == re.sub(
        r"[^a-z0-9]+", " ", normalized(right)).strip()


def fetch_employer_detail(job, timeout):
    identity = posting(job.application_url)
    if identity is None:
        raise SourceError("unsupported", "employer_url_not_supported")
    provider, board, identifier = identity
    if provider == "greenhouse":
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{identifier}?content=true"
        response = get_public(url, ("boards-api.greenhouse.io",), timeout=timeout, attempts=1)
    else:
        url = f"https://api.lever.co/v0/postings/{board}/{identifier}?mode=json"
        response = get_public(url, ("api.lever.co",), timeout=timeout, attempts=1)
    try:
        data = response.json()
        if not isinstance(data, dict) or str(data.get("id")) != identifier:
            raise ValueError("Posting identity mismatch")
        title = data.get("title") if provider == "greenhouse" else data.get("text")
        if not same_title(title, job.title):
            raise ValueError("Posting title mismatch")
        published = data.get("absolute_url") if provider == "greenhouse" else data.get("hostedUrl")
        if posting(published) != identity:
            raise ValueError("Posting URL mismatch")
        if provider == "greenhouse":
            description = plain_description(data.get("content", ""))
        else:
            pieces = [data.get("description", "")]
            for item in data.get("lists", []):
                pieces.extend([item.get("text", ""), item.get("content", "")])
            pieces.append(data.get("additional", ""))
            description = plain_description("\n".join(pieces))
        if not description:
            raise ValueError("Missing employer description")
        return {"description": description, "source_url": canonical_url(job.application_url)}
    except (ValueError, TypeError, AttributeError) as exc:
        raise SourceError("parse_failed", "employer_posting_unverified") from exc
