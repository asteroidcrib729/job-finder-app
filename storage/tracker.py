"""Atomic JSON delivery journal. Legacy timestamp-only state is migrated on save."""
import copy
import json
import math
import os
import tempfile
import time
from pathlib import Path
from scrapers.base import Job

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_JOBS_FILE = DATA_DIR / "seen_jobs.json"


class StateError(RuntimeError):
    pass


def atomic_write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as exc:
        raise StateError(f"Cannot persist state ({type(exc).__name__})") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def read_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise StateError(f"Cannot read state ({type(exc).__name__}); existing history retained") from exc


def validate_delivery_state(raw):
    raw = copy.deepcopy(raw)
    pending, receipts = {}, {}
    if not isinstance(raw, dict):
        raise StateError("Delivery state must be an object")
    if "version" in raw:
        if type(raw["version"]) is not int or raw["version"] != 2:
            raise StateError("Unsupported delivery state version")
        if not {"seen", "pending", "receipts"}.issubset(raw):
            raise StateError("Delivery state is missing required sections")
        seen = raw.get("seen", {})
        pending = raw.get("pending", {})
        receipts = raw.get("receipts", {})
    else:
        seen = raw
    if not all(isinstance(x, dict) for x in (seen, pending, receipts)):
        raise StateError("Invalid delivery state sections")
    for job_id, timestamp in seen.items():
        if not isinstance(job_id, str) or isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            raise StateError("Invalid seen timestamp; state must be repaired before delivery")
    for key, record in pending.items():
        try:
            item = Job.from_dict(record["job"])
            if key != item.job_id:
                raise ValueError("Queue identity mismatch")
            if record["status"] not in {"pending", "failed", "uncertain", "permanent_failure"}:
                raise ValueError("Invalid pending status")
            if type(record["queued_at"]) not in (int, float) or not math.isfinite(record["queued_at"]):
                raise ValueError("Invalid queue timestamp")
            if type(record.get("attempts")) is not int or record["attempts"] < 0:
                raise ValueError("Invalid attempt count")
            if type(record.get("next_retry_at", 0)) not in (int, float) or not math.isfinite(record.get("next_retry_at", 0)):
                raise ValueError("Invalid retry timestamp")
            if type(record.get("last_attempt_at", 0)) not in (int, float) or not math.isfinite(record.get("last_attempt_at", 0)):
                raise ValueError("Invalid attempt timestamp")
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise StateError("Invalid pending delivery record") from exc
    for key, receipt in receipts.items():
        if not isinstance(key, str) or not isinstance(receipt, dict):
            raise StateError("Invalid delivery receipt")
        at = receipt.get("at")
        # pyrefly: ignore [bad-argument-type]
        if type(at) not in (int, float) or not math.isfinite(at) or not isinstance(receipt.get("message_id", ""), str):
            raise StateError("Invalid delivery receipt")
    return {"version": 2, "seen": seen, "pending": pending, "receipts": receipts}


def save_with_backup(path, data, validator):
    """Keep the preceding valid snapshot; never rotate corrupt state into backup."""
    validator(data)
    path = Path(path)
    if path.exists():
        previous = read_json(path, {})
        validator(previous)
        atomic_write_json(path.with_name(path.name + ".bak"), previous)
    atomic_write_json(path, data)


class JobTracker:
    def __init__(self, storage_file=SEEN_JOBS_FILE, retention_days=30, pending_days=7, clock=time.time):
        self.storage_file = Path(storage_file)
        self.clock = clock
        self.retention_seconds = retention_days * 86400
        self.pending_seconds = pending_days * 86400
        self.seen_data, self.pending, self.receipts = {}, {}, {}
        self._load()

    def _load(self):
        raw = read_json(self.storage_file, {})
        state = validate_delivery_state(raw)
        self.seen_data, self.pending, self.receipts = state["seen"], state["pending"], state["receipts"]
        self._prune_old_entries()

    def _prune_old_entries(self):
        now = self.clock()
        self.seen_data = {key: ts for key, ts in self.seen_data.items() if now - ts < self.retention_seconds}
        self.receipts = {key: value for key, value in self.receipts.items() if key in self.seen_data}
        # Pending deliveries have a separate, explicit retirement policy.

    def save(self):
        save_with_backup(self.storage_file, {"version": 2, "seen": self.seen_data,
                                             "pending": self.pending, "receipts": self.receipts}, validate_delivery_state)

    def is_seen(self, job):
        return any(key in self.seen_data for key in [job.job_id, *job.aliases])

    def filter_new_jobs(self, jobs):
        new_jobs, batch = [], set()
        for job in jobs:
            if not self.is_seen(job) and job.job_id not in batch:
                new_jobs.append(job)
                batch.add(job.job_id)
        return new_jobs

    def enqueue(self, jobs):
        for job in self.filter_new_jobs(jobs):
            existing_key = next((key for key in [job.job_id, *job.aliases] if key in self.pending), None)
            if existing_key and existing_key != job.job_id:
                self.pending[job.job_id] = self.pending.pop(existing_key)
            if job.job_id in self.pending:
                self.pending[job.job_id]["job"] = job.to_dict()
            else:
                self.pending[job.job_id] = {"job": job.to_dict(), "status": "pending",
                    "queued_at": self.clock(), "attempts": 0, "next_retry_at": 0}
        self.save()

    def pending_jobs(self):
        return [Job.from_dict(record["job"]) for record in self.pending.values()
                if record["status"] != "permanent_failure" and record.get("next_retry_at", 0) <= self.clock()]

    def retire(self, job_id):
        self.pending.pop(job_id, None)

    def expired_pending(self, job_id):
        return self.clock() - self.pending[job_id]["queued_at"] > self.pending_seconds

    def record_delivery(self, job, outcome):
        self.record_deliveries([(job, outcome)])

    def record_deliveries(self, deliveries):
        for job, outcome in deliveries:
            self._apply_delivery(job, outcome)
        # A confirmed digest gets one atomic journal update for all its candidates.
        self.save()

    def _apply_delivery(self, job, outcome):
        if outcome.status == "delivered":
            now = self.clock()
            for key in [job.job_id, *job.aliases]:
                self.seen_data[key] = now
            self.receipts[job.job_id] = {"at": now, "message_id": outcome.message_id}
            self.pending.pop(job.job_id, None)
        else:
            record = self.pending[job.job_id]
            record["status"] = outcome.status
            record["attempts"] += outcome.attempts
            record["reason"] = outcome.reason
            record["last_attempt_at"] = self.clock()
            record["next_retry_at"] = self.clock() + min(86400, 300 * 2 ** min(record["attempts"], 8))

    def mark_as_seen(self, jobs):
        """Compatibility helper; callers must supply confirmed deliveries only."""
        for job in jobs:
            for key in [job.job_id, *job.aliases]:
                self.seen_data[key] = self.clock()
            self.pending.pop(job.job_id, None)
        self.save()
