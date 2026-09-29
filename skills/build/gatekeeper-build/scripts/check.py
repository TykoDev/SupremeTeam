#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-build`` — the build→review boundary.

Validates that a build-phase packet attaches the implementation diff, test
evidence, security outcome, cross-check completeness certification, and the
build-gate verdict for one coherent revision — plus the shared lineage,
skip-record, blocked-phrase, idempotency, and harness-doctrine §5 checks.

Reports PASS / FAIL / UNCHECKED facts only; the skill issues the verdict.
See ../SKILL.md and ../references/workflow.md.

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

# Required build-to-review evidence set (SKILL.md workflow step 1). Matched by
# filename pattern and/or a content marker so a deliverable named
# deliverable_implementation.md or review-packet.md is recognized either way.
MANIFEST = gc.Manifest(
    boundary="build-to-review",
    sub_orchestrator="build/build-management",
    artifacts=(
        gc.ArtifactSpec(
            key="implementation",
            label="implementation diff / change summary",
            patterns=("*implementation*.md", "deliverable_*build*.md", "*diff*.md"),
            content_marker=r"implementation|changed file|diff|module",
        ),
        gc.ArtifactSpec(
            key="tests",
            label="test-builder evidence (execution results)",
            patterns=("*test*.md", "deliverable_*test*.md"),
            content_marker=r"test|coverage|pass|fail|suite",
        ),
        gc.ArtifactSpec(
            key="security",
            label="security-builder outcome (findings or clean bill)",
            patterns=("*security*.md", "deliverable_*security*.md"),
            content_marker=r"security|vulnerab|clean bill|finding",
        ),
        gc.ArtifactSpec(
            key="completeness",
            label="cross-check-build-confirm completeness certification",
            patterns=("*cross-check*.md", "*completeness*.md", "*confirm*.md"),
            content_marker=r"complete|certif|confirm",
        ),
        gc.ArtifactSpec(
            key="build_verdict",
            label="gatekeeper-build verdict lineage for this revision",
            patterns=("gatekeeper-verdict.md", "*gatekeeper*.md"),
            requirement="conditional",
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
