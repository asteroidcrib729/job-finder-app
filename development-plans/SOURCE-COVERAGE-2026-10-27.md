# Source coverage improvements - October 27, 2026

## Problems and implemented changes

The preceding live verification exposed partial LinkedIn descriptions, Google errors and ambiguous recruiter-search failures. The owner authorized the proposed fixes while retaining Python, GitHub Actions, JSON state and Discord.

1. **Search health:** the worker classifies unsupported options, detail failures and Google's missing job data separately. Unsupported options are recorded as notes. Only actual unsuccessful search attempts contribute to pausing a site; usable partial rows survive and ordinary warnings cannot pause productive searches.
2. **LinkedIn:** JobSpy collects listing cards without inline description calls. The separate queue shares at most 12 requests across tracks, paces requests by two seconds, and has an eight-second request timeout and 90-second queue budget. Successful parsed descriptions cache for six hours. Blocking or repeated transient failures cools down details for three hours, without discarding cards or successful search watermarks. Expired cache evidence is not used as fallback. Closed jobs remain closed without treating them as a detail-service outage. Current card identity/location/dates take precedence over cached data. Explicit remote keywords replace the ignored LinkedIn `is_remote` search option; work mode still requires listing evidence.
3. **Google:** default `google_mode: probe` removes ordinary Google query rotation and allows one recovery query per 24 hours, after normal searches and within remaining request/time budgets. Both successful and failed probe attempts respect cadence. `disabled` and explicit full `enabled` modes remain available. This does not claim to repair JobSpy's unavailable upstream Google adapter. [Upstream FAQ](https://github.com/speedyapply/JobSpy#frequently-asked-questions).
4. **Recruiter discovery:** each backend is tried separately with sanitized outcomes, under a shared six-attempt limit. Simpler fallback drops Boolean grouping and the search-engine date filter; extracted listing dates still pass the application's freshness checks. Rate limits, timeouts and provider errors have three-hour cooldowns. DDGS `No results found` exceptions remain unverified because they can also mean no parseable results; they never establish a healthy empty search or advance success timestamps. Provider logs containing raw exception/challenge URLs are suppressed in favor of classified codes.
5. **Remote feeds:** Remotive and WWR are enabled after live parser checks. Both have a six-hour minimum between attempts, including failed attempts. The existing Pakistan eligibility, currency, age, attribution, matching and deduplication rules apply. Remotive's public feed has a 24-hour delay and recommends no more than four requests daily. [Remotive documentation](https://github.com/remotive-com/remote-jobs-api), [WWR feeds](https://weworkremotely.com/remote-job-rss-feed).
6. **State and evidence:** discovery records distinguish successful searches from retry/probe attempts. Validation and concurrent reconciliation handle attempt timestamps. Reports distinguish searches, detail requests, backend attempts, probes and full-description coverage. The zero-qualified summary now correctly describes review delivery as a separate configured policy.

## Verification

- Local live feed validation: Remotive returned 10 jobs and WWR returned 25 jobs, all with full descriptions; neither call sent notifications or changed production state.
- A public LinkedIn detail request returned a full description of 5,553 characters.
- A local six-attempt DDGS check returned ambiguous empty responses from Brave, DuckDuckGo and Yahoo. It remained unverified; no success timestamp was fabricated. Hosted verification will determine runner behavior.
- Fifteen additional regressions exercise warning classification, independent detail failures, paced/fair request budgets, expiry/cache boundaries, remote evidence, Google modes/cadence, per-backend fallback, ambiguous empty results, cooldowns, feed retry cadence, coverage counters and concurrent retry state. Existing tests were adjusted for the intentionally changed source parameters/outcomes.
- All 106 offline tests, Ruff, Pyrefly (zero errors, 17 existing suppressions), interpreter compilation, dependency consistency, Actionlint and fresh builds passed locally. The synthetic benchmark retained 54/54 expected decisions. Hosted results are recorded below. Raw reports remain under ignored `.local/output/source-coverage-2026-10-27/`.

## Hosted acceptance evidence

Implementation `0eb490a` passed [Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40555933918) and [security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40555934276). Follow-up parser commits `0c00696` and `f4ec50a` preserve inline requirement phrases and normalize escaped structured-description HTML; fixture regressions cover both. The final code `f4ec50a` passed [Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40557380784) and [security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40557381075), including all 106 tests and the static/build gates.

[Normal live production run 40555934616](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40555934616), on `0eb490a`, succeeded:

| Measurement | Observed result |
| --- | --- |
| Rows / unique jobs | 478 / 251 |
| LinkedIn listing searches | 24 usable out of 24 attempted; one returned partial warning evidence |
| LinkedIn detail requests | 12 successful; full descriptions for 12 of 217 unique LinkedIn jobs |
| Remote feeds | 34 unique jobs, all with descriptions, from two successful feed requests |
| Google recovery | One probe, `google_no_job_data`; no ordinary Google queries |
| Matching tiers | 1 qualified, 24 review, 226 rejected |
| Eligible jobs already notified | 7 |
| New deliveries | 18 jobs: 1 labeled qualified by the existing matcher, 17 review candidates |
| Delivery failures / remaining pending | 0 / 0 |

Rozee, Indeed and recruiter searches were not due in this normal run. The 12-request detail cap deliberately left 205 unique jobs without full descriptions. The matching labels are algorithm outputs, not independently established applicant suitability.

State commit `03e43d0` persisted all 18 receipts with Faraz Hussain as author and the GitHub Actions bot as committer. Each delivered job is marked seen and absent from pending. The five acknowledged Discord messages were independently retrieved by read-only checks [40556980980](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40556980980), [40556987858](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40556987858), [40556998795](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40556998795), [40557005750](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40557005750) and [40557011867](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40557011867). All passed, confirming HTTP 200, the expected server/channel and message existence. The first progress update called all 18 review candidates; this verified breakdown supersedes that shorthand.

[Bounded hosted dry run 40557017888](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40557017888), on `03e43d0` (including the inline-phrase parser correction), succeeded with 107 rows / 73 unique jobs and no missing descriptions. It sent no notifications and skipped state persistence. Eleven Indeed searches and one LinkedIn search returned usable results; eight new LinkedIn details were fetched, with additional cached descriptions reused. Yahoo's simplified/date-relaxed fallback returned six recruiter posts after five ambiguous empty backend attempts, yielding seven role leads. All seven were rejected by the existing freshness check as stale. The other configured recruiter query exhausted the shared budget and remained unverified. Rozee returned usable results for four queries and reported one HTTP 403. Google and remote feeds were not due, confirming their attempt-based cadence behavior.

The final escaped-markup correction was verified through fixtures and hosted tests; a fresh full production sweep on `f4ec50a` was not performed. The retained architecture, matcher policy and delivery history were preserved. These results show improved useful coverage and working bounded fallback, not uninterrupted availability across every source.

## Scope and remaining limits

No dependency upgrade, architecture replacement, delivery-history reset, matcher-threshold relaxation, login automation or credential-dependent provider was introduced. A public provider may still block requests or change its response format. Google restoration requires verified upstream support or a separately evaluated replacement. Recruiter backends can remain unverified after exhausting fallback. Request budgets deliberately leave some descriptions incomplete; those jobs retain conservative matching decisions.

Live parser success, successful hosted checks and measured production precision/recall are separate claims. Several scheduled cycles and held-out manually identified jobs are still needed to assess retrieval and matching quality over time.
