#!/usr/bin/env python3
"""Copy the six canonical execution-contract clauses into every skill the contract binds.

``execution-contract.md`` holds the clauses once, under ``## Canonical clauses``. Every pipeline owner, phase lead,
the front door and every gatekeeper restates them under its own ``## Execution Contract``, item N being clause N
word for word, and ``test_catalog_contracts.py`` (``ExecutionContractTests``) fails on any difference. Edit the
canonical section, then run this instead of editing every copy by hand:

    python skills/validation/sync_contracts.py          # list the copies that differ; exit 1 if any do
    python skills/validation/sync_contracts.py --write  # rewrite them from the canonical section

An item that already equals its clause, whitespace aside, is left byte for byte, so the wrapping a file chose is
kept; an item that differs is replaced by the clause on one line. A bound skill with no such section, or without
items 1 to 6 in it, is reported and never rewritten: what belongs there is not something this tool guesses.

Exit codes: 0 every copy matches (or was rewritten), 1 a copy differs (without ``--write``) or cannot be located.
Stdlib only; reads the catalog with the parser production uses.
"""
from __future__ import annotations

import argparse
import re
import sys
import _catalog

CONTRACT = _catalog.SKILLS / "execution-contract.md"
SECTION = "Execution Contract"
# An item: its number, then every line up to the next item, a blank line, or a line that is not indented.
_ITEM = re.compile(r"^([1-9])\.[ \t]+.*(?:\n[ \t]+\S.*)*", re.M)


def canonical_clauses(text: "str | None" = None) -> list:
    """The numbered clauses of ``## Canonical clauses``, each with its whitespace collapsed."""
    section = _catalog.section(text if text is not None else CONTRACT.read_text(encoding="utf-8"), "Canonical clauses")
    clauses = re.findall(r"^\d\.\s+(.*?)(?=^\d\.\s|\Z)", section or "", re.S | re.M)
    return [" ".join(clause.split()) for clause in clauses]


def bound_skills(team: "dict | None" = None) -> set:
    """The skills the contract binds, from ``team-manifest.yaml``: every pipeline owner and phase lead, the front door,
    the cross-stage gatekeeper and every phase gatekeeper."""
    team = team if team is not None else _catalog.load_spec("team-manifest.yaml")
    bound = set(team.get("pipeline_owners") or [])
    bound.update(team.get("phase_leads") or [])  # phase leads own a pipeline too
    bound.add(team.get("front_door"))
    bound.add(team.get("cross_stage_gatekeeper"))
    bound.update(team.get("phase_gatekeepers") or [])
    return {name for name in bound if name}


def synced(text: str, clauses: list) -> "tuple[str, list, str | None]":
    """``(text with items 1 to 6 of its Execution Contract section set to the clauses, the item numbers that changed,
    a problem)``. With a problem the text comes back unchanged."""
    match = re.search(rf"^## {re.escape(SECTION)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if match is None:
        return text, [], f"no '## {SECTION}' section"
    start = match.start(1)
    items: dict = {}
    for item in _ITEM.finditer(match.group(1)):
        items.setdefault(int(item.group(1)), item)  # the first list in the section is the contract's
    missing = [number for number in range(1, len(clauses) + 1) if number not in items]
    if missing:
        return text, [], f"'## {SECTION}' holds no item {', '.join(map(str, missing))}"
    changed, pieces, cursor = [], [], 0
    for number, clause in enumerate(clauses, start=1):
        item = items[number]
        body = item.group(0)[len(item.group(1)) + 1:]
        if " ".join(body.split()) == clause:
            continue
        changed.append(number)
        pieces += [text[cursor:start + item.start()], f"{number}. {clause}"]
        cursor = start + item.end()
    return "".join(pieces) + text[cursor:], changed, None


def main(argv: "list | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Copy the canonical execution-contract clauses into every bound skill.")
    parser.add_argument("--write", action="store_true", help="rewrite the copies that differ (default: only report them)")
    args = parser.parse_args(argv)
    clauses = canonical_clauses()
    if len(clauses) != 6:
        print(f"error: {CONTRACT.name} states {len(clauses)} canonical clauses, not six", file=sys.stderr)
        return 1
    directories = _catalog.skill_dirs()
    status = 0
    for name in sorted(bound_skills()):
        if name not in directories:
            print(f"error: {name} is bound by the execution contract but is not a skill", file=sys.stderr)
            status = 1
            continue
        path = directories[name] / "SKILL.md"
        relative = path.relative_to(_catalog.SKILLS).as_posix()
        text = path.read_text(encoding="utf-8")
        new, changed, problem = synced(text, clauses)
        if problem:
            print(f"error: {relative}: {problem}; add the six clauses there by hand", file=sys.stderr)
            status = 1
        elif changed and args.write:
            path.write_bytes(new.encode("utf-8"))
            print(f"rewrote {relative}: clause {', '.join(map(str, changed))}")
        elif changed:
            print(f"differs {relative}: clause {', '.join(map(str, changed))}")
            status = 1
    if status == 0 and not args.write:
        print("every bound skill states the canonical clauses")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
