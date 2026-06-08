#!/usr/bin/env python3
"""
Deterministic gate-check engine for the SupremeTeam ``gatekeeper-*`` skills.

This is the shared library behind every gatekeeper's ``scripts/check.py``. It
turns the *mechanically checkable* parts of a cross-stage / phase-exit package
validation into a deterministic Python pass, so the gatekeeper skill no longer
re-derives them as prose each run. The model still owns every *judgment* call
(design coherence, contradiction detection, scope-creep, residual reasoning) —
this engine only reports structural facts.

Doctrine alignment (../../harness-doctrine.md):
  - §0 / §3 *inert on the strong case*: every check fires only on a mechanically
    certain signal (a missing required file, two distinct ``revision:`` values, a
    literal blocked phrase). A clean, coherent package produces zero findings, so
    the engine never manufactures work on a competent package.
  - §2.4 *residual reasoning is out of scope*: the engine deliberately does NOT
    emit a verdict. It reports PASS / FAIL / UNCHECKED facts; the skill combines
    them with judgment to choose APPROVED / REVISE / ESCALATE.
  - §5 *gate behavior*: the harness-doctrine structural check surfaces a package
    that touches a cross-cutting runtime intervention without a layer citation or
    regression note, so the gatekeeper can cite the section by number.

Posture difference vs. ``harness/hooks`` (which FAIL OPEN): a gate must **fail
loud**. A hook that errors lets the action proceed; a gate that cannot prove a
package is clean must NOT silently approve it. So an internal error becomes an
``UNCHECKED`` finding and a non-zero exit, never a hidden PASS.

Stdlib only — runs on any host Python 3.8+, no ``pip install``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# --- Shared four-tier severity model (cited by every gatekeeper) --------------
# critical: package is untrusted / cannot advance without external judgment.
# major:    a blocking defect the owning orchestrator must fix before advancing.
# minor:    a non-blocking gap worth recording.
# info:     an observation or a check the model must resolve with judgment.
SEVERITIES = ("critical", "major", "minor", "info")

# Per-check outcome.
PASS = "PASS"        # the mechanical condition held
FAIL = "FAIL"        # the mechanical condition was violated
UNCHECKED = "UNCHECKED"  # could not be evaluated deterministically — model must resolve

# Text file suffixes the engine reads. A package is markdown by contract
# (save-protocol.md §2), with the occasional plain-text override list.
_TEXT_SUFFIXES = (".md", ".markdown", ".txt", ".yaml", ".yml")

# Default blocked phrases: hollow-completion claims and contamination markers
# that must never appear in a clean delivery package. Entries beginning with
# ``re:`` are treated as regular expressions (used for word-bounded code-rot
# markers); all others are literal, case-insensitive substrings. Each gate can
# extend this set with a ``blocked-phrases.txt`` file next to its check.py.
DEFAULT_BLOCKED_PHRASES = (
    "trust me",
    "works on my machine",
    "100% complete",
    "no issues whatsoever",
    "lorem ipsum",
    "placeholder content",
    "as an ai language model",
    "i cannot actually",
    r"re:\bTODO\b",
    r"re:\bFIXME\b",
    r"re:\bXXX\b",
    r"re:\bHACK\b",
)

# Tokens that signal a package adds or changes a cross-cutting runtime
# intervention (harness-doctrine §5). Their presence alone is not a defect — it
# only triggers the §5 structural check for a layer citation + regression note.
_INTERVENTION_MARKERS = re.compile(
    r"\b(?:PreToolUse|PostToolUse|pre_tool_use|post_tool_use|"
    r"runtime\s+hook|tool[-\s]?use\s+hook|action\s+realization|"
    r"trajectory\s+regulation|guard\s+boundary|freeze\s+boundary)\b",
    re.IGNORECASE,
)
_LAYER_CITATION = re.compile(
    r"\b(?:Layer\s*[1-4]|§\s*[1-5]|harness-doctrine)\b", re.IGNORECASE
)
_REGRESSION_NOTE = re.compile(r"\bregression\b", re.IGNORECASE)


# =============================================================================
# Data model
# =============================================================================

@dataclass
class Finding:
    """One deterministic observation about the package."""

    code: str           # stable id, e.g. "ARTIFACT_MISSING"
    severity: str       # one of SEVERITIES
    status: str         # PASS | FAIL | UNCHECKED
    message: str
    location: str = ""  # file / artifact / "package"

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "location": self.location,
        }


@dataclass
class ArtifactSpec:
    """A required (or conditional) package artifact, matched by filename glob
    and/or a content marker regex.

    requirement:
      - "required":    absence is a MAJOR FAIL.
      - "conditional": absence is an INFO UNCHECKED — the engine cannot know
        whether this artifact is in scope (e.g. API contracts only when
        endpoints exist), so the model must confirm. Presence is a PASS.
    """

    key: str
    label: str
    patterns: Sequence[str]
    content_marker: Optional[str] = None
    requirement: str = "required"


@dataclass
class Manifest:
    """A boundary's deterministic acceptance shape, declared by each gate."""

    boundary: str
    sub_orchestrator: str
    artifacts: Sequence[ArtifactSpec] = field(default_factory=tuple)


@dataclass
class Report:
    boundary: str
    package_path: str
    findings: List[Finding] = field(default_factory=list)
    checks_run: List[str] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    # --- Aggregates the skill reads to scope its verdict ---------------------
    @property
    def failures(self) -> List[Finding]:
        return [f for f in self.findings if f.status == FAIL]

    @property
    def unchecked(self) -> List[Finding]:
        return [f for f in self.findings if f.status == UNCHECKED]

    @property
    def has_blocking(self) -> bool:
        return any(f.status == FAIL and f.severity in ("critical", "major")
                   for f in self.findings)

    def gate_status(self) -> str:
        """A deterministic summary status — NOT a verdict.

        STRUCTURE_OK   : every deterministic check passed; nothing blocks on
                         structure. The skill may APPROVE if judgment agrees.
        BLOCKERS_PRESENT: at least one major/critical FAIL — the skill must not
                         APPROVE without resolving it.
        NEEDS_JUDGMENT : no blocking failures, but UNCHECKED items remain for the
                         model to resolve (conditional artifacts, §5, idempotency).
        """
        if self.has_blocking:
            return "BLOCKERS_PRESENT"
        if self.unchecked:
            return "NEEDS_JUDGMENT"
        return "STRUCTURE_OK"

    def exit_code(self) -> int:
        # Fail loud: any blocking failure is a non-zero exit so a caller that
        # only checks the return code never mistakes a defect for a pass.
        return 1 if self.has_blocking else 0

    def to_dict(self) -> dict:
        return {
            "boundary": self.boundary,
            "package_path": self.package_path,
            "gate_status": self.gate_status(),
            "checks_run": self.checks_run,
            "counts": {
                "fail": len(self.failures),
                "unchecked": len(self.unchecked),
                "total": len(self.findings),
            },
            "findings": [f.to_dict() for f in self.findings],
        }


# =============================================================================
# Minimal frontmatter parsing (stdlib only — no PyYAML dependency)
# =============================================================================

def parse_frontmatter(text: str) -> dict:
    """Parse a leading ``---`` YAML frontmatter block into a flat-ish dict.

    Supports the shapes used in save-protocol.md §2: ``key: value`` scalars,
    inline ``[a, b]`` lists, block ``- item`` lists, and one level of nested
    mapping. Conservative by design: anything it cannot parse is skipped, never
    raised — but an *empty* result on a file that clearly has frontmatter is the
    caller's signal to treat the field as absent, not as a silent pass.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    block: List[str] = []
    closed = False
    for line in lines[1:]:
        if line.strip() == "---":
            closed = True
            break
        block.append(line)
    if not closed:
        return {}
    return _parse_yaml_block(block)


def _coerce(value: str):
    v = value.strip()
    if not v:
        return ""
    if (v[0] == v[-1]) and v[0] in ("'", '"') and len(v) >= 2:
        return v[1:-1]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_coerce(p) for p in inner.split(",")]
    low = v.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", "~"):
        return None
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v


def _parse_yaml_block(block: List[str]) -> dict:
    result: dict = {}
    i = 0
    n = len(block)
    while i < n:
        raw = block[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest:
            result[key] = _coerce(rest)
            i += 1
            continue
        # No inline value: look ahead for a block list or nested mapping.
        j = i + 1
        children: List[str] = []
        child_indent = None
        while j < n:
            craw = block[j]
            if not craw.strip():
                j += 1
                continue
            cindent = len(craw) - len(craw.lstrip())
            if cindent <= indent:
                break
            if child_indent is None:
                child_indent = cindent
            children.append(craw)
            j += 1
        if children and all(c.strip().startswith("- ") for c in children):
            result[key] = [_coerce(c.strip()[2:]) for c in children]
        elif children:
            nested = _parse_yaml_block([c[child_indent:] if child_indent else c
                                        for c in children])
            result[key] = nested
        else:
            result[key] = ""
        i = j
    return result


# =============================================================================
# Package discovery
# =============================================================================

def iter_package_files(root: Path) -> List[Path]:
    """All readable text files under the package, sorted for stable output."""
    files: List[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES:
            files.append(p)
    return files


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


# =============================================================================
# Individual deterministic checks
# =============================================================================

def check_required_artifacts(root: Path, manifest: Manifest,
                             report: Report) -> None:
    report.checks_run.append("required_artifacts")
    files = iter_package_files(root)
    rels = [_rel(f, root) for f in files]
    for spec in manifest.artifacts:
        match = _find_artifact(files, rels, spec)
        if match is not None:
            report.add(Finding(
                code="ARTIFACT_PRESENT", severity="info", status=PASS,
                message=f"{spec.label} present.", location=match,
            ))
        elif spec.requirement == "conditional":
            report.add(Finding(
                code="ARTIFACT_CONDITIONAL", severity="info", status=UNCHECKED,
                message=(f"{spec.label} not found. This artifact is required only "
                         f"when in scope — confirm whether this submission needs it."),
                location="package",
            ))
        else:
            report.add(Finding(
                code="ARTIFACT_MISSING", severity="major", status=FAIL,
                message=(f"Required artifact missing: {spec.label} "
                         f"(expected one of: {', '.join(spec.patterns)})."),
                location="package",
            ))


def _find_artifact(files: List[Path], rels: List[str],
                   spec: ArtifactSpec) -> Optional[str]:
    marker = re.compile(spec.content_marker, re.IGNORECASE) if spec.content_marker else None
    for path, rel in zip(files, rels):
        name = path.name
        if not any(_glob_match(name, pat) or _glob_match(rel, pat)
                   for pat in spec.patterns):
            continue
        if marker is None:
            return rel
        if marker.search(_read(path)):
            return rel
    return None


def _glob_match(value: str, pattern: str) -> bool:
    import fnmatch
    return fnmatch.fnmatch(value.lower(), pattern.lower())


def check_lineage(root: Path, report: Report) -> None:
    """Detect packages that mix deliverables from different revisions, and
    surface the submission id / revision the gate keys idempotency on.

    Two distinct ``revision:`` values across the package's frontmatter is the
    mechanical signature of a contaminated, mixed-revision submission.
    """
    report.checks_run.append("lineage")
    revisions: Dict[int, List[str]] = {}
    submission_ids: Dict[str, List[str]] = {}
    for path in iter_package_files(root):
        fm = parse_frontmatter(_read(path))
        rel = _rel(path, root)
        rev = fm.get("revision")
        if isinstance(rev, int):
            revisions.setdefault(rev, []).append(rel)
        sid = fm.get("submission_id")
        if isinstance(sid, str) and sid and sid.upper() != "PENDING":
            submission_ids.setdefault(sid, []).append(rel)

    if len(revisions) > 1:
        detail = "; ".join(f"revision {r}: {', '.join(locs)}"
                           for r, locs in sorted(revisions.items()))
        report.add(Finding(
            code="MIXED_REVISIONS", severity="major", status=FAIL,
            message=(f"Package mixes deliverables from {len(revisions)} different "
                     f"revisions ({detail}). Reject as untrusted and require a "
                     f"coherent single-revision set."),
            location="package",
        ))
    elif len(revisions) == 1:
        rev = next(iter(revisions))
        report.add(Finding(
            code="REVISION_COHERENT", severity="info", status=PASS,
            message=f"All revision-bearing artifacts agree on revision {rev}.",
            location="package",
        ))
    else:
        report.add(Finding(
            code="REVISION_ABSENT", severity="info", status=UNCHECKED,
            message=("No artifact declares a `revision:` in frontmatter. Confirm "
                     "the package carries lineage the next stage can trust."),
            location="package",
        ))

    if len(submission_ids) > 1:
        report.add(Finding(
            code="MIXED_SUBMISSION_IDS", severity="major", status=FAIL,
            message=(f"Package contains {len(submission_ids)} distinct submission "
                     f"ids ({', '.join(sorted(submission_ids))}). A single handoff "
                     f"must share one submission id."),
            location="package",
        ))


def check_skip_records(root: Path, report: Report) -> None:
    """Every ``_skip-record.md`` must carry the save-protocol §2 fields, so a
    skip is explicit and evidence-backed rather than a silent gap.
    """
    report.checks_run.append("skip_records")
    required = ("pipeline", "skipped_at", "reason", "approved_by")
    found_any = False
    for path in iter_package_files(root):
        if path.name != "_skip-record.md":
            continue
        found_any = True
        fm = parse_frontmatter(_read(path))
        rel = _rel(path, root)
        missing = [k for k in required if not fm.get(k)]
        if missing:
            report.add(Finding(
                code="SKIP_RECORD_INCOMPLETE", severity="major", status=FAIL,
                message=(f"Skip record is missing required field(s): "
                         f"{', '.join(missing)}. A skip must be explicit and "
                         f"evidence-backed before approval."),
                location=rel,
            ))
        else:
            report.add(Finding(
                code="SKIP_RECORD_OK", severity="info", status=PASS,
                message=f"Skip record records reason='{fm.get('reason')}' "
                        f"approved_by='{fm.get('approved_by')}'.",
                location=rel,
            ))
    if not found_any:
        report.add(Finding(
            code="NO_SKIP_RECORDS", severity="info", status=PASS,
            message="No skip records in package (none claimed).",
            location="package",
        ))


def scan_blocked_phrases(root: Path, report: Report,
                         phrases: Sequence[str]) -> None:
    """Owned by gatekeeper-admiral, available to all: any literal blocked
    phrase inside the package is a blocking defect (harness-doctrine note).
    """
    report.checks_run.append("blocked_phrases")
    literals: List[str] = []
    regexes: List[re.Pattern] = []
    for entry in phrases:
        if entry.startswith("re:"):
            try:
                regexes.append(re.compile(entry[3:]))
            except re.error:
                continue
        else:
            literals.append(entry.lower())

    hits = 0
    for path in iter_package_files(root):
        rel = _rel(path, root)
        for lineno, line in enumerate(_read(path).splitlines(), start=1):
            low = line.lower()
            for lit in literals:
                if lit in low:
                    hits += 1
                    report.add(Finding(
                        code="BLOCKED_PHRASE", severity="major", status=FAIL,
                        message=f"Blocked phrase '{lit}' found: {line.strip()[:80]}",
                        location=f"{rel}:{lineno}",
                    ))
            for rx in regexes:
                if rx.search(line):
                    hits += 1
                    report.add(Finding(
                        code="BLOCKED_PHRASE", severity="major", status=FAIL,
                        message=(f"Blocked marker /{rx.pattern}/ found: "
                                 f"{line.strip()[:80]}"),
                        location=f"{rel}:{lineno}",
                    ))
    if hits == 0:
        report.add(Finding(
            code="BLOCKED_PHRASE_CLEAN", severity="info", status=PASS,
            message="No blocked phrases or contamination markers found.",
            location="package",
        ))


def check_idempotency(root: Path, report: Report,
                      prior_path: Optional[Path]) -> None:
    """Compare the current submission against a prior verdict record so the same
    package is not re-gated under conflicting rationale, and so a reused
    submission id with changed contents is flagged as silent drift.
    """
    report.checks_run.append("idempotency")
    if prior_path is None:
        report.add(Finding(
            code="NO_PRIOR_VERDICT", severity="info", status=PASS,
            message="No prior verdict supplied; treating as a first submission.",
            location="package",
        ))
        return
    if not prior_path.exists():
        report.add(Finding(
            code="PRIOR_VERDICT_UNREADABLE", severity="minor", status=UNCHECKED,
            message=f"Prior verdict path does not exist: {prior_path}. "
                    f"Cannot confirm idempotency — verify manually.",
            location=str(prior_path),
        ))
        return

    prior = parse_frontmatter(_read(prior_path))
    prior_sid = prior.get("submission_id")
    prior_rev = prior.get("revision")
    prior_verdict = prior.get("verdict")

    cur_sids, cur_revs = set(), set()
    for path in iter_package_files(root):
        fm = parse_frontmatter(_read(path))
        if isinstance(fm.get("submission_id"), str):
            cur_sids.add(fm["submission_id"])
        if isinstance(fm.get("revision"), int):
            cur_revs.add(fm["revision"])

    same_sid = prior_sid in cur_sids if prior_sid else False
    same_rev = prior_rev in cur_revs if isinstance(prior_rev, int) else False

    if same_sid and same_rev:
        report.add(Finding(
            code="VERDICT_REUSABLE", severity="info", status=PASS,
            message=(f"Submission id and revision match the prior verdict "
                     f"(verdict={prior_verdict}). Prior verdict is reusable; do "
                     f"not re-gate under new rationale."),
            location=str(prior_path),
        ))
    elif same_sid and not same_rev:
        report.add(Finding(
            code="SILENT_DRIFT", severity="major", status=FAIL,
            message=(f"Submission id '{prior_sid}' is reused but the revision "
                     f"changed (prior={prior_rev}, current={sorted(cur_revs)}). "
                     f"Prior verdict is non-transferable; require a fresh delta."),
            location=str(prior_path),
        ))
    else:
        report.add(Finding(
            code="NEW_SUBMISSION", severity="info", status=PASS,
            message=("Submission id/revision differ from the prior verdict; "
                     "evaluating as a fresh submission."),
            location=str(prior_path),
        ))


def check_harness_doctrine(root: Path, report: Report) -> None:
    """harness-doctrine §5: a package that adds/changes a cross-cutting runtime
    intervention must name its lifecycle layer and carry a regression note.

    Inert on the strong case (§0): fires only when intervention markers are
    actually present AND a layer citation or regression note is absent. A
    package that does not touch the harness produces nothing here.
    """
    report.checks_run.append("harness_doctrine")
    touched = False
    has_layer = False
    has_regression = False
    where: List[str] = []
    for path in iter_package_files(root):
        text = _read(path)
        if _INTERVENTION_MARKERS.search(text):
            touched = True
            where.append(_rel(path, root))
            if _LAYER_CITATION.search(text):
                has_layer = True
            if _REGRESSION_NOTE.search(text):
                has_regression = True

    if not touched:
        report.add(Finding(
            code="NO_RUNTIME_INTERVENTION", severity="info", status=PASS,
            message="Package does not add or change a cross-cutting runtime "
                    "intervention; harness-doctrine §5 not engaged.",
            location="package",
        ))
        return

    if has_layer and has_regression:
        report.add(Finding(
            code="DOCTRINE_NOTE_PRESENT", severity="info", status=UNCHECKED,
            message=("Package touches a runtime intervention and includes a layer "
                     "citation and a regression note. Confirm §5 substance "
                     "(correct layer, inert-on-strong-case)."),
            location=", ".join(sorted(set(where))),
        ))
    else:
        gaps = []
        if not has_layer:
            gaps.append("a lifecycle-layer citation (§1)")
        if not has_regression:
            gaps.append("a regression note (§3)")
        report.add(Finding(
            code="DOCTRINE_GAP", severity="major", status=FAIL,
            message=(f"Package changes a cross-cutting runtime intervention but "
                     f"lacks {', and '.join(gaps)}. harness-doctrine §5 requires "
                     f"both; cite the section by number in the verdict."),
            location=", ".join(sorted(set(where))),
        ))


# =============================================================================
# Orchestration + rendering
# =============================================================================

def load_blocked_phrases(extra_path: Optional[Path]) -> List[str]:
    phrases = list(DEFAULT_BLOCKED_PHRASES)
    if extra_path and extra_path.exists():
        for line in _read(extra_path).splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                phrases.append(s)
    return phrases


def run_gate(root: Path, manifest: Manifest,
             prior_path: Optional[Path] = None,
             blocked_phrases_path: Optional[Path] = None) -> Report:
    report = Report(boundary=manifest.boundary, package_path=str(root))
    if not root.exists() or not root.is_dir():
        report.add(Finding(
            code="PACKAGE_NOT_FOUND", severity="critical", status=FAIL,
            message=f"Package path does not exist or is not a directory: {root}.",
            location=str(root),
        ))
        return report
    if not iter_package_files(root):
        report.add(Finding(
            code="PACKAGE_EMPTY", severity="critical", status=FAIL,
            message=f"No readable text artifacts under {root}.",
            location=str(root),
        ))
        return report

    check_required_artifacts(root, manifest, report)
    check_lineage(root, report)
    check_skip_records(root, report)
    scan_blocked_phrases(root, report, load_blocked_phrases(blocked_phrases_path))
    check_idempotency(root, report, prior_path)
    check_harness_doctrine(root, report)
    return report


def render_markdown(report: Report) -> str:
    lines = [
        f"# Gate check — {report.boundary}",
        "",
        f"- Package: `{report.package_path}`",
        f"- Deterministic gate status: **{report.gate_status()}**",
        f"- Checks run: {', '.join(report.checks_run)}",
        f"- Failures: {len(report.failures)} | Needs judgment: {len(report.unchecked)}",
        "",
        "> This is a deterministic structural report, **not a verdict**. The "
        "gatekeeper skill combines it with judgment to issue "
        "APPROVED / REVISE / ESCALATE.",
        "",
    ]
    order = {FAIL: 0, UNCHECKED: 1, PASS: 2}
    for f in sorted(report.findings, key=lambda x: (order.get(x.status, 9), x.severity)):
        loc = f" — `{f.location}`" if f.location else ""
        lines.append(f"- **[{f.status}/{f.severity}] {f.code}**{loc}: {f.message}")
    lines.append("")
    return "\n".join(lines)


def build_arg_parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("package", help="Path to the package directory to validate.")
    p.add_argument("--prior", default=None,
                   help="Path to a prior gatekeeper verdict / handoff file for "
                        "idempotency comparison.")
    p.add_argument("--blocked-phrases", default=None,
                   help="Path to an extra blocked-phrases list (one per line; "
                        "lines beginning 're:' are regexes).")
    p.add_argument("--json", action="store_true",
                   help="Emit the report as JSON instead of markdown.")
    return p


def main_with_manifest(manifest: Manifest, argv: Optional[List[str]] = None) -> int:
    """Entry point each gate's check.py calls with its boundary manifest."""
    parser = build_arg_parser(f"Deterministic gate check for {manifest.boundary}.")
    args = parser.parse_args(argv)
    try:
        report = run_gate(
            Path(args.package),
            manifest,
            prior_path=Path(args.prior) if args.prior else None,
            blocked_phrases_path=Path(args.blocked_phrases) if args.blocked_phrases else None,
        )
    except Exception as exc:  # fail loud — never a silent pass
        err = {
            "boundary": manifest.boundary,
            "gate_status": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
            "note": "Gate could not be evaluated deterministically. Do NOT "
                    "approve on structure; resolve the error or validate by hand.",
        }
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"# Gate check — {manifest.boundary}\n\n"
                  f"**ERROR**: {err['error']}\n\n{err['note']}")
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(render_markdown(report))
    return report.exit_code()
