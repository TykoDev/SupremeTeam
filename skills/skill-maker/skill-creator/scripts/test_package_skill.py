"""Regression tests for package_skill: what is refused, what is skipped, and where the archive may land."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

CREATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CREATOR))
from scripts import package_skill as ps  # noqa: E402

SKILL_MD = "---\nname: sample\ndescription: Does a thing\n---\nbody\n"


def make_skill(root: Path, files: dict | None = None) -> Path:
    skill = root / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    for rel, text in (files or {}).items():
        path = skill / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return skill


def package(skill, output_dir=None) -> tuple[Path | None, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = ps.package_skill(skill, output_dir)
    return result, out.getvalue()


def names(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as z:
        return sorted(z.namelist())


class PackagingCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.out = self.root / "out" / "packages"

    def symlink(self, link: Path, target: Path) -> None:
        try:
            os.symlink(target, link, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError):
            self.skipTest("this host cannot create symlinks")


class RefusalTests(PackagingCase):
    """A secret, run state or a link in the source folder is refused, and nothing is written."""

    def assert_refused(self, skill: Path, *offenders: str):
        result, printed = package(skill, self.out)
        self.assertIsNone(result)
        self.assertFalse(self.out.exists(), "a refused package must leave no archive or directory behind")
        for offender in offenders:
            self.assertIn(offender, printed)

    def test_secrets_are_refused(self):
        for offender in (".env", ".env.production", "keys/server.pem", "keys/deploy.key", ".ENV", "keys/SERVER.PEM"):
            with self.subTest(offender=offender), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp).resolve()
                self.out = self.root / "out"
                skill = make_skill(self.root, {"references/ok.md": "fine", offender: "SECRET"})
                self.assert_refused(skill, offender)

    def test_run_state_is_refused(self):
        for offender in (".harness-state/packages/old.txt", "skillset-saves/runs/r/x.md"):
            with self.subTest(offender=offender), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp).resolve()
                self.out = self.root / "out"
                self.assert_refused(make_skill(self.root, {offender: "state"}), offender.split("/")[0])

    def test_every_offender_is_listed_not_just_the_first(self):
        skill = make_skill(self.root, {".env": "a", "x/id.pem": "b", ".harness-state/s": "c"})
        result, printed = package(skill, self.out)
        self.assertIsNone(result)
        refusal = printed[printed.index("Refusing"):]
        for offender in (".env", "id.pem", ".harness-state"):
            self.assertIn(offender, refusal)

    def test_a_symlinked_file_is_refused_not_zipped_under_an_innocent_name(self):
        secret = self.root / "secret.txt"
        secret.write_text("TOP-SECRET", encoding="utf-8")
        skill = make_skill(self.root, {"references/ok.md": "fine"})
        self.symlink(skill / "references" / "notes.md", secret)
        self.assert_refused(skill, "notes.md", "symlink")

    def test_a_symlinked_directory_and_a_dangling_link_are_refused(self):
        skill = make_skill(self.root)
        self.symlink(skill / "assets", self.root)
        self.symlink(skill / "missing", self.root / "does-not-exist")
        self.assert_refused(skill, "assets", "missing")

    def test_a_link_inside_an_excluded_directory_is_skipped_not_refused(self):
        skill = make_skill(self.root, {"node_modules/pkg/index.js": "x"})
        self.symlink(skill / "node_modules" / ".bin", self.root)
        result, printed = package(skill, self.out)
        self.assertIsNotNone(result, printed)
        self.assertEqual(["sample/SKILL.md"], names(result))


class ContentTests(PackagingCase):
    def test_ordinary_nested_content_is_packaged_with_forward_slashes(self):
        skill = make_skill(self.root, {"references/notes.md": "n", "scripts/run.py": "print()", "assets/logo.bin": "b"})
        result, _ = package(skill, self.out)
        self.assertEqual(["sample/SKILL.md", "sample/assets/logo.bin", "sample/references/notes.md", "sample/scripts/run.py"],
                         names(result))

    def test_regenerable_and_tool_owned_files_are_skipped_without_complaint(self):
        skill = make_skill(self.root, {
            ".git/config": "x", "scripts/__pycache__/a.pyc": "x", "scripts/b.pyc": "x", ".DS_Store": "x",
            "evals/evals.json": "{}", "node_modules/a/b.js": "x", "references/keep.md": "k",
        })
        (skill / "vendor").mkdir()
        (skill / "vendor" / ".git").write_text("gitdir: ../../.git/modules/v", encoding="utf-8")
        result, printed = package(skill, self.out)
        self.assertIsNotNone(result, printed)
        self.assertEqual(["sample/SKILL.md", "sample/references/keep.md"], names(result))
        self.assertIn("Skipped: sample/.git", printed)

    def test_a_previous_archive_in_the_skill_folder_is_not_packaged_into_the_next(self):
        skill = make_skill(self.root)
        first, _ = package(skill, skill)
        second, _ = package(skill, skill)
        self.assertEqual(first, second)
        self.assertEqual(["sample/SKILL.md"], names(second))


class LocationTests(PackagingCase):
    """Relative paths resolve against the working directory, which Phase 6 sets to skill-creator/."""

    def chdir(self, path: Path) -> None:
        previous = os.getcwd()
        os.chdir(path)
        self.addCleanup(os.chdir, previous)

    def test_a_relative_run_path_from_skill_creator_is_refused_instead_of_landing_beside_the_source(self):
        skill = make_skill(self.root)
        stray = CREATOR / "skillset-saves"
        self.assertFalse(stray.exists())
        self.addCleanup(shutil.rmtree, stray, True)
        self.chdir(CREATOR)
        result, printed = package(skill, "skillset-saves/runs/r1/skill-creation/packages")
        self.assertIsNone(result)
        self.assertFalse(stray.exists())
        self.assertIn("absolute path", printed)

    def test_an_absolute_path_works_whatever_the_working_directory(self):
        skill = make_skill(self.root)
        self.chdir(CREATOR)
        result, printed = package(skill, self.out)
        self.assertEqual(self.out / "sample.skill", result, printed)

    def test_a_relative_path_resolves_against_the_working_directory(self):
        skill = make_skill(self.root)
        work = self.root / "work"
        work.mkdir()
        self.chdir(work)
        result, _ = package(skill, "packages")
        self.assertEqual(work / "packages" / "sample.skill", result)

    def test_without_an_output_directory_the_archive_goes_under_the_project_harness_state(self):
        project = self.root / "proj"
        (project / ".git").mkdir(parents=True)
        (project / "sub").mkdir()
        skill = make_skill(self.root)
        self.chdir(project / "sub")
        with patch.object(Path, "home", return_value=self.root / "somewhere-else"):
            result, printed = package(skill)
        self.assertEqual(project / ".harness-state" / "packages" / "sample.skill", result, printed)

    def test_without_a_project_there_is_no_default_and_nothing_is_created_in_the_working_directory(self):
        skill = make_skill(self.root)
        work = self.root / "work"
        work.mkdir()
        self.chdir(work)
        # create=True: the marker list is a new name in this version; the old code never reads it.
        with patch("scripts.utils.PROJECT_MARKERS", ("no-such-marker",), create=True):
            result, printed = package(skill)
        self.assertIsNone(result)
        self.assertIn("Pass an output directory", printed)
        self.assertEqual([], list(work.iterdir()))


if __name__ == "__main__":
    unittest.main()
