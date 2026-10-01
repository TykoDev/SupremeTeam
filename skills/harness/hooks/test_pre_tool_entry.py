#!/usr/bin/env python3
"""The registered PreToolUse entry point: it tries the guard on any interpreter, and fails open readably on a real fault (DX-13, RR-guard-1).

Before round 1 the entry imported the guard outside its ``try``, so an import-time fault, and on
Python 3.9 the ``dict | None`` annotation in ``_state.py``, ended in a traceback and exit 1. Round 1
fixed that with a version gate, and the gate switched the guard off on Python 3.10 to 3.12, where the
guard code runs and the first revision denied ``rm -rf /``. The entry now has no version gate: it runs
the guard, and only a failure to import or run it fails open, with the fault counted and, below the floor,
the interpreter and the floor named. Every hook module imports on an interpreter below the floor, and
the real scripts are run under each older interpreter installed here.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _bootstrap  # noqa: E402
import _testkit as kit  # noqa: E402
import pre_tool_use  # noqa: E402

# The hook modules this package owns: each must import on an interpreter below the floor.
OWNED_MODULES = ("_bootstrap", "_cmdscan", "_fsutil", "_paths", "_state", "guard_hook", "guard_state", "post_tool_use",
                 "pre_tool_use", "size_audit", "audit_improve", "user_prompt_submit")
OLDER = kit.older_interpreters()
BELOW_FLOOR = (3, 10, 12, "final", 0)

# What a real failure to import the guard looks like to the entry, run under another interpreter.
_BROKEN_GUARD = (
    f"import builtins, runpy, sys\nsys.path.insert(0, {str(HOOK_DIR)!r})\nreal = builtins.__import__\n"
    "def broken(name, *a, **k):\n    if name == 'guard_hook':\n        raise SyntaxError('boom')\n    return real(name, *a, **k)\n"
    "builtins.__import__ = broken\nsys.argv = ['pre_tool_use.py']\n"
    f"runpy.run_path({str(HOOK_DIR / 'pre_tool_use.py')!r}, run_name='__main__')\n"
)


def _observation(root: Path) -> dict:
    return json.loads((root / ".harness-state" / "observations" / "PreToolUse.json").read_text(encoding="utf-8"))


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        manager = kit.project()
        self.root = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        patcher = mock.patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_entry(self, version=None) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            if version is None:
                pre_tool_use.run()
            else:
                with mock.patch.object(sys, "version_info", version):
                    pre_tool_use.run()
        return err.getvalue()

    def test_an_interpreter_below_the_floor_still_runs_the_guard(self):
        err = io.StringIO()
        with mock.patch.object(sys, "version_info", BELOW_FLOOR), contextlib.redirect_stderr(err):
            out = kit.decide(kit.bash("rm -rf /"), self.root, module="pre_tool_use", entry="run")
            quiet = kit.decide(kit.bash("ls -la"), self.root, module="pre_tool_use", entry="run")
        self.assertTrue(kit.denied(out), out)
        self.assertEqual((quiet, err.getvalue()), ("", ""))

    def test_a_boundary_is_enforced_below_the_floor_too(self):
        kit.write_guard(self.root, {"frozen_globs": [{"glob": "src/payments/**", "owner": "ops"}]})
        with mock.patch.object(sys, "version_info", BELOW_FLOOR):
            out = kit.decide(kit.edit("src/payments/a.py"), self.root, module="pre_tool_use", entry="run")
        self.assertTrue(kit.denied(out), out)

    def test_a_fault_below_the_floor_is_explained_and_counted(self):
        with mock.patch("guard_hook.main", side_effect=ImportError("secret detail")):
            message = self.run_entry(BELOW_FLOOR)
        self.assertEqual(message.count("\n"), 1, message)
        for part in ("Python 3.10", "Python 3.13 or newer", "NOT enforcing", "ImportError"):
            self.assertIn(part, message)
        self.assertNotIn("secret detail", message)
        record = _observation(self.root)
        self.assertEqual((record["faults"], record["last_fault"]["type"]), (1, "ImportError"))
        self.assertNotIn("secret detail", json.dumps(record))

    def test_the_floor_is_the_repository_floor(self):
        manifest = json.loads((HOOK_DIR.parents[1] / "runtime-manifest.yaml").read_text(encoding="utf-8"))
        floor = next(item["minimum"] for item in _walk(manifest) if str(item.get("minimum", "")).startswith("3."))
        self.assertEqual(".".join(str(part) for part in pre_tool_use.MINIMUM), floor)

    def test_a_fault_in_the_guard_is_swallowed_and_counted(self):
        with mock.patch("guard_hook.main", side_effect=RuntimeError("secret detail")):
            self.assertEqual(self.run_entry(pre_tool_use.MINIMUM + ("final", 0)), "")
        record = (self.root / ".harness-state" / "observations" / "PreToolUse.json").read_text(encoding="utf-8")
        self.assertIn('"faults": 1', record)
        self.assertIn("RuntimeError", record)
        self.assertNotIn("secret detail", record)

    def test_an_import_time_fault_fails_open_with_exit_zero(self):
        """The old entry imported the guard outside its try, so this was a traceback and exit 1."""
        proc = subprocess.run([sys.executable, "-c", _BROKEN_GUARD], input=b"{}", capture_output=True,
                              env=kit.clean_env(self.root), check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        self.assertEqual(proc.stdout, b"")

    def test_the_entry_source_parses_on_any_python_3(self):
        source = (HOOK_DIR / "pre_tool_use.py").read_text(encoding="utf-8")
        for minor in (6, 8, 9):
            with self.subTest(minor=minor):
                ast.parse(source, feature_version=(3, minor))

    def test_the_entry_still_guards_through_the_registered_script(self):
        proc = kit.run_hook("pre_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}}, self.root)
        self.assertEqual(proc.returncode, 0)
        self.assertIn(b'"permissionDecision": "deny"', proc.stdout)
        proc = kit.run_hook("pre_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, self.root)
        self.assertEqual((proc.returncode, proc.stdout), (0, b""))


class ImportabilityTests(unittest.TestCase):
    """No hook module evaluates syntax or a name a Python below the floor lacks while it is being imported (DX-13's other half)."""

    def test_no_unquoted_union_annotation_without_the_future_import(self):
        for name in OWNED_MODULES:
            unions = _union_annotations_at_import((HOOK_DIR / f"{name}.py").read_text(encoding="utf-8"))
            with self.subTest(module=name):
                self.assertEqual(unions, [], f"{name}.py evaluates `X | Y` annotations at import (line {unions[:3]}) without `from __future__ import annotations`")

    def test_no_file_a_registered_hook_runs_evaluates_a_union_annotation_at_import(self):
        """The three entry scripts import `_state` at module level and `_state` imports `save_taxonomy` from `skills/scripts`,
        so the files a Python 3.9 would have to import are the ones `enforcement_files()` lists, not only this directory's."""
        for path in _bootstrap.enforcement_files():
            unions = _union_annotations_at_import(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.name):
                self.assertEqual(unions, [], f"{path.name} evaluates `X | Y` annotations at import (line {unions[:3]}) without `from __future__ import annotations`")

    def test_the_scan_finds_the_annotation_that_broke_state_on_python_3_9(self):
        """`def refresh_run_heartbeat(data: dict, event: str) -> dict | None` stood in `_state.py` without the future import until round 2."""
        broken = "def refresh_run_heartbeat(data: dict, event: str) -> dict | None:\n    return None\n"
        self.assertEqual(_union_annotations_at_import(broken), [1])
        self.assertEqual(_union_annotations_at_import("class C:\n    field: int | None = None\n"), [2])
        self.assertEqual(_union_annotations_at_import("def f(a: int | str) -> None:\n    return None\n"), [1])
        self.assertEqual(_union_annotations_at_import("from __future__ import annotations\n" + broken), [])
        self.assertEqual(_union_annotations_at_import('def f() -> "dict | None":\n    return None\n'), [])
        self.assertEqual(_union_annotations_at_import("def f() -> dict:\n    return {}\n"), [])

    def test_every_file_a_registered_hook_runs_parses_for_python_3_9(self):
        paths = {HOOK_DIR / f"{name}.py" for name in OWNED_MODULES} | set(_bootstrap.enforcement_files())
        for path in sorted(paths):
            with self.subTest(file=path.name):
                ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))

    @unittest.skipUnless(OLDER, "no interpreter below the running one is installed")
    def test_every_owned_module_imports_under_each_older_interpreter(self):
        code = "import sys, importlib\nsys.path.insert(0, %r)\nfor name in %r:\n    importlib.import_module(name)\n" % (str(HOOK_DIR), OWNED_MODULES)
        for label, python in OLDER:
            with self.subTest(python=label):
                proc = subprocess.run([python, "-c", code], capture_output=True, text=True, check=False)
                self.assertEqual((proc.returncode, proc.stderr.strip()), (0, ""), proc.stderr)


@unittest.skipUnless(OLDER, "no interpreter below the running one is installed")
class OlderInterpreterTests(unittest.TestCase):
    """The real scripts, as a subprocess, under every older interpreter installed here (RR-guard-1)."""

    def setUp(self):
        manager = kit.project()
        self.root = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)

    def test_the_entry_denies_and_allows_exactly_as_it_does_on_the_floor(self):
        for label, python in OLDER:
            with self.subTest(python=label):
                denied = kit.run_hook("pre_tool_use.py", kit.bash("rm -rf /"), self.root, python=python)
                self.assertEqual(denied.returncode, 0, denied.stderr)
                self.assertTrue(kit.denied(denied.stdout.decode("utf-8")), denied.stdout)
                self.assertEqual(denied.stderr, b"")
                allowed = kit.run_hook("pre_tool_use.py", kit.bash("ls -la"), self.root, python=python)
                self.assertEqual((allowed.returncode, allowed.stdout, allowed.stderr), (0, b"", b""))

    def test_a_recorded_boundary_is_enforced(self):
        kit.write_guard(self.root, {"frozen_globs": [{"glob": "src/payments/**", "owner": "ops"}]})
        for label, python in OLDER:
            with self.subTest(python=label):
                proc = kit.run_hook("pre_tool_use.py", kit.bash("echo x > src/payments/a.py"), self.root, python=python)
                self.assertTrue(kit.denied(proc.stdout.decode("utf-8")), proc.stdout)

    def test_the_other_two_entries_run_without_a_traceback(self):
        for label, python in OLDER:
            with self.subTest(python=label):
                prompt = kit.run_hook("user_prompt_submit.py", {"prompt": "add a feature"}, self.root, python=python)
                self.assertEqual((prompt.returncode, prompt.stderr), (0, b""))
                self.assertIn("admiral", prompt.stdout.decode("utf-8"))
                post = kit.run_hook("post_tool_use.py", {"tool_name": "Bash", "tool_input": {"command": "ls"}, "tool_response": {}},
                                    self.root, python=python)
                self.assertEqual((post.returncode, post.stderr), (0, b""))

    def test_a_real_failure_to_import_the_guard_is_readable_and_counted(self):
        for label, python in OLDER:
            with self.subTest(python=label):
                proc = subprocess.run([python, "-c", _BROKEN_GUARD], input=b"{}", capture_output=True,
                                      env=kit.clean_env(self.root), check=False)
                self.assertEqual((proc.returncode, proc.stdout), (0, b""))
                message = proc.stderr.decode("utf-8")
                self.assertEqual(message.count("\n"), 1, message)
                for part in (f"Python {label}", "Python 3.13 or newer", "NOT enforcing", "SyntaxError"):
                    self.assertIn(part, message)
                record = _observation(self.root)
                self.assertEqual((record["faults"], record["last_fault"]["type"]), (1, "SyntaxError"))
                (self.root / ".harness-state" / "observations" / "PreToolUse.json").unlink()


def _union_annotations_at_import(source: str) -> list:
    """The lines of annotations written as `X | Y` that a Python below 3.10 would evaluate; none when the module defers them all."""
    tree = ast.parse(source)
    if any(isinstance(node, ast.ImportFrom) and node.module == "__future__" and any(alias.name == "annotations" for alias in node.names)
           for node in tree.body):
        return []
    return [line for annotation, line in _annotations(tree)
            if any(isinstance(part, ast.BinOp) and isinstance(part.op, ast.BitOr) for part in ast.walk(annotation))]


def _annotations(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                yield node.returns, node.lineno
            arguments = node.args
            for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg):
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation, node.lineno
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation, node.lineno


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


if __name__ == "__main__":
    unittest.main()
