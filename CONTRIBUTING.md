# Development workflow

Use uv 0.12.9 and Python 3.14.7. The version files, manifest and lockfile are authoritative; do not install project packages into global Python.

```powershell
uv python install
uv sync --locked
uv pip check
uv run --locked python -m unittest discover -s tests -v
uv run --locked pyrefly check
uv run --locked python -m evaluation tests/fixtures/matching.json
```

`uv sync` creates `.venv`. Select `.venv/Scripts/python.exe` in a Windows editor, or `.venv/bin/python` on Linux/macOS. Invoke tools through `uv run --locked` so the environment stays consistent. `.venv`, `.cache`, runtime reports and secrets are ignored. In a restricted workspace, `uv --cache-dir .cache/uv sync --locked` keeps package cache writes inside the repository.

Runtime dependencies belong in `[project.dependencies]`; development tools belong in `[dependency-groups].dev`. Add/remove through `uv add`, `uv add --dev`, and `uv remove`. Upgrade deliberately, inspect `uv.lock`, run the checks, and commit both the manifest and lockfile. When changing Python, update `.python-version` and `requires-python` together, resolve compatible packages, and verify Linux CI. Exact dependency pins require `uv add NAME==VERSION` to move them; `uv lock --upgrade-package NAME` respects existing constraints.

Keep changes focused, preserve delivery/discovery history, and add regression tests for behavior changes. Use temporary state paths for experiments. Offline tests must not contact job boards or send Discord messages. Real scraping uses `uv run --locked python main.py --dry-run`; notification tests and live runs have external side effects.

Before committing, inspect `git diff --check` and the staged diff. Use a descriptive prefix such as `fix:`, `feat:`, `build:` or `docs:`. Record significant operational changes and evidence in `development-plans`. Do not stage downloaded reports, environments, secrets or live state as part of an unrelated code change.

For this owner's manual commits, configure the repository identity (not global Git settings):

```powershell
git config --local user.name "Faraz Hussain"
git config --local user.email "132701966+asteroidcrib729@users.noreply.github.com"
```

Production state commits have a separate, explicit identity contract: author Faraz Hussain with that noreply address, committer `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>`. Configure those four Git environment variables on the state-persistence step. Do not substitute the triggering actor, amend historical commits, or force-push to correct attribution. State commits are created only for real state changes; no empty contribution commits are needed.

The regression CI workflow has read-only repository permissions. The production workflow alone has contents-write permission and serializes runs before reconciling/pushing state. Its tests run before notifications; the dependency lock cannot be rewritten by CI.
