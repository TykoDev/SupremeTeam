#!/usr/bin/env python3
"""The hook registration contract shared by the installer and the repair tool.

`scripts/install_hooks.py` (first-time registration) and `repair_registration.py`
(later repair) write into the same host config files. When they disagree about the
required hooks, the matcher, or the command format, the second tool either
duplicates the first tool's entry or silently narrows its scope. These tests pin
the shared definitions and assert the two tools agree on a real config file.

The installer lives in the repository's `scripts/` directory and is not part of an
installed skill tree, so the tests that invoke it skip when it is absent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import repair_registration as repair  # noqa: E402
import verify_registration as verify  # noqa: E402

INSTALLER = HOOK_DIR.parents[2] / "scripts" / "install_hooks.py"
HAS_INSTALLER = INSTALLER.is_file()


def run_installer(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(INSTALLER), "--hook-root", str(HOOK_DIR), *args],
        capture_output=True,
        text=True,
    )


class SharedDefinitionTests(unittest.TestCase):
    """One definition of the hook set, the matcher, and the command format."""

    def test_codex_matcher_names_its_patch_tool_and_other_hosts_do_not(self):
        # Codex realizes edits through apply_patch. A matcher that omits it would let
        # a Codex file edit past the Layer 3 guard entirely.
        self.assertIn("apply_patch", repair.matcher_for("pre_tool_use.py", "codex"))
        self.assertIn("apply_patch", repair.matcher_for("post_tool_use.py", "codex"))
        for host in ("claude", "copilot"):
            self.assertNotIn("apply_patch", repair.matcher_for("pre_tool_use.py", host))

    def test_the_prompt_hook_has_no_matcher_on_any_host(self):
        for host in ("claude", "codex", "copilot"):
            self.assertIsNone(repair.matcher_for("user_prompt_submit.py", host))

    def test_matcher_never_duplicates_a_tool_name(self):
        for host in ("claude", "codex", "copilot"):
            for script in ("pre_tool_use.py", "post_tool_use.py"):
                tools = repair.matcher_for(script, host).split("|")
                self.assertEqual(len(tools), len(set(tools)), f"{host}/{script} repeats a tool name")

    def test_every_required_hook_has_a_status_message(self):
        for _, script in verify.REQUIRED:
            self.assertIn(script, repair.STATUS_MESSAGES)


class LauncherQuotingTests(unittest.TestCase):
    """A registered command must survive verify_registration's tokenizer."""

    def test_a_spaced_interpreter_path_is_quoted(self):
        self.assertEqual(
            repair.launcher_token("C:/Program Files/Python313/python.exe"),
            '"C:/Program Files/Python313/python.exe"',
        )

    def test_a_launcher_carrying_arguments_is_left_alone(self):
        # Quoting "py -3.13" would collapse it into one path that does not exist.
        for launcher in ("py -3.13", "python -X utf8", "python3 -E"):
            self.assertEqual(repair.launcher_token(launcher), launcher)

    def test_an_already_quoted_or_unspaced_launcher_is_unchanged(self):
        for launcher in ("python", "python3", '"C:/a b/python.exe"', ""):
            self.assertEqual(repair.launcher_token(launcher), launcher)

    def test_quoting_does_not_depend_on_the_local_filesystem(self):
        # Registering an interpreter for another machine must behave identically.
        absent = "/nonexistent dir/python3"
        self.assertFalse(Path(absent).exists())
        self.assertEqual(repair.launcher_token(absent), f'"{absent}"')

    def test_a_spaced_interpreter_command_verifies_as_executable(self):
        command = repair.command_for("pre_tool_use.py", sys.executable)
        self.assertTrue(verify.analyse(command, "pre_tool_use.py")["executable"], command)


class PlanTests(unittest.TestCase):
    def test_plan_adds_every_required_hook_to_an_empty_config(self):
        _, added = repair.plan({}, "claude", sys.executable)
        self.assertEqual(len(added), len(verify.REQUIRED))

    def test_plan_is_idempotent(self):
        desired, _ = repair.plan({}, "claude", sys.executable)
        _, again = repair.plan(json.loads(json.dumps(desired)), "claude", sys.executable)
        self.assertEqual(again, [], "a second plan would duplicate an existing registration")

    def test_plan_refuses_a_hooks_key_that_is_not_an_object(self):
        with self.assertRaises(ValueError):
            repair.plan({"hooks": ["not", "an", "object"]}, "claude", sys.executable)


@unittest.skipUnless(HAS_INSTALLER, "scripts/install_hooks.py is repository tooling, not an installed file")
class InstallerContractTests(unittest.TestCase):
    """The installer's behaviour on real config files."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def load_installer(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("install_hooks_under_test", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_native_hosts_are_exactly_the_hosts_the_verifier_knows(self):
        module = self.load_installer()
        self.assertEqual(set(module.NATIVE_HOSTS), set(verify.EVENTS))
        self.assertFalse(set(module.PLUGIN_HOSTS) & set(verify.EVENTS),
                         "a plugin host must not claim to be verifiable")

    def test_registration_verifies_after_writing(self):
        settings = self.tmp / "settings.json"
        result = run_installer("--target", "claude", "--claude-settings", str(settings))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("status: REGISTERED", result.stdout)
        for _, script in verify.REQUIRED:
            self.assertIn(script, result.stdout)

    def test_a_second_run_changes_nothing(self):
        settings = self.tmp / "settings.json"
        run_installer("--target", "claude", "--claude-settings", str(settings))
        first = settings.read_text(encoding="utf-8")
        result = run_installer("--target", "claude", "--claude-settings", str(settings))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no changes: already registered", result.stdout)
        self.assertEqual(settings.read_text(encoding="utf-8"), first)

    def test_repair_finds_nothing_to_add_after_an_install(self):
        # The drift this whole module exists to prevent: two writers, two answers.
        project = self.tmp / "project"
        (project / ".claude").mkdir(parents=True)
        settings = project / ".claude" / "settings.json"
        run_installer("--target", "claude", "--claude-settings", str(settings))
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project)
        result = subprocess.run(
            [sys.executable, str(HOOK_DIR / "repair_registration.py"), "--host", "claude", "--scope", "project"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no changes", result.stdout)

    def test_unrelated_configuration_survives(self):
        settings = self.tmp / "settings.json"
        original = {
            "permissions": {"allow": ["Bash"]},
            "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo mine"}]}]},
        }
        settings.write_text(json.dumps(original), encoding="utf-8")
        result = run_installer("--target", "claude", "--claude-settings", str(settings))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(after["permissions"], original["permissions"])
        commands = [hook["command"] for group in after["hooks"]["PreToolUse"] for hook in group["hooks"]]
        self.assertIn("echo mine", commands)

    def test_an_overwrite_leaves_a_backup(self):
        settings = self.tmp / "settings.json"
        settings.write_text(json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
        run_installer("--target", "claude", "--claude-settings", str(settings))
        backups = list(self.tmp.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1, f"expected exactly one backup, found {backups}")
        self.assertEqual(json.loads(backups[0].read_text(encoding="utf-8")), {"permissions": {"allow": []}})

    def test_invalid_json_is_refused_and_left_untouched(self):
        settings = self.tmp / "settings.json"
        settings.write_text("{ not json", encoding="utf-8")
        result = run_installer("--target", "claude", "--claude-settings", str(settings))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("refusing to overwrite", result.stdout)
        self.assertEqual(settings.read_text(encoding="utf-8"), "{ not json")

    def test_a_non_object_config_is_refused(self):
        settings = self.tmp / "settings.json"
        settings.write_text("[1, 2, 3]", encoding="utf-8")
        result = run_installer("--target", "claude", "--claude-settings", str(settings))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(settings.read_text(encoding="utf-8"), "[1, 2, 3]")

    def test_dry_run_writes_nothing_and_prints_a_diff(self):
        settings = self.tmp / "settings.json"
        result = run_installer("--target", "claude", "--claude-settings", str(settings), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PreToolUse", result.stdout)
        self.assertIn("dry run: nothing written", result.stdout)
        self.assertFalse(settings.exists(), "a dry run created the config file")

    def test_a_missing_hook_root_is_refused(self):
        result = subprocess.run(
            [sys.executable, str(INSTALLER), "--hook-root", str(self.tmp), "--target", "claude"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Hook root is missing", result.stdout)

    def test_plugin_hosts_are_reported_as_not_verifiable(self):
        result = run_installer(
            "--target", "cursor", "--target", "opencode",
            "--cursor-plugin", str(self.tmp / "cursor"),
            "--opencode-plugin", str(self.tmp / "opencode.js"),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("not machine-verifiable", result.stdout)
        self.assertNotIn("status: REGISTERED", result.stdout)
        self.assertTrue((self.tmp / "cursor" / "hooks" / "hooks.json").is_file())
        self.assertTrue((self.tmp / "opencode.js").is_file())

    def test_the_report_never_claims_the_host_fired_a_hook(self):
        settings = self.tmp / "settings.json"
        result = run_installer("--target", "claude", "--claude-settings", str(settings))
        self.assertIn("observed: unverified", result.stdout)


if __name__ == "__main__":
    unittest.main()
