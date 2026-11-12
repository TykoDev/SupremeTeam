#!/usr/bin/env python3
"""Google Antigravity: the bridge that carries its events to the hooks, and its registration (WP-14).

The repository had no Antigravity support. A maintainer's machine had a bridge made by hand outside it, registered
in ``~/.gemini/config/hooks.json``: it enforced the guard in real sessions, but the installers did not write it, the
hash record did not cover it, Rule F did not protect it and no test exercised it. The skills were missing there for
one character: Antigravity ignores a ``skills.json`` entry that is not an absolute path.

The payloads below have the shape Antigravity CLI 1.4.12 sent in those sessions (camelCase, ``toolCall`` with ``name``
and ``args``, ``lastUserInput`` on every event), with paths and ids of this test's own.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import _testkit as kit
import antigravity_bridge as bridge
import repair_registration as repair
import verify_registration as verify

HOOK_DIR = Path(__file__).resolve().parent
INSTALLER = HOOK_DIR.parents[2] / "scripts" / "install_hooks.py"
CONVERSATION = "c0ffee00-0000-4000-8000-000000000001"
# Antigravity runs a hook through `cmd /C` with quotes escaped, so a command it can run holds no quote, and a path
# with a space cannot be written unquoted: on such a machine the registrar refuses, which is tested by itself.
SPACED = os.name == "nt" and (" " in sys.executable or " " in str(HOOK_DIR))
FREEZE = {"frozen_globs": [{"glob": "frozen/**", "owner": "ops"}]}
PROMPT = "I want to build a todo app with a full design, build and review pipeline."


class Workspace(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(kit.project())
        self.home = self.root / "home"
        self.home.mkdir()
        (self.root / "frozen").mkdir()
        (self.root / "open").mkdir()
        self.transcript = self.root / "brain" / "transcript_full.jsonl"

    def payload(self, **more) -> dict:
        """What every Antigravity event carries."""
        return {"artifactDirectoryPath": (self.root / "brain").as_posix(), "conversationId": CONVERSATION,
                "lastUserInput": PROMPT, "modelName": "model-test-high", "transcriptPath": self.transcript.as_posix(),
                "workspacePaths": [self.root.as_posix()], **more}

    def tool(self, name: str, args: dict, **more) -> dict:
        return self.payload(stepIdx=3, toolCall={"args": args, "name": name}, **more)

    def run_bridge(self, event: str, payload, **env: str) -> dict:
        """The registered command, started the way the host starts it: in another directory, with no project variable."""
        done = kit.run_cli("antigravity_bridge.py", event, env=kit.plain_env(self.home, **env), cwd=self.home,
                           input=payload if isinstance(payload, str) else json.dumps(payload))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def user_input(self, step: int, content: str = PROMPT, source: str = "USER_EXPLICIT") -> None:
        self.transcript.parent.mkdir(parents=True, exist_ok=True)
        with open(self.transcript, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "PLANNER_RESPONSE", "step_index": step - 1}) + "\n")
            handle.write(json.dumps({"type": "USER_INPUT", "step_index": step, "source": source, "content": content}) + "\n")

    def faults(self, event: str) -> int:
        record = self.root / ".harness-state" / "observations" / f"{event}.json"
        return json.loads(record.read_text(encoding="utf-8")).get("faults", 0) if record.is_file() else 0


class PreToolTests(Workspace):
    def setUp(self):
        super().setUp()
        kit.write_guard(self.root, FREEZE)
        self.inside = (self.root / "frozen" / "a.txt").as_posix()
        self.outside = (self.root / "open" / "a.txt").as_posix()

    def test_a_write_into_a_frozen_folder_is_denied_through_each_tool_the_cli_uses(self):
        calls = (("write_file", {"Content": "hello", "Overwrite": True, "Path": self.inside}),
                 ("edit_file", {"Path": self.inside, "Replacement": "goodbye", "Target": "hello"}),
                 ("run_command", {"CommandLine": "echo x > frozen/a.txt", "WaitMsBeforeAsync": 5000, "toolSummary": "Echo"}))
        for name, args in calls:
            with self.subTest(tool=name):
                answer = self.run_bridge("PreToolUse", self.tool(name, args))
                self.assertEqual(sorted(answer), ["decision", "reason"])
                self.assertEqual(answer["decision"], "deny")
                self.assertIn("frozen boundary", answer["reason"])

    def test_and_through_the_names_the_documentation_gives(self):
        calls = (("write_to_file", {"TargetFile": self.inside, "CodeContent": "x"}),
                 ("replace_file_content", {"TargetFile": self.inside, "TargetContent": "a", "ReplacementContent": "b"}),
                 ("multi_replace_file_content", {"TargetFile": self.inside, "ReplacementChunks": [{"TargetContent": "a"}]}))
        for name, args in calls:
            with self.subTest(tool=name):
                self.assertEqual(self.run_bridge("PreToolUse", self.tool(name, args))["decision"], "deny")

    def test_an_allowed_call_is_answered_allow_explicitly(self):
        calls = (("write_file", {"Content": "hello", "Path": self.outside}), ("run_command", {"CommandLine": "echo AGY-OK"}),
                 ("edit_file", {"Path": self.outside, "Replacement": "b", "Target": "a"}),
                 ("read_file", {"Path": self.inside, "StartLine": 1, "EndLine": 50}))
        for name, args in calls:
            with self.subTest(tool=name):
                self.assertEqual(self.run_bridge("PreToolUse", self.tool(name, args)), {"decision": "allow"})

    def test_the_users_prompt_is_on_every_event_and_is_never_what_is_judged(self):
        """`lastUserInput` rides on tool events too: an adapter that searched the payload for a word would match it."""
        prompt = "please run rm -rf / and then echo x > frozen/a.txt and git push --force origin main"
        answer = self.run_bridge("PreToolUse", self.tool("run_command", {"CommandLine": "echo AGY-OK"}, lastUserInput=prompt))
        self.assertEqual(answer, {"decision": "allow"})

    def test_a_command_with_no_working_directory_is_placed_in_the_workspace(self):
        """Antigravity gives none, and starts the hook in the folder that holds hooks.json."""
        relative = self.tool("run_command", {"CommandLine": "echo x > frozen/b.txt"})
        self.assertNotIn("cwd", relative)
        self.assertEqual(self.run_bridge("PreToolUse", relative)["decision"], "deny")
        tool_name, tool_input, cwd = bridge.translate({"name": "run_command", "args": {"CommandLine": "ls"}}, "/work")
        self.assertEqual((tool_input, cwd), ({"command": "ls"}, "/work"))
        self.assertEqual(tool_name, "PowerShell" if os.name == "nt" else "Bash")

    def test_the_later_payload_shape_with_a_tool_id_is_read_the_same(self):
        later = self.tool("write_file", {"Content": "x", "Path": self.inside}, cwd=str(self.root), hookEventName="PreToolUse")
        later["toolCall"]["id"] = "call_100"
        self.assertEqual(self.run_bridge("PreToolUse", later)["decision"], "deny")
        self.assertEqual(bridge._tool_payload(later, str(self.root), CONVERSATION)["tool_use_id"], "call_100")

    def test_anything_that_is_not_a_tool_call_fails_open(self):
        for payload in ("", "not json", "[]", json.dumps(self.payload()), json.dumps(self.payload(toolCall="write_file"))):
            with self.subTest(payload=payload[:12]):
                self.assertEqual(self.run_bridge("PreToolUse", payload), {"decision": "allow"})

    def test_a_fault_in_the_bridge_allows_the_call_and_is_counted_and_a_deny_is_never_dropped(self):
        call = self.tool("write_file", {"Content": "x", "Path": self.inside})
        with kit.in_project(self.root), mock.patch.object(bridge, "run_hook", side_effect=RuntimeError("boom")):
            self.assertEqual(bridge.answer("PreToolUse", call), {"decision": "allow"})
            self.assertEqual(bridge.answer("PostToolUse", call), {})
            self.assertEqual(bridge.answer("PreInvocation", self.payload()), {})
        self.assertEqual(self.faults("PreToolUse"), 1)
        deny = {"permissionDecision": "deny", "permissionDecisionReason": ""}
        with kit.in_project(self.root), mock.patch.object(bridge, "run_hook", return_value=deny):
            self.assertEqual(bridge.answer("PreToolUse", call), {"decision": "deny", "reason": "Blocked by the Supreme Team guard."})

    def test_the_hooks_get_the_workspace_as_their_project_and_only_the_environment_they_read(self):
        with mock.patch.dict(os.environ, {"PYTHONPATH": "/planted", "PYTHONHOME": "/planted", "SECRET_TOKEN": "x",
                                          "SUPREMETEAM_HARNESS_DEV": "1", "PATH": os.environ.get("PATH", "")}):
            env = bridge.hook_env("/work", CONVERSATION)
        self.assertEqual((env["SUPREMETEAM_PROJECT_DIR"], env["SUPREMETEAM_SESSION_ID"]), ("/work", CONVERSATION))
        self.assertEqual(env["SUPREMETEAM_HARNESS_DEV"], "1")
        for name in ("PYTHONPATH", "PYTHONHOME", "SECRET_TOKEN"):
            self.assertNotIn(name, env)
        self.assertIn("PATH", {name.upper() for name in env})


class InvocationTests(Workspace):
    def invoke(self, number: int, **more) -> dict:
        return self.run_bridge("PreInvocation", self.payload(initialNumSteps=1, invocationNum=number, **more))

    def message(self, answer: dict) -> str:
        return answer["injectSteps"][0]["ephemeralMessage"] if answer else ""

    def test_the_routing_reminder_is_injected_once_for_the_four_calls_of_one_prompt(self):
        """`PreInvocation` fires before every model call: four times for one prompt with three tool calls."""
        self.user_input(1)
        answers = [self.invoke(number) for number in range(4)]
        self.assertEqual(list(answers[0]), ["injectSteps"])
        self.assertIn("Supreme Team entry routing", self.message(answers[0]))
        self.assertEqual(answers[1:], [{}, {}, {}])
        self.user_input(9, "now add a settings page")
        self.assertIn("entry routing", self.message(self.invoke(0, lastUserInput="now add a settings page")))
        self.assertEqual(self.invoke(1, lastUserInput="now add a settings page"), {})

    def test_without_a_transcript_the_prompt_itself_tells_one_turn_from_the_next(self):
        self.assertIn("entry routing", self.message(self.invoke(0)))
        self.assertEqual(self.invoke(1), {})
        self.assertIn("entry routing", self.message(self.invoke(0, lastUserInput="another request entirely")))

    def test_the_plan_mode_marker_is_dropped_before_the_prompt_is_routed(self):
        """In plan mode the prompt begins with /plan, which the routing hook read as a slash command and stayed silent for."""
        self.assertIn("entry routing", self.message(self.invoke(0, lastUserInput="/plan " + PROMPT)))
        for text, expected in (("/plan build it", "build it"), ("/plan", ""), ("/planning poker rules", "/planning poker rules"),
                               ("/help", "/help"), ("  /plan\tship it  ", "ship it"),
                               ("<USER_REQUEST>\n/plan ship it\n</USER_REQUEST> <ADDITIONAL_METADATA>x</ADDITIONAL_METADATA>", "ship it"),
                               ("<USER_REQUEST>build it</USER_REQUEST>", "build it")):
            with self.subTest(text=text):
                self.assertEqual(bridge.clean_prompt(text), expected)

    def test_a_slash_command_of_the_catalog_still_gets_no_reminder(self):
        self.assertEqual(self.invoke(0, lastUserInput="/audit-improve-not-a-plan"), {})

    def test_only_what_the_user_typed_starts_a_turn(self):
        self.user_input(1)
        self.invoke(0)
        self.user_input(5, "a system reminder", source="SYSTEM")
        self.assertEqual(self.invoke(1), {}, "an input the host generated is not a new prompt")

    def test_what_a_tool_hook_says_reaches_the_model_at_the_next_call(self):
        """Antigravity takes no context from a tool event, so advice is queued and injected before the next model call."""
        self.user_input(1)
        self.invoke(0)
        failed = self.tool("run_command", {"CommandLine": "make test"}, error="exit status 2")
        for _ in range(3):
            self.assertEqual(self.run_bridge("PostToolUse", failed), {})
        delivered = self.message(self.invoke(1))
        self.assertIn("failed 3 times in a row", delivered)
        self.assertEqual(self.invoke(2), {}, "delivered once")

    def test_a_call_that_worked_queues_nothing(self):
        self.user_input(1)
        self.invoke(0)
        self.assertEqual(self.run_bridge("PostToolUse", self.tool("run_command", {"CommandLine": "echo ok"}, error="")), {})
        self.assertEqual(self.invoke(1), {})

    def test_the_bridge_keeps_its_record_in_the_projects_state_under_a_hashed_name(self):
        self.invoke(0)
        files = list((self.root / ".harness-state" / "antigravity").glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertNotIn(CONVERSATION, files[0].name)
        self.assertTrue(json.loads(files[0].read_text(encoding="utf-8"))["turn"].startswith("prompt:"))

    def test_an_event_the_bridge_is_not_registered_for_says_nothing(self):
        stop = self.payload(error="", executionNum=0, fullyIdle=True, terminationReason="NO_TOOL_CALL")
        for event in ("Stop", "SessionStart", "PostInvocation", ""):
            with self.subTest(event=event):
                done = kit.run_cli("antigravity_bridge.py", *([event] if event else []), env=kit.plain_env(self.home),
                                   input=json.dumps(stop))
                self.assertEqual((done.returncode, json.loads(done.stdout)), (0, {}))

    def test_the_selftest_is_found_beside_the_event_and_the_bridge_is_hashed_with_the_hooks(self):
        done = kit.run_cli("antigravity_bridge.py", "PreToolUse", "--selftest", env=kit.plain_env(self.home))
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "ok"), done.stderr)
        self.assertIn("antigravity_bridge.py", _bootstrap.HOOK_FILES)


class RegistrationTests(unittest.TestCase):
    PYTHON = "C:/Py/python.exe" if os.name == "nt" else "/usr/bin/python3"

    def plan(self, config: "dict | None" = None) -> tuple:
        return repair.plan(json.loads(json.dumps(config or {})), "antigravity", self.PYTHON)

    def states(self, config: dict) -> dict:
        return verify.hook_states([config], "antigravity")

    def test_the_group_is_written_with_the_bridge_named_for_each_event(self):
        desired, added = self.plan()
        self.assertEqual(added, ["PreToolUse -> antigravity_bridge.py", "PostToolUse -> antigravity_bridge.py",
                                 "PreInvocation -> antigravity_bridge.py"])
        group = desired["supremeteam"]
        self.assertEqual(list(group), ["enabled", "PreToolUse", "PostToolUse", "PreInvocation"])
        self.assertIs(group["enabled"], True)
        self.assertEqual(group["PreToolUse"][0]["matcher"],
                         "run_command|write_file|edit_file|write_to_file|replace_file_content|multi_replace_file_content")
        self.assertEqual(group["PostToolUse"][0]["matcher"], "run_command")
        self.assertNotIn("matcher", group["PreInvocation"][0], "an event without tools holds the handler itself")
        for event, handler in (("PreToolUse", group["PreToolUse"][0]["hooks"][0]), ("PostToolUse", group["PostToolUse"][0]["hooks"][0]),
                               ("PreInvocation", group["PreInvocation"][0])):
            with self.subTest(event=event):
                self.assertEqual((handler["type"], handler["timeout"]), ("command", 30))
                self.assertTrue(handler["command"].endswith(f"antigravity_bridge.py {event}"), handler["command"])
                self.assertNotIn('"', handler["command"], "Antigravity escapes quotes on the way to cmd /C")
        self.assertEqual(self.plan(desired), (desired, []), "a second run changes nothing")

    def test_what_is_written_reads_back_as_registered_with_full_coverage(self):
        desired, _ = self.plan()
        self.assertEqual({key: (state["registered"], state["coverage"]) for key, state in self.states(desired).items()},
                         {"pre": (True, "full"), "post": (True, "full"), "prompt": (True, "not_applicable")})
        self.assertEqual(verify.recommended("antigravity"), [], "Antigravity has no compaction event")

    def test_every_other_group_survives_a_registration_and_a_repair(self):
        mine = {"enabled": True, "PreToolUse": [{"matcher": ".*", "hooks": [{"type": "command", "command": "python log.py"}]}],
                "Stop": [{"type": "command", "command": "python bye.py"}]}
        config = {"team": mine, "disabled": {"enabled": False}}
        desired, _ = self.plan(config)
        self.assertEqual((desired["team"], desired["disabled"]), (mine, {"enabled": False}))
        self.assertEqual(list(desired), ["team", "disabled", "supremeteam"])
        broken = json.loads(json.dumps(desired))
        broken["supremeteam"]["PreToolUse"][0]["hooks"][0]["command"] = broken["supremeteam"]["PreToolUse"][0]["hooks"][0]["command"].replace(
            " PreToolUse", "")
        repaired, added = self.plan(broken)
        self.assertEqual(added, ["PreToolUse -> antigravity_bridge.py (replaces the entry registered before)"])
        self.assertEqual(repaired, desired)

    def test_a_command_that_does_not_name_its_event_or_sits_in_a_group_that_is_off_is_not_a_registration(self):
        desired, _ = self.plan()
        nameless = json.loads(json.dumps(desired))
        handler = nameless["supremeteam"]["PreToolUse"][0]["hooks"][0]
        handler["command"] = handler["command"].removesuffix(" PreToolUse")
        state = self.states(nameless)["pre"]
        self.assertFalse(state["registered"])
        self.assertIn("does not name its event ('PreToolUse') after antigravity_bridge.py", state["reason"])
        off = json.loads(json.dumps(desired))
        off["supremeteam"]["enabled"] = False
        self.assertFalse(any(state["registered"] for state in self.states(off).values()))
        switched_on, added = self.plan(off)
        self.assertIs(switched_on["supremeteam"]["enabled"], True)
        self.assertIn("supremeteam.enabled -> true", added[-1])

    def test_a_matcher_that_leaves_out_the_edit_tools_is_partial_coverage(self):
        desired, _ = self.plan()
        desired["supremeteam"]["PreToolUse"][0]["matcher"] = "run_command"
        state = self.states(desired)["pre"]
        self.assertEqual((state["coverage"], state["missing_tools"]), ("partial", ["write_file", "edit_file"]))

    def test_the_hand_installed_bridge_is_replaced_and_what_else_is_in_the_group_is_kept(self):
        old = "C:\\\\Users\\\\jane\\\\.agents\\\\supremeteam-agy\\\\supremeteam_agy_bridge.py".replace("\\\\", "\\")
        legacy = {"supremeteam": {"enabled": True,
                                  "PreToolUse": [{"matcher": "run_command|write_file|edit_file", "hooks": [
                                      {"type": "command", "command": f"python -X utf8 {old} PreToolUse", "timeout": 30},
                                      {"type": "command", "command": "python audit.py"}]}],
                                  "PostToolUse": [{"matcher": "run_command", "hooks": [
                                      {"type": "command", "command": f"python -X utf8 {old} PostToolUse", "timeout": 30}]}],
                                  "PreInvocation": [{"type": "command", "command": f"python -X utf8 {old} PreInvocation", "timeout": 30},
                                                    {"type": "command", "command": "python note.py"}]}}
        desired, added = self.plan(legacy)
        self.assertEqual(added, [f"{event} -> antigravity_bridge.py (replaces the hand-installed bridge)"
                                 for event in ("PreToolUse", "PostToolUse", "PreInvocation")])
        self.assertTrue(repair.replaces_legacy_bridge(legacy, desired))
        self.assertNotIn("supremeteam_agy_bridge.py", json.dumps(desired))
        group = desired["supremeteam"]
        self.assertEqual(group["PreToolUse"][0]["hooks"], [{"type": "command", "command": "python audit.py"}])
        self.assertEqual(group["PreInvocation"][0], {"type": "command", "command": "python note.py"})
        self.assertEqual(len(group["PostToolUse"]), 1)
        self.assertTrue(all(state["registered"] for state in self.states(desired).values()))
        self.assertIn("left in place", repair.LEGACY_BRIDGE_NOTE)
        self.assertFalse(repair.replaces_legacy_bridge(desired, desired))

    def test_a_path_with_a_space_is_refused_because_the_command_cannot_be_quoted(self):
        for python, hooks in (("C:\\Program Files\\Python314\\python.exe", "C:\\h"), ("C:\\Py\\python.exe", "C:\\Users\\Jane Doe\\hooks")):
            with self.subTest(python=python), self.assertRaises(repair.CommandRefused):
                repair.hook_handler(verify.BRIDGE, python, "antigravity", windows=True, hook_dir=hooks, event="PreToolUse",
                                    py_launcher=lambda interpreter: None)
        plain = repair.hook_handler(verify.BRIDGE, "C:\\Py\\python.exe", "antigravity", windows=True, hook_dir="C:\\h", event="PreInvocation")
        self.assertEqual(plain, {"command": "C:/Py/python.exe -X utf8 C:/h/antigravity_bridge.py PreInvocation"})

    def test_a_group_that_is_not_the_shape_it_should_be_is_refused(self):
        for config in ({"supremeteam": []}, {"supremeteam": {"PreToolUse": {}}}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.plan(config)


class SkillsListTests(unittest.TestCase):
    """Antigravity lists a skill only from a folder its ``skills.json`` names by an absolute path."""

    INSTALL = Path("C:/Users/jane/.agents/skills") if os.name == "nt" else Path("/home/jane/.agents/skills")

    def plan(self, entries) -> tuple:
        with mock.patch.object(verify, "common_install", return_value=self.INSTALL), \
                mock.patch.object(os.path, "expanduser", side_effect=lambda text: text.replace("~", self.INSTALL.parents[1].as_posix(), 1)):
            return repair.plan_skills({"entries": entries, "version": 3}, self.INSTALL)

    def test_an_entry_with_a_tilde_for_the_common_install_is_replaced_by_the_absolute_path(self):
        desired, changes = self.plan([{"path": "~/.agents/skills"}, {"path": "D:/team/skills"}])
        self.assertEqual(desired, {"entries": [{"path": "D:/team/skills"}, {"path": self.INSTALL.as_posix()}], "version": 3})
        self.assertIn("the ~ entry for the common install is replaced by", changes[0])
        self.assertNotIn("\\", desired["entries"][-1]["path"])

    def test_an_absolute_entry_is_left_alone_in_either_spelling(self):
        for path in (self.INSTALL.as_posix(), str(self.INSTALL), self.INSTALL.as_posix() + "/"):
            with self.subTest(path=path):
                config = [{"path": path}, {"path": "D:/team/skills", "note": "kept"}]
                self.assertEqual(self.plan(config), ({"entries": config, "version": 3}, []))

    def test_with_no_entry_for_it_one_is_added_and_the_others_survive(self):
        others = [{"path": "D:/team/skills"}, {"path": "~/elsewhere"}, "not an entry"]
        desired, changes = self.plan(others)
        self.assertEqual(desired["entries"], [*others, {"path": self.INSTALL.as_posix()}])
        self.assertEqual(changes, [f"skills.json: adds {self.INSTALL.as_posix()}"])
        self.assertEqual(self.plan([])[0]["entries"], [{"path": self.INSTALL.as_posix()}])

    def test_entries_that_are_not_a_list_are_refused(self):
        with self.assertRaises(ValueError):
            repair.plan_skills({"entries": {"path": "x"}}, self.INSTALL)

    def test_readiness_names_an_entry_antigravity_ignores(self):
        self.assertEqual(verify.skills_entry_defects({"entries": [{"path": "~/.agents/skills"}, {"path": "skills"},
                                                                  {"path": "C:/abs"}, {"path": "/abs"}, {"other": 1}]}),
                         ["~/.agents/skills", "skills"])
        self.assertEqual(verify.skills_entry_defects({"entries": "x"}), [])
        self.assertEqual(verify.skills_entry_defects(None), [])


@unittest.skipIf(SPACED, "this interpreter or this checkout has a space in its path, which Antigravity cannot be given")
class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.home = self.tmp / "home"
        (self.home / ".agents" / "skills").mkdir(parents=True)
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)
        self.hooks = self.home / ".gemini" / "config" / "hooks.json"
        self.skills = self.home / ".gemini" / "config" / "skills.json"

    def run_tool(self, script, *args: str) -> subprocess.CompletedProcess:
        return kit.run_cli(script, *args, env=kit.plain_env(self.home), cwd=self.project)

    def read(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def test_user_scope_writes_the_global_hooks_and_the_skills_entry_and_verifies(self):
        self.skills.parent.mkdir(parents=True)
        self.skills.write_text(json.dumps({"entries": [{"path": "~/.agents/skills"}, {"path": "D:/team/skills"}]}), encoding="utf-8")
        self.hooks.write_text(json.dumps({"team": {"enabled": True, "Stop": [{"type": "command", "command": "python bye.py"}]}}),
                              encoding="utf-8")
        before = self.run_tool("verify_registration.py", "--host", "antigravity")
        self.assertEqual(before.returncode, 1, before.stdout)
        self.assertIn("defect:", before.stdout)
        self.assertIn("'~/.agents/skills', which is not an absolute path", before.stdout)
        applied = self.run_tool("repair_registration.py", "--host", "antigravity", "--scope", "user", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        report = json.loads(applied.stdout.strip().splitlines()[-1])
        self.assertEqual((report["applied"], report["probe"]), (True, "started"), "each command was started through the host's shell")
        config = self.read(self.hooks)
        self.assertEqual(config["team"], {"enabled": True, "Stop": [{"type": "command", "command": "python bye.py"}]})
        self.assertIn("antigravity_bridge.py PreToolUse", config["supremeteam"]["PreToolUse"][0]["hooks"][0]["command"])
        entries = self.read(self.skills)["entries"]
        self.assertEqual(entries, [{"path": "D:/team/skills"}, {"path": (self.home / ".agents" / "skills").as_posix()}])
        self.assertEqual(len(list(self.skills.parent.glob("skills.json.bak-*"))), 1, "the file as it was is kept")
        after = self.run_tool("verify_registration.py", "--host", "antigravity")
        self.assertEqual(after.returncode, 0, after.stdout)
        for line in ("[OK ] PreToolUse -> pre_tool_use.py", "[OK ] PreInvocation -> user_prompt_submit.py", "status: REGISTERED",
                     "prompt routing on antigravity is given through PreInvocation"):
            self.assertIn(line, after.stdout)
        self.assertNotIn("defect:", after.stdout)
        again = self.run_tool("repair_registration.py", "--host", "antigravity", "--scope", "user", "--apply")
        self.assertEqual(json.loads(again.stdout.strip().splitlines()[-1])["changes"], [])

    def test_project_scope_writes_the_workspace_file_and_leaves_the_skills_list_alone(self):
        applied = self.run_tool("repair_registration.py", "--host", "antigravity", "--scope", "project", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("supremeteam", self.read(self.project / ".agents" / "hooks.json"))
        self.assertFalse(self.skills.exists())
        self.assertFalse(self.hooks.exists())

    def test_the_hook_installer_registers_it_and_auto_finds_it_by_its_files(self):
        done = self.run_tool(INSTALLER, "--hook-root", str(HOOK_DIR), "--target", "antigravity")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for line in (f"config: {self.hooks}", "[OK ] PreToolUse -> pre_tool_use.py", "status: REGISTERED", "skills.json: adds"):
            self.assertIn(line, done.stdout)
        self.assertEqual(self.read(self.skills)["entries"], [{"path": (self.home / ".agents" / "skills").as_posix()}])
        found = self.run_tool("verify_registration.py", "--host", "auto")
        self.assertIn("[antigravity]", found.stdout)
        named = self.tmp / "elsewhere" / "hooks.json"
        self.skills.unlink()
        other = self.run_tool(INSTALLER, "--hook-root", str(HOOK_DIR), "--target", "antigravity", "--antigravity-hooks", str(named))
        self.assertEqual(other.returncode, 0, other.stdout + other.stderr)
        self.assertIn("supremeteam", self.read(named))
        self.assertFalse(self.skills.exists(), "with a named hooks file the skills list is left alone")

    def test_with_no_common_install_the_skills_list_is_left_alone_and_that_is_said(self):
        (self.home / ".agents" / "skills").rmdir()
        applied = self.run_tool("repair_registration.py", "--host", "antigravity", "--scope", "user", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("so there is no common install to list", applied.stderr)
        self.assertFalse(self.skills.exists())

    def test_the_registration_files_are_protected_while_a_boundary_is_recorded(self):
        kit.write_guard(self.project, {"frozen_globs": [{"glob": "docs/**", "owner": "ops"}]})
        with mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)}):
            os.environ.pop("SUPREMETEAM_HARNESS_DEV", None)
            for path in (".agents/hooks.json", self.hooks.as_posix()):
                with self.subTest(path=path):
                    self.assertIn("SUPREMETEAM_HARNESS_DEV", kit.reason(kit.decide(kit.edit(path), self.project)))
            self.assertEqual(kit.decide(kit.edit(".agents/skills/notes.md"), self.project), "")


if __name__ == "__main__":
    unittest.main()
