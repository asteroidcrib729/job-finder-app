"""Bounded public GET requests and structured source health."""
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit, urljoin
import requests
from scrapers.base import canonical_url, optional_number


class SourceError(RuntimeError):
    def __init__(self, status, reason):
        super().__init__(reason)
        self.status, self.reason = status, reason


@dataclass
class QueryOutcome:
    query_id: str
    status: str
    raw: int = 0
    converted: int = 0
    invalid: int = 0
    duration_seconds: float = 0
    reason: str = ""


@dataclass
class SourceReport:
    source: str
    queries: list[QueryOutcome] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    skipped: bool = False

    @property
    def status(self):
        if self.skipped:
            return "skipped"
        if not self.queries:
            return "unverified"
        good = [q for q in self.queries if q.status in {"success", "valid_empty"}]
        if len(good) == len(self.queries):
            return "success" if any(q.converted for q in good) else "valid_empty"
        return "partial" if good or any(q.converted for q in self.queries) else "failed"

    def to_dict(self):
        return {**asdict(self), "status": self.status}


class SourceResult(list):
    def __init__(self, source, jobs=()):
        super().__init__(jobs)
        self.report = SourceReport(source)
        self.updates = {}


def host_allowed(url, domains):
    try:
        host = urlsplit(canonical_url(url)).hostname
        return any(host == domain or host.endswith("." + domain) for domain in domains)
    except ValueError:
        return False


def get_public(url, domains, timeout=12, session=None, attempts=2):
    """No authenticated requests. Redirects stay within the source allowlist."""
    client = session or requests
    current = url
    for redirect in range(4):
        if not host_allowed(current, domains):
            raise SourceError("unsupported", "unexpected_redirect_host")
        for attempt in range(attempts):
            try:
                response = client.get(current, timeout=(5, timeout), allow_redirects=False)
            except requests.Timeout as exc:
                if attempt + 1 == attempts:
                    raise SourceError("timed_out", "request_timeout") from exc
                continue
            except requests.RequestException as exc:
                raise SourceError("failed", type(exc).__name__) from exc
            if response.status_code in {429, 500, 502, 503, 504} and attempt + 1 < attempts:
                delay = optional_number(response.headers.get("Retry-After"))
                if delay is not None and delay > 10:
                    raise SourceError("blocked", "retry_after_exceeds_budget")
                time.sleep(max(0, delay) if delay is not None else 1)
                continue
            break
        if response.status_code in {301, 302, 303, 307, 308}:
            current = urljoin(current, response.headers.get("Location", ""))
            continue
        if response.status_code in {401, 403, 429, 999}:
            raise SourceError("blocked", f"http_{response.status_code}")
        if response.status_code in {404, 410}:
            raise SourceError("closed", f"http_{response.status_code}")
        if response.status_code != 200:
            raise SourceError("failed", f"http_{response.status_code}")
        if len(response.content) > 5_000_000:
            raise SourceError("parse_failed", "response_too_large")
        sample = response.text[:15000].lower()
        if any(marker in sample for marker in ("verify you are human", "cf-chl-", "captcha-container", "access denied", "authwall")):
            raise SourceError("blocked", "challenge_or_login")
        return response
    raise SourceError("blocked", "redirect_limit")
