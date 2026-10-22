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

import _testkit as kit
import repair_registration as repair
import verify_registration as verify

HOOK_DIR = Path(__file__).resolve().parent
REPO = HOOK_DIR.parents[2]
INSTALLER = REPO / "scripts" / "install_hooks.py"
INSTALL_SH = REPO / "scripts" / "install.sh"
INSTALL_PS1 = REPO / "scripts" / "install.ps1"
NODE = shutil.which("node")
# A directory whose node_modules holds typescript, @types/node and @earendil-works/pi-coding-agent (CI's pi job
# installs them and points SUPREMETEAM_PI_TYPES at them; a provisioned checkout keeps them under the harness's
# own test scratch so the type-check runs wherever npm has run once).
PI_TYPES_ENV = os.environ.get("SUPREMETEAM_PI_TYPES")
PI_TYPES_DEFAULT = HOOK_DIR.parents[2] / ".harness-state" / "test-work" / "pi-types"
PI_TYPES = next((str(Path(candidate)) for candidate in (PI_TYPES_ENV, PI_TYPES_DEFAULT)
                 if candidate and (Path(candidate) / "node_modules" / "typescript").is_dir()), None)


def _node_strips_types() -> bool:
    """Whether this node can import a .ts module (type stripping, node 22.6 and later)."""
    if not NODE:
        return False
    done = subprocess.run([NODE, "--experimental-strip-types", "--no-warnings", "-e", ""], capture_output=True, check=False)
    return done.returncode == 0


def write_catalog(skills: Path) -> None:
    """What install.sh copies and checks, without the 400-odd files of the real tree: every item install-items.txt
    selects, each skill directory as a SKILL.md, the real runtime contract (install.sh reads its Python floor) and a
    line of text for each other file."""
    for line in (REPO / "scripts" / "install-items.txt").read_text(encoding="utf-8").splitlines():
        kind, *words = line.split() or ("",)
        names = words[:1] if kind in ("core", "seed") else words[1:] if kind == "team" else []
        for name in names:
            source, target = REPO / "skills" / name, skills / name
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                (target / "SKILL.md").write_text(f"{name}\n", encoding="utf-8")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                if name == "runtime-manifest.yaml":
                    shutil.copy2(source, target)
                else:
                    target.write_text(f"{name}\n", encoding="utf-8")


NODE_TS = _node_strips_types()
BASH = kit.find_bash()
POSIX = os.name == "posix"


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
        return kit.plain_env(self.home, **extra)

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

    def test_a_usable_interpreter_and_an_explicit_config_path_get_no_note(self):
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
fs.appendFileSync(process.env.SUPREMETEAM_FAKE_LOG, JSON.stringify({ args, cwd: process.env.SUPREMETEAM_PROJECT_DIR }) + "\\n");
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
                              env=self.env(SUPREMETEAM_FAKE_LOG=str(log)), check=False)
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


def _installer_module():
    spec = importlib.util.spec_from_file_location("install_hooks_under_test", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PiRegistrationTests(InstallerCase):
    """``--target pi`` writes one TypeScript extension where pi loads global extensions."""

    def test_a_dry_run_previews_and_writes_nothing(self):
        path = self.tmp / "ext" / "supremeteam-guard.ts"
        result = self.install("--target", "pi", "--pi-extension", str(path), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("(proposed)", result.stdout)
        self.assertIn('from "@earendil-works/pi-coding-agent"', result.stdout)
        self.assertFalse(path.exists())

    def test_it_writes_once_and_a_second_run_changes_nothing(self):
        path = self.tmp / "ext" / "supremeteam-guard.ts"
        first = self.install("--target", "pi", "--pi-extension", str(path), "--json")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertIn("written, but not machine-verifiable", first.stdout)
        self.assertIn("SupremeTeam guard active", first.stdout, "the operator is told what the next session shows")
        report = json.loads(first.stdout.split("JSON_REPORT: ", 1)[1])
        self.assertEqual(report["hosts"][0]["host"], "pi")
        self.assertIsNone(report["hosts"][0]["registered"])
        self.assertIn(str(HOOK_DIR).replace("\\", "/"), path.read_text(encoding="utf-8"))
        second = self.install("--target", "pi", "--pi-extension", str(path))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("no changes: already registered", second.stdout)
        self.assertEqual(list(path.parent.glob("*.bak-*")), [])

    def test_the_default_path_is_pis_global_extension_directory(self):
        result = self.install("--target", "pi", "--dry-run")
        self.assertIn(f"config: {self.home / '.pi' / 'agent' / 'extensions' / 'supremeteam-guard.ts'}", result.stdout)
        agent = self.tmp / "pi-agent"
        result = self.install("--target", "pi", "--dry-run", PI_CODING_AGENT_DIR=str(agent))
        self.assertIn(f"config: {agent / 'extensions' / 'supremeteam-guard.ts'}", result.stdout)

    def test_the_extension_is_owner_only(self):
        path = self.tmp / "ext" / "supremeteam-guard.ts"
        self.install("--target", "pi", "--pi-extension", str(path))
        if os.name == "nt":
            # chmod is a read-only flag on Windows; owner-only there means the access list holds the current user
            # and nothing inherited (repair_registration._restrict_to_owner).
            import getpass
            import subprocess as sp

            listed = sp.run(["icacls", str(path)], capture_output=True, text=True, check=False, timeout=30).stdout
            self.assertIn(getpass.getuser(), listed)
            for granted in ("Everyone", "BUILTIN\\Users", "Authenticated Users"):
                self.assertNotIn(granted, listed)
        else:
            self.assertEqual(self.mode(path), 0o600)

    def test_a_non_utf8_extension_is_refused(self):
        path = self.tmp / "supremeteam-guard.ts"
        path.write_bytes(b"\xff\xfe//")
        result = self.install("--target", "pi", "--pi-extension", str(path))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), b"\xff\xfe//")

    def test_launchers_are_split_for_a_shell_free_spawn(self):
        module = _installer_module()
        for launcher, command, args in (
            ("py -3", "py", ["-3", "-X", "utf8"]),
            # F-R2: a spaced interpreter path that carries options is one command, not two words.
            ("C:/Program Files/Python313/python.exe -X dev", "C:/Program Files/Python313/python.exe", ["-X", "dev", "-X", "utf8"]),
            ("C:/Program Files/Python313/python.exe", "C:/Program Files/Python313/python.exe", ["-X", "utf8"]),
        ):
            with self.subTest(launcher=launcher):
                source = module.pi_extension_source(launcher, "C:\\hooks", repair, "3.13")
                self.assertIn(f"const pythonCommand: string = {json.dumps(command)};", source)
                self.assertIn(f"const pythonArgs: readonly string[] = {json.dumps(args)};", source)
                self.assertIn('const hookRoot: string = "C:/hooks";', source)

    def test_the_environment_list_covers_what_the_hooks_read(self):
        names = _installer_module().hook_env_names(repair)
        for name in ("PATH", "SYSTEMROOT", "HOME", "USERPROFILE", "TMPDIR", "TEMP", "LOCALAPPDATA", "PI_CODING_AGENT_DIR",
                     *repair._state.PROJECT_ENV):
            self.assertIn(name, names)
        self.assertFalse([name for name in names if name.startswith("PYTHON")])


@unittest.skipUnless(NODE_TS, "needs node 22.6 or later (type stripping) to load the TypeScript extension")
class PiExtensionTests(InstallerCase):
    """The generated extension, loaded by node the way pi's loader would and driven through pi's event shapes."""

    FAKE = r"""const fs = require("fs");
const args = process.argv.slice(2);
const log = process.env.SUPREMETEAM_FAKE_LOG;
if (args.includes("-c")) {
  fs.appendFileSync(log, JSON.stringify({ probe: args.slice(args.indexOf("-c") + 2) }) + "\n");
  const version = process.env.SUPREMETEAM_FAKE_VERSION || "3.13.9";
  process.stdout.write(JSON.stringify({ version, meets_floor: !process.env.SUPREMETEAM_FAKE_VERSION, missing: [] }));
  process.exit(0);
}
const payload = JSON.parse(fs.readFileSync(0, "utf8") || "{}");
const script = args[args.length - 1].split("/").pop();
fs.appendFileSync(log, JSON.stringify({ script, args, payload, env: Object.keys(process.env), project: process.env.SUPREMETEAM_PROJECT_DIR }) + "\n");
if (script === "pre_tool_use.py" && payload.tool_input && payload.tool_input.command === "danger") {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { permissionDecision: "deny", permissionDecisionReason: "nope" } }));
} else if (script === "post_tool_use.py") {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { additionalContext: "careful" } }));
} else if (script === "user_prompt_submit.py") {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { additionalContext: "route through admiral" } }));
}
"""
    # Stands in for pi: collects the handlers the extension registers and fires the events a script lists.
    DRIVER = r"""import guard from "./supremeteam-guard.ts";
const handlers = {};
guard({ on: (name, handler) => { (handlers[name] ||= []).push(handler); } });
const notes = [];
const status = {};
const ui = { notify: (message, type) => notes.push({ message, type }), setStatus: (key, text) => { status[key] = text; } };
const context = (session, cwd) => ({
  cwd,
  ui,
  sessionManager: { getSessionId: () => { if (session === null) throw new Error("no session"); return session; } },
});
const results = [];
for (const step of JSON.parse(process.argv[2])) {
  let result;
  for (const handler of handlers[step.event] || []) result = await handler(step.payload, context("session" in step ? step.session : "s1", step.cwd || process.cwd()));
  results.push(result === undefined ? null : result);
}
console.log(JSON.stringify({ results, notes, status, events: Object.keys(handlers).sort() }));
"""

    def build(self, python_command: str) -> Path:
        path = self.tmp / "work" / "supremeteam-guard.ts"
        path.parent.mkdir(exist_ok=True)
        (path.parent / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        result = self.install("--target", "pi", "--pi-extension", str(path), "--python-command", python_command)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (path.parent / "driver.mjs").write_text(self.DRIVER, encoding="utf-8")
        return path

    def fake(self) -> str:
        path = self.tmp / "work" / "fake.cjs"
        path.parent.mkdir(exist_ok=True)
        path.write_text(self.FAKE, encoding="utf-8")
        return f"{NODE} --no-warnings {path}"

    def drive(self, extension: Path, steps: list, cwd: Path | None = None, **env: str) -> dict:
        done = subprocess.run([NODE, "--experimental-strip-types", "--no-warnings", str(extension.parent / "driver.mjs"), json.dumps(steps)],
                              text=True, capture_output=True, cwd=str(cwd or extension.parent),
                              env=self.env(SUPREMETEAM_FAKE_LOG=str(self.tmp / "fake.log"), **env), check=False, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return json.loads(done.stdout.strip().splitlines()[-1])

    def calls(self) -> list[dict]:
        log = self.tmp / "fake.log"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.is_file() else []

    @staticmethod
    def bash(command: str, session: str | None = "s1") -> dict:
        return {"event": "tool_call", "session": session, "payload": {"type": "tool_call", "toolCallId": "t", "toolName": "bash", "input": {"command": command}}}

    def test_it_subscribes_to_the_events_it_bridges(self):
        result = self.drive(self.build(self.fake()), [])
        self.assertEqual(result["events"], ["before_agent_start", "input", "session_start", "tool_call", "tool_result"])

    def test_a_denied_call_is_blocked_with_the_guard_reason_and_an_allowed_one_passes(self):
        result = self.drive(self.build(self.fake()), [self.bash("danger"), self.bash("ls")])
        self.assertEqual(result["results"], [{"block": True, "reason": "nope"}, None])
        pre = [call for call in self.calls() if call.get("script") == "pre_tool_use.py"]
        self.assertEqual(pre[0]["payload"]["tool_name"], "Bash")
        self.assertEqual(pre[0]["payload"]["tool_input"], {"command": "danger"})
        self.assertEqual(pre[0]["args"][-3:-1], ["-X", "utf8"])

    def test_every_call_carries_pis_own_session_id(self):
        """F-R3: the session identity was one constant for every pi session."""
        self.drive(self.build(self.fake()), [self.bash("ls", "alpha"), self.bash("ls", "beta"), self.bash("ls", None)])
        ids = [call["payload"]["session_id"] for call in self.calls() if call.get("script") == "pre_tool_use.py"]
        self.assertEqual(ids[:2], ["pi:alpha", "pi:beta"])
        self.assertRegex(ids[2], r"^pi:pid-\d+$", "a session with no id falls back to this process, never a shared constant")

    def test_the_hook_gets_a_filtered_environment_and_the_project_directory(self):
        """F-R5: the hook interpreter inherited pi's whole environment, PYTHONPATH included."""
        project = self.tmp / "work"
        self.drive(self.build(self.fake()), [self.bash("ls")], cwd=project,
                   PYTHONPATH=str(self.tmp / "planted"), PYTHONHOME=str(self.tmp), SOME_API_TOKEN="secret",
                   SUPREMETEAM_SAMPLE="1", CLAUDE_PROJECT_DIR=str(project))
        call = self.calls()[0]
        for name in ("PYTHONPATH", "PYTHONHOME", "SOME_API_TOKEN"):
            self.assertNotIn(name, call["env"])
        for name in ("SUPREMETEAM_SAMPLE", "CLAUDE_PROJECT_DIR", "HOME"):
            self.assertIn(name, call["env"])
        self.assertEqual(call["project"], str(project))

    def test_post_tool_context_is_appended_to_the_result_the_model_sees(self):
        step = {"event": "tool_result", "payload": {"type": "tool_result", "toolCallId": "t", "toolName": "bash", "input": {"command": "ls"},
                                                    "content": [{"type": "text", "text": "a.txt"}], "details": None, "isError": False}}
        result = self.drive(self.build(self.fake()), [step])
        self.assertEqual(result["results"][0]["content"], [{"type": "text", "text": "a.txt"}, {"type": "text", "text": "[SupremeTeam] careful"}])
        post = [call for call in self.calls() if call.get("script") == "post_tool_use.py"][0]
        self.assertEqual(post["payload"]["tool_response"]["content"], [{"type": "text", "text": "a.txt"}])

    def test_prompt_context_is_injected_before_the_agent_starts_once(self):
        steps = [{"event": "input", "payload": {"type": "input", "text": "build me a thing", "source": "interactive"}},
                 {"event": "before_agent_start", "payload": {"type": "before_agent_start", "prompt": "build me a thing"}},
                 {"event": "before_agent_start", "payload": {"type": "before_agent_start", "prompt": "again"}},
                 {"event": "input", "payload": {"type": "input", "text": "from an extension", "source": "extension"}}]
        result = self.drive(self.build(self.fake()), steps)
        self.assertEqual(result["results"][0], {"action": "continue"})
        self.assertEqual(result["results"][1], {"message": {"customType": "supremeteam-guard", "content": "route through admiral", "display": False}})
        self.assertIsNone(result["results"][2])
        prompts = [call["payload"]["prompt"] for call in self.calls() if call.get("script") == "user_prompt_submit.py"]
        self.assertEqual(prompts, ["build me a thing"])

    def test_session_start_reports_that_the_guard_is_enforcing(self):
        """g-1: whether the guard fires in pi was only observable by trying a denied call."""
        result = self.drive(self.build(self.fake()), [{"event": "session_start", "payload": {"type": "session_start", "reason": "startup"}}])
        self.assertEqual(result["status"], {"supremeteam-guard": "SupremeTeam guard: on"})
        self.assertEqual(result["notes"][0]["type"], "info")
        self.assertIn("SupremeTeam guard active: Python 3.13.9", result["notes"][0]["message"])
        self.assertEqual(self.calls()[0]["probe"][:2], [str(HOOK_DIR).replace("\\", "/"), verify.declared_minimum()])

    def test_session_start_names_an_interpreter_below_the_floor(self):
        result = self.drive(self.build(self.fake()), [{"event": "session_start", "payload": {}}], SUPREMETEAM_FAKE_VERSION="3.11.2")
        self.assertEqual(result["status"], {"supremeteam-guard": "SupremeTeam guard: off"})
        self.assertIn(f"Python 3.11.2 is below the {verify.declared_minimum()} floor", result["notes"][0]["message"])
        self.assertEqual(result["notes"][0]["type"], "warning")

    def test_an_interpreter_that_cannot_start_never_blocks_and_is_reported_once_per_session(self):
        extension = self.build(str(self.tmp / "no-such" / "python"))
        result = self.drive(extension, [{"event": "session_start", "payload": {}}, self.bash("danger"), self.bash("danger")])
        self.assertEqual(result["results"], [None, None, None])
        self.assertEqual(result["status"], {"supremeteam-guard": "SupremeTeam guard: off"})
        warnings = [note for note in result["notes"] if "not enforcing" in note["message"]]
        self.assertEqual(len(warnings), 1, result["notes"])
        self.assertIn("ENOENT", warnings[0]["message"])

    def test_a_fault_in_the_bridge_fails_open_and_is_reported(self):
        result = self.drive(self.build(self.fake()), [{"event": "tool_call", "payload": {"type": "tool_call", "input": {}}}])
        self.assertEqual(result["results"], [None])
        self.assertIn("bridge error", result["notes"][0]["message"])

    def test_the_real_guard_blocks_through_the_extension(self):
        """The live drive: the real interpreter and the real pre_tool_use.py, in a scratch project."""
        project = self.project
        result = self.drive(self.build(sys.executable), [
            {"event": "session_start", "cwd": str(project), "payload": {}},
            {**self.bash("git push --force origin main"), "cwd": str(project)},
            {**self.bash("ls"), "cwd": str(project)},
            {"event": "tool_result", "cwd": str(project), "payload": {"type": "tool_result", "toolCallId": "t", "toolName": "bash",
                                                                     "input": {"command": "ls"}, "content": [], "isError": False}},
            {"event": "input", "cwd": str(project), "payload": {"type": "input", "text": "hello", "source": "interactive"}},
        ])
        self.assertIn("SupremeTeam guard active", result["notes"][0]["message"])
        blocked = result["results"][1]
        self.assertIs(blocked["block"], True)
        self.assertIn("force-push", blocked["reason"])
        self.assertIsNone(result["results"][2])
        self.assertFalse([note for note in result["notes"] if "not enforcing" in note["message"]], result["notes"])


@unittest.skipUnless(PI_TYPES, "set SUPREMETEAM_PI_TYPES to a directory whose node_modules holds typescript, @types/node "
                               "and @earendil-works/pi-coding-agent (the CI pi job does)")
class PiTypeCheckTests(InstallerCase):
    """F-R4: the extension was only transpiled and run, never type-checked against pi's API."""

    def test_the_extension_type_checks_strictly_against_pis_published_types(self):
        types = Path(PI_TYPES).resolve()
        tsc = types / "node_modules" / "typescript" / "bin" / "tsc"
        self.assertTrue(tsc.is_file(), f"{tsc} is missing")
        self.assertTrue((types / "node_modules" / "@earendil-works" / "pi-coding-agent").is_dir())
        # tsc resolves the pi import from the file's own directory upwards, so the file is checked beside node_modules.
        path = types / f"supremeteam-guard-{os.getpid()}.ts"
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        result = self.install("--target", "pi", "--pi-extension", str(path), "--python-command", "py -3")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        done = subprocess.run([NODE or "node", str(tsc), "--noEmit", "--strict", "--target", "es2022", "--module", "nodenext",
                               "--moduleResolution", "nodenext", "--skipLibCheck", "--types", "node", str(path)],
                              text=True, capture_output=True, cwd=str(types), check=False, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


@unittest.skipUnless(BASH and INSTALL_SH.is_file(), "needs bash and scripts/install.sh")
class ShellWrapperTests(unittest.TestCase):
    """install.sh forwards the scope and confirmation options to install_hooks.py.

    The helper is replaced by a stub that records its arguments and exits with the
    code the test asks for; everything else is the real installer, run on a catalog of
    stand-ins for the items it installs (``write_catalog``).
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
        write_catalog(cls.repo / "skills")
        # install.sh looks for a Python 3.13 under the name python3 or python.
        cls.bin = cls.root / "bin"
        cls.bin.mkdir()
        try:
            (cls.bin / "python3").symlink_to(sys.executable)
        except OSError:
            # No symlink privilege here: a launcher script names the same interpreter for install.sh's probe.
            shim = cls.bin / "python3"
            shim.write_text(f'#!/bin/sh\nexec "{Path(sys.executable).as_posix()}" "$@"\n', encoding="utf-8")
            shim.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def run_installer(self, *args: str, exit_code: int = 0) -> tuple[subprocess.CompletedProcess, list | None]:
        work = Path(tempfile.mkdtemp(dir=self.root))
        home = work / "home"
        home.mkdir()
        log = work / "stub.json"
        env = kit.plain_env(home, STUB_LOG=str(log), STUB_EXIT=str(exit_code),
                            PATH=os.pathsep.join([str(self.bin), os.environ.get("PATH", "")]))
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

    def test_a_failed_registration_still_fails_the_installer_and_the_summary_says_so(self):
        """The script stopped at the helper's exit status with no summary, after the skills were already copied."""
        result, _ = self.run_installer("--register-hooks", exit_code=2)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Supreme Team installation complete.", result.stdout, "it did not complete")
        self.assertIn("Supreme Team skills are installed, but hook registration failed.", result.stdout)
        self.assertIn("Hook registration: failed (exit status 2; see the messages above)", result.stdout)
        self.assertIn("Installed items:", result.stdout)
        self.assertRegex(result.stdout, r"repair_registration\.py\" --host <host> --scope user")
        self.assertNotIn("Hook registration: completed", result.stdout)
        self.assertTrue(list(Path(result.stdout.split("Target: ", 1)[1].splitlines()[0]).glob("admiral")), "the skills are in place")

    def test_a_failed_registration_names_the_scope_it_was_asked_for(self):
        result, _ = self.run_installer("--register-hooks", "--hooks-scope", "project", exit_code=2)
        self.assertRegex(result.stdout, r"repair_registration\.py\" --host <host> --scope project")

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

    def test_exit_3_is_a_decline_and_any_other_failure_is_recorded_for_the_summary_and_the_exit_status(self):
        body = re.search(r"function Register-HarnessHooks \{\n(.*?)\n\}\n", self.ps, re.S).group(1)
        self.assertRegex(body, r"if \(\$LASTEXITCODE -eq 3\) \{\s*\$script:hooksDeclined = \$true\s*\}\s*"
                               r"elseif \(\$LASTEXITCODE -ne 0\) \{\s*\$script:hooksFailed = \$LASTEXITCODE")
        self.assertNotIn("throw", body, "a failed registration is reported after the summary, not thrown before it")
        shell = re.search(r"register_harness_hooks\(\) \{\n(.*?)\n\}\n", self.sh, re.S).group(1)
        self.assertIn("-eq 3", shell)
        self.assertIn("hooks_failed=$status", shell)
        self.assertNotRegex(shell, r"(?m)^\s*exit\b", "a failed registration is reported after the summary, not left before it")
        main = self.ps[self.ps.index("try {\n    Import-ItemList"):]
        self.assertLess(main.index("Hook registration: $hookStatus"), main.index("exit $script:hooksFailed"),
                        "the summary comes first and the failing status after it")
        self.assertLess(self.sh.rindex("Hook registration: failed"), self.sh.rindex('exit "$hooks_failed"'))
        self.assertLess(self.ps.index("$script:hooksFailed = 0"), self.ps.index("function Register-HarnessHooks"))

    def test_the_declined_flag_is_initialised_before_strict_mode_can_read_it(self):
        self.assertLess(self.ps.index("$script:hooksDeclined = $false"), self.ps.index("function Register-HarnessHooks"))
        self.assertIn('$hookStatus = "declined (nothing was written)"', self.ps)
        self.assertIn("Hook registration: declined (nothing was written)", self.sh)


if __name__ == "__main__":
    unittest.main()
