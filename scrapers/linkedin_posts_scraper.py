import logging
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Set
from scrapers.base import Job

logger = logging.getLogger(__name__)

SEARCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def fetch_linkedin_plain_posts(config: dict) -> List[Job]:
    """
    Scrapes plain LinkedIn status posts (hiring announcements) indexed by Google
    and extracts direct recruiter email addresses.
    """
    keywords = config.get("search_keywords", ["Software Engineer", "Junior Software Engineer", "Python Developer"])
    locations = ["Karachi", "Remote"]
    
    found_jobs: List[Job] = []
    seen_urls: Set[str] = set()

    for location in locations:
        for keyword in keywords:
            # Query Google Search for LinkedIn post announcements
            query = f'site:linkedin.com/posts "{location}" ("hiring" OR "send CV" OR "apply at" OR "email") "{keyword}"'
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}"

            logger.info(f"[LinkedInPosts] Searching recruiter posts for '{keyword}' in '{location}'...")
            try:
                res = requests.get(url, headers=SEARCH_HEADERS, timeout=10)
                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                results = soup.select(".g") or soup.select("div[class*='g']") or soup.select(".MjjYud")

                for result in results:
                    a_tag = result.select_one("a[href*='linkedin.com/posts']") or result.select_one("a[href*='linkedin.com/feed']")
                    title_elem = result.select_one("h3")
                    snippet_elem = result.select_one(".VwiC3b") or result.select_one("[class*='snippet']")

                    if not a_tag:
                        continue

                    post_url = a_tag.get("href", "")
                    if not post_url or post_url in seen_urls:
                        continue

                    seen_urls.add(post_url)
                    raw_title = title_elem.get_text(strip=True) if title_elem else f"Recruiter Post: {keyword}"
                    snippet_text = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    # Extract any email addresses in the post snippet/title
                    emails = re.findall(EMAIL_REGEX, f"{raw_title} {snippet_text}")
                    extracted_email = emails[0] if emails else ""

                    # Filter out non-email domain matches like 'example.com' or image filenames
                    if extracted_email and any(invalid in extracted_email.lower() for invalid in ["example.com", "domain.com", "w3.org"]):
                        extracted_email = ""

                    clean_title = raw_title.replace(" | LinkedIn", "").replace(" on LinkedIn: ", " - ")
                    if len(clean_title) > 80:
                        clean_title = clean_title[:77] + "..."

                    found_jobs.append(
                        Job(
                            title=clean_title or f"Hiring {keyword} (Recruiter Post)",
                            company="LinkedIn Recruiter Post",
                            location=f"{location}, Pakistan" if location == "Karachi" else "Remote",
                            url=post_url,
                            platform="LinkedIn Post",
                            date_posted="Recently",
                            is_remote="remote" in location.lower() or "remote" in snippet_text.lower(),
                            description=snippet_text,
                            recruiter_email=extracted_email
                        )
                    )

            except Exception as e:
                logger.warning(f"[LinkedInPosts] Error fetching plain posts for '{keyword}': {e}")
                continue

    logger.info(f"[LinkedInPosts] Discovered {len(found_jobs)} plain LinkedIn recruiter posts.")
    return found_jobs
