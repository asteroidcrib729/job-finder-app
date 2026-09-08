"""Source-independent job data, identity, and evidence normalization."""
import hashlib
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "nat", "none", "<na>", "null"} else text


def normalized(text) -> str:
    text = unicodedata.normalize("NFKD", clean_text(text)).lower()
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip()


def optional_bool(value):
    text = clean_text(value).lower()
    return True if text in {"true", "1", "yes"} else False if text in {"false", "0", "no"} else None


def optional_number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_date(value):
    text = clean_text(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        return None


def canonical_url(value) -> str:
    text = clean_text(value)
    try:
        parts = urlsplit(text)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError("Expected an HTTP(S) listing URL without credentials")
        host, port = parts.hostname.lower(), parts.port
    except ValueError as exc:
        raise ValueError("Invalid listing URL") from exc
    if any(c.isspace() for c in text):
        raise ValueError("Invalid listing URL whitespace")
    path = parts.path.rstrip("/") or "/"
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"trk", "trackingid", "refid"}]
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        match = re.search(r"/jobs/view/(?:[^/]*-)?(\d+)$", path)
        if match:
            host, path, query = "www.linkedin.com", "/jobs/view/" + match[1], []
    authority = host + (f":{port}" if port and port not in {80, 443} else "")
    return urlunsplit(("https", authority, path, urlencode(sorted(query)), ""))


def legacy_id(title, company, url, platform):
    raw = f"{platform.lower()}_{title.lower()}_{company.lower()}_{url.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


NEGATED_REMOTE = re.compile(
    r"\b(?:no|not|non)[ -]?remote\b|\b(?:remote(?: work)?|work from home)\s+(?:is\s+)?(?:not (?:permitted|allowed|available|offered)|unavailable)\b"
    r"|\b(?:on[ -]?site|in[ -]?office)\s+only\b", re.I)


def infer_work_mode(title, location, description, reported=None):
    text = normalized(f"{title} {location} {description}")
    if NEGATED_REMOTE.search(text):
        return "on_site"
    if re.search(r"\bhybrid\b", text):
        return "hybrid"
    if reported is False:
        return "on_site"
    heading = normalized(f"{title} {location}")
    remote_description = re.search(r"\b(?:fully|100%|work(?:ing)?)\s+remote\b|\bremote\s+(?:role|position|job|work|opportunity)\b|\b(?:role|position|job)\s+is\s+remote\b|\bwork from home\b|\bwfh\b", normalized(description))
    if reported is True or re.search(r"\bremote\b", heading) or remote_description:
        return "remote"
    if re.search(r"\bon[ -]?site\b|\bin[ -]?office\b", text):
        return "on_site"
    return "unknown"


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    platform: str
    date_posted: str = ""
    is_remote: bool | None = None
    description: str = ""
    job_id: str | None = None
    recruiter_email: str = ""
    is_priority_location: bool = False
    source_id: str = ""
    application_url: str = ""
    aliases: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    work_mode: str = "unknown"
    description_status: str = "missing"
    job_level: str = ""
    job_type: str = ""
    kind: str = "vacancy"
    source_title: str = ""
    source_description: str = ""
    posted_at: str = ""
    expires_at: str = ""
    first_seen_at: str = field(default_factory=utc_now)
    last_seen_at: str = field(default_factory=utc_now)
    date_source: str = "unknown"
    active_status: str = "unknown"
    candidate_locations: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str = ""
    salary_interval: str = ""
    salary_text: str = ""
    salary_source: str = "unknown"
    query_id: str = ""
    search_track: str = ""
    evidence_warnings: list[str] = field(default_factory=list)
    decision: dict = field(default_factory=dict)

    def __post_init__(self):
        for name in ("title", "company", "location", "description", "platform", "source_id",
                     "date_posted", "posted_at", "expires_at", "candidate_locations", "salary_text",
                     "salary_currency", "salary_interval", "job_level", "job_type", "recruiter_email"):
            setattr(self, name, clean_text(getattr(self, name)))
        if not self.title or not self.platform:
            raise ValueError("Job title and platform are required")
        old_id = legacy_id(self.title, self.company, clean_text(self.url), self.platform)
        self.url = canonical_url(self.url)
        self.aliases = list(dict.fromkeys([*self.aliases, old_id]))
        self.source_urls = list(dict.fromkeys([*self.source_urls, self.url]))
        if self.application_url:
            self.application_url = canonical_url(self.application_url)
        namespace = re.sub(r"[^a-z0-9]", "", self.platform.lower())
        if not self.job_id:
            identity = self.source_id or self.url
            self.job_id = namespace + ":" + hashlib.sha256(identity.encode()).hexdigest()[:24]
        if self.work_mode not in {"remote", "on_site", "hybrid", "unknown"}:
            raise ValueError("Invalid work mode")
        inferred = infer_work_mode(self.title, self.location, self.description, optional_bool(self.is_remote))
        if self.work_mode == "unknown":
            self.work_mode = inferred
        elif self.work_mode == "remote" and inferred == "on_site":
            self.evidence_warnings.append("contradictory_work_mode")
            self.work_mode = "unknown"
        self.is_remote = None if self.work_mode == "unknown" else self.work_mode == "remote"
        if not self.description:
            self.description_status = "missing"
        self.salary_min = optional_number(self.salary_min)
        self.salary_max = optional_number(self.salary_max)
        self.salary_currency = self.salary_currency.upper()
        posted = parse_date(self.posted_at or self.date_posted)
        self.posted_at = posted.isoformat() if posted else ""
        self.date_posted = self.posted_at
        expiry = parse_date(self.expires_at)
        self.expires_at = expiry.isoformat() if expiry else ""

    def to_dict(self):
        """Full evidence for replay and pending delivery; no preview truncation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        allowed = {f.name for f in fields(cls)}
        return cls(**{key: value for key, value in data.items() if key in allowed})


def merge_jobs(jobs):
    """Merge exact identities/destinations, never fuzzy company/title similarity."""
    merged, index = [], {}
    for job in jobs:
        keys = {job.job_id, "url:" + job.url}
        destination_path = urlsplit(job.application_url).path.rstrip("/").lower()
        if job.application_url and destination_path.rsplit("/", 1)[-1] not in {"", "careers", "jobs", "positions", "apply"}:
            keys.add("url:" + job.application_url)
        existing = next((index[key] for key in [job.job_id, *sorted(keys)] if key in index
                         and not (job.source_id and index[key].source_id and job.source_id != index[key].source_id
                                  and job.platform == index[key].platform)), None)
        if existing is None:
            merged.append(job)
            existing = job
        else:
            existing.aliases = list(dict.fromkeys(existing.aliases + job.aliases + [job.job_id]))
            existing.source_urls = list(dict.fromkeys(existing.source_urls + job.source_urls))
            if existing.location and job.location and normalized(existing.location) != normalized(job.location):
                existing.evidence_warnings.append("conflicting_locations")
            if existing.work_mode != "unknown" and job.work_mode != "unknown" and existing.work_mode != job.work_mode:
                existing.evidence_warnings.append("contradictory_work_mode")
            quality = {"full": 3, "snippet": 2, "fetch_failed": 1, "missing": 0}
            if (quality.get(job.description_status, 0), len(job.description)) > (quality.get(existing.description_status, 0), len(existing.description)):
                existing.description = job.description
                existing.description_status = job.description_status
            for name in ("location", "posted_at", "expires_at", "candidate_locations", "salary_currency",
                         "salary_text", "salary_interval", "application_url", "job_level", "job_type"):
                if not getattr(existing, name):
                    setattr(existing, name, getattr(job, name))
            for name in ("salary_min", "salary_max"):
                if getattr(existing, name) is None:
                    setattr(existing, name, getattr(job, name))
            if existing.work_mode == "unknown":
                existing.work_mode, existing.is_remote = job.work_mode, job.is_remote
            existing.evidence_warnings = list(dict.fromkeys(existing.evidence_warnings + job.evidence_warnings))
        for key in keys:
            index[key] = existing
    return merged
