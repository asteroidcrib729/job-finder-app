"""Per-query retrieval and qualification yield, without attributing duplicates twice."""
from collections import defaultdict
from filtering.resume_filter import evaluate_job


def query_metrics(sources, config):
    metrics = {}
    for source in sources:
        jobs_by_query = defaultdict(dict)
        for job in source:
            if not job.decision:
                evaluate_job(job, config)
            jobs_by_query[job.query_id][job.job_id] = job
        for outcome in source.report.queries:
            key = outcome.query_id
            # Rozee reports page offsets; watermarks belong to the query.
            if key.startswith("rozee:") and key.rsplit(":", 1)[-1].isdigit():
                key = key.rsplit(":", 1)[0]
            item = metrics.setdefault(key, {"source": source.report.source, "requests": 0,
                "raw": 0, "duration_seconds": 0, "unique": 0, "qualified": 0, "review": 0, "rejected": 0,
                "full_descriptions": 0})
            item["requests"] += 1
            item["raw"] += outcome.raw
            item["duration_seconds"] += outcome.duration_seconds
        for key, item in list(metrics.items()):
            if item["source"] != source.report.source:
                continue
            jobs = list(jobs_by_query.get(key, {}).values())
            item["unique"] = len(jobs)
            for tier in ("qualified", "review", "rejected"):
                item[tier] = sum(job.decision.get("tier") == tier for job in jobs)
            item["full_descriptions"] = sum(job.description_status == "full" for job in jobs)
            item["qualified_per_request"] = item["qualified"] / item["requests"] if item["requests"] else 0
            item["qualified_per_minute"] = (60 * item["qualified"] / item["duration_seconds"]
                                          if item["duration_seconds"] else None)
            if key in source.updates:
                source.updates[key].update({name: item[name] for name in
                    ("unique", "qualified", "review", "rejected", "full_descriptions")})
    return metrics
