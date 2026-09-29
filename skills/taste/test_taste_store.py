"""Unit tests for the storage engine of the Taste writer.

`test_taste_prefs.py` proves the command surface end to end. These tests reach the
pieces underneath directly: process probing and lock staleness, the lock and its
races, the commit helpers, and the retry policy for a file another process holds open.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("taste_prefs.py")
_SPEC = importlib.util.spec_from_file_location("taste_prefs", SCRIPT)
taste = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(taste)

WINDOWS = sys.platform == "win32"


def dead_pid() -> int:
    """The pid of a process that has exited and been reaped."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def minutes_ago(minutes: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


class StoreCase(unittest.TestCase):
    """A throwaway project and global root reached through the environment the writer reads."""

    def setUp(self):
        project_tmp, global_tmp = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup)
        self.addCleanup(global_tmp.cleanup)
        self.project = Path(project_tmp.name).resolve()
        self.global_home = Path(global_tmp.name).resolve()
        environment = mock.patch.dict(os.environ, {"SUPREMETEAM_HOME": str(self.global_home), "SUPREMETEAM_OWNER": "test-owner"})
        environment.start()
        self.addCleanup(environment.stop)

    def destinations(self, *scopes: str) -> dict[str, dict[str, Path]]:
        return {scope: taste.paths(self.project, scope) for scope in scopes}

    def lock_file(self, scope: str = "project") -> Path:
        return self.destinations(scope)[scope]["lock"]

    def holder(self, **fields) -> dict:
        return {"pid": os.getpid(), "host": taste.host_id(), "created_at": taste.now(), "token": "t", **fields}

    def leave_lock(self, content: str | dict, scope: str = "project") -> Path:
        path = self.lock_file(scope)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path


class ProcessProbeTests(unittest.TestCase):
    @unittest.skipIf(WINDOWS, "the writer does not probe processes on Windows")
    def test_a_running_process_is_alive_and_a_reaped_one_is_not(self):
        self.assertIs(taste.pid_alive(os.getpid()), True)
        self.assertIs(taste.pid_alive(dead_pid()), False)

    def test_a_process_the_caller_may_not_signal_still_counts_as_alive(self):
        with mock.patch.object(taste.os, "kill", side_effect=PermissionError):
            self.assertIs(taste.pid_alive(1), True)

    def test_a_platform_error_or_an_unrepresentable_pid_makes_no_claim(self):
        for error in (OSError("unsupported"), OverflowError("too large")):
            with self.subTest(error=type(error).__name__), mock.patch.object(taste.os, "kill", side_effect=error):
                self.assertIsNone(taste.pid_alive(1))

    def test_windows_makes_no_claim_and_never_signals(self):
        with mock.patch.object(taste.sys, "platform", "win32"), mock.patch.object(taste.os, "kill", side_effect=AssertionError("os.kill must not run on Windows")):
            self.assertIsNone(taste.pid_alive(os.getpid()))

    def test_a_pid_beyond_what_the_platform_accepts_is_unknown_rather_than_a_crash(self):
        self.assertIsNone(taste.pid_alive(2**70))


class StaleReasonTests(StoreCase):
    def test_the_bound_is_ten_minutes(self):
        self.assertEqual(taste.LOCK_STALE_AFTER, 600)

    @unittest.skipIf(WINDOWS, "the writer does not probe processes on Windows")
    def test_a_dead_holder_on_this_host_is_provably_stale_however_recent_the_lock(self):
        self.assertEqual(taste.stale_reason(self.lock_file(), self.holder(pid=dead_pid())), "holder-dead")

    def test_a_live_holder_is_not_stale_while_the_lock_is_recent(self):
        self.assertIsNone(taste.stale_reason(self.lock_file(), self.holder(created_at=minutes_ago(9))))

    def test_a_lock_past_the_bound_is_stale_whatever_its_pid_or_host(self):
        old = minutes_ago(11)
        for name, fields in {"live pid": {}, "dead pid on another host": {"pid": dead_pid(), "host": "elsewhere"}, "other host": {"host": "elsewhere"}, "no host": {"host": None}}.items():
            with self.subTest(name=name):
                self.assertEqual(taste.stale_reason(self.lock_file(), self.holder(created_at=old, **fields)), "expired")

    def test_a_dead_pid_is_not_believed_without_a_matching_host(self):
        dead = dead_pid()
        for name, host in {"another host": "elsewhere", "no host recorded": None, "empty host": ""}.items():
            with self.subTest(name=name):
                fields = {"pid": dead, "host": host}
                self.assertIsNone(taste.stale_reason(self.lock_file(), self.holder(**fields)))

    def test_a_host_that_cannot_be_identified_never_matches(self):
        with mock.patch.object(taste, "host_id", return_value=""):
            self.assertIsNone(taste.stale_reason(self.lock_file(), self.holder(pid=dead_pid(), host="")))

    def test_pids_that_are_not_positive_integers_are_never_probed(self):
        with mock.patch.object(taste.os, "kill", side_effect=AssertionError("must not probe")):
            for pid in (0, -1, True, False, "12", 1.5, None, [1], {"a": 1}):
                with self.subTest(pid=pid):
                    self.assertIsNone(taste.stale_reason(self.lock_file(), self.holder(pid=pid)))

    def test_a_pid_the_platform_cannot_represent_falls_back_to_the_age(self):
        self.assertIsNone(taste.stale_reason(self.lock_file(), self.holder(pid=2**70)))
        self.assertEqual(taste.stale_reason(self.lock_file(), self.holder(pid=2**70, created_at=minutes_ago(11))), "expired")

    def test_a_future_timestamp_is_not_stale(self):
        future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
        self.assertIsNone(taste.stale_reason(self.lock_file(), self.holder(created_at=future)))

    def test_a_recorded_time_that_cannot_be_used_falls_back_to_the_file_time(self):
        path = self.leave_lock("{}")
        old = dt.datetime.now().timestamp() - 11 * 60
        for recorded in ("yesterday", 12345, None, "2026-01-01T00:00:00"):
            with self.subTest(recorded=recorded):
                os.utime(path, None)
                self.assertIsNone(taste.stale_reason(path, self.holder(created_at=recorded)))
                os.utime(path, (old, old))
                self.assertEqual(taste.stale_reason(path, self.holder(created_at=recorded)), "expired")

    def test_a_lock_with_no_readable_holder_is_judged_by_its_file_time(self):
        path = self.leave_lock("")
        self.assertIsNone(taste.stale_reason(path, taste.read_lock(path)))
        old = dt.datetime.now().timestamp() - 11 * 60
        os.utime(path, (old, old))
        self.assertEqual(taste.stale_reason(path, taste.read_lock(path)), "expired")

    def test_a_lock_that_is_gone_is_not_stale(self):
        self.assertIsNone(taste.stale_reason(self.lock_file(), {}))

    def test_read_lock_returns_a_dict_or_nothing(self):
        for content, expected in {"": {}, "{": {}, "[1]": {}, "null": {}, '{"pid": 7}': {"pid": 7}}.items():
            with self.subTest(content=content):
                self.assertEqual(taste.read_lock(self.leave_lock(content)), expected)
        self.assertEqual(taste.read_lock(self.project / "absent.lock"), {})


class LockTests(StoreCase):
    def test_a_lock_is_created_exclusively_and_records_its_holder(self):
        held = taste.lock(self.destinations("project"))
        self.addCleanup(held.release)
        path = self.lock_file()
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(sorted(record), ["created_at", "host", "pid", "token"])
        self.assertEqual((record["pid"], record["host"]), (os.getpid(), taste.host_id()))
        self.assertRegex(record["token"], r"^[0-9a-f]{32}$")
        self.assertEqual(held.locks, [(path, record["token"])])
        age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(record["created_at"])).total_seconds()
        self.assertTrue(0 <= age < 60)
        if not WINDOWS:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_the_holder_is_identified_by_an_opaque_host_hash_not_a_hostname(self):
        held = taste.lock(self.destinations("project"))
        self.addCleanup(held.release)
        host = json.loads(self.lock_file().read_text(encoding="utf-8"))["host"]
        self.assertEqual(host, hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16])
        self.assertRegex(host, r"^[0-9a-f]{16}$")

    def test_a_second_writer_is_refused_and_told_who_holds_the_lock(self):
        held = taste.lock(self.destinations("project"))
        self.addCleanup(held.release)
        with self.assertRaises(taste.TasteError) as raised:
            taste.lock(self.destinations("project"))
        error = raised.exception
        self.assertEqual(error.code, "locked")
        self.assertEqual((error.details["holder_pid"], error.details["stale_after_seconds"]), (os.getpid(), 600))
        self.assertTrue(0 <= error.details["age_seconds"] < 60)
        self.assertEqual(error.details["path"], str(self.lock_file()))
        self.assertEqual(taste.read_lock(self.lock_file())["token"], held.locks[0][1])

    def test_release_removes_the_lock_and_may_be_repeated(self):
        held = taste.lock(self.destinations("project"))
        held.release()
        self.assertFalse(self.lock_file().exists())
        self.assertEqual(held.locks, [])
        held.release()

    def test_release_retries_while_a_reader_holds_the_lock_file_open(self):
        held = taste.lock(self.destinations("project"))
        real, attempts = Path.unlink, []

        def unlink(path, *args, **kwargs):
            attempts.append(path)
            if len(attempts) == 1:
                raise PermissionError("in use by another process")
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", unlink), mock.patch.object(taste.time, "sleep") as slept:
            held.release()
        self.assertFalse(self.lock_file().exists())
        self.assertEqual(slept.call_count, 1)

    def test_release_leaves_a_lock_that_is_no_longer_ours(self):
        held = taste.lock(self.destinations("project"))
        taken_over = {"pid": 1, "token": "another-writer"}
        self.lock_file().write_text(json.dumps(taken_over), encoding="utf-8")
        held.release()
        self.assertEqual(json.loads(self.lock_file().read_text(encoding="utf-8")), taken_over)

    def test_a_lock_that_cannot_be_taken_on_the_second_scope_releases_the_first(self):
        other = self.leave_lock(self.holder(token="another-writer"), "global")
        before = other.read_bytes()
        with self.assertRaises(taste.TasteError) as raised:
            taste.lock(self.destinations("project", "global"))
        self.assertEqual(raised.exception.code, "locked")
        self.assertFalse(self.lock_file("project").exists())
        self.assertEqual(other.read_bytes(), before)

    def test_verify_notices_a_lock_another_writer_has_taken_over(self):
        held = taste.lock(self.destinations("project"))
        held.verify()
        self.lock_file().write_text(json.dumps({"token": "another-writer"}), encoding="utf-8")
        with self.assertRaises(taste.TasteError) as raised:
            held.verify()
        self.assertEqual(raised.exception.code, "lock_lost")
        self.lock_file().unlink()
        with self.assertRaises(taste.TasteError):
            held.verify()

    def test_a_lock_file_that_cannot_be_written_is_removed_rather_than_left_empty(self):
        path = self.lock_file()
        path.parent.mkdir(parents=True)
        with mock.patch.object(taste.os, "write", side_effect=OSError("disk full")), self.assertRaises(OSError):
            taste.take(path)
        self.assertFalse(path.exists())

    def test_reclaim_backs_off_when_the_lock_changes_between_its_two_reads(self):
        path = self.leave_lock(self.holder(created_at=minutes_ago(11)))
        first = {"pid": 1, "created_at": minutes_ago(11)}
        second = {"pid": 2, "created_at": taste.now()}
        with mock.patch.object(taste, "read_lock", side_effect=[first, second]):
            self.assertIsNone(taste.reclaim(path))
        self.assertTrue(path.exists())

    def test_reclaim_describes_what_it_removed_without_echoing_unbounded_content(self):
        path = self.leave_lock({"pid": 41, "created_at": minutes_ago(11), "host": "x", "token": "t", "junk": "y" * 5000})
        removed = taste.reclaim(path)
        self.assertEqual(removed["reason"], "expired")
        self.assertEqual(sorted(removed["prior"]), ["created_at", "pid"])
        self.assertFalse(path.exists())
        path = self.leave_lock({"pid": [1], "created_at": "z" * 100})
        old = dt.datetime.now().timestamp() - 11 * 60
        os.utime(path, (old, old))
        self.assertEqual(taste.reclaim(path), {"reason": "expired", "prior": {}})

    def test_losing_the_race_for_a_freed_lock_reports_it_as_held(self):
        path = self.leave_lock(self.holder(created_at=minutes_ago(11)))
        held = taste.Held()
        with mock.patch.object(taste, "take", side_effect=[FileExistsError(), FileExistsError()]), self.assertRaises(taste.TasteError) as raised:
            held.acquire("project", self.destinations("project")["project"])
        self.assertEqual(raised.exception.code, "locked")
        self.assertEqual(held.locks, [])
        self.assertFalse(path.exists())

    def test_a_lock_whose_audit_note_cannot_be_written_is_released_rather_than_leaked(self):
        self.leave_lock(self.holder(created_at=minutes_ago(11)))
        destinations = self.destinations("project")
        destinations["project"]["journal"].mkdir(parents=True)
        with self.assertRaises(OSError):
            taste.lock(destinations)
        self.assertFalse(self.lock_file().exists())

    def test_an_unexpected_error_while_locking_releases_what_was_taken(self):
        real_acquire = taste.Held.acquire

        def acquire_or_fail(held, scope, target):
            if scope == "global":
                raise RuntimeError("boom")
            real_acquire(held, scope, target)

        with mock.patch.object(taste.Held, "acquire", acquire_or_fail), self.assertRaises(RuntimeError):
            taste.lock(self.destinations("project", "global"))
        self.assertFalse(self.lock_file("project").exists())


class CommitHelperTests(StoreCase):
    def updated(self, scope: str, entry_id: str = "a", value: object = "x", existing: dict | None = None) -> dict:
        args = argparse.Namespace(entry_id=entry_id, value=json.dumps(value), redact=False, input=None)
        return taste.mutate(existing or taste.blank(self.project, scope), "set", args)

    def test_commit_pair_takes_and_releases_its_own_locks_when_it_was_given_none(self):
        destination = self.destinations("project")["project"]
        taste.commit_pair([("project", self.updated("project"), destination, False)])
        self.assertFalse(destination["lock"].exists())
        self.assertEqual(taste.load(self.project, "project")[0]["entries"]["a"]["value"], "x")

    def test_commit_pair_leaves_locks_it_did_not_take(self):
        destinations = self.destinations("project")
        held = taste.lock(destinations)
        self.addCleanup(held.release)
        taste.commit_pair([("project", self.updated("project"), destinations["project"], False)], locks_held=True)
        self.assertTrue(destinations["project"]["lock"].exists())

    def test_commit_pair_reports_a_held_lock_as_locked_and_writes_nothing(self):
        destination = self.destinations("project")["project"]
        self.leave_lock(self.holder())
        with self.assertRaises(taste.TasteError) as raised:
            taste.commit_pair([("project", self.updated("project"), destination, False)])
        self.assertEqual(raised.exception.code, "locked")
        self.assertFalse(destination["json"].exists())
        self.assertFalse(destination["journal"].exists())

    def test_stage_removes_the_first_temporary_file_when_the_second_cannot_be_made(self):
        destination = self.destinations("project")["project"]
        real = tempfile.mkstemp
        calls = []

        def mkstemp_once(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OSError("no space")
            return real(*args, **kwargs)

        with mock.patch.object(taste.tempfile, "mkstemp", mkstemp_once), self.assertRaises(OSError):
            taste.stage(self.updated("project"), destination)
        self.assertEqual([path.name for path in destination["json"].parent.iterdir()], [])

    def test_stage_writes_the_canonical_bytes_and_the_rendered_view(self):
        destination = self.destinations("project")["project"]
        record = self.updated("project")
        json_path, md_path = taste.stage(record, destination)
        self.addCleanup(json_path.unlink)
        self.addCleanup(md_path.unlink)
        self.assertEqual(json_path.read_bytes(), taste.canonical_bytes(record))
        self.assertEqual(md_path.read_text(encoding="utf-8"), taste.render(record))
        self.assertEqual((json_path.parent, md_path.parent), (destination["json"].parent,) * 2)


class ReplaceRetryTests(unittest.TestCase):
    def test_a_transient_permission_error_is_retried_with_growing_pauses(self):
        calls = []

        def replace(source, target):
            calls.append((source, target))
            if len(calls) < 4:
                raise PermissionError("held open")

        with mock.patch.object(taste.os, "replace", replace), mock.patch.object(taste.time, "sleep") as slept:
            taste.replace_with_retry(Path("a"), Path("b"))
        self.assertEqual(len(calls), 4)
        self.assertEqual([call.args[0] for call in slept.call_args_list], [0.05, 0.1, 0.2])

    def test_the_pause_is_capped_and_a_persistent_error_is_finally_raised(self):
        with mock.patch.object(taste.os, "replace", side_effect=PermissionError("held open")) as replace, mock.patch.object(taste.time, "sleep") as slept:
            with self.assertRaises(PermissionError):
                taste.replace_with_retry(Path("a"), Path("b"))
        self.assertEqual(replace.call_count, 8)
        self.assertEqual([call.args[0] for call in slept.call_args_list], [0.05, 0.1, 0.2, 0.4, 0.8, 0.8, 0.8])

    def test_an_error_other_than_a_permission_error_is_not_retried(self):
        with mock.patch.object(taste.os, "replace", side_effect=OSError("disk full")) as replace, mock.patch.object(taste.time, "sleep") as slept:
            with self.assertRaises(OSError):
                taste.replace_with_retry(Path("a"), Path("b"))
        self.assertEqual((replace.call_count, slept.call_count), (1, 0))

    def test_a_file_a_reader_briefly_holds_open_is_still_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "taste.lock"
            path.write_text("{}", encoding="utf-8")
            real, attempts = Path.unlink, []

            def unlink(target, *args, **kwargs):
                attempts.append(target)
                if len(attempts) < 3:
                    raise PermissionError("in use by another process")
                return real(target, *args, **kwargs)

            with mock.patch.object(Path, "unlink", unlink), mock.patch.object(taste.time, "sleep") as slept:
                taste.unlink_with_retry(path)
            self.assertFalse(path.exists())
            self.assertEqual([call.args[0] for call in slept.call_args_list], [0.05, 0.1])

    def test_unlinking_tolerates_a_missing_file_and_raises_a_persistent_error(self):
        with tempfile.TemporaryDirectory() as directory:
            taste.unlink_with_retry(Path(directory) / "absent")
            with mock.patch.object(Path, "unlink", side_effect=PermissionError("in use")) as unlink, mock.patch.object(taste.time, "sleep"):
                with self.assertRaises(PermissionError):
                    taste.unlink_with_retry(Path(directory) / "present")
            self.assertEqual(unlink.call_count, 8)


if __name__ == "__main__":
    unittest.main()
