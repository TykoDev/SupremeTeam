"""Contract tests for the standard-library Taste preference writer.

`TastePreferencesTests` drives the script as a subprocess. The other classes call
`taste_prefs.main` in-process so they can inject failures and prove the lock, the
commit rollback, and concurrent writers; `test_taste_store.py` covers the storage
engine underneath.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("taste_prefs.py")
_SPEC = importlib.util.spec_from_file_location("taste_prefs", SCRIPT)
taste = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(taste)


class TastePreferencesTests(unittest.TestCase):
    def setUp(self):
        project_tmp = tempfile.TemporaryDirectory(); global_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup); self.addCleanup(global_tmp.cleanup)
        self.project, self.global_home = Path(project_tmp.name), Path(global_tmp.name)
        self.env = {**os.environ, "SUPREMETEAM_HOME": str(self.global_home), "SUPREMETEAM_OWNER": "test-owner"}

    def run_cli(self, *args: str) -> tuple[int, dict]:
        process = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(self.project), *args], text=True, capture_output=True, env=self.env)
        return process.returncode, json.loads(process.stdout)

    def test_project_lifecycle_history_and_stale_writer(self):
        code, result = self.run_cli("set", "--scope", "project", "--id", "ui.density", "--value", '"compact"')
        self.assertEqual(code, 0, result)
        record = json.loads((self.project / "skillset-saves/preferences/taste.json").read_text())
        self.assertEqual(record["revision"], 1); self.assertEqual(record["entries"]["ui.density"]["state"], "active")
        code, result = self.run_cli("deprecate", "--scope", "project", "--expect-revision", "0", "--id", "ui.density")
        self.assertEqual(code, 1); self.assertEqual(result["error"]["code"], "stale_revision")
        code, result = self.run_cli("revoke", "--scope", "project", "--expect-revision", "1", "--id", "ui.density")
        self.assertEqual(code, 0, result)
        record = json.loads((self.project / "skillset-saves/preferences/taste.json").read_text())
        self.assertIn("ui.density", record["tombstones"])
        self.assertEqual(len(list((self.project / "skillset-saves/preferences/_history").glob("*.json"))), 1)

    def test_both_writes_and_effective_project_override(self):
        code, result = self.run_cli("set", "--scope", "both", "--id", "format.style", "--value", '"brief"')
        self.assertEqual(code, 0, result)
        self.assertTrue((self.project / "skillset-saves/preferences/taste.md").exists())
        self.assertTrue((self.global_home / "preferences/taste.json").exists())
        code, result = self.run_cli("effective")
        self.assertEqual(code, 0); self.assertEqual(result["entries"]["format.style"]["source_scope"], "project")

    def test_sensitive_values_rejected_or_redacted_and_corruption_preserved(self):
        code, result = self.run_cli("set", "--scope", "project", "--id", "unsafe", "--value", '"person@example.com"')
        self.assertEqual(code, 1); self.assertEqual(result["error"]["code"], "sensitive_input")
        code, result = self.run_cli("set", "--scope", "project", "--redact", "--id", "safe", "--value", '"person@example.com"')
        self.assertEqual(code, 0, result)
        target = self.project / "skillset-saves/preferences/taste.json"
        target.write_bytes(b"not-json\x00recovery")
        code, result = self.run_cli("reset", "--scope", "project", "--expect-revision", "1")
        self.assertEqual(code, 1); self.assertEqual(result["error"]["code"], "corrupt_record")
        self.assertEqual(target.read_bytes(), b"not-json\x00recovery")


class WriterCase(unittest.TestCase):
    """A throwaway project and global root, reached through the environment the writer reads."""

    def setUp(self):
        project_tmp, global_tmp = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup)
        self.addCleanup(global_tmp.cleanup)
        self.project = Path(project_tmp.name).resolve()
        self.global_home = Path(global_tmp.name).resolve()
        environment = mock.patch.dict(os.environ, {"SUPREMETEAM_HOME": str(self.global_home), "SUPREMETEAM_OWNER": "test-owner"})
        environment.start()
        self.addCleanup(environment.stop)

    def preferences(self, scope: str) -> Path:
        return self.project / "skillset-saves" / "preferences" if scope == "project" else self.global_home / "preferences"

    def cli(self, *args: str, root: Path | None = None) -> tuple[int, dict]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = taste.main(["--project-root", str(root or self.project), *args])
        return code, json.loads(out.getvalue())

    def ok(self, *args: str, root: Path | None = None) -> dict:
        code, payload = self.cli(*args, root=root)
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["ok"])
        return payload

    def refused(self, *args: str) -> dict:
        code, payload = self.cli(*args)
        self.assertEqual(code, 1, payload)
        self.assertFalse(payload["ok"])
        return payload["error"]

    def record(self, scope: str) -> dict:
        return json.loads((self.preferences(scope) / "taste.json").read_text(encoding="utf-8"))

    def revision(self, scope: str) -> int:
        target = self.preferences(scope) / "taste.json"
        return json.loads(target.read_text(encoding="utf-8"))["revision"] if target.exists() else 0

    def snapshot(self, *scopes: str) -> dict[Path, bytes]:
        """Every file under the named stores, so a refused write can be shown to change nothing."""
        return {path: path.read_bytes() for scope in scopes for path in sorted(self.preferences(scope).rglob("*")) if path.is_file()}

    def put(self, scope: str, entry_id: str, value: object, command: str = "set") -> dict:
        """Write one entry, supplying the revision each existing store is at."""
        args = [command, "--scope", scope, "--id", entry_id, "--value", json.dumps(value)]
        for name in ("project", "global") if scope == "both" else (scope,):
            if (self.preferences(name) / "taste.json").exists():
                args += ["--expect-revision", f"{name}={self.revision(name)}"]
        return self.ok(*args)

    def expect(self, *scopes: str) -> list[str]:
        return [item for scope in scopes for item in ("--expect-revision", f"{scope}={self.revision(scope)}")]


def minutes_ago(minutes: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def dead_pid() -> int:
    """The pid of a process that has exited and been reaped."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


class LockTests(WriterCase):
    """A mutation holds a lock file; a writer killed while holding it must not wedge the store for good."""

    def lock_path(self, scope: str) -> Path:
        return self.preferences(scope) / "taste.lock"

    def leave_lock(self, scope: str, **fields) -> dict:
        """Leave a lock file as another writer would."""
        holder = {"pid": os.getpid(), "host": taste.host_id(), "created_at": taste.now(), "token": "another-writer", **fields}
        self.lock_path(scope).parent.mkdir(parents=True, exist_ok=True)
        self.lock_path(scope).write_text(json.dumps(holder), encoding="utf-8")
        return holder

    def journal(self, scope: str) -> list[dict]:
        path = self.preferences(scope) / "taste.journal.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def test_a_live_holder_refuses_the_write_and_is_reported(self):
        holder = self.leave_lock("project")
        error = self.refused("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual(error["code"], "locked")
        self.assertEqual(error["holder_pid"], os.getpid())
        self.assertEqual(error["stale_after_seconds"], taste.LOCK_STALE_AFTER)
        self.assertIn(error["age_seconds"], range(0, 60))
        self.assertEqual(Path(error["path"]), self.lock_path("project"))
        self.assertEqual(json.loads(self.lock_path("project").read_text(encoding="utf-8")), holder)
        self.assertFalse((self.preferences("project") / "taste.json").exists())

    def test_the_lock_is_released_after_a_write_and_after_a_refusal(self):
        self.put("project", "a", "1")
        self.assertFalse(self.lock_path("project").exists())
        self.refused("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", "9")
        self.assertFalse(self.lock_path("project").exists())

    def test_a_lock_held_on_the_second_scope_leaves_no_lock_on_the_first(self):
        holder = self.leave_lock("global")
        self.assertEqual(self.refused("set", "--scope", "both", "--id", "a", "--value", "1")["code"], "locked")
        self.assertFalse(self.lock_path("project").exists())
        self.assertEqual(json.loads(self.lock_path("global").read_text(encoding="utf-8")), holder)
        self.assertFalse((self.preferences("project") / "taste.json").exists())

    @unittest.skipIf(sys.platform == "win32", "the writer cannot probe another process on Windows")
    def test_a_lock_whose_holder_process_is_gone_is_reclaimed_with_an_audit_note(self):
        pid = dead_pid()
        holder = self.leave_lock("project", pid=pid)
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        prior = {"pid": pid, "created_at": holder["created_at"]}
        self.assertEqual(result["lock_reclaimed"], [{"scope": "project", "reason": "holder-dead", "prior": prior}])
        self.assertFalse(self.lock_path("project").exists())
        note, commit = self.journal("project")
        self.assertEqual({key: note[key] for key in ("event", "scope", "reason", "prior")}, {"event": "lock_reclaimed", "scope": "project", "reason": "holder-dead", "prior": prior})
        self.assertRegex(note["at"], r"Z$")
        self.assertEqual(commit["revision"], 1)
        self.assertEqual(self.record("project")["entries"]["a"]["value"], 1)

    def test_a_lock_older_than_the_bound_is_reclaimed_even_though_its_pid_is_alive(self):
        self.leave_lock("project", created_at=minutes_ago(9))
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "a", "--value", "1")["code"], "locked")
        self.leave_lock("project", created_at=minutes_ago(11))
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual([(note["scope"], note["reason"]) for note in result["lock_reclaimed"]], [("project", "expired")])

    def test_a_fresh_lock_from_another_host_is_never_judged_by_its_pid(self):
        self.leave_lock("project", host="another-host", pid=dead_pid())
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "a", "--value", "1")["code"], "locked")

    def test_a_lock_from_another_host_is_reclaimed_by_age_alone(self):
        self.leave_lock("project", host="another-host", pid=dead_pid(), created_at=minutes_ago(11))
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual([note["reason"] for note in result["lock_reclaimed"]], ["expired"])

    def test_a_lock_without_readable_content_is_judged_by_its_file_time(self):
        for number, content in enumerate(("", "{", "[1]", '"text"', "null")):
            with self.subTest(content=content):
                path = self.lock_path("project")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                error = self.refused("set", "--scope", "project", "--id", f"id{number}", "--value", "1", *(self.expect("project") if self.revision("project") else []))
                self.assertEqual(error["code"], "locked")
                self.assertNotIn("holder_pid", error)
                old = time.time() - 11 * 60
                os.utime(path, (old, old))
                result = self.put("project", f"id{number}", "1")
                self.assertEqual([(note["reason"], note["prior"]) for note in result["lock_reclaimed"]], [("expired", {})])

    def test_a_lock_in_the_format_of_the_previous_writer_is_reclaimed_by_age(self):
        path = self.lock_path("project")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pid": dead_pid(), "created_at": taste.now()}), encoding="utf-8")
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "a", "--value", "1")["code"], "locked")
        path.write_text(json.dumps({"pid": dead_pid(), "created_at": minutes_ago(11)}), encoding="utf-8")
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual([note["reason"] for note in result["lock_reclaimed"]], ["expired"])

    def test_each_scope_records_its_own_reclaim_in_its_own_journal(self):
        self.leave_lock("project", created_at=minutes_ago(11))
        self.leave_lock("global", created_at=minutes_ago(12))
        result = self.ok("set", "--scope", "both", "--id", "a", "--value", "1")
        self.assertEqual([note["scope"] for note in result["lock_reclaimed"]], ["project", "global"])
        for scope in ("project", "global"):
            notes = [entry for entry in self.journal(scope) if entry.get("event") == "lock_reclaimed"]
            self.assertEqual([note["scope"] for note in notes], [scope])
            self.assertFalse(self.lock_path(scope).exists())

    def test_a_refused_write_still_reports_the_lock_it_reclaimed(self):
        self.put("project", "a", "1")
        self.leave_lock("project", created_at=minutes_ago(11))
        code, payload = self.cli("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", "9")
        self.assertEqual((code, payload["error"]["code"]), (1, "stale_revision"))
        self.assertEqual([note["reason"] for note in payload["lock_reclaimed"]], ["expired"])
        self.assertEqual([entry.get("event") for entry in self.journal("project")], [None, "lock_reclaimed"])
        self.assertFalse(self.lock_path("project").exists())

    def test_a_writer_whose_lock_was_reclaimed_mid_operation_writes_nothing(self):
        self.put("project", "a", "1")
        before = self.snapshot("project")
        real_mutate = taste.mutate

        def mutate_then_lose_the_lock(*args, **kwargs):
            result = real_mutate(*args, **kwargs)
            self.lock_path("project").write_text(json.dumps({"token": "the-reclaiming-writer"}), encoding="utf-8")
            return result

        with mock.patch.object(taste, "mutate", mutate_then_lose_the_lock):
            error = self.refused("set", "--scope", "project", "--id", "b", "--value", "2", *self.expect("project"))
        self.assertEqual(error["code"], "lock_lost")
        self.assertEqual(json.loads(self.lock_path("project").read_text(encoding="utf-8"))["token"], "the-reclaiming-writer")
        self.assertEqual({path: data for path, data in self.snapshot("project").items() if path != self.lock_path("project")}, before)


class RollbackTests(WriterCase):
    """A `--scope both` write commits two stores; a failure part-way must put both back."""

    def failing_replace(self, number: int):
        """Make the number-th replace made by the writer fail, counting the rollback's own restores too."""
        real = taste.replace_with_retry
        calls = []

        def replace(source, target, *args, **kwargs):
            calls.append(target)
            if len(calls) == number:
                raise OSError("injected failure")
            return real(source, target, *args, **kwargs)

        return mock.patch.object(taste, "replace_with_retry", replace)

    def state(self) -> dict:
        """The bytes of every file a commit must restore, by scope."""
        def read(scope, name):
            path = self.preferences(scope) / name
            return path.read_bytes() if path.exists() else None

        return {scope: {name: read(scope, name) for name in ("taste.json", "taste.md", "taste.journal.jsonl")} for scope in ("project", "global")}

    def leftovers(self) -> list[Path]:
        return [path for scope in ("project", "global") if self.preferences(scope).exists() for path in self.preferences(scope).iterdir() if path.name.startswith(".taste-") or path.name == "taste.lock"]

    def test_a_failure_at_any_point_of_a_both_write_restores_both_stores_and_their_journals(self):
        self.put("both", "a", "1")
        before = self.state()
        # The forward replaces run in this order: project json, project md, global json, global md.
        for number, failing in enumerate(("project json", "project md", "global json", "global md"), start=1):
            with self.subTest(failing=failing):
                with self.failing_replace(number):
                    error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", *self.expect("project", "global"))
                self.assertEqual((error["code"], error["reason"]), ("write_failed", "injected failure"))
                self.assertEqual(self.state(), before)
                self.assertEqual(self.leftovers(), [])
        self.put("both", "b", "2")
        self.assertEqual((self.revision("project"), self.revision("global")), (2, 2))
        self.assertEqual([line["revision"] for line in [json.loads(text) for text in (self.preferences("project") / "taste.journal.jsonl").read_text(encoding="utf-8").splitlines()]], [1, 2])

    def test_a_failed_first_write_of_a_pair_leaves_no_store_behind(self):
        with self.failing_replace(3):
            self.assertEqual(self.refused("set", "--scope", "both", "--id", "a", "--value", "1")["code"], "write_failed")
        self.assertEqual(self.snapshot("project", "global"), {})
        self.assertFalse(self.ok("status")["stores"]["project"]["exists"])
        self.put("both", "a", "1")
        self.assertEqual((self.revision("project"), self.revision("global")), (1, 1))

    def test_a_failure_while_journaling_restores_the_stores_too(self):
        self.put("both", "a", "1")
        before = self.state()
        real_open = Path.open
        global_journal = self.preferences("global") / "taste.journal.jsonl"

        def journal_unavailable(path, mode="r", *args, **kwargs):
            if path == global_journal and "a" in mode:
                raise OSError("journal unavailable")
            return real_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", journal_unavailable):
            error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", *self.expect("project", "global"))
        self.assertEqual((error["code"], error["reason"]), ("write_failed", "journal unavailable"))
        self.assertEqual(self.state(), before)
        self.assertEqual(self.leftovers(), [])

    def test_a_rollback_that_cannot_restore_a_file_reports_it_and_keeps_its_backup(self):
        self.put("both", "a", "1")
        before = self.state()
        project_md = self.preferences("project") / "taste.md"
        real = taste.replace_with_retry
        calls = []

        def replace(source, target, *args, **kwargs):
            calls.append(target)
            if len(calls) == 3:
                raise OSError("injected failure")
            if Path(source).name.startswith(".taste-rollback-") and Path(target) == project_md:
                raise OSError("restore refused")
            return real(source, target, *args, **kwargs)

        with mock.patch.object(taste, "replace_with_retry", replace):
            error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", *self.expect("project", "global"))
        self.assertEqual((error["code"], error["reason"]), ("write_failed", "injected failure"))
        self.assertIn("incomplete", error["message"])
        self.assertEqual([Path(item["path"]) for item in error["unrestored"]], [project_md])
        backup = Path(error["unrestored"][0]["backup"])
        self.assertEqual(backup.read_bytes(), before["project"]["taste.md"])
        after = self.state()
        self.assertNotEqual(after["project"]["taste.md"], before["project"]["taste.md"])
        for scope, name in (("project", "taste.json"), ("project", "taste.journal.jsonl"), ("global", "taste.json"), ("global", "taste.md"), ("global", "taste.journal.jsonl")):
            self.assertEqual(after[scope][name], before[scope][name], (scope, name))

    def test_a_transient_permission_error_on_replace_does_not_fail_the_write(self):
        real, calls = os.replace, []

        def replace(source, target):
            calls.append(target)
            if len(calls) == 1:
                raise PermissionError("held open by another process")
            return real(source, target)

        with mock.patch.object(taste.os, "replace", replace), mock.patch.object(taste.time, "sleep") as slept:
            self.put("project", "a", "1")
        self.assertEqual(slept.call_args_list, [mock.call(0.05)])
        self.assertEqual(self.record("project")["entries"]["a"]["value"], "1")
        self.assertEqual(self.leftovers(), [])


WORKER = r'''
import contextlib, importlib.util, io, json, sys, time
script, project, worker, writes = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
spec = importlib.util.spec_from_file_location("taste_prefs", script)
taste = importlib.util.module_from_spec(spec)
spec.loader.exec_module(taste)


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        taste.main(["--project-root", project, *args])
    return json.loads(out.getvalue())


done, deadline = 0, time.time() + 60
while done < writes and time.time() < deadline:
    args = ["set", "--scope", "both", "--id", f"w{worker}-{done}", "--value", json.dumps(done)]
    for scope in ("project", "global"):
        store = run("status", "--scope", scope)["stores"][scope]
        if store["exists"]:
            args += ["--expect-revision", f"{scope}={store['revision']}"]
    result = run(*args)
    if result["ok"]:
        done += 1
    elif result["error"]["code"] not in ("locked", "stale_revision", "revision_required"):
        print(json.dumps(result))
        sys.exit(1)
    else:
        time.sleep(0.005)
sys.exit(0 if done == writes else 2)
'''


class ConcurrencyTests(unittest.TestCase):
    """Real processes contending for one store: every acknowledged write survives and none is torn."""

    WORKERS, WRITES = 6, 6

    def test_concurrent_writers_lose_no_acknowledged_write_and_keep_both_chains_intact(self):
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as global_dir:
            project, global_home = Path(project_dir).resolve(), Path(global_dir).resolve()
            env = {**os.environ, "SUPREMETEAM_HOME": str(global_home), "SUPREMETEAM_OWNER": "test-owner"}
            workers = [subprocess.Popen([sys.executable, "-c", WORKER, str(SCRIPT), str(project), str(n), str(self.WRITES)], env=env, stdout=subprocess.PIPE, text=True) for n in range(self.WORKERS)]
            outputs = [worker.communicate(timeout=120)[0] for worker in workers]
            self.assertEqual([worker.returncode for worker in workers], [0] * self.WORKERS, outputs)
            total = self.WORKERS * self.WRITES
            for scope, base in (("project", project / "skillset-saves" / "preferences"), ("global", global_home / "preferences")):
                with self.subTest(scope=scope):
                    current = json.loads((base / "taste.json").read_text(encoding="utf-8"))
                    self.assertEqual(current["revision"], total)
                    self.assertEqual(sorted(current["entries"]), sorted(f"w{n}-{i}" for n in range(self.WORKERS) for i in range(self.WRITES)))
                    self.assertEqual(taste.validate(current, scope), current)
                    journal = [json.loads(line) for line in (base / "taste.journal.jsonl").read_text(encoding="utf-8").splitlines()]
                    self.assertEqual([line["revision"] for line in journal], list(range(1, total + 1)))
                    revisions = {}
                    for path in (base / "_history").glob("*.json"):
                        record = json.loads(path.read_text(encoding="utf-8"))
                        revisions[record["revision"]] = record
                    revisions[total] = current
                    self.assertEqual(sorted(revisions), list(range(1, total + 1)))
                    for revision in range(2, total + 1):
                        self.assertEqual(revisions[revision]["previous_revision_digest"], revisions[revision - 1]["canonical_record_digest"])
                    self.assertEqual(sorted(path.name for path in base.iterdir()), ["_history", "taste.journal.jsonl", "taste.json", "taste.md"])


if __name__ == "__main__":
    unittest.main()
