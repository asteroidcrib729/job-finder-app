# Production verification - October 27, 2026

## Assessment

The reorganized application completes discovery, matching, Discord delivery and Git state persistence on the real production runner. Full coverage across all configured sources is not established: this run had partial LinkedIn/Google failures and unavailable recruiter-post search providers. Those conditions are visible as coverage warnings, not healthy empty searches. No source-blocking workaround or matcher-policy change was introduced during verification.

## Local and packaging checks

- Python 3.14.7 and the locked uv environment synchronized successfully; installed dependencies were consistent.
- All 91 offline regressions passed, covering matching, source parsing, isolated workers, delivery failures, retries, queueing, configuration paths, corruption recovery and concurrent Git reconciliation.
- Ruff, Pyrefly (zero errors with 17 existing suppressions), interpreter compilation and Actionlint passed.
- The 54-case synthetic benchmark reproduced all expected tiers. This is regression evidence, not measured production precision/recall.
- Fresh wheel and source builds passed. An independently installed wheel imported and loaded external configuration from a temporary working directory and executed CLI help. Archives excluded local personal files and runtime configuration/state.
- The dependency advisory audit found no known vulnerabilities or adverse project statuses in 41 packages at the time of the check.
- Production delivery/discovery journals validated. Protected hashes confirmed that local tests did not alter production state.

## Live search and notification

The owner explicitly authorized live searches and Discord job notifications. [Manual production run 40503191316](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40503191316), dispatched on `9fc5b6396742e100e379db1c8574739978bddd7f`, passed using normal production settings (`dry_run=false`, `verification_sample=false`). Its application phase ran from 12:22:22 to 12:23:43 UTC (17:22:22 to 17:23:43 Asia/Karachi).

| Result | Count |
| --- | ---: |
| Raw source rows | 246 |
| Unique jobs | 170 |
| Qualified | 4 |
| Review | 3 |
| Rejected | 163 |
| Eligible jobs previously notified | 6 |
| New jobs delivered | 1 |
| Failed or uncertain deliveries | 0 |
| Pending jobs after delivery | 0 |

The new notification was **Software Engineer at 10-xer, Karachi**, an Indeed listing dated October 27. The captured description explicitly describes a junior role with basic programming/database knowledge and internship or project experience preferred. That evidence is consistent with the profile's junior/internship background; the score is an ordering score, not a probability of hiring or an independently verified employer claim.

Discord acknowledged message `1564615577430138971` on the first attempt. [Read-only diagnostic 40503571503](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40503571503) subsequently returned HTTP 200 for both the webhook and message, confirmed the expected server and channel, and confirmed that the message exists. [Open the delivered Discord notification](https://discord.com/channels/1529900907330928803/1529900918630518905/1564615577430138971).

The first receipt-check dispatch, [40503516216](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40503516216), used an incorrect operator-supplied message ID (`0`) and failed. The corrected dispatch above used the actual receipt and passed. This diagnostic input error was separate from the successful production delivery; neither read-only diagnostic sent another message.

## Source coverage

| Source | Observed result |
| --- | --- |
| Indeed | Three successful Karachi queries returned 21 rows. |
| LinkedIn vacancies | Three partial queries retained 65 rows; description requests reported `blocked,upstream_warning`. |
| Google Jobs | Three queries reported `upstream_error`, returning no rows. |
| Rozee.pk | Eight successful listing-page queries returned 160 rows. Bounded two-page traversal was exercised. |
| LinkedIn recruiter posts | One attempted query failed with `search_providers_unavailable`. |
| Optional remote feeds | Disabled by existing configuration; not exercised live. |

The adapter paused sources after repeated failures. Successful-query cadence also left some queries not due; the run did not attempt every configured keyword/track. Missing full descriptions affected 36 unique jobs. The application health was `degraded`, operational outcome `warning: partial_discovery_coverage`, and the workflow succeeded because usable primary discovery, delivery and persistence worked.

These classified outcomes identify affected integrations, not a confirmed root cause inside the upstream services. Continuous source availability, complete remote retrieval and production precision/recall remain unproven. No delivery history was reset to force a notification.

## Persistence, replay and security

State commit `728a17abf45949891a1ea451b1e11103fdf9fc4a` changed only the four production JSON state/backup files. Its author is Faraz Hussain with the repository-linked noreply address; its committer is the GitHub Actions bot with the configured bot noreply address. The delivered job's message receipt is present remotely, the job is marked seen and it is absent from pending delivery.

An offline replay of the production artifact reproduced every decision for all 170 unique jobs. It generated no deliveries, preserved production state hashes and found all seven eligible jobs already notified after the live run, including the new delivery. This confirms repeatable evaluation and suppression of that receipt, not a guarantee of exactly-once delivery across every crash/network scenario.

[Fresh security run 40503441885](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40503441885), on state commit `728a17a`, passed the dependency audit and CodeQL analysis. CodeQL reported zero findings and no analysis error/warning for that exact commit.

Raw reports, replay output and protected-state hashes remain Git-ignored under `.local/output/verification-2026-10-27/`. The production artifact is retained by Actions for 14 days. The committed record contains summarized evidence only; no webhook credential, resume contents or raw report was added.
