#!/usr/bin/env python3
"""Build (or dry-run) the Supreme Team distribution archive and verify its contents.

Ignore rules do not control what a packager includes; this script enumerates
the files that ``skills/package-manifest.yaml`` selects from the chosen root,
rejects runtime residue classes, confirms required assets are present, and
optionally writes the archive.

    python skills/scripts/package_check.py --root . [--out .harness-state/packages/supremeteam.zip]

Matching is case-insensitive on every host, so ``.ENV`` is the same secret as
``.env``. A required asset is matched by its exact name, because that is the name
the catalog opens it by. A link (a symlink, a Windows junction, or another reparse
point whose tag names another path, such as a WSL symlink) is a violation of class
``symlink``, never a file or a directory to walk into: the archive would carry the
bytes of whatever it points at under an innocent name. A reparse point that is not
a link, such as a OneDrive placeholder for a file not downloaded yet, is packaged
like any other file. The contents of a nested ``.git/`` directory are a violation too (a
vendored repository ships its whole history); the root ``.git`` is the checkout's
own and is never selected.

The secret and run-state names (the ``secrets``, ``runtime-state`` and
``save-state`` classes) are read from ``skill-maker/skill-creator/scripts/
residue-classes.json``, the list the skill packager refuses by as well, so a
name added there is caught by both.

``--out`` writes the archive to ``<out>.tmp`` and moves it into place only when it
is complete. A selected file that cannot be read, or an archive that cannot be
written, removes the temporary file and leaves whatever was at ``--out`` as it was.

Exit 0 when the enumerated set is clean, 1 when residue or a missing required
file is found, 2 on manifest/engine error, including a manifest that is not a
mapping of string lists, a residue list that cannot be read, a directory that
cannot be listed, or an archive that cannot be written. The JSON report lists
every violation with the class it matched.
"""
from __future__ import annotations

import argparse
import contextlib
import fnmatch
import json
import os
import sys
import zipfile
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1]
if str(SKILLS / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import load_data  # noqa: E402
from file_safety import is_link  # noqa: E402

# The skill packager refuses the same secret and run-state names, and it must run
# without this directory, so the list lives with it and is read from there.
SHARED_RESIDUE_FILE = SKILLS / "skill-maker" / "skill-creator" / "scripts" / "residue-classes.json"
SHARED_RESIDUE_CLASSES = ("runtime-state", "save-state", "secrets")


def shared_residue(path: Path = SHARED_RESIDUE_FILE) -> dict[str, list[str]]:
    """The residue names package_skill.py also refuses, or a ValueError naming what is wrong with the file."""
    try:
        data = load_data(path)
    except ValueError as exc:  # DataFormatError is a ValueError
        raise ValueError(f"cannot use the residue list {path}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or set(data) != set(SHARED_RESIDUE_CLASSES)
        or not all(isinstance(names, list) and names and all(isinstance(name, str) and name for name in names)
                   for names in data.values())
    ):
        raise ValueError(f"{path} must map {', '.join(SHARED_RESIDUE_CLASSES)} to non-empty lists of names")
    return data


def tree_globs(directories: list[str]) -> list[str]:
    """Every file under each named directory, at the root and at any depth."""
    return [glob for name in directories for glob in (f"{name}/**", f"**/{name}/**")]


try:
    _SHARED = shared_residue()
except ValueError as exc:  # DataFormatError is a ValueError
    print(json.dumps({"ok": False, "engine_error": str(exc)}))
    raise SystemExit(2) from exc

RESIDUE_CLASSES = {
    "interpreter-cache": ["**/__pycache__/**", "**/*.pyc"],
    "runtime-state": tree_globs(_SHARED["runtime-state"]),
    "save-state": tree_globs(_SHARED["save-state"]),
    "test-scratch": ["harness-test-work/**", "**/harness-test-work/**", "gatekeeper-test-work/**", "**/gatekeeper-test-work/**", "**/.harness-state/test-work/**"],
    "render-scratch": [".playwright-mcp/**", "**/.playwright-mcp/**"],
    # Coverage data and reports are run evidence under
    # skillset-saves/runs/*/*/evidence/coverage/ (output_paths.py --kind coverage),
    # never project-root residue and never part of a package.
    "coverage-residue": ["**/.coverage", "**/.coverage.*", "**/.coverage/**", "**/htmlcov/**", "**/.nyc_output/**"],
    "eval-workspace": ["**/*-workspace/**", "**/evals/workspace/**"],
    "archives": ["**/*.skill", "**/*.zip"],
    "vcs-metadata": ["**/.git/**"],
    "secrets": [f"**/{name}" for name in _SHARED["secrets"]],
}
REQUIRED_ASSET_GLOBS = [
    "skills/gates.yaml",
    "skills/pipelines.yaml",
    "skills/ownership.yaml",
    "skills/save-ownership.yaml",
    "skills/team-manifest.yaml",
    "skills/runtime-manifest.yaml",
    "skills/tech-stacks/registry.yaml",
    "skills/harness/gatekeeper/check.py",
    "skills/harness/hooks/save_run.py",
]


def matches(relative: str, patterns: list[str]) -> bool:
    """Glob match that folds case: fnmatch alone is case-sensitive on POSIX, so `.ENV` passed."""
    folded = relative.lower()
    for pattern in patterns:
        pattern = pattern.lower()
        if fnmatch.fnmatchcase(folded, pattern):
            return True
        # Unlike fnmatch, a recursive glob also matches zero directories.
        while pattern.startswith("**/"):
            pattern = pattern[3:]
            if fnmatch.fnmatchcase(folded, pattern):
                return True
    return False


def enumerate_tree(root: Path) -> list[tuple[str, bool]]:
    """Every file and every link under ``root``: its relative POSIX path, and whether it is a link.

    ``Path.rglob`` walks into a Windows junction, which ``is_symlink()`` does not
    report, so the archive took files from wherever one pointed. Here a link is a
    leaf, never entered. The root's own ``.git`` is the checkout's and is skipped.
    Raises OSError when a directory cannot be listed: a tree that was not read in
    full cannot be called clean.
    """
    entries: list[tuple[str, bool]] = []
    pending = [root]
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            if directory == root and path.name == ".git":
                continue
            if is_link(path):
                entries.append((path.relative_to(root).as_posix(), True))
            elif path.is_dir():
                pending.append(path)
            elif path.is_file():
                entries.append((path.relative_to(root).as_posix(), False))
    return entries


def write_archive(root: Path, selected: list[str], out: Path) -> None:
    """Zip the ``selected`` files of ``root`` into ``out``, which only a complete archive replaces.

    The archive was written in place, so a file it could not read ended the run in
    a traceback with half an archive at ``out``. It is built in ``<out>.tmp`` now and
    moved into place in one step. Each file is read whole before it is added, so
    a read that fails is told apart from a write that fails. Raises OSError, after
    removing the temporary file; a file that could not be read is named in it.
    """
    temporary = out.with_name(out.name + ".tmp")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for relative in sorted(selected):
                source = root / relative
                try:
                    info, data = zipfile.ZipInfo.from_file(source, relative), source.read_bytes()
                except OSError as exc:
                    raise OSError(f"cannot read {relative}: {exc}") from exc
                archive.writestr(info, data, zipfile.ZIP_DEFLATED)
        os.replace(temporary, out)
    except BaseException:
        with contextlib.suppress(OSError):
            temporary.unlink()
        raise


def manifest_globs(manifest: object) -> tuple[list[str], list[str]]:
    """The include and exclude globs, or a ValueError naming what is wrong with the manifest."""
    if not isinstance(manifest, dict):
        raise ValueError("package manifest root must be a mapping")
    globs = []
    for key, default in (("include", ["**/*"]), ("exclude", [])):
        value = manifest.get(key, default)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ValueError(f"package manifest {key} must be a list of non-empty strings")
        globs.append(value)
    return globs[0], globs[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Enumerate and verify the Supreme Team package.")
    parser.add_argument("--root", default=".",
                        help="the directory to package: the repository root, the directory that contains skills/, "
                             "not skills/ itself (default: the current directory)")
    parser.add_argument("--manifest", default=str(SKILLS / "package-manifest.yaml"))
    parser.add_argument("--out", help="write a zip archive here after a clean enumeration")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        include, exclude = manifest_globs(load_data(Path(args.manifest)))
    except ValueError as exc:  # DataFormatError is a ValueError
        print(json.dumps({"ok": False, "engine_error": str(exc)}))
        return 2
    try:
        entries = enumerate_tree(root)
    except OSError as exc:
        print(json.dumps({"ok": False, "engine_error": f"cannot enumerate {root}: {exc}"}))
        return 2
    selected: list[str] = []
    violations = []
    for relative, link in entries:
        if not matches(relative, include):
            continue
        if matches(relative, exclude):
            continue
        if link:
            violations.append({"path": relative, "class": "symlink"})
        else:
            selected.append(relative)
    for relative in selected:
        for klass, patterns in RESIDUE_CLASSES.items():
            if matches(relative, patterns):
                violations.append({"path": relative, "class": klass})
                break
    violations.sort(key=lambda violation: violation["path"])
    missing = [glob for glob in REQUIRED_ASSET_GLOBS if not any(fnmatch.fnmatchcase(rel, glob) for rel in selected)]
    ok = not violations and not missing
    report = {"ok": ok, "root": str(root), "selected_count": len(selected), "violations": violations, "missing_required": missing}
    if ok and args.out:
        out = Path(args.out).resolve()
        try:
            write_archive(root, selected, out)
        except OSError as exc:
            print(json.dumps({"ok": False, "engine_error": f"cannot write the archive {out}: {exc}"}))
            return 2
        report["archive"] = str(out)
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
