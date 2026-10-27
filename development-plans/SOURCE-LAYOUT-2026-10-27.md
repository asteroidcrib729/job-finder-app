# Source layout and engineering checks — 2026-10-27

## Problems and implemented solutions

| Problem | Resolution |
| --- | --- |
| Production modules and manual probe mixed into root directories; imports depended on checkout layout. | Installed `job_finder` package under `src/job_finder`, built with `uv_build==0.12.9`; editable installation through uv, namespaced imports, module and console entry points. Probe is `job_finder.search_probe`. Tests remain outside the package. |
| Moving files could redirect configuration or delivery state into source directories. | Shared `paths.BASE_DIR` resolves the checkout for editable installs, with optional `JOB_FINDER_HOME`. Config/profile/state remain external. Regression checks exercise actual subprocesses outside the checkout and explicit home overrides. |
| Root module commands would break production and isolated JobSpy execution after relocation. | Workflow runner, state persistence and worker invocations use `job_finder.*`. README and contributor commands updated. Existing worker integration and state-push tests retain coverage. |
| No enforced linting; existing Pyrefly scope assumed root modules. | Locked Ruff 0.17.2 checks E4/E7/E9/F/I; import ordering and unused imports corrected, ambiguous reconciliation variables renamed. Pyrefly 1.4.0 covers source/tests and resolves `src`; no new suppressions. Python 3.14.7 `compileall` complements Pyrefly's parser/type diagnostics. |
| IDE configuration ignored entirely and interpreter selection undocumented. | Allowlisted shared VS Code interpreter/extension/task/test/debug settings. `.venv` supplies dependencies, Ruff and Pyrefly. Previously cached interpreter choices must be changed explicitly. |
| No automatic dependency update or security workflow. | Weekly Dependabot uv/Actions updates, PR dependency review with high-severity threshold, locked advisory auditing and CodeQL Python security-extended scans. No auto-merge. Security tooling cannot send Discord alerts or commit state. |

Python remains exactly **3.14.7**, uv remains **0.12.9**, and automated commit attribution remains Faraz Hussain as author and GitHub Actions bot as committer. No production JSON histories or matching thresholds were changed.

## Validation

- Windows: all 83 offline tests passed, including the real isolated JobSpy subprocess and temporary-repository concurrent state push/commit identity tests.
- Synthetic matching benchmark: 54/54 expected tiers.
- Ruff passed; Pyrefly reported 0 errors with 17 existing targeted suppressions; Python syntax compilation passed.
- Locked environment consistency passed; advisory audit found no known vulnerabilities/adverse package statuses in 41 packages at validation time.
- Wheel and source archive built successfully; archive inspection confirmed no environment, cache, secret or production-state files were included.
- VS Code JSON and workflow/Dependabot YAML parsed successfully. Actionlint 1.7.12 validated all Actions workflows without findings; its official release archive checksum was verified before execution.
- Published implementation commit: `125a1e81962eda232113ac492716bb6594966362`. [Linux quality CI](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40487599330) passed all 83 tests, Ruff, Pyrefly, compilation and wheel/source builds on Python 3.14.7. [Security scans](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40487599510) passed the 41-package audit and uploaded CodeQL results: 50 rules, zero findings, no analysis errors/warnings.
- GitHub accepted the Dependabot configuration and started both uv and GitHub Actions update jobs. [Dependabot PR #1](https://github.com/asteroidcrib729/job-finder-app/pull/1) was created automatically; its quality, audit, CodeQL and [dependency-review check](https://github.com/asteroidcrib729/job-finder-app/actions/runs/40487796936) all passed. The update PR remains unmerged.
- Initial dependency review failed because this repository had dependency graph/alerts disabled. Enabled them through the documented repository API, verified alerts are enabled and uv manifest/lock changes are returned by the dependency comparison API, then reran the failed check successfully. This repository setting is required in addition to the workflow files.

The editor settings are checked against the [Pyrefly editor documentation](https://pyrefly.org/en/docs/IDE/) and [Ruff editor settings](https://docs.astral.sh/ruff/editors/settings/). Live VS Code extension activation was not observed. The [uv build backend](https://docs.astral.sh/uv/configuration/build-backend/) supplies the source layout. Dependabot uses the supported [uv ecosystem configuration](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories), not a custom Actions updater.

## Operational boundaries

Use `uv sync --locked` after pulling these changes. Replace `python main.py` with `uv run --locked python -m job_finder`; other modules now start with `job_finder.`. Run quality checks with the commands in `CONTRIBUTING.md` or the default VS Code build task. A standalone wheel needs an external configuration root and profile; the repository checkout is the supported operational deployment.

Offline checks establish package/import/state behavior, not current job-board availability or matching precision on unseen listings. Security results are point-in-time and do not establish absence of all vulnerabilities. A successful CodeQL analysis publishes findings; findings require review in the repository Security view.
