"""Shared test support for the validation suite: the catalog read the way production reads it.

Production parses every manifest and every SKILL.md frontmatter with
``data_formats``. A test that parsed with PyYAML whenever it was importable would
pass against a document the shipped parser rejects, so these helpers use
``data_formats`` and nothing else; ``test_catalog_contracts.ParserParityTests``
compares the two parsers on the whole catalog.

The suite reads everything else it shares through here too: a document's
level-2 sections, the routing-class table, the advertised triggers, the roster,
the gatekeepers, counts spelled as words, whether ``skills/`` sits in a checkout,
and the PreToolUse hook's answer. ``trigger_eval.py`` builds its corpus with
``advertised_triggers``, so the eval and the test that checks its corpus read
the same phrases. The extractor lives here rather than in the eval because the
eval exits at import without PyYAML and the suite has to run without it, which
is why everything here is standard library only.

The leading underscore keeps this module out of test discovery. Modules import it
by name because ``unittest discover -s skills/validation`` puts this directory on
``sys.path``, and so does running a test file directly.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

SKILLS = Path(__file__).resolve().parents[1]
REPO = SKILLS.parent
HOOKS = SKILLS / "harness" / "hooks"
if str(SKILLS / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import load_data, parse_yaml  # noqa: E402
import validate_manifests  # noqa: E402

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)
#: Positions as prose spells them ("the third round"); ``number_word`` spells the counts.
ORDINALS = ("zeroth", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
#: A ``Use This Skill When`` bullet either quotes the phrasings it answers to, or is itself the phrasing.
QUOTED = re.compile(r'"([^"]{4,80})"')
#: Trailing explanation after a dash is commentary, not part of the trigger.
EXPLAIN = re.compile(r"\s+[—-]\s+.*$")

#: Set by a CI leg to say whether PyYAML is installed on it ("with" or "without").
#: Unset on a developer machine, where either answer is fine.
PYYAML_VARIANT = os.environ.get("SUPREMETEAM_PYYAML", "")

#: Whether ``skills/`` sits in a repository checkout, decided by the validator's own
#: test: an install copies none of README.md, docs/ and .github/, and a checkout
#: missing one of them is still a checkout, where the test that reads the missing
#: file fails instead of skipping.
IN_A_CHECKOUT = validate_manifests.is_repository(SKILLS)
#: For the tests that read the repository around ``skills/``.
CHECKOUT_ONLY = unittest.skipUnless(IN_A_CHECKOUT, "installed copy: only skills/ is present")


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


def section(text: str, heading: str) -> str | None:
    """The body of the level-2 section ``## heading``, or None when ``text`` has none.

    The body runs to the next level-2 heading or to the end of the document, so a
    section that closes the document is read like any other.
    """
    match = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1) if match else None


def roster() -> set[str]:
    """Every skill name ``team-manifest.yaml`` declares, collected by ``validate_manifests.team_members``."""
    return validate_manifests.team_members(load_spec("team-manifest.yaml"))


def gatekeepers() -> tuple[str, ...]:
    """The gatekeepers' directories under ``skills/``, the cross-stage gatekeeper first, as the manifest names them."""
    team, directories = load_spec("team-manifest.yaml"), skill_dirs()
    names = [team["cross_stage_gatekeeper"], *team["phase_gatekeepers"]]
    return tuple(directories[name].relative_to(SKILLS).as_posix() for name in names)


def routing_rows() -> list[tuple[str, str]]:
    """(class label, Skills cell) for every row of the routing-class table in ``routing-doctrine.md``."""
    body = section((SKILLS / "routing-doctrine.md").read_text(encoding="utf-8"), "Routing classes") or ""
    rows = []
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] == "Routing class" or set(cells[0]) <= set("- "):
            continue
        rows.append((cells[0], cells[1]))
    return rows


def routing_classes() -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    """class label -> skill names, and skill name -> the labels that claim it.

    The Skills cell is written to be mechanically comparable, but it is prose: a
    bare name, a directory glob (`safety-guardrails/*`), a path that disambiguates
    a name (`taste/taste-review`), a manifest role in parentheses, `except
    `ship``, and `not named in a row above`. A backticked token that is a key of
    team-manifest.yaml is a role annotation, never a skill, which is why the two
    are told apart against the manifest rather than by a hand-kept list.
    """
    labels = set(load_spec("team-manifest.yaml"))
    paths = {name: directory.relative_to(SKILLS).as_posix() for name, directory in skill_dirs().items()}
    assigned, per_class = {}, {}
    for label, cell in routing_rows():
        excepted = set(re.findall(r"\bexcept\s+`([^`]+)`", cell))
        tokens = re.findall(r"`([^`]+)`", re.sub(r"\bexcept\s+`[^`]+`", " ", cell))
        members = set()
        for token in tokens:
            if token in labels:
                continue
            if token.endswith("/*") or token.endswith("/"):
                prefix = token.rstrip("*").rstrip("/")
                members |= {n for n, d in paths.items() if d == prefix or d.startswith(prefix + "/")}
            elif "/" in token:
                members |= {n for n, d in paths.items() if d == token}
            elif token in paths:
                members.add(token)
        if "not named in a row above" in cell:
            members -= set(assigned)
        members -= excepted
        per_class[label] = members
        for member in members:
            assigned.setdefault(member, []).append(label)
    return per_class, assigned


def advertised_triggers(text: str) -> list[str]:
    """The phrasings a SKILL.md advertises under ``## Use This Skill When``, as ``trigger_eval.py`` asks them.

    A bullet that quotes phrasings contributes each quote. A bare bullet is itself
    the phrasing, without a trailing gloss or markup, when it runs two to twelve
    words and is not prose about routing.
    """
    found: list[str] = []
    for line in (section(text, "Use This Skill When") or "").splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].strip()
        quoted = QUOTED.findall(body)
        if quoted:
            found.extend(q.strip() for q in quoted)
            continue
        body = EXPLAIN.sub("", body)
        body = re.sub(r"[`*]", "", body).strip(" .")
        # Bullets that are prose about routing, not a phrasing a user would type.
        if 2 <= len(body.split()) <= 12 and not body.lower().startswith(("route ", "a request")):
            found.append(body)
    return found


def number_word(n: int) -> str:
    """``n`` spelled out the way a document states a count, from zero to ninety-nine.

    Up to twenty the words are ``validate_manifests.NUMBER_WORDS``, the table the
    validator reads documented counts with; above it they are hyphenated, as in
    "thirty-eight".
    """
    words = validate_manifests.NUMBER_WORDS
    if not 0 <= n < 100:
        raise ValueError(f"no number word for {n}")
    if n < len(words):
        return words[n]
    tens, ones = divmod(n, 10)
    return TENS[tens] + (f"-{words[ones]}" if ones else "")


#: A count as a document states it, for a regex: digits, or a number word up to
#: ninety-nine, the longer words first so "twenty-one" is not read as "twenty".
NUMBER = "|".join([r"\d+", *sorted(map(number_word, range(100)), key=len, reverse=True)])


def number_value(stated: str) -> int:
    """The count ``stated`` gives, in digits or in words; the inverse of ``number_word``."""
    stated = stated.lower()
    if stated.isdigit():
        return int(stated)
    for n in range(100):
        if number_word(n) == stated:
            return n
    raise ValueError(f"{stated!r} states no count")


def ordinal(n: int) -> str:
    """``n`` as a position, "zeroth" to "tenth"."""
    if not 0 <= n < len(ORDINALS):
        raise ValueError(f"no ordinal for {n}")
    return ORDINALS[n]


def mentions_key(text: str, key: str) -> bool:
    """Whether ``text`` names the evidence key ``key`` in backticks.

    A bare word does not count: 19 of the gate's evidence keys (`plan`, `scope`,
    `tests`, `findings`, `runtime`, `architecture`) are ordinary English, so a
    word-boundary search passed whenever the sentence happened to use the word.
    """
    return f"`{key}`" in text


def run_hook(project: Path, tool: str, file_path: Path) -> subprocess.CompletedProcess:
    """The PreToolUse hook's answer to one ``tool`` call on ``file_path``, with ``project`` as the project root.

    The hook keeps its observations under the project root, so ``project`` is a
    scratch directory, never the repository.
    """
    payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": str(file_path)}})
    return subprocess.run([sys.executable, str(HOOKS / "pre_tool_use.py")], input=payload, text=True,
                          capture_output=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)}, check=False)


def deny_reason(stdout: str) -> str:
    """The reason of a PreToolUse deny, read from the hook's JSON envelope; fails when the hook did not deny."""
    if not stdout.strip():
        raise AssertionError("the hook did not deny: it printed nothing")
    decision = json.loads(stdout)["hookSpecificOutput"]
    if decision["permissionDecision"] != "deny":
        raise AssertionError(f"the hook did not deny: {decision}")
    return decision["permissionDecisionReason"]


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
            "PyYAML is not installed. This test needs it; CI's 'with PyYAML' legs run it "
            "and fail rather than skip when the package is missing.")
    return module
