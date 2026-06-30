#!/usr/bin/env python3
"""Regression tests for SupremeTeam runtime harness hooks."""

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path


HOOK_DIR = Path(__file__).resolve().parent
_DEFAULT_TMP_ROOT = Path.cwd() / "harness-test-work"
TEST_TMP_ROOT = Path(os.environ.get("SUPREME_HOOK_TEST_TMP", _DEFAULT_TMP_ROOT))


@contextmanager
def _project_dir():
    TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)
    project = TEST_TMP_ROOT / f"case-{uuid.uuid4().hex}"
    project.mkdir(parents=True, exist_ok=False)
    try:
        yield project
    finally:
        shutil.rmtree(project, ignore_errors=True)
        try:
            TEST_TMP_ROOT.rmdir()
        except OSError:
            pass


def _run_hook(script: str, payload, project_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK_DIR / script)],
        input=raw,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _write_guard(project_dir: Path, state: dict) -> None:
    state_dir = project_dir / ".harness-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "guard-state.json").write_text(json.dumps(state), encoding="utf-8")


def _write_run_state(project_dir: Path, run_id: str, state_body: str, *, latest: bool = True) -> None:
    """Write the documented save layout (save-protocol.md sections 1-2).

    The mutable run state lives at ``skillset-saves/runs/{run-id}/_state.md`` and
    is the only file carrying ``session_pin``; root ``_latest.md`` is a pointer.
    Pass ``latest=False`` to simulate a lost/never-written pointer (orphaned run).
    """
    saves = project_dir / "skillset-saves"
    run_dir = saves / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "_state.md").write_text(state_body, encoding="utf-8")
    if latest:
        (saves / "_latest.md").write_text(
            f"---\nlatest_run_id: {run_id}\nupdated_at: 2026-06-08T12:00:00Z\n---\n",
            encoding="utf-8",
        )


class PreToolUseTests(unittest.TestCase):
    def test_blocks_literal_dangerous_shell_command(self):
        with _project_dir() as project:
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
                project,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('"permissionDecision": "deny"', result.stdout)

    def test_allow_dangerous_flag_keeps_hook_inert(self):
        with _project_dir() as project:
            _write_guard(project, {"allow_dangerous": True})
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}},
                project,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_frozen_boundary_blocks_writes_but_not_reads(self):
        with _project_dir() as project:
            _write_guard(project, {"frozen_globs": ["src/payments/**"]})
            read_result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "PowerShell", "tool_input": {"command": "Get-Content src/payments/file.txt"}},
                project,
            )
            write_result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "PowerShell", "tool_input": {"command": "Set-Content src/payments/file.txt x"}},
                project,
            )
        self.assertEqual(read_result.stdout, "")
        self.assertIn('"permissionDecision": "deny"', write_result.stdout)

    def test_leading_wildcard_blocked_glob_matches_shell_path(self):
        with _project_dir() as project:
            _write_guard(project, {"blocked_globs": ["**/secrets/**"]})
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "PowerShell", "tool_input": {"command": "Set-Content app/secrets/token.txt x"}},
                project,
            )
        self.assertIn('"permissionDecision": "deny"', result.stdout)

    def test_malformed_json_fails_open(self):
        with _project_dir() as project:
            result = _run_hook("pre_tool_use.py", "{", project)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class PostToolUseTests(unittest.TestCase):
    def test_repeated_failing_command_emits_recovery_hint(self):
        with _project_dir() as project:
            payload = {
                "session_id": "repeat",
                "tool_name": "Bash",
                "tool_input": {"command": "ls /nope"},
                "tool_response": {"stderr": "No such file or directory"},
            }
            _run_hook("post_tool_use.py", payload, project)
            _run_hook("post_tool_use.py", payload, project)
            result = _run_hook("post_tool_use.py", payload, project)
        self.assertIn("same input", result.stdout)

    def test_empty_output_streak_emits_recovery_hint(self):
        with _project_dir() as project:
            for i in range(2):
                _run_hook(
                    "post_tool_use.py",
                    {
                        "session_id": "empty",
                        "tool_name": "Bash",
                        "tool_input": {"command": f"true {i}"},
                        "tool_response": {"stdout": "", "stderr": "", "exit_code": 0},
                    },
                    project,
                )
            result = _run_hook(
                "post_tool_use.py",
                {
                    "session_id": "empty",
                    "tool_name": "Bash",
                    "tool_input": {"command": "true 2"},
                    "tool_response": {"stdout": "", "stderr": "", "exit_code": 0},
                },
                project,
            )
        self.assertIn("empty output", result.stdout)

    def test_nonprogressing_oscillation_emits_recovery_hint(self):
        with _project_dir() as project:
            for command in ("cat missing-a", "cat missing-b", "cat missing-a"):
                _run_hook(
                    "post_tool_use.py",
                    {
                        "session_id": "osc",
                        "tool_name": "Bash",
                        "tool_input": {"command": command},
                        "tool_response": {"stderr": "No such file or directory"},
                    },
                    project,
                )
            result = _run_hook(
                "post_tool_use.py",
                {
                    "session_id": "osc",
                    "tool_name": "Bash",
                    "tool_input": {"command": "cat missing-b"},
                    "tool_response": {"stderr": "No such file or directory"},
                },
                project,
            )
        self.assertIn("oscillating", result.stdout)


class UserPromptSubmitTests(unittest.TestCase):
    def _ctx(self, result) -> str:
        self.assertEqual(result.returncode, 0)
        if not result.stdout.strip():
            return ""
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_natural_language_injects_route_reminder(self):
        with _project_dir() as project:
            result = _run_hook("user_prompt_submit.py", {"prompt": "design this system"}, project)
        self.assertIn("primary entry orchestrator", self._ctx(result))

    def test_slash_command_stays_silent(self):
        with _project_dir() as project:
            result = _run_hook("user_prompt_submit.py", {"prompt": "/freeze src/payments"}, project)
        self.assertEqual(result.stdout, "")

    def test_empty_prompt_stays_silent(self):
        with _project_dir() as project:
            result = _run_hook("user_prompt_submit.py", {"prompt": "   "}, project)
        self.assertEqual(result.stdout, "")

    def test_active_run_reinforces_session_pin(self):
        # Documented layout: root _latest.md pointer -> runs/{id}/_state.md.
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-08_dark-mode_a3f9k2",
                "---\nstate: DESIGN_ACTIVE\nsession_pin: true\n---\n",
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "add dark mode too"}, project)
        self.assertIn("an Admiral run is active", self._ctx(result))

    def test_delivered_run_is_not_active(self):
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-08_dark-mode_a3f9k2",
                "---\nstate: DELIVERED\nsession_pin: true\n---\n",
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "what next"}, project)
        self.assertIn("no active Admiral run", self._ctx(result))

    def test_orphaned_run_without_latest_pointer_is_active(self):
        # _latest.md lost/never written, but an active pinned run remains under runs/.
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-08_orphan_b7c2e1",
                "---\nstate: BUILD_ACTIVE\nsession_pin: true\n---\n",
                latest=False,
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "keep going"}, project)
        self.assertIn("an Admiral run is active", self._ctx(result))

    def test_stale_latest_pointer_falls_back_to_scan(self):
        # _latest.md points at a delivered run, but a different run is still active.
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-07_done_aaaaaa",
                "---\nstate: DELIVERED\nsession_pin: false\n---\n",
            )
            _write_run_state(
                project,
                "2026-06-08_live_bbbbbb",
                "---\nstate: REVIEW_ACTIVE\nsession_pin: true\n---\n",
                latest=False,
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "next"}, project)
        self.assertIn("an Admiral run is active", self._ctx(result))

    def test_disputed_awaiting_user_is_active(self):
        # DISPUTED_AWAITING_USER is non-terminal: the run still owns the session.
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-08_dispute_c1d2e3",
                "---\nstate: DISPUTED_AWAITING_USER\nsession_pin: true\n---\n",
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "here is my call"}, project)
        self.assertIn("an Admiral run is active", self._ctx(result))

    def test_legacy_flat_state_still_detected(self):
        # Defensive: a flat root _state.md (non-documented) is still honored.
        with _project_dir() as project:
            saves = project / "skillset-saves"
            saves.mkdir(parents=True, exist_ok=True)
            (saves / "_state.md").write_text("state: DESIGN_ACTIVE\nsession_pin: true\n", encoding="utf-8")
            result = _run_hook("user_prompt_submit.py", {"prompt": "add dark mode too"}, project)
        self.assertIn("an Admiral run is active", self._ctx(result))

    def test_malformed_json_fails_open(self):
        with _project_dir() as project:
            result = _run_hook("user_prompt_submit.py", "{", project)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class VerifyRegistrationTests(unittest.TestCase):
    _BLOCK = {
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": f"python {HOOK_DIR / 'pre_tool_use.py'}"}]}],
            "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": f"python {HOOK_DIR / 'post_tool_use.py'}"}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": f"python {HOOK_DIR / 'user_prompt_submit.py'}"}]}],
        }
    }

    def _run(self, project: Path, home: Path, host: str = "claude") -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project)
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)  # Path.home() uses USERPROFILE on Windows
        return subprocess.run(
            [sys.executable, str(HOOK_DIR / "verify_registration.py"), "--host", host],
            input="{}", text=True, capture_output=True, env=env, check=False,
        )

    def _write_settings(self, project: Path, obj) -> None:
        d = project / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps(obj), encoding="utf-8")

    def test_all_registered_exits_zero(self):
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, self._BLOCK)
            result = self._run(project, home)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("status: REGISTERED", result.stdout)

    def test_missing_exits_one_and_prompts(self):
        # A readable settings file that simply lacks the hooks -> MISSING (exit 1).
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, {"model": "opus"})
            result = self._run(project, home)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("REGISTER_PROMPT", result.stdout)
        self.assertIn("status: MISSING", result.stdout)

    def test_no_settings_anywhere_is_unknown(self):
        # No readable settings file at all -> UNKNOWN (exit 2); still prompts.
        with _project_dir() as project, _project_dir() as home:
            result = self._run(project, home)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("status: UNKNOWN", result.stdout)

    def test_partial_registration_is_missing(self):
        partial = {"hooks": {"PreToolUse": self._BLOCK["hooks"]["PreToolUse"]}}
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, partial)
            result = self._run(project, home)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[OK ] PreToolUse", result.stdout)
        self.assertIn("[MISSING] UserPromptSubmit", result.stdout)

    def test_same_basename_from_unrelated_package_is_missing(self):
        unrelated = {
            "hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python /tmp/critlabs-suite/harness/hooks/pre_tool_use.py"}]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python /tmp/critlabs-suite/harness/hooks/post_tool_use.py"}]}],
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python /tmp/critlabs-suite/harness/hooks/user_prompt_submit.py"}]}],
            }
        }
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, unrelated)
            result = self._run(project, home)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("status: MISSING", result.stdout)


class CheckReadinessTests(unittest.TestCase):
    _BLOCK = VerifyRegistrationTests._BLOCK

    def _run(self, project: Path, home: Path, *extra: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project)
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
        return subprocess.run(
            [sys.executable, str(HOOK_DIR / "check_readiness.py"), "--host", "claude", "--project-root", str(project), *extra],
            input="{}", text=True, capture_output=True, env=env, check=False,
        )

    def _write_settings(self, project: Path, obj) -> None:
        d = project / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps(obj), encoding="utf-8")

    def test_ready_when_python_hooks_and_active_run_exist(self):
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, self._BLOCK)
            _write_run_state(
                project,
                "2026-06-08_active_ready",
                "---\nstate: DESIGN_ACTIVE\nsession_pin: true\n---\n",
            )
            result = self._run(project, home, "--require-active-run")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Python: ok", result.stdout)
        self.assertIn("Hooks: registered", result.stdout)
        self.assertIn("Saves: active", result.stdout)
        self.assertIn("Ready: yes", result.stdout)

    def test_require_active_run_fails_when_saves_are_inactive(self):
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, self._BLOCK)
            _write_run_state(
                project,
                "2026-06-08_done",
                "---\nstate: DELIVERED\nsession_pin: false\n---\n",
            )
            result = self._run(project, home, "--require-active-run")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Hooks: registered", result.stdout)
        self.assertIn("Saves: inactive", result.stdout)
        self.assertIn("Ready: no", result.stdout)

    def test_json_output_reports_missing_hooks(self):
        with _project_dir() as project, _project_dir() as home:
            result = self._run(project, home, "--json")
        self.assertEqual(result.returncode, 1, result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["hooks"]["status"], "unknown")
        self.assertEqual(data["saves"]["status"], "missing")


if __name__ == "__main__":
    unittest.main()
