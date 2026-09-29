"""Regression tests for the shared helpers: project-root discovery and stdout configuration."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.utils import PROJECT_MARKERS, ProjectRootError, configure_stdout, find_project_root


class ProjectRootTests(unittest.TestCase):
    """The old finder walked up looking for .claude/, and every user's home holds one."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def test_the_home_directory_is_not_a_project_even_though_it_holds_dot_claude(self):
        start = self.home / "work" / "tools"
        start.mkdir(parents=True)
        with self.assertRaises(ProjectRootError) as raised:
            find_project_root(start=start)
        self.assertIn("home directory", str(raised.exception))

    def test_the_working_directory_being_home_is_refused(self):
        with self.assertRaises(ProjectRootError):
            find_project_root(start=self.home)

    def test_a_project_below_home_is_found_from_a_deep_directory(self):
        (self.home / "proj" / ".git").mkdir(parents=True)
        start = self.home / "proj" / "skills" / "x" / "skill-creator"
        start.mkdir(parents=True)
        self.assertEqual(self.home / "proj", find_project_root(start=start))

    def test_the_nearest_marker_wins(self):
        (self.home / "proj" / ".git").mkdir(parents=True)
        (self.home / "proj" / "app" / ".claude").mkdir(parents=True)
        start = self.home / "proj" / "app" / "src"
        start.mkdir()
        self.assertEqual(self.home / "proj" / "app", find_project_root(start=start))

    def test_every_marker_identifies_a_project(self):
        for index, marker in enumerate(PROJECT_MARKERS):
            with self.subTest(marker=marker):
                project = self.root / "elsewhere" / f"project{index}"
                (project / marker).mkdir(parents=True)
                start = project / "sub"
                start.mkdir()
                self.assertEqual(project, find_project_root(start=start))

    def test_a_git_file_counts_because_worktrees_and_submodules_use_one(self):
        project = self.home / "wt"
        project.mkdir()
        (project / ".git").write_text("gitdir: /elsewhere", encoding="utf-8")
        self.assertEqual(project, find_project_root(start=project))

    def test_a_filesystem_root_is_never_a_project(self):
        with self.assertRaises(ProjectRootError):
            find_project_root(start=Path(Path.cwd().anchor))

    def test_an_explicit_directory_is_used_as_given(self):
        project = self.root / "anywhere"
        project.mkdir()
        self.assertEqual(project, find_project_root(explicit=project))

    def test_an_explicit_home_or_missing_directory_is_refused(self):
        with self.assertRaises(ProjectRootError):
            find_project_root(explicit=self.home)
        with self.assertRaises(ProjectRootError):
            find_project_root(explicit=self.root / "missing")
        with self.assertRaises(ProjectRootError):
            find_project_root(explicit=Path(Path.cwd().anchor))


class ConfigureStdoutTests(unittest.TestCase):
    def test_a_cp1252_pipe_stops_raising_on_text_it_cannot_encode(self):
        raw = io.BytesIO()
        pipe = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", write_through=True)
        with self.assertRaises(UnicodeEncodeError):
            pipe.write("日本")
        with patch.object(sys, "stdout", pipe), patch.object(sys, "stderr", io.StringIO()):
            configure_stdout()
            print("日本 ✓")
        self.assertEqual("日本 ✓\n", raw.getvalue().decode("utf-8"))

    def test_a_stream_that_cannot_be_reconfigured_is_left_alone(self):
        with patch.object(sys, "stdout", io.StringIO()), patch.object(sys, "stderr", io.StringIO()):
            configure_stdout()  # StringIO has no reconfigure(); this must not raise


if __name__ == "__main__":
    unittest.main()
