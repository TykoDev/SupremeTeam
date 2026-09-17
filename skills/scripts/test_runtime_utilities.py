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

import hashlib

from data_formats import content_sha256, load_data, normalize_line_endings
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

    def test_coverage_kind_resolves_under_the_run_phase_evidence(self):
        """Coverage data is phase evidence in the run, never project-root residue.

        The observed failure was a `.coverage` tree of thousands of files at a
        target project's root; this destination is what a test step points
        COVERAGE_FILE, --report-dir, or --coverage.reportsDirectory at instead.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for phase, name in (("build", ".coverage"), ("qa", "html/index.html")):
                with self.subTest(phase=phase, name=name):
                    self.assertEqual(
                        resolve(root, "coverage", run_id="r1", phase=phase, name=name),
                        root / "skillset-saves" / "runs" / "r1" / phase / "evidence" / "coverage" / Path(name),
                    )
            # It is a subdirectory of the phase-evidence class, not a sibling of it.
            evidence = resolve(root, "evidence", run_id="r1", phase="build", name="tests.log")
            self.assertEqual(
                resolve(root, "coverage", run_id="r1", phase="build", name=".coverage").parent,
                evidence.parent / "coverage",
            )

    def test_coverage_kind_rejects_traversal_and_unknown_phases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for kwargs in (
                dict(run_id="r1", phase="build", name="../../escape"),
                dict(run_id="r1", phase="build", name=""),
                dict(run_id="r1", phase="not-a-phase", name=".coverage"),
                dict(run_id="", phase="build", name=".coverage"),
            ):
                with self.subTest(**kwargs):
                    with self.assertRaises(ValueError):
                        resolve(root, "coverage", **kwargs)

    def test_coverage_residue_never_packages(self):
        """package_check.py rejects the residue classes so a stray tree cannot ship."""
        from package_check import RESIDUE_CLASSES, matches

        patterns = RESIDUE_CLASSES["coverage-residue"]
        for relative in (".coverage", ".coverage.host.123.abc", ".coverage/nested/a.json",
                         "htmlcov/index.html", ".nyc_output/out.json", "app/.coverage",
                         "app/htmlcov/index.html"):
            with self.subTest(relative=relative):
                self.assertTrue(matches(relative, patterns), relative)
        for relative in ("skills/scripts/output_paths.py", "docs/coverage-notes.md",
                         "src/coverage/report.ts", "README.md"):
            with self.subTest(relative=relative):
                self.assertFalse(matches(relative, patterns), relative)

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


class LineEndingAgnosticHashTests(unittest.TestCase):
    """The catalog must work on an LF and a CRLF checkout alike: every recorded
    sha256 folds text to LF first, binary is untouched, and the CLI that
    specialists use to report hashes agrees with the gate."""

    TEXT = "line one\nline two\n\nend\n"

    def test_text_hashes_agree_across_line_endings(self):
        lf = self.TEXT.encode("utf-8")
        crlf = self.TEXT.replace("\n", "\r\n").encode("utf-8")
        self.assertEqual(normalize_line_endings(crlf), lf)
        self.assertEqual(normalize_line_endings(lf), lf)
        with tempfile.TemporaryDirectory() as directory:
            a = Path(directory) / "a.md"
            a.write_bytes(lf)
            b = Path(directory) / "b.md"
            b.write_bytes(crlf)
            self.assertEqual(content_sha256(a), content_sha256(b))
            self.assertEqual(content_sha256(a), hashlib.sha256(lf).hexdigest())

    def test_binary_content_is_hashed_byte_for_byte(self):
        payload = b"PK\x03\x04\r\n\x00\x00binary\r\n"
        self.assertEqual(normalize_line_endings(payload), payload)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.zip"
            path.write_bytes(payload)
            self.assertEqual(content_sha256(path), hashlib.sha256(payload).hexdigest())

    def test_registry_digest_verifies_on_lf_and_crlf_overlays(self):
        import check_runtime
        entry = load_data(SCRIPTS.parent / "tech-stacks" / "registry.yaml")["overlays"][0]
        lf = normalize_line_endings((SCRIPTS.parent / entry["path"]).read_bytes())
        self.assertEqual(hashlib.sha256(lf).hexdigest(), entry["sha256"], "registry digests are LF-folded")
        for ending in (b"\n", b"\r\n"):
            with self.subTest(ending=ending):
                with tempfile.TemporaryDirectory() as directory:
                    catalog = Path(directory).resolve() / "skills"
                    (catalog / "tech-stacks").mkdir(parents=True)
                    (catalog / entry["path"]).write_bytes(lf.replace(b"\n", ending))
                    (catalog / "tech-stacks" / "registry.yaml").write_text(json.dumps({
                        "schema_version": 1, "kind": "supremeteam-tech-stack-registry",
                        "overlays": [entry]}), encoding="utf-8")
                    errors: list[str] = []
                    check_runtime._load_registry(catalog, errors)
                    self.assertEqual([e for e in errors if "digest" in e], [], errors)

    def test_content_hash_cli_matches_the_gate_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "evidence.md"
            path.write_bytes(self.TEXT.replace("\n", "\r\n").encode("utf-8"))
            proc = subprocess.run([sys.executable, str(SCRIPTS / "content_hash.py"), str(path), "--project-root", str(root)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["hashes"], {"evidence.md": hashlib.sha256(self.TEXT.encode("utf-8")).hexdigest()})
            proc = subprocess.run([sys.executable, str(SCRIPTS / "content_hash.py"), str(root / "missing.md")],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(json.loads(proc.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
