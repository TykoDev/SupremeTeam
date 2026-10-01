"""Regression tests for link detection on interpreters older than Python 3.12.

Path.is_junction() does not exist before 3.12, and the packager and the eval viewer must
still run there (the packager is the one tool a Claude.ai session can use). The in-process
tests take the method away from Path; the interpreter tests run the real tools under every
older Python this host has.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

CREATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CREATOR))
from scripts import package_skill  # noqa: E402
from scripts.utils import is_link  # noqa: E402

_spec = importlib.util.spec_from_file_location("generate_review_link_test", CREATOR / "eval-viewer" / "generate_review.py")
generate_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_review)

SKILL_MD = "---\nname: sample\ndescription: Does a thing\n---\nbody\n"
MOUNT_POINT_TAG = 0xA0000003  # winnt.h IO_REPARSE_TAG_MOUNT_POINT: what makes a reparse point a junction
CLOUD_FILE_TAG = 0x9000001A  # a reparse point that is not a junction (OneDrive placeholders)
OLDER_INTERPRETERS = [exe for exe in map(shutil.which, ("python3.10", "python3.11")) if exe]


class _Missing:
    """A class attribute that reads as absent, even where a base class defines the method (3.13)."""

    def __get__(self, instance, owner=None):
        raise AttributeError("is_junction")


@contextlib.contextmanager
def without_is_junction():
    """Path as it is before Python 3.12."""
    local = Path.__dict__.get("is_junction")
    Path.is_junction = _Missing()
    try:
        yield
    finally:
        if local is not None:
            Path.is_junction = local
        else:
            del Path.is_junction


def lstat_with_reparse_tag(tag: int):
    real = Path.lstat

    def lstat(self, *args, **kwargs):
        result = real(self, *args, **kwargs)
        return SimpleNamespace(st_mode=result.st_mode, st_reparse_tag=tag)

    return patch.object(Path, "lstat", lstat)


def make_skill(root: Path) -> Path:
    skill = root / "sample"
    skill.mkdir()
    (skill / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    return skill


class LinkDetectionTests(unittest.TestCase):
    """Both copies of the check (the packager's helper and the viewer's) behave alike."""

    implementations = {"scripts.utils.is_link": is_link, "generate_review._is_link": generate_review._is_link}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "file.txt").write_text("x", encoding="utf-8")
        (self.root / "dir").mkdir()

    def assert_each(self, path: Path, expected: bool):
        for name, function in self.implementations.items():
            with self.subTest(implementation=name, path=path.name):
                self.assertEqual(function(path), expected)

    def test_a_plain_file_directory_or_missing_path_is_not_a_link(self):
        for name in ("file.txt", "dir", "absent"):
            self.assert_each(self.root / name, False)

    def test_the_same_holds_on_an_interpreter_without_is_junction(self):
        with without_is_junction():
            self.assertFalse(hasattr(Path, "is_junction"))
            for name in ("file.txt", "dir", "absent"):
                self.assert_each(self.root / name, False)

    def test_a_symlink_is_a_link_with_or_without_is_junction(self):
        link = self.root / "link"
        try:
            os.symlink(self.root / "file.txt", link)
        except (OSError, NotImplementedError):
            self.skipTest("this host cannot create symlinks")
        self.assert_each(link, True)
        with without_is_junction():
            self.assert_each(link, True)

    def test_a_mount_point_reparse_tag_is_a_junction_where_is_junction_is_missing(self):
        with without_is_junction(), lstat_with_reparse_tag(MOUNT_POINT_TAG):
            self.assert_each(self.root / "dir", True)

    def test_other_reparse_points_are_not_junctions(self):
        with without_is_junction(), lstat_with_reparse_tag(CLOUD_FILE_TAG):
            self.assert_each(self.root / "dir", False)

    def test_is_junction_is_used_where_it_exists(self):
        with patch.object(Path, "is_junction", create=True, return_value=True):
            self.assert_each(self.root / "dir", True)


class PackagerWithoutIsJunctionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def package(self, skill: Path):
        with contextlib.redirect_stdout(io.StringIO()):
            return package_skill.package_skill(skill, self.root / "out")

    def test_a_skill_is_packaged(self):
        skill = make_skill(self.root)
        with without_is_junction():
            archive = self.package(skill)
        self.assertEqual(archive, self.root / "out" / "sample.skill")
        self.assertTrue(archive.is_file())

    def test_a_symlink_is_still_refused(self):
        skill = make_skill(self.root)
        try:
            os.symlink(skill / "SKILL.md", skill / "alias.md")
        except (OSError, NotImplementedError):
            self.skipTest("this host cannot create symlinks")
        with without_is_junction():
            self.assertIsNone(self.package(skill))
        self.assertFalse((self.root / "out").exists())


@unittest.skipUnless(OLDER_INTERPRETERS, "no Python older than 3.12 on PATH")
class OlderInterpreterTests(unittest.TestCase):
    """The real tools, started by each Python below 3.12 that this host has."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def run_tool(self, interpreter: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([interpreter, *args], cwd=CREATOR, capture_output=True, text=True, encoding="utf-8")

    def test_the_packager_runs(self):
        skill = make_skill(self.root)
        for interpreter in OLDER_INTERPRETERS:
            with self.subTest(interpreter=interpreter):
                process = self.run_tool(interpreter, "-m", "scripts.package_skill", str(skill), str(self.root / "out"))
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                self.assertTrue((self.root / "out" / "sample.skill").is_file())

    def test_the_viewer_writes_its_static_page(self):
        run = self.root / "ws" / "eval-1" / "with_skill" / "outputs"
        run.mkdir(parents=True)
        (run / "answer.md").write_text("hello", encoding="utf-8")
        for interpreter in OLDER_INTERPRETERS:
            with self.subTest(interpreter=interpreter):
                page = self.root / f"{Path(interpreter).name}.html"
                process = self.run_tool(
                    interpreter, str(CREATOR / "eval-viewer" / "generate_review.py"), str(self.root / "ws"),
                    "--skill-name", "sample", "--static", str(page),
                )
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                self.assertIn("hello", page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
