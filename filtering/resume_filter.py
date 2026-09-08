"""Evidence-based matching. Scores are ranking aids, never probabilities."""
import re
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from scrapers.base import Job, normalized, parse_date

MATCHER_VERSION = "2.1"
ALIASES = {
    "javascript": [r"javascript", r"(?<!\.)js"],
    "typescript": [r"typescript"],
    "react": [r"react(?:\.?js)?"],
    "nextjs": [r"next\.?js"],
    "nodejs": [r"node(?:\.?js)?"],
    "python": [r"python"],
    "django": [r"django"],
    "flask": [r"flask"],
    "fastapi": [r"fastapi"],
    "tailwind": [r"tailwind(?:\s+css)?"],
    "csharp": [r"c#", r"c\s*sharp"],
    "java": [r"java"],
    "postgresql": [r"postgres(?:ql)?"],
    "mysql": [r"mysql"],
    "sqlserver": [r"(?:microsoft\s+)?sql\s+server"],
    "mongodb": [r"mongo(?:db)?"],
    "html": [r"html5?"],
    "css": [r"css3?"],
    "git": [r"git(?:hub)?"],
    "rest": [r"rest(?:ful)?"],
    "aws": [r"aws", r"amazon web services"],
    "azure": [r"azure"],
    # Recognize unmet requirements as well as candidate skills.
    "ruby": [r"ruby(?:\s+on\s+rails)?", r"rails"],
    "php": [r"php"],
    "laravel": [r"laravel"],
    "vue": [r"vue(?:\.?js)?"],
    "angular": [r"angular(?:js)?"],
    "go": [r"golang", r"go(?=\s+(?:developer|programming|language))"],
    "rust": [r"rust"],
    "cpp": [r"c\+\+"],
    "dotnet": [r"\.net", r"asp\.net"],
    "swift": [r"swift"],
    "kotlin": [r"kotlin"],
    "flutter": [r"flutter"],
    "sap": [r"sap"],
    "salesforce": [r"salesforce"],
    "express": [r"express(?:\.?js)?"],
    "scala": [r"scala"],
    "spring": [r"spring(?:\s+boot)?"],
    "elixir": [r"elixir"],
    "kubernetes": [r"kubernetes", r"k8s"],
}
PRIMARY_SKILLS = set(ALIASES) - {"html", "css", "git", "rest", "aws", "azure", "postgresql", "mysql", "sqlserver", "mongodb", "tailwind"}
SENIOR = re.compile(r"\b(?:senior|sr\.?|lead|principal|architect|manager|director|vp|head\s+of|staff\s+(?:software\s+)?engineer)\b|\b(?:engineer|developer)\s+(?:iii|iv)\b", re.I)
NON_SOFTWARE = re.compile(
    r"\b(?:civil|mechanical|electrical|network|hardware|embedded|devops|site reliability|telecom)\s+engineer\b"
    r"|\b(?:graphic|ui/ux)\s+designer\b|\b(?:accountant|receptionist|sales executive|data entry|content writer)\b", re.I)
ROLE_PATTERNS = {
    "frontend": r"\bfront[ -]?end\b",
    "backend": r"\bback[ -]?end\b",
    "fullstack": r"\bfull[ -]?stack\b",
    "python": r"\bpython\b",
    "software": r"\b(?:software|web|application)\s+(?:engineer|developer|development)\b|\bprogrammer\b",
}
YEAR_PATTERN = re.compile(r"(?P<min>\d+(?:\.\d+)?)\s*(?:(?:-|to)\s*(?P<max>\d+(?:\.\d+)?)\s*)?\+?\s*(?P<unit>years?|yrs?|months?)\b")
NUMBER_WORDS = dict(zip("zero one two three four five six seven eight nine ten eleven twelve".split(), range(13)))


def skills_in(text):
    text = normalized(text)
    return {name for name, aliases in ALIASES.items()
            if any(re.search(r"(?<![a-z0-9])(?:" + alias + r")(?![a-z0-9])", text) for alias in aliases)}


@dataclass
class ExperienceRequirement:
    minimum_months: float
    maximum_months: float | None
    preferred: bool
    evidence: str


def experience_requirements(text):
    text = text.lower().replace("\u2013", "-").replace("\u2014", "-")
    text = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda m: str(NUMBER_WORDS[m[0]]), text)
    result = []
    for sentence in re.split(r"(?<=[.;!?])\s+|[\n;,]", text):
        sentence = normalized(sentence)
        matches = list(YEAR_PATTERN.finditer(sentence))
        for index, match in enumerate(matches):
            previous_end = matches[index - 1].end() if index else 0
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(sentence)
            before = sentence[max(previous_end, match.start() - 65):match.start()]
            after = sentence[match.end():min(next_start, match.end() + 80)]
            if re.match(r"\s+(?:degree|bachelor|master|program|course|university|college)\b", after):
                continue
            if re.search(r"(?:company|business|founded|established|operating|serving|history|industry leader).{0,30}$", before) and not re.match(r"\s+(?:of\s+)?(?:experience|exp)\b", after):
                continue
            if not re.search(r"\b(?:experience|exp|requires?|required|minimum|at least)\b", before + " " + after):
                continue
            scale = 1 if match["unit"].startswith("month") else 12
            preferred = bool(re.search(r"\b(?:preferred|ideally|desirable|nice.to.have|a plus|bonus)\b", before + " " + after))
            result.append(ExperienceRequirement(float(match["min"]) * scale,
                          float(match["max"]) * scale if match["max"] else None,
                          preferred, sentence.strip()))
    return result


def parse_required_experience_years(text):
    """Compatibility helper: returns minima, never range upper bounds."""
    return [r.minimum_months / 12 for r in experience_requirements(text) if not r.preferred]


@dataclass
class MatchDecision:
    tier: str = "qualified"
    score: int = 0
    confidence: str = "high"
    reasons: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    matched_skills: list[str] = field(default_factory=list)
    experience: list[dict] = field(default_factory=list)
    eligibility: str = "unknown"
    salary_status: str = "unknown"
    profile_version: str = ""
    matcher_version: str = MATCHER_VERSION

    def reject(self, reason):
        self.tier = "rejected"
        self.reasons.append(reason)

    def review(self, reason):
        if self.tier != "rejected":
            self.tier = "review"
        self.confidence = "limited"
        if reason not in self.gaps:
            self.gaps.append(reason)


def location_eligibility(job):
    text = normalized(f"{job.title} {job.location} {job.candidate_locations} {job.description}")
    loc = normalized(job.location)
    if job.work_mode != "remote":
        if re.search(r"\bkarachi\b", loc):
            if re.search(r"\b(?:office in|based in|on[ -]?site in)\s+(?:lahore|islamabad|hyderabad)\b|\b(?:lahore|islamabad|hyderabad)\s+office\b", normalized(job.description)):
                return "unknown", "conflicting_office_location"
            return "allowed", "karachi_confirmed"
        # Only an explicit workplace phrase can establish city from a description.
        if not loc or loc in {"pakistan", "pk"}:
            if re.search(r"\b(?:office|on[ -]?site|based|location)\s*(?:is|in|at|:|-)*\s*karachi\b", normalized(job.description)):
                return "allowed", "karachi_confirmed"
            return "unknown", "local_city_unknown"
        return "excluded", "outside_karachi"
    # Negative country evidence takes precedence over positive broad labels.
    if re.search(r"\b(?:not|no|excluding|except)\s+(?:in\s+)?pakistan\b", text):
        return "excluded", "pakistan_excluded"
    restricted = (
        r"\b(?:us|usa|u\.s\.|united states|canada|uk|united kingdom|eu|europe|european union|australia|india|germany)[ -]only\b",
        r"\bonly\s+(?:in|within|from|for|open to)\s+(?:the\s+)?(?:us|usa|united states|canada|uk|eu|europe|india|germany)\b",
        r"\b(?:us|usa|united states|canadian|canada|uk|eu|european|german|australian)\s+(?:residents?|citizens?|work authorization)\s+(?:only|required)\b",
        r"\b(?:must|need to|required to)\s+(?:be\s+)?(?:based|reside|live|located|authorized to work)\s+in\s+(?:the\s+)?(?:us|usa|united states|canada|uk|united kingdom|eu|europe|germany|india|australia)\b",
    )
    if any(re.search(pattern, text) for pattern in restricted):
        return "excluded", "restricted_remote_country"
    candidates = normalized(job.candidate_locations)
    if candidates and not re.search(r"\b(?:pakistan|worldwide|anywhere|global|all countries)\b", candidates):
        if re.search(r"\b(?:us|usa|united states|canada|uk|united kingdom|europe|eu|germany|india|australia|latin america)\b", candidates):
            return "excluded", "restricted_remote_country"
        return "unknown", "remote_region_needs_review"
    if re.search(r"\b(?:worldwide|anywhere in the world|work from anywhere|all countries)\b", text):
        return "allowed", "worldwide_remote"
    if re.search(r"\bpakistan\b", candidates) or re.search(r"\b(?:karachi|pakistan)\b", loc):
        return "allowed", "pakistan_remote"
    if re.search(r"\b(?:open to|hiring in|candidates (?:in|from)|based in)\s+pakistan\b", text):
        return "allowed", "pakistan_remote"
    return "unknown", "remote_eligibility_unknown"


def mandatory_skill_groups(description):
    """Conservative explicit requirements; unknown technologies remain gaps."""
    groups = []
    for sentence in re.split(r"(?<=[.;!?])\s+|\n", description):
        text = normalized(sentence)
        if not re.search(r"\b(?:must|required|requires?|mandatory|essential|proficien(?:t|cy)|expertise)\b", text):
            continue
        if re.search(r"\b(?:preferred|nice.to.have|bonus|not required)\b", text):
            continue
        found = skills_in(text) & PRIMARY_SKILLS
        if not found:
            continue
        for clause in re.split(r"\band\b|,", text):
            clause_skills = skills_in(clause) & PRIMARY_SKILLS
            if re.search(r"\bor\b", clause):
                if clause_skills:
                    groups.append(clause_skills)
            else:
                groups.extend({skill} for skill in clause_skills)
    return groups


def evaluate_job(job: Job, config: dict, now=None) -> MatchDecision:
    if "profile" not in config:
        from config import load_config, deep_merge
        config = deep_merge(load_config(), config)
    profile, policy = config["profile"], config["matching"]
    now = now or datetime.now(timezone.utc)
    decision = MatchDecision(profile_version=profile["version"])
    title, full_text = normalized(job.title), normalized(job.title + " " + job.description)
    known = set(profile["demonstrated_skills"]) | set(profile["listed_skills"])
    matched = skills_in(full_text) & known
    decision.matched_skills = sorted(matched)

    if SENIOR.search(title) or SENIOR.search(job.job_level):
        decision.reject("senior_role")
    if NON_SOFTWARE.search(title):
        decision.reject("unrelated_occupation")
    families = {name for name, pattern in ROLE_PATTERNS.items() if re.search(pattern, title)}
    if re.search(r"\b(?:developer|engineer)\b", title) and skills_in(title) & PRIMARY_SKILLS:
        families.add("software")
    if not families.intersection(profile["role_families"]):
        if job.kind == "lead" and skills_in(full_text) & PRIMARY_SKILLS:
            decision.review("recruiter_role_unverified")
        else:
            decision.reject("software_role_not_established")
    if job.kind == "lead":
        decision.review("recruiter_lead")
    if not policy["allow_internships"] and re.search(r"\bintern(?:ship)?\b", title + " " + job.job_type):
        decision.reject("internships_disabled")
    if not policy["allow_contracts"] and re.search(r"\bcontract\b", title + " " + job.job_type):
        decision.reject("contracts_disabled")
    if not policy["allow_hybrid"] and job.work_mode == "hybrid":
        decision.reject("hybrid_disabled")
    candidate_degree = normalized(profile.get("education", {}).get("degree", ""))
    for sentence in re.split(r"(?<=[.;!?])\s+|\n", job.description):
        requirement = normalized(sentence)
        advanced = re.search(r"\b(?:master'?s?|ph\.?d\.?|doctorate)\b", requirement)
        mandatory = re.search(r"\b(?:required|must|mandatory|requires?)\b", requirement)
        if advanced and mandatory and not re.search(r"\bbachelor", requirement) and "bachelor" in candidate_degree:
            decision.reject("education_requirement_unmet")

    decision.eligibility, reason = location_eligibility(job)
    decision.reasons.append(reason)
    if decision.eligibility == "excluded":
        decision.reject("location_incompatible")
    elif decision.eligibility == "unknown":
        decision.review(reason)
    if job.evidence_warnings:
        for warning in job.evidence_warnings:
            if warning in {"cached_description", "cached_post"}:
                continue  # Fresh cache provenance does not imply contradictory evidence.
            decision.review(warning)

    requirements = experience_requirements(job.description + ". " + job.title)
    decision.experience = [asdict(r) for r in requirements]
    required = [r.minimum_months for r in requirements if not r.preferred]
    minimum = max(required, default=0)
    evidenced_months = profile.get("professional_months", 0)
    if minimum > evidenced_months:
        alternative = any(re.search(r"\b(?:degree|bachelor|master|equivalent)\b.*\bor\b|\bor\b.*\b(?:degree|bachelor|master|equivalent)\b", r.evidence) for r in requirements)
        if alternative:
            decision.review("experience_alternative_needs_review")
        elif minimum <= 12 and policy["allow_one_year_stretch"]:
            decision.review("experience_stretch")
        else:
            decision.reject("experience_minimum_unmet")
    if any(r.preferred and r.minimum_months > evidenced_months for r in requirements):
        decision.gaps.append("preferred_experience_unmet")
    # Explicitly unsupported alternative degree/experience paths are not guessed.
    if minimum and re.search(r"\b(?:or equivalent|in lieu of|instead of)\b", full_text):
        decision.gaps.append("experience_alternative_needs_review")

    groups = mandatory_skill_groups(job.description)
    missing = [sorted(group) for group in groups if not group.intersection(known)]
    if missing:
        decision.reject("mandatory_stack_unmet")
        decision.gaps.extend("requires:" + "/".join(group) for group in missing)
    primary = matched & PRIMARY_SKILLS
    if not primary:
        decision.review("primary_skill_evidence_missing")
    if job.description_status != "full":
        decision.review("description_incomplete")

    posted = parse_date(job.posted_at)
    expiry = parse_date(job.expires_at)
    if job.active_status == "closed" or (expiry and expiry < now):
        decision.reject("listing_closed")
    if posted and (now - posted).total_seconds() > policy["max_age_hours"] * 3600:
        decision.reject("listing_stale")
    elif posted and (posted - now).total_seconds() > 86400:
        decision.review("publication_date_in_future")
    elif not posted:
        decision.review("publication_date_unknown")
    if job.active_status in {"blocked", "unverified"}:
        decision.review("listing_unverified")

    currency = job.salary_currency if job.salary_source not in {"unknown", "inferred"} else ""
    if not currency:
        currencies = set(re.findall(r"\b(?:USD|PKR|CAD|AUD|EUR|GBP)\b", job.salary_text.upper()))
        currency = currencies.pop() if len(currencies) == 1 else ""
    decision.salary_status = "usd_disclosed" if currency == "USD" else "other_currency" if currency else "unknown"
    if job.work_mode == "remote" and policy["remote_salary_policy"] != "any":
        if decision.salary_status == "other_currency":
            if policy["remote_salary_policy"] == "require_usd":
                decision.reject("usd_required")
            else:
                decision.review("other_currency")
        elif decision.salary_status == "unknown":
            decision.review("remote_salary_unknown")

    # Transparent 100-point ordering; aliases and repeated words count once.
    role_score = 25 if families.intersection(profile["role_families"]) else 0
    if groups:
        skill_score = round(40 * sum(bool(g & known) for g in groups) / len(groups))
    else:
        skill_score = min(40, 20 * len(primary))
    experience_score = 25 if not minimum else 15 if minimum <= 12 else 0
    education_score = 10 if re.search(r"\b(?:graduate|bachelor|software engineering|computer science)\b", full_text) else 5
    decision.score = role_score + skill_score + experience_score + education_score
    if decision.score < policy["min_score"]:
        decision.review("low_fit_score")
    if matched:
        decision.reasons.append("skills:" + ",".join(sorted(matched)))
    job.is_priority_location = decision.eligibility == "allowed" and job.work_mode != "remote" and any(
        re.search(r"(?<!\w)" + re.escape(normalized(hub)) + r"(?!\w)", normalized(job.location + " " + job.description))
        for hub in policy["preferred_neighborhoods"])
    job.decision = asdict(decision)
    return decision


def rank_jobs(jobs):
    return sorted(jobs, key=lambda job: (
        {"qualified": 2, "review": 1, "rejected": 0}.get(job.decision.get("tier"), 0),
        job.decision.get("score", 0),
        job.decision.get("salary_status") == "usd_disclosed",
        job.is_priority_location,
        job.posted_at,
    ), reverse=True)


def filter_jobs_for_faraz(jobs, config):
    return rank_jobs([job for job in jobs if evaluate_job(job, config).tier == "qualified"])


def is_location_valid_for_faraz(job):
    return location_eligibility(job)[0] == "allowed", job.is_priority_location
