#!/usr/bin/env python3
"""The prompt hook (``user_prompt_submit.py``): the routing reminder, the session-pin reminder, and its fault trace.

A natural-language prompt gets the reminder that ``admiral`` is the entry orchestrator; a slash command or an empty
prompt gets nothing. The pin reminder follows the saves reader: a run that holds the session (active, orphaned from the
pointer, conflicting with another held run, or waiting on the user in a dispute) keeps it on, and a delivered run, a
stale lock or a legacy flat state turns it off. The hook fails open, and a fault it swallows is counted (CR-13).
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import _state
import _testkit as kit


def prompt(payload, project):
    return kit.run_hook("user_prompt_submit.py", payload, project, text=True)


class UserPromptSubmitTests(unittest.TestCase):
    def _ctx(self, result) -> str:
        self.assertEqual(result.returncode, 0)
        if not result.stdout.strip():
            return ""
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_natural_language_injects_route_reminder(self):
        with kit.project() as project:
            result = prompt({"prompt": "design this system"}, project)
        self.assertIn("primary entry orchestrator", self._ctx(result))
        self.assertIn("`admiral`", self._ctx(result))

    def test_slash_command_stays_silent(self):
        with kit.project() as project:
            result = prompt({"prompt": "/freeze src/payments"}, project)
        self.assertEqual(result.stdout, "")

    def test_empty_prompt_stays_silent(self):
        with kit.project() as project:
            result = prompt({"prompt": "   "}, project)
        self.assertEqual(result.stdout, "")

    def test_active_run_reinforces_session_pin(self):
        # Documented layout: root _latest.md pointer -> runs/{id}/_state.md.
        with kit.project() as project:
            kit.write_run(project, "2026-06-08_dark-mode_a3f9k2", phase_state="DESIGN_ACTIVE")
            result = prompt({"prompt": "add dark mode too"}, project)
        self.assertIn("a run is active", self._ctx(result))

    def test_delivered_run_is_not_active(self):
        with kit.project() as project:
            kit.write_run(project, "2026-06-08_dark-mode_a3f9k2", status="complete", phase_state="DELIVERED")
            result = prompt({"prompt": "what next"}, project)
        self.assertIn("no active run", self._ctx(result))

    def test_orphaned_run_without_latest_pointer_is_active(self):
        # _latest.md lost/never written, but an active pinned run remains under runs/.
        with kit.project() as project:
            kit.write_run(project, "2026-06-08_orphan_b7c2e1", pointer=False, phase_state="BUILD_ACTIVE")
            result = prompt({"prompt": "keep going"}, project)
        self.assertIn("a run is active", self._ctx(result))

    def test_stale_latest_pointer_falls_back_to_scan(self):
        # _latest.md points at a delivered run, but a different run is still active.
        with kit.project() as project:
            kit.write_run(project, "2026-06-07_done_aaaaaa", status="complete", phase_state="DELIVERED")
            kit.write_run(project, "2026-06-08_live_bbbbbb", pointer=False, phase_state="REVIEW_ACTIVE")
            result = prompt({"prompt": "next"}, project)
        self.assertIn("a run is active", self._ctx(result))

    def test_disputed_awaiting_user_is_active(self):
        """DISPUTED_AWAITING_USER is non-terminal: the run still owns the session. The run gets there as Admiral's
        escalation records it, a checkpoint that sets the phase and keeps the pin, through the real writer."""
        with kit.project() as project:
            (project / "README.md").write_text("# fixture\n", encoding="utf-8")
            run = "2026-06-08_dispute_c1d2e3"
            self.assertEqual(kit.save(project, run, "create", "--evidence", "README.md")[0], 0)
            code, out = kit.save(project, run, "checkpoint", "--set", "phase_state=DISPUTED_AWAITING_USER", "--next-action", "a call")
            self.assertEqual(code, 0, out)
            state = json.loads((project / "skillset-saves" / "runs" / run / "_state.md").read_text(encoding="utf-8"))
            self.assertEqual((state["phase_state"], state["protocol_state"], state["session_pin"]),
                             ("DISPUTED_AWAITING_USER", "ESCALATE", True))
            result = prompt({"prompt": "here is my call"}, project)
        self.assertIn("a run is active", self._ctx(result))

    def test_legacy_flat_state_is_not_treated_as_active(self):
        # Schema-invalid legacy state must not reinforce a session pin.
        with kit.project() as project:
            saves = project / "skillset-saves"
            saves.mkdir(parents=True, exist_ok=True)
            (saves / "_state.md").write_text("state: DESIGN_ACTIVE\nsession_pin: true\n", encoding="utf-8")
            result = prompt({"prompt": "add dark mode too"}, project)
        self.assertIn("no active run", self._ctx(result))

    def test_stale_lock_does_not_reinforce_session_pin(self):
        with kit.project() as project:
            kit.write_run(project, "stale")
            lock = project / "skillset-saves" / "runs" / "stale" / "_lock.md"
            lock.write_text(json.dumps({**json.loads(lock.read_text(encoding="utf-8")), "heartbeat": "2020-01-01T00:00:00Z"}), encoding="utf-8")
            result = prompt({"prompt": "continue"}, project)
        self.assertIn("no active run", self._ctx(result))

    def test_conflicting_held_runs_keep_the_session_pin_reminder_on(self):
        # Two fresh held runs are still held runs: the reminder used to go quiet for `conflicting`.
        with kit.project() as project:
            kit.write_run(project, "one")
            kit.write_run(project, "two", pointer=False)
            result = prompt({"prompt": "continue"}, project)
        self.assertIn("a run is active", self._ctx(result))

    def test_malformed_json_fails_open(self):
        with kit.project() as project:
            result = prompt("{", project)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class FaultTraceTests(unittest.TestCase):
    """CR-13: a fault the prompt hook swallows to fail open is counted, by type, in its observation record."""

    SECRET = "SECRET-PAYLOAD-MUST-NOT-BE-RECORDED"

    def setUp(self):
        self.root = self.enterContext(kit.project())
        self.enterContext(kit.in_project(self.root, HOME=str(self.root / "home")))

    def assertCounted(self, event: str, kind: str, count: int = 1) -> None:
        path = self.root / ".harness-state" / "observations" / f"{event}.json"
        record = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        self.assertEqual(record.get("faults"), count, record)
        self.assertEqual(record["last_fault"]["type"], kind)
        self.assertNotIn(self.SECRET, json.dumps(record))

    def test_a_fault_in_user_prompt_submit_exits_zero_and_is_counted(self):
        with mock.patch.object(_state, "record_observation", side_effect=RuntimeError(self.SECRET)):
            self.assertEqual(kit.decide({"prompt": "build"}, self.root, module="user_prompt_submit", entry="run"), "")
        self.assertCounted("UserPromptSubmit", "RuntimeError")

    def test_a_fault_in_the_audit_improve_trigger_is_counted_and_the_prompt_proceeds(self):
        import audit_improve

        with mock.patch.object(audit_improve, "maybe_audit", side_effect=OSError(self.SECRET)):
            output = kit.decide({"prompt": "/audit-improve now"}, self.root, module="user_prompt_submit")
        self.assertEqual(output, "")
        self.assertCounted("UserPromptSubmit", "OSError")

    def test_a_payload_that_does_not_parse_is_counted_for_the_event_that_read_it(self):
        proc = kit.run_hook("user_prompt_submit.py", b"{not json", self.root)
        self.assertEqual(proc.returncode, 0)
        record = json.loads((self.root / ".harness-state" / "observations" / "UserPromptSubmit.json").read_text(encoding="utf-8"))
        self.assertEqual(record["faults"], 1)
        self.assertEqual(record["last_fault"]["type"], "JSONDecodeError")


if __name__ == "__main__":
    unittest.main()
