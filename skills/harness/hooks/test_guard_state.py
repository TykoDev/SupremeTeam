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
GUARD_HOOK = HOOKS / "guard_hook.py"


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

    def pre_tool(self, payload, script=PRE_TOOL):
        proc = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                              capture_output=True, text=True, env=self._env(), cwd=self.project)
        self.assertEqual(proc.returncode, 0, proc.stderr)
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
        self.assertTrue(grant["created_at"])
        self.assertTrue(grant["expires_at"])
        self.assertTrue(grant["reason"])

    def test_expired_grant_leaves_destructive_blocking_in_force(self):
        past = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.project / ".harness-state" / "guard-state.json").write_text(
            json.dumps({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y",
                                            "created_at": "2026-01-01T00:00:00Z",
                                            "expires_at": past}}), encoding="utf-8")
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "rm -rf --no-preserve-root /"}})
        self.assertIn("deny", out, "an expired grant must not leave the guard open")

    def test_live_grant_lifts_destructive_blocking(self):
        future = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        (self.project / ".harness-state" / "guard-state.json").write_text(
            json.dumps({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y",
                                            "created_at": "2026-01-01T00:00:00Z",
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
            json.dumps({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y",
                                            "created_at": "2026-01-01T00:00:00Z"}}),
            encoding="utf-8")
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "rm -rf --no-preserve-root /"}})
        self.assertIn("deny", out)

    def test_grant_requires_nonempty_owner_reason_scope_and_created_at(self):
        grant = {
            "owner": "ops",
            "reason": "scratch cleanup",
            "scope": "rm -rf ./scratch",
            "created_at": "2026-01-01T00:00:00Z",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        path = self.project / ".harness-state" / "guard-state.json"
        payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf --no-preserve-root /"}}
        for field in ("owner", "reason", "scope", "created_at"):
            with self.subTest(missing=field):
                malformed = dict(grant)
                malformed[field] = ""
                path.write_text(json.dumps({"allow_dangerous": malformed}), encoding="utf-8")
                self.assertIn("deny", self.pre_tool(payload))

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

    def test_guard_hook_is_a_direct_executable_entrypoint(self):
        recorded = self.run_guard("freeze", "--glob", "src/payments/**", "--owner", "ops")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        out = self.pre_tool({"tool_name": "Edit",
                             "tool_input": {"file_path": "src/payments/charge.py"}}, GUARD_HOOK)
        self.assertIn('"permissionDecision": "deny"', out)

    def test_apply_patch_cannot_cross_frozen_or_single_writer_boundaries(self):
        recorded = self.run_guard("freeze", "--glob", "src/payments/**", "--owner", "ops")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        for target in (
            "src/payments/charge.py",
            ".harness-state/guard-state.json",
            "skillset-saves/runs/r1/_state.md",
        ):
            with self.subTest(target=target):
                patch_text = f"*** Begin Patch\n*** Update File: {target}\n@@\n-old\n+new\n*** End Patch"
                out = self.pre_tool({"tool_name": "apply_patch", "tool_input": {"patch": patch_text}})
                self.assertIn('"permissionDecision": "deny"', out)

    def test_write_content_quoting_a_patch_header_does_not_target_that_path(self):
        self.run_guard("freeze", "--glob", "src/payments/**", "--owner", "ops")
        out = self.pre_tool({"tool_name": "Write", "tool_input": {
            "file_path": "docs/example.md",
            "content": "*** Update File: src/payments/charge.py\n",
        }})
        self.assertEqual(out, "")

    def test_mentioning_writer_in_shell_comment_does_not_bypass_guard(self):
        for target, writer in (
            (".harness-state/guard-state.json", "guard_state.py"),
            ("skillset-saves/runs/r1/_state.md", "save_run.py"),
        ):
            with self.subTest(target=target):
                command = f"echo changed > {target} # {writer}"
                out = self.pre_tool({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertIn('"permissionDecision": "deny"', out)

    def test_edit_and_shell_tools_cannot_write_the_boundary_record(self):
        payloads = (
            {"tool_name": "Write", "tool_input": {"file_path": ".harness-state/guard-state.json"}},
            {"tool_name": "Bash", "tool_input": {"command": "echo '{}' > .harness-state/guard-state.json"}},
        )
        for payload in payloads:
            with self.subTest(tool=payload["tool_name"]):
                self.assertIn("guard_state.py", self.pre_tool(payload))

    def test_the_sanctioned_writer_itself_passes(self):
        out = self.pre_tool({"tool_name": "Bash", "tool_input": {
            "command": "python skills/harness/hooks/guard_state.py release "
                       "--glob infra/** --requester ops"}})
        self.assertEqual(out, "")

    def test_reading_the_boundary_record_is_never_blocked(self):
        out = self.pre_tool({"tool_name": "Bash",
                             "tool_input": {"command": "cat .harness-state/guard-state.json"}})
        self.assertEqual(out, "")


class GuardStateHardeningTests(unittest.TestCase):
    """SEC-04, SEC-14, BUGH-24, QR-PY-05: globs are normalised or refused when recorded, grants are capped, writes are serialised."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name).resolve()
        (self.project / ".harness-state").mkdir(parents=True, exist_ok=True)
        self.addCleanup(self._tmp.cleanup)

    def _env(self):
        env = dict(os.environ)
        env["SUPREMETEAM_PROJECT_DIR"] = str(self.project)
        return env

    def run_guard(self, *args):
        return subprocess.run([sys.executable, str(GUARD), *args], capture_output=True, text=True, env=self._env(), cwd=self.project)

    def record(self):
        path = self.project / ".harness-state" / "guard-state.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def write_record(self, state):
        (self.project / ".harness-state" / "guard-state.json").write_text(json.dumps(state), encoding="utf-8")

    def pre_tool(self, payload):
        proc = subprocess.run([sys.executable, str(PRE_TOOL)], input=json.dumps(payload), capture_output=True, text=True,
                              env=self._env(), cwd=self.project)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    # --- globs ---------------------------------------------------------

    def test_every_spelling_of_one_glob_is_recorded_as_one_and_enforced(self):
        for spelling in ("./src/payments/**", "src//payments/**", "src\\payments\\**", "src/x/../payments/**",
                         str(self.project / "src" / "payments") + "/**", "src/payments/"):
            with self.subTest(spelling=spelling):
                self.write_record({})
                proc = self.run_guard("freeze", "--glob", spelling, "--owner", "ops")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                normal = "src/payments" if spelling.endswith("/") else "src/payments/**"
                self.assertEqual(json.loads(proc.stdout)["glob"], normal)
                self.assertEqual(self.record()["frozen_globs"][0]["glob"], normal)
                self.assertIn("deny", self.pre_tool({"tool_name": "Edit", "tool_input": {"file_path": "src/payments/a.py"}}))
                self.assertEqual(self.pre_tool({"tool_name": "Edit", "tool_input": {"file_path": "src/other/a.py"}}), "")

    def test_a_second_spelling_of_a_recorded_glob_is_a_duplicate_not_a_second_record(self):
        self.run_guard("freeze", "--glob", "src/payments/**", "--owner", "ops")
        for spelling in ("./src/payments/**", "src//payments/**", "src\\payments\\**"):
            with self.subTest(spelling=spelling):
                proc = self.run_guard("freeze", "--glob", spelling, "--owner", "someone-else")
                self.assertEqual(proc.returncode, 1)
                self.assertIn("already inside an active boundary", proc.stderr)
        self.assertEqual(len(self.record()["frozen_globs"]), 1)

    def test_a_glob_that_can_never_match_is_refused_when_recorded(self):
        for spelling in ("../x/**", "..", ".", "./", "   ", "src/../../x/**"):
            with self.subTest(spelling=spelling):
                proc = self.run_guard("freeze", "--glob", spelling, "--owner", "ops")
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("cannot be matched", proc.stderr)
        self.assertFalse((self.project / ".harness-state" / "guard-state.json").exists())

    MISSING = "supremeteam-no-such-top-level-directory"

    def test_a_leading_slash_glob_that_names_no_directory_here_is_refused_with_the_relative_spelling(self):
        """SEC-04: `/src/payments/**` was recorded as an active freeze, `status` listed it, and it enforced nothing."""
        for spelling in (f"/{self.MISSING}/payments/**", f"\\{self.MISSING}\\payments\\**", f"//{self.MISSING}/payments/**", f"/{self.MISSING}"):
            for command in ("freeze", "block"):
                with self.subTest(spelling=spelling, command=command):
                    proc = self.run_guard(command, "--glob", spelling, "--owner", "ops")
                    self.assertEqual(proc.returncode, 1, proc.stdout)
                    self.assertIn("cannot be matched", proc.stderr)
                    self.assertIn(f"no directory /{self.MISSING} exists", proc.stderr)
                    self.assertIn(f"relative to the project root it is {self.MISSING}", proc.stderr)
        self.assertFalse((self.project / ".harness-state" / "guard-state.json").exists())

    def test_the_other_spellings_that_match_nothing_are_refused_at_record_time(self):
        for spelling in ("!src/payments/**", "/", "C:/"):
            with self.subTest(spelling=spelling):
                proc = self.run_guard("freeze", "--glob", spelling, "--owner", "ops")
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertIn("cannot be matched", proc.stderr)
        proc = self.run_guard("read-only", "--run-id", "r1", "--owner", "ops", "--allow", f"/{self.MISSING}/**")
        self.assertEqual(proc.returncode, 1)

    def test_a_real_absolute_glob_and_a_foreign_host_path_are_still_recorded(self):
        outside = Path(tempfile.gettempdir()).resolve().parent.as_posix().rstrip("/") + "/**"
        for spelling in (outside, "C:/other/proj/src/**", "src/payments/**"):
            with self.subTest(spelling=spelling):
                self.write_record({})
                proc = self.run_guard("freeze", "--glob", spelling, "--owner", "ops")
                self.assertEqual(proc.returncode, 0, proc.stderr)

    @unittest.skipIf(os.name == "nt", "a leading-slash path is a POSIX notion here")
    def test_a_leading_slash_glob_outside_the_project_is_recorded_with_a_warning_whatever_the_machine_has(self):
        """RR3-guard-2: `/lib/payments/**` was recorded in silence where `/lib` exists and refused where it does not. `/tmp` and
        `/etc` exist on every Linux, `/zz-nonexistent-dir` on none, so this does not depend on the machine."""
        for spelling, relative in (("/tmp/payments/**", "tmp/payments/**"), ("/etc/**", "etc/**"), ("\\tmp\\payments\\**", "tmp/payments/**")):
            for command in ("freeze", "block"):
                with self.subTest(spelling=spelling, command=command):
                    self.write_record({})
                    proc = self.run_guard(command, "--glob", spelling, "--owner", "ops")
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertTrue(proc.stderr.startswith("warning:"), proc.stderr)
                    self.assertIn(f"not the project's {relative}", proc.stderr)
                    self.assertIn("absolute path outside the project", proc.stderr)
                    recorded = self.record()["frozen_globs" if command == "freeze" else "blocked_globs"][0]["glob"]
                    self.assertEqual(recorded, "/" + relative)
        refused = self.run_guard("freeze", "--glob", "/zz-nonexistent-dir/payments/**", "--owner", "ops")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("relative to the project root it is zz-nonexistent-dir/payments/**", refused.stderr)
        self.assertNotIn("warning:", refused.stderr)

    @unittest.skipIf(os.name == "nt", "a leading-slash path is a POSIX notion here")
    def test_status_carries_the_warning_for_the_record_and_names_the_project_spelling(self):
        self.run_guard("freeze", "--glob", "/tmp/payments/**", "--owner", "ops")
        self.run_guard("block", "--glob", "/etc/**", "--owner", "ops")
        self.run_guard("freeze", "--glob", "src/ok/**", "--owner", "ops")
        report = json.loads(self.run_guard("status", "--json").stdout)
        self.assertEqual(report["absolute_entries"], ["/tmp/payments/**", "/etc/**"])
        self.assertIn("not the project's tmp/payments/**", report["absolute_reasons"]["/tmp/payments/**"])
        self.assertEqual(report["unmatchable_entries"], [])
        text = self.run_guard("status").stdout
        self.assertIn("WARNING absolute path outside the project", text)
        self.assertIn("record etc/**", text)
        self.assertNotIn("src/ok", text.split("WARNING")[1])

    @unittest.skipIf(os.name == "nt", "a leading-slash path is a POSIX notion here")
    def test_a_read_only_allow_glob_outside_the_project_is_warned_about_too(self):
        proc = self.run_guard("read-only", "--run-id", "r1", "--owner", "ops", "--allow", "/tmp/out/**", "--allow", "skillset-saves/runs/r1/**")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr.count("warning:"), 1)
        self.assertIn("not the project's tmp/out/**", proc.stderr)

    def test_a_glob_under_the_project_root_or_with_its_own_start_is_recorded_without_a_warning(self):
        for spelling in (str(self.project / "src" / "payments") + "/**", "src/payments/**", "C:/other/proj/src/**", "~/x/**"):
            with self.subTest(spelling=spelling):
                self.write_record({})
                proc = self.run_guard("freeze", "--glob", spelling, "--owner", "ops")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn("warning:", proc.stderr)

    def test_status_says_why_an_unmatchable_record_already_on_disk_enforces_nothing(self):
        self.write_record({"frozen_globs": [{"glob": f"/{self.MISSING}/payments/**", "owner": "ops"}, {"glob": "!x/**", "owner": "ops"},
                                            {"glob": "src/ok/**", "owner": "ops"}]})
        report = json.loads(self.run_guard("status", "--json").stdout)
        self.assertEqual(report["unmatchable_entries"], [f"/{self.MISSING}/payments/**", "!x/**"])
        self.assertIn(f"no directory /{self.MISSING} exists", report["unmatchable_reasons"][f"/{self.MISSING}/payments/**"])
        text = self.run_guard("status").stdout
        self.assertIn("WARNING unmatchable", text)
        self.assertIn(f"relative to the project root it is {self.MISSING}/payments/**", text)

    def test_release_finds_the_record_by_any_spelling_including_one_written_before_normalising(self):
        self.write_record({"frozen_globs": [{"glob": "./src/legacy/**", "owner": "ops", "released_at": None}]})
        proc = self.run_guard("release", "--glob", "src/legacy/**", "--requester", "ops")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.record()["frozen_globs"][0]["released_at"])
        self.run_guard("freeze", "--glob", "src/a/**", "--owner", "ops")
        self.assertEqual(self.run_guard("release", "--glob", "./src//a/**", "--requester", "ops").returncode, 0)

    def test_status_shows_the_effective_spelling_and_flags_an_unmatchable_legacy_record(self):
        self.write_record({"frozen_globs": [{"glob": "./src/x/**", "owner": "ops"}, {"glob": "../up/**", "owner": "ops"}]})
        report = json.loads(self.run_guard("status", "--json").stdout)
        self.assertEqual(report["frozen_globs"], ["src/x/**", "../up/**"])
        self.assertEqual(report["unmatchable_entries"], ["../up/**"])

    def test_read_only_allow_globs_are_normalised_and_unusable_ones_refused(self):
        proc = self.run_guard("read-only", "--run-id", "r1", "--owner", "ops", "--allow", "./skillset-saves/runs/r1/**", "--allow", ".harness-state//**")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.record()["read_only"][0]["allow"], ["skillset-saves/runs/r1/**", ".harness-state/**"])
        refused = self.run_guard("read-only", "--run-id", "r2", "--owner", "ops", "--allow", "../outside/**")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("cannot be matched", refused.stderr)

    # --- grants --------------------------------------------------------

    def test_a_grant_longer_than_the_cap_is_refused_and_one_at_the_cap_is_recorded(self):
        too_long = self.run_guard("allow-dangerous", "--owner", "ops", "--reason", "r", "--scope", "s", "--minutes", "5000000")
        self.assertEqual(too_long.returncode, 1)
        self.assertIn("480", too_long.stderr)
        self.assertNotIn("allow_dangerous", self.record())
        just_over = self.run_guard("allow-dangerous", "--owner", "ops", "--reason", "r", "--scope", "s", "--minutes", "481")
        self.assertEqual(just_over.returncode, 1)
        at_cap = self.run_guard("allow-dangerous", "--owner", "ops", "--reason", "r", "--scope", "s", "--minutes", "480")
        self.assertEqual(at_cap.returncode, 0, at_cap.stderr)

    def test_a_hand_written_grant_beyond_the_cap_leaves_the_block_in_force(self):
        far = (datetime.now(timezone.utc) + timedelta(days=3650)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write_record({"allow_dangerous": {"owner": "ops", "reason": "x", "scope": "y",
                                               "created_at": "2026-01-01T00:00:00Z", "expires_at": far}})
        self.assertIn("deny", self.pre_tool({"tool_name": "Bash", "tool_input": {"command": "rm -rf --no-preserve-root /"}}))

    # --- shared predicate and write ------------------------------------

    def test_released_true_retires_a_record_in_the_writer_as_in_the_hook(self):
        self.write_record({"read_only": [{"run_id": "r1", "owner": "ops", "allow": ["a/**"], "released": True}],
                           "frozen_globs": [{"glob": "b/**", "owner": "ops", "released": True}]})
        report = json.loads(self.run_guard("status", "--json").stdout)
        self.assertEqual((report["read_only_runs"], report["frozen_globs"]), ([], []))
        self.assertEqual(self.run_guard("read-only", "--run-id", "r1", "--owner", "ops", "--allow", "a/**").returncode, 0)

    def test_the_record_is_replaced_atomically_with_nothing_left_behind(self):
        self.run_guard("freeze", "--glob", "a/**", "--owner", "ops")
        self.run_guard("freeze", "--glob", "b/**", "--owner", "ops")
        names = sorted(path.name for path in (self.project / ".harness-state").iterdir())
        self.assertEqual([n for n in names if n.endswith(".tmp")], [])
        self.assertTrue(self.record()["frozen_globs"][1]["created_at"])

    def test_an_unwritable_state_directory_is_a_refusal_not_a_traceback(self):
        state = self.project / ".harness-state"
        record = state / "guard-state.json"
        record.mkdir()
        proc = self.run_guard("freeze", "--glob", "a/**", "--owner", "ops")
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr)

    # --- serialised writers --------------------------------------------

    def test_a_writer_waits_for_the_lock_and_refuses_when_another_holds_it_too_long(self):
        sys.path.insert(0, str(HOOKS))
        import _fsutil

        lock = self.project / ".harness-state" / "guard-state.json.lock"
        with _fsutil.AdvisoryLock(lock, 5.0):
            proc = self.run_guard("--lock-timeout", "0.2", "freeze", "--glob", "a/**", "--owner", "ops")
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn("another guard_state.py", proc.stderr)
            self.assertFalse((self.project / ".harness-state" / "guard-state.json").exists())
        self.assertEqual(self.run_guard("--lock-timeout", "0.2", "freeze", "--glob", "a/**", "--owner", "ops").returncode, 0)

    def test_concurrent_writers_do_not_lose_each_others_records(self):
        env = self._env()
        procs = [subprocess.Popen([sys.executable, str(GUARD), "freeze", "--glob", f"zone{n}/**", "--owner", "ops"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=self.project) for n in range(8)]
        for proc in procs:
            self.assertEqual(proc.wait(timeout=60), 0)
        self.assertEqual(sorted(entry["glob"] for entry in self.record()["frozen_globs"]), [f"zone{n}/**" for n in range(8)])


if __name__ == "__main__":
    unittest.main()
