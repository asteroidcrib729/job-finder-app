import logging
import re
import requests
from typing import List, Set
from scrapers.base import Job

logger = logging.getLogger(__name__)

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Disallowed old years and relative time markers
OLD_TIME_MARKERS = ["1y ago", "2y ago", "3y ago", "4y ago", "5y ago", "2020", "2021", "2022", "2023", "2024", "2025"]

CHECK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def is_post_active_and_recent(url: str, text: str) -> bool:
    """Verifies that the LinkedIn post is from recent months and not deleted."""
    text_lower = text.lower()
    
    # 1. Reject if snippet indicates an old year
    if any(marker in text_lower for marker in OLD_TIME_MARKERS):
        logger.debug(f"[LinkedInPosts] Dropped stale post from past years: {url}")
        return False

    # 2. Quick check if URL is accessible / not a deleted 404
    try:
        res = requests.get(url, headers=CHECK_HEADERS, timeout=5, allow_redirects=True)
        if res.status_code in [404, 410]:
            logger.debug(f"[LinkedInPosts] Dropped deleted post ({res.status_code}): {url}")
            return False
        if "post not found" in res.text.lower() or "this post was deleted" in res.text.lower():
            logger.debug(f"[LinkedInPosts] Dropped deleted post content: {url}")
            return False
    except Exception:
        pass  # If network timeout on check, allow based on time filter

    return True

def fetch_linkedin_plain_posts(config: dict) -> List[Job]:
    """
    Scrapes fresh LinkedIn recruiter status posts (published in the last month)
    using DDGS with timelimit='m' and extracts direct recruiter email addresses.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            logger.error("[LinkedInPosts] ddgs package is not installed. Skipping recruiter post scraping.")
            return []

    queries = [
        'site:linkedin.com/posts "Karachi" ("hiring" OR "send your CV" OR "apply at") ("Software Engineer" OR "Python" OR "React" OR "Full Stack")',
        'site:linkedin.com/posts "Karachi" ("we are hiring" OR "looking for") ("Junior" OR "Associate" OR "Fresh" OR "Software Developer")',
        'site:linkedin.com/posts "Remote" ("hiring" OR "send CV") ("Python Developer" OR "React Developer" OR "Full Stack" OR "Node")',
        'site:linkedin.com/posts "Karachi" ("careers@" OR "hr@" OR "jobs@") ("developer" OR "engineer")',
        'site:linkedin.com/feed/update "Karachi" ("hiring" OR "send CV") ("developer" OR "engineer")'
    ]

    found_jobs: List[Job] = []
    seen_urls: Set[str] = set()

    try:
        ddgs = DDGS()
        for query in queries:
            logger.info(f"[LinkedInPosts] Querying (Past Month): {query[:65]}...")
            try:
                # timelimit='m' restricts results strictly to the past month (no 3-4 year old posts)
                results = list(ddgs.text(query, timelimit='m', max_results=6))
                for item in results:
                    title = item.get("title", "")
                    post_url = item.get("href", "")
                    snippet = item.get("body", "")

                    if not post_url or post_url in seen_urls:
                        continue

                    # Ensure it is a genuine LinkedIn post or feed update
                    if not ("/posts/" in post_url or "/feed/update/" in post_url):
                        continue

                    seen_urls.add(post_url)
                    full_text = f"{title} {snippet}"

                    # Verify freshness and active status
                    if not is_post_active_and_recent(post_url, full_text):
                        continue

                    # Extract any email addresses in the post snippet/title
                    emails = re.findall(EMAIL_REGEX, full_text)
                    extracted_email = ""
                    if emails:
                        valid_emails = [e for e in emails if not any(inv in e.lower() for inv in ["example.com", "domain.com", "w3.org", "schema.org", "sentry.io"])]
                        if valid_emails:
                            extracted_email = valid_emails[0]

                    clean_title = title.replace(" | LinkedIn", "").replace(" on LinkedIn: ", " - ")
                    if len(clean_title) > 85:
                        clean_title = clean_title[:82] + "..."

                    is_remote = "remote" in query.lower() or "remote" in full_text.lower() or "work from home" in full_text.lower()
                    location = "Remote" if is_remote else "Karachi, Pakistan"

                    found_jobs.append(
                        Job(
                            title=clean_title or "Hiring Announcement (LinkedIn Recruiter Post)",
                            company="LinkedIn Recruiter Post",
                            location=location,
                            url=post_url,
                            platform="LinkedIn Post",
                            date_posted="Past Month (Fresh)",
                            is_remote=is_remote,
                            description=snippet,
                            recruiter_email=extracted_email
                        )
                    )

            except Exception as e:
                logger.warning(f"[LinkedInPosts] Error during query execution: {e}")
                continue

    except Exception as e:
        logger.error(f"[LinkedInPosts] Failed to initialize DDGS: {e}")

    logger.info(f"[LinkedInPosts] Discovered {len(found_jobs)} active, fresh LinkedIn recruiter posts.")
    return found_jobs
