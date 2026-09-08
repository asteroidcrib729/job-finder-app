from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from config import load_config
from scrapers.base import utc_now
from scrapers.common import SourceError
from scrapers.jobspy_adapter import fetch_jobspy_jobs
from scrapers.metrics import query_metrics
from tests.support import OfflineTestCase


class QueryMetricsTests(OfflineTestCase):
    def config(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["indeed"])]
        return config

    def rows(self, good=True):
        return {"rows": [{"id": "fixture", "title": "Junior Python Developer" if good else "Senior Python Developer",
            "job_url": "https://example.test/job/fixture", "location": "Karachi",
            "description": "Python Django. Fresh graduates welcome.", "date_posted": utc_now()}]}

    def test_query_yield_is_saved_and_low_yield_cadence_remains_bounded(self):
        config = self.config()
        first = fetch_jobspy_jobs(config, runner=lambda *_: self.rows(False))
        metrics = query_metrics([first], config)
        key = next(iter(first.updates))
        self.assertEqual(metrics[key]["rejected"], 1)
        self.assertEqual(first.updates[key]["qualified"], 0)
        self.assertEqual(first.updates[key]["review"], 0)
        first.updates[key]["last_success"] = (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
        with patch("scrapers.jobspy_adapter.run_query") as run:
            skipped = fetch_jobspy_jobs(config, first.updates)
        run.assert_not_called()
        self.assertTrue(skipped.report.skipped)
        first.updates[key]["last_success"] = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
        result = fetch_jobspy_jobs(config, first.updates, runner=lambda *_: self.rows())
        self.assertEqual(len(result), 1)
        report = query_metrics([result], config)
        self.assertEqual(report[key]["qualified"], 1)
        self.assertEqual(report[key]["qualified_per_request"], 1)

    def test_failed_query_keeps_previous_success_and_yield(self):
        config = self.config()
        first = fetch_jobspy_jobs(config, runner=lambda *_: self.rows())
        key = next(iter(first.updates))
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        first.updates[key]["last_success"] = old
        with patch("scrapers.jobspy_adapter.run_query", side_effect=SourceError("blocked", "fixture")):
            failed = fetch_jobspy_jobs(config, first.updates)
        metrics = query_metrics([failed], config)
        self.assertFalse(failed.updates)
        self.assertEqual(first.updates[key]["last_success"], old)
        self.assertEqual(metrics[key]["qualified"], 0)
        self.assertEqual(metrics[key]["requests"], 1)

    def test_shared_first_page_does_not_hide_unique_second_page_of_another_query(self):
        config = self.config()
        config["search_keywords"] = ["Python", "Django"]
        config["jobspy"].update(max_pages=2, results_wanted=1)
        def runner(kwargs, timeout):
            number = kwargs["search_term"] if kwargs["offset"] else "shared"
            return {"rows": [{"title": "Python Developer", "job_url": "https://example.test/" + number}]}
        result = fetch_jobspy_jobs(config, runner=runner)
        self.assertEqual(len({job.url for job in result}), 3)
        self.assertEqual(len(result.report.queries), 4)
