"""Fail-closed credit protection shared by scheduled, manual and dry searches."""
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from job_finder.configuration.paths import BASE_DIR
from job_finder.scrapers.common import SourceError
from job_finder.storage.quota import empty_quota, quota_date, validate_quota
from job_finder.storage.tracker import StateError, atomic_write_json, read_json

QUOTA_FILE = BASE_DIR / "data" / "serpapi_usage.json"


def account_balance(timeout):
    """The free Account API returns private fields; retain only credit counters."""
    key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not key:
        raise SourceError("unsupported", "missing_serpapi_key")
    try:
        response = requests.get("https://serpapi.com/account.json", params={"api_key": key},
            timeout=(5, min(15, timeout)), allow_redirects=False)
    except requests.RequestException as exc:
        raise SourceError("unverified", "serpapi_account_unavailable") from exc
    if response.status_code != 200 or len(response.content) > 1_000_000:
        raise SourceError("unverified", "serpapi_account_unavailable")
    try:
        data = response.json()
        names = ("plan_searches_left", "total_searches_left", "this_hour_searches", "account_rate_limit_per_hour")
        if not isinstance(data, dict) or data.get("account_status") != "Active":
            raise ValueError("Inactive or invalid account")
        if any(type(data.get(name)) is not int or data[name] < 0 for name in names):
            raise ValueError("Unverified credit counters")
        return {"remaining": min(data["plan_searches_left"], data["total_searches_left"]),
            "hour_used": data["this_hour_searches"], "hour_limit": data["account_rate_limit_per_hour"]}
    except (ValueError, TypeError, AttributeError) as exc:
        raise SourceError("unverified", "serpapi_account_invalid_response") from exc


@contextmanager
def quota_lock(path):
    lock = Path(str(path) + ".lock")
    try:
        lock.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as exc:
        raise SourceError("unverified", "serpapi_quota_locked_or_unwritable") from exc
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink(missing_ok=True)


class SerpApiBudget:
    def __init__(self, options, path=QUOTA_FILE, now=None, account=None):
        self.options, self.path = options, Path(path)
        self.clock = now or (lambda: datetime.now(timezone.utc))
        self.account = account or account_balance
        self.status = {"rolling_days": 31, "attempt_limit": options["google_api_monthly_budget"],
            "minimum_interval_hours": options["google_api_min_interval_hours"],
            "credit_reserve": options["google_api_credit_reserve"], "search_attempts_this_run": 0}

    def deny(self, reason):
        self.status["reason"] = reason
        raise SourceError("unverified", reason)

    def reserve(self, timeout):
        try:
            with quota_lock(self.path):
                state = validate_quota(read_json(self.path, empty_quota()))
                now = self.clock()
                dates = [quota_date(stamp) for stamp in state["reservations"].values()]
                if any(date > now for date in dates):
                    self.deny("serpapi_quota_clock_ahead")
                recent = [date for date in dates if date > now - timedelta(days=31)]
                self.status.update(attempts_in_window=len(recent), checked_at=now.isoformat())
                if len(recent) >= self.options["google_api_monthly_budget"]:
                    self.deny("serpapi_rolling_budget_exhausted")
                if dates and now - max(dates) < timedelta(hours=self.options["google_api_min_interval_hours"]):
                    self.status["next_attempt_at"] = (max(dates) + timedelta(
                        hours=self.options["google_api_min_interval_hours"])).isoformat()
                    self.deny("serpapi_minimum_interval")
                if self.status["search_attempts_this_run"] >= self.options["google_api_max_queries"]:
                    self.deny("serpapi_run_budget_exhausted")
                balance = self.account(timeout)
                self.status["provider_credits_before_search"] = balance["remaining"]
                if balance["remaining"] <= self.options["google_api_credit_reserve"]:
                    self.deny("serpapi_credit_reserve_reached")
                if balance["hour_used"] >= balance["hour_limit"]:
                    self.deny("serpapi_hourly_limit")
                # Durable reservation precedes the billable request. Never refund
                # timeouts, errors or crashes whose provider billing is uncertain.
                state["reservations"] = {key: stamp for key, stamp in state["reservations"].items()
                    if quota_date(stamp) >= now - timedelta(days=62)}
                state["reservations"][uuid.uuid4().hex] = now.isoformat()
                atomic_write_json(self.path, state)
                self.status.update(attempts_in_window=len(recent) + 1,
                    search_attempts_this_run=self.status["search_attempts_this_run"] + 1, reason="reserved")
        except StateError:
            self.deny("serpapi_quota_state_unavailable")
        except SourceError as exc:
            self.status["reason"] = exc.reason
            raise
