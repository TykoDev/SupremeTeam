#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-code`` — the review→delivery boundary.

Validates that a consolidated review package carries the five core review lenses
(bug, code, quality, security, adversarial) and surfaces the CSO lens as
conditional so the model confirms whether a security-leadership / accepted-risk /
release-posture claim is in scope. Adds the shared lineage, skip-record,
blocked-phrase, idempotency, and harness-doctrine §5 checks.

Reports PASS / FAIL / UNCHECKED facts only; the skill issues the verdict.
See ../SKILL.md and ../references/workflow.md.

Usage:
    python check.py <package-dir> [--prior <verdict-file>] [--json]
"""

import sys
from pathlib import Path


def _load_engine():
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

# Core review lenses (workflow.md acceptance checklist). The CSO lens is
# CONDITIONAL: required only when the package claims security leadership,
# accepted-risk readiness, release security posture, regulated-data governance,
# or operating-model control review — which the script cannot determine, so its
# absence is reported as UNCHECKED (model resolves, or accepts an explicit skip
# record, which check_skip_records validates separately).
MANIFEST = gc.Manifest(
    boundary="review-to-delivery",
    sub_orchestrator="review/code-chief",
    artifacts=(
        gc.ArtifactSpec(
            key="lens_bug",
            label="bug-review lens",
            patterns=("*bug*.md", "deliverable_*bug*.md"),
            content_marker=r"bug|defect|regression|correctness",
        ),
        gc.ArtifactSpec(
            key="lens_code",
            label="code-review lens",
            patterns=("*code-review*.md", "*code*.md", "deliverable_*code*.md"),
            content_marker=r"code|review|maintainab|readab",
        ),
        gc.ArtifactSpec(
            key="lens_quality",
            label="quality-review lens",
            patterns=("*quality*.md", "deliverable_*quality*.md"),
            content_marker=r"quality|standard|consistency",
        ),
        gc.ArtifactSpec(
            key="lens_security",
            label="security-review lens",
            patterns=("*security*.md", "deliverable_*security*.md"),
            content_marker=r"security|vulnerab|threat|exposure",
        ),
        gc.ArtifactSpec(
            key="lens_adversarial",
            label="adversarial / frontier lens",
            patterns=("*frontier*.md", "*adversarial*.md", "*mr-robot*.md"),
            content_marker=r"adversar|frontier|edge case|attack",
        ),
        gc.ArtifactSpec(
            key="lens_cso",
            label="CSO security-leadership lens",
            patterns=("*cso*.md", "deliverable_*cso*.md"),
            requirement="conditional",
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
