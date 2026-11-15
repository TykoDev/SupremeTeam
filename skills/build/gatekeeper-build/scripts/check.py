#!/usr/bin/env python3
"""
Deterministic gate check for ``gatekeeper-build`` — the build→review boundary.

Validates that a build-phase packet attaches the implementation diff, test
evidence, security outcome (when the build touched a trust boundary),
cross-check completeness certification, and the build-gate verdict for one
coherent revision — plus the shared lineage, skip-record, blocked-phrase,
idempotency, and harness-doctrine §5 checks.

The completeness certificate is read from one place, ``reports/report_completeness.md``
(the path ``cross-check-build-confirm`` resolves), and has to declare the package's
revision. A file of that kind anywhere else does not fill the slot, and a certificate
kept from an earlier revision is set aside with ``skills/scripts/run_files.py supersede``.

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
        f"{here}. Gate cannot run; ESCALATE to user through admiral.\n")
    sys.exit(2)


gc = _engine()

# The one place the completeness certificate is read from: the path
# `output_paths.py --phase build --kind reports --name report_completeness.md` resolves.
# Found by name alone, the slot was filled by an old copy in archive/ and by an
# unrelated reports/deploy-confirmation.md.
COMPLETENESS_PATH = "reports/report_completeness.md"

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
            patterns=("*completeness*.md",),
            exact_paths=(COMPLETENESS_PATH,),
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


def _number(token):
    """A revision token without its label: ``r3`` and ``3`` are the same revision."""
    text = str(token).strip()
    return text[1:] if text[:1] in "rR" and text[1:].isdigit() else text


def _package_revision(root):
    """``(revision, where it is declared)`` for the package, or ``(None, "")``: the phase manifest's ``revision``, else
    the one revision the other current artifacts agree on."""
    manifest = root / "manifest.json"
    if manifest.is_file():
        token = gc._revision_token(gc._read_record(manifest).get("revision"))
        if token is not None:
            return token, "manifest.json"
    certificate = root / COMPLETENESS_PATH
    declared = {token for path in gc.iter_package_files(root) if path != certificate
                for token in [gc._revision_token(gc.parse_frontmatter(gc._read(path)).get("revision"))] if token is not None}
    return (next(iter(declared)), "the other artifacts") if len(declared) == 1 else (None, "")


def check_completeness_revision(root, report):
    """The certificate certifies one revision, and it has to be this one. A certificate left from the previous
    submission still names the completeness slot, so the slot alone cannot tell a fresh pass from a stale one."""
    report.checks_run.append("completeness_revision")
    certificate = root / COMPLETENESS_PATH
    if not certificate.is_file():
        return  # the slot reports the missing certificate
    package, source = _package_revision(root)
    if package is None:
        return  # no revision to hold it to; lineage reports a package that declares none
    declared = gc._revision_token(gc.parse_frontmatter(gc._read(certificate)).get("revision"))
    if declared is not None and _number(declared) == _number(package):
        report.add(gc.Finding(
            code="COMPLETENESS_REVISION_OK", severity="info", status=gc.PASS,
            message=f"The completeness certificate is for revision {package}, the package's ({source}).",
            location=COMPLETENESS_PATH))
        return
    stated = f"declares revision {declared}" if declared is not None else "declares no revision in its frontmatter"
    report.add(gc.Finding(
        code="COMPLETENESS_REVISION_MISMATCH", severity="major", status=gc.FAIL,
        message=(f"{COMPLETENESS_PATH} {stated}; the package is at revision {package} ({source}). A certificate "
                 f"certifies one revision: run cross-check-build-confirm for this one, after setting the previous "
                 f"certificate aside with `python skills/scripts/run_files.py supersede --phase build --path "
                 f"{COMPLETENESS_PATH} --by-revision {_number(package)}`."),
        location=COMPLETENESS_PATH))


if __name__ == "__main__":
    sys.exit(gc.main_with_manifest(MANIFEST, extra_checks=(check_completeness_revision,)))
