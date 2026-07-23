import logging
import requests
from bs4 import BeautifulSoup
from typing import List
from scrapers.base import Job

logger = logging.getLogger(__name__)

ROZEE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def fetch_rozee_jobs(config: dict) -> List[Job]:
    local_cfg = config.get("local_scrapers", {})
    if not local_cfg.get("rozee_enabled", True):
        return []

    keywords = config.get("search_keywords", ["Software Engineer"])
    jobs: List[Job] = []

    for keyword in keywords:
        # Search Karachi specific (fc/1592) and general
        search_urls = [
            f"https://www.rozee.pk/job/jsearch/q/{keyword.replace(' ', '-')}/fc/1592",
            f"https://www.rozee.pk/job/jsearch/q/{keyword.replace(' ', '-')}"
        ]

        for url in search_urls:
            logger.info(f"[Rozee] Scraping '{keyword}' via {url}...")
            try:
                response = requests.get(url, headers=ROZEE_HEADERS, timeout=12)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, "html.parser")
                job_items = soup.select(".job") or soup.select(".s-box") or soup.select("[class*='job']")

                for item in job_items:
                    title_elem = item.select_one(".jtitle") or item.select_one("h3 a") or item.select_one("a[title]")
                    company_elem = item.select_one(".cname") or item.select_one(".company-name") or item.select_one(".comp-name")
                    
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    href = title_elem.get("href", "")
                    
                    if href and not href.startswith("http"):
                        job_url = f"https://www.rozee.pk{href}" if href.startswith("/") else f"https://www.rozee.pk/{href}"
                    else:
                        job_url = href

                    company = company_elem.get_text(strip=True) if company_elem else "Unknown Company"
                    
                    if not title or not job_url:
                        continue

                    is_remote = "remote" in title.lower() or "work from home" in title.lower()

                    jobs.append(
                        Job(
                            title=title,
                            company=company,
                            location="Karachi, Pakistan" if "1592" in url else "Pakistan",
                            url=job_url,
                            platform="Rozee.pk",
                            date_posted="Recently",
                            is_remote=is_remote,
                            description=""
                        )
                    )

            except Exception as e:
                logger.warning(f"[Rozee] Error fetching '{keyword}': {e}")
                continue

    return jobs
