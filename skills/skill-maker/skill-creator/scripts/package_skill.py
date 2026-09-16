#!/usr/bin/env python3
"""Skill packager - build a distributable .skill archive from a skill folder.

Run as a module from the skill-creator directory, so the `scripts` package
resolves:

    cd skills/skill-maker/skill-creator
    python -m scripts.package_skill <path/to/skill-folder> [output-directory]

Example:
    python -m scripts.package_skill ../../review/security-review
    python -m scripts.package_skill ../../review/security-review \\
        skillset-saves/runs/<run-id>/skill-creation/packages

Inputs:
    path/to/skill-folder  directory containing SKILL.md
    output-directory      optional; defaults to <project>/.harness-state/packages/

Output:
    <output-directory>/<folder-name>.skill - a ZIP archive rooted at the skill
    folder name, excluding evals/ at the root, __pycache__, *.pyc and .DS_Store.

Exit codes:
    0  the archive was written; its path is printed
    1  the skill folder is missing, is not a directory, has no SKILL.md,
       fails quick_validate, or the archive could not be created
"""

import fnmatch
import sys
import zipfile
from pathlib import Path
from scripts.quick_validate import validate_skill


def _default_output_dir() -> Path:
    """Packages built outside a run go under the project's .harness-state/packages/.

    The project root is the nearest ancestor of the working directory holding
    skillset-saves/, .harness-state/, or .git (save-ownership.yaml generated_roots).
    """
    start = Path.cwd().resolve()
    root = next((c for c in (start, *start.parents)
                 if any((c / m).exists() for m in ("skillset-saves", ".harness-state", ".git"))), start)
    target = root / ".harness-state" / "packages"
    target.mkdir(parents=True, exist_ok=True)
    return target

# Patterns to exclude when packaging skills.
EXCLUDE_DIRS = {"__pycache__", "node_modules"}
EXCLUDE_GLOBS = {"*.pyc"}
EXCLUDE_FILES = {".DS_Store"}
# Directories excluded only at the skill root (not when nested deeper).
ROOT_EXCLUDE_DIRS = {"evals"}


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
        print(f"❌ Error: Skill folder not found: {skill_path}")
        return None

    if not skill_path.is_dir():
        print(f"❌ Error: Path is not a directory: {skill_path}")
        return None

    # Validate SKILL.md exists
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        print(f"❌ Error: SKILL.md not found in {skill_path}")
        return None

    # Run validation before packaging
    print("🔍 Validating skill...")
    valid, message = validate_skill(skill_path)
    if not valid:
        print(f"❌ Validation failed: {message}")
        print("   Please fix the validation errors before packaging.")
        return None
    print(f"✅ {message}\n")

    # Determine output location
    skill_name = skill_path.name
    if output_dir:
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = _default_output_dir()

    skill_filename = output_path / f"{skill_name}.skill"

    # Create the .skill file (zip format)
    try:
        with zipfile.ZipFile(skill_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through the skill directory, excluding build artifacts
            for file_path in skill_path.rglob('*'):
                if file_path.resolve() == skill_filename or not file_path.is_file():
                    continue
                arcname = file_path.relative_to(skill_path.parent)
                if should_exclude(arcname):
                    print(f"  Skipped: {arcname}")
                    continue
                zipf.write(file_path, arcname)
                print(f"  Added: {arcname}")

        print(f"\n✅ Successfully packaged skill to: {skill_filename}")
        return skill_filename

    except Exception as e:
        print(f"❌ Error creating .skill file: {e}")
        return None


USAGE = """Usage: python -m scripts.package_skill <path/to/skill-folder> [output-directory]

Run from skills/skill-maker/skill-creator so the `scripts` package resolves.

Example:
  python -m scripts.package_skill ../../review/security-review
  python -m scripts.package_skill ../../review/security-review ./dist

Output directory defaults to <project>/.harness-state/packages/.
Exit codes: 0 = archive written, 1 = invalid skill folder or write failure."""


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0 if len(sys.argv) > 1 else 1)

    skill_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"📦 Packaging skill: {skill_path}")
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
