import logging
from typing import List
from scrapers.base import Job

logger = logging.getLogger(__name__)

def filter_fresh_grad_jobs(jobs: List[Job], config: dict) -> List[Job]:
    filter_cfg = config.get("filtering", {})
    includes = [k.lower() for k in filter_cfg.get("title_include_keywords", [])]
    excludes = [k.lower() for k in filter_cfg.get("title_exclude_keywords", [])]

    filtered_jobs: List[Job] = []

    for job in jobs:
        title_lower = job.title.lower()

        # Check exclusion keywords (e.g. senior, lead, principal, manager)
        if any(ex in title_lower for ex in excludes):
            logger.debug(f"Filtered out senior role: '{job.title}' ({job.company})")
            continue

        # Check inclusion keywords if specified
        if includes:
            if not any(inc in title_lower for inc in includes):
                logger.debug(f"Filtered out irrelevant title: '{job.title}' ({job.company})")
                continue

        filtered_jobs.append(job)

    logger.info(f"Filtered {len(jobs)} scraped jobs -> {len(filtered_jobs)} matching fresh graduate & junior roles.")
    return filtered_jobs
