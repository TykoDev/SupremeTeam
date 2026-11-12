#!/usr/bin/env python3
"""A registered hook command has to start in the shell its host hands it to (WP-02, issue 6).

The command the installer wrote on Windows, ``C:\\...\\python.exe -X utf8 "C:\\...\\pre_tool_use.py"``, never started
in Claude Code, which runs hooks through Git Bash, and readiness still reported the guard as live: the verifier split
the command without shell rules, and no test ran it through a shell. This module holds the three layers that close
that:

* the four command forms and the launcher choice, as pure functions of their inputs (any platform);
* ``verify_registration.shell_defects``, the static reading of a command against a shell's rules, and its agreement
  with what the real shell does;
* the forms through every real shell found on the machine: Git Bash, PowerShell 7, Windows PowerShell 5.1, ``cmd``
  and ``cmd /C`` with one escaped argument (Antigravity) on Windows, ``sh`` on POSIX. A virtual environment created in
  a directory with a space gives a spaced interpreter without installing anything.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap
import _testkit as kit
import repair_registration as repair
import verify_registration as verify

HOOK_DIR = Path(__file__).resolve().parent
WINDOWS = os.name == "nt"
SCRIPTS = [script for _, script in verify.REQUIRED]
# Every hook the registrar writes for Claude Code: the required three, then the recommended ones (WP-11).
WRITTEN = [script for _, script in repair.hook_events("claude")]
RECOMMENDED_EVENTS = {event: 1 for _, _, event in verify.recommended("claude")}

JANE = r"C:\Users\Jane\AppData\Local\Programs\Python\Python314\python.exe"
SPACED = r"C:\Program Files\Python314\python.exe"
HOOKS = r"C:\Users\Jane Doe\.agents\skills\harness\hooks"
PLAIN_HOOKS = r"C:\h"


def no_launcher(interpreter: str) -> None:
    return None


def py314(interpreter: str) -> str:
    return "py -3.14"


def handler(python: str, host: str = "claude", hooks: str = HOOKS, launcher=no_launcher) -> dict:
    return repair.hook_handler("pre_tool_use.py", python, host, windows=True, hook_dir=hooks, py_launcher=launcher)


class PathShapeTests(unittest.TestCase):
    """Only a Windows-shaped path is converted: a backslash is a legal character in a POSIX file name."""

    def test_drive_and_unc_paths_get_forward_slashes(self):
        self.assertEqual(repair.forward_slashes(JANE), "C:/Users/Jane/AppData/Local/Programs/Python/Python314/python.exe")
        self.assertEqual(repair.forward_slashes(r"c:\Program Files\x"), "c:/Program Files/x")
        self.assertEqual(repair.forward_slashes(r"\\host\share\tools\py.exe"), "//host/share/tools/py.exe")
        self.assertEqual(repair.forward_slashes("C:/already/forward"), "C:/already/forward")

    def test_a_posix_path_keeps_its_backslash(self):
        for path in ("/opt/odd\\name/python3", "relative\\name", "python3", "py"):
            with self.subTest(path=path):
                self.assertEqual(repair.forward_slashes(path), path)

    def test_an_extended_length_prefix_is_dropped_from_a_drive_path_and_refused_otherwise(self):
        self.assertEqual(repair.forward_slashes("\\\\?\\C:\\Users\\Jane\\python.exe"), "C:/Users/Jane/python.exe")
        for path in ("\\\\?\\UNC\\host\\share\\python.exe", "\\\\?\\Volume{0000}\\python.exe", "\\\\?\\GLOBALROOT\\Device\\x"):
            with self.subTest(path=path), self.assertRaises(repair.CommandRefused) as caught:
                repair.forward_slashes(path)
            self.assertIn("--python", str(caught.exception))


class CommandFormTests(unittest.TestCase):
    """The four forms, each a function of its words."""

    LAUNCHER = ["C:/Py/python.exe", "-X", "utf8"]

    def test_standard_leaves_the_interpreter_unquoted_and_quotes_the_hook(self):
        self.assertEqual(repair.standard_form(self.LAUNCHER, "C:/Users/Jane Doe/h/pre_tool_use.py"),
                         'C:/Py/python.exe -X utf8 "C:/Users/Jane Doe/h/pre_tool_use.py"')
        with self.assertRaises(repair.CommandRefused):
            repair.standard_form(["C:/Program Files/Py/python.exe", "-X", "utf8"], "C:/h/pre_tool_use.py")

    def test_bare_quotes_nothing_and_refuses_a_space(self):
        self.assertEqual(repair.bare_form(self.LAUNCHER, "C:/h/pre_tool_use.py"), "C:/Py/python.exe -X utf8 C:/h/pre_tool_use.py")
        for launcher, script in ((self.LAUNCHER, "C:/Users/Jane Doe/h/pre_tool_use.py"),
                                 (["C:/Program Files/Py/python.exe"], "C:/h/pre_tool_use.py")):
            with self.subTest(script=script), self.assertRaises(repair.CommandRefused):
                repair.bare_form(launcher, script)

    def test_call_begins_with_the_call_operator_and_quotes_both_paths(self):
        self.assertEqual(repair.call_form(["C:/Program Files/Py/python.exe", "-X", "utf8"], "C:/h/pre_tool_use.py"),
                         '& "C:/Program Files/Py/python.exe" -X utf8 "C:/h/pre_tool_use.py"')

    def test_parts_keeps_the_interpreter_apart_from_its_arguments(self):
        self.assertEqual(repair.parts_form(["C:/Program Files/Py/python.exe", "-X", "utf8"], "C:/h/pre_tool_use.py"),
                         {"command": "C:/Program Files/Py/python.exe", "args": ["-X", "utf8", "C:/h/pre_tool_use.py"]})


def host_suffix(host: str) -> str:
    """The arguments the registrar appends for a host whose hooks have to answer in another shape (WP-08)."""
    return " --host copilot" if host == "copilot" else ""


class LauncherChoiceTests(unittest.TestCase):
    """What each host is given on Windows, for the paths a real machine holds."""

    def test_an_interpreter_without_a_space_is_named_by_its_path(self):
        expected = ('C:/Users/Jane/AppData/Local/Programs/Python/Python314/python.exe -X utf8 '
                    '"C:/Users/Jane Doe/.agents/skills/harness/hooks/pre_tool_use.py"')
        for host in ("claude", "codex", "cursor", "copilot"):
            with self.subTest(host=host):
                self.assertEqual(handler(JANE, host), {"command": expected + host_suffix(host)})

    def test_the_py_launcher_stands_in_for_a_spaced_interpreter_when_it_starts_the_same_one(self):
        for host in ("claude", "codex", "cursor", "copilot"):
            with self.subTest(host=host):
                self.assertEqual(handler(SPACED, host, launcher=py314)["command"],
                                 'py -3.14 -X utf8 "C:/Users/Jane Doe/.agents/skills/harness/hooks/pre_tool_use.py"' + host_suffix(host))

    def test_a_launcher_named_by_the_operator_is_used_as_given(self):
        self.assertEqual(handler("py -3", "codex")["command"], 'py -3 -X utf8 "C:/Users/Jane Doe/.agents/skills/harness/hooks/pre_tool_use.py"')
        self.assertEqual(handler("py -3.13 -X utf8", "claude")["command"].count("utf8"), 1)

    def test_with_no_launcher_each_host_gets_its_fallback(self):
        hook = "C:/Users/Jane Doe/.agents/skills/harness/hooks/pre_tool_use.py"
        self.assertEqual(handler(SPACED, "claude"), {"command": "C:/Program Files/Python314/python.exe", "args": ["-X", "utf8", hook]})
        self.assertEqual(handler(SPACED, "copilot"),
                         {"command": f'& "C:/Program Files/Python314/python.exe" -X utf8 "{hook}" --host copilot'})
        for host in ("codex", "cursor", "antigravity"):
            with self.subTest(host=host), self.assertRaises(repair.CommandRefused) as caught:
                handler(SPACED, host)
            # A refusal names the two ways out.
            self.assertIn("hold no space", str(caught.exception))
            self.assertIn("--python", str(caught.exception))

    def test_antigravity_gets_the_bare_form_and_refuses_any_space(self):
        self.assertEqual(handler(JANE, "antigravity", hooks=PLAIN_HOOKS)["command"],
                         "C:/Users/Jane/AppData/Local/Programs/Python/Python314/python.exe -X utf8 C:/h/pre_tool_use.py")
        self.assertNotIn('"', handler("py -3", "antigravity", hooks=PLAIN_HOOKS)["command"])
        with self.assertRaises(repair.CommandRefused):
            handler(JANE, "antigravity", hooks=HOOKS)

    def test_a_unc_root_and_an_extended_root_are_spelled_with_forward_slashes(self):
        unc = handler(r"\\build\tools\python.exe", hooks=r"\\build\share\skills\harness\hooks")
        self.assertEqual(unc["command"], '//build/tools/python.exe -X utf8 "//build/share/skills/harness/hooks/pre_tool_use.py"')
        extended = handler("\\\\?\\C:\\Py\\python.exe", hooks="\\\\?\\C:\\Users\\Jane\\hooks")
        self.assertEqual(extended["command"], 'C:/Py/python.exe -X utf8 "C:/Users/Jane/hooks/pre_tool_use.py"')
        with self.assertRaises(repair.CommandRefused):
            handler(JANE, hooks="\\\\?\\UNC\\build\\share\\hooks")

    def test_options_the_operator_gave_the_interpreter_are_kept(self):
        self.assertEqual(handler(SPACED + " -X dev", "claude")["args"][:4], ["-X", "dev", "-X", "utf8"])
        self.assertTrue(handler(SPACED + " -X dev", "codex", launcher=py314)["command"].startswith("py -3.14 -X dev -X utf8 "))

    def test_command_for_gives_text_and_refuses_the_no_shell_form(self):
        self.assertEqual(repair.command_for("pre_tool_use.py", JANE, "codex", windows=True, hook_dir=PLAIN_HOOKS, py_launcher=no_launcher),
                         'C:/Users/Jane/AppData/Local/Programs/Python/Python314/python.exe -X utf8 "C:/h/pre_tool_use.py"')
        with self.assertRaises(repair.CommandRefused):
            repair.command_for("pre_tool_use.py", SPACED, "claude", windows=True, hook_dir=PLAIN_HOOKS, py_launcher=no_launcher)

    def test_nothing_changes_on_posix(self):
        hooks = "/home/jane doe/.agents/skills/harness/hooks"
        for host in ("claude", "codex", "copilot", "cursor"):
            with self.subTest(host=host):
                self.assertEqual(repair.hook_handler("pre_tool_use.py", "/usr/bin/python3", host, windows=False, hook_dir=hooks),
                                 {"command": f'/usr/bin/python3 -X utf8 "{hooks}/pre_tool_use.py"' + host_suffix(host)})
        spaced = repair.hook_handler("pre_tool_use.py", "/opt/my python/bin/python3", "claude", windows=False, hook_dir=hooks)
        self.assertEqual(spaced["command"], f'"/opt/my python/bin/python3" -X utf8 "{hooks}/pre_tool_use.py"')

    def test_every_written_form_reads_as_this_hook_and_as_free_of_defects(self):
        """What the registrar writes, the verifier accepts: the two cannot disagree about a form."""
        with tempfile.TemporaryDirectory() as tmp:
            hooks = Path(tmp) / "with space" / "harness" / "hooks"
            hooks.mkdir(parents=True)
            (hooks / "pre_tool_use.py").write_text("print('ok')\n", encoding="utf-8")
            cases = [("claude", JANE, no_launcher), ("claude", SPACED, no_launcher), ("claude", SPACED, py314),
                     ("codex", JANE, no_launcher), ("copilot", SPACED, no_launcher), ("cursor", "py -3", no_launcher)]
            with mock.patch.dict(os.environ, {"SUPREMETEAM_HOOK_ROOT": str(hooks)}):
                for host, python, launcher in cases:
                    entry = repair.hook_handler("pre_tool_use.py", python, host, windows=True, hook_dir=str(hooks), py_launcher=launcher)
                    with self.subTest(host=host, python=python, launcher=launcher.__name__):
                        read = verify.analyse(entry["command"], "pre_tool_use.py", verify.handler_tokens(entry))
                        self.assertTrue(read["executable"], (entry, read["reason"]))
                        for shell in verify.host_shells(host, entry, windows=True):
                            self.assertEqual(verify.shell_defects(entry["command"], shell), [], (shell, entry))


OLD_FORM = r'C:\Users\Jane\Python314\python.exe -X utf8 "C:\Users\Jane\.agents\skills\harness\hooks\pre_tool_use.py"'
STANDARD = 'C:/Users/Jane/Python314/python.exe -X utf8 "C:/Users/Jane Doe/.agents/skills/harness/hooks/pre_tool_use.py"'
QUOTED_BOTH = '"C:/Program Files/Py/python.exe" -X utf8 "C:/h/pre_tool_use.py"'
CALL = '& "C:/Program Files/Py/python.exe" -X utf8 "C:/h/pre_tool_use.py"'
BARE = "C:/Py/python.exe -X utf8 C:/h/pre_tool_use.py"


class ShellDefectTests(unittest.TestCase):
    """The static reading: three rules, each a failure seen in a real shell."""

    def test_the_command_the_installer_used_to_write_cannot_start_in_a_posix_shell(self):
        defects = verify.shell_defects(OLD_FORM, "posix")
        self.assertEqual(len(defects), 1)
        self.assertIn("Git Bash", defects[0])
        self.assertIn("forward slashes", defects[0])
        # The same text does start under PowerShell and cmd, which is why it shipped: Codex ran it.
        self.assertEqual(verify.shell_defects(OLD_FORM, "powershell"), [])
        self.assertEqual(verify.shell_defects(OLD_FORM, "cmd"), [])

    def test_an_unquoted_backslash_hook_path_is_a_defect_too(self):
        self.assertTrue(verify.shell_defects(r"python C:\h\pre_tool_use.py", "posix"))
        self.assertEqual(verify.shell_defects(r'python "C:\h\pre_tool_use.py"', "posix"), [],
                         "inside double quotes a POSIX shell keeps these backslashes")
        self.assertTrue(verify.shell_defects('python "\\\\build\\share\\pre_tool_use.py"', "posix"),
                        "a doubled backslash is an escape even inside double quotes")

    def test_the_standard_and_bare_forms_have_no_defect_in_any_shell_that_takes_a_quote(self):
        for shell in ("posix", "powershell", "cmd"):
            with self.subTest(shell=shell):
                self.assertEqual(verify.shell_defects(STANDARD, shell), [])
                self.assertEqual(verify.shell_defects(BARE, shell), [])
        self.assertEqual(verify.shell_defects(BARE, "antigravity"), [])

    def test_powershell_cannot_start_a_command_that_begins_with_a_quote(self):
        self.assertTrue(verify.shell_defects(QUOTED_BOTH, "powershell"))
        self.assertTrue(verify.shell_defects("'C:/Program Files/Py/python.exe' x.py", "powershell"))
        self.assertEqual(verify.shell_defects(CALL, "powershell"), [])
        self.assertEqual(verify.shell_defects(QUOTED_BOTH, "posix"), [], "the same text starts in Git Bash")

    def test_the_call_operator_is_powershell_only(self):
        self.assertTrue(verify.shell_defects(CALL, "posix"))
        self.assertTrue(verify.shell_defects(CALL, "cmd"))

    def test_antigravity_cannot_start_a_command_that_contains_a_quote(self):
        for command in (STANDARD, QUOTED_BOTH, CALL, "C:/Py/python.exe 'C:/h/pre_tool_use.py'"):
            with self.subTest(command=command):
                self.assertTrue(verify.shell_defects(command, "antigravity"))

    def test_ordinary_posix_registrations_have_no_defect(self):
        for command in ('python3 -X utf8 "/home/jane/.agents/skills/harness/hooks/pre_tool_use.py"',
                        "python3 /opt/skills/harness/hooks/pre_tool_use.py",
                        'python3 "$CLAUDE_PROJECT_DIR/skills/harness/hooks/pre_tool_use.py"',
                        '"/opt/my python/bin/python3" -X utf8 \'/opt/skills/harness/hooks/pre_tool_use.py\'',
                        "PYTHONUTF8=1 python3 /opt/skills/harness/hooks/pre_tool_use.py"):
            with self.subTest(command=command):
                self.assertEqual(verify.shell_defects(command, "posix"), [])

    def test_an_unbalanced_quote_is_a_defect_and_not_a_crash(self):
        self.assertTrue(verify.shell_defects('python3 "/opt/hooks/pre_tool_use.py', "posix"))

    def test_the_shells_a_host_may_use(self):
        for host in ("claude", "codex", "copilot", "cursor", "antigravity"):
            self.assertEqual(verify.host_shells(host, {"command": "x"}, windows=False), ("posix",))
        with mock.patch.object(verify, "git_bash", return_value="C:/Program Files/Git/bin/bash.exe"):
            self.assertEqual(verify.host_shells("claude", {"command": "x"}, windows=True), ("posix",))
            self.assertEqual(verify.host_shells("claude", {"command": "x", "shell": "powershell"}, windows=True), ("powershell",))
        with mock.patch.object(verify, "git_bash", return_value=None):
            self.assertEqual(verify.host_shells("claude", {"command": "x"}, windows=True), ("powershell",),
                             "without Git Bash Claude Code falls back to PowerShell")
            self.assertEqual(verify.host_shells("claude", {"command": "x", "shell": "bash"}, windows=True), ("posix",))
        self.assertEqual(verify.host_shells("codex", {"command": "x"}, windows=True), ("cmd", "powershell"))
        self.assertEqual(verify.host_shells("cursor", {"command": "x"}, windows=True), ("cmd", "powershell"))
        self.assertEqual(verify.host_shells("copilot", {"command": "x"}, windows=True), ("powershell",))
        self.assertEqual(verify.host_shells("antigravity", {"command": "x"}, windows=True), ("antigravity",))
        self.assertEqual(verify.host_shells("claude", {"command": "x", "args": ["y"]}, windows=True), (),
                         "a handler with args is started directly: no shell reads it")

    def test_a_handler_with_args_is_one_interpreter_word_however_many_spaces(self):
        entry = {"command": "C:/Program Files/Py/python.exe", "args": ["-X", "utf8", "C:/h/pre_tool_use.py"]}
        self.assertEqual(verify.handler_tokens(entry), ["C:/Program Files/Py/python.exe", "-X", "utf8", "C:/h/pre_tool_use.py"])
        self.assertEqual(verify.handler_tokens({"command": CALL})[0], "C:/Program Files/Py/python.exe")
        self.assertEqual(verify.handler_tokens({"command": 7}), [])


class Scratch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)
        self.enterContext(kit.in_project(self.project, HOME=str(self.home), USERPROFILE=str(self.home)))
        verify._PROBE_CACHE.clear()

    def settings(self, hooks: dict) -> Path:
        path = self.project / ".claude" / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
        return path

    def run_tool(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return kit.run_cli(script, *args, env=kit.plain_env(self.home, CLAUDE_PROJECT_DIR=str(self.project)), cwd=self.project)


def old_command(script: str) -> str:
    """The form the installer wrote before WP-02: native separators, the interpreter unquoted, the hook quoted."""
    return f'{sys.executable} -X utf8 "{HOOK_DIR / script}"'


OLD_REGISTRATION = {
    "PreToolUse": [{"matcher": "Bash|PowerShell|Edit|Write|NotebookEdit", "hooks": [
        {"type": "command", "command": old_command("pre_tool_use.py"), "statusMessage": "kept", "timeout": 30}]}],
    "PostToolUse": [{"matcher": "Bash|PowerShell", "hooks": [{"type": "command", "command": old_command("post_tool_use.py")}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": old_command("user_prompt_submit.py")}]},
                         {"hooks": [{"type": "command", "command": "echo mine"}]}],
}


def unflagged_command(script: str) -> str:
    """A command the tests below declare defective by its shape (it lacks ``-X utf8``), on any platform: on POSIX the
    form the registrar writes is the form it always wrote, so a real shell defect cannot be staged there."""
    return f'{Path(sys.executable).as_posix()} "{(HOOK_DIR / script).as_posix()}"'


def lacks_utf8_flag(entry: dict, host: str) -> list:
    return [] if " -X utf8 " in entry["command"] or "args" in entry else ["cannot start"]


class SelftestTests(Scratch):
    """``<hook> --selftest`` answers whether the registered command starts and finds its modules, and nothing else."""

    def test_every_registered_hook_prints_ok_reads_no_input_and_writes_no_state(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                done = subprocess.run([sys.executable, str(HOOK_DIR / script), verify.SELFTEST], capture_output=True, text=True,
                                      stdin=subprocess.DEVNULL, cwd=str(self.project), env=kit.clean_env(self.project), check=False)
                self.assertEqual((done.returncode, done.stdout.strip(), done.stderr.strip()), (0, "ok", ""))
        self.assertEqual(sorted(path.name for path in self.project.iterdir()), [".git"], "a self-test writes no state")

    def test_a_module_that_does_not_import_fails_the_self_test_loudly(self):
        """A self-test is not a host event, so it does not fail open: the exit status is the answer."""
        copy = self.tmp / "skills"
        shutil.copytree(HOOK_DIR, copy / "harness" / "hooks", ignore=shutil.ignore_patterns("__pycache__", "test_*.py"))
        shutil.copytree(_bootstrap.SCRIPTS, copy / "scripts", ignore=shutil.ignore_patterns("__pycache__", "test_*.py"))
        (copy / "harness" / "hooks" / "_cmdscan.py").unlink()
        for script in SCRIPTS:
            with self.subTest(script=script):
                done = subprocess.run([sys.executable, str(copy / "harness" / "hooks" / script), verify.SELFTEST], capture_output=True,
                                      text=True, stdin=subprocess.DEVNULL, env=kit.clean_env(self.project), check=False)
                self.assertNotEqual(done.returncode, 0)
                self.assertNotIn("ok", done.stdout.split())
                self.assertIn("_cmdscan", done.stderr)

    def test_the_self_test_imports_every_file_a_registered_hook_runs(self):
        seen = []
        with mock.patch.object(importlib, "import_module", side_effect=seen.append), contextlib.redirect_stdout(io.StringIO()) as out:
            _bootstrap.selftest()
        self.assertEqual(out.getvalue().strip(), "ok")
        self.assertEqual(sorted(seen), sorted(name.removesuffix(".py") for name in (*_bootstrap.HOOK_FILES, *_bootstrap.SCRIPT_FILES)))

    def test_any_other_argument_is_not_a_self_test(self):
        done = kit.run_hook("pre_tool_use.py", kit.bash("rm -rf /"), self.project, text=True)
        self.assertTrue(kit.denied(done.stdout), "the hook still reads its payload and decides")


class ProbeTests(Scratch):
    """``verify.probe`` starts a registered command the way its host does."""

    def entry(self, script: str = "pre_tool_use.py", host: str = "claude") -> dict:
        return repair.hook_handler(script, sys.executable, host)

    def test_the_command_the_registrar_writes_starts_in_every_shell_the_host_may_use(self):
        for host in ("claude", "codex", "copilot"):
            with self.subTest(host=host):
                results = verify.probe(self.entry(host=host), host)
                self.assertTrue(results)
                self.assertEqual([(r["shell"], r["executes"]) for r in results if r["executes"] is not True], [])
                self.assertEqual(verify.probe_failures(results, host, self.entry(host=host)), [])

    def test_a_command_started_without_a_shell_is_probed_directly(self):
        entry = {"command": sys.executable, "args": ["-X", "utf8", str(HOOK_DIR / "pre_tool_use.py")]}
        self.assertEqual(verify.probe(entry, "claude"), [{"shell": "direct", "executes": True, "detail": "ok"}])
        broken = {"command": sys.executable, "args": [str(self.tmp / "absent.py")]}
        result = verify.probe(broken, "claude")[0]
        self.assertEqual((result["shell"], result["executes"]), ("direct", False))
        self.assertEqual(verify.probe_failures([result], "claude", broken), [result])

    def test_a_hook_file_that_is_missing_or_broken_does_not_start(self):
        broken = self.tmp / "hooks" / "pre_tool_use.py"
        broken.parent.mkdir()
        broken.write_text("raise SystemExit(3)\n", encoding="utf-8")
        entry = repair.hook_handler("pre_tool_use.py", sys.executable, "claude", hook_dir=str(broken.parent))
        results = verify.probe(entry, "claude")
        self.assertTrue(results and all(result["executes"] is False for result in results), results)
        self.assertIn("exit 3", results[0]["detail"])

    def test_a_command_that_holds_shell_operators_is_never_started(self):
        marker = self.tmp / "ran.txt"
        base = self.entry()["command"]
        for tail in (f"; echo x > {marker.as_posix()}", f"&& echo x > {marker.as_posix()}", f"| tee {marker.as_posix()}",
                     f"> {marker.as_posix()}", "`id`", "$(id)"):
            with self.subTest(tail=tail):
                results = verify.probe({"command": f"{base} {tail}"}, "claude")
                self.assertEqual([result["executes"] for result in results], [None])
                self.assertIn("shell operators", results[0]["detail"])
        self.assertFalse(marker.exists())

    def test_an_interpreter_that_is_not_on_this_machine_is_not_probed(self):
        entry = repair.hook_handler("pre_tool_use.py", "/nonexistent/bin/python3", "claude", windows=False, hook_dir=HOOK_DIR.as_posix())
        results = verify.probe(entry, "claude")
        self.assertEqual([result["executes"] for result in results], [None])
        self.assertIn("was not found on this machine", results[0]["detail"])

    def test_an_interpreter_inside_the_project_is_not_run(self):
        planted = self.project / "bin" / ("python.exe" if WINDOWS else "python3")
        planted.parent.mkdir()
        # A copy, not a link: a link in the project to the system interpreter resolves to the system interpreter.
        shutil.copy2(sys.executable, planted)
        entry = {"command": planted.as_posix(), "args": [str(HOOK_DIR / "pre_tool_use.py")]}
        results = verify.probe(entry, "claude")
        self.assertEqual([result["executes"] for result in results], [None])
        self.assertIn("inside the project directory", results[0]["detail"])

    def test_a_command_registered_through_the_project_variable_is_given_the_project(self):
        hooks = self.project / "skills" / "harness" / "hooks"
        hooks.mkdir(parents=True)
        (hooks / "pre_tool_use.py").write_text("import sys\nprint('ok' if sys.argv[1:] == ['--selftest'] else 'no')\n", encoding="utf-8")
        variable = "$env:CLAUDE_PROJECT_DIR" if WINDOWS and not verify.git_bash() else "$CLAUDE_PROJECT_DIR"
        entry = {"command": f'{Path(sys.executable).as_posix()} "{variable}/skills/harness/hooks/pre_tool_use.py"'}
        with mock.patch.dict(os.environ):
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
            os.environ["SUPREMETEAM_PROJECT_DIR"] = str(self.project)
            results = verify.probe(entry, "claude", first_shell_only=True)
        self.assertEqual([result["executes"] for result in results], [True], results)


class ReadinessTests(Scratch):
    """Readiness no longer reports a registration as live when its command cannot start."""

    @unittest.skipUnless(WINDOWS, "the backslash form is a defect only where a path holds backslashes")
    def test_the_old_backslash_registration_is_not_executable_for_claude_code(self):
        self.settings(OLD_REGISTRATION)
        with mock.patch.object(verify, "git_bash", return_value="C:/Program Files/Git/bin/bash.exe"):
            states = verify.hook_states([json.loads((self.project / ".claude" / "settings.json").read_text(encoding="utf-8"))], "claude")
        for key, _ in verify.REQUIRED:
            with self.subTest(hook=key):
                self.assertEqual((states[key]["configured"], states[key]["resolvable"], states[key]["executable"], states[key]["registered"]),
                                 (True, True, False, False))
                self.assertIn("Git Bash", states[key]["reason"])
        self.assertEqual(verify.enforcement({"claude": states})["status"], "off")

    @unittest.skipUnless(WINDOWS and verify.git_bash(), "needs Git Bash, the shell Claude Code runs hooks through on Windows")
    def test_readiness_says_so_and_the_probe_shows_it(self):
        self.settings(OLD_REGISTRATION)
        plain = self.run_tool("check_readiness.py", "--host", "claude", "--require-hooks")
        self.assertEqual(plain.returncode, 1, plain.stdout)
        self.assertIn("Enforcement: off", plain.stdout)
        self.assertIn("the command does not start", plain.stdout)
        probed = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--probe", "--json").stdout)
        self.assertEqual(probed["capabilities"]["hooks_probed"], "no")
        bash = [entry for entry in probed["hooks"]["states"]["claude:pre"]["probe"] if entry["shell"] == "git-bash"]
        self.assertEqual([entry["executes"] for entry in bash], [False])

    def test_a_fresh_registration_is_live_and_its_probe_says_yes(self):
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertEqual(json.loads(applied.stdout.strip().splitlines()[-1])["probe"], "started")
        report = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--require-hooks", "--probe", "--json").stdout)
        self.assertTrue(report["ready"], report["blockers"])
        self.assertEqual(report["enforcement"]["status"], "live")
        self.assertEqual(report["capabilities"]["hooks_probed"], "yes")
        for key in ("claude:pre", "claude:post", "claude:prompt"):
            probe = report["hooks"]["states"][key]["probe"]
            self.assertTrue(probe and all(entry["executes"] for entry in probe), (key, probe))
        text = self.run_tool("check_readiness.py", "--host", "claude", "--probe").stdout
        self.assertIn("executes: claude:pre:", text)

    def test_a_plugin_host_is_named_as_present_and_not_inspected(self):
        """WP-09: pi, Cursor and OpenCode are registered through a file the verifier cannot read. Readiness says the
        file is there and that the host reports its own state, instead of saying nothing about a guard that may run."""
        self.assertEqual(json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json").stdout)["plugin_hosts"], {})
        extension = self.home / ".pi" / "agent" / "extensions" / "supremeteam-guard.ts"
        extension.parent.mkdir(parents=True)
        extension.write_text("// stand-in\n", encoding="utf-8")
        plugin = self.home / ".config" / "opencode" / "plugins" / "supremeteam-hooks.js"
        plugin.parent.mkdir(parents=True)
        plugin.write_text("// stand-in\n", encoding="utf-8")
        report = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json").stdout)
        self.assertEqual(sorted(report["plugin_hosts"]), ["opencode", "pi"])
        self.assertEqual(report["plugin_hosts"]["pi"]["path"], str(extension))
        text = self.run_tool("check_readiness.py", "--host", "claude").stdout
        self.assertIn(f"Plugin host: pi - extension at {extension}; not inspected here", text)
        self.assertIn("at every session start", text)

    def test_the_pi_extension_is_found_where_its_variable_puts_it(self):
        agent = self.tmp / "moved-agent"
        (agent / "extensions").mkdir(parents=True)
        (agent / "extensions" / "supremeteam-guard.ts").write_text("// stand-in\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PI_CODING_AGENT_DIR": str(agent)}):
            self.assertEqual(sorted(verify.plugin_hosts()), ["pi"])
        with mock.patch.dict(os.environ):
            os.environ.pop("PI_CODING_AGENT_DIR", None)
            self.assertEqual(verify.plugin_hosts(), {})

    def test_without_the_flag_no_command_is_started(self):
        self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply", "--no-probe")
        report = json.loads(self.run_tool("check_readiness.py", "--host", "claude", "--json").stdout)
        self.assertEqual(report["capabilities"]["hooks_probed"], "not_run")
        self.assertIsNone(report["hooks"]["states"]["claude:pre"]["probe"])

    def test_a_registered_command_that_fails_the_probe_is_not_registered(self):
        hooks = self.tmp / "relocated"
        hooks.mkdir()
        for script in SCRIPTS:
            (hooks / script).write_text("raise SystemExit(5)\n", encoding="utf-8")
        self.settings({verify.EVENTS["claude"][key]: [{"hooks": [{"type": "command", **repair.hook_handler(script, sys.executable, "claude", hook_dir=str(hooks))}]}]
                       for key, script in verify.REQUIRED})
        env = kit.plain_env(self.home, CLAUDE_PROJECT_DIR=str(self.project), SUPREMETEAM_HOOK_ROOT=str(hooks))
        static = kit.run_cli("verify_registration.py", "--host", "claude", env=env, cwd=self.project)
        self.assertEqual(static.returncode, 0, static.stdout)
        probed = kit.run_cli("verify_registration.py", "--host", "claude", "--probe", env=env, cwd=self.project)
        self.assertEqual(probed.returncode, 1, probed.stdout)
        self.assertIn("the command does not start under", probed.stdout)


class RepairTests(Scratch):
    """Repair replaces a Supreme Team command that cannot start, in place, and writes nothing that cannot start."""

    def repaired(self) -> dict:
        return json.loads((self.project / ".claude" / "settings.json").read_text(encoding="utf-8"))["hooks"]

    def test_a_defective_entry_is_replaced_in_place_and_keeps_its_matcher_and_fields(self):
        config = {"hooks": json.loads(json.dumps(OLD_REGISTRATION))}
        for event, script in (("PreToolUse", "pre_tool_use.py"), ("PostToolUse", "post_tool_use.py"), ("UserPromptSubmit", "user_prompt_submit.py")):
            config["hooks"][event][0]["hooks"][0]["command"] = unflagged_command(script)
        with mock.patch.object(verify, "handler_defects", side_effect=lacks_utf8_flag):
            desired, changes = repair.plan(config, "claude", sys.executable)
        replaced = [change for change in changes if "(recommended)" not in change]
        self.assertEqual(len(replaced), 3)
        self.assertTrue(all("replaces a command that cannot start" in change for change in replaced), changes)
        self.assertEqual({event: len(groups) for event, groups in desired["hooks"].items()},
                         {"PreToolUse": 1, "PostToolUse": 1, "UserPromptSubmit": 2, **RECOMMENDED_EVENTS},
                         "no second group is added beside the broken one")
        pre = desired["hooks"]["PreToolUse"][0]
        self.assertEqual(pre["matcher"], "Bash|PowerShell|Edit|Write|NotebookEdit")
        self.assertEqual((pre["hooks"][0]["statusMessage"], pre["hooks"][0]["timeout"]), ("kept", 30))
        self.assertEqual(pre["hooks"][0]["command"], repair.hook_handler("pre_tool_use.py", sys.executable, "claude")["command"])
        self.assertEqual(desired["hooks"]["UserPromptSubmit"][1], {"hooks": [{"type": "command", "command": "echo mine"}]},
                         "an entry that is not ours is never touched")

    def test_a_replaced_entry_with_a_narrow_matcher_still_gets_the_tools_it_misses(self):
        narrow = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": unflagged_command("pre_tool_use.py")}]}]}}
        with mock.patch.object(verify, "handler_defects", side_effect=lacks_utf8_flag):
            desired, changes = repair.plan(narrow, "claude", sys.executable)
        groups = desired["hooks"]["PreToolUse"]
        self.assertEqual([group["matcher"] for group in groups], ["Bash", "PowerShell|Edit|Write|NotebookEdit"])
        self.assertEqual(len([change for change in changes if "(recommended)" not in change]), 4, changes)

    @unittest.skipUnless(WINDOWS and verify.git_bash(), "needs Git Bash, the shell Claude Code runs hooks through on Windows")
    def test_repair_replaces_the_old_backslash_registration_and_a_second_run_changes_nothing(self):
        self.settings(OLD_REGISTRATION)
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        hooks = self.repaired()
        self.assertEqual({event: len(groups) for event, groups in hooks.items()},
                         {"PreToolUse": 1, "PostToolUse": 1, "UserPromptSubmit": 2, **RECOMMENDED_EVENTS})
        for event in ("PreToolUse", "PostToolUse", "UserPromptSubmit"):
            command = hooks[event][0]["hooks"][0]["command"]
            self.assertNotIn("\\", command)
            self.assertEqual(verify.handler_defects(hooks[event][0]["hooks"][0], "claude"), [])
        again = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply")
        self.assertEqual(again.returncode, 0)
        self.assertIn("no changes", again.stdout)
        self.assertEqual(len(list((self.project / ".claude").glob("settings.json.bak-*"))), 1)

    def test_a_registration_that_cannot_start_is_not_written(self):
        hooks = self.tmp / "broken"
        hooks.mkdir()
        for script in SCRIPTS:
            (hooks / script).write_text("raise SystemExit(9)\n", encoding="utf-8")
        with mock.patch.object(repair, "HOOK_DIR", hooks), mock.patch.dict(os.environ, {"SUPREMETEAM_HOOK_ROOT": str(hooks)}):
            desired, changes = repair.plan({}, "claude", sys.executable)
            failures, notes = repair.probe_written({}, desired, "claude")
        self.assertEqual(len(changes), len(WRITTEN))
        self.assertEqual(len(failures), 3, failures)
        self.assertIn("pre_tool_use.py does not start under", failures[0])
        self.assertEqual(notes, [])

    def test_only_what_this_change_writes_is_probed(self):
        existing, _ = repair.plan({}, "claude", sys.executable)
        self.assertEqual(repair.written_handlers(existing, json.loads(json.dumps(existing)), "claude"), [])
        self.assertEqual([script for script, _ in repair.written_handlers({}, existing, "claude")], WRITTEN)

    def test_an_interpreter_for_another_machine_is_written_with_a_note(self):
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply", "--python", "python3.99")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        report = json.loads(applied.stdout.strip().splitlines()[-1])
        self.assertTrue(report["applied"])
        self.assertTrue(any("was not found on this machine" in note for note in report["probe_notes"]), report)

    def test_the_no_probe_flag_writes_without_starting_anything(self):
        with mock.patch.object(verify, "probe", side_effect=AssertionError("a probe ran")):
            desired, _ = repair.plan({}, "claude", sys.executable)
        applied = self.run_tool("repair_registration.py", "--host", "claude", "--scope", "project", "--apply", "--no-probe")
        self.assertEqual(json.loads(applied.stdout.strip().splitlines()[-1])["probe"], "skipped")
        self.assertTrue(desired["hooks"])


class CodexNoticeTests(Scratch):
    """Codex skips a changed hook until it is trusted, and reads inline hooks from config.toml as well."""

    def codex(self, *args: str) -> subprocess.CompletedProcess:
        return self.run_tool("repair_registration.py", "--host", "codex", "--scope", "project", *args)

    def test_a_rewrite_says_that_codex_has_to_trust_the_hooks_again(self):
        applied = self.codex("--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("/hooks", applied.stderr)
        self.assertTrue(any("/hooks" in warning for warning in json.loads(applied.stdout.strip().splitlines()[-1])["warnings"]))
        readiness = self.run_tool("check_readiness.py", "--host", "codex")
        self.assertIn("readiness cannot see whether Codex trusts these hooks", readiness.stdout)

    def test_inline_hooks_in_config_toml_count_as_registered_and_are_not_written_twice(self):
        folder = self.project / ".codex"
        folder.mkdir()
        tables = []
        for event, script in repair.hook_events("codex"):
            matcher = repair.matcher_for(script, "codex")
            command = repair.hook_handler(script, sys.executable, "codex")["command"].replace('"', '\\"')
            tables.append(f"[[hooks.{event}]]\n" + (f'matcher = "{matcher}"\n' if matcher else "")
                          + f'[[hooks.{event}.hooks]]\ntype = "command"\ncommand = "{command}"\n')
        (folder / "config.toml").write_text("model = \"x\"\n\n" + "\n".join(tables), encoding="utf-8")
        inline = verify.codex_inline_hooks(folder / "hooks.json")
        self.assertEqual(sorted(inline["hooks"]), sorted({event for event, _ in repair.hook_events("codex")}))
        dry = self.codex()
        self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
        self.assertIn("no changes", dry.stdout)
        self.assertFalse((folder / "hooks.json").exists(), "no second copy is written")
        verified = self.run_tool("verify_registration.py", "--host", "codex")
        self.assertEqual(verified.returncode, 0, verified.stdout)
        self.assertIn("config.toml", verified.stdout)

    def test_a_partly_inline_registration_warns_about_the_merge(self):
        folder = self.project / ".codex"
        folder.mkdir()
        command = repair.hook_handler("user_prompt_submit.py", sys.executable, "codex")["command"].replace('"', '\\"')
        (folder / "config.toml").write_text(f'[[hooks.UserPromptSubmit]]\n[[hooks.UserPromptSubmit.hooks]]\ntype = "command"\ncommand = "{command}"\n',
                                            encoding="utf-8")
        applied = self.codex("--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("config.toml beside this file has inline [hooks] tables", applied.stderr)
        written = json.loads((folder / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(sorted(written), ["PostToolUse", "PreCompact", "PreToolUse", "SessionStart"],
                         "the hook registered inline is not written again")

    def test_a_config_toml_without_hooks_or_one_that_does_not_parse_is_ignored(self):
        folder = self.project / ".codex"
        folder.mkdir()
        self.assertIsNone(verify.codex_inline_hooks(folder / "hooks.json"))
        for text in ('model = "x"\n', "not = [toml", "[hooks]\n"):
            (folder / "config.toml").write_text(text, encoding="utf-8")
            with self.subTest(text=text):
                self.assertIsNone(verify.codex_inline_hooks(folder / "hooks.json"))


# --- the forms through real shells (Appendix A.2 of the plan) -----------------------------------------------------

def _shells() -> dict:
    """Every way a host hands a command to a shell on this machine: label -> a function from text to what to start."""
    if not WINDOWS:
        return {"sh": lambda text: ["sh", "-c", text]}
    found = {}
    bash = verify.git_bash()
    if bash:
        found["git-bash"] = lambda text: [bash, "-c", text]
    for label, path in verify.powershells():
        found[label] = lambda text, path=path: [path, "-NoProfile", "-NonInteractive", "-Command", text]
    found["cmd"] = lambda text: f'cmd /d /s /c "{text}"'
    found["cmd /C"] = lambda text: ["cmd.exe", "/C", text]
    return found


def _starts(what) -> bool:
    try:
        done = subprocess.run(what, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip().splitlines()[-1:] == ["ok"]


class ShellMatrixTests(unittest.TestCase):
    """Each form through each real shell, and the static check against the same answer."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp = Path(cls._tmp.name).resolve()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.plain = cls.tmp / "plain"
        cls.spaced = cls.tmp / "with space"
        for folder in (cls.plain, cls.spaced):
            folder.mkdir()
            (folder / "pre_tool_use.py").write_text("print('ok')\n", encoding="utf-8")
        # A virtual environment in a directory with a space: a spaced interpreter with nothing installed.
        venv = cls.spaced / "venv"
        made = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], capture_output=True, text=True, check=False)
        candidate = venv / ("Scripts/python.exe" if WINDOWS else "bin/python")
        cls.spaced_python = str(candidate) if made.returncode == 0 and candidate.exists() else None
        cls.shells = _shells()

    def check(self, label: str, command: str, expected: dict) -> None:
        """Run ``command`` through every shell found; ``expected`` maps a shell label to whether it has to start."""
        for shell, build in self.shells.items():
            if shell not in expected:
                continue
            with self.subTest(form=label, shell=shell):
                self.assertEqual(_starts(build(command)), expected[shell], command)
                kind = verify._SHELL_KINDS[shell]
                if not expected[shell] and kind in ("posix", "powershell", "antigravity"):
                    self.assertTrue(verify.shell_defects(command, kind), f"the static check missed what {shell} refuses: {command}")
                if expected[shell]:
                    self.assertEqual(verify.shell_defects(command, kind), [], f"the static check refuses what {shell} starts: {command}")

    def native(self, folder: Path) -> str:
        return str(folder / "pre_tool_use.py")

    @unittest.skipUnless(WINDOWS, "the Windows forms")
    def test_the_standard_form_starts_in_every_shell_with_and_without_a_space_in_the_hook_path(self):
        everywhere = {"git-bash": True, "pwsh": True, "powershell": True, "cmd": True}
        for folder in (self.plain, self.spaced):
            command = repair.hook_handler("pre_tool_use.py", sys.executable, "claude", hook_dir=str(folder))["command"]
            self.assertNotIn("\\", command)
            self.check(f"standard, {folder.name}", command, everywhere)
            # Antigravity passes the command as one escaped argument, and the quote does not survive.
            self.check(f"standard, {folder.name}", command, {"cmd /C": False})

    @unittest.skipUnless(WINDOWS, "the Windows forms")
    def test_the_form_the_installer_used_to_write_does_not_start_in_git_bash(self):
        for folder in (self.plain, self.spaced):
            command = f'{sys.executable} -X utf8 "{self.native(folder)}"'
            self.check(f"old form, {folder.name}", command, {"git-bash": False, "pwsh": True, "powershell": True, "cmd": True})

    @unittest.skipUnless(WINDOWS, "the Windows forms")
    def test_the_bare_form_starts_everywhere_and_is_the_one_form_antigravity_can_run(self):
        command = repair.hook_handler("pre_tool_use.py", sys.executable, "antigravity", hook_dir=str(self.plain))["command"]
        self.assertNotIn('"', command)
        self.check("bare", command, {"git-bash": True, "pwsh": True, "powershell": True, "cmd": True, "cmd /C": True})

    @unittest.skipUnless(WINDOWS, "the Windows forms")
    def test_the_py_launcher_form_starts_in_every_shell(self):
        selector = repair.py_launcher_for(sys.executable)
        if not selector:
            self.skipTest("no py launcher on PATH starts the interpreter running the tests")
        command = repair.standard_form([*selector.split(), "-X", "utf8"], repair.forward_slashes(self.native(self.spaced)))
        self.check("py launcher", command, {"git-bash": True, "pwsh": True, "powershell": True, "cmd": True})

    @unittest.skipUnless(WINDOWS, "the Windows forms")
    def test_a_spaced_interpreter_has_no_text_form_that_starts_in_every_shell(self):
        if not self.spaced_python:
            self.skipTest("a virtual environment could not be created in a directory with a space")
        interpreter = repair.forward_slashes(self.spaced_python)
        hook = repair.forward_slashes(self.native(self.spaced))
        quoted = f'"{interpreter}" -X utf8 "{hook}"'
        self.check("both quoted (the original plan)", quoted, {"git-bash": True, "pwsh": False, "powershell": False, "cmd": True})
        call = repair.call_form([interpreter, "-X", "utf8"], hook)
        self.check("call", call, {"git-bash": False, "pwsh": True, "powershell": True})
        self.assertTrue(verify.shell_defects(call, "cmd"))
        # The no-shell form is the one that starts whatever the paths hold.
        parts = repair.parts_form([interpreter, "-X", "utf8"], hook)
        self.assertTrue(_starts([parts["command"], *parts["args"]]))
        self.assertEqual(repair.hook_handler("pre_tool_use.py", self.spaced_python, "claude", hook_dir=str(self.spaced),
                                             py_launcher=no_launcher), parts)

    @unittest.skipUnless(WINDOWS, "the py launcher is a Windows program")
    def test_the_py_launcher_is_not_offered_for_a_virtual_environment(self):
        if not self.spaced_python:
            self.skipTest("a virtual environment could not be created in a directory with a space")
        if not shutil.which("py"):
            self.skipTest("no py launcher on PATH")
        self.assertIsNone(repair.py_launcher_for(self.spaced_python), "py -3.x starts the base interpreter, not the environment's")

    @unittest.skipIf(WINDOWS, "the POSIX leg")
    def test_the_posix_form_starts_under_sh_with_spaces_in_both_paths(self):
        for python in filter(None, (sys.executable, self.spaced_python)):
            for folder in (self.plain, self.spaced):
                command = repair.hook_handler("pre_tool_use.py", python, "claude", hook_dir=str(folder))["command"]
                self.check(f"posix, {Path(python).parent.name}, {folder.name}", command, {"sh": True})

    def test_the_command_registered_for_this_machine_starts_the_real_hook(self):
        """The whole chain for the interpreter and directory in use: what the registrar writes starts and prints ok."""
        for host in ("claude", "codex", "copilot"):
            entry = repair.hook_handler("pre_tool_use.py", sys.executable, host)
            for result in verify.probe(entry, host):
                with self.subTest(host=host, shell=result["shell"]):
                    self.assertTrue(result["executes"], result)


if __name__ == "__main__":
    unittest.main()
