"""Regression tests for the scripts on interpreters older than this repository's own floor.

Path.is_junction() does not exist before 3.12, and the packager and the eval viewer must
still run there (the packager is the one tool a Claude.ai session can use). The in-process
tests take the method away from Path; the interpreter tests run the real tools under every
older Python this host has; the 3.9 tests read the source because no 3.9 is assumed.
"""
import ast
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


def runnable_interpreters(names=("python3.10", "python3.11")) -> list[str]:
    """Return candidates that can actually start, not dormant version-manager shims."""
    runnable = []
    for executable in filter(None, map(shutil.which, names)):
        try:
            probe = subprocess.run(
                [executable, "-c", "import sys; print(sys.version_info[:2])"],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0:
            runnable.append(executable)
    return runnable


OLDER_INTERPRETERS = runnable_interpreters()


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


class Python39FloorTests(unittest.TestCase):
    """The scripts r1 ran on Python 3.9 still can: no annotation is evaluated as a union when the def runs.

    A "X | None" annotation raises TypeError before 3.10 unless annotations stay strings
    (from __future__ import annotations). No 3.9 interpreter is assumed here, so this
    reads the source instead of running it.
    """

    # Importable on 3.9 at r1: no definition-time union, no syntax newer than 3.9.
    RAN_ON_39 = ("package_skill", "quick_validate", "utils", "aggregate_benchmark", "generate_report")

    @staticmethod
    def evaluated_unions(tree: ast.Module) -> list[int]:
        """Line numbers of defs whose signature holds a PEP 604 union that Python evaluates."""
        lazy = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                   and any(alias.name == "annotations" for alias in node.names) for node in tree.body)
        if lazy:
            return []
        lines = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs, node.args.vararg, node.args.kwarg]
            annotations = [argument.annotation for argument in arguments if argument is not None and argument.annotation]
            if node.returns:
                annotations.append(node.returns)
            if any(isinstance(part, ast.BinOp) and isinstance(part.op, ast.BitOr)
                   for annotation in annotations for part in ast.walk(annotation)):
                lines.append(node.lineno)
        return lines

    def test_no_script_r1_ran_on_39_evaluates_a_union_annotation(self):
        for name in self.RAN_ON_39:
            with self.subTest(script=name):
                source = (CREATOR / "scripts" / f"{name}.py").read_text(encoding="utf-8")
                tree = ast.parse(source, feature_version=(3, 9))
                self.assertEqual(self.evaluated_unions(tree), [])

    def test_the_check_sees_a_union_that_python_would_evaluate(self):
        eager = ast.parse("def f(x: int | None) -> str | None: ...\n")
        lazy = ast.parse("from __future__ import annotations\ndef f(x: int | None) -> str | None: ...\n")
        plain = ast.parse("def f(x: int) -> str: ...\nvalue: int | None = None\n")
        self.assertEqual(self.evaluated_unions(eager), [1])
        self.assertEqual(self.evaluated_unions(lazy), [])
        self.assertEqual(self.evaluated_unions(plain), [])


class InterpreterDiscoveryTests(unittest.TestCase):
    def test_a_dormant_version_manager_shim_is_not_selected(self):
        with patch.object(shutil, "which", return_value="/shim/python3.10"), patch.object(
            subprocess, "run", return_value=subprocess.CompletedProcess([], 127)
        ):
            self.assertEqual(runnable_interpreters(("python3.10",)), [])

    def test_an_interpreter_that_starts_is_selected(self):
        with patch.object(shutil, "which", return_value="/bin/python3.10"), patch.object(
            subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ):
            self.assertEqual(runnable_interpreters(("python3.10",)), ["/bin/python3.10"])


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
