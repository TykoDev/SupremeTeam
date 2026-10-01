#!/usr/bin/env python3
"""``scripts/install_hooks.py`` and the ``--register-hooks`` block of ``install.sh``.

Covers what ``test_registration_contract.py`` does not: refusing files that are
not UTF-8, the OpenCode plugin (generated JavaScript, executed with node against
a stand-in interpreter), file modes, the preview-and-ask step on a terminal, the
hook-hash record, and the shell wrapper's scope and confirmation options.

The installer is repository tooling and is not part of an installed skill tree,
so every test skips when it is absent.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

try:
    import pty
    import select
except ImportError:  # Windows has no pseudo-terminals
    pty = select = None

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import repair_registration as repair  # noqa: E402
import verify_registration as verify  # noqa: E402

REPO = HOOK_DIR.parents[2]
INSTALLER = REPO / "scripts" / "install_hooks.py"
INSTALL_SH = REPO / "scripts" / "install.sh"
INSTALL_PS1 = REPO / "scripts" / "install.ps1"
NODE = shutil.which("node")
BASH = shutil.which("bash")
POSIX = os.name == "posix"
_STRIP = ("CLAUDE", "CODEX_", "COPILOT", "GITHUB_COPILOT", "SUPREMETEAM_", "GITHUB_WORKSPACE")


@unittest.skipUnless(INSTALLER.is_file(), "scripts/install_hooks.py is repository tooling, not an installed file")
class InstallerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.project = self.tmp / "project"
        (self.project / ".git").mkdir(parents=True)
        self.settings = self.tmp / "settings.json"

    def env(self, **extra: str) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(_STRIP)}
        env["HOME"] = env["USERPROFILE"] = str(self.home)
        env.update(extra)
        return env

    def argv(self, *args: str) -> list[str]:
        return [sys.executable, str(INSTALLER), "--hook-root", str(HOOK_DIR), *args]

    def install(self, *args: str, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(self.argv(*args), text=True, capture_output=True, cwd=str(self.project), env=self.env(**extra), check=False)

    def mode(self, path: Path) -> int:
        return stat.S_IMODE(path.stat().st_mode)


class DefaultsTests(InstallerCase):
    def test_the_interpreter_that_ran_the_installer_is_what_gets_registered(self):
        result = self.install("--target", "claude", "--claude-settings", str(self.settings))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = json.loads(self.settings.read_text(encoding="utf-8"))
        for groups in config["hooks"].values():
            command = groups[0]["hooks"][0]["command"]
            self.assertTrue(command.startswith(repair.launcher_token(sys.executable) + " -X utf8 "), command)

    def test_an_interpreter_that_cannot_start_the_hooks_is_named_before_and_after_the_write(self):
        missing = "/nonexistent/python3.13" if POSIX else "C:/nonexistent/python3.13.exe"
        for extra in (("--dry-run",), ()):
            with self.subTest(extra=extra):
                result = self.install("--target", "claude", "--claude-settings", str(self.settings), "--python-command", missing, *extra)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("note: interpreter", result.stdout)
                self.assertIn("was not found on this PATH", result.stdout)

    @unittest.skipUnless(POSIX, "needs a shell script to stand in for an interpreter")
    def test_an_interpreter_below_the_floor_is_named(self):
        old = self.tmp / "bin" / "python3.11"
        old.parent.mkdir()
        old.write_text('#!/bin/sh\necho "3 11 4"\n', encoding="utf-8")
        old.chmod(0o755)
        result = self.install("--target", "claude", "--claude-settings", str(self.settings), "--python-command", str(old), "--dry-run")
        self.assertIn("is Python 3.11.4, below the 3.13 floor", result.stdout)

    def test_a_usable_interpreter_gets_no_note(self):
        result = self.install("--target", "claude", "--claude-settings", str(self.settings), "--dry-run")
        self.assertNotIn("note:", result.stdout)

    def test_the_hash_of_every_registered_script_is_recorded_in_the_project(self):
        result = self.install("--target", "claude", "--claude-settings", str(self.settings))
        self.assertIn("hook hashes recorded in:", result.stdout)
        record = json.loads((self.project / ".harness-state" / verify.HASH_RECORD).read_text(encoding="utf-8"))
        self.assertEqual(len(record["hooks"]), len(verify.REQUIRED))
        self.assertEqual(record["directories"][verify.hash_key(HOOK_DIR)]["files"], verify.module_hashes(HOOK_DIR),
                         "every module beside the scripts is recorded too")

    def test_a_dry_run_records_nothing(self):
        self.install("--target", "claude", "--claude-settings", str(self.settings), "--dry-run")
        self.assertFalse((self.project / ".harness-state").exists())

    def test_a_widened_matcher_is_added_to_a_narrow_registration(self):
        narrow = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": repair.command_for("pre_tool_use.py", sys.executable)}]}]}}
        self.settings.write_text(json.dumps(narrow), encoding="utf-8")
        result = self.install("--target", "claude", "--claude-settings", str(self.settings))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        groups = json.loads(self.settings.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
        self.assertEqual([g.get("matcher") for g in groups], ["Bash", "PowerShell|Edit|Write|NotebookEdit"])
        self.assertIn("status: REGISTERED", result.stdout)

    def test_project_scope_notes_that_the_file_is_usually_committed(self):
        result = self.install("--target", "claude", "--scope", "project", "--dry-run")
        self.assertIn("note: project scope writes machine-absolute hook paths", result.stdout)
        self.assertFalse((self.project / ".claude").exists())

    def test_user_scope_names_the_global_file_before_touching_it(self):
        result = self.install("--target", "claude", "--dry-run")
        self.assertIn(f"config: {self.home / '.claude' / 'settings.json'}", result.stdout)
        self.assertIn("note: user scope edits the global claude configuration", result.stdout)
        self.assertFalse((self.home / ".claude").exists())

    def test_an_explicit_config_path_carries_no_scope_note(self):
        result = self.install("--target", "claude", "--claude-settings", str(self.settings), "--dry-run")
        self.assertNotIn("note:", result.stdout)


class EncodingTests(InstallerCase):
    def test_a_utf16_settings_file_is_refused_and_the_other_hosts_still_register(self):
        # Windows PowerShell 5.1 `>` and Out-File write UTF-16.
        original = '{"theme": "dark"}'.encode("utf-16")
        self.settings.write_bytes(original)
        codex = self.tmp / "codex.json"
        result = self.install("--target", "claude", "--target", "codex", "--claude-settings", str(self.settings), "--codex-hooks", str(codex))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("is not UTF-8 text", result.stdout)
        self.assertEqual(self.settings.read_bytes(), original)
        self.assertTrue(codex.is_file(), "a refusal for one host must not skip the next")
        self.assertIn("[codex]", result.stdout)

    def test_a_non_utf8_plugin_file_is_refused(self):
        plugin = self.tmp / "plugin.js"
        plugin.write_bytes(b"\xff\xfe//")
        result = self.install("--target", "opencode", "--opencode-plugin", str(plugin))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(plugin.read_bytes(), b"\xff\xfe//")

    def test_a_non_utf8_cursor_file_is_refused(self):
        root = self.tmp / "cursor"
        (root / "hooks").mkdir(parents=True)
        (root / "hooks" / "hooks.json").write_bytes(b"\xff\xfe{")
        result = self.install("--target", "cursor", "--cursor-plugin", str(root))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)


@unittest.skipUnless(POSIX, "symbolic links need privileges on Windows")
class ConfigLinkTests(InstallerCase):
    """RR-V3-2: the installer replaced a config that is a symbolic link with a regular file."""

    def linked(self, at: Path) -> Path:
        target = self.tmp / "dotfiles" / "settings.json"
        target.parent.mkdir()
        target.write_text('{"theme": "dark"}\n', encoding="utf-8")
        at.parent.mkdir(parents=True, exist_ok=True)
        at.symlink_to(target)
        return target

    def test_the_user_level_config_is_written_through_its_link(self):
        link = self.home / ".claude" / "settings.json"
        target = self.linked(link)
        result = self.install("--target", "claude")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertIn("hooks", json.loads(target.read_text(encoding="utf-8")))
        self.assertIn("is a symbolic link: writing through it to", result.stdout)
        self.assertIn("status: REGISTERED", result.stdout)

    def test_a_path_named_on_the_command_line_is_written_through_at_any_scope(self):
        link = self.tmp / "named.json"
        target = self.linked(link)
        result = self.install("--target", "claude", "--scope", "project", "--claude-settings", str(link))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertIn("hooks", json.loads(target.read_text(encoding="utf-8")))

    def test_a_project_level_link_is_refused_and_the_link_and_its_target_are_untouched(self):
        link = self.project / ".claude" / "settings.json"
        target = self.linked(link)
        before = target.read_bytes()
        result = self.install("--target", "claude", "--scope", "project")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("REFUSED: ", result.stdout)
        self.assertIn("refusing to replace it", result.stdout)
        self.assertTrue(link.is_symlink())
        self.assertEqual(target.read_bytes(), before)

    def test_a_refused_link_does_not_stop_the_other_hosts(self):
        link = self.project / ".claude" / "settings.json"
        self.linked(link)
        result = self.install("--target", "claude", "--target", "codex", "--scope", "project")
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertTrue((self.project / ".codex" / "hooks.json").is_file())


@unittest.skipUnless(POSIX, "permission bits are POSIX")
class FileModeTests(InstallerCase):
    def setUp(self):
        super().setUp()
        self._umask = os.umask(0o022)
        self.addCleanup(os.umask, self._umask)

    def test_a_private_file_and_its_backup_stay_private(self):
        self.settings.write_text(json.dumps({"env": {"TOKEN": "x"}}), encoding="utf-8")
        self.settings.chmod(0o600)
        result = self.install("--target", "claude", "--claude-settings", str(self.settings))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.mode(self.settings), 0o600)
        backups = list(self.tmp.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.mode(backups[0]), 0o600)

    def test_new_user_level_files_are_owner_only(self):
        plugin, cursor = self.tmp / "plugin.js", self.tmp / "cursor"
        result = self.install("--target", "claude", "--claude-settings", str(self.settings),
                              "--target", "opencode", "--opencode-plugin", str(plugin),
                              "--target", "cursor", "--cursor-plugin", str(cursor))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in (self.settings, plugin, cursor / "hooks" / "hooks.json", cursor / ".cursor-plugin" / "plugin.json"):
            self.assertEqual(self.mode(path), 0o600, path)

    def test_a_new_project_scope_file_follows_the_umask(self):
        result = self.install("--target", "claude", "--scope", "project")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.mode(self.project / ".claude" / "settings.json"), 0o644)


@unittest.skipUnless(pty and POSIX, "needs a pseudo-terminal")
class PromptTests(InstallerCase):
    """On a terminal the installer shows the preview and asks before it writes."""

    def in_terminal(self, *args: str, answers: tuple[bytes, ...] = (), timeout: float = 60) -> tuple[int, str]:
        try:
            master, slave = pty.openpty()
        except OSError:
            self.skipTest("this environment has no pseudo-terminals")
        proc = subprocess.Popen(self.argv(*args), stdin=slave, stdout=slave, stderr=slave, cwd=str(self.project),
                                env=self.env(), close_fds=True)
        os.close(slave)
        output, pending, answered = b"", list(answers), 0
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                if select.select([master], [], [], 0.2)[0]:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    output += chunk
                    if pending and output.count(b"[y/N]") > answered:
                        answered += 1
                        os.write(master, pending.pop(0))
                elif proc.poll() is not None:
                    break
            else:
                proc.kill()
                self.fail(f"the installer did not finish: {output.decode(errors='replace')}")
            return proc.wait(timeout=10), output.decode(errors="replace").replace("\r\n", "\n")
        finally:
            os.close(master)
            if proc.poll() is None:
                proc.kill()

    def test_declining_writes_nothing_and_exits_3(self):
        code, output = self.in_terminal("--target", "claude", "--claude-settings", str(self.settings), answers=(b"n\n",))
        self.assertEqual(code, 3, output)
        self.assertIn("Preview of the changes. Nothing is written until you confirm.", output)
        self.assertIn("(proposed)", output)
        self.assertIn("Write these changes? [y/N]", output)
        self.assertIn("Declined: nothing was written.", output)
        self.assertFalse(self.settings.exists())
        self.assertFalse((self.project / ".harness-state").exists())

    def test_an_empty_answer_declines(self):
        code, output = self.in_terminal("--target", "claude", "--claude-settings", str(self.settings), answers=(b"\n",))
        self.assertEqual(code, 3, output)
        self.assertFalse(self.settings.exists())

    def test_confirming_writes_and_verifies(self):
        code, output = self.in_terminal("--target", "claude", "--claude-settings", str(self.settings), answers=(b"y\n",))
        self.assertEqual(code, 0, output)
        self.assertIn("Writing:", output)
        self.assertIn("status: REGISTERED", output)
        self.assertTrue(self.settings.is_file())

    def test_yes_skips_the_question(self):
        code, output = self.in_terminal("--target", "claude", "--claude-settings", str(self.settings), "--yes")
        self.assertEqual(code, 0, output)
        self.assertNotIn("[y/N]", output)
        self.assertTrue(self.settings.is_file())

    def test_a_dry_run_never_asks(self):
        code, output = self.in_terminal("--target", "claude", "--claude-settings", str(self.settings), "--dry-run")
        self.assertEqual(code, 0, output)
        self.assertNotIn("[y/N]", output)
        self.assertFalse(self.settings.exists())

    def test_nothing_to_change_never_asks(self):
        self.install("--target", "claude", "--claude-settings", str(self.settings))
        code, output = self.in_terminal("--target", "claude", "--claude-settings", str(self.settings))
        self.assertEqual(code, 0, output)
        self.assertNotIn("[y/N]", output)
        self.assertIn("no changes: already registered", output)

    def test_without_a_terminal_it_writes_straight_away(self):
        result = self.install("--target", "claude", "--claude-settings", str(self.settings))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("[y/N]", result.stdout)
        self.assertTrue(self.settings.is_file())


@unittest.skipUnless(NODE, "node is not installed")
class OpenCodePluginTests(InstallerCase):
    """The generated plugin is executed, with a node script standing in for the interpreter."""

    FAKE = """const fs = require("fs");
const args = process.argv.slice(2);
fs.appendFileSync(process.env.FAKE_LOG, JSON.stringify({ args, cwd: process.env.SUPREMETEAM_PROJECT_DIR }) + "\\n");
const payload = JSON.parse(fs.readFileSync(0, "utf8") || "{}");
const script = args[args.length - 1];
if (script.endsWith("pre_tool_use.py") && payload.tool_input && payload.tool_input.command === "danger") {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { permissionDecision: "deny", permissionDecisionReason: "nope" } }));
} else if (script.endsWith("post_tool_use.py")) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { additionalContext: "careful" } }));
}
"""
    FAILING = """process.stderr.write("boom");
process.exit(1);
"""
    DRIVER = """import { SupremeTeamHooks } from "./plugin.mjs";
const logs = [];
const hooks = await SupremeTeamHooks({ directory: process.cwd(), client: { app: { log: async (entry) => logs.push(entry.body) } } });
const result = { denied: false };
try {
  await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: process.argv[2] } });
} catch (error) {
  result.denied = error.message;
}
await hooks["tool.execute.before"]({ tool: "bash", sessionID: "s1" }, { args: { command: "ls" } });
await hooks["tool.execute.after"]({ tool: "bash", sessionID: "s1", args: { command: "ls" } }, { exit_code: 0 });
result.logs = logs;
console.log(JSON.stringify(result));
"""

    def build(self, python_command: str) -> Path:
        plugin = self.tmp / "work" / "plugin.mjs"
        plugin.parent.mkdir(exist_ok=True)
        result = self.install("--target", "opencode", "--opencode-plugin", str(plugin), "--python-command", python_command)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (plugin.parent / "driver.mjs").write_text(self.DRIVER, encoding="utf-8")
        return plugin

    def drive(self, plugin: Path, command: str = "danger") -> dict:
        log = self.tmp / "fake.log"
        done = subprocess.run([NODE, str(plugin.parent / "driver.mjs"), command], text=True, capture_output=True, cwd=str(plugin.parent),
                              env=self.env(FAKE_LOG=str(log)), check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return json.loads(done.stdout)

    def fake(self, name: str, body: str) -> Path:
        path = self.tmp / "work" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in (self.tmp / "fake.log").read_text(encoding="utf-8").splitlines()]

    def test_a_launcher_with_arguments_is_split_into_command_and_arguments(self):
        spec = importlib.util.spec_from_file_location("install_hooks_under_test", INSTALLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin = module.opencode_plugin_source("py -3", "C:\\hooks", repair)
        self.assertIn('const pythonCommand = "py";', plugin)
        self.assertIn('const pythonArgs = ["-3", "-X", "utf8"];', plugin)
        self.assertIn('const hookRoot = "C:/hooks";', plugin)

    def test_the_plugin_runs_a_launcher_that_has_arguments_and_blocks_what_the_hook_denies(self):
        fake = self.fake("fake.js", self.FAKE)
        plugin = self.build(f"{NODE} --no-warnings {fake}")
        result = self.drive(plugin)
        self.assertEqual(result["denied"], "nope")
        first = self.calls()[0]
        self.assertEqual(first["args"][:2], ["-X", "utf8"])
        self.assertTrue(first["args"][2].endswith("/pre_tool_use.py"), first)
        self.assertEqual(first["cwd"], str(plugin.parent))
        self.assertIn({"service": "supremeteam-hooks", "level": "warn", "message": "careful"}, result["logs"])

    def test_an_allowed_call_is_not_blocked(self):
        fake = self.fake("fake.js", self.FAKE)
        plugin = self.build(f"{NODE} --no-warnings {fake}")
        self.assertIs(self.drive(plugin, "ls")["denied"], False)

    def test_an_interpreter_that_cannot_start_is_reported_once_and_never_blocks(self):
        plugin = self.build(str(self.tmp / "no-such" / "python"))
        result = self.drive(plugin)
        self.assertIs(result["denied"], False)
        warnings = [entry for entry in result["logs"] if "not running" in entry["message"]]
        self.assertEqual(len(warnings), 1, result["logs"])
        self.assertIn("ENOENT", warnings[0]["message"])
        self.assertEqual(warnings[0]["level"], "warn")

    def test_a_hook_that_exits_with_an_error_is_reported_once(self):
        fail = self.fake("fail.js", self.FAILING)
        plugin = self.build(f"{NODE} --no-warnings {fail}")
        result = self.drive(plugin)
        self.assertIs(result["denied"], False)
        warnings = [entry for entry in result["logs"] if "not running" in entry["message"]]
        self.assertEqual(len(warnings), 1, result["logs"])
        self.assertIn("exited with status 1: boom", warnings[0]["message"])

    def test_the_generated_file_is_valid_javascript(self):
        plugin = self.build(f"{NODE} --no-warnings {self.fake('fake.js', self.FAKE)}")
        done = subprocess.run([NODE, "--check", str(plugin)], text=True, capture_output=True, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)


@unittest.skipUnless(BASH and INSTALL_SH.is_file(), "needs bash and scripts/install.sh")
class ShellWrapperTests(unittest.TestCase):
    """install.sh forwards the scope and confirmation options to install_hooks.py.

    The helper is replaced by a stub that records its arguments and exits with the
    code the test asks for; everything else is the real installer and the real catalog.
    """

    STUB = ("import json, os, sys\n"
            "open(os.environ['STUB_LOG'], 'w').write(json.dumps(sys.argv[1:]))\n"
            "sys.exit(int(os.environ.get('STUB_EXIT', '0')))\n")

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name).resolve()
        cls.repo = cls.root / "checkout"
        (cls.repo / "scripts").mkdir(parents=True)
        shutil.copy2(INSTALL_SH, cls.repo / "scripts" / "install.sh")
        shutil.copy2(REPO / "scripts" / "install-items.txt", cls.repo / "scripts" / "install-items.txt")
        (cls.repo / "scripts" / "install_hooks.py").write_text(cls.STUB, encoding="utf-8")
        shutil.copytree(REPO / "skills", cls.repo / "skills", ignore=shutil.ignore_patterns("__pycache__", ".harness-state", "skillset-saves"))
        # install.sh looks for a Python 3.13 under the name python3 or python.
        cls.bin = cls.root / "bin"
        cls.bin.mkdir()
        (cls.bin / "python3").symlink_to(sys.executable)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_installer(self, *args: str, exit_code: int = 0) -> tuple[subprocess.CompletedProcess, list | None]:
        work = Path(tempfile.mkdtemp(dir=self.root))
        home = work / "home"
        home.mkdir()
        log = work / "stub.json"
        env = {**os.environ, "HOME": str(home), "STUB_LOG": str(log), "STUB_EXIT": str(exit_code),
               "PATH": os.pathsep.join([str(self.bin), os.environ.get("PATH", "")])}
        result = subprocess.run([BASH, str(self.repo / "scripts" / "install.sh"), "--destination", str(work / "dest"),
                                 "--target", "claude", "--claude-destination", str(work / "claude"), *args],
                                capture_output=True, text=True, env=env, cwd=str(work), timeout=180, check=False)
        return result, json.loads(log.read_text(encoding="utf-8")) if log.is_file() else None

    def test_the_default_scope_is_user_and_nothing_pre_answers_the_question(self):
        result, forwarded = self.run_installer("--register-hooks")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(forwarded[forwarded.index("--scope") + 1], "user")
        self.assertNotIn("--yes", forwarded)
        self.assertIn("Hook registration: completed", result.stdout)

    def test_scope_and_yes_are_forwarded(self):
        result, forwarded = self.run_installer("--register-hooks", "--hooks-scope", "project", "--hooks-yes")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(forwarded[forwarded.index("--scope") + 1], "project")
        self.assertIn("--yes", forwarded)
        self.assertIn("claude", forwarded[forwarded.index("--target") + 1])

    def test_declining_is_reported_as_declined_not_completed(self):
        result, _ = self.run_installer("--register-hooks", exit_code=3)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Supreme Team installation complete.", result.stdout)
        self.assertIn("Hook registration: declined (nothing was written)", result.stdout)
        self.assertNotIn("Hook registration: completed", result.stdout)

    def test_a_failed_registration_still_fails_the_installer(self):
        result, _ = self.run_installer("--register-hooks", exit_code=2)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Supreme Team installation complete.", result.stdout)

    def test_an_unknown_scope_is_refused_before_anything_is_written(self):
        result, forwarded = self.run_installer("--register-hooks", "--hooks-scope", "galaxy")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--hooks-scope must be user, project or local", result.stderr)
        self.assertIsNone(forwarded)

    def test_a_missing_scope_value_is_refused(self):
        result, _ = self.run_installer("--register-hooks", "--hooks-scope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Missing value for --hooks-scope", result.stderr)

    def test_help_documents_the_options_and_what_registration_edits(self):
        result = subprocess.run([BASH, str(INSTALL_SH), "--help"], capture_output=True, text=True, check=False)
        for text in ("--hooks-scope SCOPE", "--hooks-yes", "host config files", "previews them and asks first"):
            self.assertIn(text, result.stdout)


@unittest.skipUnless(INSTALL_PS1.is_file() and INSTALL_SH.is_file(), "needs both installers")
class PowerShellWrapperTests(unittest.TestCase):
    """PowerShell cannot run here, so the wrapper is held to the tested shell one by static checks."""

    def setUp(self):
        self.ps = INSTALL_PS1.read_text(encoding="utf-8")
        self.sh = INSTALL_SH.read_text(encoding="utf-8")

    def test_the_parameters_mirror_the_shell_options(self):
        self.assertRegex(self.ps, r'\[ValidateSet\("User", "Project", "Local"\)\]\s*\[string\]\$HooksScope = "User"')
        self.assertRegex(self.ps, r"\[switch\]\$HooksYes")
        self.assertIn("user|project|local", self.sh)

    def test_the_helper_receives_the_scope_and_the_confirmation_switch(self):
        body = re.search(r"function Register-HarnessHooks \{\n(.*?)\n\}\n", self.ps, re.S).group(1)
        self.assertIn('$hookArgs += @("--scope", $HooksScope.ToLowerInvariant())', body)
        self.assertRegex(body, r'if \(\$HooksYes\) \{\s*\$hookArgs \+= "--yes"')

    def test_exit_3_is_a_decline_and_any_other_failure_still_throws(self):
        body = re.search(r"function Register-HarnessHooks \{\n(.*?)\n\}\n", self.ps, re.S).group(1)
        self.assertRegex(body, r"if \(\$LASTEXITCODE -eq 3\) \{\s*\$script:hooksDeclined = \$true\s*\}\s*"
                               r'elseif \(\$LASTEXITCODE -ne 0\) \{\s*throw "Hook registration failed\."')
        shell = re.search(r"register_harness_hooks\(\) \{\n(.*?)\n\}\n", self.sh, re.S).group(1)
        self.assertIn("-eq 3", shell)

    def test_the_declined_flag_is_initialised_before_strict_mode_can_read_it(self):
        self.assertLess(self.ps.index("$script:hooksDeclined = $false"), self.ps.index("function Register-HarnessHooks"))
        self.assertIn('$hookStatus = "declined (nothing was written)"', self.ps)
        self.assertIn("Hook registration: declined (nothing was written)", self.sh)


if __name__ == "__main__":
    unittest.main()
