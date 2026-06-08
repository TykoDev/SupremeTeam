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


def _find_repo_root():
    """Return the working-tree root: the nearest ancestor that contains
    harness/gatekeeper/_gatecheck.py, or None if it cannot be located."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "harness" / "gatekeeper" / "_gatecheck.py").exists():
            return parent
    return None


_REPO_ROOT = _find_repo_root()


def _load_engine():
    if _REPO_ROOT is not None:
        sys.path.insert(0, str(_REPO_ROOT / "harness" / "gatekeeper"))
        import _gatecheck  # type: ignore
        return _gatecheck
    sys.stderr.write(
        "ERROR: could not locate harness/gatekeeper/_gatecheck.py above "
        f"{Path(__file__).resolve()}. Gate cannot run; validate by hand.\n")
    sys.exit(2)


def _validate_package_dir(raw):
    """Confine the untrusted <package-dir> argument to an existing directory
    inside the working tree before the engine reads it. Enforcing this in code
    (not only in SKILL.md prose) stops a malformed or manipulated build context
    from pointing the gate at a non-existent path or arbitrary files outside the
    tree. Exits 2 — the 'cannot run, validate by hand' code — on any violation."""
    resolved = Path(raw).resolve()
    if not resolved.is_dir():
        sys.stderr.write(
            f"ERROR: <package-dir> does not exist or is not a directory: {raw!r}\n")
        sys.exit(2)
    if _REPO_ROOT is not None and _REPO_ROOT not in (resolved, *resolved.parents):
        sys.stderr.write(
            f"ERROR: <package-dir> {resolved} is outside the working tree "
            f"{_REPO_ROOT}; refusing to read it.\n")
        sys.exit(2)
    return resolved


gc = _load_engine()

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
    _args = sys.argv[1:]
    _pkg_idx = next((i for i, a in enumerate(_args) if not a.startswith("-")), None)
    if _pkg_idx is None:
        sys.stderr.write(
            "ERROR: <package-dir> is required. "
            "Usage: python check.py <package-dir> [--prior <verdict-file>] [--json]\n")
        sys.exit(2)
    # Validate and normalize the untrusted path before the engine consumes it.
    sys.argv[1 + _pkg_idx] = str(_validate_package_dir(_args[_pkg_idx]))
    sys.exit(gc.main_with_manifest(MANIFEST))
