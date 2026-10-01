#!/usr/bin/env python3
"""Path canonicalisation and glob matching for the guard (SEC-04, BUGH-20).

The guard used to compare path strings textually: ``..`` escaped the read-only allow
list, ``//`` and ``/./`` and upper case slipped past the single-writer rules, a glob
written ``./src/**`` never matched, and ``fnmatch("secrets/x", "**/secrets/**")`` was
false. Both sides, the target and the boundary, now go through ``_paths`` first.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOK_DIR))
import _paths  # noqa: E402


class PathCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def locate(self, text: str, bases=None):
        return _paths.locate(text, self.root, bases)

    def deny(self, text: str, glob: str, bases=None) -> bool:
        return _paths.matches(self.locate(text, bases), glob, self.root)

    def allow(self, text: str, globs, bases=None, fold: bool = False) -> bool:
        return _paths.inside_allowed(self.locate(text, bases), list(globs), self.root, fold=fold)


class LocateTests(PathCase):
    def test_spellings_of_one_path_collapse_to_one_relative_form(self):
        for text in ("src/payments/a.py", "./src/payments/a.py", "src//payments/a.py", "src/./payments/a.py",
                     "src/x/../payments/a.py", f"{self.root}/src/payments/a.py", f"{self.root}//src/./payments/a.py",
                     "src\\payments\\a.py", f"{self.root}/src/x/../payments/a.py"):
            with self.subTest(text=text):
                self.assertIn("src/payments/a.py", self.locate(text).rel)

    def test_a_dot_dot_that_leaves_the_project_is_not_inside_it(self):
        target = self.locate("skillset-saves/runs/r/investigation/" + "../" * 12 + "etc/passwd")
        self.assertEqual(target.rel, ())
        self.assertTrue(target.abs[0].endswith("/etc/passwd"))

    def test_relative_paths_resolve_against_each_base(self):
        sub = self.root / "src" / "payments"
        sub.mkdir(parents=True)
        target = self.locate("a.py", bases=[str(sub), str(self.root)])
        self.assertEqual(set(target.rel), {"src/payments/a.py", "a.py"})

    def test_a_foreign_absolute_path_is_marked_foreign(self):
        target = self.locate("D:\\proj\\src\\payments\\charge.py")
        self.assertTrue(target.foreign)
        self.assertEqual(target.abs, ("D:/proj/src/payments/charge.py",))
        self.assertFalse(self.locate("src/a.py").foreign)

    def test_a_drive_letter_is_never_consumed_by_dot_dot(self):
        self.assertEqual(self.locate("C:/../x").abs, ("C:/x",))

    def test_device_prefixes_and_alternate_data_streams_are_stripped(self):
        self.assertIn("src/a.py", self.locate(f"//?/{self.root}/src/a.py").rel)
        self.assertIn("skillset-saves/_latest.md", self.locate("skillset-saves/_latest.md::$DATA").rel)

    def test_trailing_dots_and_spaces_are_ignored_where_the_platform_ignores_them(self):
        with mock.patch.object(_paths, "WINDOWS", True):
            self.assertIn(".harness-state/guard-state.json", self.locate(".harness-state/guard-state.json. . ").rel)
            self.assertIn("a/b.txt", self.locate("a./b.txt.").rel)
        with mock.patch.object(_paths, "WINDOWS", False):
            self.assertNotIn(".harness-state/guard-state.json", self.locate(".harness-state/guard-state.json.").rel)

    def test_a_home_relative_path_gains_its_expanded_form(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.root), "USERPROFILE": str(self.root)}):
            self.assertIn("notes.txt", self.locate("~/notes.txt").rel)

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "needs POSIX symlinks")
    def test_a_symlink_adds_the_form_it_points_to(self):
        (self.root / "real").mkdir()
        (self.root / "alias").symlink_to(self.root / "real", target_is_directory=True)
        target = self.locate("alias/x.txt")
        self.assertEqual(set(target.rel), {"alias/x.txt", "real/x.txt"})

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "needs POSIX symlinks")
    def test_a_symlink_that_leaves_the_project_has_an_outside_form(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        (self.root / "escape").symlink_to(outside.name, target_is_directory=True)
        target = self.locate("escape/x.txt")
        self.assertEqual(target.rel, ("escape/x.txt",))
        self.assertEqual(len(target.abs), 2)


class NormalizeGlobTests(PathCase):
    def test_equivalent_spellings_become_one_glob(self):
        for raw in ("src/payments/**", "./src/payments/**", ".//src/payments/**", "src//payments/**", "src/./payments/**",
                    "src\\payments\\**", "src/x/../payments/**", f"{self.root}/src/payments/**"):
            with self.subTest(raw=raw):
                self.assertEqual(_paths.normalize_glob(raw, self.root), "src/payments/**")

    def test_a_trailing_slash_is_dropped_and_wildcard_forms_survive(self):
        self.assertEqual(_paths.normalize_glob("src/payments/", self.root), "src/payments")
        self.assertEqual(_paths.normalize_glob("**/secrets/**", self.root), "**/secrets/**")
        self.assertEqual(_paths.normalize_glob("*.tf", self.root), "*.tf")

    def test_a_glob_that_names_no_project_path_is_rejected(self):
        for raw in ("", "   ", ".", "./", "..", "../x/**", "src/../../x/**"):
            with self.subTest(raw=raw):
                self.assertIsNone(_paths.normalize_glob(raw, self.root))

    def test_an_absolute_glob_outside_the_project_stays_absolute(self):
        self.assertEqual(_paths.normalize_glob("/etc/**", self.root), "/etc/**")

    def test_a_glob_matches_the_same_paths_whichever_way_it_was_written(self):
        for raw in ("./src/payments/**", f"{self.root}/src/payments/**", "src/payments/"):
            with self.subTest(raw=raw):
                self.assertTrue(self.deny("src/payments/a.py", raw))
                self.assertTrue(self.deny(f"{self.root}/src/payments/a.py", raw))


class DenyMatchTests(PathCase):
    def test_a_leading_double_star_matches_a_top_level_directory(self):
        """BUGH-20: fnmatch('secrets/token.txt', '**/secrets/**') is False."""
        self.assertTrue(self.deny("secrets/token.txt", "**/secrets/**"))
        self.assertTrue(self.deny("app/secrets/token.txt", "**/secrets/**"))
        self.assertTrue(self.deny(f"{self.root}/secrets/token.txt", "**/secrets/**"))
        self.assertFalse(self.deny("mysecrets/token.txt", "**/secrets/**"))

    def test_the_boundary_is_a_path_boundary_not_a_prefix(self):
        self.assertTrue(self.deny("src/payments", "src/payments/**"))
        self.assertTrue(self.deny("src/payments/old/x.py", "src/payments/**"))
        self.assertFalse(self.deny("src/payments-archive/x.py", "src/payments/**"))
        self.assertFalse(self.deny("mysrc/payments/x.py", "src/payments/**"))
        self.assertFalse(self.deny("lib/src/payments/x.py", "src/payments/**"), "a relative glob is anchored at the project root")

    def test_non_canonical_spellings_of_the_target_still_hit(self):
        for text in ("src//payments/a.py", "src/./payments/a.py", "src/x/../payments/a.py", "SRC/Payments/A.PY",
                     "src\\payments\\a.py"):
            with self.subTest(text=text):
                self.assertTrue(self.deny(text, "src/payments/**"))

    def test_a_host_absolute_path_outside_the_known_root_still_matches_a_relative_glob(self):
        """Hosts report absolute paths; a Windows host path need not share this process's root."""
        self.assertTrue(self.deny("D:\\proj\\src\\payments\\charge.py", "src/payments/**"))
        self.assertTrue(self.deny("D:/proj/src/payments/charge.py", "src/payments/**"))
        self.assertFalse(self.deny("D:/proj/src/billing/charge.py", "src/payments/**"))
        self.assertFalse(self.deny("D:/proj/mysrc/payments/charge.py", "src/payments/**"))

    def test_extension_globs_match_at_any_depth(self):
        self.assertTrue(self.deny("certs/server.pem", "**/*.pem"))
        self.assertTrue(self.deny("server.pem", "**/*.pem"))
        self.assertTrue(self.deny("infra/main.tf", "infra/*.tf"))
        self.assertFalse(self.deny("infra/main.py", "infra/*.tf"))

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "needs POSIX symlinks")
    def test_a_boundary_is_hit_through_a_symlink_alias_in_either_direction(self):
        (self.root / "data").mkdir()
        (self.root / "link").symlink_to(self.root / "data", target_is_directory=True)
        self.assertTrue(self.deny("link/x.txt", "data/**"))
        self.assertTrue(self.deny("data/x.txt", "link/**"))

    def test_an_unusable_legacy_glob_still_matches_literally(self):
        self.assertTrue(self.deny("../x/y.txt", "../x/**"))


class CoverTests(PathCase):
    """A directory above a boundary is the boundary for a command that removes or rewrites a whole tree."""

    def covers(self, text: str, glob: str) -> bool:
        return _paths.covers(self.locate(text), glob, self.root)

    def test_the_boundary_directory_and_every_directory_above_it_cover_it(self):
        for text in ("src/payments", "src", ".", "./", f"{self.root}", f"{self.root}/src", "src//payments/", "SRC"):
            with self.subTest(text=text):
                self.assertTrue(self.covers(text, "src/payments/**"), text)

    def test_neighbours_children_and_unrelated_paths_do_not(self):
        for text in ("src/payments/old", "src/payments/old/x.py", "src/other", "srcx", "src/payments-archive", "lib", "../x"):
            with self.subTest(text=text):
                self.assertFalse(self.covers(text, "src/payments/**"), text)

    def test_a_glob_with_no_literal_prefix_is_covered_only_by_the_project_root(self):
        self.assertTrue(self.covers(".", "**/secrets/**"))
        self.assertFalse(self.covers("src", "**/secrets/**"))
        self.assertTrue(self.covers(".", "*.tf"))

    def test_an_alias_of_the_boundary_directory_is_covered_too(self):
        if not hasattr(os, "symlink") or os.name == "nt":
            self.skipTest("needs POSIX symlinks")
        (self.root / "real").mkdir()
        (self.root / "alias").symlink_to(self.root / "real", target_is_directory=True)
        self.assertTrue(self.covers("alias", "real/**"))
        self.assertTrue(self.covers("real", "alias/**"))


class AllowMatchTests(PathCase):
    ALLOW = ("skillset-saves/runs/r1/investigation/**", ".harness-state/**")

    def test_inside_the_allow_glob_is_allowed_in_every_spelling(self):
        for text in ("skillset-saves/runs/r1/investigation/a.md", f"{self.root}/skillset-saves/runs/r1/investigation/a.md",
                     "skillset-saves//runs/r1/./investigation/a.md", ".harness-state/trajectory.json"):
            with self.subTest(text=text):
                self.assertTrue(self.allow(text, self.ALLOW))

    def test_dot_dot_cannot_climb_out_of_the_allow_glob(self):
        """SEC-04: the old textual match accepted .../investigation/../../../../src/app.py."""
        for text in ("skillset-saves/runs/r1/investigation/../../../../src/app.py",
                     f"{self.root}/skillset-saves/runs/r1/investigation/../../../../src/app.py",
                     "skillset-saves/runs/r1/investigation/../design/x.md"):
            with self.subTest(text=text):
                self.assertFalse(self.allow(text, self.ALLOW))

    def test_a_same_named_path_deeper_in_the_tree_is_not_the_allowed_path(self):
        self.assertFalse(self.allow("src/skillset-saves/runs/r1/investigation/x.py", self.ALLOW))
        self.assertFalse(self.allow(f"{self.root}/src/skillset-saves/runs/r1/investigation/x.py", self.ALLOW))

    def test_a_foreign_absolute_path_is_never_allowed(self):
        self.assertFalse(self.allow("D:/proj/skillset-saves/runs/r1/investigation/x.md", self.ALLOW))
        self.assertFalse(self.allow("/etc/passwd", self.ALLOW))

    def test_the_allow_list_does_not_fold_case_unless_the_file_system_does(self):
        text = "skillset-saves/RUNS/r1/investigation/a.md"
        self.assertFalse(self.allow(text, self.ALLOW, fold=False))
        self.assertTrue(self.allow(text, self.ALLOW, fold=True))

    def test_every_base_a_relative_path_could_mean_must_be_allowed(self):
        sub = self.root / "src"
        sub.mkdir()
        self.assertFalse(self.allow("skillset-saves/runs/r1/investigation/a.md", self.ALLOW, bases=[str(sub), str(self.root)]))
        self.assertTrue(self.allow("skillset-saves/runs/r1/investigation/a.md", self.ALLOW, bases=[str(self.root)]))

    @unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "needs POSIX symlinks")
    def test_a_symlink_inside_the_allow_glob_that_points_out_is_not_allowed(self):
        allowed = self.root / "skillset-saves" / "runs" / "r1" / "investigation"
        allowed.mkdir(parents=True)
        (self.root / "src").mkdir()
        (allowed / "out").symlink_to(self.root / "src", target_is_directory=True)
        self.assertFalse(self.allow("skillset-saves/runs/r1/investigation/out/app.py", self.ALLOW))
        self.assertTrue(self.allow("skillset-saves/runs/r1/investigation/real.md", self.ALLOW))


@unittest.skipUnless(hasattr(os, "symlink") and os.name != "nt", "needs POSIX symlinks")
class ResolverTests(PathCase):
    """RR-guard-2: a shared resolver follows links exactly as ``realpath`` does, in one look per directory."""

    def build(self) -> list:
        (self.root / "real" / "deep" / "er").mkdir(parents=True)
        (self.root / "real" / "file.txt").write_text("x", encoding="utf-8")
        (self.root / "alias").symlink_to(self.root / "real", target_is_directory=True)
        (self.root / "rel").symlink_to("real/deep", target_is_directory=True)
        (self.root / "up").symlink_to("../" + self.root.name + "/real", target_is_directory=True)
        (self.root / "real" / "back").symlink_to("..", target_is_directory=True)
        (self.root / "chain").symlink_to("alias", target_is_directory=True)
        (self.root / "dangling").symlink_to(self.root / "nowhere")
        (self.root / "loop-a").symlink_to("loop-b")
        (self.root / "loop-b").symlink_to("loop-a")
        (self.root / "file-link").symlink_to("real/file.txt")
        return [f"{self.root}/{tail}" for tail in (
            "real", "real/deep/er", "alias", "alias/deep/er/new.txt", "rel", "rel/er/x/y", "up/deep", "real/back/real/file.txt",
            "chain/deep", "chain/deep/er/a/b/c", "dangling", "dangling/x", "loop-a", "loop-a/x", "file-link", "file-link/x",
            "real/file.txt/x", "missing/a/b/c", "alias/back/alias/deep")]

    def test_it_returns_what_realpath_returns(self):
        resolver = _paths.Resolver()
        for text in self.build():
            with self.subTest(path=text):
                self.assertEqual(resolver.real(text), _paths._real(text))

    def test_the_order_in_which_paths_are_asked_does_not_change_an_answer(self):
        paths = self.build()
        forward = [_paths.Resolver().real(text) for text in paths]
        shared = _paths.Resolver()
        self.assertEqual([shared.real(text) for text in reversed(paths)][::-1], forward)

    def test_a_relative_or_drive_path_is_not_resolved_and_the_root_is_itself(self):
        resolver = _paths.Resolver()
        self.assertEqual((resolver.real("a/b"), resolver.real("/")), (None, "/"))

    def test_a_directory_is_looked_at_once_however_many_paths_lie_below_it(self):
        deep = self.root / "/".join(f"d{i}" for i in range(40))
        deep.mkdir(parents=True)
        resolver = _paths.Resolver()
        with mock.patch("os.lstat", wraps=os.lstat) as lstat:
            for index in range(500):
                resolver.real(f"{deep}/f{index}")
        self.assertLess(lstat.call_count, 40 + len(deep.parts) + 500 + 5)

    def test_locate_with_a_resolver_gives_the_same_forms(self):
        self.build()
        resolver = _paths.Resolver()
        for text in ("alias/deep/new.txt", "rel/x", "chain/file.txt", "plain/none", "up/deep/er"):
            with self.subTest(text=text):
                self.assertEqual(_paths.locate(text, self.root, None, resolver), _paths.locate(text, self.root))


class CaseFoldTests(unittest.TestCase):
    def test_deny_matching_always_folds_and_allow_folds_only_on_a_case_insensitive_platform(self):
        with mock.patch.object(_paths, "WINDOWS", False), mock.patch.object(_paths.sys, "platform", "linux"):
            self.assertFalse(_paths.case_insensitive_fs())
        with mock.patch.object(_paths, "WINDOWS", True):
            self.assertTrue(_paths.case_insensitive_fs())
        with mock.patch.object(_paths, "WINDOWS", False), mock.patch.object(_paths.sys, "platform", "darwin"):
            self.assertTrue(_paths.case_insensitive_fs())


if __name__ == "__main__":
    unittest.main()
