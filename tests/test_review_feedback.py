import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from config import load_config
from evaluation import evaluate_benchmark
from feedback import record_feedback, export_benchmark
from filtering.resume_filter import evaluate_job
from notifiers.discord import DiscordNotifier
from scrapers.base import Job, merge_jobs, utc_now
from scrapers.post_roles import split_post_roles
from storage.tracker import JobTracker, StateError, atomic_write_json
from tests.support import OfflineTestCase, job
from tests.test_delivery import response
from tests.test_matching import NOW


class ReviewFeedbackTests(OfflineTestCase):
    def test_mixed_roles_keep_requirements_location_and_identity_separate(self):
        post = job(platform="LinkedIn Post", title="Senior Python and Junior React Developers",
            url="https://www.linkedin.com/posts/fixture", kind="lead", location="Lahore",
            description="We are expanding.\nRole: Senior Python Developer\nLocation: Lahore. Python Django required. 5 years experience required.\n"
                        "Role: Junior React Developer\nLocation: Karachi. React TypeScript. Fresh graduates welcome.\nHow to apply:\nVisit our post.")
        roles = split_post_roles(post)
        self.assertEqual(len(roles), 2)
        self.assertEqual(len(merge_jobs(roles)), 2)
        self.assertEqual(evaluate_job(roles[0], load_config(), NOW).tier, "rejected")
        self.assertEqual(evaluate_job(roles[1], load_config(), NOW).tier, "review")
        self.assertNotIn("5 years", roles[1].description)
        self.assertNotIn("Lahore", roles[1].location)
        self.assertEqual(roles[1].source_description, post.description)
        self.assertEqual(roles[1].source_title, post.title)
        reordered = Job.from_dict(post.to_dict())
        reordered.description = "Role: Junior React Developer\nReact TypeScript\nRole: Senior Python Developer\nPython Django"
        by_title = {role.title: role.job_id for role in split_post_roles(reordered)}
        self.assertEqual(by_title[roles[1].title], roles[1].job_id)
        with tempfile.TemporaryDirectory() as directory:
            tracker = JobTracker(Path(directory) / "state")
            tracker.mark_as_seen([roles[0]])
            self.assertFalse(tracker.is_seen(roles[1]))

    def test_unsplittable_and_snippet_posts_stay_intact(self):
        post = job(kind="lead", description="Hiring junior React and senior Python developers. Requirements vary by role.")
        self.assertEqual(split_post_roles(post), [post])
        post.description = "Role: Python Developer\nPython\nRole: React Developer\nReact"
        post.description_status = "snippet"
        self.assertEqual(split_post_roles(post), [post])

    def test_cache_provenance_does_not_reduce_otherwise_complete_fit(self):
        cached = job(evidence_warnings=["cached_description"])
        self.assertEqual(evaluate_job(cached, load_config(), NOW).tier, "qualified")

    def reviews(self, number):
        return [job(str(index), title="React " + "x" * 500, company="@everyone" * 300,
                    decision={"tier": "review", "score": 60, "gaps": ["unknown_salary" * 300]})
                for index in range(number)]

    def test_digest_batches_are_bounded_and_confirmed_as_one_atomic_group(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = self.reviews(7)
            tracker = JobTracker(Path(directory) / "state")
            tracker.enqueue(jobs)
            notifier = DiscordNotifier("https://example.test/webhook", sleep=lambda _: None)
            with patch("notifiers.discord.requests.post", side_effect=[
                response(200, {"id": "digest-1"}), response(200, {"id": "digest-2"})]) as post, \
                 patch.object(tracker, "save", wraps=tracker.save) as save:
                result = notifier.send_jobs(jobs, tracker.record_delivery, review_digest=True,
                                            on_batch_result=tracker.record_deliveries)
            self.assertEqual(len(result.delivered_ids), 7)
            self.assertEqual(save.call_count, 2)
            self.assertFalse(tracker.pending)
            self.assertEqual(tracker.receipts[jobs[4].job_id]["message_id"], "digest-1")
            self.assertEqual(tracker.receipts[jobs[5].job_id]["message_id"], "digest-2")
            for call in post.call_args_list:
                payload = call.kwargs["json"]
                self.assertLessEqual(len(payload["embeds"]), 5)
                self.assertLess(sum(len(embed["title"]) + len(embed["description"]) + len(embed["footer"]["text"])
                                    for embed in payload["embeds"]), 6000)
                self.assertEqual(payload["allowed_mentions"], {"parse": []})

    def test_failed_digest_keeps_every_job_pending_and_save_failure_stops_next_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            jobs = self.reviews(7)
            tracker = JobTracker(Path(directory) / "state")
            tracker.enqueue(jobs)
            notifier = DiscordNotifier("https://example.test/webhook", max_attempts=1, sleep=lambda _: None)
            with patch("notifiers.discord.requests.post", return_value=response(500)):
                result = notifier.send_jobs(jobs, tracker.record_delivery, True, tracker.record_deliveries)
            self.assertEqual(len(result.failed_ids), 7)
            self.assertFalse(tracker.seen_data)
            self.assertEqual(len(tracker.pending), 7)
            with patch("notifiers.discord.requests.post", return_value=response(200)) as post:
                with self.assertRaises(StateError):
                    notifier.send_jobs(jobs, review_digest=True,
                        on_batch_result=lambda _: (_ for _ in ()).throw(StateError("fixture save failure")))
            self.assertEqual(post.call_count, 1)

    def test_feedback_export_is_evaluated_at_capture_time_and_does_not_touch_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, feedback, benchmark = root / "run.json", root / "feedback.json", root / "benchmark.json"
            item = job()
            atomic_write_json(report, {"jobs": [item.to_dict()], "started_at": "2026-09-07T12:00:00Z"})
            state = record_feedback(report, item.job_id, "relevant", "Good internship fit", feedback)
            self.assertEqual(state["labels"][item.job_id]["label"], "relevant")
            export_benchmark(feedback, benchmark)
            self.assertEqual(evaluate_benchmark(benchmark)["tier_agreement"], 1)
            with self.assertRaises(ValueError):
                record_feedback(report, "missing", "relevant", output=feedback)
            self.assertEqual(len(json.loads(feedback.read_text())["labels"]), 1)
            self.assertEqual({p.name for p in root.iterdir()}, {"run.json", "feedback.json", "benchmark.json"})
