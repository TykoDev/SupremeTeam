#!/usr/bin/env python3
"""Validate a Supreme Team boundary package for shape, evidence, lineage, and drift.

Inputs (CLI flags):
  --boundary     a boundary name defined in skills/gates.yaml (e.g. design-to-build).
  --package      path to the package manifest (JSON, or the documented YAML subset).
  --prior        optional prior verdict record or manifest; enables the
                 idempotency-drift and prior-reuse checks.
  --gates        optional override path to the gate spec (default: skills/gates.yaml).
  --verdict-out  optional path; the result JSON is also written there as the
                 durable verdict record for later --prior comparisons.
  --intake-log   check one intake grilling log against the decision_log tables
                 on its own (no --boundary or --package); the gate_watch hook runs
                 it when the log is written.
  --judgment     optional path to the gatekeeper's judgment record (its verdict
                 and judgment findings). It is checked for grounding - each
                 finding cites a source of truth that exists and hashed package
                 artifacts, and the verdict follows from the findings - and is
                 embedded in the verdict record; an ungrounded record fails the
                 run and is never written to --verdict-out.

The boundary table is not hardcoded here: skills/gates.yaml is the single
source of truth for required evidence keys, artifact-backed evidence keys,
sanctioned fallback values, typed evidence records, and the finding policy.
A missing or malformed gate spec is an engine error, never a pass.

Evidence root
-------------
Artifact paths are manifest-relative. The *authorised evidence root* is:

  * the run directory when the manifest lives in the canonical save layout
    ``skillset-saves/runs/<run-id>/<phase>/...`` and the manifest's ``run_id``
    agrees with both the directory name and the run's ``_state.md``;
  * otherwise the manifest's own directory (a standalone flat package).

Sibling phase evidence inside the same run (``../intake/report_grilling.md``)
is therefore admissible; another run, a traversal above the root, a drive or
UNC path, or a symlink/junction that leaves the root is rejected.

Manifest schema
---------------
``schema_version`` 1 (default when absent) is the legacy flat-package shape.
``schema_version`` 2 additionally requires ``boundary``, ``owner``, and
``run_id`` (inside a run), forbids bare-string fallbacks in favour of typed
applicability records, and validates typed evidence records declared in the
gate spec. Typed records are mostly independent of each other; the ``selection``
kind is the exception, because what it decides changes what four other keys are
allowed to carry (see ``check_selection_dependencies``).

A manifest inside a run must declare schema 2: an absent or schema-1 version
fails, and the package is checked as schema 2 anyway so the submitter gets
every failure at once. A flat package at schema 1 still passes, and the result
says in ``warnings`` that no typed check ran.

What is verified and what is attested: a typed record is the submitter's own
statement. The gate checks its shape, that each artifact it names exists and
matches its digest, that each ``inputs`` entry still hashes to what the record
says, and that a pass does not sit beside a non-zero exit code. It does not compare
an artifact's content with the record or re-run anything (``.md`` and ``.txt`` artifacts
are read for blocked phrases and local links only), and a probe record that binds no inputs is
listed in ``warnings`` as attested rather than tied to the source it describes.

Output: a JSON report on stdout. On engine error, including any fault inside the
engine itself, a JSON object carrying "engine_error" is written to stderr and
nothing is printed to stdout. The report names every input that was not the
shipped one (``gate_spec_is_shipped``, ``registry_is_shipped``, ``prior_record``);
its digests are unkeyed, so a stored verdict is not authority by itself and the
reader re-runs this script against the shipped spec.

Exit codes: 0 = facts pass, 1 = defects found, 2 = engine error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]
GATE_SPEC_PATH = SKILLS_ROOT / "gates.yaml"
REGISTRY_PATH = SKILLS_ROOT / "tech-stacks" / "registry.yaml"
for _path in (SKILLS_ROOT / "scripts", Path(__file__).resolve().parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from _gatecheck import DEFAULT_BLOCKED_PHRASES, compile_blocked_phrases, is_blank_file  # noqa: E402
from data_formats import DataFormatError, content_sha256, load_data  # noqa: E402
from contract_floor import gate_floor_errors  # noqa: E402

SUPPORTED_MANIFEST_SCHEMAS = {1, 2}
#: The schema a manifest inside skillset-saves/runs/<run>/<phase>/ must declare.
RUN_MANIFEST_SCHEMA = 2
#: The blocked-phrase rule is _gatecheck.py's, so both validators agree on what
#: a hollow claim is and on which markers are case-sensitive.
BLOCKED_LITERALS, BLOCKED_MARKERS = compile_blocked_phrases(DEFAULT_BLOCKED_PHRASES)
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FENCED = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HEX64 = re.compile(r"[0-9a-f]{64}")
# A string counts as an artifact reference when it is shaped like a file path:
# no whitespace, an extension, optional directory segments. An absolute, drive
# or UNC root still counts, because such a path can never be a hashed artifact
# and must be refused rather than read as prose.
PATH_LIKE = re.compile(r"^(?:[A-Za-z]:)?(?:[/\\]{1,2}|(?:\.\.?[/\\])*)(?:[\w.\-]+[/\\])*[\w.\-]+\.[A-Za-z0-9]{1,8}$")
SCANNED_TEXT_SUFFIXES = {".md", ".txt"}
VERDICTS = {"APPROVED", "REVISE", "ESCALATE"}
RESULT_STATUSES = {"pass", "fail", "error", "not-run", "unavailable", "inferred"}
FINDING_SEVERITIES = {"Critical", "Major", "Minor", "Info"}
FINDING_STATUSES = {"open", "in-progress", "resolved", "verified", "deferred", "not-applicable"}
#: Default file fields of a variant_set record when the gate spec names none.
VARIANT_FILES = ("spec", "tokens", "components", "app")
#: Every evidence type check_typed dispatches. A spec that names another kind is
#: an engine error: an unknown kind would switch its key's typed validation off
#: and still print a pass.
EVIDENCE_KINDS = frozenset({
    "scan", "render", "probe", "findings", "verdict", "stack_lock", "revision_ref",
    "preference_diff", "confirmation", "conflict_analysis", "persistence_result", "effective_profile",
    "consumer_handoff", "variant_set", "selection", "security_seed", "human_go",
    "decision_log", "acceptance_table", "interface_set", "change_set", "trace_map"})
#: What a gatekeeper's judgment finding may stand on (gates.yaml judgment_policy).
#: There is deliberately no kind for the gate's own preference: a requirement
#: that is in none of these sources is not the gate's to impose.
JUDGMENT_BASIS_KINDS = frozenset({"decision", "acceptance", "contract", "contradiction"})
#: The id shape each source-of-truth basis kind cites, and the evidence key whose
#: artifacts the cited file must be when the boundary carries that key.
JUDGMENT_REF_SHAPES = {"decision": re.compile(r"D-\d+"), "acceptance": re.compile(r"AC-\d+")}
JUDGMENT_SOURCE_KEYS = {"decision": ("decisions",), "acceptance": ("acceptance", "plan")}
BLOCKING_SEVERITIES = frozenset({"Critical", "Major"})
MANIFEST_ANCHOR = re.compile(r"manifest:evidence\.([A-Za-z0-9_]+)")
#: The intake grilling log (grill-me-doctrine.md Output): four level-2 sections,
#: each holding one Markdown table with at least these columns, and the fewest
#: data rows each may carry. Every row's ID is a D-<n> unique across the log.
DECISION_SECTIONS = (
    ("Resolved decisions", ("ID", "Decision", "Chosen", "Source"), 1),
    ("Deferred decisions", ("ID", "Decision", "Why deferral is safe", "Owner", "Reopen phase"), 0),
    ("Rejected options", ("ID", "Option", "Rationale"), 0),
    ("Non-goals and YAGNI deferrals", ("ID", "Non-goal", "Reopen trigger", "Owner"), 0),
)
DECISION_SOURCES = frozenset({"user", "codebase", "prior-artifact", "delegated-default"})
#: The plan's acceptance table (design/planner references/workflow.md).
ACCEPTANCE_SECTION = ("Acceptance criteria", ("ID", "Slice", "Observable condition", "Check that proves it", "Acceptor"))
DECISION_ID = re.compile(r"D-\d+")
ACCEPTANCE_ID = re.compile(r"AC-\d+")
INTERFACE_ID = re.compile(r"IF-\d+")
CHANGE_STATUSES = frozenset({"added", "modified", "deleted"})
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
TABLE_RULE = re.compile(r"^:?-+:?$")
#: A cell that names nothing.
EMPTY_CELLS = frozenset({"", "-", "--", "—", "n/a", "na", "none", "tbd", "?"})


class Engine(ValueError):
    """Engine/input failure: exit 2, never a pass."""


def digest(path: Path) -> str:
    """Canonical artifact digest: text folded to LF, binary byte-for-byte.

    Every hash the gate compares - ``artifact_hashes``, typed-record ``inputs``,
    ``evidence_digests`` - goes through ``data_formats.content_sha256`` so the
    same value verifies on an LF and a CRLF checkout, and so the writer
    (``save_run.py``, ``check_parity.py``, ``scan_record.py``) and this checker
    can never disagree on line endings.
    """
    return content_sha256(path)


def overlay_digest(path: Path) -> str:
    """Digest of a tech-stack overlay; the same canonical fold as ``digest``.

    Registry digests are computed over LF content, and a checkout that converts
    line endings (core.autocrlf=true) must not make every stack_lock fail.
    """
    return content_sha256(path)


def load_mapping(path: Path, what: str) -> dict:
    try:
        data = load_data(path)
    except DataFormatError as exc:
        raise Engine(f"{what} is not valid JSON/YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise Engine(f"{what} root must be a mapping")
    return data


def load_gate_spec(path: Path) -> dict:
    """Load and shape-check the gate spec. Raises Engine on any defect."""
    spec = load_mapping(path, "gate spec")
    if spec.get("schema_version") != 1:
        raise Engine("gate spec schema_version must be 1")
    if spec.get("kind") != "supremeteam-gate-spec":
        raise Engine("gate spec kind is invalid")
    boundaries = spec.get("boundaries")
    if not isinstance(boundaries, dict) or not boundaries:
        raise Engine("gate spec boundaries must be a non-empty JSON object")
    for name, boundary in boundaries.items():
        if not isinstance(boundary, dict):
            raise Engine(f"gate spec boundary {name!r} must be a JSON object")
        required = boundary.get("required_evidence")
        if not isinstance(required, list) or not required or not all(isinstance(k, str) and k for k in required):
            raise Engine(f"gate spec boundary {name!r} required_evidence must be a non-empty string list")
        artifact_keys = boundary.get("artifact_evidence", [])
        if not isinstance(artifact_keys, list) or not all(isinstance(k, str) and k for k in artifact_keys):
            raise Engine(f"gate spec boundary {name!r} artifact_evidence must be a string list")
        unknown = sorted(set(artifact_keys) - set(required))
        if unknown:
            raise Engine(f"gate spec boundary {name!r} artifact_evidence not in required_evidence: {unknown}")
        if not isinstance(boundary.get("submitter"), str) or not boundary.get("submitter"):
            raise Engine(f"gate spec boundary {name!r} must name a submitter")
        boundary_fallbacks = boundary.get("fallback_values", {})
        if not isinstance(boundary_fallbacks, dict):
            raise Engine(f"gate spec boundary {name!r} fallback_values must be a JSON object")
        for key, values in boundary_fallbacks.items():
            if key not in required or not isinstance(values, list) or not all(
                    isinstance(v, str) and v for v in values):
                raise Engine(f"gate spec boundary {name!r} has invalid fallback_values for {key!r}")
    fallbacks = spec.get("fallback_values", {})
    if not isinstance(fallbacks, dict):
        raise Engine("gate spec fallback_values must be a JSON object")
    for key, values in fallbacks.items():
        if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
            raise Engine(f"gate spec fallback_values for {key!r} must be a non-empty string list")
    types = spec.get("evidence_types", {})
    if not isinstance(types, dict) or not all(isinstance(v, str) for v in types.values()):
        raise Engine("gate spec evidence_types must map evidence keys to type names")
    unknown_kinds = sorted({v for v in types.values() if v not in EVIDENCE_KINDS})
    if unknown_kinds:
        raise Engine(f"gate spec evidence_types names unknown kinds {unknown_kinds} (known: {sorted(EVIDENCE_KINDS)})")
    policy = spec.get("finding_policy", {})
    if not isinstance(policy, dict):
        raise Engine("gate spec finding_policy must be a JSON object")
    if path.resolve() == GATE_SPEC_PATH.resolve():
        floor = gate_floor_errors(spec)
        if floor:
            raise Engine("; ".join(floor))
    return spec


def evidence_strings(value: object) -> list[str]:
    """Flatten an evidence value into the strings that may reference artifacts."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        found: list[str] = []
        for key in ("artifacts", "artifact", "path", "paths", "captures", "report", "verdict"):
            found.extend(evidence_strings(value.get(key)))
        return found
    return []


def is_path_like(text: str) -> bool:
    return bool(PATH_LIKE.match(text.strip()))


def has_blocked_phrase(prose: str) -> bool:
    """True when prose holds a blocked phrase: literals fold case, ``re:`` markers do not."""
    folded = prose.lower()
    return any(literal in folded for literal in BLOCKED_LITERALS) or any(rx.search(prose) for rx in BLOCKED_MARKERS)


def filled(value: object) -> bool:
    """True for a real, non-blank string; null, numbers, lists and mappings are not filled.

    ``str(x.get(f, ""))`` turns an explicit JSON null into the truthy word "None",
    so every field that means "someone named this" is read through here.
    """
    return isinstance(value, str) and bool(value.strip())


def utc_today() -> date:
    """Today in UTC, read once per check; a seam so the freshness tests fix the date instead of racing midnight."""
    return datetime.now(timezone.utc).date()


def parse_date(value: object) -> date | None:
    """A YYYY-MM-DD string (or the date PyYAML makes of an unquoted one), else None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value) if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except ValueError:
        return None


def timestamp_valid(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except ValueError:
        return False


def is_sha256(value: object) -> bool:
    """True for a lowercase-foldable 64-digit hex string with nothing before or after it."""
    return isinstance(value, str) and HEX64.fullmatch(value.lower()) is not None


def fingerprint(data: dict) -> str:
    stable = {k: v for k, v in data.items() if k not in {"gate_verdict", "checked_at", "package_fingerprint"}}
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def strip_code(text: str) -> str:
    """Remove fenced code, inline code, and quoted lines before phrase scanning.

    Quoted or code-formatted text is diagnostic evidence about something that
    was inspected; only the report's own prose is judged for unfinished-work
    markers.
    """
    text = FENCED.sub(" ", text)
    text = INLINE_CODE.sub(" ", text)
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _cells(line: str) -> list[str]:
    """The cells of one Markdown table row; an escaped pipe stays inside its cell."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", body)]


def md_section(text: str, title: str) -> list[str] | None:
    """The lines under the heading named ``title`` (any level), up to the next heading of the same or a higher level."""
    lines = strip_fences(text).splitlines()
    wanted = _norm(title)
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if match and _norm(match.group(2)) == wanted:
            level = len(match.group(1))
            body = []
            for following in lines[index + 1:]:
                nxt = HEADING.match(following)
                if nxt and len(nxt.group(1)) <= level:
                    break
                body.append(following)
            return body
    return None


def md_table(lines: list[str]) -> tuple[list[str], list[list[str]]] | None:
    """The first Markdown table in ``lines``: its normalised header and its data rows, or None."""
    for index, line in enumerate(lines):
        if not line.strip().startswith("|") or index + 1 >= len(lines):
            continue
        rule = _cells(lines[index + 1])
        if not rule or not all(TABLE_RULE.match(cell.replace(" ", "")) for cell in rule):
            continue
        header = [_norm(cell) for cell in _cells(line)]
        rows = []
        for row in lines[index + 2:]:
            if not row.strip().startswith("|"):
                break
            rows.append(_cells(row))
        return header, rows
    return None


def strip_fences(text: str) -> str:
    """Text with fenced code blocks blanked, so a template quoted in a fence is not read as the table itself."""
    return FENCED.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def table_records(text: str, title: str, columns: tuple[str, ...], label: str) -> tuple[list[dict], list[str]]:
    """Rows of the table under ``title`` as {column: cell} for the required ``columns``, and every defect found."""
    section = md_section(text, title)
    if section is None:
        return [], [f"{label} lacks the section '{title}'"]
    table = md_table(section)
    if table is None:
        return [], [f"{label} section '{title}' holds no table"]
    header, rows = table
    missing = [column for column in columns if _norm(column) not in header]
    if missing:
        return [], [f"{label} section '{title}' table lacks the columns {missing}"]
    positions = {column: header.index(_norm(column)) for column in columns}
    records, defects = [], []
    for number, row in enumerate(rows, start=1):
        record = {column: (row[pos] if pos < len(row) else "") for column, pos in positions.items()}
        blank = [column for column, cell in record.items() if _norm(cell) in EMPTY_CELLS]
        if blank:
            defects.append(f"{label} '{title}' row {number} leaves {blank} empty")
        records.append(record)
    return records, defects


def decision_log_defects(text: str, label: str) -> list[str]:
    """Every way ``text`` falls short of the intake grilling log's fixed tables (gates.yaml decision_log)."""
    failures: list[str] = []
    seen: dict[str, str] = {}
    for title, columns, least in DECISION_SECTIONS:
        rows, defects = table_records(text, title, columns, label)
        failures.extend(defects)
        if not defects and len(rows) < least:
            failures.append(f"{label} '{title}' needs at least {least} row")
        for row in rows:
            ident = row["ID"].strip()
            if not DECISION_ID.fullmatch(ident):
                failures.append(f"{label} '{title}' id {ident!r} is not D-<n>")
            elif ident in seen:
                failures.append(f"{label} id {ident} repeats (first in '{seen[ident]}')")
            else:
                seen[ident] = title
            source = _norm(row.get("Source", ""))
            if "Source" in row and source not in DECISION_SOURCES and source not in EMPTY_CELLS:
                failures.append(f"{label} {ident} source {row['Source']!r} is not one of {sorted(DECISION_SOURCES)}")
    return failures


def intake_log_main(path: Path) -> int:
    """--intake-log: check one grilling log on its own, before any design package names it."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(json.dumps({"intake_log": str(path), "engine_error": str(exc)}, indent=2), file=sys.stderr)
        return 2
    failures = decision_log_defects(text, path.name)
    print(json.dumps({"intake_log": str(path), "pass": not failures, "failures": failures}, indent=2))
    return 0 if not failures else 1


class Package:
    def __init__(self, manifest_path: Path, data: dict, boundary_name: str, spec: dict) -> None:
        self.manifest_path = manifest_path
        self.base = manifest_path.parent
        self.data = data
        self.boundary_name = boundary_name
        self.spec = spec
        self.boundary = spec["boundaries"][boundary_name]
        self.failures: list[str] = []
        #: Facts about what this pass did not verify; they never fail a package.
        self.warnings: list[str] = []
        self.schema = self._schema_version()
        if self._run_layout_dir() is not None and self.schema < RUN_MANIFEST_SCHEMA:
            # Read as the schema it must be, so the typed checks still run and the
            # submitter gets every failure in one pass instead of a silent downgrade.
            declared = data.get("schema_version", "absent")
            self.failures.append(
                f"manifest inside a run must declare schema_version {RUN_MANIFEST_SCHEMA} (declared: {declared}); "
                f"checked as schema {RUN_MANIFEST_SCHEMA}")
            self.schema = RUN_MANIFEST_SCHEMA
        elif self.schema < 2:
            self.warnings.append(
                "schema 1 manifest: typed records and the finding policy were not checked; boundary and owner were "
                "not required (a declared one was still compared); bare sanctioned fallback strings were accepted in "
                "place of applicability records; paths in records under keys that are not artifact-backed were not "
                "required to be hashed; a non-string run_id was not refused; declare schema_version 2")
        self.root, self.root_kind, self.run_dir, self.project_root = self._evidence_root()
        self.artifact_hashes: dict[str, str] = {}
        self.hashed_ok: set[str] = set()
        #: Hashed artifacts that are zero bytes or whitespace only.
        self.blank_artifacts: set[str] = set()
        #: Upstream packages bound by a revision_ref record: key -> (manifest data, manifest directory).
        self.upstream: dict[str, tuple[dict, Path]] = {}
        #: Per upstream manifest directory, the artifacts it hashed that still verify.
        self.upstream_hashed: dict[str, set[str]] = {}

    # ------------------------------------------------------------- identity
    def _schema_version(self) -> int:
        raw = self.data.get("schema_version", 1)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw not in SUPPORTED_MANIFEST_SCHEMAS:
            raise Engine(f"unsupported manifest schema_version: {raw!r} (supported: {sorted(SUPPORTED_MANIFEST_SCHEMAS)})")
        return raw

    def _run_layout_dir(self) -> Path | None:
        """The run directory when the manifest sits anywhere below skillset-saves/runs/<run-id>/, else None.

        Every ancestor is searched. A bounded walk let a manifest three directories below a phase directory read as a
        detached package, where schema 1 is still accepted and the run's rules (schema 2, ``run_id``, the run as the
        evidence root) do not apply; such a package with an open Critical finding passed ``review-to-delivery``."""
        node = self.base
        while node.parent != node:
            parent = node.parent
            if parent.name == "runs" and parent.parent.name == "skillset-saves":
                return node
            node = parent
        return None

    def _evidence_root(self) -> tuple[Path, str, Path | None, Path]:
        """Resolve the authorised evidence root (see module docstring)."""
        run_dir = self._run_layout_dir()
        declared = self.data.get("run_id")
        if run_dir is None:
            if self.schema >= 2 and declared is not None and not isinstance(declared, str):
                self.failures.append("run_id must be a string")
            return self.base, "package", None, self.base
        project_root = run_dir.parent.parent.parent
        if declared is None:
            if self.schema >= 2:
                self.failures.append("manifest inside a run must declare run_id")
            return self.base, "package", None, project_root
        if declared != run_dir.name:
            self.failures.append(f"run_id does not match run directory: {declared!r} != {run_dir.name!r}")
            return self.base, "package", None, project_root
        state_path = run_dir / "_state.md"
        if not state_path.is_file():
            self.failures.append("run has no _state.md; evidence root limited to the package")
            return self.base, "package", None, project_root
        try:
            state = load_data(state_path)
        except DataFormatError:
            state = None
        if not isinstance(state, dict) or str(state.get("run_id", "")) != declared:
            self.failures.append("run _state.md does not name this run; evidence root limited to the package")
            return self.base, "package", None, project_root
        return run_dir, "run", run_dir, project_root

    # ---------------------------------------------------------------- paths
    def contain(self, relative: str, label: str) -> Path | None:
        """Resolve a manifest-relative path inside the evidence root or record why not."""
        raw = str(relative)
        if not raw or raw != raw.strip() or "\x00" in raw:
            self.failures.append(f"{label} malformed path: {relative!r}")
            return None
        if raw.startswith(("\\\\", "//")):
            self.failures.append(f"{label} escapes evidence root (UNC path): {relative}")
            return None
        candidate_rel = Path(raw)
        # Drive-letter forms are absolute on every host: a manifest is portable
        # evidence, so "C:/x" must be rejected on POSIX too, where pathlib would
        # otherwise treat it as a relative directory named "C:".
        if candidate_rel.is_absolute() or candidate_rel.drive or raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", raw):
            self.failures.append(f"{label} escapes evidence root (absolute path): {relative}")
            return None
        candidate = Path(os.path.normpath(self.base / candidate_rel))
        root = Path(os.path.normpath(self.root))
        try:
            candidate.relative_to(root)
        except ValueError:
            if self.run_dir is not None:
                runs_dir = Path(os.path.normpath(self.run_dir.parent))
                try:
                    candidate.relative_to(runs_dir)
                    self.failures.append(f"{label} references another run: {relative}")
                    return None
                except ValueError:
                    pass
            noun = "run evidence root" if self.root_kind == "run" else "package"
            self.failures.append(f"{label} escapes {noun}: {relative}")
            return None
        if candidate.exists():
            real = Path(os.path.realpath(candidate))
            real_root = Path(os.path.realpath(root))
            try:
                real.relative_to(real_root)
            except ValueError:
                self.failures.append(f"{label} escapes evidence root via link: {relative}")
                return None
        return candidate

    def project_path(self, relative: str, label: str) -> Path | None:
        """Resolve a project-root-relative *input* reference (binding, not evidence)."""
        raw = str(relative)
        candidate_rel = Path(raw)
        if (not raw or raw != raw.strip() or "\x00" in raw or candidate_rel.is_absolute() or candidate_rel.drive
                or raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", raw)):
            self.failures.append(f"{label} input path must be project-relative: {relative}")
            return None
        candidate = Path(os.path.normpath(self.project_root / candidate_rel))
        try:
            candidate.relative_to(Path(os.path.normpath(self.project_root)))
        except ValueError:
            self.failures.append(f"{label} input path escapes project root: {relative}")
            return None
        # Resolve even a missing leaf: a parent symlink/junction can already
        # leave the project. Hashing an external file is not input containment.
        try:
            Path(os.path.realpath(candidate)).relative_to(Path(os.path.realpath(self.project_root)))
        except ValueError:
            self.failures.append(f"{label} input path escapes project root via link: {relative}")
            return None
        return candidate

    # ------------------------------------------------------------ artifacts
    def check_artifacts(self) -> list[Path]:
        artifact_hashes = self.data.get("artifact_hashes")
        if not isinstance(artifact_hashes, dict) or not artifact_hashes:
            self.failures.append("missing artifact hashes")
            artifact_hashes = {}
        self.artifact_hashes = {str(k): str(v) for k, v in artifact_hashes.items()}
        scan_files: list[Path] = []
        for relative, expected in self.artifact_hashes.items():
            candidate = self.contain(relative, "artifact")
            if candidate is None:
                continue
            if not candidate.is_file():
                self.failures.append(f"missing artifact: {relative}")
                continue
            if is_blank_file(candidate):
                self.blank_artifacts.add(relative)
            if not is_sha256(expected):
                self.failures.append(f"invalid artifact digest: {relative}")
            elif digest(candidate) != expected.lower():
                self.failures.append(f"artifact hash mismatch: {relative}")
            else:
                self.hashed_ok.add(relative)
            # A hash mismatch is a defect, not an exemption: the file still
            # gets the blocked-phrase and link scan.
            scan_files.append(candidate)
        return scan_files

    # ------------------------------------------------------------- evidence
    def applicability_record(self, key: str, value: object) -> bool:
        """True when value is a typed not-applicable record for a waivable key."""
        if not isinstance(value, dict) or value.get("applicable") is not False:
            return False
        waivable = set(self.spec.get("fallback_values", {})) | set(self.boundary.get("fallback_values", {}))
        waivable -= set(self.boundary.get("no_fallback", []) or [])
        if key not in waivable:
            self.failures.append(f"evidence not waivable: {key}")
            return True
        for field in ("reason", "scope", "decided_by"):
            if not filled(value.get(field)):
                self.failures.append(f"applicability record incomplete: {key} requires {field}")
        # The sanctioned wording is the whole waiver; any other reason would let
        # a submitter waive a scan or a stack lock in its own words.
        reason = value.get("reason")
        allowed = self.sanctioned_values(key)
        if filled(reason) and reason not in allowed:
            self.failures.append(
                f"applicability reason not sanctioned: {key} reason {reason!r} is not one of {sorted(allowed)}")
        return True

    def sanctioned_values(self, key: str) -> list[str]:
        """The wordings this boundary sanctions for a key, or none if barred."""
        if key in set(self.boundary.get("no_fallback", []) or []):
            return []
        return list(self.boundary.get("fallback_values", {}).get(key)
                    or self.spec.get("fallback_values", {}).get(key, []))

    def fallback_match(self, key: str, value: object) -> bool:
        allowed = self.sanctioned_values(key)
        if isinstance(value, str):
            return value in allowed
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            return value[0] in allowed
        return False

    def waived_as(self, key: str, value: object) -> str | None:
        """The sanctioned wording a key stands down on, whichever form it took.

        A bare string is the schema-1 form; at schema 2 the same wording arrives
        as the `reason` of an applicability record. Both are the key saying "not
        applicable for this sanctioned reason", so a cross-key rule that asks
        whether a key stood down has to read both.
        """
        allowed = self.sanctioned_values(key)
        if not allowed:
            return None
        if isinstance(value, str):
            return value if value in allowed else None
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            return value[0] if value[0] in allowed else None
        if isinstance(value, dict) and value.get("applicable") is False:
            reason = value.get("reason")
            return reason if isinstance(reason, str) and reason in allowed else None
        return None

    def check_evidence(self) -> list[str]:
        evidence = self.data.get("evidence", {})
        if not isinstance(evidence, dict):
            raise Engine("evidence must be a JSON object")
        required = self.boundary["required_evidence"]
        artifact_keys = set(self.boundary.get("artifact_evidence", []))
        types = self.spec.get("evidence_types", {})
        missing = sorted(k for k in required if not evidence.get(k))
        self.failures.extend(f"missing evidence: {key}" for key in missing)

        for key in required:
            value = evidence.get(key)
            if not value:
                continue
            # An explicit no-boundary seed is evidence of a scoped assessment,
            # not a waiver. Other applicable:false records retain waiver rules.
            seed_assessment = key == "security_seed" and types.get(key) == "security_seed"
            if not seed_assessment and self.applicability_record(key, value):
                continue
            if self.fallback_match(key, value):
                if self.schema >= 2:
                    self.failures.append(f"bare fallback string not accepted at schema 2: {key} (use an applicability record)")
                continue
            refs = evidence_strings(value)
            # A bare string or list is a file reference only where the key is
            # artifact-backed; elsewhere it is prose, and a version number or a
            # hostname is path-shaped without being a file.
            if key not in artifact_keys and not isinstance(value, dict):
                refs = []
            path_refs = [item for item in refs if is_path_like(item)]
            # Every declared path reference must be a correctly hashed artifact.
            enforce_refs = key in artifact_keys or self.schema >= 2
            if enforce_refs:
                for item in path_refs:
                    if item not in self.artifact_hashes:
                        self.failures.append(f"evidence references unhashed path: {key} -> {item}")
                    elif item not in self.hashed_ok:
                        self.failures.append(f"evidence references defective artifact: {key} -> {item}")
            if key in artifact_keys and not any(item in self.artifact_hashes for item in path_refs):
                self.failures.append(f"evidence not artifact-backed: {key}")
            self.check_blank_references(key, types.get(key), value)
            if self.schema >= 2 and key in types:
                self.check_typed(key, types[key], value)
        if self.schema >= 2:
            for key in required:
                if types.get(key) == "selection":
                    self.check_selection_dependencies(key)
                elif types.get(key) == "trace_map" and evidence.get(key):
                    self.check_trace_map(key, evidence.get(key))
        return missing

    def check_blank_references(self, key: str, kind: str | None, value: object) -> None:
        """An empty or whitespace-only file is no evidence for a key that names it.

        A correct hash of nothing proves nothing. The one exception is a scan
        record: its artifacts are the scanner's raw stdout and stderr, and a
        scanner that exits 0 in silence leaves them empty, while the record
        itself carries the command, the exit code and the inputs it bound."""
        if kind == "scan" or not self.blank_artifacts:
            return
        for ref in sorted({item for item in deep_strings(value) if item in self.blank_artifacts}):
            self.failures.append(f"empty artifact: {key} -> {ref}")

    # ---------------------------------------------------------------- typed
    def check_typed(self, key: str, kind: str, value: object) -> None:
        if kind in {"scan", "render", "probe"}:
            self.check_result_record(key, kind, value)
        elif kind == "security_seed":
            self.check_security_seed(key, value)
        elif kind == "human_go":
            self.check_human_go(key, value)
        elif kind == "findings":
            self.check_findings(key, value)
        elif kind == "verdict":
            self.check_verdict(key, value)
        elif kind == "stack_lock":
            self.check_stack_lock(key, value)
        elif kind == "revision_ref":
            self.check_upstream(key, value)
        elif kind == "decision_log":
            self.check_decision_log(key, value)
        elif kind == "acceptance_table":
            self.acceptance_ids(key, value, self, label=key)
        elif kind == "interface_set":
            self.check_interface_set(key, value)
        elif kind == "change_set":
            self.check_change_set(key, value)
        elif kind == "trace_map":
            pass  # cross-key: check_trace_map runs once every key it reads has been checked
        elif kind in {"preference_diff", "confirmation", "conflict_analysis",
                      "persistence_result", "effective_profile", "consumer_handoff"}:
            self.check_taste_record(key, kind, value)
        elif kind == "variant_set":
            self.check_variant_set(key, value)
        elif kind == "selection":
            self.check_selection(key, value)
        else:
            raise Engine(f"evidence type {kind!r} for {key} has no validator")

    def check_security_seed(self, key: str, value: object) -> None:
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a scoped security_seed assessment")
            return
        for field in ("scope", "decided_by", "architecture_revision", "reason"):
            if not filled(value.get(field)):
                self.failures.append(f"{key} requires {field}")
        if not isinstance(value.get("applicable"), bool):
            self.failures.append(f"{key} applicable must be boolean")
        boundaries = value.get("boundaries")
        if not isinstance(boundaries, list):
            self.failures.append(f"{key} requires a boundaries list")
        elif value.get("applicable") is False and boundaries:
            self.failures.append(f"{key} no-boundary assessment must have no boundaries")
        elif value.get("applicable") is True and not boundaries:
            self.failures.append(f"{key} applicable assessment requires boundaries and controls")
        else:
            for index, boundary in enumerate(boundaries):
                if not isinstance(boundary, dict) or not filled(boundary.get("id")) or not filled(boundary.get("control")):
                    self.failures.append(f"{key}.boundaries[{index}] requires id and control")

    def check_human_go(self, key: str, value: object) -> None:
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a human_go record")
            return
        for field in ("approver", "approval_reference", "revision", "decided_at"):
            if not filled(value.get(field)):
                self.failures.append(f"{key} requires {field}")
        if value.get("decision") != "go":
            self.failures.append(f"{key} decision must be go")
        if not timestamp_valid(value.get("decided_at")):
            self.failures.append(f"{key} decided_at must be a timezone-qualified ISO timestamp")
        delivery = self.data.get("evidence", {}).get("approved_delivery")
        if isinstance(delivery, dict):
            delivery = delivery.get("revision")
        if (filled(delivery) or isinstance(delivery, int)) and identity_token(value.get("revision")) != identity_token(delivery):
            self.failures.append(f"{key} revision must match approved_delivery")

    # ------------------------------------------------- source-of-truth records
    def artifact_texts(self, key: str, value: object) -> dict[str, str]:
        """The correctly hashed artifacts a value names, read as text; a missing one is already a failure."""
        texts = {}
        for ref in evidence_strings(value):
            if ref in self.hashed_ok:
                path = self.contain(ref, key)
                if path is not None:
                    texts[ref] = path.read_text(encoding="utf-8", errors="replace")
        return texts

    def check_decision_log(self, key: str, value: object) -> None:
        """The intake grilling log, read as the four fixed tables grill-me-doctrine.md Output defines."""
        texts = self.artifact_texts(key, value)
        if not texts:
            self.failures.append(f"{key} names no readable hashed decision log")
            return
        for ref, text in texts.items():
            self.failures.extend(decision_log_defects(text, f"{key} {ref}"))

    def acceptance_ids(self, key: str, value: object, owner: "Package", label: str, base: Path | None = None) -> list[str]:
        """The AC ids of the acceptance table the value names, recording each defect on ``owner``.

        ``base`` reads an upstream package's artifact (already re-hashed by check_upstream) instead of this one's."""
        if base is None:
            texts = self.artifact_texts(key, value)
        else:
            texts = {}
            hashed = owner.upstream_hashed.get(str(base), set())
            for ref in evidence_strings(value):
                path = Path(os.path.normpath(base / ref))
                if ref in hashed and path.is_file():
                    texts[ref] = path.read_text(encoding="utf-8", errors="replace")
        if not texts:
            owner.failures.append(f"{label} names no readable hashed acceptance table")
            return []
        ids: list[str] = []
        found = False
        for ref, text in texts.items():
            if md_section(text, ACCEPTANCE_SECTION[0]) is None:
                continue
            found = True
            rows, defects = table_records(text, ACCEPTANCE_SECTION[0], ACCEPTANCE_SECTION[1], f"{label} {ref}")
            owner.failures.extend(defects)
            if not defects and not rows:
                owner.failures.append(f"{label} {ref} acceptance table has no criteria")
            for row in rows:
                ident = row["ID"].strip()
                if not ACCEPTANCE_ID.fullmatch(ident):
                    owner.failures.append(f"{label} {ref} acceptance id {ident!r} is not AC-<n>")
                elif ident in ids:
                    owner.failures.append(f"{label} acceptance id {ident} repeats")
                else:
                    ids.append(ident)
        if not found:
            owner.failures.append(f"{label} names no artifact with a '{ACCEPTANCE_SECTION[0]}' section")
        return ids

    def check_interface_set(self, key: str, value: object) -> None:
        """{artifacts, change: changed|none, items: [{id: IF-<n>, kind, name}]}; each id stands in an artifact."""
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be an interface_set record at schema 2")
            return
        change = value.get("change")
        if change not in ("changed", "none"):
            self.failures.append(f"{key} change must be 'changed' or 'none'")
        items = value.get("items")
        if not isinstance(items, list):
            self.failures.append(f"{key} requires an items list")
            return
        if change == "changed" and not items:
            self.failures.append(f"{key} change 'changed' requires at least one item")
        if change == "none" and items:
            self.failures.append(f"{key} change 'none' must list no items")
        text = "\n".join(self.artifact_texts(key, value).values())
        seen: set[str] = set()
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not all(filled(item.get(f)) for f in ("id", "kind", "name")):
                self.failures.append(f"{key}.items[{index}] requires id, kind and name")
                continue
            ident = item["id"].strip()
            if not INTERFACE_ID.fullmatch(ident):
                self.failures.append(f"{key}.items[{index}] id {ident!r} is not IF-<n>")
            elif ident in seen:
                self.failures.append(f"{key} id {ident} repeats")
            elif not _cites(text, ident):
                self.failures.append(f"{key} {ident} appears in none of its artifacts")
            seen.add(ident)

    def check_change_set(self, key: str, value: object) -> None:
        """{artifacts: [diff], changed_files: [{path, sha256, status}]}: each file re-hashed and named by the diff."""
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a change_set record at schema 2")
            return
        files = value.get("changed_files")
        if not isinstance(files, list) or not files:
            self.failures.append(f"{key} requires a non-empty changed_files list")
            return
        text = "\n".join(self.artifact_texts(key, value).values())
        seen: set[str] = set()
        for index, entry in enumerate(files):
            if not isinstance(entry, dict) or not filled(entry.get("path")):
                self.failures.append(f"{key}.changed_files[{index}] requires path")
                continue
            path = entry["path"].strip()
            status = entry.get("status", "modified")
            if path in seen:
                self.failures.append(f"{key} lists {path} twice")
            seen.add(path)
            if not _one_of(status, CHANGE_STATUSES):
                self.failures.append(f"{key} {path} status must be one of {sorted(CHANGE_STATUSES)}")
                continue
            if path not in text:
                self.failures.append(f"{key} {path} does not appear in the diff artifact")
            target = self.project_path(path, key)
            if target is None:
                continue
            if status == "deleted":
                if target.exists():
                    self.failures.append(f"{key} {path} is marked deleted but exists")
            elif not is_sha256(entry.get("sha256")):
                self.failures.append(f"{key} {path} requires sha256")
            elif not target.is_file():
                self.failures.append(f"{key} {path} is missing")
            elif digest(target) != entry["sha256"].lower():
                self.failures.append(f"{key} {path} hash drift: the file changed after the build evidence was taken")

    def changed_paths(self) -> set[str]:
        evidence = self.data.get("evidence", {})
        types = self.spec.get("evidence_types", {})
        paths: set[str] = set()
        for key in self.boundary["required_evidence"]:
            value = evidence.get(key)
            if types.get(key) == "change_set" and isinstance(value, dict) and isinstance(value.get("changed_files"), list):
                paths |= {e["path"].strip() for e in value["changed_files"] if isinstance(e, dict) and filled(e.get("path"))}
        return paths

    def check_trace_map(self, key: str, value: object) -> None:
        """Every approved AC id is traced to changes and to tests the test log names, and every change is traced."""
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            self.failures.append(f"{key} must be a trace_map record with an items list at schema 2")
            return
        evidence = self.data.get("evidence", {})
        types = self.spec.get("evidence_types", {})
        required = self.boundary["required_evidence"]
        upstream_key = next((k for k in required if types.get(k) == "revision_ref"), None)
        approved: list[str] = []
        if upstream_key and upstream_key in self.upstream:
            data, base = self.upstream[upstream_key]
            source = (self.type_params(upstream_key, "revision_ref").get("acceptance_key") or "acceptance")
            approved = self.acceptance_ids(source, (data.get("evidence") or {}).get(source), self,
                                           label=f"{key} upstream {source}", base=base)
        if not approved:
            self.failures.append(f"{key} cannot be checked: no approved acceptance ids reached through {upstream_key}")
        changed = self.changed_paths()
        # The tests log is the one place a test name proves it ran (evidence_type_rules.probe).
        log = "\n".join(self.artifact_texts("tests", evidence.get("tests")).values()) if "tests" in required else ""
        covered: set[str] = set()
        traced: set[str] = set()
        for index, item in enumerate(value["items"]):
            label = f"{key}.items[{index}]"
            if not isinstance(item, dict):
                self.failures.append(f"{label} must be a mapping")
                continue
            ac = item.get("acceptance")
            if not filled(ac) or (approved and ac.strip() not in approved):
                self.failures.append(f"{label} acceptance {ac!r} is not an approved acceptance id")
            else:
                covered.add(ac.strip())
            changes = item.get("changes")
            if not isinstance(changes, list) or not changes or not all(filled(c) for c in changes):
                self.failures.append(f"{label} requires a non-empty changes list")
                changes = []
            for change in changes:
                if change.strip() not in changed:
                    self.failures.append(f"{label} change {change} is not in the implementation change set")
                traced.add(change.strip())
            tests = item.get("tests")
            if not isinstance(tests, list) or not tests or not all(filled(t) for t in tests):
                self.failures.append(f"{label} requires a non-empty tests list")
                tests = []
            for test in tests:
                if test.strip() not in log:
                    self.failures.append(f"{label} test {test.strip()!r} does not appear in the tests log")
        for ac in approved:
            if ac not in covered:
                self.failures.append(f"{key} leaves approved acceptance {ac} untraced")
        supporting = value.get("supporting", [])
        if not isinstance(supporting, list):
            self.failures.append(f"{key} supporting must be a list")
            supporting = []
        for index, entry in enumerate(supporting):
            if not isinstance(entry, dict) or not filled(entry.get("path")) or not filled(entry.get("reason")):
                self.failures.append(f"{key}.supporting[{index}] requires path and reason")
                continue
            if entry["path"].strip() not in changed:
                self.failures.append(f"{key}.supporting[{index}] {entry['path']} is not in the implementation change set")
            traced.add(entry["path"].strip())
        for path in sorted(changed - traced):
            self.failures.append(f"{key} leaves changed file {path} untraced")

    def check_upstream(self, key: str, value: object) -> None:
        """Bind an approved upstream revision to the cross-stage verdict that approved it, and prove the
        approved package is unchanged: its manifest fingerprint and every artifact it hashed still match."""
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a {{revision, verdict}} record binding the upstream verdict at schema 2")
            return
        revision = value.get("revision")
        if isinstance(revision, bool) or not isinstance(revision, (str, int)) or not str(revision).strip():
            self.failures.append(f"{key} must name an approved upstream revision")
        ref = value.get("verdict")
        if not filled(ref):
            self.failures.append(f"{key} requires verdict: the path of the upstream cross-stage verdict record")
            return
        if ref not in self.hashed_ok:
            self.failures.append(f"{key} verdict {ref} is not a correctly hashed artifact of this package")
            return
        path = self.contain(ref, key)
        if path is None:
            return
        params = self.type_params(key, "revision_ref")
        boundary = params.get("upstream_boundary")
        gate = (self.spec.get("judgment_policy", {}) or {}).get("cross_stage_gate", "gatekeeper-admiral")
        try:
            record = load_data(path)
        except DataFormatError:
            record = None
        if not isinstance(record, dict):
            self.failures.append(f"{key} verdict {ref} is not a verdict record")
            return
        judgment = record.get("judgment") if isinstance(record.get("judgment"), dict) else {}
        if boundary and record.get("boundary") != boundary:
            self.failures.append(f"{key} verdict is for {record.get('boundary')!r}, not {boundary!r}")
        if record.get("pass") is not True:
            self.failures.append(f"{key} verdict records mechanical failures")
        if judgment.get("gate") != gate or judgment.get("verdict") != "APPROVED" or judgment.get("valid") is not True:
            self.failures.append(f"{key} verdict is not a valid APPROVED judgment by {gate} "
                                 f"(gate {judgment.get('gate')!r}, verdict {judgment.get('verdict')!r})")
        if identity_token(record.get("revision")) != identity_token(revision):
            self.failures.append(f"{key} revision {revision!r} is not the approved revision {record.get('revision')!r}")
        run_id = self.data.get("run_id")
        if run_id is not None and record.get("run_id") != run_id:
            self.failures.append(f"{key} verdict belongs to run {record.get('run_id')!r}, not {run_id!r}")
        if record.get("gate_spec_is_shipped") is not True:
            self.warnings.append(f"{key} verdict was not produced against the shipped gate spec")
        name = record.get("manifest") if filled(record.get("manifest")) else "manifest.json"
        manifest = path.parent / Path(name).name
        root = Path(os.path.normpath(self.root))
        try:
            Path(os.path.realpath(manifest)).relative_to(Path(os.path.realpath(root)))
        except ValueError:
            self.failures.append(f"{key} approved manifest escapes the evidence root via link")
            return
        try:
            upstream = load_data(manifest)
        except (DataFormatError, OSError):
            upstream = None
        if not isinstance(upstream, dict):
            self.failures.append(f"{key} approved manifest {manifest.name} beside the verdict is unreadable")
            return
        if fingerprint(upstream) != record.get("package_fingerprint"):
            self.failures.append(f"{key} approved manifest changed after approval (fingerprint mismatch)")
        hashes = upstream.get("artifact_hashes") if isinstance(upstream.get("artifact_hashes"), dict) else {}
        for rel, expected in hashes.items():
            target = Path(os.path.normpath(manifest.parent / str(rel)))
            try:
                target.relative_to(root)
                Path(os.path.realpath(target)).relative_to(Path(os.path.realpath(root)))
            except ValueError:
                self.failures.append(f"{key} approved artifact escapes the evidence root: {rel}")
                continue
            if not target.is_file() or not is_sha256(expected) or digest(target) != str(expected).lower():
                self.failures.append(f"{key} approved artifact changed after approval: {rel}")
            else:
                self.upstream_hashed.setdefault(str(manifest.parent), set()).add(str(rel))
        self.upstream[key] = (upstream, manifest.parent)

    def type_params(self, key: str, kind: str) -> dict:
        """Typed-record parameters, read by evidence key first and kind second.

        One type can serve several keys with different shapes - at
        redesign-review `mock_set` and `selected_variant` are both `variant_set`
        records but count four mocks and one variant - so the key-specific entry
        wins and the kind-level entry stays the default for any key that has none.
        """
        params = self.spec.get("evidence_type_params", {}) or {}
        for name in (key, kind):
            entry = params.get(name)
            if isinstance(entry, dict):
                return entry
        return {}

    def set_ids(self, key: str) -> set[str] | None:
        """The declared ids of a variant_set-shaped evidence key, if it has any."""
        evidence = self.data.get("evidence", {})
        value = evidence.get(key) if isinstance(evidence, dict) else None
        params = self.type_params(key, "variant_set")
        entries = value.get(str(params.get("list_field") or "variants")) if isinstance(value, dict) else None
        if not isinstance(entries, list):
            return None
        return {item["id"].strip() for item in entries if isinstance(item, dict) and filled(item.get("id"))}

    def check_variant_set(self, key: str, value: object) -> None:
        """Exactly N entries, unique ids, every declared file a hashed artifact.

        The list name, the file fields, and the count all come from the gate
        spec, so the same rule counts four mocks under `mocks` and one built
        variant under `variants`.
        """
        params = self.type_params(key, "variant_set")
        required_count = int(params.get("required_count", 4))
        list_field = str(params.get("list_field") or "variants")
        file_fields = tuple(str(f) for f in (params.get("file_fields") or VARIANT_FILES))
        if not isinstance(value, dict) or not isinstance(value.get(list_field), list):
            self.failures.append(f"{key} must be a variant_set record with a {list_field} list at schema 2")
            return
        entries = value[list_field]
        if len(entries) != required_count:
            self.failures.append(f"{key} requires exactly {required_count} {list_field}, found {len(entries)}")
        if value.get("count") is not None and value.get("count") != len(entries):
            self.failures.append(f"{key} count {value.get('count')!r} does not match {len(entries)} {list_field}")
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            label = f"{key}.{list_field}[{index}]"
            if not isinstance(entry, dict):
                self.failures.append(f"{label} must be a mapping")
                continue
            if not filled(entry.get("id")):
                self.failures.append(f"{label} requires id")
            else:
                ident = entry["id"].strip()
                if ident in seen:
                    self.failures.append(f"{label} duplicate id {ident}")
                seen.add(ident)
            for field in file_fields:
                if not filled(entry.get(field)):
                    self.failures.append(f"{label} requires {field}")
                    continue
                path = entry[field].strip()
                if path not in self.artifact_hashes:
                    self.failures.append(f"{label} {field} is not a hashed artifact: {path}")
                elif path not in self.hashed_ok:
                    self.failures.append(f"{label} {field} references a defective artifact: {path}")

    def check_selection(self, key: str, value: object) -> None:
        """The recorded decision: a shape, and ids drawn from the set it chose from."""
        params = self.type_params(key, "selection")
        decisions = [str(d) for d in (params.get("decision_values") or ("variant", "merge", "deferred"))]
        variant_decision = str(params.get("variant_decision") or "variant")
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a typed selection record at schema 2")
            return
        decision = value.get("decision")
        if decision not in decisions:
            self.failures.append(f"{key} decision must be one of {sorted(decisions)}")
        for field in ("recommended", "decided_by", "decided_at", "basis"):
            if not filled(value.get(field)):
                self.failures.append(f"{key} record requires {field}")
        chosen = value.get("chosen")
        if decision == variant_decision:
            if not filled(chosen):
                self.failures.append(f"{key} decision {variant_decision!r} requires a chosen id")
        elif decision in decisions and chosen is not None:
            self.failures.append(f"{key} decision {decision!r} requires chosen: null")
        option_key = str(params.get("option_key") or "")
        option_ids = self.set_ids(option_key) if option_key else None
        if option_ids:
            for field in ("recommended", "chosen"):
                ident = value.get(field)
                if filled(ident) and ident not in option_ids:
                    self.failures.append(
                        f"{key} {field} {ident!r} is not one of the {option_key} ids {sorted(option_ids)}")

    def check_selection_dependencies(self, key: str) -> None:
        """The cross-key half of the decision: what the four dependent keys carry.

        A decision that names a variant means that variant was built, so the
        keys that describe a built prototype must hold real evidence - standing
        down in any wording, sanctioned or not, is refused - and the built
        variant must be the one that was chosen. Any other decision means no
        prototype exists, so each of them must stand down on the exact
        sanctioned wording for that decision - not a different one, and not
        silence.
        """
        evidence = self.data.get("evidence", {})
        record = evidence.get(key) if isinstance(evidence, dict) else None
        if not isinstance(record, dict):
            return
        params = self.type_params(key, "selection")
        decisions = [str(d) for d in (params.get("decision_values") or ())]
        dependent = [str(d) for d in (params.get("dependent_keys") or ())]
        if not dependent:
            return
        decision = record.get("decision")
        variant_decision = str(params.get("variant_decision") or "variant")
        if decision == variant_decision:
            for dep in dependent:
                value = evidence.get(dep)
                if isinstance(value, dict) and value.get("applicable") is False:
                    wording = value.get("reason")
                elif self.fallback_match(dep, value):
                    wording = value if isinstance(value, str) else value[0]
                else:
                    continue
                self.failures.append(
                    f"{dep} stands down on {wording!r} but {key} decision is {variant_decision!r}: "
                    f"a selected variant was built, so this key carries real evidence")
            built_key = str(params.get("built_key") or "")
            built_ids = self.set_ids(built_key) if built_key else None
            chosen = record.get("chosen")
            built = evidence.get(built_key) if built_key else None
            list_field = str(self.type_params(built_key, "variant_set").get("list_field") or "variants")
            entries = built.get(list_field) if isinstance(built, dict) else None
            first = entries[0] if isinstance(entries, list) and entries and isinstance(entries[0], dict) else None
            if first is not None and filled(chosen):
                ident = first["id"].strip() if filled(first.get("id")) else ""
                if ident != chosen.strip():
                    self.failures.append(
                        f"{built_key} was built for {ident!r} but {key} chose {chosen.strip()!r}: "
                        f"the built variant must be the selected one")
            elif built_ids is None and filled(chosen):
                self.failures.append(
                    f"{built_key} declares no {list_field} to compare against the {key} decision")
        elif decision in decisions:
            expected = (params.get("fallback_by_decision") or {}).get(str(decision))
            if not expected:
                return
            for dep in dependent:
                waived = self.waived_as(dep, evidence.get(dep))
                if waived != expected:
                    self.failures.append(
                        f"{dep} must stand down on {expected!r} because {key} decision is {decision!r}, "
                        f"not {waived!r}")

    def check_taste_record(self, key: str, kind: str, value: object) -> None:
        """Validate the preference-management records used by taste-review."""
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a typed {kind} record at schema 2")
            return
        list_fields = {
            "preference_diff": ("added", "updated", "deprecated", "revoked", "unchanged"),
            "confirmation": ("candidate_ids",),
            "conflict_analysis": ("conflicting_ids", "unresolved_conflicts",
                                  "accessibility_policy_collisions"),
            "persistence_result": ("requested_destinations", "committed_revisions"),
            "effective_profile": ("entries",),
        }.get(kind, ())
        scalar_fields = {
            "preference_diff": ("before_digest", "after_digest"),
            "confirmation": ("actor", "timestamp", "confirmed_scope", "source_run"),
            "conflict_analysis": ("precedence_decision",),
            "persistence_result": ("hashes", "atomicity_status", "rollback_result"),
            "effective_profile": ("digest",),
            "consumer_handoff": ("consuming_pipeline", "effective_profile_digest",
                                 "applicability_summary"),
        }[kind]
        for field in list_fields:
            if not isinstance(value.get(field), list):
                self.failures.append(f"{key} record requires list field {field}")
        for field in scalar_fields:
            if field == "hashes":
                continue
            if not filled(value.get(field)):
                self.failures.append(f"{key} record requires {field}")
        id_fields = {
            "preference_diff": list_fields,
            "confirmation": ("candidate_ids",),
            "conflict_analysis": list_fields,
        }.get(kind, ())
        for field in id_fields:
            items = value.get(field)
            if isinstance(items, list) and any(not filled(item) for item in items):
                self.failures.append(f"{key} record requires string ids in {field}")
        digest_fields = {
            "preference_diff": ("before_digest", "after_digest"),
            "effective_profile": ("digest",),
            "consumer_handoff": ("effective_profile_digest",),
        }.get(kind, ())
        for field in digest_fields:
            if not is_sha256(value.get(field)):
                self.failures.append(f"{key} record requires sha256 {field}")
        if kind == "confirmation":
            if not timestamp_valid(value.get("timestamp")):
                self.failures.append(f"{key} timestamp must be a timezone-qualified ISO timestamp")
            if not filled(value.get("confirmed_scope")) or value["confirmed_scope"] not in {"project", "repository", "global", "session"}:
                self.failures.append(f"{key} confirmed_scope is invalid")
            evidence = self.data.get("evidence", {})
            diff = evidence.get("preference_diff") if isinstance(evidence, dict) else None
            candidates = value.get("candidate_ids")
            if isinstance(candidates, list) and all(filled(item) for item in candidates):
                if len(candidates) != len(set(candidates)):
                    self.failures.append(f"{key} candidate_ids must be unique")
                changed_fields = ("added", "updated", "deprecated", "revoked")
                if isinstance(diff, dict) and all(isinstance(diff.get(field), list) and
                        all(filled(item) for item in diff[field]) for field in changed_fields):
                    changed = {item for field in changed_fields for item in diff[field]}
                    if set(candidates) != changed:
                        self.failures.append(f"{key} candidate_ids must match the preference_diff changed ids")
        if kind == "consumer_handoff":
            # gates.yaml calls this "the immutable effective-profile sha256", and
            # both records sit in the same manifest, so the comparison is mechanical.
            profile_key = next((k for k, t in self.spec.get("evidence_types", {}).items() if t == "effective_profile"), "")
            evidence = self.data.get("evidence")
            profile = evidence.get(profile_key) if isinstance(evidence, dict) else None
            handed = value.get("effective_profile_digest")
            if isinstance(profile, dict) and is_sha256(profile.get("digest")) and is_sha256(handed):
                if handed.lower() != profile["digest"].lower():
                    self.failures.append(f"{key} effective_profile_digest does not match the {profile_key} digest")
        if kind == "persistence_result":
            destinations = value.get("requested_destinations")
            if isinstance(destinations, list) and any(not filled(item) for item in destinations):
                self.failures.append(f"{key} requested_destinations requires non-blank strings")
            revisions = value.get("committed_revisions")
            if isinstance(revisions, list) and any(isinstance(item, bool) or
                    not ((isinstance(item, int) and item > 0) or filled(item)) for item in revisions):
                self.failures.append(f"{key} committed_revisions requires positive integers or revision identifiers")
            if not filled(value.get("atomicity_status")) or value["atomicity_status"] not in {"committed", "not-required", "unchanged"}:
                self.failures.append(f"{key} atomicity_status must be committed, unchanged or not-required")
            hashes = value.get("hashes")
            if not isinstance(hashes, dict) or not hashes or any(
                    not is_sha256(item) for item in hashes.values()):
                self.failures.append(f"{key} record requires a non-empty hashes map of sha256 values")
        if kind == "effective_profile" and isinstance(value.get("entries"), list):
            for index, entry in enumerate(value["entries"]):
                if not isinstance(entry, dict) or any(
                        not filled(entry.get(field))
                        for field in ("id", "source_scope", "source_id")):
                    self.failures.append(
                        f"{key}.entries[{index}] requires id, source_scope, and source_id")
                elif entry["source_scope"] not in {"project", "repository", "global", "session"}:
                    self.failures.append(f"{key}.entries[{index}] source_scope is invalid")

    def check_result_record(self, key: str, kind: str, value: object) -> None:
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a typed {kind} record at schema 2")
            return
        artifacts = [a for a in evidence_strings(value) if is_path_like(a)]
        if not artifacts:
            self.failures.append(f"{key} record declares no artifacts")
        result = value.get("result")
        status = result.get("status") if isinstance(result, dict) else result
        if not isinstance(status, str) or status not in RESULT_STATUSES:
            self.failures.append(f"{key} result status must be one of {sorted(RESULT_STATUSES)}")
        elif status != "pass" and not (kind == "render" and status == "inferred"):
            self.failures.append(f"{key} result not passing: {status}")
        if kind == "scan":
            for field in ("tool", "command", "observed_at"):
                if not filled(value.get(field)):
                    self.failures.append(f"{key} scan record requires {field}")
            if "exit_code" not in value:
                self.failures.append(f"{key} scan record requires exit_code")
        # The record is self-asserted, so the one contradiction it can show
        # against itself is refused: a pass beside a non-zero exit code.
        exit_code = value.get("exit_code")
        if isinstance(exit_code, bool) or not (exit_code is None or isinstance(exit_code, int)):
            self.failures.append(f"{key} exit_code must be an integer")
        elif status == "pass" and exit_code not in (None, 0):
            self.failures.append(f"{key} result pass contradicts exit_code {exit_code}")
        elif status == "pass" and exit_code is None and kind == "scan":
            self.failures.append(f"{key} scan record with result pass requires exit_code 0")
        if kind == "render":
            if status == "inferred" and not filled(value.get("limitation")):
                self.failures.append(f"{key} inferred render requires a limitation statement")
            for field in ("breakpoints", "themes"):
                items = value.get(field)
                if not isinstance(items, list) or not items:
                    self.failures.append(f"{key} render record requires non-empty {field}")
                elif any(not (filled(item) or (field == "breakpoints" and
                         isinstance(item, int) and not isinstance(item, bool) and item > 0)) for item in items):
                    self.failures.append(f"{key} render {field} has invalid nested values")
        inputs = value.get("inputs")
        if kind in {"scan", "render"}:
            if not isinstance(inputs, list) or not inputs:
                self.failures.append(f"{key} record must bind inputs (path + sha256) to the inspected source")
                inputs = []
        elif inputs is None:
            inputs = []
        if not isinstance(inputs, list):
            self.failures.append(f"{key} inputs must be a list")
            inputs = []
        for entry in inputs:
            if not isinstance(entry, dict) or not filled(entry.get("path")) or not is_sha256(entry.get("sha256")):
                self.failures.append(f"{key} input entry requires path and sha256")
                continue
            target = self.project_path(entry["path"], key)
            if target is None:
                continue
            if not target.is_file():
                self.failures.append(f"{key} input missing: {entry['path']}")
            elif digest(target) != entry["sha256"].lower():
                self.failures.append(f"{key} input hash drift (stale evidence): {entry['path']}")
        if not inputs and kind not in {"scan", "render"}:
            self.warnings.append(f"{key} binds no inputs: attested, not tied to the source it describes")
        input_revision = value.get("input_revision")
        if input_revision is not None and str(input_revision) != str(self.data.get("revision")):
            self.failures.append(f"{key} input_revision {input_revision!r} does not match package revision")

    def check_findings(self, key: str, value: object) -> None:
        items = value.get("items") if isinstance(value, dict) else value
        if not isinstance(items, list):
            self.failures.append(f"{key} must be a findings record with an items list at schema 2")
            return
        policy = self.spec.get("finding_policy", {})
        seen: dict[str, int] = {}
        for index, item in enumerate(items):
            label = f"{key}[{index}]"
            if not isinstance(item, dict):
                self.failures.append(f"{label} must be a mapping")
                continue
            # evidence_type_rules.findings: every item carries an id, and an id
            # names one finding, so a REVISE and a later delta can point at it.
            ident = item.get("id")
            if not filled(ident):
                self.failures.append(f"{label} requires id")
            else:
                ident = ident.strip()
                if ident in seen:
                    self.failures.append(f"{label} duplicate id {ident} (first at {key}[{seen[ident]}])")
                else:
                    seen[ident] = index
            severity = item.get("severity")
            status = item.get("status")
            if not isinstance(severity, str) or severity not in FINDING_SEVERITIES:
                self.failures.append(f"{label} severity must be one of {sorted(FINDING_SEVERITIES)}")
                continue
            if not isinstance(status, str) or status not in FINDING_STATUSES:
                self.failures.append(f"{label} status must be one of {sorted(FINDING_STATUSES)}")
                continue
            if status == "not-applicable" and not filled(item.get("reason")):
                self.failures.append(f"{label} not-applicable requires a reason")
            if severity == "Critical" and status != "verified" and status != "not-applicable":
                self.failures.append(f"{label} open Critical finding blocks the gate (status {status})")
            elif severity == "Major":
                closed = status in {"verified", "not-applicable"}
                deferred_ok = (
                    status == "deferred"
                    and policy.get("major_deferral", "owner-and-reopen-trigger") == "owner-and-reopen-trigger"
                    and filled(item.get("owner"))
                    and filled(item.get("reopen_trigger"))
                )
                if not closed and not deferred_ok:
                    self.failures.append(f"{label} unresolved Major finding blocks the gate (status {status})")

    def check_verdict(self, key: str, value: object) -> None:
        recommendation = value.get("recommendation") if isinstance(value, dict) else value
        if not isinstance(recommendation, str) or recommendation not in VERDICTS:
            self.failures.append(f"{key} must carry a recommendation in {sorted(VERDICTS)}")
            return
        if recommendation != "APPROVED":
            challenge = value.get("challenge") if isinstance(value, dict) else None
            if not isinstance(challenge, dict) or not filled(challenge.get("by")) or not filled(challenge.get("reason")):
                self.failures.append(f"{key} recommendation {recommendation} without a challenge record")

    def check_stack_lock(self, key: str, value: object) -> None:
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a stack-lock record or applicability record at schema 2")
            return
        slug = value.get("slug")
        overlay = value.get("overlay_sha256")
        overlay = overlay.strip() if isinstance(overlay, str) else overlay
        versions = value.get("versions")
        if not filled(slug) or not is_sha256(overlay) or not isinstance(versions, list) or not versions:
            self.failures.append(f"{key} record requires slug, versions, and overlay_sha256")
            return
        slug, overlay = slug.strip(), overlay.lower()
        registry_path = Path(str(self.spec.get("_registry_path") or REGISTRY_PATH))
        try:
            registry = load_data(registry_path)
        except DataFormatError as exc:
            raise Engine(f"tech-stack registry unreadable: {exc}") from exc
        overlays = registry.get("overlays", []) if isinstance(registry, dict) else []
        entry = next((o for o in overlays if isinstance(o, dict) and str(o.get("slug")) == slug), None)
        if entry is None:
            self.failures.append(f"{key} slug not in tech-stack registry: {slug}")
            return
        if str(entry.get("sha256", "")).lower() != overlay:
            self.failures.append(f"{key} overlay_sha256 does not match registry entry for {slug}")
        overlay_file = registry_path.parent.parent / str(entry.get("path", ""))
        if not overlay_file.is_file():
            # Without the file only the registry's own string was compared, which
            # verifies one side of "matches registry and file".
            self.failures.append(f"{key} overlay file for {slug} is missing: {entry.get('path')}")
        elif overlay_digest(overlay_file) != overlay:
            self.failures.append(f"{key} overlay file digest does not match declared overlay_sha256")
        offered = {str(v) for v in (entry.get("versions") or [])}
        unoffered = [v for v in versions if str(v) not in offered]
        if unoffered:
            self.failures.append(f"{key} versions {unoffered} not offered by registry entry {slug}")
        self.warn_registry_freshness(key, slug, registry)

    def warn_registry_freshness(self, key: str, slug: str, registry: object) -> None:
        """Say when a lock rests on pins the registry itself marks as past their date.

        A lock on an overlay whose ``support_ends`` has passed, or against a
        registry not re-read within its own ``verification_ttl_days``, still
        passes: choosing a supported version is the owner's decision and the
        gate makes none. The reader of the result is told, because the lock is
        then a statement about versions nobody has confirmed are current.
        """
        if not isinstance(registry, dict):
            return
        today = utc_today()
        support_ends = registry.get("support_ends")
        ended = support_ends.get(slug) if isinstance(support_ends, dict) else None
        if ended is not None:
            last_day = parse_date(ended)
            if last_day is None:
                self.warnings.append(f"{key}: support_ends for {slug} is not a YYYY-MM-DD date: {ended!r}")
            elif last_day < today:
                self.warnings.append(
                    f"{key}: support for the {slug} stack ended on {last_day.isoformat()}; the lock passes, "
                    "but its pinned versions are past their end of life")
        ttl = registry.get("verification_ttl_days")
        if ttl is None:
            return
        verified = parse_date(registry.get("verified_at"))
        if isinstance(ttl, bool) or not isinstance(ttl, int) or ttl < 1 or verified is None:
            self.warnings.append(
                f"{key}: the tech-stack registry's verified_at and verification_ttl_days are not a date and a positive "
                "whole number of days, so its freshness was not checked")
        elif (today - verified).days > ttl:
            self.warnings.append(
                f"{key}: the tech-stack registry was last verified on {verified.isoformat()}, more than {ttl} days ago; "
                "its pins are not known to be current")

    # ------------------------------------------------------------- lineage
    def check_identity(self) -> tuple[bool, set[str]]:
        data = self.data
        revisions = data.get("revisions", [])
        if not isinstance(revisions, list):
            raise Engine("revisions must be a JSON array")
        self.check_revision_types(revisions)
        distinct = set(map(str, revisions))
        mixed = len(distinct) > 1
        if mixed:
            self.failures.append("mixed revisions")
        elif not distinct:
            self.failures.append("revisions must contain exactly one value")
        for key in ("submission_id", "revision"):
            if not data.get(key):
                self.failures.append(f"missing {key}")
        if data.get("revision") and distinct and str(data.get("revision")) not in distinct:
            self.failures.append("revision not in revisions lineage")
        if data.get("verdict_revision") not in (None, data.get("revision")):
            self.failures.append("stale verdict revision")
        declared_boundary = data.get("boundary")
        if declared_boundary is not None and declared_boundary != self.boundary_name:
            self.failures.append(f"boundary mismatch: manifest declares {declared_boundary!r}")
        owner = data.get("owner", data.get("submitter"))
        if owner is not None and owner != self.boundary["submitter"]:
            self.failures.append(f"submitter mismatch: {owner!r} may not submit {self.boundary_name} (expected {self.boundary['submitter']!r})")
        if self.schema >= 2:
            if declared_boundary is None:
                self.failures.append("missing boundary (required at schema 2)")
            if owner is None:
                self.failures.append("missing owner (required at schema 2)")
        return mixed, distinct

    def check_revision_types(self, revisions: list) -> None:
        """A revision is a string or an integer, and one manifest uses one of them.

        ``str`` folds ``1`` and ``"1"`` into one value, so without this a manifest
        could mix them, and a resubmission that only retypes its revision would
        read as the same revision under a different fingerprint."""
        values = [("revisions", item) for item in revisions]
        for field in ("revision", "verdict_revision"):
            if self.data.get(field) is not None:
                values.append((field, self.data.get(field)))
        kinds: dict[str, list[str]] = {}
        for field, value in values:
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                self.failures.append(f"{field} value {value!r} must be a string or an integer")
                continue
            kinds.setdefault("integer" if isinstance(value, int) else "string", []).append(field)
        if len(kinds) > 1:
            self.failures.append(
                "revision values mix integer and string types: "
                + "; ".join(f"{kind}: {', '.join(sorted(set(fields)))}" for kind, fields in sorted(kinds.items())))

    # -------------------------------------------------------------- scanning
    def scan_text(self, scan_files: list[Path]) -> None:
        for path in scan_files:
            suffix = path.suffix.lower()
            if suffix not in SCANNED_TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            prose = strip_code(text)
            if has_blocked_phrase(prose):
                self.failures.append(f"blocked phrase: {path.name}")
            if suffix != ".md":
                continue
            for target in MD_LINK.findall(FENCED.sub(" ", text)):
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                resolved = Path(os.path.normpath(path.parent / clean))
                root = Path(os.path.normpath(self.root))
                if not resolved.exists():
                    self.failures.append(f"broken link in {path.name}: {target}")
                    continue
                try:
                    resolved.relative_to(root)
                    Path(os.path.realpath(resolved)).relative_to(Path(os.path.realpath(root)))
                except ValueError:
                    noun = "run evidence root" if self.root_kind == "run" else "package"
                    self.failures.append(f"link escapes {noun} in {path.name}: {target}")


def deep_strings(value: object):
    """Every string inside a nested evidence value (lists and mappings included)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from deep_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from deep_strings(item)


def evidence_digests(data: dict, artifact_hashes: dict[str, str]) -> dict[str, str]:
    """Per-key digest of each evidence value plus the artifact hashes it references.

    A resubmission can then be re-judged only where a key actually changed
    (gates.yaml revise_policy.delta_review).
    """
    digests: dict[str, str] = {}
    evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
    for key, value in evidence.items():
        refs = {item for item in deep_strings(value) if is_path_like(item)}
        bound = {item: artifact_hashes.get(item) for item in sorted(refs)}
        payload = json.dumps({"value": value, "artifacts": bound}, sort_keys=True, separators=(",", ":"), default=str)
        digests[str(key)] = hashlib.sha256(payload.encode()).hexdigest()
    return digests


def revise_packet(failures: list[str], required: list[str], owners: dict, submitter: str) -> dict:
    """Group failures by the evidence key they name and by that key's owner.

    One REVISE then routes to every owner at once (gates.yaml revise_policy.one_packet);
    failures that name no key (lineage, hashes, blocked phrases) go to the submitter.
    """
    by_key: dict[str, list[str]] = {}
    unassigned: list[str] = []
    for failure in failures:
        best: tuple[int, str] | None = None
        for key in required:
            match = re.search(r"(?:^|: )" + re.escape(key) + r"(?=$|[\s\[.:>,])", failure)
            if match and (best is None or match.start() < best[0]):
                best = (match.start(), key)
        if best is None:
            unassigned.append(failure)
        else:
            by_key.setdefault(best[1], []).append(failure)
    by_owner: dict[str, list[str]] = {}
    for key, items in by_key.items():
        by_owner.setdefault(str(owners.get(key) or submitter), []).extend(items)
    if unassigned:
        by_owner.setdefault(submitter, []).extend(unassigned)
    return {
        "by_owner": {owner: sorted(items) for owner, items in sorted(by_owner.items())},
        "by_key": {key: sorted(items) for key, items in sorted(by_key.items())},
        "unassigned": sorted(unassigned),
    }


def _cites(text: str, ref: str) -> bool:
    """True when ``ref`` (an id such as D-3 or AC-12) stands in ``text`` as a whole id, so D-3 is not found in D-30."""
    return re.search(r"(?<![A-Za-z0-9_-])" + re.escape(ref) + r"(?![A-Za-z0-9_])", text) is not None


def _catalog_file(source: object) -> Path | None:
    """A catalog-relative contract file (gates.yaml, design-doctrine.md, contracts/...) that exists, else None."""
    if not filled(source):
        return None
    raw = str(source).strip().removeprefix("skills/")
    rel = Path(raw)
    if rel.is_absolute() or rel.drive or ".." in rel.parts or rel.suffix not in {".md", ".yaml"}:
        return None
    candidate = (SKILLS_ROOT / rel).resolve()
    try:
        candidate.relative_to(SKILLS_ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _one_of(value: object, allowed: frozenset | set) -> bool:
    """Membership for a value read from a record: a list or mapping is never a member, and never a TypeError."""
    return isinstance(value, str) and value in allowed


def check_judgment(package: "Package", record: object, mechanical: list[str], spec: dict,
                   prior: dict | None, changed_evidence: list[str] | None) -> tuple[dict, list[str]]:
    """Validate a gatekeeper's judgment record against the package it judges.

    The mechanical pass proves what the package holds; this proves what the gate
    says about it is grounded (gates.yaml judgment_policy). Every finding names a
    required evidence key or none, stands on a source of truth that exists - a
    decision id in the intake log, an acceptance id in the plan, a section of a
    catalog contract, or two package artifacts that contradict each other - and,
    when it can block, points at hashed artifacts in the package. The verdict
    must follow from the findings and the mechanical result (revise_threshold),
    the owner is the spec's and never the gate's choice, and on a resubmission to
    the same gate a new blocking finding may name only changed evidence
    (batch_fix). Returns the normalised judgment and its failures; it never reads
    whether a finding is right, only whether it could be checked.
    """
    failures: list[str] = []
    boundary = package.boundary_name
    required = list(package.boundary["required_evidence"])
    owners = (spec.get("evidence_owners", {}) or {}).get(boundary, {}) or {}
    submitter = str(package.boundary.get("submitter", ""))
    policy = spec.get("judgment_policy", {}) or {}
    if not isinstance(record, dict):
        return {"valid": False}, ["judgment record must be a mapping"]

    if record.get("boundary") != boundary:
        failures.append(f"judgment boundary {record.get('boundary')!r} is not {boundary!r}")
    for field in ("submission_id", "revision"):
        if identity_token(record.get(field)) != identity_token(package.data.get(field)):
            failures.append(f"judgment {field} {record.get(field)!r} does not match the package's {package.data.get(field)!r}")
    gate = record.get("gate")
    allowed_gates = {str(policy.get("cross_stage_gate", "gatekeeper-admiral"))}
    phase_gate = (policy.get("phase_gates", {}) or {}).get(boundary)
    if phase_gate:
        allowed_gates.add(str(phase_gate))
    if not _one_of(gate, allowed_gates) or gate == submitter:
        failures.append(f"judgment gate {gate!r} may not judge {boundary} (allowed: {sorted(allowed_gates - {submitter})})")
    verdict = record.get("verdict")
    if not _one_of(verdict, VERDICTS):
        failures.append(f"judgment verdict must be one of {sorted(VERDICTS)}")

    findings = record.get("findings", [])
    if not isinstance(findings, list):
        failures.append("judgment findings must be a list")
        findings = []
    evidence = package.data.get("evidence", {}) if isinstance(package.data.get("evidence"), dict) else {}
    texts: dict[str, str] = {}

    def text_of(relative: str) -> str:
        if relative not in texts:
            path = package.contain(relative, "judgment basis")
            try:
                texts[relative] = path.read_text(encoding="utf-8", errors="replace") if path else ""
            except OSError:
                texts[relative] = ""
        return texts[relative]

    normalised: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(findings):
        label = f"judgment finding [{index}]"
        if not isinstance(item, dict):
            failures.append(f"{label} must be a mapping")
            continue
        ident = item.get("id")
        if not filled(ident):
            failures.append(f"{label} requires id")
        else:
            label = f"judgment finding {ident.strip()}"
            if ident.strip() in seen:
                failures.append(f"{label} duplicate id")
            seen.add(ident.strip())
        severity = item.get("severity")
        if not _one_of(severity, FINDING_SEVERITIES):
            failures.append(f"{label} severity must be one of {sorted(FINDING_SEVERITIES)}")
        if not filled(item.get("statement")):
            failures.append(f"{label} requires statement")
        key = item.get("key")
        if key is not None and not _one_of(key, set(required)):
            # A gate never invents an evidence key the spec does not require here.
            failures.append(f"{label} key {key!r} is not required evidence at {boundary}")
            key = None
        owner = str(owners.get(key) or submitter) if key else submitter
        if item.get("owner") is not None and item.get("owner") != owner:
            failures.append(f"{label} owner {item.get('owner')!r} is not the spec owner {owner!r}")

        anchors = item.get("evidence", [])
        if not isinstance(anchors, list) or any(not isinstance(a, str) for a in anchors):
            failures.append(f"{label} evidence must be a list of paths")
            anchors = []
        for anchor in anchors:
            manifest_key = MANIFEST_ANCHOR.fullmatch(anchor)
            if manifest_key:
                if manifest_key.group(1) not in required or manifest_key.group(1) not in evidence:
                    failures.append(f"{label} anchor {anchor} names no evidence in this manifest")
            elif anchor not in package.artifact_hashes:
                failures.append(f"{label} anchor is not a hashed package artifact: {anchor}")
            elif anchor not in package.hashed_ok:
                failures.append(f"{label} anchor is a defective artifact: {anchor}")
        if _one_of(severity, BLOCKING_SEVERITIES) and not anchors:
            failures.append(f"{label} {severity} requires at least one evidence anchor")

        basis = item.get("basis")
        if not isinstance(basis, dict) or not _one_of(basis.get("kind"), JUDGMENT_BASIS_KINDS):
            failures.append(f"{label} basis.kind must be one of {sorted(JUDGMENT_BASIS_KINDS)}")
        else:
            kind = basis["kind"]
            ref = basis.get("ref")
            if kind in JUDGMENT_REF_SHAPES:
                artifact = basis.get("artifact")
                if not filled(ref) or not JUDGMENT_REF_SHAPES[kind].fullmatch(ref.strip()):
                    failures.append(f"{label} {kind} basis ref must be an id like {JUDGMENT_REF_SHAPES[kind].pattern}")
                elif not filled(artifact) or artifact not in package.hashed_ok:
                    failures.append(f"{label} {kind} basis artifact is not a correctly hashed package artifact: {artifact!r}")
                else:
                    sources = [k for k in JUDGMENT_SOURCE_KEYS[kind] if k in required and evidence.get(k)]
                    named = {s for k in sources for s in evidence_strings(evidence.get(k))}
                    if sources and artifact not in named:
                        failures.append(f"{label} {kind} basis artifact {artifact} is not the package's {'/'.join(sources)} evidence")
                    elif not _cites(text_of(artifact), ref.strip()):
                        failures.append(f"{label} cites {ref.strip()}, which {artifact} does not contain")
            elif kind == "contract":
                if _catalog_file(basis.get("source")) is None:
                    failures.append(f"{label} contract basis source must be an existing catalog file: {basis.get('source')!r}")
                if not filled(ref):
                    failures.append(f"{label} contract basis requires ref (the section or rule)")
            elif len({a for a in anchors if a in package.hashed_ok}) < 2:
                failures.append(f"{label} contradiction basis requires two hashed artifacts that disagree")
        normalised.append({**item, "key": key, "owner": owner})

    blocking = [f for f in normalised if _one_of(f.get("severity"), BLOCKING_SEVERITIES)]
    if verdict == "APPROVED" and mechanical:
        failures.append("judgment APPROVED over mechanical failures")
    if verdict == "APPROVED" and blocking:
        failures.append("judgment APPROVED with a Critical or Major finding")
    if verdict == "REVISE" and not mechanical and not blocking:
        failures.append("judgment REVISE without a mechanical failure or a grounded Critical or Major finding "
                        "(revise_threshold)")
    if verdict == "ESCALATE":
        escalation = record.get("escalation")
        if not isinstance(escalation, dict) or not filled(escalation.get("reason")) or not filled(escalation.get("to")):
            failures.append("judgment ESCALATE requires escalation {to, reason}")

    prior_judgment = prior.get("judgment") if isinstance(prior, dict) else None
    if (isinstance(prior_judgment, dict) and prior_judgment.get("gate") == gate
            and changed_evidence is not None):
        carried = {str(f.get("id", "")).strip() for f in prior_judgment.get("findings", []) or [] if isinstance(f, dict)}
        for item in blocking:
            key, ident = item.get("key"), str(item.get("id", "")).strip()
            if key and key not in changed_evidence and ident not in carried:
                failures.append(f"judgment finding {ident} is new on unchanged evidence {key} (batch_fix)")

    by_owner: dict[str, list[str]] = {}
    for item in blocking:
        by_owner.setdefault(item["owner"], []).append(str(item.get("id", "")).strip())
    summary = {
        "gate": gate, "verdict": verdict, "findings": normalised,
        "by_owner": {owner: sorted(ids) for owner, ids in sorted(by_owner.items())},
        "escalation": record.get("escalation"), "valid": not failures,
    }
    return summary, sorted(set(failures))


def same_content(path: Path, other: Path) -> bool:
    """True when both files exist and hold the same content, line endings folded."""
    try:
        return digest(path) == digest(other)
    except OSError:
        return False


def identity_token(value: object) -> object:
    """A submission id or revision as compared across records: an integer and its
    decimal string are one token, surrounding blanks are ignored, anything else
    (None, a flag, a list) is compared as itself."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return value


def prior_check(prior_path: Path, data: dict, current_fingerprint: str, spec_digest: str,
                current_digests: dict[str, str] | None = None
                ) -> tuple[bool, bool | None, list[str] | None, list[str] | None, object]:
    """Return (drift, prior_reusable, changed_evidence, unchanged_evidence, prior gate_spec_digest)."""
    prior = load_mapping(prior_path, "prior record")
    # Delta review works across revisions: a resubmission is a new revision, and
    # the gatekeeper still wants to know which evidence keys actually changed.
    changed: list[str] | None = None
    unchanged: list[str] | None = None
    prior_digests = prior.get("evidence_digests")
    if isinstance(prior_digests, dict) and current_digests is not None:
        changed = sorted(k for k, v in current_digests.items() if prior_digests.get(k) != v)
        unchanged = sorted(k for k, v in current_digests.items() if prior_digests.get(k) == v)
    prior_spec = prior.get("gate_spec_digest")
    # Identity is compared as a token, so a revision or submission id that was
    # only retyped (1 -> "1") or re-spaced still reads as the same submission and
    # is held to the fingerprint below, never waved through as a new one.
    same = (identity_token(prior.get("submission_id")) == identity_token(data.get("submission_id"))
            and identity_token(prior.get("revision")) == identity_token(data.get("revision")))
    if not same:
        return False, None, changed, unchanged, prior_spec
    prior_fingerprint = prior.get("package_fingerprint") or fingerprint(prior)
    retyped = any(type(prior.get(field)) is not type(data.get(field)) for field in ("submission_id", "revision"))
    drift = retyped or prior_fingerprint != current_fingerprint
    prior_boundary = prior.get("boundary")
    reusable = (not drift) and prior_spec == spec_digest and (prior_boundary in (None, data.get("boundary")) )
    return drift, reusable, changed, unchanged, prior_spec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundary")
    parser.add_argument("--package")
    parser.add_argument("--intake-log")
    parser.add_argument("--prior")
    parser.add_argument("--gates", default=str(GATE_SPEC_PATH))
    parser.add_argument("--verdict-out")
    parser.add_argument("--judgment")
    parser.add_argument("--registry", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.intake_log:
        return intake_log_main(Path(args.intake_log).resolve())
    if not args.boundary or not args.package:
        parser.error("--boundary and --package are required (or --intake-log alone)")
    manifest_path = Path(args.package).resolve()
    try:
        spec_path = Path(args.gates).resolve()
        spec = load_gate_spec(spec_path)
        if args.registry:
            spec["_registry_path"] = args.registry
        spec_digest = digest(spec_path)
        boundaries = spec["boundaries"]
        if args.boundary not in boundaries:
            raise Engine(f"unknown boundary: {args.boundary!r} (expected one of {sorted(boundaries)})")
        data = load_mapping(manifest_path, "package")
        package = Package(manifest_path, data, args.boundary, spec)
        mixed, _ = package.check_identity()
        scan_files = package.check_artifacts()
        missing = package.check_evidence()
        package.scan_text(scan_files)

        current_fingerprint = fingerprint(data)
        digests = evidence_digests(data, package.artifact_hashes)
        drift, prior_reusable, changed_evidence, unchanged_evidence = False, None, None, None
        # The digests are unkeyed, so a verdict is only as canonical as the spec
        # it names; say when any input to this pass was not the shipped one.
        shipped_digest = digest(GATE_SPEC_PATH) if GATE_SPEC_PATH.is_file() else None
        spec_shipped = spec_digest == shipped_digest
        registry_shipped = not args.registry or same_content(Path(args.registry), REGISTRY_PATH)
        warnings = list(package.warnings)
        if not spec_shipped:
            warnings.append(f"gate spec is not the shipped skills/gates.yaml: {spec_path}")
        if not registry_shipped:
            warnings.append(f"tech-stack registry is not the shipped one: {args.registry}")
        prior_record = None
        if args.prior:
            drift, prior_reusable, changed_evidence, unchanged_evidence, prior_spec = prior_check(
                Path(args.prior).resolve(), data, current_fingerprint, spec_digest, digests)
            prior_record = {"path": str(Path(args.prior).resolve()), "gate_spec_digest": prior_spec,
                            "gate_spec_is_shipped": prior_spec is not None and prior_spec == shipped_digest}
            if not prior_record["gate_spec_is_shipped"]:
                warnings.append("prior record was not produced against the shipped gate spec")
            if drift:
                package.failures.append("idempotency drift on unchanged revision")
        failures = sorted(set(package.failures))
        packet = revise_packet(failures, list(boundaries[args.boundary]["required_evidence"]),
                               (spec.get("evidence_owners", {}) or {}).get(args.boundary, {}) or {},
                               str(boundaries[args.boundary].get("submitter", "")))
        # The prior gate's semantic verdict is read from the gate's own record,
        # never from the submitter's checkpoint, so a carried judgment is the
        # gate's and not the judged party's account of it.
        prior_data = load_mapping(Path(args.prior).resolve(), "prior record") if args.prior else None
        prior_judgment = prior_data.get("judgment") if prior_data else None
        if prior_record is not None and isinstance(prior_judgment, dict):
            prior_record["judgment"] = {"gate": prior_judgment.get("gate"), "verdict": prior_judgment.get("verdict"),
                                        "valid": prior_judgment.get("valid") is True}
        judgment, judgment_failures = None, []
        if args.judgment:
            judgment, judgment_failures = check_judgment(
                package, load_mapping(Path(args.judgment).resolve(), "judgment record"), failures, spec,
                prior_data, changed_evidence)
            packet["judgment_by_owner"] = judgment.get("by_owner", {})
        verdict_id = hashlib.sha256("|".join([
            args.boundary, spec_digest, str(data.get("submission_id")), str(data.get("revision")), current_fingerprint,
        ]).encode()).hexdigest()
        result = {
            "boundary": args.boundary, "pass": not failures, "failures": failures, "manifest": manifest_path.name,
            "missing": missing, "mixed_revisions": mixed, "idempotency_drift": drift,
            "prior_reusable": prior_reusable,
            "submission_id": data.get("submission_id"), "revision": data.get("revision"),
            "run_id": data.get("run_id"), "owner": data.get("owner", data.get("submitter")),
            "manifest_schema_version": package.schema,
            "declared_schema_version": data.get("schema_version"),
            "evidence_root": str(package.root), "evidence_root_kind": package.root_kind,
            "package_fingerprint": current_fingerprint, "gate_spec_digest": spec_digest,
            "gate_spec_is_shipped": spec_shipped, "registry_is_shipped": registry_shipped,
            "prior_record": prior_record,
            "verdict_id": verdict_id,
            "warnings": sorted(set(warnings)),
            "evidence_digests": digests,
            "changed_evidence": changed_evidence, "unchanged_evidence": unchanged_evidence,
            "revise_packet": packet,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "mechanical_only": judgment is None,
            "judgment": judgment, "judgment_failures": judgment_failures,
        }
        if args.verdict_out and judgment_failures:
            # An ungrounded judgment is never put on record: a stored REVISE or
            # APPROVED is what the next reader carries, so it must be checkable.
            print("judgment record rejected; verdict not written: " + "; ".join(judgment_failures), file=sys.stderr)
        elif args.verdict_out:
            out = Path(args.verdict_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(out.suffix + ".tmp")
            tmp.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, out)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not failures and not judgment_failures else 1
    except Exception as exc:  # fail loud: an engine fault is exit 2, never a bare traceback or a hidden pass
        message = str(exc) if isinstance(exc, (OSError, ValueError)) else f"internal error: {type(exc).__name__}: {exc}"
        print(json.dumps({"boundary": args.boundary, "engine_error": message}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
