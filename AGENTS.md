# Project history and agent memory

Last updated: **2026-10-27**. This file is the repository-local historical archive and handoff record for Job Finder App. It covers the recorded local work and published changes on `main`; Git retains the individual commits, including automated state updates. It does not claim to reconstruct undocumented activity. Detailed audit evidence remains in `development-plans`.

## Reading this archive

The current conventions below govern new work. Dated history describes decisions and behavior at that time, including settings that were later replaced. Old root script commands, `requirements` files, `pyrefly.toml`, root report/cache paths and previous Git identities in historical records are not current instructions.

At the start of repository work, an agent checks the working tree, current configuration and relevant history before relying on this record. After a meaningful change, the agent records the date, purpose, implementation, validation evidence and remaining limits here, with links to detailed records. Secrets, resume contents, raw personal reports and webhook URLs never belong in this archive. A successful push, a successful hosted check and demonstrated production behavior remain separate facts.

## Current project and operating conventions

- **Owner and purpose:** Faraz Hussain; graduate/junior software opportunities aligned with his qualifications and internships. Local searches target Karachi; remote searches consider Pakistan eligibility and prefer USD compensation. The structured profile separates demonstrated internship evidence from listed skills.
- **Architecture:** Python JobSpy/custom adapters, GitHub Actions, persistent repository JSON and Discord. The owner explicitly chose to preserve this architecture while improving retrieval, matching and delivery reliability.
- **Runtime:** exact Python **3.14.7**, uv **0.12.9**, root `.venv`. `.python-version`, `pyproject.toml` and `uv.lock` are authoritative. Project packages never use global pip. Runtime and development dependencies remain separate; uv manages manifest/lock changes together.
- **Source:** installed package `src/job_finder`, imports under `job_finder.*`, tests in `tests`. Commands use `uv run --locked python -m job_finder` or installed console scripts; root script wrappers are not restored. Runtime settings live in `config/config.yaml`, the profile in `config/profiles/candidate-profile.yaml`, and tracked delivery/discovery state in `data/`. The underscore in `job_finder` preserves normal Python import syntax.
- **Tool configuration:** uv, Ruff and `[tool.pyrefly]` live in `pyproject.toml`. No separate `pyrefly.toml` is maintained. The current tool pins are Ruff 0.17.2 and Pyrefly 1.4.0; the manifest/lock take precedence if later changes supersede this snapshot.
- **Local material:** `.local/` holds personal files, reports, caches and builds. The resume is `.local/Resume - Faraz Hussain.pdf`. `.venv` stays at the root for standard uv/IDE discovery; source/test bytecode remains beside its modules. The whole `.local` tree is Git-ignored and excluded from source distributions. Only the explicitly selected redacted `.local/output/latest/` directory may be uploaded, never the entire `.local` tree.
- **Workflow convention:** workflows orchestrate actions and invoke single tool/script commands. Python/JavaScript/shell programs, heredocs and interpreter `-c` snippets are not embedded in YAML. Custom logic belongs in dedicated `src/job_finder` modules with offline regression coverage.
- **Delivery policy:** scheduled and normal manual runs send qualified jobs first, then labeled review candidates in digests of up to five jobs, under a shared 20-job limit. Deferred jobs remain queued and are reevaluated. Rejections remain excluded. The optional manual verification sample caps delivery at three jobs and uses review candidates only when no qualified candidates exist.
- **Evidence and safety:** no reset of production delivery history for experiments, no committed reports/secrets/environments, and no real source requests or Discord sends from offline tests. Live diagnostics require an appropriate task scope; replay and temporary state paths are preferred for reproducible evaluation.
- **Git attribution:** automated state commits use author `Faraz Hussain <132701966+asteroidcrib729@users.noreply.github.com>` and committer `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>`. The workflow supplies all four identity variables and writer defaults match. Owner-authorized manual commits use the owner's repository identity. Independent contributors retain their own authorship.
- **Publication:** staged changes remain scoped to the task. Concurrent remote state updates are preserved; pushes are ordinary fast-forwards. No historical rewrite, force push or empty contribution commits. Test/diagnostic workflows remain read-only for repository contents; production alone writes state. CodeQL's security-events permission is separate.
- **Documentation voice:** README uses Faraz Hussain's first-person perspective. CONTRIBUTING uses third-person language about contributors and the maintainer. This archive uses factual historical narration and distinguishes current rules from superseded decisions.

## Repository and evidence map

| Location | Responsibility |
| --- | --- |
| `src/job_finder/configuration/loader.py`, `config/config.yaml`, `config/profiles/candidate-profile.yaml` | Validated settings and structured candidate evidence. |
| `src/job_finder/filtering/` | Role, skill, experience, geography, freshness, compensation and ranking decisions. |
| `src/job_finder/scrapers/` | Isolated JobSpy workers, Rozee parsing, recruiter-post discovery, optional remote feeds, cadence and query health. |
| `src/job_finder/notifiers/` | Bounded Discord cards/digests, checked retries and individual delivery outcomes. |
| `src/job_finder/storage/`, `data/` | Durable journals, pending queue, backups, recovery and concurrent Git reconciliation. |
| `src/job_finder/application/pipeline.py`, `automation/runner.py`, `application/health.py` | Application orchestration, replay, reports and operational outcome policy. All listed modules are inside `src/job_finder`. |
| `src/job_finder/diagnostics/discord.py`, `automation/failure.py` | Read-only destination/message checks and explicit final workflow failure signaling. |
| `src/job_finder/evaluation/benchmark.py`, `evaluation/feedback.py` | Synthetic/user-labeled benchmark evaluation and local relevance feedback. |
| `.github/workflows/`, `.github/dependabot.yml` | Production, read-only diagnostic, quality CI, dependency review, security scans and weekly update configuration. |
| `.vscode/` | Shared interpreter, recommended extensions, unittest discovery, tasks and dry-run debugging. |
| `.local/` | Ignored resume, cached historical evidence, runtime reports, distributions and archived root bytecode. |
| [development-plans/MEMORY.md](development-plans/MEMORY.md) | Original audit and subsequent implementation summaries. |
| [development-plans/ISSUES.md](development-plans/ISSUES.md), [SOLUTIONS.md](development-plans/SOLUTIONS.md) | The 24-issue register, corresponding solutions and later updates. |

## Recorded chronology

### July 23, 2026 ? Initial application and stable baseline

Commits `45c7470`, `ac4d156` and `321fa4a` introduced the Job Finder App and clarified workflow permissions and desktop/mobile Discord webhook setup. The local `v1.0-stable` tag and `backup-v1.0` branch preserve the original baseline at `321fa4a`; they are historical recovery references, not deployment targets for current changes.

### July 27, 2026 ? Early profile filtering and notification scope

Commit `7df224a` added resume-based precision filtering, recruiter email scraping and schedule optimization. Commit `7518fc3` tightened entry-level checks, revised search keywords and removed the Telegram notifier. Discord became the retained notification integration. These early filtering approaches were later audited and substantially corrected.

### August 17, 2026 ? Recruiter discovery expansion

Commit `334b80f` adopted DDGS for LinkedIn recruiter-post discovery and expanded fresh-graduate searches. Commit `beec22c` added one-month post freshness and live-URL validation. Later audit work found that accessibility, publication date and actual vacancy evidence needed stronger separation; these commits describe the earlier behavior, not the current guarantees.

### September 7?8, 2026 ? Audit and core corrective implementation

The owner reported that manually found LinkedIn/Indeed jobs matched his background better than automated alerts, despite the deployed app. The audit used the resume and code to document 24 issues and proposed solutions while retaining the existing architecture. Commit `d404142` published the corrective implementation.

The work covered:

- A versioned candidate profile separating internship evidence, listed skills and professional tenure; interpretable qualified/review/rejected decisions with reasons and gaps.
- Role-aware skill aliases and mandatory groups; contextual experience requirements; education, seniority, Karachi/remote eligibility, currency and freshness checks; ranking after eligibility decisions.
- Listing-derived work mode and location, null-safe row normalization, invalid-row isolation, stable/canonical identities and merged duplicate evidence.
- Source-specific JobSpy arguments and isolated query deadlines; fuller descriptions; corrected Rozee city/extraction, bounded pagination/detail caches, separate recruiter roles with provenance, configurable discovery cadence and query-yield records.
- Optional Remotive/We Work Remotely feed adapters, left disabled for separate evaluation.
- Per-job delivery acknowledgements, bounded checked retries, uncertain-delivery handling, safe cards/digests, persistent pending jobs and deferred delivery caps.
- Atomic JSON writes, validated backups, explicit recovery export, concurrent three-way Git reconciliation, state-only commits and bounded push retries.
- Offline replay, run reports, source health, synthetic evaluation, relevance feedback and validated configuration.

[IMPLEMENTATION.md](development-plans/IMPLEMENTATION.md) maps the implemented work to I-01 through I-24 and records the original validation boundaries. Production data was retained. Completion of those code changes did not establish measured production precision/recall or permanent source availability.

### September 8, 2026 ? Failed manual and scheduled runs

The initial manual run on `d404142` and scheduled run on `2781f83` completed discovery and state persistence but failed their final workflow step. Their artifacts recorded 348 and 237 unique jobs respectively, with zero qualified and 21 review candidates in each run. Review delivery was disabled at that time.

The root cause was escalation of every degraded application exit into a workflow failure, even when primary discovery succeeded. Google cursor warnings and DDGS provider behavior also lacked adequate classification. Commit `68fdf80` separated partial-coverage warnings from fatal operational outcomes, classified missing Google cursors, selected web search backends and added manual dry-run control. Commit `6712dcc` recorded verification.

[Linux CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34237249338) and the [manual hosted dry run](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34237275969) passed. The latter sent no messages and skipped state persistence; primary queries were not due, so it was not a fresh complete source sweep. Total primary outages, delivery failures, corrupt state and persistence failures still fail. Full evidence: [production incident](development-plans/PRODUCTION-INCIDENT-2026-09-08.md).

### September 8?9, 2026 ? Discord verification and review visibility

Commit `9237aff` added the owner-authorized manual verification sample: refreshed queries within a bounded budget, at most three delivered jobs, and clearly labeled review candidates if no qualified matches exist. It preserved deduplication and rejection rules.

Commit `550f356` added a read-only Discord destination/message diagnostic. The [recorded diagnostic](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34365201374) verified the configured webhook's Job Finder server, `general` channel and existence of an acknowledged September 8 message. That diagnostic did not send another message. The owner's report of no visible notifications was investigated separately from transport acknowledgement.

The September 9 production evidence contained 603 raw rows, 336 unique jobs, one already-notified qualified job, 25 review candidates and 310 rejected jobs. Missing dates, unknown remote pay/eligibility and experience stretch cases kept plausible results out of the qualified tier. Those were recorded matcher decisions, not independently confirmed labels.

Commit `ddb9db8` enabled scheduled review digests at the owner's request and included pending Pyrefly configuration/suppressions. Qualified-first ordering, the shared 20-job cap, digest size of five and no-resend behavior were retained. Matcher thresholds were not loosened in this change. The suite then had 75 tests. [Filtering and review assessment](development-plans/FILTERING-REVIEW-2026-09-09.md) preserves the rule analysis and remaining accuracy concerns.

### September 17, 2026 ? Owner attribution restored

Commit `d127c36` restored account-linked author attribution for automated state commits after the owner questioned contribution-graph activity. The historical author display name was `asteroidcrib729`, and the committer was then `Job Finder Bot <actions@github.com>`. Those names were superseded by the October identity contract above. Existing history was not rewritten and empty commits were not introduced.

### October 27, 2026 ? uv, Python 3.14.7 and explicit commit identities

Commit `e9bed47` introduced uv project/dependency management, the dedicated `.venv`, exact Python 3.14.7, generated `uv.lock`, separate runtime/development groups and locked Actions environments. Requirements files were replaced; CONTRIBUTING and the original AGENTS instructions were added.

JobSpy 1.1.82's NumPy constraint blocked the requested runtime. The migration upgraded JobSpy to 1.4.1, pandas to 3.1.0 and NumPy to 2.5.4, refreshed compatible transitives and replaced the obsolete JobSpy transport dependency through its upgrade. The adapter maps the existing description option to `fetch_description`; the worker recognizes lowercase JobSpy logging and DataFrame error metadata, retains valid partial rows and sanitizes failures.

The state writer/workflow now explicitly distinguish Faraz Hussain as author from the GitHub Actions bot as committer. Tests verify the workflow/default identity agreement and actual pushed commit metadata after a concurrent branch race. The chosen noreply address preserves account attribution without publishing the personal Gmail address discussed earlier.

Validation at this stage: 80 offline tests, 54/54 synthetic tiers, dependency consistency and lock checks, Pyrefly with zero diagnostics and 17 existing suppressions, and a point-in-time audit of 40 dependencies. The application was initially still an unpackaged checkout; the next milestone superseded that layout. Detailed record: [uv migration](development-plans/UV-MIGRATION-2026-10-27.md).

### October 27, 2026 ? Source package, editor, quality and security workflows

Commit `125a1e8` moved production modules into installed `src/job_finder`, added `uv_build` and console entry points, updated imports/mock targets/worker and workflow invocations, and kept configuration/state external through shared path resolution. Tests covered imports and configuration from outside the checkout and explicit `JOB_FINDER_HOME` overrides.

Ruff and Pyrefly checks, interpreter compilation and package builds were added to quality CI. VS Code received shared interpreter, extension, task, unittest and dry-run debug settings. Weekly Dependabot uv/Actions updates, PR dependency review, advisory auditing and CodeQL scans were added. An initial dependency-review failure exposed disabled repository dependency graph/alerts; enabling those settings and rerunning the check resolved it.

[Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40487599330) passed 83 tests and the quality/build gates. [Security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40487599510) passed the 41-package advisory audit and CodeQL's 50-rule analysis with zero findings. The first Dependabot PR passed its checks after the setting correction; this was not authorization to merge it. Commit `c1316b9` recorded the hosted evidence. Details: [source layout record](development-plans/SOURCE-LAYOUT-2026-10-27.md).

### October 27, 2026 ? Consolidated configuration and local cleanup

Commit `6c03bb1` moved Pyrefly settings into `pyproject.toml`, removed `pyrefly.toml`, extracted the standard-library Discord diagnostic and production failure helper, and converted every workflow run step into a tool/script invocation. Regressions enforce the no-inline-code rule and exercise diagnostic validation, GET-only transport, redirect refusal, safe output and failures.

The resume, caches, reports, distributions and obsolete root bytecode moved into ignored `.local`; the resume SHA-256 remained unchanged. Only empty `scratch` was removed. `.venv` and source/test bytecode remained in their conventional locations. Application, evaluation, feedback and workflow report paths now use `.local/output`; artifact uploads select only `.local/output/latest` and explicitly allow hidden paths. Source distributions exclude `.local/**`. A reused local build cache produced an old wheel, so fresh build commands use `--no-cache`, and archive inspection verified the extracted scripts were included and personal material was absent.

[Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40495710302) passed all 90 tests, Ruff, consolidated Pyrefly, compilation and fresh builds. [Security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40495710190) passed with zero CodeQL findings. Commit `f3426e8` recorded these results. Production state and the resume contents were not changed. Details: [cleanup record](development-plans/LOCAL-CLEANUP-2026-10-27.md).

### October 27, 2026 ? Documentation voice and historical handoff

At the owner's request, README was rewritten in his first-person voice, CONTRIBUTING was rewritten in third person, and this file was expanded from a short instruction list into the project archive. Current rules, dated evidence and unresolved work are separated to prevent old instructions from being reused accidentally. The update changes documentation only; the runtime validation below belongs to the preceding code revision, not a new test execution for these prose changes.

### October 27, 2026 - Configuration and functional module organization

Following documentation commit `228a912`, the owner requested a dedicated configuration directory and grouped source modules, then clarified that the Python package must remain at `src/job_finder`. Settings moved to `config/config.yaml` and the unchanged profile to `config/profiles/candidate-profile.yaml`. Application, configuration, automation, diagnostics and evaluation subpackages now contain the former package-root scripts. Only package entry files remain at that root. Shared paths account for the additional module nesting; relative profile references resolve within `config/`. Imports, workflows, console targets, regression patches and documentation links follow the new paths. The lockfile, dependencies and production state were retained.

Local checks passed: 91 offline tests, 54/54 synthetic cases, Ruff, Pyrefly (zero errors, 17 suppressions), compilation, dependency consistency, Actionlint and fresh builds. An independently installed wheel loaded configuration and ran CLI help outside the checkout. Hosted checks remain pending publication. Details: [structure record](development-plans/PROJECT-STRUCTURE-2026-10-27.md).

## Last recorded validation and remaining work

Latest local validation covers the configuration/module refactor described above (91 tests). The preceding hosted-validated implementation was **`6c03bb1`**, recorded by **`f3426e8`** on October 27, 2026. The working tree and remote may advance after this record; Git status/history and the relevant hosted run are the verification sources.

- 90 offline regressions passed locally and on Linux; the matching benchmark contains 54 synthetic cases with previously recorded 54/54 agreement.
- Ruff, Pyrefly, interpreter compilation, dependency consistency, fresh package builds and workflow validation passed. Pyrefly retained 17 targeted suppressions; zero diagnostics is not complete type coverage.
- The most recent hosted security analysis reported zero CodeQL findings. Advisory checks are point-in-time results, not proof that all vulnerabilities are absent.
- Real production precision/recall is still unmeasured. Held-out manually found jobs are needed to separate retrieval misses, parser limitations, qualification decisions, deduplication and delivery effects.
- Title recognition for adjacent software roles, treatment of internships, source seniority labels and mandatory-stack sentence parsing remain candidates for evidence-based review. The historical report highlighted examples; it did not prove that every rejected job was actually suitable.
- Google cursor availability, job-board blocking, Rozee live pagination and DDGS provider behavior remain external/operational constraints. Offline fixture success does not prove continuous live availability.
- Minimum salary and acceptable time zones remain owner decisions. Optional remote-feed expansion and automatic depth tuning are separate future work.
- Delivery is not exactly-once across uncertain network outcomes or a crash between Discord acknowledgement and remote state persistence. Recovery requires reconciling later receipts before restoring older state.
- VS Code configuration was validated as configuration; actual extension activation was not observed during the recorded rollout. Dependabot PR status and repository security settings are mutable and must be checked when relevant.

## Commands and continuation checklist

For behavior/configuration work, appropriate checks run through the locked environment:

```powershell
uv sync --locked
uv pip check
uv run --locked ruff check src tests
uv run --locked pyrefly check
uv run --locked python -m compileall -q src tests
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m job_finder.evaluation.benchmark tests/fixtures/matching.json
```

Package/layout changes also require `uv build --no-cache --out-dir .local/dist` and archive inspection. Dependency/runtime changes also require `uv audit --locked` and applicable hosted checks. Documentation-only changes require wording, command/link and staged-diff review. Reports and benchmark outputs stay in `.local/output`; experiments do not overwrite production state.

Before publishing authorized changes, an agent inspects the staged diff, preserves concurrent remote state updates, verifies the final remote SHA and reports any untested boundary. Historical records remain dated; a new observation supplements them rather than silently replacing the evidence that explained an earlier decision.
