"""Unit tests for the storage engine and the safety validators of the Taste writer.

`test_taste_prefs.py` proves the command surface end to end. These tests reach the
pieces underneath directly: process probing and lock staleness, the lock and its
races, the commit helpers, global root resolution, owner identity, the secret and
field-name validators, proposal validation, and the checks that keep the writer's
vocabularies equal to `taste-doctrine.md`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("taste_prefs.py")
DOCTRINE = Path(__file__).resolve().parents[1] / "taste-doctrine.md"
OWNERSHIP = Path(__file__).resolve().parents[1] / "save-ownership.yaml"
SKILL = Path(__file__).with_name("SKILL.md")
WORKFLOW = Path(__file__).with_name("references") / "workflow.md"
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


class GlobalRootTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.home = self.tmp / "home"

    def root(self, env: dict[str, str], platform: str = "linux") -> Path:
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(taste.sys, "platform", platform), mock.patch.object(taste.Path, "home", return_value=self.home):
            return taste.global_root()

    def test_an_explicit_root_wins_and_is_used_as_given(self):
        self.assertEqual(self.root({"SUPREMETEAM_HOME": str(self.tmp / "explicit"), "CODEX_HOME": str(self.tmp / "codex")}), self.tmp / "explicit")

    def test_codex_home_then_agents_home_hold_a_supremeteam_directory(self):
        self.assertEqual(self.root({"CODEX_HOME": str(self.tmp / "codex"), "AGENTS_HOME": str(self.tmp / "agents")}), self.tmp / "codex" / "supremeteam")
        self.assertEqual(self.root({"AGENTS_HOME": str(self.tmp / "agents")}), self.tmp / "agents" / "supremeteam")

    def test_an_empty_override_is_ignored(self):
        self.assertEqual(self.root({"SUPREMETEAM_HOME": "", "CODEX_HOME": "", "AGENTS_HOME": str(self.tmp / "agents")}), self.tmp / "agents" / "supremeteam")

    def test_linux_uses_an_absolute_xdg_data_home(self):
        self.assertEqual(self.root({"XDG_DATA_HOME": str(self.tmp / "xdg")}), self.tmp / "xdg" / "supremeteam")

    def test_linux_falls_back_to_the_home_directory_without_xdg_data_home(self):
        self.assertEqual(self.root({}), (self.home / ".local" / "share" / "supremeteam").resolve())

    def test_an_empty_or_relative_xdg_data_home_is_ignored_not_resolved_against_the_current_directory(self):
        expected = (self.home / ".local" / "share" / "supremeteam").resolve()
        for name, value in {"empty": "", "relative": "data", "dot": ".", "dotted relative": "./share", "tilde": "~/share"}.items():
            with self.subTest(name=name):
                root = self.root({"XDG_DATA_HOME": value})
                self.assertEqual(root, expected)
                self.assertNotEqual(root, (Path.cwd() / "supremeteam").resolve())

    def test_macos_uses_application_support(self):
        self.assertEqual(self.root({"XDG_DATA_HOME": str(self.tmp / "xdg")}, "darwin"), (self.home / "Library" / "Application Support" / "SupremeTeam").resolve())

    def test_windows_prefers_local_app_data_then_app_data_then_the_profile(self):
        local, roaming = self.tmp / "local", self.tmp / "roaming"
        self.assertEqual(self.root({"LOCALAPPDATA": str(local), "APPDATA": str(roaming)}, "win32"), local / "SupremeTeam")
        self.assertEqual(self.root({"LOCALAPPDATA": "", "APPDATA": str(roaming)}, "win32"), roaming / "SupremeTeam")
        self.assertEqual(self.root({}, "win32"), (self.home / "AppData" / "Local" / "SupremeTeam").resolve())


class PathsTests(StoreCase):
    def test_project_files_live_under_the_project_preferences_directory(self):
        found = taste.paths(self.project, "project")
        base = self.project / "skillset-saves" / "preferences"
        self.assertEqual(found, {"json": base / "taste.json", "md": base / "taste.md", "history": base / "_history", "journal": base / "taste.journal.jsonl", "lock": base / "taste.lock"})

    def test_global_files_live_under_the_global_root_outside_the_checkout(self):
        found = taste.paths(self.project, "global")
        self.assertEqual(found["json"], self.global_home / "preferences" / "taste.json")
        self.assertNotIn(self.project, found["json"].parents)

    def test_a_global_root_that_is_or_contains_the_checkout_is_refused(self):
        for root in (self.project, self.project / "inside", self.project / "a" / "b"):
            with self.subTest(root=root), mock.patch.dict(os.environ, {"SUPREMETEAM_HOME": str(root)}):
                with self.assertRaises(taste.TasteError) as raised:
                    taste.paths(self.project, "global")
                self.assertEqual(raised.exception.code, "unsafe_global_path")

    def test_the_files_the_writer_creates_are_the_ones_the_ownership_policy_declares(self):
        declared = set(re.findall(r"^\s+- skillset-saves/preferences/(\S+)$", OWNERSHIP.read_text(encoding="utf-8"), re.M))
        written = {path.name + ("/*" if key == "history" else "") for key, path in taste.paths(self.project, "project").items()}
        self.assertEqual(written, declared)

    def test_a_scope_is_identified_by_kind_and_an_opaque_project_hash(self):
        project = taste.scope_identity(self.project, "project")
        self.assertEqual(project, {"kind": "project", "id": "sha256:" + hashlib.sha256(str(self.project).encode()).hexdigest()})
        self.assertEqual(taste.scope_identity(self.project, "global"), {"kind": "global", "id": "host-user-data"})


class OwnerIdentityTests(unittest.TestCase):
    def owner(self, explicit: str | None, user: dict | None = None):
        """The owner identity for a given SUPREMETEAM_OWNER (unset when None) on a fixed account and host."""
        with mock.patch.dict(os.environ):
            os.environ.pop("SUPREMETEAM_OWNER", None)
            if explicit is not None:
                os.environ["SUPREMETEAM_OWNER"] = explicit
            with mock.patch.object(taste.getpass, "getuser", **(user or {"return_value": "alice"})), mock.patch.object(taste.socket, "gethostname", return_value="workstation-7"):
                return taste.owner_identity()

    def test_a_well_formed_explicit_owner_is_recorded_as_given(self):
        self.assertEqual(self.owner("Team-1_a.b"), {"id": "Team-1_a.b", "source": "SUPREMETEAM_OWNER"})

    def test_a_malformed_explicit_owner_is_replaced_by_an_opaque_identifier(self):
        for value in ("has space", "", "a" * 81, "bad/slash", "bad:colon"):
            with self.subTest(value=value):
                owner = self.owner(value)
                self.assertEqual(owner["source"], "local-opaque")
                self.assertRegex(owner["id"], r"^sha256:[0-9a-f]{64}$")

    def test_the_opaque_owner_is_a_hash_that_carries_no_account_or_host_name(self):
        owner = self.owner(None)
        self.assertEqual(owner, {"id": "sha256:" + hashlib.sha256(b"alice\0workstation-7").hexdigest(), "source": "local-opaque"})
        text = json.dumps(owner)
        self.assertNotIn("alice", text)
        self.assertNotIn("workstation", text)

    def test_no_owner_is_recorded_when_none_can_be_derived(self):
        self.assertIsNone(self.owner(None, {"side_effect": OSError("no account")}))
        with mock.patch.object(taste, "owner_identity", return_value=None):
            self.assertNotIn("owner", taste.blank(Path("."), "project"))

    def test_a_blank_record_is_self_consistent_and_starts_at_revision_zero(self):
        record = taste.blank(Path("."), "project")
        self.assertEqual((record["revision"], record["entries"], record["tombstones"], record["previous_revision_digest"]), (0, {}, {}, None))
        self.assertIs(taste.validate(record, "project"), record)
        self.assertEqual(record["canonical_record_digest"], taste.digest(record))


class SensitiveKeyTests(unittest.TestCase):
    """A key is sensitive by whole words, so ordinary design vocabulary passes and real fields do not."""

    SENSITIVE = (
        "password", "Password", "user_password", "userPassword", "PASSWORD_HASH", "password-confirmation", "password2", "passwd",
        "secret", "client_secret", "secretKey", "secret_key", "secrets", "secret2", "credential", "credentials", "credentials_json",
        "authorization", "Authorization", "ssn", "SSN", "ssn_last4", "social_security_number",
        "api_key", "apiKey", "API_KEY", "APIKey", "api-keys", "apikey", "private_key", "privateKey",
        "full_name", "fullName", "user_name", "userName", "username", "usernames",
        "token", "tokens", "access_token", "accessToken", "refresh_token", "api-token", "token_value", "token_id", "token2",
        "cookie", "cookies", "session_cookie", "cookie_value",
        "prompt", "system_prompt", "prompt_text", "prompt_history",
        "conversation", "conversation_history", "conversation_id",
        "email", "emails", "user_email", "emailAddress", "email_address", "contact-email", "email2",
        "phone", "phones", "phone_number", "phoneNumbers", "home_phone", "mobile.phone", "phone2",
        "address", "addresses", "home_address", "street_address", "address_line1", "address_line_2", "address2",
    )
    ORDINARY = (
        "design-tokens", "design_tokens", "designTokens", "DesignTokens", "design-token", "design-token-scale", "ui.design-tokens", "design-tokens.naming",
        "phone-layout", "phoneLayout", "phone_breakpoints", "mobile-phone-frame",
        "email-density", "email-template-style", "cookie-banner", "cookie-consent-layout", "cookies-banner",
        "address-bar", "address_bar", "address-book-layout", "prompt-style", "prompt-dialog", "prompt_position",
        "conversation-density", "conversational-ui", "tokenizer", "tokenization", "microphone", "headphones", "telephone",
        "addressable", "emailed", "passwordless", "secretary", "secretive", "authorize", "density", "layout", "color-scheme", "spacing", "ui.density", "tables.density-v2", "a", "", "-", "...",
    )

    def test_credential_and_personal_datum_names_are_sensitive(self):
        for key in self.SENSITIVE:
            with self.subTest(key=key):
                self.assertTrue(taste.sensitive_key(key))

    def test_ordinary_design_vocabulary_is_not_sensitive(self):
        for key in self.ORDINARY:
            with self.subTest(key=key):
                self.assertFalse(taste.sensitive_key(key))

    def test_a_credential_word_counts_anywhere_but_a_personal_datum_word_only_at_the_end(self):
        self.assertTrue(taste.sensitive_key("password-strength-meter"))
        self.assertTrue(taste.sensitive_key("secret-santa-theme"))
        self.assertFalse(taste.sensitive_key("email-newsletter-layout"))
        self.assertTrue(taste.sensitive_key("newsletter-email"))

    def test_the_design_token_exemption_does_not_hide_a_credential_beside_it(self):
        self.assertFalse(taste.sensitive_key("design-tokens"))
        self.assertTrue(taste.sensitive_key("design-tokens-secret"))
        self.assertTrue(taste.sensitive_key("design-tokens.api-token"))


class SensitiveValueTests(unittest.TestCase):
    ORDINARY = (
        "skeleton-loading-states", "skeuomorphic-glass-theme", "sketchy-hand-drawn-icons", "sketch-style-illustrations", "skeleton_placeholders",
        "skeuomorphic-shadows", "prefer skeleton-loading states over spinners", "skewed-card-layout", "skin-tone-neutral-palette", "skeletons",
        "sk-loading-states-for-everything-everywhere", "risk-averse-confirmation-dialogs", "task-abcdefghijklmnop123", "desk-lamp-elevation-shadows",
        "Bearer of bad news is fine", "bearer authentication", "a bearer credential-free scheme", "the ghpages theme", "xoxo hugs and kisses",
        "dark-mode-first-with-high-contrast", "e-mail newsletter layout", "compact", "", "sk-", "sk-1234", "sk-abcdefghijk1234",
    )
    SECRETS = (
        "sk-abcdefghijklmnopqrstuvwxyz123456", "sk-proj-abcdefghijklmnopqrstuvwxyz0123456789", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz",
        "SK-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", "sk_" "live_abcdefghijklmnopqrstuvwx", "sk_" "test_4eC39HqLyjWDarjtT1zdp7dc",
        "gh" "p_abcdefghijklmnopqrstuvwxyz0123456789", "github_" "pat_11ABCDEFG0abcdefghijkl_abcdefghij", "xo" "xb-1234567890-abcdefghijkl", "xo" "xp-abcdefghijklmnop",
        "-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN PRIVATE KEY-----", "-----BEGIN OPENSSH PRIVATE KEY-----",
        "Bearer eyJhbGciOiJIUzI1NiJ9.abc", "bearer abcdefghijklmnop1234", "person@example.com", "first.last+tag@sub.example.co.uk",
    )

    def test_ordinary_design_vocabulary_is_not_mistaken_for_a_secret(self):
        for text in self.ORDINARY:
            with self.subTest(text=text):
                self.assertIsNone(taste.SENSITIVE_VALUE.search(text))

    def test_real_secret_shapes_are_still_found(self):
        for text in self.SECRETS:
            with self.subTest(text=text):
                self.assertIsNotNone(taste.SENSITIVE_VALUE.search(text))

    def test_a_secret_is_found_inside_a_sentence(self):
        for secret in self.SECRETS:
            for template in ("my key is {} remember it", "{}", "curl -H 'Authorization: {}' now", "value={};"):
                with self.subTest(secret=secret, template=template):
                    self.assertIsNotNone(taste.SENSITIVE_VALUE.search(template.format(secret)))

    def test_an_sk_key_needs_a_separator_a_token_shaped_tail_and_a_digit(self):
        digits = "abcdefghijklmn12"
        self.assertIsNotNone(taste.SENSITIVE_VALUE.search(f"sk-{digits}"))
        self.assertIsNone(taste.SENSITIVE_VALUE.search(f"sk-{digits[:-1]}"))
        self.assertIsNone(taste.SENSITIVE_VALUE.search("sk-" + "a" * 40))
        self.assertIsNone(taste.SENSITIVE_VALUE.search("skabcdefghijklmnopqrstuvwxyz123456"))
        self.assertIsNotNone(taste.SENSITIVE_VALUE.search("sk_" "live_" + "a" * 10))
        self.assertIsNone(taste.SENSITIVE_VALUE.search("sk_" "live_" + "a" * 9))

    def test_a_bearer_credential_needs_a_long_token_after_the_word(self):
        self.assertIsNotNone(taste.SENSITIVE_VALUE.search("Bearer " + "a" * 16))
        self.assertIsNone(taste.SENSITIVE_VALUE.search("Bearer " + "a" * 15))


class ValidateSafeTests(unittest.TestCase):
    def refused(self, value, **kwargs) -> "taste.TasteError":
        with self.assertRaises(taste.TasteError) as raised:
            taste.validate_safe(value, **kwargs)
        return raised.exception

    def test_json_data_passes_unchanged(self):
        value = {"a": [1, 2.5, True, None, "text"], "b": {"c": "compact"}, "d": ""}
        self.assertEqual(taste.validate_safe(value), value)
        self.assertEqual(taste.validate_safe(value, redact=True), value)

    def test_a_sensitive_field_is_refused_with_its_full_path(self):
        error = self.refused({"a": {"b": [{"password": "x"}]}})
        self.assertEqual((error.code, error.details["field"]), ("sensitive_input", "$.a.b[].password"))

    def test_a_secret_value_is_refused_with_its_path_and_without_its_content(self):
        error = self.refused({"a": ["ok", "person@example.com"]})
        self.assertEqual((error.code, error.details["field"]), ("sensitive_input", "$.a[]"))
        self.assertNotIn("person@example.com", json.dumps([error.message, error.details]))

    def test_redaction_drops_fields_replaces_secret_values_truncates_and_reports_each(self):
        report: list[dict[str, str]] = []
        cleaned = taste.validate_safe({"keep": "compact", "email": "x", "note": "mail person@example.com", "long": "x" * 1200, "nested": {"api_key": "k", "fine": 1}}, redact=True, report=report)
        self.assertEqual(cleaned, {"keep": "compact", "note": "[REDACTED]", "long": "x" * 1000 + "[REDACTED:TRUNCATED]", "nested": {"fine": 1}})
        self.assertEqual(sorted(report, key=lambda item: item["path"]), [
            {"path": "$.email", "action": "dropped"},
            {"path": "$.long", "action": "truncated"},
            {"path": "$.nested.api_key", "action": "dropped"},
            {"path": "$.note", "action": "redacted"},
        ])

    def test_the_report_is_optional_and_stays_empty_when_nothing_is_removed(self):
        report: list[dict[str, str]] = []
        taste.validate_safe({"a": "b"}, redact=True, report=report)
        self.assertEqual(report, [])
        taste.validate_safe({"email": "x"}, redact=True)

    def test_text_over_the_limit_is_refused_unless_redacting(self):
        taste.validate_safe("x" * 1000)
        error = self.refused("x" * 1001)
        self.assertEqual((error.code, error.details["field"]), ("unbounded_input", "$"))
        self.assertEqual(taste.validate_safe("x" * 1001, redact=True), "x" * 1000 + "[REDACTED:TRUNCATED]")

    def test_more_than_one_hundred_list_items_are_refused_even_when_redacting(self):
        taste.validate_safe(list(range(100)))
        for redact in (False, True):
            with self.subTest(redact=redact):
                self.assertEqual(self.refused(list(range(101)), redact=redact).code, "unbounded_input")

    def test_a_secret_in_text_that_will_be_truncated_is_replaced_not_kept(self):
        key = "sk-abcdefghijklmnopqrstuvwxyz123456"
        report: list[dict[str, str]] = []
        for name, text in {"at the start": "person@example.com " + "x" * 1100, "straddling the cut": "x" * 989 + " " + key + " " + "y" * 200, "just inside the cut": "x" * (999 - len(key)) + " " + key + " " + "y" * 300}.items():
            with self.subTest(name=name):
                self.assertEqual(taste.validate_safe(text, redact=True, report=report), "[REDACTED]")
        self.assertEqual({item["action"] for item in report}, {"redacted"})

    def test_a_secret_beyond_the_scanned_window_leaves_with_the_truncated_text(self):
        text = "x" * 1400 + "person@example.com"
        report: list[dict[str, str]] = []
        cleaned = taste.validate_safe(text, redact=True, report=report)
        self.assertEqual(cleaned, "x" * 1000 + "[REDACTED:TRUNCATED]")
        self.assertEqual(report, [{"path": "$", "action": "truncated"}])

    def test_the_secret_scan_never_reads_unbounded_text(self):
        seen = []

        class Recording:
            def search(self, text):
                seen.append(len(text))

        with mock.patch.object(taste, "SENSITIVE_VALUE", Recording()):
            taste.validate_safe("a" * 2_000_000, redact=True)
            taste.validate_safe("b" * 999, redact=True)
        self.assertEqual(seen, [taste.MAX_TEXT + 256, 999])

    def test_a_value_that_is_not_json_data_is_refused(self):
        for value in (object(), {1, 2}, b"bytes", (1, 2)):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(self.refused(value).code, "invalid_input")


class ProposalValidationTests(unittest.TestCase):
    VALID = {"category": "density", "normalized_rule": "Prefer compact table rows", "strength": "soft", "source": "explicit"}

    def refused(self, value) -> "taste.TasteError":
        with self.assertRaises(taste.TasteError) as raised:
            taste.validate_proposal(value)
        self.assertEqual(raised.exception.code, "invalid_entry")
        return raised.exception

    def test_a_proposal_with_the_four_doctrine_fields_is_accepted(self):
        self.assertIsNone(taste.validate_proposal(self.VALID))

    def test_every_category_strength_and_source_the_doctrine_lists_is_accepted(self):
        for category in taste.CATEGORIES:
            for strength in taste.STRENGTHS:
                for source in taste.SOURCES:
                    with self.subTest(category=category, strength=strength, source=source):
                        taste.validate_proposal({**self.VALID, "category": category, "strength": strength, "source": source})

    def test_the_optional_doctrine_fields_and_unknown_extras_are_carried_as_given(self):
        extras = {"rationale": "Chose it in review", "confidence": 0.6, "source_run": "run-1", "applicability_selectors": {"surface": "tables"}, "conflicts": ["other"], "supersedes": "old", "expires_at": "2027-01-01", "anything": [1]}
        self.assertIsNone(taste.validate_proposal({**self.VALID, **extras}))

    def test_a_proposal_that_is_not_an_object_is_refused(self):
        for value in ("text", ["density"], 7, None, True):
            with self.subTest(value=value):
                self.refused(value)

    def test_each_required_field_must_be_present(self):
        for field in self.VALID:
            with self.subTest(field=field):
                error = self.refused({key: item for key, item in self.VALID.items() if key != field})
                self.assertEqual(error.details["field"], field)

    def test_an_identifier_outside_the_doctrine_is_refused_with_the_allowed_values(self):
        cases = {"category": ("colour", "Density", "", 5, ["density"], None), "strength": ("medium", "HARD", "", 1), "source": ("inferred", "confirmed", "user", "", None)}
        allowed = {"category": taste.CATEGORIES, "strength": taste.STRENGTHS, "source": taste.SOURCES}
        for field, values in cases.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    error = self.refused({**self.VALID, field: value})
                    self.assertEqual((error.details["field"], error.details["allowed"]), (field, list(allowed[field])))

    def test_the_normalized_rule_must_be_a_non_empty_string(self):
        for value in ("", "   ", "\n", 5, None, ["compact"], {"rule": "x"}):
            with self.subTest(value=value):
                self.assertEqual(self.refused({**self.VALID, "normalized_rule": value}).details["field"], "normalized_rule")


class DoctrineParityTests(unittest.TestCase):
    """The doctrine is canonical for the vocabularies and the operation table; the writer must equal it."""

    def setUp(self):
        self.doctrine = DOCTRINE.read_text(encoding="utf-8")

    @staticmethod
    def section(text: str, start: str, end: str) -> str:
        return text.split(start, 1)[1].split(end, 1)[0]

    def test_the_category_registry_equals_section_three(self):
        identifiers = re.findall(r"^\| `([a-z-]+)` \|", self.section(self.doctrine, "## 3. Stable categories", "## 4."), re.M)
        self.assertEqual(len(identifiers), 11)
        self.assertEqual(sorted(identifiers), sorted(taste.CATEGORIES))
        self.assertEqual(len(set(taste.CATEGORIES)), len(taste.CATEGORIES))

    def test_the_strength_and_source_enumerations_equal_section_four(self):
        section = self.section(self.doctrine, "## 4. Entry record and provenance", "## 5.")
        for field, values in (("strength", taste.STRENGTHS), ("source", taste.SOURCES)):
            with self.subTest(field=field):
                line = re.search(rf"^- `{field}`: (.+?);", section, re.M)
                self.assertIsNotNone(line)
                self.assertEqual(sorted(re.findall(r"`([a-z-]+)`", line.group(1))), sorted(values))

    def test_the_operation_table_equals_the_commands_the_writer_exposes(self):
        rows = dict(re.findall(r"^\|[^|]+\| `([a-z]+)` \| (yes|no) \|", self.section(self.doctrine, "## 6. Operations", "## 7."), re.M))
        self.assertEqual(set(rows), set(taste.READS) | taste.MUTATIONS)
        self.assertEqual({name for name, mutating in rows.items() if mutating == "yes"}, taste.MUTATIONS)

    def test_the_skill_names_every_command_the_writer_exposes(self):
        sentence = re.search(r"`taste_prefs.py` exposes (.+?)\.\n", SKILL.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(sentence)
        self.assertEqual(set(re.findall(r"`([a-z]+)`", sentence.group(1))), set(taste.READS) | taste.MUTATIONS)

    def test_every_error_code_the_writer_raises_appears_in_the_runbooks(self):
        codes = set(re.findall(r'TasteError\(\s*"([a-z_]+)"', SCRIPT.read_text(encoding="utf-8")))
        self.assertGreaterEqual(len(codes), 19)
        documented = "\n".join(path.read_text(encoding="utf-8") for path in (SKILL, WORKFLOW, DOCTRINE))
        self.assertEqual(sorted(code for code in codes if f"`{code}`" not in documented), [])


if __name__ == "__main__":
    unittest.main()
