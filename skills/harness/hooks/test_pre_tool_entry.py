#!/usr/bin/env python3
"""The registered PreToolUse entry point: fail open, readably, on every fault and on a Python below the floor (DX-13).

Before this the entry imported the guard outside its ``try``, so an import-time fault, and
on Python 3.9 the ``dict | None`` annotation in ``_state.py``, ended in a traceback and exit 1
instead of the documented silent exit 0. The entry now checks the interpreter first, and its
own source has to parse on any Python 3 a host might launch it with.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _testkit as kit  # noqa: E402
import pre_tool_use  # noqa: E402


class EntryPointTests(unittest.TestCase):
    def setUp(self):
        manager = kit.project()
        self.root = manager.__enter__()
        self.addCleanup(manager.__exit__, None, None, None)
        patcher = mock.patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_entry(self) -> str:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            pre_tool_use.run()
        return err.getvalue()

    def test_an_interpreter_below_the_floor_gets_a_readable_message_and_no_guard_import(self):
        with mock.patch.object(sys, "version_info", (3, 9, 18, "final", 0)), \
                mock.patch.dict(sys.modules, {"guard_hook": None}):
            message = self.run_entry()
        self.assertIn("Python 3.13", message)
        self.assertIn("3.9", message)
        self.assertIn("NOT enforcing", message)
        self.assertEqual(message.count("\n"), 1)

    def test_the_floor_is_the_repository_floor(self):
        manifest = json.loads((HOOK_DIR.parents[1] / "runtime-manifest.yaml").read_text(encoding="utf-8"))
        floor = next(item["minimum"] for item in _walk(manifest) if str(item.get("minimum", "")).startswith("3."))
        self.assertEqual(".".join(str(part) for part in pre_tool_use.MINIMUM), floor)

    def test_a_fault_in_the_guard_is_swallowed_and_counted(self):
        with mock.patch("guard_hook.main", side_effect=RuntimeError("secret detail")):
            self.assertEqual(self.run_entry(), "")
        record = (self.root / ".harness-state" / "observations" / "PreToolUse.json").read_text(encoding="utf-8")
        self.assertIn('"faults": 1', record)
        self.assertIn("RuntimeError", record)
        self.assertNotIn("secret detail", record)

    def test_an_import_time_fault_fails_open_with_exit_zero(self):
        """The old entry imported the guard outside its try, so this was a traceback and exit 1."""
        code = "import sys, builtins\nreal = builtins.__import__\n" \
               "def broken(name, *a, **k):\n    if name == 'guard_hook':\n        raise ImportError('boom')\n    return real(name, *a, **k)\n" \
               "builtins.__import__ = broken\nsys.argv = ['pre_tool_use.py']\n" \
               f"import runpy\nrunpy.run_path({str(HOOK_DIR / 'pre_tool_use.py')!r}, run_name='__main__')\n"
        import subprocess

        proc = subprocess.run([sys.executable, "-c", code], input=b"{}", capture_output=True, env=kit.clean_env(self.root), check=False)
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
