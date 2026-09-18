#!/usr/bin/env python3
"""Regression tests for Supreme Team runtime harness hooks."""

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))


HOOK_DIR = Path(__file__).resolve().parent
import _state  # noqa: E402  (HOOK_DIR is on sys.path)

# Test scratch lives under the project's .harness-state/, one of the two
# sanctioned generated roots (save-ownership.yaml generated_roots).
_DEFAULT_TMP_ROOT = _state.project_root() / ".harness-state" / "test-work"
TEST_TMP_ROOT = Path(os.environ.get("SUPREMETEAM_HOOK_TEST_TMP", _DEFAULT_TMP_ROOT))


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
    """Write a canonical save fixture while keeping the call sites readable."""
    saves = project_dir / "skillset-saves"
    run_dir = saves / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    state_name = next((line.split(":", 1)[1].strip() for line in state_body.splitlines() if line.lower().startswith("state:")), "DESIGN_ACTIVE")
    pin_text = next((line.split(":", 1)[1].strip().lower() for line in state_body.splitlines() if line.lower().startswith("session_pin:")), "true")
    pin = pin_text == "true"
    terminal = state_name.upper() in {"DELIVERED", "RUN_COMPLETE"}
    status = "complete" if terminal else "active"
    if terminal:
        pin = False
    timestamp = datetime.now(timezone.utc).isoformat()
    canonical = (
        "schema_version: 1\n"
        f"run_id: {run_id}\n"
        f"status: {status}\n"
        f"session_pin: {'true' if pin else 'false'}\n"
        "execution_mode: test\n"
        "active_owner: test\n"
        "evidence_paths:\n"
        "  - skillset-saves\n"
        f"revision: 1\n"
        f"timestamp: {timestamp}\n"
    )
    (run_dir / "_state.md").write_text(canonical, encoding="utf-8")
    (run_dir / "_lock.md").write_text(
        "schema_version: 1\n"
        f"run_id: {run_id}\n"
        "owner: test\n"
        f"status: {'released' if status == 'complete' else 'held'}\n"
        f"session_pin: {'true' if pin else 'false'}\n"
        f"heartbeat: {timestamp}\n"
        "revision: 1\n",
        encoding="utf-8",
    )
    if latest:
        (saves / "_latest.md").write_text(
            f"schema_version: 1\nrun_id: {run_id}\nrevision: 1\nupdated_at: {timestamp}\n",
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

    def test_frozen_relative_glob_blocks_edit_of_absolute_windows_path(self):
        # Hosts report absolute target paths; a relative frozen glob must still catch them.
        with _project_dir() as project:
            _write_guard(project, {"frozen_globs": ["src/payments/**"]})
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "Edit", "tool_input": {"file_path": "D:\\proj\\src\\payments\\charge.py"}},
                project,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn('"permissionDecision": "deny"', result.stdout)

    def test_frozen_relative_glob_blocks_write_of_absolute_path(self):
        with _project_dir() as project:
            _write_guard(project, {"frozen_globs": ["src/payments/**"]})
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "Write", "tool_input": {"file_path": "D:/proj/src/payments/charge.py"}},
                project,
            )
        self.assertIn('"permissionDecision": "deny"', result.stdout)

    def test_read_only_command_on_absolute_frozen_path_still_allowed(self):
        with _project_dir() as project:
            _write_guard(project, {"frozen_globs": ["src/payments/**"]})
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "PowerShell", "tool_input": {"command": "Get-Content D:\\proj\\src\\payments\\charge.py"}},
                project,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_absolute_path_outside_frozen_glob_is_allowed(self):
        with _project_dir() as project:
            _write_guard(project, {"frozen_globs": ["src/payments/**"]})
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "Edit", "tool_input": {"file_path": "D:\\proj\\src\\billing\\charge.py"}},
                project,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

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


def _drop_residue(project: Path) -> None:
    """Reproduce the observed explosion in miniature: parallel-mode fragments, a
    `.coverage/` tree with nested files, and an HTML report at the project root."""
    for index in range(12):
        (project / f".coverage.host.4242.{index:03d}x").write_text(f"fragment-{index}", encoding="utf-8")
    nested = project / ".coverage" / "nested"
    nested.mkdir(parents=True, exist_ok=True)
    (nested / "a.json").write_text("{}", encoding="utf-8")
    (project / ".coverage" / "top.json").write_text("{}", encoding="utf-8")
    html = project / "htmlcov"
    html.mkdir(exist_ok=True)
    (html / "index.html").write_text("<html></html>", encoding="utf-8")
    nyc = project / ".nyc_output"
    nyc.mkdir(exist_ok=True)
    (nyc / "out.json").write_text("{}", encoding="utf-8")


def _residue_names(project: Path) -> list:
    return sorted(p.name for p in project.iterdir() if p.name == ".coverage"
                  or p.name.startswith(".coverage.") or p.name in ("htmlcov", ".nyc_output"))


def _bash(command: str = "python -m pytest --cov") -> dict:
    return {"session_id": "sweep", "tool_name": "Bash", "tool_input": {"command": command},
            "tool_response": {"stdout": "ok", "exit_code": 0}}


class CoverageResidueSweepTests(unittest.TestCase):
    """Coverage data is run evidence; the project root is never where it lives.

    The observed failure was a `.coverage` tree of over 3000 files appearing at a
    target project's root in under two minutes — parallel/per-process coverage
    with nothing combining or relocating the fragments. The prose rule stops it
    being created; this sweep is the mechanical backstop that repairs it on the
    next tool call.
    """

    def _context(self, result) -> str:
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip(), "sweep produced no envelope")
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]

    def test_residue_moves_into_the_active_run_keeping_relative_structure(self):
        with _project_dir() as project:
            _write_run_state(project, "2026-09-17_sweep_a1b2c3", "state: BUILD_ACTIVE\n")
            _drop_residue(project)
            result = _run_hook("post_tool_use.py", _bash(), project)
            context = self._context(result)
            dest = project / "skillset-saves" / "runs" / "2026-09-17_sweep_a1b2c3" / "build" / "evidence" / "coverage"
            self.assertEqual(_residue_names(project), [], "project root still holds coverage residue")
            self.assertTrue(dest.is_dir(), context)
            self.assertEqual(len(list(dest.glob(".coverage.host.4242.*"))), 12)
            # Relative structure survives the move.
            self.assertEqual((dest / ".coverage" / "nested" / "a.json").read_text(encoding="utf-8"), "{}")
            self.assertEqual((dest / "htmlcov" / "index.html").read_text(encoding="utf-8"), "<html></html>")
            self.assertEqual((dest / ".nyc_output" / "out.json").read_text(encoding="utf-8"), "{}")
            # Nothing is deleted: every fragment's bytes are still readable.
            self.assertEqual((dest / ".coverage.host.4242.000x").read_text(encoding="utf-8"), "fragment-0")
        self.assertIn("build/evidence/coverage", context)
        self.assertIn("Nothing was deleted", context)
        self.assertIn("COVERAGE_FILE", context)
        self.assertIn("never run coverage in parallel", context.lower())

    def test_the_sweep_is_bounded_per_call(self):
        """Bounded work is a doctrine requirement, not an optimisation: the hook
        runs on every command action and must never walk an unbounded tree."""
        import post_tool_use

        self.assertEqual(post_tool_use._RESIDUE_CAP, 5000)

    def test_recorded_phase_state_selects_the_run_phase(self):
        with _project_dir() as project:
            _write_run_state(project, "phase-run", "state: QA_ACTIVE\n")
            state = project / "skillset-saves" / "runs" / "phase-run" / "_state.md"
            state.write_text(state.read_text(encoding="utf-8") + "phase_state: QA_GATE_PENDING\n", encoding="utf-8")
            _drop_residue(project)
            context = self._context(_run_hook("post_tool_use.py", _bash(), project))
            self.assertTrue((project / "skillset-saves" / "runs" / "phase-run" / "qa" / "evidence" / "coverage").is_dir())
        self.assertIn("qa/evidence/coverage", context)

    def test_unrecognised_phase_state_falls_back_to_build(self):
        with _project_dir() as project:
            _write_run_state(project, "dispute-run", "state: DESIGN_ACTIVE\n")
            state = project / "skillset-saves" / "runs" / "dispute-run" / "_state.md"
            state.write_text(state.read_text(encoding="utf-8") + "phase_state: DISPUTED_AWAITING_USER\n", encoding="utf-8")
            _drop_residue(project)
            self._context(_run_hook("post_tool_use.py", _bash(), project))
            self.assertTrue((project / "skillset-saves" / "runs" / "dispute-run" / "build" / "evidence" / "coverage").is_dir())

    def test_without_an_active_run_residue_goes_to_the_declared_scratch_class(self):
        with _project_dir() as project:
            _drop_residue(project)
            context = self._context(_run_hook("post_tool_use.py", _bash(), project))
            scratch = project / ".harness-state" / "test-work" / "coverage-residue"
            self.assertEqual(_residue_names(project), [])
            stamps = list(scratch.iterdir())
            self.assertEqual(len(stamps), 1, stamps)
            self.assertEqual(len(list(stamps[0].glob(".coverage.host.4242.*"))), 12)
        self.assertIn("coverage-residue", context)
        self.assertIn("No active run", context)

    def test_frozen_boundary_entries_are_never_moved(self):
        with _project_dir() as project:
            _write_guard(project, {"frozen_globs": ["htmlcov/**"], "blocked_globs": [".nyc_output/**"]})
            _write_run_state(project, "frozen-run", "state: BUILD_ACTIVE\n")
            _drop_residue(project)
            context = self._context(_run_hook("post_tool_use.py", _bash(), project))
            dest = project / "skillset-saves" / "runs" / "frozen-run" / "build" / "evidence" / "coverage"
            self.assertEqual(_residue_names(project), [".nyc_output", "htmlcov"])
            self.assertTrue((project / "htmlcov" / "index.html").is_file())
            self.assertFalse((dest / "htmlcov").exists())
            self.assertFalse((dest / ".nyc_output").exists())
            self.assertEqual(len(list(dest.glob(".coverage.host.4242.*"))), 12)
        self.assertIn("frozen or blocked boundary", context)

    def test_non_command_tools_sweep_nothing(self):
        with _project_dir() as project:
            _write_run_state(project, "edit-run", "state: BUILD_ACTIVE\n")
            _drop_residue(project)
            before = _residue_names(project)
            result = _run_hook(
                "post_tool_use.py",
                {"session_id": "edit", "tool_name": "Edit",
                 "tool_input": {"file_path": "src/app.py", "new_string": "x"},
                 "tool_response": {"stdout": "ok", "exit_code": 0}},
                project,
            )
            self.assertEqual(result.stdout, "")
            self.assertEqual(_residue_names(project), before)

    def test_clean_root_stays_silent(self):
        with _project_dir() as project:
            _write_run_state(project, "clean-run", "state: BUILD_ACTIVE\n")
            result = _run_hook("post_tool_use.py", _bash("python -m unittest discover"), project)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_generated_roots_are_the_destination_not_the_residue(self):
        with _project_dir() as project:
            _write_run_state(project, "roots-run", "state: BUILD_ACTIVE\n")
            _drop_residue(project)
            _run_hook("post_tool_use.py", _bash(), project)
            self.assertTrue((project / "skillset-saves" / "_latest.md").is_file())
            self.assertTrue((project / "skillset-saves" / "runs" / "roots-run" / "_state.md").is_file())
            self.assertTrue((project / ".harness-state").is_dir())

    def test_a_trajectory_hint_carries_the_sweep_report_rather_than_hiding_it(self):
        with _project_dir() as project:
            _write_run_state(project, "both-run", "state: BUILD_ACTIVE\n")
            payload = {"session_id": "both", "tool_name": "Bash",
                       "tool_input": {"command": "coverage run -p -m pytest"},
                       "tool_response": {"stderr": "No such file or directory"}}
            _run_hook("post_tool_use.py", payload, project)
            _run_hook("post_tool_use.py", payload, project)
            _drop_residue(project)
            context = self._context(_run_hook("post_tool_use.py", payload, project))
        self.assertIn("same input", context)
        self.assertIn("[harness:coverage-residue]", context)


class PreToolCoverageAdvisoryTests(unittest.TestCase):
    """Advisory context, never a deny: running coverage is legitimate; leaving its
    output at the project root is the defect, and it is still correctable here."""

    def _advice(self, command: str, project: Path) -> str:
        result = _run_hook("pre_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": command}}, project)
        self.assertEqual(result.returncode, 0)
        if not result.stdout.strip():
            return ""
        payload = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", payload, "the advisory must never deny")
        return payload["additionalContext"]

    def test_parallel_and_unrouted_coverage_commands_are_advised(self):
        cases = (
            "coverage run -p -m pytest tests/",
            "coverage run --parallel-mode -m unittest discover",
            "python -m pytest --cov=app tests/",
            "npx nyc mocha",
            "npx c8 node --test",
            "npx vitest run --coverage",
        )
        with _project_dir() as project:
            for command in cases:
                with self.subTest(command=command):
                    advice = self._advice(command, project)
                    self.assertIn("output_paths.py", advice)
                    self.assertIn("evidence/coverage", advice)

    def test_commands_that_name_a_destination_stay_silent(self):
        cases = (
            "coverage run -p -m pytest && coverage combine --data-file=skillset-saves/runs/r/build/evidence/coverage/.coverage",
            "python -m pytest --cov=app --cov-report=xml:skillset-saves/runs/r/build/evidence/coverage/cov.xml",
            "npx nyc --report-dir=skillset-saves/runs/r/qa/evidence/coverage --temp-dir=skillset-saves/runs/r/qa/evidence/coverage/tmp mocha",
            "npx vitest run --coverage --coverage.reportsDirectory=skillset-saves/runs/r/qa/evidence/coverage",
            "coverage run -m pytest tests/",
            "python -m unittest discover -s tests",
            "git status --porcelain",
        )
        with _project_dir() as project:
            for command in cases:
                with self.subTest(command=command):
                    self.assertEqual(self._advice(command, project), "")

    def test_a_denied_command_is_still_denied_not_advised(self):
        with _project_dir() as project:
            result = _run_hook(
                "pre_tool_use.py",
                {"tool_name": "Bash", "tool_input": {"command": "rm -rf / && coverage run -p -m pytest"}},
                project,
            )
        self.assertIn('"permissionDecision": "deny"', result.stdout)


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
        self.assertIn("`admiral`", self._ctx(result))

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
        self.assertIn("a run is active", self._ctx(result))

    def test_delivered_run_is_not_active(self):
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-08_dark-mode_a3f9k2",
                "---\nstate: DELIVERED\nsession_pin: true\n---\n",
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "what next"}, project)
        self.assertIn("no active run", self._ctx(result))

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
        self.assertIn("a run is active", self._ctx(result))

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
        self.assertIn("a run is active", self._ctx(result))

    def test_disputed_awaiting_user_is_active(self):
        # DISPUTED_AWAITING_USER is non-terminal: the run still owns the session.
        with _project_dir() as project:
            _write_run_state(
                project,
                "2026-06-08_dispute_c1d2e3",
                "---\nstate: DISPUTED_AWAITING_USER\nsession_pin: true\n---\n",
            )
            result = _run_hook("user_prompt_submit.py", {"prompt": "here is my call"}, project)
        self.assertIn("a run is active", self._ctx(result))

    def test_legacy_flat_state_is_not_treated_as_active(self):
        # Schema-invalid legacy state must not reinforce a session pin.
        with _project_dir() as project:
            saves = project / "skillset-saves"
            saves.mkdir(parents=True, exist_ok=True)
            (saves / "_state.md").write_text("state: DESIGN_ACTIVE\nsession_pin: true\n", encoding="utf-8")
            result = _run_hook("user_prompt_submit.py", {"prompt": "add dark mode too"}, project)
        self.assertIn("no active run", self._ctx(result))

    def test_stale_lock_does_not_reinforce_session_pin(self):
        with _project_dir() as project:
            _write_run_state(project, "stale", "state: DESIGN_ACTIVE\n")
            lock = project / "skillset-saves" / "runs" / "stale" / "_lock.md"
            lock.write_text(lock.read_text(encoding="utf-8").replace("heartbeat:", "heartbeat: 2020-01-01T00:00:00Z\n#"), encoding="utf-8")
            result = _run_hook("user_prompt_submit.py", {"prompt": "continue"}, project)
        self.assertIn("no active run", self._ctx(result))

    def test_conflicting_active_runs_do_not_reinforce_session_pin(self):
        with _project_dir() as project:
            _write_run_state(project, "one", "state: DESIGN_ACTIVE\n")
            _write_run_state(project, "two", "state: DESIGN_ACTIVE\n", latest=False)
            result = _run_hook("user_prompt_submit.py", {"prompt": "continue"}, project)
        self.assertIn("no active run", self._ctx(result))

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

    def _run(self, project: Path, home: Path, host: str = "claude", env_extra=None) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project)
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)  # Path.home() uses USERPROFILE on Windows
        env.update(env_extra or {})
        command = [sys.executable, str(HOOK_DIR / "verify_registration.py"), "--host", host]
        return subprocess.run(
            command,
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
        self.assertIn("skills/harness/hooks/", result.stdout)
        self.assertNotIn("skills/admiral/harness/hooks/", result.stdout)

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
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python /tmp/other/skills/harness/hooks/pre_tool_use.py"}]}],
                "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "python /tmp/other/skills/harness/hooks/post_tool_use.py"}]}],
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "python /tmp/other/skills/harness/hooks/user_prompt_submit.py"}]}],
            }
        }
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, unrelated)
            result = self._run(project, home)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("status: MISSING", result.stdout)

    def test_supremeteam_named_lookalike_paths_are_rejected(self):
        for root in (r"C:\unrelated\admiral-hooks", r"C:\other\skills\Supreme Team\harness\hooks"):
            block = {
                "hooks": {
                    "PreToolUse": [{"hooks": [{"command": f"python {root}\\pre_tool_use.py"}]}],
                    "PostToolUse": [{"hooks": [{"command": f"python {root}\\post_tool_use.py"}]}],
                    "UserPromptSubmit": [{"hooks": [{"command": f"python {root}\\user_prompt_submit.py"}]}],
                }
            }
            with self.subTest(root=root), _project_dir() as project, _project_dir() as home:
                self._write_settings(project, block)
                result = self._run(project, home)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("status: MISSING", result.stdout)

    def test_explicit_supremeteam_hook_root_is_accepted(self):
        with _project_dir() as project, _project_dir() as home, _project_dir() as explicit:
            # The explicit root must hold real script files: a configured path
            # that does not exist is "configured" but never "registered".
            for name in ("pre_tool_use.py", "post_tool_use.py", "user_prompt_submit.py"):
                (explicit / name).write_text("# relocated hook\n", encoding="utf-8")
            block = {
                "hooks": {
                    "PreToolUse": [{"hooks": [{"command": f"python {explicit / 'pre_tool_use.py'}"}]}],
                    "PostToolUse": [{"hooks": [{"command": f"python {explicit / 'post_tool_use.py'}"}]}],
                    "UserPromptSubmit": [{"hooks": [{"command": f"python {explicit / 'user_prompt_submit.py'}"}]}],
                }
            }
            self._write_settings(project, block)
            result = self._run(project, home, env_extra={"SUPREMETEAM_HOOK_ROOT": str(explicit)})
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("status: REGISTERED", result.stdout)

    def test_real_path_suffix_reference_and_note_are_rejected(self):
        real = HOOK_DIR / "pre_tool_use.py"
        cases = (
            f'python "{real}.bak"',
            f'echo "{real}"',
            f'python C:\\wrapper.py --note="{real}"',
        )
        for command in cases:
            block = {
                "hooks": {
                    "PreToolUse": [{"hooks": [{"command": command}]}],
                    "PostToolUse": self._BLOCK["hooks"]["PostToolUse"],
                    "UserPromptSubmit": self._BLOCK["hooks"]["UserPromptSubmit"],
                }
            }
            with self.subTest(command=command), _project_dir() as project, _project_dir() as home:
                self._write_settings(project, block)
                result = self._run(project, home)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("[MISSING] PreToolUse", result.stdout)

    def test_all_requires_every_declared_host(self):
        with _project_dir() as project, _project_dir() as home:
            self._write_settings(project, self._BLOCK)
            result = self._run(project, home, host="all")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("[codex]", result.stdout)
        self.assertIn("[claude]", result.stdout)
        self.assertIn("[copilot]", result.stdout)

    def test_copilot_native_config_is_detected(self):
        with _project_dir() as project, _project_dir() as home:
            config = project / ".github" / "hooks.json"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps(self._BLOCK), encoding="utf-8")
            result = self._run(project, home, host="copilot")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("status: REGISTERED", result.stdout)


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
            result = self._run(project, home, "--require-active-run", "--min-python", f"{sys.version_info.major}.{sys.version_info.minor}")
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
