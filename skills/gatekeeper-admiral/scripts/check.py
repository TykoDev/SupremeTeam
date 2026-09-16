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



def _find_repo_root():
    """Return the working-tree root: the nearest ancestor that contains
    harness/gatekeeper/_gatecheck.py, or None if it cannot be located."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "harness" / "gatekeeper" / "_gatecheck.py").exists():
            return parent
    return None


_REPO_ROOT = _find_repo_root()


def _validate_package_dir(raw):
    """Confine the untrusted <package-dir> argument to an existing directory
    inside the working tree before the engine reads it. Enforcing this in code,
    not only in SKILL.md prose, stops a malformed or manipulated context from
    pointing the gate at a non-existent path or at files outside the tree.
    Exits 2 - the "cannot run, validate by hand" code - on any violation, and
    refuses when the root cannot be located rather than skipping the check: a
    gate that fails open is worse than no gate."""
    resolved = Path(raw).resolve()
    if not resolved.is_dir():
        sys.stderr.write(
            f"ERROR: <package-dir> does not exist or is not a directory: {raw!r}\n")
        sys.exit(2)
    if _REPO_ROOT is None:
        sys.stderr.write(
            "ERROR: cannot locate the working-tree root, so <package-dir> containment "
            "cannot be verified; refusing to read it.\n")
        sys.exit(2)
    if _REPO_ROOT not in (resolved, *resolved.parents):
        sys.stderr.write(
            f"ERROR: <package-dir> {resolved} is outside the working tree "
            f"{_REPO_ROOT}; refusing to read it.\n")
        sys.exit(2)
    return resolved


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
