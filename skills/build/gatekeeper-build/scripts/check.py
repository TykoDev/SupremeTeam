#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-build`` — the build→review boundary.

Validates that a build-phase packet attaches the implementation diff, test
evidence, security outcome (when the build touched a trust boundary),
cross-check completeness certification, and the build-gate verdict for one
coherent revision — plus the shared lineage, skip-record, blocked-phrase,
idempotency, and harness-doctrine §5 checks.

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

# `diff` as a part of a file name, not the start of "different".
_DIFF_NAMES = ("diff.md", "diff[-_.]*.md", "*[-_.]diff.md", "*[-_.]diff[-_.]*.md")

# Required build-to-review evidence set (SKILL.md workflow step 2), matched by
# file name and proved by a whole-word marker in the file. The security outcome is
# not declared optional here: gates.yaml lets a submitter waive security_evidence
# and pipelines.yaml runs security-checkpoint only on a trust-boundary change, so
# the engine reads both and reports an absent outcome UNCHECKED.
MANIFEST = gc.Manifest(
    boundary="build-to-review",
    sub_orchestrator="build/build-management",
    pipeline="build",
    artifacts=(
        gc.ArtifactSpec(
            key="implementation",
            label="implementation diff / change summary",
            patterns=("*implementation*.md", "deliverable_*build*.md", *_DIFF_NAMES),
            content_marker=r"implement\w*|changed files?|diff|modules?",
            stages=("implementation",),
        ),
        gc.ArtifactSpec(
            key="tests",
            label="test-builder evidence (execution results)",
            patterns=("*test*.md", "deliverable_*test*.md"),
            content_marker=r"tests?|testing|coverage|pass(?:ed|es)?|fail(?:ed|s|ures?)?|suites?",
            stages=("test-surface",),
        ),
        gc.ArtifactSpec(
            key="security",
            label="security-builder outcome (findings or clean bill)",
            patterns=("*security*.md", "deliverable_*security*.md"),
            content_marker=r"security|vulnerab\w*|clean bill|findings?",
            evidence_key="security_evidence",
            stages=("security-checkpoint",),
        ),
        gc.ArtifactSpec(
            key="completeness",
            label="cross-check-build-confirm completeness certification",
            patterns=("*cross-check*.md", "*completeness*.md", "*confirm*.md"),
            content_marker=r"complet\w*|certif\w*|confirm\w*",
            stages=("completeness-cross-check",),
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
