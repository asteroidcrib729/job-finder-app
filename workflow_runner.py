"""Actions entry point: coverage warnings remain visible without false failure emails."""
import logging
import os
from pathlib import Path
from main import BASE_DIR, run_job_finder
from run_health import assess_run, workflow_exit_code
from storage.tracker import read_json, StateError


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for name in ("primp", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)
    dry_run = os.getenv("JOB_FINDER_DRY_RUN", "false").lower() == "true"
    if os.getenv("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as handle:
            handle.write(f"persist_state={'false' if dry_run else 'true'}\n")
    directory = BASE_DIR / "output" / "latest"
    code = run_job_finder(dry_run=dry_run, report_dir=directory)
    try:
        report = read_json(directory / "run.json", {})
        if not report.get("finished_at"):
            raise StateError("Finished run report is missing")
    except StateError:
        print("::error::Cannot verify the completed run report.")
        return 1
    outcome = assess_run(report)
    exit_code = workflow_exit_code(code, report)
    if exit_code:
        print("::error::Job pipeline requires attention: " + ", ".join(outcome["reasons"] or ["unexpected_exit"]))
    elif outcome["status"] == "warning":
        print("::warning::Discovery completed with reduced source coverage. Review source diagnostics in the run summary.")
    print(f"Application exit: {code}; Actions outcome: {outcome['status']}; "
          f"qualified: {report.get('counts', {}).get('qualified', 0)}; "
          f"delivered: {report.get('counts', {}).get('delivered', 0)}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
