import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Set
from scrapers.base import Job

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEEN_JOBS_FILE = DATA_DIR / "seen_jobs.json"

# Max age for tracked jobs (30 days in seconds)
MAX_AGE_SECONDS = 30 * 24 * 60 * 60

class JobTracker:
    def __init__(self, storage_file: Path = SEEN_JOBS_FILE):
        self.storage_file = storage_file
        self.seen_data: Dict[str, float] = {}  # job_id -> timestamp
        self._load()

    def _load(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.seen_data = json.load(f)
                self._prune_old_entries()
            except Exception as e:
                logger.error(f"Failed to load seen jobs file {self.storage_file}: {e}")
                self.seen_data = {}
        else:
            self.seen_data = {}

    def _prune_old_entries(self):
        now = time.time()
        initial_count = len(self.seen_data)
        self.seen_data = {
            job_id: ts for job_id, ts in self.seen_data.items()
            if (now - ts) < MAX_AGE_SECONDS
        }
        pruned_count = initial_count - len(self.seen_data)
        if pruned_count > 0:
            logger.info(f"Pruned {pruned_count} old entries from seen jobs state.")

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self.seen_data, f, indent=2)
            logger.info(f"Saved {len(self.seen_data)} total tracked job IDs to {self.storage_file}")
        except Exception as e:
            logger.error(f"Failed to save seen jobs state to {self.storage_file}: {e}")

    def filter_new_jobs(self, jobs: List[Job]) -> List[Job]:
        new_jobs: List[Job] = []
        seen_in_batch: Set[str] = set()

        for job in jobs:
            if job.job_id not in self.seen_data and job.job_id not in seen_in_batch:
                new_jobs.append(job)
                seen_in_batch.add(job.job_id)

        return new_jobs

    def mark_as_seen(self, jobs: List[Job]):
        now = time.time()
        for job in jobs:
            self.seen_data[job.job_id] = now
        self.save()
