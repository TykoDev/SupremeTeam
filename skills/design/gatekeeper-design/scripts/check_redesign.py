#!/usr/bin/env python3
"""
Deterministic package-shape check for ``gatekeeper-design`` at the
``redesign-review`` boundary.

Validates that a redesign phase directory carries the design inventory, the
taste grilling log, the four design directions, one specification per mock, the
recorded selection, the comparison and decision package, and parity evidence,
then applies the shared lineage, skip-record, blocked-phrase, idempotency, and
harness-doctrine §5 checks. The evidence contract itself (typed records, hashes,
the four-mock count, the selection rule) is validated by
``harness/gatekeeper/check.py --boundary redesign-review``.

On top of the shared engine this gate checks the mock-first *layout*, which is
where a package that reverted to building four prototypes shows up first:

  * ``artifacts/mocks/<id>/mock.html`` for exactly four mock ids;
  * ``reports/selection.md``, the recorded decision;
  * ``artifacts/variants/<id>/app.html`` only when that decision named a
    variant - a merge or a deferral that shipped a living prototype anyway
    built the thing the decision said not to build, and four of them is the
    build-three-to-throw-away shape the pipeline exists to avoid.

Reports PASS / FAIL / UNCHECKED facts only; the skill issues the verdict.
See ../SKILL.md and ../references/workflow.md.

Usage:
    python check_redesign.py <redesign-phase-dir> [--prior <verdict-file>] [--json]
"""

import json
import re
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
            label="mock and variant specifications (one variant.md per mock, and per built variant)",
            patterns=("*variant*.md",),
            content_marker=r"Component Template|UI/UX Handoff|token",
        ),
        gc.ArtifactSpec(
            key="selection",
            label="recorded selection (decision, chosen mock or merge brief or deferral)",
            patterns=("*selection*.md",),
            content_marker=r"decision|chosen|merge|defer",
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


#: The mock field the pipeline fans out, mirroring
#: ``gates.yaml`` ``evidence_type_params.mock_set.required_count``.
MOCK_COUNT = 4

#: ``decision: variant`` in frontmatter, or a "Decision: variant" line in the
#: body. Anything else leaves the decision unread, which is UNCHECKED rather
#: than a pass: the layout rule below depends on knowing what was decided.
_DECISION = re.compile(
    r"^[\s>*\-|]*\**decision\**\s*[:=|]\s*\**\s*[`\"']?(variant|merge|deferred)\b",
    re.I | re.M)


def read_decision(root):
    """The recorded decision, or None when the package does not state one."""
    selection = root / "reports" / "selection.md"
    if not selection.is_file():
        return None
    text = selection.read_text(encoding="utf-8", errors="replace")
    front = gc.parse_frontmatter(text)
    declared = str(front.get("decision", "")).strip().lower()
    if declared in ("variant", "merge", "deferred"):
        return declared
    match = _DECISION.search(text)
    return match.group(1).lower() if match else None


def check_mock_first_layout(root, report):
    """The four mocks, the recorded selection, and at most one built variant."""
    report.checks_run.append("mock_first_layout")
    mocks_dir = root / "artifacts" / "mocks"
    mocks = sorted(p.name for p in mocks_dir.iterdir()
                   if p.is_dir() and (p / "mock.html").is_file()) if mocks_dir.is_dir() else []
    if len(mocks) == MOCK_COUNT:
        report.add(gc.Finding(
            code="MOCK_SET_COMPLETE", severity="info", status=gc.PASS,
            message=f"Four mock drafts present: {', '.join(mocks)}.",
            location="artifacts/mocks",
        ))
    else:
        report.add(gc.Finding(
            code="MOCK_SET_INCOMPLETE", severity="major", status=gc.FAIL,
            message=(f"{len(mocks)} of {MOCK_COUNT} mock drafts carry "
                     f"artifacts/mocks/<id>/mock.html. The field is compared as mocks, "
                     f"so a short field is a comparison with a predetermined winner."),
            location="artifacts/mocks",
        ))

    decision = read_decision(root)
    if not (root / "reports" / "selection.md").is_file():
        report.add(gc.Finding(
            code="SELECTION_MISSING", severity="major", status=gc.FAIL,
            message=("reports/selection.md is absent. The decision that authorises "
                     "the one living prototype is not recorded anywhere."),
            location="reports/selection.md",
        ))
    elif decision is None:
        report.add(gc.Finding(
            code="SELECTION_DECISION_UNREAD", severity="minor", status=gc.UNCHECKED,
            message=("reports/selection.md states no decision this script can read "
                     "(frontmatter `decision:` or a 'Decision: variant|merge|deferred' "
                     "line). Confirm what was decided before judging the build."),
            location="reports/selection.md",
        ))
    else:
        report.add(gc.Finding(
            code="SELECTION_RECORDED", severity="info", status=gc.PASS,
            message=f"Selection recorded: decision '{decision}'.",
            location="reports/selection.md",
        ))

    variants_dir = root / "artifacts" / "variants"
    built = sorted(p.name for p in variants_dir.iterdir()
                   if p.is_dir() and (p / "app.html").is_file()) if variants_dir.is_dir() else []
    if decision == "variant":
        if len(built) == 1:
            report.add(gc.Finding(
                code="SELECTED_BUILD_PRESENT", severity="info", status=gc.PASS,
                message=f"One living prototype built, for '{built[0]}'.",
                location="artifacts/variants",
            ))
        else:
            report.add(gc.Finding(
                code="SELECTED_BUILD_COUNT", severity="major", status=gc.FAIL,
                message=(f"The decision names a variant but {len(built)} directories carry "
                         f"artifacts/variants/<id>/app.html. Exactly one prototype is built, "
                         f"for the chosen mock."),
                location="artifacts/variants",
            ))
    elif decision in ("merge", "deferred"):
        if built:
            report.add(gc.Finding(
                code="UNSELECTED_BUILD_PRESENT", severity="major", status=gc.FAIL,
                message=(f"The decision is '{decision}', which selects no variant, but "
                         f"{', '.join(built)} carries a living prototype. Nothing is built "
                         f"until a draft is chosen."),
                location="artifacts/variants",
            ))
        else:
            report.add(gc.Finding(
                code="NO_BUILD_AS_DECIDED", severity="info", status=gc.PASS,
                message=f"No living prototype, as a '{decision}' decision requires.",
                location="artifacts/variants",
            ))
    elif built:
        report.add(gc.Finding(
            code="BUILD_WITHOUT_READABLE_DECISION", severity="minor", status=gc.UNCHECKED,
            message=(f"{', '.join(built)} carries a living prototype but the decision could "
                     f"not be read. Confirm the build was authorised by the selection."),
            location="artifacts/variants",
        ))


def main(argv=None):
    """The shared engine plus this boundary's layout check, same envelope."""
    parser = gc.build_arg_parser(f"Deterministic gate check for {MANIFEST.boundary}.")
    args = parser.parse_args(argv)
    try:
        report = gc.run_gate(
            Path(args.package), MANIFEST,
            prior_path=Path(args.prior) if args.prior else None,
            blocked_phrases_path=Path(args.blocked_phrases) if args.blocked_phrases else None,
        )
        # Only when the package itself was readable: an empty or missing package
        # has already failed critically and a layout check would just repeat it.
        if not any(f.code in ("PACKAGE_NOT_FOUND", "PACKAGE_EMPTY") for f in report.findings):
            check_mock_first_layout(Path(args.package), report)
    except Exception as exc:  # fail loud - never a silent pass
        err = {
            "boundary": MANIFEST.boundary,
            "gate_status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "note": "Gate could not be evaluated deterministically. Do NOT "
                    "approve on structure; resolve the error or validate by hand.",
        }
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"# Gate check — {MANIFEST.boundary}\n\n"
                  f"**ERROR**: {err['error']}\n\n{err['note']}")
        return 2
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(gc.render_markdown(report))
    return report.exit_code()


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
    sys.exit(main(sys.argv[1:]))
