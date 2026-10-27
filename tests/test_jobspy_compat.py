"""Exercise the installed JobSpy API without making job-board requests."""
import io
import json
import logging
from datetime import date
from unittest.mock import patch

import jobspy
from jobspy.model import Country, JobPost, Location, Scraper, Site

from job_finder.configuration.loader import load_config
from job_finder.scrapers.common import SourceError
from job_finder.scrapers.jobspy_adapter import build_query, row_to_job, run_query
from job_finder.scrapers.jobspy_worker import main as worker_main
from tests.support import OfflineTestCase


class JobSpyCompatibilityTests(OfflineTestCase):
    def invoke(self, mode, site="indeed"):
        calls = []

        class FixtureScraper(Scraper):
            def scrape(self, scraper_input):
                calls.append(scraper_input)
                if mode == "empty":
                    return []
                if mode == "blocked":
                    # Exercise DataFrame.attrs even when upstream emits no log.
                    self.error = "response status code 403 https://private.example/token"
                    return []
                if mode == "partial":
                    self.warnings = ["a detail request timed out"]
                    logging.getLogger("jobspy.indeed").warning("skipping an invalid job")
                return [JobPost(id="fixture-1", title="Junior Python Developer", company="Fixture",
                    job_url="https://example.test/job/1", location=Location(city="Karachi", country=Country.PAKISTAN),
                    description="Python Django. Fresh graduates welcome.", is_remote=False,
                    date_posted=date(2026, 10, 26), min_amount=50000, currency="PKR")]

        config = load_config()
        args = build_query(config, config["search_tracks"][0], "Python", site)
        output = io.StringIO()
        with patch.dict(jobspy.SCRAPER_MAPPING, {Site(site): FixtureScraper}), \
             patch("sys.stdin", io.StringIO(json.dumps(args))), patch("sys.stdout", output):
            worker_main()
        return json.loads(output.getvalue()), calls

    def test_installed_api_serializes_job_evidence_and_uses_new_detail_option(self):
        payload, calls = self.invoke("success", "linkedin")
        self.assertNotIn("error", payload)
        self.assertTrue(calls[0].fetch_description)
        self.assertEqual(payload["warnings"], [])
        result = row_to_job(payload["rows"][0], "linkedin", load_config()["search_tracks"][0], "fixture")
        self.assertEqual(result.location, "Karachi, Pakistan")
        self.assertEqual(result.description_status, "full")
        self.assertEqual(result.salary_source, "disclosed")
        self.assertEqual(result.salary_currency, "PKR")
        self.assertFalse(result.is_remote)

    def test_blocked_attrs_cannot_look_like_valid_empty_or_expose_raw_errors(self):
        payload, _ = self.invoke("blocked")
        self.assertEqual(payload, {"rows": [], "warnings": ["blocked"]})

    def test_partial_attrs_and_lowercase_logging_preserve_rows_and_health(self):
        payload, _ = self.invoke("partial")
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(set(payload["warnings"]), {"timed_out", "upstream_warning"})
        empty, _ = self.invoke("empty")
        self.assertEqual(empty, {"rows": [], "warnings": []})

    def test_real_worker_subprocess_uses_installed_api_and_reports_invalid_input(self):
        # Validation occurs before any network access, inside the real child interpreter.
        with self.assertRaises(SourceError) as context:
            run_query({"site_name": ["not-a-job-board"]}, 30)
        self.assertEqual(context.exception.reason, "ValueError")
