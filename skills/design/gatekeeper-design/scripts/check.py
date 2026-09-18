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



# A project root is recognised by one of these markers, matching
# harness/hooks/_state.py ``_ROOT_MARKERS`` so both locate the same directory.
_ROOT_MARKERS = ("skillset-saves", ".harness-state", ".git")


def _find_catalog_root():
    """Nearest ancestor holding harness/gatekeeper/_gatecheck.py, else None.

    This is where the shared engine lives, which is not necessarily where
    packages live: the catalog can be vendored inside a larger project.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "harness" / "gatekeeper" / "_gatecheck.py").exists():
            return parent
    return None


def _find_repo_root():
    """Return the root a package may live under.

    Packages are written to ``<project>/skillset-saves/runs/<id>/<phase>``,
    which is a *sibling* of the catalog when the catalog is vendored as
    ``<project>/skills``. Confining to the catalog root therefore refused every
    path the save protocol actually produces, so containment is checked against
    the nearest project marker at or above the catalog, and falls back to the
    catalog itself for a standalone checkout.
    """
    catalog = _find_catalog_root()
    if catalog is None:
        return None
    for candidate in (catalog, *catalog.parents):
        try:
            if any((candidate / marker).exists() for marker in _ROOT_MARKERS):
                return candidate
        except OSError:
            continue
    return catalog


_CATALOG_ROOT = _find_catalog_root()
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
    # Reuse the catalog root already located. _REPO_ROOT is deliberately wider
    # (it may be a parent of the catalog, so packages under skillset-saves/
    # validate); the engine lives under the catalog, so resolve against that.
    if _CATALOG_ROOT is not None:
        sys.path.insert(0, str(_CATALOG_ROOT / "harness" / "gatekeeper"))
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
            key="taste_snapshot",
            label="effective Taste profile snapshot",
            patterns=("*taste*snapshot*", "*effective*profile*"),
            content_marker=r"canonical digest|source revisions|resolved entries|applicability",
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
    _args = sys.argv[1:]
    # Options that consume the following argument. Without this, the value of
    # such a flag is the first non-dash token, so `--prior <file> <pkg>` would
    # validate <file> as the package directory and check the wrong tree.
    _VALUE_OPTS = ("--prior", "--blocked-phrases")
    _pkg_idx, _skip = None, False
    for _i, _a in enumerate(_args):
        if _skip:
            _skip = False
            continue
        if _a in _VALUE_OPTS:
            _skip = True
            continue
        if _a.startswith("-"):
            continue
        _pkg_idx = _i
        break
    if _pkg_idx is None:
        sys.stderr.write(
            "ERROR: <package-dir> is required. "
            "Usage: python check.py <package-dir> [--prior <verdict-file>] [--json]\n")
        sys.exit(2)
    # Validate and normalize the untrusted path before the engine consumes it.
    sys.argv[1 + _pkg_idx] = str(_validate_package_dir(_args[_pkg_idx]))
    sys.exit(gc.main_with_manifest(MANIFEST))
