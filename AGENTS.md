# Repository instructions

- Use Astral uv 0.12.9 and the exact Python 3.14.7 pin. The dedicated project environment is `.venv`; never use global pip for project dependencies.
- `pyproject.toml` and `uv.lock` are the dependency source of truth. Use `uv add`/`uv remove` and commit manifest/lock updates together. See `CONTRIBUTING.md` for commands.
- Run appropriate regression checks through `uv run --locked`. For dependency/runtime changes run `uv sync --locked`, `uv pip check`, the full unittest suite and Pyrefly. In restricted environments use `uv --cache-dir .cache/uv ...`.
- Preserve the existing Python adapters, GitHub Actions, JSON state and Discord architecture. Do not reset production delivery history or commit generated reports/secrets/environments.
- Automated state commits must name Faraz Hussain as author, using `132701966+asteroidcrib729@users.noreply.github.com`, and `github-actions[bot]` as committer, using `41898282+github-actions[bot]@users.noreply.github.com`. Keep the workflow environment and writer defaults consistent. Test/diagnostic workflows remain read-only.
- Use Faraz Hussain's repository identity for user-authorized manual commits. Preserve concurrent remote state changes; do not rewrite history or force-push. Inspect staged files and update relevant development records for operational changes.
