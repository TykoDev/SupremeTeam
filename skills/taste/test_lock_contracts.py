#!/usr/bin/env python3
"""The lock's contention contract under the spellings each host gives it.

POSIX reports a held lock file as ``FileExistsError`` and Windows as a sharing-violation
``PermissionError``. Both must land in the same path: judge the lock by its content and
age, then free it or refuse. These cases hold that mapping directly; the concurrency
suite holds the six-writer behaviour it produces.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taste_prefs as taste  # noqa: E402


class ContentionMappingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.lock = self.root / "taste.lock"

    def test_a_sharing_violation_is_reported_as_a_held_lock_not_a_crash(self):
        """Windows: another writer's open lock file raises PermissionError at O_EXCL."""
        self.lock.write_text(json.dumps({"pid": os.getpid(), "host": taste.host_id(),
                                         "created_at": taste.now(), "token": "theirs"}), encoding="utf-8")
        with mock.patch("os.open", side_effect=PermissionError(13, "sharing violation")):
            with self.assertRaises(FileExistsError):
                taste.take(self.lock)

    def test_a_permission_problem_with_no_lock_file_stays_a_permission_problem(self):
        with mock.patch("os.open", side_effect=PermissionError(13, "access denied")):
            with self.assertRaises(PermissionError):
                taste.take(self.lock)

    def test_a_live_holder_refuses_the_write_with_the_locked_code(self):
        self.lock.write_text(json.dumps({"pid": os.getpid(), "host": taste.host_id(),
                                         "created_at": taste.now(), "token": "theirs"}), encoding="utf-8")
        held = taste.Held()
        with self.assertRaises(taste.TasteError) as raised:
            held.acquire("project", {"lock": self.lock, "journal": self.root / "taste.journal.jsonl"})
        self.assertEqual(raised.exception.code, "locked")

    def test_a_stale_lock_is_reclaimed_through_the_same_path(self):
        self.lock.write_text(json.dumps({"pid": 2 ** 22, "host": "somewhere-else",
                                         "created_at": "2020-01-01T00:00:00+00:00", "token": "theirs"}), encoding="utf-8")
        held = taste.Held()
        held.acquire("project", {"lock": self.lock, "journal": self.root / "taste.journal.jsonl"})
        self.assertEqual(len(held.locks), 1)
        self.assertTrue(held.reclaimed)
        self.assertEqual(held.reclaimed[0]["scope"], "project")
        held.release()
        self.assertFalse(self.lock.exists())


class TransientReadTests(unittest.TestCase):
    """A read that crosses another writer's commit is transient, never a corrupt store."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def write_store(self) -> Path:
        import contextlib
        import io

        with contextlib.redirect_stdout(io.StringIO()):
            taste.main(["--project-root", str(self.root), "set", "--scope", "project", "--id", "p1", "--value", "1"])
        return taste.paths(self.root, "project")["json"]

    def test_a_read_that_crosses_a_rename_retries_and_reads_the_store(self):
        self.write_store()
        real = Path.read_text
        calls = {"n": 0}

        def flaky(self_path, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError(13, "sharing violation")
            return real(self_path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", flaky), mock.patch.object(taste.time, "sleep", lambda _s: None):
            record, existed = taste.load(self.root, "project")
        self.assertTrue(existed)
        self.assertIn("p1", record["entries"])
        self.assertGreaterEqual(calls["n"], 3)

    def test_an_unreadable_state_that_outlasts_the_retries_is_retryable_not_corruption(self):
        self.write_store()
        with mock.patch.object(Path, "read_text", side_effect=PermissionError(13, "sharing violation")), \
                mock.patch.object(taste.time, "sleep", lambda _s: None):
            with self.assertRaises(taste.TasteError) as raised:
                taste.load(self.root, "project")
        self.assertEqual(raised.exception.code, "locked")

    def test_bytes_that_read_and_do_not_parse_are_still_corruption(self):
        target = self.write_store()
        target.write_text("not-json\u0000recovery", encoding="utf-8")
        with self.assertRaises(taste.TasteError) as raised:
            taste.load(self.root, "project")
        self.assertEqual(raised.exception.code, "corrupt_record")
        self.assertIn("unreadable", raised.exception.message)

    def test_a_store_the_writer_rolled_back_reads_as_absent_not_broken(self):
        self.write_store()
        calls = {"n": 0}

        def vanishing(self_path, *args, **kwargs):
            calls["n"] += 1
            raise FileNotFoundError(2, "no such file")

        with mock.patch.object(Path, "read_text", vanishing), mock.patch.object(taste.time, "sleep", lambda _s: None):
            with mock.patch.object(Path, "exists", lambda _self: calls["n"] < 2):
                record, existed = taste.load(self.root, "project")
        self.assertFalse(existed)
        self.assertEqual(record["entries"], {})


if __name__ == "__main__":
    unittest.main()
