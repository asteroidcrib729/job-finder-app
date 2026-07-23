import logging
import requests
import time
from typing import List
from scrapers.base import Job

logger = logging.getLogger(__name__)

# Platform color branding for Discord embeds
PLATFORM_COLORS = {
    "linkedin": 0x0A66C2,  # LinkedIn Blue
    "indeed": 0x2164F3,    # Indeed Blue
    "glassdoor": 0x0CAA41, # Glassdoor Green
    "google": 0x4285F4,    # Google Blue
    "bayt": 0xFF6C00,      # Bayt Orange
    "rozee.pk": 0xD9251D,  # Rozee Red
}

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_jobs(self, jobs: List[Job]) -> bool:
        if not self.webhook_url:
            logger.warning("[Discord] No Webhook URL provided. Skipping Discord notification.")
            return False

        success_count = 0
        for job in jobs:
            embed = self._build_embed(job)
            payload = {
                "username": "Job Finder Alert Bot 🚀",
                "avatar_url": "https://cdn-icons-png.flaticon.com/512/2936/2936886.png",
                "embeds": [embed]
            }

            try:
                res = requests.post(self.webhook_url, json=payload, timeout=10)
                if res.status_code in [200, 204]:
                    success_count += 1
                elif res.status_code == 429: # Rate limited
                    retry_after = res.json().get("retry_after", 1.5)
                    logger.warning(f"[Discord] Rate limited. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    requests.post(self.webhook_url, json=payload, timeout=10)
                    success_count += 1
                else:
                    logger.error(f"[Discord] Failed to send webhook ({res.status_code}): {res.text}")
            except Exception as e:
                logger.error(f"[Discord] Error sending job '{job.title}': {e}")

            # Avoid overwhelming Discord rate limits
            time.sleep(0.5)

        logger.info(f"[Discord] Successfully delivered {success_count}/{len(jobs)} job alerts.")
        return success_count > 0

    def _build_embed(self, job: Job) -> dict:
        color = PLATFORM_COLORS.get(job.platform.lower(), 0x7289DA)
        location_badge = "🌐 Remote" if job.is_remote else f"📍 {job.location}"

        fields = [
            {"name": "🏢 Company", "value": job.company, "inline": True},
            {"name": "📍 Location", "value": location_badge, "inline": True},
            {"name": "🏷️ Platform", "value": job.platform, "inline": True},
        ]

        if job.date_posted:
            fields.append({"name": "🕒 Posted", "value": job.date_posted, "inline": True})

        description_snippet = job.description[:250] + "..." if len(job.description) > 250 else job.description

        embed = {
            "title": f"🆕 {job.title}",
            "url": job.url,
            "color": color,
            "description": f"{description_snippet}\n\n👉 **[Click Here to Apply on {job.platform}]({job.url})**" if description_snippet else f"👉 **[Click Here to Apply on {job.platform}]({job.url})**",
            "fields": fields,
            "footer": {
                "text": "Automated Fresh Graduate & Junior Job Discovery Pipeline"
            }
        }
        return embed
