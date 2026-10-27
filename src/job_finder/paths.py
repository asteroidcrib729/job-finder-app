"""Keep mutable application data outside the installed source package."""
import os
from pathlib import Path

_checkout = Path(__file__).resolve().parents[2]
# Editable installs resolve the checkout even when invoked from another directory.
# A wheel install uses the working directory, or an explicitly configured data root.
BASE_DIR = Path(os.environ.get("JOB_FINDER_HOME") or (
    _checkout if (_checkout / "pyproject.toml").is_file() else Path.cwd()
)).resolve()

OUTPUT_DIR = BASE_DIR / ".local" / "output"
