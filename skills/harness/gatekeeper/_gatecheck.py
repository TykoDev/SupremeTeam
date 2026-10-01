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

Stdlib only — no ``pip install``. The supported floor is Python 3.13, declared
once in ``skills/runtime-manifest.yaml`` (``runtime.python.minimum``) and checked by
``scripts/check_runtime.py``; this module states no floor of its own.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

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
# ``re:`` are regular expressions compiled exactly as written (the code-rot
# markers are word-bounded and case-sensitive, so the ordinary word "hack" is not
# a hit); all others are literal, case-insensitive substrings. This is the one
# list: the boundary validator (check.py) scans manifest artifacts against it
# too. A gate extends it with ``--blocked-phrases <file>``.
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


def compile_blocked_phrases(phrases: Sequence[str]) -> tuple[List[str], List[re.Pattern]]:
    """Split a phrase list into lowercase literals and compiled ``re:`` patterns.

    A pattern that does not compile raises ``ValueError``: a rule the gate cannot
    apply must stop the gate, because skipping it would still print a clean scan.
    """
    literals: List[str] = []
    regexes: List[re.Pattern] = []
    for entry in phrases:
        if entry.startswith("re:"):
            try:
                regexes.append(re.compile(entry[3:]))
            except re.error as exc:
                raise ValueError(f"blocked-phrase entry {entry!r} is not a valid regular expression: {exc}") from exc
        else:
            literals.append(entry.lower())
    return literals, regexes


# Tokens that signal a package adds or changes a cross-cutting runtime
# intervention (harness-doctrine §5). Their presence alone is not a defect — it
# only triggers the §5 structural check for a layer citation + regression note.
_INTERVENTION_MARKERS = re.compile(
    r"\b(?:PreToolUse|PostToolUse|pre_tool_use|post_tool_use|"
    r"runtime\s+hook|tool[-\s]?use\s+hook|action\s+realization|"
    r"trajectory\s+regulation|guard\s+boundary|freeze\s+boundary)\b",
    re.IGNORECASE,
)
# A word boundary needs a word character on one side and the section sign is not
# one, so only the alternatives that begin with a word are anchored on the left.
_LAYER_CITATION = re.compile(
    r"(?:\bLayer\s*[1-4]|§\s*[1-5]|\bharness-doctrine)\b", re.IGNORECASE
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
    """A required (or conditional) package artifact: found by file name, proved
    by what the file contains, and held to one file per slot.

    patterns:       shell globs matched against the file's own name, never its
                    directory components, so ``latest/x.md`` does not answer to
                    ``*test*.md``.
    content_marker: a regex, case-insensitive, that must match on whole words:
                    letters and digits may not continue it, so ``pass`` is not
                    found in ``password`` (``pass_rate`` and ``pass-rate`` count).
    fields:         packet field names (``Outcome``, ``Findings``) that must each
                    open a line as ``Name:``. This is the structural proof; a
                    common word in prose is not.

    requirement:
      - "required":    absence is a MAJOR FAIL.
      - "conditional": absence is an INFO UNCHECKED — the engine cannot know
        whether this artifact is in scope (e.g. API contracts only when
        endpoints exist), so the model must confirm. Presence is a PASS.

    evidence_key and stages name the contracts that decide whether the slot is
    optional, so a wrapper states where the condition lives instead of copying
    it: ``evidence_key`` is a gates.yaml key a submitter may waive at this
    boundary, ``stages`` are the pipelines.yaml stages that produce the file. A
    required slot whose key is waivable, or whose every stage carries a ``when``,
    is held as conditional (see ``Contracts``).
    """

    key: str
    label: str
    patterns: Sequence[str]
    content_marker: Optional[str] = None
    requirement: str = "required"
    fields: Sequence[str] = ()
    evidence_key: Optional[str] = None
    stages: Sequence[str] = ()


@dataclass
class Manifest:
    """A boundary's deterministic acceptance shape, declared by each gate.

    ``pipeline`` names the pipelines.yaml pipeline that closes at this boundary;
    without it a slot's ``evidence_key`` and ``stages`` cannot be looked up."""

    boundary: str
    sub_orchestrator: str
    artifacts: Sequence[ArtifactSpec] = field(default_factory=tuple)
    pipeline: Optional[str] = None


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
# Project root and package containment
# =============================================================================

# A project root is recognised by one of these markers. harness/hooks/_state.py
# keeps the same three; the engine does not import the hooks (they fail open, a
# gate fails loud), and test_gate_wrappers.py fails when the two tuples drift.
ROOT_MARKERS = ("skillset-saves", ".harness-state", ".git")


def find_project_root(start: Path) -> Optional[Path]:
    """Nearest ancestor of ``start`` (itself included) holding a project marker."""
    for candidate in (start, *start.parents):
        try:
            if any((candidate / marker).exists() for marker in ROOT_MARKERS):
                return candidate
        except OSError:
            continue
    return None


class PackageRefused(ValueError):
    """The package directory cannot be read: exit 2, never a pass."""


def resolve_package_dir(raw: str, cwd: Optional[Path] = None) -> Path:
    """Confine the untrusted <package-dir> argument to an existing directory
    inside the project before the engine reads it.

    Saves are written to ``<project>/skillset-saves/runs/<run>/<phase>``. That is
    inside the project but not below the catalog: a vendored copy sits within the
    project and an installed one (``~/.agents/skills``) beside it. So the project
    is found from where the gate is run, never from this file: the nearest marked
    ancestor of the working directory, or of the package itself when the working
    directory is in no project. ``resolve`` folds ``..`` and follows symlinks
    first, so neither leads out of the project. Enforcing this in code, not only
    in SKILL.md prose, stops a manipulated context from pointing the gate at a
    non-existent path or at files outside the project.

    ``cwd`` is the directory the project is searched from; it defaults to the
    process's own and exists so a test can name another."""
    try:
        resolved = Path(raw).resolve()
        is_dir = resolved.is_dir()
    except (OSError, ValueError) as exc:  # an embedded NUL, a name too long
        raise PackageRefused(f"<package-dir> cannot be read: {raw[:200]!r} ({exc})") from exc
    if not is_dir:
        raise PackageRefused(
            f"<package-dir> does not exist or is not a directory: {raw!r}")
    try:
        here = (cwd or Path.cwd()).resolve()
    except OSError as exc:
        raise PackageRefused(f"cannot read the working directory: {exc}") from exc
    root = find_project_root(here) or find_project_root(resolved)
    if root is None:
        raise PackageRefused(
            f"cannot locate a project root (a directory holding skillset-saves/, "
            f".harness-state/ or .git) above the working directory or {resolved}, so "
            f"<package-dir> containment cannot be verified; refusing to read it.")
    if root not in (resolved, *resolved.parents):
        raise PackageRefused(
            f"<package-dir> {resolved} is outside the project {root}; run the gate "
            f"from the project that holds the package. Refusing to read it.")
    return resolved


# =============================================================================
# Package discovery
# =============================================================================

def _leaves(path: Path, real_root: Path) -> bool:
    """True when ``path`` resolves outside ``real_root``, or cannot be resolved."""
    try:
        path.resolve().relative_to(real_root)
    except (OSError, ValueError):
        return True
    return False


def find_escaping_links(root: Path) -> List[Path]:
    """Symlinks and junctions inside the package whose target leaves it."""
    real_root = root.resolve()
    return [p for p in sorted(root.rglob("*"))
            if (p.is_symlink() or p.is_junction()) and _leaves(p, real_root)]


def iter_all_files(root: Path) -> List[Path]:
    """Every regular file under the package (JSON evidence records and HTML
    prototypes included), sorted for stable output. Used for artifact
    presence; lineage and phrase scans use the text-only enumeration. A member
    that resolves outside the package is left out, so the gate reads what the
    package contains and nothing a link points at; ``find_escaping_links``
    reports the links."""
    real_root = root.resolve()
    return [p for p in sorted(root.rglob("*"))
            if p.is_file() and not _leaves(p, real_root)]


def iter_package_files(root: Path) -> List[Path]:
    """All readable text files under the package, sorted for stable output."""
    return [p for p in iter_all_files(root)
            if p.suffix.lower() in _TEXT_SUFFIXES]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


# =============================================================================
# Contracts a manifest derives its optional slots from
# =============================================================================

class ContractsUnreadable(Exception):
    """gates.yaml or pipelines.yaml could not be read from the catalog."""


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


class Contracts:
    """What gates.yaml and pipelines.yaml say about which artifacts are optional.

    Read from the catalog this engine ships in (two levels above this file), so a
    wrapper cites a key or a stage instead of restating its condition, and a
    change to either file reaches every gate that cites it."""

    def __init__(self, gates: dict, pipelines: dict) -> None:
        self.gates = gates
        self.pipelines = pipelines

    @classmethod
    def load(cls, catalog: Optional[Path] = None) -> "Contracts":
        root = catalog or Path(__file__).resolve().parents[2]
        scripts = str(root / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        try:
            from data_formats import load_data  # stdlib only, ships in scripts/
            gates = load_data(root / "gates.yaml")
            pipelines = load_data(root / "pipelines.yaml")
        except (ImportError, ValueError) as exc:  # DataFormatError is a ValueError
            raise ContractsUnreadable(f"{type(exc).__name__}: {exc}") from exc
        if not isinstance(gates, dict) or not isinstance(pipelines, dict):
            raise ContractsUnreadable("gates.yaml and pipelines.yaml must be mappings")
        return cls(gates, pipelines)

    def _pipeline(self, name: str) -> dict:
        return _mapping(_mapping(self.pipelines.get("pipelines")).get(name))

    def boundary_of(self, pipeline: str) -> Optional[str]:
        boundary = self._pipeline(pipeline).get("boundary")
        return boundary if isinstance(boundary, str) else None

    def waiver(self, boundary: str, key: str) -> Optional[str]:
        """The reason a submitter may waive ``key`` at ``boundary``, if one is sanctioned."""
        spec = _mapping(_mapping(self.gates.get("boundaries")).get(boundary))
        if key in (spec.get("no_fallback") or ()):
            return None
        for table in (spec.get("fallback_values"), self.gates.get("fallback_values")):
            reasons = _mapping(table).get(key)
            if isinstance(reasons, list) and reasons and isinstance(reasons[0], str):
                return reasons[0]
        return None

    def stage_condition(self, pipeline: str, stage: str) -> Optional[str]:
        """The ``when`` that gates ``stage``, or None when the stage always runs."""
        stages = self._pipeline(pipeline).get("stages")
        for entry in stages if isinstance(stages, list) else ():
            if isinstance(entry, dict) and entry.get("step") == stage:
                when = entry.get("when")
                return when if isinstance(when, str) and when.strip() else None
        return None


def _contracts_for(manifest: Manifest, report: Report) -> Optional[Contracts]:
    """The contracts, read only when a slot cites one. When they cannot be read
    every slot keeps its declared requirement: stricter, never looser."""
    if not manifest.pipeline or not any(
            spec.evidence_key or spec.stages for spec in manifest.artifacts):
        return None
    try:
        return Contracts.load()
    except ContractsUnreadable as exc:
        report.add(Finding(
            code="CONTRACTS_UNREADABLE", severity="minor", status=UNCHECKED,
            message=(f"Could not read gates.yaml / pipelines.yaml ({exc}); artifacts "
                     f"those files make optional are held to their declared requirement."),
            location="package",
        ))
        return None


def _optional_because(spec: ArtifactSpec, manifest: Manifest,
                      contracts: Optional[Contracts]) -> str:
    """Why the contracts make this slot optional, or "" when they do not."""
    if contracts is None or not manifest.pipeline:
        return ""
    reasons: List[str] = []
    boundary = contracts.boundary_of(manifest.pipeline)
    if boundary and spec.evidence_key:
        waiver = contracts.waiver(boundary, spec.evidence_key)
        if waiver:
            reasons.append(f'gates.yaml lets a submitter waive {spec.evidence_key} '
                           f'at {boundary} ("{waiver}")')
    if spec.stages:
        conditions = [contracts.stage_condition(manifest.pipeline, stage)
                      for stage in spec.stages]
        if all(conditions):
            reasons.append("pipelines.yaml runs " + " and ".join(
                f'{stage} only when "{when}"'
                for stage, when in zip(spec.stages, conditions, strict=True)))
    return "; ".join(reasons)


# =============================================================================
# Individual deterministic checks
# =============================================================================

def _named(path: Path, patterns: Sequence[str]) -> bool:
    """Does the file's own name match a pattern? Directory names never count."""
    name = path.name.lower()
    return any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in patterns)


def _field_line(name: str) -> re.Pattern:
    """A packet field: ``name`` opening a line (list, quote and emphasis marks
    allowed) and followed by a colon, so frontmatter keys count too."""
    return re.compile(r"^[ \t>*_|`\-]*" + re.escape(name) + r"[ \t*_`]*:",
                      re.IGNORECASE | re.MULTILINE)


def _whole_word(marker: str) -> re.Pattern:
    return re.compile(r"(?<![^\W_])(?:" + marker + r")(?![^\W_])", re.IGNORECASE)


def _structure_gaps(texts: Dict[Path, str], path: Path, spec: ArtifactSpec) -> List[str]:
    """What the file lacks of the structure the slot asks for; empty when it
    qualifies. ``texts`` caches reads across slots."""
    if not (spec.content_marker or spec.fields):
        return []
    if path not in texts:
        texts[path] = _read(path)
    text = texts[path]
    gaps = [f"the field {name}:" for name in spec.fields
            if not _field_line(name).search(text)]
    if spec.content_marker and not _whole_word(spec.content_marker).search(text):
        gaps.append(f"a whole-word match for /{spec.content_marker}/")
    return gaps


def _assign(candidates: List[List[Path]], real: Dict[Path, Path]) -> List[Optional[Path]]:
    """Give each slot a file of its own, re-routing earlier slots when a later
    one needs their file (bipartite matching over resolved paths).

    A file names one artifact, not several: a single stand-in whose name and text
    satisfy five slots would otherwise turn five missing lenses green, and a
    symlink alias of a file is the same file. Slots are placed in list order, so
    callers list the required slots first."""
    holder: Dict[Path, int] = {}
    assigned: Dict[int, Path] = {}

    def place(slot: int, tried: Set[Path]) -> bool:
        for path in candidates[slot]:
            key = real[path]
            if key in tried:
                continue
            tried.add(key)
            if key not in holder or place(holder[key], tried):
                holder[key] = slot
                assigned[slot] = path
                return True
        return False

    for slot in range(len(candidates)):
        place(slot, set())
    return [assigned.get(slot) for slot in range(len(candidates))]


def _near_misses(root: Path, lacking: Dict[Path, List[str]],
                 taken: List[Tuple[Path, str]]) -> str:
    """Name-matching files that did not fill a slot, and why, so a REVISE can say
    what to fix and not only what is absent."""
    notes = [f"{_rel(path, root)} lacks {' and '.join(gaps)}"
             for path, gaps in lacking.items()]
    notes += [f"{_rel(path, root)} is already the {label}" for path, label in taken]
    if not notes:
        return ""
    more = f" (+{len(notes) - 3} more)" if len(notes) > 3 else ""
    return "; near misses: " + "; ".join(notes[:3]) + more


def check_package_links(root: Path, report: Report) -> None:
    """A link out of the package lets a file elsewhere stand in for a member, so
    it is a defect in itself and is never read."""
    report.checks_run.append("package_links")
    for link in find_escaping_links(root):
        rel = _rel(link, root)
        report.add(Finding(
            code="LINK_ESCAPES_PACKAGE", severity="major", status=FAIL,
            message=(f"{rel} is a link to {link.readlink()}, which leaves the "
                     f"package. It is not read; ship the file itself."),
            location=rel,
        ))


def check_required_artifacts(root: Path, manifest: Manifest,
                             report: Report) -> None:
    report.checks_run.append("required_artifacts")
    specs = list(manifest.artifacts)
    files = iter_all_files(root)
    real = {f: f.resolve() for f in files}
    contracts = _contracts_for(manifest, report)
    why = [_optional_because(spec, manifest, contracts) for spec in specs]
    optional = [spec.requirement == "conditional" or bool(reason)
                for spec, reason in zip(specs, why, strict=True)]

    texts: Dict[Path, str] = {}
    candidates: List[List[Path]] = []
    lacking: List[Dict[Path, List[str]]] = []
    for spec in specs:
        named = [f for f in files if _named(f, spec.patterns)]
        gaps = {f: _structure_gaps(texts, f, spec) for f in named}
        candidates.append([f for f in named if not gaps[f]])
        lacking.append({f: g for f, g in gaps.items() if g})

    order = sorted(range(len(specs)), key=lambda i: optional[i])
    placed = _assign([candidates[i] for i in order], real)
    chosen = {i: placed[n] for n, i in enumerate(order)}
    holder = {real[p]: i for i, p in chosen.items() if p is not None}

    for i, spec in enumerate(specs):
        if chosen[i] is not None:
            report.add(Finding(
                code="ARTIFACT_PRESENT", severity="info", status=PASS,
                message=f"{spec.label} present.", location=_rel(chosen[i], root),
            ))
            continue
        near = _near_misses(root, lacking[i], [
            (f, specs[holder[real[f]]].label) for f in candidates[i]])
        if optional[i]:
            when = (f"{why[i]}. Confirm that condition was false for this "
                    f"submission, or that a valid _skip-record.md or the "
                    f"sanctioned waiver covers it" if why[i] else
                    "This artifact is required only when in scope — confirm "
                    "whether this submission needs it")
            report.add(Finding(
                code="ARTIFACT_CONDITIONAL", severity="info", status=UNCHECKED,
                message=f"{spec.label} not found. {when}{near}.",
                location="package",
            ))
        else:
            report.add(Finding(
                code="ARTIFACT_MISSING", severity="major", status=FAIL,
                message=(f"Required artifact missing: {spec.label} "
                         f"(expected one of: {', '.join(spec.patterns)}{near})."),
                location="package",
            ))


def _revision_token(value: object) -> Optional[str]:
    """A revision as a comparable token. Both ``3`` (handoff templates) and ``r3``
    (gate manifests) are in use, so a bare number and a label count alike and
    neither is coerced into the other."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _submission_token(value: object) -> Optional[str]:
    if isinstance(value, str) and value.strip() and value.strip().upper() != "PENDING":
        return value.strip()
    return None


def check_lineage(root: Path, report: Report) -> None:
    """Detect packages that mix deliverables from different revisions, and
    surface the submission id / revision the gate keys idempotency on.

    Two distinct ``revision:`` values across the package's frontmatter is the
    mechanical signature of a contaminated, mixed-revision submission.
    """
    report.checks_run.append("lineage")
    revisions: Dict[str, List[str]] = {}
    submission_ids: Dict[str, List[str]] = {}
    for path in iter_package_files(root):
        fm = parse_frontmatter(_read(path))
        rel = _rel(path, root)
        rev = _revision_token(fm.get("revision"))
        if rev is not None:
            revisions.setdefault(rev, []).append(rel)
        sid = _submission_token(fm.get("submission_id"))
        if sid is not None:
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
    literals, regexes = compile_blocked_phrases(phrases)

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


def _read_record(path: Path) -> dict:
    """A record as a mapping: Markdown frontmatter, or a JSON object such as the
    verdict ``harness/gatekeeper/check.py --verdict-out`` writes."""
    text = _read(path)
    record = parse_frontmatter(text)
    if record:
        return record
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _declared_identity(root: Path) -> Tuple[Set[str], Set[str]]:
    """The submission ids and revisions the package declares: in the frontmatter
    of its Markdown and in its own manifest.json, where a package that ships
    evidence records its identity."""
    sids: Set[str] = set()
    revs: Set[str] = set()
    for path in iter_all_files(root):
        if path.suffix.lower() not in _TEXT_SUFFIXES and path != root / "manifest.json":
            continue
        record = _read_record(path)
        sid = _submission_token(record.get("submission_id"))
        rev = _revision_token(record.get("revision"))
        if sid is not None:
            sids.add(sid)
        if rev is not None:
            revs.add(rev)
    return sids, revs


def check_idempotency(root: Path, report: Report,
                      prior_path: Optional[Path]) -> None:
    """Compare the current submission against a prior verdict record so the same
    package is not re-gated under conflicting rationale, and so a reused
    submission id with changed contents is flagged as silent drift. Two packages
    are called different only when both declare an identity; a side that declares
    none leaves the comparison undetermined, never a pass.
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

    prior = _read_record(prior_path)
    prior_sid = _submission_token(prior.get("submission_id"))
    prior_rev = _revision_token(prior.get("revision"))
    prior_verdict = prior.get("verdict")
    if prior_verdict is None and isinstance(prior.get("pass"), bool):
        prior_verdict = "mechanical pass" if prior["pass"] else "mechanical fail"

    cur_sids, cur_revs = _declared_identity(root)
    known_sid = prior_sid is not None and bool(cur_sids)
    known_rev = prior_rev is not None and bool(cur_revs)
    same_sid = known_sid and prior_sid in cur_sids
    same_rev = known_rev and prior_rev in cur_revs

    if same_sid and same_rev:
        report.add(Finding(
            code="VERDICT_REUSABLE", severity="info", status=PASS,
            message=(f"Submission id and revision match the prior verdict "
                     f"(verdict={prior_verdict}). Prior verdict is reusable; do "
                     f"not re-gate under new rationale."),
            location=str(prior_path),
        ))
    elif same_sid and known_rev:
        report.add(Finding(
            code="SILENT_DRIFT", severity="major", status=FAIL,
            message=(f"Submission id '{prior_sid}' is reused but the revision "
                     f"changed (prior={prior_rev}, current={sorted(cur_revs)}). "
                     f"Prior verdict is non-transferable; require a fresh delta."),
            location=str(prior_path),
        ))
    elif known_sid and not same_sid:
        report.add(Finding(
            code="NEW_SUBMISSION", severity="info", status=PASS,
            message=("Submission id/revision differ from the prior verdict; "
                     "evaluating as a fresh submission."),
            location=str(prior_path),
        ))
    else:
        report.add(Finding(
            code="IDEMPOTENCY_UNDETERMINED", severity="minor", status=UNCHECKED,
            message=(f"Cannot confirm idempotency: the prior verdict and the package "
                     f"do not both declare a readable submission_id and revision "
                     f"(Markdown frontmatter, a JSON record, or the package's "
                     f"manifest.json). Prior: submission_id={prior_sid!r} "
                     f"revision={prior_rev!r}. Package: submission_ids="
                     f"{sorted(cur_sids)} revisions={sorted(cur_revs)}. Verify "
                     f"manually."),
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
    if extra_path is not None:
        # A mistyped path used to be ignored, which left the extra rules off and
        # the report clean.
        if not extra_path.is_file():
            raise ValueError(f"blocked-phrases file not found: {extra_path}")
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
    check_package_links(root, report)
    if not iter_all_files(root):
        report.add(Finding(
            code="PACKAGE_EMPTY", severity="critical", status=FAIL,
            message=f"No artifacts under {root}.",
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
    p.add_argument("package", help="Path to the package directory to validate; it "
                                   "must sit inside the project (see "
                                   "resolve_package_dir).")
    p.add_argument("--prior", default=None,
                   help="Path to a prior gatekeeper verdict for idempotency "
                        "comparison: Markdown frontmatter or the JSON record "
                        "check.py --verdict-out writes.")
    p.add_argument("--blocked-phrases", default=None,
                   help="Path to an extra blocked-phrases list (one per line; "
                        "lines beginning 're:' are regexes).")
    p.add_argument("--json", action="store_true",
                   help="Emit the report as JSON instead of markdown.")
    return p


def main_with_manifest(manifest: Manifest, argv: Optional[List[str]] = None,
                       extra_checks: Sequence[Callable[[Path, Report], None]] = ()) -> int:
    """Entry point each gate's check.py calls with its boundary manifest.

    ``extra_checks`` are gate-specific checks run, after the shared ones, on a
    package that could be read (check_redesign.py's mock-first layout). Exit 2
    always means the gate could not run: a refused package directory, bad
    arguments, or an internal error; it is never a verdict."""
    parser = build_arg_parser(f"Deterministic gate check for {manifest.boundary}.")
    args = parser.parse_args(argv)
    try:
        package = resolve_package_dir(args.package)
    except PackageRefused as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        return 2
    try:
        report = run_gate(
            package,
            manifest,
            prior_path=Path(args.prior) if args.prior else None,
            blocked_phrases_path=Path(args.blocked_phrases) if args.blocked_phrases else None,
        )
        # An empty or missing package has already failed critically and a
        # layout check would only repeat it.
        if not any(f.code in ("PACKAGE_NOT_FOUND", "PACKAGE_EMPTY") for f in report.findings):
            for check in extra_checks:
                check(package, report)
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
