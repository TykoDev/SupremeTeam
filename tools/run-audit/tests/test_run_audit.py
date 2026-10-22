"""Tests for run-audit (design package pi-deploy-02, acceptance AC-1 to AC-5)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_audit

CATALOG_SCRIPTS = Path(__file__).resolve().parents[3] / "skills" / "scripts"
if (CATALOG_SCRIPTS / "data_formats.py").is_file():
    sys.path.insert(0, str(CATALOG_SCRIPTS))
    import data_formats
else:  # the deployed copy ships without the catalog
    data_formats = None


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def make_run(root: Path, run_id: str, status: str, revisions: list[int]) -> Path:
    run = root / "skillset-saves" / "runs" / run_id
    run.mkdir(parents=True, exist_ok=True)
    write_json(run / "_state.md", {"run_id": run_id, "status": status,
                                   "phase_state": "RUN_COMPLETE", "revision": revisions[-1]})
    lines = []
    for number, revision in enumerate(revisions, start=1):
        lines.append(json.dumps({"at": f"2026-10-11T10:00:{number:02d}+00:00",
                                 "event": "checkpoint", "owner": "admiral", "revision": revision}))
    (run / "_audit-trail.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run


class ScanTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "skillset-saves" / "runs").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_scan_reports_every_run_with_revisions_and_terminal_state(self):
        make_run(self.root, "alpha", "complete", [1, 2, 3])
        make_run(self.root, "beta", "active", [1])
        runs, findings = run_audit.scan_runs(self.root)
        self.assertEqual([run["run_id"] for run in runs], ["alpha", "beta"])
        self.assertEqual([run["revisions"] for run in runs], [3, 1])
        self.assertEqual([run["terminal"] for run in runs], ["complete", "active"])
        self.assertEqual(findings, [])

    def test_scan_reports_evidence_drift_and_passes_clean_hashes(self):
        run = make_run(self.root, "alpha", "complete", [1])
        phase = run / "build"
        phase.mkdir()
        artifact = phase / "report.md"
        artifact.write_text("# report\n", encoding="utf-8")
        write_json(phase / "manifest.json", {
            "boundary": "build-to-review",
            "artifact_hashes": {"report.md": run_audit.content_sha256(artifact)},
        })
        runs, findings = run_audit.scan_runs(self.root)
        self.assertEqual(runs[0]["evidence_drift"], [])
        self.assertEqual(findings, [])
        artifact.write_text("# report, changed\n", encoding="utf-8")
        runs, findings = run_audit.scan_runs(self.root)
        drift = runs[0]["evidence_drift"]
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["path"], "report.md")
        self.assertEqual(drift[0]["kind"], "hash-drift")
        self.assertTrue(any("report.md" in finding["statement"] for finding in findings))

    def test_digest_matches_the_gate_line_ending_folding(self):
        if data_formats is None:
            self.skipTest("catalog data_formats module not available from this layout")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = {
                "crlf.txt": b"a\r\nb\r\n",
                "lone-cr.txt": b"a\rb\r",
                "mixed.txt": b"a\r\nb\nc\r",
                "binary.bin": b"\x00\r\n\xff\r\n",
            }
            for name, payload in cases.items():
                path = root / name
                path.write_bytes(payload)
                self.assertEqual(run_audit.content_sha256(path),
                                 data_formats.content_sha256(path), name)

    def test_scan_survives_malformed_state_and_reports_it(self):
        make_run(self.root, "alpha", "complete", [1])
        broken = self.root / "skillset-saves" / "runs" / "broken"
        broken.mkdir()
        (broken / "_state.md").write_text("{not json", encoding="utf-8")
        runs, findings = run_audit.scan_runs(self.root)
        self.assertEqual([run["run_id"] for run in runs], ["alpha", "broken"])
        self.assertTrue(any("_state.md" in finding["where"] for finding in findings))
        self.assertTrue(all(finding["severity"] in run_audit.SEVERITIES for finding in findings))


class RenderTests(unittest.TestCase):
    def model(self):
        return {
            "generated_at": "2026-10-11T10:00:00+00:00",
            "tool_version": run_audit.TOOL_VERSION,
            "project_root": "/tmp/<script>alert(1)</script>",
            "runs": [{
                "run_id": "alpha<img src=x onerror=alert(2)>",
                "revisions": 2,
                "terminal": "complete",
                "phase_state": "RUN_COMPLETE",
                "event_count": 1,
                "events": [],
                "manifests": [],
                "gate_verdicts": [{"file": "a.json", "boundary": "build-to-review",
                                   "verdict": "APPROVED", "gate": "gatekeeper-build",
                                   "pass": True, "gate_spec_is_shipped": True}],
                "evidence_drift": [{"manifest": "m.json", "path": "r.md",
                                    "expected": "e", "actual": "a", "kind": "hash-drift"}],
            }],
            "harness": {"observations": {"PreToolUse": {"at": "2026-10-11T10:00:00Z", "count": 3}},
                        "trajectories": {}},
            "findings": [{"id": "F-1", "severity": "Critical",
                          "statement": "<script>alert(3)</script> bad",
                          "where": "x.json"}],
        }

    def test_report_html_is_self_contained_and_escaped(self):
        rendered = run_audit.render_html(self.model())
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered)
        self.assertIn("&lt;script&gt;alert(3)&lt;/script&gt;", rendered)
        self.assertNotIn("<script>alert(3)</script>", rendered)
        self.assertNotIn("<img src=x onerror=alert(2)>", rendered)
        for marker in ("http://", "https://", "@import", "<img", "<link", "<script src"):
            self.assertNotIn(marker, rendered)

    def test_report_html_carries_theme_tokens_and_breakpoints(self):
        rendered = run_audit.render_html(self.model())
        self.assertIn("--bg", rendered)
        self.assertIn("--sev-critical", rendered)
        self.assertIn("@media (prefers-color-scheme: dark)", rendered)
        self.assertIn("@media (max-width: 960px)", rendered)
        self.assertIn("@media (max-width: 640px)", rendered)
        self.assertIn('aria-pressed', rendered)


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "skillset-saves" / "runs").mkdir(parents=True)
        self.out = self.root / "out"

    def tearDown(self):
        self._tmp.cleanup()

    def test_exit_codes_follow_policy(self):
        run = make_run(self.root, "alpha", "complete", [1])
        clean = run_audit.main(["--project-root", str(self.root), "--out", str(self.out),
                                "--fail-on", "high"])
        self.assertEqual(clean, 0)
        phase = run / "build"
        phase.mkdir()
        write_json(phase / "manifest.json", {"boundary": "build-to-review",
                                             "artifact_hashes": {"report.md": "0" * 64}})
        drifted = run_audit.main(["--project-root", str(self.root), "--out", str(self.out),
                                  "--fail-on", "high"])
        self.assertEqual(drifted, 1)
        broken = self.root / "skillset-saves" / "runs" / "broken"
        broken.mkdir()
        (broken / "_state.md").write_text("{not json", encoding="utf-8")
        tolerated = run_audit.main(["--project-root", str(self.root), "--out", str(self.out),
                                    "--fail-on", "none"])
        self.assertEqual(tolerated, 0)
        any_findings = run_audit.main(["--project-root", str(self.root), "--out", str(self.out),
                                       "--fail-on", "any"])
        self.assertEqual(any_findings, 1)
        with self.assertRaises(SystemExit) as caught:
            run_audit.main(["--no-such-flag"])
        self.assertEqual(caught.exception.code, 2)


class DeployTests(unittest.TestCase):
    def test_deployed_copy_reports_version_and_writes_both_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "deploy" / "run-audit"
            target.mkdir(parents=True)
            shutil.copy2(Path(run_audit.__file__), target / "run_audit.py")
            (root / "skillset-saves" / "runs").mkdir(parents=True)
            make_run(root, "alpha", "complete", [1])
            version = subprocess.run(
                [sys.executable, str(target / "run_audit.py"), "--version"],
                capture_output=True, text=True, cwd=tmp, check=False)
            self.assertEqual(version.returncode, 0)
            self.assertEqual(version.stdout.strip(), f"run-audit {run_audit.TOOL_VERSION}")
            scan = subprocess.run(
                [sys.executable, str(target / "run_audit.py"), "--project-root", str(root),
                 "--out", str(target / "report"), "--format", "both"],
                capture_output=True, text=True, cwd=tmp, check=False)
            self.assertEqual(scan.returncode, 0, scan.stderr)
            self.assertTrue((target / "report" / "report.json").is_file())
            self.assertTrue((target / "report" / "report.html").is_file())


if __name__ == "__main__":
    unittest.main()
