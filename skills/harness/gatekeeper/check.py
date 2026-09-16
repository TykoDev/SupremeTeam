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
gate spec.

Output: a JSON report on stdout. On engine error a JSON object carrying
"engine_error" is written to stderr instead.

Exit codes: 0 = facts pass, 1 = defects found, 2 = engine error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]
GATE_SPEC_PATH = SKILLS_ROOT / "gates.yaml"
REGISTRY_PATH = SKILLS_ROOT / "tech-stacks" / "registry.yaml"
if str(SKILLS_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS_ROOT / "scripts"))

from data_formats import DataFormatError, load_data  # noqa: E402

SUPPORTED_MANIFEST_SCHEMAS = {1, 2}
BLOCKED = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b|\btrust me\b|\b100% complete\b|\blorem ipsum\b", re.IGNORECASE)
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
FENCED = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
# A string counts as an artifact reference when it is shaped like a relative
# file path: no whitespace, an extension, optional directory segments.
PATH_LIKE = re.compile(r"^(?:\.\.?[/\\])*(?:[\w.\-]+[/\\])*[\w.\-]+\.[A-Za-z0-9]{1,8}$")
SCANNED_TEXT_SUFFIXES = {".md", ".txt"}
VERDICTS = {"APPROVED", "REVISE", "ESCALATE"}
RESULT_STATUSES = {"pass", "fail", "error", "not-run", "unavailable", "inferred"}
FINDING_SEVERITIES = {"Critical", "Major", "Minor", "Info"}
FINDING_STATUSES = {"open", "in-progress", "resolved", "verified", "deferred", "not-applicable"}


class Engine(ValueError):
    """Engine/input failure: exit 2, never a pass."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overlay_digest(path: Path) -> str:
    """Digest of a tech-stack overlay with line endings normalised to LF.

    Registry digests are computed over the canonical LF content committed to the
    repository. A checkout that converts line endings (core.autocrlf=true) must
    not make every stack_lock fail, so overlays are hashed line-ending
    independently. Package artifacts are hashed byte-for-byte because the same
    machine writes and checks them.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


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
    policy = spec.get("finding_policy", {})
    if not isinstance(policy, dict):
        raise Engine("gate spec finding_policy must be a JSON object")
    return spec


def evidence_strings(value: object) -> list[str]:
    """Flatten an evidence value into the strings that may reference artifacts."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        found: list[str] = []
        for key in ("artifacts", "artifact", "path", "paths", "captures", "report"):
            found.extend(evidence_strings(value.get(key)))
        return found
    return []


def is_path_like(text: str) -> bool:
    return bool(PATH_LIKE.match(text.strip()))


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


class Package:
    def __init__(self, manifest_path: Path, data: dict, boundary_name: str, spec: dict) -> None:
        self.manifest_path = manifest_path
        self.base = manifest_path.parent
        self.data = data
        self.boundary_name = boundary_name
        self.spec = spec
        self.boundary = spec["boundaries"][boundary_name]
        self.failures: list[str] = []
        self.schema = self._schema_version()
        self.root, self.root_kind, self.run_dir, self.project_root = self._evidence_root()
        self.artifact_hashes: dict[str, str] = {}
        self.hashed_ok: set[str] = set()

    # ------------------------------------------------------------- identity
    def _schema_version(self) -> int:
        raw = self.data.get("schema_version", 1)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw not in SUPPORTED_MANIFEST_SCHEMAS:
            raise Engine(f"unsupported manifest schema_version: {raw!r} (supported: {sorted(SUPPORTED_MANIFEST_SCHEMAS)})")
        return raw

    def _evidence_root(self) -> tuple[Path, str, Path | None, Path]:
        """Resolve the authorised evidence root (see module docstring)."""
        run_dir = None
        node = self.base
        for _ in range(4):
            parent = node.parent
            if parent.name == "runs" and parent.parent.name == "skillset-saves":
                run_dir = node
                break
            if parent == node:
                break
            node = parent
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
        if not raw or candidate_rel.is_absolute() or candidate_rel.drive or raw.startswith(("/", "\\", "\\\\")):
            self.failures.append(f"{label} input path must be project-relative: {relative}")
            return None
        candidate = Path(os.path.normpath(self.project_root / candidate_rel))
        try:
            candidate.relative_to(Path(os.path.normpath(self.project_root)))
        except ValueError:
            self.failures.append(f"{label} input path escapes project root: {relative}")
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
            if not HEX64.match(expected.lower()):
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
        if key not in waivable:
            self.failures.append(f"evidence not waivable: {key}")
            return True
        for field in ("reason", "scope", "decided_by"):
            if not isinstance(value.get(field), str) or not value.get(field).strip():
                self.failures.append(f"applicability record incomplete: {key} requires {field}")
        return True

    def fallback_match(self, key: str, value: object) -> bool:
        allowed = (self.boundary.get("fallback_values", {}).get(key)
                   or self.spec.get("fallback_values", {}).get(key, []))
        if isinstance(value, str):
            return value in allowed
        if isinstance(value, list) and len(value) == 1 and isinstance(value[0], str):
            return value[0] in allowed
        return False

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
            if self.applicability_record(key, value):
                continue
            if self.fallback_match(key, value):
                if self.schema >= 2:
                    self.failures.append(f"bare fallback string not accepted at schema 2: {key} (use an applicability record)")
                continue
            refs = evidence_strings(value)
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
            if self.schema >= 2 and key in types:
                self.check_typed(key, types[key], value)
        return missing

    # ---------------------------------------------------------------- typed
    def check_typed(self, key: str, kind: str, value: object) -> None:
        if kind in {"scan", "render", "probe", "audit"}:
            self.check_result_record(key, kind, value)
        elif kind == "findings":
            self.check_findings(key, value)
        elif kind == "verdict":
            self.check_verdict(key, value)
        elif kind == "stack_lock":
            self.check_stack_lock(key, value)
        elif kind == "revision_ref":
            # An upstream approved revision is recorded, not necessarily equal to
            # this package's own revision; it must be a non-empty scalar identifier.
            if isinstance(value, bool) or not isinstance(value, (str, int)) or not str(value).strip():
                self.failures.append(f"{key} must name an approved upstream revision")
        elif kind in {"preference_diff", "confirmation", "conflict_analysis",
                      "persistence_result", "effective_profile", "consumer_handoff"}:
            self.check_taste_record(key, kind, value)

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
            item = value.get(field)
            if not isinstance(item, str) or not item.strip():
                self.failures.append(f"{key} record requires {field}")
        id_fields = {
            "preference_diff": list_fields,
            "confirmation": ("candidate_ids",),
            "conflict_analysis": list_fields,
        }.get(kind, ())
        for field in id_fields:
            items = value.get(field)
            if isinstance(items, list) and any(not isinstance(item, str) or not item.strip()
                                               for item in items):
                self.failures.append(f"{key} record requires string ids in {field}")
        digest_fields = {
            "preference_diff": ("before_digest", "after_digest"),
            "effective_profile": ("digest",),
            "consumer_handoff": ("effective_profile_digest",),
        }.get(kind, ())
        for field in digest_fields:
            if not HEX64.match(str(value.get(field, "")).lower()):
                self.failures.append(f"{key} record requires sha256 {field}")
        if kind == "persistence_result":
            hashes = value.get("hashes")
            if not isinstance(hashes, dict) or not hashes or any(
                    not HEX64.match(str(item).lower()) for item in hashes.values()):
                self.failures.append(f"{key} record requires a non-empty hashes map of sha256 values")
        if kind == "effective_profile" and isinstance(value.get("entries"), list):
            for index, entry in enumerate(value["entries"]):
                if not isinstance(entry, dict) or any(
                        not str(entry.get(field, "")).strip()
                        for field in ("id", "source_scope", "source_id")):
                    self.failures.append(
                        f"{key}.entries[{index}] requires id, source_scope, and source_id")

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
                if not str(value.get(field, "")).strip():
                    self.failures.append(f"{key} scan record requires {field}")
            if "exit_code" not in value:
                self.failures.append(f"{key} scan record requires exit_code")
        if kind == "render":
            if status == "inferred" and not str(value.get("limitation", "")).strip():
                self.failures.append(f"{key} inferred render requires a limitation statement")
            for field in ("breakpoints", "themes"):
                if not isinstance(value.get(field), list) or not value.get(field):
                    self.failures.append(f"{key} render record requires non-empty {field}")
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
            if not isinstance(entry, dict) or not str(entry.get("path", "")).strip() or not HEX64.match(str(entry.get("sha256", "")).lower()):
                self.failures.append(f"{key} input entry requires path and sha256")
                continue
            target = self.project_path(str(entry["path"]), key)
            if target is None:
                continue
            if not target.is_file():
                self.failures.append(f"{key} input missing: {entry['path']}")
            elif digest(target) != str(entry["sha256"]).lower():
                self.failures.append(f"{key} input hash drift (stale evidence): {entry['path']}")
        input_revision = value.get("input_revision")
        if input_revision is not None and str(input_revision) != str(self.data.get("revision")):
            self.failures.append(f"{key} input_revision {input_revision!r} does not match package revision")

    def check_findings(self, key: str, value: object) -> None:
        items = value.get("items") if isinstance(value, dict) else value
        if not isinstance(items, list):
            self.failures.append(f"{key} must be a findings record with an items list at schema 2")
            return
        policy = self.spec.get("finding_policy", {})
        for index, item in enumerate(items):
            label = f"{key}[{index}]"
            if not isinstance(item, dict):
                self.failures.append(f"{label} must be a mapping")
                continue
            severity = item.get("severity")
            status = item.get("status")
            if severity not in FINDING_SEVERITIES:
                self.failures.append(f"{label} severity must be one of {sorted(FINDING_SEVERITIES)}")
                continue
            if status not in FINDING_STATUSES:
                self.failures.append(f"{label} status must be one of {sorted(FINDING_STATUSES)}")
                continue
            if status == "not-applicable" and not str(item.get("reason", "")).strip():
                self.failures.append(f"{label} not-applicable requires a reason")
            if severity == "Critical" and status != "verified" and status != "not-applicable":
                self.failures.append(f"{label} open Critical finding blocks the gate (status {status})")
            elif severity == "Major":
                closed = status in {"verified", "not-applicable"}
                deferred_ok = (
                    status == "deferred"
                    and policy.get("major_deferral", "owner-and-reopen-trigger") == "owner-and-reopen-trigger"
                    and str(item.get("owner", "")).strip()
                    and str(item.get("reopen_trigger", "")).strip()
                )
                if not closed and not deferred_ok:
                    self.failures.append(f"{label} unresolved Major finding blocks the gate (status {status})")

    def check_verdict(self, key: str, value: object) -> None:
        recommendation = value.get("recommendation") if isinstance(value, dict) else value
        if recommendation not in VERDICTS:
            self.failures.append(f"{key} must carry a recommendation in {sorted(VERDICTS)}")
            return
        if recommendation != "APPROVED":
            challenge = value.get("challenge") if isinstance(value, dict) else None
            if not isinstance(challenge, dict) or not str(challenge.get("by", "")).strip() or not str(challenge.get("reason", "")).strip():
                self.failures.append(f"{key} recommendation {recommendation} without a challenge record")

    def check_stack_lock(self, key: str, value: object) -> None:
        if not isinstance(value, dict):
            self.failures.append(f"{key} must be a stack-lock record or applicability record at schema 2")
            return
        slug = str(value.get("slug", "")).strip()
        overlay = str(value.get("overlay_sha256", "")).lower().strip()
        versions = value.get("versions")
        if not slug or not HEX64.match(overlay) or not isinstance(versions, list) or not versions:
            self.failures.append(f"{key} record requires slug, versions, and overlay_sha256")
            return
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
        if overlay_file.is_file() and overlay_digest(overlay_file) != overlay:
            self.failures.append(f"{key} overlay file digest does not match declared overlay_sha256")
        registry_versions = {str(v) for v in (entry.get("versions") or [])}
        if registry_versions and not ({str(v) for v in versions} & registry_versions):
            self.failures.append(f"{key} versions {versions} not offered by registry entry {slug}")

    # ------------------------------------------------------------- lineage
    def check_identity(self) -> tuple[bool, set[str]]:
        data = self.data
        revisions = data.get("revisions", [])
        if not isinstance(revisions, list):
            raise Engine("revisions must be a JSON array")
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

    # -------------------------------------------------------------- scanning
    def scan_text(self, scan_files: list[Path]) -> None:
        for path in scan_files:
            suffix = path.suffix.lower()
            if suffix not in SCANNED_TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            prose = strip_code(text)
            if BLOCKED.search(prose):
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


def prior_check(prior_path: Path, data: dict, current_fingerprint: str, spec_digest: str) -> tuple[bool, bool | None]:
    """Return (drift, prior_reusable)."""
    prior = load_mapping(prior_path, "prior record")
    same = prior.get("submission_id") == data.get("submission_id") and prior.get("revision") == data.get("revision")
    if not same:
        return False, None
    prior_fingerprint = prior.get("package_fingerprint") or fingerprint(prior)
    drift = prior_fingerprint != current_fingerprint
    prior_spec = prior.get("gate_spec_digest")
    prior_boundary = prior.get("boundary")
    reusable = (not drift) and prior_spec == spec_digest and (prior_boundary in (None, data.get("boundary")) )
    return drift, reusable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boundary", required=True)
    parser.add_argument("--package", required=True)
    parser.add_argument("--prior")
    parser.add_argument("--gates", default=str(GATE_SPEC_PATH))
    parser.add_argument("--verdict-out")
    parser.add_argument("--registry", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
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
        drift, prior_reusable = False, None
        if args.prior:
            drift, prior_reusable = prior_check(Path(args.prior).resolve(), data, current_fingerprint, spec_digest)
            if drift:
                package.failures.append("idempotency drift on unchanged revision")
        failures = sorted(set(package.failures))
        verdict_id = hashlib.sha256("|".join([
            args.boundary, spec_digest, str(data.get("submission_id")), str(data.get("revision")), current_fingerprint,
        ]).encode()).hexdigest()
        result = {
            "boundary": args.boundary, "pass": not failures, "failures": failures,
            "missing": missing, "mixed_revisions": mixed, "idempotency_drift": drift,
            "prior_reusable": prior_reusable,
            "submission_id": data.get("submission_id"), "revision": data.get("revision"),
            "run_id": data.get("run_id"), "owner": data.get("owner", data.get("submitter")),
            "manifest_schema_version": package.schema,
            "evidence_root": str(package.root), "evidence_root_kind": package.root_kind,
            "package_fingerprint": current_fingerprint, "gate_spec_digest": spec_digest,
            "verdict_id": verdict_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "mechanical_only": True,
        }
        if args.verdict_out:
            out = Path(args.verdict_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(out.suffix + ".tmp")
            tmp.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, out)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not failures else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"boundary": args.boundary, "engine_error": str(exc)}, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
