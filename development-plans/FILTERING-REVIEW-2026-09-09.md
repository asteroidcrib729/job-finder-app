# Scheduled review alerts and filtering assessment

## Change requested by the owner

On September 9, 2026, the owner authorized enabling scheduled review alerts and publishing all pending changes. `notifications.send_review` is now true. Scheduled and ordinary manual runs deliver qualified jobs first, followed by review candidates in labeled digests of up to five jobs. The shared cap remains 20 jobs per run; overflow stays pending and is reevaluated before sending. Confirmed jobs are not resent. Explicit rejections remain excluded.

The separate manual `verification_sample` option retains its three-job cap and qualified-first fallback behavior. It is not required for scheduled review delivery. No matcher thresholds or profile experience values were changed in this update.

The other pending edits are Pyrefly ignore comments in application/tests and a `pyrefly.toml` project configuration. These are type-check tooling changes, not runtime scraper or matcher corrections.

## Actual production evidence

The [September 9 scheduled run](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34345722195) collected 603 rows and deduplicated them to 336 jobs:

| Decision | Count | Previous delivery behavior |
| --- | ---: | --- |
| Qualified | 1 | Already in notification history; no repeat |
| Review | 25 | Withheld by the previous qualified-only policy |
| Rejected | 310 | Excluded by one or more hard rules |

Of the 25 review candidates, 23 scored at least 60. Missing evidence was a major barrier to automatic qualification: 20 lacked a publication date, 19 lacked remote salary information, seven lacked confirmed remote country eligibility, three had unknown local city, and three were one-year experience stretch cases. Counts overlap. A high score describes keyword/role alignment; it does not establish actual employer eligibility or a probability of hiring.

Hard rejection flags across the 310 rejected jobs also overlap:

| Flag | Jobs |
| --- | ---: |
| Senior title or source seniority label | 182 |
| Incompatible location | 166 |
| Target software role not recognized | 99 |
| Required experience exceeds policy | 98 |
| Older than seven days | 54 |
| Unsupported mandatory technology | 17 |
| Explicitly unrelated occupation | 12 |
| Closed listing | 6 |
| Mandatory advanced degree unmet | 2 |

These are the matcher's recorded decisions, not independently validated labels of unsuitable jobs. Broad source searches return senior jobs, other cities, old listings, and unrelated roles despite query keywords. The raw count is not the number of plausible applications.

## How strict the rules are

- **Experience:** the structured profile has zero months of full-time professional experience and five months of internships. The requirement comparison currently uses professional months only. A mandatory requirement up to one year becomes review when `allow_one_year_stretch` is enabled; more than one year is rejected unless the parser recognizes an alternative qualification path. Preferred experience alone does not reject. Internship/project experience may matter to an employer even when this rule does not count it.
- **Role/seniority:** a senior title or senior source label rejects regardless of skills. Titles must match configured software/frontend/backend/fullstack/Python patterns or recognized technology-developer wording. This is deterministic pattern matching, not semantic understanding.
- **Location:** confirmed local work outside Karachi and explicitly country-restricted remote jobs reject. Unknown location/remote eligibility goes to review. Karachi hybrid work is allowed.
- **Technology:** an explicitly required recognized technology absent from the profile can reject. Both demonstrated and listed profile skills are accepted; a score does not validate depth of experience.
- **Freshness:** a known publication date older than 168 hours rejects; unknown date goes to review. Missing data cannot establish that a listing is stale.
- **Pay:** `prefer_usd` puts remote jobs with unknown or non-USD salary into review; local jobs have no USD requirement. It does not reject unknown remote salary.
- **Score:** the threshold is 60/100. Falling below it also produces review, not rejection. Lowering it would not remove hard location, seniority, experience or stack exclusions, or turn missing evidence into verified information.

## Remaining accuracy questions

The old qualified-only notification policy was too restrictive for showing potentially useful but uncertain opportunities. Enabling labeled review alerts addresses that visibility problem without asserting that every review candidate fits.

Some hard rules also merit a real-job audit. The report includes `Forward Deployed Engineer` and `Agentic Engineer - Automation` in Karachi with matched Python/JavaScript but `software_role_not_established`; the title parser can miss adjacent software roles. `New Graduate Engineer, Software` also fails that role pattern, although that particular listing has a separate location rejection. These are concrete candidates for review, not proof that each job meets the full profile. Internship treatment, source seniority labels, and mandatory-stack sentence parsing also warrant checking against manually labeled examples before changing rejection rules.

Production precision and recall remain unmeasured. The owner should be able to judge actual review cards and use existing feedback tooling to record relevant, irrelevant and uncertain examples. This update does not claim all 310 rejections were correct.

## Validation and Discord evidence

- All 75 offline tests pass, including live-path review digest delivery, exclusion of a rejected job, and no resend on the next run. Existing tests cover caps, pending delivery, failed digest retention and atomic acknowledgements.
- `python -m pip check` passes. `pyrefly check` reports zero errors with 22 suppressions and five warnings not shown by its default output; this is not a claim of warning-free static analysis.
- The [read-only destination diagnostic](https://github.com/asteroidcrib729/job-finder-app/actions/runs/34365201374) confirmed the configured webhook targets the owner's Job Finder server, channel `general`, and the September 8 acknowledged job message still exists there. No additional message was sent by that diagnostic.
- Historical downloaded reports remain under ignored `.cache/discord-verification/`; no webhook credential is committed.
