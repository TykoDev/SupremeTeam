#!/usr/bin/env python3
"""Packaging and root-discovery contracts the Windows re-run surfaced.

The refusal message must name its offender with forward slashes whatever the host
spells, and the project-root walk must stop at the home directory instead of climbing
above it to a stranger's ``.claude``. Both are pinned here in the spellings the
original suites did not hold.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.package_skill import refusal_class, should_exclude
from scripts.utils import PROJECT_MARKERS, ProjectRootError, find_project_root, load_residue_classes
from scripts.test_package_skill import PackagingCase, make_skill, package


class RefusalMessageTests(PackagingCase):
    """One spelling for an offender's name in every message, whatever separator the host uses."""

    NESTED = ("keys/server.pem", "creds/credentials.json", "home/id_ed25519", "keys/CERT.P12")

    def test_every_nested_offender_is_named_with_forward_slashes(self):
        for offender in self.NESTED:
            with self.subTest(offender=offender), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp).resolve()
                self.out = self.root / "out"
                result, printed = package(make_skill(self.root, {"references/ok.md": "fine", offender: "SECRET"}), self.out)
                self.assertIsNone(result)
                self.assertIn(offender, printed.replace("\\", "/"))
                self.assertNotIn("\\", printed.split("Refusing", 1)[1].splitlines()[1])

    def test_a_skipped_file_is_named_with_forward_slashes_too(self):
        skill = make_skill(self.root, {"scripts/__pycache__/a.pyc": "x", "references/keep.md": "k"})
        result, printed = package(skill, self.out)
        self.assertIsNotNone(result, printed)
        self.assertIn("Skipped: sample/scripts/__pycache__/a.pyc", printed.replace("\\", "/"))

    def test_the_classification_matches_the_shared_list_for_every_spelling(self):
        residue = load_residue_classes()
        for offender in self.NESTED:
            with self.subTest(offender=offender):
                self.assertEqual(refusal_class(Path(offender), residue), "secret")
        self.assertIsNone(refusal_class(Path("references/notes.md"), residue))

    def test_an_excluded_directory_matches_at_any_depth(self):
        self.assertTrue(should_exclude(Path("sample/scripts/__pycache__/a.pyc")))
        self.assertTrue(should_exclude(Path("sample/vendor/node_modules/x/y.js")))
        self.assertFalse(should_exclude(Path("sample/references/notes.md")))


class HomeBoundaryTests(unittest.TestCase):
    """The walk stops at home: nothing above it is ever the project root."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        patcher = patch.object(Path, "home", return_value=self.home)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_marker_between_the_start_and_home_does_not_win_over_the_refusal(self):
        # The shape the Windows temp directory makes ordinary: the scratch lives under a home
        # that itself holds .claude, and the walk used to climb to it.
        start = self.home / "work" / "tools"
        start.mkdir(parents=True)
        with self.assertRaises(ProjectRootError):
            find_project_root(start=start)

    def test_the_walk_stops_at_home_even_with_markers_all_the_way_up(self):
        (self.root / ".claude").mkdir(exist_ok=True)
        with self.assertRaises(ProjectRootError):
            find_project_root(start=self.home / "work")

    def test_a_real_project_below_home_is_still_found_first(self):
        project = self.home / "proj"
        (project / ".git").mkdir(parents=True)
        deep = project / "skills" / "x"
        deep.mkdir(parents=True)
        self.assertEqual(project, find_project_root(start=deep))
        self.assertIn(".git", PROJECT_MARKERS)


if __name__ == "__main__":
    unittest.main()
