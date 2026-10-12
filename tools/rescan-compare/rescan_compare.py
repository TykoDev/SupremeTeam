#!/usr/bin/env python3
"""Compare two re-scan reports and decide whether a follow-up scan matches a release.

A re-scan report is JSON carrying a run set and a finding set::

    {"runs": ["run-a", "run-b"],
     "findings": [{"id": "F-1", "severity": "Major"}, ...]}

Two reports are equal when their run id sets match and their finding
(id, severity) sets match.  A severity drift with unchanged ids is a
difference: the same finding at a different grade is not the same finding.

Exit codes follow the catalog convention: 0 equal, 1 different,
2 engine error (unreadable or malformed input).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "1.0.0"

SEVERITIES = ("Critical", "Major", "Minor", "Info")


class ReportError(ValueError):
    """A scan report is unreadable or malformed."""


def _run_ids(report: dict, source: str) -> set[str]:
    runs = report.get("runs")
    if not isinstance(runs, list):
        raise ReportError(f"{source}: 'runs' must be a list")
    ids: set[str] = set()
    for index, entry in enumerate(runs):
        if isinstance(entry, str):
            ident = entry
        elif isinstance(entry, dict) and isinstance(entry.get("id"), str):
            ident = entry["id"]
        else:
            raise ReportError(f"{source}: runs[{index}] must be a string or carry an id")
        if not ident:
            raise ReportError(f"{source}: runs[{index}] has an empty id")
        ids.add(ident)
    return ids


def _findings(report: dict, source: str) -> set[tuple[str, str]]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ReportError(f"{source}: 'findings' must be a list")
    pairs: set[tuple[str, str]] = set()
    for index, entry in enumerate(findings):
        if not isinstance(entry, dict):
            raise ReportError(f"{source}: findings[{index}] must be a mapping")
        ident = entry.get("id")
        severity = entry.get("severity")
        if not isinstance(ident, str) or not ident:
            raise ReportError(f"{source}: findings[{index}] requires an id")
        if severity not in SEVERITIES:
            raise ReportError(
                f"{source}: findings[{index}] severity must be one of {list(SEVERITIES)}"
            )
        pairs.add((ident, severity))
    return pairs


def load_report(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReportError(f"{path}: unreadable ({exc.strerror})") from exc
    try:
        report = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReportError(f"{path}: not valid JSON ({exc.msg})") from exc
    if not isinstance(report, dict):
        raise ReportError(f"{path}: report must be a JSON object")
    return report


def compare(before: dict, after: dict) -> dict:
    """Compare two loaded reports; the finding set is (id, severity) pairs."""
    before_runs = _run_ids(before, "before")
    after_runs = _run_ids(after, "after")
    before_findings = _findings(before, "before")
    after_findings = _findings(after, "after")

    runs_missing = sorted(before_runs - after_runs)
    runs_extra = sorted(after_runs - before_runs)
    findings_missing = sorted(before_findings - after_findings)
    findings_extra = sorted(after_findings - before_findings)

    equal = not (runs_missing or runs_extra or findings_missing or findings_extra)
    return {
        "version": VERSION,
        "equal": equal,
        "runs": {
            "compared": len(before_runs | after_runs),
            "missing_in_after": runs_missing,
            "extra_in_after": runs_extra,
        },
        "findings": {
            "compared": len(before_findings | after_findings),
            "missing_in_after": [{"id": i, "severity": s} for i, s in findings_missing],
            "extra_in_after": [{"id": i, "severity": s} for i, s in findings_extra],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rescan-compare",
        description="compare run sets and finding sets between two re-scan reports",
    )
    parser.add_argument("before", help="release-time report (JSON)")
    parser.add_argument("after", help="later re-scan report (JSON)")
    parser.add_argument("--out", help="write the comparison report here (JSON)")
    parser.add_argument("--version", action="version", version=f"rescan-compare {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        before = load_report(Path(args.before))
        after = load_report(Path(args.after))
        result = compare(before, after)
    except ReportError as exc:
        print(f"rescan-compare: {exc}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    verdict = "equal" if result["equal"] else "different"
    print(
        f"rescan-compare: {verdict}; runs compared {result['runs']['compared']}, "
        f"findings compared {result['findings']['compared']}"
    )
    return 0 if result["equal"] else 1


if __name__ == "__main__":
    sys.exit(main())
