# Repository instructions

- Use Astral uv 0.12.9 and the exact Python 3.14.7 pin. The dedicated project environment is `.venv`; never use global pip for project dependencies.
- Application modules belong in `src/job_finder` with `job_finder.*` imports. Configuration/profile YAML and mutable state stay at the root. Use `python -m job_finder` or the installed console scripts; do not reintroduce root script wrappers.
- Before delivery run Ruff (`uv run --locked ruff check src tests`), Pyrefly (`uv run --locked pyrefly check`), Python syntax compilation (`uv run --locked python -m compileall -q src tests`) and offline tests. Build package/layout changes with `uv build`; audit dependency changes with `uv audit --locked`. Do not silence security findings without documenting a justified exception.
- `pyproject.toml` and `uv.lock` are the dependency source of truth. Use `uv add`/`uv remove` and commit manifest/lock updates together. See `CONTRIBUTING.md` for commands.
- Run appropriate regression checks through `uv run --locked`. For dependency/runtime changes run `uv sync --locked`, `uv pip check`, the full unittest suite and Pyrefly. In restricted environments use `uv --cache-dir .cache/uv ...`.
- Preserve the existing Python adapters, GitHub Actions, JSON state and Discord architecture. Do not reset production delivery history or commit generated reports/secrets/environments.
- Automated state commits must name Faraz Hussain as author, using `132701966+asteroidcrib729@users.noreply.github.com`, and `github-actions[bot]` as committer, using `41898282+github-actions[bot]@users.noreply.github.com`. Keep the workflow environment and writer defaults consistent. Test/diagnostic workflows remain read-only.
- Use Faraz Hussain's repository identity for user-authorized manual commits. Preserve concurrent remote state changes; do not rewrite history or force-push. Inspect staged files and update relevant development records for operational changes.
