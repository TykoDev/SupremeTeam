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

import re
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

MANIFEST = gc.Manifest(
    boundary="redesign phase-exit (redesign-review)",
    sub_orchestrator="design/redesign",
    artifacts=(
        gc.ArtifactSpec(
            key="design_inventory",
            label="design inventory (JSON parity contract and report)",
            patterns=("*design-inventory*.json", "*design-inventory*.md", "*inventory*.md"),
            content_marker=r"routes?|components?|states?|flows?",
        ),
        gc.ArtifactSpec(
            key="taste_grilling",
            label="taste grilling log",
            patterns=("*taste*grill*.md", "*grilling*taste*.md", "*taste-grilling*"),
            content_marker=r"categor\w*|preferences?|recommend\w*|decisions?",
        ),
        gc.ArtifactSpec(
            key="design_directions",
            label="four design directions with Taste traceability",
            patterns=("*direction*.md",),
            content_marker=r"directions?|differentiat\w*|taste",
        ),
        gc.ArtifactSpec(
            key="variant_specs",
            label="mock and variant specifications (one variant.md per mock, and per built variant)",
            patterns=("*variant*.md",),
            content_marker=r"Component Template|UI/UX Handoff|tokens?",
        ),
        gc.ArtifactSpec(
            key="selection",
            label="recorded selection (decision, chosen mock or merge brief or deferral)",
            patterns=("*selection*.md",),
            content_marker=r"decisions?|chosen|merge\w*|defer\w*",
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
            content_marker=r"recommend\w*|decisions?|matri(?:x|ces)",
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


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST, extra_checks=(check_mock_first_layout,)))
