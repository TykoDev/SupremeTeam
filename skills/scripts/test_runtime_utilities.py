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

    def assert_wrapper_error(self, root: Path, out: Path) -> subprocess.CompletedProcess:
        """Run the wrapper at an unusable `out` and assert the documented failure shape.

        scan_record.py documents exit 0 when a record was written and 2 on wrapper
        error, so every unwritable destination must take the wrapper-error branch
        with a structured engine_error rather than raising out of main() as a
        traceback and exiting 1.
        """
        process = subprocess.run(
            [sys.executable, str(SCRIPTS / "scan_record.py"), "--project-root", str(root),
             "--out", str(out), "--no-run", "--", "pip-audit"],
            capture_output=True, text=True,
        )
        self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
        self.assertNotIn("Traceback", process.stderr)
        self.assertIn("engine_error", json.loads(process.stderr.strip()))
        return process

    def test_unusable_record_destination_exits_two_with_a_structured_error(self):
        """An --out whose parent cannot be created is a wrapper error, not a crash."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocker = root / "blocker"
            blocker.write_text("not a directory", encoding="utf-8")
            self.assert_wrapper_error(root, blocker / "nested" / "scan.json")

    def test_unwritable_raw_output_destination_exits_two_and_writes_no_record(self):
        """The sidecars are the artifacts the record names, so losing one aborts the run.

        gates.yaml requires a scan record to carry hashed artifacts, so a record that
        outlived a failed sidecar write would name raw output that does not exist.
        Aborting keeps the documented contract exact: no record written, exit 2.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "scan.json"
            (root / "scan.stdout.txt").mkdir()
            self.assert_wrapper_error(root, record)
            self.assertFalse(record.exists())

    def test_unwritable_record_file_exits_two_with_a_structured_error(self):
        """A record whose own JSON cannot be written is not a usable record at all."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "scan.json"
            (root / "scan.json.tmp").mkdir()
            self.assert_wrapper_error(root, record)
            self.assertFalse(record.exists())

    def test_failed_record_replace_exits_two_and_leaves_no_temp_file(self):
        """os.replace can fail after a clean write; the temp file must not survive it."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = root / "scan.json"
            record.mkdir()
            self.assert_wrapper_error(root, record)
            self.assertFalse((root / "scan.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
