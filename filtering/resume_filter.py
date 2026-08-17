import re
import logging
from typing import List, Tuple
from scrapers.base import Job

logger = logging.getLogger(__name__)

# Faraz Hussain's Core Tech Stack Skills
FARAZ_SKILLS = [
    "python", "javascript", "typescript", "react.js", "reactjs", "react developer",
    "node.js", "nodejs", "express", "django", "flask", "fastapi", "tailwind",
    "postgresql", "mysql", "sql server", "sql", "mongodb", "c#", "java",
    "rest", "api", "git", "web", "frontend", "backend", "fullstack", "full stack",
    "software engineer", "software developer", "html", "css"
]

# Required Software Engineering / Developer Title Tokens
ALLOWED_TITLE_TOKENS = [
    "software", "developer", "engineer", "frontend", "front-end", "backend", "back-end",
    "fullstack", "full stack", "full-stack", "web", "programmer", "coder", "intern",
    "trainee", "react", "python", "node", "javascript", "typescript", "django", "flask",
    "fastapi", "stack", "technology"
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
    "flutter", "android developer", "kotlin", "devops engineer",
    "cloud security", "cyber security", "network engineer", "telecom", "fpga",
    "autocad", "graphic designer", "ui/ux designer", "seo specialist", "content writer",
    "digital marketing", "marketing specialist", "sales", "business development", "accountant", "hr executive",
    "cad", "cam", "creo", "operator", "data entry", "accounts", "finance", "media", "textile", "receptionist"
]

# Excluded titles for Experienced / Senior / Lead positions
EXCLUDED_TITLES = [
    "senior", "sr.", "sr ", "lead", "principal", "architect", 
    "staff engineer", "manager", "director", "head of", "vp", "executive",
    "specialist iii", "level 3", "tier 3"
]

def parse_required_experience_years(text: str) -> List[int]:
    """Extracts required experience years from job title/description text."""
    if not text:
        return []
    
    text_lower = text.lower()
    years_found: List[int] = []

    patterns = [
        r'(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp|in)?\b',
        r'(?:experience|exp)\s*(?:of|:)?\s*(\d+)\s*\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)\b',
        r'(\d+)\s*\+\s*(?:years?|yrs?)\b',
        r'(\d+)\s*(?:years?|yrs?)\s*(?:plus|\+)\b',
        r'minimum\s*(?:of)?\s*(\d+)\s*\+?\s*(?:years?|yrs?)\b',
        r'at least\s*(\d+)\s*\+?\s*(?:years?|yrs?)\b',
        r'requires?\s*(\d+)\s*\+?\s*(?:years?|yrs?)\b',
        r'(\d+)\s*to\s*\d+\s*(?:years?|yrs?)\b'
    ]

    for pat in patterns:
        matches = re.findall(pat, text_lower)
        for m in matches:
            try:
                val = int(m)
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

    is_remote = job.is_remote or "remote" in location_lower or "remote" in title_lower or "work from home" in desc_lower

    if is_remote:
        return True, False

    # For On-Site / Hybrid positions: MUST be in Karachi
    if not ("karachi" in location_lower or "pk" in location_lower or "pakistan" in location_lower or "karāchi" in location_lower):
        logger.debug(f"[Filter] Rejected non-Karachi on-site job: '{job.title}' @ {job.company} ({job.location})")
        return False, False

    other_cities = ["lahore", "islamabad", "rawalpindi", "peshawar", "faisalabad", "multan", "dubai", "uae"]
    if any(city in location_lower for city in other_cities) and "karachi" not in location_lower:
        logger.debug(f"[Filter] Rejected non-Karachi city on-site job: '{job.title}' @ {job.company} ({job.location})")
        return False, False

    is_priority = any(hub in location_lower or hub in desc_lower for hub in PREFERRED_KARACHI_HUBS)
    return True, is_priority

def filter_jobs_for_faraz(jobs: List[Job], config: dict) -> List[Job]:
    """
    Intelligent balanced filter for Faraz Hussain:
    - Rejects any job requiring >= 2 years experience (unless explicitly permitting fresh/0-2 yrs).
    - Rejects Senior/Lead/Architect/Manager/Principal roles.
    - Rejects non-Karachi on-site roles.
    - Highlights preferred Karachi locations (Gulshan, Jauhar, Shahrah-e-Faisal, PECHS, NASTP, Nazimabad).
    - Accepts all tech roles matching Faraz's software/web development stack.
    """
    approved_jobs: List[Job] = []

    for job in jobs:
        title_lower = job.title.lower()
        full_text = f"{job.title} {job.description}".lower()

        # 1. Reject Senior / Lead / Principal / Manager titles
        if any(ex in title_lower for ex in EXCLUDED_TITLES):
            logger.debug(f"[Filter] Rejected senior title: '{job.title}' ({job.company})")
            continue

        # 2. Check for Irrelevant Domains
        if any(domain in title_lower for domain in IRRELEVANT_DOMAINS):
            logger.debug(f"[Filter] Rejected irrelevant domain title: '{job.title}' ({job.company})")
            continue

        # 3. Must have a Software/Tech title indicator
        has_tech_title = any(token in title_lower for token in ALLOWED_TITLE_TOKENS)
        if not has_tech_title:
            logger.debug(f"[Filter] Rejected non-software title: '{job.title}' ({job.company})")
            continue

        # 4. Strict Experience Check (Reject >= 2 years requirement)
        req_years = parse_required_experience_years(full_text)
        if any(y >= 2 for y in req_years):
            # Allow only if explicitly fresh-friendly (e.g. 0-2 years, fresh to 2 years, fresh graduate)
            is_fresh_friendly = any(phrase in full_text for phrase in [
                "0-2", "0 to 2", "fresh to 2", "fresh", "fresher", "graduate", "intern", "trainee", "entry level", "entry-level"
            ])
            if not is_fresh_friendly:
                logger.debug(f"[Filter] Rejected high experience job (requires {max(req_years)} yrs): '{job.title}' ({job.company})")
                continue

        # 5. Location Check (On-site MUST be Karachi, prioritize preferred hubs)
        is_loc_valid, is_priority = is_location_valid_for_faraz(job)
        if not is_loc_valid:
            continue
        
        job.is_priority_location = is_priority

        # 6. Tech Stack & Role Relevance Matching
        skill_matches = [skill for skill in FARAZ_SKILLS if skill in full_text]
        if not skill_matches:
            logger.debug(f"[Filter] Rejected non-tech stack role: '{job.title}' ({job.company})")
            continue

        approved_jobs.append(job)

    logger.info(f"[ResumeFilter] Filtered {len(jobs)} scraped jobs -> {len(approved_jobs)} qualified positions for Faraz Hussain.")
    return approved_jobs
