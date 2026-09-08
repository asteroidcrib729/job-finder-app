# Job Finder App: implemented solutions and acceptance plan

## Current status — 2026-09-08

The corrective implementation for S-01 through S-24 is complete at the code level and included in the user-authorized publication to main. This file now records implemented results alongside the original design rationale and acceptance criteria.

**Validation:** 64 offline tests pass and all 54 synthetic expected tiers agree. The full evidence and source limitations are in [IMPLEMENTATION.md](IMPLEMENTATION.md).

**Remaining acceptance work:** inspect published Linux CI, perform controlled live-source checks, collect held-out real-job labels and compare manually found matches through retrieval, qualification, deduplication and delivery. No production precision/recall percentage is claimed. Optional remote-feed pilots, automatic depth tuning and unprovided salary/time-zone preferences remain separate from the completed core fixes.

## Implemented solution map

| Solution | Implemented result |
| --- | --- |
| S-01 | Structured candidate profile separates internship evidence, listed skills and professional tenure. |
| S-02 | Role-aware aliases, occupation checks and mandatory skill groups replace substring-only matching. |
| S-03 | Contextual experience parsing handles minima, ranges, months, written numbers and preference clauses. |
| S-04 | Description completeness, LinkedIn detail requests and bounded Rozee/post caches preserve qualification evidence. |
| S-05 | Independent local/remote query tracks preserve listing-derived work mode. |
| S-06 | Karachi and Pakistan-eligible remote rules distinguish explicit compatibility from unknown restrictions. |
| S-07 | Salary evidence preserves disclosed currency and routes ambiguous/other-currency remote pay to review. |
| S-08 | Source-specific parameters correct Indeed remote/date behavior and explicitly construct Google queries. |
| S-09 | Rozee uses verified bootstrap fields and city ID, bounded pagination, caches and blocking/parse diagnostics. |
| S-10 | Recruiter posts use host checks, saved cadence, independent explicit role sections and original-post provenance. |
| S-11 | Publication, expiry, discovery and active/unknown/closed states remain separate evidence. |
| S-12 | Query-specific pagination, successful watermarks, budgets, yield reporting and longer zero-yield intervals improve coverage control. |
| S-13 | Null-safe normalization, isolated conversion failures and complete job round trips enforce the shared contract. |
| S-14 | Native IDs, canonical URLs, explicit aliases and exact merging replace unstable title-only identity. |
| S-15 | Per-job acknowledgements and a persistent deferred queue prevent failed/unsent jobs from being marked delivered. |
| S-16 | Checked bounded retries distinguish confirmed, failed, uncertain and permanent delivery outcomes. |
| S-17 | Bounded payloads, mention suppression and per-job error isolation support cards and review digests. |
| S-18 | Validated atomic journals, previous-good backups and recovery-candidate export preserve history on failure. |
| S-19 | Serialized default-branch execution and three-way state-only Git commits preserve concurrent code/history changes. |
| S-20 | Exact dependency pins, environment reporting and independent Python 3.11 CI make execution reproducible. |
| S-21 | Source health, query yield/budgets, reason counts, reports and meaningful exit codes make failures visible. |
| S-22 | Offline tests, a fixed-date 54-case synthetic benchmark and capture-time feedback evaluation support regression checking. |
| S-23 | Nested validated configuration, active source/policy settings and updated README replace misleading controls. |
| S-24 | Constraint-first ranking, explanations, optional review digests and job-ID relevance feedback support usable alerts. |

## Original design and acceptance criteria

The sections below preserve the initial plan, now annotated with implemented code and tests. Their proposed production acceptance gates are not automatically satisfied by implementation.

## Preserve the architecture

Keep Python source adapters, a shared job representation, filtering/ranking, JSON state, GitHub Actions, and Discord webhooks. Improve their contracts and sequencing. No new hosted service, paid model, vector database, browser farm, or replacement notification architecture is required.

The target flow is: source-specific queries → normalize and validate → deduplicate/merge source evidence → enrich promising incomplete listings → check hard eligibility constraints → score fit and confidence → deduplicate against acknowledged deliveries → order and notify → persist individual outcomes. Keep discovery evidence separate from claimed listing facts.

## Implementation order and completion gates

| Stage | Work | Completion gate |
| --- | --- | --- |
| 1. Protect alerts and establish baseline | S-15, S-16, S-18, S-19, S-21, S-22, S-20 | Failed Discord messages remain retryable; state failures are visible; runs cannot overlap against the same production state; offline fixtures and dependency baseline exist. |
| 2. Repair source data | S-04, S-05, S-08, S-09, S-10, S-11, S-13, S-14 | No adapter invents location, remote status, or dates from a query; missing data and partial source failure are explicit. |
| 3. Align qualification with the résumé | S-01, S-02, S-03, S-06, S-07, S-23 | Matching/eligibility counterexamples have correct outcomes; candidate and search policies are configurable and versioned. |
| 4. Improve coverage and presentation | S-12, S-17, S-24; optional source expansion below | Better results on held-out manually labeled jobs; no duplicate flood; alerts explain evidence and uncertainty. |

Keep changes small enough to compare with the baseline. Capture a limited baseline dataset before changing qualification. Do not reset the production seen file to assess improvement; use replay fixtures or isolated evaluation state.

## S-01 — Create a structured, evidence-based candidate profile

**Implemented:** Structured candidate profile separates internship evidence, listed skills and professional tenure. [Code](../candidate-profile.yaml), [checks](../tests/test_matching.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-01.** Add a reviewed YAML profile, loaded through `config.py`, containing education, internship periods, demonstrated technologies, listed technologies, role families, and geography/compensation preferences. Keep the PDF local and ignored; do not add contact details to matching configuration.

Record Next.js/React/TypeScript/Tailwind/Node and Python/Django/Flask as internship-backed. Keep Java/C#, FastAPI, databases, AWS/Azure as résumé-listed unless more evidence is supplied. Do not assert Express experience. Store internship months separately from full-time experience; use explicit overlap-aware date handling and month precision rather than fabricating exact days.

Start with junior frontend, junior full-stack, junior backend, Python developer, associate software engineer, graduate/trainee, and relevant internship families. Neighborhood boosts remain optional and low weight; Karachi itself is the required local geography. Record a profile version and the résumé review date.

**Acceptance:** changing a profile skill changes evaluated evidence without Python edits; Next.js is represented; elapsed time since 2025 does not increase professional experience automatically; no personal contact data enters alert rationale.

## S-02 — Replace substring qualification with role-aware skill matching

**Implemented:** Role-aware aliases, occupation checks and mandatory skill groups replace substring-only matching. [Code](../filtering/resume_filter.py), [checks](../tests/test_matching.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-02.** Normalize text with Unicode normalization, whitespace handling, and punctuation-aware aliases. Use explicit technology aliases such as React/React.js/ReactJS, Next.js/NextJS, Node.js/NodeJS, PostgreSQL/Postgres, and front-end/frontend. Handle punctuation in C#, C++, and .NET deliberately instead of relying only on generic word boundaries.

Separate software role classification from skill evidence. Generic words such as software, engineer, web, API, and Git cannot alone prove fit. Match occupations instead of excluding every product domain: software for a sales platform can still fit. Require evidence for a relevant role family and assess mandatory skill groups, including alternatives such as React **or** Vue. Preferred/unfamiliar tools lower fit without automatically rejecting; a clearly incompatible mandatory primary stack should reject or become a disclosed stretch decision.

Missing descriptions should trigger evidence collection/review, not automatic acceptance or automatic permanent rejection. Do not count aliases repeatedly or let repeated keyword text inflate scores.

**Acceptance:** Next.js fixture is recognized; `rapidly` does not match API; `Academy` does not match CAD; civil engineering is rejected; a Ruby-only mandatory role does not become a strong match because its title says Software Engineer; duplicate aliases do not raise score.

## S-03 — Parse experience requirements with context and alternatives

**Implemented:** Contextual experience parsing handles minima, ranges, months, written numbers and preference clauses. [Code](../filtering/resume_filter.py), [checks](../tests/test_matching.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-03.** Return structured requirements: minimum/maximum months or years, required/preferred status, relevant skill/role, exact evidence span, and uncertainty. Normalize hyphens/en dashes and ranges; preserve zero; support common written numbers and months. Exclude degree duration, company age, and unrelated narrative numbers using sentence context.

Interpret `1 to 3 years` as minimum one/maximum three rather than independent requirements. Handle `2+`, `0–2`, `six months`, `one year`, and `fresh graduates with internships` explicitly. A generic `graduate` word must never erase a mandatory five-year requirement. When requirements conflict, flag review instead of using a broad exception.

Policy should reflect internship-level experience: strong junior/fresh eligibility first; one-year requirements may be a configurable stretch tier; clear two-plus-year mandatory professional requirements generally fall outside the evidenced baseline. A two-year **preferred** requirement is different. Do not automatically sum unrelated skill-specific experience minima.

**Acceptance:** all experience fixtures in MEMORY have documented expected outcomes; degree duration is ignored; five-year requirements survive incidental `graduate`/`international`; `1 to 3` has a correct minimum and is evaluated under the selected stretch policy.

## S-04 — Obtain enough description evidence before qualification

**Implemented:** Description completeness, LinkedIn detail requests and bounded Rozee/post caches preserve qualification evidence. [Code](../scrapers/cache.py), [checks](../tests/test_cache_pagination.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-04.** Enable LinkedIn detail fetching for selected queries or add a supported detail-enrichment step after candidate deduplication. Use bounded detail-fetch budgets and cache by source ID/content version. Preserve descriptions and job-level fields returned by JobSpy. Extract Rozee detail text and recruiter post content only when accessible through the supported source path.

Add `description_status` such as full/snippet/missing/fetch_failed and evidence provenance. Hard reject obvious wrong occupations early to save enrichment requests, but do not permanently reject a plausible title solely for missing skills in an empty description. Failed enrichment should produce review/deferred evidence, not a claim of qualification.

**Acceptance:** a generic Software Engineer with no description cannot be high-confidence; LinkedIn detail behavior is covered by adapter fixtures; description retrieval has a measurable success rate and bounded request count.

## S-05 — Separate search targeting from listing work mode

**Implemented:** Independent local/remote query tracks preserve listing-derived work mode. [Code](../scrapers/jobspy_adapter.py), [checks](../tests/test_sources.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-05.** Define separate query profiles for Karachi local, Pakistan remote, and globally accessible remote discovery. Select locations and country parameters per source; do not replace every remote location with Karachi or assume one global country setting works everywhere.

Preserve query metadata as `search_track`/`query_id`. Derive `work_mode` from listing fields and explicit text, with values remote/on_site/hybrid/unknown and supporting evidence. Read JobSpy's structured remote field with null-safe conversion; check contradictory listing text and source reliability. Query terms are never proof of a vacancy's mode. Apply the same rule to recruiter posts.

**Acceptance:** a nonremote row returned by a remote query remains nonremote; a remote row returned by a local query retains that fact; unknown mode stays unknown; remote-query parameters no longer all point to Karachi.

## S-06 — Validate Karachi and remote-country eligibility independently

**Implemented:** Karachi and Pakistan-eligible remote rules distinguish explicit compatibility from unknown restrictions. [Code](../filtering/resume_filter.py), [checks](../tests/test_matching.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-06.** Normalize city/country/work-mode fields. Require explicit Karachi evidence for local on-site/hybrid delivery; country-only Pakistan goes to enrichment/review. Prefer a city match over a blacklist and use exact/normalized geography aliases, including accented forms. Neighborhood names supplement verified Karachi evidence instead of establishing the city by themselves.

For remote roles, model candidate location eligibility as allowed/excluded/unknown. Parse residency, work authorization, hiring countries, regional restrictions, and required time-zone overlap separately. Explicit Pakistan/worldwide eligibility can satisfy geography; US-only, EU-only, or similarly incompatible requirements exclude the role. A time zone is not a residency rule, and Pakistan location does not establish any particular citizenship or foreign work authorization.

Negated statements such as `no remote work` and `work from home is not permitted` override naive keyword presence. Missing restrictions mean unknown, not worldwide. Keep an optional review digest for promising unknowns so precision improvements do not silently erase recall.

**Acceptance:** Hyderabad/Pakistan-only local fixtures are not qualified as Karachi; US-only remote is excluded; negated remote is recognized; worldwide/Pakistan-eligible remote fits can pass; unfamiliar restrictions remain visible as uncertainty.

## S-07 — Preserve compensation and support a distinct USD remote track

**Implemented:** Salary evidence preserves disclosed currency and routes ambiguous/other-currency remote pay to review. [Code](../filtering/resume_filter.py), [checks](../tests/test_matching.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-07.** Extend `Job` with salary min/max, ISO currency, interval, raw salary text, evidence source, and confidence. Preserve source values and distinguish structured disclosures from description extraction or estimates. Do not infer USD merely from `$`, the source's default currency, employer location, or a conversion from PKR.

Maintain at least three statuses: USD confirmed, other currency confirmed, and undisclosed/ambiguous. For the remote-dollar goal, rank or route USD-confirmed eligible matches first. Keep unknown-pay matches in a clearly labeled optional review/digest track until the user chooses whether to exclude them. Local Karachi matches have an independent policy. A salary floor and whether listed USD denotes actual payment currency remain configurable decisions; a quoted USD amount alone does not verify contractual payment arrangements.

**Acceptance:** explicit USD, PKR, CAD, ambiguous `$`, and missing-pay fixtures remain distinct; amounts include their interval; Karachi jobs are not rejected just for PKR pay; alerts never claim verified dollar pay without supporting evidence.

## S-08 — Make query construction source-specific

**Implemented:** Source-specific parameters correct Indeed remote/date behavior and explicitly construct Google queries. [Code](../scrapers/jobspy_adapter.py), [checks](../tests/test_sources.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-08.** Introduce a small capability table and per-source parameter builders inside the existing adapter structure. For the inspected Indeed behavior, choose either remote filtering with local publication-date filtering, or date filtering with strict local work-mode verification; optionally run two budgeted query variants and merge. Do not send the incompatible combination and assume both filters applied.

Build explicit Google queries per track, including intended role/location/freshness terms; cover fallback behavior with fixtures for the selected version. Enable LinkedIn details deliberately and preserve returned metadata. Validate source/country combinations and report unsupported settings. Document behavior against the pinned release, since the installed implementation and upstream README can differ. [JobSpy parameters and limitations](https://github.com/speedyapply/JobSpy).

**Acceptance:** captured kwargs differ appropriately by site; Indeed remote/date semantics are enforced end to end; Google local and global-remote queries are intentional and testable; unsupported options are visible.

## S-09 — Repair Rozee extraction using verified listing evidence

**Implemented:** Rozee uses verified bootstrap fields and city ID, bounded pagination, caches and blocking/parse diagnostics. [Code](../scrapers/rozee_scraper.py), [checks](../tests/test_cache_pagination.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-09.** First capture a small, current, read-only sample of search and detail pages and confirm the meaning of the city filter. Store sanitized HTML fixtures. Prefer structured job data where present; otherwise use narrow verified card/anchor selectors, URL joining, and proper query encoding. Parse actual location, description, posting/expiry dates, employer, and experience. Use bounded pagination and deduplicate before detail fetches.

Distinguish legitimate zero results from non-200 responses, challenge pages, missing expected markup, and conversion failures. Cache details, honor source throttling, and stop that source after repeated blocking instead of increasing request volume. Do not claim an HTML strategy works until checked against real current samples; if the content requires unsupported rendering, report it as an unresolved adapter constraint.

**Acceptance:** the Lahore/five-year/old-date fixture no longer becomes a fresh Karachi role; fixtures cover nested wrappers, missing anchors, relative URLs, no-results pages, and blocking; unknown dates remain unknown.

## S-10 — Treat recruiter announcements as a separate evidence type

**Implemented:** Recruiter posts use host checks, saved cadence, independent explicit role sections and original-post provenance. [Code](../scrapers/post_roles.py), [checks](../tests/test_review_feedback.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-10.** Add an enable flag, configurable query families, result budget, and cadence. Validate parsed hostnames against LinkedIn hosts and expected post paths before fetching. Preserve full original titles and bodies; truncate only presentation text, after classification and identity assignment.

Model recruiter posts as leads unless a specific role and its requirements can be extracted. Where a post contains multiple roles, create role-level candidates with source-post provenance; otherwise keep a single review lead instead of applying one blended requirement set. Record whether recruiter email was observed in the actual post or merely a search snippet; do not present it as employer-verified without evidence. Use canonical post identifiers for identity.

**Acceptance:** long titles remain available to matching; mixed senior/junior announcements do not become one misleading role; config can disable this source; non-LinkedIn lookalike URLs are rejected; missing email is represented honestly.

## S-11 — Separate publication date, discovery time, and active status

**Implemented:** Publication, expiry, discovery and active/unknown/closed states remain separate evidence. [Code](../scrapers/base.py), [checks](../tests/test_sources.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-11.** Use timezone-aware `posted_at`, `first_seen_at`, `last_seen_at`, `expires_at` when supplied, and date provenance/precision. A search time limit is a discovery hint, not a verified publication timestamp. Replace old-year blacklists with date parsing linked to publication metadata; dates mentioned in eligibility text must not determine age.

Track active/closed/unknown independently of freshness. Treat 404/410 or explicit closure as negative evidence; 403/429, authentication redirects, challenge pages, and timeouts mean unverified. Check closure/detail endpoints within a budget. Configure publication lookback by track/source and permit honest first-seen handling where publication dates are absent. Never substitute a feed update timestamp for original publication without labeling it.

**Acceptance:** hiring 2025 graduates is not stale by itself; blocked posts are unverified; genuinely old/closed listings cannot be labeled fresh; all adapters use the same date contract; a source with a documented feed delay is not marked broken solely for that delay.

## S-12 — Improve retrieval coverage with measured query budgets

**Implemented:** Query-specific pagination, successful watermarks, budgets, yield reporting and longer zero-yield intervals improve coverage control. [Code](../scrapers/metrics.py), [checks](../tests/test_query_metrics.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-12.** Start with a focused role-family matrix derived from the résumé: Next.js/React/frontend, TypeScript/Node/full-stack, Python/Django/Flask/backend, and graduate/associate software. Include local and remote variants separately. Avoid expanding every synonym across every source at once.

Measure raw results, unique results, description completeness, eligible matches, and accepted matches per query. Use supported pagination/offsets selectively where additional pages add distinct relevant jobs. Track successful source/query watermarks with overlap and a bounded recovery window after failures; never advance a watermark after a failed fetch. Run less productive/broader queries less often.

Add per-source timeouts, request budgets, bounded retries with backoff/jitter, and a source pause after repeated blocking. Reuse sessions/cached details where supported. Preserve JobSpy's useful internal handling while adding application-level limits; do not claim that unlimited retries or proxies solve coverage. Bounded concurrency is optional only after source limits and state behavior are understood.

**Acceptance:** a plan summary reports intended query/request budget; fixtures show a later page can add a fit and repeated pages stop; failures do not advance watermarks; report distinct eligible matches per request and per minute before/after.

## S-13 — Define and enforce the shared job-data contract

**Implemented:** Null-safe normalization, isolated conversion failures and complete job round trips enforce the shared contract. [Code](../scrapers/base.py), [checks](../tests/test_sources.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-13.** Normalize pandas missing values with scalar-safe helpers before string/boolean conversion. Require nonempty title and valid HTTP(S) listing URL. Keep unknown company/location/date as unknown rather than `nan` or search-derived facts. Normalize optional description to a stable empty-string or explicit optional contract at the boundary, consistently used downstream.

Catch row conversion failures per row with source/query/field reason codes so valid later rows survive. Preserve structured remote, salary, source IDs, job level, direct application URL, and dates when available. Retain full text for evaluation; do not use the 200-character `to_dict()` preview as an audit snapshot. Extend the dataclass conservatively or introduce typed companion records within the current modules.

**Acceptance:** NaN/NaT/None/pd.NA/empty strings, malformed rows, and invalid URLs have defined outcomes; a bad row cannot discard a later valid row; null descriptions cannot crash matching or notification rendering.

## S-14 — Use stable source identity and merge duplicate evidence

**Implemented:** Native IDs, canonical URLs, explicit aliases and exact merging replace unstable title-only identity. [Code](../scrapers/base.py), [checks](../tests/test_sources.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-14.** Prefer a namespaced native source ID and canonical URL. Strip known tracking parameters while retaining identity-bearing query values such as Indeed's `jk`. Normalize host/path conventions carefully. Preserve links to every contributing source and direct employer URLs.

Deduplicate/merge before expensive enrichment and final matching, favoring complete trustworthy evidence. For cross-source candidates, require strong identity such as the same employer requisition or canonical destination; fuzzy title/company similarity alone must not merge distinct openings, locations, or requisitions. Preserve contradictory evidence for review.

Version identity/state changes and retain old aliases during migration so all jobs do not re-alert. Separate notification cooldown from listing active/freshness status. A new listing version can justify reevaluation without automatically justifying a new alert.

**Acceptance:** tracking variants deduplicate, distinct requisitions remain separate, richer descriptions survive, multi-location jobs are not accidentally merged, and migration does not clear current suppression history.

## S-15 — Acknowledge delivery per job

**Implemented:** Per-job acknowledgements and a persistent deferred queue prevent failed/unsent jobs from being marked delivered. [Code](../storage/tracker.py), [checks](../tests/test_delivery.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-15.** Make Discord/manager return a structured result containing delivered IDs, failed IDs, and failure/uncertain status per job. `main.py` must mark only confirmed deliveries seen. Capture pending jobs with sufficient normalized payload/evidence to retry independently of whether the source returns them on the next scrape.

Do not replace the boolean with `all_success` and keep batch marking: that would resend successful messages whenever another job fails. Persist successful acknowledgements and failed/pending records incrementally in the existing JSON state design. Version/migrate the old hash-to-timestamp file deliberately; retain `.github` file patterns for any new state files.

**Acceptance:** for two jobs returning 204/500, only the first is acknowledged; the second is retryable on the next run even if absent from newly scraped results; the first is not resent during ordinary retry handling. An empty batch performs no network call.

## S-16 — Check every webhook attempt and handle uncertainty explicitly

**Implemented:** Checked bounded retries distinguish confirmed, failed, uncertain and permanent delivery outcomes. [Code](../notifiers/discord.py), [checks](../tests/test_delivery.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-16.** Count success only after a checked successful response. Validate rate-limit delay values, bound attempts and total wait time, and retry appropriate transient failures. Permanent payload/authentication failures should produce actionable errors rather than repeated identical POSTs.

Use webhook `wait=true` when requesting a persisted message response/ID; capture it for acknowledgement. Discord documents that with `wait=false`, an unsaved message may not return an error. [Discord execute webhook](https://docs.discord.com/developers/resources/webhook#execute-webhook).

A network timeout after Discord accepted a request is ambiguous; local JSON cannot guarantee exactly-once delivery. Keep an uncertain outcome with attempt metadata and an explicit bounded retry policy. Prefer avoiding silent loss, while acknowledging a rare duplicate remains possible without a remote idempotency mechanism.

**Acceptance:** 429→500 is not delivered; 429→success is delivered once; exhausted retries remain pending/failed; permanent errors stop; ambiguous timeouts are not silently recorded as confirmed success.

## S-17 — Validate and safely render each Discord card

**Implemented:** Bounded payloads, mention suppression and per-job error isolation support cards and review digests. [Code](../notifiers/discord.py), [checks](../tests/test_review_feedback.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-17.** Build and validate each embed inside per-job error handling. Bound title, description, individual fields, footer, and aggregate length according to Discord's limits; supply safe placeholders for missing display data and validate listing URLs. Escape untrusted Markdown where needed and suppress unintended mentions in any message content. [Discord embed limits](https://docs.discord.com/developers/resources/message#embed-object-embed-limits).

Preserve useful remote geography such as `Remote — Pakistan eligible` or `Remote — eligibility unknown`, rather than replacing the source location with only `Remote`. Show salary currency/interval if known. Truncate presentation only, retaining full evidence for matching and audit.

**Acceptance:** long titles/company names, empty values, null descriptions, and special characters produce valid cards or isolated failures; one bad job does not abort later deliveries; payload validation is offline and sends no test messages by default.

## S-18 — Make JSON state durable and failures visible

**Implemented:** Validated atomic journals, previous-good backups and recovery-candidate export preserve history on failure. [Code](../storage/recover.py), [checks](../tests/test_state_recovery.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-18.** Write a temporary file in the destination directory, flush/close it, then atomically replace the state file. Validate the schema and timestamps on load, preserve a backup or diagnostic copy on corruption, and surface failures to the orchestrator. Create `storage_file.parent` for custom paths. Quarantine bad entries where possible instead of resetting all valid history.

Store acknowledged/pending/uncertain statuses separately, with timestamps and schema version. Make pruning explicit and safe; it must not delete pending deliveries just because notification history expires. Persist on state transitions and controlled shutdown. If production state cannot be read reliably, stop normal notification dispatch rather than treating the entire backlog as new.

**Acceptance:** simulated interrupted writes preserve a valid previous file; custom nested paths work; bad entries do not erase good ones; failed persistence changes run health; pending retries survive restarts; old-format migration preserves IDs/timestamps.

## S-19 — Serialize production runs and reconcile state commits

**Implemented:** Serialized default-branch execution and three-way state-only Git commits preserve concurrent code/history changes. [Code](../storage/sync_state.py), [checks](../tests/test_state_recovery.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-19.** Add one concurrency group for the production state writer, with `cancel-in-progress: false`. Ensure scheduled/manual runs writing the same state use that same group; prevent feature-branch evaluation from sending production alerts or sharing state. Set a realistic explicit job timeout and smaller source budgets. GitHub supports workflow/job concurrency controls. [GitHub concurrency documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

Ensure a queued run loads current state after acquiring execution, rather than assuming an older triggering commit includes all prior state commits. Keep the code revision under test identifiable. Make state push failure visible; merge/reconcile by stable ID and outcome instead of blindly overwriting JSON during a conflict. If pipeline health later becomes nonzero after partial delivery, still run a guarded state-persistence step for valid acknowledgements. Upload diagnostic artifacts on failure.

The Discord-send → remote-Git-commit crash window cannot be made exactly-once merely by adding concurrency. Preserve pending/acknowledged outcomes and provide reconciliation evidence; prefer a rare visible duplicate over silent loss.

**Acceptance:** overlapping scheduled/manual runs cannot send from the same stale state concurrently; a state-commit failure is distinguishable from scraper failure; the next run reads the last persisted state; feature-branch dry runs send nothing.

## S-20 — Pin and record the execution environment

**Implemented:** Exact dependency pins, environment reporting and independent Python 3.11 CI make execution reproducible. [Code](../requirements.lock), [checks](../.github/workflows/tests.yml). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-20.** Select and validate a dependency set on Python 3.11, then commit exact versions/constraints including reproducible transitive resolution. The locally installed JobSpy 1.1.82 is evidence for this audit, not an automatic recommendation to freeze it without validation. Upgrade intentionally through offline fixtures and a limited source smoke check.

Record Python and relevant package versions in each run artifact. Align development/evaluation with the workflow runtime, document installation, and cache using the lock/constraints content. Preserve the ability to roll back the dependency set alongside code.

**Acceptance:** a clean Python 3.11 installation resolves the documented versions; tests pass under that set; each run identifies its dependency baseline; upgrades have a reviewable diff and adapter evidence.

## S-21 — Report source health and meaningful process outcomes

**Implemented:** Source health, query yield/budgets, reason counts, reports and meaningful exit codes make failures visible. [Code](../main.py), [checks](../tests/test_pipeline.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-21.** Return source outcomes alongside jobs: success, valid_empty, partial, blocked, timed_out, parse_failed, or unsupported. Report query duration/count, rows rejected during conversion, missing-description share, freshness/eligibility uncertainty, filter reason counts, duplicate counts, and confirmed/pending/failed deliveries.

Define process health: valid empty searches are healthy; total source failure, required notification configuration missing, all intended deliveries failed, or state persistence failure should be actionable. Partial source failure can still deliver verified results but must be marked degraded. Publish a concise Actions step summary and bounded sanitized artifacts containing the stage funnel and versions.

Keep secrets, webhook URLs, authorization headers, and unnecessary contact information out of artifacts/logged exceptions. Preserve source listing links and decision evidence needed for debugging. Do not rely solely on DEBUG messages to explain rejections.

**Acceptance:** fixtures distinguish no jobs from blocked source, partial scrape from full failure, delivery failure from deduplication, and state-save failure from successful completion. Nonzero exit policies do not prevent saving valid acknowledgements from a partial run.

## S-22 — Build a benchmark that measures both bad alerts and missed jobs

**Implemented:** Offline tests, a fixed-date 54-case synthetic benchmark and capture-time feedback evaluation support regression checking. [Code](../evaluation.py), [checks](../tests/test_matching.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-22.** Add meaningful offline tests around the reproduced failures, plus adapter HTML/DataFrame fixtures and per-job delivery/state tests. Move the live scratch search behind an explicit entry point or outside automatic test collection. CI tests must not query job boards or send notifications.

Build an initial candidate benchmark of roughly 50–100 manually reviewed listings covering good fits, poor fits, and uncertain cases across sources/tracks. This is a proposed sample size, not evidence already collected. Include the user's manually found good jobs with capture date, URL, full requirements, publication window, location restrictions, and relevance labels. No such examples were supplied for this audit.

Separate development/tuning examples from held-out evaluation. Label qualification and listing-data sufficiency independently; one person can review a first version, with disputed cases left uncertain. Store only the job evidence needed for evaluation and keep candidate contact data out.

Measure:

- **Alert precision:** relevant reviewed alerts / all reviewed alerts, with unknowns reported separately.
- **Precision at K:** relevant jobs among the first K ranked results, using a fixed K such as 10 when enough candidates exist.
- **Known-positive discovery recall:** manually found eligible benchmark jobs rediscovered / eligible known positives in the same source/time/query scope. This is not recall across every job on the internet.
- **Filter recall:** labeled relevant jobs retained / labeled relevant jobs actually retrieved; distinguishes search misses from filter misses.
- **Eligibility error rate:** alerts with explicit incompatible location/work authorization / reviewed alerts.
- **Freshness and reliability:** publication-to-discovery lag where dates are known, duplicate-alert rate, description completeness, source success rate, and confirmed delivery rate.

Trace each missed manual example through retrieval → normalization → enrichment → qualification → deduplication → delivery. Do not count a closed/previously notified/out-of-window listing as a scraper miss without checking scope.

**Acceptance:** all reproduced defects have regression fixtures; zero explicit wrong-city/restricted-country cases pass the controlled suite; held-out precision improves without an unexplained drop in known-positive/filter recall; every retained/rejected job has reasons. Choose numerical production targets only after a baseline exists. A proposed rollout observation window is 7–14 days, covering multiple source cycles.

## S-23 — Make configuration truthful, validated, and documented

**Implemented:** Nested validated configuration, active source/policy settings and updated README replace misleading controls. [Code](../config.py), [checks](../tests/test_pipeline.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-23.** Define a schema for profile, query tracks, source options, freshness, matching thresholds, notification routing, and state. Validate types/ranges/source names at startup with field-specific errors. Use a deliberate nested-default strategy or fully explicit validated sections; test partial overrides.

Wire all documented settings into the active path. Consolidate or retire the unused filter after behavior migration; remove misleading `experience_levels` or implement its actual semantics. Add recruiter-source enable/cadence settings. Update README to state the enabled sources, Discord-only implementation, correct local commands, actual configuration keys, and repository-relative links. Document that current dry run still scrapes the network; add an offline replay mode for evaluation if needed.

**Acceptance:** invalid nested YAML fails before scraping; toggling a source works; every documented tuning field demonstrably changes active behavior; no README claim suggests Telegram is implemented.

## S-24 — Rank qualified candidates and explain each alert

**Implemented:** Constraint-first ranking, explanations, optional review digests and job-ID relevance feedback support usable alerts. [Code](../feedback.py), [checks](../tests/test_review_feedback.py). The original design and acceptance criteria below remain as reference; production gates are tracked separately.

**Resolves I-24.** Apply ranking only after mandatory role/geography/experience constraints. Return a structured decision with tier, score, confidence, matched evidence, gaps, and reason codes. Start with an interpretable weighted approach rather than requiring an external model.

An initial experimental fit score could weight role family 25%, relevant mandatory skills 40%, experience fit 25%, and education 10%. These are tuning hypotheses, not calibrated probabilities. A high score cannot override an explicit incompatibility. Evidence completeness remains a separate confidence value; duplicated aliases and repeated words cannot inflate it. Use freshness, verified USD pay for the remote track, and confirmed neighborhood preference as separate ordering/routing factors rather than disguising them as technical fit.

Order strong eligible matches first, then optionally send a bounded review digest for plausible but incomplete/stretch cases. A notification cap must defer unsent jobs in state, not mark them seen. Show concise rationale such as `React + TypeScript + Node internship fit; 0–1 years; Karachi confirmed`, plus important uncertainty or missing requirements. The user should be able to provide simple relevant/not relevant feedback linked to a job ID without requiring a new hosted application.

**Acceptance:** a demonstrably strong résumé match ranks above a generic weak-evidence listing; strong scores never rescue US-only or non-Karachi on-site incompatibility; rationale points to real job/profile evidence; deferred jobs remain pending; neighborhood badges do not substitute for qualification.

## Optional source expansion after core fixes

These are adapter candidates, not integrations built or live-tested in this audit. Keep the same `Job` normalization, eligibility checks, ranking, and Discord delivery for every source. Source-specific cadence can run inside the existing three-hour workflow using persisted fetch timestamps. Verify each provider's current format and permitted use before implementing its adapter.

| Candidate | Proposed role | Constraints and evidence |
| --- | --- | --- |
| Remotive public API | First remote API candidate: structured listings with descriptions and candidate-location information | Public feed is delayed 24 hours; provider recommends at most four fetches daily, so do not poll on all eight daily workflow runs. Preserve attribution and original links; verify current redistribution restrictions for the intended destination. Salary/location fields still need validation. [Provider API documentation](https://github.com/remotive-com/remote-jobs-api). |
| We Work Remotely RSS | First remote feed candidate, using frontend/backend/full-stack/programming categories | Provider publishes public all-jobs and category feeds and requires attribution back to WWR. RSS availability does not establish Pakistan eligibility, junior seniority, or salary disclosure. [Provider feed documentation](https://weworkremotely.com/remote-job-rss-feed). |
| Selected employer Greenhouse boards | Direct employer coverage for a curated set of remote-friendly or Karachi employers | Public Job Board GET endpoints do not require authentication. Each employer board token must be configured; this is not a global search API. Preserve actual job content and distinguish update timestamps from publication dates. [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html). |
| Selected employer Lever boards | Direct employer coverage using configured company boards | Published postings API includes workplace type and optional salary ranges. Board discovery and country eligibility remain separate tasks; the feed is not a guarantee of worldwide hiring. [Lever Postings API](https://github.com/lever/postings-api). |
| Arbeitnow | Lower-priority experiment if measured Pakistan-eligible yield supports it | Provider documents a public API and Germany/Europe-oriented jobs. Do not prioritize a remote label over location restrictions or assume this feed offers dollar-paying Pakistan opportunities. [Provider API article](https://www.arbeitnow.com/blog/job-board-api). |
| Existing LinkedIn/Indeed/Rozee and selected Karachi employer career pages | Primary Karachi local coverage | Repair current adapters first. Add employer-specific adapters only after confirming a usable public feed/API/page format and relevant actual vacancies; no new local platform is asserted to have a tested API here. |

Recommended expansion sequence: a small Remotive pilot and WWR feed pilot, then curated employer boards based on observed eligible yield. Keep local queries running independently so remote expansion does not crowd them out. Other platforms can be evaluated later using the same evidence and request-budget criteria.

For each pilot, capture response fixtures and measure distinct Pakistan-eligible junior matches, disclosed USD share, freshness lag, duplicate overlap, and request cost. Disable or reduce cadence for low-yield sources. More raw jobs is not the success criterion.

## Rollout and remaining decisions

Implement the delivery corrections first, then evaluate new source normalization and matching in offline replay/shadow mode against the same saved jobs. Shadow runs must use separate state and send no Discord messages. Inspect accepted, rejected, and unknown samples before enabling the new policy; expand one source at a time after the core benchmark improves. Keep configuration/profile/matcher versions in state and artifacts so changes can be compared or rolled back without wiping delivery history.

Before setting strict user preference gates, resolve: minimum salary and meaning of dollar pay, acceptable time-zone overlap, internship/contract interest, one-year stretch-role tolerance, whether Karachi hybrid is desired, and whether neighborhood preferences are real. None of these questions blocks correcting the demonstrated false remote labels, substring collisions, delivery loss, or missing-data handling.

Future production verification needs recent Actions logs/version output, a bounded sample of current source responses, and manually found matching jobs. The initial audit intentionally makes no percentage claim about current accuracy and no promise of exhaustive LinkedIn/Indeed coverage.


## Implementation continuation — 2026-09-08

Implemented bounded Rozee pagination/caching, recruiter cadence/role sections, per-query yield and zero-yield intervals, validated backup recovery exports, state-only commits on the latest remote tree with bounded retries, optional review digests, and local feedback-to-benchmark commands.

Recovery exports a separate candidate because older state cannot prove which later Discord messages succeeded. State reconciliation uses the initial checkout as its baseline, preserving concurrent confirmations and unrelated code while respecting retention and queue retirement. Tests simulate a branch advance during push using temporary local repositories only.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for validation and remaining boundaries. Production source checks, real labeled examples and preference decisions remain necessary for the original production acceptance gates.
