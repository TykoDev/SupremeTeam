"""Shared utilities for skill-creator scripts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# A directory is a project when it holds Claude Code's own config directory, a git
# checkout, or a harness root (save-ownership.yaml generated_roots).
PROJECT_MARKERS = (".claude", ".git", ".harness-state", "skillset-saves")

# winnt.h IO_REPARSE_TAG_MOUNT_POINT, which marks a junction. The stat module only
# defines it on Windows, and this check has to be importable everywhere.
MOUNT_POINT_REPARSE_TAG = 0xA0000003

# The secret and run-state names the packager refuses. skills/scripts/package_check.py reads
# the same file, which is how the two lists stay one list.
RESIDUE_CLASSES_FILE = Path(__file__).with_name("residue-classes.json")
RESIDUE_CLASS_NAMES = ("runtime-state", "save-state", "secrets")


class ProjectRootError(Exception):
    """No project directory could be determined safely."""


def configure_stdout() -> None:
    """Write UTF-8 to stdout and stderr, so a cp1252 Windows pipe cannot raise on a path or model text."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def is_link(path: Path) -> bool:
    """True for a symlink or a Windows junction, on every supported interpreter.

    Path.is_junction() arrived in Python 3.12 and the packager must also run on older
    ones, where a junction is the mount-point reparse tag that only Windows reports.
    eval-viewer/generate_review.py carries the same function because it runs standalone.
    """
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None:
        return is_junction()
    try:
        return getattr(path.lstat(), "st_reparse_tag", 0) == MOUNT_POINT_REPARSE_TAG
    except OSError:
        return False


def load_residue_classes() -> dict[str, list[str]]:
    """The directory and file names the packager refuses, by residue class.

    Raises ValueError when the list cannot be read or is malformed: a protection
    that cannot read its list must stop, not refuse nothing.
    """
    try:
        data = json.loads(RESIDUE_CLASSES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read {RESIDUE_CLASSES_FILE}: {exc}") from exc
    if (
        not isinstance(data, dict)
        or set(data) != set(RESIDUE_CLASS_NAMES)
        or not all(
            isinstance(names, list) and names and all(isinstance(name, str) and name for name in names)
            for names in data.values()
        )
    ):
        raise ValueError(f"{RESIDUE_CLASSES_FILE} must map {', '.join(RESIDUE_CLASS_NAMES)} to non-empty lists of names")
    return data


def find_project_root(explicit: Path | None = None, start: Path | None = None) -> Path:
    """The directory tools write into and run `claude -p` from.

    An explicit directory is used as given. Otherwise the nearest ancestor of
    `start` (default: the working directory) that holds a project marker wins.
    The home directory and filesystem roots never qualify however they are
    reached: every user's home holds a `.claude/`, so walking up from anywhere
    below it would land there and write `~/.claude/commands`.
    """
    home = Path.home().resolve()
    if explicit is not None:
        root = Path(explicit).resolve()
        if not root.is_dir():
            raise ProjectRootError(f"project root is not a directory: {root}")
        if root == home or root == root.parent:
            raise ProjectRootError(f"refusing {root} as a project root: it is the home directory or a filesystem root")
        return root

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if candidate == home or candidate == candidate.parent:
            continue
        if any((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate
    raise ProjectRootError(
        f"no project root found above {current} (looked for {', '.join(PROJECT_MARKERS)}; "
        "the home directory never counts)"
    )


def parse_skill_md(skill_path: Path) -> tuple[str, str, str]:
    """Parse a SKILL.md file, returning (name, description, full_content)."""
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    lines = content.split("\n")

    if lines[0].strip() != "---":
        raise ValueError("SKILL.md missing frontmatter (no opening ---)")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        raise ValueError("SKILL.md missing frontmatter (no closing ---)")

    name = ""
    description = ""
    frontmatter_lines = lines[1:end_idx]
    i = 0
    while i < len(frontmatter_lines):
        line = frontmatter_lines[i]
        if line.startswith("name:"):
            name = line[len("name:"):].strip().strip('"').strip("'")
        elif line.startswith("description:"):
            value = line[len("description:"):].strip()
            # Handle YAML multiline indicators (>, |, >-, |-)
            if value in (">", "|", ">-", "|-"):
                continuation_lines: list[str] = []
                i += 1
                while i < len(frontmatter_lines) and (frontmatter_lines[i].startswith("  ") or frontmatter_lines[i].startswith("\t")):
                    continuation_lines.append(frontmatter_lines[i].strip())
                    i += 1
                description = " ".join(continuation_lines)
                continue
            else:
                description = value.strip('"').strip("'")
        i += 1

    return name, description, content
