#!/usr/bin/env python3
"""Verify, repair and readiness: host selection, matcher coverage, interpreter,
project root, read-only diagnostics, and hook-script integrity.

Every test runs the scripts as subprocesses in a scratch project and a scratch
home with the host environment signals removed, so none of them depends on the
shell the suite happens to run in.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import repair_registration as repair  # noqa: E402
import verify_registration as verify  # noqa: E402

_SIGNAL_PREFIXES = ("CLAUDE", "CODEX_", "COPILOT", "GITHUB_COPILOT")
_PROJECT_VARS = ("SUPREMETEAM_PROJECT_DIR", "CLAUDE_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE", "SUPREMETEAM_HOOK_ROOT")
POSIX = os.name == "posix"


def plain_env(home: Path, **extra: str) -> dict:
    """An ordinary terminal: no host signal, no project variable, a scratch home."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(_SIGNAL_PREFIXES) and k not in _PROJECT_VARS}
    env["HOME"] = env["USERPROFILE"] = str(home)
    env.update(extra)
    return env


class Scratch(unittest.TestCase):
    """A scratch home and a scratch project (a ``.git`` marker makes it a root)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)

    def run_tool(self, script: str, *args: str, cwd: Path | None = None, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(HOOK_DIR / script), *args], text=True, capture_output=True,
                              cwd=str(cwd or self.project), env=plain_env(self.home, **extra), check=False)

    def write_json(self, path: Path, data) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def registered(self, host: str = "claude", python: str | None = None) -> dict:
        return repair.plan({}, host, python or sys.executable)[0]

    def claude_settings(self, data) -> Path:
        return self.write_json(self.project / ".claude" / "settings.json", data)


class AutoHostTests(Scratch):
    """DX-03: --host auto from a plain terminal."""

    def test_one_registered_host_verifies_from_a_plain_terminal(self):
        self.claude_settings(self.registered())
        result = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("auto -> claude (config found)", result.stdout)
        self.assertNotIn("[codex]", result.stdout)
        self.assertNotIn("[copilot]", result.stdout)
        self.assertNotIn("UNKNOWN", result.stdout)

    def test_readiness_is_ready_for_that_one_host(self):
        self.claude_settings(self.registered())
        result = self.run_tool("check_readiness.py", "--host", "auto", "--json")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(data["hooks"]["status"], "registered")
        self.assertEqual(data["hooks"]["selected_hosts"], ["claude"])
        self.assertTrue(data["capabilities"]["hooks_configured"])
        self.assertTrue(data["ready"])

    def test_no_host_anywhere_is_missing_not_unknown(self):
        result = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("auto -> none", result.stdout)
        self.assertIn("status: MISSING", result.stdout)
        self.assertIn("REGISTER_PROMPT", result.stdout)
        self.assertNotIn("UNKNOWN", result.stdout)

    def test_a_host_signalled_by_the_environment_without_config_is_missing(self):
        result = self.run_tool("verify_registration.py", "--host", "auto", CODEX_SESSION_ID="s")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("auto -> codex (environment signal)", result.stdout)
        self.assertIn("[MISSING] PreToolUse", result.stdout)
        self.assertIn("--host codex", result.stdout, "the repair preview names the host that needs it")

    def test_a_config_without_the_hooks_is_missing_for_that_host_only(self):
        self.claude_settings({"theme": "dark"})
        result = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("auto -> claude (config found)", result.stdout)
        self.assertNotIn("[codex]", result.stdout)

    def test_every_selected_host_is_reported_and_counted(self):
        self.claude_settings(self.registered())
        self.write_json(self.project / ".codex" / "hooks.json", {"hooks": {}})
        result = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[claude]", result.stdout)
        self.assertIn("[codex]", result.stdout)
        self.assertIn("status: REGISTERED", result.stdout)
        self.assertIn("status: MISSING", result.stdout)

    def test_an_unreadable_config_is_unknown_even_under_auto(self):
        path = self.project / ".claude" / "settings.json"
        path.parent.mkdir()
        path.write_bytes(b"\xff\xfe{")
        result = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("status: UNKNOWN", result.stdout)

    def test_all_still_checks_the_three_hosts(self):
        self.claude_settings(self.registered())
        result = self.run_tool("verify_registration.py", "--host", "all")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        for host in ("codex", "claude", "copilot"):
            self.assertIn(f"[{host}]", result.stdout)


class ReadinessSemanticsTests(Scratch):
    """DX-11: hooks are optional; BUGH-19 and BUGH-27: the root and read-only."""

    def readiness(self, *args: str, cwd: Path | None = None, **extra: str) -> tuple[subprocess.CompletedProcess, dict]:
        result = self.run_tool("check_readiness.py", *args, "--json", cwd=cwd, **extra)
        return result, json.loads(result.stdout)

    def test_missing_hooks_do_not_make_the_project_not_ready(self):
        self.claude_settings({"theme": "dark"})
        result, data = self.readiness("--host", "auto")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(data["hooks"]["status"], "missing")
        self.assertTrue(data["ready"])
        self.assertEqual(data["blockers"], [])
        self.assertIn("repair_registration.py", data["repair_hint"])

    def test_text_output_says_hooks_are_optional_and_reports_ready(self):
        self.claude_settings({"theme": "dark"})
        result = self.run_tool("check_readiness.py", "--host", "auto")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Hooks: missing", result.stdout)
        self.assertIn("optional", result.stdout)
        self.assertIn("Ready: yes", result.stdout)

    def test_require_hooks_makes_missing_hooks_a_blocker(self):
        self.claude_settings({"theme": "dark"})
        result, data = self.readiness("--host", "auto", "--require-hooks")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertFalse(data["ready"])
        self.assertTrue(any("--require-hooks" in blocker for blocker in data["blockers"]), data["blockers"])

    def test_an_undeterminable_hook_state_is_not_a_pass(self):
        path = self.project / ".claude" / "settings.json"
        path.parent.mkdir()
        path.write_bytes(b"\xff\xfe{")
        result, data = self.readiness("--host", "auto")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(data["hooks"]["status"], "unknown")
        self.assertTrue(any("could not be determined" in blocker for blocker in data["blockers"]), data["blockers"])

    def test_hooks_coverage_counts_the_tool_hooks_not_the_prompt_hook(self):
        """With both tool hooks registered for a tool they never see, only the prompt hook counted and coverage read `full`."""
        unrelated = {"matcher": "Read", "hooks": [{"type": "command", "command": repair.command_for("pre_tool_use.py", sys.executable)}]}
        post = {"matcher": "Read", "hooks": [{"type": "command", "command": repair.command_for("post_tool_use.py", sys.executable)}]}
        prompt = {"hooks": [{"type": "command", "command": repair.command_for("user_prompt_submit.py", sys.executable)}]}
        self.claude_settings({"hooks": {"PreToolUse": [unrelated], "PostToolUse": [post], "UserPromptSubmit": [prompt]}})
        _, data = self.readiness("--host", "auto")
        self.assertFalse(data["capabilities"]["hooks_executable"])
        self.assertEqual(data["capabilities"]["hooks_coverage"], "unverified")
        full = self.registered()
        self.claude_settings(full)
        self.assertEqual(self.readiness("--host", "auto")[1]["capabilities"]["hooks_coverage"], "full")
        del full["hooks"]["PostToolUse"]
        self.claude_settings(full)
        self.assertEqual(self.readiness("--host", "auto")[1]["capabilities"]["hooks_coverage"], "partial",
                         "a tool hook that is not registered at all leaves the surface partly uncovered")
        narrow = self.registered()
        narrow["hooks"]["PreToolUse"][0]["matcher"] = "Bash"
        self.claude_settings(narrow)
        self.assertEqual(self.readiness("--host", "auto")[1]["capabilities"]["hooks_coverage"], "partial")

    def test_the_active_run_requirement_still_applies(self):
        self.claude_settings(self.registered())
        result, data = self.readiness("--host", "auto", "--require-active-run")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertTrue(any("--require-active-run" in blocker for blocker in data["blockers"]), data["blockers"])

    def test_readiness_says_what_to_do_about_the_saves_it_found(self):
        # DX-19: only the hooks had a remediation line; `status` had a next step and readiness did not.
        self.claude_settings(self.registered())
        result, data = self.readiness("--host", "auto")
        self.assertEqual(data["saves"]["status"], "missing")
        self.assertIn("save_run.py create", data["saves"]["next_step"])
        text = self.run_tool("check_readiness.py", "--host", "auto").stdout
        self.assertIn("Saves: missing", text)
        self.assertIn("  next: no run exists yet", text)
        (self.project / "skillset-saves" / "runs" / "r1" / "intake").mkdir(parents=True)
        result, data = self.readiness("--host", "auto")
        self.assertEqual(data["saves"]["status"], "uninitialized")
        self.assertIn("run save_run.py create", data["saves"]["next_step"])

    def test_an_active_run_needs_no_instruction(self):
        self.claude_settings(self.registered())
        (self.project / "README.md").write_text("x\n", encoding="utf-8")
        created = subprocess.run([sys.executable, str(HOOK_DIR / "save_run.py"), "create", "--project-root", str(self.project),
                                  "--run-id", "r1", "--evidence", "README.md"], capture_output=True, text=True, check=False,
                                 env=plain_env(self.home))
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        _, data = self.readiness("--host", "auto")
        self.assertEqual((data["saves"]["status"], data["saves"]["next_step"]), ("active", ""))
        self.assertNotIn("  next:", self.run_tool("check_readiness.py", "--host", "auto").stdout)

    def test_project_root_reaches_the_hook_inspection(self):
        # BUGH-19: the hooks live in the other project; the working directory is a bare one.
        other = self.tmp / "other"
        (other / ".git").mkdir(parents=True)
        self.write_json(other / ".claude" / "settings.json", self.registered())
        bare = self.tmp / "bare"
        (bare / ".git").mkdir(parents=True)
        result, data = self.readiness("--host", "claude", "--project-root", str(other), cwd=bare)
        self.assertEqual(data["hooks"]["status"], "registered", data["hooks"]["detail"])
        self.assertTrue(data["capabilities"]["hooks_configured"])
        self.assertEqual(data["saves"]["project_root"], str(other))

    def tree(self) -> list[str]:
        return sorted(str(path.relative_to(self.tmp)) for path in self.tmp.rglob("*"))

    def test_readiness_creates_no_state_directory(self):
        # BUGH-27: a diagnostic reads; it does not leave a .harness-state behind.
        self.claude_settings(self.registered())
        before = self.tree()
        for args in (("--host", "auto"), ("--host", "auto", "--json"), ("--host", "claude", "--project-root", str(self.project))):
            with self.subTest(args=args):
                self.run_tool("check_readiness.py", *args)
                self.assertFalse((self.project / ".harness-state").exists())
                self.assertEqual(self.tree(), before, "readiness wrote something")

    def test_the_verifier_creates_nothing_either(self):
        self.claude_settings(self.registered())
        before = self.tree()
        self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(self.tree(), before)

    def test_observations_are_still_read_when_they_exist(self):
        self.claude_settings(self.registered())
        record = self.project / ".harness-state" / "observations" / "PreToolUse.json"
        self.write_json(record, {"observed": {"at": "2026-01-01T00:00:00Z", "count": 2}})
        _, data = self.readiness("--host", "auto")
        self.assertEqual(data["hooks"]["observations"]["PreToolUse"]["state"], "observed")
        self.assertEqual(data["capabilities"]["hooks_observed"], "partial")

    def test_a_firing_hook_with_faults_is_reported_and_absence_is_tolerated(self):
        self.claude_settings(self.registered())
        observations = self.project / ".harness-state" / "observations"
        self.write_json(observations / "PreToolUse.json", {
            "observed": {"at": "2026-01-01T00:00:00Z", "count": 9}, "faults": 3,
            "last_fault": {"type": "ValueError", "at": "2026-01-02T03:04:05Z"}})
        self.write_json(observations / "PostToolUse.json", {"observed": {"at": "2026-01-01T00:00:00Z", "count": 1}})
        self.write_json(observations / "UserPromptSubmit.json", {"observed": {"count": 1}, "faults": "garbage", "last_fault": "oops"})
        result, data = self.readiness("--host", "auto")
        events = data["hooks"]["observations"]
        self.assertEqual(events["PreToolUse"]["faults"], 3)
        self.assertEqual(events["PreToolUse"]["last_fault"], {"type": "ValueError", "at": "2026-01-02T03:04:05Z"})
        self.assertNotIn("faults", events["PostToolUse"])
        self.assertNotIn("faults", events["UserPromptSubmit"], "a malformed counter is ignored, not trusted")
        self.assertEqual(data["capabilities"]["hooks_faults"], 3)
        text = self.run_tool("check_readiness.py", "--host", "auto").stdout
        self.assertIn("PreToolUse: firing with 3 faults (last: ValueError at 2026-01-02T03:04:05Z)", text)
        self.assertEqual(result.returncode, 0, "faults are reported, they do not fail readiness")


class MatcherCoverageTests(Scratch):
    """BUGH-16 and SEC-11: a registered matcher has to select the tools the hook needs."""

    def entry(self, matcher, script="pre_tool_use.py", python: str | None = None):
        group = {"hooks": [{"type": "command", "command": repair.command_for(script, python or sys.executable)}]}
        if matcher is not None:
            group = {"matcher": matcher, **group}
        return group

    def config(self, pre=None, post=None, host="claude") -> dict:
        full = self.registered(host)
        config = {"hooks": dict(full["hooks"])}
        if pre is not None:
            config["hooks"]["PreToolUse"] = [pre]
        if post is not None:
            config["hooks"]["PostToolUse"] = [post]
        return config

    def states(self, config, host="claude"):
        return verify.hook_states([config], host)

    def test_selection_rules(self):
        for matcher, tool, expected in (
            (None, "Bash", True), ("", "Bash", True), ("*", "Edit", True), (".*", "Write", True),
            ("Bash", "Bash", True), ("Bash", "PowerShell", False), ("Edit|Write", "Write", True),
            ("Edit|Write", "NotebookEdit", False), ("Notebook.*", "NotebookEdit", True),
            ("Bash", "BashOutput", False), ("Read", "Bash", False), (5, "Bash", False), ("(", "(", True),
        ):
            with self.subTest(matcher=matcher, tool=tool):
                self.assertEqual(verify.matcher_selects(matcher, tool), expected)

    def test_a_matcher_that_selects_none_of_the_tools_is_not_a_registration(self):
        state = self.states(self.config(pre=self.entry("Read")))["pre"]
        self.assertFalse(state["registered"])
        self.assertEqual(state["coverage"], "none")
        self.assertIn("selects none of the tools", state["reason"])

    def test_a_narrower_matcher_is_partial_and_names_what_it_misses(self):
        state = self.states(self.config(pre=self.entry("Bash")))["pre"]
        self.assertTrue(state["registered"])
        self.assertEqual(state["coverage"], "partial")
        self.assertEqual(state["missing_tools"], ["PowerShell", "Edit", "Write", "NotebookEdit"])

    def test_matchers_of_several_entries_add_up(self):
        config = self.config(pre=self.entry("Bash|PowerShell"))
        config["hooks"]["PreToolUse"].append(self.entry("Edit|Write|NotebookEdit"))
        self.assertEqual(self.states(config)["pre"]["coverage"], "full")

    def test_absent_empty_and_wildcard_matchers_cover_everything(self):
        for matcher in (None, "", "*", ".*"):
            with self.subTest(matcher=matcher):
                self.assertEqual(self.states(self.config(pre=self.entry(matcher)))["pre"]["coverage"], "full")

    def test_codex_needs_its_patch_tool(self):
        config = self.registered("codex")
        config["hooks"]["PreToolUse"] = [self.entry("Bash|PowerShell|Edit|Write|NotebookEdit")]
        state = self.states(config, "codex")["pre"]
        self.assertEqual(state["coverage"], "partial")
        self.assertEqual(state["missing_tools"], ["apply_patch"])

    def test_a_hooks_key_of_the_wrong_shape_is_missing_not_a_crash(self):
        for shape in (["x"], "x", {"PreToolUse": "x"}, {"PreToolUse": [5, {"hooks": "x"}, {"hooks": [7, {"command": 3}]}]}):
            with self.subTest(shape=shape):
                self.claude_settings({"hooks": shape})
                result = self.run_tool("verify_registration.py", "--host", "claude")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("status: MISSING", result.stdout)
                self.assertNotIn("error (", result.stdout)

    def test_the_prompt_hook_needs_no_matcher(self):
        self.assertEqual(self.states(self.registered())["prompt"]["coverage"], "not_applicable")

    def test_verify_reports_a_narrow_matcher_as_a_warning_with_exit_zero(self):
        self.claude_settings(self.config(pre=self.entry("Bash")))
        result = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("partial coverage: the matcher misses PowerShell, Edit, Write, NotebookEdit", result.stdout)
        self.assertIn("status: REGISTERED (with warnings)", result.stdout)

    def test_verify_fails_a_matcher_that_selects_nothing(self):
        self.claude_settings(self.config(pre=self.entry("Read")))
        result = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[MISSING] PreToolUse", result.stdout)

    def test_readiness_reports_partial_coverage_and_require_hooks_rejects_it(self):
        self.claude_settings(self.config(pre=self.entry("Bash")))
        ready = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json").stdout)
        self.assertEqual(ready["capabilities"]["hooks_coverage"], "partial")
        self.assertTrue(ready["ready"])
        self.assertIn("repair_registration.py", ready["repair_hint"])
        strict = self.run_tool("check_readiness.py", "--host", "claude", "--require-hooks", "--json")
        self.assertEqual(strict.returncode, 1)
        self.assertFalse(json.loads(strict.stdout)["ready"])

    def test_repair_widens_a_narrow_registration_without_touching_the_old_entry(self):
        narrow = self.entry("Bash")
        settings = self.claude_settings(self.config(pre=narrow))
        preview = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project")
        self.assertEqual(preview.returncode, 1, preview.stdout)
        self.assertIn("PowerShell|Edit|Write|NotebookEdit", preview.stdout)
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout)
        groups = json.loads(settings.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        self.assertEqual(groups[0], narrow, "the entry that was there is left exactly as it was")
        self.assertEqual(groups[1]["matcher"], "PowerShell|Edit|Write|NotebookEdit")
        again = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertIn("no changes", again.stdout)
        self.assertEqual(self.states(json.loads(settings.read_text(encoding="utf-8")))["pre"]["coverage"], "full")

    def test_repair_adds_a_full_group_next_to_a_matcher_that_selects_nothing(self):
        settings = self.claude_settings(self.config(pre=self.entry("Read")))
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        groups = json.loads(settings.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        self.assertEqual(groups[-1]["matcher"], repair.matcher_for("pre_tool_use.py", "claude"))
        self.assertEqual(self.states(json.loads(settings.read_text(encoding="utf-8")))["pre"]["coverage"], "full")

    def test_plan_reports_the_widening_in_its_change_list(self):
        _, added = repair.plan(self.config(pre=self.entry("Bash")), "claude", sys.executable)
        self.assertEqual(added, ["PreToolUse -> pre_tool_use.py (adds PowerShell|Edit|Write|NotebookEdit to a narrower matcher)"])


class InterpreterTests(Scratch):
    """DX-04: repair registers the interpreter that ran it; the verifier checks it."""

    def registered_with(self, interpreter: str) -> dict:
        return self.registered("claude", interpreter)

    def fake_interpreter(self, directory: Path, name: str, body: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_repair_registers_the_interpreter_that_ran_it_not_a_bare_python(self):
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        config = json.loads((self.project / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for event, groups in config["hooks"].items():
            command = groups[0]["hooks"][0]["command"]
            self.assertTrue(command.startswith(repair.launcher_token(sys.executable)), (event, command))

    def test_the_command_starts_python_in_utf8_mode_once(self):
        self.assertIn(" -X utf8 ", repair.command_for("pre_tool_use.py", "python"))
        for launcher in ("python -X utf8", "python -Xutf8", "py -3.13 -X utf8"):
            with self.subTest(launcher=launcher):
                command = repair.command_for("pre_tool_use.py", launcher)
                self.assertEqual(command.count("utf8"), 1, command)
        command = repair.command_for("pre_tool_use.py", "py -3.13")
        self.assertTrue(command.startswith("py -3.13 -X utf8 "), command)
        self.assertTrue(verify.analyse(command, "pre_tool_use.py")["executable"], command)

    def test_the_utf8_flag_survives_a_spaced_interpreter_path(self):
        command = repair.command_for("pre_tool_use.py", "C:/Program Files/Python313/python.exe")
        self.assertTrue(command.startswith('"C:/Program Files/Python313/python.exe" -X utf8 "'), command)

    def test_launcher_parts_split_the_command_from_its_arguments(self):
        for launcher, parts in (
            ("python", ["python"]), ("py -3", ["py", "-3"]), ("C:/Program Files/Python313/python.exe", ["C:/Program Files/Python313/python.exe"]),
            ('"C:/Program Files/Python313/python.exe" -X dev', ["C:/Program Files/Python313/python.exe", "-X", "dev"]),
        ):
            with self.subTest(launcher=launcher):
                self.assertEqual(repair.launcher_parts(launcher), parts)

    def test_the_running_interpreter_is_read_without_being_launched(self):
        report = verify.interpreter_report(repair.command_for("pre_tool_use.py", sys.executable))
        self.assertTrue(report["on_path"])
        self.assertEqual(report["version"], ".".join(str(part) for part in sys.version_info[:3]))
        self.assertTrue(report["meets_floor"])
        self.assertIsNone(verify.interpreter_warning(report))

    def test_an_interpreter_that_does_not_exist_is_a_warning_in_verify_and_readiness(self):
        missing = "/nonexistent/python3.13" if POSIX else "C:/nonexistent/python3.13.exe"
        self.claude_settings(self.registered_with(missing))
        verified = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("was not found on this PATH", verified.stdout)
        self.assertIn("status: REGISTERED (with warnings)", verified.stdout)
        data = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json").stdout)
        self.assertEqual(data["capabilities"]["hooks_interpreter"], "not_found")
        self.assertTrue(any("was not found on this PATH" in warning for warning in data["warnings"]), data["warnings"])
        self.assertTrue(data["ready"])
        strict = self.run_tool("check_readiness.py", "--host", "claude", "--require-hooks", "--json")
        self.assertEqual(strict.returncode, 1)
        self.assertTrue(any("interpreter" in blocker for blocker in json.loads(strict.stdout)["blockers"]))

    @unittest.skipUnless(POSIX, "needs a shell script to stand in for an interpreter")
    def test_an_interpreter_below_the_floor_is_reported(self):
        old = self.fake_interpreter(self.tmp / "bin", "python3.11", 'echo "3 11 4"')
        self.claude_settings(self.registered_with(str(old)))
        verified = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("is Python 3.11.4, below the 3.13 floor", verified.stdout)
        data = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json").stdout)
        self.assertEqual(data["capabilities"]["hooks_interpreter"], "too_old")
        self.assertEqual(data["hooks"]["states"]["claude:pre"]["interpreter"]["version"], "3.11.4")
        strict = self.run_tool("check_readiness.py", "--host", "claude", "--require-hooks", "--json")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("too old", " ".join(json.loads(strict.stdout)["blockers"]))

    @unittest.skipUnless(POSIX, "needs a shell script to stand in for an interpreter")
    def test_an_interpreter_inside_the_project_is_never_run(self):
        marker = self.tmp / "ran"
        planted = self.fake_interpreter(self.project / "tools", "python", f'echo ran > "{marker}"; echo "3 13 0"')
        self.claude_settings(self.registered_with(str(planted)))
        verified = self.run_tool("verify_registration.py", "--host", "claude", "--json")
        self.assertFalse(marker.exists(), "the verifier launched a binary that lives in the project")
        report = json.loads(verified.stdout.split("JSON_REPORT: ", 1)[1])
        self.assertIsNone(report["claude"]["hooks"]["pre"]["interpreter"]["version"])

    @unittest.skipUnless(POSIX, "needs a shell script to stand in for an interpreter")
    def test_an_interpreter_that_prints_nonsense_is_unverified_not_a_crash(self):
        odd = self.fake_interpreter(self.tmp / "bin", "python", 'echo "not a version"')
        self.claude_settings(self.registered_with(str(odd)))
        verified = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertNotIn("below the", verified.stdout)


class ProjectRootTests(Scratch):
    """BUGH-15: repair and verify resolve the project the same way."""

    def test_repair_from_a_subdirectory_writes_where_verify_reads(self):
        sub = self.project / "src" / "deep"
        sub.mkdir(parents=True)
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply", cwd=sub)
        self.assertEqual(applied.returncode, 0, applied.stdout)
        self.assertTrue((self.project / ".claude" / "settings.json").is_file())
        self.assertFalse((sub / ".claude").exists(), "repair wrote under the working directory instead of the project")
        verified = self.run_tool("verify_registration.py", "--host", "claude", cwd=sub)
        self.assertEqual(verified.returncode, 0, verified.stdout)

    def test_both_honour_the_same_project_variable_order(self):
        first, second = self.tmp / "first", self.tmp / "second"
        first.mkdir()
        second.mkdir()
        env = {"SUPREMETEAM_PROJECT_DIR": str(first), "CLAUDE_PROJECT_DIR": str(second)}
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply", **env)
        self.assertEqual(applied.returncode, 0, applied.stdout)
        self.assertTrue((first / ".claude" / "settings.json").is_file())
        self.assertFalse((second / ".claude").exists())
        verified = self.run_tool("verify_registration.py", "--host", "claude", **env)
        self.assertEqual(verified.returncode, 0, verified.stdout)

    def test_every_project_scope_target_is_a_file_verify_reads(self):
        # install_hooks.py takes its target from repair.target_path, so this is the
        # installer's path too.
        sub = self.project / "pkg"
        sub.mkdir()
        code = ("import sys; sys.path.insert(0, %r); import repair_registration as r, verify_registration as v; "
                "print(all(r.target_path(h, s) in v._paths(h) for h in v.HOSTS for s in ('project', 'local') "
                "if (h, s) != ('codex', 'local') and (h, s) != ('copilot', 'local')))" % str(HOOK_DIR))
        out = subprocess.run([sys.executable, "-c", code], cwd=str(sub), env=plain_env(self.home), text=True, capture_output=True, check=False)
        self.assertEqual(out.stdout.strip(), "True", out.stderr)


class ScopeWarningTests(Scratch):
    """DX-15: say what a scope touches before it is touched."""

    def test_project_scope_warns_that_the_file_is_usually_committed(self):
        result = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project")
        self.assertIn("machine-absolute hook paths", result.stderr)
        self.assertIn("--scope local", result.stderr)
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual(len(payload["warnings"]), 1)

    def test_other_hosts_are_told_to_keep_the_file_out_of_the_commit(self):
        result = self.run_tool("repair_registration.py", "--host", "copilot", "--scope", "project")
        self.assertIn("keep it out of the commit", result.stderr)

    def test_local_scope_has_nothing_to_warn_about(self):
        result = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "local")
        self.assertEqual(result.stderr, "")

    def test_user_scope_says_it_is_global(self):
        result = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "user")
        self.assertIn("global claude configuration", result.stderr)
        self.assertFalse((self.home / ".claude").exists(), "a preview must not create the global directory")

    def test_nothing_to_change_prints_no_warning(self):
        self.claude_settings(self.registered())
        result = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project")
        self.assertEqual(result.stderr, "")


@unittest.skipUnless(POSIX, "permission bits are POSIX")
class FileModeTests(Scratch):
    """SEC-15: the config keeps its mode, so does its backup, and new user files are owner-only."""

    def setUp(self):
        super().setUp()
        self._umask = os.umask(0o022)
        self.addCleanup(os.umask, self._umask)

    def mode(self, path: Path) -> int:
        return stat.S_IMODE(path.stat().st_mode)

    def test_a_private_settings_file_stays_private_and_so_does_its_backup(self):
        settings = self.claude_settings({"env": {"TOKEN": "x"}})
        settings.chmod(0o600)
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout)
        self.assertEqual(self.mode(settings), 0o600)
        backups = list(settings.parent.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.mode(backups[0]), 0o600)

    def test_an_unusual_mode_is_kept_exactly(self):
        settings = self.claude_settings({})
        settings.chmod(0o640)
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(self.mode(settings), 0o640)
        self.assertEqual(self.mode(next(settings.parent.glob("settings.json.bak-*"))), 0o640)

    def test_a_new_user_scope_file_is_owner_only(self):
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "user", "--apply")
        self.assertEqual(self.mode(self.home / ".claude" / "settings.json"), 0o600)

    def test_a_new_project_file_follows_the_umask(self):
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(self.mode(self.project / ".claude" / "settings.json"), 0o644)

    def test_no_temporary_file_is_left_behind(self):
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(list((self.project / ".claude").glob("*.tmp")), [])


@unittest.skipUnless(POSIX, "symbolic links need privileges on Windows")
class ConfigLinkTests(Scratch):
    """RR-V3-2: a host config that is a symbolic link was replaced by a regular file, so the dotfiles copy never learned of it."""

    def link(self, at: Path, content: str = '{"theme": "dark"}\n') -> Path:
        target = self.tmp / "dotfiles" / at.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        target.chmod(0o640)
        at.parent.mkdir(parents=True, exist_ok=True)
        at.symlink_to(target)
        return target

    def test_a_user_level_link_is_written_through_and_stays_a_link(self):
        settings = self.home / ".claude" / "settings.json"
        target = self.link(settings)
        out = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "user", "--apply")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(settings.is_symlink(), "the link is still a link")
        written = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(written["theme"], "dark")
        self.assertEqual(sorted(written["hooks"]), ["PostToolUse", "PreToolUse", "UserPromptSubmit"])
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o640, "the target keeps its own mode")
        self.assertIn("symbolic link", out.stderr)
        self.assertIn("machine-absolute", out.stderr, "a file synced to other machines needs its own registration there")
        self.assertEqual(json.loads(out.stdout)["path"], str(target))
        self.assertEqual(len(list(target.parent.glob("settings.json.bak-*"))), 1, "the backup sits beside the file it backs up")

    def test_a_project_level_link_is_refused_and_nothing_changes(self):
        settings = self.project / ".claude" / "settings.json"
        target = self.link(settings)
        before = target.read_bytes()
        for args in (("--scope", "project"), ("--scope", "project", "--apply")):
            with self.subTest(args=args):
                out = self.run_tool("repair_registration.py", "--host", "claude", *args)
                self.assertEqual(out.returncode, 2, out.stdout + out.stderr)
                error = json.loads(out.stdout)["error"]
                self.assertIn(str(target), error)
                self.assertIn("refusing to replace it", error)
                self.assertTrue(settings.is_symlink())
                self.assertEqual(target.read_bytes(), before)

    def test_a_link_that_leads_nowhere_is_refused_at_any_scope(self):
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.symlink_to(self.tmp / "gone.json")
        out = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "user", "--apply")
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("does not lead to a file", json.loads(out.stdout)["error"])
        self.assertTrue(settings.is_symlink())
        self.assertFalse((self.tmp / "gone.json").exists(), "nothing was created at the end of a dangling link")

    def test_a_link_to_a_directory_is_refused(self):
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.symlink_to(self.tmp)
        out = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "user", "--apply")
        self.assertEqual(out.returncode, 2, out.stdout)
        self.assertIn("not a file", json.loads(out.stdout)["error"])

    def test_a_regular_file_is_written_as_before(self):
        settings = self.claude_settings({"theme": "dark"})
        out = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertFalse(settings.is_symlink())
        self.assertNotIn("symbolic link", out.stderr)


class RepairEncodingTests(Scratch):
    """BUGH-17: a settings file that is not UTF-8 is refused, not a traceback."""

    def test_repair_refuses_a_utf16_file_and_leaves_it_alone(self):
        settings = self.project / ".claude" / "settings.json"
        settings.parent.mkdir()
        original = '{"theme": "dark"}'.encode("utf-16")
        settings.write_bytes(original)
        for args in (("--scope", "project"), ("--scope", "project", "--apply")):
            with self.subTest(args=args):
                result = self.run_tool("repair_registration.py", "--host", "claude", *args)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("cannot be read as UTF-8", json.loads(result.stdout)["error"])
                self.assertEqual(settings.read_bytes(), original)

    def test_repair_refuses_a_file_it_cannot_read(self):
        settings = self.project / ".claude" / "settings.json"
        settings.mkdir(parents=True)
        result = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class IntegrityTests(Scratch):
    """Tamper evidence: hook scripts are hashed when registered; a change is reported, not failed."""

    def relocated_hooks(self) -> Path:
        root = self.tmp / "hooks"
        root.mkdir()
        for _, script in verify.REQUIRED:
            (root / script).write_text(f"# {script}\n", encoding="utf-8")
        return root

    def settings_pointing_at(self, root: Path) -> Path:
        handlers = {verify.EVENTS["claude"][key]: [{"hooks": [{"type": "command", "command": f'"{sys.executable}" -X utf8 "{root / script}"'}]}]
                    for key, script in verify.REQUIRED}
        return self.claude_settings({"hooks": handlers})

    def record(self) -> dict:
        return json.loads((self.project / ".harness-state" / verify.HASH_RECORD).read_text(encoding="utf-8"))

    def test_apply_records_the_sha256_of_each_registered_script(self):
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout)
        hooks = self.record()["hooks"]
        self.assertEqual(len(hooks), len(verify.REQUIRED))
        for _, script in verify.REQUIRED:
            entry = hooks[verify.hash_key(HOOK_DIR / script)]
            self.assertEqual(entry["sha256"], verify.hook_hash(HOOK_DIR / script))
            self.assertEqual(entry["host"], "claude")
        self.assertEqual(json.loads(applied.stdout)["hash_record"], str(self.project / ".harness-state" / verify.HASH_RECORD))
        self.assertEqual(list((self.project / ".harness-state").glob("*.tmp")), [])

    def test_a_script_that_matches_its_record_is_unchanged(self):
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        out = self.run_tool("verify_registration.py", "--host", "claude", "--json")
        report = json.loads(out.stdout.split("JSON_REPORT: ", 1)[1])
        self.assertEqual({h["integrity"] for h in report["claude"]["hooks"].values()}, {"unchanged"})
        self.assertNotIn("changed since registration", out.stdout)

    def test_no_record_is_reported_as_unrecorded_and_says_nothing(self):
        self.claude_settings(self.registered())
        out = self.run_tool("verify_registration.py", "--host", "claude", "--json")
        report = json.loads(out.stdout.split("JSON_REPORT: ", 1)[1])
        self.assertEqual({h["integrity"] for h in report["claude"]["hooks"].values()}, {"unrecorded"})
        self.assertNotIn("changed since registration", out.stdout)

    def test_an_edited_script_is_reported_with_the_way_to_re_record_and_does_not_fail(self):
        root = self.relocated_hooks()
        self.settings_pointing_at(root)
        env = {"SUPREMETEAM_HOOK_ROOT": str(root)}
        recorded = self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        self.assertEqual(recorded.returncode, 0, recorded.stdout)
        self.assertIn("recorded", json.loads(recorded.stdout))
        (root / "pre_tool_use.py").write_text("# edited\n", encoding="utf-8")
        verified = self.run_tool("verify_registration.py", "--host", "claude", **env)
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("pre_tool_use.py changed since registration", verified.stdout)
        self.assertIn("repair_registration.py --host claude --record-hashes", verified.stdout)
        ready = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json", **env).stdout)
        self.assertTrue(ready["ready"], "an edited hook is a note, not a failure")
        self.assertTrue(any("changed since registration" in warning for warning in ready["warnings"]), ready["warnings"])
        again = self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        self.assertEqual(again.returncode, 0)
        after = self.run_tool("verify_registration.py", "--host", "claude", **env)
        self.assertNotIn("changed since registration", after.stdout)

    def hooks_with_modules(self) -> Path:
        """A hook directory like the real one: the three entry scripts, the modules they import, and a test module."""
        root = self.relocated_hooks()
        for name in ("guard_hook.py", "_state.py", "_saves.py", "test_guard_rules.py"):
            (root / name).write_text(f"# {name}\n", encoding="utf-8")
        self.settings_pointing_at(root)
        return root

    def verify_json(self, **env: str) -> tuple[subprocess.CompletedProcess, dict]:
        out = self.run_tool("verify_registration.py", "--host", "claude", "--json", **env)
        return out, json.loads(out.stdout.split("JSON_REPORT: ", 1)[1])["claude"]["hooks"]

    def test_every_module_beside_the_entry_scripts_is_recorded_but_not_the_tests(self):
        """Only the three entry scripts were hashed, so an edit of the module that holds the rules left readiness at Ready: yes."""
        root = self.hooks_with_modules()
        env = {"SUPREMETEAM_HOOK_ROOT": str(root)}
        self.assertEqual(self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env).returncode, 0)
        directories = self.record()["directories"]
        entry = directories[verify.hash_key(root)]
        self.assertEqual(sorted(entry["files"]), ["_saves.py", "_state.py", "guard_hook.py", "post_tool_use.py", "pre_tool_use.py",
                                                  "user_prompt_submit.py"])
        self.assertEqual(entry["files"]["guard_hook.py"], verify.hook_hash(root / "guard_hook.py"))

    def test_an_edit_of_a_module_that_is_not_an_entry_script_is_reported_and_does_not_fail(self):
        root = self.hooks_with_modules()
        env = {"SUPREMETEAM_HOOK_ROOT": str(root)}
        self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        out, hooks = self.verify_json(**env)
        self.assertEqual({h["integrity"] for h in hooks.values()}, {"unchanged"})
        (root / "guard_hook.py").write_text("# return early\n", encoding="utf-8")
        out, hooks = self.verify_json(**env)
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual({h["integrity"] for h in hooks.values()}, {"changed"})
        self.assertEqual({tuple(h["changed_files"]) for h in hooks.values()}, {("guard_hook.py",)})
        self.assertIn("guard_hook.py changed since registration", out.stdout)
        ready = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json", **env).stdout)
        self.assertTrue(ready["ready"], "a changed module is a warning, not a failure")
        self.assertTrue(any("claude:guard_hook.py" in warning for warning in ready["warnings"]), ready["warnings"])
        self.assertFalse(any("pre_tool_use.py" in warning for warning in ready["warnings"]), "an entry script that did not change is not named")
        self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        self.assertEqual({h["integrity"] for h in self.verify_json(**env)[1].values()}, {"unchanged"})

    def test_a_module_added_or_removed_after_registration_is_a_change_and_a_test_edit_is_not(self):
        root = self.hooks_with_modules()
        env = {"SUPREMETEAM_HOOK_ROOT": str(root)}
        self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        (root / "test_guard_rules.py").write_text("# edited test\n", encoding="utf-8")
        self.assertEqual({h["integrity"] for h in self.verify_json(**env)[1].values()}, {"unchanged"})
        (root / "planted.py").write_text("# new\n", encoding="utf-8")
        (root / "_saves.py").unlink()
        hooks = self.verify_json(**env)[1]
        self.assertEqual({tuple(h["changed_files"]) for h in hooks.values()}, {("_saves.py", "planted.py")})

    def test_a_record_made_before_directories_were_recorded_still_reads_and_says_nothing_new(self):
        root = self.hooks_with_modules()
        env = {"SUPREMETEAM_HOOK_ROOT": str(root)}
        self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        record = self.record()
        del record["directories"]
        self.write_json(self.project / ".harness-state" / verify.HASH_RECORD, record)
        (root / "guard_hook.py").write_text("# edited\n", encoding="utf-8")
        hooks = self.verify_json(**env)[1]
        self.assertEqual({h["integrity"] for h in hooks.values()}, {"unchanged"}, "nothing was recorded about the module, so nothing can differ")
        (root / "pre_tool_use.py").write_text("# edited\n", encoding="utf-8")
        self.assertEqual(self.verify_json(**env)[1]["pre"]["changed_files"], ["pre_tool_use.py"])

    def test_the_note_is_worded_for_an_upgrade_as_well_as_an_edit(self):
        root = self.hooks_with_modules()
        env = {"SUPREMETEAM_HOOK_ROOT": str(root)}
        self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes", **env)
        (root / "_state.py").write_text("# a newer release\n", encoding="utf-8")
        verified = self.run_tool("verify_registration.py", "--host", "claude", **env).stdout
        self.assertIn("expected after a deliberate edit or an upgrade", verified)
        self.assertIn("restore the files", verified)
        ready = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json", **env).stdout)
        self.assertTrue(any("or an upgrade" in warning for warning in ready["warnings"]), ready["warnings"])

    def test_recording_needs_a_registration(self):
        result = self.run_tool("repair_registration.py", "--host", "claude", "--record-hashes")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("not registered", json.loads(result.stdout)["error"])
        self.assertFalse((self.project / ".harness-state").exists())

    def test_recording_merges_into_the_existing_record_by_script_path(self):
        record = self.project / ".harness-state" / verify.HASH_RECORD
        self.write_json(record, {"schema_version": 1, "hooks": {"/elsewhere/pre_tool_use.py": {"sha256": "ab" * 32}}})
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.run_tool("repair_registration.py", "--host", "codex", "--scope", "project", "--apply")
        hooks = self.record()["hooks"]
        self.assertIn("/elsewhere/pre_tool_use.py", hooks, "an entry for another install is kept")
        self.assertEqual(len(hooks), len(verify.REQUIRED) + 1)
        self.assertEqual({hooks[verify.hash_key(HOOK_DIR / script)]["host"] for _, script in verify.REQUIRED}, {"codex"},
                         "the same script registered for a second host updates its entry")

    def test_a_malformed_record_is_ignored(self):
        self.claude_settings(self.registered())
        record = self.project / ".harness-state" / verify.HASH_RECORD
        record.parent.mkdir()
        record.write_text("{nope", encoding="utf-8")
        out = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(out.returncode, 0, out.stdout)


class MirrorRootTests(Scratch):
    """RR-V3-3: the installer registers the common root, and `Install.md` names the host mirrors as roots too."""

    def install_root(self, relative: str, with_scripts: bool = True) -> Path:
        hooks = self.home / relative / "harness" / "hooks"
        hooks.mkdir(parents=True)
        for _, script in verify.REQUIRED:
            if with_scripts or script != "pre_tool_use.py":
                (hooks / script).write_text(f"# {script}\n", encoding="utf-8")
        return hooks

    def register_at(self, hooks: Path) -> None:
        handlers = {verify.EVENTS["claude"][key]: [{"matcher": verify.matcher_for(script, "claude"),
                                                    "hooks": [{"type": "command", "command": f'"{sys.executable}" -X utf8 "{hooks / script}"'}]}]
                    for key, script in verify.REQUIRED}
        self.write_json(self.home / ".claude" / "settings.json", {"hooks": handlers})

    def test_a_check_run_from_a_mirror_recognises_the_registration_of_the_common_root(self):
        common = self.install_root(".agents/skills")
        self.install_root(".claude/skills")
        self.register_at(common)
        out = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("status: REGISTERED", out.stdout)

    def test_the_repair_preview_adds_nothing_when_an_install_root_is_already_registered(self):
        self.register_at(self.install_root(".agents/skills"))
        out = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "user")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(json.loads(out.stdout)["changes"], [])

    def test_a_mirror_registered_instead_is_recognised_from_the_checkout_as_well(self):
        self.register_at(self.install_root(".claude/skills"))
        self.assertEqual(self.run_tool("verify_registration.py", "--host", "claude").returncode, 0)

    def test_an_install_root_without_the_hook_scripts_is_not_taken_for_a_registration(self):
        hooks = self.install_root(".agents/skills", with_scripts=False)
        self.register_at(hooks)
        self.assertEqual(self.run_tool("verify_registration.py", "--host", "claude").returncode, 1)

    def test_a_registration_pointing_anywhere_else_is_still_missing(self):
        self.install_root(".agents/skills")
        self.register_at(self.tmp / "elsewhere" / "harness" / "hooks")
        self.assertEqual(self.run_tool("verify_registration.py", "--host", "claude").returncode, 1)


class InstalledCopyTests(Scratch):
    """DX-06: the repair command a diagnostic prints has to exist where the diagnostic runs."""

    def installed_hooks(self) -> Path:
        """The hooks directory as an installer lays it out: `<root>/harness/hooks` beside `<root>/scripts`, no checkout around it."""
        root = self.tmp / "installed-skills"
        keep = shutil.ignore_patterns("__pycache__", "test_*", "_testkit.py")
        shutil.copytree(HOOK_DIR, root / "harness" / "hooks", ignore=keep)
        shutil.copytree(HOOK_DIR.parents[1] / "scripts", root / "scripts", ignore=keep)
        return root / "harness" / "hooks"

    def assert_runs_from_here(self, command: str, hooks: Path) -> None:
        tokens = verify._tokens(command)
        self.assertEqual(Path(tokens[1]), hooks / "repair_registration.py", command)
        self.assertTrue(Path(tokens[1]).is_absolute() and Path(tokens[1]).is_file(), command)
        preview = subprocess.run(tokens, text=True, capture_output=True, cwd=str(self.project), env=plain_env(self.home), check=False)
        self.assertEqual(preview.returncode, 1, preview.stdout + preview.stderr)
        self.assertIn("proposed", preview.stdout)

    def test_the_verifier_prints_a_repair_command_that_runs_in_an_installed_copy(self):
        hooks = self.installed_hooks()
        self.claude_settings({"theme": "dark"})
        out = subprocess.run([sys.executable, str(hooks / "verify_registration.py"), "--host", "claude"], text=True, capture_output=True,
                             cwd=str(self.project), env=plain_env(self.home), check=False)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        line = next(line for line in out.stdout.splitlines() if "preview a scoped repair with: " in line)
        self.assert_runs_from_here(line.split("preview a scoped repair with: ", 1)[1], hooks)

    def test_readiness_prints_a_repair_command_that_runs_in_an_installed_copy(self):
        hooks = self.installed_hooks()
        self.claude_settings({"theme": "dark"})
        out = subprocess.run([sys.executable, str(hooks / "check_readiness.py"), "--host", "claude", "--json"], text=True, capture_output=True,
                             cwd=str(self.project), env=plain_env(self.home), check=False)
        hint = json.loads(out.stdout)["repair_hint"]
        self.assert_runs_from_here(hint.split(" (dry run", 1)[0], hooks)

    def test_the_hash_note_names_the_same_command(self):
        command = verify.repair_command("claude", "--record-hashes")
        self.assertEqual(verify._tokens(command)[1:], [str(HOOK_DIR / "repair_registration.py"), "--host", "claude", "--record-hashes"])
        self.assertEqual(verify._tokens(command)[0], sys.executable)


class DeclaredMinimumTests(unittest.TestCase):
    """QR-PY-16: the floor is read with the catalog's loader, so reformatting the manifest cannot hide it."""

    def read(self, text: str | None) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "runtime-manifest.yaml"
            if text is not None:
                manifest.write_text(text, encoding="utf-8")
            with mock.patch.object(verify, "RUNTIME_MANIFEST", manifest):
                return verify.declared_minimum()

    def test_a_manifest_written_as_json_is_read(self):
        self.assertEqual(self.read('{"schema_version": 1, "runtime": {"python": {"minimum": "3.77"}}}'), "3.77")

    def test_a_manifest_written_as_block_yaml_is_read_not_replaced_by_the_default(self):
        self.assertEqual(self.read('schema_version: 1\nruntime:\n  python:\n    minimum: "3.77"\n'), "3.77")

    def test_a_missing_or_unreadable_manifest_falls_back_to_the_default(self):
        self.assertEqual(self.read(None), "3.13")
        self.assertEqual(self.read("{not a manifest"), "3.13")

    def test_the_real_manifest_declares_the_floor_the_default_names(self):
        self.assertEqual(verify.declared_minimum(default="0.0"), "3.13")


class RepairWriteTests(Scratch):
    """QR-PY-05: the repair tool's writer has the guarantees of the shared one."""

    def test_a_transient_sharing_violation_on_the_replace_is_retried(self):
        settings = self.claude_settings({"theme": "dark"})
        real = os.replace
        attempts = []

        def flaky(source, target):
            if Path(target) == settings:
                attempts.append(source)
                if len(attempts) < 3:
                    raise PermissionError(13, "sharing violation")
            return real(source, target)

        with mock.patch.object(os, "replace", flaky), mock.patch("_fsutil.time.sleep"):
            repair.write_with_backup(settings, '{"theme": "light"}\n')
        self.assertEqual(len(attempts), 3)
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), {"theme": "light"})
        self.assertEqual(list(settings.parent.glob("*.tmp")), [])

    def test_the_bytes_are_flushed_to_disk_before_the_replace(self):
        settings = self.claude_settings({})
        with mock.patch.object(os, "fsync", wraps=os.fsync) as fsync:
            repair.write_with_backup(settings, "{}\n")
        self.assertGreaterEqual(fsync.call_count, 2, "the backup and the new file are both synced")

    def test_the_hash_record_is_written_with_the_shared_atomic_write(self):
        import _fsutil

        script = str(HOOK_DIR / "pre_tool_use.py")
        with mock.patch.dict(os.environ, {"SUPREMETEAM_PROJECT_DIR": str(self.project)}):
            with mock.patch("_fsutil.atomic_write", wraps=_fsutil.atomic_write) as writer:
                record = repair.record_hashes({"pre": {"registered": True, "script": script}}, "claude")
        self.assertTrue(any(call.args[0] == record for call in writer.call_args_list))
        self.assertIn(verify.hash_key(script), json.loads(record.read_text(encoding="utf-8"))["hooks"])


if __name__ == "__main__":
    unittest.main()
