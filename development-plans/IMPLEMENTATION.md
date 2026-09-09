# Implementation and validation record

**Production incident update (2026-09-08):** Both initial production runs completed discovery/state persistence but were marked failed because partial source warnings triggered exit 2 and the workflow escalated that to exit 1. The operational health policy, Google diagnostic classification and recruiter search handling are corrected. See [production incident analysis](PRODUCTION-INCIDENT-2026-09-08.md) for evidence, fixes and validation. Prior statements of code completion did not establish live-source acceptance.

Implementation dates: 2026-09-07 and 2026-09-08. The user subsequently authorized committing and pushing the completed implementation and updated records to main. No production workflow was manually dispatched and no Discord test message was sent during implementation. Git integration tests use disposable local repositories and local bare remotes. Repository history records the publication commit; live production acceptance is tracked separately.

Python, JobSpy/custom adapters, GitHub Actions, JSON state, and Discord remain the architecture. Implemented behavior and offline tests do not establish production accuracy or continuous source availability.

## Core implementation

- Versioned résumé profile separates demonstrated internship skills from listed skills and professional tenure.
- Matcher 2.1 checks occupations, contextual experience, mandatory skill groups, education, Karachi/remote eligibility, compensation, publication/closure evidence and confidence before ranking.
- Normalized jobs preserve complete descriptions, identity, aliases, dates, restrictions, salary provenance, query metadata and explanations.
- Source-specific JobSpy queries have bounded workers, query/depth/time budgets, successful watermarks and source pauses.
- Individual delivery acknowledgement, retry/deferred journal, atomic writes, replay, fixed-date evaluator, pinned dependencies, CI and source-health reports are implemented.

## Continuation on 2026-09-08

- Rozee follows bounded bootstrap pagination, stops repeated pages and blocked detail requests, converts HTML descriptions to text, and reports failed details as partial.
- Rozee/post details use six-hour, 200-entry caches in discovery state. Current Rozee listing facts override cached descriptions; expired evidence never substitutes for a blocked request.
- Rozee/post searches have stable query identities, cadence and successful watermarks. JobSpy uses configurable longer intervals after successful queries with zero qualified/review yield.
- Per-query reports measure unique candidates, qualification tiers, description completeness and yield per request/minute; planned request/time budgets are included.
- Explicit recruiter role sections become independent candidates with stable identities and role-specific requirements/location. Original title/body remain available as provenance.
- Optional review digests contain up to five candidates. One confirmed digest produces one atomic acknowledgement update for the group. Qualified alerts stay individual.
- Local feedback records relevant/not_relevant/uncertain labels by job ID and exports capture-time evaluation cases without changing delivery history.
- Both state files keep validated previous backups. Recovery exports a separate candidate, never silently replacing corrupt delivery history with older acknowledgements.
- Workflow state commits reconcile concurrent changes onto the latest remote tree, retry branch advances, preserve unrelated code and retention pruning, and retain recovery artifacts after persistent failure.
- Actions receives one final step summary.

## Live evidence from 2026-09-07

Rozee public search HTML had loading placeholders and no JSON-LD but contained a public **apResp** JSON object. The parser extracted **20 jobs, 20 full descriptions, zero conversion failures** from a captured broad Python search; locations spanned six distinct strings.

Public city metadata identified **Karachi as 1184**, replacing the incorrect old 1592 path. A corrected read-only request returned **seven listings, all Karachi**. Publication uses created_at, expiry uses applyBy, and hidden/search-index salary values are not displayed.

Later Rozee-only application dry runs received **HTTP 403**, correctly reported as blocked/degraded without notifications or state writes. Captured-page parsing success and later blocking are separate observations. The new pagination path is covered offline; live second-page behavior is not verified.

Raw pages/bundles remain ignored in .cache. Repository fixtures are synthetic/sanitized. No additional live source probing was performed on 2026-09-08.

## Issue status

| Issue | Implemented | Remaining boundary |
| --- | --- | --- |
| I-01 | Structured profile, education/internship evidence | Profile updates remain reviewed inputs. |
| I-02 | Aliases, occupations, mandatory groups | Real-job calibration and further language coverage. |
| I-03 | Contextual ranges/minima/months/written numbers | Complex alternatives require review. |
| I-04 | LinkedIn details, full Rozee text, bounded Rozee/post caches | JobSpy internal LinkedIn enrichment still precedes application deduplication. |
| I-05 | Separate query tracks and listing-derived mode | Contradictory evidence requires review. |
| I-06 | Karachi and remote-country eligibility | Additional region/time-zone expressions need real fixtures. |
| I-07 | Salary provenance and currency routing | Salary floor and contractual pay preferences need user decisions. |
| I-08 | Indeed parameter correction and explicit Google/LinkedIn queries | Live LinkedIn/Indeed/Google validation outstanding. |
| I-09 | Bootstrap parser, corrected city, pagination, caches, blocking pause | Later live requests blocked; live multi-page validation outstanding. |
| I-10 | Configurable discovery, role sections, provenance, cadence | Ambiguous announcements remain unsplit leads. |
| I-11 | Publication/expiry and closure/unknown states | Closure checks remain source-specific. |
| I-12 | Focused queries, budgets, yield, zero-yield cadence, watermarks | Tune intervals/depth using measured production yield. |
| I-13 | Null-safe normalization, isolation, full round trips | Future adapters must follow the contract. |
| I-14 | Native/canonical identity and legacy aliases | Unknown historical variants cannot be recovered; no fuzzy merge. |
| I-15 | Acknowledgements and persistent pending queue | Discord/Git crash window can still duplicate alerts. |
| I-16 | Checked bounded retries and uncertainty | Ambiguous deliveries may duplicate on retry. |
| I-17 | Bounded cards/digests and isolated payload errors | Discord tested with mocks only. |
| I-18 | Atomic writes, validated backups, recovery export | Reconcile later receipts before restoring; permanent failures need repair. |
| I-19 | Default-branch guard, serialization, three-way state pushes | Persistent Git/authentication failures require the recovery artifact. |
| I-20 | Exact dependency pins and environment recording | Linux/Python 3.11 resolved; local execution used Windows/Python 3.12. |
| I-21 | Query health/yield, budgets, reports, exit codes | Empty JobSpy results still depend on library diagnostics. |
| I-22 | Offline suite/evaluator and 54 synthetic cases | Real held-out examples and production precision/recall baseline needed. |
| I-23 | Active validated settings, consolidated filter, README | Optional preference gates need user input. |
| I-24 | Ranking/reasons, review digest, deferred cap, feedback CLI | Relevance labels remain user input; no hosted feedback service. |

## Validation

- **73 offline tests passed**, including 54 parameterized matching cases.
- Evaluator: **54/54 expected tiers**, synthetic regression agreement, not production accuracy.
- Local dependency check: no broken requirements.
- Earlier Python 3.11/Linux wheel-resolution dry run succeeded with all **38 distributions** pinned. Actual Linux CI execution remains outstanding.
- Replay tests assert no source/HTTP calls or delivery/discovery/backup writes.
- Source tests cover query parameters, malformed rows, repeated/later pages, blocked details, cache expiry/isolation, role identities, location/date preservation and remote-feed evidence.
- Delivery/state tests cover retries, uncertain outcomes, partial delivery, digest group persistence, save-failure stops, migration, backups, corrupt-history protection, concurrent acknowledgements, retention pruning and pending retirement.
- A real local Git integration test races another writer during push, verifies retry success and preserved concurrent code/state, and confirms the original checkout/index are unchanged.
- Feedback tests preserve capture-time evaluation and reject unknown job IDs.

## Rollout and remaining decisions

1. Run the suite under the deployment environment and inspect real dry-run qualified/review/rejected samples.
2. Publish through the normal repository workflow, preserving production history, as authorized by the user; inspect the resulting CI before assessing scheduled production behavior.
3. Inspect initial Actions source/delivery reports and compare manually found matches through retrieval, matching, deduplication and delivery.
4. Collect held-out user labels separately from tuning examples. Good-fit URLs were requested but have not been supplied.
5. Pilot optional Remotive/WWR feeds individually and measure Pakistan-eligible junior yield.
6. Tune cadence, page depth and language parsing from measured misses.

As of September 9, the owner enabled notifications.send_review for scheduled and ordinary manual runs. Unknown remote eligibility/pay and unknown publication dates remain labeled review cases, now delivered in digests within the shared 20-job cap. Review delivery never overrides explicit rejection. See [the filtering assessment](FILTERING-REVIEW-2026-09-09.md) for current validation and remaining accuracy concerns. Salary floors, time-zone overlap and stricter preference gates remain explicit user decisions.
