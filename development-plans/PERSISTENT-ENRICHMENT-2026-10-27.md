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

## Remaining external limits

Public LinkedIn endpoints can block descriptions. Recruiter engines can throttle or index stale/no posts. Google JobSpy remains dependent on an unavailable upstream endpoint. SerpApi needs account access/quota; Greenhouse/Lever fallback requires an exact supported application link in the card. Missing publication, eligibility and salary evidence stays visible in review gaps. True profile accuracy still requires held-out owner labels and manually found positive examples.

Provider contracts: [Greenhouse public Job Board API](https://docs.greenhouse.io/job-board.html), [Lever Postings API](https://github.com/lever/postings-api), [SerpApi Google Jobs API](https://serpapi.com/google-jobs-api).
