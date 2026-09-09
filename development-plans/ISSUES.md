# Job Finder App: issue register

**Latest update (2026-09-09):** Scheduled review alerts are enabled at the owner's request, with labeled digests of up to five jobs and the existing shared 20-job run cap. All pending Pyrefly configuration/ignore-comment changes are included. All 75 offline tests and dependency checks pass; Pyrefly reports zero errors with suppressions. The latest inspected production run had 1 already-notified qualified job, 25 review candidates and 310 rejected jobs. Discord destination/message retrieval is verified. See [filtering assessment and review-alert rollout](FILTERING-REVIEW-2026-09-09.md) for exact rule strictness, evidence, and remaining accuracy concerns. The September 8 status below is a historical implementation baseline; published Linux CI and real Discord delivery have since been verified.

**Production incident update (2026-09-08):** Both initial production runs completed discovery/state persistence but were marked failed because partial source warnings triggered exit 2 and the workflow escalated that to exit 1. The operational health policy, Google diagnostic classification and recruiter search handling are corrected. See [production incident analysis](PRODUCTION-INCIDENT-2026-09-08.md) for evidence, fixes and validation. Prior statements of code completion did not establish live-source acceptance.

## Current status — 2026-09-08

All 24 original issues have corresponding implemented corrections and offline validation. Each issue below now begins with its resolution and links to code and checks. The original problem description, severity and baseline line references are retained for traceability; they do not describe the current implementation.

**Verified:** 73 tests pass; all 54 synthetic matching cases produce their expected tiers. Source, delivery, recovery, feedback and concurrent-Git regression checks are included.

**Production acceptance remains open:** real LinkedIn/Indeed/Google availability, live Rozee pagination after observed blocking, published Linux CI results and held-out user relevance/known-positive recall. Discord and Git cannot guarantee exactly-once delivery across a network/crash boundary. Extra source pilots and unprovided salary/time-zone preferences are follow-on decisions.

The user has authorized publication to main. [MEMORY.md](MEMORY.md) summarizes the current system; [SOLUTIONS.md](SOLUTIONS.md) maps the implementation; [IMPLEMENTATION.md](IMPLEMENTATION.md) records evidence and limits.

## Historical findings with current resolutions

Evidence labels below apply to the original audit. **Reproduced** means executed against synthetic data/mocked services; **Code** means directly established by source inspection; **Risk** means a failure path exists but its occurrence in production is unverified; **Gap** means a requested capability is absent. P0 means silent delivery loss; P1 means core accuracy/discovery/reliability; P2 means supporting hardening or maintainability. Source references use baseline line numbers and named functions.

## I-01 — The candidate profile is incomplete and does not represent experience evidence

**Resolution: implemented and regression-covered.** Structured candidate profile separates internship evidence, listed skills and professional tenure. [Implementation](../candidate-profile.yaml), [validation](../tests/test_matching.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Gap.** `filtering/resume_filter.py:9`, `filter_jobs_for_faraz`; `config.yaml`.

The runtime never reads the PDF or a structured candidate profile. `FARAZ_SKILLS` omits Next.js, AWS, and Azure, adds Express without explicit résumé evidence, and treats internship-backed skills and merely listed skills equally. Education, internship dates, evidence strength, and role preferences are not modeled. Updating the résumé does not update matching. Hard-coded neighborhood preferences are also not grounded in the supplied résumé.

**Impact:** prominent strengths are missed and weaker assumptions can drive qualification. This is a profile representation problem, not a requirement to parse PDFs on every run. **Solution: S-01.**

## I-02 — Substring matching causes false acceptance and false rejection

**Resolution: implemented and regression-covered.** Role-aware aliases, occupation checks and mandatory skill groups replace substring-only matching. [Implementation](../filtering/resume_filter.py), [validation](../tests/test_matching.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `filtering/resume_filter.py:18`, `:37`, `:47`, `:162`.

One substring from `FARAZ_SKILLS` is enough. `Software Engineer` matches itself even for a Ruby-only requirement; `api` matches `rapidly` in a civil-engineering fixture. `cad` rejects `Academy`; `sales` rejects software development for a sales product. `Next.js Developer` with a Next.js-only description fails. There is no distinction between mandatory, preferred, and incidental technology mentions, and no token-aware seniority classification.

**Impact:** both precision and recall suffer; adding keywords without changing matching logic can worsen collisions. **Solution: S-02.**

## I-03 — Experience parsing confuses durations, ranges, and permissive wording

**Resolution: implemented and regression-covered.** Contextual experience parsing handles minima, ranges, months, written numbers and preference clauses. [Implementation](../filtering/resume_filter.py), [validation](../tests/test_matching.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `filtering/resume_filter.py:53`, `:144`.

The first regex permits a year count without experience context. A four-year degree rejects a junior role. `1 to 3 years experience` produces `[3, 1]`; zero is discarded; written numbers are missed. Any occurrence of `graduate`, `fresh`, `intern`, or similar text can override even a five-year minimum; `international` contains `intern`. Required and preferred experience, alternatives, individual skills, and employer-history durations are not distinguished.

**Impact:** truly senior requirements pass and plausible junior/stretch roles are rejected. The fixed two-year cutoff is not calibrated to the résumé. **Solution: S-03.**

## I-04 — Qualification runs without sufficient job descriptions

**Resolution: implemented and regression-covered.** Description completeness, LinkedIn detail requests and bounded Rozee/post caches preserve qualification evidence. [Implementation](../scrapers/cache.py), [validation](../tests/test_cache_pagination.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Reproduced.** `scrapers/jobspy_adapter.py:33`; `scrapers/rozee_scraper.py:69`; `filtering/resume_filter.py:162`.

LinkedIn detail fetching is not enabled. Installed JobSpy 1.1.82 defaults `linkedin_fetch_description=False` and initializes description to `None` without details. Rozee always uses an empty description. JobSpy missing descriptions become empty strings; generic titles still pass the skill gate. Recruiter search snippets provide only partial evidence.

**Impact:** seniority, mandatory stack, residency, and salary can be absent from the text used for a supposedly qualified alert. Missing evidence is silently treated as compatible. **Solution: S-04.**

## I-05 — Search intent overwrites actual work mode and narrows remote discovery

**Resolution: implemented and regression-covered.** Independent local/remote query tracks preserve listing-derived work mode. [Implementation](../scrapers/jobspy_adapter.py), [validation](../tests/test_sources.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `scrapers/jobspy_adapter.py:28`, `:58`; `scrapers/linkedin_posts_scraper.py:105`.

Every remote JobSpy search is anchored to Karachi. Every result from it becomes remote even if the source row explicitly says false; the row's `is_remote` field is ignored. Conversely, a true remote row from a local query can lose that flag. Recruiter-post queries similarly determine location/work mode regardless of listing evidence.

**Impact:** international discovery is constrained while local/foreign on-site results can masquerade as remote. **Solution: S-05.**

## I-06 — Karachi locality and Pakistan remote eligibility are not enforced

**Resolution: implemented and regression-covered.** Karachi and Pakistan-eligible remote rules distinguish explicit compatibility from unknown restrictions. [Implementation](../filtering/resume_filter.py), [validation](../tests/test_matching.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `filtering/resume_filter.py:84`.

Any location containing `Pakistan` or `pk` passes the initial local gate, except for a short city blacklist. `Hyderabad, Pakistan` and country-only `Pakistan` pass. Remote roles bypass city checks without country eligibility review. `Work from home is not permitted` is taken as remote evidence. Karachi mentions are not reconciled with residency restrictions, actual office location, or contradictory descriptions.

**Impact:** inaccessible remote jobs and non-Karachi on-site jobs reach alerts. Neighborhood priority is a broad substring badge, not verified geography. **Solution: S-06.**

## I-07 — USD compensation preference cannot be evaluated

**Resolution: implemented and regression-covered.** Salary evidence preserves disclosed currency and routes ambiguous/other-currency remote pay to review. [Implementation](../filtering/resume_filter.py), [validation](../tests/test_matching.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Gap/Code.** `scrapers/base.py:6`; `scrapers/jobspy_adapter.py:47`; `notifiers/discord.py`.

The job model has no salary amount, interval, currency, or salary evidence. Adapter conversion discards those JobSpy fields. There is no salary policy or notification display.

**Impact:** the requested remote-dollar track cannot be distinguished from local-currency or undisclosed-pay remote roles. This is a new requirement gap, not evidence that current alerts promise USD. **Solution: S-07.**

## I-08 — One JobSpy parameter set is incorrectly reused across sites

**Resolution: implemented and regression-covered.** Source-specific parameters correct Indeed remote/date behavior and explicitly construct Google queries. [Implementation](../scrapers/jobspy_adapter.py), [validation](../tests/test_sources.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/version-verified.** `scrapers/jobspy_adapter.py:33`; installed JobSpy 1.1.82 `indeed/__init__.py`, `_build_filters`.

The adapter always supplies `hours_old`, including with `is_remote=True`. The installed Indeed implementation prioritizes the date branch and omits its remote/job-type branch in that combination. This interacts directly with I-05. Source capability differences are not modeled.

Google receives no explicit `google_search_term`. This is a query-quality concern, **not** a proven absent-results bug: the inspected Google implementation constructs a fallback query containing the keyword, location, time phrase, and remote term. Current documentation and code must both be checked when updating the pinned version. [JobSpy reference](https://github.com/speedyapply/JobSpy).

**Impact:** a configured filter may not reach the underlying source, and site-specific query quality is uncontrolled. **Solution: S-08.**

## I-09 — Rozee extracts too little and manufactures location/freshness

**Resolution: implemented and regression-covered.** Rozee uses verified bootstrap fields and city ID, bounded pagination, caches and blocking/parse diagnostics. [Implementation](../scrapers/rozee_scraper.py), [validation](../tests/test_cache_pagination.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code; live-selector failure unverified.** `scrapers/rozee_scraper.py:15`, `:38`, `:66`.

Results inherit Karachi from a hard-coded `fc/1592` URL or Pakistan from the general search. Actual card location, experience, date, and description are not read. Every job is `Recently`. Broad fallback selectors such as `[class*='job']` can include nested/nonlisting elements; selecting a `.jtitle` wrapper without an anchor can lose a link. Search uses only the first page, simple space-to-hyphen substitution, and no detail fetch. HTTP non-200 results are silently skipped.

A mocked Lahore card with five-year experience and an old date passed qualification after these fields were discarded. The current meaning of `fc/1592`, real markup compatibility, and blocking rates were not verified live.

**Impact:** wrong-city and stale jobs can pass, while valid jobs can disappear without a diagnostic. **Solution: S-09.**

## I-10 — LinkedIn recruiter snippets are treated as verified single vacancies

**Resolution: implemented and regression-covered.** Recruiter posts use host checks, saved cadence, independent explicit role sections and original-post provenance. [Implementation](../scrapers/post_roles.py), [validation](../tests/test_review_feedback.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Risk.** `scrapers/linkedin_posts_scraper.py:42` and its fixed `queries`, title cleanup, and job construction.

The source ignores configuration and always runs. It uses five fixed searches, truncates titles to 85 characters before filtering/identity, does not parse the actual post body or isolate individual roles, and assigns a generic company. A multi-role post can mix senior/junior requirements; an author/hiring headline can hide the role after truncation. Email is extracted only from a snippet, is optional, and is not attributable to a particular role. URL validation checks path substrings, not a parsed LinkedIn hostname. Accessibility fetches are not used to enrich the post.

**Impact:** ambiguous announcements can be misclassified, valid posts can fail title checks, and application context can be unreliable. **Solution: S-10.**

## I-11 — Freshness and active-status labels are not trustworthy

**Resolution: implemented and regression-covered.** Publication, expiry, discovery and active/unknown/closed states remain separate evidence. [Implementation](../scrapers/base.py), [validation](../tests/test_sources.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `scrapers/linkedin_posts_scraper.py:12`, `:19`, `:115`; `scrapers/rozee_scraper.py:69`; `scrapers/base.py:12`.

Hard-coded old years reject current posts mentioning a 2025 graduating class and will age incorrectly. A month-limited search is labeled `Past Month (Fresh)` without parsing a publication date. HTTP 403, login/challenge responses, most server errors, and timeouts can return true from the active check. There is no source-independent date policy; JobSpy requests 72 hours, recruiter discovery a month, and Rozee no age constraint. There is no general closure/expiry check.

**Impact:** stale/unverified listings appear fresh and legitimate posts disappear. Expired dedup entries can later re-alert old jobs. **Solution: S-11.**

## I-12 — Search coverage is shallow, repetitive, and not measured

**Resolution: implemented and regression-covered.** Query-specific pagination, successful watermarks, budgets, yield reporting and longer zero-yield intervals improve coverage control. [Implementation](../scrapers/metrics.py), [validation](../tests/test_query_metrics.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Gap; production coverage unmeasured.** `config.yaml:4`, `:30`; adapter loops; Rozee URLs; recruiter queries.

Thirteen overlapping keywords receive only 15 requested JobSpy results each before filtering. Next.js, explicit frontend/backend variants, Django, and Flask are missing from the configured search terms. No application-level offset strategy, per-source successful-search watermark, recovery window, or query-yield tracking exists. With the full configuration there are 78 serial JobSpy invocations and 26 Rozee page requests each run, plus recruiter discovery. Custom sources lack bounded retry/backoff policies and all sources lack an application request budget; JobSpy does have some internal retries.

**Impact:** duplicate top results consume work while niche fits may be missed; bursts, slow sources, and failures can reduce useful coverage. Source blocking and the exact effect of query depth require measurements. **Solution: S-12.**

## I-13 — Inconsistent null handling can discard valid rows or crash filtering

**Resolution: implemented and regression-covered.** Null-safe normalization, isolated conversion failures and complete job round trips enforce the shared contract. [Implementation](../scrapers/base.py), [validation](../tests/test_sources.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `scrapers/jobspy_adapter.py:47`, `:73`; `scrapers/base.py:14`; `filtering/resume_filter.py:92`; `notifiers/discord.py:86`.

`str(value or fallback)` turns NaN into `nan` and raises on `pd.NA`. The exception handler encloses the entire source query, so a malformed row prevents remaining valid rows from being processed. `Job.description` allows `None`, but the filter calls `.lower()` and embeds call `len()` without normalization. Missing location can fall back to the search location, creating false evidence. URL validity is not consistently checked.

**Impact:** intermittent missing jobs, misleading fields, and a fragile adapter contract, especially as sources expand. **Solution: S-13.**

## I-14 — Synthetic identity is unstable and deduplication loses richer evidence

**Resolution: implemented and regression-covered.** Native IDs, canonical URLs, explicit aliases and exact merging replace unstable title-only identity. [Implementation](../scrapers/base.py), [validation](../tests/test_sources.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Reproduced/Code.** `scrapers/base.py:20`; `storage/tracker.py:55`; ordering in `main.py`.

Identity hashes platform/title/company/raw URL, discarding JobSpy's source ID. Tracking parameters, source names, changed titles, and snippets produce different IDs for the same vacancy. Cross-source duplicates are not linked. Exact duplicates keep the first result after filtering, even when a later copy contains more detail. IDs include no location when the other fields/URL are shared, creating a potential collision for multi-location listings.

**Impact:** repeated alerts consume attention and richer evidence can be lost. The 30-day TTL is a notification-retention policy, not evidence of a new publication. **Solution: S-14.**

## I-15 — Partial notification success permanently suppresses failed alerts within retention

**Resolution: implemented and regression-covered.** Per-job acknowledgements and a persistent deferred queue prevent failed/unsent jobs from being marked delivered. [Implementation](../storage/tracker.py), [validation](../tests/test_delivery.py). See the current acceptance boundaries above before claiming production closure.

**P0 · Reproduced.** `notifiers/discord.py:56`; `notifiers/manager.py:23`; `main.py:92`.

Notifier returns true if any job succeeds. `main.py` then marks every `new_job` seen. With mocked HTTP 204 followed by HTTP 500, both job IDs are saved. Failed jobs are suppressed until their state ages out, and may never be rediscovered afterward.

**Impact:** suitable jobs can be discovered and filtered correctly yet never reach the user. **Solution: S-15.**

## I-16 — Discord retry success is counted without inspecting the retry response

**Resolution: implemented and regression-covered.** Checked bounded retries distinguish confirmed, failed, uncertain and permanent delivery outcomes. [Implementation](../notifiers/discord.py), [validation](../tests/test_delivery.py). See the current acceptance boundaries above before claiming production closure.

**P0 · Reproduced.** `notifiers/discord.py:41`.

After HTTP 429, the second POST response is discarded and success is incremented unconditionally if no exception is raised. Mocked 429 followed by 500 returns true. Other transient server/network errors have no bounded retry handling. Aggregate status hides which job failed.

**Impact:** failed messages are reported delivered and enter seen state. **Solution: S-16.**

## I-17 — Discord payload construction is not validated or isolated per job

**Resolution: implemented and regression-covered.** Bounded payloads, mention suppression and per-job error isolation support cards and review digests. [Implementation](../notifiers/discord.py), [validation](../tests/test_review_feedback.py). See the current acceptance boundaries above before claiming production closure.

**P2 · Code/Risk; None handling reproduced in filter.** `notifiers/discord.py:30`, `_build_embed`.

Embed construction occurs outside the try block. Titles and field values are unbounded, empty required values can survive, and URLs/source text are not consistently normalized. A malformed job can abort delivery; oversized fields can receive HTTP 400. Description truncation alone does not bound all fields or the full payload. The embed also replaces remote location details with a generic remote badge.

**Impact:** a single malformed listing can interrupt alerts or obscure geographic restrictions. Discord's documented limits include title 256 characters, field value 1,024, and 6,000 aggregate embed characters. [Discord embed limits](https://docs.discord.com/developers/resources/message#embed-object-embed-limits). **Solution: S-17.**

## I-18 — State persistence failures are swallowed and writes are not atomic

**Resolution: implemented and regression-covered.** Validated atomic journals, previous-good backups and recovery-candidate export preserve history on failure. [Implementation](../storage/recover.py), [validation](../tests/test_state_recovery.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Risk.** `storage/tracker.py:24`, `:43`, `:66`.

State load failure resets all history to empty. `save()` writes directly to the destination, catches failures, and returns no failure status. A malformed timestamp can reset the entire loaded state during pruning. A supplied custom storage path still creates `DATA_DIR`, not its own parent. Pruning persists only when a later save occurs. There is no backup/recovery, schema version, or pending-delivery record.

**Impact:** duplicate alerts after corruption/save failures and undetected loss of delivery history. A crash between Discord delivery and state persistence remains an architectural delivery window requiring explicit handling. **Solution: S-18.**

## I-19 — Workflow runs can overlap and race on shared notification state

**Resolution: implemented and regression-covered.** Serialized default-branch execution and three-way state-only Git commits preserve concurrent code/history changes. [Implementation](../storage/sync_state.py), [validation](../tests/test_state_recovery.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Risk.** `.github/workflows/job_finder.yml:3`, `:14`, `:40`.

Scheduled and manually dispatched runs have no concurrency group. They can read the same old state, send duplicate alerts, then compete to auto-commit updates. There is no explicit runtime deadline or retry/reconciliation strategy for state push conflicts. Notification success precedes remote state persistence; a failed later commit means the next runner can resend jobs.

**Impact:** duplicate/lost state and inconsistent execution under overlap. No production collision was observed during this audit. **Solution: S-19.**

## I-20 — Dependency installations are not reproducible

**Resolution: implemented and regression-covered.** Exact dependency pins, environment reporting and independent Python 3.11 CI make execution reproducible. [Implementation](../requirements.lock), [validation](../.github/workflows/tests.yml). See the current acceptance boundaries above before claiming production closure.

**P2 · Code/Risk.** `requirements.txt`; `.github/workflows/job_finder.yml:23`.

All dependencies use minimum-only constraints; fresh runner resolution can change behavior without a source change. The inspected local runtime differs from workflow Python. There is no lock/constraints file or recorded run version manifest. A pip cache is not a dependency lock.

**Impact:** reproducing source behavior and diagnosing regressions becomes difficult. This does not prove a particular dependency update caused the user's current problem. **Solution: S-20.**

## I-21 — Healthy empty searches and failures are difficult to distinguish

**Resolution: implemented and regression-covered.** Source health, query yield/budgets, reason counts, reports and meaningful exit codes make failures visible. [Implementation](../main.py), [validation](../tests/test_pipeline.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code.** Scraper exception handlers; `main.py:29`; `storage/tracker.py:52`; notifier return handling.

Source errors often become empty lists. Rozee non-200s are silent; normal pipeline early returns succeed. Missing webhook, all notifications failing, failed test notification, and state-save failures generally log without a nonzero process exit. There is no structured source outcome, row-conversion failure count, or per-query health report. Filter rejections are DEBUG logs while main logging is INFO.

**Impact:** a green workflow can coexist with unsuccessful discovery/delivery and no clear explanation. **Solution: S-21.**

## I-22 — There is no repeatable accuracy benchmark or automated regression suite

**Resolution: implemented and regression-covered.** Offline tests, a fixed-date 54-case synthetic benchmark and capture-time feedback evaluation support regression checking. [Implementation](../evaluation.py), [validation](../tests/test_matching.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Gap.** `scratch/test_search.py`; workflow; `data/seen_jobs.json`.

The scratch script makes live searches at import time and prints results; it has no assertions. There are no fixtures or tests for résumé matching, source conversion, retry behavior, or state acknowledgement, and no CI validation of changes. Nothing saves raw candidate evidence, rejection reasons, scores, source coverage, or user relevance feedback. The seen file has only hashes/timestamps.

**Impact:** precision, missed-job recall, source reliability, and improvement cannot be established. Blind threshold changes risk trading one error type for another. **Solution: S-22.**

## I-23 — Configuration and documentation disagree with active behavior

**Resolution: implemented and regression-covered.** Nested validated configuration, active source/policy settings and updated README replace misleading controls. [Implementation](../config.py), [validation](../tests/test_pipeline.py). See the current acceptance boundaries above before claiming production closure.

**P2 · Code.** `config.py:7`, `:29`; `filtering/filter.py`; `filtering/resume_filter.py:112`; `README.md`.

Configuration merges shallowly and validates neither schema nor types. The active filter accepts but ignores its configuration argument; `experience_levels` is unused. Recruiter scraping has no enable/configuration switch. README describes Telegram and broader enabled platforms than the code/config provide, points to a nonexistent active `filtering.title_exclude_keywords` setting, and contains a machine-specific `file:///` link. Invalid nested YAML types can fail at runtime rather than at load.

**Impact:** plausible user tuning can have no effect, and troubleshooting instructions can send maintenance in the wrong direction. **Solution: S-23.**

## I-24 — Alerts provide neither ordering by fit nor reasons for the match

**Resolution: implemented and regression-covered.** Constraint-first ranking, explanations, optional review digests and job-ID relevance feedback support usable alerts. [Implementation](../feedback.py), [validation](../tests/test_review_feedback.py). See the current acceptance boundaries above before claiming production closure.

**P1 · Code/Gap.** `filtering/resume_filter.py:112`; `main.py`; `notifiers/discord.py:58`.

Accepted jobs preserve scraper order; there is no fit score, confidence, reason list, or freshness sort. The priority-hub flag changes badge/color but not ordering. All accepted new jobs are sent individually with generic descriptions and no explicit missing requirements, eligibility evidence, or salary status.

**Impact:** weak evidence can occupy the same attention as excellent matches, and the user cannot efficiently diagnose bad recommendations. Ranking cannot repair incorrect hard constraints or lost delivery, so this follows earlier fixes. **Solution: S-24.**


## Continuation findings — 2026-09-08

Current resolution status is in [IMPLEMENTATION.md](IMPLEMENTATION.md).

- **I-04/I-09:** Bootstrap HTML reached requirement matching directly; it is now converted to text. Detail failures now produce partial health and no successful-query watermark.
- **I-12:** Using all earlier queries' IDs to detect repeated pages could hide another query's second-page results. Repetition is now query-specific.
- **I-10:** Blended announcements could apply a senior role's experience or city to a junior role. Explicit sections now have independent evidence and identity, retaining original provenance.
- **I-18/I-19:** A naive acknowledgement union would restore intentionally pruned history. Three-way merging honors baseline pruning while preserving concurrent new acknowledgements.
- **I-21:** Pre-delivery and final reports appended duplicate Actions summaries. Only the final report now appends the summary.

Regression tests cover these corrections. Live source availability and held-out accuracy remain validation gaps.
