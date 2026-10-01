#!/usr/bin/env python3
"""Check the package runtime contract without installing or mutating anything."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

from data_formats import DataFormatError, load_data
from project_files import has_reparse_ancestor
from project_inspection import inspect_project
from redaction import add_error
from redaction import redact_value as _redact_value

# Private names this module exported before the inspector moved out; the test suites import them from here.
from redaction import redact as _redact  # noqa: F401
from stack_detection import load_registry as _load_registry  # noqa: F401


OPTIONAL_MODULES = {"PyYAML": "yaml"}


def _version(value: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError("invalid Python version")
    match = re.fullmatch(r"(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("invalid Python version")
    return int(match.group(1)), int(match.group(2))


def _runtime_error_report(
    errors: list[str],
    *,
    minimum: Any = "unknown",
    optional: list[dict[str, Any]] | None = None,
    launchers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "python": {
            "current": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "minimum": minimum,
            "status": "error",
        },
        "optional_dependencies": optional or [],
        "launchers": launchers or {},
        "ok": False,
        "errors": sorted(set(errors)),
    }


def _runtime_manifest_inputs(
    manifest: Any,
) -> tuple[Any, tuple[int, int] | None, list[dict[str, Any]], dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        add_error(errors, "runtime manifest root must be a mapping")
        return "unknown", None, [], {}, errors

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        add_error(errors, "runtime manifest runtime must be a mapping")
        return "unknown", None, [], {}, errors
    python = runtime.get("python")
    if not isinstance(python, dict):
        add_error(errors, "runtime manifest runtime.python must be a mapping")
        return "unknown", None, [], {}, errors

    minimum = python.get("minimum")
    try:
        minimum_version = _version(minimum)
    except ValueError:
        add_error(errors, "runtime manifest runtime.python.minimum must be major.minor")
        minimum = "unknown"
        minimum_version = None

    optional_value = python.get("optional_dependencies", [])
    optional: list[dict[str, Any]] = []
    if not isinstance(optional_value, list):
        add_error(errors, "runtime manifest optional_dependencies must be a list")
    else:
        for index, dependency in enumerate(optional_value):
            if not isinstance(dependency, dict):
                add_error(errors, f"runtime manifest optional dependency {index} must be a mapping")
                continue
            name = dependency.get("name")
            if not isinstance(name, str) or not name.strip():
                add_error(errors, f"runtime manifest optional dependency {index} requires a name")
                continue
            if "version" in dependency and not isinstance(dependency["version"], str):
                add_error(errors, f"runtime manifest optional dependency {index} version must be a string")
            if "fallback" in dependency and not isinstance(dependency["fallback"], str):
                add_error(errors, f"runtime manifest optional dependency {index} fallback must be a string")
            optional.append(dependency)

    launchers_value = manifest.get("launchers", {})
    launchers: dict[str, Any] = {}
    if not isinstance(launchers_value, dict):
        add_error(errors, "runtime manifest launchers must be a mapping")
    else:
        launchers = launchers_value
        for name, command in launchers.items():
            if not isinstance(name, str) or not isinstance(command, str):
                add_error(errors, "runtime manifest launcher names and commands must be strings")

    return minimum, minimum_version, optional, launchers, errors


def _probe_optional_dependencies(
    dependencies: list[dict[str, Any]],
    errors: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dependency in dependencies:
        name = str(dependency.get("name", ""))
        module = OPTIONAL_MODULES.get(name)
        if module is None:
            add_error(errors, f"unsupported optional dependency probe: {name}")
            available = False
        else:
            available = importlib.util.find_spec(module) is not None
        rows.append({"name": name, "version": dependency.get("version"), "available": available, "fallback": dependency.get("fallback")})
    return rows


def check(
    catalog_root: Path,
    *,
    project_root: Path | None = None,
    detect_project: bool = False,
    detect_start_command: bool = False,
    scan_scaffold: bool = False,
) -> dict:
    requested_root = catalog_root.expanduser().absolute()
    if has_reparse_ancestor(requested_root):
        errors: list[str] = []
        add_error(errors, "catalog root: reparse points are not inspected")
        return _redact_value(_runtime_error_report(errors))
    catalog_root = requested_root.resolve()
    manifest_path = catalog_root / "runtime-manifest.yaml"
    try:
        manifest = load_data(manifest_path)
    except (DataFormatError, UnicodeError, ValueError, RecursionError) as exc:
        errors: list[str] = []
        add_error(errors, str(exc))
        return _redact_value(_runtime_error_report(errors))
    minimum_value, minimum, optional_dependencies, launchers, manifest_errors = _runtime_manifest_inputs(manifest)
    errors = []
    optional = _probe_optional_dependencies(optional_dependencies, errors)
    if manifest_errors or minimum is None:
        return _redact_value(
            _runtime_error_report(
                manifest_errors + errors,
                minimum=minimum_value,
                optional=optional,
                launchers=launchers,
            )
        )
    current = (sys.version_info.major, sys.version_info.minor)
    python_ok = current >= minimum
    report = {
        "python": {"current": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "minimum": minimum_value, "status": "ok" if python_ok else "too_old"},
        "optional_dependencies": optional,
        "launchers": launchers,
        "ok": python_ok and not errors,
        "errors": sorted(set(errors + ([] if python_ok else [f"Python {sys.version_info.major}.{sys.version_info.minor} is below required {minimum_value}"]))),
    }
    if detect_project or detect_start_command or scan_scaffold:
        inspection = inspect_project(
            catalog_root,
            project_root if project_root is not None else Path("."),
            detect_project=detect_project,
            detect_start_command=detect_start_command,
            scan_scaffold=scan_scaffold,
        )
        report["project_inspection"] = inspection
        if inspection["errors"]:
            report["ok"] = False
            report["errors"] = sorted(
                set(report["errors"])
                | {f"project inspection: {error}" for error in inspection["errors"]}
            )
    return _redact_value(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalog-root",
        "--root",
        dest="catalog_root",
        default=str(Path(__file__).resolve().parents[1]),
        help="catalog directory holding runtime-manifest.yaml and tech-stacks/ "
        "(default: this script's skills/ directory); --root is the older spelling",
    )
    parser.add_argument(
        "--project-root",
        help="project directory to inspect read-only (default: the current directory)",
    )
    parser.add_argument("--detect-project", action="store_true", help="detect project evidence and registered stacks")
    parser.add_argument("--detect-start-command", action="store_true", help="record package start-command candidates without running them")
    parser.add_argument("--scan-scaffold", action="store_true", help="scan conservative scaffold markers without changing files")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-optional", action="store_true", help="fail when an optional dependency is unavailable")
    args = parser.parse_args()
    report = check(
        Path(args.catalog_root),
        project_root=Path(args.project_root) if args.project_root else None,
        detect_project=args.detect_project,
        detect_start_command=args.detect_start_command,
        scan_scaffold=args.scan_scaffold,
    )
    if args.require_optional and any(not item["available"] for item in report.get("optional_dependencies", [])):
        report["ok"] = False
        report["errors"].append("one or more optional dependencies are unavailable")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Supreme Team runtime contract")
        print(f"Python: {report.get('python', {}).get('status', 'error')} ({report.get('python', {}).get('current', 'unknown')})")
        for item in report.get("optional_dependencies", []):
            print(f"Optional {item['name']}: {'available' if item['available'] else 'missing; stdlib fallback documented'}")
        inspection = report.get("project_inspection")
        if isinstance(inspection, dict):
            print(f"Inspecting: {inspection.get('root')}")
            stacks = ", ".join(str(item.get("slug")) for item in inspection.get("stacks", [])) or "none"
            print(
                "Inspection: "
                f"{inspection.get('classification') or 'not classified'}; "
                f"stacks={stacks}; "
                f"start candidates={len(inspection.get('start_commands', []))}; "
                f"scaffold markers={len(inspection.get('scaffold_markers', []))}"
            )
            for candidate in inspection.get("start_commands", []):
                print(f"Candidate {candidate['source']}: {candidate['command']}")
            for error in inspection.get("errors", []):
                print(f"Inspection error: {error}")
            for warning in inspection.get("warnings", []):
                print(f"Inspection warning: {warning}")
            for ambiguity in inspection.get("ambiguities", []):
                print(f"Inspection note: {ambiguity}")
        print(f"Ready: {'yes' if report['ok'] else 'no'}")
        for error in report.get("errors", []):
            print(f"Error: {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
