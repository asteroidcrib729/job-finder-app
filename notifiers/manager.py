import logging
from typing import List
from scrapers.base import Job
from notifiers.discord import DiscordNotifier

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self, config: dict):
        self.config = config
        self.discord_enabled = config.get("notifications", {}).get("discord_enabled", True)
        self.discord_url = config.get("discord_webhook_url", "")
        self.discord_notifier = DiscordNotifier(self.discord_url) if self.discord_url else None

    def send_notifications(self, jobs: List[Job]) -> bool:
        if not jobs:
            logger.info("No new jobs to notify.")
            return True

        logger.info(f"Dispatching notifications for {len(jobs)} new job postings to Discord...")

        if self.discord_enabled and self.discord_notifier:
            return self.discord_notifier.send_jobs(jobs)

        logger.warning("[Discord] No Webhook URL configured! Set DISCORD_WEBHOOK_URL environment secret.")
        return False

    def send_test_notification(self) -> bool:
        test_job = Job(
            title="Junior / Associate Software Engineer (Test Alert)",
            company="Job Finder Test Corp",
            location="Karachi, Pakistan (Remote Available)",
            url="https://github.com",
            platform="Test System",
            date_posted="Just Now",
            is_remote=True,
            description="This is a test notification confirming your Job Finder Discord push alerts are working properly!"
        )
        return self.send_notifications([test_job])
