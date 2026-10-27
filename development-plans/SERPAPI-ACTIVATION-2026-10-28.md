# SerpApi activation and quota protection

The owner supplied `SERPAPI_API_KEY` through repository Actions secrets and authorized activation, testing and credit protection. No key was read from GitHub or written into source, reports or documentation.

## Configuration and controls

Google Jobs now uses `google_provider: serpapi`, `google_mode: enabled`, one search attempt per run, a maximum of 120 attempts per rolling 31 days, six-hour spacing between attempts and a reserve of 100 provider credits. Due keyword/track queries rotate through the existing least-successful-query scheduling, covering Karachi and global remote tracks over successive permitted runs. Explicit city/country/language parameters avoid relying on proxy location. Google Jobs returns up to ten results per page; no extra pages or automatic search retries consume additional credits.

Before each billable request the app checks the free [Account API](https://serpapi.com/account-api). Only allowlisted numeric counters survive parsing. It refuses to search if the active account balance cannot be verified, if the provider's hourly limit is reached, or if the minimum remaining plan/total credits is at or below 100. It never buys credits or changes account plans. The local rolling cap counts all attempts, even failed or timed-out requests, conservatively.

`data/serpapi_usage.json` records random reservation IDs and UTC timestamps only. A local exclusive lock covers the read/check/reserve transaction. The atomic, flushed reservation precedes the search HTTP request. Invalid, future-dated, locked or unwritable state blocks the search. Historical entries older than 62 days can be trimmed; active-window reservations are preserved during three-way Git reconciliation, including concurrent additions and attempted deletions. Provider balance checking supplies an additional guard if a hosted runner dies before its local journal can be pushed.

Normal scheduled/manual workflows serialize through the existing production concurrency group. Manual refresh and verification sample do not bypass quota controls. Live dry runs consume credits too: they persist quota history and backup through `sync_state --scope quota`, while job discovery/delivery files remain untouched. Offline replay never calls SerpApi or writes quota history. Recovery artifacts include the quota journal/backup after persistence failure.

The 120-attempt cap leaves 130 of a 250-search plan unused by this app when it is the only consumer. The account reserve also responds to already-used credits from other clients. Separate clients using the same account can still spend independently; this app cannot enforce their behavior. Account checks are not counted toward monthly search credits, according to the provider documentation. Calendar-month boundaries do not reset the rolling app cap; provider billing-cycle balance is checked independently.

## Verification

Offline regressions cover pre-request durable reservation, timeout accounting, restart/month-boundary spacing, rolling cap, provider reserve/hourly limits, account failure/redaction, corrupt/future/locked/unwritable state, overlapping local requests, per-run caps, concurrent Git union without refunds, old-entry expiry, query rotation, refresh throttling and quota-only Git persistence. Existing matching decisions and delivery suppression remain unchanged.

Local and hosted acceptance results are recorded below as verification completes. Secrets and raw account responses remain excluded from evidence.

Local validation passed: 152 offline tests, 54/54 synthetic matching decisions, Ruff, Pyrefly (zero errors, 16 existing suppressions), compilation, dependency consistency (41 packages), Actionlint, package builds and archive checks. The final policy-skip change also passed all 24 targeted API/quota tests. Expected quota/cadence skips appear in quota telemetry and notes rather than being mislabeled as failed provider searches. No dependency/lockfile changes were needed.

### Hosted acceptance

Published code SHA `6aa69a3104ad5752f1e5415bad23b30ec497f08a` passed [Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40568543664) and [security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40568543095). The exact CodeQL analysis reported zero findings, no analysis errors/warnings, and the dependency audit passed.

| Evidence | Production run | Immediate manual refresh |
| --- | --- | --- |
| Successful workflow | [40568583326](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40568583326) | [40568590162](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40568590162) |
| Mode | Live, normal cadence/delivery | Dry run with refresh and verification sample enabled |
| SerpApi search attempts | 1 | 0 |
| Google outcome | Success, two rows converted, no invalid rows | Six-hour minimum interval; intentional skip |
| Quota journal reservations | 1 | Still 1 |
| Provider balance before search | 250 | Not requested because local spacing already blocked searching |
| New Discord deliveries | Five review jobs in one digest: four LinkedIn, one Google | None |
| Job history persistence | Production discovery/delivery state and quota saved | Quota-only scope; no new commit or job-history changes |

The new Google results both had full descriptions; one was review-tier and one rejected. This establishes live API access and normalization, not measured production matching accuracy. The production run returned 48 unique jobs, two qualified, five review and 41 rejected; the two qualified jobs were already notified. It fetched 24 fresh LinkedIn descriptions and completed three reappearing cards from cache, reducing the saved backlog from 45 to 21 and raising the next detail budget from 24 to 28. The dry-run report's smaller in-memory backlog was deliberately not persisted.

Production state commit `ea79bedecf520eaf081af8cf2b215179b198d791` used the required Faraz Hussain author and GitHub Actions bot committer identities. The quota ledger/backup contain only reservation metadata. Validation confirmed all five new delivery IDs were acknowledged with receipts and none remained queued. [Read-only Discord diagnostic 40569166375](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40569166375) retrieved the digest with webhook/message HTTP 200 from the expected server and channel. This proves message existence, not phone-client notification display.

The refresh report explicitly recorded `search_attempts_this_run: 0`, `attempts_in_window: 1` and `serpapi_minimum_interval`. No Google request was issued. Its next permitted attempt was October 28 at 06:23 Asia/Karachi; the unchanged three-hour workflow schedule may run it later. One reservation counts conservatively as one attempted search; no post-search balance check was used to claim exact provider billing.

Both hosted runs succeeded with visible partial-coverage warnings from other sources. Rozee returned HTTP 403; LinkedIn listing metadata and some recruiter search responses remained partial/unverified. Google Jobs is now live-verified, while full source availability and held-out matching accuracy remain separate acceptance work.
