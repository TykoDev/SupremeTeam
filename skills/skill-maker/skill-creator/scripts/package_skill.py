#!/usr/bin/env python3
"""Skill packager - build a distributable .skill archive from a skill folder.

Run as a module from the skill-creator directory, so the `scripts` package
resolves:

    cd skills/skill-maker/skill-creator
    python -m scripts.package_skill <path/to/skill-folder> [output-directory]

Relative paths resolve against the working directory, which is skill-creator/
after that `cd`, not the project root. Pass the output directory as an absolute
path: a run's packages belong in
<project root>/skillset-saves/runs/<run-id>/skill-creation/packages. The packager
refuses to write inside skill-creator/, so a relative run path cannot silently
land beside the source instead of in the run.

Example:
    python -m scripts.package_skill ../../review/security-review
    python -m scripts.package_skill ../../review/security-review \\
        /abs/path/to/project/skillset-saves/runs/<run-id>/skill-creation/packages

Inputs:
    path/to/skill-folder  directory containing SKILL.md
    output-directory      optional; defaults to <project>/.harness-state/packages/,
                          <project> being the nearest ancestor of the working
                          directory holding .claude, .git, .harness-state or
                          skillset-saves (never the home directory)

Output:
    <output-directory>/<folder-name>.skill - a ZIP archive rooted at the skill
    folder name. evals/ at the root, .git, node_modules, __pycache__, *.pyc and
    .DS_Store are skipped.

Refused, listing every offender and writing nothing: a symlink or junction
anywhere in the folder (its target's bytes would be zipped under an innocent
name), a secret (.env, .env.*, *.pem, *.key) or run state (.harness-state,
skillset-saves). These are the residue classes of skills/scripts/package_check.py
that can occur in a skill folder; they are refused rather than skipped so that
the folder gets cleaned instead of hiding the next one.

Exit codes:
    0  the archive was written; its path is printed
    1  the skill folder is missing, is not a directory, has no SKILL.md,
       fails quick_validate, holds something refused above, the output
       location is unusable, or the archive could not be created
"""

import fnmatch
import sys
import zipfile
from pathlib import Path
from scripts.quick_validate import validate_skill
from scripts.utils import ProjectRootError, configure_stdout, find_project_root

# Skipped without comment: regenerable, or owned by another tool.
EXCLUDE_DIRS = {"__pycache__", "node_modules", ".git"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}
# Directories excluded only at the skill root (not when nested deeper).
ROOT_EXCLUDE_DIRS = {"evals"}
# Refused, not skipped: a secret or run state in the source folder is a defect
# to remove, and skipping it would hide the next one (package_check.py's stance).
REFUSE_DIRS = {".harness-state", "skillset-saves"}
REFUSE_GLOBS = {".env", ".env.*", "*.pem", "*.key"}

# Phase 6 runs from this directory, so a relative run path would resolve into it.
CREATOR_DIR = Path(__file__).resolve().parents[1]


def _default_output_dir() -> Path:
    """Packages built outside a run go under the project's .harness-state/packages/.

    Raises ProjectRootError when the working directory is inside no project: the
    alternative is the working directory itself, which for an installed skill is
    the skill's own directory.
    """
    return find_project_root() / ".harness-state" / "packages"


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def should_exclude(rel_path: Path) -> bool:
    """Check if a path should be excluded from packaging."""
    parts = rel_path.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    # rel_path is relative to skill_path.parent, so parts[0] is the skill
    # folder name and parts[1] (if present) is the first subdir.
    if len(parts) > 1 and parts[1] in ROOT_EXCLUDE_DIRS:
        return True
    name = rel_path.name
    if name in EXCLUDE_FILES:
        return True
    return any(fnmatch.fnmatch(name, pat) for pat in EXCLUDE_GLOBS)


def refusal_class(rel_path: Path) -> str | None:
    """Why a file must not be packaged at all, or None. Matched case-insensitively:
    `.ENV` is as much a secret as `.env`, and only some filesystems fold case."""
    parts = [part.lower() for part in rel_path.parts]
    if any(part in REFUSE_DIRS for part in parts):
        return "run state"
    if any(fnmatch.fnmatchcase(parts[-1], pat) for pat in REFUSE_GLOBS):
        return "secret"
    return None


def package_skill(skill_path, output_dir=None):
    """
    Package a skill folder into a .skill file.

    Args:
        skill_path: Path to the skill folder
        output_dir: Optional output directory for the .skill file (defaults to <project>/.harness-state/packages/)

    Returns:
        Path to the created .skill file, or None if error
    """
    skill_path = Path(skill_path).resolve()

    # Validate skill folder exists
    if not skill_path.exists():
        print(f"ERROR: Skill folder not found: {skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"ERROR: Path is not a directory: {skill_path}")
        return None

    # Validate SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"ERROR: SKILL.md not found in {skill_path}")
        return None

    # Run validation before packaging
    print("Validating skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"ERROR: Validation failed: {message}")
        print("   Please fix the validation errors before packaging.")
        return None
    print(f"OK: {message}\n")

    # Determine output location
    skill_name = skill_path.name
    try:
        output_path = Path(output_dir).resolve() if output_dir else _default_output_dir()
    except ProjectRootError as e:
        print(f"ERROR: {e}. Pass an output directory.")
        return None
    if output_path == CREATOR_DIR or CREATOR_DIR in output_path.parents:
        print(f"ERROR: Refusing to write the package inside {CREATOR_DIR}: {output_path}")
        print(f"   A relative output directory resolves against the working directory ({Path.cwd()}), "
              "not the project root. Pass an absolute path.")
        return None

    skill_filename = output_path / f"{skill_name}.skill"

    # Decide everything before the archive exists, so a refusal leaves nothing behind.
    to_add: list[tuple[Path, Path]] = []
    refused: list[str] = []
    for file_path in sorted(skill_path.rglob('*')):
        link = _is_link(file_path)
        if not link and (not file_path.is_file() or file_path.resolve() == skill_filename):
            continue
        arcname = file_path.relative_to(skill_path.parent)
        if should_exclude(arcname):
            print(f"  Skipped: {arcname}")
            continue
        reason = "symlink" if link else refusal_class(arcname)
        if reason:
            refused.append(f"{arcname} ({reason})")
        else:
            to_add.append((file_path, arcname))

    if refused:
        print(f"ERROR: Refusing to package {skill_name}. Remove these from the skill folder first:")
        for entry in refused:
            print(f"   {entry}")
        return None

    # Create the .skill file (zip format)
    try:
        output_path.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path, arcname in to_add:
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")

        print(f"\nOK: Successfully packaged skill to: {skill_filename}")
        return skill_filename

    except Exception as e:
        print(f"ERROR: Error creating .skill file: {e}")
        return None


USAGE = """Usage: python -m scripts.package_skill <path/to/skill-folder> [output-directory]

Run from skills/skill-maker/skill-creator so the `scripts` package resolves.
Relative paths resolve against that directory; pass the output directory as an
absolute path.

Example:
  python -m scripts.package_skill ../../review/security-review
  python -m scripts.package_skill ../../review/security-review /abs/path/to/packages

Output directory defaults to <project>/.harness-state/packages/.
Exit codes: 0 = archive written, 1 = invalid or refused skill folder, or write failure."""


def main():
    configure_stdout()
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0 if len(sys.argv) > 1 else 1)

    skill_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Packaging skill: {skill_path}")
    if output_dir:
        print(f"   Output directory: {output_dir}")
    print()

    result = package_skill(skill_path, output_dir)

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
