"""``run_files.py``: the sanctioned writer for a run's phase files.

``write`` (WP-10) puts a report, an artifact or an evidence file into a run of the main checkout, from either tree,
and holds itself to the boundaries the guard cannot apply to a script's arguments.

``supersede`` (WP-04): one place for a superseded file, one record of it, and no way to misuse the move.

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

    def put(self, *args: str, cwd: "Path | None" = None, content: "bytes | None" = b"# Packet\n") -> subprocess.CompletedProcess:
        """``run_files.py write`` with ``content`` on standard input (None: no standard input at all)."""
        return subprocess.run([sys.executable, str(SCRIPT), "write", *args], capture_output=True, cwd=str(cwd or self.root),
                              input=content, stdin=subprocess.DEVNULL if content is None else None, check=False)

    def worktree(self, name: str = "agent-a1") -> Path:
        """A linked git worktree of the project, as the files ``git worktree add`` writes."""
        entry = self.root / ".git" / "worktrees" / name
        entry.mkdir(parents=True)
        tree = self.root / ".claude" / "worktrees" / name
        tree.mkdir(parents=True)
        (entry / "commondir").write_text("../..\n", encoding="utf-8")
        (entry / "gitdir").write_text(f"{(tree / '.git').as_posix()}\n", encoding="utf-8")
        (tree / ".git").write_text(f"gitdir: {entry.as_posix()}\n", encoding="utf-8")
        return tree

    def guard(self, state: dict) -> None:
        directory = self.root / ".harness-state"
        directory.mkdir(exist_ok=True)
        (directory / "guard-state.json").write_text(json.dumps(state), encoding="utf-8")

    def run_files(self) -> list:
        """Every file under the run, apart from the fixture's own certificate."""
        run = self.root / "skillset-saves" / "runs" / RUN
        return sorted(path.relative_to(run).as_posix() for path in run.rglob("*") if path.is_file() and path != self.file)


class WriteTests(Case):
    """WP-10: the one way a delegate writes a run file that works from the main checkout and from a worktree."""

    def write(self, kind="reports", name="packet.md", data=b"# Packet\n", phase="review", run=RUN) -> dict:
        return run_files.write(self.root, run, phase, kind, name, data)

    def test_the_file_is_written_where_the_path_tool_resolves_it_and_reported_with_its_digest(self):
        done = self.write()
        target = self.root / "skillset-saves" / "runs" / RUN / "review" / "reports" / "packet.md"
        self.assertEqual(target.read_bytes(), b"# Packet\n")
        self.assertEqual(done, {"kind": "reports", "path": target, "relative": f"skillset-saves/runs/{RUN}/review/reports/packet.md",
                                "bytes": 9, "sha256": content_sha256(target), "replaced": False})
        self.assertEqual(run_files.output_paths.resolve(self.root, "reports", run_id=RUN, phase="review", name="packet.md"), target)

    def test_each_delegate_kind_lands_in_its_directory_and_a_name_may_hold_directories(self):
        for kind, name, relative in (("reports", "lens/bug-review.md", "review/reports/lens/bug-review.md"),
                                     ("artifacts", "tokens.css", "review/artifacts/tokens.css"),
                                     ("evidence", "logs/run.log", "review/evidence/logs/run.log"),
                                     ("coverage", ".coverage", "review/evidence/coverage/.coverage"),
                                     ("phase_report", "report_review.md", "review/report_review.md")):
            with self.subTest(kind=kind):
                self.assertEqual(self.write(kind, name)["relative"], f"skillset-saves/runs/{RUN}/{relative}")
        self.assertEqual(len(self.run_files()), 5)

    def test_a_second_write_replaces_the_file_whole_and_leaves_no_temporary_file(self):
        self.write(data=b"first\n" * 400)
        done = self.write(data=b"second\n")
        self.assertTrue(done["replaced"])
        self.assertEqual(done["path"].read_bytes(), b"second\n")
        self.assertEqual([path.name for path in done["path"].parent.iterdir()], ["packet.md"])

    def test_bytes_are_written_as_they_are_given(self):
        data = "# Größe ✓\r\nline\r\n".encode("utf-8") + bytes([0, 255, 254])
        self.assertEqual(self.write("evidence", "capture.bin", data)["path"].read_bytes(), data)

    def test_a_kind_with_a_writer_of_its_own_is_refused(self):
        for kind, name in (("core", "_state.md"), ("verdict", "x"), ("guards", "x"), ("trajectory", "x"),
                           ("project_preferences", "x"), ("global_preferences", "x")):
            with self.subTest(kind=kind), self.assertRaisesRegex(run_files.Refused, "one writer of its own"):
                self.write(kind, name)
        self.assertEqual(self.run_files(), [])

    def test_a_path_the_policy_gives_no_delegate_is_refused(self):
        for kind, name, phase, owner in (("manifest", "", "review", "phase-lead"), ("packages", "bundle.zip", "review", "phase-lead"),
                                         ("packages", "report_x.md", "review", "phase-lead"),
                                         ("phase_report", "report_grilling.md", "intake", "admiral"),
                                         ("phase_report", "intake-brief.md", "intake", "admiral"),
                                         ("product", "src/a.py", "review", "no class"), ("test_work", "x", "review", "harness-tests"),
                                         ("standalone_packages", "x.zip", "review", "skill-maker")):
            with self.subTest(kind=kind, name=name), self.assertRaisesRegex(run_files.Refused, f"not a path a delegated specialist writes.*{owner}"):
                self.write(kind, name, phase=phase)
        self.assertEqual(self.run_files(), [])
        self.assertFalse((self.root / "src").exists())
        self.assertFalse((self.root / ".harness-state").exists())

    def test_what_the_path_tool_refuses_is_refused(self):
        for kind, name, phase, run, fragment in (("reports", "../../_state.md", "review", RUN, "without traversal"),
                                                 ("reports", "/etc/passwd", "review", RUN, "without traversal|escapes project root"),
                                                 ("reports", "", "review", RUN, "without traversal"),
                                                 ("reports", "p.md", "nowhere", RUN, "phase must be one of"),
                                                 ("reports", "p.md", "review", "../r", "run_id must be"),
                                                 ("phase_report", "notes.md", "review", RUN, "phase-root files must be named"),
                                                 ("letters", "p.md", "review", RUN, "unknown output kind")):
            with self.subTest(name=name, phase=phase, run=run, kind=kind), self.assertRaisesRegex(run_files.Refused, fragment):
                self.write(kind, name, phase=phase, run=run)

    def test_a_run_that_has_no_directory_an_empty_content_and_a_directory_name(self):
        with self.assertRaisesRegex(run_files.Refused, "run r-2 has no directory"):
            self.write(run="r-2")
        self.assertFalse((self.root / "skillset-saves" / "runs" / "r-2").exists(), "a write never creates a run")
        with self.assertRaisesRegex(run_files.Refused, "nothing to write"):
            self.write(data=b"")
        (self.root / "skillset-saves" / "runs" / RUN / "review" / "reports" / "lens").mkdir(parents=True)
        with self.assertRaisesRegex(run_files.Refused, "is a directory"):
            self.write(name="lens")

    def test_a_destination_reached_through_a_link_is_refused(self):
        outside = self.root / "elsewhere"
        outside.mkdir()
        link = self.root / "skillset-saves" / "runs" / RUN / "review"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt":
                self.skipTest("this account cannot make a symlink")
            import _winapi

            _winapi.CreateJunction(str(outside), str(link))
        with self.assertRaisesRegex(run_files.Refused, "reached through a link"):
            self.write()
        self.assertEqual(list(outside.iterdir()), [])

    def test_a_frozen_or_blocked_glob_covers_the_destination(self):
        for key, kind in (("frozen_globs", "frozen"), ("blocked_globs", "blocked")):
            self.guard({key: [{"glob": f"skillset-saves/runs/{RUN}/review/evidence/**", "owner": "ops"}]})
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(run_files.Refused, f"inside a {kind} boundary"):
                    self.write("evidence", "log.txt")
                self.assertEqual(self.write("reports", f"{kind}.md")["replaced"], False, "a neighbour of the boundary is written")
        self.guard({"frozen_globs": [{"glob": f"skillset-saves/runs/{RUN}/review/evidence/**", "owner": "ops", "released_at": "2026-11-12T00:00:00Z"}]})
        self.write("evidence", "log.txt")

    def test_a_read_only_record_confines_the_writer_to_what_it_allows(self):
        (self.root / "skillset-saves" / "runs" / "r-2").mkdir()
        record = {"run_id": RUN, "owner": "code-chief", "allow": [f"skillset-saves/runs/{RUN}/**"]}
        self.guard({"read_only": [record]})
        self.write()
        with self.assertRaisesRegex(run_files.Refused, f"outside what the read-only record of run {RUN} allows"):
            self.write(run="r-2")
        self.assertEqual(list((self.root / "skillset-saves" / "runs" / "r-2").iterdir()), [])
        self.guard({"read_only": [dict(record, released_at="2026-11-12T00:00:00Z")]})
        self.write(run="r-2")

    def test_a_record_that_cannot_be_read_enforces_nothing_as_in_the_guard(self):
        (self.root / ".harness-state").mkdir()
        (self.root / ".harness-state" / "guard-state.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.write()["bytes"], 9)

    def test_a_linked_worktree_given_as_the_project_is_refused_by_the_function(self):
        tree = self.worktree()
        with self.assertRaisesRegex(run_files.Refused, "is a linked git worktree"):
            run_files.write(tree, RUN, "review", "reports", "packet.md", b"x")
        self.assertFalse((tree / "skillset-saves").exists())

    def test_a_policy_file_that_cannot_be_read_stops_the_command_without_deciding(self):
        with mock.patch.object(run_files, "OWNERSHIP", self.root / "absent.yaml"), self.assertRaises(run_files.CannotRun):
            self.write()
        self.assertEqual(self.run_files(), [])

    def test_a_policy_pattern_is_matched_one_segment_at_a_time(self):
        classes = run_files.ownership_classes()
        owner = lambda relative: (run_files.owning_class(relative, classes) or {}).get("id")  # noqa: E731
        run = "skillset-saves/runs/r1"
        self.assertEqual(owner(f"{run}/review/reports/a.md"), "phase-reports")
        self.assertEqual(owner(f"{run}/review/reports/lens/a.md"), "phase-reports")
        self.assertEqual(owner(f"{run}/review/report_x.md"), "phase-reports")
        self.assertEqual(owner(f"{run}/review/packages/report_x.md"), "phase-packages")
        self.assertEqual(owner(f"{run}/intake/report_grilling.md"), "grilling-log")
        self.assertEqual(owner(f"{run}/review/evidence/coverage/.coverage"), "phase-evidence")
        self.assertEqual(owner(f"{run}/review/manifest.json"), "phase-manifest")
        self.assertEqual(owner(f"{run}/_state.md"), "core-run-record")
        self.assertIsNone(owner("src/a.py"))


class WriteCommandTests(Case):
    def args(self, *more: str) -> tuple:
        return ("--run-id", RUN, "--phase", "review", "--kind", "reports", "--name", "packet.md", *more)

    def test_standard_input_is_written_and_the_report_has_the_path_tools_shape(self):
        done = self.put(*self.args())
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        target = self.root / "skillset-saves" / "runs" / RUN / "review" / "reports" / "packet.md"
        self.assertEqual(target.read_bytes(), b"# Packet\n")
        self.assertEqual((report["ok"], report["command"], report["kind"], report["path"], report["relative"]),
                         (True, "write", "reports", str(target), f"skillset-saves/runs/{RUN}/review/reports/packet.md"))
        self.assertEqual((report["bytes"], report["sha256"], report["replaced"]), (9, content_sha256(target), False))
        resolver = subprocess.run([sys.executable, str(SCRIPT.with_name("output_paths.py")), "--project-root", str(self.root), *self.args()],
                                  capture_output=True, text=True, check=False)
        resolved = json.loads(resolver.stdout)
        self.assertEqual({key: report[key] for key in resolved}, resolved, "the keys output_paths.py prints, with the same values")

    def test_a_file_named_with_from_is_written_and_a_missing_one_is_a_refusal(self):
        source = self.root / "draft.bin"
        source.write_bytes(bytes(range(256)))
        done = self.put(*self.args("--from", str(source)), content=None)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual((self.root / "skillset-saves" / "runs" / RUN / "review" / "reports" / "packet.md").read_bytes(), bytes(range(256)))
        missing = self.put(*self.args("--from", str(self.root / "absent.md")), content=None)
        self.assertEqual(missing.returncode, 1)
        self.assertIn("cannot be read", json.loads(missing.stdout)["error"])

    def test_a_refusal_exits_1_with_the_reason_and_writes_nothing(self):
        for label, args, content, fragment in (("no content", self.args(), b"", "nothing to write"),
                                               ("a single-writer kind", ("--run-id", RUN, "--phase", "review", "--kind", "core", "--name", "_state.md"),
                                                b"x", "one writer of its own"),
                                               ("an unknown run", ("--run-id", "r-9", "--phase", "review", "--kind", "reports", "--name", "p.md"),
                                                b"x", "has no directory")):
            with self.subTest(refused=label):
                done = self.put(*args, content=content)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertEqual(json.loads(done.stdout)["ok"], False)
                self.assertIn(fragment, json.loads(done.stdout)["error"])
        self.assertEqual(self.run_files(), [])
        self.assertEqual(self.put("--run-id", RUN).returncode, 2, "a usage error")

    def test_from_a_linked_worktree_the_file_lands_in_the_main_checkout(self):
        tree = self.worktree()
        for label, more in (("the default project", ()), ("the worktree named as the project", ("--project-root", str(tree))),
                            ("a relative project root", ("--project-root", "."))):
            with self.subTest(project=label):
                done = self.put(*self.args(*more), cwd=tree, content=label.encode())
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                target = self.root / "skillset-saves" / "runs" / RUN / "review" / "reports" / "packet.md"
                self.assertEqual(target.read_bytes(), label.encode())
                self.assertEqual(json.loads(done.stdout)["path"], str(target))
        self.assertFalse((tree / "skillset-saves").exists())
        self.assertFalse((tree / ".harness-state").exists())

    def test_the_guard_record_read_is_the_main_checkouts_from_a_worktree(self):
        tree = self.worktree()
        self.guard({"read_only": [{"run_id": "another", "owner": "ops", "allow": ["skillset-saves/runs/another/**"]}]})
        done = self.put(*self.args(), cwd=tree)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("outside what the read-only record of run another allows", json.loads(done.stdout)["error"])

    def test_a_missing_policy_file_exits_2_and_is_not_a_refusal(self):
        code = ("import sys; sys.argv = ['run_files.py', *sys.argv[1:]]; import run_files; from pathlib import Path; "
                "run_files.OWNERSHIP = Path('absent.yaml'); raise SystemExit(run_files.main())")
        done = subprocess.run([sys.executable, "-c", code, "write", "--project-root", str(self.root), *self.args()], capture_output=True,
                              input=b"x", cwd=str(SCRIPT.parent), check=False)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertEqual(done.stdout, b"")
        self.assertIn(b"cannot run", done.stderr)
        self.assertEqual(self.run_files(), [])


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
