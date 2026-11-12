"""``run_files.py supersede``: one place for a superseded file, one record of it, and no way to misuse the move (WP-04).

The contracts tell every owner to preserve superseded artifacts, and the shape engine reads every file of a phase
directory, so a preserved copy either failed lineage or filled the slot of a missing current file. The command moves
such a file to ``<phase>/_superseded/rev-<n>/<original path>`` and lists it in ``_superseded/index.json``; the gate
leaves that tree out of the current package and holds every file in it to the index.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import run_files
from data_formats import content_sha256

SCRIPT = Path(run_files.__file__).resolve()
RUN = "r-1"


def certificate(revision: "int | str | None") -> str:
    front = f"---\nrevision: {revision}\nsubmission_id: S{revision}\n---\n" if revision is not None else ""
    return f"{front}# Completeness\nThe build is complete and certified.\n"


class Case(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.phase = self.root / "skillset-saves" / "runs" / RUN / "build"
        (self.phase / "reports").mkdir(parents=True)
        self.file = self.phase / "reports" / "report_completeness.md"
        self.file.write_text(certificate(1), encoding="utf-8")

    def supersede(self, path="reports/report_completeness.md", by=2, **more) -> dict:
        return run_files.supersede(self.root, RUN, "build", str(path), by, **more)

    def index(self) -> dict:
        return json.loads((self.phase / "_superseded" / "index.json").read_text(encoding="utf-8"))

    def cli(self, *args: str, cwd: "Path | None" = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "supersede", *args], capture_output=True, text=True,
                              cwd=str(cwd or self.root), stdin=subprocess.DEVNULL, check=False)


class SupersedeTests(Case):
    def test_the_file_moves_under_its_revision_and_is_indexed_with_its_digest(self):
        digest = content_sha256(self.file)
        moment = datetime(2026, 11, 12, 9, 30, tzinfo=timezone.utc)
        done = self.supersede(now=moment)
        moved = self.phase / "_superseded" / "rev-1" / "reports" / "report_completeness.md"
        self.assertFalse(self.file.exists())
        self.assertEqual(moved.read_text(encoding="utf-8"), certificate(1))
        self.assertEqual(done["moved_to"], moved)
        entry = {"path": "reports/report_completeness.md", "sha256": digest, "from_revision": 1, "superseded_by": 2,
                 "superseded_at": "2026-11-12T09:30:00Z"}
        self.assertEqual(done["entry"], entry)
        self.assertEqual(self.index(), {"schema_version": 1, "entries": [entry]})

    def test_a_second_revision_of_the_same_path_is_kept_beside_the_first(self):
        self.supersede()
        self.file.write_text(certificate(2), encoding="utf-8")
        self.supersede(by=3)
        self.assertEqual([(entry["from_revision"], entry["superseded_by"]) for entry in self.index()["entries"]], [(1, 2), (2, 3)])
        for revision in (1, 2):
            self.assertTrue((self.phase / "_superseded" / f"rev-{revision}" / "reports" / "report_completeness.md").is_file())

    def test_revision_labels_and_numbers_are_the_same_revision(self):
        self.file.write_text(certificate("r1"), encoding="utf-8")
        self.assertEqual(self.supersede(by="r2")["entry"]["from_revision"], 1)
        for value, number in ((3, 3), ("3", 3), ("r3", 3), ("R12", 12), (" 4 ", 4), ("three", None), ("r", None), (None, None),
                              (True, None), (-1, None), ("3.1", None)):
            with self.subTest(value=value):
                self.assertEqual(run_files.revision_number(value), number)

    def test_a_file_with_no_frontmatter_takes_its_revision_from_the_option(self):
        log = self.phase / "evidence" / "tests.log"
        log.parent.mkdir()
        log.write_text("12 passed\n", encoding="utf-8")
        with self.assertRaises(run_files.Refused) as caught:
            self.supersede("evidence/tests.log")
        self.assertIn("--from-revision", str(caught.exception))
        done = self.supersede("evidence/tests.log", from_revision=1)
        self.assertEqual(done["entry"]["from_revision"], 1)
        self.assertTrue((self.phase / "_superseded" / "rev-1" / "evidence" / "tests.log").is_file())

    def test_an_absolute_path_inside_the_phase_is_accepted(self):
        self.assertEqual(self.supersede(self.file)["entry"]["path"], "reports/report_completeness.md")

    def test_the_index_is_written_whole_and_no_temporary_file_is_left(self):
        self.supersede()
        self.assertEqual(sorted(path.name for path in (self.phase / "_superseded").iterdir()), ["index.json", "rev-1"])


class RefusalTests(Case):
    """Each refusal changes nothing: the file is where it was and no index appears."""

    def refused(self, fragment: str, *args, **kwargs) -> None:
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))
        with self.assertRaises(run_files.Refused) as caught:
            self.supersede(*args, **kwargs)
        self.assertIn(fragment, str(caught.exception))
        self.assertEqual(sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*") if path.name != "_superseded"), before)
        self.assertFalse((self.phase / "_superseded" / "index.json").exists())

    def test_a_path_outside_the_phase_directory(self):
        other = self.root / "skillset-saves" / "runs" / RUN / "review" / "reports" / "x.md"
        other.parent.mkdir(parents=True)
        other.write_text(certificate(1), encoding="utf-8")
        product = self.root / "src" / "a.py"
        product.parent.mkdir()
        product.write_text("x", encoding="utf-8")
        for path in ("../review/reports/x.md", other, product, "../../../../src/a.py", "reports/../../review/reports/x.md"):
            with self.subTest(path=str(path)):
                self.refused("is not inside", path)

    def test_a_file_already_under_superseded(self):
        self.supersede()
        with self.assertRaises(run_files.Refused) as caught:
            self.supersede("_superseded/rev-1/reports/report_completeness.md", by=5)
        self.assertIn("already under _superseded/", str(caught.exception))
        self.assertEqual(len(self.index()["entries"]), 1)

    def test_a_file_with_a_single_writer_of_its_own(self):
        for name in ("verdict_build-to-review.json", "verdict_build-to-review.cross-stage.json", "verdict_build-to-review.cycles.json",
                     "verdict_build-to-review.cycles.lock", "verdict_build-to-review.md"):
            (self.phase / name).write_text("{}", encoding="utf-8")
            with self.subTest(name=name):
                self.refused("single writer", name, from_revision=1)

    def test_a_revision_that_is_not_higher_than_the_files_own(self):
        for by in (1, 0, "r1"):
            with self.subTest(by=by):
                self.refused("is not higher than", by=by)
        self.refused("--by-revision must be a revision number", by="next")

    def test_a_from_revision_that_contradicts_the_frontmatter(self):
        self.refused("declares revision 1 in its frontmatter, not 3", by=5, from_revision=3)
        self.refused("--from-revision must be a revision number", from_revision="old")

    def test_a_directory_a_missing_file_and_an_unknown_run_or_phase(self):
        self.refused("is not a file", "reports")
        self.refused("is not a file", "reports/absent.md")
        with self.assertRaises(run_files.Refused):
            run_files.supersede(self.root, "../r-1", "build", "reports/report_completeness.md", 2)
        with self.assertRaises(run_files.Refused):
            run_files.supersede(self.root, RUN, "builds", "reports/report_completeness.md", 2)
        with self.assertRaises(run_files.Refused) as caught:
            run_files.supersede(self.root, "no-such-run", "build", "reports/report_completeness.md", 2)
        self.assertIn("does not exist", str(caught.exception))

    def test_a_file_reached_through_a_link(self):
        target = self.phase / "reports"
        link = self.phase / "alias"
        try:
            if os.name == "nt":
                import _winapi

                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"no link could be made here: {exc}")
        with self.assertRaises(run_files.Refused) as caught:
            self.supersede("alias/report_completeness.md")
        self.assertIn("reached through a link", str(caught.exception))
        self.assertTrue(self.file.is_file())

    def test_the_same_revision_of_a_path_twice(self):
        self.supersede()
        self.file.write_text(certificate(1), encoding="utf-8")
        with self.assertRaises(run_files.Refused) as caught:
            self.supersede()
        self.assertIn("already exists", str(caught.exception))
        self.assertTrue(self.file.is_file())

    def test_an_index_that_cannot_be_read_is_never_overwritten(self):
        index = self.phase / "_superseded" / "index.json"
        index.parent.mkdir()
        for text in ("{ not json", "[]", '{"entries": "x"}', '{"entries": [1]}'):
            index.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(run_files.Refused):
                self.supersede()
            self.assertEqual(index.read_text(encoding="utf-8"), text)
            self.assertTrue(self.file.is_file())


class FailureTests(Case):
    """A move that fails halfway leaves the file and the index agreeing with each other."""

    def test_a_failed_move_changes_nothing(self):
        with mock.patch.object(run_files.os, "replace", side_effect=PermissionError("denied")), self.assertRaises(OSError):
            self.supersede()
        self.assertTrue(self.file.is_file())
        self.assertFalse((self.phase / "_superseded" / "index.json").exists())
        self.assertFalse((self.phase / "_superseded" / "index.json.lock").exists(), "the lock is released")

    def test_a_failed_index_write_puts_the_file_back(self):
        with mock.patch.object(run_files, "_write_index", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.supersede()
        self.assertEqual(self.file.read_text(encoding="utf-8"), certificate(1))
        self.assertFalse((self.phase / "_superseded" / "rev-1" / "reports" / "report_completeness.md").exists())
        self.assertFalse((self.phase / "_superseded" / "index.json").exists())

    def test_a_failed_index_write_keeps_the_entries_it_had(self):
        self.supersede()
        self.file.write_text(certificate(2), encoding="utf-8")
        before = self.index()
        real = os.replace

        def fail_on_index(source, destination):
            if str(destination).endswith("index.json"):
                raise OSError("disk full")
            return real(source, destination)

        with mock.patch.object(run_files.os, "replace", side_effect=fail_on_index), self.assertRaises(OSError):
            self.supersede(by=3)
        self.assertEqual(self.index(), before)
        self.assertTrue(self.file.is_file())
        self.assertEqual(sorted(path.name for path in (self.phase / "_superseded").iterdir()), ["index.json", "rev-1", "rev-2"])
        self.assertEqual(list((self.phase / "_superseded" / "rev-2").rglob("*.md")), [])

    def test_a_stale_lock_is_broken_and_a_fresh_one_is_waited_for(self):
        lock = self.phase / "_superseded" / "index.json.lock"
        lock.parent.mkdir()
        lock.write_text("", encoding="utf-8")
        old = lock.stat().st_mtime - run_files.LOCK_STALE_SECONDS - 5
        os.utime(lock, (old, old))
        self.supersede()
        self.assertFalse(lock.exists())
        self.file.write_text(certificate(2), encoding="utf-8")
        lock.write_text("", encoding="utf-8")
        with mock.patch.object(run_files, "LOCK_WAIT_SECONDS", 0.2), self.assertRaises(run_files.Refused) as caught:
            self.supersede(by=3)
        self.assertIn("another run_files.py holds", str(caught.exception))
        self.assertTrue(self.file.is_file())


class CommandLineTests(Case):
    def test_the_command_prints_what_it_did_as_json(self):
        done = self.cli("--project-root", str(self.root), "--run-id", RUN, "--phase", "build", "--path", "reports/report_completeness.md",
                        "--by-revision", "2")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        self.assertEqual((report["ok"], report["command"], report["superseded"]["from_revision"]), (True, "supersede", 1))
        self.assertEqual(report["moved_to"], f"skillset-saves/runs/{RUN}/build/_superseded/rev-1/reports/report_completeness.md")
        self.assertEqual(report["index"], f"skillset-saves/runs/{RUN}/build/_superseded/index.json")

    def test_a_refusal_exits_1_with_the_reason_and_a_usage_error_exits_2(self):
        refused = self.cli("--project-root", str(self.root), "--run-id", RUN, "--phase", "build", "--path", "reports/report_completeness.md",
                           "--by-revision", "1")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("is not higher than", json.loads(refused.stdout)["error"])
        self.assertEqual(self.cli("--run-id", RUN).returncode, 2)

    def test_the_default_project_is_the_working_directory_and_a_worktrees_main_checkout(self):
        (self.root / ".git" / "worktrees" / "wt").mkdir(parents=True)
        worktree = self.root / ".claude" / "worktrees" / "wt"
        worktree.mkdir(parents=True)
        entry = self.root / ".git" / "worktrees" / "wt"
        (entry / "commondir").write_text("../..\n", encoding="utf-8")
        (entry / "gitdir").write_text(f"{(worktree / '.git').as_posix()}\n", encoding="utf-8")
        (worktree / ".git").write_text(f"gitdir: {entry.as_posix()}\n", encoding="utf-8")
        done = self.cli("--run-id", RUN, "--phase", "build", "--path", "reports/report_completeness.md", "--by-revision", "2", cwd=worktree)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue((self.phase / "_superseded" / "rev-1" / "reports" / "report_completeness.md").is_file())
        self.assertFalse((worktree / "skillset-saves").exists())


if __name__ == "__main__":
    unittest.main()
