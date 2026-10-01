#!/usr/bin/env python3
"""Canonical paths and globs for the guard: both sides of a comparison, never one.

The guard compared the path a tool reported with the glob a boundary was recorded
under, as text. ``..`` climbed out of an allow list, ``//``, ``/./`` and upper case
slipped under the single-writer rules, a glob pasted as ``./src/**`` never matched
anything, and a leading ``**/`` missed a top-level directory. Here a target is
located (every spelling of it, and the place a link leads, relative to the project
root) and a glob is normalised the same way when it is recorded and when it is
matched, so two spellings of one path are one path.

Matching keeps the semantics the boundaries always had: ``*`` and ``**`` both cross
a separator, a glob names the directory itself and everything under it, and a
relative glob is anchored at the project root. A host path outside the known root
(a Windows path while this process runs elsewhere) cannot be related to it, so a
relative glob still matches it at any depth, the one loose rule left, and only ever
in the deny direction. An allow list is never loosened: every form a target can take
must lie inside it.

Stdlib only, no I/O beyond ``realpath``, no import of another hook module.
"""
from __future__ import annotations

import fnmatch
import functools
import os
import posixpath
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

# Windows ignores trailing dots and spaces in a name and so does the guard, but only
# where that is true: a file named ``x.`` on Linux is a different file.
WINDOWS = os.name == "nt"

_DRIVE = re.compile(r"^[A-Za-z]:")
_WILDCARD = re.compile(r"[*?\[]")


def case_insensitive_fs() -> bool:
    """True where a default volume treats ``A`` and ``a`` as one name (Windows, macOS)."""
    return WINDOWS or sys.platform == "darwin"


@dataclass(frozen=True)
class Form:
    """One absolute spelling of a target and, when it lies in the project, its root-relative one."""

    abs: str
    rel: "str | None"


@dataclass(frozen=True)
class Target:
    """Every canonical form of one path a tool named."""

    raw: str
    forms: tuple

    @property
    def abs(self) -> tuple:
        return tuple(form.abs for form in self.forms)

    @property
    def rel(self) -> tuple:
        return tuple(form.rel for form in self.forms if form.rel is not None)

    @property
    def foreign(self) -> bool:
        """No form lies inside the project: the path cannot be related to this process's root."""
        return not self.rel


def _is_abs(text: str) -> bool:
    return text.startswith("/") or bool(_DRIVE.match(text))


def is_absolute(text: str) -> bool:
    """True for a POSIX or drive-letter absolute path in any separator spelling."""
    return _is_abs(clean(text))


def clean(text: str) -> str:
    """Spelling-level cleanup of one path: separators, device prefixes, streams, Windows name quirks."""
    text = str(text).replace("\\", "/")
    if text[:4] in ("//?/", "//./"):
        text = text[4:]
    if text.endswith("::$DATA"):
        text = text[: -len("::$DATA")]
    text = re.sub(r"/{2,}", "/", text)
    if WINDOWS:
        parts = text.split("/")
        text = "/".join(part if part in ("", ".", "..") else (part.rstrip(". ") or part) for part in parts)
    return text


def _normalise(text: str) -> str:
    """Collapse ``.``, ``..`` and repeated separators in an absolute path without consuming a drive letter."""
    drive = _DRIVE.match(text)
    if drive:
        return drive.group(0) + posixpath.normpath("/" + text[2:].lstrip("/"))
    return posixpath.normpath(text)


def posix(path: "str | Path") -> str:
    """The forward-slash text of a path."""
    return Path(path).as_posix() if not isinstance(path, str) else path.replace("\\", "/")


def _real(text: str) -> "str | None":
    """The place a path leads once links are followed, or None where that cannot differ or be asked."""
    try:
        if not os.path.isabs(text):
            return None
        return os.path.realpath(text).replace("\\", "/")
    except (OSError, ValueError):
        return None


class Resolver:
    """Link resolution for many paths that share a prefix: each directory is looked at once.

    ``os.path.realpath`` stats every component of every path it is given, so a long working
    directory and a thousand writes in it cost a thousand walks of the whole directory. Here a
    path is its parent's resolution plus one component, and the parents are remembered. One
    resolver serves one tool call, never longer, so a link made afterwards is never missed.
    Windows keeps ``realpath`` for every path: it also corrects case and expands short names."""

    def __init__(self) -> None:
        self._known: dict = {"/": "/"}

    def real(self, text: str) -> "str | None":
        """What ``_real`` returns for ``text``: a normalised absolute path with no ``.``, ``..`` or doubled separators."""
        if WINDOWS or not text.startswith("/"):
            return _real(text)
        known = self._known
        chain = []
        node = text
        while node not in known:
            chain.append(node)
            node = node.rpartition("/")[0] or "/"
        resolved = known[node]
        for node in reversed(chain):
            candidate = resolved.rstrip("/") + "/" + node.rpartition("/")[2]
            try:
                link = stat.S_ISLNK(os.lstat(candidate).st_mode)
            except OSError:
                link = False
            except ValueError:
                return None
            resolved = (_real(candidate) or candidate) if link else candidate
            known[node] = resolved
        return known[text]


def _fold(text: str, fold: bool) -> str:
    return text.lower() if fold else text


@functools.lru_cache(maxsize=64)
def _cached_root_forms(root: str) -> tuple:
    lexical = _normalise(clean(root))
    real = _real(lexical)
    return (lexical,) if real is None or real == lexical else (lexical, real)


def _root_forms(root: "str | Path") -> list:
    return list(_cached_root_forms(posix(root)))


def _relative_to(form: str, roots: list) -> "str | None":
    """``form`` relative to the first root holding it, folding case only where the file system does."""
    fold = case_insensitive_fs()
    folded = _fold(form, fold)
    for base in roots:
        base_folded = _fold(base, fold).rstrip("/")
        if folded == base_folded:
            return ""
        if folded.startswith(base_folded + "/"):
            return form[len(base_folded) + 1:]
    return None


def locate(text: str, root: "str | Path", bases=None, resolver: "Resolver | None" = None) -> Target:
    """Every canonical form of ``text``: relative paths are tried against each of ``bases`` (default: the root).

    A ``resolver`` shared by many calls makes following links cost one look per directory, not one walk per path."""
    roots = _root_forms(root)
    real_of = resolver.real if resolver is not None else _real
    cleaned = clean(text)
    candidates = [cleaned]
    if cleaned.startswith("~"):
        candidates.append(clean(os.path.expanduser(cleaned)))
    absolute: list = []
    for candidate in candidates:
        if _is_abs(candidate):
            absolute.append(_normalise(candidate))
        else:
            for base in (bases or [roots[0]]):
                absolute.append(_normalise(clean(posix(base)).rstrip("/") + "/" + candidate))
    for form in list(absolute):
        real = real_of(form)
        if real is not None:
            absolute.append(_normalise(real))
    seen: dict = {}
    for form in absolute:
        seen.setdefault(form, Form(form, _relative_to(form, roots)))
    return Target(cleaned, tuple(seen.values()))


def normalize_glob(glob: str, root: "str | Path | None" = None) -> "str | None":
    """One spelling of a boundary glob, or None when it names no path the project can hold.

    ``./src/**``, ``src//payments/**``, ``src\\payments\\**`` and the absolute form of a
    path inside the project all become the root-relative ``src/**``. A glob that is
    empty, names the project root itself or climbs out of it cannot be matched and is
    refused here so it is never recorded as a boundary that enforces nothing."""
    text = clean(str(glob).strip())
    if text.startswith("~"):
        text = clean(os.path.expanduser(text))
    if not text:
        return None
    if _is_abs(text):
        text = _normalise(text)
        if root is not None:
            relative = _relative_to(text, _root_forms(root))
            if relative is not None:
                text = relative or "."
    else:
        text = posixpath.normpath(text)
    if text in (".", "") or text == ".." or text.startswith("../"):
        return None
    return text.rstrip("/") if len(text) > 1 else text


def glob_problem(glob: str, root: "str | Path | None" = None) -> "str | None":
    """Why ``glob`` can never match a path anything is about to write, or None when it can.

    ``normalize_glob`` already refuses a glob that names no project path. These are the spellings
    it keeps that match nothing either: a leading ``!`` (gitignore negation, which a boundary does
    not have), the root of a drive or of the file system, and an absolute POSIX path outside the
    project under a top-level directory that does not exist here, which is what ``/src/payments/**``
    is when it was meant relative to the project root. An absolute path under a directory that
    exists is a real boundary outside the project (``/etc/**``) and stays one; so does a drive
    path, which a host on another system reports, and on Windows no leading-slash path is judged."""
    text = clean(str(glob).strip())
    if text.startswith("!"):
        return "a leading '!' is gitignore negation, which a boundary does not have, so nothing can match it; record the paths to protect"
    normal = normalize_glob(glob, root)
    if normal is None:
        return "a boundary glob must name a path inside the project (not '.', not empty, and not climbing out with '..')"
    if not _is_abs(normal):
        return None
    if re.fullmatch(r"(?:[A-Za-z]:/?|/)", normal):
        return "it names the root of a drive or of the file system, which no path is compared against; to freeze the whole project record '**'"
    if not WINDOWS and normal.startswith("/"):
        first = normal.split("/")[1]
        if not _WILDCARD.search(first) and not os.path.isdir("/" + first):
            return (f"it names the absolute path /{first}/..., and no directory /{first} exists on this machine, so it can never match; "
                    f"relative to the project root it is {normal.lstrip('/')}")
    return None


def _variants(glob: str, fold: bool) -> list:
    """The patterns one glob stands for: itself, everything under it, and (for ``dir/**``) the directory."""
    base = glob[:-3] if glob.endswith("/**") else glob
    return [_fold(item, fold) for item in dict.fromkeys((glob, base + "/**", base))]


def _alias_globs(glob: str, root: "str | Path") -> list:
    """The glob re-expressed through the place its literal prefix leads, when a link makes that differ."""
    if _is_abs(glob):
        return []
    segments = glob.split("/")
    cut = next((index for index, part in enumerate(segments) if _WILDCARD.search(part)), len(segments))
    prefix = "/".join(segments[:cut])
    if not prefix:
        return []
    anchored = _root_forms(root)[0] + "/" + prefix
    real = _real(anchored)
    if real is None or real == anchored:
        return []
    rest = "/".join(segments[cut:])
    resolved = real + ("/" + rest if rest else "")
    relative = _relative_to(real, _root_forms(root))
    return [resolved] if relative is None else [relative + ("/" + rest if rest else "")]


def _glob_forms(glob: str, root: "str | Path") -> list:
    return [glob, *_alias_globs(glob, root)]


def _match_forms(target: Target, glob: str, fold: bool) -> bool:
    variants = _variants(glob, fold)
    if _is_abs(glob):
        return any(fnmatch.fnmatchcase(_fold(form, fold), pattern) for form in target.abs for pattern in variants)
    for relative in target.rel:
        for candidate in (relative, "/" + relative):
            if any(fnmatch.fnmatchcase(_fold(candidate, fold), pattern) for pattern in variants):
                return True
    if target.foreign:
        return any(fnmatch.fnmatchcase(_fold(form, fold), "*/" + pattern)
                   for form in target.abs for pattern in variants)
    return False


class Boundary:
    """A recorded glob, normalised and alias-resolved once so many targets can be tested against it."""

    def __init__(self, glob: str, root: "str | Path") -> None:
        self.glob = str(glob)
        self.root = root
        self.normal = normalize_glob(glob, root)
        self.forms = _glob_forms(self.normal, root) if self.normal is not None else []

    def matches(self, target: Target, fold: bool = True) -> bool:
        """True when any form of ``target`` lies on the boundary (the deny direction)."""
        if self.normal is None:
            literal = clean(self.glob)
            patterns = _variants(literal, fold) if literal else []
            return any(fnmatch.fnmatchcase(_fold(text, fold), pattern) for text in (target.raw, *target.abs) for pattern in patterns)
        return any(_match_forms(target, form, fold) for form in self.forms)

    def covers(self, target: Target, fold: bool = True) -> bool:
        """True when ``target`` is the boundary's directory or one above it, so removing or moving it takes the boundary along.

        A glob with no literal prefix (``**/secrets/**``, ``*.tf``) can sit anywhere, so only the
        project root itself covers it."""
        for form in self.forms:
            base = _fold(literal_base(form), fold).rstrip("/")
            candidates = target.abs if _is_abs(form) else target.rel
            if any(item == "" or item == base or base.startswith(item + "/")
                   for item in (_fold(c, fold).rstrip("/") for c in candidates)):
                return True
        return False

    def fragments(self) -> list:
        """Lower-case literal pieces any path in the boundary must contain; empty when the glob is all wildcard."""
        text = self.normal if self.normal is not None else clean(self.glob)
        return [piece.strip("/").lower() for piece in re.split(r"[*?\[\]]+", text) if piece.strip("/")]


def matches(target: Target, glob: str, root: "str | Path", *, fold: bool = True) -> bool:
    """True when any form of ``target`` lies on the boundary ``glob`` (the deny direction)."""
    return Boundary(glob, root).matches(target, fold)


def inside_allowed(target: Target, globs: list, root: "str | Path", *, fold: bool) -> bool:
    """True only when every form ``target`` can take lies inside one of the allow ``globs``.

    A ``..`` that leaves an allowed directory, a same-named directory deeper in the
    tree, a link that points out of the allowed directory and a host path that cannot
    be related to the project each fail; ``fold`` is true only where the file system
    itself ignores case."""
    if not target.forms:
        return False
    normal = [item for item in (normalize_glob(g, root) for g in globs) if item is not None]
    patterns = [form for glob in normal for form in _glob_forms(glob, root)]
    for form in target.forms:
        one = Target(target.raw, (form,))
        if not any(_match_allowed(one, pattern, fold) for pattern in patterns):
            return False
    return True


def _match_allowed(target: Target, glob: str, fold: bool) -> bool:
    """Anchored matching for an allow list: a relative glob matches relative forms only, no suffix rule."""
    variants = _variants(glob, fold)
    if _is_abs(glob):
        return any(fnmatch.fnmatchcase(_fold(form, fold), pattern) for form in target.abs for pattern in variants)
    return any(fnmatch.fnmatchcase(_fold(candidate, fold), pattern)
               for relative in target.rel for candidate in (relative, "/" + relative) for pattern in variants)


def literal_base(glob: str) -> str:
    """The leading path segments of a glob that hold no wildcard: ``src/payments`` for ``src/payments/**``."""
    segments = glob.split("/")
    cut = next((index for index, part in enumerate(segments) if _WILDCARD.search(part)), len(segments))
    return "/".join(segments[:cut])


def covers(target: Target, glob: str, root: "str | Path", *, fold: bool = True) -> bool:
    """True when ``target`` is the boundary's directory or one above it (see ``Boundary.covers``)."""
    return Boundary(glob, root).covers(target, fold)
