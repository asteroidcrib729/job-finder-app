# Contribution and maintenance workflow

This document describes the conventions followed by contributors and the repository maintainer. [AGENTS.md](AGENTS.md) records the project history, current operating rules, validation evidence and unresolved work. [README.md](README.md) presents the project in Faraz Hussain's first-person voice; this guide uses third-person language.

## Project structure and local files

Application code belongs in `src/job_finder/`, with `job_finder.*` imports and package modules or console entry points. Tests belong in `tests/`; configuration and candidate-profile YAML remain at the root; production delivery and discovery state remain in `data/`. Configuration secrets and generated state do not belong inside the installed package.

Contributors keep personal documents, caches, reports and build output in Git-ignored `.local/`. The owner's resume is `.local/Resume - Faraz Hussain.pdf`. uv and Ruff cache paths are configured there. The root `.venv` remains the standard environment for uv and IDE discovery; relocating an existing environment requires recreating its launchers. Neither Git commits nor artifact uploads include the entire `.local` directory. Legacy root ignore patterns remain as protection against accidentally generated files.

Tool configuration stays in `pyproject.toml`, including `[tool.pyrefly]`, uv and Ruff settings. Workflow YAML contains action configuration and single tool/script invocations. Dedicated modules in `src/job_finder` contain executable logic, including diagnostics; offline tests cover changes to that logic. Embedded Python, JavaScript, shell programs, heredocs and interpreter code snippets are excluded from workflow YAML.

## Environment and verification

Contributors use **uv 0.12.9** and **Python 3.14.7**. `.python-version`, `pyproject.toml` and `uv.lock` define the supported environment. Project dependencies are installed into `.venv`, rather than global Python.

The following commands establish the environment and run the available checks:

```powershell
uv python install
uv sync --locked
uv pip check
uv run --locked ruff check src tests
uv run --locked pyrefly check
uv run --locked python -m compileall -q src tests
uv run --locked python -m unittest discover -s tests -v
uv run --locked python -m job_finder.evaluation tests/fixtures/matching.json
uv build --no-cache --out-dir .local/dist
uv audit --locked
```

`uv sync` creates the dedicated environment. `uv run --locked` keeps commands aligned with the lockfile. uv's configured cache is `.local/cache/uv`; an explicit `uv --cache-dir .local/cache/uv sync --locked` command provides the same location when needed. Fresh builds produce a wheel and source archive in ignored `.local/dist/`.

Shared VS Code settings recommend Python, Pyrefly and Ruff extensions, enable unittest discovery and provide a dry-run debugger. The default build task runs the offline quality checks. Contributors whose editor remembers another interpreter select `.venv/Scripts/python.exe` on Windows or `.venv/bin/python` on Linux/macOS through **Python: Select Interpreter**.

Verification follows the scope of the change. Behavior and configuration changes require the relevant regressions and quality checks. Runtime or dependency changes also require locked synchronization, dependency consistency checks, an advisory audit and hosted Linux evidence. Package/layout changes require a fresh build and inspection of its contents. Documentation-only changes require review of wording, commands, local links and the staged diff; historical test results remain labeled as historical rather than being presented as newly executed tests.

## Dependency maintenance

Runtime dependencies belong in `[project.dependencies]`; development tools belong in `[dependency-groups].dev`. Contributors manage them with `uv add`, `uv add --dev` and `uv remove`, inspect the resulting lockfile, run the relevant checks, and commit manifest and lockfile changes together.

An exact dependency pin changes through `uv add NAME==VERSION`. `uv lock --upgrade-package NAME` updates a package only within its declared constraints. A Python-version change requires matching updates to `.python-version` and `requires-python`, compatible package resolution, and Linux CI verification.

Dependabot opens weekly uv and GitHub Actions update pull requests. The maintainer reviews manifest/lock diffs and check results before merging; automatic merging is disabled. Dependency review blocks high/critical vulnerabilities introduced by pull requests. The separate security workflow performs advisory auditing and CodeQL analysis on code changes and weekly. Findings require investigation; blanket advisory ignores do not substitute for remediation or a documented exception.

GitHub's dependency graph and Dependabot alerts must be enabled for dependency review. These settings were enabled and verified during the October 27, 2026 rollout; forks and new repositories may require equivalent configuration. The [layout validation record](development-plans/SOURCE-LAYOUT-2026-10-27.md) contains the original hosted evidence.

## Behavior, evidence and state protection

Contributors preserve the Python adapters, GitHub Actions, JSON state and Discord architecture. Experiments use temporary state paths. Offline tests do not contact job boards or send Discord messages. The live scraping command `uv run --locked python -m job_finder --dry-run` contacts sources but does not send notifications or persist delivery/discovery history. Notification tests and live runs have external side effects.

The maintainer records meaningful operational changes and evidence in `development-plans` and adds a dated summary to `AGENTS.md`. Completed code changes, hosted execution and real-world matching accuracy are separate claims. The 54-case synthetic benchmark does not establish production precision or recall.

## Commit and publication conventions

Contributors inspect `git diff --check` and the staged diff before committing. Commit messages use descriptive prefixes such as `fix:`, `feat:`, `build:` or `docs:`. Reports, environments, secrets and unrelated live state are excluded from code/documentation commits. Concurrent remote state changes are preserved; publication uses ordinary fast-forward pushes rather than rewritten history.

For maintenance performed on behalf of the repository owner, the owner's manual Git identity is configured locally:

```powershell
git config --local user.name "Faraz Hussain"
git config --local user.email "132701966+asteroidcrib729@users.noreply.github.com"
```

Independent contributors retain their own authorship. Automated production state commits follow a separate identity contract:

| Role | Name | Email |
| --- | --- | --- |
| Author | Faraz Hussain | `132701966+asteroidcrib729@users.noreply.github.com` |
| Committer | github-actions[bot] | `41898282+github-actions[bot]@users.noreply.github.com` |

The persistence step supplies all four `GIT_AUTHOR_*` and `GIT_COMMITTER_*` values, and writer defaults match them. The triggering actor does not replace those identities. Attribution changes do not amend historical commits or justify force pushes. State commits record real changes; empty commits are not created for contribution-graph activity.

Quality and diagnostic workflows have read-only repository contents permissions. The production workflow alone has contents-write permission and serializes runs before reconciling/pushing state. CodeQL has the separate security-events write permission required to publish analysis. Production tests run before notifications; CI does not rewrite the dependency lock.
