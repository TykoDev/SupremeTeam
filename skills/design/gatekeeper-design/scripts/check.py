#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-design`` — the design phase-exit
boundary.

Validates that a design packet carries the research evidence, project plan,
architecture decisions, and implementation spec for the phase exit, plus the
stack lock and Taste snapshot unless the sanctioned waiver for either applies —
and surfaces the conditional API-contract and frontend/UI-handoff artifacts as
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

# Design phase-exit artifact set (SKILL.md workflow step 1), matched by file name
# and proved by a whole-word marker in the file. The stack lock and the Taste
# snapshot are not declared optional here: gates.yaml lets a submitter waive
# stack_lock and taste_snapshot, so the engine reads that and reports an absent
# one UNCHECKED. API contracts and the frontend/UI handoff are CONDITIONAL —
# required only when endpoints or a user-facing surface are in scope, which the
# script cannot determine, so their absence is reported as UNCHECKED for the model
# to resolve against the actual scope and the design-doctrine / api-endpoint-design
# contracts.
MANIFEST = gc.Manifest(
    boundary="design phase-exit",
    sub_orchestrator="design/commander",
    pipeline="design",
    artifacts=(
        gc.ArtifactSpec(
            key="research",
            label="research evidence",
            patterns=("*research*.md", "deliverable_*research*.md", "requirements-brief.md"),
            content_marker=r"research\w*|findings?|evidence|sources?",
            stages=("research",),
        ),
        gc.ArtifactSpec(
            key="plan",
            label="project plan",
            patterns=("*plan*.md", "deliverable_*plan*.md"),
            content_marker=r"plans?|planning|milestones?|phases?|scope",
            stages=("plan",),
        ),
        gc.ArtifactSpec(
            key="architecture",
            label="architecture decisions (ADRs)",
            patterns=("*architect*.md", "*adr*.md", "deliverable_*arch*.md"),
            content_marker=r"architect\w*|decisions?|components?|ADR",
            stages=("architecture",),
        ),
        gc.ArtifactSpec(
            key="stack_locks",
            label="locked technology choices / stack locks",
            patterns=("*stack*.md", "*lock*.md", "*tech*.md"),
            content_marker=r"stacks?|locks?|locked|versions?|dependenc\w*",
            evidence_key="stack_lock",
            stages=("stack-lock",),
        ),
        gc.ArtifactSpec(
            key="taste_snapshot",
            label="effective Taste profile snapshot",
            patterns=("*taste*snapshot*", "*effective*profile*"),
            content_marker=r"canonical digest|source revisions?|resolved entries|applicability",
            evidence_key="taste_snapshot",
            stages=("taste-snapshot",),
        ),
        gc.ArtifactSpec(
            key="impl_spec",
            label="implementation specification",
            patterns=("*spec*.md", "*implementation*.md", "deliverable_*spec*.md"),
            content_marker=r"specs?|specification|interfaces?|contracts?|implement\w*",
            stages=("implementation-spec",),
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
            patterns=("ui-*.md", "*_ui*.md", "*-ui*.md", "*frontend*.md", "*handoff*.md", "*design-system*.md"),
            requirement="conditional",
            stages=("interface-and-design-system",),
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
