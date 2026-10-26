# uv and Python 3.14.7 migration

## Requested outcome and implementation

The owner requested Astral uv for project/dependency management, a dedicated environment, and explicit author/committer instructions for Actions commits. The owner then specified Python **3.14.7**, allowing incompatible dependencies to be upgraded or replaced. That exact version supersedes the earlier Python 3.11/3.12 baseline.

- Added `pyproject.toml`, `.python-version` and the generated `uv.lock`. Both Python declarations require 3.14.7. uv is pinned to 0.12.9, matching the locally validated CLI and Actions installer input.
- Created the ignored project `.venv` on Windows using Python 3.14.7. Runtime dependencies and the development group (Pyrefly plus YAML stubs) are separate. The application remains an unpackaged checkout application, preserving module/config/state paths.
- Replaced the hand-maintained requirements files with the uv manifest/lock. An optional requirements export can be generated into ignored `output/` for other tools.
- Production installs `uv sync --locked --no-dev`; regression CI installs the development group. Both use `uv run --locked`, check dependency consistency, and run offline tests. Regression CI also runs Pyrefly. The read-only Discord diagnostic selects the same Python pin with uv and needs only the standard library.
- Added `CONTRIBUTING.md` and `AGENTS.md` with environment, dependency maintenance, testing, Git identity and state-preservation instructions. README commands use uv.

## Compatibility changes

JobSpy 1.1.82 pinned NumPy 1.26.3, which blocked modern Python support. Upgraded to JobSpy 1.4.1, pandas 3.1.0 and NumPy 2.5.4. Runtime transitive packages were freshly resolved; the obsolete `tls-client` dependency is gone and JobSpy now uses `curl-cffi`. Exact versions/hashes are in `uv.lock`; no dependency constraints were overridden to force an incompatible installation.

JobSpy still provides LinkedIn, Indeed and Google adapters in the inspected release. Its `linkedin_fetch_description` argument is deprecated, so the application maps the existing configuration option to the new `fetch_description` API argument. Its logging namespace is now lowercase `jobspy`, and failures/warnings also appear in DataFrame attributes. The worker handles both channels, retains valid partial results, and emits only classified codes rather than raw provider error text. This prevents blocked or failed searches from being misreported as valid empty results after the upgrade.

Compatibility tests call the installed JobSpy API with fixture scrapers, check actual DataFrame serialization, preserve location/salary evidence, cover empty/partial/blocked outcomes, and execute the real worker subprocess with invalid input before network access. Existing matcher and delivery behavior remains covered. Small annotation/HTML-attribute validation changes address the updated type checker's findings.

## Commit identity contract

The production state-persistence step supplies:

| Role | Name | Email |
| --- | --- | --- |
| Author | Faraz Hussain | `132701966+asteroidcrib729@users.noreply.github.com` |
| Committer | github-actions[bot] | `41898282+github-actions[bot]@users.noreply.github.com` |

The state writer honors these four Git environment variables and has matching repository-specific defaults. Invalid blank/multiline identity values stop persistence. The bot identity was checked against GitHub's `github-actions[bot]` account ID. The owner's noreply email retains profile attribution without publishing the personal Gmail address. Tests verify workflow/default agreement and actual author/committer fields after a concurrent state-push retry. Read-only workflows do not create commits. No historical commits are rewritten and state is only committed when it changes.

## Local validation

- Dedicated interpreter verified as `.venv/Scripts/python.exe`, Python 3.14.7.
- All **80 offline tests passed**; **54/54** synthetic matching decisions agreed.
- `uv pip check` passed; `uv lock --check` passed.
- Pyrefly 1.4.0 reported **zero diagnostics**, with 17 existing suppressions.
- `uv audit --locked` found **no known vulnerabilities or adverse project statuses** in 40 locked dependencies, including development tools, on October 27, 2026. This is a point-in-time advisory check.
- Workflow YAML and the embedded read-only diagnostic Python parsed successfully. Scraper imports and DDGS construction passed without performing searches.

Live source availability and real-job matching accuracy are separate from runtime compatibility. No Discord messages or production state writes were used for these local checks. Linux execution is validated by the published regression workflow; Windows results alone are not evidence of Linux execution.

## References

- [Astral uv migration guide](https://docs.astral.sh/uv/guides/migration/pip-to-project/)
- [Astral uv GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/)
- [Upstream JobSpy Python 3.14 incompatibility and resolution](https://github.com/speedyapply/JobSpy/issues/376)
- [JobSpy package release](https://pypi.org/project/python-jobspy/1.4.1/)
