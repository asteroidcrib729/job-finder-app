# Production failure analysis — 2026-09-08

## Observed failures

| Run | Trigger | Raw / unique jobs | Qualified / review | Result |
| --- | --- | --- | --- | --- |
| [34193004929](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34193004929) | Manual, d404142 | 608 / 348 | 0 / 21 | Application exit 2; workflow final step exit 1 |
| [34220455004](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34220455004) | Scheduled, 2781f83 | 478 / 237 | 0 / 21 | Application exit 2; workflow final step exit 1 |

Both runs installed dependencies, passed all 64 Linux/Python 3.11 tests, completed discovery, persisted discovery state and uploaded reports. Neither had a recorded application exception, Discord delivery failure or state-push failure. The last workflow step, previously named **Surface degraded discovery or state persistence failure**, caused the red run result. Deprecation warnings about Node actions were not the cause.

## Root causes

1. **Coverage degradation was conflated with operational failure.** Any source partial/failure made main return 2, and the workflow escalated every nonzero pipeline outcome to exit 1. This treated an optional search-provider problem as failure of the entire otherwise completed run.
2. **Google diagnostics were reduced to upstream_warning.** The same three Google queries returned zero rows in each run. Inspection of pinned JobSpy plus one bounded reproduction identified **initial cursor not found**, now classified as **google_jobs_cursor_missing**. This can mean unavailable/changed Google Jobs markup; with zero rows it is not proof of a valid empty search. The same warning with actual initial-page jobs can also mean a legitimate single page.
3. **Recruiter search used DDGS auto backends.** In the pinned version auto prioritizes Wikipedia/Grokipedia before web search engines. The manual run received a non-post hit and incorrectly counted normal URL filtering as an invalid scrape. The scheduled run produced DDGSException; provider logs included challenges/rate limiting. Exception details were too generic to diagnose from the summary.

No alerts were sent because neither run had a candidate in the qualified tier; review delivery is disabled by default. That is separate from the workflow failure. This correction does not loosen qualification or turn missing eligibility/pay into verified evidence.

## Corrections

- Added an operational outcome assessment and Actions entry point. Partial coverage stays visible as warning in the JSON/Markdown report and Actions annotation; CLI exit 2 remains available for diagnostics.
- Total due primary discovery failure still fails. Google/recruiter-only probes cannot fail an otherwise idle cycle. Failed/uncertain/permanent deliveries, fatal configuration/state errors and failed Git persistence remain fatal.
- Added site/track fields to JobSpy query outcomes, explicit Google cursor diagnostics and readable source failure reasons in the summary. Single-page Google results are retained without incorrectly pausing the source.
- Restricted recruiter discovery to configured web engines supported by pinned DDGS: Brave, DuckDuckGo and Yahoo by default. Non-post links are counted as ignored results, not conversion failures. Real provider failures remain visible and never advance successful watermarks.
- Added manual **dry_run** workflow input. It executes the same source and outcome handling without Discord or state commits, allowing validation on the actual runner.

Google Jobs extraction and third-party search availability are external constraints. These changes do not claim to restore an unavailable Google response or bypass provider blocking.

## Regression and validation

Sanitized source-health/count data from both actual artifacts is retained in **tests/fixtures/production_health.json**, without job descriptions, recruiter details or raw challenge URLs. The regression suite covers both incidents, total-outage/delivery/state failure preservation, the optional-only probe case, Google cursor warnings, rejected non-post hits, provider failures, summary explanations and dry-run state suppression.

Raw downloaded reports/logs remain in ignored **.cache/incidents/**. Production state is preserved. The published fix will be verified with Linux CI and a manual Actions dry run; results are recorded below once available.

Local validation: **73 tests passed**, **54/54 synthetic matching cases agreed**, workflow YAML parsed, and production data files were unchanged. A bounded Google reproduction returned zero rows with google_jobs_cursor_missing.
