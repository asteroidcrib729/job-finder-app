"""Discord delivery with explicit per-job acknowledgements and bounded retries."""
import re
import time
from dataclasses import dataclass, field
from typing import Callable
import requests
from scrapers.base import Job, clean_text, canonical_url, optional_number


@dataclass
class DeliveryOutcome:
    job_id: str
    status: str
    reason: str = ""
    attempts: int = 0
    message_id: str = ""


@dataclass
class DeliveryResult:
    outcomes: list[DeliveryOutcome] = field(default_factory=list)

    @property
    def delivered_ids(self):
        return [item.job_id for item in self.outcomes if item.status == "delivered"]

    @property
    def failed_ids(self):
        return [item.job_id for item in self.outcomes if item.status != "delivered"]

    def __bool__(self):
        return not self.failed_ids


def display(value, limit=1024):
    text = clean_text(value) or "Unknown"
    text = re.sub(r"([\\*_~|<>\[\]])", r"\\\1", text).replace(chr(96), "'")
    text = text.replace("@", "@\u200b")
    return text[:limit]


class DiscordNotifier:
    def __init__(self, webhook_url, max_attempts=3, max_retry_wait=30, sleep=time.sleep):
        self.webhook_url = webhook_url
        self.max_attempts = max_attempts
        self.max_retry_wait = max_retry_wait
        self.sleep = sleep

    def _send_one(self, job):
        try:
            payload = {"username": "Job Finder Alert Bot",
                       "allowed_mentions": {"parse": []}, "embeds": [self._build_embed(job)]}
        except (ValueError, TypeError, AttributeError):
            return DeliveryOutcome(job.job_id, "permanent_failure", "invalid_payload")
        return self._send_payload(job.job_id, payload)

    def _send_payload(self, job_id, payload):
        if not self.webhook_url:
            return DeliveryOutcome(job_id, "permanent_failure", "missing_webhook")
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = requests.post(self.webhook_url, params={"wait": "true"}, json=payload, timeout=(5, 15))
            except (requests.Timeout, requests.ConnectionError):
                return DeliveryOutcome(job_id, "uncertain", "network_outcome_unknown", attempt)
            except requests.RequestException:
                return DeliveryOutcome(job_id, "failed", "request_error", attempt)
            if response.status_code in {200, 204}:
                message_id = ""
                if response.status_code == 200:
                    try:
                        message_id = clean_text(response.json().get("id"))
                    except (ValueError, AttributeError):
                        pass
                return DeliveryOutcome(job_id, "delivered", attempts=attempt, message_id=message_id)
            if response.status_code not in {429, 500, 502, 503, 504}:
                return DeliveryOutcome(job_id, "permanent_failure", f"http_{response.status_code}", attempt)
            if attempt == self.max_attempts:
                return DeliveryOutcome(job_id, "failed", f"http_{response.status_code}", attempt)
            wait = min(self.max_retry_wait, 2 ** attempt)
            if response.status_code == 429:
                try:
                    delay = optional_number(response.json().get("retry_after"))
                except (ValueError, AttributeError):
                    delay = None
                if delay is not None and delay > self.max_retry_wait:
                    return DeliveryOutcome(job_id, "failed", "rate_limit_wait_exceeds_budget", attempt)
                wait = max(0, delay) if delay is not None else wait
            self.sleep(wait)
        raise AssertionError("Unreachable retry state")

    def send_jobs(self, jobs, on_result: Callable | None = None, review_digest=False, on_batch_result=None):
        result = DeliveryResult()
        review = []
        for job in jobs:
            if review_digest and job.decision.get("tier") == "review":
                review.append(job)
                continue
            outcome = self._send_one(job)
            result.outcomes.append(outcome)
            if on_result:
                on_result(job, outcome)
            self.sleep(0.5)
        for offset in range(0, len(review), 5):
            valid, embeds = [], []
            for job in review[offset:offset + 5]:
                try:
                    gaps = "; ".join(job.decision.get("gaps", [])) or "Verify source details before applying."
                    embeds.append({"title": display(job.title, 180), "url": canonical_url(job.url),
                        "description": display(f"{job.company} | {job.location or 'Location unknown'}\n"
                            f"Review | {job.decision.get('score', 0)}/100\n"
                            f"Published: {job.posted_at or 'Unknown'}\n"
                            f"Check: {gaps}", 650),
                        "color": 0xD9A32D, "footer": {"text": display(job.job_id, 100)}})
                    valid.append(job)
                except (ValueError, TypeError, AttributeError):
                    outcome = DeliveryOutcome(job.job_id, "permanent_failure", "invalid_payload")
                    result.outcomes.append(outcome)
                    if on_result:
                        on_result(job, outcome)
            if not valid:
                continue
            payload = {"username": "Job Finder Alert Bot", "allowed_mentions": {"parse": []},
                       "content": "Review candidates — verify the listed uncertainties before applying.",
                       "embeds": embeds}
            receipt = self._send_payload(valid[0].job_id, payload)
            outcomes = [DeliveryOutcome(job.job_id, receipt.status, receipt.reason,
                         receipt.attempts, receipt.message_id) for job in valid]
            result.outcomes.extend(outcomes)
            if on_batch_result:
                on_batch_result(list(zip(valid, outcomes)))
            elif on_result:
                for job, outcome in zip(valid, outcomes):
                    on_result(job, outcome)
            self.sleep(0.5)
        return result

    def _build_embed(self, job: Job):
        decision = job.decision
        eligibility = decision.get("eligibility", "unknown")
        location = f"{job.work_mode.replace('_', ' ')} | {job.location or 'Location unknown'}"
        if job.is_remote:
            location += f" | Pakistan eligibility: {eligibility}"
        salary = job.salary_text
        if not salary and (job.salary_min is not None or job.salary_max is not None):
            amounts = " - ".join(f"{value:g}" for value in (job.salary_min, job.salary_max) if value is not None)
            salary = f"{job.salary_currency or 'Currency unknown'} {amounts} / {job.salary_interval or 'interval unknown'}"
        fields = [
            {"name": "Company", "value": display(job.company, 400), "inline": True},
            {"name": "Location", "value": display(location, 600), "inline": False},
            {"name": "Source", "value": display(job.platform, 100), "inline": True},
            {"name": "Published", "value": display(job.posted_at or "Unknown; newly discovered", 100), "inline": True},
            {"name": "Salary disclosure", "value": display(salary or "Undisclosed", 500), "inline": False},
        ]
        if decision:
            fields.extend([
                {"name": "Fit", "value": display(f"{decision.get('tier', 'review')} | {decision.get('score', 0)}/100 | {decision.get('confidence', 'limited')} evidence", 200)},
                {"name": "Why this match", "value": display("; ".join(decision.get("reasons", [])), 800)},
            ])
            if decision.get("gaps"):
                fields.append({"name": "Check before applying", "value": display("; ".join(decision["gaps"]), 800)})
        if job.recruiter_email:
            fields.append({"name": "Email observed in source (unverified)", "value": display(job.recruiter_email, 250)})
        return {
            "title": display(job.title, 256),
            "url": canonical_url(job.url),
            "color": 0x2878C8 if decision.get("tier") == "qualified" else 0xD9A32D,
            "description": display(job.description or "Full description unavailable.", 500),
            "fields": fields,
            "footer": {"text": f"Job Finder | {job.job_id}"[:200]},
        }
