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

Two groups of checks read files that sit beside ``skills/`` rather than inside
it: the CI workflow the runtime manifest declares, and the counts and tables the
documentation mirrors. An installed copy carries only ``skills/`` (Install.md), so
they run when the directory holding ``skills/`` looks like a repository checkout
and the report says ``repository_checks: false`` when they were skipped.

Output: a JSON report on stdout. Exit 0 when clean, 1 when a contract is
violated or unreadable.
"""
from __future__ import annotations

import argparse
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
    "runtime_check", "manifests", "hooks", "gates", "validation", "scripts", "taste",
    "installers", "skill_creator", "readiness", "hook_registration", "gate_check",
    "save_lifecycle", "package_check",
)
REQUIRED_CI_PLATFORMS = {"windows", "macos", "linux"}
# GitHub-hosted runner labels carry the platform as a prefix and a changing
# version after it, so the prefix is the part a manifest platform can name.
CI_RUNNER_PREFIX = {"windows": "windows-", "macos": "macos-", "linux": "ubuntu-"}
CI_PYYAML_VARIANTS = {"with", "without"}
# A command carrying one of these cannot run as written.
PLACEHOLDER_MARKS = ("<", "[")
REPOSITORY_MARKERS = ("README.md", "docs", ".github")
DOCUMENTATION_MIRRORS = (
    "AGENTS.md", "README.md", "docs/architecture.md", "docs/skills.md",
    "docs/gatekeepers.md", "docs/directory-structure.md",
)
NUMBER_WORDS = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen", "twenty",
)


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
    # check.py reads evidence_type_params by evidence key first and by record
    # type second, so an entry may be named either way; an entry that is neither
    # is a parameter nothing will ever load.
    type_names = set(map(str, (gates.get("evidence_types", {}) or {}).values()))
    for kind in (gates.get("evidence_type_params", {}) or {}):
        if kind not in type_names and kind not in declared:
            errors.append(f"gates.yaml: evidence_type_params for unknown record type or evidence key {kind!r}")
    policy = gates.get("revise_policy")
    if not isinstance(policy, dict) or policy.get("cycle_cap") != 2 or not all(
            str(policy.get(k, "")).strip() for k in ("self_check", "one_packet", "parallel_fix", "delta_review")):
        errors.append("gates.yaml: revise_policy must declare self_check, one_packet, parallel_fix, delta_review, and cycle_cap 2")


def _skills_path(root: Path, value: str) -> Path:
    """Resolve a path the manifests write as ``skills/...`` inside ``root``.

    Stripping the prefix keeps the check independent of what the directory is
    called and of what sits beside it.
    """
    return root / value.removeprefix("skills/")


def is_repository(root: Path) -> bool:
    """True when ``root`` sits in a repository checkout rather than an installed copy.

    The README, docs/ and .github/ that the repository-level checks read are
    never copied by an install, so a directory holding none of them is an
    installed copy. A checkout with one of them deleted still counts as a
    checkout, and the check that reads the missing file fails loudly.
    """
    return any((root.parent / name).exists() for name in REPOSITORY_MARKERS)


def _command_text(text: Any) -> str:
    """A command without its quoting or spacing, so a quoted glob still matches."""
    return " ".join(str(text).replace('"', "").replace("'", "").split())


def _platform_of(runner: str) -> str | None:
    for platform, prefix in CI_RUNNER_PREFIX.items():
        if runner.startswith(prefix):
            return platform
    return None


def _python_block(runtime: dict[str, Any]) -> dict[str, Any]:
    block = runtime.get("runtime")
    python = block.get("python") if isinstance(block, dict) else None
    return python if isinstance(python, dict) else {}


def _ci_platforms(runtime: dict[str, Any]) -> dict[str, str]:
    """Platform to launcher for every ci_matrix entry that names one."""
    matrix = runtime.get("ci_matrix")
    if not isinstance(matrix, list):
        return {}
    return {
        str(item.get("platform")): str(item["launcher"]) for item in matrix
        if isinstance(item, dict) and str(item.get("launcher", "")).strip()
    }


def check_runtime(runtime: dict[str, Any], root: Path, errors: list[str]) -> None:
    python = _python_block(runtime)
    minimum = str(python.get("minimum", ""))
    parts = minimum.split(".")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        errors.append("runtime-manifest.yaml: runtime.python.minimum must be major.minor")
    elif tuple(int(part) for part in parts) < (3, 9):
        errors.append("runtime-manifest.yaml: Python minimum may not fall below 3.9")
    elif minimum not in _names(python.get("supported", [])):
        errors.append("runtime-manifest.yaml: runtime.python.supported must include the minimum, or CI never runs the floor")
    if python.get("stdlib_only_for_hooks_and_gates") is not True:
        errors.append("runtime-manifest.yaml: hooks and gates must stay stdlib-only")
    for dependency in python.get("optional_dependencies", []) or []:
        if not isinstance(dependency, dict):
            errors.append("runtime-manifest.yaml: optional dependency must be a mapping")
            continue
        fallback = str(dependency.get("fallback", ""))
        if not fallback or not _skills_path(root, fallback).is_file():
            errors.append(f"runtime-manifest.yaml: {dependency.get('name')!r} fallback path is invalid")
    launchers = runtime.get("launchers", {})
    for name in REQUIRED_LAUNCHERS:
        if not isinstance(launchers, dict) or not str(launchers.get(name, "")).strip():
            errors.append(f"runtime-manifest.yaml: missing launcher {name}")
    commands = runtime.get("commands", {})
    for name in REQUIRED_COMMANDS:
        if not isinstance(commands, dict) or not str(commands.get(name, "")).strip():
            errors.append(f"runtime-manifest.yaml: missing command {name}")
    platforms = _ci_platforms(runtime)
    if set(platforms) != REQUIRED_CI_PLATFORMS:
        errors.append(f"runtime-manifest.yaml: CI platform matrix mismatch {sorted(platforms)}")
    elif isinstance(launchers, dict):
        shared = {"windows": "windows", "macos": "macos_linux", "linux": "macos_linux"}
        for platform, launcher in platforms.items():
            if launcher != str(launchers.get(shared[platform])):
                errors.append(
                    f"runtime-manifest.yaml: ci_matrix launcher for {platform} differs from launchers.{shared[platform]}")
    check_ci_declaration(runtime, errors)


def check_ci_declaration(runtime: dict[str, Any], errors: list[str]) -> None:
    """Every command is either run by CI or says why it is not."""
    ci = runtime.get("ci")
    if not isinstance(ci, dict):
        errors.append("runtime-manifest.yaml: ci must be a mapping naming the workflow and its commands")
        return
    workflow = str(ci.get("workflow", "")).strip()
    location = Path(workflow)
    if not workflow or location.is_absolute() or ".." in location.parts:
        errors.append("runtime-manifest.yaml: ci.workflow must be a relative path inside the repository")
    if _names(ci.get("pyyaml")) != CI_PYYAML_VARIANTS:
        errors.append("runtime-manifest.yaml: ci.pyyaml must name both with and without, so the stdlib fallback runs")
    elif not _pyyaml_install(runtime):
        errors.append("runtime-manifest.yaml: ci.pyyaml needs a PyYAML optional dependency with an install command")
    commands = runtime.get("commands")
    commands = commands if isinstance(commands, dict) else {}
    run = _names(ci.get("commands"))
    not_run = ci.get("not_run")
    not_run = not_run if isinstance(not_run, dict) else {}
    if not run:
        errors.append("runtime-manifest.yaml: ci.commands must list the commands CI runs")
    for name in sorted(run):
        command = str(commands.get(name, ""))
        if name not in commands:
            errors.append(f"runtime-manifest.yaml: ci.commands names {name!r}, which is not in commands")
        elif any(mark in command for mark in PLACEHOLDER_MARKS):
            errors.append(
                f"runtime-manifest.yaml: ci.commands names {name!r}, whose command holds a placeholder and cannot run as written")
    for name, reason in not_run.items():
        if name not in commands:
            errors.append(f"runtime-manifest.yaml: ci.not_run names {name!r}, which is not in commands")
        elif name in run:
            errors.append(f"runtime-manifest.yaml: {name!r} is both run by CI and listed under ci.not_run")
        if not str(reason).strip():
            errors.append(f"runtime-manifest.yaml: ci.not_run gives no reason for {name!r}")
    for name in commands:
        if name not in run and name not in not_run:
            errors.append(f"runtime-manifest.yaml: command {name!r} is neither run by CI nor explained under ci.not_run")


def _pyyaml_install(runtime: dict[str, Any]) -> str:
    for dependency in _python_block(runtime).get("optional_dependencies", []) or []:
        if isinstance(dependency, dict) and str(dependency.get("name", "")).lower() == "pyyaml":
            return str(dependency.get("install", "")).strip()
    return ""


def check_ci_workflow(runtime: dict[str, Any], repo_root: Path, errors: list[str]) -> None:
    """The workflow ``ci.workflow`` names exists and covers what the manifest declares.

    ``check_ci_declaration`` reports a bad declaration, so this returns quietly
    when there is nothing to compare against.
    """
    ci = runtime.get("ci")
    workflow = str(ci.get("workflow", "")).strip() if isinstance(ci, dict) else ""
    if not workflow:
        return
    path = repo_root / workflow
    if not path.is_file():
        errors.append(f"runtime-manifest.yaml: ci.workflow {workflow} does not exist, so no CI runs the declared matrix")
        return
    try:
        data = load_data(path)
    except (OSError, DataFormatError) as exc:
        errors.append(f"{workflow}: unreadable ({exc})")
        return
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, dict) or not jobs:
        errors.append(f"{workflow}: jobs must be a non-empty mapping")
        return
    triggers = data.get("on")
    named = _names(list(triggers) if isinstance(triggers, dict) else triggers)
    for event in ("push", "pull_request"):
        if event not in named:
            errors.append(f"{workflow}: the workflow never runs on {event}")
    gaps = {name: _job_gaps(job, runtime) for name, job in jobs.items()}
    best = min(gaps, key=lambda name: len(gaps[name]))
    errors.extend(f"{workflow}: job {best}: {gap}" for gap in gaps[best])


def _job_gaps(job: Any, runtime: dict[str, Any]) -> list[str]:
    """What one job leaves uncovered; a job that covers everything returns nothing.

    One job has to carry the whole matrix: platforms in one job and commands in
    another would pass a union check while no leg ran every command everywhere.
    """
    if not isinstance(job, dict):
        return ["is not a mapping"]
    ci = runtime["ci"]
    commands = runtime.get("commands") or {}
    gaps: list[str] = []
    strategy = job.get("strategy") if isinstance(job.get("strategy"), dict) else {}
    matrix = strategy.get("matrix") if isinstance(strategy.get("matrix"), dict) else {}
    if str(job.get("runs-on", "")).replace(" ", "") != "${{matrix.os}}":
        gaps.append("runs-on must be ${{ matrix.os }}")
    if matrix.get("exclude"):
        gaps.append("matrix excludes legs, which drops declared coverage")
    if job.get("continue-on-error"):
        gaps.append("continue-on-error lets the job fail without failing the workflow")
    if job.get("if"):
        gaps.append("a job-level if can skip the whole matrix")

    declared = _ci_platforms(runtime)
    runners = _names(matrix.get("os"))
    for platform in sorted(set(declared) - {_platform_of(runner) for runner in runners}):
        gaps.append(f"no matrix.os runner for {platform}")
    for runner in sorted(runner for runner in runners if _platform_of(runner) is None):
        gaps.append(f"matrix.os runner {runner!r} maps to no declared platform")
    launchers: dict[str | None, str] = {}
    for entry in matrix.get("include") or []:
        if isinstance(entry, dict) and "os" in entry and "launcher" in entry:
            launchers.setdefault(_platform_of(str(entry["os"])), str(entry["launcher"]))
    for platform, launcher in sorted(declared.items()):
        if launchers.get(platform) != launcher:
            gaps.append(f"launcher for {platform} is {launchers.get(platform)!r}; the manifest declares {launcher!r}")

    supported = _names(_python_block(runtime).get("supported", []))
    if _names(matrix.get("python")) != supported:
        gaps.append(f"matrix.python is {sorted(_names(matrix.get('python')))}; the manifest supports {sorted(supported)}")
    if _names(matrix.get("pyyaml")) != _names(ci.get("pyyaml")):
        gaps.append(
            f"matrix.pyyaml is {sorted(_names(matrix.get('pyyaml')))}; the manifest declares {sorted(_names(ci.get('pyyaml')))}")

    steps = [step for step in job.get("steps") or [] if isinstance(step, dict)]
    runs = {_command_text(step["run"]): step for step in steps if "run" in step}
    install = _command_text(_pyyaml_install(runtime))
    if install and "matrix.pyyaml" not in str(runs.get(install, {}).get("if", "")):
        gaps.append(f"no step runs {install!r} only for the matrix.pyyaml legs that ask for it")
    if not any(str(step.get("run", "")).startswith("${{ matrix.launcher }}") for step in steps):
        gaps.append("no step runs the declared launcher (${{ matrix.launcher }})")
    for name in sorted(_names(ci.get("commands"))):
        step = runs.get(_command_text(commands.get(name, "")))
        if step is None:
            gaps.append(f"no step runs {name}: {commands.get(name)}")
        elif step.get("if") or step.get("continue-on-error"):
            gaps.append(f"{name} runs conditionally or may fail without failing the job")
    return gaps


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
            if not str(script).startswith("skills/") or not _skills_path(root, str(script)).is_file():
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
    if is_repository(root):
        texts: dict[str, str] = {}
        for name in DOCUMENTATION_MIRRORS:
            try:
                texts[name] = (root.parent / name).read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(f"documentation mirror unreadable: {name} ({exc})")
        taste_skills = len(list((root / "taste").glob("**/SKILL.md")))
        errors.extend(documentation_gaps(texts, skill_count, taste_skills, pipelines, gate_names))
    return len(pipelines)


def _table_rows(text: str) -> list[list[str]]:
    """The cells of every Markdown table row, without padding or backticks."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            rows.append([cell.strip().strip("`").strip() for cell in line[1:-1].split("|")])
    return rows


def documentation_gaps(texts: dict[str, str], skill_count: int, taste_skills: int,
                       pipelines: dict[str, Any], boundaries: set[str]) -> list[str]:
    """What the documentation mirrors say that the specs do not.

    Counts come from the specs and the tree. The pipeline and boundary tables are
    read as tables, one row per pipeline and per boundary, so re-wrapping a row,
    spelling a number out or adding a pipeline never needs an edit here. A
    document absent from ``texts`` was already reported as unreadable.
    """
    gaps: list[str] = []

    def missing(name: str, needle: str) -> None:
        if name in texts and needle not in texts[name]:
            gaps.append(f"documentation mirror {name} is missing {needle!r}")

    def count_missing(name: str, count: int, noun: str) -> None:
        spelled = [f"{count} {noun}"] + ([f"{NUMBER_WORDS[count]} {noun}"] if count < len(NUMBER_WORDS) else [])
        if name in texts and not any(form in texts[name].lower() for form in spelled):
            gaps.append(f"documentation mirror {name} states no count of {noun}; expected {spelled[0]!r}")

    def rows_missing(name: str, rows: list[list[str]]) -> None:
        if name not in texts:
            return
        table = _table_rows(texts[name])
        for row in rows:
            if not any(cells[:len(row)] == row for cells in table):
                gaps.append(f"documentation mirror {name} has no table row starting {' | '.join(row)!r}")

    pipeline_rows = [[name, str(data.get("owner")), str(data.get("boundary"))] for name, data in pipelines.items()]
    missing("AGENTS.md", f"## The {skill_count} skills")
    missing("AGENTS.md", f"**{skill_count} skills**")
    rows_missing("AGENTS.md", pipeline_rows)
    missing("README.md", f"{skill_count} skills · {len(pipelines)} pipelines")
    count_missing("docs/architecture.md", len(pipelines), "pipelines")
    rows_missing("docs/architecture.md", pipeline_rows)
    missing("docs/skills.md", f"{skill_count} of them.")
    missing("docs/skills.md", f"## Taste ({taste_skills})")
    rows_missing("docs/gatekeepers.md", [[boundary] for boundary in sorted(boundaries)])
    missing("docs/directory-structure.md", f"Gate spec: {len(boundaries)} boundaries")
    missing("docs/directory-structure.md", f"Pipeline map: {len(pipelines)} pipelines")
    return gaps


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
    repository = is_repository(root)
    if repository:
        check_ci_workflow(runtime, root.parent, errors)

    return {
        "repository_checks": repository,
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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("skills_dir", nargs="?", type=Path, default=SKILLS, metavar="SKILLS_DIR",
                        help="the skills/ directory to validate, not the repository root "
                             "(default: the skills/ directory this script sits in)")
    root = parser.parse_args().skills_dir
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
