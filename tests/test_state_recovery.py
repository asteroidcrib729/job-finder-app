import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from notifiers.discord import DeliveryOutcome
from storage.reconcile import merge_delivery, merge_discovery, validate_discovery_state
from storage.recover import export_recovery
from storage.sync_state import Git, persist_state
from storage.tracker import JobTracker, StateError, atomic_write_json, read_json, save_with_backup
from tests.support import OfflineTestCase, job


class StateRecoveryTests(OfflineTestCase):
    def state(self, pending=(), seen=None):
        return {"version": 2, "seen": seen or {},
                "pending": {item.job_id: {"job": item.to_dict(), "status": "pending",
                    "queued_at": 1000, "attempts": 0, "next_retry_at": 0} for item in pending},
                "receipts": {}}

    def test_backup_recovery_exports_candidate_and_preserves_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seen.json"
            tracker = JobTracker(path, clock=lambda: 1000)
            item = job()
            tracker.enqueue([item])
            before = read_json(path, {})
            tracker.record_delivery(item, DeliveryOutcome(item.job_id, "delivered", message_id="receipt"))
            backup = path.with_name("seen.json.bak")
            self.assertEqual(read_json(backup, {}), before)
            path.write_text("corrupt", encoding="utf-8")
            with self.assertRaises(StateError):
                JobTracker(path)
            recovered = Path(directory) / "candidate.json"
            state = export_recovery(backup, recovered)
            self.assertIn(item.job_id, state["pending"])
            self.assertEqual(path.read_text(), "corrupt")
            with self.assertRaises(StateError):
                export_recovery(backup, recovered)
            with self.assertRaises(StateError):
                export_recovery(path, Path(directory) / "invalid.json")

    def test_backup_is_not_replaced_by_corrupt_primary(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "discovery.json"
            first = {"q": {"last_success": "2026-09-07T00:00:00Z"}}
            second = {"q": {"last_success": "2026-09-08T00:00:00Z"}}
            save_with_backup(path, first, validate_discovery_state)
            save_with_backup(path, second, validate_discovery_state)
            backup = path.with_name(path.name + ".bak")
            path.write_text('{"q":null}', encoding="utf-8")
            with self.assertRaises(StateError):
                save_with_backup(path, second, validate_discovery_state)
            self.assertEqual(read_json(backup, {}), first)

    def test_merge_preserves_both_acknowledgements_and_removes_aliased_pending(self):
        one, two = job("one"), job("two")
        base = self.state([one, two])
        local = self.state([two], {one.job_id: 1100})
        local["receipts"][one.job_id] = {"at": 1100, "message_id": "a"}
        remote = self.state([one], {two.aliases[0]: 1200})
        merged = merge_delivery(base, local, remote)
        self.assertEqual(merged["pending"], {})
        self.assertEqual(len(merged["seen"]), 2)
        self.assertEqual(merged["receipts"][one.job_id]["message_id"], "a")
        self.assertEqual(len(base["pending"]), 2, "Inputs must not mutate")

    def test_merge_respects_retirement_and_preserves_new_remote_pending(self):
        one, two, three = job("one"), job("two"), job("three")
        base = self.state([one, two])
        local = self.state([two])
        remote = self.state([one, two, three])
        remote["pending"][two.job_id].update(status="uncertain", attempts=2, last_attempt_at=1200, next_retry_at=2000)
        local["pending"][two.job_id].update(status="failed", attempts=1, last_attempt_at=1100, next_retry_at=1500)
        merged = merge_delivery(base, local, remote)
        self.assertNotIn(one.job_id, merged["pending"])
        self.assertIn(three.job_id, merged["pending"])
        self.assertEqual(merged["pending"][two.job_id]["status"], "uncertain")
        self.assertEqual(merged["pending"][two.job_id]["next_retry_at"], 2000)

    def test_merge_legacy_and_validate_corrupt_receipts_before_push(self):
        merged = merge_delivery({"old": 1000}, {"old": 1000, "new": 1100}, {"old": 1000, "remote": 1200})
        self.assertEqual(set(merged["seen"]), {"old", "new", "remote"})
        corrupt = self.state()
        corrupt["receipts"]["bad"] = {"at": "invalid", "message_id": "x"}
        with self.assertRaises(StateError):
            merge_delivery({}, corrupt, {})

    def test_seen_retention_prunes_baseline_but_preserves_concurrent_new_receipt(self):
        self.assertEqual(merge_delivery({"old": 1000}, {}, {"old": 1000})["seen"], {})
        self.assertEqual(merge_delivery({"old": 1000}, {}, {"old": 1200})["seen"], {"old": 1200})

    def test_discovery_merge_keeps_newer_watermark_and_independent_cache_entries(self):
        old, new = "2026-09-07T00:00:00Z", "2026-09-08T00:00:00Z"
        def cache(url, date):
            return {"entries": {url: {"fetched_at": date, "payload": {"text": date}}}, "updated_at": date}
        base = {"q": {"last_success": old}}
        local = {"q": {"last_success": new}, "cache:posts": cache("https://example.test/a", old)}
        remote = {"q": {"last_success": old}, "r": {"last_success": new},
                  "cache:posts": cache("https://example.test/b", new)}
        result = merge_discovery(base, local, remote)
        self.assertEqual(result["q"]["last_success"], new)
        self.assertIn("r", result)
        self.assertEqual(len(result["cache:posts"]["entries"]), 2)
        with self.assertRaises(StateError):
            validate_discovery_state({"q": {"last_success": "yesterday"}})

    def test_git_reconciliation_preserves_concurrent_code_and_retries_branch_advance(self):
        # All remotes are local temporary bare repositories. No network or production Git writes.
        with tempfile.TemporaryDirectory(prefix="job-finder-git-test-") as directory:
            root = Path(directory)
            remote, worker, human = root / "remote.git", root / "worker", root / "human"
            env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.test",
                   "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.test"}
            def git(where, *args):
                return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=where,
                    env=env, check=True, capture_output=True, text=True, timeout=20).stdout.strip()
            git(root, "init", "--bare", str(remote))
            git(root, "clone", str(remote), str(worker))
            git(worker, "checkout", "-b", "main")
            (worker / "app.txt").write_text("initial code")
            atomic_write_json(worker / "data/seen_jobs.json", {"old": 1000})
            git(worker, "add", ".")
            git(worker, "commit", "-m", "initial")
            git(worker, "push", "-u", "origin", "main")
            git(root, "clone", "--branch", "main", str(remote), str(human))
            base_head = git(worker, "rev-parse", "HEAD")
            atomic_write_json(worker / "data/seen_jobs.json", {"old": 1000, "local": 1100})
            (human / "app.txt").write_text("concurrent human code")
            atomic_write_json(human / "data/seen_jobs.json", {"old": 1000, "remote": 1200})
            git(human, "add", ".")
            git(human, "commit", "-m", "human change")
            git(human, "push", "origin", "main")
            original = Git.run
            advances = []
            def racing_run(instance, *args, **kwargs):
                if args[0] == "push" and not advances:
                    advances.append(True)
                    (human / "app.txt").write_text("latest human code")
                    git(human, "add", ".")
                    git(human, "commit", "-m", "second human change")
                    git(human, "push", "origin", "main")
                return original(instance, *args, **kwargs)
            with patch.object(Git, "run", racing_run):
                result = persist_state(worker, "main")
            self.assertEqual(result["attempts"], 2)
            self.assertEqual(result["status"], "persisted")
            self.assertEqual(git(remote, "show", "main:app.txt"), "latest human code")
            final = json.loads(git(remote, "show", "main:data/seen_jobs.json"))
            self.assertEqual(set(final["seen"]), {"old", "local", "remote"})
            self.assertEqual(git(worker, "rev-parse", "HEAD"), base_head)
            self.assertEqual((worker / "app.txt").read_text(), "initial code")
            self.assertEqual(git(worker, "diff", "--cached", "--name-only"), "")
            self.assertEqual(persist_state(worker, "main")["status"], "unchanged")
            (worker / "data/seen_jobs.json").write_text("corrupt")
            with patch.object(Git, "run", wraps=Git(worker).run) as calls:
                with self.assertRaises(StateError):
                    persist_state(worker, "main")
            self.assertFalse(any(call.args[0] == "push" for call in calls.call_args_list))
