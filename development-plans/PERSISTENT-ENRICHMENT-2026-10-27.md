# Persistent enrichment and source coverage

## Scope and root causes

The previous bounded description pass enriched only cards returned during the current search. A successful listing search advanced its cadence even when most cards lacked descriptions. Those unfinished cards were lost between runs; the existing description cache retained completed work only. A fixed 12-request budget also left healthy sessions underused. Recruiter fallback could consume its global attempt budget on early queries and repeatedly favor the same unavailable backend.

The architecture and qualification policy remain unchanged. These changes improve retrieval and evidence completion; they do not establish measured production precision/recall or guarantee every provider's availability.

## Implemented behavior

- Persist up to 500 unfinished LinkedIn cards in versioned discovery state for 72 hours, with four attempts per card. Restore work even when listing queries are not due. Clear seniority, occupation, closure and age failures skip requests; incomplete descriptions alone do not exclude plausible cards. Junior/relevant roles take priority, older work ages into priority, and tracks alternate.
- Start with 16 shared detail requests; grow by four after a fully successful budget-sized cycle with backlog, up to 36. Blocking/timeouts/repeated failures halve the next budget, with a minimum of four, and double pacing up to ten seconds. Base pacing is two seconds, timeout eight seconds, queue time budget 180 seconds, cache six hours and retry cooldown three hours. No proxy rotation, CAPTCHA automation or authenticated-session harvesting was added.
- Persist per-job retries, terminal closure/exhaustion, adaptive control and telemetry. Validate before network work; reconcile concurrent queue additions, completions and deletions. Existing production delivery history is preserved. Dry run changes neither delivery nor discovery state.
- Use an explicitly supplied Greenhouse/Lever application URL as a fallback via fixed public GET API hosts. Require matching posting ID, title and published URL; never guess a company page. Fallback shares the detail request cap and may operate during a LinkedIn-specific cooldown.
- Refresh existing pending deliveries with the latest listing evidence before reevaluation. Newly closed or rejected jobs cannot be dispatched using an older queued payload.
- Share recruiter attempts across six focused queries under a 12-attempt cap; rotate queries/backends and prefer a previously successful backend. Preserve per-provider cooldowns and unverified empty-result classification.
- Add an optional Google Jobs SerpApi adapter with fixed endpoint, sanitized errors, credential-free reports/state, response-contract checks, invalid-row isolation and a two-query run cap. Default remains the JobSpy daily recovery probe. SerpApi requires owner-provided credentials and explicit `google_provider: serpapi`; no live account was configured or subscription purchased. `probe` further limits calls to one per day. It has its own probe identity, so an earlier failed JobSpy probe cannot suppress it.
- Add `--refresh-searches` and the equivalent manual workflow input. Listing intervals are bypassed within normal request limits; feed/probe/detail cooldowns and delivery suppression remain. Verification samples still cap details at 12/90 seconds and deliveries at three.

## Validation and acceptance

Local and hosted results are recorded below as they complete. New regressions cover persisted queue restart with zero repeated listing searches, healthy growth, blocking/backoff, expiry, bounds, aging, retry/exhaustion, concurrent merge, cache reuse, duplicate cards, closed-delivery retirement, exact Greenhouse/Lever identity, shared request caps, employer fallback during LinkedIn cooldown, recruiter fairness/rotation, dry-run state immutability and the optional API's contract/credentials/quota errors.

Local validation passed on Python 3.14.7: **136 offline tests**, **54/54 synthetic decisions**, Ruff, Pyrefly (zero errors, 16 targeted suppressions), interpreter compilation, dependency consistency (41 packages), Actionlint and `git diff --check`. Wheel and source distribution built successfully; archive inspection confirmed the new modules are included and `.local`, `.venv` and resume PDFs are excluded. No dependency or lockfile changes were required.

Live source availability, Discord receipt retrieval and state persistence require separate hosted evidence. Employer fallback and SerpApi readiness must not be reported as live coverage unless those paths are actually exercised.

### Hosted acceptance on `603b4ea`

[Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40563505048) and [security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40563505013) passed. CodeQL's analysis for the exact full code SHA `603b4ea80b217e2d02992eee72cdbf9020ad5d85` reported zero results and no analysis errors/warnings. The dependency audit passed.

| Evidence | First production refresh | Follow-up with normal cadence |
| --- | --- | --- |
| Successful workflow | [40563530692](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40563530692) | [40564183004](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40564183004) |
| Raw / unique jobs | 482 / 248 | 43 / 43 |
| Qualified / review / rejected decisions | 7 / 20 / 221 | 2 / 4 / 37 |
| Usable LinkedIn listing searches | 24 | 1 repeated partial query; successful prior queries were not due |
| Usable Indeed listing searches | 16 | 0; not due |
| New successful LinkedIn detail requests | 16 | 20 |
| Cache completions | 6 | 3 reappearing cards |
| Total completion events | 22 | 23 |
| Saved pending enrichment cards | 65 | 45 |
| Saved jobs recovered without reappearing in searches | 0 | 20 |
| Adaptive current -> next request budget | 16 -> 20 | 20 -> 24 |
| Pacing | 2 seconds | 2 seconds |
| New Discord deliveries | 2 review jobs in one digest | 2 different review jobs in one digest |
| Delivery errors / uncertain outcomes | 0 | 0 |

The follow-up restored all 65 pending cards, completed 20 from saved work and retained 45. Three current cards were re-enqueued and completed from cache; completion-event totals therefore must not be presented as 45 distinct newly fetched descriptions. Together the runs fetched **36 fresh LinkedIn descriptions**. The follow-up did repeat one listing query whose upstream warning had prevented its success watermark; it was not a fully search-free live run. The separate offline restart test establishes the zero-search case.

The first refresh excluded 130 clearly ineligible cards from description requests. The normal cadence run also respected feed intervals and Google probe timing. Recruiter discovery used all 12 attempts across multiple queries/backends, with Yahoo returning results in both runs; other engines frequently reported unverified empty responses. Newly found stale/unqualified leads were still rejected by the unchanged matcher. Job counts/tiers from different snapshots are not a controlled accuracy comparison.

Automated state commits `0962de1990dd0875ae504d4f03e5c4be9cd0231a` and `3469f07d151202694e1d2558b78d9cdadffab627` persisted validated queue/adaptive state and delivery receipts. Both used author Faraz Hussain with the account-linked noreply address and committer github-actions[bot] with its bot noreply address. Local validation confirmed four distinct acknowledged jobs, no duplicate delivery between runs and none of those jobs remaining pending.

Both digests were independently retrieved by [read-only diagnostic 40564471387](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40564471387) and [follow-up diagnostic 40564668991](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40564668991): webhook and message HTTP 200, expected server and channel. These checks establish message existence in the configured destination, not whether every Discord client displayed a phone notification.

Both production workflows succeeded with visible partial-coverage warnings. Rozee returned HTTP 403 in both; Brave/DuckDuckGo discovery was frequently unverified. Feeds and Google were not due. No supported employer application link triggered fallback, and SerpApi was not configured, so those new adapters remain contract-tested rather than live-verified.

## Remaining external limits

Public LinkedIn endpoints can block descriptions. Recruiter engines can throttle or index stale/no posts. Google JobSpy remains dependent on an unavailable upstream endpoint. SerpApi needs account access/quota; Greenhouse/Lever fallback requires an exact supported application link in the card. Missing publication, eligibility and salary evidence stays visible in review gaps. True profile accuracy still requires held-out owner labels and manually found positive examples.

Provider contracts: [Greenhouse public Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [SerpApi Google Jobs API](https://serpapi.com/google-jobs-api).
