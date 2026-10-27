"""Separate discovery coverage warnings from failures requiring an Actions alert."""


def assess_run(report):
    reasons = []
    if report.get("error") or report.get("health") == "failed":
        reasons.append("pipeline_error")
    counts = report.get("counts", {})
    if counts.get("delivery_failed_or_uncertain", 0) or any(
            outcome.get("status") != "delivered" for outcome in report.get("deliveries", [])):
        reasons.append("delivery_failed_or_uncertain")
    if counts.get("permanent_delivery_failures", 0):
        reasons.append("permanent_delivery_failure")
    # Recruiter announcements cannot establish that vacancy discovery worked,
    # or fail an otherwise idle cycle.
    primary = [source for source in report.get("sources", []) if not source.get("skipped")
               and source.get("source") not in {"LinkedIn Post", "fetch_linkedin_plain_posts"}]
    # Google Jobs is supplementary too: its probe can run while successful
    # LinkedIn/Indeed/Rozee searches are intentionally not due yet.
    queries = [query for source in primary
               for query in (source.get("queries") or [{"status": "unverified"}])
               if query.get("site") != "google"]
    usable = any(query.get("status") in {"success", "valid_empty"} or query.get("converted", 0) > 0
                 for query in queries)
    if queries and not usable:
        reasons.append("vacancy_discovery_unavailable")
    if reasons:
        return {"status": "failure", "reasons": reasons}
    if report.get("health") == "degraded":
        return {"status": "warning", "reasons": ["partial_discovery_coverage"]}
    return {"status": "success", "reasons": []}


def workflow_exit_code(pipeline_code, report):
    # Only coverage-only exit 2 can recover; fatal/unexpected exits still fail.
    if pipeline_code not in {0, 2}:
        return 1
    return int(assess_run(report)["status"] == "failure")
