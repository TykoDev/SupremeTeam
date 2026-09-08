#!/usr/bin/env python3
"""Harness regression tests captured from the 2026-09-05 audit (UPDATED-REPORT.md F3, F4).

Registration false positives (`python -c "pass" <hook>` and a configured but
nonexistent script), missing-session trajectory sharing, freeze records with
release metadata, the scoped repair tool, and readiness capability reporting.
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
import verify_registration as verify  # noqa: E402


def env_for(project: Path, home: Path | None = None, **extra: str) -> dict:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    for name in ("SUPREMETEAM_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "COPILOT_SESSION_ID", "GITHUB_RUN_ID"):
        env.pop(name, None)
    if home is not None:
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
    env.update(extra)
    return env


class RegistrationAnalysisTests(unittest.TestCase):
    def test_inline_program_mentioning_the_hook_is_not_executable(self):
        real = HOOK_DIR / "pre_tool_use.py"
        state = verify.analyse(f'python -c "pass" "{real}"', "pre_tool_use.py")
        self.assertTrue(state["configured"])
        self.assertTrue(state["resolvable"])
        self.assertFalse(state["executable"])
        self.assertIn("-c", state["reason"])
        state = verify.analyse(f'python -m runpy "{real}"', "pre_tool_use.py")
        self.assertFalse(state["executable"])

    def test_nonexistent_configured_script_is_not_registered(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SUPREMETEAM_HOOK_ROOT"] = tmp
            try:
                state = verify.analyse(f'python "{Path(tmp) / "pre_tool_use.py"}"', "pre_tool_use.py")
            finally:
                os.environ.pop("SUPREMETEAM_HOOK_ROOT", None)
        self.assertTrue(state["configured"])
        self.assertFalse(state["resolvable"])
        self.assertFalse(state["executable"])

    def test_environment_variable_forms_and_py_launcher_are_accepted(self):
        real = HOOK_DIR / "post_tool_use.py"
        os.environ["SUPREMETEAM_HOOK_ROOT_TEST"] = str(HOOK_DIR)
        try:
            for command in (f'python "$SUPREMETEAM_HOOK_ROOT_TEST/post_tool_use.py"', f'py -3.13 "%SUPREMETEAM_HOOK_ROOT_TEST%/post_tool_use.py"',
                            f'python -u -X utf8 "{real}"', f'FOO=bar python "{real}"'):
                with self.subTest(command=command):
                    self.assertTrue(verify.analyse(command, "post_tool_use.py")["executable"], command)
        finally:
            os.environ.pop("SUPREMETEAM_HOOK_ROOT_TEST", None)

    def test_option_that_swallows_the_path_is_not_executable(self):
        real = HOOK_DIR / "post_tool_use.py"
        self.assertFalse(verify.analyse(f'python -W "{real}"', "post_tool_use.py")["executable"])
        self.assertFalse(verify.analyse(f'node "{real}"', "post_tool_use.py")["executable"])


class TrajectoryIsolationTests(unittest.TestCase):
    def _fail_payload(self) -> str:
        return json.dumps({"tool_name": "Bash", "tool_input": {"command": "make test"},
                           "tool_response": {"exit_code": 1, "stdout": "boom"}})

    def _spawn_via_fresh_parent(self, project: Path) -> str:
        """Run the post hook from a distinct parent process (an independent host)."""
        wrapper = (
            "import subprocess, sys, json;"
            f"r = subprocess.run([sys.executable, r'{HOOK_DIR / 'post_tool_use.py'}'], input=sys.stdin.read(), text=True, capture_output=True);"
            "sys.stdout.write(r.stdout)"
        )
        proc = subprocess.run([sys.executable, "-c", wrapper], input=self._fail_payload(), text=True, capture_output=True,
                              env=env_for(project), check=False)
        return proc.stdout

    def test_independent_processes_without_session_id_do_not_share_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            outputs = [self._spawn_via_fresh_parent(project) for _ in range(3)]
        self.assertTrue(all(out.strip() == "" for out in outputs), outputs)

    def test_same_session_id_still_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            payload = json.loads(self._fail_payload())
            payload["session_id"] = "s-1"
            outputs = []
            for _ in range(3):
                proc = subprocess.run([sys.executable, str(HOOK_DIR / "post_tool_use.py")], input=json.dumps(payload), text=True,
                                      capture_output=True, env=env_for(project), check=False)
                outputs.append(proc.stdout)
            self.assertIn("failed 3 times", outputs[-1])
            files = list((project / ".harness-state" / "trajectories").rglob("*.json"))
            self.assertEqual(len(files), 1)
            self.assertNotIn("s-1", files[0].name, "identity is hashed, not embedded")

    def test_environment_session_id_scopes_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            payload = self._fail_payload()
            for session in ("a", "a", "b"):
                proc = subprocess.run([sys.executable, str(HOOK_DIR / "post_tool_use.py")], input=payload, text=True, capture_output=True,
                                      env=env_for(project, SUPREMETEAM_SESSION_ID=session), check=False)
            self.assertEqual(proc.stdout.strip(), "")
            files = list((project / ".harness-state" / "trajectories").rglob("*.json"))
            self.assertEqual(len(files), 2)


class FreezeRecordTests(unittest.TestCase):
    def _write_guard(self, project: Path, state: dict) -> None:
        (project / ".harness-state").mkdir(parents=True, exist_ok=True)
        (project / ".harness-state" / "guard-state.json").write_text(json.dumps(state), encoding="utf-8")

    def _edit(self, project: Path, path: str) -> str:
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(project / path)}})
        proc = subprocess.run([sys.executable, str(HOOK_DIR / "pre_tool_use.py")], input=payload, text=True, capture_output=True,
                              env=env_for(project), check=False)
        return proc.stdout

    def test_old_freeze_record_stays_effective_until_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._write_guard(project, {"frozen_globs": [{"glob": "src/payments/**", "owner": "ops", "scope": "release",
                                                          "created_at": "2000-01-01T00:00:00Z", "run_id": "old", "released_at": None}]})
            self.assertIn("deny", self._edit(project, "src/payments/a.py"))
            self._write_guard(project, {"frozen_globs": [{"glob": "src/payments/**", "owner": "ops", "released_at": "2026-09-05T00:00:00Z"}]})
            self.assertEqual(self._edit(project, "src/payments/a.py").strip(), "")

    def test_mixed_string_and_record_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self._write_guard(project, {"frozen_globs": ["infra/*.tf", {"glob": "src/payments/**", "owner": "ops"}]})
            self.assertIn("deny", self._edit(project, "infra/main.tf"))
            self.assertIn("deny", self._edit(project, "src/payments/a.py"))
            self.assertEqual(self._edit(project, "src/other/a.py").strip(), "")


class RepairRegistrationTests(unittest.TestCase):
    def _run(self, project: Path, home: Path, *args: str) -> tuple[int, str]:
        proc = subprocess.run([sys.executable, str(HOOK_DIR / "repair_registration.py"), *args], text=True, capture_output=True,
                              env=env_for(project, home), check=False)
        return proc.returncode, proc.stdout

    def _verify(self, project: Path, home: Path) -> int:
        proc = subprocess.run([sys.executable, str(HOOK_DIR / "verify_registration.py"), "--host", "claude"], text=True, capture_output=True,
                              env=env_for(project, home), check=False)
        return proc.returncode

    def test_dry_run_apply_preserve_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            project, home = Path(tmp), Path(home_tmp)
            settings = project / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(json.dumps({"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo unrelated"}]}]}}), encoding="utf-8")
            code, out = self._run(project, home, "--host", "claude", "--scope", "project")
            self.assertEqual(code, 1, out)
            self.assertIn("(proposed)", out)
            self.assertIn('"model": "opus"', settings.read_text(encoding="utf-8"))
            self.assertNotIn("pre_tool_use.py", settings.read_text(encoding="utf-8"))
            code, out = self._run(project, home, "--host", "claude", "--scope", "project", "--apply", "--python", sys.executable)
            self.assertEqual(code, 0, out)
            after = json.loads(settings.read_text(encoding="utf-8"))
            self.assertEqual(after["model"], "opus")
            commands = [h["command"] for g in after["hooks"]["PreToolUse"] for h in g["hooks"]]
            self.assertIn("echo unrelated", commands)
            self.assertTrue(list(settings.parent.glob("settings.json.bak-*")))
            self.assertEqual(self._verify(project, home), 0)
            self.assertFalse((home / ".claude" / "settings.json").exists(), "user scope must not be touched")
            code, out = self._run(project, home, "--host", "claude", "--scope", "project", "--apply", "--python", sys.executable)
            self.assertEqual(code, 0)
            self.assertIn("no changes", out)
            self.assertEqual(len(list(settings.parent.glob("settings.json.bak-*"))), 1)

    def test_refuses_to_overwrite_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            project, home = Path(tmp), Path(home_tmp)
            settings = project / ".claude" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text("{not json", encoding="utf-8")
            code, out = self._run(project, home, "--host", "claude", "--scope", "project", "--apply")
            self.assertEqual(code, 2)
            self.assertEqual(settings.read_text(encoding="utf-8"), "{not json")


class ReadinessCapabilityTests(unittest.TestCase):
    def test_capabilities_are_reported_independently(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as home_tmp:
            project, home = Path(tmp), Path(home_tmp)
            proc = subprocess.run([sys.executable, str(HOOK_DIR / "check_readiness.py"), "--host", "claude", "--project-root", str(project), "--json"],
                                  text=True, capture_output=True, env=env_for(project, home), check=False)
            data = json.loads(proc.stdout)
            self.assertEqual(data["hooks"]["status"], "unknown")
            caps = data["capabilities"]
            self.assertFalse(caps["hooks_executable"])
            self.assertEqual(caps["hooks_observed"], "unverified")
            self.assertTrue(caps["deterministic_validators"])
            self.assertIn("repair_registration.py", data["repair_hint"])


if __name__ == "__main__":
    unittest.main()
