#!/usr/bin/env python3
"""Validate the Supreme Team orchestration manifests and their cross-references.

Checks five contracts and the agreements between them:

  team-manifest.yaml     roster shape; every named role exists exactly once
  ownership.yaml         one writer per artifact; every owner is a team member
  gates.yaml             every boundary submitter is an ownership owner
  runtime-manifest.yaml  runtime floor, launchers, commands, CI matrix
  package-manifest.yaml  include/exclude and the delivery contract

It also confirms that every skill path named in an agent manifest's
``delegates_to`` list resolves to a SKILL.md on disk.

Two groups of checks read files that sit beside ``skills/`` rather than inside
it: the CI workflow the runtime manifest declares, and the counts and tables the
documentation mirrors. An installed copy carries only ``skills/`` (Install.md), so
they run when the directory holding ``skills/`` looks like a repository checkout
and the report says ``repository_checks: false`` when they were skipped.

An installed copy may hold only the teams chosen at install time (``--team``).
The installers record what they put there in ``.supremeteam-manifest``, one
``item <name>`` line per top-level entry, and an installed copy is checked against
that record. Only the recorded items are read, so the user's own skills beside them
do not count. The record names items, not the skills inside them, so each roster
skill is placed: at the skill_path an agent manifest in a recorded item gives it,
else at its ``UNDELEGATED_SKILLS`` path, else at the top level under its own name.
A skill placed in a recorded item that has no SKILL.md there is an error; one placed
in an item the record leaves out is listed under ``not_installed``. A checkout is
always checked in full, and so is an installed copy whose record is missing (a hand
copy) or cannot be read; ``install_record`` in the report says which applied.

Checked in full, every skill must sit where that placement would put it in any
install that holds its item: a skill nested in an item is named at its path by an
agent manifest in the same item or in admiral's, which every install holds, or is
listed in ``UNDELEGATED_SKILLS``. So a skill no recorded manifest names is either at
the top level or inside an item the install does not hold, and the top-level place
decides the same way for both.

Output: a JSON report on stdout. Exit 0 when clean, 1 when a contract is
violated or unreadable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SKILLS = Path(__file__).resolve().parents[1]
if str(SKILLS / "scripts") not in sys.path:
    sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import DataFormatError, load_data  # noqa: E402
from contract_floor import gate_floor_errors  # noqa: E402

TEAM_ROLE_KEYS = ("front_door", "session_memory", "cross_stage_gatekeeper")
TEAM_LIST_KEYS = (
    "phase_leads", "phase_gatekeepers", "pipeline_owners", "specialists", "standalone_tools",
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
# The record install.sh and install.ps1 write into every install root, and the item
# names they accept: one path component that starts with neither a dot nor a dash.
INSTALL_RECORD = ".supremeteam-manifest"
INSTALL_RECORD_HEADER = "supremeteam-manifest 1"
INSTALL_ITEM_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")
# The front door's agent manifest. admiral is installed with every team, so the
# skills it delegates to are placed in any install.
FRONT_DOOR_MANIFEST = "admiral/agent/agent-manifest.yaml"
# A skill nested in an item that no agent manifest delegates to, and its path. Every
# other skill is placed by the manifests or sits at the top level under its own
# name; check_skill_places holds a catalog checked in full to that.
UNDELEGATED_SKILLS = {"taste-review": "taste/taste-review"}
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
    errors.extend(gate_floor_errors(gates))
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
    if not isinstance(policy, dict) or policy.get("cycle_cap") != 3 or not all(
            str(policy.get(k, "")).strip() for k in ("self_check", "one_packet", "parallel_fix", "delta_review")):
        errors.append("gates.yaml: revise_policy must declare self_check, one_packet, parallel_fix, delta_review, and cycle_cap 3")


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


def install_record(root: Path) -> tuple[set[str] | None, str]:
    """The top-level items the installer recorded in ``root``, and what was read.

    None means check every skill: there is no record, as a hand copy leaves it, or
    the record cannot be read, which is no reason to check less. The second value
    says which, for the report.
    """
    path = root / INSTALL_RECORD
    if not path.exists() and not path.is_symlink():
        return None, "no install record: every skill is checked"
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("not a regular file")
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        return None, f"install record unreadable ({exc}): every skill is checked"
    if not lines or lines[0] != INSTALL_RECORD_HEADER:
        return None, f"install record unreadable (no {INSTALL_RECORD_HEADER!r} header): every skill is checked"
    names = (line.removeprefix("item ").strip() for line in lines if line.startswith("item "))
    items = {name for name in names if INSTALL_ITEM_RE.fullmatch(name)}
    if not items:
        return None, "install record unreadable (it lists no items): every skill is checked"
    teams = next((line.removeprefix("teams ").split() for line in lines if line.startswith("teams ")), [])
    return items, f"install record: teams {' '.join(teams) or 'not named'}; the recorded items are checked"


def skill_directories(root: Path, installed: set[str] | None) -> list[str]:
    """The directory name of every SKILL.md in the catalog, or in the recorded items only."""
    if installed is None:
        return [path.parent.name for path in root.glob("**/SKILL.md")]
    return [path.parent.name for item in sorted(installed) for path in (root / item).glob("**/SKILL.md")]


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
    # Absolute in any host spelling: a leading separator or a drive prefix. Path.is_absolute alone says False for
    # a POSIX-style "/etc/ci.yml" on Windows, where the path still names outside the repository.
    spelled_absolute = workflow.startswith(("/", "\\")) or workflow[1:2] == ":"
    if not workflow or spelled_absolute or location.is_absolute() or ".." in location.parts:
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


def stage_dependencies(pipeline: dict[str, Any], stage: dict[str, Any]) -> dict[str, Any]:
    graph = pipeline.get("dependency_graph", {})
    step = stage.get("step")
    contract = graph.get(step, stage) if isinstance(graph, dict) and isinstance(step, str) else stage
    return contract if isinstance(contract, dict) else {}


def pipeline_dependency_errors(name: str, pipeline: dict[str, Any]) -> list[str]:
    """Validate dependency shapes, total stage coverage and approval ordering."""
    errors: list[str] = []

    def names(value: object, label: str) -> set[str]:
        if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
            errors.append(f"pipelines.yaml: {name}/{label} must be a list of non-blank strings")
            return set()
        if len(value) != len(set(value)):
            errors.append(f"pipelines.yaml: {name}/{label} contains duplicate dependencies")
        return set(value)

    produced = names(pipeline.get("external_inputs"), "external_inputs")
    if "approved-boundary" in produced:
        errors.append(f"pipelines.yaml: {name} approval cannot be an external intake input")
        produced.discard("approved-boundary")
    graph = pipeline.get("dependency_graph", {})
    if not isinstance(graph, dict):
        errors.append(f"pipelines.yaml: {name}/dependency_graph must be a mapping")
        graph = {}
    stage_ids = [stage.get("step") for stage in pipeline.get("stages", []) if isinstance(stage, dict)]
    if any(not isinstance(step, str) or not step.strip() for step in stage_ids):
        errors.append(f"pipelines.yaml: {name} step ids must be non-blank strings")
    steps = {step for step in stage_ids if isinstance(step, str)}
    if len(stage_ids) != len(steps):
        errors.append(f"pipelines.yaml: {name} stage step ids must be unique")
    if graph and set(graph) != steps:
        errors.append(f"pipelines.yaml: {name}/dependency_graph must cover exactly every stage")
    after_boundary = False
    for stage in pipeline.get("stages", []):
        step = stage.get("step")
        fan_out = stage.get("fan_out", 1)
        if not isinstance(fan_out, int) or isinstance(fan_out, bool) or fan_out < 1:
            errors.append(f"pipelines.yaml: {name}/{step}.fan_out must be a positive integer")
        contract = stage_dependencies(pipeline, stage)
        if step in graph and any(field in stage for field in ("requires", "produces")):
            errors.append(f"pipelines.yaml: {name}/{step} has duplicate dependency declarations")
        requires = names(contract.get("requires"), f"{step}.requires")
        creates = names(contract.get("produces"), f"{step}.produces")
        marked = stage.get("after_boundary", False)
        if not isinstance(marked, bool):
            errors.append(f"pipelines.yaml: {name}/{step}.after_boundary must be boolean")
        if marked is True:
            after_boundary = True
            produced.add("approved-boundary")
            if "approved-boundary" not in requires:
                errors.append(f"pipelines.yaml: {name}/{step} must require approved-boundary")
        elif after_boundary:
            errors.append(f"pipelines.yaml: {name}/{step} cannot move back before the boundary")
        if ((name == "release" and step in {"land-and-deploy", "document"}) or
                (name == "investigation" and step == "return-to-owning-phase")) and marked is not True:
            errors.append(f"pipelines.yaml: {name}/{step} must be after_boundary")
        if "approved-boundary" in creates:
            errors.append(f"pipelines.yaml: {name}/{step} cannot produce gate approval")
            creates.discard("approved-boundary")
        unavailable = sorted(requires - produced)
        if unavailable:
            errors.append(
                f"pipelines.yaml: {name}/{stage.get('step')} requires unavailable inputs "
                f"{unavailable}; declare them in external_inputs or produce them in an earlier stage")
        repeated = sorted(creates & produced)
        if repeated:
            errors.append(
                f"pipelines.yaml: {name}/{stage.get('step')} produces inputs already available {repeated}")
        produced.update(creates)
    return errors


def review_execution_errors(spec: dict) -> list[str]:
    """Review specialists produce evidence at declared stages, never every gate."""
    specialists = {"bug-review", "code-review", "quality-review", "security-review", "mr-robot",
                   "frontier", "design-qa", "devex-review", "taste-review", "skill-reviewer"}
    policy = spec.get("review_execution")
    if not isinstance(policy, dict) or policy.get("mode") != "one-gate-per-review":
        return ["pipelines.yaml: review_execution must declare one-gate-per-review"]
    expected = {name: set() for name in specialists}
    for pipeline in spec.get("pipelines", {}).values():
        for stage in pipeline.get("stages", []):
            if stage.get("owner") in specialists:
                expected[stage["owner"]].add(pipeline.get("boundary"))
    declared = policy.get("specialists")
    if (not isinstance(declared, dict) or set(declared) != specialists
            or any(not isinstance(value, list) or set(value) != expected[name]
                   for name, value in declared.items())):
        return ["pipelines.yaml: review_execution specialists must match their producing stages and boundaries"]
    if not all(isinstance(policy.get(key), str) and policy[key].strip() for key in ("reuse", "followup")):
        return ["pipelines.yaml: review_execution must declare reuse and followup discipline"]
    return []


def check_pipeline_mirrors(root: Path, team: dict[str, Any], ownership: dict[str, Any],
                           gates: dict[str, Any], errors: list[str], installed: set[str] | None = None) -> int:
    pipeline_spec = _load(root / "pipelines.yaml", errors)
    pipelines = pipeline_spec.get("pipelines", {})
    save = _load(root / "save-ownership.yaml", errors)
    if not isinstance(pipelines, dict) or not pipelines:
        errors.append("pipelines.yaml: pipelines must be a non-empty mapping")
        return 0
    errors.extend(review_execution_errors(pipeline_spec))
    members = team_members(team)
    artifact_owner = {str(x.get("id")): str(x.get("owner")) for x in ownership.get("artifacts", [])
                      if isinstance(x, dict)}
    boundary_owners: dict[str, list[str]] = {}
    for name, pipeline in pipelines.items():
        if pipeline.get("owner") not in members:
            errors.append(f"pipelines.yaml: {name} owner is not a team member")
        boundary = str(pipeline.get("boundary", ""))
        boundary_owners.setdefault(boundary, []).append(name)
        errors.extend(pipeline_dependency_errors(name, pipeline))
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

    skill_count = len(skill_directories(root, None))
    if installed is None:
        if team.get("skill_count") != skill_count or len(members) != skill_count:
            errors.append(f"team-manifest.yaml: skill_count/members must match {skill_count} skill directories")
    else:
        # An install of chosen teams holds part of the roster, so the count on disk is
        # not the roster's: the roster has to agree with itself, and every installed
        # skill has to be on it.
        if team.get("skill_count") != len(members):
            errors.append(f"team-manifest.yaml: skill_count must match its {len(members)} distinct members")
        unlisted = sorted(set(skill_directories(root, installed)) - members)
        if unlisted:
            errors.append(f"team-manifest.yaml: installed skills {unlisted} are not in the roster")
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

    def opening_missing(name: str, needle: str) -> None:
        """The needle has to open a line: a page that quotes it to explain the check would satisfy a substring."""
        if name in texts and not any(line.startswith(needle) for line in texts[name].splitlines()):
            gaps.append(f"documentation mirror {name} has no line starting {needle!r}")

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
    opening_missing("docs/skills.md", f"{skill_count} of them.")
    opening_missing("docs/skills.md", f"## Taste ({taste_skills})")
    rows_missing("docs/gatekeepers.md", [[boundary] for boundary in sorted(boundaries)])
    missing("docs/directory-structure.md", f"Gate spec: {len(boundaries)} boundaries")
    missing("docs/directory-structure.md", f"Pipeline map: {len(pipelines)} pipelines")
    return gaps


def agent_manifests(root: Path, installed: set[str] | None) -> list[Path]:
    """The front door's agent manifest, then every other one in the catalog or in the recorded items."""
    front = root / FRONT_DOOR_MANIFEST
    if installed is None:
        found = root.glob("**/agent/agent-manifest.yaml")
    else:
        found = (path for item in sorted(installed) for path in (root / item).glob("**/agent/agent-manifest.yaml"))
    return [front, *sorted(path for path in found if path != front)]


def check_agent_manifests(root: Path, errors: list[str],
                          installed: set[str] | None = None) -> tuple[int, dict[str, set[tuple[str, str]]]]:
    """Every delegate's skill_path holds a SKILL.md, unless the install record leaves its item out.

    The front door's manifest must delegate; every other agent manifest is read the
    same way. Returns the front door's delegate count, and where the manifests place
    each skill: by skill name, every (skill_path, item of the manifest that names it).
    """
    places: dict[str, set[tuple[str, str]]] = {}
    front_count = 0
    for path in agent_manifests(root, installed):
        relative = path.relative_to(root).as_posix()
        owner = path.parent.parent.name
        delegates = _load(path, errors).get("delegates_to", [])
        if relative == FRONT_DOOR_MANIFEST:
            if not isinstance(delegates, list) or not delegates:
                errors.append(f"{relative}: delegates_to must be a non-empty list")
                continue
            front_count = len(delegates)
        elif not isinstance(delegates, list):
            errors.append(f"{relative}: delegates_to must be a list")
            continue
        for entry in delegates:
            if not isinstance(entry, dict):
                errors.append(f"{owner} agent manifest: delegates_to row must be a mapping")
                continue
            skill_path = str(entry.get("skill_path", "")).strip()
            if not skill_path:
                errors.append(f"{owner} agent manifest: {entry.get('name')!r} has no skill_path")
                continue
            places.setdefault(skill_path.rsplit("/", 1)[-1], set()).add((skill_path, relative.split("/", 1)[0]))
            if installed is not None and skill_path.split("/", 1)[0] not in installed:
                continue
            if not (root / skill_path / "SKILL.md").is_file():
                errors.append(f"{owner} agent manifest: skill_path {skill_path!r} has no SKILL.md")
    return front_count, places


def check_skill_places(root: Path, members: set[str], places: dict[str, set[tuple[str, str]]],
                       errors: list[str]) -> None:
    """Every skill sits where an install that holds its item would place it.

    An install reads only the agent manifests in the items it holds, so a skill
    nested in an item must be named at its path by a manifest in that item or in the
    front door's, or be listed in UNDELEGATED_SKILLS. Otherwise an install that lost
    it could not tell it missing from left out.
    """
    front = FRONT_DOOR_MANIFEST.split("/", 1)[0]
    for name, path in UNDELEGATED_SKILLS.items():
        if not (root / path / "SKILL.md").is_file():
            errors.append(f"UNDELEGATED_SKILLS places {name} at {path}, which has no SKILL.md")
    for skill in sorted(root.glob("**/SKILL.md")):
        path = skill.parent.relative_to(root).as_posix()
        name, item = skill.parent.name, path.split("/", 1)[0]
        if name not in members or path == name or UNDELEGATED_SKILLS.get(name) == path:
            continue
        if not any(place == path and owner in (item, front) for place, owner in places.get(name, ())):
            errors.append(f"{path}/SKILL.md: no agent manifest in {item}/ or {front}/ delegates to it there, "
                          "so an install could not tell it missing from left out")


def left_out_skills(root: Path, members: set[str], places: dict[str, set[tuple[str, str]]],
                    installed: set[str], errors: list[str]) -> list[str]:
    """The roster skills placed in an item the install record leaves out.

    A skill with no SKILL.md in the recorded items is placed at the skill_paths the
    recorded agent manifests give it, else at its UNDELEGATED_SKILLS path, else at
    the top level under its own name. A place inside a recorded item is an error:
    check_agent_manifests reports a skill_path, and this the places no manifest gives.
    """
    left_out = []
    for name in sorted(members - set(skill_directories(root, installed))):
        named = {place for place, _ in places.get(name, ())}
        held = [place for place in sorted(named or {UNDELEGATED_SKILLS.get(name, name)})
                if place.split("/", 1)[0] in installed]
        if not held:
            left_out.append(name)
        elif not named:
            errors.append(f"{INSTALL_RECORD}: {held[0].split('/', 1)[0]!r} is installed but has no {held[0]}/SKILL.md")
    return left_out


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

    repository = is_repository(root)
    if repository:
        installed, record = None, "not read: a repository checkout is checked in full"
    else:
        installed, record = install_record(root)

    members = check_team(team, errors)
    artifact_ids = check_ownership(ownership, members, errors)
    check_gates(gates, set(ownership.get("owners", {}) or {}), errors)
    check_runtime(runtime, root, errors)
    check_package(package, errors)
    pipeline_count = check_pipeline_mirrors(root, team, ownership, gates, errors, installed)
    delegate_count, places = check_agent_manifests(root, errors, installed)
    if installed is None:
        check_skill_places(root, members, places, errors)
        not_installed: list[str] = []
    else:
        not_installed = left_out_skills(root, members, places, installed, errors)
    if repository:
        check_ci_workflow(runtime, root.parent, errors)

    return {
        "install_record": record,
        "not_installed": not_installed,
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
