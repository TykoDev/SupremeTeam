#!/usr/bin/env python3
"""Focused regression tests for the bounded audit and advisory trigger."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HOOKS = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS))
import audit_improve as subject  # noqa: E402


class AuditImproveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.run = self.root / "skillset-saves" / "runs" / "r1"
        self.run.mkdir(parents=True)
        (self.root / ".harness-state" / "trajectories" / "r1").mkdir(parents=True)

    def record(self, path: Path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def seed(self):
        self.record(self.root / "skillset-saves" / "_latest.md", {"run_id": "r1", "revision": 2})
        self.record(self.run / "_state.md", {"status": "active", "revision": 2})
        self.record(self.run / "_lock.md", {"status": "held", "revision": 1})
        (self.run / "_audit-trail.md").write_text(
            json.dumps({"event": "degraded", "error": "SECRET_DO_NOT_ECHO"}) + "\n"
            + json.dumps({"event": "rollback", "reason": "SECRET_DO_NOT_ECHO"}) + "\n", encoding="utf-8")
        self.record(self.run / "build" / "verdict_build-to-review.json", {"verdict": "REVISE", "details": "SECRET_DO_NOT_ECHO"})
        self.record(self.root / ".harness-state" / "trajectories" / "r1" / "session.json", [
            {"sig": "private-input-signature", "failed": True, "empty": False},
            {"sig": "private-input-signature", "failed": True, "empty": True},
            {"sig": "different", "failed": True, "empty": False},
        ])

    def test_correlates_state_failure_history_and_redacts_payloads(self):
        self.seed()
        report = subject.audit(self.root)
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("revision_mismatch", codes)
        self.assertIn("failure_history", codes)
        self.assertEqual(report["run_statuses"], {"active": 1})
        history = next(item for item in report["findings"] if item["code"] == "failure_history")
        self.assertEqual(history["audit_events"], {"degraded": 1, "rollback": 1})
        self.assertEqual(history["gate_verdicts"], {"REVISE": 1})
        self.assertEqual(history["failed_steps"], 3)
        self.assertEqual(history["consecutive_failed_signatures"], 1)
        self.assertEqual(report["run_history"], [{"run": subject._id("r1"),
                                                  "audit_events": {"degraded": 1, "rollback": 1},
                                                  "gate_verdicts": {"REVISE": 1}}])
        self.assertEqual(report["trajectory_history"], [{"run": subject._id("r1"),
                                                         "trajectory": subject._id("session.json"),
                                                         "failed_steps": 3, "empty_steps": 1,
                                                         "consecutive_failed_signatures": 1}])
        rendered = json.dumps(report)
        self.assertNotIn("SECRET_DO_NOT_ECHO", rendered)
        self.assertNotIn("private-input-signature", rendered)
        self.assertNotIn("r1", rendered)

    def test_oversized_and_invalid_records_are_reported_without_reading_contents(self):
        self.record(self.run / "_lock.md", {"revision": 1})
        (self.run / "_state.md").write_bytes(b"X" * (subject.MAX_RECORD + 1))
        (self.run / "_audit-trail.md").write_text("not json\n", encoding="utf-8")
        report = subject.audit(self.root)
        unreadable = next(item for item in report["findings"] if item["code"] == "unreadable_records")
        self.assertEqual(unreadable["counts"]["state:too_large"], 1)
        self.assertEqual(unreadable["counts"]["audit:invalid_line"], 1)

    def test_unreadable_records_identify_the_hashed_source_among_runs(self):
        other = self.root / "skillset-saves" / "runs" / "r2"
        other.mkdir(parents=True)
        self.record(self.run / "_state.md", {"status": "active", "revision": 1})
        self.record(other / "_state.md", {"status": "active", "revision": 1})
        (other / "_lock.md").write_bytes(b"X" * (subject.MAX_RECORD + 1))
        report = subject.audit(self.root)
        lock_error = next(item for item in report["record_errors"]
                          if item["record"] == "lock" and item["reason"] == "too_large")
        self.assertEqual(lock_error["run"], subject._id("r2"))
        self.assertNotEqual(lock_error["run"], subject._id("r1"))

    def test_guard_and_hook_observations_are_summarized_without_values(self):
        self.record(self.root / ".harness-state" / "guard-state.json", {
            "frozen_globs": [{"glob": "private/SECRET_DO_NOT_ECHO/**"},
                             {"glob": "released/**", "released_at": "yesterday"}],
            "blocked_globs": ["sensitive/**"],
        })
        self.record(self.root / ".harness-state" / "observations" / "PostToolUse.json", {
            "observed": {"count": 12, "session_hash": "SECRET_DO_NOT_ECHO"}})
        report = subject.audit(self.root)
        self.assertEqual(report["guard_state"], {"frozen_globs": 1, "blocked_globs": 1})
        self.assertEqual(report["hook_observations"], {"PostToolUse": 12})
        self.assertNotIn("SECRET_DO_NOT_ECHO", json.dumps(report))

    def test_large_audit_log_reports_incomplete_tail(self):
        self.record(self.run / "_state.md", {"status": "active", "revision": 1})
        self.record(self.run / "_lock.md", {"status": "held", "revision": 1})
        (self.run / "_audit-trail.md").write_text(
            "X" * subject.MAX_AUDIT_TAIL + "\n" + json.dumps({"event": "degraded"}) + "\n",
            encoding="utf-8")
        report = subject.audit(self.root)
        self.assertEqual(report["coverage"]["audit_tails_truncated"], 1)
        self.assertIn("audit_tail_truncated", {f["code"] for f in report["findings"]})
        self.assertIsNotNone(subject.maybe_audit(self.root, now=1000))

    def test_cooldown_suppresses_automatic_repeat_and_force_is_read_only(self):
        self.seed()
        first = subject.maybe_audit(self.root, now=1000)
        self.assertIsNotNone(first)
        marker = self.root / ".harness-state" / "observations" / "audit-improve.json"
        self.assertTrue(marker.exists())
        self.assertIsNone(subject.maybe_audit(self.root, now=1001))
        old = marker.read_bytes()
        self.assertIsNotNone(subject.maybe_audit(self.root, force=True, now=1002))
        self.assertEqual(marker.read_bytes(), old)
        self.assertIsNotNone(subject.maybe_audit(self.root, now=1000 + subject.COOLDOWN_SECONDS))

    def test_quiet_automatic_path_does_not_create_marker(self):
        self.record(self.run / "_state.md", {"status": "active", "revision": 1})
        self.record(self.run / "_lock.md", {"status": "held", "revision": 1})
        (self.run / "_audit-trail.md").write_text(json.dumps({"event": "create"}) + "\n", encoding="utf-8")
        report = subject.maybe_audit(self.root, now=1000)
        self.assertIsNone(report)
        self.assertFalse((self.root / ".harness-state" / "observations" / "audit-improve.json").exists())

    def test_cooldown_never_writes_through_observations_symlink(self):
        self.seed()
        outside = self.root / "outside"
        outside.mkdir()
        link = self.root / ".harness-state" / "observations"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable on this host")
        report = subject.maybe_audit(self.root, now=1000)
        self.assertIsNotNone(report)
        self.assertFalse((outside / "audit-improve.json").exists())
        self.assertIn("observation_root_symlink", {f["code"] for f in report["findings"]})

    def test_cooldown_refuses_a_linked_parent_even_without_symlink_support(self):
        self.seed()
        parent = self.root / ".harness-state" / "observations"
        original = subject._is_link
        with patch.object(subject, "_is_link", side_effect=lambda path: Path(path) == parent or original(path)):
            report = subject.maybe_audit(self.root, now=1000)
        self.assertIsNotNone(report)
        self.assertFalse((parent / "audit-improve.json").exists())

    def test_explicit_hook_trigger_only(self):
        self.seed()
        env = os.environ.copy()
        command = [sys.executable, str(HOOKS / "audit_improve.py"), "--project-root", str(self.root)]
        silent = subprocess.run(command, input=json.dumps({"prompt": "please review code"}),
                                text=True, capture_output=True, env=env, check=False)
        self.assertEqual(silent.returncode, 0)
        self.assertEqual(silent.stdout, "")
        triggered = subprocess.run(command, input=json.dumps({"prompt": "/audit-improve now"}),
                                   text=True, capture_output=True, env=env, check=False)
        self.assertEqual(triggered.returncode, 0)
        output = json.loads(triggered.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        self.assertIn("skill-maker", output["additionalContext"])
        self.assertFalse((self.root / ".harness-state" / "observations" / "audit-improve.json").exists())

    def test_registered_prompt_and_post_hooks_surface_the_audit(self):
        self.seed()
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(self.root)
        prompt = subprocess.run([sys.executable, str(HOOKS / "user_prompt_submit.py")],
                                input=json.dumps({"prompt": "/audit-improve", "session_id": "s1"}),
                                text=True, capture_output=True, env=env, check=False)
        self.assertEqual(prompt.returncode, 0, prompt.stderr)
        self.assertIn("audit-improve trigger", prompt.stdout)
        failure = {"tool_name": "Bash", "tool_input": {"command": "test-failure"},
                   "tool_response": {"exit_code": 1, "stderr": "fixture failure"}, "session_id": "s1"}
        outputs = []
        for _ in range(3):
            proc = subprocess.run([sys.executable, str(HOOKS / "post_tool_use.py")],
                                  input=json.dumps(failure), text=True, capture_output=True,
                                  env=env, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs.append(proc.stdout)
        self.assertIn("audit-improve trigger", outputs[-1])
        self.assertNotIn("SECRET_DO_NOT_ECHO", outputs[-1])

    def test_run_scan_is_bounded(self):
        for index in range(subject.MAX_RUNS + 2):
            (self.root / "skillset-saves" / "runs" / f"run-{index:02d}").mkdir()
        report = subject.audit(self.root)
        self.assertTrue(report["coverage"]["runs_truncated"])
        self.assertEqual(report["coverage"]["runs_scanned"], subject.MAX_RUNS)

    def test_reads_records_written_by_canonical_save_writer(self):
        self.run.rmdir()
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
        proc = subprocess.run([
            sys.executable, str(HOOKS / "save_run.py"), "create",
            "--project-root", str(self.root), "--run-id", "r1",
            "--evidence", "README.md",
        ], text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = subject.audit(self.root)
        self.assertEqual(report["run_statuses"], {"active": 1})
        self.assertNotIn("unreadable_records", {f["code"] for f in report["findings"]})


if __name__ == "__main__":
    unittest.main()
