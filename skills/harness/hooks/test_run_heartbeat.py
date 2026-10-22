#!/usr/bin/env python3
"""The heartbeat every registered hook refreshes on a host event (``run_heartbeat.py``), run through the real scripts.

A payload with a host ``session_id`` refreshes the lock of the lone live run once its heartbeat is older than the
throttle, and rewrites a damaged pointer from that run; a synthetic payload, a recent heartbeat, a stale lock and an
interrupted run are left as they are, and the prompt hook still says whether a run is active.
"""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import _testkit as kit


def fire(script: str, payload: dict, project: Path) -> str:
    return kit.run_hook(script, payload, project).stdout.decode("utf-8")


def lock_of(project: Path, run_id: str) -> dict:
    return json.loads((project / "skillset-saves" / "runs" / run_id / "_lock.md").read_text(encoding="utf-8"))


def backdate_lock(project: Path, run_id: str, minutes: int) -> None:
    lock = lock_of(project, run_id)
    lock["heartbeat"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    (project / "skillset-saves" / "runs" / run_id / "_lock.md").write_text(json.dumps(lock), encoding="utf-8")


class HookHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.project = self.enterContext(kit.project())
        (self.project / "README.md").write_text("# fixture\n", encoding="utf-8")
        code, out = kit.save(self.project, "run-1", "create", "--evidence", "README.md")
        self.assertEqual(code, 0, out)

    def test_real_host_event_refreshes_a_fresh_lock_older_than_the_throttle(self):
        backdate_lock(self.project, "run-1", 12)
        before = lock_of(self.project, "run-1")["heartbeat"]
        fire("pre_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, self.project)
        self.assertEqual(lock_of(self.project, "run-1")["heartbeat"], before, "synthetic payloads never touch save state")
        fire("pre_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}, self.project)
        lock = lock_of(self.project, "run-1")
        self.assertNotEqual(lock["heartbeat"], before)
        self.assertEqual(lock["heartbeat_source"], "hook:PreToolUse")
        pointer = json.loads((self.project / "skillset-saves/_latest.md").read_text(encoding="utf-8"))
        self.assertEqual(pointer["updated_at"], lock["heartbeat"])
        code, out = kit.save(self.project, "run-1", "status")
        self.assertEqual(out["status"], "active", out)

    def test_a_host_event_rewrites_a_damaged_pointer_from_the_lone_live_run(self):
        """The refresh asked for an `active` or `orphaned` save root, so behind a damaged pointer the live run went stale."""
        backdate_lock(self.project, "run-1", 12)
        pointer = self.project / "skillset-saves/_latest.md"
        pointer.write_text("{", encoding="utf-8")
        self.assertEqual(kit.save(self.project, "run-1", "status")[1]["detail"], "pointer missing or malformed")
        fire("pre_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}, self.project)
        lock = lock_of(self.project, "run-1")
        self.assertEqual(lock["heartbeat_source"], "hook:PreToolUse")
        self.assertEqual(json.loads(pointer.read_text(encoding="utf-8"))["updated_at"], lock["heartbeat"])
        self.assertEqual(kit.save(self.project, "run-1", "status")[1]["status"], "active")

    def test_recent_heartbeat_is_not_rewritten_on_every_call(self):
        before = lock_of(self.project, "run-1")["heartbeat"]
        fire("post_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"},
                                  "tool_response": {"exit_code": 0, "stdout": "ok"}}, self.project)
        self.assertEqual(lock_of(self.project, "run-1")["heartbeat"], before)

    def test_stale_lock_is_never_revived_by_a_hook(self):
        backdate_lock(self.project, "run-1", 45)
        before = lock_of(self.project, "run-1")["heartbeat"]
        out = fire("user_prompt_submit.py", {"session_id": "host-1", "prompt": "keep going"}, self.project)
        self.assertEqual(lock_of(self.project, "run-1")["heartbeat"], before)
        self.assertIn("no active run", json.loads(out)["hookSpecificOutput"]["additionalContext"])

    def test_prompt_hook_refreshes_and_reinforces_the_pin(self):
        backdate_lock(self.project, "run-1", 12)
        out = fire("user_prompt_submit.py", {"session_id": "host-1", "prompt": "keep going"}, self.project)
        self.assertIn("a run is active", json.loads(out)["hookSpecificOutput"]["additionalContext"])
        self.assertEqual(lock_of(self.project, "run-1")["heartbeat_source"], "hook:UserPromptSubmit")

    def test_interrupted_run_is_left_alone(self):
        backdate_lock(self.project, "run-1", 12)
        run_dir = self.project / "skillset-saves/runs/run-1"
        (run_dir / "_journal.json").write_text(json.dumps({"revision": 2, "step": "begin"}), encoding="utf-8")
        before = lock_of(self.project, "run-1")["heartbeat"]
        fire("pre_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}, self.project)
        self.assertEqual(lock_of(self.project, "run-1")["heartbeat"], before)


if __name__ == "__main__":
    unittest.main()
