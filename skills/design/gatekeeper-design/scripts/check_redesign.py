#!/usr/bin/env python3
"""
Deterministic package-shape check for ``gatekeeper-design`` at the
``redesign-review`` boundary.

Validates that a redesign phase directory carries the design inventory, the
taste grilling log, the four design directions, one specification per variant,
the comparison and decision package, and parity evidence, then applies the
shared lineage, skip-record, blocked-phrase, idempotency, and harness-doctrine
§5 checks. The evidence contract itself (typed records, hashes, the four-variant
count) is validated by ``harness/gatekeeper/check.py --boundary redesign-review``.

Reports PASS / FAIL / UNCHECKED facts only; the skill issues the verdict.
See ../SKILL.md and ../references/workflow.md.

Usage:
    python check_redesign.py <redesign-phase-dir> [--prior <verdict-file>] [--json]
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

MANIFEST = gc.Manifest(
    boundary="redesign phase-exit (redesign-review)",
    sub_orchestrator="design/redesign",
    artifacts=(
        gc.ArtifactSpec(
            key="design_inventory",
            label="design inventory (JSON parity contract and report)",
            patterns=("*design-inventory*.json", "*design-inventory*.md", "*inventory*.md"),
            content_marker=r"route|component|state|flow",
        ),
        gc.ArtifactSpec(
            key="taste_grilling",
            label="taste grilling log",
            patterns=("*taste*grill*.md", "*grilling*taste*.md", "*taste-grilling*"),
            content_marker=r"category|preference|recommend|decision",
        ),
        gc.ArtifactSpec(
            key="design_directions",
            label="four design directions with Taste traceability",
            patterns=("*direction*.md",),
            content_marker=r"direction|differentiat|taste",
        ),
        gc.ArtifactSpec(
            key="variant_specs",
            label="variant specifications (one variant.md per design-system variant)",
            patterns=("*variant*.md",),
            content_marker=r"Component Template|UI/UX Handoff|token",
        ),
        gc.ArtifactSpec(
            key="parity_evidence",
            label="parity records from check_parity.py",
            patterns=("*parity*.json",),
        ),
        gc.ArtifactSpec(
            key="redesign_package",
            label="comparison matrix, recommendation, and recorded decision",
            patterns=("*redesign-package*.md", "*comparison*.md"),
            content_marker=r"recommend|decision|matrix",
        ),
        gc.ArtifactSpec(
            key="rendered_verification",
            label="rendered verification captures or record per variant",
            patterns=("*render*", "*capture*"),
            requirement="conditional",
        ),
    ),
)


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST))
