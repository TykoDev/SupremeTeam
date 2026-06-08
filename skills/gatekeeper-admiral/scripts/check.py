#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-admiral`` — the cross-stage boundary.

Validates a cross-stage handoff package (design→build, build→review,
review→delivery, or skill-maker→delivery) for the structural facts a gatekeeper
must not re-derive by hand: the handoff record's shape, single-revision lineage,
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


def _load_engine():
    """Locate harness/gatekeeper/_gatecheck.py by walking up to the repo root."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "harness" / "gatekeeper" / "_gatecheck.py"
        if candidate.exists():
            sys.path.insert(0, str(candidate.parent))
            import _gatecheck  # type: ignore
            return _gatecheck
    sys.stderr.write(
        "ERROR: could not locate harness/gatekeeper/_gatecheck.py above "
        f"{Path(__file__).resolve()}. Gate cannot run; validate by hand.\n")
    sys.exit(2)


gc = _load_engine()

# The cross-stage handoff record (save-protocol.md §2: gatekeeper-admiral_handoff
# -{N}.md) is the one artifact admiral must attach for any boundary. The package
# narrative + delivery package are validated structurally by the shared checks.
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
