import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pandas as pd
from config import load_config
from scrapers.base import Job, merge_jobs
from scrapers.jobspy_adapter import build_query, row_to_job, fetch_jobspy_jobs, run_query
from scrapers.common import SourceError, get_public
from scrapers.rozee_scraper import parse_rozee, fetch_rozee_jobs
from scrapers.linkedin_posts_scraper import valid_post_url, is_post_active_and_recent
from scrapers.remote_feeds import parse_remotive, parse_wwr, fetch_remote_feeds
from tests.support import OfflineTestCase, job

FIXTURES = Path(__file__).parent / "fixtures"


def page(text, status=200):
    return SimpleNamespace(text=text, content=text.encode(), status_code=status, headers={})


class SourceTests(OfflineTestCase):
    def test_query_params_are_site_specific(self):
        config = load_config()
        remote = config["search_tracks"][1]
        indeed = build_query(config, remote, "Python", "indeed")
        self.assertTrue(indeed["is_remote"])
        self.assertNotIn("hours_old", indeed)
        local = build_query(config, config["search_tracks"][0], "Python", "indeed")
        self.assertEqual(local["hours_old"], 168)
        linkedin = build_query(config, config["search_tracks"][2], "Python", "linkedin")
        self.assertIsNone(linkedin["location"])
        self.assertTrue(linkedin["linkedin_fetch_description"])
        google = build_query(config, config["search_tracks"][2], "Python", "google")
        self.assertIn("worldwide Pakistan eligible", google["google_search_term"])

    def test_source_remote_flag_is_not_query_intent(self):
        config = load_config()
        row = dict(title="Python Developer", company="Fixture", job_url="https://example.test/1",
                   location="Lahore, Pakistan", description="On-site only", is_remote=False)
        result = row_to_job(row, "indeed", config["search_tracks"][1], "q")
        self.assertFalse(result.is_remote)
        row.update(location="United States", description="Python", is_remote=True)
        self.assertTrue(row_to_job(row, "indeed", config["search_tracks"][0], "q").is_remote)

    def test_null_normalization_and_per_row_failure(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["indeed"])]
        row = dict(title="Python Developer", job_url="https://example.test/1",
                   company=pd.NA, location=float("nan"), date_posted=pd.NaT, description=None)
        bad = dict(row, job_url="javascript:bad")
        result = fetch_jobspy_jobs(config, runner=lambda *_: {"rows": [bad, row]})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].company, "")
        self.assertEqual(result[0].location, "")
        self.assertEqual(result[0].posted_at, "")
        self.assertEqual(result.report.queries[0].invalid, 1)

    def test_later_page_adds_results_and_repeated_page_stops(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["indeed"])]
        config["jobspy"].update(results_wanted=1, max_pages=3)
        calls = []
        def runner(kwargs, timeout):
            calls.append(kwargs["offset"])
            number = min(kwargs["offset"], 1)
            return {"rows": [dict(title="Python Developer", job_url=f"https://example.test/{number}")] }
        result = fetch_jobspy_jobs(config, runner=runner)
        self.assertEqual(calls, [0, 1, 2])
        self.assertEqual(len(merge_jobs(result)), 2)

    def test_source_failure_does_not_advance_watermark(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["indeed"])]
        def runner(*_):
            raise SourceError("blocked", "fixture")
        result = fetch_jobspy_jobs(config, runner=runner)
        self.assertEqual(result.report.status, "failed")
        self.assertEqual(result.updates, {})

    def test_later_page_failure_does_not_advance_watermark(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["indeed"])]
        config["jobspy"].update(results_wanted=1, max_pages=2)
        def runner(kwargs, timeout):
            if kwargs["offset"]:
                raise SourceError("blocked", "fixture")
            return {"rows": [{"title": "Python Developer", "job_url": "https://example.test/1"}]}
        result = fetch_jobspy_jobs(config, runner=runner)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.updates, {})

    def test_distinct_native_ids_and_generic_career_pages_are_not_merged(self):
        items = [job("a", source_id="one", application_url="https://example.test/careers"),
                 job("b", source_id="two", application_url="https://example.test/careers")]
        self.assertEqual(len(merge_jobs(items)), 2)
        self.assertEqual(len(merge_jobs([job(source_id="one"), job(source_id="two")])), 2)

    def test_worker_timeout_is_classified(self):
        import subprocess
        with patch("scrapers.jobspy_adapter.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 1)):
            with self.assertRaises(SourceError) as context:
                run_query({}, 1)
        self.assertEqual(context.exception.status, "timed_out")

    def test_stable_identity_and_richer_merge(self):
        one = job(url="https://example.test/job/1?utm_source=a", description="", description_status="missing")
        two = job(url="https://example.test/job/1?utm_source=b", description="Python Django required.")
        self.assertEqual(one.job_id, two.job_id)
        merged = merge_jobs([one, two])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].description, "Python Django required.")
        self.assertEqual(len(merge_jobs([job("a"), job("b")])), 2)
        self.assertEqual(Job.from_dict(job(location="", is_remote=None).to_dict()).work_mode, "unknown")

    def test_rozee_bootstrap_uses_actual_facts(self):
        rows, invalid = parse_rozee((FIXTURES / "rozee_bootstrap.html").read_text(), "https://www.rozee.pk/search")
        self.assertEqual(invalid, 0)
        item = rows[0]
        self.assertEqual(item.location, "Karachi, Pakistan")
        self.assertEqual(item.description_status, "full")
        self.assertTrue(item.posted_at.startswith("2026-09-06"))
        self.assertIsNone(item.salary_min, "Hidden salary index fields must not be exposed")

    def test_rozee_fallbacks_do_not_invent_city_or_freshness(self):
        for filename in ("rozee_structured.html", "rozee_cards.html"):
            rows, invalid = parse_rozee((FIXTURES / filename).read_text(), "https://www.rozee.pk/search")
            self.assertEqual(invalid, 0)
            self.assertIn("Lahore", rows[0].location)
        config = load_config()
        config["local_scrapers"]["max_queries"] = 1
        with patch("scrapers.rozee_scraper.get_public", return_value=page((FIXTURES / "rozee_loading.html").read_text())):
            result = fetch_rozee_jobs(config)
        self.assertEqual(result.report.status, "failed")
        self.assertEqual(result.report.queries[0].reason, "expected_listing_markup_missing")

    def test_rozee_empty_is_distinct_from_broken_markup(self):
        config = load_config()
        config["local_scrapers"]["max_queries"] = 1
        html = '<script>var apResp = {"response":{"jobs":{"basic":[]},"numFound":0}};</script>'
        with patch("scrapers.rozee_scraper.get_public", return_value=page(html)):
            result = fetch_rozee_jobs(config)
        self.assertEqual(result.report.status, "valid_empty")

    def test_post_hosts_and_unverified_dates(self):
        self.assertTrue(valid_post_url("https://www.linkedin.com/posts/fixture"))
        self.assertFalse(valid_post_url("https://linkedin.com.evil.test/posts/fixture"))
        self.assertFalse(valid_post_url("https://example.test/posts/fixture"))
        with patch("scrapers.linkedin_posts_scraper.inspect_post", side_effect=SourceError("blocked", "403")):
            self.assertFalse(is_post_active_and_recent("https://www.linkedin.com/posts/fixture"))
        with patch("scrapers.linkedin_posts_scraper.inspect_post", return_value={
            "status": "active", "posted_at": datetime.now(timezone.utc).isoformat(), "text": "2025 graduates welcome"}):
            self.assertTrue(is_post_active_and_recent("https://www.linkedin.com/posts/fixture", "2025 graduates welcome"))

    def test_remote_feeds_preserve_eligibility_and_ambiguous_pay(self):
        rows, invalid = parse_remotive({"jobs": [{"id": 1, "title": "Python Developer",
            "company_name": "Fixture", "url": "https://remotive.com/remote-jobs/fixture",
            "candidate_required_location": "US only", "description": "<p>Python</p>", "salary": "$1000"}]}, 10)
        self.assertEqual(rows[0].candidate_locations, "US only")
        self.assertEqual(rows[0].salary_currency, "")
        self.assertEqual(invalid, 0)
        rss = "<rss><channel><item><title>Fixture: Python Developer</title><link>https://weworkremotely.com/remote-jobs/fixture</link><description>Python</description><pubDate>Sun, 06 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>"
        rows, _ = parse_wwr(rss, 10)
        self.assertEqual(rows[0].company, "Fixture")
        self.assertEqual(rows[0].location, "")
        self.assertTrue(rows[0].posted_at.startswith("2026-09-06"))

    def test_remotive_cadence_skips_recent_fetch(self):
        config = load_config()
        config["remote_feeds"]["remotive_enabled"] = True
        with patch("scrapers.remote_feeds.get_public") as get:
            result = fetch_remote_feeds(config, {"feed:remotive": {"last_success": datetime.now(timezone.utc).isoformat()}})
        self.assertTrue(result.report.skipped)
        get.assert_not_called()

    def test_redirect_allowlist_and_block_status(self):
        redirect = page("", 302)
        redirect.headers = {"Location": "https://example.test/private"}
        with patch("scrapers.common.requests.get", return_value=redirect):
            with self.assertRaises(SourceError) as context:
                get_public("https://www.rozee.pk/search", ("rozee.pk",))
        self.assertEqual(context.exception.reason, "unexpected_redirect_host")
        with patch("scrapers.common.requests.get", return_value=page("", 403)):
            with self.assertRaises(SourceError) as context:
                get_public("https://www.rozee.pk/search", ("rozee.pk",))
        self.assertEqual(context.exception.status, "blocked")
