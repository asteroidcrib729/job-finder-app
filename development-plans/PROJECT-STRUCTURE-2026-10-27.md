# Configuration and module organization - October 27, 2026

## Result

The owner requested configuration outside the project root and modules grouped by responsibility. The subsequent clarification explicitly retained `src/job_finder`; no hyphenated source container is used.

- Operational defaults moved to `config/config.yaml`; the unchanged candidate profile moved to `config/profiles/candidate-profile.yaml`.
- `profile_path: profiles/candidate-profile.yaml` resolves against the configuration directory, including values supplied through an external override file. Absolute profile paths remain supported. `JOB_FINDER_HOME` selects the instance root containing `config/` and `data/`.
- `application` contains pipeline/health; `configuration` contains loader/paths; `automation` contains runner/failure; `diagnostics` contains Discord/search tools; `evaluation` contains benchmark/feedback. Existing filtering, scrapers, notifiers and storage packages remain.
- Only `__init__.py` and `__main__.py` remain as package-root source files. Imports, test patches, console entry points and workflows use the new module paths. Console command names and `python -m job_finder` remain stable.
- README, contributor guidance, archive and audit links reflect the new paths. Contributors refresh the editable installation with `uv sync --locked` after pulling.

## Validation

- Locked offline uv sync and dependency consistency passed on Python 3.14.7.
- All 91 offline tests passed, including out-of-directory entry points, instance-root configuration, replay without delivery state and relative profile overrides.
- Ruff passed; Pyrefly reported zero errors with 17 existing suppressions; interpreter compilation passed.
- Synthetic benchmark: 54/54 expected decisions.
- Fresh wheel/source builds passed. An independently installed wheel loaded external configuration and executed CLI help from a temporary directory. Archives exclude local personal material.
- Actionlint and whitespace checks passed. Hosted validation is pending publication.

Production state, dependency versions, filtering policy and delivery behavior were preserved. No live scrape or Discord send was performed as part of this refactor; offline success does not establish live source availability or production matching accuracy.
