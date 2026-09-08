#!/usr/bin/env python3
"""Host-observed hook firing and save-writer roll-forward (second remediation pass, 2026-09-05)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent


def env_for(project: Path) -> dict:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return env


def fire(script: str, payload: dict, project: Path) -> str:
    proc = subprocess.run([sys.executable, str(HOOK_DIR / script)], input=json.dumps(payload), text=True, capture_output=True,
                          env=env_for(project), check=False)
    return proc.stdout


class ObservationTests(unittest.TestCase):
    def test_real_host_payload_records_observed_and_synthetic_records_simulated(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fire("pre_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, project)
            record = json.loads((project / ".harness-state" / "observations" / "PreToolUse.json").read_text(encoding="utf-8"))
            self.assertIn("simulated", record)
            self.assertNotIn("observed", record)
            fire("pre_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}, project)
            fire("post_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_response": {"exit_code": 0, "stdout": "ok"}}, project)
            fire("user_prompt_submit.py", {"session_id": "host-1", "prompt": "hello"}, project)
            record = json.loads((project / ".harness-state" / "observations" / "PreToolUse.json").read_text(encoding="utf-8"))
            self.assertEqual(record["observed"]["count"], 1)
            self.assertNotIn("host-1", json.dumps(record), "session ids are hashed, never stored")
            proc = subprocess.run([sys.executable, str(HOOK_DIR / "check_readiness.py"), "--host", "claude", "--project-root", str(project), "--json"],
                                  text=True, capture_output=True, env=env_for(project), check=False)
            data = json.loads(proc.stdout)
            self.assertEqual(data["capabilities"]["hooks_observed"], "observed")
            self.assertEqual({e["state"] for e in data["hooks"]["observations"].values()}, {"observed"})

    def test_readiness_reports_partial_when_only_some_events_observed(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fire("pre_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}, project)
            proc = subprocess.run([sys.executable, str(HOOK_DIR / "check_readiness.py"), "--host", "claude", "--project-root", str(project), "--json"],
                                  text=True, capture_output=True, env=env_for(project), check=False)
            self.assertEqual(json.loads(proc.stdout)["capabilities"]["hooks_observed"], "partial")


class RollForwardTests(unittest.TestCase):
    def test_pointer_only_interruption_rolls_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "README.md").write_text("x", encoding="utf-8")
            save = lambda *a: subprocess.run([sys.executable, str(HOOK_DIR / "save_run.py"), *a, "--project-root", str(project), "--run-id", "r1"],
                                             text=True, capture_output=True, check=False)
            save("create", "--evidence", "README.md")
            save("checkpoint")
            run_dir = project / "skillset-saves" / "runs" / "r1"
            # Core publish of revision 2 completed; only the pointer/journal step was lost.
            (run_dir / "_journal.json").write_text(json.dumps({"revision": 2, "step": "begin"}), encoding="utf-8")
            (project / "skillset-saves" / "_latest.md").write_text(json.dumps({"schema_version": 1, "run_id": "r1", "revision": 1, "updated_at": "2026-09-05T00:00:00+00:00"}), encoding="utf-8")
            out = json.loads(save("recover", "--rollback").stdout)
            self.assertEqual(out["operation"], "rollforward", out)
            self.assertEqual(out["revision"], 2)
            pointer = json.loads((project / "skillset-saves" / "_latest.md").read_text(encoding="utf-8"))
            self.assertEqual(pointer["revision"], 2)
            self.assertEqual(json.loads(save("status").stdout)["status"], "active")


if __name__ == "__main__":
    unittest.main()
