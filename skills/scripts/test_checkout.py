"""A linked git worktree maps to its main checkout, and nothing else maps anywhere (WP-03).

``checkout_root`` decides where ``.harness-state/`` and ``skillset-saves/`` are read and written. A wrong answer in
one direction leaves the guard without its record (the defect this fixes); in the other it would let a ``.git`` file
somebody wrote send the state of one project into another. So the fixtures are built by hand, byte for byte the files
git writes, and the test needs no ``git``; one more case builds them with a real ``git worktree add`` when git is here.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import checkout
from checkout import checkout_root, is_linked_worktree


def same(first, second) -> bool:
    return os.path.realpath(first) == os.path.realpath(second)


def make_main(root: Path) -> Path:
    """A main checkout: a ``.git`` directory with the files a repository has."""
    (root / ".git" / "worktrees").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return root


def link_worktree(main: Path, worktree: Path, name: str, *, relative: bool = False) -> Path:
    """What ``git worktree add`` writes: the entry under ``.git/worktrees/<name>`` and the ``.git`` file that names it."""
    entry = main / ".git" / "worktrees" / name
    entry.mkdir(parents=True)
    worktree.mkdir(parents=True)
    (entry / "commondir").write_text("../..\n", encoding="utf-8")
    (entry / "gitdir").write_text(f"{(worktree / '.git').as_posix()}\n", encoding="utf-8")
    (entry / "HEAD").write_text("ref: refs/heads/x\n", encoding="utf-8")
    target = os.path.relpath(entry, worktree).replace("\\", "/") if relative else entry.as_posix()
    (worktree / ".git").write_text(f"gitdir: {target}\n", encoding="utf-8")
    return worktree


class CheckoutRootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.main = make_main(self.tmp / "main")

    def test_a_main_checkout_and_a_directory_with_no_git_are_themselves(self):
        plain = self.tmp / "plain"
        plain.mkdir()
        for root in (self.main, plain, self.tmp / "absent"):
            with self.subTest(root=root.name):
                self.assertEqual(checkout_root(root), root)
                self.assertFalse(is_linked_worktree(root))

    def test_a_linked_worktree_maps_to_its_main_checkout(self):
        inside = link_worktree(self.main, self.main / ".claude" / "worktrees" / "agent-a1", "agent-a1")
        outside = link_worktree(self.main, self.tmp / "elsewhere" / "wt2", "wt2")
        for worktree in (inside, outside):
            with self.subTest(worktree=worktree.name):
                self.assertTrue(same(checkout_root(worktree), self.main))
                self.assertTrue(is_linked_worktree(worktree))
        self.assertTrue(same(checkout_root(str(inside)), self.main), "a path given as text is accepted")

    def test_a_relative_gitdir_and_a_relative_commondir_are_followed(self):
        worktree = link_worktree(self.main, self.main / "wt" / "rel", "rel", relative=True)
        self.assertTrue(same(checkout_root(worktree), self.main))

    def test_an_absolute_commondir_is_followed(self):
        worktree = link_worktree(self.main, self.tmp / "abs", "abs")
        (self.main / ".git" / "worktrees" / "abs" / "commondir").write_text(f"{(self.main / '.git').as_posix()}\n", encoding="utf-8")
        self.assertTrue(same(checkout_root(worktree), self.main))

    def test_a_submodule_is_not_mapped(self):
        """A submodule's ``.git`` file names ``<super>/.git/modules/<name>``, which has no ``commondir``."""
        module = self.main / ".git" / "modules" / "vendor"
        module.mkdir(parents=True)
        (module / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        submodule = self.main / "vendor" / "sub"
        submodule.mkdir(parents=True)
        (submodule / ".git").write_text("gitdir: ../../.git/modules/vendor\n", encoding="utf-8")
        self.assertEqual(checkout_root(submodule), submodule)

    def test_the_worktree_of_a_bare_repository_is_not_mapped(self):
        """Its common directory is ``<name>.git`` with no working tree beside it: there is no main checkout."""
        bare = self.tmp / "bare.git"
        entry = bare / "worktrees" / "wt"
        entry.mkdir(parents=True)
        worktree = self.tmp / "bare-wt"
        worktree.mkdir()
        (entry / "commondir").write_text("../..\n", encoding="utf-8")
        (entry / "gitdir").write_text(f"{(worktree / '.git').as_posix()}\n", encoding="utf-8")
        (worktree / ".git").write_text(f"gitdir: {entry.as_posix()}\n", encoding="utf-8")
        self.assertEqual(checkout_root(worktree), worktree)

    def test_a_git_file_whose_back_link_names_another_directory_is_not_mapped(self):
        """Copying a worktree's ``.git`` file into another directory must not hand that directory the project's state."""
        real = link_worktree(self.main, self.tmp / "real", "real")
        forged = self.tmp / "forged"
        forged.mkdir()
        shutil.copy2(real / ".git", forged / ".git")
        self.assertEqual(checkout_root(forged), forged)
        self.assertFalse(is_linked_worktree(forged))
        (self.main / ".git" / "worktrees" / "real" / "gitdir").unlink()
        self.assertEqual(checkout_root(real), real, "with no back-link the link is not confirmed")

    def test_a_malformed_git_file_is_never_followed(self):
        for text in ("", "not a gitdir line\n", "gitdir:\n", "gitdir: /nonexistent/entry\n", "gitdir: \x00\n"):
            worktree = self.tmp / f"bad-{abs(hash(text))}"
            worktree.mkdir()
            (worktree / ".git").write_bytes(text.encode("utf-8"))
            with self.subTest(text=text):
                self.assertEqual(checkout_root(worktree), worktree)

    def test_a_main_checkout_that_is_gone_leaves_the_worktree_as_it_is(self):
        worktree = link_worktree(self.main, self.tmp / "orphan", "orphan")
        entry = self.main / ".git" / "worktrees" / "orphan"
        (entry / "commondir").write_text(f"{(self.tmp / 'gone' / '.git').as_posix()}\n", encoding="utf-8")
        self.assertEqual(checkout_root(worktree), worktree)

    def test_a_fault_while_reading_answers_with_the_directory_given(self):
        worktree = link_worktree(self.main, self.tmp / "faulty", "faulty")
        with mock.patch.object(checkout, "_line", side_effect=PermissionError("denied")):
            self.assertEqual(checkout_root(worktree), worktree)

    def test_it_never_starts_a_process(self):
        worktree = link_worktree(self.main, self.tmp / "quiet", "quiet")
        with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("a process was started")):
            self.assertTrue(same(checkout_root(worktree), self.main))

    def test_an_oversized_git_file_is_read_only_as_far_as_a_line_goes(self):
        worktree = self.tmp / "huge"
        worktree.mkdir()
        (worktree / ".git").write_bytes(b"gitdir: " + b"a" * 1_000_000)
        self.assertEqual(checkout_root(worktree), worktree)


@unittest.skipUnless(shutil.which("git"), "needs git")
class RealWorktreeTests(unittest.TestCase):
    """The same answers for the files git itself writes."""

    def git(self, cwd: Path, *args: str) -> None:
        done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "protocol.file.allow=always",
                               "-c", "init.defaultBranch=main", "-c", "core.autocrlf=false", *args],
                              cwd=str(cwd), capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 0, f"git {' '.join(args)}: {done.stderr}")

    def setUp(self):
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory(ignore_cleanup_errors=True))).resolve()
        self.main = self.tmp / "main"
        self.main.mkdir()
        self.git(self.main, "init", "-q")
        (self.main / "a.txt").write_text("x", encoding="utf-8")
        self.git(self.main, "add", ".")
        self.git(self.main, "commit", "-qm", "init")

    def test_git_worktree_add_maps_to_the_main_checkout_from_wherever_it_was_added(self):
        first = self.main / ".claude" / "worktrees" / "agent-a1"
        self.git(self.main, "worktree", "add", "-q", str(first))
        second = self.tmp / "elsewhere" / "wt2"
        second.parent.mkdir()
        self.git(first, "worktree", "add", "-q", str(second))
        for worktree in (first, second):
            with self.subTest(worktree=worktree.name):
                self.assertTrue(same(checkout_root(worktree), self.main))
        self.assertEqual(checkout_root(self.main), self.main)
        self.assertEqual(checkout_root(first / "nested"), first / "nested", "only the worktree's own root is a worktree")

    def test_a_submodule_and_a_bare_repository_worktree_are_themselves(self):
        source = self.tmp / "subsrc"
        source.mkdir()
        self.git(source, "init", "-q")
        (source / "s.txt").write_text("s", encoding="utf-8")
        self.git(source, "add", ".")
        self.git(source, "commit", "-qm", "init")
        self.git(self.main, "submodule", "add", "-q", str(source), "vendor/sub")
        submodule = self.main / "vendor" / "sub"
        self.assertEqual(checkout_root(submodule), submodule)
        bare = self.tmp / "bare.git"
        self.git(self.tmp, "clone", "-q", "--bare", str(self.main), str(bare))
        worktree = self.tmp / "bare-wt"
        self.git(bare, "worktree", "add", "-q", str(worktree))
        self.assertEqual(checkout_root(worktree), worktree)


if __name__ == "__main__":
    unittest.main()
