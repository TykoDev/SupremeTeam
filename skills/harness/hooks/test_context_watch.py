#!/usr/bin/env python3
"""A run in flight is advised as the conversation's context window fills (WP-12).

The request was a context dump at 90 %. A host's tool and prompt payloads carry no usage figure, so the figure comes
from the status-line sidecar (``context_statusline.py``: Claude Code hands its status line the percentage in use) or
from the last assistant line of the session transcript, measured against a window somebody has stated. With neither,
nothing is said: a guessed window would tell an agent to dump at the wrong moment.

Crossing ``warn``, ``dump`` or ``handoff`` (``context_pressure`` in ``runtime-manifest.yaml``) gives one note, once
per session. It is advice: nothing is denied. Only while a run holds the pin, never inside a sub-agent, and at most
every ``check_every_s`` seconds.

The status line runs only in an interactive session, so the sidecar's input is the shape Claude Code documents and
was not captured from one.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import _bootstrap
import _testkit as kit
import context_statusline
import context_watch
import repair_registration as repair
import verify_registration as verify

HOOK_DIR = Path(__file__).resolve().parent
INSTALLER = HOOK_DIR.parents[2] / "scripts" / "install_hooks.py"
RUN = "r1"
SESSION = "s-watch"
PAYLOAD = {"session_id": SESSION, "tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_response": {"exit_code": 0, "stdout": "a"}}


def assistant(tokens: int, model: str = "claude-test-1", cached: int = 0, **more) -> str:
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "model": model, "usage": {
        "input_tokens": tokens, "cache_read_input_tokens": cached, "cache_creation_input_tokens": 0, "output_tokens": 900}}, **more})


class Project(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(kit.project())
        self.enterContext(kit.in_project(self.root, HOME=str(self.root / "home"), USERPROFILE=str(self.root / "home")))
        os.environ.pop(context_watch.WINDOW_ENV, None)
        self.clock = 1_800_000_000.0
        self.enterContext(mock.patch.object(context_watch.time, "time", side_effect=lambda: self.clock))
        self.usage_dir = self.root / ".harness-state" / "context-usage"

    def pin(self) -> None:
        kit.pin_a_run(self.root, RUN)

    def sidecar(self, percentage, window=200_000, age: float = 0.0, payload: dict = PAYLOAD) -> Path:
        path = context_watch.session_file(payload, "usage", create=True)
        path.write_text(json.dumps({"used_percentage": percentage, "window": window, "model": "claude-test-1",
                                    "at": self.clock - age}), encoding="utf-8")
        return path

    def transcript(self, *lines: str) -> dict:
        path = self.root / "transcript.jsonl"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return dict(PAYLOAD, transcript_path=str(path))

    def ask(self, payload: dict = PAYLOAD, later: float = 31.0) -> "str | None":
        """``advice`` after ``later`` more seconds: past the throttle by default."""
        self.clock += later
        return context_watch.advice(payload, "PostToolUse")

    def faults(self, event: str = "PostToolUse") -> int:
        record = self.root / ".harness-state" / "observations" / f"{event}.json"
        return json.loads(record.read_text(encoding="utf-8")).get("faults", 0) if record.is_file() else 0


class ThresholdTests(Project):
    def test_each_level_is_advised_once_as_the_status_line_figure_rises(self):
        self.pin()
        said = []
        for percentage in (79, 80, 85, 90, 93, 95, 99):
            self.sidecar(percentage)
            said.append(self.ask())
        self.assertEqual([bool(note) for note in said], [False, True, False, True, False, True, False])
        warn, dump, handoff = said[1], said[3], said[5]
        for note in (warn, dump, handoff):
            self.assertTrue(note.startswith("[harness:context-pressure] "))
            self.assertIn("by the status line", note)
        self.assertIn("is at 80% of its context window", warn)
        self.assertIn("At 90% you will be asked to write a context dump", warn)
        self.assertIn(f"run {RUN} is in flight", warn)
        command = context_watch._dump_command(RUN)
        self.assertTrue(command.endswith(f" dump --run-id {RUN} --trigger context-pressure --narrative-from -"), command)
        # The command has to run from wherever the agent is: this interpreter and the writer beside the hook, by path.
        self.assertIn((HOOK_DIR / "save_run.py").as_posix(), command)
        self.assertIn(Path(sys.executable).as_posix(), command.replace('"', ""))
        self.assertNotIn("\\", command)
        self.assertIn(f"Write a context dump for run {RUN} now: pipe a narrative to '{command}'", dump)
        for part in ("the objective", "the decisions made and why", "the files in flight", "the open questions", "the exact next action",
                     "The dump does not change the revision"):
            self.assertIn(part, dump)
        self.assertIn("start nothing new", handoff)
        self.assertIn(command, handoff)
        self.assertIn("let the host compact", handoff)

    def test_a_figure_that_jumps_past_two_levels_gives_the_highest_and_not_the_lower_ones_later(self):
        self.pin()
        self.sidecar(96)
        self.assertIn("start nothing new", self.ask())
        for percentage in (97, 91, 82):
            self.sidecar(percentage)
            self.assertIsNone(self.ask())

    def test_the_levels_are_armed_again_after_the_context_was_compacted(self):
        self.pin()
        self.sidecar(91)
        self.assertIn("Write a context dump", self.ask())
        self.sidecar(60)
        self.assertIsNone(self.ask(), "a small drop is not a compaction")
        self.sidecar(91)
        self.assertIsNone(self.ask())
        self.sidecar(30)
        self.assertIsNone(self.ask())
        self.sidecar(91)
        self.assertIn("Write a context dump", self.ask(), "a new stretch of the conversation, a new dump")

    def test_the_thresholds_are_the_manifests(self):
        self.pin()
        custom = dict(context_watch.DEFAULTS, warn=0.5, dump=0.6, handoff=0.7)
        with mock.patch.object(context_watch, "settings", return_value=custom):
            self.sidecar(55)
            self.assertIn("At 60% you will be asked", self.ask())
        shipped = context_watch.settings()
        self.assertEqual((shipped["warn"], shipped["dump"], shipped["handoff"], shipped["check_every_s"], shipped["window_tokens"]),
                         (0.80, 0.90, 0.95, 30.0, {}))

    def test_a_manifest_that_is_not_the_shape_it_should_be_falls_back_to_the_defaults_and_is_counted(self):
        self.pin()
        for broken in ({"warn": "0.80", "dump": 0.9, "handoff": 0.95, "check_every_s": 30},
                       {"warn": 0.9, "dump": 0.8, "handoff": 0.95, "check_every_s": 30},
                       {"warn": 0.8, "dump": 0.9, "handoff": 1.5, "check_every_s": 30}, None):
            with self.subTest(broken=broken), mock.patch("data_formats.load_data", return_value={"context_pressure": broken}), \
                    self.assertRaises(context_watch.Unreadable):
                context_watch.settings()
        with mock.patch.object(context_watch, "settings", side_effect=context_watch.Unreadable("x")):
            self.sidecar(91)
            self.assertIn("Write a context dump", self.ask())
        self.assertEqual(self.faults(), 1)


class SourceTests(Project):
    def test_the_transcript_is_read_when_the_window_is_known(self):
        self.pin()
        payload = self.transcript(json.dumps({"type": "user", "message": {"role": "user", "content": "hi"}}),
                                  assistant(100_000), assistant(120_000, cached=62_000))
        with mock.patch.dict(os.environ, {context_watch.WINDOW_ENV: "200000"}):
            note = self.ask(payload)
        self.assertIn("is at 91% of its context window (by the transcript)", note)
        self.assertIn("Write a context dump", note)

    def test_the_window_can_come_from_the_manifest_for_the_exact_model_or_from_a_stale_sidecar(self):
        self.pin()
        payload = self.transcript(assistant(170_000, model="claude-test-1"))
        known = dict(context_watch.DEFAULTS, window_tokens={"claude-test-1": 200_000})
        with mock.patch.object(context_watch, "settings", return_value=known):
            self.assertIn("is at 85%", self.ask(payload))
        other = dict(PAYLOAD, session_id="s-other", transcript_path=payload["transcript_path"])
        with mock.patch.object(context_watch, "settings", return_value=dict(context_watch.DEFAULTS, window_tokens={"claude-test": 200_000})):
            self.assertIsNone(self.ask(other), "a model id that only resembles the one in the table is not that model")
        third = dict(PAYLOAD, session_id="s-third", transcript_path=payload["transcript_path"])
        self.sidecar(10, window=180_000, age=context_watch.SIDECAR_MAX_AGE + 60, payload=third)
        self.assertIn("is at 94% of its context window (by the transcript)", self.ask(third),
                      "an old sidecar says nothing about usage now, and still knows the window")

    def test_a_fresh_sidecar_is_preferred_to_the_transcript(self):
        self.pin()
        payload = self.transcript(assistant(199_000))
        self.sidecar(81)
        with mock.patch.dict(os.environ, {context_watch.WINDOW_ENV: "200000"}):
            self.assertIn("is at 81% of its context window (by the status line)", self.ask(payload))

    def test_an_unknown_window_is_silent_and_no_guess_is_made(self):
        self.pin()
        self.assertIsNone(self.ask(self.transcript(assistant(900_000))))
        self.assertIsNone(self.ask(PAYLOAD), "no sidecar and no transcript")
        self.assertEqual(self.faults(), 0)

    def test_the_main_conversations_last_turn_is_the_one_measured(self):
        self.pin()
        payload = self.transcript(assistant(184_000), assistant(20_000, isSidechain=True),
                                  json.dumps({"type": "user", "message": {"role": "user", "content": "x"}}), "", "{broken")
        with mock.patch.dict(os.environ, {context_watch.WINDOW_ENV: "200000"}):
            self.assertIn("is at 92%", self.ask(payload))

    def test_only_the_end_of_a_long_transcript_is_read(self):
        self.pin()
        filler = json.dumps({"type": "user", "message": {"role": "user", "content": "x" * 2000}})
        payload = self.transcript(assistant(10_000), *([filler] * 400), assistant(190_000))
        self.assertGreater(Path(payload["transcript_path"]).stat().st_size, context_watch.TRANSCRIPT_TAIL * 2)
        with mock.patch.dict(os.environ, {context_watch.WINDOW_ENV: "200000"}), \
                mock.patch.object(context_watch, "TRANSCRIPT_TAIL", 16 * 1024):
            self.assertIn("is at 95%", self.ask(payload))

    def test_a_garbled_source_is_silent_and_counted(self):
        self.pin()
        garbled = self.sidecar(91)
        for content in ("{not json", "[]", json.dumps({"used_percentage": 91})):
            garbled.write_text(content, encoding="utf-8")
            with self.subTest(sidecar=content[:10]):
                self.assertIsNone(self.ask())
        self.assertEqual(self.faults(), 3)
        garbled.unlink()
        payload = self.transcript("this is not", "a transcript at all")
        with mock.patch.dict(os.environ, {context_watch.WINDOW_ENV: "200000"}):
            self.assertIsNone(self.ask(payload))
        self.assertEqual(self.faults(), 4)
        with mock.patch.dict(os.environ, {context_watch.WINDOW_ENV: "lots"}):
            self.assertIsNone(self.ask(self.transcript(assistant(190_000))))
        self.assertEqual(self.faults(), 5)


class ScopeTests(Project):
    def test_the_throttle_holds(self):
        self.pin()
        self.sidecar(50)
        self.assertIsNone(self.ask())
        self.sidecar(91)
        self.assertIsNone(self.ask(later=10), "measured ten seconds ago: not again yet")
        self.assertIsNone(self.ask(later=19))
        self.sidecar(91)
        self.assertIn("Write a context dump", self.ask(later=2))

    def test_a_call_inside_a_sub_agent_is_not_advised(self):
        """The figures are the main conversation's; nothing measures a sub-agent."""
        self.pin()
        self.sidecar(96)
        self.assertIsNone(self.ask(dict(PAYLOAD, agent_id="a1", agent_type="general-purpose")))
        self.assertIn("start nothing new", self.ask())

    def test_outside_a_run_nothing_is_said_and_nothing_is_written(self):
        self.assertIsNone(self.ask())
        self.assertFalse((self.root / ".harness-state").exists())
        kit.pin_a_run(self.root, RUN)
        kit.save(self.root, RUN, "release")
        before = sorted(path.name for path in (self.root / ".harness-state").rglob("*"))
        self.assertIsNone(self.ask(self.transcript(assistant(199_000))))
        self.assertEqual(sorted(path.name for path in (self.root / ".harness-state").rglob("*")), before)

    def test_each_session_has_its_own_levels(self):
        self.pin()
        other = dict(PAYLOAD, session_id="s-other")
        self.sidecar(91)
        self.sidecar(91, payload=other)
        self.assertIn("Write a context dump", self.ask())
        self.assertIn("Write a context dump", self.ask(other))
        self.assertIsNone(self.ask())

    def test_the_hooks_carry_the_note_and_deny_nothing(self):
        self.pin()
        self.clock = datetime.now().timestamp()  # the hooks run as processes of their own, on the real clock
        self.sidecar(91)
        posted = kit.run_hook("post_tool_use.py", PAYLOAD, self.root, text=True)
        self.assertEqual(posted.returncode, 0, posted.stderr)
        self.assertIn("[harness:context-pressure]", json.loads(posted.stdout)["hookSpecificOutput"]["additionalContext"])
        self.sidecar(96)
        os.utime(self.usage_dir, None)
        watch = context_watch.session_file(PAYLOAD, "watch")
        watch.write_text(json.dumps({"checked_at": 0, "every": 30, "advised": ["warn", "dump"]}), encoding="utf-8")
        prompted = kit.run_hook("user_prompt_submit.py", {"session_id": SESSION, "prompt": "carry on"}, self.root, text=True)
        said = json.loads(prompted.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("start nothing new", said)
        self.assertIn("a run is active", said, "with the reminder the prompt hook gives anyway")
        self.assertNotIn("permissionDecision", posted.stdout + prompted.stdout)

    def test_the_module_is_one_a_registered_hook_runs(self):
        self.assertIn("context_watch.py", _bootstrap.HOOK_FILES)


class StatusLineTests(Project):
    def line(self, used=42.5, size=200_000, **more) -> dict:
        return {"hook_event_name": "Status", "session_id": SESSION, "model": {"id": "claude-test-1", "display_name": "Test"},
                "workspace": {"current_dir": str(self.root), "project_dir": str(self.root)},
                "context_window": {"used_percentage": used, "context_window_size": size, "remaining_percentage": None}, **more}

    def status(self, payload, *args: str, **env: str) -> subprocess.CompletedProcess:
        return kit.run_cli("context_statusline.py", *args, env=kit.plain_env(self.root / "home", **env), cwd=self.root,
                           input=payload if isinstance(payload, str) else json.dumps(payload))

    def written(self) -> dict:
        return json.loads(context_watch.session_file(PAYLOAD, "usage").read_text(encoding="utf-8"))

    def test_the_figures_are_written_for_the_session_and_a_short_status_is_printed(self):
        self.pin()
        done = self.status(self.line())
        self.assertEqual((done.returncode, done.stdout), (0, "ctx 42%\n"), done.stderr)
        record = self.written()
        self.assertEqual((record["used_percentage"], record["window"], record["model"]), (42.5, 200_000, "claude-test-1"))
        self.clock = record["at"]
        self.assertEqual(context_watch.measure(PAYLOAD, context_watch.DEFAULTS), {"used": 0.425, "source": "status line"})

    def test_the_project_is_the_one_the_payload_names_wherever_the_command_is_started(self):
        self.pin()
        elsewhere = self.root / "home"
        elsewhere.mkdir(exist_ok=True)
        done = kit.run_cli("context_statusline.py", env=kit.plain_env(elsewhere), cwd=elsewhere, input=json.dumps(self.line(91)))
        self.assertEqual(done.stdout, "ctx 91%\n")
        self.assertEqual(self.written()["used_percentage"], 91)

    def test_a_figure_that_is_not_there_yet_writes_nothing(self):
        """Claude Code documents the percentage as null early in a session."""
        self.pin()
        done = self.status(self.line(used=None))
        self.assertEqual((done.returncode, done.stdout), (0, "ctx --\n"))
        self.assertFalse(self.usage_dir.exists())

    def test_a_project_with_no_saved_runs_gets_no_sidecar(self):
        done = self.status(self.line(91))
        self.assertEqual(done.stdout, "ctx 91%\n")
        self.assertFalse((self.root / ".harness-state").exists())

    def test_an_unchanged_figure_is_not_rewritten_at_once_and_a_changed_one_is(self):
        self.pin()
        self.status(self.line(50))
        first = self.written()["at"]
        self.status(self.line(50.2))
        self.assertEqual(self.written()["at"], first)
        self.status(self.line(53))
        self.assertEqual(self.written()["used_percentage"], 53)

    def test_a_status_line_of_ones_own_keeps_working_behind_it(self):
        self.pin()
        own = self.root / "own.py"
        own.write_text("import json, sys\nd = json.load(sys.stdin)\nprint('[' + d['model']['display_name'] + '] mine')\n", encoding="utf-8")
        done = self.status(self.line(77), "--", sys.executable, str(own))
        self.assertEqual(done.stdout.strip(), "[Test] mine")
        self.assertEqual(self.written()["used_percentage"], 77, "and the figure is still recorded")
        missing = self.status(self.line(77), "--", str(self.root / "no-such-program"))
        self.assertEqual((missing.returncode, missing.stdout), (0, ""))

    def test_input_that_is_not_a_status_line_never_fails(self):
        for payload in ("", "{not json", "[]", json.dumps({"context_window": "full"})):
            with self.subTest(payload=payload[:10]):
                done = self.status(payload)
                self.assertEqual((done.returncode, done.stdout), (0, "ctx --\n"), done.stderr)

    def test_the_figures_are_read_from_the_fields_claude_code_documents(self):
        self.assertEqual(context_statusline.figures(self.line(8, 1_000_000)), (8.0, 1_000_000, "claude-test-1"))
        self.assertEqual(context_statusline.figures({"context_window": {"used_percentage": True, "context_window_size": 0}}), (None, None, None))


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)
        self.settings = self.project / ".claude" / "settings.json"

    def run_tool(self, script, *args: str, **extra: str) -> subprocess.CompletedProcess:
        return kit.run_cli(script, *args, env=kit.plain_env(self.home, **extra), cwd=self.project)

    def config(self) -> dict:
        return json.loads(self.settings.read_text(encoding="utf-8"))

    def test_the_status_line_is_set_when_none_is_configured(self):
        desired, added, notes = repair.plan_statusline({"model": "opus"}, "claude", sys.executable)
        self.assertEqual((added, notes), (["statusLine -> context_statusline.py"], []))
        line = desired["statusLine"]
        self.assertEqual((line["type"], line["padding"]), ("command", 0))
        self.assertTrue(line["command"].endswith('context_statusline.py"'), line["command"])
        self.assertEqual(verify.handler_defects(line, "claude"), [], "a form the host's shell can start")
        self.assertEqual(repair.plan_statusline(desired, "claude", sys.executable), (desired, [], []), "a second run changes nothing")

    def test_a_status_line_of_ones_own_is_left_and_the_command_that_keeps_it_is_given(self):
        mine = {"statusLine": {"type": "command", "command": "~/.claude/statusline.sh"}}
        desired, added, notes = repair.plan_statusline(mine, "claude", sys.executable)
        self.assertEqual((desired, added), (mine, []))
        self.assertEqual(len(notes), 1)
        self.assertIn("is left as it is", notes[0])
        self.assertIn('context_statusline.py" -- ~/.claude/statusline.sh', notes[0])
        wrapped = {"statusLine": {"type": "command", "command": "python context_statusline.py -- ~/.claude/statusline.sh"}}
        self.assertEqual(repair.plan_statusline(wrapped, "claude", sys.executable), (wrapped, [], []))

    def test_only_claude_code_has_one(self):
        for host in ("codex", "copilot"):
            desired, added, notes = repair.plan_statusline({}, host, sys.executable)
            self.assertEqual((desired, added), ({}, []))
            self.assertIn(f"--statusline does nothing for {host}", notes[0])

    def test_the_registrar_and_the_hook_installer_take_the_option(self):
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--statusline", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("statusLine -> context_statusline.py", json.loads(applied.stdout.strip().splitlines()[-1])["changes"])
        self.assertIn("context_statusline.py", self.config()["statusLine"]["command"])
        again = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--statusline", "--apply")
        self.assertIn("no changes", again.stdout)
        named = self.tmp / "settings.json"
        named.write_text(json.dumps({"statusLine": {"type": "command", "command": "echo mine"}}), encoding="utf-8")
        installed = self.run_tool(INSTALLER, "--hook-root", str(HOOK_DIR), "--target", "claude", "--claude-settings", str(named), "--statusline")
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.assertIn("a status line is already configured and is left as it is", installed.stdout)
        self.assertEqual(json.loads(named.read_text(encoding="utf-8"))["statusLine"]["command"], "echo mine")
        plain = self.tmp / "plain.json"
        self.run_tool(INSTALLER, "--hook-root", str(HOOK_DIR), "--target", "claude", "--claude-settings", str(plain))
        self.assertNotIn("statusLine", json.loads(plain.read_text(encoding="utf-8")), "never without the option")

    def test_the_verifier_says_what_the_advice_would_be_measured_by(self):
        self.settings.parent.mkdir(parents=True)
        registered = repair.plan({}, "claude", sys.executable)[0]
        self.settings.write_text(json.dumps(registered), encoding="utf-8")
        none = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertIn("note: context pressure: no usage source, so a run is not advised as the context window fills", none.stdout)
        self.assertIn("status: REGISTERED", none.stdout)
        by_window = self.run_tool("verify_registration.py", "--host", "claude", SUPREMETEAM_CONTEXT_WINDOW="200000")
        self.assertIn("read from the session transcript against SUPREMETEAM_CONTEXT_WINDOW", by_window.stdout)
        self.settings.write_text(json.dumps(repair.plan_statusline(registered, "claude", sys.executable)[0]), encoding="utf-8")
        with_sidecar = self.run_tool("verify_registration.py", "--host", "claude")
        self.assertIn("the status-line sidecar (context_statusline.py) is configured", with_sidecar.stdout)
        self.assertEqual(with_sidecar.returncode, 0)


if __name__ == "__main__":
    unittest.main()
