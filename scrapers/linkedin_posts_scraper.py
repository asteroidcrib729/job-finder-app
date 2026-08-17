import logging
import re
from typing import List, Set
from scrapers.base import Job

logger = logging.getLogger(__name__)

EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def fetch_linkedin_plain_posts(config: dict) -> List[Job]:
    """
    Scrapes plain LinkedIn status posts (hiring announcements) using DDGS
    and extracts direct recruiter email addresses.
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
        'site:linkedin.com/posts "Karachi" ("hiring" OR "send CV" OR "apply at" OR "email") ("Software" OR "Python" OR "React" OR "Developer")',
        'site:linkedin.com/feed/update "Karachi" ("hiring" OR "send CV" OR "apply") ("Engineer" OR "Developer" OR "Python")',
        'LinkedIn Karachi "send your CV" "developer" OR "engineer"',
        'LinkedIn Karachi hiring "Junior" OR "Associate" OR "Fresh" "Engineer"',
        'site:linkedin.com/posts "Remote" ("hiring" OR "send CV") ("Python" OR "Full Stack" OR "React" OR "Node" OR "Developer")',
        'site:linkedin.com/feed/update "Remote" hiring ("Software Engineer" OR "Python" OR "React")'
    ]

    found_jobs: List[Job] = []
    seen_urls: Set[str] = set()

    try:
        ddgs = DDGS()
        for query in queries:
            logger.info(f"[LinkedInPosts] Querying: {query[:60]}...")
            try:
                results = list(ddgs.text(query, max_results=6))
                for item in results:
                    title = item.get("title", "")
                    post_url = item.get("href", "")
                    snippet = item.get("body", "")

                    if not post_url or post_url in seen_urls:
                        continue

                    # Ensure it is a genuine LinkedIn post or feed update, not general search or profile
                    if not ("/posts/" in post_url or "/feed/update/" in post_url):
                        continue

                    seen_urls.add(post_url)

                    # Extract any email addresses in the post snippet/title
                    full_text = f"{title} {snippet}"
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
                            date_posted="Recently",
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

    logger.info(f"[LinkedInPosts] Discovered {len(found_jobs)} plain LinkedIn recruiter posts.")
    return found_jobs
