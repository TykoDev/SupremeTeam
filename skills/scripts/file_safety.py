"""Two file operations the scripts share: telling a link from a file, and writing a record in one step.

``Path.is_symlink()`` does not see a Windows junction, and ``Path.rglob`` walks
straight through one, so a check written with ``is_symlink()`` alone reads or
packages files from wherever a junction points. ``is_reparse_point`` is true for a
symlink, a junction and every other reparse point, and ``project_files`` refuses to
inspect what it names. ``is_link`` is true only for a symlink and for a reparse
point whose tag names another path, as a junction's and a WSL symlink's do, and
``package_check`` refuses to package what it names. A cloud placeholder, such as a
OneDrive file that is not downloaded yet, is a reparse point but not a link, so a
repository kept in a OneDrive folder still packages.

``write_atomically`` writes a temporary file beside its target and moves it into
place, so no reader sees a half-written record, and it removes the temporary file
when either step fails, so a failed write leaves nothing behind. ``scan_record``
and ``check_parity`` write their records through it.

``check_runtime.py`` imports this module and has to run on an interpreter below
the catalog's Python floor, to report it as too old, so ``Path.is_junction``
(Python 3.12) is looked up rather than assumed.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


# winnt.h IsReparseTagNameSurrogate: the reparse tag names another path. The tags of
# a symlink, a junction and a WSL symlink carry it; a cloud placeholder's
# (0x9000001A) and an app execution alias's (0x8000001B) do not.
NAME_SURROGATE = 0x20000000


class AtomicWriteError(OSError):
    """A write that did not complete. The message says which step failed; no temporary file is left."""


def is_reparse_point(path: Path) -> bool:
    """True for a symlink, a Windows junction or any other reparse point; False when ``path`` cannot be examined."""
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except (OSError, ValueError):
        return False


def is_link(path: Path) -> bool:
    """True for a symlink or a reparse point whose tag names another path; False when ``path`` cannot be examined."""
    try:
        status = os.lstat(path)
    except (OSError, ValueError):
        return False
    return stat.S_ISLNK(status.st_mode) or bool(getattr(status, "st_reparse_tag", 0) & NAME_SURROGATE)


def _discard(path: Path) -> None:
    """Drop a temporary file a failed write or replace left behind, masking nothing."""
    try:
        path.unlink()
    except OSError:
        pass


def write_atomically(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` as UTF-8 through ``<path>.tmp``, replacing ``path`` in one step.

    Raises AtomicWriteError when the write or the replace fails, after removing the
    temporary file. Its message begins "could not be written" or "could not be
    moved into place", followed by the operating system's reason.
    """
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
    except OSError as exc:
        _discard(temporary)
        raise AtomicWriteError(f"could not be written: {exc}") from exc
    try:
        os.replace(temporary, path)
    except OSError as exc:
        _discard(temporary)
        raise AtomicWriteError(f"could not be moved into place: {exc}") from exc
