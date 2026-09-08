"""Validated configuration; secrets are never stored in YAML or run artifacts."""
import copy
import os
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent


def deep_merge(base, overrides):
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _mapping(value, path):
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping")
    return value


def _strings(value, path, nonempty=True):
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(v, str) or not v.strip() for v in value):
        raise ValueError(f"{path} must be a list of nonempty strings")


def validate_config(config):
    allowed_sections = {
        "jobspy": {"enabled", "sites", "results_wanted", "max_pages", "max_queries", "hours_old", "query_timeout", "max_seconds", "linkedin_fetch_description", "interval_hours", "low_yield_interval_hours"},
        "local_scrapers": {"rozee_enabled", "max_queries", "max_details", "timeout", "keywords", "max_pages", "interval_hours", "detail_cache_hours"},
        "linkedin_posts": {"enabled", "max_results", "max_checks", "timeout", "queries", "interval_hours", "detail_cache_hours", "search_backends"},
        "remote_feeds": {"remotive_enabled", "wwr_enabled", "interval_hours", "max_jobs"},
        "matching": {"max_age_hours", "min_score", "allow_hybrid", "allow_internships", "allow_contracts", "allow_one_year_stretch", "remote_salary_policy", "preferred_neighborhoods"},
        "notifications": {"discord_enabled", "send_review", "review_digest", "max_per_run", "max_attempts", "max_retry_wait"},
        "state": {"retention_days", "pending_days"},
    }
    unknown = set(config) - set(allowed_sections) - {"profile", "profile_path", "search_keywords", "search_tracks", "discord_webhook_url"}
    if unknown:
        raise ValueError("Unknown configuration fields: " + ", ".join(sorted(unknown)))
    for section in ("jobspy", "local_scrapers", "linkedin_posts", "remote_feeds", "matching", "notifications", "state", "profile"):
        _mapping(config.get(section), section)
    for section, allowed in allowed_sections.items():
        unknown = set(config[section]) - allowed
        if unknown:
            raise ValueError(f"Unknown {section} fields: " + ", ".join(sorted(unknown)))
    _strings(config.get("search_keywords"), "search_keywords")
    _strings(config["jobspy"].get("sites"), "jobspy.sites")
    if set(config["jobspy"]["sites"]) - {"linkedin", "indeed", "google"}:
        raise ValueError("jobspy.sites supports linkedin, indeed, google")
    for section, names in {
        "jobspy": ["enabled", "linkedin_fetch_description"],
        "local_scrapers": ["rozee_enabled"], "linkedin_posts": ["enabled"],
        "remote_feeds": ["remotive_enabled", "wwr_enabled"],
        "notifications": ["discord_enabled", "send_review", "review_digest"],
        "matching": ["allow_hybrid", "allow_internships", "allow_contracts", "allow_one_year_stretch"]
    }.items():
        for name in names:
            if not isinstance(config[section].get(name), bool):
                raise ValueError(f"{section}.{name} must be boolean")
    for section, limits in {
        "jobspy": {"results_wanted": (1, 100), "max_pages": (1, 4), "max_queries": (1, 200), "hours_old": (1, 720), "query_timeout": (5, 300), "max_seconds": (30, 1800), "interval_hours": (0, 168), "low_yield_interval_hours": (0, 168)},
        "local_scrapers": {"max_queries": (1, 20), "max_details": (0, 50), "timeout": (1, 60), "max_pages": (1, 4), "interval_hours": (0, 168), "detail_cache_hours": (0, 24)},
        "linkedin_posts": {"max_results": (1, 20), "max_checks": (0, 50), "timeout": (1, 60), "interval_hours": (0, 168), "detail_cache_hours": (0, 24)},
        "remote_feeds": {"interval_hours": (6, 168), "max_jobs": (1, 500)},
        "notifications": {"max_per_run": (1, 100), "max_attempts": (1, 5), "max_retry_wait": (1, 60)},
        "matching": {"max_age_hours": (1, 2160), "min_score": (0, 100)},
        "state": {"retention_days": (1, 365), "pending_days": (1, 90)}
    }.items():
        for name, (low, high) in limits.items():
            value = config[section].get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f"{section}.{name} must be between {low} and {high}")
            if name != "interval_hours" and not isinstance(value, int):
                raise ValueError(f"{section}.{name} must be an integer")
    tracks = config.get("search_tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("search_tracks must be a nonempty list")
    ids = set()
    for track in tracks:
        _mapping(track, "search_tracks item")
        if not isinstance(track.get("id"), str) or not track["id"] or track["id"] in ids:
            raise ValueError("search_tracks IDs must be unique nonempty strings")
        ids.add(track["id"])
        if not isinstance(track.get("remote"), bool):
            raise ValueError("search_tracks.remote must be boolean")
        _strings(track.get("sites"), "search_tracks.sites")
        if set(track["sites"]) - set(config["jobspy"]["sites"]):
            raise ValueError("search_tracks.sites must be enabled JobSpy sites")
        for key in ("location", "country_indeed"):
            if not isinstance(track.get(key), str):
                raise ValueError(f"search_tracks.{key} must be a string")
    profile = config["profile"]
    _mapping(profile.get("education"), "profile.education")
    for key in ("demonstrated_skills", "listed_skills", "role_families"):
        _strings(profile.get(key), f"profile.{key}")
    if not isinstance(profile.get("version"), str):
        raise ValueError("profile.version must be a string")
    for key in ("professional_months", "internship_months"):
        if type(profile.get(key)) is not int or profile[key] < 0:
            raise ValueError(f"profile.{key} must be a nonnegative integer")
    from filtering.resume_filter import ALIASES, ROLE_PATTERNS
    if (set(profile["demonstrated_skills"]) | set(profile["listed_skills"])) - set(ALIASES):
        raise ValueError("Profile skills must use canonical names from filtering.resume_filter.ALIASES")
    if set(profile["role_families"]) - set(ROLE_PATTERNS):
        raise ValueError("Unknown profile role family")
    if config["matching"].get("remote_salary_policy") not in {"prefer_usd", "require_usd", "any"}:
        raise ValueError("matching.remote_salary_policy must be prefer_usd, require_usd, or any")
    _strings(config["linkedin_posts"].get("queries"), "linkedin_posts.queries")
    _strings(config["linkedin_posts"].get("search_backends"), "linkedin_posts.search_backends")
    if set(config["linkedin_posts"]["search_backends"]) - {"brave", "duckduckgo", "yahoo", "mojeek", "startpage"}:
        raise ValueError("linkedin_posts.search_backends must name supported web search engines")
    _strings(config["local_scrapers"].get("keywords"), "local_scrapers.keywords")
    _strings(config["matching"].get("preferred_neighborhoods"), "matching.preferred_neighborhoods", False)
    return config


def load_config(config_path=None):
    default_path = BASE_DIR / "config.yaml"
    with default_path.open(encoding="utf-8") as handle:
        config = _mapping(yaml.safe_load(handle), "config")
    if config_path is not None and Path(config_path).resolve() != default_path:
        with Path(config_path).open(encoding="utf-8") as handle:
            config = deep_merge(config, _mapping(yaml.safe_load(handle), "config override"))
    configured_profile = config.get("profile_path", "candidate-profile.yaml")
    if not isinstance(configured_profile, str) or not configured_profile.strip():
        raise ValueError("profile_path must be a nonempty path string")
    profile_path = Path(configured_profile)
    if not profile_path.is_absolute():
        profile_path = BASE_DIR / profile_path
    with profile_path.open(encoding="utf-8") as handle:
        config["profile"] = deep_merge(_mapping(yaml.safe_load(handle), "profile"), config.get("profile", {}))
    config["discord_webhook_url"] = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    return validate_config(config)
