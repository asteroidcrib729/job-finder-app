from notifiers.discord import DiscordNotifier, DeliveryOutcome, DeliveryResult
from scrapers.base import Job


class NotificationManager:
    def __init__(self, config):
        self.config = config
        options = config["notifications"]
        self.enabled = options["discord_enabled"]
        self.discord_notifier = DiscordNotifier(config.get("discord_webhook_url", ""),
            max_attempts=options["max_attempts"], max_retry_wait=options["max_retry_wait"])

    def send_notifications(self, jobs, on_result=None, on_batch_result=None):
        if self.enabled:
            return self.discord_notifier.send_jobs(jobs, on_result,
                review_digest=self.config["notifications"]["review_digest"], on_batch_result=on_batch_result)
        return DeliveryResult([DeliveryOutcome(job.job_id, "failed", "notifications_disabled") for job in jobs])

    def send_test_notification(self):
        return self.send_notifications([Job("Job Finder test notification", "Test", "Karachi, Pakistan",
            "https://github.com", "Test", description="Webhook connection test.")])
