#!/usr/bin/env python3
"""GitHub Copilot: where its hooks are registered, in what shape, and how the hooks answer it (WP-08).

The registrar wrote Copilot's hooks to ``~/.config/github-copilot/hooks.json`` and ``.github/hooks.json``, in the
nested shape Claude Code reads, and the guard answered under ``hookSpecificOutput``. Copilot reads ``*.json`` inside
``~/.copilot/hooks/`` (``$COPILOT_HOME/hooks/``) and ``.github/hooks/``, as ``{"version": 1, "hooks": {event:
[handler, ...]}}`` with the command in a ``bash`` or ``powershell`` field, and documents the decision and the context
at the top level of the answer. So the hooks were never started there, and would not have been understood.

Two things about that host shape every rule here. A pre-tool hook that exits with anything but 0 denies the tool
call, so a command is written only after it has been started. And Copilot drops what a command hook prints for a
prompt, so the routing reminder is registered on the start of the session.

None of this was run in a Copilot session: Copilot CLI is not installed where these tests were written. They hold
the code to Copilot's hooks reference.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _testkit as kit
import repair_registration as repair
import verify_registration as verify

HOOK_DIR = Path(__file__).resolve().parent
INSTALLER = HOOK_DIR.parents[2] / "scripts" / "install_hooks.py"
FIELD = verify.command_field()
OTHER_FIELD = "bash" if FIELD == "powershell" else "powershell"
EVENTS = ("PreToolUse", "PostToolUse", "SessionStart")
COPILOT = ("--host", "copilot")
MISSING_PYTHON = "/nonexistent/python3.13" if os.name == "posix" else "C:/nonexistent/python3.13.exe"


def hook(script: str) -> str:
    return (HOOK_DIR / script).as_posix()


def registration() -> dict:
    """What the registrar writes for this interpreter."""
    return repair.plan({}, "copilot", sys.executable)[0]


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)
        self.user_file = self.home / ".copilot" / "hooks" / "supremeteam.json"
        self.project_file = self.project / ".github" / "hooks" / "supremeteam.json"

    def run_tool(self, script: "str | Path", *args: str, **extra: str) -> subprocess.CompletedProcess:
        return kit.run_cli(script, *args, env=kit.plain_env(self.home, **extra), cwd=self.project)

    def repair(self, *args: str, **extra: str) -> tuple[subprocess.CompletedProcess, dict]:
        done = self.run_tool("repair_registration.py", "--host", "copilot", *args, **extra)
        lines = done.stdout.strip().splitlines()
        return done, json.loads(lines[-1]) if lines else {}

    def write_json(self, path: Path, data) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def read(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def states(self, *objects: dict) -> dict:
        return verify.hook_states(list(objects), "copilot")


class WrittenFileTests(Scratch):
    def test_user_scope_writes_our_own_file_where_copilot_reads_hooks(self):
        done, report = self.repair("--scope", "user", "--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(Path(report["path"]), self.user_file)
        self.assertEqual(report["probe"], "started")
        config = self.read(self.user_file)
        self.assertEqual(list(config), ["version", "hooks"])
        self.assertEqual(config["version"], 1)
        self.assertEqual(tuple(config["hooks"]), EVENTS, "PascalCase events, and the session start in place of the prompt")
        for event, script in zip(EVENTS, ("pre_tool_use.py", "post_tool_use.py", "user_prompt_submit.py"), strict=True):
            with self.subTest(event=event):
                entries = config["hooks"][event]
                self.assertEqual(len(entries), 1, "a flat list of handlers, not matcher groups")
                entry = entries[0]
                self.assertEqual(entry["type"], "command")
                self.assertEqual(entry["timeoutSec"], 30)
                self.assertNotIn("command", entry)
                self.assertNotIn(OTHER_FIELD, entry, "only the platform this machine runs is given a command")
                self.assertNotIn("hooks", entry)
                self.assertTrue(entry[FIELD].endswith(f'"{hook(script)}" --host copilot') or
                                entry[FIELD].endswith(f'"{HOOK_DIR / script}" --host copilot'), entry[FIELD])
                self.assertEqual(entry.get("matcher"), repair.matcher_for(script, "copilot"))
        self.assertNotIn("matcher", config["hooks"]["SessionStart"][0])
        self.assertFalse((self.home / ".config").exists(), "nothing is written where Copilot does not look")
        verified = self.run_tool("verify_registration.py", "--host", "copilot")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        for line in ("[OK ] PreToolUse -> pre_tool_use.py", "[OK ] PostToolUse -> post_tool_use.py",
                     "[OK ] SessionStart -> user_prompt_submit.py", "status: REGISTERED",
                     "prompt routing on copilot is given at session start only"):
            self.assertIn(line, verified.stdout)
        again, report = self.repair("--scope", "user", "--apply")
        self.assertEqual((again.returncode, report["changes"]), (0, []))

    def test_copilot_home_moves_the_user_file(self):
        moved = self.tmp / "copilot-home"
        done, report = self.repair("--scope", "user", "--apply", COPILOT_HOME=str(moved))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(Path(report["path"]), moved / "hooks" / "supremeteam.json")
        self.assertFalse(self.user_file.exists())
        verified = self.run_tool("verify_registration.py", "--host", "copilot", COPILOT_HOME=str(moved))
        self.assertEqual(verified.returncode, 0, verified.stdout)

    def test_a_project_file_with_this_machines_paths_is_refused_unless_asked_for(self):
        """D4: where those paths do not exist the pre-tool command fails, and on Copilot that denies every tool call."""
        for extra in ((), ("--apply",)):
            with self.subTest(extra=extra):
                done, report = self.repair("--scope", "project", *extra)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("--allow-absolute", report["error"])
                self.assertIn("every tool call would be refused", report["error"])
        self.assertFalse((self.project / ".github").exists())
        done, report = self.repair("--scope", "project", "--apply", "--allow-absolute")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(Path(report["path"]), self.project_file)
        self.assertIn("keep it out of the commit", done.stderr)
        self.assertEqual(tuple(self.read(self.project_file)["hooks"]), EVENTS)

    def test_a_command_is_never_written_unprobed(self):
        """Copilot fails closed: a pre-tool command that cannot start denies every tool call, so the probe is not optional."""
        done, report = self.repair("--scope", "user", "--apply", "--no-probe")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("--no-probe is not accepted for copilot", report["error"])
        done, report = self.repair("--scope", "user", "--apply", "--python", MISSING_PYTHON)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("a command that was not started is not written", report["error"])
        self.assertFalse(self.user_file.exists())
        claude = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply", "--python", MISSING_PYTHON)
        self.assertEqual(claude.returncode, 0, "a host that fails open still takes an interpreter for another machine")

    def test_a_hook_another_file_of_the_directory_registers_is_not_written_twice(self):
        self.write_json(self.user_file.with_name("team.json"), registration())
        done, report = self.repair("--scope", "user", "--apply")
        self.assertEqual((done.returncode, report["changes"]), (0, []), done.stdout + done.stderr)
        self.assertFalse(self.user_file.exists())
        verified = self.run_tool("verify_registration.py", "--host", "copilot")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("team.json", verified.stdout)


class PlanTests(Scratch):
    def test_an_entry_of_ours_in_an_older_shape_is_replaced_and_anything_else_is_kept(self):
        mine = {"type": "command", "bash": "./scripts/log-tool.sh", "powershell": "./scripts/log-tool.ps1"}
        old = {"type": "command", "command": f'python "{hook("pre_tool_use.py")}"'}
        config = {"disableAllHooks": False, "hooks": {"PreToolUse": [mine, old, dict(old)], "notification": [mine]}}
        desired, added = repair.plan(json.loads(json.dumps(config)), "copilot", sys.executable)
        self.assertEqual(desired["version"], 1)
        self.assertEqual(desired["disableAllHooks"], False)
        self.assertEqual(desired["hooks"]["notification"], [mine])
        pre = desired["hooks"]["PreToolUse"]
        self.assertEqual(pre[0], mine)
        self.assertEqual(len(pre), 2, "the two old entries of ours become one")
        self.assertEqual(pre[1], repair.flat_entry("pre_tool_use.py", sys.executable, "copilot"))
        self.assertEqual(added[0], "PreToolUse -> pre_tool_use.py (replaces the entry registered before)")
        self.assertEqual(repair.plan(json.loads(json.dumps(desired)), "copilot", sys.executable), (desired, []))

    def test_the_other_platforms_command_stays_beside_the_new_one(self):
        fresh = registration()
        entry = dict(fresh["hooks"]["PreToolUse"][0])
        del entry[FIELD]
        # Written on the other platform: another interpreter, the same script.
        entry[OTHER_FIELD] = f'/opt/python/bin/python3 -X utf8 "{hook("pre_tool_use.py")}" --host copilot'
        config = {"version": 1, "hooks": {**fresh["hooks"], "PreToolUse": [entry]}}
        desired, added = repair.plan(json.loads(json.dumps(config)), "copilot", sys.executable)
        self.assertEqual(added, ["PreToolUse -> pre_tool_use.py (replaces the entry registered before)"])
        written = desired["hooks"]["PreToolUse"][0]
        self.assertEqual(written[OTHER_FIELD], entry[OTHER_FIELD])
        self.assertEqual(written[FIELD], fresh["hooks"]["PreToolUse"][0][FIELD])

    def test_a_file_that_is_not_the_shape_it_should_be_is_refused(self):
        for config in ({"hooks": []}, {"hooks": {"PreToolUse": {}}}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                repair.plan(config, "copilot", sys.executable)


class VerifierTests(Scratch):
    def entry(self, script: str = "pre_tool_use.py", **changes) -> dict:
        entry = repair.flat_entry(script, sys.executable, "copilot")
        entry.update(changes)
        return {key: value for key, value in entry.items() if value is not None}

    def pre(self, *entries: dict, event: str = "PreToolUse") -> dict:
        return self.states({"version": 1, "hooks": {event: list(entries)}})["pre"]

    def test_what_the_registrar_writes_is_a_registration(self):
        states = self.states(registration())
        self.assertEqual({key: (state["registered"], state["coverage"]) for key, state in states.items()},
                         {"pre": (True, "full"), "post": (True, "full"), "prompt": (True, "not_applicable")})

    def test_a_command_without_the_host_argument_is_not_one(self):
        """Without it the guard answers under hookSpecificOutput, which Copilot does not read: a deny that denies nothing."""
        plain = self.entry()[FIELD].removesuffix(" --host copilot")
        state = self.pre(self.entry(**{FIELD: plain}))
        self.assertFalse(state["registered"])
        self.assertIn("does not carry '--host copilot'", state["reason"])
        self.assertTrue(self.pre(self.entry(**{FIELD: plain + " --host copilot"}))["registered"])

    def test_the_camel_case_event_and_the_nested_shape_are_not_registrations(self):
        """The camelCase events carry toolName and toolArgs, which the guard does not read; Copilot's own files are flat."""
        self.assertFalse(self.pre(self.entry(), event="preToolUse")["registered"])
        nested = {"matcher": "Bash|Edit|Write", "hooks": [{"type": "command", "command": self.entry()[FIELD]}]}
        self.assertEqual(self.pre(nested)["reason"], "no command registered")

    def test_the_command_is_read_from_this_platforms_field_and_then_from_command(self):
        text = self.entry()[FIELD]
        self.assertEqual(self.pre(self.entry(**{FIELD: None, OTHER_FIELD: text}))["reason"], "no command registered")
        self.assertTrue(self.pre(self.entry(**{FIELD: None, "command": text}))["registered"])
        self.assertEqual(self.pre(self.entry(**{"command": "true"}))["command"], text, "the platform field wins over command")
        self.assertEqual(self.pre(self.entry(type="http", url="https://example.invalid"))["reason"], "no command registered")

    def test_a_matcher_that_leaves_out_a_tool_is_partial_coverage(self):
        state = self.pre(self.entry(matcher="Bash|Edit"))
        self.assertEqual((state["registered"], state["coverage"], state["missing_tools"]), (True, "partial", ["Write"]))
        self.assertEqual(self.pre(self.entry(matcher="view|grep"))["coverage"], "none")
        for everything in (None, "", "*"):
            self.assertEqual(self.pre(self.entry(matcher=everything))["coverage"], "full")

    def test_every_json_file_of_both_directories_is_read(self):
        self.write_json(self.user_file.with_name("a.json"), {"version": 1, "hooks": {}})
        self.write_json(self.project_file.with_name("b.json"), {"version": 1, "hooks": {}})
        (self.project_file.parent / "notes.txt").write_text("x", encoding="utf-8")
        code = ("import sys; sys.path.insert(0, %r); import verify_registration as v; "
                "print(';'.join(str(p) for p in v._paths('copilot')))" % str(HOOK_DIR))
        out = subprocess.run([sys.executable, "-c", code], cwd=str(self.project), env=kit.plain_env(self.home), text=True,
                             capture_output=True, check=False)
        self.assertEqual([Path(line) for line in out.stdout.strip().split(";") if line],
                         [self.user_file, self.user_file.with_name("a.json"), self.project_file, self.project_file.with_name("b.json")],
                         out.stderr)


class LegacyFileTests(Scratch):
    OLD = {"hooks": {
        "PreToolUse": [{"matcher": "Bash|Edit|Write", "hooks": [{"type": "command", "command": f'python -X utf8 "{hook("pre_tool_use.py")}"',
                                                                 "statusMessage": "SupremeTeam: checking pending tool use"}]}],
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": f'python -X utf8 "{hook("user_prompt_submit.py")}"'}]}],
    }}

    def setUp(self):
        super().setUp()
        self.legacy = self.home / ".config" / "github-copilot" / "hooks.json"

    def backups(self, path: Path) -> list:
        return sorted(path.parent.glob(path.name + ".bak-*"))

    def test_a_file_that_is_ours_alone_is_set_aside_when_the_new_one_is_written(self):
        self.write_json(self.legacy, self.OLD)
        preview, report = self.repair("--scope", "user")
        self.assertEqual(preview.returncode, 1, "a dry run with changes to make")
        self.assertTrue(any("it would be moved to hooks.json.bak-" in warning for warning in report["warnings"]), report)
        self.assertTrue(self.legacy.exists())
        done, report = self.repair("--scope", "user", "--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse(self.legacy.exists())
        kept = self.backups(self.legacy)
        self.assertEqual(len(kept), 1)
        self.assertEqual(self.read(kept[0]), self.OLD, "moved, not rewritten")
        self.assertTrue(any("held only Supreme Team entries and copilot does not read it: moved to" in warning
                            for warning in report["warnings"]), report)
        self.assertNotIn("would be moved", " ".join(report["warnings"]))
        self.assertTrue(self.user_file.is_file())

    def test_a_file_that_holds_anything_else_is_left_and_named(self):
        for label, config in (("a setting beside the hooks", {**self.OLD, "telemetry": False}),
                              ("somebody else's hook", {"hooks": {**self.OLD["hooks"], "PostToolUse": [
                                  {"hooks": [{"type": "command", "command": "./log.sh"}]}]}}),
                              ("a hook of ours and one that is not, in one group", {"hooks": {"PreToolUse": [{"hooks": [
                                  self.OLD["hooks"]["PreToolUse"][0]["hooks"][0], {"type": "command", "command": "./log.sh"}]}]}}),
                              ("no hooks at all", {"hooks": {}})):
            with self.subTest(file=label):
                self.write_json(self.legacy, config)
                done, report = self.repair("--scope", "user")
                self.assertTrue(any("so it is left as it is" in warning for warning in report["warnings"]), report)
                self.assertEqual(self.read(self.legacy), config)
                self.assertEqual(self.backups(self.legacy), [])

    def test_the_repository_file_is_handled_with_project_scope_and_not_with_user_scope(self):
        legacy = self.write_json(self.project / ".github" / "hooks.json", self.OLD)
        done, report = self.repair("--scope", "user", "--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue(legacy.exists(), "user scope leaves the repository alone")
        done, report = self.repair("--scope", "project", "--apply", "--allow-absolute")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse(legacy.exists())
        self.assertEqual(len(self.backups(legacy)), 1)

    def test_an_already_registered_host_still_has_its_old_file_set_aside(self):
        self.write_json(self.user_file, registration())
        self.write_json(self.legacy, self.OLD)
        done, report = self.repair("--scope", "user", "--apply")
        self.assertEqual((done.returncode, report["changes"]), (0, []), done.stdout + done.stderr)
        self.assertFalse(self.legacy.exists())
        self.assertTrue(any("moved to" in warning for warning in report["warnings"]), report)

    def test_readiness_names_the_old_file_and_selects_the_host_by_it(self):
        self.write_json(self.legacy, self.OLD)
        result = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("[copilot]", result.stdout)
        self.assertIn(f"{self.legacy} is where an earlier version registered Copilot hooks, and Copilot does not read it", result.stdout)
        self.assertIn("status: MISSING", result.stdout)


class DoubleRunTests(Scratch):
    """Copilot CLI also runs the hooks of a repository's ``.claude/settings.json``: one tool call, two deliveries."""

    FAILED = {"tool_name": "Bash", "tool_input": {"command": "make test"}, "tool_response": {"exit_code": 1, "stdout": "boom"},
              "session_id": "s-copilot"}

    def post(self, payload: dict, *args: str) -> str:
        done = kit.run_hook("post_tool_use.py", payload, self.project, text=True, args=args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def steps(self) -> list:
        files = list((self.project / ".harness-state" / "trajectories").rglob("*.json"))
        self.assertEqual(len(files), 1)
        return json.loads(files[0].read_text(encoding="utf-8"))

    def test_the_registrar_says_when_a_claude_registration_in_the_project_will_run_as_well(self):
        self.write_json(self.project / ".claude" / "settings.json", repair.plan({}, "claude", sys.executable)[0])
        done, report = self.repair("--scope", "user")
        self.assertTrue(any("Copilot CLI runs a repository's Claude Code hooks as well" in warning for warning in report["warnings"]),
                        report)
        self.write_json(self.project / ".claude" / "settings.json", {"model": "opus"})
        done, report = self.repair("--scope", "user")
        self.assertFalse(any("Claude Code hooks as well" in warning for warning in report["warnings"]), report)

    def test_a_tool_event_delivered_twice_is_recorded_once_and_hinted_once(self):
        """Counted twice, the second failure of a command would read as the fourth and the hint come a call early."""
        said = []
        for call in ("toolu_1", "toolu_2", "toolu_3"):
            payload = dict(self.FAILED, tool_use_id=call)
            said.append((self.post(payload), self.post(payload, *COPILOT)))
        self.assertEqual([bool(first.strip()) for first, _ in said], [False, False, True], said)
        self.assertIn("failed 3 times", said[2][0])
        self.assertEqual([second for _, second in said], ["", "", ""], "the second delivery says nothing")
        self.assertEqual(len(self.steps()), 3)

    def test_without_an_id_a_timestamp_tells_a_second_delivery_from_a_repeat(self):
        first = dict(self.FAILED, timestamp="2026-11-12T05:00:00.000Z")
        self.post(first)
        self.post(first)
        self.assertEqual(len(self.steps()), 1, "the same bytes twice: one event")
        self.post(dict(first, timestamp="2026-11-12T05:00:07.000Z"))
        self.assertEqual(len(self.steps()), 2, "the same command at another time: a repeat")

    def test_with_neither_every_delivery_counts_because_a_repeat_has_to(self):
        outputs = [self.post(self.FAILED) for _ in range(3)]
        self.assertEqual(len(self.steps()), 3)
        self.assertIn("failed 3 times", outputs[-1])
        self.assertTrue(all("event" not in step for step in self.steps()))


class AnswerShapeTests(Scratch):
    """``--host copilot`` on the command line chooses the shape; without it the output is what it always was."""

    def setUp(self):
        super().setUp()
        (self.project / "src" / "payments").mkdir(parents=True)
        kit.write_guard(self.project, {"frozen_globs": [{"glob": "src/payments/**", "owner": "ops"}]})

    def pre(self, tool: str, tool_input: dict, *args: str) -> subprocess.CompletedProcess:
        payload = {"hook_event_name": "PreToolUse", "session_id": "s1", "timestamp": "2026-11-12T05:00:00.000Z",
                   "cwd": str(self.project), "tool_name": tool, "tool_input": tool_input}
        done = kit.run_hook("pre_tool_use.py", payload, self.project, text=True, args=args)
        self.assertEqual(done.returncode, 0, "the hook exits 0 whatever it decides: on Copilot any other exit is a deny")
        return done

    def test_a_deny_is_at_the_top_level_for_copilot_and_nested_for_everyone_else(self):
        for args in (COPILOT, ("--host=copilot",), ("--host", "Copilot")):
            with self.subTest(args=args):
                answer = json.loads(self.pre("Write", {"path": "src/payments/a.py", "file_text": "x"}, *args).stdout)
                self.assertEqual(sorted(answer), ["permissionDecision", "permissionDecisionReason"])
                self.assertEqual(answer["permissionDecision"], "deny")
                self.assertIn("frozen boundary", answer["permissionDecisionReason"])
        for args in ((), ("--host", "claude")):
            with self.subTest(args=args):
                answer = json.loads(self.pre("Write", {"file_path": "src/payments/a.py", "content": "x"}, *args).stdout)
                self.assertEqual(list(answer), ["hookSpecificOutput"])
                self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_copilots_tools_are_judged_under_the_names_it_documents_and_under_its_own(self):
        target = {"path": "src/payments/a.py"}
        for tool, tool_input in (("Write", {**target, "file_text": "x"}), ("Edit", {**target, "old_str": "a", "new_str": "b"}),
                                 ("create", {**target, "file_text": "x"}), ("edit", {**target, "old_str": "a", "new_str": "b"}),
                                 ("str_replace_editor", {**target, "command": "str_replace", "old_str": "a", "new_str": "b"}),
                                 ("Bash", {"command": "echo x > src/payments/a.py"}), ("bash", {"command": "echo x > src/payments/a.py"}),
                                 ("powershell", {"command": "Set-Content -Path src/payments/a.py -Value x"})):
            with self.subTest(tool=tool):
                self.assertEqual(json.loads(self.pre(tool, tool_input, *COPILOT).stdout)["permissionDecision"], "deny")

    def test_an_ordinary_call_gets_no_answer(self):
        for tool, tool_input in (("Bash", {"command": "ls src"}), ("Write", {"path": "src/other.py", "file_text": "x"}),
                                 ("view", {"path": "src/payments/a.py"})):
            with self.subTest(tool=tool):
                done = self.pre(tool, tool_input, *COPILOT)
                self.assertEqual((done.stdout, done.stderr), ("", ""))

    def test_advice_before_a_tool_goes_to_stderr_for_copilot_which_has_no_channel_for_it(self):
        (self.project / ".harness-state" / "guard-state.json").write_text("{not json", encoding="utf-8")
        done = self.pre("Bash", {"command": "ls"}, *COPILOT)
        self.assertEqual(done.stdout, "")
        self.assertIn("[harness:guard-state]", done.stderr)
        nested = json.loads(self.pre("Bash", {"command": "ls"}).stdout)
        self.assertIn("[harness:guard-state]", nested["hookSpecificOutput"]["additionalContext"])

    def test_the_post_tool_hook_reads_copilots_result_and_answers_at_the_top_level(self):
        payload = {"hook_event_name": "PostToolUse", "session_id": "s1", "cwd": str(self.project), "tool_name": "Bash",
                   "tool_input": {"command": "make test"}, "tool_result": {"result_type": "failure", "text_result_for_llm": "boom"}}
        outputs = [kit.run_hook("post_tool_use.py", dict(payload, timestamp=f"2026-11-12T05:00:0{n}.000Z"), self.project,
                                text=True, args=COPILOT).stdout for n in range(3)]
        self.assertEqual(outputs[:2], ["", ""])
        answer = json.loads(outputs[2])
        self.assertEqual(list(answer), ["additionalContext"])
        self.assertIn("failed 3 times", answer["additionalContext"])

    def test_a_result_copilot_calls_a_success_is_not_a_failure_whatever_its_text_says(self):
        payload = {"session_id": "s2", "tool_name": "Bash", "tool_input": {"command": "grep -c error log"},
                   "tool_result": {"result_type": "success", "text_result_for_llm": "error: 3 failed"}}
        outputs = [kit.run_hook("post_tool_use.py", dict(payload, timestamp=f"2026-11-12T05:00:0{n}.000Z"), self.project,
                                text=True, args=COPILOT).stdout for n in range(4)]
        self.assertEqual(outputs, ["", "", "", ""])

    def test_the_session_start_gets_the_routing_reminder_once_whatever_the_first_prompt_is(self):
        start = {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": str(self.project), "source": "startup",
                 "initial_prompt": "/help"}
        done = kit.run_hook("user_prompt_submit.py", start, self.project, text=True, args=COPILOT)
        answer = json.loads(done.stdout)
        self.assertEqual(list(answer), ["additionalContext"])
        self.assertIn("no active run detected", answer["additionalContext"])
        kit.pin_a_run(self.project)
        pinned = json.loads(kit.run_hook("user_prompt_submit.py", start, self.project, text=True, args=COPILOT).stdout)
        self.assertIn("a run is active", pinned["additionalContext"])
        other = json.loads(kit.run_hook("user_prompt_submit.py", start, self.project, text=True).stdout)
        self.assertEqual(other["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_a_prompt_event_is_still_routed_by_its_prompt(self):
        for prompt, said in (("build me a login page", True), ("/help", False), ("", False)):
            with self.subTest(prompt=prompt):
                done = kit.run_hook("user_prompt_submit.py", {"hook_event_name": "UserPromptSubmit", "prompt": prompt}, self.project,
                                    text=True, args=COPILOT)
                self.assertEqual(bool(done.stdout.strip()), said)

    def test_the_selftest_is_found_after_the_host_argument(self):
        for script in ("pre_tool_use.py", "post_tool_use.py", "user_prompt_submit.py"):
            with self.subTest(script=script):
                done = kit.run_cli(script, *COPILOT, "--selftest", env=kit.clean_env(self.project))
                self.assertEqual((done.returncode, done.stdout.strip()), (0, "ok"), done.stderr)
        self.assertFalse((self.project / ".harness-state" / "observations").exists(), "a self-test is not a host event")


class InstallerTests(Scratch):
    def install(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        return self.run_tool(INSTALLER, "--hook-root", str(HOOK_DIR), "--target", "copilot", *args, **extra)

    def test_the_hook_installer_writes_the_same_file_and_verifies_it(self):
        self.write_json(self.home / ".config" / "github-copilot" / "hooks.json", LegacyFileTests.OLD)
        done = self.install()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for line in (f"config: {self.user_file}", "[OK ] PreToolUse -> pre_tool_use.py", "[OK ] SessionStart -> user_prompt_submit.py",
                     "status: REGISTERED", "held only Supreme Team entries and copilot does not read it: moved to"):
            self.assertIn(line, done.stdout)
        self.assertEqual(self.read(self.user_file), registration())
        again = self.install()
        self.assertIn("no changes: already registered", again.stdout)

    def test_it_refuses_what_the_registrar_refuses(self):
        for label, args, said in (("a project file with this machine's paths", ("--scope", "project"), "--allow-absolute"),
                                  ("an unprobed command", ("--no-probe",), "--no-probe is not accepted for copilot"),
                                  ("an interpreter that is not here", ("--python-command", MISSING_PYTHON),
                                   "a command that was not started is not written")):
            with self.subTest(refused=label):
                done = self.install(*args)
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn("REFUSED", done.stdout)
                self.assertIn(said, done.stdout)
        self.assertFalse(self.user_file.exists())
        self.assertFalse((self.project / ".github").exists())

    def test_a_dry_run_previews_the_file_and_the_move_and_writes_nothing(self):
        legacy = self.write_json(self.home / ".config" / "github-copilot" / "hooks.json", LegacyFileTests.OLD)
        done = self.install("--dry-run")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn('+  "version": 1,', done.stdout)
        self.assertIn("it would be moved to hooks.json.bak-", done.stdout)
        self.assertTrue(legacy.exists())
        self.assertFalse(self.user_file.exists())

    def test_a_named_path_and_an_allowed_project_file(self):
        named = self.tmp / "elsewhere" / "hooks" / "supremeteam.json"
        done = self.install("--copilot-hooks", str(named))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.read(named), registration())
        done = self.install("--scope", "project", "--allow-absolute")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(tuple(self.read(self.project_file)["hooks"]), EVENTS)


if __name__ == "__main__":
    unittest.main()
