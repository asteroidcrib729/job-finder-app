import copy
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ddgs.exceptions import DDGSException, RatelimitException

from job_finder.application.health import assess_run
from job_finder.configuration.loader import load_config, validate_config
from job_finder.scrapers.cache import DetailCache
from job_finder.scrapers.common import SourceError, SourceResult
from job_finder.scrapers.jobspy_adapter import fetch_jobspy_jobs, row_to_job
from job_finder.scrapers.jobspy_worker import HealthHandler
from job_finder.scrapers.linkedin_details import COOLDOWN_KEY, enrich_linkedin_jobs, parse_detail
from job_finder.scrapers.linkedin_posts_scraper import fetch_linkedin_plain_posts
from job_finder.scrapers.metrics import source_coverage
from job_finder.scrapers.remote_feeds import fetch_remote_feeds
from job_finder.storage.reconcile import merge_discovery, validate_discovery_state
from tests.support import OfflineTestCase
from tests.test_sources import page


class SourceResilienceTests(OfflineTestCase):
    def config(self, sites=None):
        config = load_config()
        config["search_keywords"] = ["Python", "React", "Node", "Next.js"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=sites or ["indeed"])]
        config["jobspy"].update(interval_hours=0, low_yield_interval_hours=0)
        return config

    def row(self, number=1, **changes):
        row = {"id": f"li-{number}", "title": "Junior Python Developer", "company": "Fixture",
               "job_url": f"https://www.linkedin.com/jobs/view/{number}", "location": "Karachi",
               "is_remote": False, "date_posted": "2026-10-27"}
        return {**row, **changes}

    def test_warning_classification_does_not_pause_productive_searches(self):
        handler = HealthHandler()
        for text in ["is_remote isn't supported, ignoring it", "job 123: response status code 429",
                     "job 456: request timed out", "no job data returned"]:
            handler.record_message(text)
        self.assertEqual(handler.codes, ["unsupported_option", "detail_blocked", "detail_timed_out", "google_no_job_data"])
        calls = []
        def runner(kwargs, timeout):
            calls.append(kwargs)
            return {"rows": [self.row(len(calls))], "warnings": ["unsupported_option", "upstream_warning"]}
        result = fetch_jobspy_jobs(self.config(), runner=runner)
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(result), 4)
        self.assertNotIn("source_paused_after_repeated_failures", result.report.notes)
        self.assertEqual(result.report.status, "partial", "Unknown warnings must remain visible")

    def test_blocked_searches_pause_only_the_affected_site(self):
        calls = []
        def runner(kwargs, timeout):
            site = kwargs["site_name"][0]
            calls.append(site)
            return {"rows": [], "warnings": ["blocked"]} if site == "linkedin" else {"rows": [self.row()]}
        result = fetch_jobspy_jobs(self.config(["linkedin", "indeed"]), runner=runner)
        self.assertEqual(calls.count("linkedin"), 3)
        self.assertEqual(calls.count("indeed"), 4)
        self.assertEqual(len(result), 4)

    def test_detail_block_preserves_listing_searches_watermarks_and_retry_cooldown(self):
        config = self.config(["linkedin"])
        calls = []
        def runner(kwargs, timeout):
            self.assertFalse(kwargs["fetch_description"])
            self.assertNotIn("is_remote", kwargs)
            calls.append(kwargs)
            return {"rows": [self.row(len(calls))]}
        fetcher = MagicMock(side_effect=SourceError("blocked", "http_429"))
        result = fetch_jobspy_jobs(config, runner=runner, detail_fetcher=fetcher, sleep=lambda _: None)
        self.assertEqual(len(calls), 4)
        self.assertEqual(len(result), 4)
        fetcher.assert_called_once()
        self.assertEqual(sum("last_success" in record for record in result.updates.values()), 4)
        self.assertIn("last_attempt", result.updates[COOLDOWN_KEY])
        second = fetch_jobspy_jobs(config, result.updates, runner=runner, detail_fetcher=fetcher)
        fetcher.assert_called_once()
        self.assertIn("linkedin_details_cooling_down", second.report.notes)
        self.assertEqual(assess_run({"health": "degraded", "sources": [result.report.to_dict()]})["status"], "warning")

    def test_detail_cache_preserves_card_facts_and_recomputes_explicit_remote_evidence(self):
        config = self.config(["linkedin"])
        row = self.row(location="Pakistan")
        cached = DetailCache({}, "linkedin", 6)
        cached.put(row["job_url"], {"description": "Fully remote role in Pakistan. Python Django.",
                                    "location": "United States", "posted_at": "2020-01-01"})
        updates = SourceResult("Fixture")
        cached.publish(updates)
        state = copy.deepcopy(updates.updates)
        fetcher = MagicMock()
        result = fetch_jobspy_jobs(config, state, runner=lambda *_: {"rows": [row]}, detail_fetcher=fetcher)
        fetcher.assert_not_called()
        self.assertEqual(result[0].location, "Pakistan")
        self.assertTrue(result[0].posted_at.startswith("2026-10-27"))
        self.assertEqual(result[0].work_mode, "remote")
        self.assertEqual(result[0].description_status, "full")
        self.assertIn("cached_description", result[0].evidence_warnings)
        self.assertEqual(state, updates.updates, "Adapters must not mutate supplied discovery state")

    def test_expired_details_are_not_used_when_refetch_is_blocked(self):
        config = self.config(["linkedin"])
        cached = DetailCache({}, "linkedin", 6, now=datetime.now(timezone.utc) - timedelta(days=2))
        cached.put(self.row()["job_url"], {"description": "Old Python requirements"})
        state = SourceResult("Fixture")
        cached.publish(state)
        result = fetch_jobspy_jobs(config, state.updates, runner=lambda *_: {"rows": [self.row()]},
            detail_fetcher=MagicMock(side_effect=SourceError("blocked", "http_403")))
        self.assertEqual(result[0].description, "")
        self.assertEqual(result[0].description_status, "fetch_failed")
        self.assertEqual(result.updates["cache:linkedin"]["entries"], {})

    def test_detail_queue_shares_budget_between_tracks_and_paces_requests(self):
        config = self.config(["linkedin"])
        config["jobspy"]["linkedin_max_details"] = 2
        result = SourceResult("JobSpy", [row_to_job(self.row(i), "linkedin",
            {"id": "local" if i < 3 else "remote"}, "q") for i in range(1, 5)])
        calls, delays = [], []
        def fetch(url, timeout):
            calls.append(url)
            return {"description": "Python Django. Fresh graduates welcome."}
        enrich_linkedin_jobs(result, config, {}, fetcher=fetch, sleep=delays.append)
        self.assertEqual(calls, [self.row(1)["job_url"], self.row(3)["job_url"]])
        self.assertEqual(delays, [2])
        self.assertEqual(sum(job.description_status == "full" for job in result), 2)
        self.assertIn("linkedin_detail_budget_exhausted", result.report.notes)

    def test_detail_parsers_preserve_requirement_boundaries_and_reject_missing_markup(self):
        html = '<div class="show-more-less-html__markup"><p>Python.</p><p>1 year required.</p></div>'
        self.assertEqual(parse_detail(html)["description"], "Python.\n1 year required.")
        structured = '<script type="application/ld+json">' + json.dumps({"@type": "JobPosting",
            "description": "<p>Django.</p><p>Fresh graduates.</p>"}) + '</script>'
        self.assertEqual(parse_detail(structured)["description"], "Django.\nFresh graduates.")
        with self.assertRaises(SourceError):
            parse_detail('<html>Please sign in</html>')

    def test_google_probe_attempts_once_and_failed_attempt_is_not_success(self):
        config = self.config(["indeed", "google"])
        calls = []
        def runner(kwargs, timeout):
            calls.append(kwargs["site_name"][0])
            return {"rows": [], "warnings": ["google_no_job_data"]} if calls[-1] == "google" else {"rows": []}
        first = fetch_jobspy_jobs(config, runner=runner)
        self.assertEqual(calls, ["indeed"] * 4 + ["google"])
        self.assertIn("last_attempt", first.updates["probe:google"])
        self.assertNotIn("last_success", first.updates["probe:google"])
        fetch_jobspy_jobs(config, first.updates, runner=runner)
        self.assertEqual(calls.count("google"), 1)
        config["jobspy"]["google_mode"] = "disabled"
        fetch_jobspy_jobs(config, runner=runner)
        self.assertEqual(calls.count("google"), 1)

    def test_phase_coverage_counts_details_separately_from_listing_searches(self):
        config = self.config(["linkedin"])
        config["search_keywords"] = ["Python"]
        result = fetch_jobspy_jobs(config, runner=lambda *_: {"rows": [self.row()]},
            detail_fetcher=lambda *_: {"description": "Python Django. Fresh graduates welcome."})
        item = source_coverage([result])[0]
        self.assertEqual((item["search_requests"], item["usable_searches"], item["detail_requests"]), (1, 1, 1))
        self.assertEqual((item["full_descriptions"], item["unique_jobs"]), (1, 1))

    def test_expired_job_is_not_a_detail_service_outage_and_budget_remains_bounded(self):
        config = self.config(["linkedin"])
        config["jobspy"]["linkedin_max_details"] = 4
        result = SourceResult("JobSpy", [row_to_job(self.row(i), "linkedin", {"id": "local"}, "q") for i in range(1, 5)])
        fetcher = MagicMock(side_effect=[SourceError("closed", "http_404"), SourceError("closed", "http_410"),
            SourceError("timed_out", "request_timeout"), {"description": "Python Django"}])
        enrich_linkedin_jobs(result, config, {}, fetcher=fetcher, sleep=lambda _: None)
        self.assertEqual(fetcher.call_count, 4)
        self.assertEqual(result[0].active_status, "closed")
        self.assertEqual(result[-1].description_status, "full")
        self.assertNotIn(COOLDOWN_KEY, result.updates)

    def test_search_fallback_recovers_after_rate_limit_and_keeps_backend_evidence(self):
        config = load_config()
        config["linkedin_posts"]["queries"] = ['site:linkedin.com/posts "Karachi" ("React" OR "Python") hiring']
        factory = MagicMock()
        search = factory.return_value.__enter__.return_value
        search.text.side_effect = [RatelimitException("429 https://private.test/token"),
            [{"href": "https://www.linkedin.com/posts/fixture", "title": "Python Developer", "body": "Karachi hiring Python"}]]
        with patch("ddgs.DDGS", factory), patch("job_finder.scrapers.linkedin_posts_scraper.inspect_post",
                return_value={"status": "active", "text": "Karachi Python hiring. Fresh graduates.", "posted_at": "2026-10-27"}):
            result = fetch_linkedin_plain_posts(config)
        self.assertEqual(len(result), 1)
        self.assertEqual([call.kwargs["backend"] for call in search.text.call_args_list], ["brave", "duckduckgo"])
        self.assertEqual(result.report.queries[0].reason, "search_rate_limited")
        self.assertEqual(result.report.queries[1].backend, "duckduckgo")
        self.assertNotIn("private.test", json.dumps(result.report.to_dict()))

    def test_ambiguous_no_results_triggers_simplified_queries_without_false_success(self):
        config = load_config()
        config["linkedin_posts"]["queries"] = ['site:linkedin.com/posts "Karachi" ("React" OR "Python") hiring']
        factory = MagicMock()
        search = factory.return_value.__enter__.return_value
        search.text.side_effect = DDGSException("No results found.")
        with patch("ddgs.DDGS", factory):
            result = fetch_linkedin_plain_posts(config)
        self.assertEqual(search.text.call_count, 6)
        self.assertNotIn("(", search.text.call_args_list[-1].args[0])
        self.assertIsNone(search.text.call_args_list[-1].kwargs["timelimit"])
        self.assertEqual(result.report.queries[0].reason, "search_no_results_unconfirmed")
        self.assertFalse(any("last_success" in item for item in result.updates.values()))

    def test_backend_failure_cooldown_survives_next_run_and_budget_is_global(self):
        config = load_config()
        config["linkedin_posts"]["max_search_attempts"] = 2
        factory = MagicMock()
        search = factory.return_value.__enter__.return_value
        search.text.side_effect = DDGSException("service error with secret https://private.test/token")
        with patch("ddgs.DDGS", factory):
            first = fetch_linkedin_plain_posts(config)
            second = fetch_linkedin_plain_posts(config, first.updates)
        self.assertEqual(search.text.call_count, 3, "Only the remaining third backend may run in the second cycle")
        self.assertIn("post_search_budget_exhausted", first.report.notes)
        self.assertNotIn("secret", json.dumps(first.updates))
        self.assertFalse(any("last_success" in item for item in second.updates.values()))

    def test_failed_feed_attempts_respect_cadence_and_do_not_claim_success(self):
        config = load_config()
        config["remote_feeds"].update(remotive_enabled=True, wwr_enabled=True)
        with patch("job_finder.scrapers.remote_feeds.get_public", side_effect=[
                SourceError("blocked", "http_429"), page('<rss><channel/></rss>')]) as get:
            first = fetch_remote_feeds(config)
            second = fetch_remote_feeds(config, first.updates)
        self.assertEqual(get.call_count, 2)
        self.assertIn("last_attempt", first.updates["feed:remotive"])
        self.assertNotIn("last_success", first.updates["feed:remotive"])
        self.assertIn("last_success", first.updates["feed:wwr"])
        self.assertTrue(second.report.skipped)

    def test_new_policy_validation_and_concurrent_retry_state(self):
        for section, key, value in [("jobspy", "google_mode", "silently_ignore"),
                ("jobspy", "linkedin_detail_delay", 0), ("linkedin_posts", "max_search_attempts", 0)]:
            config = load_config()
            config[section][key] = value
            with self.assertRaises(ValueError):
                validate_config(config)
        key = "attempt:posts:brave"
        older = {key: {"last_attempt": "2026-10-27T10:00:00Z"}}
        newer = {key: {"last_attempt": "2026-10-27T12:00:00Z"}}
        self.assertEqual(merge_discovery({}, older, newer)[key], newer[key])
        from job_finder.storage.tracker import StateError
        with self.assertRaises(StateError):
            validate_discovery_state({key: {"last_attempt": "invalid"}})
