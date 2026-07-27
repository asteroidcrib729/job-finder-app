import re
import logging
from typing import List, Tuple
from scrapers.base import Job

logger = logging.getLogger(__name__)

# Faraz Hussain's Skill Keywords from Resume
FARAZ_SKILLS = [
    "python", "javascript", "typescript", "react", "next.js", "nextjs", 
    "node.js", "nodejs", "express", "django", "flask", "fastapi", "tailwind",
    "postgresql", "mysql", "sql server", "sql", "mongodb", "c#", "java",
    "rest", "api", "git", "web", "frontend", "backend", "fullstack", "full stack",
    "software engineer", "software developer"
]

# Preferred Karachi Locations
PREFERRED_KARACHI_HUBS = [
    "gulshan", "gulshan-e-iqbal",
    "jauhar", "johar", "gulistan-e-jauhar", "gulistan-e-johar",
    "shahrah-e-faisal", "faisal",
    "pechs", "p.e.c.h.s",
    "nastp",
    "north nazimabad", "nazimabad",
    "naya nazimabad"
]

# Irrelevant domains for Faraz's software/full-stack profile
IRRELEVANT_DOMAINS = [
    "salesforce", "sap", "embedded", "hardware", "ios developer", "swift",
    "flutter", "react native", "android developer", "kotlin", "devops engineer",
    "cloud security", "cyber security", "network engineer", "telecom", "fpga",
    "autocad", "graphic designer", "ui/ux designer", "seo specialist", "content writer"
]

# Senior / High-level title exclusions
EXCLUDED_TITLES = [
    "senior", "sr.", "sr ", "lead", "principal", "architect", 
    "staff engineer", "manager", "director", "head of", "vp", "executive"
]

def parse_required_experience_years(text: str) -> List[int]:
    """Extracts required experience years from job title/description text."""
    if not text:
        return []
    
    text_lower = text.lower()
    years_found: List[int] = []

    # Patterns matching '5+ years', '3-5 yrs', 'minimum 2 years of experience'
    patterns = [
        r'(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp|in)?',
        r'(?:experience|exp)\s*(?:of|:)?\s*(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)',
        r'(\d+)\s*\+\s*(?:years?|yrs?)',
        r'(\d+)\s*(?:years?|yrs?)\s*(?:plus|\+)',
        r'minimum\s*(\d+)\s*(?:years?|yrs?)',
        r'at least\s*(\d+)\s*(?:years?|yrs?)',
        r'requires?\s*(\d+)\s*\+?\s*(?:years?|yrs?)',
        r'(\d+)\s*to\s*\d+\s*(?:years?|yrs?)'
    ]

    for pat in patterns:
        matches = re.findall(pat, text_lower)
        for m in matches:
            try:
                val = int(m)
                # Ignore unreasonable numbers (e.g. 2026 year or 100)
                if 1 <= val <= 25:
                    years_found.append(val)
            except ValueError:
                continue

    return years_found

def is_location_valid_for_faraz(job: Job) -> Tuple[bool, bool]:
    """
    Returns (is_valid, is_priority_hub).
    On-Site / Hybrid jobs MUST be in Karachi, Pakistan.
    Remote jobs can be located anywhere.
    """
    location_lower = job.location.lower()
    title_lower = job.title.lower()
    desc_lower = job.description.lower()

    # Determine if remote
    is_remote = job.is_remote or "remote" in location_lower or "remote" in title_lower or "work from home" in desc_lower

    if is_remote:
        # Remote positions are valid worldwide or Pakistan
        return True, False

    # For On-Site / Hybrid positions: MUST be in Karachi
    if not ("karachi" in location_lower or "pk" in location_lower or "pakistan" in location_lower or "karāchi" in location_lower):
        logger.debug(f"[Filter] Rejected non-Karachi on-site job: '{job.title}' @ {job.company} ({job.location})")
        return False, False

    # Ensure it's not on-site in another city (e.g. Lahore, Islamabad, Rawalpindi)
    other_cities = ["lahore", "islamabad", "rawalpindi", "peshawar", "faisalabad", "multan", "dubai", "uae"]
    if any(city in location_lower for city in other_cities) and "karachi" not in location_lower:
        logger.debug(f"[Filter] Rejected non-Karachi city on-site job: '{job.title}' @ {job.company} ({job.location})")
        return False, False

    # Check for Priority Karachi Hubs
    is_priority = any(hub in location_lower or hub in desc_lower for hub in PREFERRED_KARACHI_HUBS)
    
    return True, is_priority

def filter_jobs_for_faraz(jobs: List[Job], config: dict) -> List[Job]:
    """
    Strict filter for Faraz Hussain:
    - Rejects any job requiring >= 2 years experience.
    - Rejects Senior/Lead/Architect/Manager roles.
    - Rejects non-Karachi on-site roles.
    - Highlights preferred Karachi locations (Gulshan, Jauhar, Shahrah-e-Faisal, PECHS, NASTP, Nazimabad).
    - Ensures job matches Faraz's software engineering / web stack.
    """
    approved_jobs: List[Job] = []

    for job in jobs:
        title_lower = job.title.lower()
        desc_lower = job.description.lower()
        full_text = f"{job.title} {job.description}"

        # 1. Reject Senior / Lead titles
        if any(ex in title_lower for ex in EXCLUDED_TITLES):
            logger.debug(f"[Filter] Rejected senior title: '{job.title}' ({job.company})")
            continue

        # 2. Strict Experience Check (Reject >= 2 years requirement)
        req_years = parse_required_experience_years(full_text)
        if any(y >= 2 for y in req_years):
            # Exception check: if text explicitly says "0-2 years" or "fresh to 2 years", allow if min is 0/1
            if not ("0-2" in full_text or "fresh" in full_text or "0 to 2" in full_text or "intern" in title_lower):
                logger.debug(f"[Filter] Rejected high experience job (requires {max(req_years)} yrs): '{job.title}' ({job.company})")
                continue

        # 3. Location Check (On-site MUST be Karachi, prioritize preferred hubs)
        is_loc_valid, is_priority = is_location_valid_for_faraz(job)
        if not is_loc_valid:
            continue
        
        job.is_priority_location = is_priority

        # 4. Check for Irrelevant Domains (Cyber Security, DevOps, Hardware, Salesforce, etc.)
        if any(domain in title_lower for domain in IRRELEVANT_DOMAINS):
            logger.debug(f"[Filter] Rejected irrelevant domain title: '{job.title}' ({job.company})")
            continue

        # 5. Tech Stack Matching (Must align with Faraz's profile: Python, JS/TS, React, Next, Node, Web)
        skill_matches = [skill for skill in FARAZ_SKILLS if skill in full_text.lower()]
        if not skill_matches:
            logger.debug(f"[Filter] Rejected non-tech stack role: '{job.title}' ({job.company})")
            continue

        approved_jobs.append(job)

    logger.info(f"[ResumeFilter] Filtered {len(jobs)} scraped jobs -> {len(approved_jobs)} relevant positions for Faraz Hussain.")
    return approved_jobs
