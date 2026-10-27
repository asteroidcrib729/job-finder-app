"""Exercise the installed src package independently of the working directory."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackageLayoutTests(unittest.TestCase):
    def run_python(self, args, directory, home=None):
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("JOB_FINDER_HOME", None)
        if home is not None:
            environment["JOB_FINDER_HOME"] = str(home)
        result = subprocess.run([sys.executable, *args], cwd=directory, env=environment,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_installed_module_help_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            output = self.run_python(["-m", "job_finder", "--help"], directory)
        self.assertIn("--dry-run", output)
        self.assertIn("--replay", output)

    def test_editable_install_resolves_configuration_and_state_at_checkout_root(self):
        script = (
            "import json; from job_finder.config import BASE_DIR, load_config; "
            "from job_finder.storage.tracker import DATA_DIR; "
            "from job_finder.main import DISCOVERY_FILE; "
            "load_config(); print(json.dumps([str(BASE_DIR), str(DATA_DIR), str(DISCOVERY_FILE)]))"
        )
        with tempfile.TemporaryDirectory() as directory:
            actual = json.loads(self.run_python(["-c", script], directory))
        self.assertEqual(actual, [str(ROOT), str(ROOT / "data"), str(ROOT / "data/discovery_state.json")])

    def test_explicit_home_keeps_mutable_data_outside_package(self):
        script = (
            "import json; from job_finder.paths import BASE_DIR; "
            "from job_finder.storage.tracker import DATA_DIR; "
            "print(json.dumps([str(BASE_DIR), str(DATA_DIR)]))"
        )
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve() / "instance"
            actual = json.loads(self.run_python(["-c", script], directory, home=home))
            self.assertEqual(actual, [str(home), str(home / "data")])
            self.assertFalse(home.exists(), "Importing must not create or write state")
