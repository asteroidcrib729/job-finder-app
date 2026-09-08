# Job Finder App

A Python job-discovery pipeline for Faraz Hussain's graduate/junior software profile. GitHub Actions runs searches every three hours, checks qualifications and location, ranks matches, and sends Discord alerts. JSON files in the repository retain delivery and discovery state.

## Matching behavior

The [candidate profile](candidate-profile.yaml) records Next.js/React/TypeScript/Node and Python/Django/Flask internship evidence separately from listed skills. Update it when your experience changes; the PDF remains local and ignored.

- **Qualified:** compatible role, experience and location, adequate description/date evidence, and sufficient fit.
- **Review:** plausible but incomplete or a stretch: unknown remote eligibility/pay, one-year requirements, incomplete descriptions, or recruiter announcements.
- **Rejected:** explicit incompatibility, such as a senior role, unsupported mandatory stack, non-Karachi local work, restricted-country remote work, or stale/closed listing.

Scores order candidates; they are not probabilities. Every decision includes reasons and gaps. The default sends qualified matches only. Review candidates remain visible in run reports. Setting **notifications.send_review: true** also sends review digests of up to five candidates, subject to the same candidate cap. Set **notifications.review_digest: false** for individual review cards.

Local Karachi and remote searches are independent. Remote does not establish Pakistan eligibility or USD pay. The default **prefer_usd** policy puts remote jobs with unknown/non-USD pay into review; Karachi jobs have no USD requirement. A disclosed salary currency is not verification of contractual payment arrangements.

## Sources

| Source | Implementation |
| --- | --- |
| LinkedIn / Indeed / Google | JobSpy with source-specific parameters and isolated query timeouts. LinkedIn descriptions are requested. Indeed remote queries omit the incompatible date parameter; age is checked locally. |
| Rozee.pk | Public embedded JSON, with structured-data/card fallbacks. Karachi city ID 1184 was verified on 2026-09-07. Actual location, creation date, description, and experience are extracted. Loading placeholders are not jobs. Bounded pagination follows source offsets. |
| LinkedIn recruiter posts | Configurable DDGS discovery and accessible post content. Explicit role sections become separate review leads with original-post provenance. Queries have saved cadence and bounded detail caches. |
| Remotive / We Work Remotely | Optional public-feed adapters, disabled by default for separate evaluation. Remotive cadence is at least six hours. |

Sources can block requests or change formats. Blocked, timed-out, partial, and parse-failed queries are distinguished from valid empty searches. Rozee captured-page parsing succeeded during development, but later application dry runs received HTTP 403. Continuous source availability is not guaranteed.

Remotive's public feed has a 24-hour delay and recommends at most four fetches daily. Preserve source attribution and original listing links for both remote feeds. [Remotive API](https://github.com/remotive-com/remote-jobs-api), [WWR RSS](https://weworkremotely.com/remote-job-rss-feed).

## Installation and tests

Use Python 3.11 to match Actions; local tests also ran on Python 3.12.

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pip check
python -m unittest discover -s tests -v
~~~

The lock file pins direct and transitive dependencies. The package set resolved for Python 3.11/Linux; local test execution used Python 3.12/Windows. CI performs the actual Linux tests. Update pins deliberately and validate adapter fixtures.

## Offline evaluation and live dry runs

These commands send no Discord messages and do not save delivery/discovery state:

~~~powershell
# Fixed-date synthetic regression benchmark.
python -m evaluation tests/fixtures/matching.json

# Evaluate saved job evidence using the current date/profile.
python main.py --replay output/latest/run.json --report-dir output/replay

# Live source requests and an evaluation report.
python main.py --dry-run
~~~

Replay makes no job-board requests. Dry run does make requests, respecting configured budgets. Both can write reports. Use **--state** and **--discovery-state** for isolated evaluation paths; missing state files are not created by dry-run/replay.

Outputs:

- **output/latest/run.json:** normalized job evidence, decisions, source health, versions, counts, query yield/budgets, and delivery outcomes.
- **output/latest/summary.md:** concise run summary.
- **output/benchmark.json:** benchmark decisions and metrics.

Reports redact emails and webhook-shaped URLs, retain job descriptions/listing URLs, and are ignored by Git. Actions uploads run reports for 14 days. Inspect them before sharing externally.

The synthetic benchmark has 54 cases. Passing them is regression evidence, not a production accuracy estimate. Real-job benchmarks use the same candidates/job/expected schema with qualified, review, and rejected labels. Keep held-out examples separate from tuning examples.

## Configuration

[config.yaml](config.yaml) defines defaults. **--config path/to/override.yaml** recursively merges overrides and validates them; lists replace entire lists. Unknown settings fail at startup.

| Setting | Purpose |
| --- | --- |
| search_keywords | Focused JobSpy role/technology queries. |
| search_tracks | Karachi, Pakistan-remote, and global-remote locations/countries/source lists. |
| jobspy.results_wanted / max_pages / max_queries / max_seconds / query_timeout | Retrieval depth, request count, total JobSpy time, and per-query wall-clock budget. |
| jobspy.hours_old | Discovery lookback; successful-query timestamps permit bounded recovery after gaps. |
| jobspy.linkedin_fetch_description | Qualification evidence; disabling this moves incomplete results into review. |
| jobspy.interval_hours / low_yield_interval_hours | Minimum query interval; successful queries with no qualified/review candidates use the longer interval. Defaults 3/12 hours. |
| local_scrapers | Enable flag, keywords, max_queries, max_pages (2), max_details, timeout, interval_hours (3), detail_cache_hours (6). |
| linkedin_posts | Enable flag, queries, web search_backends (brave/duckduckgo/yahoo), result/check budgets, timeout, interval_hours (6), detail_cache_hours (6). |
| remote_feeds | Remotive/WWR flags, cadence, result cap. |
| matching.max_age_hours / min_score | Publication-age and fit thresholds. Unknown dates go to review. |
| matching.allow_* | Hybrid, internship, contract, one-year stretch handling. |
| matching.remote_salary_policy | prefer_usd reviews other/unknown pay; require_usd rejects disclosed non-USD and reviews unknown; any removes the currency gate. |
| matching.preferred_neighborhoods | Optional small ordering preference after Karachi compatibility; empty by default. |
| notifications.max_per_run | Send cap; unsent eligible jobs remain pending. |
| notifications.send_review / review_digest | Opt-in review delivery; digest groups up to five candidates with shared acknowledgements. Never overrides a rejection. |
| state.retention_days / pending_days | Separate acknowledged-history retention and queued-candidate expiry. |

Rozee and recruiter detail caches hold at most 200 normalized entries per source in discovery state. Expired/future-dated entries are discarded; failures never fall back to stale content. Current Rozee listing facts override cached descriptions. Zero detail_cache_hours disables caching; zero interval_hours disables the base interval (JobSpy's low-yield interval is separate). Minimum intervals are checked on scheduled runs, so actual gaps may be longer.

Minimum salary and acceptable time zones still need user decisions. New canonical skill names require aliases in the matcher; validation prevents silently ineffective profile entries.

## Discord and delivery state

Set **DISCORD_WEBHOOK_URL** in repository Actions secrets. It is the only notification credential; Telegram is not implemented.

~~~powershell
# Explicitly sends one message.
python main.py --test-notify

# Normal discovery, delivery, and state persistence.
python main.py
~~~

Delivery records individual outcomes and requests Discord message confirmation. Server/rate-limit retries are bounded; network timeouts are uncertain because Discord may already have accepted a message.

**data/seen_jobs.json** migrates from the legacy hash/timestamp object on the first live save. Its versioned journal contains seen IDs/legacy aliases, pending payloads, and receipt timestamps/message IDs. Atomic replacement protects prior state from interrupted writes. Corrupt state stops dispatch; a successful message never marks a failed message seen.

Pending jobs are reevaluated later, including runs with no new scraped jobs. Permanent payload/authentication failures remain visible for repair rather than being blindly retried. Successful source timestamps are stored separately in **data/discovery_state.json**. Do not reset production state to evaluate matcher changes.

Exactly-once delivery is not guaranteed across an uncertain network outcome or a crash between Discord acceptance and remote state persistence. State pushes reconcile concurrent changes and retry three times. Persistent failure requires reconciling the retained recovery artifact before relying on the next run's history.

Each state save keeps its previous valid JSON in a sibling **.bak** file. Corruption stops dispatch and cannot overwrite that backup. Export a separate recovery candidate:

~~~powershell
python -m storage.recover --backup data/seen_jobs.json.bak --output output/recovered-delivery.json
python -m storage.recover --kind discovery --backup data/discovery_state.json.bak --output output/recovered-discovery.json
~~~

Compare delivery recovery candidates with later Discord receipts and Git history before replacing live state. A previous snapshot may lack recent successful acknowledgements; automatic fallback could duplicate alerts.

## Relevance feedback

Copy a job ID from a card or saved run report, then label it locally:

~~~powershell
python -m feedback label --job-id "ID_FROM_REPORT" --label relevant --note "Junior React role in Karachi"
python -m feedback export
python -m evaluation output/user-benchmark.json --output output/user-evaluation.json
~~~

Labels are **relevant**, **not_relevant**, or **uncertain**. Feedback defaults to ignored **output/feedback.json** and never changes delivery history. Exported cases retain capture time, so later evaluation does not turn historical relevance labels into age failures. Keep tuning and held-out feedback in separate files.

## GitHub Actions

The default-branch production workflow runs at minute 17 every three hours UTC and supports manual dispatch. It checks out current production state after acquiring a shared concurrency group, installs pinned packages, runs offline tests, executes discovery, commits valid state even after degraded execution, and uploads reports.

Feature-branch manual dispatch cannot send production alerts. A separate read-only CI workflow tests code pushes/pull requests without a Discord secret.

CLI exit codes remain **0** healthy/valid-empty/idle, **1** fatal configuration/state failure, and **2** degraded source or delivery outcome. Actions uses **workflow_runner.py** to distinguish partial coverage from operational failure: successful primary discovery with optional source problems produces a visible warning; total due primary discovery failure, notification failure, corruption, or failed state persistence still fails the run. A Google/recruiter probe cannot fail a cycle whose primary queries are intentionally not due. Zero qualified matches alone is not a failure. State commit/push failures are surfaced. The writer builds a state-only commit on the latest remote tree using a temporary index, preserving concurrent code changes. Acknowledgements override pending jobs; retention pruning and queue retirement are reconciled against the starting state. Normal fast-forward pushes retry branch races. Persistent failures retain state files/backups in a seven-day recovery artifact. There is no force push or working-tree rebase.

## Development records

- [Audit memory](development-plans/MEMORY.md)
- [Issue register](development-plans/ISSUES.md)
- [Solution plan](development-plans/SOLUTIONS.md)
- [Implementation and validation record](development-plans/IMPLEMENTATION.md)


For production diagnosis, use the manual workflow input **dry_run: true**. This runs the same discovery and health classification on GitHub without Discord messages or state commits. Source warnings remain in the Actions summary and run artifact; Google missing-cursor results are unverified rather than claimed as healthy empty. See [the initial production incident](development-plans/PRODUCTION-INCIDENT-2026-09-08.md).


For an explicitly requested Discord verification, dispatch with **dry_run: false** and **verification_sample: true**. This refreshes source searches within a bounded sample (at most 12 JobSpy queries/300 seconds), sends at most three jobs, and uses clearly labeled review candidates only when the sample contains no qualified jobs. It does not change scheduled-run defaults, resend acknowledged jobs, or override rejection rules. Successful notifications are journaled normally; review candidates outside the sample are not queued.
