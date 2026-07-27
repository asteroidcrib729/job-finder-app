import os
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def load_config(config_path=None):
    if config_path is None:
        config_path = BASE_DIR / "config.yaml"
        
    config = {
        "search_keywords": ["Junior Software Engineer", "Associate Software Engineer", "Python Developer"],
        "locations": ["Karachi, Pakistan", "Remote"],
        "jobspy": {
            "sites": ["linkedin", "indeed", "google"],
            "results_wanted": 20,
            "hours_old": 72,
            "country_indeed": "Pakistan",
        },
        "experience_levels": ["entry_level", "associate"],
        "local_scrapers": {"rozee_enabled": True},
        "notifications": {"discord_enabled": True},
    }
    
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                config.update(yaml_config)
                
    # Environment variables take precedence for secrets
    config["discord_webhook_url"] = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    
    return config
