#!/usr/bin/env python3
"""Save-writer hardening, hook-driven heartbeat, and widened action guards (2026-09-05, third pass).

Each case reproduced a gap against the previous writer or hook: a routine
checkpoint silently reopened a completed run, heartbeat/complete/release ignored
an interrupted journal, recover re-pinned a fresh lock of the same owner and
clobbered a journal, create succeeded beside a stale run (leaving both
conflicting), an attended run went stale between checkpoints, shell redirects
into core save files were not intercepted, and `rm -fr /` slipped past the
`-rf`-only guard.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
SAVE_RUN = HOOK_DIR / "save_run.py"


def run_save(project: Path, run_id: str, *args: str) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(SAVE_RUN), *args, "--project-root", str(project), "--run-id", run_id],
                          text=True, capture_output=True, check=False)
    text = (proc.stdout or proc.stderr).strip()
    try:
        payload = json.loads(text[text.index("{"):]) if "{" in text else {}
    except ValueError:
        payload = {"raw": text}
    return proc.returncode, payload


def fire(script: str, payload: dict, project: Path) -> str:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(project)
    proc = subprocess.run([sys.executable, str(HOOK_DIR / script)], input=json.dumps(payload), text=True,
                          capture_output=True, env=env, check=False)
    return proc.stdout


def lock_of(project: Path, run_id: str) -> dict:
    return json.loads((project / "skillset-saves" / "runs" / run_id / "_lock.md").read_text(encoding="utf-8"))


def backdate_lock(project: Path, run_id: str, minutes: int) -> None:
    lock = lock_of(project, run_id)
    lock["heartbeat"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    (project / "skillset-saves" / "runs" / run_id / "_lock.md").write_text(json.dumps(lock), encoding="utf-8")


class SaveWriterHardeningTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        (self.project / "README.md").write_text("# fixture\n", encoding="utf-8")

    def save(self, *args: str, run_id: str = "run-1") -> tuple[int, dict]:
        return run_save(self.project, run_id, *args)

    def test_create_rejects_parent_revision_override_before_writing(self):
        code, out = self.save("create", "--evidence", "README.md", "--set", "parent_revision=99")
        self.assertEqual(code, 1, out)
        self.assertIn("reserved field", out["reason"])
        self.assertFalse((self.project / "skillset-saves/runs/run-1/_state.md").exists())

    def test_checkpoint_on_completed_run_needs_reopen(self):
        self.save("create", "--evidence", "README.md")
        self.save("complete")
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("--reopen", out["reason"])
        code, out = self.save("checkpoint", "--reopen", "--next-action", "REVISE")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["operation"], "reopen")
        code, out = self.save("status")
        self.assertEqual(out["status"], "active", out)
        audit = [json.loads(line) for line in (self.project / "skillset-saves/runs/run-1/_audit-trail.md").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(audit[-1]["event"], "reopen")
        self.assertEqual(audit[-1]["from_status"], "complete")

    def test_released_run_resumes_by_checkpoint_unless_another_run_holds_the_pin(self):
        self.save("create", "--evidence", "README.md")
        code, out = self.save("release")
        self.assertEqual(code, 0, out)
        code, out = self.save("release")
        self.assertEqual(code, 1)
        self.assertIn("already released", out["reason"])
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 0, out)
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("another run holds the session pin", out["reason"])
        self.save("complete", run_id="run-2")
        code, out = self.save("checkpoint")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["operation"], "resume")

    def test_interrupted_journal_blocks_heartbeat_finish_and_plain_recover(self):
        self.save("create", "--evidence", "README.md")
        run_dir = self.project / "skillset-saves/runs/run-1"
        (run_dir / "_journal.json").write_text(json.dumps({"revision": 2, "step": "begin"}), encoding="utf-8")
        for op in (("heartbeat",), ("complete",), ("release",), ("recover", "--reason", "just because")):
            with self.subTest(op=op[0]):
                code, out = self.save(*op)
                self.assertEqual(code, 1, out)
                self.assertIn("rollback", out["reason"])
        self.assertTrue((run_dir / "_journal.json").exists(), "a refused operation must not consume the journal")

    def test_recover_refuses_a_fresh_lock_of_the_same_owner(self):
        self.save("create", "--evidence", "README.md")
        code, out = self.save("recover", "--reason", "impatient")
        self.assertEqual(code, 1, out)
        self.assertIn("held by this owner", out["reason"])
        lock = lock_of(self.project, "run-1")
        self.assertEqual(lock["revision"], 1)

    def test_create_refuses_beside_a_stale_held_run(self):
        self.save("create", "--evidence", "README.md")
        backdate_lock(self.project, "run-1", 45)
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 1, out)
        self.assertIn("stale", out["reason"])
        self.assertFalse((self.project / "skillset-saves/runs/run-2").exists())
        code, out = self.save("heartbeat")
        self.assertEqual(code, 1, out)
        self.assertIn("recover --reason", out["reason"])
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("stale", out["reason"])
        code, out = self.save("recover", "--reason", "heartbeat older than 30 minutes")
        self.assertEqual(code, 0, out)
        code, out = self.save("complete")
        self.assertEqual(code, 0, out)
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 0, out)

    def test_heartbeat_records_its_source(self):
        self.save("create", "--evidence", "README.md")
        code, out = self.save("heartbeat")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["source"], "cli")
        self.assertEqual(lock_of(self.project, "run-1")["heartbeat_source"], "cli")


class HookHeartbeatTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        (self.project / "README.md").write_text("# fixture\n", encoding="utf-8")
        run_save(self.project, "run-1", "create", "--evidence", "README.md")

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
        code, out = run_save(self.project, "run-1", "status")
        self.assertEqual(out["status"], "active", out)

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


class ActionGuardTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()

    def pre(self, tool: str, command: str) -> str:
        return fire("pre_tool_use.py", {"tool_name": tool, "tool_input": {"command": command}}, self.project)

    def test_recursive_root_wipes_are_denied_in_every_flag_spelling(self):
        for cmd in ("rm -rf /", "rm -fr /", "rm -Rf ~", "rm -r -f $HOME", "rm --recursive --force /*",
                    "cd /tmp && rm -rf *", "rm -rf build /", "rm -rf --no-preserve-root /",
                    "Remove-Item -Recurse -Force C:\\", "Remove-Item -Path / -Recurse", "rd /s /q C:\\", "format C:"):
            with self.subTest(cmd=cmd):
                tool = "PowerShell" if cmd[0].isupper() or cmd.startswith(("rd ", "format")) else "Bash"
                self.assertIn('"permissionDecision": "deny"', self.pre(tool, cmd))

    def test_scoped_deletes_stay_allowed(self):
        for cmd in ("rm -rf build/", "rm -rf ./dist node_modules", "rm -f /tmp/x.log", "rm -r src/old",
                    "Remove-Item -Recurse -Force .\\build", "Remove-Item -Recurse C:\\proj\\dist", "git rm -r cached/",
                    "python skills/harness/hooks/save_run.py status --run-id x"):
            with self.subTest(cmd=cmd):
                tool = "PowerShell" if cmd.startswith("Remove") else "Bash"
                self.assertEqual(self.pre(tool, cmd), "")

    def test_shell_writes_to_core_save_files_are_denied_but_reads_and_save_run_pass(self):
        denied = (
            'echo "{}" > skillset-saves/runs/r1/_state.md',
            "cp backup.json skillset-saves/_latest.md",
            "Set-Content skillset-saves\\runs\\r1\\_lock.md '{}'",
            "tee -a skillset-saves/runs/r1/_audit-trail.md < event.json",
            "rm skillset-saves/runs/r1/_journal.json",
            "mv old.json skillset-saves/runs/r1/_history/rev-1.state.json",
        )
        for cmd in denied:
            with self.subTest(cmd=cmd):
                tool = "PowerShell" if cmd.startswith("Set-Content") else "Bash"
                self.assertIn("save_run.py", self.pre(tool, cmd))
        allowed = (
            "cat skillset-saves/runs/r1/_state.md",
            "Get-Content skillset-saves/runs/r1/_lock.md",
            "python skills/harness/hooks/save_run.py checkpoint --run-id r1 --evidence skillset-saves/runs/r1/_state.md",
            "python skills/harness/hooks/save_run.py status --run-id r1 > skillset-saves/runs/r1/review/status.json",
            'echo "x" > skillset-saves/runs/r1/design/reports/report_plan.md',
        )
        for cmd in allowed:
            with self.subTest(cmd=cmd):
                tool = "PowerShell" if cmd.startswith("Get-Content") else "Bash"
                self.assertEqual(self.pre(tool, cmd), "")


class ReadOnlyRunTests(unittest.TestCase):
    """Rule D: an unreleased read_only record (explore pipeline) confines every write
    to the run's own save path and the harness state; save_run.py keeps working."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        self.run = "explore-1"
        self.allow = f"skillset-saves/runs/{self.run}/explore/**"

    def guard(self, released: bool = False) -> None:
        state = self.project / ".harness-state"
        state.mkdir(parents=True, exist_ok=True)
        record = {"run_id": self.run, "owner": "explore-lead", "scope": "explore read-only",
                  "created_at": "2026-09-05T10:00:00Z", "released_at": "2026-09-05T11:00:00Z" if released else None,
                  "allow": [self.allow]}
        (state / "guard-state.json").write_text(json.dumps({"read_only": [record], "frozen_globs": ["src/legacy/**"]}), encoding="utf-8")

    def write(self, path: str) -> str:
        return fire("pre_tool_use.py", {"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"}}, self.project)

    def bash(self, cmd: str) -> str:
        return fire("pre_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": cmd}}, self.project)

    def test_edit_tools_are_confined_to_the_run_save_path(self):
        self.guard()
        for path in ("src/app/main.py", str(self.project / "src" / "app" / "main.py"), "README.md", "docs/index.md",
                     f"skillset-saves/runs/{self.run}/design/reports/plan.md"):
            with self.subTest(path=path):
                self.assertIn("read-only (explore pipeline)", self.write(path))
        for path in (f"skillset-saves/runs/{self.run}/explore/reports/exploration-map.md",
                     str(self.project / "skillset-saves" / "runs" / self.run / "explore" / "reports" / "tickets" / "t1.md"),
                     ".harness-state/guard-state.json"):
            with self.subTest(path=path):
                self.assertEqual(self.write(path), "")

    def test_mutating_shell_commands_need_an_allowed_path_but_reads_and_save_run_pass(self):
        self.guard()
        for cmd in ("echo x > src/app/main.py", "git add -A", "sed -i 's/a/b/' README.md", "touch notes.md",
                    "rm -rf build/"):
            with self.subTest(cmd=cmd):
                self.assertIn("read-only (explore pipeline)", self.bash(cmd))
        for cmd in (f"mkdir -p skillset-saves/runs/{self.run}/explore/reports/tickets",
                    f"git status --porcelain > skillset-saves/runs/{self.run}/explore/evidence/read-only-attestation.log",
                    f"python skills/harness/hooks/save_run.py checkpoint --run-id {self.run} --expect-revision 2",
                    "cat src/app/main.py", "grep -rn TODO src/", "git log --oneline -50",
                    "python skills/scripts/check_runtime.py --project-root . --detect-project"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), "")

    def test_released_record_is_inert_and_freeze_still_applies(self):
        self.guard(released=True)
        self.assertEqual(self.write("src/app/main.py"), "")
        self.assertIn("frozen boundary", self.write("src/legacy/old.py"))

    def test_malformed_guard_state_fails_open(self):
        state = self.project / ".harness-state"
        state.mkdir(parents=True, exist_ok=True)
        (state / "guard-state.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.write("src/app/main.py"), "")


if __name__ == "__main__":
    unittest.main()
