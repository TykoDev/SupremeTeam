#!/usr/bin/env python3
"""Tests for guard_state.py, the sole sanctioned writer of the guard boundary.

These cover the properties that made the boundary self-liftable before the
writer existed: every recorded boundary carries an owner, a release is
authority-checked and preserves the record, and lifting destructive-pattern
blocking is bounded by an expiry rather than a permanent flag.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
GUARD = HOOKS / "guard_state.py"
PRE_TOOL = HOOKS / "pre_tool_use.py"


class GuardStateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        (self.project / ".harness-state").mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._tmp.cleanup)

    def _env(self):
        env = dict(os.environ)
        env["SUPREMETEAM_PROJECT_DIR"] = str(self.project)
        return env

    def run_guard(self, *args):
        return subprocess.run([sys.executable, str(GUARD), *args],
                              capture_output=True, text=True, env=self._env(), cwd=self.project)

    def record(self):
        path = self.project / ".harness-state" / "guard-state.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def pre_tool(self, payload):
        proc = subprocess.run([sys.executable, str(PRE_TOOL)], input=json.dumps(payload),
                              capture_output=True, text=True, env=self._env(), cwd=self.project)
        return proc.stdout

    # --- recording -------------------------------------------------------

    def test_freeze_records_an_owner_so_release_authority_is_checkable(self):
        proc = self.run_guard("freeze", "--glob", "src/payments/**", "--owner", "ops",
                              "--scope", "release freeze")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entry = self.record()["frozen_globs"][0]
        self.assertEqual(entry["glob"], "src/payments/**")
        self.assertEqual(entry["owner"], "ops")
        self.assertEqual(entry["scope"], "release freeze")
        self.assertIsNone(entry["released_at"])
        self.assertTrue(entry["created_at"])

    def test_freeze_refuses_to_double_record_an_active_boundary(self):
        self.run_guard("freeze", "--glob", "infra/**", "--owner", "ops")
        proc = self.run_guard("freeze", "--glob", "infra/**", "--owner", "someone-else")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("already inside an active boundary", proc.stderr)

    def test_owner_is_required(self):
        proc = self.run_guard("freeze", "--glob", "infra/**")
        self.assertEqual(proc.returncode, 2)

    # --- release ---------------------------------------------------------

    def test_release_sets_released_at_and_never_deletes_the_record(self):
        self.run_guard("freeze", "--glob", "infra/**", "--owner", "ops")
        proc = self.run_guard("release", "--glob", "infra/**", "--requester", "ops",
                              "--reason", "launch complete")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        entries = self.record()["frozen_globs"]
        self.assertEqual(len(entries), 1, "the record must survive a release")
        self.assertTrue(entries[0]["released_at"])
        self.assertEqual(entries[0]["released_by"], "ops")
        self.assertEqual(entries[0]["release_reason"], "launch complete")

    def test_release_refuses_a_requester_who_is_neither_owner_nor_approver(self):
        self.run_guard("freeze", "--glob", "infra/**", "--owner", "ops")
        proc = self.run_guard("release", "--glob", "infra/**", "--requester", "someone-else")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("neither the owner", proc.stderr)
        self.assertIsNone(self.record()["frozen_globs"][0]["released_at"])

    def test_release_accepts_a_delegated_approver(self):
        self.run_guard("freeze", "--glob", "infra/**", "--owner", "ops", "--approver", "sre")
        proc = self.run_guard("release", "--glob", "infra/**", "--requester", "sre")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.record()["frozen_globs"][0]["released_at"])

    def test_release_refuses_an_ownerless_legacy_entry_rather_than_trusting_the_requester(self):
        path = self.project / ".harness-state" / "guard-state.json"
        path.write_text(json.dumps({"frozen_globs": ["infra/**"]}), encoding="utf-8")
        proc = self.run_guard("release", "--glob", "infra/**", "--requester", "anyone")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no owner", proc.stderr)

    # --- allow_dangerous -------------------------------------------------

    def test_allow_dangerous_is_an_owned_grant_with_an_expiry(self):
        proc = self.run_guard("allow-dangerous", "--owner", "ops", "--reason", "disk wipe of scratch",
                              "--scope", "rm -rf ./scratch", "--minutes", "5")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        grant = self.record()["allow_dangerous"]
        self.assertEqual(grant["owner"], "ops")
        self.assertTrue(grant["expires_at"])
        self.assertTrue(grant["reason"])

    def test_expired_grant_leaves_destructive_blocking_in_force(self):
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.project / ".harness-state" / "guard-state.json").write_text(
            json.dumps({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y",
                                            "expires_at": past}}), encoding="utf-8")
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "rm -rf --no-preserve-root /"}})
        self.assertIn("deny", out, "an expired grant must not leave the guard open")

    def test_live_grant_lifts_destructive_blocking(self):
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.project / ".harness-state" / "guard-state.json").write_text(
            json.dumps({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y",
                                            "expires_at": future}}), encoding="utf-8")
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "rm -rf --no-preserve-root /"}})
        self.assertEqual(out, "")

    def test_grant_without_an_expiry_does_not_lift_the_block(self):
        """An unbounded lift is the state this rule exists to prevent.

        guard_state.py always records an expiry, so a grant missing one is
        malformed — and a malformed grant must fail closed rather than hand out
        a permanent global kill-switch.
        """
        (self.project / ".harness-state" / "guard-state.json").write_text(
            json.dumps({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y"}}),
            encoding="utf-8")
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "rm -rf --no-preserve-root /"}})
        self.assertIn("deny", out)

    def test_deny_text_points_at_the_sanctioned_writer(self):
        """The old text told the owner to edit the file the hook now denies."""
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "rm -rf --no-preserve-root /"}})
        self.assertIn("guard_state.py allow-dangerous", out)

    def test_revoke_dangerous_requires_the_granting_owner(self):
        self.run_guard("allow-dangerous", "--owner", "ops", "--reason", "x", "--scope", "y")
        denied = self.run_guard("revoke-dangerous", "--requester", "someone-else")
        self.assertEqual(denied.returncode, 1)
        allowed = self.run_guard("revoke-dangerous", "--requester", "ops")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertFalse(self.record()["allow_dangerous"])

    # --- read-only -------------------------------------------------------

    def test_read_only_round_trip_is_owned_and_released_not_deleted(self):
        self.run_guard("read-only", "--run-id", "r1", "--owner", "ops",
                       "--allow", "skillset-saves/runs/r1/**")
        entry = self.record()["read_only"][0]
        self.assertEqual(entry["owner"], "ops")
        self.assertIsNone(entry["released_at"])
        refused = self.run_guard("release-read-only", "--run-id", "r1", "--requester", "other")
        self.assertEqual(refused.returncode, 1)
        ok = self.run_guard("release-read-only", "--run-id", "r1", "--requester", "ops")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(len(self.record()["read_only"]), 1)
        self.assertTrue(self.record()["read_only"][0]["released_at"])

    # --- corruption ------------------------------------------------------

    def test_corrupt_record_is_reported_never_overwritten(self):
        path = self.project / ".harness-state" / "guard-state.json"
        path.write_text("{not json", encoding="utf-8")
        proc = self.run_guard("freeze", "--glob", "infra/**", "--owner", "ops")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not valid JSON", proc.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), "{not json")

    # --- hook protection -------------------------------------------------

    def test_edit_tool_cannot_write_the_boundary_record(self):
        out = self.pre_tool({"tool_name": "Write",
                             "tool_input": {"file_path": ".harness-state/guard-state.json"}})
        self.assertIn("guard_state.py", out)

    def test_mutating_shell_cannot_write_the_boundary_record(self):
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "echo '{}' > .harness-state/guard-state.json"}})
        self.assertIn("guard_state.py", out)

    def test_the_sanctioned_writer_itself_passes(self):
        out = self.pre_tool({"tool_name": "Bash", "tool_input": {
            "command": "python skills/harness/hooks/guard_state.py release "
                       "--glob infra/** --requester ops"}})
        self.assertEqual(out, "")

    def test_reading_the_boundary_record_is_never_blocked(self):
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "cat .harness-state/guard-state.json"}})
        self.assertEqual(out, "")


if __name__ == "__main__":
    unittest.main()
