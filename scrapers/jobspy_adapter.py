import logging
from typing import List
from scrapers.base import Job

logger = logging.getLogger(__name__)

def fetch_jobspy_jobs(config: dict) -> List[Job]:
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.error("python-jobspy is not installed. Skipping JobSpy scraping.")
        return []

    jobspy_cfg = config.get("jobspy", {})
    sites = jobspy_cfg.get("sites", ["linkedin", "indeed", "google"])
    results_wanted = jobspy_cfg.get("results_wanted", 15)
    hours_old = jobspy_cfg.get("hours_old", 72)
    country_indeed = jobspy_cfg.get("country_indeed", "Pakistan")
    
    keywords = config.get("search_keywords", ["Software Engineer"])
    locations = config.get("locations", ["Karachi, Pakistan", "Remote"])
    
    collected_jobs: List[Job] = []

    for location in locations:
        for keyword in keywords:
            is_remote_search = "remote" in location.lower()
            actual_location = "Karachi, Pakistan" if is_remote_search else location

            for site in sites:
                logger.info(f"[JobSpy] Searching '{keyword}' on {site.upper()} in '{location}'...")
                try:
                    jobs_df = scrape_jobs(
                        site_name=[site],
                        search_term=keyword,
                        location=actual_location,
                        is_remote=is_remote_search,
                        results_wanted=results_wanted,
                        hours_old=hours_old,
                        country_indeed=country_indeed
                    )

                    if jobs_df is None or jobs_df.empty:
                        continue

                    for _, row in jobs_df.iterrows():
                        title = str(row.get("title", "") or "").strip()
                        company = str(row.get("company", "") or "").strip()
                        job_url = str(row.get("job_url", "") or "").strip()
                        site_name = str(row.get("site", site) or site).capitalize()
                        job_location = str(row.get("location", "") or location).strip()
                        date_posted = str(row.get("date_posted", "") or "Recently")
                        description = str(row.get("description", "") or "")
                        
                        if not title or not job_url or title.lower() == "nan" or job_url.lower() == "nan":
                            continue

                        is_remote = is_remote_search or ("remote" in job_location.lower()) or ("remote" in title.lower())

                        collected_jobs.append(
                            Job(
                                title=title,
                                company=company or "Unknown Company",
                                location=job_location or location,
                                url=job_url,
                                platform=site_name,
                                date_posted=date_posted,
                                is_remote=is_remote,
                                description=description if description and description.lower() != "nan" else ""
                            )
                        )

                except Exception as e:
                    logger.warning(f"[JobSpy] Failed on {site} for '{keyword}' in '{location}': {e}")
                    continue

    return collected_jobs
