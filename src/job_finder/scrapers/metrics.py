"""Per-query retrieval and qualification yield, without attributing duplicates twice."""
from collections import defaultdict

from job_finder.filtering.resume_filter import evaluate_job


def source_coverage(sources):
    """Separate discovery throughput, detail evidence and recovery probes."""
    coverage = []
    for source in sources:
        sites = sorted({q.site for q in source.report.queries if q.site}) if source.report.source == "JobSpy" else [""]
        for site in sites or [""]:
            queries = [q for q in source.report.queries if not site or q.site == site]
            jobs = {job.job_id: job for job in source if not site or job.platform.lower() == site}
            searches = [q for q in queries if q.phase == "search"]
            coverage.append({"source": source.report.source, "site": site,
                "search_requests": len(searches),
                "usable_searches": sum(q.status in {"success", "valid_empty"} or q.converted > 0 for q in searches),
                "detail_requests": sum(q.phase == "detail" for q in queries),
                "probe_requests": sum(q.phase == "probe" for q in queries),
                "backend_attempts": sum(q.phase == "discovery" for q in queries),
                "unique_jobs": len(jobs),
                "full_descriptions": sum(job.description_status == "full" for job in jobs.values())})
    return coverage


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
                "phase": outcome.phase, "backend": outcome.backend,
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
