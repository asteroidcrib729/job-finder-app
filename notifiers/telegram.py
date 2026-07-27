import logging
import requests
import time
from typing import List
from scrapers.base import Job

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage" if bot_token else ""

    def send_jobs(self, jobs: List[Job]) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.warning("[Telegram] Bot Token or Chat ID missing. Skipping Telegram notification.")
            return False

        success_count = 0
        for job in jobs:
            msg = self._build_message(job)
            payload = {
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }

            try:
                res = requests.post(self.api_url, json=payload, timeout=10)
                if res.status_code == 200:
                    success_count += 1
                else:
                    logger.error(f"[Telegram] Failed ({res.status_code}): {res.text}")
            except Exception as e:
                logger.error(f"[Telegram] Error sending job alert: {e}")

            time.sleep(0.4)

        logger.info(f"[Telegram] Delivered {success_count}/{len(jobs)} job alerts.")
        return success_count > 0

    def _build_message(self, job: Job) -> str:
        if job.is_priority_location:
            location_str = f"⭐ <b>{job.location}</b> (Priority Karachi Hub)"
        elif job.is_remote:
            location_str = "🌐 <b>Remote</b>"
        else:
            location_str = f"📍 <b>{job.location}</b>"

        email_block = ""
        if job.recruiter_email:
            email_block = f"\n📧 <b>Direct Recruiter Email:</b> <code>{job.recruiter_email}</code>\n"

        return (
            f"🚨 <b>New Job Alert ({job.platform})</b>\n\n"
            f"💼 <b>Role:</b> {job.title}\n"
            f"🏢 <b>Company:</b> {job.company}\n"
            f"Location: {location_str}\n"
            f"🕒 <b>Posted:</b> {job.date_posted}\n"
            f"{email_block}\n"
            f"🔗 <a href='{job.url}'>Click Here to Apply Directly</a>"
        )
