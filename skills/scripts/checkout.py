#!/usr/bin/env python3
"""Which checkout holds a project's runtime state.

``skillset-saves/`` and ``.harness-state/`` are git-ignored, so they exist only in the *main checkout*: the working
tree that holds the real ``.git`` directory. A *linked worktree* (``git worktree add``) is a second working tree of
the same repository whose ``.git`` is a file, and it has neither directory. A hook or a path tool that takes a linked
worktree for the project finds no guard record and no run there: the guard enforced no boundary in a session started
with ``claude --worktree``, and a report resolved from a worktree landed where no gate looks and was deleted with it.

``checkout_root`` maps a linked worktree to its main checkout and everything else to itself. It reads three small
files and never starts ``git``: the hooks call it on every host event. Stdlib only.
"""
from __future__ import annotations

import os
from pathlib import Path

__all__ = ["checkout_root", "is_linked_worktree"]

_GITDIR = "gitdir:"
# A ``.git`` file, a ``commondir`` and a ``gitdir`` back-link are one short line each; anything longer is not one.
_MAX_BYTES = 4096


def _line(path: Path) -> str:
    """The text of a one-line git file, stripped. Raises ``OSError`` when it cannot be read."""
    with open(path, "rb") as handle:
        return handle.read(_MAX_BYTES).decode("utf-8", "replace").strip()


def checkout_root(root: "str | os.PathLike[str]") -> Path:
    """The main checkout when ``root`` is a linked worktree of it, else ``root``.

    A linked worktree is recognised by all of these, and by nothing less:

    * ``root/.git`` is a file that says ``gitdir: <dir>`` (relative to ``root`` when not absolute);
    * ``<dir>/commondir`` exists and names the common git directory (relative to ``<dir>`` when not absolute). A
      submodule's ``.git`` file names a directory with no ``commondir``, so a submodule is not mapped;
    * the common directory is named ``.git``, so it has a working tree beside it. The worktree of a bare repository has
      no main checkout and is not mapped;
    * ``<dir>/gitdir``, git's own back-link, names ``root/.git``. A ``.git`` file that points at another worktree's
      entry (a copy, or one written to redirect the state) is not confirmed in both directions and is not mapped.

    On any error the answer is ``root``: a fault here must not move the state somewhere else."""
    root = Path(root)
    try:
        dot_git = root / ".git"
        if not dot_git.is_file():
            return root
        text = _line(dot_git)
        if not text.startswith(_GITDIR):
            return root
        git_dir = Path(text[len(_GITDIR):].strip())
        if not git_dir.is_absolute():
            git_dir = root / git_dir
        common_file = git_dir / "commondir"
        if not common_file.is_file():
            return root
        common = Path(_line(common_file))
        if not common.is_absolute():
            common = git_dir / common
        common = Path(os.path.realpath(common))
        if common.name != ".git":
            return root
        back_link = git_dir / "gitdir"
        if not back_link.is_file() or os.path.realpath(_line(back_link)) != os.path.realpath(dot_git):
            return root
        main = common.parent
        return main if main.is_dir() else root
    except (OSError, ValueError):
        return root


def is_linked_worktree(root: "str | os.PathLike[str]") -> bool:
    """True when ``checkout_root`` maps ``root`` to another directory."""
    try:
        return os.path.realpath(checkout_root(root)) != os.path.realpath(root)
    except (OSError, ValueError):
        return False
