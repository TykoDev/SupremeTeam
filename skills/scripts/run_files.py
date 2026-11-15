#!/usr/bin/env python3
"""The sanctioned writer for a run's phase files that have rules of their own.

    python skills/scripts/run_files.py write --run-id <run> --phase <phase> \
        --kind reports|artifacts|evidence --name <file> [--from FILE]
    python skills/scripts/run_files.py supersede --run-id <run> --phase <phase> \
        --path <file inside the phase> --by-revision <n> [--from-revision <n>]

``write`` puts a report, an artifact or an evidence file into a run, from the content on standard input or from
``--from FILE``. It exists for the delegate that cannot write the file any other way. A sub-agent the host isolates in
a linked git worktree has no run directory of its own (``skillset-saves/`` is git-ignored, so it is in the main
checkout only); Claude Code refuses its edit tool on a path in the main checkout; and a destination built at run time
(``cat > "$(output_paths.py ...)"``) is one the guard cannot place and denies. The command resolves the destination
through ``output_paths.resolve()`` against the main checkout, whichever tree it is run from, so the same line works
in both. A script's arguments are not write targets to the guard, so the command applies the guard's boundaries to
itself: it refuses

* a kind with one writer of its own (``core``, ``verdict``, ``guards``, ``trajectory``, the preferences) and any path
  ``save-ownership.yaml`` does not give to a delegated specialist (the manifest, a package, the intake log);
* a run that has no directory, a destination reached through a link, and a ``--project-root`` that is a linked
  worktree;
* a destination a frozen or blocked glob of the guard record covers, or that an unreleased read-only record's allow
  list leaves out (another run's directory, for one).

It writes the file in one step and prints the JSON object ``output_paths.py`` prints for the same destination, with
the file's ``sha256`` and size.

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

Exit 0 with a JSON object on success; exit 1 with ``{"ok": false, "error": ...}`` on a refusal or a failed write or
move; exit 2 on a usage error, or when a module or contract this script reads is missing. Stdlib only.
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
# The guard's own readers of its record and of a path: ``write`` holds itself to the boundaries they describe.
HOOKS_DIR = SCRIPT_DIR.parent / "harness" / "hooks"
for _directory in (HOOKS_DIR, SCRIPT_DIR):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

try:
    import _fsutil
    import _paths
    import _state
    import output_paths
    import save_taxonomy as taxonomy
    from checkout import checkout_root
    from data_formats import content_sha256, load_data
except ImportError as exc:  # a catalog with a file missing: say which, and never look like a refusal
    sys.stderr.write(f"ERROR: run_files.py cannot run: {exc}. A catalog file it imports is missing; reinstall the catalog.\n")
    raise SystemExit(2) from exc

SUPERSEDED = "_superseded"
INDEX = "index.json"
INDEX_SCHEMA = 1
# Files in a phase directory that have a single writer of their own (save-ownership.yaml gate-verdict): setting one
# aside would take a verdict or a boundary's REVISE history out of the gate's sight.
SINGLE_WRITER = ("verdict_*.json", "verdict_*.md", "verdict_*.cycles.lock")
LOCK_WAIT_SECONDS = 10.0
LOCK_STALE_SECONDS = 120.0

# ``write``: the path policy it reads, the writer it serves, and the kinds that have a writer of their own.
OWNERSHIP = SCRIPT_DIR.parent / "save-ownership.yaml"
DELEGATE_WRITER = "phase-lead-or-delegated-specialist"
OWNED_KINDS = {
    "core": "harness/hooks/save_run.py",
    "verdict": "harness/gatekeeper/check.py --verdict-out",
    "guards": "harness/hooks/guard_state.py",
    "trajectory": "the post-tool hook",
    "project_preferences": "taste/taste_prefs.py",
    "global_preferences": "taste/taste_prefs.py",
}

_FRONTMATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_REVISION_LINE = re.compile(r"^revision[ \t]*:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_REVISION = re.compile(r"r?(\d+)", re.IGNORECASE)


class Refused(ValueError):
    """The request is not one this writer performs. Nothing was changed."""


class CannotRun(RuntimeError):
    """A contract this writer has to read is missing or unreadable. Nothing was changed, and nothing was decided."""


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


def ownership_classes() -> list:
    """The path classes of ``save-ownership.yaml``, in the order the file gives them (a narrower class comes first)."""
    try:
        classes = load_data(OWNERSHIP).get("classes")
    except Exception as exc:  # absent, unreadable, or not the mapping it should be
        raise CannotRun(f"{OWNERSHIP} cannot be read ({type(exc).__name__}: {exc})") from exc
    if not isinstance(classes, list) or not classes:
        raise CannotRun(f"{OWNERSHIP} declares no path classes")
    return [entry for entry in classes if isinstance(entry, dict)]


def _pattern_matches(relative: str, pattern: str) -> bool:
    """A policy pattern against a project-relative path, one segment at a time: ``*`` stays inside its segment, and
    only a pattern that ends in ``/*`` reaches the files below that directory. Matched as one string,
    ``runs/*/*/report_*.md`` would take ``runs/r1/review/packages/report_x.md`` for a phase report."""
    parts, wanted = relative.split("/"), pattern.split("/")
    if len(parts) < len(wanted) or (len(parts) > len(wanted) and wanted[-1] != "*"):
        return False
    return all(fnmatch.fnmatchcase(part, want) for part, want in zip(parts, wanted, strict=False))


def owning_class(relative: str, classes: list) -> "dict | None":
    """The first class whose pattern matches a project-relative path, which is the narrowest: the file lists the
    intake log before the phase reports its two paths also match."""
    for entry in classes:
        patterns = entry.get("patterns")
        if isinstance(patterns, list) and any(_pattern_matches(relative, str(pattern)) for pattern in patterns):
            return entry
    return None


def guard_refusal(root: Path, target: Path, relative: str) -> "str | None":
    """Why the guard record forbids this destination, or None. The guard reads a script's arguments as arguments,
    never as write targets, so it cannot hold this command to a boundary; the command reads the record itself, with
    the guard's own matching, and refuses what an edit tool would be refused."""
    state = _state.load_guard_state(root)
    located = _paths.locate(target.as_posix(), root)
    fold = _paths.case_insensitive_fs()
    for key, kind in (("frozen_globs", "frozen"), ("blocked_globs", "blocked")):
        for glob in state.get(key) or []:
            if isinstance(glob, str) and glob and _paths.Boundary(glob, root).matches(located):
                return (f"{relative} is inside a {kind} boundary ({_state.safe_text(glob)}); it is lifted through the "
                        "unfreeze skill, not written around")
    records = state.get("read_only") or []
    allow = _state.read_only_allow(records)
    if records and not _paths.inside_allowed(located, allow, root, fold=fold):
        runs = ", ".join(_state.safe_text(record.get("run_id", "?"), 60) for record in records)
        return (f"{relative} is outside what the read-only record of run {runs} allows ({', '.join(allow)}); only that "
                "run's own save path may change")
    return None


def write(project_root: Path, run_id: str, phase: str, kind: str, name: str, data: bytes) -> dict:
    """Write ``data`` to the destination ``output_paths.resolve()`` gives for the run, phase, kind and name. Returns
    what was written. Raises ``Refused`` (nothing changed), ``CannotRun`` or ``OSError`` (the write failed)."""
    root = Path(project_root).resolve()
    main = Path(os.path.realpath(checkout_root(root)))
    if main != Path(os.path.realpath(root)):
        raise Refused(f"{root} is a linked git worktree, and a run's files are in the main checkout only ({main}). Leave "
                      "--project-root out, or name that directory")
    if kind in OWNED_KINDS:
        raise Refused(f"kind {kind!r} has one writer of its own ({OWNED_KINDS[kind]}); run_files.py write never writes it")
    try:
        target = output_paths.resolve(root, kind, run_id=run_id, phase=phase, name=name)
    except ValueError as exc:
        raise Refused(str(exc)) from exc
    if not isinstance(target, Path):
        raise Refused(f"kind {kind!r} does not name one file in a run")
    relative = target.relative_to(root).as_posix()
    owner = owning_class(relative, ownership_classes())
    if owner is None or owner.get("writer") != DELEGATE_WRITER or owner.get("tool"):
        writer = (owner.get("tool") or owner.get("writer") or "another writer") if owner else "no class of save-ownership.yaml"
        raise Refused(f"{relative} (kind {kind!r}) is not a path a delegated specialist writes: it belongs to {writer}. "
                      "This command writes reports, artifacts and evidence")
    run_dir = root / "skillset-saves" / "runs" / run_id
    if not run_dir.is_dir():
        raise Refused(f"run {run_id} has no directory in {root} (skillset-saves/runs/{run_id}/); a file is written into "
                      "a run that exists, so check the run id and the project root")
    if _has_link(target, root):
        raise Refused(f"{relative} is reached through a link; the run's own directories are written, never what one "
                      "points at")
    if target.is_dir():
        raise Refused(f"{relative} is a directory; --name has to name a file")
    if not data:
        raise Refused("there is nothing to write: the content was empty. Pipe it on standard input or name --from FILE")
    reason = guard_refusal(root, target, relative)
    if reason:
        raise Refused(reason)
    replaced = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    _fsutil.atomic_write(target, data)
    return {"kind": kind, "path": target, "relative": relative, "bytes": len(data), "sha256": content_sha256(target),
            "replaced": replaced}


def _content(source: "str | None") -> bytes:
    """The bytes to write: the file ``--from`` names, else standard input. Raises ``Refused`` when there is neither."""
    if source:
        try:
            return Path(source).read_bytes()
        except OSError as exc:
            raise Refused(f"--from {source!r} cannot be read ({type(exc).__name__})") from exc
    stream = sys.stdin
    if stream is None or stream.isatty():
        raise Refused("there is no content: pipe it on standard input (a heredoc, a pipe) or name --from FILE")
    return stream.buffer.read()


def _project_root(given: "str | None") -> Path:
    """The checkout that holds the runs: a linked worktree, named or defaulted, is read as its main checkout, as
    ``output_paths.py`` reads it."""
    return Path(checkout_root(Path(given) if given else Path.cwd()))


_ROOT_HELP = ("the project that holds skillset-saves/ (default: the working directory); a linked git worktree is read "
              "as its main checkout")


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Sanctioned writer for a run's phase files.")
    commands = parser.add_subparsers(dest="command", required=True)
    put = commands.add_parser(
        "write", help="write a report, an artifact or an evidence file into a run, from standard input or --from FILE",
        description="Write one file into a run of the main checkout. The content is read as bytes from standard input, "
                    "or from --from FILE. Windows PowerShell 5.1 re-encodes text it pipes to a program as ASCII unless "
                    "$OutputEncoding is set to UTF-8; a heredoc in bash and a pipe in PowerShell 7 pass UTF-8 through.")
    put.add_argument("--project-root", default=None, help=_ROOT_HELP)
    put.add_argument("--run-id", required=True)
    put.add_argument("--phase", required=True)
    put.add_argument("--kind", required=True,
                     help="reports, artifacts or evidence (phase_report and coverage are taken too; a kind with a "
                          "writer of its own is refused)")
    put.add_argument("--name", required=True, help="the file, relative to the kind's directory")
    put.add_argument("--from", dest="source", default=None, help="read the content from this file instead of standard input")
    cmd = commands.add_parser("supersede", help="set a file of an earlier revision aside under <phase>/_superseded/ and index it")
    cmd.add_argument("--project-root", default=None, help=_ROOT_HELP)
    cmd.add_argument("--run-id", required=True)
    cmd.add_argument("--phase", required=True)
    cmd.add_argument("--path", required=True, help="the file, relative to the phase directory or absolute inside it")
    cmd.add_argument("--by-revision", required=True, help="the revision that supersedes the file (3 or r3)")
    cmd.add_argument("--from-revision", default=None,
                     help="the file's own revision, when its frontmatter declares none")
    args = parser.parse_args(argv)
    root = _project_root(args.project_root)
    if args.command == "write":
        try:
            done = write(root, args.run_id, args.phase, args.kind, args.name, _content(args.source))
        except Refused as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 1
        except CannotRun as exc:
            sys.stderr.write(f"ERROR: run_files.py cannot run: {exc}. Reinstall the catalog.\n")
            return 2
        except OSError as exc:
            print(json.dumps({"ok": False, "error": f"the file could not be written ({type(exc).__name__}: {exc}); "
                                                    "the destination is as it was"}))
            return 1
        print(json.dumps({"ok": True, "command": "write", **done, "path": str(done["path"])}))
        return 0
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
