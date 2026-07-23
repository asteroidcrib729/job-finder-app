import argparse
import logging
import sys

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from typing import List
from config import load_config
from scrapers.base import Job
from scrapers.jobspy_adapter import fetch_jobspy_jobs
from scrapers.rozee_scraper import fetch_rozee_jobs
from filtering.filter import filter_fresh_grad_jobs
from storage.tracker import JobTracker
from notifiers.manager import NotificationManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("JobFinderMain")

def run_job_finder(dry_run: bool = False, test_notify: bool = False):
    config = load_config()
    notifier = NotificationManager(config)

    if test_notify:
        logger.info("Executing test notification...")
        success = notifier.send_test_notification()
        if success:
            logger.info("✅ Test notification sent successfully!")
        else:
            logger.error("❌ Test notification failed. Check your webhook / bot credentials.")
        return

    logger.info("==========================================")
    logger.info("🚀 Starting Job Discovery Pipeline")
    logger.info("==========================================")

    raw_jobs: List[Job] = []

    # 1. Scrape via JobSpy (LinkedIn, Indeed, Glassdoor, Google Jobs, Bayt)
    logger.info("--- 1. Running JobSpy Scraper ---")
    jobspy_jobs = fetch_jobspy_jobs(config)
    logger.info(f"JobSpy fetched {len(jobspy_jobs)} raw jobs.")
    raw_jobs.extend(jobspy_jobs)

    # 2. Scrape via Local Scraper (Rozee.pk)
    logger.info("--- 2. Running Rozee.pk Scraper ---")
    rozee_jobs = fetch_rozee_jobs(config)
    logger.info(f"Rozee.pk fetched {len(rozee_jobs)} raw jobs.")
    raw_jobs.extend(rozee_jobs)

    if not raw_jobs:
        logger.info("No job postings fetched in this run.")
        return

    # 3. Client-side title & experience level filtering
    logger.info("--- 3. Filtering Fresh Graduate & Junior Positions ---")
    relevant_jobs = filter_fresh_grad_jobs(raw_jobs, config)

    # 4. Deduplicate against seen jobs state
    logger.info("--- 4. Deduplicating against Previously Notified Jobs ---")
    tracker = JobTracker()
    new_jobs = tracker.filter_new_jobs(relevant_jobs)

    logger.info(f"Found {len(new_jobs)} NEW un-notified job postings.")

    if dry_run:
        logger.info("⚡ DRY-RUN ENABLED: Skipping notification delivery and state saving.")
        logger.info("--- DRY-RUN SUMMARY ---")
        for idx, job in enumerate(new_jobs, 1):
            logger.info(f"#{idx} | [{job.platform}] {job.title} @ {job.company} | Location: {job.location} | URL: {job.url}")
        return

    # 5. Dispatch Notifications
    if new_jobs:
        logger.info("--- 5. Dispatching Phone Alerts ---")
        sent = notifier.send_notifications(new_jobs)
        if sent:
            logger.info("Marking newly notified jobs as seen...")
            tracker.mark_as_seen(new_jobs)
    else:
        logger.info("No new job posts to notify at this time.")

    logger.info("==========================================")
    logger.info("✨ Job Discovery Pipeline Completed")
    logger.info("==========================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automated Job Finder & Alert Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Scrape & filter jobs without sending alerts or saving state.")
    parser.add_argument("--test-notify", action="store_true", help="Send a test notification to verify webhook/bot settings.")
    args = parser.parse_args()

    run_job_finder(dry_run=args.dry_run, test_notify=args.test_notify)
