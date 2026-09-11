#!/usr/bin/env python3
"""Behavioural tests for the save lifecycle writer, output path resolver,
package check, scan recorder, and the agreement between ownership.yaml,
save-ownership.yaml, pipelines.yaml, and save-protocol.md."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
HOOKS = ROOT / "harness" / "hooks"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HOOKS))
from data_formats import load_data  # noqa: E402
from output_paths import resolve  # noqa: E402

SAVE_RUN = HOOKS / "save_run.py"
SCAN = SCRIPTS / "scan_record.py"
PACKAGE_CHECK = SCRIPTS / "package_check.py"


def run(script: Path, *args: str, cwd: Path | None = None) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True, check=False, cwd=str(cwd) if cwd else None)
    payload = {}
    for stream in (proc.stdout, proc.stderr):
        text = stream.strip()
        if text:
            try:
                payload = json.loads(text[text.index("{"):]) if "{" in text else {}
            except ValueError:
                payload = {"raw": text}
            if payload:
                break
    return proc.returncode, payload


class SaveLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        (self.project / "README.md").write_text("# fixture\n", encoding="utf-8")

    def save(self, *args: str) -> tuple[int, dict]:
        return run(SAVE_RUN, *args, "--project-root", str(self.project))

    def test_create_checkpoint_heartbeat_complete_lifecycle(self):
        code, out = self.save("create", "--run-id", "run-1", "--evidence", "README.md")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["revision"], 1)
        state = json.loads((self.project / "skillset-saves/runs/run-1/_state.md").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "active")
        self.assertTrue(state["session_pin"])
        self.assertIn("README.md", state["artifact_hashes"])
        pointer = json.loads((self.project / "skillset-saves/_latest.md").read_text(encoding="utf-8"))
        self.assertEqual(pointer["run_id"], "run-1")
        code, out = self.save("status", "--run-id", "run-1")
        self.assertEqual(out["status"], "active", out)

        (self.project / "notes.md").write_text("design decided\n", encoding="utf-8")
        code, out = self.save("checkpoint", "--run-id", "run-1", "--expect-revision", "1", "--evidence", "notes.md", "--next-action", "design-to-build")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["revision"], 2)
        self.assertTrue((self.project / "skillset-saves/runs/run-1/_history/rev-1.state.json").exists())
        code, out = self.save("checkpoint", "--run-id", "run-1", "--expect-revision", "1")
        self.assertEqual(code, 1)
        self.assertIn("revision conflict", out["reason"])

        code, out = self.save("heartbeat", "--run-id", "run-1")
        self.assertEqual(code, 0, out)
        code, out = self.save("complete", "--run-id", "run-1")
        self.assertEqual(code, 0, out)
        code, out = self.save("status", "--run-id", "run-1")
        self.assertEqual(out["status"], "inactive", out)
        lock = json.loads((self.project / "skillset-saves/runs/run-1/_lock.md").read_text(encoding="utf-8"))
        self.assertEqual(lock["status"], "released")
        self.assertFalse(lock["session_pin"])
        audit = (self.project / "skillset-saves/runs/run-1/_audit-trail.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["event"] for line in audit], ["create", "checkpoint", "complete"])

    def test_competing_owner_and_wrong_owner_are_refused(self):
        self.save("create", "--run-id", "run-1", "--evidence", "README.md")
        code, out = self.save("create", "--run-id", "run-2", "--evidence", "README.md")
        self.assertEqual(code, 1)
        self.assertIn("another run holds the session pin", out["reason"])
        code, out = self.save("checkpoint", "--run-id", "run-1", "--owner", "intruder")
        self.assertEqual(code, 1)
        self.assertIn("owned by", out["reason"])
        code, out = self.save("recover", "--run-id", "run-1", "--owner", "intruder", "--reason", "impatient")
        self.assertEqual(code, 1)
        self.assertIn("fresh and held by another owner", out["reason"])

    def test_unsafe_evidence_paths_are_refused(self):
        code, out = self.save("create", "--run-id", "run-1", "--evidence", "../outside.md")
        self.assertEqual(code, 1)
        self.assertIn("traversal", out["reason"])
        self.assertFalse((self.project / "skillset-saves/runs/run-1/_state.md").exists())

    def test_interrupted_checkpoint_is_visible_and_rolls_back(self):
        self.save("create", "--run-id", "run-1", "--evidence", "README.md")
        self.save("checkpoint", "--run-id", "run-1")
        run_dir = self.project / "skillset-saves/runs/run-1"
        # Simulate a crash after the journal and lock were written for revision 3.
        (run_dir / "_journal.json").write_text(json.dumps({"revision": 3, "step": "begin"}), encoding="utf-8")
        lock = json.loads((run_dir / "_lock.md").read_text(encoding="utf-8"))
        lock["revision"] = 3
        (run_dir / "_lock.md").write_text(json.dumps(lock), encoding="utf-8")
        code, out = self.save("status", "--run-id", "run-1")
        self.assertEqual(out["status"], "interrupted")
        code, out = self.save("checkpoint", "--run-id", "run-1")
        self.assertEqual(code, 1)
        self.assertIn("interrupted", out["reason"])
        code, out = self.save("recover", "--run-id", "run-1", "--rollback")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["revision"], 2)
        code, out = self.save("status", "--run-id", "run-1")
        self.assertEqual(out["status"], "active", out)

    def test_stale_lock_recovery_records_evidence(self):
        self.save("create", "--run-id", "run-1", "--evidence", "README.md")
        run_dir = self.project / "skillset-saves/runs/run-1"
        lock = json.loads((run_dir / "_lock.md").read_text(encoding="utf-8"))
        lock["heartbeat"] = "2020-01-01T00:00:00+00:00"
        (run_dir / "_lock.md").write_text(json.dumps(lock), encoding="utf-8")
        code, out = self.save("recover", "--run-id", "run-1", "--owner", "resumer")
        self.assertEqual(code, 1)
        self.assertIn("--reason", out["reason"])
        code, out = self.save("recover", "--run-id", "run-1", "--owner", "resumer", "--reason", "heartbeat older than 30 minutes")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["evidence"]["prior_heartbeat"], "2020-01-01T00:00:00+00:00")
        audit = [json.loads(line) for line in (run_dir / "_audit-trail.md").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(audit[-1]["event"], "recover")
        self.assertEqual(audit[-1]["prior_owner"], "admiral")

    def test_direct_edit_of_core_files_is_denied_by_hook(self):
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        for path in ("skillset-saves/runs/other/_state.md", "skillset-saves/_latest.md", "skillset-saves/runs/x/_history/rev-1.state.json"):
            with self.subTest(path=path):
                payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(self.project / path)}})
                proc = subprocess.run([sys.executable, str(HOOKS / "pre_tool_use.py")], input=payload, text=True, capture_output=True, env=env, check=False)
                self.assertIn("save_run.py", proc.stdout)
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(self.project / "skillset-saves/runs/other/design/reports/report_plan.md")}})
        proc = subprocess.run([sys.executable, str(HOOKS / "pre_tool_use.py")], input=payload, text=True, capture_output=True, env=env, check=False)
        self.assertEqual(proc.stdout.strip(), "")

    def test_direct_edit_of_durable_taste_profile_is_denied_by_hook(self):
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(self.project)
        payload = json.dumps({"tool_name": "Write", "tool_input": {
            "file_path": str(self.project / "skillset-saves/preferences/taste.json")}})
        proc = subprocess.run([sys.executable, str(HOOKS / "pre_tool_use.py")],
                              input=payload, text=True, capture_output=True, env=env, check=False)
        self.assertIn("taste_prefs.py", proc.stdout)


class OutputPathTests(unittest.TestCase):
    def test_every_kind_resolves_inside_project(self):
        root = Path(tempfile.gettempdir()) / "admiral-output-paths"
        cases = {
            "manifest": dict(run_id="r1", phase="design"),
            "reports": dict(run_id="r1", phase="design", name="report_plan.md"),
            "artifacts": dict(run_id="r1", phase="design-system", name="tokens.css"),
            "evidence": dict(run_id="r1", phase="security", name="scan-pip-audit.json"),
            "packages": dict(run_id="r1", phase="skill-creation", name="my-skill.skill"),
            "verdict": dict(run_id="r1", phase="review", boundary="review-to-delivery"),
            "core": dict(run_id="r1", name="_state.md"),
            "preferences": {},
            "trajectory": dict(run_id="r1", session="abc"),
            "product": dict(name="src/app.css"),
            "design_spec": {},
        }
        for kind, kwargs in cases.items():
            with self.subTest(kind=kind):
                target = resolve(root, kind, **kwargs)
                target.resolve().relative_to(root.resolve())
        with self.assertRaises(ValueError):
            resolve(root, "artifacts", run_id="r1", phase="design", name="../escape.css")
        with self.assertRaises(ValueError):
            resolve(root, "manifest", run_id="../x", phase="design")
        with self.assertRaises(ValueError):
            resolve(root, "core", run_id="r1", name="manifest.json")


class ScanRecordTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        (self.project / "requirements.txt").write_text("requests==2.32.0\n", encoding="utf-8")

    def scan(self, *command: str, extra: tuple[str, ...] = ()) -> tuple[int, dict, dict]:
        out = self.project / "evidence" / "scan.json"
        code, summary = run(SCAN, "--project-root", str(self.project), "--out", str(out), "--input", "requirements.txt", *extra, "--", *command)
        record = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
        return code, summary, record

    def test_pass_fail_error_unavailable_and_not_run_are_distinguished(self):
        code, summary, record = self.scan(sys.executable, "-c", "print('0 vulnerabilities')")
        self.assertEqual(code, 0)
        self.assertEqual(record["result"]["status"], "pass")
        self.assertEqual(record["inputs"][0]["path"], "requirements.txt")
        self.assertTrue((self.project / "evidence" / "scan.stdout.txt").exists())
        _, _, record = self.scan(sys.executable, "-c", "import sys; print('1 vulnerability'); sys.exit(1)")
        self.assertEqual(record["result"]["status"], "fail")
        _, _, record = self.scan(sys.executable, "-c", "import sys; sys.exit(7)")
        self.assertEqual(record["result"]["status"], "error")
        _, _, record = self.scan("definitely-not-a-scanner-binary")
        self.assertEqual(record["result"]["status"], "unavailable")
        _, _, record = self.scan(sys.executable, "-c", "pass", extra=("--no-run",))
        self.assertEqual(record["result"]["status"], "not-run")


class PackageCheckTests(unittest.TestCase):
    def test_residue_is_reported_and_clean_root_builds_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skills = root / "skills"
            for rel in ("gates.yaml", "pipelines.yaml", "ownership.yaml", "save-ownership.yaml",
                        "team-manifest.yaml", "runtime-manifest.yaml", "tech-stacks/registry.yaml",
                        "harness/gatekeeper/check.py", "harness/hooks/save_run.py"):
                target = skills / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x\n", encoding="utf-8")
            (root / ".harness-state").mkdir()
            (root / ".harness-state" / "guard-state.json").write_text("{}", encoding="utf-8")
            (skills / "__pycache__").mkdir()
            (skills / "__pycache__" / "x.pyc").write_bytes(b"\x00")
            (skills / "deploy.pem").write_text("PRIVATE", encoding="utf-8")
            code, report = run(PACKAGE_CHECK, "--root", str(root))
            self.assertEqual(code, 1, report)
            classes = {v["class"] for v in report["violations"]}
            self.assertIn("secrets", classes)
            self.assertNotIn("runtime-state", classes, "manifest exclude must drop .harness-state before residue scan")
            self.assertNotIn("interpreter-cache", classes, "manifest exclude must drop caches before residue scan")
            (skills / "deploy.pem").unlink()
            code, report = run(PACKAGE_CHECK, "--root", str(root), "--out", str(root / "dist" / "supremeteam.zip"))
            self.assertEqual(code, 0, report)
            self.assertTrue((root / "dist" / "supremeteam.zip").exists())

    def test_repository_package_enumeration_is_clean(self):
        code, report = run(PACKAGE_CHECK, "--root", str(ROOT.parent))
        self.assertEqual(code, 0, report)

    def test_preference_state_is_excluded_from_packages(self):
        manifest = load_data(ROOT / "package-manifest.yaml")
        self.assertIn("skillset-saves/**", manifest["exclude"])
        self.assertIn(".supremeteam/**", manifest["exclude"])


class OwnershipAgreementTests(unittest.TestCase):
    def test_save_ownership_agrees_with_ownership_and_pipelines(self):
        ownership = load_data(ROOT / "ownership.yaml")
        save_ownership = load_data(ROOT / "save-ownership.yaml")
        classes = {c["id"]: c for c in save_ownership["classes"]}
        self.assertEqual(classes["core-run-record"]["writer"], "session-memory")
        self.assertEqual(classes["gate-verdict"]["writer"], "gatekeeper")
        self.assertEqual(classes["grilling-log"]["writer"], "admiral")
        self.assertIn("grilling-log", set(ownership["owners"]["admiral"]["writes"]))
        self.assertIn("run-state", set(ownership["owners"]["session-memory"]["writes"]))
        for tool_class in ("core-run-record", "gate-verdict"):
            tool = classes[tool_class]["tool"].split()[0]
            self.assertTrue((ROOT.parent / tool).is_file(), tool)
        for klass in classes.values():
            for pattern in klass["patterns"]:
                self.assertFalse(pattern.startswith("/"), pattern)
                self.assertNotIn("..", pattern)

    def test_every_pipeline_phase_has_a_save_directory(self):
        save_ownership = load_data(ROOT / "save-ownership.yaml")
        directories = set(save_ownership["phase_directories"])
        pipelines = json.loads((ROOT / "pipelines.yaml").read_text(encoding="utf-8"))["pipelines"]
        for name in pipelines:
            with self.subTest(pipeline=name):
                phase = "preferences" if name == "taste" else name
                self.assertIn(phase, directories | {"design", "build", "review"})
        self.assertIn("skills/scripts/scan_record.py", pipelines["security"]["scripts"])
        self.assertIn("preferences", directories)
        self.assertIn("skills/taste/taste_prefs.py", pipelines["taste"]["scripts"])

    def test_save_protocol_points_at_the_machine_contracts(self):
        protocol = (ROOT / "save-protocol.md").read_text(encoding="utf-8")
        for reference in ("save-ownership.yaml", "save_run.py", "_journal.json"):
            self.assertIn(reference, protocol)


if __name__ == "__main__":
    unittest.main()
