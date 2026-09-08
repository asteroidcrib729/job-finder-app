"""Bounded normalized detail cache; expired evidence is never a fallback."""
import copy
import hashlib
from datetime import datetime, timezone
from scrapers.base import canonical_url, parse_date

CACHE_LIMIT = 200


def query_key(source, query):
    return source + ":" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:20]


def query_due(discovery, key, interval_hours, now=None):
    now = now or datetime.now(timezone.utc)
    previous = parse_date((discovery or {}).get(key, {}).get("last_success"))
    return not previous or not 0 <= (now - previous).total_seconds() < interval_hours * 3600


class DetailCache:
    """Only adapters' parsed public evidence is persisted, never raw responses."""
    def __init__(self, discovery, namespace, hours, now=None):
        self.key = "cache:" + namespace
        self.now = now or datetime.now(timezone.utc)
        self.hours = hours
        self.hits = 0
        self.entries = {}
        for url, entry in (discovery or {}).get(self.key, {}).get("entries", {}).items():
            if not isinstance(entry, dict) or not isinstance(entry.get("payload"), dict):
                continue
            date = parse_date(entry.get("fetched_at"))
            if date and 0 <= (self.now - date).total_seconds() < hours * 3600:
                self.entries[url] = copy.deepcopy(entry)
        self._bound()

    def _bound(self):
        self.entries = dict(sorted(self.entries.items(),
            key=lambda item: item[1]["fetched_at"], reverse=True)[:CACHE_LIMIT])

    def get(self, url):
        entry = self.entries.get(canonical_url(url))
        if entry is None:
            return None
        self.hits += 1
        return copy.deepcopy(entry["payload"])

    def put(self, url, payload):
        if self.hours:
            self.entries[canonical_url(url)] = {
                "fetched_at": self.now.isoformat(), "payload": copy.deepcopy(payload)}
            self._bound()

    def discard(self, url):
        self.entries.pop(canonical_url(url), None)

    def publish(self, result):
        result.updates[self.key] = {"entries": self.entries, "updated_at": self.now.isoformat()}
        if self.hits:
            result.report.notes.append(f"detail_cache_hits:{self.hits}")
