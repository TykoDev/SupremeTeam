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



# A project root is recognised by one of these markers, matching
# harness/hooks/_state.py ``_ROOT_MARKERS`` so both locate the same directory.
_ROOT_MARKERS = ("skillset-saves", ".harness-state", ".git")


def _find_repo_root():
    """Return the root a package may live under.

    Packages are written to ``<project>/skillset-saves/runs/<id>/<phase>``,
    which is a *sibling* of the catalog when the catalog is vendored as
    ``<project>/skills``. Confining to the catalog root therefore refused every
    path the save protocol actually produces, so containment is checked against
    the nearest project marker at or above the catalog, and falls back to the
    catalog itself for a standalone checkout.
    """
    here = Path(__file__).resolve()
    catalog = None
    for parent in here.parents:
        if (parent / "harness" / "gatekeeper" / "_gatecheck.py").exists():
            catalog = parent
            break
    if catalog is None:
        return None
    for candidate in (catalog, *catalog.parents):
        try:
            if any((candidate / marker).exists() for marker in _ROOT_MARKERS):
                return candidate
        except OSError:
            continue
    return catalog


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
    _args = sys.argv[1:]
    _pkg_idx = next((i for i, a in enumerate(_args) if not a.startswith("-")), None)
    if _pkg_idx is None:
        sys.stderr.write(
            "ERROR: <package-dir> is required. "
            "Usage: python check_redesign.py <package-dir> [--prior <verdict-file>] [--json]\n")
        sys.exit(2)
    # Validate and normalize the untrusted path before the engine consumes it.
    sys.argv[1 + _pkg_idx] = str(_validate_package_dir(_args[_pkg_idx]))
    sys.exit(gc.main_with_manifest(MANIFEST))
