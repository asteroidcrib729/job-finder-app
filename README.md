# Job Finder App

I built Job Finder App to find opportunities that fit my graduate/junior software background. I focus on on-site and hybrid roles in Karachi and remote roles that accept applicants in Pakistan, with a preference for USD pay. I use GitHub Actions to search every three hours, evaluate qualifications and location, rank candidates, and send results to my Discord server. I retain delivery and discovery history in repository JSON files.

## How I evaluate matches

I keep my Next.js/React/TypeScript/Node and Python/Django/Flask internship evidence separate from listed skills in my [candidate profile](config/profiles/candidate-profile.yaml). I update that profile as my experience changes and keep my resume PDF local and Git-ignored. I classify each result into one of three tiers:

- **Qualified:** compatible role, experience and location, adequate description/date evidence, and sufficient fit.
- **Review:** plausible but incomplete or a stretch: unknown remote eligibility/pay, one-year requirements, incomplete descriptions, or recruiter announcements.
- **Rejected:** explicit incompatibility, such as a senior role, unsupported mandatory stack, non-Karachi local work, restricted-country remote work, or stale/closed listing.

I use scores to order candidates, not to estimate hiring probabilities. I include reasons and gaps with every decision. On September 9, 2026, I enabled both qualified matches and labeled review candidates for scheduled and ordinary manual runs (**notifications.send_review: true**). Review digests contain up to five candidates per message, under the shared limit of 20 jobs per run. Qualified jobs rank first; deferred candidates remain queued and are reevaluated before delivery. I can switch to qualified-only alerts with **notifications.send_review: false**, or individual review cards with **notifications.review_digest: false**.

I search for local Karachi and remote roles independently. Remote does not establish Pakistan eligibility or USD pay. The default **prefer_usd** policy puts remote jobs with unknown/non-USD pay into review; Karachi jobs have no USD requirement. A disclosed salary currency is not verification of contractual payment arrangements.

## Sources I search

| Source | Implementation |
| --- | --- |
| LinkedIn / Indeed / Google | JobSpy with source-specific parameters and isolated query timeouts. LinkedIn listing searches run without inline detail requests. I enrich cards afterward through a paced, cached queue, shared across search tracks. Google runs as one daily recovery probe because its upstream adapter is currently unavailable. Indeed remote queries omit the incompatible date parameter; age is checked locally. |
| Rozee.pk | Public embedded JSON, with structured-data/card fallbacks. Karachi city ID 1184 was verified on 2026-09-07. Actual location, creation date, description, and experience are extracted. Loading placeholders are not jobs. Bounded pagination follows source offsets. |
| LinkedIn recruiter posts | Bounded DDGS backend fallback, simpler query fallback, separate provider outcomes and accessible post content. Explicit role sections become separate review leads with original-post provenance. Queries have saved cadence and bounded detail caches. |
| Remotive / We Work Remotely | Enabled public-feed adapters, validated with live responses. Both have a six-hour minimum between attempts, including failed attempts. |

I track blocked, timed-out, partial, and parse-failed queries separately from valid empty searches because providers can block requests or change formats. Rozee captured-page parsing and later live pagination succeeded; earlier runs also received HTTP 403. Continuous source availability is not guaranteed. I separate listing searches, description requests, recovery probes and backend attempts in reports; unavailable descriptions keep incomplete jobs in review.

Remotive's public feed has a 24-hour delay and recommends at most four fetches daily. I preserve source attribution and original listing links for both remote feeds. [Remotive API](https://github.com/remotive-com/remote-jobs-api), [WWR RSS](https://weworkremotely.com/remote-job-rss-feed).

## Installation and tests

I manage the project with [Astral uv](https://docs.astral.sh/uv/getting-started/installation/) **0.12.9**. After installing it, I run these commands from the repository root. Python **3.14.7** is required by both `.python-version` and `pyproject.toml`. uv creates the dedicated, ignored `.venv`; activation and globally installed Python packages are unnecessary.

~~~powershell
uv python install
uv sync --locked
uv pip check
uv run --locked ruff check src tests
uv run --locked python -m compileall -q src tests
uv run --locked python -m unittest discover -s tests -v
uv run --locked pyrefly check
~~~

`pyproject.toml` declares runtime dependencies and a separate development group; `uv.lock` records the exact resolution and package hashes. The application is an installed `job_finder` package in `src/job_finder`, built with `uv_build`. `uv sync` installs it in editable mode; configuration and profiles live in `config/`, while mutable production state stays in `data/`. `uv sync --locked --no-dev` installs runtime packages only. CI uses the same Python pin and rejects stale lockfiles. The old requirements files are superseded by these uv files.

I add and remove dependencies with `uv add PACKAGE`, `uv add --dev PACKAGE`, and `uv remove PACKAGE`. For a targeted update within existing constraints, I use `uv lock --upgrade-package PACKAGE`, followed by `uv sync --locked` and the checks above. I change an exact pin with `uv add PACKAGE==NEW_VERSION` and commit the manifest and lockfile together. My maintenance and commit conventions are documented in [CONTRIBUTING.md](CONTRIBUTING.md). When another tool needs requirements format, I export it with `uv export --locked --no-dev --format requirements-txt --output-file .local/output/requirements.txt` instead of maintaining a second lockfile.

For Python 3.14 compatibility, I upgraded JobSpy to 1.4.1 and pandas/NumPy to compatible releases. The adapter uses JobSpy's current `fetch_description` option and captures both lowercase loggers and structured DataFrame error metadata. A successful install is not proof that a live job board is available; fixture/API tests and run health remain separate checks.

## Source layout and editor setup

I keep uv, Ruff and `[tool.pyrefly]` configuration together in `pyproject.toml`. A separate `pyrefly.toml` is unnecessary. I keep personal files and generated material in Git-ignored `.local/`, including `Resume - Faraz Hussain.pdf`, `cache/`, `ruff-cache/`, `output/` and `dist/`. I build fresh distributions with `uv build --no-cache --out-dir .local/dist`. The root `.venv` remains the standard uv/IDE environment, and Python's ignored bytecode stays next to source/test modules. The obsolete root bytecode was archived in `.local/legacy-root-pycache`; the empty `scratch` directory was removed.

```text
config/
  config.yaml                  Operational defaults
  profiles/candidate-profile.yaml
src/job_finder/                 Importable Python package
  __init__.py, __main__.py      Package entry files
  application/                 Pipeline and run health
  configuration/               Settings loading and shared paths
  automation/                  Workflow runner and failure signaling
  diagnostics/                 Discord and search diagnostics
  evaluation/                  Benchmark and relevance feedback
  filtering/                   Matching and ranking
  scrapers/                    Source adapters and discovery
  notifiers/                   Discord delivery
  storage/                     State, recovery and Git reconciliation
tests/                         Offline regressions and fixtures
data/                          Persistent delivery and discovery state
.github/                       CI, security scans and Dependabot
.vscode/                       Interpreter, editor, tests and debugging
.local/                        Ignored personal files and generated output
development-plans/             Audit and validation records
```

For development, I open the repository folder in VS Code, run `uv sync --locked`, and install the recommended Python, Pyrefly and Ruff extensions. The workspace points Python at `.venv`, and both analysis tools use that environment. If VS Code remembers another interpreter, I use **Python: Select Interpreter** to choose `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` elsewhere; a saved selection takes precedence over the default. **Tasks: Run Build Task** runs lint, type/syntax analysis, compilation and offline tests. Test Explorer uses unittest. The debug configuration performs a live scrape with `--dry-run`.

I retain the underscore in `src/job_finder` for valid Python imports. I organize application imports under `job_finder.*` and start the app with `uv run --locked python -m job_finder` or `uv run --locked job-finder`. These replace the former root `main.py` command. Workers, workflow and recovery tools also use the package namespace. Editable installs resolve configuration and state relative to the checkout even when launched from another directory. `JOB_FINDER_HOME` can select an explicit configuration/data root. A standalone wheel requires that root to contain `config/config.yaml` and its referenced profile; these personal configuration files and delivery state are deliberately not bundled. CLI file arguments remain relative to the caller's working directory.

I use Ruff to check import order, unused/undefined names and selected Python errors. I use Pyrefly for types and parsing across `src` and `tests`; `compileall` additionally validates syntax with the actual Python 3.14.7 interpreter. Existing targeted Pyrefly suppressions are retained, so a clean result does not imply complete static type coverage.

## Offline evaluation and live dry runs

I use these commands to evaluate results without sending Discord messages or saving delivery/discovery state:

~~~powershell
# Fixed-date synthetic regression benchmark.
uv run --locked python -m job_finder.evaluation.benchmark tests/fixtures/matching.json

# Evaluate saved job evidence using the current date/profile.
uv run --locked python -m job_finder --replay .local/output/latest/run.json --report-dir .local/output/replay

# Live source requests and an evaluation report.
uv run --locked python -m job_finder --dry-run
~~~

Replay makes no job-board requests. Dry run does make requests, respecting configured budgets. Both can write reports. I use **--state** and **--discovery-state** for isolated evaluation paths; missing state files are not created by dry-run/replay.

Outputs:

- **.local/output/latest/run.json:** normalized job evidence, decisions, source health, versions, counts, query yield/budgets, and delivery outcomes.
- **.local/output/latest/summary.md:** concise run summary.
- **.local/output/benchmark.json:** benchmark decisions and metrics.

Reports redact emails and webhook-shaped URLs, retain job descriptions/listing URLs, and are ignored by Git. Actions uploads run reports for 14 days. I inspect reports before sharing them externally.

I maintain a 54-case synthetic benchmark. Passing it gives me regression evidence, not an estimate of production accuracy. Real-job benchmarks use the same candidates/job/expected schema with qualified, review, and rejected labels. I keep held-out examples separate from tuning examples.

## Configuration

I define operational defaults in [config/config.yaml](config/config.yaml). I set `profile_path: profiles/candidate-profile.yaml`, resolved relative to the configuration directory (`JOB_FINDER_HOME/config` when overridden). Absolute profile paths are also supported. This rule also applies to profile paths supplied by an override file. **--config path/to/override.yaml** recursively merges overrides and validates them; lists replace entire lists. Unknown settings fail at startup.

| Setting | Purpose |
| --- | --- |
| search_keywords | Focused JobSpy role/technology queries. |
| search_tracks | Karachi, Pakistan-remote, and global-remote locations/countries/source lists. |
| jobspy.results_wanted / max_pages / max_queries / max_seconds / query_timeout | Retrieval depth, request count, total JobSpy time, and per-query wall-clock budget. |
| jobspy.hours_old | Discovery lookback; successful-query timestamps permit bounded recovery after gaps. |
| jobspy.linkedin_fetch_description | Enable the separate LinkedIn description queue; searches always collect cards first. |
| jobspy.linkedin_max_details / linkedin_detail_timeout / linkedin_detail_delay / linkedin_detail_max_seconds | Detail request cap (12), timeout (8 seconds), pacing (2 seconds), and queue time budget (90 seconds). Tracks share the queue. |
| jobspy.linkedin_detail_cache_hours / linkedin_detail_retry_hours | Fresh parsed descriptions cache for 6 hours; blocked/repeatedly failing detail service cools down for 3 hours. Listing searches continue. |
| jobspy.google_mode / google_probe_interval_hours | probe (default), disabled or enabled. Probe mode attempts one query at most every 24 hours after normal searches, within the remaining search budget. |
| jobspy.interval_hours / low_yield_interval_hours | Minimum query interval; successful queries with no qualified/review candidates use the longer interval. Defaults 3/12 hours. |
| local_scrapers | Enable flag, keywords, max_queries, max_pages (2), max_details, timeout, interval_hours (3), detail_cache_hours (6). |
| linkedin_posts | Backend-specific outcomes and fallback (brave/duckduckgo/yahoo), at most 6 backend attempts per run, 3-hour provider-error cooldowns, result/detail budgets, timeout, interval_hours (6), detail_cache_hours (6). Simplified fallback omits the search-engine date filter; listing dates still pass local freshness checks. |
| remote_feeds | Enabled Remotive/WWR adapters, six-hour attempt cadence and result cap (100 per feed). |
| matching.max_age_hours / min_score | Publication-age and fit thresholds. Unknown dates go to review. |
| matching.allow_* | Hybrid, internship, contract, one-year stretch handling. |
| matching.remote_salary_policy | prefer_usd reviews other/unknown pay; require_usd rejects disclosed non-USD and reviews unknown; any removes the currency gate. |
| matching.preferred_neighborhoods | Optional small ordering preference after Karachi compatibility; empty by default. |
| notifications.max_per_run | Send cap; unsent eligible jobs remain pending. |
| notifications.send_review / review_digest | Review delivery is enabled; digest groups up to five candidates with shared acknowledgements. Never overrides a rejection. |
| state.retention_days / pending_days | Separate acknowledged-history retention and queued-candidate expiry. |

LinkedIn, Rozee and recruiter detail caches hold at most 200 normalized entries per source in discovery state. Expired/future-dated entries are discarded; failures never fall back to stale content. Current Rozee listing facts override cached descriptions. Zero detail_cache_hours disables caching; zero interval_hours disables the base interval (JobSpy's low-yield interval is separate). Minimum intervals are checked on scheduled runs, so actual gaps may be longer.

I have not yet settled a minimum salary or acceptable time-zone range. New canonical skill names require aliases in the matcher; validation prevents silently ineffective profile entries.

## Discord and delivery state

I store **DISCORD_WEBHOOK_URL** in repository Actions secrets. It is my only notification credential; the app does not implement Telegram delivery. I use the following commands for an explicit test message or a normal live run:

~~~powershell
# Explicitly sends one message.
uv run --locked python -m job_finder --test-notify

# Normal discovery, delivery, and state persistence.
uv run --locked python -m job_finder
~~~

Delivery records individual outcomes and requests Discord message confirmation. Server/rate-limit retries are bounded; network timeouts are uncertain because Discord may already have accepted a message.

**data/seen_jobs.json** migrates from the legacy hash/timestamp object on the first live save. Its versioned journal contains seen IDs/legacy aliases, pending payloads, and receipt timestamps/message IDs. Atomic replacement protects prior state from interrupted writes. Corrupt state stops dispatch; a successful message never marks a failed message seen.

Pending jobs are reevaluated later, including runs with no new scraped jobs. Permanent payload/authentication failures remain visible for repair rather than being blindly retried. Successful source timestamps, retry/probe attempts and bounded detail caches are stored separately in **data/discovery_state.json**. Failed attempts never masquerade as successful searches. I preserve production history when evaluating matcher changes.

Exactly-once delivery is not guaranteed across an uncertain network outcome or a crash between Discord acceptance and remote state persistence. State pushes reconcile concurrent changes and retry three times. Persistent failure requires reconciling the retained recovery artifact before relying on the next run's history.

Each state save keeps its previous valid JSON in a sibling **.bak** file. Corruption stops dispatch and cannot overwrite that backup. I export a separate recovery candidate with:

~~~powershell
uv run --locked python -m job_finder.storage.recover --backup data/seen_jobs.json.bak --output .local/output/recovered-delivery.json
uv run --locked python -m job_finder.storage.recover --kind discovery --backup data/discovery_state.json.bak --output .local/output/recovered-discovery.json
~~~

I compare recovery candidates with later Discord receipts and Git history before replacing live state. A previous snapshot may lack recent successful acknowledgements; automatic fallback could duplicate alerts.

## Relevance feedback

I copy a job ID from a card or saved report and record my relevance judgment locally:

~~~powershell
uv run --locked python -m job_finder.evaluation.feedback label --job-id "ID_FROM_REPORT" --label relevant --note "Junior React role in Karachi"
uv run --locked python -m job_finder.evaluation.feedback export
uv run --locked python -m job_finder.evaluation.benchmark .local/output/user-benchmark.json --output .local/output/user-evaluation.json
~~~

Labels are **relevant**, **not_relevant**, or **uncertain**. Feedback defaults to ignored **.local/output/feedback.json** and never changes delivery history. Exported cases retain capture time, so later evaluation does not turn historical relevance labels into age failures. I keep tuning and held-out feedback in separate files.

## GitHub Actions

I keep my workflows focused on orchestration: each `run` step invokes a command-line tool or dedicated script, with custom Python and shell logic kept outside YAML. The read-only Discord check is `src/job_finder/diagnostics/discord.py`; production failure signaling is `job_finder.automation.failure`. Offline regressions cover the diagnostic's safe output, GET-only requests and failure cases, and enforce the workflow rule. Artifact uploads target only `.local/output/latest`, with hidden-path inclusion explicitly enabled; they never upload the résumé or cache directories.

I schedule the default-branch production workflow at minute 17 every three hours UTC and also support manual dispatch. It checks out current production state after acquiring a shared concurrency group, installs pinned packages, runs offline tests, executes discovery, commits valid state even after degraded execution, and uploads reports.

I attribute automated state commits to **myself, Faraz Hussain** `<132701966+asteroidcrib729@users.noreply.github.com>` as author and **github-actions[bot]** `<41898282+github-actions[bot]@users.noreply.github.com>` as committer. The state-persistence step supplies all four `GIT_AUTHOR_*`/`GIT_COMMITTER_*` values, and the writer honors them. Its defaults match this repository's workflow. Manual and scheduled triggers use the same identities; existing history is unchanged. Test and diagnostic workflows are read-only and do not create commits.

Feature-branch manual dispatch cannot send production alerts. A separate read-only CI workflow tests code pushes/pull requests without a Discord secret.

Quality CI also runs Ruff, Pyrefly, Python syntax compilation and a package build. Dependabot checks the uv manifest/lock and GitHub Actions weekly via `.github/dependabot.yml`; its pull requests receive the same tests and dependency review as other PRs, with high/critical newly introduced vulnerabilities blocked. I review dependency updates before merging them; automatic merging is disabled. The security workflow runs on code pushes, pull requests, weekly and on manual dispatch: `uv audit --locked` checks runtime/development dependencies against known advisories, and CodeQL scans Python with the extended security query suite. Findings are available in GitHub's **Security → Code scanning** view. These scans do not access the Discord secret or write delivery state. Known-advisory checks are a point-in-time result, not a guarantee of security.

CLI exit codes remain **0** healthy/valid-empty/idle, **1** fatal configuration/state failure, and **2** degraded source or delivery outcome. I use **job_finder.automation.runner** to distinguish partial coverage from operational failure: successful primary discovery with optional source problems produces a visible warning; total due primary discovery failure, notification failure, corruption, or failed state persistence still fails the run. A Google/recruiter probe cannot fail a cycle whose primary queries are intentionally not due. Zero qualified matches alone is not a failure. State commit/push failures are surfaced. The writer builds a state-only commit on the latest remote tree using a temporary index, preserving concurrent code changes. Acknowledgements override pending jobs; retention pruning and queue retirement are reconciled against the starting state. Normal fast-forward pushes retry branch races. Persistent failures retain state files/backups in a seven-day recovery artifact. There is no force push or working-tree rebase.

## My development records

I keep the project history, verified results and remaining questions in these records:

- [Project history and agent memory](AGENTS.md)
- [Audit memory](development-plans/MEMORY.md)
- [Issue register](development-plans/ISSUES.md)
- [Solution plan](development-plans/SOLUTIONS.md)
- [Implementation and validation record](development-plans/IMPLEMENTATION.md)


For production diagnosis, I set the manual workflow input **dry_run: true**. This runs the same discovery and health classification on GitHub without Discord messages or state commits. Source warnings remain in the Actions summary and run artifact; Google missing-cursor results are unverified rather than claimed as healthy empty. I documented the cause and correction in [the initial production incident](development-plans/PRODUCTION-INCIDENT-2026-09-08.md).


When I explicitly want to verify Discord delivery, I dispatch with **dry_run: false** and **verification_sample: true**. This refreshes source searches within a bounded sample (at most 12 JobSpy queries/300 seconds), sends at most three jobs, and uses clearly labeled review candidates only when the sample contains no qualified jobs. It does not change scheduled-run defaults, resend acknowledged jobs, or override rejection rules. Successful notifications are journaled normally; review candidates outside the sample are not queued.
