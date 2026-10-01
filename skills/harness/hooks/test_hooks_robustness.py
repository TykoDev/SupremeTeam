#!/usr/bin/env python3
"""The hardening claims the README makes, each one run against the registered hooks (SEC-17).

The README credited ``test_hooks_hardening.py`` with path canonicalisation, Windows-versus-POSIX separators, symlink
protection, malformed-JSON fuzzing and universal fail-open. That file holds registration, trajectory and freeze-record
tests; none of those five existed anywhere end to end. They are here:

* spellings of one path that every rule must treat as the same path, in the separators of both platforms;
* links that lead out of an allowed or into a frozen tree, and links the hooks must not follow;
* a fixed-seed fuzz of the three registered hooks with mutated valid payloads: exit 0, no traceback, no internal fault
  for a payload that parses, and a dangerous command still denied however much noise surrounds it;
* universal fail-open: every hook, with its own internals made to fail or its state made unusable, exits 0 silently,
  counts the fault, and a deny stays a deny.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _testkit as kit  # noqa: E402

SEED = 20260929
SCRIPTS = {"PreToolUse": "pre_tool_use.py", "PostToolUse": "post_tool_use.py", "UserPromptSubmit": "user_prompt_submit.py"}
MODULES = {"PreToolUse": "pre_tool_use", "PostToolUse": "post_tool_use", "UserPromptSubmit": "user_prompt_submit"}
FROZEN = {"frozen_globs": [{"glob": "src/payments/**", "owner": "ops", "scope": "release"}]}


def can_link() -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink(tmp, Path(tmp) / "probe", target_is_directory=True)
            return True
        except (OSError, NotImplementedError):
            return False


class Project(unittest.TestCase):
    def setUp(self):
        manager = kit.project()
        self.root = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        self.scratch = self.root / "tmp"
        self.scratch.mkdir()
        self.env = {"TMPDIR": str(self.scratch), "TEMP": str(self.scratch), "TMP": str(self.scratch), "HOME": str(self.root / "home"),
                    "USERPROFILE": str(self.root / "home")}

    def entry(self, payload, module: str = "pre_tool_use", function: "str | None" = None) -> str:
        """The registered entry's stdout, run in this process with the project and home of this case.

        ``run`` is the fail-open entry the registered scripts call; a module without one (an older tree) is driven through ``main``."""
        saved = {name: os.environ.get(name) for name in self.env}
        os.environ.update(self.env)
        try:
            import importlib

            function = function or ("run" if hasattr(importlib.import_module(module), "run") else "main")
            return kit.decide(payload, self.root, module=module, entry=function)
        finally:
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def script(self, event: str, payload) -> subprocess.CompletedProcess:
        return kit.run_hook(SCRIPTS[event], payload, self.root, **self.env)

    def faults(self, event: str) -> dict:
        path = self.root / ".harness-state" / "observations" / f"{event}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


class PathCanonicalisationTests(Project):
    """One path has many spellings; the guard decides on the path, not the spelling."""

    def setUp(self):
        super().setUp()
        kit.write_guard(self.root, FROZEN)

    def spellings(self, tail: str = "a.py") -> list:
        base = "src/payments"
        return [f"{base}/{tail}", f"./{base}/{tail}", f"src//payments//{tail}", f"src/./payments/./{tail}", f"src/other/../payments/{tail}",
                f"{self.root}/{base}/{tail}", f"{self.root}/src/../{base}/{tail}", f"{self.root}//{base}/{tail}", f"./src/payments/../payments/{tail}"]

    def test_every_spelling_of_a_frozen_path_is_denied_to_every_edit_tool(self):
        for spelling in self.spellings():
            for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
                with self.subTest(spelling=spelling, tool=tool):
                    self.assertTrue(kit.denied(self.entry(kit.edit(spelling, tool))))

    def test_every_spelling_is_denied_to_the_shell_too(self):
        for spelling in self.spellings():
            with self.subTest(spelling=spelling):
                self.assertTrue(kit.denied(self.entry(kit.bash(f"echo x > {spelling}"))))
                self.assertTrue(kit.denied(self.entry(kit.bash(f"sed -i s/a/b/ {spelling}"))))

    def test_neighbours_of_the_frozen_tree_are_not_denied(self):
        for neighbour in ("src/payments-old/a.py", "src/paymentsx", "docs/src/payments/a.py", "src/pay/ments/a.py", "src/payment/a.py"):
            with self.subTest(path=neighbour):
                self.assertEqual(self.entry(kit.edit(neighbour)), "")
                self.assertEqual(self.entry(kit.bash(f"echo x > {neighbour}")), "")

    def test_a_case_variant_of_a_frozen_path_is_denied_everywhere_and_of_an_allowed_one_only_where_case_is_ignored(self):
        """Deny is conservative (a case-insensitive file system needs it, a case-sensitive one loses nothing); allow is exact."""
        self.assertTrue(kit.denied(self.entry(kit.edit("SRC/Payments/a.py"))))
        kit.write_guard(self.root, {"read_only": [{"run_id": "r1", "owner": "o", "allow": ["skillset-saves/runs/r1/**"]}]})
        inside_the_allow_list = not kit.denied(self.entry(kit.edit("SKILLSET-SAVES/runs/r1/notes.md")))
        import _paths

        self.assertEqual(inside_the_allow_list, _paths.case_insensitive_fs())

    def test_the_registered_script_decides_the_same_way_as_the_in_process_entry(self):
        for spelling, expected in (("src/other/../payments/a.py", True), (f"{self.root}//src/payments/a.py", True), ("src/other/a.py", False)):
            with self.subTest(spelling=spelling):
                proc = self.script("PreToolUse", kit.edit(spelling))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(kit.denied(proc.stdout.decode("utf-8")), expected)

    def test_a_read_only_allow_list_is_not_escaped_with_dot_dot(self):
        kit.write_guard(self.root, {"read_only": [{"run_id": "r1", "owner": "o", "allow": ["skillset-saves/runs/r1/**"]}]})
        for target in ("skillset-saves/runs/r1/../r2/_state.md", "skillset-saves/runs/r1/../../../src/app.py", "src/app.py"):
            with self.subTest(target=target):
                self.assertTrue(kit.denied(self.entry(kit.edit(target))))
        self.assertEqual(self.entry(kit.edit("skillset-saves/runs/r1/build/notes.md")), "")


class SeparatorTests(Project):
    """Windows and POSIX spell the same path differently; a record written on one is enforced on the other."""

    def test_backslash_and_mixed_spellings_hit_a_forward_slash_boundary(self):
        kit.write_guard(self.root, FROZEN)
        for spelling in ("src\\payments\\a.py", "src/payments\\a.py", ".\\src\\payments\\a.py", "src\\\\payments\\a.py", "src\\other\\..\\payments\\a.py"):
            with self.subTest(spelling=spelling):
                self.assertTrue(kit.denied(self.entry(kit.edit(spelling))))

    def test_a_boundary_recorded_with_backslashes_still_matches_forward_slash_paths(self):
        kit.write_guard(self.root, {"frozen_globs": [{"glob": "src\\payments\\**", "owner": "ops"}]})
        for spelling in ("src/payments/a.py", "src\\payments\\a.py", "./src/payments/a.py"):
            with self.subTest(spelling=spelling):
                self.assertTrue(kit.denied(self.entry(kit.edit(spelling))))
        self.assertEqual(self.entry(kit.edit("src/other/a.py")), "")

    def test_a_windows_drive_letter_path_under_a_posix_root_is_judged_by_its_tail(self):
        kit.write_guard(self.root, FROZEN)
        for spelling in ("C:\\work\\proj\\src\\payments\\a.py", "C:/work/proj/src/payments/a.py", "\\\\?\\C:\\work\\proj\\src\\payments\\a.py"):
            with self.subTest(spelling=spelling):
                self.assertTrue(kit.denied(self.entry(kit.edit(spelling))))
        self.assertEqual(self.entry(kit.edit("C:\\work\\proj\\src\\other\\a.py")), "")

    def test_the_windows_shell_verbs_are_writes_too(self):
        kit.write_guard(self.root, FROZEN)
        for command, tool in (("cmd /c \"del src\\payments\\a.py\"", "Bash"), ("cmd /c \"copy x.txt src\\payments\\a.py\"", "Bash"),
                              ("cmd /c \"rd /s /q src\\payments\"", "Bash"), ("del src\\payments\\a.py", "PowerShell"),
                              ("copy x.txt src\\payments\\a.py", "PowerShell"), ("rd src\\payments", "PowerShell"),
                              ("Set-Content -Path src\\payments\\a.py -Value x", "PowerShell"), ("Remove-Item -Recurse src\\payments", "PowerShell"),
                              ("'x' | Out-File src\\payments\\a.py", "PowerShell"), ("Copy-Item x.txt src\\payments\\a.py", "PowerShell")):
            with self.subTest(command=command):
                self.assertTrue(kit.denied(self.entry(kit.bash(command, tool))), command)
        for command, tool in (("cmd /c \"type src\\payments\\a.py\"", "Bash"), ("Get-Content src\\payments\\a.py", "PowerShell"),
                              ("dir src\\payments", "PowerShell"), ("type src\\payments\\a.py", "PowerShell")):
            with self.subTest(command=command):
                self.assertEqual(self.entry(kit.bash(command, tool)), "", command)

    def test_the_writer_stores_every_spelling_as_one_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            guard = [sys.executable, str(HOOK_DIR / "guard_state.py")]
            for glob in ("src\\payments\\**", "./src/payments/**", "src/payments/**", "src//payments//**"):
                subprocess.run([*guard, "freeze", "--glob", glob, "--owner", "ops", "--scope", "s"], capture_output=True, text=True,
                               env=kit.clean_env(project), check=False)
            records = json.loads((project / ".harness-state" / "guard-state.json").read_text(encoding="utf-8"))["frozen_globs"]
            self.assertEqual([record["glob"] for record in records], ["src/payments/**"])


@unittest.skipUnless(can_link(), "this host cannot create symbolic links")
class SymlinkTests(Project):
    def link(self, name: str, target: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(self.root / target, path, target_is_directory=True)

    def test_a_link_into_a_frozen_tree_is_the_frozen_tree(self):
        (self.root / "src" / "payments").mkdir(parents=True)
        self.link("alias", "src/payments")
        kit.write_guard(self.root, FROZEN)
        for tool in ("Edit", "Write", "MultiEdit"):
            self.assertTrue(kit.denied(self.entry(kit.edit("alias/a.py", tool))), tool)
        self.assertTrue(kit.denied(self.entry(kit.bash("echo x > alias/a.py"))))
        self.assertTrue(kit.denied(self.entry(kit.bash("rm -r alias"))))

    def test_a_link_that_leaves_the_read_only_allow_list_does_not_extend_it(self):
        (self.root / "src").mkdir()
        (self.root / "skillset-saves" / "runs" / "r1").mkdir(parents=True)
        self.link("skillset-saves/runs/r1/out", "src")
        kit.write_guard(self.root, {"read_only": [{"run_id": "r1", "owner": "o", "allow": ["skillset-saves/runs/r1/**"]}]})
        self.assertTrue(kit.denied(self.entry(kit.edit("skillset-saves/runs/r1/out/app.py"))))
        self.assertTrue(kit.denied(self.entry(kit.bash("echo x > skillset-saves/runs/r1/out/app.py"))))
        self.assertEqual(self.entry(kit.edit("skillset-saves/runs/r1/notes.md")), "")

    def test_a_link_to_the_guard_record_is_the_guard_record(self):
        (self.root / ".harness-state").mkdir()
        os.symlink(self.root / ".harness-state" / "guard-state.json", self.root / "innocent.json")
        self.assertTrue(kit.denied(self.entry(kit.edit("innocent.json"))))
        self.assertTrue(kit.denied(self.entry(kit.bash("echo {} > innocent.json"))))

    def test_a_linked_state_directory_loses_its_permissive_grants_and_keeps_its_restrictions(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        grant = {"owner": "o", "reason": "r", "scope": "s", "created_at": "2099-01-01T00:00:00Z", "expires_at": "2099-01-01T00:10:00Z"}
        (elsewhere / "guard-state.json").write_text(json.dumps({"allow_dangerous": grant, "frozen_globs": [{"glob": "src/**", "owner": "o"}]}), encoding="utf-8")
        os.symlink(elsewhere, self.root / ".harness-state", target_is_directory=True)
        self.assertTrue(kit.denied(self.entry(kit.bash("rm -rf /"))), "a grant behind a link must not lift Rule A")
        self.assertTrue(kit.denied(self.entry(kit.edit("src/app.py"))), "a restriction behind a link still holds")

    def test_the_coverage_sweep_moves_a_link_and_never_the_directory_it_points_to(self):
        victim = self.root / "victim"
        victim.mkdir()
        (victim / "precious.txt").write_text("keep", encoding="utf-8")
        os.symlink(victim, self.root / ".coverage", target_is_directory=True)
        kit.decide({"tool_name": "Bash", "tool_input": {"command": "pytest"}, "tool_response": {"stdout": "ok"}}, self.root,
                   module="post_tool_use", entry="run")
        self.assertEqual((victim / "precious.txt").read_text(encoding="utf-8"), "keep")
        self.assertFalse((self.root / ".coverage").exists() and not (self.root / ".coverage").is_symlink())

    def test_the_size_scan_does_not_follow_a_link_out_of_the_generated_roots(self):
        import size_audit

        outside = self.root / "outside"
        outside.mkdir()
        (outside / "big.bin").write_bytes(b"x" * 4096)
        (self.root / ".harness-state").mkdir()
        os.symlink(outside, self.root / ".harness-state" / "escape", target_is_directory=True)
        result = size_audit.scan(self.root, threshold_bytes=1024)
        self.assertEqual(result["files"], [])
        self.assertEqual(result["directories"], [])


def _mutations(raw: bytes, rng: random.Random) -> list:
    """Deterministic damage to one valid payload: byte-level edits, then structural edits that stay valid JSON."""
    size = len(raw)
    out = [raw[: rng.randrange(1, size)], raw[rng.randrange(size):], b"\xef\xbb\xbf" + raw, raw + b"\x00", raw.replace(b'"', b"'", 1)]
    for _ in range(4):
        i = rng.randrange(size)
        out.append(raw[:i] + raw[i + 1:])
        out.append(raw[:i] + bytes([rng.randrange(256)]) + raw[i + 1:])
        out.append(raw[:i] + bytes(rng.randrange(256) for _ in range(rng.randrange(1, 9))) + raw[i:])
    document = json.loads(raw)
    replacements = [None, True, False, 0, -1, 2**70, 1.5, "", "x" * 5000, "\u0000\ud800", [], {}, [[]], {"a": {"b": [1, {"c": None}]}}, ["rm -rf /"]]
    for _ in range(10):
        mutated = json.loads(raw)
        holder, key = mutated, None
        while isinstance(holder, dict) and holder:
            key = rng.choice(sorted(holder))
            if not isinstance(holder[key], dict) or rng.random() < 0.4:
                break
            holder = holder[key]
        if isinstance(holder, dict) and key is not None:
            holder[key] = rng.choice(replacements)
        out.append(json.dumps(mutated).encode("utf-8"))
    out.append(json.dumps(document, ensure_ascii=True).encode("ascii").replace(b"rm", b"\\ud800rm"))
    out.append(b"[" * 3000 + b"]" * 3000)
    out.append(b'{"tool_name": "Bash", "tool_input": {"command": "' + b"a" * 200_000 + b'"}}')
    out.append(b"")
    out.append(b"\xff\xfe\xfd")
    return out


BASE_PAYLOADS = {
    "PreToolUse": [{"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "session_id": "fz", "cwd": "/work"},
                   {"tool_name": "Edit", "tool_input": {"file_path": "src/payments/a.py", "new_string": "x"}, "session_id": "fz"},
                   {"tool_name": "PowerShell", "tool_input": {"command": "Set-Content -Path src\\payments\\a.py -Value x"}}],
    "PostToolUse": [{"tool_name": "Bash", "tool_input": {"command": "make test"}, "tool_response": {"exit_code": 1, "stdout": "boom"}, "session_id": "fz"},
                    {"tool_name": "Edit", "tool_input": {"file_path": "a.py", "new_string": "x"}, "tool_response": "ok", "session_id": "fz"}],
    "UserPromptSubmit": [{"prompt": "design a payments service", "session_id": "fz"}, {"prompt": "/audit-improve", "session_id": "fz"}],
}


def parses_to_a_mapping(raw: bytes) -> bool:
    try:
        return isinstance(json.loads(raw.decode("utf-8", errors="replace").lstrip("\ufeff")), dict)
    except Exception:
        return False


class FuzzTests(Project):
    """Mutated payloads, fixed seed: the hooks neither crash nor fault on anything that parses."""

    def corpus(self, event: str) -> list:
        rng = random.Random(f"{SEED}:{event}")
        return [mutated for base in BASE_PAYLOADS[event] for mutated in _mutations(json.dumps(base).encode("utf-8"), rng)]

    def test_the_corpus_is_the_same_every_run(self):
        first = self.corpus("PreToolUse")
        self.assertEqual(first, self.corpus("PreToolUse"))
        self.assertGreater(len(first), 60)
        self.assertGreater(sum(parses_to_a_mapping(item) for item in first), 20)
        self.assertGreater(sum(not parses_to_a_mapping(item) for item in first), 20)

    def test_no_hook_raises_and_a_payload_that_parses_never_causes_an_internal_fault(self):
        parse_faults = {"JSONDecodeError", "RecursionError", "ValueError"}
        for event, module in MODULES.items():
            observations = self.root / ".harness-state" / "observations" / f"{event}.json"
            for raw in self.corpus(event):
                if observations.exists():
                    observations.unlink()
                try:
                    self.entry(raw, module)
                except Exception as exc:  # the entry must not raise whatever arrives
                    self.fail(f"{module}.run raised {type(exc).__name__} for {raw[:120]!r}")
                record = self.faults(event)
                kind = (record.get("last_fault") or {}).get("type")
                if parses_to_a_mapping(raw):
                    self.assertIsNone(kind, f"{event}: internal fault {kind} on a payload that parses: {raw[:160]!r}")
                elif kind is not None:
                    self.assertIn(kind, parse_faults, f"{event}: {kind} on an unparseable payload {raw[:120]!r}")

    def test_the_registered_scripts_exit_zero_without_a_traceback_on_a_sample_of_the_corpus(self):
        for event in MODULES:
            sample = random.Random(f"{SEED}:sample:{event}").sample(self.corpus(event), 12)
            for raw in sample:
                with self.subTest(event=event, payload=raw[:60]):
                    proc = self.script(event, raw)
                    self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-400:])
                    self.assertNotIn(b"Traceback", proc.stderr)
                    if proc.stdout.strip():
                        json.loads(proc.stdout.decode("utf-8"))

    def test_noise_around_a_dangerous_command_never_unlocks_it(self):
        rng = random.Random(f"{SEED}:noise")
        junk = [None, True, 7, 2**70, "x" * 3000, [], {}, [1, [2, [3]]], {"a": {"b": None}}, "\u202e\u0000", "rm -rf ./harmless"]
        for round_number in range(40):
            payload = {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}, "session_id": "fz"}
            for _ in range(rng.randrange(1, 6)):
                payload[f"extra{rng.randrange(99)}"] = rng.choice(junk)
                payload["tool_input"][f"flag{rng.randrange(99)}"] = rng.choice(junk)
            if round_number % 3 == 0:
                payload["cwd"] = rng.choice(["/", "", "C:\\", "~", ".", "/nonexistent/\u00e9"])
            with self.subTest(round=round_number):
                self.assertTrue(kit.denied(self.entry(payload)), json.dumps(payload)[:200])

    def test_a_tool_input_of_an_unknown_shape_is_allowed_through_not_crashed_on(self):
        """A shape the guard cannot read is a documented limit (it cannot judge what it cannot parse), not a crash."""
        for tool_input in (None, "rm -rf /", ["rm -rf /"], 7, True):
            with self.subTest(tool_input=tool_input):
                self.assertEqual(self.entry({"tool_name": "Bash", "tool_input": tool_input}), "")
                self.assertIsNone(self.faults("PreToolUse").get("last_fault"))


class FailOpenTests(Project):
    """Whatever breaks, a hook exits 0 and says nothing; it counts the fault; and a deny stays a deny."""

    RM = kit.bash("rm -rf /")

    def run_broken(self, event: str, what: str) -> subprocess.CompletedProcess:
        """Run the registered script as ``__main__`` with one internal function made to raise."""
        script = HOOK_DIR / SCRIPTS[event]
        code = ("import runpy, sys, _state\n"
                "def boom(*a, **k):\n    raise RuntimeError('SECRET-DETAIL')\n"
                f"_state.{what} = boom\n"
                f"sys.argv = ['{script.name}']\nrunpy.run_path({str(script)!r}, run_name='__main__')\n")
        return subprocess.run([sys.executable, "-c", code], input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}, "prompt": "hello"}).encode(),
                              capture_output=True, cwd=HOOK_DIR, env=kit.clean_env(self.root, PYTHONPATH=str(HOOK_DIR), **self.env), check=False)

    def test_every_hook_survives_its_own_internals_failing_and_counts_it(self):
        for event in SCRIPTS:
            for what in ("read_hook_input", "load_guard_state", "project_root"):
                with self.subTest(event=event, what=what):
                    proc = self.run_broken(event, what)
                    self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-400:])
                    self.assertNotIn(b"Traceback", proc.stderr)
                    self.assertNotIn(b"SECRET-DETAIL", proc.stdout + proc.stderr)
                    if event != "UserPromptSubmit":  # its routing reminder needs none of the broken parts
                        self.assertEqual(proc.stdout, b"")
                    elif proc.stdout.strip():
                        json.loads(proc.stdout.decode("utf-8"))

    def test_a_fault_is_counted_by_type_and_never_by_content(self):
        proc = self.run_broken("PreToolUse", "read_hook_input")
        self.assertEqual(proc.returncode, 0)
        record = self.faults("PreToolUse")
        self.assertEqual(record["faults"], 1)
        self.assertEqual(record["last_fault"]["type"], "RuntimeError")
        self.assertNotIn("SECRET-DETAIL", json.dumps(record))

    def test_a_deny_stays_a_deny_when_the_state_directory_cannot_be_used(self):
        (self.root / ".harness-state").write_text("a file where the directory should be", encoding="utf-8")
        proc = self.script("PreToolUse", self.RM)
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(kit.denied(proc.stdout.decode("utf-8")))
        for event in ("PostToolUse", "UserPromptSubmit"):
            proc = self.script(event, {"tool_name": "Bash", "tool_input": {"command": "ls"}, "prompt": "hi", "session_id": "s"})
            self.assertEqual(proc.returncode, 0, event)
            self.assertNotIn(b"Traceback", proc.stderr)

    def test_a_deny_stays_a_deny_when_the_guard_record_is_damaged_in_any_way(self):
        damage = {"binary": b"\xff\xfe\x00\x01{", "empty": b"", "huge": b"[" * 2_000_000, "wrong type": b'"text"', "null": b"null",
                  "nested": b'{"frozen_globs": 5, "blocked_globs": {"a": 1}, "read_only": "x", "allow_dangerous": [1]}'}
        for name, content in damage.items():
            with self.subTest(damage=name):
                directory = self.root / ".harness-state"
                directory.mkdir(exist_ok=True)
                (directory / "guard-state.json").write_bytes(content)
                proc = self.script("PreToolUse", self.RM)
                self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-300:])
                self.assertTrue(kit.denied(proc.stdout.decode("utf-8")), name)
                self.assertNotIn(b"Traceback", proc.stderr)

    def test_a_guard_record_that_is_a_directory_does_not_stop_the_hook(self):
        (self.root / ".harness-state" / "guard-state.json").mkdir(parents=True)
        proc = self.script("PreToolUse", self.RM)
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(kit.denied(proc.stdout.decode("utf-8")))
        proc = self.script("PreToolUse", kit.bash("ls"))
        self.assertEqual((proc.returncode, proc.stdout), (0, b""))

    def test_a_rule_that_faults_does_not_switch_off_the_rules_after_it(self):
        import guard_hook

        kit.write_guard(self.root, FROZEN)
        broken = [("A", lambda call: (_ for _ in ()).throw(RuntimeError("SECRET-DETAIL"))), *guard_hook.RULES[1:]]
        saved = guard_hook.RULES
        guard_hook.RULES = broken
        try:
            output = self.entry(kit.edit("src/payments/a.py"), "guard_hook", "main")
        finally:
            guard_hook.RULES = saved
        self.assertTrue(kit.denied(output))
        self.assertEqual(self.faults("PreToolUse")["last_fault"]["type"], "RuntimeError")

    def test_a_project_without_a_home_directory_or_a_usable_temp_directory_still_runs(self):
        env = kit.clean_env(self.root)
        for name in ("HOME", "USERPROFILE", "TMPDIR", "TEMP", "TMP", "XDG_CONFIG_HOME"):
            env.pop(name, None)
        env["TMPDIR"] = str(self.root / "does" / "not" / "exist")
        proc = subprocess.run([sys.executable, str(HOOK_DIR / "pre_tool_use.py")], input=json.dumps(self.RM).encode(), capture_output=True, env=env, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-300:])
        self.assertTrue(kit.denied(proc.stdout.decode("utf-8")))

    def test_every_registered_script_exits_zero_on_empty_and_on_closed_input(self):
        for event, name in SCRIPTS.items():
            for stdin in (subprocess.DEVNULL, b""):
                with self.subTest(event=event, stdin=stdin):
                    proc = subprocess.run([sys.executable, str(HOOK_DIR / name)], stdin=stdin if stdin is subprocess.DEVNULL else None,
                                          input=None if stdin is subprocess.DEVNULL else stdin, capture_output=True,
                                          env=kit.clean_env(self.root, **self.env), check=False)
                    self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-300:])
                    self.assertNotIn(b"Traceback", proc.stderr)


class RunIdTests(Project):
    """QR-PY-10: a run id becomes a directory name, so traversal in it is refused by the writer and ignored by the reader."""

    HOSTILE = ("", ".", "..", "../x", "..\\x", "a/b", "a\\b", "x/../y", "/abs", "C:evil", "C:\\evil", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b")

    def test_the_writer_refuses_every_traversal_and_reserved_spelling_and_accepts_a_plain_id(self):
        import save_run

        for run_id in self.HOSTILE:
            with self.subTest(run_id=run_id):
                with self.assertRaises(save_run.Refused):
                    save_run.safe_run_id(run_id)
        for run_id in ("r1", "2026-09-29_full-review-audit_k7q2xd", "a.b-c_d"):
            with self.subTest(run_id=run_id):
                self.assertEqual(save_run.safe_run_id(run_id), run_id)

    def test_the_writer_refuses_every_id_the_reader_would_never_find(self):
        """The writer allowed ids that `_state.active_run_id` ignores, so such a run was written and then invisible to the hooks."""
        import _state
        import save_run

        for run_id in ("a b", "x" * 129, ".hidden", "-flag", "a\nb", "r1\n", "naïve", "r;1", "r$HOME", "r'1", "r(1)", "r~1"):
            with self.subTest(run_id=run_id):
                with self.assertRaises(save_run.Refused) as raised:
                    save_run.safe_run_id(run_id)
                self.assertIn("letters, digits", str(raised.exception))
        for run_id in ("x" * 128, "_r1", "0", "a.b-c_d", "2026-09-29_full-review-audit_k7q2xd"):
            with self.subTest(run_id=run_id):
                self.assertEqual(save_run.safe_run_id(run_id), run_id)
                self.assertIsNotNone(_state.RUN_ID.match(run_id))

    def test_the_reader_scopes_nothing_by_an_id_that_could_leave_the_runs_directory(self):
        import _state

        saves = self.root / "skillset-saves"
        saves.mkdir()
        for run_id in ("../x", "a/b", "..", "", "a b", "x" * 200):
            (saves / "_latest.md").write_text(json.dumps({"run_id": run_id}), encoding="utf-8")
            with self.subTest(run_id=run_id):
                self.assertEqual(_state.active_run_id(self.root), "no-run")
        (saves / "_latest.md").write_text(json.dumps({"run_id": "r1"}), encoding="utf-8")
        self.assertEqual(_state.active_run_id(self.root), "r1")

    def test_the_command_line_writer_creates_nothing_outside_the_runs_directory(self):
        (self.root / "README.md").write_text("# fixture\n", encoding="utf-8")
        for run_id in ("../escape", "a/b"):
            with self.subTest(run_id=run_id):
                proc = subprocess.run([sys.executable, str(HOOK_DIR / "save_run.py"), "create", "--run-id", run_id, "--evidence", "README.md",
                                       "--project-root", str(self.root)], capture_output=True, text=True, env=kit.clean_env(self.root), check=False)
                self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertFalse((self.root / "skillset-saves" / "escape").exists())
        self.assertFalse((self.root / "escape").exists())
        self.assertEqual(sorted(p.name for p in (self.root / "skillset-saves" / "runs").glob("*")) if (self.root / "skillset-saves" / "runs").is_dir() else [], [])


if __name__ == "__main__":
    unittest.main()
