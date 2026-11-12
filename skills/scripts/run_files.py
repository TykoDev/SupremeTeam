#!/usr/bin/env python3
"""The sanctioned writer for a run's phase files that have rules of their own.

    python skills/scripts/run_files.py supersede --run-id <run> --phase <phase> \
        --path <file inside the phase> --by-revision <n> [--from-revision <n>]

``supersede`` sets a file of an earlier revision aside so that a resubmission can keep it without the gate reading
it as part of the current package. The contracts tell every owner to preserve superseded artifacts, and the shape
engine reads every file in a phase directory: a preserved ``report_completeness.r1.md`` beside the current
certificate failed lineage as ``MIXED_REVISIONS``, and an old copy under any other name could fill the slot of a
missing current one. There is one place for a superseded file and one record of it:

    <phase>/_superseded/rev-<from revision>/<original path inside the phase>
    <phase>/_superseded/index.json     {"schema_version": 1, "entries": [{path, sha256, from_revision,
                                                                           superseded_by, superseded_at}]}

The gate leaves ``_superseded/`` out of the current package, requires every file in it to be listed in the index
with a matching digest, and refuses evidence that cites a superseded copy. The guard denies any other write into
``_superseded/`` (Rule C), so the index cannot be edited to match a file somebody placed there.

The command refuses, and changes nothing, when: the path is outside ``skillset-saves/runs/<run>/<phase>/``, is not
a regular file, or is reached through a link; the file is already under ``_superseded/``; the file has one writer
of its own (a gate verdict record, the cycle history); ``--by-revision`` is not higher than the
file's revision; or a copy of that path at that revision is already set aside.

``from_revision`` is the ``revision`` in the file's frontmatter, or ``--from-revision`` when it declares none.

Exit 0 with a JSON object on success; exit 1 with ``{"ok": false, "error": ...}`` on a refusal or a failed move;
exit 2 on a usage error or when a module beside this script is missing. Stdlib only.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    import save_taxonomy as taxonomy
    from checkout import checkout_root
    from data_formats import content_sha256
except ImportError as exc:  # a catalog with a file missing: say which, and never look like a refusal
    sys.stderr.write(f"ERROR: run_files.py cannot run: {exc}. A module beside it is missing; reinstall the catalog.\n")
    raise SystemExit(2) from exc

SUPERSEDED = "_superseded"
INDEX = "index.json"
INDEX_SCHEMA = 1
# Files in a phase directory that have a single writer of their own (save-ownership.yaml gate-verdict): setting one
# aside would take a verdict or a boundary's REVISE history out of the gate's sight.
SINGLE_WRITER = ("verdict_*.json", "verdict_*.md", "verdict_*.cycles.lock")
LOCK_WAIT_SECONDS = 10.0
LOCK_STALE_SECONDS = 120.0

_FRONTMATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_REVISION_LINE = re.compile(r"^revision[ \t]*:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_REVISION = re.compile(r"r?(\d+)", re.IGNORECASE)


class Refused(ValueError):
    """The request is not one this writer performs. Nothing was changed."""


def revision_number(value: object) -> "int | None":
    """A revision as a number: ``3``, ``"3"`` and ``"r3"`` are all revision 3. Anything else is None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    match = _REVISION.fullmatch(str(value).strip().strip("'\"")) if value is not None else None
    return int(match.group(1)) if match else None


def declared_revision(path: Path) -> "int | None":
    """The ``revision`` in a file's leading frontmatter block, or None when it declares none or is not text."""
    try:
        head = path.read_bytes()[:65536].decode("utf-8", "replace")
    except OSError:
        return None
    block = _FRONTMATTER.match(head)
    line = _REVISION_LINE.search(block.group(1)) if block else None
    return revision_number(line.group(1)) if line else None


def phase_directory(project_root: Path, run_id: str, phase: str) -> Path:
    if not taxonomy.RUN_ID.fullmatch(run_id or ""):
        raise Refused(f"run_id must be {taxonomy.RUN_ID_RULE}, got {run_id!r}")
    if phase not in taxonomy.PHASE_DIRECTORIES:
        raise Refused(f"phase must be one of {sorted(taxonomy.PHASE_DIRECTORIES)}, got {phase!r}")
    return project_root.resolve() / "skillset-saves" / "runs" / run_id / phase


def _inside(path: Path, directory: Path) -> "Path | None":
    """``path`` relative to ``directory`` when it lies inside it by its own spelling, else None."""
    try:
        relative = path.relative_to(directory)
    except ValueError:
        return None
    return None if ".." in relative.parts or not relative.parts else relative


def _has_link(path: Path, directory: Path) -> bool:
    """Whether any component from ``directory`` down to ``path`` is a symlink or a junction."""
    current = directory
    for part in path.relative_to(directory).parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            return True
    return False


def read_index(phase_dir: Path) -> list:
    """The entries of ``<phase>/_superseded/index.json``; an absent index is empty. Raises ``Refused`` when the file
    exists and cannot be read as the record this writer makes: it is never overwritten on a guess."""
    path = phase_dir / SUPERSEDED / INDEX
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"{path} cannot be read as JSON ({type(exc).__name__}); it is not overwritten") from exc
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise Refused(f"{path} is not a superseded-copies index (no list of entries); it is not overwritten")
    return entries


def _write_index(phase_dir: Path, entries: list) -> None:
    path = phase_dir / SUPERSEDED / INDEX
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{INDEX}.{os.getpid()}.tmp")
    text = json.dumps({"schema_version": INDEX_SCHEMA, "entries": entries}, indent=2, sort_keys=True) + "\n"
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


class _IndexLock:
    """One writer at a time per phase: an exclusive lock file beside the index, broken when it is stale."""

    def __init__(self, phase_dir: Path) -> None:
        self.path = phase_dir / SUPERSEDED / f"{INDEX}.lock"

    def __enter__(self) -> "_IndexLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + LOCK_WAIT_SECONDS
        while True:
            try:
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > LOCK_STALE_SECONDS:
                        self.path.unlink()
                        continue
                except OSError:
                    continue
                if time.monotonic() >= deadline:
                    raise Refused(f"another run_files.py holds {self.path}; run the command again") from None
                time.sleep(0.05)

    def __exit__(self, *exc_info) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


def supersede(project_root: Path, run_id: str, phase: str, path: str, by_revision: object,
              from_revision: object = None, *, now: "datetime | None" = None) -> dict:
    """Move one file of an earlier revision to ``_superseded/rev-<n>/`` and record it. Returns the index entry and
    where the file went. Raises ``Refused`` (nothing changed) or ``OSError`` (the move failed and was undone)."""
    phase_dir = phase_directory(project_root, run_id, phase)
    if not phase_dir.is_dir():
        raise Refused(f"{phase_dir} does not exist")
    given = Path(path)
    source = given if given.is_absolute() else phase_dir / given
    source = Path(os.path.normpath(source))
    relative = _inside(source, phase_dir)
    if relative is None:
        raise Refused(f"{path!r} is not inside {phase_dir}: only a file of this run's {phase} phase can be superseded here")
    if relative.parts[0].casefold() == SUPERSEDED:
        raise Refused(f"{relative.as_posix()} is already under {SUPERSEDED}/")
    if _has_link(source, phase_dir):
        raise Refused(f"{relative.as_posix()} is reached through a link; name the file itself")
    if not source.is_file():
        raise Refused(f"{relative.as_posix()} is not a file in {phase_dir}")
    if len(relative.parts) == 1 and any(fnmatch.fnmatchcase(relative.name.lower(), pattern) for pattern in SINGLE_WRITER):
        raise Refused(f"{relative.name} has a single writer of its own (harness/gatekeeper/check.py --verdict-out) and is "
                      "not superseded by hand")
    target_revision = revision_number(by_revision)
    if target_revision is None:
        raise Refused(f"--by-revision must be a revision number such as 3 or r3, got {by_revision!r}")
    declared = declared_revision(source)
    named = revision_number(from_revision) if from_revision is not None else None
    if from_revision is not None and named is None:
        raise Refused(f"--from-revision must be a revision number such as 2 or r2, got {from_revision!r}")
    if declared is not None and named is not None and declared != named:
        raise Refused(f"{relative.as_posix()} declares revision {declared} in its frontmatter, not {named}")
    origin = declared if declared is not None else named
    if origin is None:
        raise Refused(f"{relative.as_posix()} declares no revision in its frontmatter; say which revision it belongs to "
                      "with --from-revision")
    if target_revision <= origin:
        raise Refused(f"--by-revision {target_revision} is not higher than the file's revision {origin}: a file is "
                      "superseded by a later revision, never by its own or an earlier one")
    destination = phase_dir / SUPERSEDED / f"rev-{origin}" / relative
    with _IndexLock(phase_dir):
        entries = read_index(phase_dir)
        if destination.exists():
            raise Refused(f"{SUPERSEDED}/rev-{origin}/{relative.as_posix()} already exists; that revision of the file "
                          "was superseded before")
        digest = content_sha256(source)
        entry = {"path": relative.as_posix(), "sha256": digest, "from_revision": origin, "superseded_by": target_revision,
                 "superseded_at": (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        try:
            _write_index(phase_dir, [*entries, entry])
        except OSError:
            # The index is what makes the copy legitimate: without the entry the file goes back where it was.
            os.replace(destination, source)
            raise
    return {"entry": entry, "moved_to": destination, "index": phase_dir / SUPERSEDED / INDEX}


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Sanctioned writer for a run's phase files.")
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("supersede", help="set a file of an earlier revision aside under <phase>/_superseded/ and index it")
    cmd.add_argument("--project-root", default=None,
                     help="the project that holds skillset-saves/ (default: the working directory, or its main checkout "
                          "when that is a linked git worktree)")
    cmd.add_argument("--run-id", required=True)
    cmd.add_argument("--phase", required=True)
    cmd.add_argument("--path", required=True, help="the file, relative to the phase directory or absolute inside it")
    cmd.add_argument("--by-revision", required=True, help="the revision that supersedes the file (3 or r3)")
    cmd.add_argument("--from-revision", default=None,
                     help="the file's own revision, when its frontmatter declares none")
    args = parser.parse_args(argv)
    root = Path(args.project_root) if args.project_root else Path(checkout_root(Path.cwd()))
    try:
        done = supersede(root, args.run_id, args.phase, args.path, args.by_revision, args.from_revision)
    except Refused as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"the file could not be moved ({type(exc).__name__}: {exc}); nothing was changed"}))
        return 1
    base = root.resolve()
    print(json.dumps({"ok": True, "command": "supersede", "superseded": done["entry"],
                      "moved_to": done["moved_to"].relative_to(base).as_posix(),
                      "index": done["index"].relative_to(base).as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
