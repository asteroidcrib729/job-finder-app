import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import requests
from notifiers.discord import DiscordNotifier, DeliveryOutcome
from storage.tracker import JobTracker, StateError, atomic_write_json
from scrapers.base import legacy_id
from tests.support import OfflineTestCase, job


def response(status, body=None):
    return SimpleNamespace(status_code=status, json=lambda: body or {}, text="")


class DeliveryTests(OfflineTestCase):
    def test_partial_success_and_retry_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "seen.json"
            tracker = JobTracker(path, clock=lambda: 1000)
            jobs = [job("a"), job("b")]
            tracker.enqueue(jobs)
            notifier = DiscordNotifier("https://example.test/webhook", max_attempts=1, sleep=lambda _: None)
            with patch("notifiers.discord.requests.post", side_effect=[response(200, {"id": "message-1"}), response(500)]):
                result = notifier.send_jobs(jobs, tracker.record_delivery)
            self.assertEqual(result.delivered_ids, [jobs[0].job_id])
            self.assertEqual(result.failed_ids, [jobs[1].job_id])
            restarted = JobTracker(path, clock=lambda: 5000)
            self.assertTrue(restarted.is_seen(jobs[0]))
            self.assertFalse(restarted.is_seen(jobs[1]))
            self.assertEqual([item.job_id for item in restarted.pending_jobs()], [jobs[1].job_id])
            self.assertEqual(restarted.receipts[jobs[0].job_id]["message_id"], "message-1")

    def test_retry_response_is_checked(self):
        notifier = DiscordNotifier("https://example.test/webhook", max_attempts=2, sleep=lambda _: None)
        with patch("notifiers.discord.requests.post", side_effect=[response(429, {"retry_after": 0}), response(500)]):
            self.assertFalse(notifier.send_jobs([job()]))
        with patch("notifiers.discord.requests.post", side_effect=[response(429, {"retry_after": 0}), response(200, {"id": "1"})]) as post:
            result = notifier.send_jobs([job()])
            self.assertTrue(result)
            self.assertEqual(post.call_args.kwargs["params"], {"wait": "true"})

    def test_long_rate_limit_defers_instead_of_retrying_early(self):
        notifier = DiscordNotifier("https://example.test/webhook", sleep=lambda _: None)
        with patch("notifiers.discord.requests.post", return_value=response(429, {"retry_after": 600})) as post:
            result = notifier.send_jobs([job()])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result.outcomes[0].status, "failed")

    def test_timeout_is_uncertain_and_permanent_error_is_not_retried(self):
        notifier = DiscordNotifier("https://example.test/webhook", sleep=lambda _: None)
        with patch("notifiers.discord.requests.post", side_effect=requests.Timeout) as post:
            result = notifier.send_jobs([job()])
            self.assertEqual(post.call_count, 1)
            self.assertEqual(result.outcomes[0].status, "uncertain")
        with patch("notifiers.discord.requests.post", return_value=response(400)) as post:
            self.assertEqual(notifier.send_jobs([job()]).outcomes[0].status, "permanent_failure")
            self.assertEqual(post.call_count, 1)

    def test_embed_limits_and_per_job_isolation(self):
        notifier = DiscordNotifier("https://example.test/webhook", sleep=lambda _: None)
        big = job(title="x" * 1000, company="y" * 5000, description=None)
        embed = notifier._build_embed(big)
        self.assertLessEqual(len(embed["title"]), 256)
        self.assertTrue(all(0 < len(field["value"]) <= 1024 for field in embed["fields"]))
        size = len(embed["title"]) + len(embed["description"]) + len(embed["footer"]["text"])
        size += sum(len(field["name"]) + len(field["value"]) for field in embed["fields"])
        self.assertLessEqual(size, 6000)
        broken = job("broken")
        broken.url = "javascript:bad"
        with patch("notifiers.discord.requests.post", return_value=response(204)) as post:
            result = notifier.send_jobs([broken, big])
        self.assertEqual(post.call_count, 1)
        self.assertEqual(result.outcomes[0].status, "permanent_failure")
        self.assertEqual(result.outcomes[1].status, "delivered")

    def test_state_failure_stops_later_delivery(self):
        notifier = DiscordNotifier("https://example.test/webhook", sleep=lambda _: None)
        def failed_save(job, outcome):
            raise StateError("fixture write failure")
        with patch("notifiers.discord.requests.post", return_value=response(204)) as post:
            with self.assertRaises(StateError):
                notifier.send_jobs([job("a"), job("b")], failed_save)
        self.assertEqual(post.call_count, 1)

    def test_legacy_state_is_migrated_without_resending(self):
        item = job()
        key = legacy_id(item.title, item.company, item.url, item.platform)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            path.write_text(json.dumps({key: 1000}))
            tracker = JobTracker(path, clock=lambda: 1100)
            self.assertEqual(tracker.filter_new_jobs([item]), [])
            tracker.save()
            self.assertEqual(json.loads(path.read_text())["version"], 2)
            self.assertTrue(JobTracker(path, clock=lambda: 1200).is_seen(item))

    def test_corrupt_state_does_not_reset_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            for contents in ('{"broken":', '{"id":"bad-timestamp"}', '[]'):
                path.write_text(contents)
                with self.assertRaises(StateError):
                    JobTracker(path)
                self.assertEqual(path.read_text(), contents)

    def test_interrupted_atomic_replace_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            atomic_write_json(path, {"old": 1})
            with patch("storage.tracker.os.replace", side_effect=OSError):
                with self.assertRaises(StateError):
                    atomic_write_json(path, {"new": 2})
            self.assertEqual(json.loads(path.read_text()), {"old": 1})
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])
