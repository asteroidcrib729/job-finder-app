import copy
import json
import logging
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
from config import load_config, validate_config
from main import write_report
from run_health import assess_run, workflow_exit_code
from scrapers.jobspy_worker import HealthHandler
from scrapers.jobspy_adapter import fetch_jobspy_jobs
from scrapers.linkedin_posts_scraper import fetch_linkedin_plain_posts
from storage.tracker import atomic_write_json
from tests.support import OfflineTestCase
import workflow_runner

FIXTURES = Path(__file__).parent / "fixtures"


class RunHealthTests(OfflineTestCase):
    def test_actual_failed_run_reports_are_warnings_not_total_outages(self):
        for report in json.loads((FIXTURES / "production_health.json").read_text()):
            with self.subTest(run=report["run_id"]):
                self.assertEqual(report["counts"]["qualified"], 0)
                self.assertEqual(assess_run(report)["status"], "warning")
                self.assertEqual(workflow_exit_code(2, report), 0)

    def test_total_vacancy_failure_is_fatal_even_with_successful_recruiter_search(self):
        report = {"health": "degraded", "sources": [
            {"source": "JobSpy", "queries": [{"status": "blocked", "converted": 0}]},
            {"source": "LinkedIn Post", "queries": [{"status": "success", "converted": 2}]}]}
        self.assertEqual(workflow_exit_code(2, report), 1)
        self.assertIn("vacancy_discovery_unavailable", assess_run(report)["reasons"])
        # pyrefly: ignore [unsupported-operation]
        report["sources"][0]["queries"][0] = {"status": "valid_empty", "converted": 0}
        self.assertEqual(workflow_exit_code(2, report), 0)

    def test_delivery_state_and_unexpected_errors_remain_fatal(self):
        base = {"health": "degraded", "sources": [
            {"source": "Rozee.pk", "queries": [{"status": "success", "converted": 5}]}]}
        for update in [
            {"error": "StateError"},
            {"counts": {"delivery_failed_or_uncertain": 1}},
            {"counts": {"permanent_delivery_failures": 1}},
            {"deliveries": [{"status": "uncertain"}]},
        ]:
            report = {**base, **update}
            self.assertEqual(workflow_exit_code(2, report), 1)
        self.assertEqual(workflow_exit_code(1, base), 1)
        self.assertEqual(workflow_exit_code(137, base), 1)

    def test_google_probe_does_not_fail_when_primary_queries_are_not_due(self):
        report = {"health": "degraded", "sources": [
            {"source": "JobSpy", "queries": [{"status": "unverified", "site": "google", "converted": 0}]},
            {"source": "Rozee.pk", "skipped": True, "queries": []}]}
        self.assertEqual(workflow_exit_code(2, report), 0)
        # pyrefly: ignore [bad-index, unsupported-operation]
        report["sources"][0]["queries"][0]["site"] = "indeed"
        self.assertEqual(workflow_exit_code(2, report), 1)

    def test_google_cursor_warning_is_specific_and_single_page_results_survive(self):
        handler = HealthHandler()
        handler.emit(logging.LogRecord("JobSpy:Google", logging.WARNING, "", 1,
            "initial cursor not found, try changing your query or there was at most 10 results", (), None))
        self.assertEqual(handler.codes, ["google_jobs_cursor_missing"])
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["google"])]
        empty = fetch_jobspy_jobs(config, runner=lambda *_: {"rows": [], "warnings": handler.codes})
        query = empty.report.queries[0]
        self.assertEqual((query.status, query.site, query.reason),
                         ("unverified", "google", "google_jobs_cursor_missing"))
        self.assertFalse(empty.updates)
        rows = [{"title": "Python Developer", "job_url": "https://example.test/job"}]
        filled = fetch_jobspy_jobs(config, runner=lambda *_: {"rows": rows, "warnings": handler.codes})
        self.assertEqual(filled.report.status, "success")
        self.assertTrue(filled.updates)
        self.assertIn("google_initial_page_only", filled.report.notes)

    def test_irrelevant_search_hits_are_filtered_without_becoming_scrape_errors(self):
        config = load_config()
        config["linkedin_posts"]["queries"] = ["fixture"]
        factory = MagicMock()
        search = factory.return_value.__enter__.return_value
        search.text.return_value = [{"href": "https://example.test/unrelated", "title": "Irrelevant"}]
        with patch("ddgs.DDGS", factory), patch("scrapers.linkedin_posts_scraper.inspect_post") as inspect:
            result = fetch_linkedin_plain_posts(config)
        inspect.assert_not_called()
        self.assertEqual(result.report.status, "valid_empty")
        self.assertEqual(result.report.queries[0].invalid, 0)
        self.assertIn("ignored_non_post_results:1", result.report.notes)
        self.assertEqual(search.text.call_args.kwargs["backend"], "brave,duckduckgo,yahoo")
        self.assertTrue(any("last_success" in v for v in result.updates.values()))
        config["linkedin_posts"]["search_backends"] = ["wikipedia"]
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_search_provider_failure_is_visible_and_never_advances_watermark(self):
        from ddgs.exceptions import DDGSException
        config = load_config()
        config["linkedin_posts"]["queries"] = ["fixture"]
        factory = MagicMock()
        factory.return_value.__enter__.return_value.text.side_effect = DDGSException("upstream unavailable")
        with patch("ddgs.DDGS", factory):
            result = fetch_linkedin_plain_posts(config)
        self.assertEqual(result.report.queries[0].reason, "search_providers_unavailable")
        self.assertFalse(any("last_success" in v for v in result.updates.values()))

    def test_actions_runner_dry_run_disables_state_persistence_and_warns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = json.loads((FIXTURES / "production_health.json").read_text())[0]
            report["finished_at"] = "2026-09-08T12:00:00Z"
            atomic_write_json(root / "output/latest/run.json", report)
            output = root / "step-output"
            with patch.object(workflow_runner, "BASE_DIR", root), \
                 patch.dict("os.environ", {"JOB_FINDER_DRY_RUN": "true", "GITHUB_OUTPUT": str(output)}), \
                 patch.object(workflow_runner, "run_job_finder", return_value=2) as run, patch("builtins.print") as output_log:
                self.assertEqual(workflow_runner.main(), 0)
                self.assertTrue(any("::warning::" in str(call) for call in output_log.call_args_list))
            self.assertTrue(run.call_args.kwargs["dry_run"])
            self.assertEqual(output.read_text().strip(), "persist_state=false")

    def test_summary_identifies_sources_and_explains_zero_alerts(self):
        with tempfile.TemporaryDirectory() as directory:
            report = json.loads((FIXTURES / "production_health.json").read_text())[0]
            write_report(report, directory, step_summary=False)
            summary = (Path(directory) / "summary.md").read_text(encoding="utf-8")
            self.assertIn("Operational outcome: **warning**", summary)
            self.assertIn("upstream_warning", summary)
            self.assertIn("No candidates met the qualified-only alert policy", summary)
