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
        self.record_message(record.getMessage(), error=record.levelno >= logging.ERROR)

    def record_message(self, message, error=False):
        text = str(message).lower()
        if "initial cursor not found" in text:
            self.codes.append("google_jobs_cursor_missing")
        elif any(word in text for word in ("429", "403", "blocked", "captcha")):
            self.codes.append("blocked")
        elif "timeout" in text or "timed out" in text:
            self.codes.append("timed_out")
        else:
            self.codes.append("upstream_error" if error else "upstream_warning")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        from jobspy import scrape_jobs
        args = json.load(sys.stdin)
        health = HealthHandler()
        # JobSpy 1.4 uses lowercase loggers and also reports errors in DataFrame attrs.
        logger = logging.getLogger("jobspy")
        previous_handlers, previous_level, previous_propagate = logger.handlers[:], logger.level, logger.propagate
        logger.handlers = [health]
        logger.propagate = False
        try:
            with redirect_stdout(io.StringIO()):
                frame = scrape_jobs(**args)
        finally:
            logger.handlers, logger.level, logger.propagate = previous_handlers, previous_level, previous_propagate
        if frame is not None:
            for message in frame.attrs.get("errors", {}).values():
                health.record_message(message, error=True)
            for messages in frame.attrs.get("warnings", {}).values():
                for message in messages:
                    health.record_message(message)
        rows = json.loads(frame.to_json(orient="records", date_format="iso")) if frame is not None else []
        print(json.dumps({"rows": rows, "warnings": sorted(set(health.codes))}))
    except Exception as exc:
        print(json.dumps({"rows": [], "error": type(exc).__name__}))


if __name__ == "__main__":
    main()
