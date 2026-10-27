"""Validated bounded discovery work, distinct from acknowledged delivery state."""
import math
import re

from job_finder.scrapers.base import Job, parse_date
from job_finder.storage.tracker import StateError

QUEUE_KEY = "queue:linkedin_details"
ADAPTIVE_KEY = "adaptive:linkedin_details"
QUEUE_LIMIT = 1000


def validate_queue(record):
    try:
        if type(record.get("version")) is not int or record["version"] != 1 or not parse_date(record.get("updated_at")):
            raise ValueError("Invalid queue header")
        entries = record["entries"]
        if not isinstance(entries, dict) or len(entries) > QUEUE_LIMIT:
            raise ValueError("Invalid queue size")
        for key, entry in entries.items():
            job = Job.from_dict(entry["job"])
            if key != job.job_id or job.platform.lower() != "linkedin" or not re.fullmatch(
                    r"https://www\.linkedin\.com/jobs/view/[0-9]+", job.url):
                raise ValueError("Invalid queue identity")
            if entry["status"] not in {"pending", "closed", "exhausted"}:
                raise ValueError("Invalid queue status")
            if type(entry["attempts"]) is not int or not 0 <= entry["attempts"] <= 100:
                raise ValueError("Invalid queue attempts")
            for field in ("queued_at", "updated_at"):
                if not parse_date(entry.get(field)):
                    raise ValueError("Invalid queue timestamp")
            for field in ("last_attempt", "retry_after"):
                if field in entry and not parse_date(entry[field]):
                    raise ValueError("Invalid queue retry timestamp")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise StateError("Invalid enrichment queue; existing state retained") from exc


def validate_adaptive(record):
    try:
        if type(record["request_limit"]) is not int or not 0 <= record["request_limit"] <= 100:
            raise ValueError("Invalid adaptive limit")
        delay = record["delay_seconds"]
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or not math.isfinite(delay) or not 1 <= delay <= 60:
            raise ValueError("Invalid adaptive delay")
        if not parse_date(record.get("updated_at")):
            raise ValueError("Invalid adaptive timestamp")
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise StateError("Invalid enrichment budget; existing state retained") from exc
