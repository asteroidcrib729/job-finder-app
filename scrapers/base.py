import hashlib
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    platform: str
    date_posted: Optional[str] = "Recently"
    is_remote: bool = False
    description: Optional[str] = ""
    job_id: Optional[str] = None

    def __post_init__(self):
        if not self.job_id:
            # Generate deterministic hash identifier
            raw_id = f"{self.platform.lower()}_{self.title.lower()}_{self.company.lower()}_{self.url.strip()}"
            self.job_id = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16]

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "platform": self.platform,
            "date_posted": self.date_posted,
            "is_remote": self.is_remote,
            "description": self.description[:200] if self.description else ""
        }
