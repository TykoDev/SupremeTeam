#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-admiral`` — the cross-stage boundary.

Validates a cross-stage handoff package at any of the ten boundaries in
``gates.yaml`` — ``contracts/workflow-protocol.md`` makes gatekeeper-admiral the
cross-stage validator at every one of them, not only the phase-to-phase handoffs
— for the structural facts a gatekeeper must not re-derive by hand: the handoff record's shape, single-revision lineage,
skip-record completeness, blocked-phrase cleanliness (this gate OWNS that scan),
idempotency against a prior verdict, and harness-doctrine §5 structure.

The script reports PASS / FAIL / UNCHECKED facts only. It does NOT issue a
verdict — the skill combines this report with judgment to choose APPROVED /
REVISE / ESCALATE. See ../SKILL.md and ../references/workflow.md.

Usage:
    python check.py <package-dir> [--prior <verdict-file>] [--json]
"""

import sys
from pathlib import Path


def _engine():
    """Import the shared engine from the nearest ancestor that holds it. The
    engine owns everything else: the project root, the package-directory guard,
    and the arguments."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        directory = parent / "harness" / "gatekeeper"
        if (directory / "_gatecheck.py").is_file():
            sys.path.insert(0, str(directory))
            import _gatecheck  # type: ignore
            return _gatecheck
    sys.stderr.write(
        "ERROR: could not locate harness/gatekeeper/_gatecheck.py above "
        f"{here}. Gate cannot run; validate by hand.\n")
    sys.exit(2)


gc = _engine()

# The cross-stage handoff record (save-protocol.md §1:
# delivery/reports/handoff_<boundary>.md) is the one artifact admiral must attach
# for any boundary; pass the run's delivery/ directory as <package-dir>. The
# package narrative + delivery package are validated structurally by the shared
# checks.
MANIFEST = gc.Manifest(
    boundary="cross-stage handoff (admiral)",
    sub_orchestrator="admiral",
    artifacts=(
        gc.ArtifactSpec(
            key="handoff_record",
            label="cross-stage handoff record with submission/verdict frontmatter",
            patterns=("*handoff*.md", "gatekeeper-admiral_handoff-*.md"),
            content_marker=r"submission_id|package_path|verdict",
        ),
        gc.ArtifactSpec(
            key="delivery_or_package",
            label="package or delivery summary the next consumer reads",
            patterns=("*package*.md", "delivery-package.md", "*delivery*.md"),
            requirement="conditional",
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
