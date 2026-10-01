#!/usr/bin/env python3
"""Run-state writer: mutual exclusion, evidence, closed runs, recovery, and the audit trail.

The writer had no mutual exclusion, so two overlapping invocations lost an update
or left the lock and the state at different revisions, and every host tool event
runs a heartbeat against the same run the orchestrator is checkpointing. These
tests make each interleaving deterministic instead of racing for it: a driver
process runs a real writer and stops it after it has read the run and decided,
before it writes, and the test runs the rival while the first is held there.
Without exclusion the rival finishes inside that window and the first then
overwrites it; with it the rival waits for the first and finds the run changed.

The remaining cases were each reproduced against the previous writer: create
accepted no evidence, a vanished evidence path could never be dropped, a closed
run could be closed again in place, `recover --rollback` with no journal reclaimed
a lock with an empty reason, rollback restored an old heartbeat or published an
empty record from a damaged snapshot, an interrupted create had no way out, and
the audit trail recorded events that never happened and none that did.

Round two found what those fixes introduced: a run created under the previous
writer's looser id could no longer be closed or recovered, `--drop-evidence` could
leave a run with no evidence, and a hook that skipped because a writer held the lock
was counted as a hook fault.
"""
from __future__ import annotations

import errno
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
SAVE_RUN = HOOK_DIR / "save_run.py"
sys.path.insert(0, str(HOOK_DIR))
import _saves  # noqa: E402
import _state  # noqa: E402
import run_heartbeat  # noqa: E402
import save_run  # noqa: E402

# A real writer, stopped after it has read the run and decided but before it
# writes: `snapshot` precedes the publish of a checkpoint, `stale` is the last
# check before a heartbeat writes, and `probe` follows the competing-run check of
# a create.
DRIVER = r"""
import json, sys, time
from pathlib import Path

hooks, project, run_id, operation, reached, go = sys.argv[1:7]
sys.path.insert(0, hooks)
import save_run

pause_in = {"checkpoint": "snapshot", "heartbeat": "stale", "create": "probe"}[operation]
original = getattr(save_run.RunStore, pause_in)

def paused(self, *args):
    Path(reached).write_text("1", encoding="utf-8")
    deadline = time.monotonic() + 60
    while not Path(go).exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    return original(self, *args)

setattr(save_run.RunStore, pause_in, paused)
store = save_run.RunStore(Path(project), run_id)
try:
    if operation == "checkpoint":
        result = store.checkpoint("admiral", 1, ["a.md"], "active", "from-driver", {"writer": "driver"})
    elif operation == "heartbeat":
        result = store.heartbeat("admiral", source="hook:test")
    else:
        result = store.create("admiral", ["README.md"], "agent", "from-driver", {"writer": "driver"})
    print(json.dumps({"result": "ok", **result}))
except (save_run.Refused, save_run.Degraded) as exc:
    print(json.dumps({"result": "refused", "reason": str(exc)}))
"""


@contextmanager
def crash_when_writing(name: str):
    """Fail the writer as if the process died just before it wrote ``name``."""
    real = save_run.atomic_write

    def failing(path, data):
        if path.name == name:
            raise save_run.Degraded(f"injected failure before writing {name}")
        return real(path, data)

    with mock.patch.object(save_run, "atomic_write", failing):
        yield


class RunStateCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name).resolve()
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        for name in ("README.md", "a.md", "b.md", "notes.md"):
            (self.project / name).write_text(f"# {name}\n", encoding="utf-8")
        self.run_dir = self.project / "skillset-saves" / "runs" / "run-1"
        save_run.WRITE_NOTES.clear()

    def command(self, run_id: str, *args: str) -> list[str]:
        # The `=` form, so an id that starts with a dash is not read as an option.
        return [sys.executable, str(SAVE_RUN), *args, "--project-root", str(self.project), f"--run-id={run_id}"]

    def save(self, *args: str, run_id: str = "run-1") -> tuple[int, dict]:
        proc = subprocess.run(self.command(run_id, *args), text=True, capture_output=True, check=False)
        text = (proc.stdout or proc.stderr).strip()
        return proc.returncode, json.loads(text[text.index("{"):])

    def store(self, run_id: str = "run-1", **options) -> save_run.RunStore:
        return save_run.RunStore(self.project, run_id, **options)

    def create(self, *evidence: str) -> None:
        code, out = self.save("create", *(arg for path in (evidence or ("README.md",)) for arg in ("--evidence", path)))
        self.assertEqual(code, 0, out)

    def state(self) -> dict:
        return json.loads((self.run_dir / "_state.md").read_text(encoding="utf-8"))

    def lock(self) -> dict:
        return json.loads((self.run_dir / "_lock.md").read_text(encoding="utf-8"))

    def events(self) -> list[dict]:
        return [json.loads(line) for line in (self.run_dir / "_audit-trail.md").read_text(encoding="utf-8").splitlines()]

    def age_records(self, minutes: int, *extra: Path) -> None:
        stamp = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        for path in (self.run_dir / "_lock.md", *extra):
            record = json.loads(path.read_text(encoding="utf-8"))
            record["heartbeat"] = stamp
            path.write_text(json.dumps(record), encoding="utf-8")


class WriterExclusionTests(RunStateCase):
    def start_driver(self, run_id: str, operation: str) -> tuple[subprocess.Popen, Path]:
        reached, go = self.scratch / f"{operation}.reached", self.scratch / f"{operation}.go"
        proc = subprocess.Popen([sys.executable, "-c", DRIVER, str(HOOK_DIR), str(self.project), run_id, operation,
                                 str(reached), str(go)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, proc)
        deadline = time.monotonic() + 30
        while not reached.exists():
            if proc.poll() is not None:
                self.fail(f"the driver exited before its pause: {proc.stdout.read()} {proc.stderr.read()}")
            if time.monotonic() > deadline:
                self.fail("the driver never reached its pause")
            time.sleep(0.01)
        return proc, go

    def start_rival(self, run_id: str, *args: str) -> subprocess.Popen:
        proc = subprocess.Popen(self.command(run_id, *args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop, proc)
        return proc

    @staticmethod
    def stop(proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.kill()
        proc.communicate()

    def finish_both(self, driver: subprocess.Popen, go: Path, rival: subprocess.Popen) -> tuple[dict, dict]:
        """Let the held writer go, then collect both outcomes. The rival either finished inside
        the window (nothing excluded it) or is still waiting for the lock the driver holds."""
        try:
            rival_out = rival.communicate(timeout=1.0)[0]
        except subprocess.TimeoutExpired:
            rival_out = None
        go.write_text("1", encoding="utf-8")
        first = json.loads(driver.communicate(timeout=30)[0])
        second = json.loads(rival_out if rival_out is not None else rival.communicate(timeout=30)[0])
        return first, second

    def test_overlapping_checkpoints_on_one_revision_do_not_both_win(self):
        self.create()
        driver, go = self.start_driver("run-1", "checkpoint")
        rival = self.start_rival("run-1", "checkpoint", "--expect-revision", "1", "--evidence", "b.md", "--set", "writer=rival")
        first, second = self.finish_both(driver, go, rival)
        self.assertEqual(sorted([first["result"], second["result"]]), ["ok", "refused"], (first, second))
        self.assertIn("revision conflict", second["reason"])
        self.assertEqual((self.state()["revision"], self.state()["writer"]), (2, "driver"))
        self.assertEqual([e["event"] for e in self.events() if e["event"] == "checkpoint"], ["checkpoint"])

    def test_a_heartbeat_cannot_overwrite_a_checkpoint_published_while_it_was_deciding(self):
        self.create()
        driver, go = self.start_driver("run-1", "heartbeat")
        rival = self.start_rival("run-1", "checkpoint", "--expect-revision", "1", "--evidence", "a.md")
        first, second = self.finish_both(driver, go, rival)
        self.assertEqual((first["result"], second["result"]), ("ok", "ok"), (first, second))
        code, out = self.save("status")
        self.assertEqual(out["status"], "active", out)
        pointer = json.loads((self.project / "skillset-saves" / "_latest.md").read_text(encoding="utf-8"))
        self.assertEqual((self.state()["revision"], self.lock()["revision"], pointer["revision"]), (2, 2, 2))

    def test_two_creates_cannot_both_take_the_session_pin(self):
        driver, go = self.start_driver("run-1", "create")
        rival = self.start_rival("run-2", "create", "--evidence", "README.md")
        first, second = self.finish_both(driver, go, rival)
        self.assertEqual(sorted([first["result"], second["result"]]), ["ok", "refused"], (first, second))
        self.assertIn("another run holds the session pin", second["reason"])
        code, out = self.save("status")
        self.assertNotEqual(out["status"], "conflicting", out)

    def test_a_writer_that_must_succeed_waits_a_bounded_time_and_then_refuses_clearly(self):
        self.create()
        driver, go = self.start_driver("run-1", "checkpoint")
        started = time.monotonic()
        code, out = self.save("checkpoint", "--expect-revision", "1", "--lock-timeout", "0.3")
        elapsed = time.monotonic() - started
        go.write_text("1", encoding="utf-8")
        driver.communicate(timeout=30)
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertIn("write lock", out["reason"])
        self.assertIn("retry", out["reason"])
        self.assertLess(elapsed, 10)

    def test_a_hook_never_waits_for_the_writer_lock(self):
        """A hook holds up the host for as long as it runs, so a busy writer means no refresh."""
        self.create()
        driver, go = self.start_driver("run-1", "checkpoint")
        self.age_records(12)
        before = self.lock()["heartbeat"]
        started = time.monotonic()
        env = {**os.environ, "SUPREMETEAM_PROJECT_DIR": str(self.project), "CLAUDE_PROJECT_DIR": str(self.project)}
        proc = subprocess.run([sys.executable, str(HOOK_DIR / "pre_tool_use.py")],
                              input=json.dumps({"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}),
                              text=True, capture_output=True, env=env, check=False)
        elapsed = time.monotonic() - started
        while_held = self.lock()
        go.write_text("1", encoding="utf-8")
        driver.communicate(timeout=30)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""), proc.stderr)
        self.assertEqual(while_held["heartbeat"], before, "the hook skipped its refresh while a writer held the lock")
        self.assertNotIn("heartbeat_source", while_held)
        self.assertLess(elapsed, 5)
        observed = _state.load_observations(self.project)
        self.assertEqual(observed.get("PreToolUse", {}).get("faults", 0), 0,
                         "a skip because the writer is busy is the design, not a hook fault")


class LockMechanismTests(RunStateCase):
    def test_staging_files_are_named_per_process(self):
        """One shared `<name>.tmp` let overlapping writers truncate each other's half-written file."""
        seen: list[str] = []
        real = os.replace

        def spy(source, target):
            seen.append(Path(source).name)
            return real(source, target)

        with mock.patch.object(os, "replace", spy):
            self.store().create("admiral", ["README.md"], "agent", "next", {})
        self.assertTrue(seen)
        for name in seen:
            self.assertIn(f".{os.getpid()}.tmp", name)

    def test_a_lock_another_writer_holds_is_refused_after_the_wait_and_nothing_is_written(self):
        holder = self.store()
        with holder.exclusive(create=True):
            rival = self.store(lock_timeout=0.1)
            with self.assertRaises(save_run.LockBusy) as raised:
                rival.create("admiral", ["README.md"], "agent", "next", {})
        self.assertIn("write lock", str(raised.exception))
        self.assertFalse((self.run_dir / "_state.md").exists())

    def test_a_file_system_without_locking_degrades_to_an_unlocked_write_and_says_so(self):
        stub = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8,
                               flock=mock.Mock(side_effect=OSError(errno.ENOLCK, "No locks available")))
        with mock.patch.object(save_run, "fcntl", stub):
            result = self.store().create("admiral", ["README.md"], "agent", "next", {})
        self.assertEqual(result["result"], "ok")
        self.assertTrue(any("without mutual exclusion" in note for note in save_run.WRITE_NOTES), save_run.WRITE_NOTES)

    def test_the_windows_backend_locks_one_byte_and_reads_contention_as_busy(self):
        """Not run on Windows here: this checks the call sequence and the contention mapping against a stub of msvcrt."""
        calls: list[int] = []

        def locking(fd, mode, length):
            calls.append(mode)
            if mode == 1 and calls.count(1) == 1:
                raise OSError(errno.EACCES, "Permission denied")
            self.assertEqual(length, 1)

        stub = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=0, locking=locking)
        with mock.patch.object(save_run, "fcntl", None), mock.patch.object(save_run, "msvcrt", stub):
            with save_run.WriteLock(self.project / "skillset-saves" / "_write.lock", 2.0, "lock", create_dir=True) as lock:
                self.assertTrue(lock.held)
        self.assertEqual(calls, [1, 1, 0], "one contended attempt, one that took the lock, one release")

    def test_a_heartbeat_skips_when_another_writer_already_refreshed_it(self):
        self.create()
        before = (self.run_dir / "_lock.md").read_bytes()
        result = self.store().heartbeat("admiral", source="hook:test", min_age=300)
        self.assertEqual(result["skipped"], "heartbeat is already fresh")
        self.assertEqual((self.run_dir / "_lock.md").read_bytes(), before)

    def test_a_busy_lock_skips_the_optional_hook_refresh_and_refuses_the_one_that_must_happen(self):
        self.create()
        with self.store().exclusive():
            skipped = self.store().heartbeat("admiral", source="hook:test", wait=0.05, min_age=300)
            self.assertEqual(skipped["skipped"], "another writer holds the save write lock")
            with self.assertRaises(save_run.LockBusy):
                self.store().heartbeat("admiral", wait=0.05)

    def test_a_heartbeat_refuses_a_run_whose_lock_and_state_disagree(self):
        self.create()
        lock = self.lock()
        lock["revision"] = 7
        (self.run_dir / "_lock.md").write_text(json.dumps(lock), encoding="utf-8")
        code, out = self.save("heartbeat")
        self.assertEqual(code, 1, out)
        self.assertIn("revisions differ", out["reason"])


class HeartbeatHotPathTests(RunStateCase):
    """Every host event runs the refresh; a scan of every saved run made each one cost as much as the history is long."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"SUPREMETEAM_PROJECT_DIR": str(self.project)})
        patch.start()
        self.addCleanup(patch.stop)
        self.scans = 0
        real = _saves.inspect_saves

        def counting(*args, **kwargs):
            self.scans += 1
            return real(*args, **kwargs)

        scan = mock.patch.object(_saves, "inspect_saves", counting)
        scan.start()
        self.addCleanup(scan.stop)

    def refresh(self):
        return run_heartbeat.refresh({"session_id": "host-1"}, "PreToolUse")

    def test_a_fresh_heartbeat_costs_no_scan(self):
        self.create()
        self.assertIsNone(self.refresh())
        self.assertEqual(self.scans, 0)

    def test_an_idle_project_with_history_scans_at_most_once_a_minute(self):
        self.create()
        self.assertEqual(self.save("complete")[0], 0)
        self.age_records(60)
        for _ in range(4):
            self.assertIsNone(self.refresh())
        self.assertEqual(self.scans, 1)

    def test_a_due_heartbeat_is_refreshed_once_and_the_next_call_is_free(self):
        self.create()
        self.age_records(12)
        result = self.refresh()
        self.assertEqual(result["source"], "hook:PreToolUse", result)
        self.assertEqual(self.scans, 1)
        self.assertIsNone(self.refresh())
        self.assertEqual(self.scans, 1)

    def test_a_refresh_skipped_for_a_busy_writer_is_not_counted_as_a_fault(self):
        self.create()
        self.age_records(12)
        with self.store().exclusive():
            self.assertEqual(self.refresh()["skipped"], "another writer holds the save write lock")
        self.assertEqual(_state.load_observations(self.project).get("PreToolUse", {}).get("faults", 0), 0)

    def test_a_damaged_throttle_marker_does_not_switch_refreshing_off(self):
        self.create()
        self.age_records(12)
        marker = self.project / ".harness-state" / "observations" / "heartbeat-scan.json"
        marker.parent.mkdir(parents=True)
        marker.write_text("[]", encoding="utf-8")
        self.assertEqual(self.refresh()["source"], "hook:PreToolUse")


class EvidenceTests(RunStateCase):
    def test_create_refuses_a_run_with_no_evidence_and_writes_nothing(self):
        """It used to publish an empty evidence list, return ok, and read back as corrupt."""
        code, out = self.save("create")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertIn("--evidence", out["reason"])
        self.assertFalse(self.run_dir.exists(), "a refused create leaves no directory behind")

    def test_a_create_refused_for_its_evidence_leaves_no_directory_behind(self):
        code, out = self.save("create", "--evidence", "missing.md")
        self.assertEqual(code, 1, out)
        self.assertIn("evidence path missing", out["reason"])
        self.assertFalse(self.run_dir.exists())

    def test_one_spelling_of_an_evidence_path_is_registered_and_hashed(self):
        self.create("./README.md")
        self.assertEqual(self.save("checkpoint", "--evidence", "README.md", "--evidence", "./notes.md", "--evidence", "notes.md")[0], 0)
        state = self.state()
        self.assertEqual(state["evidence_paths"], ["README.md", "notes.md"])
        self.assertEqual(sorted(state["artifact_hashes"]), state["evidence_paths"])

    def test_a_vanished_evidence_path_can_be_dropped_with_a_recorded_reason(self):
        """It stayed in the union for ever, so every later checkpoint was refused and the remedy in the docs could not work."""
        self.create("README.md", "notes.md")
        (self.project / "notes.md").unlink()
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("--drop-evidence", out["reason"])
        self.assertEqual(self.save("checkpoint", "--drop-evidence", "notes.md")[0], 1, "a drop needs its reason")
        code, out = self.save("checkpoint", "--drop-evidence", "./notes.md", "--reason", "pruned after the size advisory")
        self.assertEqual((code, out["dropped_evidence"]), (0, ["notes.md"]), out)
        self.assertEqual(self.state()["evidence_paths"], ["README.md"])
        self.assertNotIn("notes.md", self.state()["artifact_hashes"])
        recorded = [event for event in self.events() if event.get("dropped_evidence")][0]
        self.assertEqual((sorted(recorded["dropped_evidence"]), recorded["reason"]), (["notes.md"], "pruned after the size advisory"))
        self.assertRegex(recorded["dropped_evidence"]["notes.md"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.save("status")[1]["status"], "active")

    def test_a_moved_evidence_file_is_superseded_in_one_checkpoint(self):
        self.create("README.md", "notes.md")
        (self.project / "notes.md").replace(self.project / "b.md")
        code, out = self.save("checkpoint", "--drop-evidence", "notes.md", "--evidence", "b.md", "--reason", "moved to b.md")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["evidence_paths"], ["README.md", "b.md"])

    def test_dropping_the_only_evidence_path_is_refused_not_published_as_an_empty_list(self):
        """The drop published `evidence_paths: []` and returned ok, and the run then read corrupt."""
        self.create()
        (self.project / "README.md").unlink()
        code, out = self.save("checkpoint", "--drop-evidence", "README.md", "--reason", "pruned")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertIn("at least one evidence path", out["reason"])
        self.assertEqual((self.state()["revision"], self.state()["evidence_paths"]), (1, ["README.md"]))
        code, out = self.save("checkpoint", "--drop-evidence", "README.md", "--evidence", "b.md", "--reason", "replaced")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state()["evidence_paths"], ["b.md"])
        self.assertEqual(self.save("status")[1]["status"], "active")

    def test_dropping_an_unregistered_path_or_dropping_and_registering_one_path_is_refused(self):
        self.create()
        code, out = self.save("checkpoint", "--drop-evidence", "b.md", "--reason", "why")
        self.assertEqual(code, 1, out)
        self.assertIn("not registered", out["reason"])
        code, out = self.save("checkpoint", "--drop-evidence", "README.md", "--evidence", "README.md", "--reason", "why")
        self.assertEqual(code, 1, out)
        self.assertEqual(self.state()["revision"], 1)

    def test_a_held_run_with_a_missing_path_stays_corrupt_until_it_is_dropped_but_a_closed_one_does_not(self):
        self.create("README.md", "notes.md")
        (self.project / "notes.md").unlink()
        self.assertEqual(self.save("status")[1]["status"], "corrupt")
        self.assertEqual(self.save("checkpoint", "--drop-evidence", "notes.md", "--reason", "gone")[0], 0)
        self.assertEqual(self.save("status")[1]["status"], "active")
        self.assertEqual(self.save("checkpoint", "--evidence", "b.md")[0], 0)
        self.assertEqual(self.save("complete")[0], 0)
        (self.project / "b.md").unlink()
        code, out = self.save("status")
        self.assertEqual((out["status"], out["evidence_missing"]), ("complete", ["b.md"]), out)


class LegacyRunIdTests(RunStateCase):
    """The previous writer accepted any single path segment as a run id. The new grammar governs creation only,
    so a run made under a looser id can still be read, kept alive, recovered and closed."""

    LOOSE_IDS = ("my run", "-leading-dash", ".leading-dot", "semi;colon$and'quote", "x" * 129)

    def legacy(self, run_id: str) -> Path:
        """What the previous writer left: create no longer takes the id, so build the run under a valid one and rename it."""
        self.create()
        renamed = self.run_dir.with_name(run_id)
        self.run_dir.rename(renamed)
        self.run_dir = renamed
        records = [renamed / "_state.md", renamed / "_lock.md", self.project / "skillset-saves" / "_latest.md"]
        for path in records:
            record = json.loads(path.read_text(encoding="utf-8"))
            record["run_id"] = run_id
            path.write_text(json.dumps(record), encoding="utf-8")
        return renamed

    def test_create_still_refuses_an_id_outside_the_grammar_and_writes_nothing(self):
        for run_id in self.LOOSE_IDS:
            with self.subTest(run_id=run_id):
                code, out = self.save("create", "--evidence", "README.md", run_id=run_id)
                self.assertEqual((code, out["result"]), (1, "refused"), out)
                self.assertIn("letters, digits", out["reason"])
        self.assertFalse((self.project / "skillset-saves" / "runs").exists())

    def test_every_operation_still_reaches_a_run_created_under_a_looser_id(self):
        for run_id in self.LOOSE_IDS:
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as tmp:
                self.project = Path(tmp).resolve()
                for name in ("README.md", "b.md"):
                    (self.project / name).write_text("x\n", encoding="utf-8")
                self.run_dir = self.project / "skillset-saves" / "runs" / "run-1"
                self.legacy(run_id)
                self.assertEqual(self.save("status", run_id=run_id)[1]["requested_run"]["state"], "active")
                self.assertEqual(self.save("heartbeat", run_id=run_id)[0], 0)
                self.assertEqual(self.save("checkpoint", "--evidence", "b.md", run_id=run_id)[0], 0)
                self.assertEqual(self.save("release", run_id=run_id)[0], 0)
                self.assertEqual(self.save("checkpoint", run_id=run_id)[0], 0, "a released run resumes")
                self.age_records(45)
                code, out = self.save("recover", "--reason", "stale after a crash", run_id=run_id)
                self.assertEqual((code, out["operation"]), (0, "recover"), out)
                self.assertEqual(self.save("complete", run_id=run_id)[0], 0)
                self.assertEqual(self.save("status", run_id=run_id)[1]["status"], "complete")
                self.assertEqual(self.save("checkpoint", "--reopen", run_id=run_id)[0], 0)
                self.assertEqual(self.save("block", run_id=run_id)[0], 0)

    def test_the_hook_refresh_keeps_a_run_under_a_looser_id_alive_and_counts_no_fault(self):
        self.legacy("my run")
        self.age_records(12)
        with mock.patch.dict(os.environ, {"SUPREMETEAM_PROJECT_DIR": str(self.project)}):
            result = run_heartbeat.refresh({"session_id": "host-1"}, "PreToolUse")
        self.assertEqual(result["source"], "hook:PreToolUse", result)
        self.assertEqual(_state.load_observations(self.project).get("PreToolUse", {}).get("faults", 0), 0)

    def test_an_id_that_is_not_one_path_segment_is_still_refused_by_every_operation(self):
        for run_id in ("..", "a/b", "a\\b", "c:x", "q?"):
            for operation in ("status", "checkpoint", "recover"):
                with self.subTest(run_id=run_id, operation=operation):
                    code, out = self.save(operation, "--reason", "x", run_id=run_id)
                    self.assertEqual((code, out["result"]), (1, "refused"), out)
                    self.assertIn("unsafe run id", out["reason"])


class ClosedRunTests(RunStateCase):
    def test_a_closed_run_is_not_closed_again_in_place(self):
        """`complete` on a complete run, or `block` on one, rewrote it as a new revision with no reopen on the trail."""
        self.create()
        self.assertEqual(self.save("complete", "--set", "delivery=first")[0], 0)
        for operation in ("complete", "block"):
            with self.subTest(operation=operation):
                code, out = self.save(operation, "--set", "delivery=second")
                self.assertEqual((code, out["result"]), (1, "refused"), out)
                self.assertIn("checkpoint --reopen", out["reason"])
        self.assertEqual((self.state()["revision"], self.state()["delivery"], self.state()["status"]), (2, "first", "complete"))

    def test_a_blocked_run_is_not_completed_in_place_but_reopens_and_closes_again(self):
        self.create()
        self.assertEqual(self.save("block")[0], 0)
        self.assertEqual(self.save("complete")[0], 1)
        self.assertEqual(self.save("checkpoint", "--reopen")[0], 0)
        self.assertEqual(self.save("complete")[0], 0)
        self.assertEqual([e["event"] for e in self.events() if e["event"] != "refused"], ["create", "blocked", "reopen", "complete"])

    def test_a_released_run_can_still_be_completed(self):
        self.create()
        self.assertEqual(self.save("release")[0], 0)
        self.assertEqual(self.save("complete")[0], 0)


class BlockReasonTests(RunStateCase):
    def test_block_refuses_a_reason_it_would_discard(self):
        """`--reason` belongs to recover and checkpoint --drop-evidence; block accepted it and recorded nothing."""
        self.create()
        code, out = self.save("block", "--reason", "waiting on the owner")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertIn("--reason", out["reason"])
        self.assertIn("recover", out["reason"])
        self.assertEqual((self.state()["status"], self.state()["revision"]), ("active", 1))
        self.assertEqual(self.events()[-1]["event"], "refused")

    def test_block_without_a_reason_still_blocks_and_says_why_through_next_action(self):
        self.create()
        code, out = self.save("block", "--next-action", "waiting on the owner")
        self.assertEqual(code, 0, out)
        self.assertEqual((self.state()["status"], self.state()["next_action"]), ("blocked", "waiting on the owner"))


class RecoveryTests(RunStateCase):
    def crash_second_checkpoint(self) -> None:
        """Revision 3 dies after its lock was written and before its state was; revision 2 is the last coherent one."""
        self.create()
        self.assertEqual(self.save("checkpoint")[0], 0)
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().checkpoint("admiral", 2, [], "active", None, {})
        self.assertEqual(self.save("status")[1]["status"], "interrupted")

    def test_rollback_with_no_journal_is_refused_and_does_not_reclaim_the_lock(self):
        self.create()
        self.age_records(45)
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertIn("no _journal.json", out["reason"])
        self.assertEqual(self.lock()["revision"], 1, "nothing was reclaimed")

    def test_reclaiming_a_stale_lock_needs_a_reason_that_says_something(self):
        self.create()
        self.age_records(45)
        for reason in ("", "   "):
            with self.subTest(reason=reason):
                code, out = self.save("recover", "--reason", reason)
                self.assertEqual(code, 1, out)
                self.assertIn("--reason", out["reason"])
        self.assertEqual(self.lock()["revision"], 1)

    def test_rollback_leaves_a_fresh_heartbeat_so_the_run_can_checkpoint_again(self):
        """It restored the old heartbeat, so a run interrupted overnight came back stale after an ok rollback."""
        self.crash_second_checkpoint()
        self.age_records(90, self.run_dir / "_history" / "rev-2.lock.json")
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"], out["revision"]), (0, "rollback", 2), out)
        self.assertEqual(self.save("status")[1]["status"], "active")
        self.assertEqual(self.save("checkpoint", "--expect-revision", "2")[0], 0)

    def test_roll_forward_also_leaves_a_fresh_heartbeat(self):
        self.crash_second_checkpoint()
        state = self.state()
        state["revision"] = 3
        (self.run_dir / "_state.md").write_text(json.dumps(state), encoding="utf-8")
        self.age_records(90)
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"], out["revision"]), (0, "rollforward", 3), out)
        self.assertEqual(self.save("status")[1]["status"], "active")

    def test_a_truncated_snapshot_is_never_published_as_the_restored_state(self):
        """`read_json(...) or {}` wrote an empty record over the run, and the run read corrupt after an ok."""
        self.crash_second_checkpoint()
        (self.run_dir / "_history" / "rev-2.state.json").write_text('{"schema_ver', encoding="utf-8")
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"]), (0, "rollback"), out)
        self.assertEqual(self.state()["revision"], 2)
        self.assertEqual(self.save("status")[1]["status"], "active")
        self.assertEqual([e["source"] for e in self.events() if e["event"] == "rollback"], ["state file (lock rebuilt)"])

    def test_rollback_refuses_when_neither_the_snapshot_nor_the_state_can_be_trusted(self):
        self.crash_second_checkpoint()
        (self.run_dir / "_history" / "rev-2.state.json").write_text("{", encoding="utf-8")
        (self.run_dir / "_state.md").unlink()
        lock_before = (self.run_dir / "_lock.md").read_bytes()
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertIn("unreadable", out["reason"])
        self.assertEqual((self.run_dir / "_lock.md").read_bytes(), lock_before)
        self.assertTrue((self.run_dir / "_journal.json").exists(), "the interruption stays visible")

    def test_a_damaged_snapshot_is_replaced_at_the_next_snapshot_not_kept_for_ever(self):
        self.create()
        store = self.store()
        store.snapshot(1)
        damaged = self.run_dir / "_history" / "rev-1.state.json"
        damaged.write_text('{"run_id"', encoding="utf-8")
        store.snapshot(1)
        self.assertEqual(json.loads(damaged.read_text(encoding="utf-8"))["revision"], 1)

    def test_a_good_snapshot_is_never_rewritten(self):
        self.create()
        store = self.store()
        store.snapshot(1)
        kept = self.run_dir / "_history" / "rev-1.state.json"
        record = json.loads(kept.read_text(encoding="utf-8"))
        record["marker"] = "written by the first snapshot"
        kept.write_text(json.dumps(record), encoding="utf-8")
        store.snapshot(1)
        self.assertEqual(json.loads(kept.read_text(encoding="utf-8"))["marker"], "written by the first snapshot")

    def test_a_create_that_died_mid_publish_rolls_back_and_the_run_id_is_usable_again(self):
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().create("admiral", ["README.md"], "agent", "next", {})
        self.assertEqual(self.save("status")[1]["status"], "interrupted")
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"], out["revision"]), (0, "rollback", 0), out)
        remaining = sorted(path.name for path in self.run_dir.iterdir())
        self.assertNotIn("_lock.md", remaining)
        self.assertNotIn("_journal.json", remaining)
        self.assertTrue([p for p in (self.run_dir / "_history").iterdir() if ".unpublished-" in p.name], "the bytes are kept as evidence")
        code, out = self.save("status")
        self.assertEqual((out["status"], out["requested_run"]["state"]), ("uninitialized", "uninitialized"), out)
        self.assertEqual(self.save("create", "--evidence", "README.md")[0], 0)
        self.assertEqual([e["event"] for e in self.events()], ["rollback", "create"])

    def test_an_interrupted_create_says_how_to_recover(self):
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().create("admiral", ["README.md"], "agent", "next", {})
        code, out = self.save("create", "--evidence", "README.md")
        self.assertEqual(code, 1, out)
        self.assertIn("recover --rollback", out["reason"])


class AuditTrailTests(RunStateCase):
    def test_a_publish_that_fails_leaves_no_event_for_a_revision_that_never_existed(self):
        self.create()
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().checkpoint("admiral", 1, [], "active", None, {})
        self.assertEqual([e["event"] for e in self.events()], ["create"])

    def test_an_audit_append_that_fails_leaves_the_journal_so_the_gap_is_visible_and_recoverable(self):
        self.create()
        real = save_run.RunStore.append_audit

        def failing(store, event, payload):
            if event == "checkpoint":
                raise save_run.Degraded("audit append failed: No space left on device")
            return real(store, event, payload)

        with mock.patch.object(save_run.RunStore, "append_audit", failing):
            with self.assertRaises(save_run.Degraded) as raised:
                self.store().checkpoint("admiral", 1, [], "active", None, {})
        self.assertIn("audit event was not recorded", str(raised.exception))
        self.assertEqual(self.save("status")[1]["status"], "interrupted")
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"], out["revision"]), (0, "rollforward", 2), out)
        self.assertEqual(self.save("status")[1]["status"], "active")

    def test_refused_and_degraded_operations_reach_the_trail(self):
        self.create()
        self.assertEqual(self.save("checkpoint", "--expect-revision", "9", "--owner", "admiral")[0], 1)
        pointer = self.project / "skillset-saves" / "_latest.md"
        pointer.unlink()
        pointer.mkdir()
        code, out = self.save("checkpoint")
        self.assertEqual((code, out["result"]), (2, "degraded"), out)
        events = self.events()
        self.assertEqual([e["event"] for e in events], ["create", "refused", "checkpoint", "pointer-degraded", "degraded"])
        self.assertEqual((events[1]["operation"], events[1]["owner"]), ("checkpoint", "admiral"))
        self.assertIn("revision conflict", events[1]["reason"])

    def test_a_refusal_does_not_create_a_run_directory_to_hold_its_event(self):
        code, out = self.save("checkpoint", run_id="ghost")
        self.assertEqual(code, 1, out)
        self.assertFalse((self.project / "skillset-saves" / "runs" / "ghost").exists())

    def test_recovery_evidence_names_paths_relative_to_the_project(self):
        """The trail and the state carried the absolute path of the lock, user name included."""
        self.create()
        self.age_records(45)
        code, out = self.save("recover", "--reason", "stale")
        self.assertEqual(code, 0, out)
        expected = "skillset-saves/runs/run-1/_lock.md"
        self.assertEqual(out["evidence"]["prior_lock_path"], expected)
        self.assertEqual(self.state()["recovered_from"]["prior_lock_path"], expected)
        self.assertNotIn(str(self.project), (self.run_dir / "_audit-trail.md").read_text(encoding="utf-8"))

    def test_a_degraded_result_reports_the_reason_without_the_absolute_path(self):
        self.create()
        pointer = self.project / "skillset-saves" / "_latest.md"
        pointer.unlink()
        pointer.mkdir()
        self.save("checkpoint")
        self.assertNotIn(str(self.project), (self.run_dir / "_audit-trail.md").read_text(encoding="utf-8"))


@unittest.skipUnless(os.name == "posix", "POSIX permission bits")
class SavedFileModeTests(RunStateCase):
    """SEC-19: the writer took whatever mode the umask gave, so a permissive umask left every record world-readable."""

    def setUp(self):
        super().setUp()
        previous = os.umask(0)
        self.addCleanup(os.umask, previous)

    def modes(self) -> dict[str, int]:
        saves = self.project / "skillset-saves"
        # `_write.lock` is the empty mutex file and holds no record.
        return {path.relative_to(saves).as_posix(): stat.S_IMODE(path.stat().st_mode)
                for path in saves.rglob("*") if path.is_file() and path.name != "_write.lock"}

    def test_every_record_the_writer_creates_is_owner_only_whatever_the_umask(self):
        self.create()
        self.assertEqual(self.save("checkpoint", "--evidence", "b.md")[0], 0)
        self.assertEqual(self.save("heartbeat")[0], 0)
        self.assertEqual(self.save("release")[0], 0)
        self.assertEqual(self.save("checkpoint")[0], 0)
        self.assertEqual(self.save("complete")[0], 0)
        modes = self.modes()
        for name in ("_latest.md", "runs/run-1/_state.md", "runs/run-1/_lock.md", "runs/run-1/_audit-trail.md",
                     "runs/run-1/_history/rev-1.state.json"):
            self.assertIn(name, modes)
        self.assertEqual({name: oct(mode) for name, mode in modes.items() if mode != 0o600}, {}, modes)

    def test_the_heartbeat_a_hook_makes_keeps_the_lock_record_owner_only(self):
        self.create()
        os.chmod(self.run_dir / "_lock.md", 0o644)
        self.assertEqual(self.save("heartbeat")[0], 0)
        self.assertEqual(stat.S_IMODE((self.run_dir / "_lock.md").stat().st_mode), 0o600)

    def test_an_audit_trail_an_earlier_writer_created_is_narrowed_at_the_next_event(self):
        self.create()
        os.chmod(self.run_dir / "_audit-trail.md", 0o644)
        self.assertEqual(self.save("checkpoint")[0], 0)
        self.assertEqual(stat.S_IMODE((self.run_dir / "_audit-trail.md").stat().st_mode), 0o600)

    def test_directories_keep_the_default_mode(self):
        self.create()
        self.assertEqual(stat.S_IMODE((self.project / "skillset-saves").stat().st_mode), 0o777)

    def test_the_umask_is_restored_after_every_write(self):
        self.create()
        self.assertEqual(os.umask(0), 0)


class TrailVocabularyTests(RunStateCase):
    """save-protocol.md says which events the trail holds. Every one of them has to be producible and nothing else may appear."""

    def documented(self) -> set[str]:
        text = (HOOK_DIR.parents[1] / "save-protocol.md").read_text(encoding="utf-8")
        sentence = re.search(r"The trail holds \w+ events and no others:(.*?)\.\s", text, re.S).group(1)
        return set(re.findall(r"`([a-z][a-z-]*)`", sentence.split(" with its ")[0]))

    def test_the_writer_emits_exactly_the_documented_events(self):
        self.create("README.md", "notes.md")
        self.assertEqual(self.save("checkpoint", "--expect-revision", "9")[0], 1)                  # refused
        self.assertEqual(self.save("release")[0], 0)                                                 # released
        self.assertEqual(self.save("checkpoint")[0], 0)                                              # resume
        self.assertEqual(self.save("block")[0], 0)                                                   # blocked
        self.assertEqual(self.save("checkpoint", "--reopen")[0], 0)                                  # reopen
        self.assertEqual(self.save("complete")[0], 0)                                                # complete
        self.assertEqual(self.save("checkpoint", "--reopen")[0], 0)
        self.age_records(45)
        self.assertEqual(self.save("recover", "--reason", "stale")[0], 0)                            # recover
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().checkpoint("admiral", None, [], "active", None, {})
        self.assertEqual(self.save("recover", "--rollback")[0], 0)                                   # rollback
        state = self.state()
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().checkpoint("admiral", None, [], "active", None, {})
        state["revision"] += 1
        (self.run_dir / "_state.md").write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(self.save("recover", "--rollback")[0], 0)                                   # rollforward
        pointer = self.project / "skillset-saves" / "_latest.md"
        pointer.unlink()
        pointer.mkdir()
        self.assertEqual(self.save("checkpoint")[0], 2)                                              # pointer-degraded, degraded
        seen = {event["event"] for event in self.events()}
        self.assertEqual(seen, self.documented())


if __name__ == "__main__":
    unittest.main()
