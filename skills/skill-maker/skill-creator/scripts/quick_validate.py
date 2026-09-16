#!/usr/bin/env python3
"""Pre-package structural validation of a skill folder.

Checks only what makes a skill loadable, so a skill that cannot load is never
packaged: SKILL.md exists, the YAML frontmatter parses, no unexpected
frontmatter key is present, and `name` and `description` satisfy the Skills
spec (kebab-case name <= 64 chars; description non-empty, <= 1024 chars, no
angle brackets). It does not score rubric dimensions - that is skill-reviewer's
job - and it does not inspect the body.

Run as a module from the skill-creator directory, so the `scripts` package
resolves:

    cd skills/skill-maker/skill-creator
    python -m scripts.quick_validate <path/to/skill-folder>

Inputs:
    path/to/skill-folder  directory expected to contain SKILL.md

Output:
    One line on stdout: "Skill is valid!" or the first failure found.
    Capture it as the `validation_report` evidence at skill-maker-to-delivery;
    that key is artifact-backed, so write the line to a file and hash it.

Exit codes:
    0  the skill is structurally valid
    1  a validation failure, or no skill folder argument was given

Importable API:
    validate_skill(path) -> (bool ok, str message)
"""

import sys
import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:  # PyYAML is optional (runtime-manifest.yaml); use the stdlib parser.
    yaml = None
    _SKILLS_SCRIPTS = next(
        (p / 'scripts' for p in Path(__file__).resolve().parents if (p / 'scripts' / 'data_formats.py').is_file()),
        None,
    )
    if _SKILLS_SCRIPTS is not None and str(_SKILLS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SKILLS_SCRIPTS))
    from data_formats import DataFormatError, parse_yaml as _parse_yaml

if yaml is not None:
    _YAML_ERRORS = (yaml.YAMLError,)

    def _load_yaml(text):
        return yaml.safe_load(text)
else:
    _YAML_ERRORS = (DataFormatError,)

    def _load_yaml(text):
        return _parse_yaml(text)

def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    content = skill_md.read_text(encoding='utf-8')
    if not content.startswith('---'):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    # Parse YAML frontmatter
    try:
        frontmatter = _load_yaml(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except _YAML_ERRORS as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    # Official Claude Skills frontmatter properties (per the Skills spec).
    OFFICIAL_PROPERTIES = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'}

    # SupremeTeam catalog extension fields. These are intentional, catalog-wide
    # taxonomy/orchestration keys (used by 32-76 of the catalog's skills) and are
    # consumed as prose by the orchestrators, not by the host loader. They are
    # accepted here so the validator does not reject the catalog's own skills.
    # Note: 'allowed_tools' (underscore) is deliberately NOT in either set — the
    # real field is the hyphenated 'allowed-tools', so the underscore form stays
    # a caught typo (the host silently ignores it).
    SUPREMETEAM_EXTENSIONS = {'version', 'family', 'role', 'auth_context', 'mcp_servers', 'canonical'}

    ALLOWED_PROPERTIES = OFFICIAL_PROPERTIES | SUPREMETEAM_EXTENSIONS

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(map(str, unexpected_keys)))}. "
            f"Allowed properties are: {', '.join(sorted(OFFICIAL_PROPERTIES))} "
            f"(plus SupremeTeam extensions: {', '.join(sorted(SUPREMETEAM_EXTENSIONS))})"
        )

    # Check required fields
    if 'name' not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if 'description' not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if not name:
        return False, "Name must not be empty"
    if name:
        # Check naming convention (kebab-case: lowercase with hyphens)
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"Name '{name}' should be kebab-case (lowercase letters, digits, and hyphens only)"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens"
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."

    # Extract and validate description
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if not description:
        return False, "Description must not be empty"
    if description:
        # Check for angle brackets
        if '<' in description or '>' in description:
            return False, "Description cannot contain angle brackets (< or >)"
        # Check description length (max 1024 characters per spec)
        if len(description) > 1024:
            return False, f"Description is too long ({len(description)} characters). Maximum is 1024 characters."

    # Validate compatibility field if present (optional)
    compatibility = frontmatter.get('compatibility', '')
    if 'compatibility' in frontmatter:
        if not isinstance(compatibility, str):
            return False, f"Compatibility must be a string, got {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return False, f"Compatibility is too long ({len(compatibility)} characters). Maximum is 500 characters."

    return True, "Skill is valid!"

USAGE = """Usage: python -m scripts.quick_validate <path/to/skill-folder>

Run from skills/skill-maker/skill-creator so the `scripts` package resolves.

Checks SKILL.md exists, the frontmatter parses, no unexpected key is present,
and name/description satisfy the Skills spec. Prints one line.
Exit codes: 0 = valid, 1 = a validation failure or a missing argument."""

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(USAGE)
        sys.exit(0)
    if len(sys.argv) != 2:
        print(USAGE)
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)