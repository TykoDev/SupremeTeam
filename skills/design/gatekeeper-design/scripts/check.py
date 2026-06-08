#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-design`` — the design phase-exit
boundary.

Validates that a design packet carries the research evidence, project plan,
architecture decisions, stack locks, and implementation spec for the phase exit
— and surfaces the conditional API-contract and frontend/UI-handoff artifacts as
UNCHECKED so the model confirms whether they are in scope. Adds the shared
lineage, skip-record, blocked-phrase, idempotency, and harness-doctrine §5
checks.

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

# Design phase-exit artifact set (SKILL.md workflow step 1). API contracts and
# frontend/UI handoff are CONDITIONAL — required only when endpoints or a
# user-facing surface are in scope, which the script cannot determine, so their
# absence is reported as UNCHECKED for the model to resolve against the actual
# scope and the design-doctrine / api-endpoint-design contracts.
MANIFEST = gc.Manifest(
    boundary="design phase-exit",
    sub_orchestrator="design/commander",
    artifacts=(
        gc.ArtifactSpec(
            key="research",
            label="research evidence",
            patterns=("*research*.md", "deliverable_*research*.md"),
            content_marker=r"research|finding|evidence|source",
        ),
        gc.ArtifactSpec(
            key="plan",
            label="project plan",
            patterns=("*plan*.md", "deliverable_*plan*.md"),
            content_marker=r"plan|milestone|phase|scope",
        ),
        gc.ArtifactSpec(
            key="architecture",
            label="architecture decisions (ADRs)",
            patterns=("*architect*.md", "*adr*.md", "deliverable_*arch*.md"),
            content_marker=r"architect|decision|component|ADR",
        ),
        gc.ArtifactSpec(
            key="stack_locks",
            label="locked technology choices / stack locks",
            patterns=("*stack*.md", "*lock*.md", "*tech*.md"),
            content_marker=r"stack|lock|version|dependency",
        ),
        gc.ArtifactSpec(
            key="impl_spec",
            label="implementation specification",
            patterns=("*spec*.md", "*implementation*.md", "deliverable_*spec*.md"),
            content_marker=r"spec|interface|contract|implementation",
        ),
        gc.ArtifactSpec(
            key="api_contracts",
            label="API endpoint contracts (api-endpoint-design.md shape)",
            patterns=("*api*.md", "*endpoint*.md", "*contract*.md"),
            requirement="conditional",
        ),
        gc.ArtifactSpec(
            key="ui_handoff",
            label="frontend/UI handoff (shadcn template + UI/UX handoff)",
            patterns=("*ui*.md", "*frontend*.md", "*handoff*.md", "*design-system*.md"),
            requirement="conditional",
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
