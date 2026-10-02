#!/usr/bin/env python3
"""Focused tests for the bounded, advisory-only runtime size audit."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import size_audit


class SizeAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".harness-state").mkdir()
        (self.root / "skillset-saves").mkdir()

    def _sparse(self, relative: str, size: int) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            stream.truncate(size)
        return path

    def test_reports_relative_paths_without_changing_files(self):
        large = self._sparse(".harness-state/packages/archive.zip", 600)
        before = large.stat()
        result = size_audit.scan(self.root, threshold_bytes=500)
        self.assertEqual(result["files"], [{"path": ".harness-state/packages/archive.zip", "bytes": 600}])
        self.assertEqual(large.stat().st_size, before.st_size)
        self.assertIsNotNone(size_audit.advisory_for(result))

    def test_reports_large_folder_composed_of_small_files(self):
        for index in range(4):
            self._sparse(f".harness-state/test-work/session/{index}.bin", 200)
        result = size_audit.scan(self.root, threshold_bytes=500)
        self.assertEqual(result["files"], [])
        folders = {item["path"]: item["bytes"] for item in result["directories"]}
        self.assertEqual(folders[".harness-state/test-work/session"], 800)
        self.assertIn("test-work/session", size_audit.advisory_for(result))

    def test_skips_live_core_history_and_frozen_files(self):
        self._sparse(".harness-state/guard-state.json", 600).write_text(json.dumps({
            "frozen_globs": [{"glob": ".harness-state/private/**", "owner": "test"}],
        }), encoding="utf-8")
        self._sparse(".harness-state/private/data.bin", 600)
        self._sparse("skillset-saves/_latest.md", 600)
        self._sparse("skillset-saves/runs/r1/_state.md", 600)
        self._sparse("skillset-saves/runs/r1/_history/large.bin", 600)
        self._sparse("skillset-saves/runs/r1/build/evidence/large.bin", 600)
        result = size_audit.maybe_scan(self.root, force=True, threshold_bytes=500)
        self.assertEqual([item["path"] for item in result["files"]],
                         ["skillset-saves/runs/r1/build/evidence/large.bin"])

    def test_throttle_persists_and_force_bypasses_it(self):
        self._sparse("skillset-saves/package.zip", 600)
        first = size_audit.maybe_scan(self.root, now=1000, threshold_bytes=500, interval_seconds=300)
        self.assertEqual(len(first["files"]), 1)
        self.assertIsNone(size_audit.maybe_scan(self.root, now=1200, threshold_bytes=500, interval_seconds=300))
        self.assertIsNotNone(size_audit.maybe_scan(self.root, now=1200, force=True,
                                                  threshold_bytes=500, interval_seconds=300))
        self.assertEqual(json.loads((self.root / size_audit.STAMP).read_text(encoding="utf-8"))["checked_at"], 1200)
        self.assertIsNotNone(size_audit.maybe_scan(self.root, now=1500, threshold_bytes=500, interval_seconds=300))

    def test_bounded_scan_marks_truncation(self):
        for index in range(20):
            self._sparse(f"skillset-saves/{index:02d}.bin", 600)
        result = size_audit.scan(self.root, threshold_bytes=500, max_entries=3)
        self.assertEqual(result["scanned_entries"], 3)
        self.assertTrue(result["truncated"])
        self.assertIsNotNone(size_audit.advisory_for(result))

    def test_no_runtime_roots_does_not_create_throttle_state(self):
        empty = self.root / "empty"
        empty.mkdir()
        self.assertIsNone(size_audit.maybe_scan(empty, force=True))
        self.assertFalse((empty / ".harness-state").exists())

    def test_symlink_outside_roots_is_never_followed(self):
        external = self.root / "external"
        external.mkdir()
        outside = external / "large.bin"
        with outside.open("wb") as stream:
            stream.truncate(600)
        link = self.root / "skillset-saves" / "linked"
        try:
            link.symlink_to(external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this host")
        result = size_audit.scan(self.root, threshold_bytes=500)
        self.assertEqual(result["files"], [])

    def test_cli_emits_post_tool_advisory(self):
        self._sparse("skillset-saves/package.zip", 2 * 1024 * 1024)
        proc = subprocess.run([sys.executable, str(Path(size_audit.__file__)), "--project-root", str(self.root),
                               "--force"], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL,
                              env={**os.environ, "SUPREMETEAM_SIZE_AUDIT_THRESHOLD_BYTES": str(1024 * 1024)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        envelope = json.loads(proc.stdout)
        self.assertEqual(envelope["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("skillset-saves/package.zip", envelope["hookSpecificOutput"]["additionalContext"])
        result = json.loads(subprocess.run([sys.executable, str(Path(size_audit.__file__)),
                                            "--project-root", str(self.root), "--json"],
                                           capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL).stdout)
        self.assertEqual(result, {"skipped": "not-due"})


class LiveStdinTests(unittest.TestCase):
    def test_the_cli_test_finishes_when_the_runners_stdin_is_a_pipe_that_never_closes(self):
        """size_audit drains a piped stdin, so a child that inherits one waits for an end that never comes."""
        runner = subprocess.Popen(
            [sys.executable, "-m", "unittest", "test_size_audit.SizeAuditTests.test_cli_emits_post_tool_advisory"],
            cwd=Path(__file__).resolve().parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.addCleanup(runner.stdout.close)
        self.addCleanup(runner.stdin.close)
        try:
            runner.wait(timeout=60)
        except subprocess.TimeoutExpired:
            runner.kill()
            runner.wait()
            self.fail("the CLI test hangs while the runner's stdin is an open pipe")
        self.assertEqual(runner.returncode, 0, runner.stdout.read().decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
