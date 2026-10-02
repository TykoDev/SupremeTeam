"""Shared test support for the validation suite: the catalog read the way production reads it.

Production parses every manifest and every SKILL.md frontmatter with
``data_formats``. A test that parsed with PyYAML whenever it was importable would
pass against a document the shipped parser rejects, so these helpers use
``data_formats`` and nothing else; ``test_catalog_contracts.ParserParityTests``
compares the two parsers on the whole catalog.

The leading underscore keeps this module out of test discovery. Modules import it
by name because ``unittest discover -s skills/validation`` puts this directory on
``sys.path``, and so does running a test file directly.
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any

SKILLS = Path(__file__).resolve().parents[1]
if str(SKILLS / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import load_data, parse_yaml  # noqa: E402

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)

#: Set by a CI leg to say whether PyYAML is installed on it ("with" or "without").
#: Unset on a developer machine, where either answer is fine.
PYYAML_VARIANT = os.environ.get("SUPREMETEAM_PYYAML", "")


def load_spec(name: str) -> Any:
    """A manifest or spec under ``skills/``, parsed by ``data_formats``."""
    return load_data(SKILLS / name)


def parse_frontmatter(text: str) -> dict:
    """The frontmatter mapping of a Markdown document, or an empty dict."""
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    parsed = parse_yaml(match.group(1))
    return parsed if isinstance(parsed, dict) else {}


def skill_front(skill_md: Path) -> dict:
    """Parsed frontmatter of a SKILL.md, or an empty dict."""
    return parse_frontmatter(skill_md.read_text(encoding="utf-8"))


def skill_dirs() -> dict[str, Path]:
    """Map skill name to directory, from the name each SKILL.md declares."""
    found = {}
    for md in sorted(SKILLS.rglob("SKILL.md")):
        name = skill_front(md).get("name")
        if name:
            found[name] = md.parent
    return found


def corpus(directory: Path) -> str:
    """Every document a skill owns, excluding any nested skill's subtree."""
    parts = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".yaml", ".yml"}:
            continue
        if "__pycache__" in path.parts:
            continue
        nested = False
        for parent in path.parents:
            if parent == directory:
                break
            if (parent / "SKILL.md").is_file():
                nested = True
                break
        if not nested:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def mentions(text: str, token: str) -> bool:
    """Whether ``token`` appears in ``text`` as a whole word."""
    return re.search(r"\b" + re.escape(token) + r"\b", text) is not None


def mentions_key(text: str, key: str) -> bool:
    """Whether ``text`` names the evidence key ``key`` in backticks.

    A bare word does not count: 19 of the gate's evidence keys (`plan`, `scope`,
    `tests`, `findings`, `runtime`, `architecture`) are ordinary English, so a
    word-boundary search passed whenever the sentence happened to use the word.
    """
    return f"`{key}`" in text


def pyyaml() -> Any:
    """The PyYAML module, or None, after checking it against the CI leg's promise.

    A leg that promises PyYAML and does not have it fails here instead of
    skipping, so a broken install cannot hide a test; a leg that promises its
    absence fails when it is present, so the stdlib fallback really is the only
    parser.
    """
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None
    if PYYAML_VARIANT == "with" and yaml is None:
        raise AssertionError("this CI leg promises PyYAML (SUPREMETEAM_PYYAML=with) but it is not installed")
    if PYYAML_VARIANT == "without" and yaml is not None:
        raise AssertionError("this CI leg promises no PyYAML (SUPREMETEAM_PYYAML=without) but it is installed")
    return yaml


def require_pyyaml() -> Any:
    """``pyyaml()``, or a skip that says why and where the test does run."""
    module = pyyaml()
    if module is None:
        raise unittest.SkipTest(
            "PyYAML is not installed. This test compares against it; CI's 'with PyYAML' legs run it "
            "and fail rather than skip when the package is missing.")
    return module
