#!/usr/bin/env python3
"""The shared atomic write and advisory lock every hook-directory writer uses (QR-PY-05).

Before ``_fsutil`` the guard record, the observation and trajectory files and the
throttle stamps were replaced with a bare ``os.replace`` (no retry on the transient
Windows sharing violation, a leaked staging file on failure, no flush to disk), and
the guard record had no lock at all, so two writers lost one update. These tests pin
the one strongest variant that ``save_run`` already had and that every other writer
now adopts.
"""
from __future__ import annotations

import errno
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _fsutil  # noqa: E402


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def leftovers(self) -> list:
        return sorted(p.name for p in self.dir.iterdir() if p.name.endswith(".tmp"))

    def test_text_and_bytes_are_written_exactly_and_no_staging_file_remains(self):
        target = self.dir / "a.json"
        _fsutil.atomic_write(target, "line1\nline2\n")
        self.assertEqual(target.read_bytes(), b"line1\nline2\n", "no newline translation on any platform")
        _fsutil.atomic_write(target, b"\x00\xffraw")
        self.assertEqual(target.read_bytes(), b"\x00\xffraw")
        self.assertEqual(self.leftovers(), [])

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_an_explicit_mode_is_the_mode_the_file_ends_with_whatever_the_umask(self):
        """QR-PY-05: registration needed this for host config files, and kept its own copy of the write to get it."""
        for umask in (0o022, 0o077, 0):
            for mode in (0o600, 0o644):
                with self.subTest(umask=oct(umask), mode=oct(mode)):
                    target = self.dir / f"m{umask}-{mode}.json"
                    previous = os.umask(umask)
                    try:
                        _fsutil.atomic_write(target, b"{}", mode=mode)
                    finally:
                        os.umask(previous)
                    self.assertEqual(os.stat(target).st_mode & 0o777, mode)
                    self.assertEqual(target.read_bytes(), b"{}")
        self.assertEqual(self.leftovers(), [])

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_a_private_file_is_never_wider_than_its_mode_while_it_is_staged(self):
        seen: list = []
        real_replace = _fsutil.replace_with_retry

        def look(tmp, path, attempts=8):
            seen.append(os.stat(tmp).st_mode & 0o777)
            real_replace(tmp, path, attempts)

        previous = os.umask(0)
        try:
            with mock.patch.object(_fsutil, "replace_with_retry", look):
                _fsutil.atomic_write(self.dir / "private.json", b"x", mode=0o600)
        finally:
            os.umask(previous)
        self.assertEqual(seen, [0o600])

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_no_mode_leaves_the_bits_to_the_umask_as_before(self):
        target = self.dir / "plain.json"
        previous = os.umask(0o027)
        try:
            _fsutil.atomic_write(target, "x")
        finally:
            os.umask(previous)
        self.assertEqual(os.stat(target).st_mode & 0o777, 0o640)

    def test_staging_is_named_per_process(self):
        seen = []
        real = os.replace

        def spy(source, destination):
            seen.append(Path(source).name)
            return real(source, destination)

        with mock.patch.object(_fsutil.os, "replace", spy):
            _fsutil.atomic_write(self.dir / "state.json", "x")
        self.assertEqual(seen, [f"state.json.{os.getpid()}.tmp"])

    def test_a_failed_replace_leaves_no_staging_file_and_raises_oserror(self):
        target = self.dir / "a.json"
        target.write_text("old", encoding="utf-8")
        with mock.patch.object(_fsutil.os, "replace", side_effect=OSError(errno.EIO, "disk")):
            with self.assertRaises(OSError):
                _fsutil.atomic_write(target, "new")
        self.assertEqual(target.read_text(encoding="utf-8"), "old", "the previous bytes survive a failed write")
        self.assertEqual(self.leftovers(), [])

    def test_a_transient_sharing_violation_is_retried(self):
        target = self.dir / "a.json"
        real = os.replace
        calls = []

        def flaky(source, destination):
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError(errno.EACCES, "sharing violation")
            return real(source, destination)

        with mock.patch.object(_fsutil.os, "replace", flaky), mock.patch.object(_fsutil.time, "sleep"):
            _fsutil.atomic_write(target, "ok")
        self.assertEqual(len(calls), 3)
        self.assertEqual(target.read_text(encoding="utf-8"), "ok")

    def test_a_target_that_cannot_be_replaced_is_overwritten_in_place_and_the_degradation_is_noted(self):
        target = self.dir / "a.json"
        target.write_text("old", encoding="utf-8")
        notes: list = []
        with mock.patch.object(_fsutil.os, "replace", side_effect=PermissionError(errno.EACCES, "denied")), \
                mock.patch.object(_fsutil.time, "sleep"):
            _fsutil.atomic_write(target, "new", notes=notes)
        self.assertEqual(target.read_text(encoding="utf-8"), "new")
        self.assertTrue(any("replaced in place" in note for note in notes), notes)
        self.assertEqual(self.leftovers(), [])

    def test_a_missing_target_that_cannot_be_created_raises(self):
        with mock.patch.object(_fsutil.os, "replace", side_effect=PermissionError(errno.EACCES, "denied")), \
                mock.patch.object(_fsutil.time, "sleep"):
            with self.assertRaises(PermissionError):
                _fsutil.atomic_write(self.dir / "new.json", "x")
        self.assertEqual(self.leftovers(), [])

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "needs POSIX symlinks")
    def test_a_planted_symlink_at_the_staging_name_is_not_written_through(self):
        victim = self.dir / "victim.txt"
        victim.write_text("precious", encoding="utf-8")
        target = self.dir / "a.json"
        (self.dir / f"a.json.{os.getpid()}.tmp").symlink_to(victim)
        _fsutil.atomic_write(target, "new")
        self.assertEqual(victim.read_text(encoding="utf-8"), "precious")
        self.assertEqual(target.read_text(encoding="utf-8"), "new")

    def test_the_written_bytes_are_flushed_before_the_replace(self):
        order = []
        real_fsync, real_replace = os.fsync, os.replace
        with mock.patch.object(_fsutil.os, "fsync", lambda fd: (order.append("fsync"), real_fsync(fd))[1]), \
                mock.patch.object(_fsutil.os, "replace", lambda a, b: (order.append("replace"), real_replace(a, b))[1]):
            _fsutil.atomic_write(self.dir / "a.json", "x")
        self.assertEqual(order, ["fsync", "replace"])

    def test_an_unsupported_fsync_does_not_fail_the_write(self):
        with mock.patch.object(_fsutil.os, "fsync", side_effect=OSError(errno.EINVAL, "no fsync here")):
            _fsutil.atomic_write(self.dir / "a.json", "x")
        self.assertEqual((self.dir / "a.json").read_text(encoding="utf-8"), "x")


class AdvisoryLockTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.path = self.dir / "x.lock"

    def test_a_second_holder_times_out_with_lock_timeout(self):
        with _fsutil.AdvisoryLock(self.path, 1.0) as first:
            self.assertTrue(first.held)
            with self.assertRaises(_fsutil.LockTimeout):
                with _fsutil.AdvisoryLock(self.path, 0.05):
                    self.fail("the lock must not be granted twice")

    def test_fail_open_proceeds_without_the_lock_after_the_wait(self):
        with _fsutil.AdvisoryLock(self.path, 1.0):
            with _fsutil.AdvisoryLock(self.path, 0.05, fail_open=True) as second:
                self.assertFalse(second.held)

    def test_the_lock_is_released_on_exit(self):
        with _fsutil.AdvisoryLock(self.path, 1.0):
            pass
        with _fsutil.AdvisoryLock(self.path, 0.05) as again:
            self.assertTrue(again.held)

    def test_a_killed_holder_never_wedges_the_lock(self):
        """The operating system drops an advisory lock when its holder dies, so no stale-lock guess is needed."""
        script = textwrap.dedent(f"""
            import sys, time
            sys.path.insert(0, {str(HOOK_DIR)!r})
            import _fsutil
            lock = _fsutil.AdvisoryLock({str(self.path)!r}, 2.0)
            lock.__enter__()
            print("held", flush=True)
            time.sleep(60)
        """)
        proc = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "held")
            with self.assertRaises(_fsutil.LockTimeout):
                with _fsutil.AdvisoryLock(self.path, 0.05):
                    pass
        finally:
            proc.kill()
            proc.wait()
            proc.stdout.close()
        with _fsutil.AdvisoryLock(self.path, 2.0) as after:
            self.assertTrue(after.held)

    def test_the_lock_directory_is_created_on_request(self):
        nested = self.dir / "a" / "b" / "x.lock"
        with _fsutil.AdvisoryLock(nested, 1.0, create_dir=True) as lock:
            self.assertTrue(lock.held)

    def test_a_file_system_without_locking_degrades_to_unlocked_and_says_so(self):
        stub = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8,
                               flock=mock.Mock(side_effect=OSError(errno.ENOLCK, "No locks available")))
        notes: list = []
        lock = _fsutil.AdvisoryLock(self.path, 1.0, notes=notes, backends=lambda: (stub, None))
        with lock:
            self.assertFalse(lock.held)
        self.assertTrue(any("without mutual exclusion" in note for note in notes), notes)

    def test_the_windows_backend_locks_one_byte_and_reads_contention_as_busy(self):
        """Not run on Windows here: this checks the call sequence against a stub of msvcrt."""
        calls: list = []

        def locking(fd, mode, length):
            calls.append(mode)
            if mode == 1 and calls.count(1) == 1:
                raise OSError(errno.EACCES, "Permission denied")
            self.assertEqual(length, 1)

        stub = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=0, locking=locking)
        with _fsutil.AdvisoryLock(self.path, 2.0, backends=lambda: (None, stub)) as lock:
            self.assertTrue(lock.held)
        self.assertEqual(calls, [1, 1, 0], "one contended attempt, one that took the lock, one release")

    def test_an_uncreatable_lock_file_degrades_to_unlocked_and_says_so(self):
        notes: list = []
        blocked = self.dir / "file-not-dir" / "x.lock"
        (self.dir / "file-not-dir").write_text("a file where a directory is needed", encoding="utf-8")
        with _fsutil.AdvisoryLock(blocked, 0.05, notes=notes) as lock:
            self.assertFalse(lock.held)
        self.assertTrue(any("without mutual exclusion" in note for note in notes), notes)


if __name__ == "__main__":
    unittest.main()
