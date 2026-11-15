#!/usr/bin/env python3
"""Evidence has to cite the current file, by the path the directory gives it (WP-07, issue 3).

``Package.contain`` decided on the spelling of a path and on whether it left the evidence root. It never asked which
file the path reaches. Reproduced on Windows before the change: a junction inside the package that points at an old
copy passed with ``pass: true``; so did a direct citation of ``_history/rev-1/...`` and an upper-case spelling; and
the trailing-dot, ``::$DATA`` and short-name spellings were refused as evidence values only by accident, and accepted
as ``artifact_hashes`` keys.

The cases run a detached schema-1 package through ``check.py`` as a subprocess. A link is a symlink on POSIX and a
junction on Windows, which needs no privilege, so every case runs on an ordinary account.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
SKILLS = ENGINE_DIR.parents[1]
for _path in (SKILLS / "scripts", ENGINE_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import _gatecheck as gc  # noqa: E402
import check  # noqa: E402
from data_formats import content_sha256, load_data  # noqa: E402

CHECK = ENGINE_DIR / "check.py"
BOUNDARY = "skill-maker-to-delivery"
CURRENT = "# Validation\nrevision 2: all checks ran.\n"
OLD = "# Validation\nrevision 1: all checks ran.\n"


def link_directory(target: Path, link: Path) -> None:
    """A directory link the account may create: a junction on Windows, a symlink elsewhere."""
    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.pkg = self.tmp / "pkg"
        write(self.pkg / "reports" / "validation.md", CURRENT)
        write(self.pkg / "reports" / "links.md", "# Links\nAll links resolve.\n")

    def supersede(self, text: str = OLD, path: str = "reports/validation.md", revision: int = 1) -> Path:
        """Put a superseded copy and its index entry in place, as ``run_files.py supersede`` leaves them."""
        copy = write(self.pkg / "_superseded" / f"rev-{revision}" / path, text)
        index = self.pkg / "_superseded" / "index.json"
        entries = json.loads(index.read_text(encoding="utf-8"))["entries"] if index.exists() else []
        entries.append({"path": path, "sha256": content_sha256(copy), "from_revision": revision, "superseded_by": revision + 1,
                        "superseded_at": "2026-11-12T00:00:00Z"})
        write(index, json.dumps({"schema_version": 1, "entries": entries}))
        return copy

    def check(self, cited: str = "reports/validation.md", extra_hashes: "dict | None" = None) -> dict:
        """The gate's answer for a package whose ``validation_report`` cites ``cited``."""
        hashes = {"reports/links.md": content_sha256(self.pkg / "reports" / "links.md")}
        target = self.pkg / cited
        hashes[cited] = content_sha256(target) if target.is_file() else "0" * 64
        hashes.update(extra_hashes or {})
        manifest = {"submission_id": "s1", "revision": "r2", "revisions": ["r2"], "verdict_revision": "r2",
                    "evidence": {"skills": True, "team_manifest": True, "link_report": "reports/links.md", "validation_report": cited},
                    "artifact_hashes": hashes}
        write(self.pkg / "manifest.json", json.dumps(manifest))
        done = subprocess.run([sys.executable, str(CHECK), "--boundary", BOUNDARY, "--package", str(self.pkg / "manifest.json")],
                              capture_output=True, text=True, check=False)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return json.loads(done.stdout)

    def spelling_notes(self, result: dict) -> list:
        return [note for note in result["warnings"] if "on-disk spelling" in note or "reached through a link" in note]


class CurrentFileTests(Case):
    """No spelling of a superseded file satisfies an evidence key, and every refusal names the file it resolved to."""

    def test_the_path_the_directory_gives_passes_with_nothing_to_say(self):
        result = self.check()
        self.assertTrue(result["pass"], result["failures"])
        self.assertEqual(self.spelling_notes(result), [])

    def test_a_link_into_the_superseded_copies_is_refused(self):
        self.supersede()
        link_directory(self.pkg / "_superseded" / "rev-1" / "reports", self.pkg / "current_evidence")
        result = self.check("current_evidence/validation.md")
        self.assertFalse(result["pass"])
        self.assertIn("artifact cites a superseded copy: current_evidence/validation.md "
                      "(resolves to _superseded/rev-1/reports/validation.md)", result["failures"])

    def test_a_direct_citation_of_a_superseded_copy_or_of_the_history_is_refused(self):
        self.supersede()
        write(self.pkg / "_history" / "rev-1" / "validation.md", OLD)
        write(self.pkg / "reports" / "_History" / "validation.md", OLD)
        for cited in ("_superseded/rev-1/reports/validation.md", "_history/rev-1/validation.md", "reports/_History/validation.md"):
            with self.subTest(cited=cited):
                result = self.check(cited)
                self.assertFalse(result["pass"])
                self.assertTrue(any(failure.startswith(f"artifact cites a superseded copy: {cited} (resolves to ") for failure in result["failures"]),
                                result["failures"])

    def test_a_copy_of_a_superseded_file_under_a_new_name_is_refused(self):
        self.supersede()
        write(self.pkg / "reports" / "validation-final.md", OLD)
        result = self.check("reports/validation-final.md")
        self.assertFalse(result["pass"])
        self.assertIn("artifact content matches superseded copy rev 1: reports/validation-final.md", result["failures"])

    def test_an_unchanged_file_at_its_original_path_passes(self):
        """A log or a JSON record can be byte-identical from one revision to the next: at the path the superseded
        copy came from, it is the current file."""
        self.supersede(text=CURRENT)
        result = self.check()
        self.assertTrue(result["pass"], result["failures"])
        self.assertNotIn("superseded", " ".join(result["failures"]))

    def test_an_index_that_cannot_be_read_stops_no_package_that_cites_current_files(self):
        write(self.pkg / "_superseded" / "index.json", "{ not json")
        self.assertTrue(self.check()["pass"])

    def test_a_link_to_a_current_file_is_said_and_still_passes_for_one_release(self):
        link_directory(self.pkg / "reports", self.pkg / "alias")
        result = self.check("alias/validation.md")
        self.assertTrue(result["pass"], result["failures"])
        notes = self.spelling_notes(result)
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("artifact reached through a link: alias/validation.md (resolves to reports/validation.md)", notes[0])
        self.assertIn("becomes a failure in the next release", notes[0])

    def test_dot_and_dot_dot_components_are_not_another_spelling(self):
        for cited in ("./reports/validation.md", "reports/../reports/validation.md"):
            with self.subTest(cited=cited):
                result = self.check(cited)
                self.assertEqual(self.spelling_notes(result), [], result["warnings"])


class CaseSpellingTests(Case):
    def test_a_different_letter_case_is_reported_where_the_volume_ignores_case(self):
        if not (self.pkg / "REPORTS").exists():
            self.skipTest("this volume is case-sensitive: a different-case spelling names no file here")
        result = self.check("Reports/VALIDATION.md")
        notes = self.spelling_notes(result)
        self.assertEqual(len(notes), 2, result["warnings"])
        self.assertIn("artifact is not the on-disk spelling: Reports/VALIDATION.md (on disk: reports)", notes[0])
        self.assertIn("(on disk: validation.md)", notes[1])
        self.assertTrue(result["pass"], "a warning for one release, not yet a failure")

    def test_a_different_letter_case_of_a_superseded_folder_is_still_refused(self):
        if not (self.pkg / "REPORTS").exists():
            self.skipTest("this volume is case-sensitive")
        self.supersede()
        result = self.check("_SUPERSEDED/rev-1/reports/validation.md")
        self.assertTrue(any("cites a superseded copy" in failure for failure in result["failures"]), result["failures"])


@unittest.skipUnless(os.name == "nt", "trailing dots, streams and short names are Windows spellings")
class WindowsAliasTests(Case):
    """These spellings were refused as evidence values only because the path pattern rejects them, and were accepted
    as ``artifact_hashes`` keys. Each is now named for what it is."""

    def alias_note(self, alias: str) -> list:
        digest = content_sha256(self.pkg / "reports" / "validation.md")
        result = self.check(extra_hashes={alias: digest})
        return [note for note in self.spelling_notes(result) if alias in note]

    def test_a_trailing_dot_is_not_the_on_disk_spelling(self):
        notes = self.alias_note("reports/validation.md.")
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("artifact is not the on-disk spelling: reports/validation.md. (on disk: validation.md)", notes[0])

    def test_an_alternate_data_stream_is_not_the_on_disk_spelling(self):
        notes = self.alias_note("reports/validation.md::$DATA")
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("(on disk: validation.md)", notes[0])

    def test_a_short_name_is_not_the_on_disk_spelling(self):
        import ctypes

        long_path = str(self.pkg / "reports" / "validation.md")
        buffer = ctypes.create_unicode_buffer(1024)
        length = ctypes.windll.kernel32.GetShortPathNameW(long_path, buffer, 1024)
        short = Path(buffer.value).name if length else ""
        if not short or short.casefold() == "validation.md":
            self.skipTest("this volume keeps no short (8.3) names, so there is no short spelling to cite")
        notes = self.alias_note(f"reports/{short}")
        self.assertEqual(len(notes), 1, notes)
        self.assertIn(f"artifact is not the on-disk spelling: reports/{short} (on disk: validation.md)", notes[0])


class SpellingDefectTests(Case):
    """``spelling_defects``: each component against the listing of its parent."""

    def test_the_listed_spelling_and_a_path_through_dot_dot_have_no_defect(self):
        for cited in ("reports/validation.md", "reports/../reports/validation.md", "reports//validation.md", "./reports/validation.md",
                      "reports\\validation.md"):
            with self.subTest(cited=cited):
                self.assertEqual(gc.spelling_defects(self.pkg, cited), [])

    def test_a_link_is_reported_with_where_it_leads(self):
        link_directory(self.pkg / "reports", self.pkg / "alias")
        defects = gc.spelling_defects(self.pkg, "alias/validation.md")
        self.assertEqual([(kind, part) for kind, part, _ in defects], [("link", "alias")])
        self.assertEqual(os.path.realpath(defects[0][2]), os.path.realpath(self.pkg / "reports"))

    @unittest.skipIf(os.name == "nt", "a file symlink needs a privilege on Windows; the directory link covers the rule there")
    def test_a_file_symlink_is_reported_too(self):
        os.symlink(self.pkg / "reports" / "validation.md", self.pkg / "reports" / "alias.md")
        self.assertEqual([(kind, part) for kind, part, _ in gc.spelling_defects(self.pkg, "reports/alias.md")], [("link", "alias.md")])

    def test_a_name_no_entry_carries_is_reported_and_the_walk_stops(self):
        self.assertEqual(gc.spelling_defects(self.pkg, "absent/validation.md"), [("spelling", "absent", "")])

    def test_a_different_case_is_reported_with_the_entry_on_disk(self):
        if not (self.pkg / "REPORTS").exists():
            self.skipTest("this volume is case-sensitive")
        self.assertEqual(gc.spelling_defects(self.pkg, "REPORTS/Validation.MD"),
                         [("spelling", "REPORTS", "reports"), ("spelling", "Validation.MD", "validation.md")])

    def test_superseded_locations_are_told_in_any_letter_case(self):
        for parts, expected in ((("_superseded", "rev-1", "reports"), True), (("reports", "_SUPERSEDED"), True), (("_History",), True),
                                (("reports",), False), ((), False), (("superseded",), False)):
            with self.subTest(parts=parts):
                self.assertEqual(gc.in_superseded_location(parts), expected)


class RunLayoutTests(unittest.TestCase):
    """Inside a run the evidence root is the run directory, and an input is named from the project root."""

    def setUp(self):
        self.project = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.run = self.project / "skillset-saves" / "runs" / "r1"
        write(self.run / "_state.md", json.dumps({"run_id": "r1"}))
        write(self.run / "build" / "reports" / "validation.md", CURRENT)
        write(self.run / "_history" / "rev-1.state.json", "{}")
        write(self.run / "build" / "_superseded" / "rev-1" / "evidence" / "tests.log", "12 passed\n")
        write(self.project / "src" / "_history" / "module.py", "x = 1\n")
        manifest = {"schema_version": 2, "run_id": "r1", "boundary": BOUNDARY, "owner": "skill-maker", "submission_id": "s1",
                    "revision": 2, "revisions": [2], "evidence": {}, "artifact_hashes": {}}
        path = write(self.run / "build" / "manifest.json", json.dumps(manifest))
        self.package = check.Package(path, manifest, BOUNDARY, load_data(SKILLS / "gates.yaml"))

    def test_the_run_records_own_history_is_not_evidence(self):
        self.assertEqual(self.package.root_kind, "run")
        self.assertIsNone(self.package.contain("../_history/rev-1.state.json", "artifact"))
        self.assertIn("artifact cites a superseded copy: ../_history/rev-1.state.json (resolves to _history/rev-1.state.json)",
                      self.package.failures)

    def test_a_superseded_copy_is_not_an_input_and_a_product_folder_of_that_name_is(self):
        refused = self.package.project_path("skillset-saves/runs/r1/build/_superseded/rev-1/evidence/tests.log", "probe")
        self.assertIsNone(refused)
        self.assertTrue(any("probe cites a superseded copy" in failure for failure in self.package.failures), self.package.failures)
        before = list(self.package.failures)
        self.assertIsNotNone(self.package.project_path("src/_history/module.py", "probe"))
        self.assertEqual(self.package.failures, before)

    def test_a_sibling_phases_current_file_is_still_evidence(self):
        write(self.run / "intake" / "report_grilling.md", "# Intake\n")
        self.assertIsNotNone(self.package.contain("../intake/report_grilling.md", "artifact"))
        self.assertEqual(self.package.failures, [])
        self.assertEqual(self.package.warnings, [])


class PackageLinkTests(Case):
    """The shape engine: a link that stays inside the package may not stand a superseded copy in a current place."""

    def findings(self) -> list:
        report = gc.Report(boundary="x", package_path=str(self.pkg))
        gc.check_package_links(self.pkg, report)
        return [(finding.code, finding.location) for finding in report.findings]

    def test_a_link_to_a_superseded_folder_fails_and_one_to_a_current_folder_does_not(self):
        self.supersede()
        link_directory(self.pkg / "_superseded" / "rev-1" / "reports", self.pkg / "old-reports")
        link_directory(self.pkg / "reports", self.pkg / "same-reports")
        self.assertEqual(self.findings(), [("LINK_TO_SUPERSEDED", "old-reports")])

    def test_a_package_without_links_has_no_link_finding(self):
        self.supersede()
        self.assertEqual(self.findings(), [])


if __name__ == "__main__":
    unittest.main()
