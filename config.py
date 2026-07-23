import os
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def load_config(config_path=None):
    if config_path is None:
        config_path = BASE_DIR / "config.yaml"
        
    config = {
        "search_keywords": ["Software Engineer", "Junior Software Engineer", "Associate Software Engineer"],
        "locations": ["Karachi, Pakistan", "Remote"],
        "jobspy": {
            "sites": ["linkedin", "indeed", "google", "bayt", "glassdoor"],
            "results_wanted": 25,
            "hours_old": 24,
            "country_indeed": "Pakistan",
        },
        "experience_levels": ["entry_level", "associate"],
        "local_scrapers": {"rozee_enabled": True},
        "notifications": {"discord_enabled": True, "telegram_enabled": True},
        "filtering": {
            "title_include_keywords": ["software", "developer", "engineer", "python", "backend", "fullstack", "frontend", "web", "associate", "junior", "fresh", "entry", "graduate"],
            "title_exclude_keywords": ["senior", "sr.", "sr ", "lead", "principal", "architect", "manager", "director", "head of", "vp"]
        }
    }
    
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                config.update(yaml_config)
                
    # Environment variables take precedence for secrets
    config["discord_webhook_url"] = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    config["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    config["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    
    return config
