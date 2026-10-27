"""Persistent, prioritized description work and bounded adaptive pacing."""
import copy
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from job_finder.filtering.resume_filter import evaluate_job, skills_in
from job_finder.scrapers.base import Job, parse_date
from job_finder.storage.enrichment import ADAPTIVE_KEY, QUEUE_KEY, validate_queue


class EnrichmentQueue:
    def __init__(self, result, config, discovery, now=None):
        self.result, self.config = result, config
        self.options = config["jobspy"]
        self.now = now or datetime.now(timezone.utc)
        self.stamp = self.now.isoformat()
        if QUEUE_KEY in discovery:
            validate_queue(discovery[QUEUE_KEY])
        self.entries = copy.deepcopy(discovery.get(QUEUE_KEY, {}).get("entries", {}))
        self.metrics = {"initial_pending": sum(e["status"] == "pending" for e in self.entries.values()),
            "enqueued": 0, "completed": 0, "cache_hits": 0, "retired": 0, "failed": 0,
            "recovered_jobs": 0, "fallback_requests": 0, "excluded": 0, "overflow": 0}
        self.indices = defaultdict(list)
        for key, entry in list(self.entries.items()):
            if self.expired(entry) or not self.relevant(Job.from_dict(entry["job"])):
                self.entries.pop(key)
                self.metrics["retired"] += 1
            elif entry["status"] == "pending" and entry["attempts"] >= self.options["linkedin_queue_max_attempts"]:
                entry["status"] = "exhausted"
        for index, job in enumerate(result):
            if job.platform.lower() != "linkedin":
                continue
            self.indices[job.job_id].append(index)
        for key, indices in self.indices.items():
            job = max((result[index] for index in indices), key=lambda item: item.description_status == "full")
            if job.description_status == "full" or not self.relevant(job):
                self.entries.pop(job.job_id, None)
                self.metrics["excluded"] += int(job.description_status != "full")
                continue
            if not re.fullmatch(r"https://www\.linkedin\.com/jobs/view/[0-9]+", job.url):
                continue
            if job.job_id not in self.entries:
                self.entries[job.job_id] = {"job": job.to_dict(), "queued_at": self.stamp,
                    "updated_at": self.stamp, "status": "pending", "attempts": 0}
                self.metrics["enqueued"] += 1
            else:
                self.entries[job.job_id].update(job=job.to_dict(), updated_at=self.stamp)
                if self.entries[job.job_id]["status"] == "closed":
                    for index in indices:
                        result[index].active_status = "closed"
        self.metrics["overflow"] = max(0, len(self.entries) - self.options["linkedin_queue_limit"])
        self.entries = dict(sorted(self.entries.items(), key=lambda pair: self.priority(pair[1]))[
            :self.options["linkedin_queue_limit"]])
        control = discovery.get(ADAPTIVE_KEY, {})
        maximum = self.options["linkedin_max_details"]
        self.minimum = min(maximum, self.options["linkedin_detail_min_requests"])
        self.limit = min(maximum, max(self.minimum, control.get("request_limit",
            self.options["linkedin_detail_initial_requests"])))
        self.delay = min(self.options["linkedin_detail_max_delay"], max(self.options["linkedin_detail_delay"],
            control.get("delay_seconds", self.options["linkedin_detail_delay"])))
        self.metrics.update(effective_request_limit=self.limit, delay_seconds=self.delay)
        result.report.enrichment = self.metrics

    def relevant(self, job):
        decision = evaluate_job(Job.from_dict(job.to_dict()), self.config, now=self.now)
        excluded = {"senior_role", "unrelated_occupation", "software_role_not_established", "listing_stale",
            "listing_closed", "internships_disabled", "contracts_disabled", "hybrid_disabled"}
        return not excluded.intersection(decision.reasons)

    def expired(self, entry):
        date = parse_date(entry["queued_at"])
        if date is None:
            return True
        age = (self.now - date).total_seconds()
        return not 0 <= age < self.options["linkedin_queue_retention_hours"] * 3600

    def priority(self, entry):
        job = Job.from_dict(entry["job"])
        known = set(self.config["profile"]["demonstrated_skills"]) | set(self.config["profile"]["listed_skills"])
        junior = bool(re.search(r"\b(?:junior|jr\.?|graduate|intern(?:ship)?|entry)\b", job.title, re.I))
        rank = 0 if junior else 1 if skills_in(job.title) & known else 2
        hours = (self.now - (parse_date(entry["queued_at"]) or self.now)).total_seconds() / 3600
        # Waiting work ages into the highest tier rather than starving forever.
        return max(0, rank - int(hours / 6)), entry["queued_at"]

    def ready(self):
        tracks = defaultdict(deque)
        for key, entry in sorted(self.entries.items(), key=lambda pair: self.priority(pair[1])):
            if entry["status"] != "pending" or entry["attempts"] >= self.options["linkedin_queue_max_attempts"]:
                continue
            retry = parse_date(entry.get("retry_after"))
            if retry and retry > self.now:
                continue
            job = Job.from_dict(entry["job"])
            tracks[job.search_track].append(key)
        ordered = []
        while tracks:
            for track in list(tracks):
                ordered.append(tracks[track].popleft())
                if not tracks[track]:
                    del tracks[track]
        return ordered

    def put_job(self, key, enriched):
        if self.indices.get(key):
            for index in self.indices[key]:
                # Current card evidence has already replaced the stored payload.
                self.result[index] = Job.from_dict({**enriched.to_dict(),
                    "query_id": self.result[index].query_id, "search_track": self.result[index].search_track})
        else:
            self.indices[key].append(len(self.result))
            self.result.append(enriched)
            self.metrics["recovered_jobs"] += 1

    def completed(self, key, job, cached=False):
        self.put_job(key, job)
        self.entries.pop(key, None)
        self.metrics["completed"] += 1
        self.metrics["cache_hits"] += int(cached)

    def attempted(self, key):
        entry = self.entries[key]
        entry["attempts"] += 1
        entry.update(last_attempt=self.stamp, updated_at=self.stamp)

    def failed(self, key, status):
        entry = self.entries[key]
        entry["status"] = "closed" if status == "closed" else (
            "exhausted" if entry["attempts"] >= self.options["linkedin_queue_max_attempts"] else "pending")
        entry["retry_after"] = (self.now + timedelta(hours=self.options["linkedin_detail_retry_hours"])).isoformat()
        self.metrics["failed"] += 1
        for index in self.indices.get(key, []):
            self.result[index].description_status = "fetch_failed"
            if status == "closed":
                self.result[index].active_status = "closed"
        if status == "closed" and not self.indices.get(key):
            closed = Job.from_dict(entry["job"])
            closed.active_status = "closed"
            self.put_job(key, closed)

    def publish(self, attempted, successful, trouble):
        next_limit, delay = self.limit, self.delay
        if trouble:
            next_limit = max(self.minimum, self.limit // 2)
            delay = min(self.options["linkedin_detail_max_delay"], self.delay * 2)
        elif attempted and attempted == successful:
            if attempted >= self.limit and any(e["status"] == "pending" for e in self.entries.values()):
                next_limit = min(self.options["linkedin_max_details"], self.limit + 4)
            delay = max(self.options["linkedin_detail_delay"], self.delay - 0.5)
        if attempted:
            self.result.updates[ADAPTIVE_KEY] = {"request_limit": next_limit, "delay_seconds": delay,
                "updated_at": self.stamp}
        self.metrics.update(pending=sum(e["status"] == "pending" for e in self.entries.values()),
            exhausted=sum(e["status"] == "exhausted" for e in self.entries.values()),
            retained=len(self.entries), next_request_limit=next_limit, next_delay_seconds=delay)
        self.result.updates[QUEUE_KEY] = {"version": 1, "entries": self.entries, "updated_at": self.stamp}
