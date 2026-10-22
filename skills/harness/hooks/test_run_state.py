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
import functools
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _saves
import _state
import _testkit as kit
import run_heartbeat
import save_run

HOOK_DIR = Path(__file__).resolve().parent
SAVE_RUN = HOOK_DIR / "save_run.py"

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


# What `mode_bound` runs: a file with no permission bits that the process must be refused.
BOUND_PROBE = """
import pathlib, sys, tempfile
with tempfile.TemporaryDirectory() as tmp:
    probe = pathlib.Path(tmp, "probe")
    probe.write_text("x")
    probe.chmod(0)
    try:
        probe.read_text()
    except PermissionError:
        sys.exit(0)
    sys.exit(1)
"""


@functools.cache
def mode_bound() -> list[str] | None:
    """The command prefix under which a process is bound by file modes, so a directory it may not search is really refused.

    Empty where this process already is, `setpriv` without the two capabilities that let root past the modes where that
    works, and None where neither does (root without `setpriv`, an administrator on Windows)."""
    if kit.modes_are_enforced():
        return []
    setpriv = shutil.which("setpriv")
    if setpriv:
        prefix = [setpriv, "--bounding-set=-dac_override,-dac_read_search"]
        if subprocess.run([*prefix, sys.executable, "-c", BOUND_PROBE], capture_output=True, check=False).returncode == 0:
            return prefix
    return None


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
        return kit.save(self.project, run_id, *args)

    def in_process(self, *args: str, run_id: str = "run-1") -> tuple[int, dict]:
        """The writer's own entry point, run here so a read this module refuses is refused for it."""
        argv = ["save_run.py", *args, "--project-root", str(self.project), f"--run-id={run_id}"]
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out):
            code = save_run.main()
        return code, json.loads(out.getvalue())

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
        proc = kit.run_hook("pre_tool_use.py", {"session_id": "host-1", "tool_name": "Bash", "tool_input": {"command": "ls"}}, self.project)
        elapsed = time.monotonic() - started
        while_held = self.lock()
        go.write_text("1", encoding="utf-8")
        driver.communicate(timeout=30)
        self.assertEqual((proc.returncode, proc.stdout), (0, b""), proc.stderr)
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

    def test_a_refresh_by_an_account_that_cannot_search_the_saves_is_not_a_fault(self):
        """R3e hand-off: the blanket handler counted a hook fault on every call for a second account."""
        self.create()
        self.age_records(12)

        def refused(path, *args, **kwargs):
            raise PermissionError(13, "Permission denied", str(path))

        with mock.patch.object(Path, "is_dir", refused):
            self.assertIsNone(self.refresh())
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

    def test_unsafe_evidence_paths_are_refused(self):
        code, out = self.save("create", "--evidence", "../outside.md")
        self.assertEqual(code, 1, out)
        self.assertIn("traversal", out["reason"])
        self.assertFalse((self.run_dir / "_state.md").exists())

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

    def writer(self, index: int) -> Callable[..., tuple[int, dict]]:
        """The first id of a list goes through a real command line, where a space has to survive the quoting; the others run
        in this process, through the same argument parsing, so each operation starts one interpreter, not one per id."""
        return self.save if index == 0 else self.in_process

    def legacy(self, run_id: str) -> Path:
        """What the previous writer left: create no longer takes the id, so build the run under a valid one and rename it."""
        code, out = self.in_process("create", "--evidence", "README.md")
        self.assertEqual(code, 0, out)
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
        for index, run_id in enumerate(self.LOOSE_IDS):
            with self.subTest(run_id=run_id):
                code, out = self.writer(index)("create", "--evidence", "README.md", run_id=run_id)
                self.assertEqual((code, out["result"]), (1, "refused"), out)
                self.assertIn("letters, digits", out["reason"])
        self.assertFalse((self.project / "skillset-saves" / "runs").exists())

    def test_every_operation_still_reaches_a_run_created_under_a_looser_id(self):
        for index, run_id in enumerate(self.LOOSE_IDS):
            save = self.writer(index)
            with self.subTest(run_id=run_id), tempfile.TemporaryDirectory() as tmp:
                self.project = Path(tmp).resolve()
                for name in ("README.md", "b.md"):
                    (self.project / name).write_text("x\n", encoding="utf-8")
                self.run_dir = self.project / "skillset-saves" / "runs" / "run-1"
                self.legacy(run_id)
                self.assertEqual(save("status", run_id=run_id)[1]["requested_run"]["state"], "active")
                self.assertEqual(save("heartbeat", run_id=run_id)[0], 0)
                self.assertEqual(save("checkpoint", "--evidence", "b.md", run_id=run_id)[0], 0)
                self.assertEqual(save("release", run_id=run_id)[0], 0)
                self.assertEqual(save("checkpoint", run_id=run_id)[0], 0, "a released run resumes")
                self.age_records(45)
                code, out = save("recover", "--reason", "stale after a crash", run_id=run_id)
                self.assertEqual((code, out["operation"]), (0, "recover"), out)
                self.assertEqual(save("complete", run_id=run_id)[0], 0)
                self.assertEqual(save("status", run_id=run_id)[1]["status"], "complete")
                self.assertEqual(save("checkpoint", "--reopen", run_id=run_id)[0], 0)
                self.assertEqual(save("block", run_id=run_id)[0], 0)

    def test_the_hook_refresh_keeps_a_run_under_a_looser_id_alive_and_counts_no_fault(self):
        self.legacy("my run")
        self.age_records(12)
        with mock.patch.dict(os.environ, {"SUPREMETEAM_PROJECT_DIR": str(self.project)}):
            result = run_heartbeat.refresh({"session_id": "host-1"}, "PreToolUse")
        self.assertEqual(result["source"], "hook:PreToolUse", result)
        self.assertEqual(_state.load_observations(self.project).get("PreToolUse", {}).get("faults", 0), 0)

    def test_an_id_that_is_not_one_path_segment_is_still_refused_by_every_operation(self):
        for index, run_id in enumerate(("..", "a/b", "a\\b", "c:x", "q?")):
            for operation in ("status", "checkpoint", "recover"):
                with self.subTest(run_id=run_id, operation=operation):
                    code, out = self.writer(index)(operation, "--reason", "x", run_id=run_id)
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


class RunTransitionTests(RunStateCase):
    """The lifecycle from create to complete, reopen and resume, a second release, a competing pin and a wrong owner,
    refusals beside an interrupted journal or a stale run, and the heartbeat's source."""

    def test_create_checkpoint_heartbeat_complete_lifecycle(self):
        code, out = self.save("create", "--evidence", "README.md")
        self.assertEqual((code, out["revision"]), (0, 1), out)
        state = self.state()
        self.assertEqual((state["status"], state["session_pin"]), ("active", True))
        self.assertIn("README.md", state["artifact_hashes"])
        pointer = json.loads((self.project / "skillset-saves" / "_latest.md").read_text(encoding="utf-8"))
        self.assertEqual(pointer["run_id"], "run-1")
        self.assertEqual(self.save("status")[1]["status"], "active")
        code, out = self.save("checkpoint", "--expect-revision", "1", "--evidence", "notes.md", "--next-action", "design-to-build")
        self.assertEqual((code, out["revision"]), (0, 2), out)
        self.assertTrue((self.run_dir / "_history" / "rev-1.state.json").exists())
        code, out = self.save("checkpoint", "--expect-revision", "1")
        self.assertEqual(code, 1, out)
        self.assertIn("revision conflict", out["reason"])
        self.assertEqual(self.save("heartbeat")[0], 0)
        self.assertEqual(self.save("complete")[0], 0)
        code, out = self.save("status")
        self.assertEqual((out["status"], out["run_status"]), ("complete", "complete"), out)
        self.assertEqual((self.lock()["status"], self.lock()["session_pin"]), ("released", False))
        # The refused stale-revision checkpoint is on the trail between the two it bracketed.
        self.assertEqual([e["event"] for e in self.events()], ["create", "checkpoint", "refused", "complete"])

    def test_create_rejects_parent_revision_override_before_writing(self):
        code, out = self.save("create", "--evidence", "README.md", "--set", "parent_revision=99")
        self.assertEqual(code, 1, out)
        self.assertIn("reserved field", out["reason"])
        self.assertFalse((self.project / "skillset-saves/runs/run-1/_state.md").exists())

    def test_checkpoint_on_completed_run_needs_reopen(self):
        self.save("create", "--evidence", "README.md")
        self.save("complete")
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("--reopen", out["reason"])
        code, out = self.save("checkpoint", "--reopen", "--next-action", "REVISE")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["operation"], "reopen")
        code, out = self.save("status")
        self.assertEqual(out["status"], "active", out)
        audit = [json.loads(line) for line in (self.project / "skillset-saves/runs/run-1/_audit-trail.md").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(audit[-1]["event"], "reopen")
        self.assertEqual(audit[-1]["from_status"], "complete")

    def test_released_run_resumes_by_checkpoint_unless_another_run_holds_the_pin(self):
        self.save("create", "--evidence", "README.md")
        code, out = self.save("release")
        self.assertEqual(code, 0, out)
        code, out = self.save("release")
        self.assertEqual(code, 1)
        self.assertIn("already released", out["reason"])
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 0, out)
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("another run holds the session pin", out["reason"])
        self.save("complete", run_id="run-2")
        code, out = self.save("checkpoint")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["operation"], "resume")

    def test_competing_owner_and_wrong_owner_are_refused(self):
        self.create()
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 1, out)
        self.assertIn("another run holds the session pin", out["reason"])
        code, out = self.save("checkpoint", "--owner", "intruder")
        self.assertEqual(code, 1, out)
        self.assertIn("owned by", out["reason"])
        code, out = self.save("recover", "--owner", "intruder", "--reason", "impatient")
        self.assertEqual(code, 1, out)
        self.assertIn("fresh and held by another owner", out["reason"])

    def test_interrupted_journal_blocks_checkpoint_heartbeat_finish_and_plain_recover(self):
        self.save("create", "--evidence", "README.md")
        run_dir = self.project / "skillset-saves/runs/run-1"
        (run_dir / "_journal.json").write_text(json.dumps({"revision": 2, "step": "begin"}), encoding="utf-8")
        for op in (("checkpoint",), ("heartbeat",), ("complete",), ("release",), ("recover", "--reason", "just because")):
            with self.subTest(op=op[0]):
                code, out = self.save(*op)
                self.assertEqual(code, 1, out)
                self.assertIn("rollback", out["reason"])
        self.assertTrue((run_dir / "_journal.json").exists(), "a refused operation must not consume the journal")

    def test_recover_refuses_a_fresh_lock_of_the_same_owner(self):
        self.save("create", "--evidence", "README.md")
        code, out = self.save("recover", "--reason", "impatient")
        self.assertEqual(code, 1, out)
        self.assertIn("held by this owner", out["reason"])
        lock = self.lock()
        self.assertEqual(lock["revision"], 1)

    def test_create_refuses_beside_a_stale_held_run(self):
        self.save("create", "--evidence", "README.md")
        self.age_records(45)
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 1, out)
        self.assertIn("stale", out["reason"])
        self.assertFalse((self.project / "skillset-saves/runs/run-2").exists())
        code, out = self.save("heartbeat")
        self.assertEqual(code, 1, out)
        self.assertIn("recover --reason", out["reason"])
        code, out = self.save("checkpoint")
        self.assertEqual(code, 1, out)
        self.assertIn("stale", out["reason"])
        code, out = self.save("recover", "--reason", "heartbeat older than 30 minutes")
        self.assertEqual(code, 0, out)
        code, out = self.save("complete")
        self.assertEqual(code, 0, out)
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 0, out)

    def test_heartbeat_records_its_source(self):
        self.save("create", "--evidence", "README.md")
        code, out = self.save("heartbeat")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["source"], "cli")
        self.assertEqual(self.lock()["heartbeat_source"], "cli")


class RecordedFieldTests(RunStateCase):
    """What a mutation takes and keeps: a run id it is never without, the skills the run engaged as a typed list that only
    grows, and the protocol state the recorded phase maps to."""

    def test_mutations_still_require_a_run_id(self):
        proc = kit.run_cli(SAVE_RUN, "create", "--project-root", str(self.project), env=kit.clean_env(self.project))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--run-id is required", proc.stderr)
        self.assertFalse((self.project / "skillset-saves").exists())

    def test_engaged_skills_are_a_typed_append_once_list(self):
        extra = save_run.parse_extra(['skills_engaged=["session-memory", "commander", "commander"]'])
        self.store().create("admiral", ["README.md"], "skill", "next", extra)
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "commander"])
        self.store().checkpoint("admiral", 1, [], "active", "next",
                                save_run.parse_extra(['skills_engaged=["taste", "commander"]']))
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "commander", "taste"])

    def test_terminal_writes_preserve_engagement_history(self):
        self.store().create("admiral", ["README.md"], "skill", "next",
                            save_run.parse_extra(['skills_engaged=["session-memory"]']))
        self.store().finish("admiral", "blocked", "missing evidence",
                            save_run.parse_extra(['skills_engaged=["taste"]']))
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "taste"])

    def test_legacy_json_string_is_migrated_without_losing_skills(self):
        self.store().create("admiral", ["README.md"], "skill", "next",
                            {"skills_engaged": '["session-memory"]'})
        self.store().checkpoint("admiral", 1, [], "active", "next",
                                save_run.parse_extra(['skills_engaged=["taste"]']))
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "taste"])

    def test_invalid_engaged_skills_are_refused_before_persistence(self):
        for value in ('"taste"', '{}', '[null]', '[1]', '[""]', 'not-json'):
            with self.subTest(value=value), self.assertRaises(save_run.Refused):
                save_run.parse_extra(["skills_engaged=" + value])

    def test_phase_labels_map_to_declared_protocol_states(self):
        from save_taxonomy import protocol_state_for

        expected = {"INTAKE": "INTAKE", "DESIGN": "DESIGN", "REDESIGN": "DESIGN", "BUILD": "BUILD",
                    "INVESTIGATION": "BUILD", "SKILL_CREATION": "BUILD", "CREATE": "BUILD", "IMPROVE": "BUILD",
                    "OPTIMIZE": "BUILD", "PACKAGE": "BUILD", "REVIEW": "REVIEW", "SECURITY": "REVIEW", "QA": "REVIEW",
                    "DELIVERY": "GATE", "RELEASE": "GATE"}
        for prefix, active in expected.items():
            for suffix, protocol in (("_ACTIVE", active), ("_GATE_PENDING", "GATE"), ("_GATE_REVISE", "REVISE")):
                with self.subTest(prefix=prefix, suffix=suffix):
                    self.assertEqual(protocol_state_for(prefix + suffix), protocol)
        for phase in ("TASTE_ACTIVE", "TASTE_GATE_PENDING", "TASTE_GATE_REVISE"):
            self.assertEqual(protocol_state_for(phase), phase)
        self.assertEqual(protocol_state_for("RUN_COMPLETE"), "COMPLETE")
        self.assertEqual(protocol_state_for("DISPUTED_AWAITING_USER"), "ESCALATE")
        with self.assertRaises(save_run.Refused):
            save_run.parse_extra(["phase_state=UNKNOWN_ACTIVE"])
        with self.assertRaises(save_run.Refused):
            save_run.parse_extra(["protocol_state=RELEASE"])

    def test_writer_persists_mapping_and_terminal_state(self):
        self.store().create("admiral", ["README.md"], "skill", "next",
                            save_run.parse_extra(["phase_state=DESIGN_ACTIVE"]))
        self.assertEqual(self.state()["protocol_state"], "DESIGN")
        self.store().checkpoint("admiral", 1, [], "active", "next",
                                save_run.parse_extra(["phase_state=PACKAGE_GATE_PENDING"]))
        self.assertEqual(self.state()["protocol_state"], "GATE")
        self.store().finish("admiral", "blocked", "missing evidence", {})
        self.assertEqual(self.state()["protocol_state"], "BLOCKED")


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

    def test_stale_lock_recovery_records_evidence(self):
        self.create()
        self.age_records(45)
        heartbeat = self.lock()["heartbeat"]
        code, out = self.save("recover", "--owner", "resumer")
        self.assertEqual(code, 1, out)
        self.assertIn("--reason", out["reason"])
        code, out = self.save("recover", "--owner", "resumer", "--reason", "heartbeat older than 30 minutes")
        self.assertEqual(code, 0, out)
        self.assertEqual(out["evidence"]["prior_heartbeat"], heartbeat)
        self.assertEqual((self.events()[-1]["event"], self.events()[-1]["prior_owner"]), ("recover", "admiral"))

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

    def test_pointer_only_interruption_rolls_forward(self):
        """Revision 2 was published in full; only the pointer and the journal's last step were lost."""
        self.create()
        self.assertEqual(self.save("checkpoint")[0], 0)
        (self.run_dir / "_journal.json").write_text(json.dumps({"revision": 2, "step": "begin"}), encoding="utf-8")
        pointer = self.project / "skillset-saves" / "_latest.md"
        pointer.write_text(json.dumps({"schema_version": 1, "run_id": "run-1", "revision": 1, "updated_at": "2026-09-05T00:00:00+00:00"}),
                           encoding="utf-8")
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"], out["revision"]), (0, "rollforward", 2), out)
        self.assertEqual(json.loads(pointer.read_text(encoding="utf-8"))["revision"], 2)
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

    def test_a_retired_first_revision_whose_event_fails_says_where_its_records_went(self):
        """Revision 0 publishes nothing: the rollback of a create that died mid-publish moves what it wrote into _history/,
        and if the event then fails, that is what the reason says was done."""
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().create("admiral", ["README.md"], "agent", "next", {})
        real = save_run.RunStore.append_audit

        def failing(store, event, payload):
            if event == "rollback":
                raise save_run.Degraded("audit append failed: No space left on device")
            return real(store, event, payload)

        with mock.patch.object(save_run.RunStore, "append_audit", failing):
            code, out = self.in_process("recover", "--rollback")
        self.assertEqual((code, out["result"]), (2, "degraded"), out)
        self.assertIn("any lock or state the unpublished first revision wrote is in _history/ but the rollback audit event "
                      "was not recorded (audit append failed: No space left on device)", out["reason"])
        self.assertFalse((self.run_dir / "_lock.md").exists(), "the lock was retired before the event failed")
        self.assertEqual(self.save("status")[1]["status"], "interrupted")
        code, out = self.save("recover", "--rollback")
        self.assertEqual((code, out["operation"], out["revision"]), (0, "rollback", 0), out)
        self.assertEqual([e["event"] for e in self.events()], ["degraded", "rollback"])


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

    def checkpoint_through_a_link(self, target: Path) -> None:
        """Put a link to ``target`` where the trail belongs and checkpoint: the revision is published, its event is not,
        and the reason says what stands where the trail belongs."""
        self.create()
        trail = self.run_dir / "_audit-trail.md"
        trail.unlink()
        os.symlink(target, trail)
        code, out = self.save("checkpoint")
        self.assertEqual((code, out["result"]), (2, "degraded"), out)
        self.assertIn("(audit append failed: skillset-saves/runs/run-1/_audit-trail.md is a link, not a file)", out["reason"])
        self.assertTrue(os.path.islink(trail), "the link is left where it stands")
        self.assertEqual(self.save("status")[1]["status"], "interrupted", "the journal stays, so the gap is visible")

    @unittest.skipUnless(kit.can_link(), kit.NO_LINKS)
    def test_an_append_through_a_link_to_a_file_elsewhere_is_refused_and_leaves_that_file_alone(self):
        """The append followed the link: the event went into the file it led to, whose mode was then narrowed."""
        theirs = self.scratch / "theirs.md"
        theirs.write_text("theirs\n", encoding="utf-8")
        mode = stat.S_IMODE(theirs.stat().st_mode)
        self.checkpoint_through_a_link(theirs)
        self.assertEqual(theirs.read_text(encoding="utf-8"), "theirs\n")
        self.assertEqual(stat.S_IMODE(theirs.stat().st_mode), mode)

    @unittest.skipUnless(kit.can_link(), kit.NO_LINKS)
    def test_an_append_through_a_dangling_link_creates_nothing_where_it_leads(self):
        """The append created the file the link named, wherever that was."""
        elsewhere = self.scratch / "made-by-the-writer.md"
        self.checkpoint_through_a_link(elsewhere)
        self.assertFalse(os.path.lexists(elsewhere))


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
        """The writer runs here, as a hook runs it: a umask left narrowed would make this process's next file owner-only
        too. Run as a child process, as ``create`` is, the parent's umask could never show it."""
        for args in (("create", "--evidence", "README.md"), ("checkpoint",), ("heartbeat",)):
            with self.subTest(operation=args[0]):
                code, out = self.in_process(*args)
                self.assertEqual(code, 0, out)
                self.assertEqual(os.umask(0), 0)


class SecondAccountTests(RunStateCase):
    """RR3-state-1: records are owner-only on POSIX since SEC-19, so a second account sharing the project directory read the
    first one's run as no run: its `create` passed the one-held-run check, and the hook-file gate went quiet for it.

    The refused read is simulated where it happens, so these run for every account; the cases below the line use a
    real file with no permission bits and run wherever the file modes bind the process."""

    OWNER_ONLY = ("run-1/_state.md", "run-1/_lock.md", "/_latest.md")

    def test_create_refuses_beside_a_record_it_cannot_read_and_names_it(self):
        self.create()
        before = (self.project / "skillset-saves" / "_latest.md").read_bytes()
        with kit.refusing(*self.OWNER_ONLY):
            code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 1, out)
        self.assertIn("skillset-saves/_latest.md exists but this account cannot read it (permission denied)", out["reason"])
        self.assertNotIn("missing", out["reason"])
        self.assertFalse((self.project / "skillset-saves" / "runs" / "run-2").exists(), "a refused create leaves no directory")
        self.assertEqual((self.project / "skillset-saves" / "_latest.md").read_bytes(), before, "the pointer is not overwritten")

    def test_the_refusal_names_the_record_whichever_one_it_is(self):
        for tail, path in (("run-1/_lock.md", "runs/run-1/_lock.md"), ("run-1/_state.md", "runs/run-1/_state.md")):
            with self.subTest(tail):
                self.create()
                with kit.refusing(tail), self.assertRaises(save_run.Refused) as caught:
                    self.store("run-2").create("admiral", ["README.md"], "agent", "next", {})
                self.assertIn(f"skillset-saves/{path} exists but this account cannot read it", str(caught.exception))
                self.assertIn(_saves.ACCESS_DENIED_STEP, str(caught.exception))
                self.setUp()

    def test_a_refused_state_beside_a_readable_released_lock_is_a_closed_run_and_create_goes_ahead(self):
        """RR3-state-9: the lock decides. The key is not carried, the guard does not count the run as held, and the writer
        is not refused, which is what the documents say of this one arrangement."""
        self.create()
        self.assertEqual(self.save("release")[0], 0)
        with kit.refusing("run-1/_state.md"):
            status = self.store().status()
            held = _saves.has_active_run(self.project)
            code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(status["status"], "corrupt", status)
        self.assertNotIn("access_denied", status)
        self.assertEqual(status["next_step"], _saves.NEXT_STEPS["corrupt"])
        self.assertFalse(held)
        self.assertEqual((code, out["result"]), (0, "ok"), out)

    def test_closing_the_run_does_not_lift_the_refusal_because_its_records_stay_unreadable(self):
        """RR3-state-7: the step used to name the owner completing or releasing the run as the way forward, and the second
        account met the same refusal afterwards: on POSIX a closed run's records are as owner-only as a held one's."""
        for close in ("complete", "release"):
            with self.subTest(close):
                self.create()
                self.assertEqual(self.save(close)[0], 0)
                with kit.refusing(*self.OWNER_ONLY):
                    code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
                self.assertEqual(code, 1, out)
                self.assertIn("this account cannot read it (permission denied)", out["reason"])
                self.assertIn("completing or releasing the run only ends its claim", out["reason"])
                self.assertFalse((self.project / "skillset-saves" / "runs" / "run-2").exists())
                self.setUp()

    def test_resuming_or_recovering_beside_a_record_it_cannot_read_is_refused_too(self):
        self.create()
        self.assertEqual(self.save("release")[0], 0)
        self.save("create", "--evidence", "README.md", run_id="run-2")
        with kit.refusing("run-2/_lock.md"), self.assertRaises(save_run.Refused) as caught:
            self.store().checkpoint("admiral", None, [], "active", None, {})
        self.assertIn("run-2/_lock.md exists but this account cannot read it", str(caught.exception))

    def test_every_operation_on_a_run_it_cannot_read_says_so_instead_of_saying_there_is_no_lock(self):
        self.create()
        for operation, extra in (("checkpoint", ()), ("heartbeat", ()), ("complete", ()), ("release", ()), ("block", ()),
                                 ("recover", ("--reason", "why"))):
            with self.subTest(operation), kit.refusing("run-1/_state.md", "run-1/_lock.md"):
                code, out = self.in_process(operation, *extra)
                self.assertEqual(code, 1, out)
                self.assertIn("exists but this account cannot read it (permission denied)", out["reason"])
                self.assertNotIn("no lock", out["reason"])

    def test_a_directory_the_account_may_not_search_refuses_every_operation_in_the_words_the_readers_use(self):
        """RR3-state-6: the probes of the writer were `Path.exists`, which raised out of `create` and `status` as an engine
        error and out of the refusal handler of every other operation, and which answers no where pathlib is built on
        `os.path`. The reads of the records are left alone here, so what is refused is the way to the run."""
        self.create()
        pointer = (self.project / "skillset-saves" / "_latest.md").read_bytes()
        operations = (("create", "--evidence", "README.md"), ("checkpoint",), ("heartbeat",), ("complete",), ("release",),
                      ("block",), ("recover", "--reason", "why"))
        for operation, *extra in operations:
            with self.subTest(operation), kit.unsearchable("skillset-saves/runs"):
                code, out = self.in_process(operation, *extra, run_id="run-2" if operation == "create" else "run-1")
                self.assertEqual((code, out["result"]), (1, "refused"), out)
                self.assertIn("skillset-saves/runs/run-1 exists but this account cannot read it (permission denied)", out["reason"])
                self.assertIn(_saves.ACCESS_DENIED_STEP, out["reason"])
        self.assertFalse((self.project / "skillset-saves" / "runs" / "run-2").exists(), "a refused create leaves no directory")
        self.assertEqual((self.project / "skillset-saves" / "_latest.md").read_bytes(), pointer, "the pointer is not overwritten")

    def test_evidence_under_a_directory_the_account_may_not_search_is_refused_naming_the_path(self):
        """The same probe sat in the evidence hashing: an engine error with an absolute path, or `evidence path missing`."""
        evidence = self.project / "docs" / "private" / "spec.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("x\n", encoding="utf-8")
        with kit.unsearchable("docs/private"):
            code, out = self.in_process("create", "--evidence", "docs/private/spec.md")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertEqual(out["reason"], "evidence path cannot be read by this account (permission denied): docs/private/spec.md")
        self.assertFalse(self.run_dir.exists())

    def test_status_reports_evidence_it_cannot_check_beside_the_run_s_own_classification(self):
        evidence = self.project / "docs" / "private" / "spec.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("x\n", encoding="utf-8")
        self.create("docs/private/spec.md")
        with kit.unsearchable("docs/private"):
            result = self.store().status()
            held = _saves.has_active_run(self.project)
        self.assertEqual((result["status"], result["evidence_unverifiable"]), ("active", ["docs/private/spec.md"]), result)
        self.assertNotIn("access_denied", result)
        self.assertEqual(result["requested_run"]["state"], "active", result)
        self.assertTrue(held)

    def test_status_classifies_a_directory_it_may_not_search_instead_of_raising(self):
        self.create()
        with kit.unsearchable("skillset-saves/runs"):
            result = self.store("run-2").status()
        self.assertEqual((result["status"], result["access_denied"], result["interrupted"]),
                         ("corrupt", ["skillset-saves/runs/run-1"], False), result)
        self.assertEqual(result["requested_run"]["state"], "corrupt")
        self.assertEqual(result["next_step"], _saves.ACCESS_DENIED_STEP)

    def test_a_directory_where_a_record_belongs_is_not_called_a_permission_problem(self):
        """Windows raises PermissionError for the read of a directory; the writer says what is there, as the readers do,
        where it used to say the run had no lock."""
        self.create()
        lock = self.run_dir / "_lock.md"
        lock.unlink()
        lock.mkdir()
        with kit.refusing("run-1/_lock.md"), self.assertRaises(save_run.Refused) as caught:
            self.store().checkpoint("admiral", None, [], "active", None, {})
        self.assertEqual(str(caught.exception), "skillset-saves/runs/run-1/_lock.md is a directory, not a file: "
                                                "preserve the record and escalate; never overwrite it")

    def test_status_says_a_record_cannot_be_read_and_what_to_do(self):
        self.create()
        with kit.refusing("run-1/_lock.md"):
            result = self.store("run-1").status()
        self.assertEqual((result["status"], result["access_denied"]), ("corrupt", ["skillset-saves/runs/run-1/_lock.md"]), result)
        self.assertIn("cannot read it (permission denied)", result["detail"])
        self.assertEqual(result["next_step"], _saves.ACCESS_DENIED_STEP)
        self.assertEqual(result["requested_run"]["state"], "corrupt")
        self.assertEqual(result["requested_run"]["access_denied"], ["skillset-saves/runs/run-1/_lock.md"])

    def test_a_run_the_account_can_read_is_refused_and_resumed_as_before(self):
        """Nothing changes for the account that owns the records."""
        self.create()
        self.assertEqual(self.save("create", "--evidence", "README.md", run_id="run-2")[1]["reason"].split(" (")[0],
                         "another run holds the session pin")
        self.assertEqual(self.save("checkpoint", "--expect-revision", "1")[0], 0)
        self.assertEqual(self.save("status")[1]["status"], "active")

    def test_the_hook_file_gate_stays_engaged_for_a_run_whose_records_it_cannot_read(self):
        """Rule F asks whether a run is held; an account that cannot read the records used to hear no."""
        self.create()
        hook_script = f"{HOOK_DIR.as_posix()}/guard_hook.py"
        saved = {name: os.environ.pop(name, None) for name in ("SUPREMETEAM_HARNESS_DEV",)}
        self.addCleanup(lambda: [os.environ.__setitem__(name, value) for name, value in saved.items() if value is not None])
        self.assertTrue(kit.denied(kit.decide(kit.edit(hook_script), self.project)), "the owner is protected")
        with kit.refusing(*self.OWNER_ONLY):
            output = kit.decide(kit.edit(hook_script), self.project)
        self.assertTrue(kit.denied(output), "a second account is protected too")

    @unittest.skipUnless(kit.modes_are_enforced(), "this process bypasses file modes")
    def test_a_record_with_no_permission_bits_is_refused_for_real(self):
        self.create()
        lock, state = self.run_dir / "_lock.md", self.run_dir / "_state.md"
        self.addCleanup(lambda: [path.chmod(0o600) for path in (lock, state)])
        lock.chmod(0)
        code, out = self.save("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual(code, 1, out)
        self.assertIn("skillset-saves/runs/run-1/_lock.md exists but this account cannot read it (permission denied)", out["reason"])
        self.assertFalse((self.project / "skillset-saves" / "runs" / "run-2").exists())
        state.chmod(0)
        code, out = self.save("status")
        self.assertEqual((code, out["status"]), (0, "corrupt"), out)
        self.assertEqual(sorted(out["access_denied"]), ["skillset-saves/runs/run-1/_lock.md", "skillset-saves/runs/run-1/_state.md"])
        self.assertIn("and 1 more record exist but this account cannot read them", out["detail"])


class UnsearchableDirectoryTests(RunStateCase):
    """RR3-state-6 with a real directory: a run made under `umask 077` is a 0700 tree, which a second account may not search.

    The directory has no permission bits and the writer runs in a child bound by the file modes (see `mode_bound`), so
    this is the failure itself and not a simulation of it; it skips only where the process cannot drop its privileges."""

    HAS_ACTIVE_RUN = ("import pathlib, sys; sys.path.insert(0, sys.argv[1]); import _saves; "
                      "print(_saves.has_active_run(pathlib.Path(sys.argv[2])))")
    ARRANGEMENTS = {"runs": "skillset-saves/runs", "the run": "skillset-saves/runs/run-1", "the save root": "skillset-saves"}

    def setUp(self):
        super().setUp()
        self.bound = mode_bound()
        if self.bound is None:
            self.skipTest("this process bypasses file modes and cannot drop the privileges that do")
        self.create()
        self.before = {name: (self.project / "skillset-saves" / name).read_bytes() for name in ("_latest.md", "runs/run-1/_state.md")}

    @contextmanager
    def closed(self, relative: str):
        path = self.project / relative
        path.chmod(0)
        try:
            yield
        finally:
            path.chmod(0o755)

    def child(self, command: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run([*self.bound, *command], text=True, capture_output=True, env=kit.clean_env(self.project), check=False)

    def bound_save(self, *args: str, run_id: str = "run-1") -> tuple[int, dict]:
        proc = self.child(self.command(run_id, *args))
        text = (proc.stdout or proc.stderr).strip()
        try:
            return proc.returncode, json.loads(text[text.index("{"):])
        except ValueError:
            return proc.returncode, {"result": "no JSON result", "output": text[-300:]}

    def test_status_classifies_the_directory_where_it_used_to_die_with_an_engine_error(self):
        for label, relative in self.ARRANGEMENTS.items():
            with self.subTest(label), self.closed(relative):
                for run_id in ("run-1", "run-2"):
                    code, out = self.bound_save("status", run_id=run_id)
                    self.assertEqual((code, out.get("status")), (0, "corrupt"), out)
                    self.assertTrue(out["access_denied"], out)
                    self.assertRegex(out["detail"], r"cannot read (it|them) \(permission denied\)")
                    self.assertEqual(out["next_step"], _saves.ACCESS_DENIED_STEP)
                    if run_id == "run-1":
                        self.assertEqual(out["requested_run"]["state"], "corrupt", out)

    def test_every_operation_refuses_naming_the_directory_instead_of_raising(self):
        operations = (("create", "--evidence", "README.md"), ("checkpoint",), ("heartbeat",), ("complete",), ("release",),
                      ("block",), ("recover", "--reason", "why"))
        for label, relative in self.ARRANGEMENTS.items():
            for operation, *extra in operations:
                with self.subTest(f"{operation}, {label}"), self.closed(relative):
                    code, out = self.bound_save(operation, *extra, run_id="run-2" if operation == "create" else "run-1")
                    self.assertEqual((code, out["result"]), (1, "refused"), out)
                    self.assertRegex(out["reason"], r"cannot read (it|them) \(permission denied\)")
                    self.assertIn(_saves.ACCESS_DENIED_STEP, out["reason"])
                    self.assertNotIn(str(self.project), out["reason"], "no absolute path is reported")
        after = {name: (self.project / "skillset-saves" / name).read_bytes() for name in self.before}
        self.assertEqual(after, self.before, "nothing was written")
        self.assertFalse((self.run_dir.parent / "run-2").exists())

    def test_evidence_in_a_directory_that_cannot_be_searched_is_refused_naming_the_path(self):
        evidence = self.project / "docs" / "private" / "spec.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("x\n", encoding="utf-8")
        with self.closed("docs/private"):
            code, out = self.bound_save("checkpoint", "--evidence", "docs/private/spec.md")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertEqual(out["reason"], "evidence path cannot be read by this account (permission denied): docs/private/spec.md")

    def test_evidence_in_a_directory_that_cannot_be_searched_does_not_make_the_owners_run_corrupt(self):
        """RR3-state-10: a `chmod` of an evidence directory read, to the owner of the run, as another account's unreadable run."""
        evidence = self.project / "docs" / "private" / "spec.md"
        evidence.parent.mkdir(parents=True)
        evidence.write_text("x\n", encoding="utf-8")
        self.assertEqual(self.save("checkpoint", "--evidence", "docs/private/spec.md")[0], 0)
        with self.closed("docs/private"):
            code, out = self.bound_save("status")
            self.assertEqual((code, out.get("status")), (0, "active"), out)
            self.assertNotIn("access_denied", out)
            self.assertEqual(out["evidence_unverifiable"], ["docs/private/spec.md"], out)
            self.assertEqual(out["requested_run"]["state"], "active", out)
            held = self.child([sys.executable, "-c", self.HAS_ACTIVE_RUN, str(HOOK_DIR), str(self.project)])
            self.assertEqual(held.stdout.strip(), "True", held.stderr)
            code, out = self.bound_save("heartbeat")
            self.assertEqual((code, out["result"]), (0, "ok"), out)

    def test_the_hooks_and_readiness_see_the_run_they_cannot_reach(self):
        for label, relative in self.ARRANGEMENTS.items():
            with self.subTest(label), self.closed(relative):
                held = self.child([sys.executable, "-c", self.HAS_ACTIVE_RUN, str(HOOK_DIR), str(self.project)])
                self.assertEqual(held.stdout.strip(), "True", held.stderr)
                ready = self.child([sys.executable, str(HOOK_DIR / "check_readiness.py"), "--project-root", str(self.project), "--json"])
                saves = json.loads(ready.stdout)
                self.assertEqual(saves["saves"]["status"], "corrupt", saves)
                self.assertTrue(saves["saves"]["access_denied"] and not saves["capabilities"]["saves_readable"], saves)


class DamagedPointerCase(RunStateCase):
    """run-1 beside a pointer each defect leaves, made on disk as a failure leaves it, and the held runs beside it."""

    DEFECTS = ("malformed", "unsafe id", "missing target", "incoherent target", "revision mismatch", "directory at the pointer")
    FRESH = "run run-1 holds a fresh lock: complete, block, or release it"
    STALE = ("run run-1 holds a stale lock: complete, block, or release it as its owner, or reclaim it with recover --run-id "
             "run-1 --reason <why> once it is the only held run")

    def setUp(self):
        super().setUp()
        self.pointer = self.project / "skillset-saves" / "_latest.md"

    def start(self) -> None:
        self.assertEqual(self.in_process("create", "--evidence", "README.md")[0], 0)

    def damage(self, defect: str) -> None:
        """Leave the pointer as ``defect`` leaves it, beside run-1."""
        if defect == "directory at the pointer":
            self.pointer.unlink()
            self.pointer.mkdir()
            return
        if defect == "incoherent target":
            (self.run_dir.parent / "broken").mkdir()
            (self.run_dir.parent / "broken" / "_state.md").write_text("{", encoding="utf-8")
        names = {"schema_version": 1, "run_id": "run-1", "revision": 1, "updated_at": datetime.now(timezone.utc).isoformat()}
        self.pointer.write_text({
            "malformed": "{",
            "unsafe id": json.dumps({**names, "run_id": "../run-1"}),
            "missing target": json.dumps({**names, "run_id": "ghost"}),
            "incoherent target": json.dumps({**names, "run_id": "broken"}),
            "revision mismatch": json.dumps({**names, "revision": 5}),
        }[defect], encoding="utf-8")

    def interrupt(self) -> None:
        """A checkpoint that died after it wrote the lock and before the state: a held run mid-publish, whose lock and
        state are at different revisions."""
        with crash_when_writing("_state.md"), self.assertRaises(save_run.Degraded):
            self.store().checkpoint("admiral", 1, [], "active", None, {})

    def second_held_run(self) -> None:
        """A second held run, which the writer no longer makes: run-1's records under another id."""
        other = self.run_dir.parent / "run-2"
        other.mkdir()
        for name in ("_state.md", "_lock.md"):
            record = json.loads((self.run_dir / name).read_text(encoding="utf-8"))
            (other / name).write_text(json.dumps({**record, "run_id": "run-2"}), encoding="utf-8")

    def pointer_bytes(self) -> bytes | None:
        return self.pointer.read_bytes() if self.pointer.is_file() else None


class DamagedPointerTests(DamagedPointerCase):
    """A damaged pointer was decided first and ended the reading, so no run behind it was looked at. The save root read
    `corrupt`, which the writer let through: a second `create` took the session pin beside a live run, and the hook-file
    gate and the pin reminder went quiet for it. A record this account could not read was dropped from that answer too.
    Each defect is made on disk as a failure leaves it; the classification itself does not move."""

    def test_create_is_refused_beside_a_held_run_whatever_the_pointer_says(self):
        variants = {
            "fresh": (lambda: None, self.FRESH, True),
            "stale": (lambda: self.age_records(45), self.STALE, False),
            "interrupted": (self.interrupt, "run run-1 has an interrupted publish: settle it with recover --run-id run-1 "
                                            "--rollback", True),
            "interrupted, stale": (lambda: (self.interrupt(), self.age_records(45)), "run run-1 has an interrupted publish: "
                                   "settle it with recover --run-id run-1 --rollback", False),
        }
        for variant, (make, way_out, counted) in variants.items():
            for defect in self.DEFECTS:
                with self.subTest(variant=variant, defect=defect):
                    self.setUp()
                    self.start()
                    make()
                    self.damage(defect)
                    before = self.pointer_bytes()
                    self.assertEqual(_saves.inspect_saves(self.project)["status"], "corrupt")
                    code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
                    self.assertEqual((code, out["result"]), (1, "refused"), out)
                    self.assertEqual(out["reason"], f"another run holds the session pin ({way_out})")
                    self.assertFalse((self.run_dir.parent / "run-2").exists(), "a refused create leaves no directory")
                    self.assertEqual(self.pointer_bytes(), before, "the pointer is not written")
                    # A fresh lock counts as a live run for the hooks, mid-publish too; a stale one does not.
                    self.assertEqual(_saves.has_active_run(self.project), counted)

    def test_a_released_run_is_not_resumed_beside_a_held_run_the_pointer_does_not_show(self):
        self.start()
        self.assertEqual(self.in_process("release")[0], 0)
        self.assertEqual(self.in_process("create", "--evidence", "README.md", run_id="run-2")[0], 0)
        self.pointer.write_text("{", encoding="utf-8")
        code, out = self.in_process("checkpoint")
        self.assertEqual((code, out["result"]), (1, "refused"), out)
        self.assertEqual(out["reason"], "cannot resume a released run while another run holds the session pin (run run-2 "
                                        "holds a fresh lock: complete, block, or release it)")
        self.assertEqual(self.lock()["status"], "released")

    def test_a_record_this_account_cannot_read_beside_a_damaged_pointer_refuses_create(self):
        refusals = {
            "the lock of the held run": (lambda: kit.refusing("run-1/_lock.md"), "skillset-saves/runs/run-1/_lock.md"),
            "the state of the held run": (lambda: kit.refusing("run-1/_state.md"), "skillset-saves/runs/run-1/_state.md"),
            "the listing of runs": (lambda: mock.patch.object(Path, "iterdir", side_effect=PermissionError(
                errno.EACCES, "Permission denied", str(self.run_dir.parent))), "skillset-saves/runs"),
        }
        for label, (refused, path) in refusals.items():
            for defect in self.DEFECTS:
                with self.subTest(refused=label, defect=defect):
                    self.setUp()
                    self.start()
                    self.damage(defect)
                    with refused():
                        held = _saves.has_active_run(self.project)
                        code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
                    self.assertTrue(held)
                    self.assertEqual((code, out["result"]), (1, "refused"), out)
                    self.assertEqual(out["reason"], f"{path} exists but this account cannot read it (permission denied); "
                                                    f"{_saves.PIN_MAY_BE_HELD}: {_saves.ACCESS_DENIED_STEP}")
                    self.assertFalse((self.run_dir.parent / "run-2").exists())

    def test_the_hook_file_gate_and_the_pin_reminder_stay_on_beside_a_damaged_pointer_and_for_conflicting_runs(self):
        """Both ask `has_active_run`, which answered no for `corrupt` and for `conflicting`."""
        hook_script = f"{HOOK_DIR.as_posix()}/guard_hook.py"
        saved = os.environ.pop("SUPREMETEAM_HARNESS_DEV", None)
        if saved is not None:
            self.addCleanup(os.environ.__setitem__, "SUPREMETEAM_HARNESS_DEV", saved)
        for arrangement in (*self.DEFECTS, "conflicting"):
            with self.subTest(arrangement):
                self.setUp()
                self.start()
                if arrangement == "conflicting":
                    self.second_held_run()
                else:
                    self.damage(arrangement)
                status = _saves.inspect_saves(self.project)["status"]
                self.assertEqual(status, "conflicting" if arrangement == "conflicting" else "corrupt")
                self.assertTrue(kit.denied(kit.decide(kit.edit(hook_script), self.project)), "the hook-file gate")
                prompt = kit.run_hook("user_prompt_submit.py", {"prompt": "continue"}, self.project)
                self.assertIn("a run is active (session pin held)",
                              json.loads(prompt.stdout)["hookSpecificOutput"]["additionalContext"])
        code, out = self.in_process("create", "--evidence", "README.md", run_id="run-3")
        self.assertEqual(out["reason"], f"another run holds the session pin ({self.FRESH}; "
                                        f"{self.FRESH.replace('run-1', 'run-2')})")

    def test_a_run_whose_records_disagree_does_not_block_unless_it_is_mid_publish(self):
        """Only a held run blocks: a coherent one, one mid-publish, or one whose records agree beside a directory where its
        journal belongs. A run damaged in any other way is preserved for escalation, and `create` goes ahead beside it, as
        it always has."""
        self.start()
        state = self.state()
        state["revision"] = 7
        (self.run_dir / "_state.md").write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(_saves.inspect_run(self.project, "run-1")["detail"], "state and lock revisions differ")
        self.assertEqual(self.lock()["status"], "held")
        code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual((code, out["result"]), (0, "ok"), out)

    def test_the_way_out_of_a_stale_lock_is_true_beside_one_held_run_and_beside_two(self):
        """It said to reclaim the lock with `recover --reason`, which refuses while another run holds the pin: beside two
        stale runs each refused the other. Its owner closing it works either way, and the reclaim once it is the only one."""
        self.start()
        self.age_records(45)
        code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
        self.assertEqual((code, out["reason"]), (1, f"another run holds the session pin ({self.STALE})"), out)
        self.assertEqual(self.in_process("recover", "--reason", "its session is gone")[0], 0, "the only held run is reclaimed")
        self.assertEqual(self.in_process("complete")[0], 0)

        self.setUp()
        self.start()
        self.second_held_run()
        self.age_records(45, self.run_dir.parent / "run-2" / "_lock.md")
        code, out = self.in_process("create", "--evidence", "README.md", run_id="run-3")
        self.assertEqual(out["reason"], f"another run holds the session pin ({self.STALE}; {self.STALE.replace('run-1', 'run-2')})")
        code, out = self.in_process("recover", "--reason", "its session is gone")
        self.assertEqual((code, out["reason"]), (1, f"another run holds the session pin ({self.STALE.replace('run-1', 'run-2')}); "
                                                    f"recovery would create a conflicting active set"), out)
        self.assertEqual(self.in_process("complete")[0], 0, "its owner closes it whatever else holds the pin")
        self.assertEqual(self.in_process("recover", "--reason", "its session is gone", run_id="run-2")[0], 0,
                         "the other is reclaimed once it is the only held run")
        self.assertEqual(self.in_process("complete", run_id="run-2")[0], 0)
        self.assertEqual(self.in_process("create", "--evidence", "README.md", run_id="run-3")[0], 0)

    def test_a_held_run_beside_a_directory_at_its_journal_blocks_create_and_counts_while_its_lock_is_fresh(self):
        """At HEAD the directory read as a journal: the run was active, mid-publish, and blocked `create`. Read as damage it
        stopped blocking and counting, though its lock still said held. It holds its pin again, and the way out is the
        damage's: no rollback settles a directory."""
        for kind, make in kit.directory_kinds().items():
            with self.subTest(kind):
                self.setUp()
                self.start()
                make(self.run_dir / "_journal.json")
                way_out = ("run run-1 holds a lock, but a directory stands at skillset-saves/runs/run-1/_journal.json: "
                           "preserve the record and escalate")
                for fresh in (True, False):
                    if not fresh:
                        self.age_records(45)
                    self.assertEqual(_saves.has_active_run(self.project), fresh)
                    code, out = self.in_process("create", "--evidence", "README.md", run_id="run-2")
                    self.assertEqual((code, out["reason"]), (1, f"another run holds the session pin ({way_out})"), out)
                    self.assertFalse((self.run_dir.parent / "run-2").exists())
                code, out = self.in_process("status")
                self.assertEqual((out["requested_run"]["state"], out["interrupted"]), ("corrupt", False), out)
                code, out = self.in_process("recover", "--rollback")
                self.assertEqual((code, out["reason"]), (1, "skillset-saves/runs/run-1/_journal.json is a directory, not a file: "
                                                            "preserve the record and escalate; never overwrite it"), out)


class HeartbeatBesideADamagedPointerTests(DamagedPointerCase):
    """The hook refresh kept a run alive only where the save root read `active` or `orphaned`, so behind a damaged pointer
    a live run went stale under real host activity while it still held the pin. The one coherent held run is kept alive
    whatever the pointer says, and the heartbeat rewrites the pointer from it: never beside a second coherent held run,
    never a stale lock, and never where the classification stopped at a record this account cannot read."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.dict(os.environ, {"SUPREMETEAM_PROJECT_DIR": str(self.project)})
        patch.start()
        self.addCleanup(patch.stop)

    def refresh(self):
        return run_heartbeat.refresh({"session_id": "host-1"}, "PreToolUse")

    def faults(self) -> int:
        return _state.load_observations(self.project).get("PreToolUse", {}).get("faults", 0)

    @staticmethod
    def aged(lock: Path, minutes: int) -> None:
        record = json.loads(lock.read_text(encoding="utf-8"))
        record["heartbeat"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        lock.write_text(json.dumps(record), encoding="utf-8")

    def test_the_lone_live_run_behind_each_damaged_pointer_is_kept_alive_and_the_pointer_rewritten(self):
        for defect in self.DEFECTS[:-1]:
            with self.subTest(defect):
                self.setUp()
                self.start()
                self.age_records(12)
                self.damage(defect)
                self.assertEqual(_saves.inspect_saves(self.project)["status"], "corrupt")
                result = self.refresh()
                self.assertEqual(result["source"], "hook:PreToolUse", result)
                self.assertEqual(self.lock()["heartbeat_source"], "hook:PreToolUse")
                pointer = json.loads(self.pointer.read_text(encoding="utf-8"))
                self.assertEqual((pointer["run_id"], pointer["revision"], pointer["updated_at"]),
                                 ("run-1", 1, self.lock()["heartbeat"]))
                self.assertEqual(_saves.inspect_saves(self.project)["status"], "active")
                self.assertEqual(self.faults(), 0)

    def test_a_directory_at_the_pointer_still_lets_the_lock_be_kept_alive_and_the_failed_pointer_write_is_counted(self):
        """The lock is written before the pointer; the directory stays where it is, said as the damage it is. The failed
        pointer write waits for nothing: on Windows the replace was retried for about three seconds inside the hook, as a
        permission problem."""
        self.start()
        self.age_records(12)
        self.damage("directory at the pointer")
        with mock.patch.object(save_run._fsutil.time, "sleep") as sleep:
            self.assertIsNone(self.refresh())
        sleep.assert_not_called()
        self.assertEqual(self.lock()["heartbeat_source"], "hook:PreToolUse")
        self.assertTrue(_saves.not_a_file(self.pointer))
        self.assertEqual(self.faults(), 1)

    def test_never_beside_a_second_coherent_held_run_whatever_the_pointer_says(self):
        for arrangement in ("conflicting", "a stale second run behind a damaged pointer"):
            with self.subTest(arrangement):
                self.setUp()
                self.start()
                self.second_held_run()
                other = self.run_dir.parent / "run-2" / "_lock.md"
                self.age_records(12, other)
                if arrangement != "conflicting":
                    self.aged(other, 45)
                    self.damage("malformed")
                before = (self.lock(), other.read_bytes(), self.pointer_bytes())
                self.assertIsNone(self.refresh())
                self.assertEqual((self.lock(), other.read_bytes(), self.pointer_bytes()), before)

    def test_never_a_stale_lock_behind_a_damaged_pointer(self):
        self.start()
        self.age_records(45)
        self.damage("malformed")
        before = self.lock()
        self.assertIsNone(self.refresh())
        self.assertEqual((self.lock(), self.pointer_bytes()), (before, b"{"))

    def test_never_over_a_pointer_this_account_cannot_read(self):
        """It may name a run this account cannot see; the classification stops there, and nothing is written."""
        self.start()
        self.age_records(12)
        before = (self.lock(), self.pointer_bytes())
        with kit.refusing("skillset-saves/_latest.md"):
            self.assertIsNone(self.refresh())
        self.assertEqual((self.lock(), self.pointer_bytes()), before)

    def test_a_held_run_mid_publish_beside_it_does_not_leave_the_live_run_to_go_stale(self):
        """A run whose records disagree is no second coherent one: it keeps its own way out (`recover --rollback`)."""
        self.start()
        self.second_held_run()
        other = self.run_dir.parent / "run-2"
        lock = json.loads((other / "_lock.md").read_text(encoding="utf-8"))
        (other / "_lock.md").write_text(json.dumps({**lock, "revision": 2}), encoding="utf-8")
        (other / "_journal.json").write_text('{"revision": 2, "step": "begin"}', encoding="utf-8")
        self.age_records(12)
        self.damage("malformed")
        self.assertEqual([(run["run_id"], run["state"]) for run in _saves.inspect_saves(self.project)["held_runs"]],
                         [("run-1", "active"), ("run-2", "corrupt")])
        self.assertEqual(self.refresh()["source"], "hook:PreToolUse")
        self.assertEqual(json.loads(self.pointer.read_text(encoding="utf-8"))["run_id"], "run-1")


class DirectoryWhereARecordBelongsTests(RunStateCase):
    """A directory where a record of the run belongs (a plain one, a junction, or a link to one) is damage, which no
    operation writes over. Windows refuses the read of one with the PermissionError it gives a file this account may not
    read, which the writer took for no record (`run has no lock; create it first`) or, for a journal, for an interrupted
    publish that no rollback could settle; POSIX raises IsADirectoryError, which it took for no record. Each is read here
    as this system reads it and as each system would, and said one way."""

    OPERATIONS = (("checkpoint",), ("heartbeat",), ("complete",), ("release",), ("block",), ("recover", "--reason", "why"),
                  ("recover", "--rollback"))

    def damaged(self, name: str) -> str:
        return f"skillset-saves/runs/run-1/{name} is a directory, not a file: preserve the record and escalate; never overwrite it"

    def test_every_operation_refuses_a_directory_at_the_state_the_lock_or_the_journal(self):
        for name in ("_state.md", "_lock.md", "_journal.json"):
            for kind, make in kit.directory_kinds().items():
                for system in kit.SYSTEMS:
                    with self.subTest(record=name, kind=kind, read_as=system):
                        self.setUp()
                        self.assertEqual(self.in_process("create", "--evidence", "README.md")[0], 0)
                        path = self.run_dir / name
                        path.unlink(missing_ok=True)
                        make(path)
                        kept = {other: (self.run_dir / other).read_bytes() for other in ("_state.md", "_lock.md") if other != name}
                        for operation, *extra in self.OPERATIONS:
                            with kit.read_as(system, name):
                                code, out = self.in_process(operation, *extra)
                            self.assertEqual((code, out["result"], out["reason"]), (1, "refused", self.damaged(name)), operation)
                        self.assertTrue(_saves.not_a_file(path), "nothing was written over it")
                        self.assertEqual({other: (self.run_dir / other).read_bytes() for other in kept}, kept)

    def test_create_refuses_a_directory_where_a_record_of_the_new_run_belongs_and_writes_no_record(self):
        """Create used to say the run already existed, or to publish into a dangling junction and leave an interrupted
        first revision behind."""
        for name in ("_state.md", "_lock.md", "_journal.json"):
            for kind, make in kit.directory_kinds().items():
                with self.subTest(record=name, kind=kind):
                    self.setUp()
                    self.run_dir.mkdir(parents=True)
                    make(self.run_dir / name)
                    code, out = self.in_process("create", "--evidence", "README.md")
                    self.assertEqual((code, out["result"], out["reason"]), (1, "refused", self.damaged(name)), out)
                    self.assertFalse((self.project / "skillset-saves" / "_latest.md").exists())
                    for record in {"_state.md", "_lock.md", "_journal.json"} - {name}:
                        self.assertFalse(os.path.lexists(self.run_dir / record), record)

    def test_a_directory_at_the_pointer_or_the_trail_degrades_the_write_and_says_what_stands_there(self):
        """The cause was the system's word for it: `Permission denied` on Windows, as for a record this account may not
        write, and `Is a directory` on POSIX. A rename replaces a link, so a link stays out of the pointer's cases."""
        cases =[("_latest.md", kind, make) for kind, make in kit.directory_kinds().items() if "link" not in kind]
        cases += [("_audit-trail.md", kind, make) for kind, make in kit.directory_kinds().items()]
        for name, kind, make in cases:
            with self.subTest(record=name, kind=kind):
                self.setUp()
                self.assertEqual(self.in_process("create", "--evidence", "README.md")[0], 0)
                path = self.project / "skillset-saves" / name if name == "_latest.md" else self.run_dir / name
                path.unlink()
                make(path)
                code, out = self.in_process("checkpoint")
                self.assertEqual((code, out["result"]), (2, "degraded"), out)
                cause = ("pointer not updated (write failed for _latest.md: _latest.md is a directory, not a file)"
                         if name == "_latest.md" else
                         "(audit append failed: skillset-saves/runs/run-1/_audit-trail.md is a directory, not a file)")
                self.assertIn(cause, out["reason"])
                self.assertNotIn("ermission denied", out["reason"])

    def test_status_reports_a_directory_at_the_journal_as_damage_not_as_an_interrupted_publish(self):
        """`status --run-id` read it as `interrupted` and named `recover --rollback`, which then found no revision in it."""
        for kind, make in kit.directory_kinds().items():
            with self.subTest(kind):
                self.setUp()
                self.assertEqual(self.in_process("create", "--evidence", "README.md")[0], 0)
                make(self.run_dir / "_journal.json")
                result = self.store().status()
                self.assertFalse(result["interrupted"], result)
                self.assertEqual((result["status"], result["detail"]),
                                 ("corrupt", "skillset-saves/runs/run-1/_journal.json is a directory, not a file"), result)
                self.assertEqual(result["requested_run"]["state"], "corrupt")
                self.assertEqual(result["next_step"], _saves.NEXT_STEPS["corrupt"])
                self.assertNotIn("access_denied", result)


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
