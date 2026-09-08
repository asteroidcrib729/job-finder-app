"""Record relevance labels from a saved run; export an offline benchmark."""
import argparse
from pathlib import Path
from main import sanitize
from scrapers.base import Job, utc_now
from storage.tracker import StateError, atomic_write_json, read_json

LABELS = {"relevant": "qualified", "not_relevant": "rejected", "uncertain": "review"}


def record_feedback(report_path, job_id, label, note="", output="output/feedback.json"):
    if label not in LABELS:
        raise ValueError("Unknown relevance label")
    report = read_json(report_path, {})
    item = next((item for item in report.get("jobs", []) if item.get("job_id") == job_id), None)
    if item is None:
        raise ValueError("Job ID is absent from the saved run")
    item = Job.from_dict(item).to_dict()
    state = read_json(output, {"version": 1, "labels": {}})
    if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("labels"), dict):
        raise StateError("Invalid feedback file; existing labels retained")
    state["labels"][job_id] = sanitize({"label": label, "note": note, "job": item,
        "captured_at": report.get("started_at", ""), "labeled_at": utc_now(),
        "profile_version": report.get("profile_version", ""), "matcher_version": report.get("matcher_version", "")})
    atomic_write_json(output, state)
    return state


def export_benchmark(feedback_path, output):
    state = read_json(feedback_path, {})
    if state.get("version") != 1 or not isinstance(state.get("labels"), dict):
        raise StateError("Invalid feedback file")
    candidates = []
    for job_id, row in state["labels"].items():
        if row.get("label") not in LABELS:
            raise StateError("Invalid feedback label")
        candidates.append({"id": job_id, "job": Job.from_dict(row["job"]).to_dict(),
            "expected": LABELS[row["label"]], "evaluated_at": row.get("captured_at"),
            "review_note": row.get("note", "")})
    atomic_write_json(output, {"benchmark_type": "user_labeled", "candidates": candidates})
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    label = commands.add_parser("label")
    label.add_argument("--report", default="output/latest/run.json")
    label.add_argument("--job-id", required=True)
    label.add_argument("--label", choices=LABELS, required=True)
    label.add_argument("--note", default="")
    label.add_argument("--output", default="output/feedback.json")
    export = commands.add_parser("export")
    export.add_argument("--feedback", default="output/feedback.json")
    export.add_argument("--output", default="output/user-benchmark.json")
    args = parser.parse_args()
    try:
        if args.command == "label":
            record_feedback(args.report, args.job_id, args.label, args.note, args.output)
            print("Saved relevance feedback for " + args.job_id)
        else:
            rows = export_benchmark(args.feedback, args.output)
            print(f"Exported {len(rows)} labeled cases. Keep held-out examples separate from tuning.")
    except (ValueError, StateError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
