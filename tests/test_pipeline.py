import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import yaml
from config import load_config
from main import run_job_finder
from scrapers.base import utc_now
from scrapers.common import SourceResult, QueryOutcome
from storage.tracker import JobTracker
from tests.support import OfflineTestCase, job
from tests.test_delivery import response


def source(jobs=()):
    result = SourceResult("Fixture", jobs)
    result.report.queries.append(QueryOutcome("fixture", "success" if jobs else "valid_empty", len(jobs), len(jobs)))
    return result


class PipelineTests(OfflineTestCase):
    def test_replay_never_scrapes_sends_or_writes_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay = root / "jobs.json"
            replay.write_text(json.dumps([job(posted_at=utc_now()).to_dict()]))
            state, discovery = root / "state.json", root / "discovery.json"
            with patch("main.fetch_jobspy_jobs") as scrape, patch("notifiers.discord.requests.post") as post:
                code = run_job_finder(replay_path=replay, state_path=state, discovery_path=discovery, report_dir=root / "report")
            self.assertEqual(code, 0)
            scrape.assert_not_called()
            post.assert_not_called()
            self.assertFalse(state.exists())
            self.assertFalse(discovery.exists())
            report = json.loads((root / "report" / "run.json").read_text())
            self.assertEqual(report["counts"]["qualified"], 1)

    def test_empty_scrape_still_delivers_pending_and_cap_defers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            override = root / "config.yaml"
            override.write_text("notifications:\n  max_per_run: 1\n")
            state, discovery = root / "state.json", root / "discovery.json"
            jobs = [job("a", posted_at=utc_now()), job("b", posted_at=utc_now())]
            with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.test/webhook"}), \
                 patch("main.fetch_jobspy_jobs", side_effect=[source(jobs), source()]), \
                 patch("main.fetch_rozee_jobs", return_value=source()), \
                 patch("main.fetch_linkedin_plain_posts", return_value=source()), \
                 patch("main.fetch_remote_feeds", return_value=source()), \
                 patch("notifiers.discord.requests.post", return_value=response(200, {"id": "fixture-message"})) as post:
                for count in (1, 0):
                    code = run_job_finder(config_path=override, state_path=state, discovery_path=discovery, report_dir=root / "report")
                    self.assertEqual(code, 0)
                    self.assertEqual(len(JobTracker(state).pending), count)
                self.assertEqual(post.call_count, 2)

    def test_missing_webhook_and_corrupt_state_fail_before_scraping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": ""}), patch("main.fetch_jobspy_jobs") as scrape:
                self.assertEqual(run_job_finder(state_path=root / "state", report_dir=root / "report"), 1)
                scrape.assert_not_called()
            state = root / "state"
            state.write_text("{")
            with patch("main.fetch_jobspy_jobs") as scrape:
                self.assertEqual(run_job_finder(dry_run=True, state_path=state, report_dir=root / "report"), 1)
                scrape.assert_not_called()

    def test_degraded_source_is_not_healthy_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failed = SourceResult("Fixture")
            failed.report.queries.append(QueryOutcome("q", "blocked", reason="403"))
            with patch("main.fetch_jobspy_jobs", return_value=failed), \
                 patch("main.fetch_rozee_jobs", return_value=source()), \
                 patch("main.fetch_linkedin_plain_posts", return_value=source()), \
                 patch("main.fetch_remote_feeds", return_value=source()):
                code = run_job_finder(dry_run=True, state_path=root / "state", discovery_path=root / "discovery", report_dir=root / "report")
            self.assertEqual(code, 2)
            self.assertEqual(json.loads((root / "report" / "run.json").read_text())["health"], "degraded")

    def test_config_partial_override_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.yaml"
            config_path.write_text("notifications:\n  max_per_run: 5\n")
            config = load_config(config_path)
            self.assertEqual(config["notifications"]["max_per_run"], 5)
            self.assertTrue(config["notifications"]["discord_enabled"])
            for bad in ("notifications: []", "jobspy:\n  results_wanted: 0\n", "matching:\n  allow_hybrid: maybe\n", "filtering: {}", "matching:\n  silent_typo: true\n"):
                config_path.write_text(bad)
                with self.assertRaises(ValueError):
                    load_config(config_path)

    def test_notifications_disabled_still_preserves_source_cadence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            override = root / "config.yaml"
            override.write_text("notifications:\n  discord_enabled: false\n")
            feed = source()
            feed.updates = {"feed:remotive": {"last_success": utc_now()}}
            with patch("main.fetch_jobspy_jobs", return_value=source()), \
                 patch("main.fetch_rozee_jobs", return_value=source()), \
                 patch("main.fetch_linkedin_plain_posts", return_value=source()), \
                 patch("main.fetch_remote_feeds", return_value=feed), \
                 patch("notifiers.discord.requests.post") as post:
                code = run_job_finder(config_path=override, state_path=root / "state", discovery_path=root / "discovery", report_dir=root / "report")
            self.assertEqual(code, 0)
            self.assertIn("feed:remotive", json.loads((root / "discovery").read_text()))
            self.assertFalse((root / "state").exists())
            post.assert_not_called()
