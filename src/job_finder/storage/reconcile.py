"""Three-way state reconciliation; acknowledgements win over pending deliveries."""
import copy
from datetime import datetime, timezone

from job_finder.scrapers.base import Job, parse_date
from job_finder.scrapers.cache import CACHE_LIMIT
from job_finder.storage.enrichment import (
    ADAPTIVE_KEY,
    QUEUE_KEY,
    QUEUE_LIMIT,
    validate_adaptive,
    validate_queue,
)
from job_finder.storage.tracker import StateError, validate_delivery_state


def validate_discovery_state(raw):
    if not isinstance(raw, dict):
        raise StateError("Discovery state must be an object")
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            raise StateError("Invalid discovery record")
        for field in ("last_success", "last_attempt"):
            if field in value and not parse_date(value[field]):
                raise StateError("Invalid discovery timestamp")
        if key == QUEUE_KEY:
            validate_queue(value)
        if key == ADAPTIVE_KEY:
            validate_adaptive(value)
        if key.startswith("cache:"):
            if not isinstance(value.get("entries"), dict) or not parse_date(value.get("updated_at")):
                raise StateError("Invalid detail cache")
            for url, entry in value["entries"].items():
                if (not isinstance(url, str) or not isinstance(entry, dict)
                        or not parse_date(entry.get("fetched_at")) or not isinstance(entry.get("payload"), dict)):
                    raise StateError("Invalid detail cache entry")
    return copy.deepcopy(raw)


def changed_records(base, local, remote, conflict):
    """Apply unilateral changes/deletions and resolve only concurrent changes."""
    missing = object()
    merged = {}
    for key in sorted(set(base) | set(local) | set(remote)):
        baseline, local_value, remote_value = (mapping.get(key, missing) for mapping in (base, local, remote))
        if local_value == baseline:
            value = remote_value
        elif remote_value == baseline or local_value == remote_value:
            value = local_value
        elif local_value is missing or remote_value is missing:
            # Explicit retirement wins over a competing queue/cache update.
            value = missing
        else:
            value = conflict(local_value, remote_value)
        if value is not missing:
            merged[key] = copy.deepcopy(value)
    return merged


def merge_delivery(base, local, remote):
    base, local, remote = map(validate_delivery_state, (base, local, remote))
    # Preserve every confirmed delivery from either writer. Never infer a receipt.
    seen = {}
    for key in set(local["seen"]) | set(remote["seen"]):
        # pyrefly: ignore [bad-index]
        values = [state["seen"][key] for state in (local, remote) if key in state["seen"]]
        # Honor retention pruning when the other writer still has the baseline value.
        # A newly recorded acknowledgement wins over a concurrent removal.
        if len(values) == 1 and values[0] == base["seen"].get(key):
            continue
        seen[key] = max(values)

    def pending_conflict(left, right):
        order = {"pending": 0, "failed": 1, "uncertain": 2, "permanent_failure": 3}
        latest = max((left, right), key=lambda record: (
            record.get("last_attempt_at", 0), order[record["status"]], record["attempts"]))
        value = copy.deepcopy(latest)
        value["attempts"] = max(left["attempts"], right["attempts"])
        value["next_retry_at"] = max(left.get("next_retry_at", 0), right.get("next_retry_at", 0))
        value["queued_at"] = min(float(left["queued_at"]), float(right["queued_at"]))
        return value

    pending = changed_records(base["pending"], local["pending"], remote["pending"], pending_conflict)
    for key, record in list(pending.items()):
        # pyrefly: ignore [bad-index]
        item = Job.from_dict(record["job"])
        if any(identity in seen for identity in [key, *item.aliases]):
            pending.pop(key)
    receipts = {}
    for state in (local, remote):
        # pyrefly: ignore [missing-attribute]
        for key, value in state["receipts"].items():
            if key in seen and value["at"] >= receipts.get(key, {}).get("at", float("-inf")):
                receipts[key] = copy.deepcopy(value)
    return validate_delivery_state({"version": 2, "seen": seen, "pending": pending, "receipts": receipts})


def date_key(record, key):
    return parse_date(record.get(key)) or datetime.min.replace(tzinfo=timezone.utc)


def merge_discovery(base, local, remote):
    base, local, remote = map(validate_discovery_state, (base, local, remote))

    def conflict(left, right):
        return max((left, right), key=lambda record: max(
            date_key(record, "last_success"), date_key(record, "last_attempt"), date_key(record, "updated_at")))

    merged = changed_records(base, local, remote, conflict)
    if QUEUE_KEY in local and QUEUE_KEY in remote:
        def queue_conflict(left, right):
            value = copy.deepcopy(max((left, right), key=lambda entry: date_key(entry, "updated_at")))
            value["queued_at"] = min(left["queued_at"], right["queued_at"])
            value["attempts"] = max(left["attempts"], right["attempts"])
            return value
        entries = changed_records(base.get(QUEUE_KEY, {}).get("entries", {}),
            local[QUEUE_KEY]["entries"], remote[QUEUE_KEY]["entries"], queue_conflict)
        entries = dict(sorted(entries.items(), key=lambda item: date_key(item[1], "queued_at"))[:QUEUE_LIMIT])
        newest = max((local[QUEUE_KEY], remote[QUEUE_KEY]), key=lambda value: date_key(value, "updated_at"))
        merged[QUEUE_KEY] = {"version": 1, "entries": entries, "updated_at": newest["updated_at"]}
    for key in set(local) & set(remote):
        if not key.startswith("cache:"):
            continue
        entries = changed_records(base.get(key, {}).get("entries", {}),
            local[key]["entries"], remote[key]["entries"],
            lambda left, right: max((left, right), key=lambda entry: date_key(entry, "fetched_at")))
        entries = dict(sorted(entries.items(), key=lambda item: date_key(item[1], "fetched_at"),
                              reverse=True)[:CACHE_LIMIT])
        newest = max((local[key], remote[key]), key=lambda record: date_key(record, "updated_at"))
        merged[key] = {"entries": entries, "updated_at": newest["updated_at"]}
    return validate_discovery_state(merged)
