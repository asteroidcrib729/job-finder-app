"""Compatibility entry point; the résumé matcher is the single active policy."""
from filtering.resume_filter import filter_jobs_for_faraz


def filter_fresh_grad_jobs(jobs, config):
    return filter_jobs_for_faraz(jobs, config)
