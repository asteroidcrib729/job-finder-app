"""GitHub Actions entry point, offline replay, evidence reports, and delivery journal."""
import argparse
from collections import Counter
from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
import json
import logging
import os
from pathlib import Path
import platform
import re
import sys
from config import BASE_DIR, load_config
from scrapers.base import Job, merge_jobs, utc_now
from scrapers.common import SourceResult, QueryOutcome
from scrapers.jobspy_adapter import fetch_jobspy_jobs
from scrapers.rozee_scraper import fetch_rozee_jobs
from scrapers.linkedin_posts_scraper import fetch_linkedin_plain_posts
from scrapers.remote_feeds import fetch_remote_feeds
from scrapers.metrics import query_metrics
from filtering.resume_filter import evaluate_job, rank_jobs, MATCHER_VERSION
from storage.tracker import JobTracker, StateError, atomic_write_json, read_json, SEEN_JOBS_FILE
from storage.tracker import save_with_backup
from storage.reconcile import validate_discovery_state
from notifiers.manager import NotificationManager
from run_health import assess_run

logger = logging.getLogger("JobFinder")
DISCOVERY_FILE = BASE_DIR / "data" / "discovery_state.json"


def environment_versions():
    packages = {}
    for name in ("python-jobspy", "pandas", "requests", "beautifulsoup4", "PyYAML", "ddgs"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "missing"
    return {"python": platform.python_version(), "packages": packages}


def sanitize(value):
    if isinstance(value, dict):
        return {key: ("" if key == "recruiter_email" else sanitize(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email redacted]", value)
        value = re.sub(r"https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/\S+", "[webhook redacted]", value)
    return value


def write_report(report, directory, step_summary=True):
    directory = Path(directory)
    atomic_write_json(directory / "run.json", sanitize(report))
    lines = ["# Job discovery run", "", f"Health: **{report['health']}**",
             f"Profile: {report.get('profile_version', 'unknown')} | Matcher: {MATCHER_VERSION}", ""]
    for key, value in report.get("counts", {}).items():
        lines.append(f"- {key.replace('_', ' ')}: {value}")
    lines += ["", "| Source | Outcome | Queries |", "| --- | --- | --- |"]
    for source in report.get("sources", []):
        lines.append(f"| {source['source']} | {source['status']} | {len(source['queries'])} |")
    lines += ["", "Operational outcome: **" + assess_run(report)["status"] + "**", ""]
    for source in report.get("sources", []):
        problems = Counter((query.get("site") or source["source"], query["status"], query.get("reason") or "unspecified")
                           for query in source.get("queries", []) if query["status"] not in {"success", "valid_empty"})
        for (site, status, reason), count in problems.items():
            lines.append(f"- {site}: {count} {status} query(s) — {reason}.")
    if report.get("counts", {}).get("qualified") == 0:
        lines += ["", "No candidates met the qualified-only alert policy. This alone is not a pipeline failure."]
    if report.get("error"):
        lines += ["", "Error: " + report["error"]]
    summary = "\n".join(lines) + "\n"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.md").write_text(summary, encoding="utf-8")
    if step_summary and os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as handle:
            handle.write(summary)


def read_replay(path):
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("jobs", payload.get("candidates", [])) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Replay must contain a list of jobs")
    result = SourceResult("Offline replay")
    invalid = 0
    for row in rows:
        try:
            result.append(Job.from_dict(row.get("job", row)))
        except (ValueError, TypeError, AttributeError):
            invalid += 1
    result.report.queries.append(QueryOutcome("replay", "partial" if invalid else "success" if rows else "valid_empty",
        len(rows), len(result), invalid))
    return result


def run_job_finder(dry_run=False, test_notify=False, config_path=None, replay_path=None,
                   state_path=SEEN_JOBS_FILE, discovery_path=DISCOVERY_FILE, report_dir=None,
                   verification_sample=False):
    report_dir = report_dir or BASE_DIR / "output" / "latest"
    dry_run = dry_run or replay_path is not None
    report = {"started_at": utc_now(), "health": "failed", "environment": environment_versions(),
              "sources": [], "counts": {}, "jobs": [], "deliveries": []}
    try:
        config = load_config(config_path)
        if verification_sample:
            # Manual verification only: refresh within existing request budgets,
            # cap delivery at three jobs and leave repository defaults untouched.
            config["notifications"]["max_per_run"] = 3
            config["jobspy"]["interval_hours"] = 0
            config["jobspy"]["low_yield_interval_hours"] = 0
            config["jobspy"]["max_queries"] = min(12, config["jobspy"]["max_queries"])
            config["jobspy"]["max_seconds"] = min(300, config["jobspy"]["max_seconds"])
            config["local_scrapers"]["interval_hours"] = 0
            config["linkedin_posts"]["interval_hours"] = 0
        report["verification_sample"] = verification_sample
        report["profile_version"] = config["profile"]["version"]
        report["matcher_version"] = MATCHER_VERSION
        report["mode"] = "replay" if replay_path else "dry_run" if dry_run else "live"
        notifier = NotificationManager(config)
        if test_notify:
            if dry_run:
                raise ValueError("Test notification cannot be combined with dry-run or replay")
            delivery = notifier.send_test_notification()
            report["deliveries"] = [asdict(item) for item in delivery.outcomes]
            report["health"] = "healthy" if delivery and delivery.outcomes else "failed"
            return 0 if report["health"] == "healthy" else 1
        if not dry_run and config["notifications"]["discord_enabled"] and not config["discord_webhook_url"]:
            raise ValueError("DISCORD_WEBHOOK_URL is required for live delivery; use --dry-run for evaluation")
        # Load history before any network activity; corruption must not reset suppression.
        tracker = JobTracker(state_path, **config["state"])
        discovery = validate_discovery_state(read_json(discovery_path, {}))
        sources = []
        if replay_path:
            sources.append(read_replay(replay_path))
        else:
            for fetch in (fetch_jobspy_jobs, fetch_rozee_jobs, fetch_linkedin_plain_posts, fetch_remote_feeds):
                try:
                    sources.append(fetch(config, discovery))
                except Exception as exc:
                    failed = SourceResult(fetch.__name__)
                    failed.report.queries.append(QueryOutcome(fetch.__name__, "failed", reason=type(exc).__name__))
                    sources.append(failed)
        report["sources"] = [source.report.to_dict() for source in sources]
        raw = [job for source in sources for job in source]
        candidates = merge_jobs(raw)
        for job in candidates:
            evaluate_job(job, config)
        candidates = rank_jobs(candidates)
        tiers = Counter(job.decision["tier"] for job in candidates)
        reasons = Counter(reason for job in candidates for reason in job.decision["reasons"] + job.decision["gaps"])
        report["counts"] = {"raw": len(raw), "unique": len(candidates),
            "qualified": tiers["qualified"], "review": tiers["review"], "rejected": tiers["rejected"],
            "missing_descriptions": sum(job.description_status != "full" for job in candidates)}
        report["reason_counts"] = dict(reasons)
        report["jobs"] = [job.to_dict() for job in candidates]
        report["query_metrics"] = query_metrics(sources, config)
        report["query_budgets"] = {
            "jobspy_search_requests": config["jobspy"]["max_queries"],
            "jobspy_max_seconds": config["jobspy"]["max_seconds"],
            "rozee_search_requests": config["local_scrapers"]["max_queries"] * config["local_scrapers"]["max_pages"],
            "rozee_detail_requests": config["local_scrapers"]["max_details"],
            "post_search_queries": len(config["linkedin_posts"]["queries"]),
            "post_detail_requests": config["linkedin_posts"]["max_checks"],
        }
        eligible_tiers = {"qualified", "review"} if config["notifications"]["send_review"] else {"qualified"}
        if verification_sample:
            eligible_tiers = {"qualified"} if tiers["qualified"] else {"review"}
            report["verification_tier"] = next(iter(eligible_tiers))
        eligible = [job for job in candidates if job.decision["tier"] in eligible_tiers]
        new = tracker.filter_new_jobs(eligible)
        report["counts"]["already_notified"] = len(eligible) - len(new)
        if verification_sample:
            report["counts"]["outside_verification_sample"] = max(0, len(new) - 3)
            new = new[:3]
        report["counts"]["new_candidates"] = len(new)
        active_sources = [source for source in sources if not source.report.skipped]
        degraded = any(source.report.status not in {"success", "valid_empty"} for source in active_sources)
        report["health"] = "degraded" if degraded else "healthy"
        if not active_sources:
            report["health"] = "idle"
        if dry_run or not config["notifications"]["discord_enabled"]:
            report["counts"]["would_notify"] = min(len(new), config["notifications"]["max_per_run"])
            report["counts"]["pending_existing"] = len(tracker.pending)
            logger.info("Evaluation: %s", report["counts"])
            if not dry_run:
                for source in sources:
                    discovery.update(source.updates)
                save_with_backup(discovery_path, discovery, validate_discovery_state)
            return 2 if degraded else 0

        tracker.enqueue(new)  # Payloads persist before delivery, including deferred candidates.
        due = []
        retired = Counter()
        # Reevaluate stored payloads even when every source returns zero jobs.
        for job in tracker.pending_jobs():
            decision = evaluate_job(job, config)
            if tracker.is_seen(job) or tracker.expired_pending(job.job_id) or decision.tier == "rejected":
                tracker.retire(job.job_id)
                retired["ineligible_or_expired"] += 1
            elif decision.tier in eligible_tiers:
                due.append(job)
        tracker.save()
        report["retired_pending"] = dict(retired)
        due = rank_jobs(due)[:config["notifications"]["max_per_run"]]
        # Capture evidence before side effects; failures still leave useful diagnostics.
        write_report(report, report_dir, step_summary=False)
        delivery = notifier.send_notifications(due, on_result=tracker.record_delivery,
                                                on_batch_result=tracker.record_deliveries)
        report["deliveries"] = [asdict(item) for item in delivery.outcomes]
        report["counts"]["delivered"] = len(delivery.delivered_ids)
        report["counts"]["delivery_failed_or_uncertain"] = len(delivery.failed_ids)
        report["counts"]["pending_remaining"] = len(tracker.pending)
        report["counts"]["permanent_delivery_failures"] = sum(r["status"] == "permanent_failure" for r in tracker.pending.values())
        if delivery.failed_ids or any(r["status"] == "permanent_failure" for r in tracker.pending.values()):
            report["health"] = "degraded"
        for source in sources:
            discovery.update(source.updates)
        save_with_backup(discovery_path, discovery, validate_discovery_state)
        return 2 if report["health"] == "degraded" else 0
    except (ValueError, StateError, OSError) as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc) if isinstance(exc, (ValueError, StateError)) else type(exc).__name__
        report["health"] = "failed"
        logger.error("Pipeline stopped: %s", type(exc).__name__)
        return 1
    finally:
        report["finished_at"] = utc_now()
        report["operational_outcome"] = assess_run(report)
        write_report(report, report_dir)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Resume-aligned job discovery and Discord alerts")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Live scraping, no notifications or state writes")
    mode.add_argument("--test-notify", action="store_true", help="Explicitly send one Discord test message")
    mode.add_argument("--replay", dest="replay_path", help="Offline JSON evaluation; never sends or writes state")
    parser.add_argument("--config", dest="config_path", help="YAML overrides merged with repository defaults")
    parser.add_argument("--state", dest="state_path", type=Path, default=SEEN_JOBS_FILE)
    parser.add_argument("--discovery-state", dest="discovery_path", type=Path, default=DISCOVERY_FILE)
    parser.add_argument("--report-dir", type=Path)
    return run_job_finder(**vars(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
