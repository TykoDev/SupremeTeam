"""Regression coverage for package selection and scanner command fidelity."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from output_paths import global_data_root, resolve
from package_check import REQUIRED_ASSET_GLOBS


SCRIPTS = Path(__file__).resolve().parent


class RuntimeUtilitiesTests(unittest.TestCase):
    def test_preference_paths_are_explicit_and_global_stays_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as home:
            root = Path(directory).resolve()
            project_json, project_md = resolve(root, "project_preferences")
            self.assertEqual(project_json, root / "skillset-saves/preferences/taste.json")
            self.assertEqual(project_md, root / "skillset-saves/preferences/taste.md")
            with mock.patch.dict("os.environ", {"SUPREMETEAM_HOME": home}, clear=False):
                self.assertEqual(global_data_root(), Path(home).resolve())
                global_json, global_md = resolve(root, "global_preferences")
                self.assertNotIn(root, global_json.parents)
                self.assertEqual(global_md.parent, global_json.parent)
    def test_declared_pipelines_have_output_destinations(self):
        pipelines = json.loads((SCRIPTS.parent / "pipelines.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for phase in pipelines["pipelines"]:
                with self.subTest(phase=phase):
                    self.assertEqual(
                        resolve(root, "reports", run_id="audit", phase=phase, name="result.md"),
                        root / "skillset-saves" / "runs" / "audit" / phase / "reports" / "result.md",
                    )

    def test_package_contains_root_docs_and_excludes_root_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in [*REQUIRED_ASSET_GLOBS, "README.md", "Install.md", ".env", ".env.local"]:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("fixture", encoding="utf-8")
            archive = root / "distribution.zip"
            process = subprocess.run(
                [sys.executable, str(SCRIPTS / "package_check.py"), "--root", str(root), "--out", str(archive)],
                capture_output=True, text=True,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            with zipfile.ZipFile(archive) as package:
                self.assertIn("README.md", package.namelist())
                self.assertIn("Install.md", package.namelist())
                self.assertNotIn(".env", package.namelist())
                self.assertNotIn(".env.local", package.namelist())

    def test_scanner_receives_its_own_end_of_options_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "scan.json"
            process = subprocess.run(
                [sys.executable, str(SCRIPTS / "scan_record.py"), "--project-root", str(root),
                 "--out", str(record), "--", sys.executable, "-c",
                 "import json, sys; print(json.dumps(sys.argv[1:]))", "--", "--target"],
                capture_output=True, text=True,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["result"]["status"], "pass")
            self.assertEqual(json.loads((root / "scan.stdout.txt").read_text(encoding="utf-8")), ["--", "--target"])


if __name__ == "__main__":
    unittest.main()
