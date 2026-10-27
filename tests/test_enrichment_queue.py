import copy
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ddgs.exceptions import DDGSException

from job_finder.application.pipeline import run_job_finder
from job_finder.configuration.loader import load_config, validate_config
from job_finder.scrapers.base import Job
from job_finder.scrapers.common import SourceError, SourceResult
from job_finder.scrapers.employer_details import fetch_employer_detail, posting
from job_finder.scrapers.jobspy_adapter import fetch_jobspy_jobs
from job_finder.scrapers.linkedin_details import enrich_linkedin_jobs
from job_finder.scrapers.linkedin_posts_scraper import fetch_linkedin_plain_posts
from job_finder.storage.enrichment import ADAPTIVE_KEY, QUEUE_KEY
from job_finder.storage.reconcile import merge_discovery, validate_discovery_state
from job_finder.storage.tracker import JobTracker, StateError
from tests.support import OfflineTestCase

NOW = datetime.now(timezone.utc).replace(microsecond=0)


def candidate(number=1, **changes):
    values = dict(title="Junior Python Developer", company="Fixture", location="Karachi",
        url=f"https://www.linkedin.com/jobs/view/{number}", source_id=f"li-{number}", platform="Linkedin",
        posted_at=NOW.isoformat(), search_track="local")
    return Job.from_dict({**values, **changes})


def detail(*_):
    return {"description": "Python Django. Fresh graduates welcome."}


class EnrichmentQueueTests(OfflineTestCase):
    def config(self):
        config = load_config()
        config["search_keywords"] = ["Python"]
        config["search_tracks"] = [dict(config["search_tracks"][0], sites=["linkedin"])]
        config["jobspy"].update(linkedin_max_details=8, linkedin_detail_initial_requests=2,
            linkedin_detail_min_requests=1, linkedin_detail_max_seconds=60)
        return config

    def queued(self, jobs, config=None):
        config = config or self.config()
        config = copy.deepcopy(config)
        config["jobspy"]["linkedin_max_details"] = 0
        result = SourceResult("JobSpy", jobs)
        enrich_linkedin_jobs(result, config, {}, fetcher=MagicMock(), now=NOW)
        return result.updates

    def test_queue_drains_after_restart_without_repeating_not_due_searches(self):
        config = self.config()
        rows = [{"id": f"li-{n}", "title": "Junior Python Developer", "job_url": candidate(n).url,
                 "location": "Karachi", "date_posted": NOW.isoformat()} for n in range(1, 6)]
        first = fetch_jobspy_jobs(config, runner=lambda *_: {"rows": rows}, detail_fetcher=detail, sleep=lambda _: None)
        self.assertEqual(len(first.updates[QUEUE_KEY]["entries"]), 3)
        self.assertEqual(first.updates[ADAPTIVE_KEY]["request_limit"], 6)
        reloaded = json.loads(json.dumps(first.updates))
        runner, fetcher = MagicMock(), MagicMock(side_effect=detail)
        second = fetch_jobspy_jobs(config, reloaded, runner=runner, detail_fetcher=fetcher, sleep=lambda _: None)
        runner.assert_not_called()
        self.assertEqual(fetcher.call_count, 3)
        self.assertEqual(len(second), 3)
        self.assertTrue(all(job.description_status == "full" for job in second))
        self.assertFalse(second.updates[QUEUE_KEY]["entries"])
        self.assertEqual(second.report.enrichment["recovered_jobs"], 3)
        validate_discovery_state(second.updates)

    def test_blocking_reduces_budget_increases_delay_and_preserves_work(self):
        config = self.config()
        config["jobspy"].update(linkedin_detail_initial_requests=4)
        result = SourceResult("JobSpy", [candidate(i) for i in range(1, 6)])
        fetcher = MagicMock(side_effect=SourceError("blocked", "http_429"))
        enrich_linkedin_jobs(result, config, {}, fetcher=fetcher, now=NOW)
        self.assertEqual(fetcher.call_count, 1)
        self.assertEqual(result.updates[ADAPTIVE_KEY]["request_limit"], 2)
        self.assertEqual(result.updates[ADAPTIVE_KEY]["delay_seconds"], 4)
        self.assertEqual(len(result.updates[QUEUE_KEY]["entries"]), 5)
        held = SourceResult("JobSpy")
        enrich_linkedin_jobs(held, config, result.updates, fetcher=fetcher, now=NOW + timedelta(hours=1))
        self.assertEqual(fetcher.call_count, 1)
        self.assertEqual(held.report.enrichment["pending"], 5)

    def test_repeated_healthy_cycles_raise_limit_only_to_configured_ceiling(self):
        config = self.config()
        config["jobspy"].update(linkedin_max_details=6)
        result = SourceResult("JobSpy", [candidate(i) for i in range(1, 11)])
        enrich_linkedin_jobs(result, config, {}, fetcher=detail, sleep=lambda _: None, now=NOW)
        self.assertEqual(result.updates[ADAPTIVE_KEY]["request_limit"], 6)
        again = SourceResult("JobSpy")
        enrich_linkedin_jobs(again, config, result.updates, fetcher=detail, sleep=lambda _: None, now=NOW)
        self.assertEqual(again.report.enrichment["completed"], 6)
        self.assertEqual(again.updates[ADAPTIVE_KEY]["request_limit"], 6)

    def test_per_job_retry_and_exhaustion_do_not_lose_other_pending_jobs(self):
        config = self.config()
        config["jobspy"]["linkedin_queue_max_attempts"] = 2
        state = self.queued([candidate()], config)
        fetcher = MagicMock(side_effect=SourceError("parse_failed", "fixture"))
        first = SourceResult("JobSpy")
        enrich_linkedin_jobs(first, config, state, fetcher=fetcher, now=NOW)
        waiting = SourceResult("JobSpy")
        enrich_linkedin_jobs(waiting, config, first.updates, fetcher=fetcher, now=NOW + timedelta(hours=1))
        self.assertEqual(fetcher.call_count, 1)
        second = SourceResult("JobSpy")
        enrich_linkedin_jobs(second, config, first.updates, fetcher=fetcher, now=NOW + timedelta(hours=4))
        self.assertEqual(second.report.enrichment["exhausted"], 1)
        final = SourceResult("JobSpy")
        enrich_linkedin_jobs(final, config, second.updates, fetcher=fetcher, now=NOW + timedelta(hours=8))
        self.assertEqual(fetcher.call_count, 2)

    def test_queue_expiry_stale_jobs_and_known_seniority_avoid_wasted_requests(self):
        config = self.config()
        state = self.queued([candidate()])
        fetcher = MagicMock()
        result = SourceResult("JobSpy", [candidate(2, title="Senior Python Developer"),
            candidate(3, posted_at=(NOW - timedelta(days=8)).isoformat())])
        enrich_linkedin_jobs(result, config, state, fetcher=fetcher, now=NOW + timedelta(hours=73))
        fetcher.assert_not_called()
        self.assertFalse(result.updates[QUEUE_KEY]["entries"])

    def test_waiting_generic_roles_age_ahead_of_new_junior_work(self):
        config = self.config()
        older = candidate(1, title="Software Engineer")
        state = self.queued([older])
        entry = state[QUEUE_KEY]["entries"][older.job_id]
        entry["queued_at"] = (NOW - timedelta(hours=13)).isoformat()
        config["jobspy"]["linkedin_max_details"] = 1
        result = SourceResult("JobSpy", [candidate(2)])
        fetcher = MagicMock(side_effect=detail)
        enrich_linkedin_jobs(result, config, state, fetcher=fetcher, now=NOW)
        self.assertEqual(fetcher.call_args.args[0], older.url)

    def test_cache_can_complete_saved_work_without_search_or_network(self):
        state = self.queued([candidate()])
        state["cache:linkedin"]["entries"][candidate().url] = {"fetched_at": NOW.isoformat(), "payload": detail()}
        result = SourceResult("JobSpy")
        fetcher = MagicMock()
        enrich_linkedin_jobs(result, self.config(), state, fetcher=fetcher, now=NOW)
        fetcher.assert_not_called()
        self.assertEqual(result.report.enrichment["cache_hits"], 1)
        self.assertEqual(result[0].description_status, "full")
        self.assertEqual(result.report.queries[0].phase, "cache")

    def test_configured_queue_bound_and_invalid_state_fail_before_network(self):
        config = self.config()
        config["jobspy"].update(linkedin_queue_limit=3, linkedin_max_details=0)
        result = SourceResult("JobSpy", [candidate(i) for i in range(1, 12)])
        enrich_linkedin_jobs(result, config, {}, now=NOW)
        self.assertEqual(len(result.updates[QUEUE_KEY]["entries"]), 3)
        state = copy.deepcopy(result.updates)
        first = next(iter(state[QUEUE_KEY]["entries"].values()))
        first["job"]["url"] = "https://localhost/private"
        with self.assertRaises(StateError):
            validate_discovery_state(state)
        state = copy.deepcopy(result.updates)
        first = next(iter(state[QUEUE_KEY]["entries"].values()))
        first["retry_after"] = "invalid"
        with self.assertRaises(StateError):
            validate_discovery_state(state)

    def test_concurrent_queue_changes_preserve_additions_completion_and_attempts(self):
        one, two, three = candidate(1), candidate(2), candidate(3)
        base = self.queued([one, two])
        local, remote = copy.deepcopy(base), copy.deepcopy(base)
        local[QUEUE_KEY]["entries"].pop(one.job_id)
        extra = self.queued([three])[QUEUE_KEY]["entries"][three.job_id]
        remote[QUEUE_KEY]["entries"][three.job_id] = extra
        remote[QUEUE_KEY]["entries"][two.job_id].update(attempts=1, last_attempt=NOW.isoformat())
        merged = merge_discovery(base, local, remote)
        self.assertEqual(set(merged[QUEUE_KEY]["entries"]), {two.job_id, three.job_id})
        self.assertEqual(merged[QUEUE_KEY]["entries"][two.job_id]["attempts"], 1)
        self.assertIn(one.job_id, base[QUEUE_KEY]["entries"], "Inputs must remain untouched")

    def test_adaptive_state_is_validated_and_newest_control_survives_merge(self):
        old: dict = {ADAPTIVE_KEY: {"request_limit": 4, "delay_seconds": 4, "updated_at": NOW.isoformat()}}
        new = {ADAPTIVE_KEY: {"request_limit": 2, "delay_seconds": 8,
            "updated_at": (NOW + timedelta(minutes=1)).isoformat()}}
        self.assertEqual(merge_discovery({}, old, new)[ADAPTIVE_KEY], new[ADAPTIVE_KEY])
        for field, value in [("request_limit", -1), ("request_limit", True), ("delay_seconds", float("inf"))]:
            invalid = copy.deepcopy(old)
            invalid[ADAPTIVE_KEY][field] = value
            with self.assertRaises(StateError):
                validate_discovery_state(invalid)

    def test_closed_saved_job_is_returned_as_negative_evidence(self):
        state = self.queued([candidate()])
        result = SourceResult("JobSpy")
        enrich_linkedin_jobs(result, self.config(), state,
            fetcher=MagicMock(side_effect=SourceError("closed", "http_404")), now=NOW)
        self.assertEqual(result[0].active_status, "closed")
        self.assertEqual(result.updates[QUEUE_KEY]["entries"][candidate().job_id]["status"], "closed")

    def test_employer_fallback_shares_request_budget_and_preserves_source_identity(self):
        job = candidate(application_url="https://boards.greenhouse.io/fixture/jobs/123")
        config = self.config()
        result = SourceResult("JobSpy", [job])
        employer = MagicMock(return_value={**detail(), "source_url": job.application_url})
        enrich_linkedin_jobs(result, config, {}, fetcher=MagicMock(side_effect=SourceError("blocked", "http_403")),
            employer_fetcher=employer, sleep=lambda _: None, now=NOW)
        employer.assert_called_once()
        self.assertEqual(len(result.report.queries), 2)
        self.assertEqual(result[0].job_id, job.job_id)
        self.assertEqual(result[0].location, "Karachi")
        self.assertIn(job.application_url, result[0].source_urls)
        self.assertEqual(result.report.enrichment["fallback_requests"], 1)
        self.assertFalse(result.updates[QUEUE_KEY]["entries"])

    def test_employer_fallback_cannot_exceed_total_request_cap(self):
        config = self.config()
        config["jobspy"]["linkedin_max_details"] = 1
        employer = MagicMock()
        result = SourceResult("JobSpy", [candidate(application_url="https://boards.greenhouse.io/fixture/jobs/123")])
        enrich_linkedin_jobs(result, config, {}, fetcher=MagicMock(side_effect=SourceError("blocked", "http_403")),
            employer_fetcher=employer, now=NOW)
        employer.assert_not_called()
        self.assertEqual(len(result.report.queries), 1)

    def test_public_employer_api_requires_exact_identity_title_and_published_url(self):
        job = candidate(application_url="https://job-boards.greenhouse.io/fixture/jobs/123")
        payload = {"id": 123, "title": job.title, "absolute_url": job.application_url,
            "content": "<p>Python.</p><p>2 years required.</p>"}
        with patch("job_finder.scrapers.employer_details.get_public", return_value=SimpleNamespace(json=lambda: payload)) as get:
            self.assertEqual(fetch_employer_detail(job, 8)["description"], "Python.\n2 years required.")
            self.assertIn("boards-api.greenhouse.io/v1/boards/fixture/jobs/123", get.call_args.args[0])
            for field, value in [("id", 456), ("title", "Unrelated Developer"),
                    ("absolute_url", "https://job-boards.greenhouse.io/other/jobs/123")]:
                invalid = {**payload, field: value}
                get.return_value = SimpleNamespace(json=lambda: invalid)
                with self.assertRaises(SourceError):
                    fetch_employer_detail(job, 8)

    def test_unsupported_employer_destinations_make_no_requests(self):
        for url in ["http://127.0.0.1/private", "https://jobs.lever.co.evil.test/fixture/1234567890",
                    "https://jobs.lever.co/", "https://user:secret@jobs.lever.co/fixture/1234567890"]:
            self.assertIsNone(posting(url))
        with patch("job_finder.scrapers.employer_details.get_public") as get, self.assertRaises(SourceError):
            fetch_employer_detail(candidate(application_url="https://example.test/careers"), 8)
        get.assert_not_called()

    def test_recruiter_attempt_budget_is_shared_between_queries_and_rotates(self):
        config = load_config()
        config["linkedin_posts"].update(queries=["first Python", "second React", "third Node"], max_search_attempts=3)
        factory = MagicMock()
        search = factory.return_value.__enter__.return_value
        search.text.side_effect = DDGSException("No results found.")
        with patch("ddgs.DDGS", factory):
            first = fetch_linkedin_plain_posts(config)
            calls = search.text.call_args_list[:]
            second = fetch_linkedin_plain_posts(config, first.updates)
        self.assertEqual([call.args[0] for call in calls], config["linkedin_posts"]["queries"])
        self.assertEqual(search.text.call_args_list[3].args[0], "second React")
        self.assertEqual(search.text.call_count, 6)
        self.assertEqual(second.updates["rotation:posts"]["offset"], 2)

    def test_fresh_closed_evidence_retires_a_previously_eligible_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial = candidate(description=detail()["description"], description_status="full")
            tracker = JobTracker(root / "state")
            tracker.enqueue([initial])
            closed = Job.from_dict(initial.to_dict())
            closed.active_status = "closed"
            fresh = SourceResult("JobSpy", [closed])
            from job_finder.scrapers.common import QueryOutcome
            fresh.report.queries.append(QueryOutcome("details", "closed", phase="detail", site="linkedin"))
            with patch.dict("os.environ", {"DISCORD_WEBHOOK_URL": "https://example.test/webhook"}), \
                 patch("job_finder.application.pipeline.fetch_jobspy_jobs", return_value=fresh), \
                 patch("job_finder.application.pipeline.fetch_rozee_jobs", return_value=SourceResult("Rozee.pk")), \
                 patch("job_finder.application.pipeline.fetch_linkedin_plain_posts", return_value=SourceResult("LinkedIn Post")), \
                 patch("job_finder.application.pipeline.fetch_remote_feeds", return_value=SourceResult("Remote feeds")), \
                 patch("job_finder.notifiers.discord.requests.post") as post:
                run_job_finder(state_path=root / "state", discovery_path=root / "discovery", report_dir=root / "report")
            post.assert_not_called()
            self.assertFalse(JobTracker(root / "state").pending)

    def test_new_budget_relationships_are_validated(self):
        for key, value in [("linkedin_detail_initial_requests", 100), ("linkedin_queue_limit", 1001),
                ("linkedin_detail_max_delay", 1), ("linkedin_queue_max_attempts", 0)]:
            config = load_config()
            config["jobspy"][key] = value
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_full_duplicate_does_not_enqueue_an_incomplete_copy(self):
        job = candidate(description=detail()["description"], description_status="full")
        result = SourceResult("JobSpy", [candidate(), job])
        fetcher = MagicMock()
        enrich_linkedin_jobs(result, self.config(), {}, fetcher=fetcher, now=NOW)
        fetcher.assert_not_called()
        self.assertFalse(result.updates[QUEUE_KEY]["entries"])

    def test_exact_employer_fallback_can_complete_work_during_linkedin_cooldown(self):
        from job_finder.scrapers.linkedin_details import COOLDOWN_KEY
        job = candidate(application_url="https://jobs.lever.co/fixture/01234567-89ab-cdef")
        state = self.queued([job])
        state[COOLDOWN_KEY] = {"last_attempt": NOW.isoformat(), "reason": "blocked"}
        result = SourceResult("JobSpy")
        fetcher, employer = MagicMock(), MagicMock(return_value={**detail(), "source_url": job.application_url})
        enrich_linkedin_jobs(result, self.config(), state, fetcher=fetcher, employer_fetcher=employer, now=NOW)
        fetcher.assert_not_called()
        employer.assert_called_once()
        self.assertEqual(result.report.enrichment["recovered_jobs"], 1)
        self.assertFalse(result.updates[QUEUE_KEY]["entries"])

    def test_lever_api_description_requires_the_exact_known_posting(self):
        job = candidate(application_url="https://jobs.lever.co/fixture/01234567-89ab-cdef")
        payload = {"id": "01234567-89ab-cdef", "text": job.title, "hostedUrl": job.application_url,
            "description": "<p>Python Django.</p>", "lists": [
                {"text": "Requirements", "content": "<ul><li>Fresh graduates welcome.</li></ul>"}],
            "additional": "<p>Karachi.</p>"}
        with patch("job_finder.scrapers.employer_details.get_public", return_value=SimpleNamespace(json=lambda: payload)) as get:
            result = fetch_employer_detail(job, 8)
        self.assertIn("Fresh graduates welcome.", result["description"])
        self.assertEqual(result["source_url"], job.application_url)
        self.assertIn("api.lever.co/v0/postings/fixture/01234567-89ab-cdef", get.call_args.args[0])

    def test_refreshing_dry_run_drains_in_memory_without_changing_persisted_queue(self):
        state = self.queued([candidate()])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            discovery = root / "discovery.json"
            original = json.dumps(state).encode()
            discovery.write_bytes(original)
            def fetch(config, saved):
                self.assertEqual(config["jobspy"]["interval_hours"], 0)
                self.assertEqual(config["remote_feeds"]["interval_hours"], 6)
                result = SourceResult("JobSpy")
                enrich_linkedin_jobs(result, config, saved, fetcher=detail, sleep=lambda _: None)
                return result
            with patch("job_finder.application.pipeline.fetch_jobspy_jobs", side_effect=fetch), \
                 patch("job_finder.application.pipeline.fetch_rozee_jobs", return_value=SourceResult("Rozee.pk")), \
                 patch("job_finder.application.pipeline.fetch_linkedin_plain_posts", return_value=SourceResult("LinkedIn Post")), \
                 patch("job_finder.application.pipeline.fetch_remote_feeds", return_value=SourceResult("Remote feeds")), \
                 patch("job_finder.notifiers.discord.requests.post") as post:
                run_job_finder(dry_run=True, refresh_searches=True, state_path=root / "seen.json",
                    discovery_path=discovery, report_dir=root / "report")
            post.assert_not_called()
            self.assertEqual(discovery.read_bytes(), original)
            self.assertFalse((root / "seen.json").exists())
            report = json.loads((root / "report/run.json").read_text())
            self.assertEqual(report["counts"]["enrichment_completed"], 1)
