# Configuration, workflow and local cleanup — 2026-10-27

## Changes

| Finding/request | Implemented resolution |
| --- | --- |
| Pyrefly configuration separate from project configuration | Moved the same analysis scope, search paths and Python version into `[tool.pyrefly]`; removed `pyrefly.toml`. Pyrefly confirms it loads `pyproject.toml`. Both formats are supported upstream; consolidation is the project convention. |
| Python embedded in Discord workflow | Extracted `src/job_finder/discord_diagnostic.py`. The workflow invokes the standard-library-only script with `uv run --no-project python ...`; `.python-version` still selects Python 3.14.7. No dependency installation, messages or state writes are needed for the read-only diagnostic. |
| Inline shell logic in production workflow | Replaced `exit 1` with `job_finder.fail_workflow`; split setup/check command blocks into individual steps. All five workflows contain only action configuration and single tool/script invocations. Regression coverage rejects multiline scripts, heredocs, interpreter code flags and shell command composition. |
| Ignored personal material and generated directories at root | Moved the resume to `.local/Resume - Faraz Hussain.pdf`, `.cache` to `.local/cache`, `.ruff_cache` to `.local/ruff-cache`, `output` to `.local/output`, `dist` to `.local/dist`, and root `__pycache__` to `.local/legacy-root-pycache`. Resume SHA-256 was identical before and after. Removed only the empty `scratch` directory. Existing cached evidence and reports were retained. |
| Tools or runtime would recreate root clutter | uv/Ruff cache settings point inside `.local`; shared application report defaults, evaluation/feedback commands, documentation and the artifact upload path were updated. Fresh package builds use `uv build --no-cache --out-dir .local/dist`. |
| Hidden report directory could prevent artifact upload or expose private files | Upload only `.local/output/latest/` with `include-hidden-files: true`. Never upload `.local` as a whole. Package source excludes `.local/**`; fresh wheel/source archives were inspected and contain no private material. |

The root `.venv` is retained for standard uv and VS Code discovery and to avoid breaking installed launchers. Source/test `__pycache__` directories remain beside their modules. Tracked configuration, candidate profile and production JSON state remain at their existing locations. The whole `.local` tree is Git-ignored; legacy ignore patterns are retained as safeguards. No resume content or local evidence was added to Git.

## Verification

- Locked editable environment reinstallation succeeded offline after moving caches. Python remains 3.14.7.
- All 90 offline regressions passed together, including six diagnostic/workflow tests and the isolated-home replay test. Hosted validation is pending publication.
- The extracted diagnostic is tested for matching/mismatched server IDs, missing receipts, invalid inputs, safe summaries, GET-only transport, redirect refusal, malformed JSON shapes and sanitized errors. No live Discord call was made.
- Replay subprocess test verifies that default reports land under `.local/output/latest` without creating delivery state or a root `output` directory.
- Ruff, Pyrefly (0 errors, 17 existing suppressions), interpreter compilation, dependency consistency and Actionlint passed.
- A fresh uncached wheel contains both extracted scripts; wheel/source archives exclude `.local`, environments and the resume. Reused local wheel cache initially produced an older wheel, so documented/CI builds now use `--no-cache` and the fresh contents were inspected.
- `git check-ignore` confirms local assets remain excluded. The original resume's hash was preserved; production state was not edited by cleanup.

Historical documents retain the paths and validation results recorded at the time. Current commands and storage conventions are documented in README, CONTRIBUTING and AGENTS.
