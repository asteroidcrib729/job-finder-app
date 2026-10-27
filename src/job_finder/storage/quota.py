"""Append-only search reservations; concurrent reconciliation never refunds usage."""
import copy
import re
from datetime import datetime, timedelta

from job_finder.scrapers.base import parse_date
from job_finder.storage.tracker import StateError


def empty_quota():
    return {"version": 1, "reservations": {}}


def quota_date(stamp) -> datetime:
    value = parse_date(stamp)
    if value is None:
        raise StateError("Invalid SerpApi quota date")
    return value


def validate_quota(raw):
    if (not isinstance(raw, dict) or set(raw) != {"version", "reservations"}
            or type(raw["version"]) is not int or raw["version"] != 1
            or not isinstance(raw["reservations"], dict) or len(raw["reservations"]) > 4096):
        raise StateError("Invalid SerpApi quota journal; searches remain blocked")
    for identifier, stamp in raw["reservations"].items():
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{32}", identifier) or not parse_date(stamp):
            raise StateError("Invalid SerpApi reservation; searches remain blocked")
    return copy.deepcopy(raw)


def merge_quota(base, local, remote):
    # A removed or older ledger cannot refund a concurrent reservation.
    values = {}
    for state in (base, local, remote):
        for identifier, stamp in validate_quota(state)["reservations"].items():
            values[identifier] = max(stamp, values.get(identifier, stamp), key=quota_date)
    if values:
        cutoff = max(map(quota_date, values.values())) - timedelta(days=62)
        values = {key: stamp for key, stamp in values.items() if quota_date(stamp) >= cutoff}
    return validate_quota({"version": 1, "reservations": values})
