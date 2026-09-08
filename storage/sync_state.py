"""Persist only state on the latest branch tree; retry concurrent branch advances."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from storage.reconcile import merge_delivery, merge_discovery, validate_discovery_state
from storage.tracker import StateError, read_json, validate_delivery_state

STATE_FILES = {
    "data/seen_jobs.json": (validate_delivery_state, merge_delivery),
    "data/discovery_state.json": (validate_discovery_state, merge_discovery),
}


class Git:
    def __init__(self, repo):
        self.repo = Path(repo).resolve()

    def run(self, *args, input=None, env=None, check=True):
        try:
            process = subprocess.run(["git", *args], cwd=self.repo, input=input,
                text=True, encoding="utf-8", capture_output=True, timeout=60,
                env={**os.environ, **(env or {})})
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StateError("Git state persistence command could not complete") from exc
        if check and process.returncode:
            # Git's stderr may contain remote URLs; do not echo credentials.
            raise StateError("Git state persistence failed at " + args[0])
        return process

    def snapshot(self, commit, path):
        listing = self.run("ls-tree", commit, "--", path).stdout.strip()
        if not listing:
            return {}
        if not listing.startswith("100644 blob ") and not listing.startswith("100755 blob "):
            raise StateError("State history must contain a regular JSON file")
        try:
            return json.loads(self.run("show", commit + ":" + path).stdout)
        except ValueError as exc:
            raise StateError("Remote state JSON is invalid; nothing was pushed") from exc


def persist_state(repo, branch, attempts=3):
    git = Git(repo)
    git.run("check-ref-format", "refs/heads/" + branch)
    base_commit = git.run("rev-parse", "HEAD").stdout.strip()
    local, baseline, backups = {}, {}, {}
    for path, (validate, _) in STATE_FILES.items():
        target = git.repo / path
        if not target.is_file():
            continue
        if not target.resolve().is_relative_to(git.repo) or target.is_symlink():
            raise StateError("Local state must be a regular file inside the repository")
        local[path] = read_json(target, {})
        validate(local[path])
        baseline[path] = git.snapshot(base_commit, path)
        validate(baseline[path])
        backup = target.with_name(target.name + ".bak")
        if backup.is_file():
            if not backup.resolve().is_relative_to(git.repo) or backup.is_symlink():
                raise StateError("Local backup must be a regular file inside the repository")
            backups[path] = read_json(backup, {})
            validate(backups[path])
    if not local:
        return {"status": "unchanged", "attempts": 0}

    for attempt in range(1, attempts + 1):
        git.run("fetch", "--no-tags", "origin", "refs/heads/" + branch)
        remote_commit = git.run("rev-parse", "FETCH_HEAD").stdout.strip()
        changes = {}
        for path, state in local.items():
            validate, merge = STATE_FILES[path]
            remote = git.snapshot(remote_commit, path)
            validate(remote)
            merged = merge(baseline[path], state, remote)
            # Normalize legacy delivery formats when comparing equivalent content.
            if validate(merged) == validate(remote):
                continue
            changes[path] = merged
            if path in backups:
                changes[path + ".bak"] = merge(baseline[path], backups[path], remote)
            elif remote:
                changes[path + ".bak"] = remote
        if not changes:
            return {"status": "unchanged", "attempts": attempt}
        with tempfile.TemporaryDirectory(prefix="job-finder-index-") as directory:
            env = {
                "GIT_INDEX_FILE": str(Path(directory) / "index"),
                "GIT_AUTHOR_NAME": "Job Finder Bot", "GIT_AUTHOR_EMAIL": "actions@github.com",
                "GIT_COMMITTER_NAME": "Job Finder Bot", "GIT_COMMITTER_EMAIL": "actions@github.com",
            }
            # Build on the remote tree, preserving every non-state file and the checkout.
            git.run("read-tree", remote_commit, env=env)
            for path, data in changes.items():
                encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
                blob = git.run("hash-object", "-w", "--stdin", input=encoded, env=env).stdout.strip()
                git.run("update-index", "--add", "--cacheinfo", "100644," + blob + "," + path, env=env)
            tree = git.run("write-tree", env=env).stdout.strip()
            commit = git.run("commit-tree", tree, "-p", remote_commit,
                input="chore: update job discovery state [skip ci]\n", env=env).stdout.strip()
            # Normal fast-forward push. No force, reset, checkout, rebase, or code merge.
            pushed = git.run("push", "origin", commit + ":refs/heads/" + branch, env=env, check=False)
        if pushed.returncode == 0:
            return {"status": "persisted", "attempts": attempt, "files": sorted(changes)}
    raise StateError("State push failed after bounded reconciliation retries; retain the workflow state artifact")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True)
    args = parser.parse_args()
    try:
        result = persist_state(Path.cwd(), args.branch)
    except StateError as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
