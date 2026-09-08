"""Offline benchmark evaluator. This never scrapes, notifies, or writes job state."""
import argparse
from collections import Counter
import json
from pathlib import Path
from config import load_config
from filtering.resume_filter import evaluate_job, rank_jobs
from scrapers.base import Job, parse_date
from storage.tracker import atomic_write_json


def evaluate_benchmark(path, config=None):
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    config = config or load_config()
    now = parse_date(payload.get("evaluated_at"))
    cases = payload["candidates"]
    results, confusion, predicted_jobs = [], Counter(), []
    for row in cases:
        job = Job.from_dict(row["job"])
        decision = evaluate_job(job, config, parse_date(row.get("evaluated_at")) or now)
        expected = row["expected"]
        if expected not in {"qualified", "review", "rejected"}:
            raise ValueError("Expected label must be qualified, review, or rejected")
        confusion[(expected, decision.tier)] += 1
        results.append({"id": row["id"], "expected": expected, "actual": decision.tier,
                        "score": decision.score, "reasons": decision.reasons, "gaps": decision.gaps})
        predicted_jobs.append((job, expected))
    predicted = sum(row["actual"] == "qualified" for row in results)
    relevant = sum(row["expected"] == "qualified" for row in results)
    correct = sum(row["actual"] == row["expected"] == "qualified" for row in results)
    top = rank_jobs([job for job, _ in predicted_jobs if job.decision["tier"] == "qualified"])[:10]
    labels = {job.job_id: expected for job, expected in predicted_jobs}
    return {
        "scope": payload.get("benchmark_type", "user_labeled"),
        "cases": len(results),
        "tier_agreement": sum(row["expected"] == row["actual"] for row in results),
        "qualified_precision": correct / predicted if predicted else None,
        "filter_recall": correct / relevant if relevant else None,
        "precision_at_10": sum(labels[job.job_id] == "qualified" for job in top) / len(top) if top else None,
        "discovery_recall": None,
        "discovery_recall_note": "Requires time-scoped known-positive source retrieval evidence.",
        "confusion": {expected + "->" + actual: count for (expected, actual), count in confusion.items()},
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark")
    parser.add_argument("--config")
    parser.add_argument("--output", default="output/benchmark.json")
    args = parser.parse_args()
    report = evaluate_benchmark(args.benchmark, load_config(args.config))
    atomic_write_json(args.output, report)
    print(f"{report['scope']}: {report['tier_agreement']}/{report['cases']} expected decisions; report: {args.output}")
    return 0 if report["tier_agreement"] == report["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
