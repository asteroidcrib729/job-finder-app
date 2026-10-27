import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests

from job_finder.configuration.loader import load_config
from job_finder.scrapers.common import SourceError
from job_finder.scrapers.google_api import posted_date, result_row, run_google_api
from job_finder.scrapers.jobspy_adapter import fetch_jobspy_jobs
from tests.support import OfflineTestCase


class GoogleApiTests(OfflineTestCase):
    def args(self):
        return {"search_term": "Python", "google_search_term": "Python jobs near Karachi", "results_wanted": 10}

    def response(self, payload, status=200):
        return SimpleNamespace(status_code=status, content=json.dumps(payload).encode(), json=lambda: payload)

    def row(self):
        return {"job_id": "public-job-1", "title": "Junior Python Developer", "company_name": "Fixture",
            "location": "Pakistan", "description": "Python Django. Fully remote in Pakistan.",
            "apply_options": [{"link": "https://example.test/job/1"}],
            "detected_extensions": {"posted_at": "2 hours ago", "work_from_home": True}}

    def test_missing_key_performs_no_request(self):
        with patch.dict("os.environ", {}, clear=True), patch("job_finder.scrapers.google_api.requests.get") as get:
            with self.assertRaises(SourceError) as context:
                run_google_api(self.args(), 20)
        self.assertEqual(context.exception.reason, "missing_serpapi_key")
        get.assert_not_called()

    def test_real_response_contract_normalizes_jobs_without_inferred_currency(self):
        payload = {"search_metadata": {"status": "Success"}, "jobs_results": [self.row(), {"title": "Missing URL"}]}
        with patch.dict("os.environ", {"SERPAPI_API_KEY": "secret-fixture-key"}), \
             patch("job_finder.scrapers.google_api.requests.get", return_value=self.response(payload)) as get:
            result = run_google_api(self.args(), 20)
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["warnings"], ["google_api_invalid_rows"])
        self.assertTrue(result["rows"][0]["is_remote"])
        self.assertNotIn("currency", result["rows"][0])
        self.assertNotIn("secret-fixture-key", json.dumps(result))
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_error_payload_auth_quota_redirect_and_timeout_are_sanitized(self):
        cases = [(self.response({"error": "secret https://private.test/token"}), "google_api_invalid_response"),
            (self.response({}, 429), "google_api_auth_or_quota"),
            (self.response({}, 302), "google_api_http_error"),
            (requests.Timeout("secret-fixture-key"), "google_api_timeout")]
        with patch.dict("os.environ", {"SERPAPI_API_KEY": "secret-fixture-key"}):
            for value, expected in cases:
                with patch("job_finder.scrapers.google_api.requests.get", side_effect=value if isinstance(value, Exception) else None,
                        return_value=value), self.assertRaises(SourceError) as context:
                    run_google_api(self.args(), 20)
                self.assertEqual(context.exception.reason, expected)
                self.assertNotIn("secret", str(context.exception))

    def test_relative_dates_are_bounded_to_published_evidence(self):
        now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
        self.assertEqual(posted_date("2 days ago", now), (now - timedelta(days=2)).isoformat())
        self.assertEqual(posted_date("unknown", now), "")
        self.assertEqual(posted_date("2026-10-20"), "2026-10-20T00:00:00+00:00")

    def test_invalid_links_cannot_become_listing_destinations(self):
        item = self.row()
        item["apply_options"] = [{"link": "javascript:bad"}]
        with self.assertRaises(ValueError):
            result_row(item)

    def test_selected_provider_uses_separate_probe_state_and_never_calls_jobspy(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["google"])]
        config["jobspy"]["google_provider"] = "serpapi"
        runner = MagicMock()
        with patch("job_finder.scrapers.jobspy_adapter.run_google_api", return_value={"rows": []}) as api:
            first = fetch_jobspy_jobs(config, runner=runner)
            fetch_jobspy_jobs(config, first.updates, runner=runner)
        api.assert_called_once()
        runner.assert_not_called()
        self.assertIn("probe:google:serpapi", first.updates)

    def test_missing_credentials_do_not_delay_a_later_configured_probe(self):
        config = load_config()
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["google"])]
        config["jobspy"]["google_provider"] = "serpapi"
        with patch.dict("os.environ", {}, clear=True):
            result = fetch_jobspy_jobs(config)
        self.assertNotIn("probe:google:serpapi", result.updates)
        self.assertEqual(result.report.queries[0].reason, "missing_serpapi_key")

    def test_api_request_ceiling_applies_to_full_search_mode(self):
        config = load_config()
        config["search_keywords"] = ["Python", "React", "Node"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["google"])]
        config["jobspy"].update(google_provider="serpapi", google_mode="enabled", google_api_max_queries=1)
        with patch("job_finder.scrapers.jobspy_adapter.run_google_api", return_value={"rows": []}) as api:
            result = fetch_jobspy_jobs(config)
        api.assert_called_once()
        self.assertIn("google_api_budget_exhausted", result.report.notes)
