#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-code`` — the review→delivery boundary.

Validates that a consolidated review package carries the three unconditional
review lenses (bug, code, quality) as packets with their own Outcome and Findings
fields, and surfaces the conditional lenses (security, adversarial/frontier, CSO)
as UNCHECKED when absent so the model confirms whether their condition held. Adds
the shared lineage, skip-record, blocked-phrase, idempotency, and harness-doctrine
§5 checks.

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

# The bug, code, quality, security, and adversarial lenses file their packet in the
# shape their SKILL.md fixes. Outcome and Findings are fields a prose mention of
# the topic does not supply.
_PACKET = ("Outcome", "Findings")

# review/cso fixes no packet template and no Findings field. Its SKILL.md states
# the return every gate-owning skill makes (execution-contract clause 6), which
# names Outcome first, so that is the one field asked of a CSO packet.
_CSO_PACKET = ("Outcome",)

# Bug, code, and quality run on every review: their stages carry no condition in
# pipelines.yaml. The others are not declared optional here. pipelines.yaml gives
# their stages a `when`, code-chief schedules them by it, and the engine reads it,
# so an absent one is UNCHECKED: the model resolves it against the condition, or
# accepts an explicit skip record, which check_skip_records validates separately.
# The CSO lens has no review stage at all (governance escalates to the security
# pipeline), so it is declared conditional.
MANIFEST = gc.Manifest(
    boundary="review-to-delivery",
    sub_orchestrator="review/code-chief",
    pipeline="review",
    artifacts=(
        gc.ArtifactSpec(
            key="lens_bug",
            label="bug-review lens",
            patterns=("*bug*.md", "deliverable_*bug*.md"),
            fields=_PACKET,
            stages=("correctness-review",),
        ),
        gc.ArtifactSpec(
            key="lens_code",
            label="code-review lens",
            patterns=("*code-review*.md", "*code*.md", "deliverable_*code*.md"),
            fields=_PACKET,
            stages=("merge-readiness-review",),
        ),
        gc.ArtifactSpec(
            key="lens_quality",
            label="quality-review lens",
            patterns=("*quality*.md", "deliverable_*quality*.md"),
            fields=_PACKET,
            stages=("maintainability-review",),
        ),
        gc.ArtifactSpec(
            key="lens_security",
            label="security-review lens",
            patterns=("security-review.md", "deliverable_security-review.md", "lens-security*.md",
                      "*security-review-report*.md", "*security-review-packet*.md", "*security-findings*.md"),
            fields=_PACKET,
            stages=("security-review",),
        ),
        gc.ArtifactSpec(
            key="lens_adversarial",
            label="adversarial / frontier lens",
            patterns=("*frontier*.md", "*adversarial*.md", "*mr-robot*.md"),
            fields=_PACKET,
            stages=("penetration-review", "frontend-review"),
        ),
        gc.ArtifactSpec(
            key="lens_cso",
            label="CSO security-leadership lens",
            patterns=("*cso*.md", "deliverable_*cso*.md", "security-review-package.md",
                      "deliverable_security-review-package.md"),
            fields=_CSO_PACKET,
            requirement="conditional",
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
