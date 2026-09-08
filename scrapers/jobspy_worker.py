"""One isolated JobSpy query; parent enforces a wall-clock timeout."""
import io
import json
import logging
import sys
from contextlib import redirect_stdout


class HealthHandler(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.codes = []

    def emit(self, record):
        text = record.getMessage().lower()
        if any(word in text for word in ("429", "403", "blocked", "captcha")):
            self.codes.append("blocked")
        elif "timeout" in text or "timed out" in text:
            self.codes.append("timed_out")
        else:
            self.codes.append("upstream_warning")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        from jobspy import scrape_jobs
        args = json.load(sys.stdin)
        health = HealthHandler()
        for name in list(logging.Logger.manager.loggerDict):
            if name.startswith("JobSpy"):
                logger = logging.getLogger(name)
                logger.handlers = [health]
        with redirect_stdout(io.StringIO()):
            frame = scrape_jobs(**args)
        rows = json.loads(frame.to_json(orient="records", date_format="iso")) if frame is not None else []
        print(json.dumps({"rows": rows, "warnings": list(set(health.codes))}))
    except Exception as exc:
        print(json.dumps({"rows": [], "error": type(exc).__name__}))


if __name__ == "__main__":
    main()
