import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from config import load_config
from scrapers.base import Job
from scrapers.cache import DetailCache, query_due, query_key
from scrapers.common import SourceError, SourceResult
from scrapers.rozee_scraper import fetch_rozee_jobs, job_from_bootstrap
from scrapers.linkedin_posts_scraper import fetch_linkedin_plain_posts
from tests.support import OfflineTestCase
from tests.test_sources import page

NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


def listing(number, following=None, full=True):
    row = {"jid": str(number), "title": "Junior Python Developer", "city": "Karachi",
           "rozeePermaLink": f"fixture-python-jobs-{number}",
           "description_raw": "<p>Python Django.</p><p>Fresh graduates welcome.</p>" if full else "",
           "created_at": "2026-09-07", "description": "Python"}
    payload = {"jobs": {"basic": [row]}, "numFound": 80}
    if following is not None:
        payload["pagination"] = {"list": [{"type": "m", "lang": "Next", "fpn": following}]}
    return page("<script>var apResp = " + json.dumps({"response": payload}) + ";</script>")


class CachePaginationTests(OfflineTestCase):
    def config(self):
        config = load_config()
        config["local_scrapers"].update(max_queries=1, max_pages=4, keywords=["Python"])
        config["linkedin_posts"].update(queries=["fixture query"])
        return config

    def test_cache_expiry_future_dates_bounds_and_copy_isolation(self):
        cache = DetailCache({}, "fixture", 6, now=NOW)
        for n in range(205):
            cache.put(f"https://example.test/{n}", {"text": str(n)})
        result = SourceResult("Fixture")
        cache.publish(result)
        self.assertEqual(len(cache.entries), 200)
        copy_cache = DetailCache(result.updates, "fixture", 6, now=NOW + timedelta(hours=1))
        url = next(iter(copy_cache.entries))
        data = copy_cache.get(url)
        data["text"] = "modified"
        self.assertNotEqual(copy_cache.get(url)["text"], "modified")
        self.assertEqual(DetailCache(result.updates, "fixture", 6, now=NOW + timedelta(hours=6)).entries, {})
        self.assertEqual(DetailCache(result.updates, "fixture", 6, now=NOW - timedelta(hours=1)).entries, {})
        self.assertEqual(DetailCache(result.updates, "fixture", 0, now=NOW).entries, {})

    def test_rozee_second_page_retains_identity_and_html_paragraphs(self):
        with patch("scrapers.rozee_scraper.get_public", side_effect=[listing(1, 20), listing(2)]) as get:
            result = fetch_rozee_jobs(self.config())
        self.assertEqual(len(result), 2)
        self.assertEqual(get.call_count, 2)
        self.assertTrue(get.call_args.args[0].endswith("/fc/1184/fpn/20"))
        self.assertNotIn("<p>", result[0].description)
        self.assertIn("Fresh graduates", result[0].description)
        self.assertIn(query_key("rozee", "Python"), result.updates)

    def test_failed_or_repeated_page_never_advances_query_watermark(self):
        for tail in (listing(1, 40), SourceError("blocked", "fixture"), listing(2, 20)):
            with self.subTest(tail=type(tail).__name__):
                with patch("scrapers.rozee_scraper.get_public", side_effect=[listing(1, 20), tail]) as get:
                    result = fetch_rozee_jobs(self.config())
                self.assertNotIn(query_key("rozee", "Python"), result.updates)
                self.assertEqual(result.report.status, "partial")
                self.assertEqual(get.call_count, 2)

    def test_recent_rozee_query_skips_and_stale_cache_does_not_mask_block(self):
        config = self.config()
        key = query_key("rozee", "Python")
        with patch("scrapers.rozee_scraper.get_public") as get:
            result = fetch_rozee_jobs(config, {key: {"last_success": datetime.now(timezone.utc).isoformat()}})
        get.assert_not_called()
        self.assertTrue(result.report.skipped)
        url = "https://www.rozee.pk/fixture-python-jobs-1"
        cached = DetailCache({}, "rozee", 6, now=NOW - timedelta(days=5))
        cached.put(url, {"url": url, "description": "stale"})
        updates = SourceResult("Fixture")
        cached.publish(updates)
        with patch("scrapers.rozee_scraper.get_public", side_effect=[listing(1, full=False), SourceError("blocked", "fixture")]):
            result = fetch_rozee_jobs(config, updates.updates)
        self.assertEqual(result[0].description_status, "fetch_failed")
        self.assertEqual(result[0].active_status, "unverified")
        self.assertEqual(result.report.status, "partial")
        self.assertNotIn(key, result.updates)
        self.assertEqual(result.updates["cache:rozee"]["entries"], {})

    def test_cached_detail_never_overwrites_current_listing_location_or_date(self):
        config = self.config()
        url = "https://www.rozee.pk/fixture-python-jobs-1"
        cached = DetailCache({}, "rozee", 6)
        cached.put(url, Job(title="Old title", company="Fixture", platform="Rozee.pk", url=url, location="Lahore",
            description="Python Django", description_status="full", posted_at="2020-01-01").to_dict())
        updates = SourceResult("Fixture")
        cached.publish(updates)
        original = copy.deepcopy(updates.updates)
        with patch("scrapers.rozee_scraper.get_public", return_value=listing(1, full=False)) as get:
            result = fetch_rozee_jobs(config, updates.updates)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(result[0].location, "Karachi")
        self.assertTrue(result[0].posted_at.startswith("2026-09-07"))
        self.assertIn("cached_description", result[0].evidence_warnings)
        self.assertEqual(updates.updates, original)

    def test_post_cadence_is_query_based_and_detail_cache_is_reused(self):
        config = self.config()
        factory = MagicMock()
        factory.return_value.__enter__.return_value.text.return_value = [
            {"href": "https://www.linkedin.com/posts/fixture", "title": "Python Developer", "body": "Karachi"}]
        post = {"status": "active", "text": "Karachi. Python Django. Fresh graduates welcome.",
                "posted_at": "2026-09-07"}
        with patch("ddgs.DDGS", factory), patch("scrapers.linkedin_posts_scraper.inspect_post", return_value=post) as inspect:
            first = fetch_linkedin_plain_posts(config)
            second = fetch_linkedin_plain_posts(config, first.updates)
            config["linkedin_posts"]["interval_hours"] = 0
            third = fetch_linkedin_plain_posts(config, first.updates)
        self.assertTrue(second.report.skipped)
        self.assertEqual(inspect.call_count, 1)
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(first[0].posted_at, third[0].posted_at)
        self.assertIn("cached_post", third[0].evidence_warnings)
        self.assertFalse(query_due(first.updates, query_key("posts", "fixture query"), 6))
        self.assertTrue(query_due(first.updates, query_key("posts", "changed query"), 6))

    def test_blocked_post_is_partial_without_success_watermark(self):
        config = self.config()
        factory = MagicMock()
        factory.return_value.__enter__.return_value.text.return_value = [
            {"href": "https://www.linkedin.com/posts/fixture", "title": "Python Developer", "body": "Karachi"}]
        with patch("ddgs.DDGS", factory), patch("scrapers.linkedin_posts_scraper.inspect_post", side_effect=SourceError("blocked", "fixture")):
            result = fetch_linkedin_plain_posts(config)
        self.assertEqual(result.report.status, "partial")
        self.assertNotIn(query_key("posts", "fixture query"), result.updates)
        self.assertEqual(result[0].active_status, "unverified")
