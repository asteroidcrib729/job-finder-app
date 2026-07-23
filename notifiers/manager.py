import logging
from typing import List
from scrapers.base import Job
from notifiers.discord import DiscordNotifier
from notifiers.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

class NotificationManager:
    def __init__(self, config: dict):
        self.config = config
        self.discord_enabled = config.get("notifications", {}).get("discord_enabled", True)
        self.telegram_enabled = config.get("notifications", {}).get("telegram_enabled", True)
        
        self.discord_url = config.get("discord_webhook_url", "")
        self.telegram_token = config.get("telegram_bot_token", "")
        self.telegram_chat_id = config.get("telegram_chat_id", "")

        self.discord_notifier = DiscordNotifier(self.discord_url) if self.discord_url else None
        self.telegram_notifier = TelegramNotifier(self.telegram_token, self.telegram_chat_id) if self.telegram_token else None

    def send_notifications(self, jobs: List[Job]) -> bool:
        if not jobs:
            logger.info("No new jobs to notify.")
            return True

        logger.info(f"Dispatching notifications for {len(jobs)} new job postings...")

        sent_any = False
        if self.discord_enabled and self.discord_notifier:
            if self.discord_notifier.send_jobs(jobs):
                sent_any = True

        if self.telegram_enabled and self.telegram_notifier:
            if self.telegram_notifier.send_jobs(jobs):
                sent_any = True

        if not self.discord_notifier and not self.telegram_notifier:
            logger.warning("No notification channels configured! Set DISCORD_WEBHOOK_URL or TELEGRAM_BOT_TOKEN/CHAT_ID.")

        return sent_any

    def send_test_notification(self) -> bool:
        test_job = Job(
            title="Junior / Associate Software Engineer (Test Alert)",
            company="Job Finder Test Corp",
            location="Karachi, Pakistan (Remote Available)",
            url="https://github.com",
            platform="Test System",
            date_posted="Just Now",
            is_remote=True,
            description="This is a test notification confirming your Job Finder push alerts are working properly!"
        )
        return self.send_notifications([test_job])
