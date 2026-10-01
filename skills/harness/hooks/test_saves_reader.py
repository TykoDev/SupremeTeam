#!/usr/bin/env python3
"""Classification of saved state: `_saves.inspect_saves` for the save root and
`inspect_run` for one run.

The classifier had no direct test. Corrupt, conflicting, orphaned, and unreadable
were asserted nowhere, so these went unnoticed: a run directory that intake had
already written into (the report has to exist before `create`) read as `corrupt`;
a record that was not valid UTF-8, or was nested deeply enough to overflow the
parser, raised out of the classifier and wedged `status`, `create`, and readiness
for the whole save root; a heartbeat dated in the future never went stale; the
documented `complete` status was never emitted; and a closed run whose evidence
had been pruned read as `corrupt`.
"""
from __future__ import annotations

import errno
import json
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
SAVE_RUN = HOOK_DIR / "save_run.py"
sys.path.insert(0, str(HOOK_DIR))
import _saves  # noqa: E402
from test_run_state import refusing  # noqa: E402

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


class SavedProject:
    """A save root written record by record, so each case states exactly what is on disk.

    Times are minutes from ``now``; a fixed clock keeps a case exact, while the
    tests of the clock-reading `has_active_run` build theirs from the real one."""

    def __init__(self, root: Path, now: datetime = NOW) -> None:
        self.root = root
        self.now = now
        self.runs = root / "skillset-saves" / "runs"
        (root / "README.md").write_text("# fixture\n", encoding="utf-8")

    def at(self, minutes: float) -> str:
        return (self.now + timedelta(minutes=minutes)).isoformat()

    def run(self, run_id: str, *, status: str = "active", revision: int = 1, lock_revision: int | None = None,
            heartbeat: float = -1, owner: str = "admiral", evidence: tuple[str, ...] = ("README.md",)) -> Path:
        held = status in {"active", "paused", "awaiting-input"}
        directory = self.runs / run_id
        directory.mkdir(parents=True, exist_ok=True)
        state = {"schema_version": 1, "run_id": run_id, "status": status, "session_pin": held, "revision": revision,
                 "active_owner": owner, "evidence_paths": list(evidence), "timestamp": self.at(heartbeat)}
        lock = {"schema_version": 1, "run_id": run_id, "owner": owner, "status": "held" if held else "released",
                "session_pin": held, "revision": lock_revision or revision, "heartbeat": self.at(heartbeat)}
        (directory / "_state.md").write_text(json.dumps(state), encoding="utf-8")
        (directory / "_lock.md").write_text(json.dumps(lock), encoding="utf-8")
        return directory

    def pointer(self, run_id: str, revision: int = 1, updated: float = -1) -> None:
        (self.root / "skillset-saves").mkdir(exist_ok=True)
        (self.root / "skillset-saves" / "_latest.md").write_text(
            json.dumps({"schema_version": 1, "run_id": run_id, "revision": revision, "updated_at": self.at(updated)}),
            encoding="utf-8")

    def classify(self) -> dict:
        return _saves.inspect_saves(self.root, now=self.now)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = SavedProject(Path(tmp.name).resolve())

    def expect(self, status: str, **fields) -> dict:
        result = self.project.classify()
        self.assertEqual(result["status"], status, result)
        for key, value in fields.items():
            self.assertEqual(result.get(key), value, result)
        return result

    # ------------------------------------------------ nothing usable on disk
    def test_missing_when_there_is_no_save_root_or_no_runs_directory(self):
        self.expect("missing", detail="skillset-saves does not exist")
        (self.project.root / "skillset-saves").mkdir()
        self.expect("missing", detail="skillset-saves/runs does not exist")

    def test_unreadable_when_the_runs_directory_is_empty(self):
        self.project.runs.mkdir(parents=True)
        self.expect("unreadable")

    def test_a_run_directory_intake_wrote_into_before_create_is_uninitialized_not_corrupt(self):
        """The documented order writes the grilling log first, and create cites it as evidence."""
        report = self.project.runs / "r1" / "intake" / "report_grilling.md"
        report.parent.mkdir(parents=True)
        report.write_text("decisions\n", encoding="utf-8")
        self.expect("uninitialized", run_id="r1")

    def test_an_uninitialized_directory_beside_a_closed_run_does_not_change_the_answer(self):
        self.project.run("done", status="complete")
        self.project.pointer("done")
        (self.project.runs / "later").mkdir()
        self.expect("complete", run_id="done")

    # ---------------------------------------------------------- corruption
    def test_corrupt_state_and_a_record_that_cannot_be_decoded_or_parsed(self):
        records = {
            "not a mapping": b"just words, no structure: [",
            "undecodable bytes": b"\xff\xfe\x00{",
            "nested past the parser": b"[" * 100_000 + b"]" * 100_000,
            "integer past the interpreter's digit limit": b'{"schema_version": 1, "revision": ' + b"9" * 5000 + b"}",
        }
        for label, content in records.items():
            with self.subTest(label):
                directory = self.project.run("r1")
                (directory / "_state.md").write_bytes(content)
                self.expect("corrupt", run_id="r1", detail="state is missing or schema-invalid")

    def test_a_damaged_record_beside_a_healthy_run_does_not_hide_it(self):
        self.project.run("healthy")
        self.project.pointer("healthy")
        (self.project.run("damaged") / "_lock.md").write_bytes(b"\xff\xfe\x00")
        self.expect("active", run_id="healthy")

    def test_incoherent_records_each_read_corrupt_with_their_reason(self):
        cases = {
            "state and lock revisions differ": lambda: self.project.run("r1", revision=2, lock_revision=1),
            "lock owner does not match active_owner": lambda: self.project.run("r1").joinpath("_lock.md").write_text(
                json.dumps({"schema_version": 1, "run_id": "r1", "owner": "someone-else", "status": "held", "session_pin": True,
                            "revision": 1, "heartbeat": self.project.at(-1)}), encoding="utf-8"),
            "missing evidence path": lambda: self.project.run("r1", evidence=("gone.md",)),
            "unsafe evidence path": lambda: self.project.run("r1", status="complete", evidence=("../outside.md",)),
        }
        for reason, build in cases.items():
            with self.subTest(reason):
                build()
                self.project.pointer("r1")
                self.assertIn(reason, self.expect("corrupt", run_id="r1")["detail"])

    def test_the_pointer_must_name_a_readable_coherent_run_at_its_revision(self):
        self.project.run("r1")
        cases = {
            "pointer requires run_id, revision, and updated_at": lambda: (self.project.root / "skillset-saves" / "_latest.md").write_text(
                '{"schema_version": 1}', encoding="utf-8"),
            "pointer target run ghost does not exist": lambda: self.project.pointer("ghost"),
            "pointer run_id is not a safe directory name": lambda: self.project.pointer("../r1"),
            "pointer revision 5 does not match run revision 1": lambda: self.project.pointer("r1", revision=5),
        }
        for reason, build in cases.items():
            with self.subTest(reason):
                build()
                self.assertEqual(self.expect("corrupt")["detail"], reason)

    # -------------------------------------------------- held runs and staleness
    def test_conflicting_when_two_runs_are_held(self):
        self.project.run("a")
        self.project.run("b")
        self.project.pointer("a")
        self.expect("conflicting", run_id="")

    def test_orphaned_when_the_pointer_is_missing_or_stale(self):
        self.project.run("r1")
        self.expect("orphaned", run_id="r1")
        self.project.pointer("r1", updated=-45)
        self.assertIn("stale", self.expect("orphaned", run_id="r1")["detail"])

    def test_active_names_the_run_status(self):
        self.project.run("r1", status="paused")
        self.project.pointer("r1")
        self.expect("active", run_id="r1", run_status="paused")

    def test_stale_when_the_heartbeat_is_old_or_further_in_the_future_than_clock_skew(self):
        for label, heartbeat, status in (("old", -45, "stale"), ("future", 120, "stale"), ("within skew", 2, "active")):
            with self.subTest(label):
                self.project.run("r1", heartbeat=heartbeat)
                self.project.pointer("r1", updated=heartbeat)
                self.expect(status, run_id="r1")

    # ------------------------------------------------------- closed runs
    def test_a_complete_run_reads_complete_and_a_released_or_blocked_run_reads_inactive_with_its_status(self):
        for status, expected in (("complete", "complete"), ("released", "inactive"), ("blocked", "inactive")):
            with self.subTest(status):
                self.project.run("r1", status=status)
                self.project.pointer("r1")
                self.expect(expected, run_id="r1", run_status=status)

    def test_closed_runs_without_a_pointer_read_inactive(self):
        self.project.run("r1", status="complete")
        self.expect("inactive", run_id="")

    def test_a_closed_run_whose_evidence_was_pruned_stays_readable_and_says_what_is_gone(self):
        self.project.run("r1", status="complete", evidence=("README.md", "pruned.log"))
        self.project.pointer("r1")
        result = self.expect("complete", run_id="r1", evidence_missing=["pruned.log"])
        self.assertIn("no longer exist", result["detail"])

    def test_a_held_run_is_not_excused_missing_evidence(self):
        self.project.run("r1", evidence=("README.md", "gone.log"))
        self.project.pointer("r1")
        self.assertIn("gone.log", self.expect("corrupt", run_id="r1")["detail"])

    def test_only_a_coherent_fresh_or_orphaned_run_counts_as_active(self):
        for label, build, expected in (("active", lambda p: (p.run("r1"), p.pointer("r1")), True),
                                       ("orphaned", lambda p: p.run("r1"), True),
                                       ("stale", lambda p: (p.run("r1", heartbeat=-45), p.pointer("r1", updated=-45)), False),
                                       ("complete", lambda p: (p.run("r1", status="complete"), p.pointer("r1")), False),
                                       ("uninitialized", lambda p: (p.runs / "r1").mkdir(parents=True), False)):
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                project = SavedProject(Path(tmp).resolve(), now=datetime.now(timezone.utc))
                build(project)
                self.assertEqual(_saves.has_active_run(project.root), expected)


class HasActiveRunTests(unittest.TestCase):
    """QR-PY-07: a prompt, and a guarded write, classified every saved run to learn whether one is active.

    The answer must stay the classification's, because the guard's hook-file protection and the
    session-pin reminder both read it (a conflicting set, for one, never counts), so the saving
    is in what is read, not in what is decided."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = SavedProject(Path(tmp.name).resolve(), now=datetime.now(timezone.utc))
        for index in range(40):
            self.project.run(f"closed-{index:02d}", status="complete", heartbeat=-600 - index)

    def classified_runs(self) -> int:
        """How many run directories the call classified in full."""
        real = _saves._record
        with mock.patch.object(_saves, "_record", side_effect=real) as record:
            self.answer = _saves.has_active_run(self.project.root)
        return record.call_count

    def test_closed_runs_are_never_classified_in_full(self):
        self.project.run("live")
        self.project.pointer("live")
        self.assertEqual(self.classified_runs(), 1)
        self.assertTrue(self.answer)

    def test_an_orphaned_run_is_found_among_the_closed_ones_and_the_pointed_run_is_read_too(self):
        self.project.run("orphan")
        self.project.pointer("closed-00")
        self.assertEqual(self.classified_runs(), 2)
        self.assertTrue(self.answer)

    def test_no_held_run_classifies_nothing_and_is_not_active(self):
        self.assertEqual(self.classified_runs(), 0)
        self.assertFalse(self.answer)

    def test_it_agrees_with_the_classification_in_every_arrangement(self):
        """Each case is judged against the full classification of the same directory."""
        cases = {
            "one live run": lambda p: (p.run("r"), p.pointer("r")),
            "paused": lambda p: (p.run("r", status="paused"), p.pointer("r")),
            "awaiting input": lambda p: (p.run("r", status="awaiting-input"), p.pointer("r")),
            "orphaned": lambda p: p.run("r"),
            "pointer behind": lambda p: (p.run("r"), p.pointer("r", updated=-45)),
            "stale": lambda p: (p.run("r", heartbeat=-45), p.pointer("r", updated=-45)),
            "future heartbeat": lambda p: (p.run("r", heartbeat=120), p.pointer("r")),
            "released": lambda p: (p.run("r", status="released"), p.pointer("r")),
            "blocked": lambda p: (p.run("r", status="blocked"), p.pointer("r")),
            "complete": lambda p: (p.run("r", status="complete"), p.pointer("r")),
            "two held runs": lambda p: (p.run("a"), p.run("b"), p.pointer("a")),
            "a stale held run beside the live pointed one": lambda p: (p.run("a"), p.run("b", heartbeat=-45), p.pointer("a")),
            "an orphan beside a pointer to a closed run": lambda p: (p.run("a"), p.pointer("closed-03")),
            "a stale held run only": lambda p: (p.run("a", heartbeat=-45), p.pointer("closed-03")),
            "pointer names nothing": lambda p: (p.run("r"), p.pointer("ghost")),
            "pointer is not a plain name": lambda p: (p.run("r"), p.pointer("../r")),
            "pointer at another revision": lambda p: (p.run("r", revision=3), p.pointer("r", revision=2)),
            "pointer is malformed": lambda p: (p.run("r"), (p.root / "skillset-saves" / "_latest.md").write_text("{", encoding="utf-8")),
            "pointed run lost its evidence": lambda p: (p.run("r", evidence=("gone.md",)), p.pointer("r")),
            "held lock, closed state": lambda p: (p.run("r", status="complete").joinpath("_lock.md").write_text(json.dumps(
                {"schema_version": 1, "run_id": "r", "owner": "admiral", "status": "held", "session_pin": True, "revision": 1,
                 "heartbeat": p.at(-1)}), encoding="utf-8"), p.pointer("r")),
            "unreadable lock beside a live run": lambda p: (p.run("a"), p.pointer("a"), p.run("b").joinpath("_lock.md").write_bytes(b"\xff\xfe")),
        }
        for label, build in cases.items():
            with self.subTest(label):
                self.setUp()
                build(self.project)
                expected = self.project.classify()["status"] in {"active", "orphaned"}
                self.assertEqual(_saves.has_active_run(self.project.root), expected, self.project.classify())


class RefusedRecordTests(unittest.TestCase):
    """RR3-state-1: records are owner-only since SEC-19, and an account that could not read one read it as no run.

    The permission error is simulated at the read, which is the same call that fails for a second account (and for
    a process that bypasses file modes, as root does, so these run everywhere)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = SavedProject(Path(tmp.name).resolve(), now=datetime.now(timezone.utc))

    def test_a_record_this_account_cannot_read_is_neither_absent_nor_damaged(self):
        cases = {
            "the lock of a held run": ("runs/a/_lock.md", "skillset-saves/runs/a/_lock.md", "a"),
            "the state of a held run": ("runs/a/_state.md", "skillset-saves/runs/a/_state.md", "a"),
            "the pointer": ("skillset-saves/_latest.md", "skillset-saves/_latest.md", ""),
        }
        for label, (tail, path, run_id) in cases.items():
            with self.subTest(label):
                self.project.run("a")
                self.project.pointer("a")
                with refusing(tail):
                    result = self.project.classify()
                    self.assertEqual(_saves.has_active_run(self.project.root), True)
                self.assertEqual((result["status"], result["access_denied"], result["run_id"]), ("corrupt", [path], run_id), result)
                self.assertIn(f"{path} exists but this account cannot read it (permission denied)", result["detail"])
                self.assertNotIn("missing", result["detail"])
                self.assertEqual(_saves.next_step(result), _saves.ACCESS_DENIED_STEP)

    def test_a_refused_lock_is_a_possible_pin_even_when_the_run_may_be_closed(self):
        self.project.run("done", status="complete")
        self.project.pointer("done")
        with refusing("runs/done/_lock.md"):
            result = self.project.classify()
            self.assertTrue(_saves.has_active_run(self.project.root))
        self.assertEqual((result["status"], result["access_denied"]), ("corrupt", ["skillset-saves/runs/done/_lock.md"]))

    def test_a_readable_released_lock_is_a_closed_run_whatever_else_is_refused(self):
        self.project.run("done", status="complete")
        self.project.pointer("done")
        with refusing("runs/done/_state.md"):
            result = self.project.classify()
            self.assertFalse(_saves.has_active_run(self.project.root))
        self.assertEqual(result["status"], "corrupt")
        self.assertNotIn("access_denied", result)
        self.assertIn("cannot read it (permission denied)", result["detail"])

    def test_a_refused_record_never_hides_a_readable_held_run_and_outranks_every_answer_that_says_none(self):
        arrangements = {
            "beside a live run": (lambda p: (p.run("a"), p.pointer("a"), p.run("b")), "runs/b/_lock.md", "active"),
            "beside a stale run": (lambda p: (p.run("a", heartbeat=-45), p.pointer("a", updated=-45), p.run("b")), "runs/b/_lock.md", "corrupt"),
            "beside a complete run": (lambda p: (p.run("a", status="complete"), p.pointer("a"), p.run("b")), "runs/b/_lock.md", "corrupt"),
            "beside closed runs and an orphan": (lambda p: (p.run("a", status="released"), p.pointer("a"), p.run("b"), p.run("c")),
                                                 "runs/c/_state.md", "orphaned"),
        }
        for label, (build, tail, status) in arrangements.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                project = SavedProject(Path(tmp).resolve(), now=datetime.now(timezone.utc))
                build(project)
                with refusing(tail):
                    result = project.classify()
                    self.assertEqual(result["status"], status, result)
                    self.assertTrue(_saves.has_active_run(project.root))

    def test_a_directory_this_account_cannot_list_is_not_read_as_nothing(self):
        """`Path.iterdir` raised out of the classifier, which `status` reported as an engine error and the hooks as a fault."""
        self.project.run("a")
        self.project.pointer("a")
        with mock.patch.object(Path, "iterdir", side_effect=PermissionError(errno.EACCES, "Permission denied",
                                                                            str(self.project.runs))):
            result = self.project.classify()
            self.assertTrue(_saves.has_active_run(self.project.root))
        self.assertEqual((result["status"], result["access_denied"]), ("corrupt", ["skillset-saves/runs"]), result)
        self.assertNotIn(str(self.project.root), result["detail"])

    def test_one_run_is_classified_corrupt_with_the_path_when_its_record_is_refused(self):
        self.project.run("a")
        with refusing("runs/a/_state.md"):
            result = _saves.inspect_run(self.project.root, "a", now=self.project.now)
        self.assertEqual((result["state"], result["access_denied"]), ("corrupt", ["skillset-saves/runs/a/_state.md"]), result)
        self.assertIn("cannot read it (permission denied)", result["detail"])

    def test_has_active_run_agrees_with_the_classification_when_a_record_cannot_be_read(self):
        """The answer is the classification's: active, orphaned, or a record that may be a held run."""
        arrangements = {
            "the lock of a live run": (lambda p: (p.run("r"), p.pointer("r")), "runs/r/_lock.md", True),
            "the state of a live run": (lambda p: (p.run("r"), p.pointer("r")), "runs/r/_state.md", True),
            "the pointer of a live run": (lambda p: (p.run("r"), p.pointer("r")), "/_latest.md", True),
            "the lock of a run that may be closed": (lambda p: p.pointer("closed-03"), "runs/closed-03/_lock.md", True),
            "the lock of a stale run": (lambda p: (p.run("r", heartbeat=-45), p.pointer("r", updated=-45)), "runs/r/_lock.md", True),
            "the lock of a closed run among others": (lambda p: p.run("x", status="released"), "runs/x/_lock.md", True),
            "the state of a closed run with a readable lock": (lambda p: (p.run("x", status="released"), p.pointer("x")),
                                                                "runs/x/_state.md", False),
            "the lock of a closed run beside an orphan": (lambda p: (p.run("r"), p.pointer("closed-03")), "runs/closed-03/_lock.md", True),
            "a record that is not there beside an orphan": (lambda p: p.run("r"), "runs/nothing/_lock.md", True),
        }
        for label, (build, tail, expected) in arrangements.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                project = SavedProject(Path(tmp).resolve(), now=datetime.now(timezone.utc))
                for index in range(10):
                    project.run(f"closed-{index:02d}", status="complete", heartbeat=-600 - index)
                build(project)
                with refusing(tail):
                    full = project.classify()
                    self.assertEqual(_saves.has_active_run(project.root), expected, full)
                    self.assertEqual(full["status"] in {"active", "orphaned"} or bool(full.get("access_denied")), expected, full)


class SharedConstantsTests(unittest.TestCase):
    def test_reader_and_writer_import_the_taxonomy_instead_of_restating_it(self):
        import save_run
        import save_taxonomy as taxonomy

        self.assertIs(_saves.ACTIVE_STATUSES, taxonomy.ACTIVE_STATUSES)
        self.assertIs(_saves.TERMINAL_STATUSES, taxonomy.TERMINAL_STATUSES)
        self.assertEqual(_saves.STALE_AFTER_SECONDS, taxonomy.STALE_AFTER_SECONDS)
        self.assertEqual(_saves.SCHEMA_VERSION, taxonomy.SCHEMA_VERSION)
        self.assertIs(save_run.ACTIVE_STATUSES, taxonomy.ACTIVE_STATUSES)
        self.assertEqual(save_run.POINTER, taxonomy.POINTER)


class VocabularyTests(unittest.TestCase):
    """save-protocol.md lists the classifications; one of the ten it listed was never emitted."""

    def documented(self) -> set[str]:
        text = (HOOK_DIR.parents[1] / "save-protocol.md").read_text(encoding="utf-8")
        sentence = re.search(r"Classify state as (.*?) with\s", text, re.S).group(1)
        return set(re.split(r",\s*(?:or\s+)?|\s+or\s+", " ".join(sentence.split())))

    def emitted(self) -> set[str]:
        seen = set()
        builds = {
            "missing": lambda p: None,
            "unreadable": lambda p: p.runs.mkdir(parents=True),
            "uninitialized": lambda p: (p.runs / "r1").mkdir(parents=True),
            "corrupt": lambda p: (p.run("r1"), (p.runs / "r1" / "_state.md").write_bytes(b"\xff")),
            "conflicting": lambda p: (p.run("a"), p.run("b")),
            "orphaned": lambda p: p.run("r1"),
            "active": lambda p: (p.run("r1"), p.pointer("r1")),
            "stale": lambda p: (p.run("r1", heartbeat=-45), p.pointer("r1")),
            "complete": lambda p: (p.run("r1", status="complete"), p.pointer("r1")),
            "inactive": lambda p: (p.run("r1", status="released"), p.pointer("r1")),
        }
        for label, build in builds.items():
            with tempfile.TemporaryDirectory() as tmp:
                project = SavedProject(Path(tmp).resolve())
                build(project)
                seen.add(project.classify()["status"])
                if label == "active":
                    (project.runs / "r1" / "_journal.json").write_text("{}", encoding="utf-8")
                    proc = subprocess.run([sys.executable, str(SAVE_RUN), "status", "--project-root", tmp, "--run-id", "r1"],
                                          text=True, capture_output=True, check=False)
                    seen.add(json.loads(proc.stdout)["status"])
        return seen

    def test_every_documented_classification_is_emitted_and_none_besides(self):
        self.assertEqual(self.emitted(), self.documented())


class SingleRunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = SavedProject(Path(tmp.name).resolve())

    def inspect(self, run_id: str) -> dict:
        return _saves.inspect_run(self.project.root, run_id, now=NOW)

    def test_each_run_is_classified_on_its_own_whatever_else_the_save_root_holds(self):
        self.project.run("live")
        self.project.pointer("live")
        self.project.run("late", heartbeat=-45)
        self.project.run("done", status="complete", evidence=("README.md", "pruned.log"))
        (self.project.runs / "fresh" / "intake").mkdir(parents=True)
        (self.project.run("broken") / "_state.md").write_bytes(b"\xff")
        expected = {"live": "active", "late": "stale", "done": "complete", "fresh": "uninitialized",
                    "broken": "corrupt", "nothing-here": "absent"}
        for run_id, state in expected.items():
            with self.subTest(run_id):
                self.assertEqual(self.inspect(run_id)["state"], state)
        self.assertEqual(self.inspect("done")["evidence_missing"], ["pruned.log"])
        self.assertEqual(self.inspect("live")["revision"], 1)


class StatusReportsTheRequestedRunTests(unittest.TestCase):
    """`status --run-id X` classified the whole project and only echoed X."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "README.md").write_text("# fixture\n", encoding="utf-8")

    def save(self, run_id: str, *args: str) -> tuple[int, dict]:
        proc = subprocess.run([sys.executable, str(SAVE_RUN), *args, "--project-root", str(self.root), "--run-id", run_id],
                              text=True, capture_output=True, check=False)
        return proc.returncode, json.loads((proc.stdout or proc.stderr)[(proc.stdout or proc.stderr).index("{"):])

    def test_the_documented_intake_then_create_order_never_reads_corrupt(self):
        report = self.root / "skillset-saves" / "runs" / "r1" / "intake" / "report_grilling.md"
        report.parent.mkdir(parents=True)
        report.write_text("decisions\n", encoding="utf-8")
        code, out = self.save("r1", "status")
        self.assertEqual((code, out["status"], out["requested_run"]["state"]), (0, "uninitialized", "uninitialized"), out)
        self.assertIn("create", out["next_step"])
        code, out = self.save("r1", "create", "--evidence", "skillset-saves/runs/r1/intake/report_grilling.md")
        self.assertEqual(code, 0, out)
        code, out = self.save("r1", "status")
        self.assertEqual((out["status"], out["requested_run"]["state"]), ("active", "active"), out)

    def test_the_requested_run_is_reported_beside_the_project_wide_answer(self):
        self.save("live", "create", "--evidence", "README.md")
        (self.root / "skillset-saves" / "runs" / "other" / "intake").mkdir(parents=True)
        code, out = self.save("other", "status")
        self.assertEqual(out["status"], "active", "the project-wide classification is unchanged")
        self.assertEqual(out["requested_run"]["state"], "uninitialized")
        code, out = self.save("nothing", "status")
        self.assertEqual(out["requested_run"]["state"], "absent")

    def test_a_record_that_cannot_be_decoded_does_not_stop_status_or_create(self):
        """One damaged record made `status`, `create`, and readiness fail for every run."""
        damaged = self.root / "skillset-saves" / "runs" / "damaged"
        damaged.mkdir(parents=True)
        (damaged / "_state.md").write_bytes(b"\xff\xfe\x00")
        (damaged / "_lock.md").write_bytes(b"[" * 100_000)
        code, out = self.save("damaged", "status")
        self.assertEqual((code, out["status"], out["requested_run"]["state"]), (0, "corrupt", "corrupt"), out)
        code, out = self.save("fresh", "create", "--evidence", "README.md")
        self.assertEqual(code, 0, out)

    def test_a_heartbeat_dated_in_the_future_can_be_reclaimed_like_a_stale_one(self):
        self.save("r1", "create", "--evidence", "README.md")
        lock_path = self.root / "skillset-saves" / "runs" / "r1" / "_lock.md"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["heartbeat"] = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        code, out = self.save("r1", "status")
        self.assertEqual(out["status"], "stale", "a future heartbeat used to read as fresh for ever")
        code, out = self.save("other", "create", "--evidence", "README.md")
        self.assertEqual(code, 1, out)
        self.assertIn("stale", out["reason"])
        code, out = self.save("r1", "recover", "--reason", "heartbeat is in the future")
        self.assertEqual(code, 0, out)
        code, out = self.save("r1", "status")
        self.assertEqual(out["status"], "active", out)


if __name__ == "__main__":
    unittest.main()
