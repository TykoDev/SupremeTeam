"""Regression coverage for scan_record.py: argument handling, command fidelity, and gate-ready artifact names.

Each case here reproduced a defect: a non-integer --fail-exit-codes escaped as a
traceback, --version-command ran through a shell, the recorded command lost
argument boundaries, and a record written in the documented layout named its raw
output relative to evidence/ so no honest manifest could hash it.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from data_formats import content_sha256

SCRIPTS = Path(__file__).resolve().parent
SCAN_RECORD = SCRIPTS / "scan_record.py"
CHECK = SCRIPTS.parent / "harness" / "gatekeeper" / "check.py"


def python(code: str) -> tuple[str, ...]:
    return (sys.executable, "-c", code)


class ScanRecordCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.out = self.root / "scan.json"

    def scan(self, *options: str, scanner: tuple[str, ...] = python("print('0 vulnerabilities')"),
             out: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCAN_RECORD), "--project-root", str(self.root), "--out", str(out or self.out),
             *options, "--", *scanner],
            capture_output=True, text=True, check=False)

    def record(self, out: Path | None = None) -> dict:
        return json.loads((out or self.out).read_text(encoding="utf-8"))

    def assert_wrapper_error(self, proc: subprocess.CompletedProcess, needle: str) -> None:
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(needle, json.loads(proc.stderr.strip())["engine_error"])
        self.assertFalse(self.out.exists(), "a refused run must not leave a record behind")


class ArgumentValidationTests(ScanRecordCase):
    def test_a_non_integer_fail_exit_code_is_a_wrapper_error_not_a_traceback(self):
        for value in ("1,x", "x", "1.5", "one"):
            with self.subTest(value=value):
                self.assert_wrapper_error(self.scan("--fail-exit-codes", value), "--fail-exit-codes")

    def test_integer_fail_exit_codes_are_accepted_with_blanks_and_signs(self):
        proc = self.scan("--fail-exit-codes", "1, 2,,-3", scanner=python("import sys; sys.exit(2)"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.record()["result"]["status"], "fail")

    def test_an_invalid_output_pattern_is_a_wrapper_error(self):
        self.assert_wrapper_error(self.scan("--fail-on-output", "(unclosed"), "--fail-on-output")

    def test_an_unparseable_version_command_is_a_wrapper_error(self):
        self.assert_wrapper_error(self.scan("--version-command", "tool --version 'unterminated"), "--version-command")


class CommandFidelityTests(ScanRecordCase):
    def test_argv_survives_an_argument_with_a_space(self):
        scanner = python("import sys; print(sys.argv[1:])") + ("my req.txt", "--flag=a b")
        self.assertEqual(self.scan(scanner=scanner).returncode, 0)
        record = self.record()
        self.assertEqual(record["argv"], list(scanner))
        self.assertEqual(shlex.split(record["command"]), list(scanner))
        self.assertNotEqual(record["command"], " ".join(scanner), "a bare join loses the argument boundary")

    def test_version_command_is_run_as_an_argument_list_not_through_a_shell(self):
        marker = self.root / "shell-ran"
        version = (shlex.join(python("print('scanner 9.9')")) + " ; "
                   + shlex.join(python(f"open({str(marker)!r}, 'w').close()")))
        self.assertEqual(self.scan("--version-command", version).returncode, 0)
        self.assertFalse(marker.exists(), "the text after ';' ran, so the version command went through a shell")
        record = self.record()
        self.assertEqual(record["tool_version"], "scanner 9.9")
        self.assertEqual(shlex.split(record["version_command"]), shlex.split(version))

    def test_a_version_command_that_cannot_start_records_no_version_rather_than_a_shell_error(self):
        self.assertEqual(self.scan("--version-command", "definitely-not-a-scanner-binary --version").returncode, 0)
        record = self.record()
        self.assertIsNone(record["tool_version"])
        self.assertEqual(record["version_command"], "definitely-not-a-scanner-binary --version")

    def test_a_version_command_that_cannot_start_is_named_in_the_limitations(self):
        """RR-gate-4: the version went missing without a word, and nothing told the reader why."""
        self.scan("--version-command", "definitely-not-a-scanner-binary --version")
        limitations = self.record()["limitations"]
        self.assertEqual(["version command not run: executable not found on PATH: definitely-not-a-scanner-binary"],
                         limitations)

    def test_an_unquoted_windows_path_is_named_with_the_way_to_write_it(self):
        self.scan("--version-command", r"C:\Tools\pip-audit.exe --version")
        (gap,) = self.record()["limitations"]
        self.assertIn("executable not found on PATH: C:Toolspip-audit.exe", gap)
        self.assertIn("write the path with / or double each backslash", gap)

    def test_a_path_written_the_documented_way_is_not_reported_missing(self):
        script = self.root / "version.py"
        script.write_text("print('scanner 1.2')\n", encoding="utf-8")
        for spelling in (shlex.join([sys.executable, script.as_posix()]),
                         " ".join(['"' + sys.executable.replace("\\", "\\\\") + '"', script.as_posix()])):
            with self.subTest(spelling=spelling):
                self.scan("--version-command", spelling)
                record = self.record()
                self.assertEqual((record["tool_version"], record["limitations"]), ("scanner 1.2", []))

    def test_a_version_command_that_runs_adds_no_limitation_and_a_no_run_request_says_nothing_about_it(self):
        self.scan("--version-command", shlex.join(python("print('scanner 9.9')")))
        self.assertEqual(self.record()["limitations"], [])
        self.scan("--no-run", "--version-command", "definitely-not-a-scanner-binary --version")
        self.assertEqual(self.record()["limitations"], [])

    def test_no_version_command_leaves_both_fields_null(self):
        self.scan()
        record = self.record()
        self.assertEqual((record["tool_version"], record["version_command"]), (None, None))

    def test_a_no_run_request_records_the_version_command_without_running_it(self):
        marker = self.root / "probe-ran"
        version = shlex.join(python(f"open({str(marker)!r}, 'w').close()"))
        self.assertEqual(self.scan("--no-run", "--version-command", version).returncode, 0)
        self.assertFalse(marker.exists())
        record = self.record()
        self.assertEqual((record["result"]["status"], record["tool_version"]), ("not-run", None))
        self.assertEqual(shlex.split(record["version_command"]), shlex.split(version))


class ExitZeroWithFindingsTests(ScanRecordCase):
    FINDING = python("print('Found 3 vulnerabilities')")

    def test_a_plain_pass_records_only_that_the_scanner_exited_zero(self):
        self.assertEqual(self.scan(scanner=self.FINDING).returncode, 0)
        record = self.record()
        self.assertEqual((record["result"]["status"], record["exit_code"]), ("pass", 0))
        self.assertIn("not proof it found nothing", record["note"])

    def test_output_matching_a_pattern_turns_an_exit_zero_run_into_a_fail(self):
        self.assertEqual(self.scan("--fail-on-output", r"Found \d+ vulnerabilit", scanner=self.FINDING).returncode, 0)
        record = self.record()
        self.assertEqual((record["result"]["status"], record["exit_code"]), ("fail", 0))
        self.assertTrue(any("matched --fail-on-output" in item for item in record["limitations"]), record["limitations"])

    def test_the_pattern_is_read_from_stderr_as_well(self):
        scanner = python("import sys; print('WARNING: 2 findings', file=sys.stderr)")
        self.scan("--fail-on-output", "findings", scanner=scanner)
        self.assertEqual(self.record()["result"]["status"], "fail")

    def test_output_that_matches_no_pattern_stays_a_pass(self):
        self.scan("--fail-on-output", "CRITICAL", "--fail-on-output", "HIGH", scanner=python("print('clean')"))
        record = self.record()
        self.assertEqual(record["result"]["status"], "pass")
        self.assertEqual(record["limitations"], [])

    def test_a_pattern_never_upgrades_a_failed_run(self):
        self.scan("--fail-on-output", "never", scanner=python("import sys; sys.exit(7)"))
        self.assertEqual(self.record()["result"]["status"], "error")


class ArtifactNameTests(ScanRecordCase):
    def run_layout(self, phase: str = "security") -> Path:
        directory = self.root / "skillset-saves" / "runs" / "run-a" / phase / "evidence"
        directory.mkdir(parents=True)
        return directory / "vulnerability-scan.json"

    def test_a_record_inside_a_run_phase_names_its_output_relative_to_the_phase(self):
        out = self.run_layout()
        self.assertEqual(self.scan(out=out).returncode, 0)
        self.assertEqual(self.record(out)["artifacts"],
                         ["evidence/vulnerability-scan.stdout.txt", "evidence/vulnerability-scan.stderr.txt"])
        self.assertTrue((out.parent / "vulnerability-scan.stdout.txt").is_file())

    def test_a_record_outside_a_run_names_its_output_beside_itself(self):
        self.assertEqual(self.scan().returncode, 0)
        self.assertEqual(self.record()["artifacts"], ["scan.stdout.txt", "scan.stderr.txt"])

    def test_a_manifest_root_overrides_the_default(self):
        out = self.run_layout()
        self.assertEqual(self.scan("--manifest-root", str(out.parent.parent.parent), out=out).returncode, 0)
        self.assertEqual(self.record(out)["artifacts"][0], "security/evidence/vulnerability-scan.stdout.txt")

    def test_a_manifest_root_that_does_not_contain_the_record_is_a_wrapper_error(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        self.assert_wrapper_error(self.scan("--manifest-root", str(elsewhere)), "manifest root")
        self.assertFalse((self.root / "scan.stdout.txt").exists(), "no scanner output may be written for a refused run")

    def test_names_use_forward_slashes_on_every_platform(self):
        out = self.run_layout()
        self.scan(out=out)
        self.assertTrue(all("\\" not in name for name in self.record(out)["artifacts"]))


class GateRoundTripTests(ScanRecordCase):
    """The sanctioned tool in the sanctioned layout must produce evidence the gate accepts unedited."""

    def test_a_record_written_in_the_run_layout_passes_check_py_without_being_edited(self):
        run = self.root / "skillset-saves" / "runs" / "run-a"
        phase = run / "security"
        (phase / "evidence").mkdir(parents=True)
        (run / "_state.md").write_text(json.dumps({"run_id": "run-a"}), encoding="utf-8")
        (self.root / "requirements.txt").write_text("requests==2.32.0\n", encoding="utf-8")
        (phase / "threat.md").write_text("# Threat model\n\nAssets and entry points listed.\n", encoding="utf-8")
        (phase / "deny.md").write_text("# Deny paths\n\nProbe log attached.\n", encoding="utf-8")
        record_path = phase / "evidence" / "vulnerability-scan.json"
        proc = self.scan("--input", "requirements.txt", out=record_path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        record = self.record(record_path)
        self.assertEqual(record["artifacts"][0], "evidence/vulnerability-scan.stdout.txt")

        names = ("threat.md", "deny.md", *record["artifacts"])
        manifest = phase / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": 2, "run_id": "run-a", "boundary": "security-review", "owner": "cso",
            "submission_id": "sec-1", "revision": "r1", "revisions": ["r1"],
            "evidence": {
                "scope": "api", "threat_model": "threat.md", "findings": {"items": []},
                "vulnerability_scan": record,
                "denial_path_evidence": {"artifacts": ["deny.md"], "result": {"status": "pass"}},
                "remediation_plan": "none needed", "residual_risk": "none"},
            "artifact_hashes": {name: content_sha256(phase / name) for name in names}}), encoding="utf-8")
        gate = subprocess.run([sys.executable, str(CHECK), "--boundary", "security-review", "--package", str(manifest)],
                              capture_output=True, text=True, check=False)
        report = json.loads(gate.stdout)
        self.assertEqual(gate.returncode, 0, report["failures"])
        self.assertTrue(report["pass"])

    def test_the_same_record_names_are_refused_when_hashed_under_another_spelling(self):
        """The names are the artifact_hashes keys: a manifest that hashes `vulnerability-scan.stdout.txt` is not covered."""
        run = self.root / "skillset-saves" / "runs" / "run-a"
        phase = run / "security"
        (phase / "evidence").mkdir(parents=True)
        (run / "_state.md").write_text(json.dumps({"run_id": "run-a"}), encoding="utf-8")
        (self.root / "requirements.txt").write_text("requests==2.32.0\n", encoding="utf-8")
        (phase / "threat.md").write_text("# Threat model\n\nAssets listed.\n", encoding="utf-8")
        record_path = phase / "evidence" / "vulnerability-scan.json"
        self.assertEqual(self.scan("--input", "requirements.txt", out=record_path).returncode, 0)
        record = self.record(record_path)
        hashes = {"threat.md": content_sha256(phase / "threat.md"),
                  "evidence/vulnerability-scan.stdout.txt": content_sha256(phase / "evidence" / "vulnerability-scan.stdout.txt")}
        manifest = phase / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": 2, "run_id": "run-a", "boundary": "security-review", "owner": "cso",
            "submission_id": "sec-1", "revision": "r1", "revisions": ["r1"],
            "evidence": {"scope": "api", "threat_model": "threat.md", "findings": {"items": []},
                         "vulnerability_scan": record, "denial_path_evidence": "static analysis only - active probes not authorized",
                         "remediation_plan": "none", "residual_risk": "none"},
            "artifact_hashes": hashes}), encoding="utf-8")
        report = json.loads(subprocess.run([sys.executable, str(CHECK), "--boundary", "security-review", "--package", str(manifest)],
                                           capture_output=True, text=True, check=False).stdout)
        self.assertIn("evidence references unhashed path: vulnerability_scan -> evidence/vulnerability-scan.stderr.txt",
                      report["failures"])


if __name__ == "__main__":
    unittest.main()
