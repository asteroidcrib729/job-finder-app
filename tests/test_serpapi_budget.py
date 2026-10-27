import copy
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from job_finder.configuration.loader import load_config, validate_config
from job_finder.scrapers.common import SourceError
from job_finder.scrapers.google_api import run_google_api
from job_finder.scrapers.jobspy_adapter import fetch_jobspy_jobs
from job_finder.scrapers.serpapi_budget import SerpApiBudget, account_balance
from job_finder.storage.quota import empty_quota, merge_quota, validate_quota
from job_finder.storage.sync_state import persist_state
from job_finder.storage.tracker import StateError, atomic_write_json, read_json
from tests.support import OfflineTestCase

NOW = datetime.now(timezone.utc).replace(microsecond=0)


class SerpApiBudgetTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "quota.json"
        self.options = load_config()["jobspy"]
        self.account = MagicMock(return_value={"remaining": 250, "hour_used": 0, "hour_limit": 50})

    def budget(self, now=NOW):
        return SerpApiBudget(self.options, self.path, now=lambda: now, account=self.account)

    def seed(self, dates):
        state = {"version": 1, "reservations": {f"{i:032x}": d.isoformat() for i, d in enumerate(dates)}}
        atomic_write_json(self.path, state)
        return state

    def blocked(self, budget, reason):
        with self.assertRaises(SourceError) as context:
            budget.reserve(20)
        self.assertEqual(context.exception.reason, reason)

    def test_search_is_reserved_durably_before_http_and_timeout_is_not_refunded(self):
        def timeout(*args, **kwargs):
            self.assertEqual(len(read_json(self.path, {})["reservations"]), 1)
            raise requests.Timeout("private-key")
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "private-key"}), \
             patch("job_finder.scrapers.google_api.requests.get", side_effect=timeout), self.assertRaises(SourceError):
            run_google_api({"search_term": "Python", "results_wanted": 10}, 20, budget=self.budget())
        self.assertEqual(len(read_json(self.path, {})["reservations"]), 1)
        self.assertNotIn("private-key", self.path.read_text())

    def test_restart_and_month_boundary_do_not_bypass_six_hour_spacing(self):
        end = datetime(2026, 10, 31, 23, tzinfo=timezone.utc)
        self.budget(end).reserve(20)
        self.blocked(self.budget(end + timedelta(hours=1)), "serpapi_minimum_interval")
        self.assertEqual(self.account.call_count, 1)
        self.budget(end + timedelta(hours=6)).reserve(20)
        self.assertEqual(len(read_json(self.path, {})["reservations"]), 2)

    def test_rolling_cap_survives_calendar_month_reset_and_counts_failed_attempts(self):
        self.seed([NOW - timedelta(hours=7 + 6 * i) for i in range(120)])
        self.blocked(self.budget(), "serpapi_rolling_budget_exhausted")
        self.account.assert_not_called()
        self.budget(NOW + timedelta(days=31)).reserve(20)
        self.assertEqual(len(read_json(self.path, {})["reservations"]), 121)

    def test_account_reserve_handles_usage_by_other_clients(self):
        for remaining in (0, 50, 100):
            self.account.return_value["remaining"] = remaining
            self.blocked(self.budget(), "serpapi_credit_reserve_reached")
            self.assertFalse(self.path.exists())
        self.account.return_value["remaining"] = 101
        self.budget().reserve(20)
        self.assertTrue(self.path.exists())

    def test_provider_hourly_limit_and_unavailable_account_block_paid_requests(self):
        self.account.return_value.update(hour_used=50)
        self.blocked(self.budget(), "serpapi_hourly_limit")
        self.account.side_effect = SourceError("unverified", "serpapi_account_unavailable")
        self.blocked(self.budget(), "serpapi_account_unavailable")
        self.assertFalse(self.path.exists())

    def test_corrupt_locked_future_or_unwritable_ledger_prevents_spending(self):
        self.path.write_text("corrupt")
        self.blocked(self.budget(), "serpapi_quota_state_unavailable")
        self.path.unlink()
        lock = Path(str(self.path) + ".lock")
        lock.touch()
        self.blocked(self.budget(), "serpapi_quota_locked_or_unwritable")
        lock.unlink()
        self.seed([NOW + timedelta(hours=1)])
        self.blocked(self.budget(), "serpapi_quota_clock_ahead")
        self.account.assert_not_called()
        self.path.unlink()
        with patch("job_finder.scrapers.serpapi_budget.atomic_write_json", side_effect=StateError("write failed")):
            self.blocked(self.budget(), "serpapi_quota_state_unavailable")
        self.assertFalse(self.path.exists())

    def test_per_run_limit_is_enforced_even_if_clock_advances(self):
        budget = self.budget()
        budget.reserve(20)
        budget.clock = lambda: NOW + timedelta(hours=6)
        self.blocked(budget, "serpapi_run_budget_exhausted")
        self.assertEqual(self.account.call_count, 1)

    def test_overlapping_local_reservations_cannot_both_spend(self):
        other_account = MagicMock()
        other = SerpApiBudget(self.options, self.path, now=lambda: NOW, account=other_account)
        def balance(_):
            self.blocked(other, "serpapi_quota_locked_or_unwritable")
            return {"remaining": 250, "hour_used": 0, "hour_limit": 50}
        self.account.side_effect = balance
        self.budget().reserve(20)
        other_account.assert_not_called()
        self.assertEqual(len(read_json(self.path, {})["reservations"]), 1)

    def test_merge_preserves_both_reservations_and_prevents_refunds(self):
        base = self.seed([NOW - timedelta(days=1)])
        local = copy.deepcopy(base)
        remote = empty_quota()
        local["reservations"]["a" * 32] = NOW.isoformat()
        remote["reservations"]["b" * 32] = NOW.isoformat()
        result = merge_quota(base, local, remote)
        self.assertEqual(len(result["reservations"]), 3)
        for invalid in [{}, {"version": True, "reservations": {}}, {"version": 1, "reservations": {"bad": "today"}}]:
            with self.assertRaises(StateError):
                validate_quota(invalid)

    def test_old_entries_expire_without_refunding_the_active_window(self):
        base = self.seed([NOW - timedelta(days=65), NOW - timedelta(days=30)])
        self.budget().reserve(20)
        merged = merge_quota(base, read_json(self.path, {}), base)
        self.assertEqual(len(merged["reservations"]), 2)
        self.assertIn(NOW.isoformat(), merged["reservations"].values())

    def test_manual_refresh_cannot_spend_again_and_google_queries_rotate(self):
        config = load_config()
        config["search_keywords"] = ["Python", "React"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["google"]),
            dict(config["search_tracks"][2], sites=["google"])]
        config["jobspy"].update(interval_hours=0, low_yield_interval_hours=0)
        selected = []
        def fake_api(kwargs, timeout, budget):
            budget.reserve(timeout)
            selected.append(kwargs["google_search_term"])
            return {"rows": []}
        with patch("job_finder.scrapers.jobspy_adapter.run_google_api", side_effect=fake_api):
            first = fetch_jobspy_jobs(config, api_budget=self.budget())
            second = fetch_jobspy_jobs(config, first.updates, api_budget=self.budget(NOW + timedelta(hours=1)))
            fetch_jobspy_jobs(config, first.updates, api_budget=self.budget(NOW + timedelta(hours=6)))
        self.assertEqual(len(selected), 2)
        self.assertIn("Karachi", selected[0])
        self.assertIn("worldwide", selected[1])
        self.assertEqual(second.report.quota["reason"], "serpapi_minimum_interval")
        self.assertTrue(second.report.skipped)
        self.assertFalse(second.report.queries)

    def test_account_api_keeps_only_numeric_credit_counters(self):
        data = {"account_status": "Active", "plan_searches_left": 200, "total_searches_left": 300,
            "this_hour_searches": 0, "account_rate_limit_per_hour": 50,
            "api_key": "private-key", "account_email": "private@example.test"}
        response = SimpleNamespace(status_code=200, content=b"{}", json=lambda: data)
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "private-key"}), \
             patch("job_finder.scrapers.serpapi_budget.requests.get", return_value=response) as get:
            result = account_balance(20)
        self.assertEqual(result, {"remaining": 200, "hour_used": 0, "hour_limit": 50})
        self.assertNotIn("private", json.dumps(result))
        self.assertEqual(get.call_args.args[0], "https://serpapi.com/account.json")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_account_api_rejects_malformed_auth_error_redirect_and_timeout_responses(self):
        invalid = [SimpleNamespace(status_code=200, content=b"{}", json=lambda: {}),
            SimpleNamespace(status_code=302, content=b""), SimpleNamespace(status_code=401, content=b""),
            requests.Timeout("private-key")]
        with patch.dict(os.environ, {"SERPAPI_API_KEY": "private-key"}):
            for response in invalid:
                with patch("job_finder.scrapers.serpapi_budget.requests.get",
                        return_value=response, side_effect=response if isinstance(response, Exception) else None), \
                     self.assertRaises(SourceError) as context:
                    account_balance(20)
                self.assertNotIn("private", str(context.exception))

    def test_quota_configuration_requires_bounded_integer_limits(self):
        for field, invalid in [("google_api_monthly_budget", 251), ("google_api_min_interval_hours", 0),
                ("google_api_credit_reserve", 0), ("google_api_monthly_budget", True)]:
            config = load_config()
            config["jobspy"][field] = invalid
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_dry_run_quota_only_git_persistence_cannot_write_job_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote, worker = root / "remote.git", root / "worker"
            env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.test",
                "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.test"}
            def git(where, *args):
                return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=where,
                    env=env, check=True, capture_output=True, text=True, timeout=20).stdout.strip()
            git(root, "init", "--bare", str(remote))
            git(root, "clone", str(remote), str(worker))
            git(worker, "checkout", "-b", "main")
            atomic_write_json(worker / "data/serpapi_usage.json", empty_quota())
            atomic_write_json(worker / "data/seen_jobs.json", {"old": 1000})
            atomic_write_json(worker / "data/discovery_state.json", {})
            git(worker, "add", ".")
            git(worker, "commit", "-m", "initial")
            git(worker, "push", "-u", "origin", "main")
            (worker / "data/seen_jobs.json").write_text("deliberately invalid")
            atomic_write_json(worker / "data/discovery_state.json", {"do_not_publish": {}})
            usage = {"version": 1, "reservations": {"a" * 32: NOW.isoformat()}}
            atomic_write_json(worker / "data/serpapi_usage.json", usage)
            self.assertEqual(persist_state(worker, "main", scope="quota")["files"],
                ["data/serpapi_usage.json", "data/serpapi_usage.json.bak"])
            self.assertEqual(json.loads(git(remote, "show", "main:data/seen_jobs.json")), {"old": 1000})
            self.assertEqual(json.loads(git(remote, "show", "main:data/discovery_state.json")), {})
            self.assertEqual(json.loads(git(remote, "show", "main:data/serpapi_usage.json")), usage)
