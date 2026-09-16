#!/usr/bin/env python3
"""Validate the Supreme Team orchestration manifests and their cross-references.

Checks five contracts and the agreements between them:

  team-manifest.yaml     roster shape; every named role exists exactly once
  ownership.yaml         one writer per artifact; every owner is a team member
  gates.yaml             every boundary submitter is an ownership owner
  runtime-manifest.yaml  runtime floor, launchers, commands, CI matrix
  package-manifest.yaml  include/exclude and the delivery contract

It also confirms that every skill path named in the Admiral agent manifest's
``delegates_to`` list resolves to a SKILL.md on disk.

Output: a JSON report on stdout. Exit 0 when clean, 1 when a contract is
violated or unreadable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SKILLS = Path(__file__).resolve().parents[1]
if str(SKILLS / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import DataFormatError, load_data  # noqa: E402

TEAM_ROLE_KEYS = ("front_door", "session_memory", "cross_stage_gatekeeper")
TEAM_LIST_KEYS = (
    "phase_leads", "phase_gatekeepers", "pipeline_owners", "specialists",
    "creation", "release", "safety", "browser", "testing",
)
REQUIRED_LAUNCHERS = ("windows", "macos_linux", "codex", "claude_code", "copilot")
REQUIRED_COMMANDS = (
    "runtime_check", "manifests", "hooks", "gates", "validation", "readiness",
    "hook_registration", "gate_check", "save_lifecycle", "package_check",
)
REQUIRED_CI_PLATFORMS = {"windows", "macos", "linux"}


def _load(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        data = load_data(path)
    except (OSError, DataFormatError) as exc:
        errors.append(f"{path.name}: unreadable ({exc})")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{path.name}: root must be a mapping")
        return {}
    return data


def _names(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value} if value.strip() else set()
    if isinstance(value, list):
        return {str(item) for item in value if str(item).strip()}
    return set()


def team_members(team: dict[str, Any]) -> set[str]:
    members: set[str] = set()
    for key in TEAM_ROLE_KEYS:
        members |= _names(team.get(key))
    for key in TEAM_LIST_KEYS:
        members |= _names(team.get(key, []))
    return members


def check_team(team: dict[str, Any], errors: list[str]) -> set[str]:
    for key in TEAM_ROLE_KEYS:
        if not str(team.get(key, "")).strip():
            errors.append(f"team-manifest.yaml: missing role {key}")
    for key in TEAM_LIST_KEYS:
        value = team.get(key)
        if not isinstance(value, list) or not value:
            errors.append(f"team-manifest.yaml: {key} must be a non-empty list")
    if team.get("state_root") != "skillset-saves":
        errors.append("team-manifest.yaml: state_root must be skillset-saves")
    if _names(team.get("verdicts", [])) != {"APPROVED", "REVISE", "ESCALATE"}:
        errors.append("team-manifest.yaml: verdicts must be APPROVED, REVISE, ESCALATE")
    return team_members(team)


def check_ownership(ownership: dict[str, Any], members: set[str], errors: list[str]) -> set[str]:
    """One writer per artifact, and every owner is a member of the team."""
    owners = ownership.get("owners")
    if not isinstance(owners, dict) or not owners:
        errors.append("ownership.yaml: owners must be a non-empty mapping")
        owners = {}
    artifacts = ownership.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("ownership.yaml: artifacts must be a non-empty list")
        artifacts = []

    # "gatekeeper" and "safety-guardrails" are role names filled by exactly one
    # skill per boundary or action; ownership.yaml names the role, not the skill.
    role_owners = {"gatekeeper", "safety-guardrails", "phase-lead"}
    for name in owners:
        if name not in members and name not in role_owners:
            errors.append(f"ownership.yaml: owner {name!r} is not in team-manifest.yaml")

    artifact_ids: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            errors.append("ownership.yaml: artifact row must be a mapping")
            continue
        artifact_id = str(artifact.get("id", ""))
        owner = str(artifact.get("owner", ""))
        if not artifact_id:
            errors.append("ownership.yaml: artifact row without an id")
            continue
        if artifact_id in artifact_ids:
            errors.append(f"ownership.yaml: duplicate artifact id {artifact_id!r}")
        artifact_ids.add(artifact_id)
        if owner not in owners and owner not in role_owners:
            errors.append(f"ownership.yaml: {artifact_id} has unknown owner {owner!r}")
        writers = sorted(
            name for name, contract in owners.items()
            if isinstance(contract, dict) and artifact_id in _names(contract.get("writes", []))
        )
        if owner in role_owners:
            if not writers:
                errors.append(f"ownership.yaml: {artifact_id} is a role artifact with no declared writer")
        elif writers != [owner]:
            errors.append(
                f"ownership.yaml: {artifact_id} must have exactly {owner!r} as writer; found {writers}"
            )
        if not str(artifact.get("before", "")).strip():
            errors.append(f"ownership.yaml: {artifact_id} requires a non-empty before boundary")
        evidence = artifact.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"ownership.yaml: {artifact_id} requires non-empty evidence")

    for name, contract in owners.items():
        if not isinstance(contract, dict):
            errors.append(f"ownership.yaml: owner {name!r} must be a mapping")
            continue
        if not str(contract.get("role", "")).strip():
            errors.append(f"ownership.yaml: owner {name!r} requires a role")
        unknown = sorted(_names(contract.get("writes", [])) - artifact_ids)
        if unknown:
            errors.append(f"ownership.yaml: owner {name!r} writes undeclared artifacts {unknown}")
    return artifact_ids


def check_gates(gates: dict[str, Any], owners: set[str], errors: list[str]) -> None:
    boundaries = gates.get("boundaries")
    if not isinstance(boundaries, dict) or not boundaries:
        errors.append("gates.yaml: boundaries must be a non-empty mapping")
        return
    waivable = set(gates.get("fallback_values", {}) or {})
    typed = set(gates.get("evidence_types", {}) or {})
    declared: set[str] = set()
    for name, boundary in boundaries.items():
        submitter = str(boundary.get("submitter", ""))
        if submitter not in owners:
            errors.append(f"gates.yaml: boundary {name!r} submitter {submitter!r} is not an ownership owner")
        if not str(boundary.get("guards", "")).strip():
            errors.append(f"gates.yaml: boundary {name!r} must name the transition it guards")
        declared |= _names(boundary.get("required_evidence", []))
    orphan_fallbacks = sorted(waivable - declared)
    if orphan_fallbacks:
        errors.append(f"gates.yaml: fallback_values for keys no boundary requires {orphan_fallbacks}")
    orphan_types = sorted(typed - declared)
    if orphan_types:
        errors.append(f"gates.yaml: evidence_types for keys no boundary requires {orphan_types}")
    owner_map = gates.get("evidence_owners", {}) or {}
    for name, boundary in boundaries.items():
        required = _names(boundary.get("required_evidence", []))
        for key in _names(boundary.get("no_fallback", [])):
            if key not in required:
                errors.append(f"gates.yaml: boundary {name!r} no_fallback names unrequired key {key!r}")
        mapping = owner_map.get(name)
        if not isinstance(mapping, dict) or set(mapping) != required:
            errors.append(f"gates.yaml: evidence_owners for {name!r} must map exactly its required evidence keys")
            continue
        for key, owner in mapping.items():
            if str(owner) not in owners:
                errors.append(f"gates.yaml: evidence_owners {name}.{key} names unknown owner {owner!r}")
    type_names = set(map(str, (gates.get("evidence_types", {}) or {}).values()))
    for kind in (gates.get("evidence_type_params", {}) or {}):
        if kind not in type_names:
            errors.append(f"gates.yaml: evidence_type_params for unknown record type {kind!r}")
    policy = gates.get("revise_policy")
    if not isinstance(policy, dict) or policy.get("cycle_cap") != 2 or not all(
            str(policy.get(k, "")).strip() for k in ("self_check", "one_packet", "parallel_fix", "delta_review")):
        errors.append("gates.yaml: revise_policy must declare self_check, one_packet, parallel_fix, delta_review, and cycle_cap 2")


def check_runtime(runtime: dict[str, Any], root: Path, errors: list[str]) -> None:
    python = runtime.get("runtime", {}).get("python", {}) if isinstance(runtime.get("runtime"), dict) else {}
    minimum = str(python.get("minimum", ""))
    parts = minimum.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        errors.append("runtime-manifest.yaml: runtime.python.minimum must be major.minor")
    elif tuple(int(part) for part in parts) < (3, 9):
        errors.append("runtime-manifest.yaml: Python minimum may not fall below 3.9")
    if python.get("stdlib_only_for_hooks_and_gates") is not True:
        errors.append("runtime-manifest.yaml: hooks and gates must stay stdlib-only")
    for dependency in python.get("optional_dependencies", []) or []:
        if not isinstance(dependency, dict):
            errors.append("runtime-manifest.yaml: optional dependency must be a mapping")
            continue
        fallback = str(dependency.get("fallback", ""))
        target = (root.parent / fallback) if fallback.startswith("skills/") else (root / fallback)
        if not fallback or not target.is_file():
            errors.append(f"runtime-manifest.yaml: {dependency.get('name')!r} fallback path is invalid")
    launchers = runtime.get("launchers", {})
    for name in REQUIRED_LAUNCHERS:
        if not isinstance(launchers, dict) or not str(launchers.get(name, "")).strip():
            errors.append(f"runtime-manifest.yaml: missing launcher {name}")
    commands = runtime.get("commands", {})
    for name in REQUIRED_COMMANDS:
        if not isinstance(commands, dict) or not str(commands.get(name, "")).strip():
            errors.append(f"runtime-manifest.yaml: missing command {name}")
    matrix = runtime.get("ci_matrix", [])
    platforms = {
        str(item.get("platform")) for item in matrix
        if isinstance(item, dict) and str(item.get("launcher", "")).strip()
    } if isinstance(matrix, list) else set()
    if platforms != REQUIRED_CI_PLATFORMS:
        errors.append(f"runtime-manifest.yaml: CI platform matrix mismatch {sorted(platforms)}")


def check_package(package: dict[str, Any], errors: list[str]) -> None:
    for key in ("package", "root", "include", "exclude", "delivery_contract"):
        if key not in package:
            errors.append(f"package-manifest.yaml: missing key {key}")
    contract = package.get("delivery_contract", {})
    if not isinstance(contract, dict):
        errors.append("package-manifest.yaml: delivery_contract must be a mapping")
        return
    for key in ("cache_files_are_publishable", "runtime_state_is_publishable", "save_state_is_publishable"):
        if contract.get(key) is not False:
            errors.append(f"package-manifest.yaml: delivery_contract.{key} must be false")
    excludes = set(_names(package.get("exclude", [])))
    for required in ("**/__pycache__/**", "**/*.pyc", "skillset-saves/**", ".harness-state/**", ".supremeteam/**"):
        if required not in excludes:
            errors.append(f"package-manifest.yaml: exclude must contain {required}")


def check_pipeline_mirrors(root: Path, team: dict[str, Any], ownership: dict[str, Any],
                           gates: dict[str, Any], errors: list[str]) -> int:
    pipelines = _load(root / "pipelines.yaml", errors).get("pipelines", {})
    save = _load(root / "save-ownership.yaml", errors)
    if not isinstance(pipelines, dict) or not pipelines:
        errors.append("pipelines.yaml: pipelines must be a non-empty mapping")
        return 0
    members = team_members(team)
    artifact_owner = {str(x.get("id")): str(x.get("owner")) for x in ownership.get("artifacts", [])
                      if isinstance(x, dict)}
    boundary_owners: dict[str, list[str]] = {}
    for name, pipeline in pipelines.items():
        if pipeline.get("owner") not in members:
            errors.append(f"pipelines.yaml: {name} owner is not a team member")
        boundary = str(pipeline.get("boundary", ""))
        boundary_owners.setdefault(boundary, []).append(name)
        for stage in pipeline.get("stages", []):
            owner, artifact = stage.get("owner"), stage.get("artifact")
            if owner not in members:
                errors.append(f"pipelines.yaml: {name}/{stage.get('step')} owner is not a team member")
            if artifact and artifact_owner.get(str(artifact)) != owner:
                errors.append(f"pipelines.yaml: {name}/{stage.get('step')} artifact {artifact!r} writer mismatch")
        for script in pipeline.get("scripts", []):
            if not str(script).startswith("skills/") or not (root.parent / str(script)).is_file():
                errors.append(f"pipelines.yaml: {name} required script {script!r} does not exist")
    gate_names = set(gates.get("boundaries", {}) or {})
    if set(boundary_owners) != gate_names:
        errors.append("pipelines.yaml and gates.yaml boundary lists differ")
    for boundary, owners in boundary_owners.items():
        if len(owners) != 1:
            errors.append(f"pipelines.yaml: boundary {boundary!r} is owned by {owners}")
    if _names(save.get("generated_roots", [])) != {"skillset-saves", ".harness-state"}:
        errors.append("save-ownership.yaml: generated_roots must be exactly skillset-saves and .harness-state")
    phases = set(save.get("phase_directories", []) or [])
    for pipeline in pipelines:
        if pipeline not in phases:
            errors.append(f"save-ownership.yaml: missing phase directory {pipeline!r} for {pipeline}")

    skill_count = len(list(root.glob("**/SKILL.md")))
    if team.get("skill_count") != skill_count or len(members) != skill_count:
        errors.append(f"team-manifest.yaml: skill_count/members must match {skill_count} skill directories")
    mirrors = {
        root.parent / "AGENTS.md": (f"## The {skill_count} skills", f"**{skill_count} skills**", "| `taste` | `taste` | `taste-review` |"),
        root.parent / "README.md": (f"{skill_count} skills · {len(pipelines)} pipelines",),
        root.parent / "docs/architecture.md": ("Ten pipelines", "| `taste` | taste | `taste-review` |", "| `redesign` | redesign | `redesign-review` |"),
        root.parent / "docs/skills.md": (f"{skill_count} of them.", "## Taste (2)"),
        root.parent / "docs/gatekeepers.md": ("| `taste-review` |",),
        root.parent / "docs/directory-structure.md": (f"Gate spec: {len(gate_names)} boundaries", f"Pipeline map: {len(pipelines)} pipelines"),
    }
    for path, needles in mirrors.items():
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"documentation mirror unreadable: {path.name} ({exc})")
            continue
        for needle in needles:
            if needle not in text:
                errors.append(f"documentation mirror {path.name} is missing {needle!r}")
    return len(pipelines)


def check_agent_manifest(root: Path, errors: list[str]) -> int:
    path = root / "admiral" / "agent" / "agent-manifest.yaml"
    agent = _load(path, errors)
    delegates = agent.get("delegates_to", [])
    if not isinstance(delegates, list) or not delegates:
        errors.append("admiral/agent/agent-manifest.yaml: delegates_to must be a non-empty list")
        return 0
    for entry in delegates:
        if not isinstance(entry, dict):
            errors.append("admiral agent manifest: delegates_to row must be a mapping")
            continue
        skill_path = str(entry.get("skill_path", "")).strip()
        if not skill_path:
            errors.append(f"admiral agent manifest: {entry.get('name')!r} has no skill_path")
            continue
        if not (root / skill_path / "SKILL.md").is_file():
            errors.append(f"admiral agent manifest: skill_path {skill_path!r} has no SKILL.md")
    return len(delegates)


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    errors: list[str] = []
    team = _load(root / "team-manifest.yaml", errors)
    ownership = _load(root / "ownership.yaml", errors)
    gates = _load(root / "gates.yaml", errors)
    runtime = _load(root / "runtime-manifest.yaml", errors)
    package = _load(root / "package-manifest.yaml", errors)

    for name, data in (
        ("team-manifest.yaml", team), ("ownership.yaml", ownership),
        ("gates.yaml", gates), ("runtime-manifest.yaml", runtime),
        ("package-manifest.yaml", package),
    ):
        if data and data.get("schema_version") != 1:
            errors.append(f"{name}: schema_version must be 1")

    members = check_team(team, errors)
    artifact_ids = check_ownership(ownership, members, errors)
    check_gates(gates, set(ownership.get("owners", {}) or {}), errors)
    check_runtime(runtime, root, errors)
    check_package(package, errors)
    pipeline_count = check_pipeline_mirrors(root, team, ownership, gates, errors)
    delegate_count = check_agent_manifest(root, errors)

    return {
        "root": str(root),
        "team_member_count": len(members),
        "ownership_owner_count": len(ownership.get("owners", {}) or {}),
        "ownership_artifact_count": len(artifact_ids),
        "gate_boundary_count": len(gates.get("boundaries", {}) or {}),
        "pipeline_count": pipeline_count,
        "agent_delegate_count": delegate_count,
        "errors": sorted(set(errors)),
        "ok": not errors,
    }


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else SKILLS
    report = validate(root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    try:
        exit_code = main()
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        print(json.dumps({
            "errors": [f"manifest validation failed: {type(exc).__name__}: {exc}"],
            "ok": False,
        }, indent=2, sort_keys=True))
        exit_code = 1
    raise SystemExit(exit_code)
