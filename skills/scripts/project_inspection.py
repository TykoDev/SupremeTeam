"""Assemble the read-only project inspection that check_runtime reports."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from language_entrypoints import (
    PYTHON_WEB_MODULES,
    cargo_start_command,
    go_start_command,
    python_imports_module,
)
from project_files import (
    COMPOSE_NAMES,
    classify_path,
    collect_evidence,
    has_reparse_ancestor,
    is_sensitive,
    load_cached_data,
    read_cached_text,
    relative_path,
    walk_project,
)
from redaction import add_error, add_warning, redact
from scaffold_scan import find_scaffold_markers
from script_commands import makefile_recipe
from stack_detection import classify_project, detect_stacks, load_registry, read_package, validate_package_scripts


START_SCRIPT_ORDER = ("dev", "start")

SPRING_BOOT_RE = re.compile(r"(?i)spring[-.]?boot|org\.springframework\.boot")


def _start_commands(
    package: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    *,
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    packages: list[tuple[Path, dict[str, Any]]] | None = None,
) -> list[dict[str, str]]:
    package_records = packages if packages is not None else [(root / "package.json", package)]
    candidates: list[dict[str, str]] = []
    for package_path, package_value in package_records:
        scripts = package_value.get("scripts", {})
        if scripts is None:
            continue
        package_relative = relative_path(package_path, root)
        if not isinstance(scripts, dict):
            add_error(errors, f"{package_relative}: scripts must be an object")
            continue
        for name in START_SCRIPT_ORDER:
            if name not in scripts:
                continue
            command = scripts[name]
            if not isinstance(command, str):
                add_error(errors, f"{package_relative}:scripts.{name}: command must be a string")
                continue
            if command.strip():
                candidates.append(
                    {
                        "source": f"{package_relative}:scripts.{name}",
                        "path": package_relative,
                        "command": redact(command),
                    }
                )
    if candidates:
        return candidates

    root_files = {
        path.name.lower(): path
        for path in files
        if path.parent == root and not is_sensitive(path, root)
    }
    makefiles = sorted(
        path
        for path in files
        if (
            path.name.lower() == "makefile"
            and not is_sensitive(path, root)
            and classify_path(relative_path(path, root)) == "production"
        )
    )
    make_candidates: list[dict[str, str]] = []
    for makefile in makefiles:
        text = read_cached_text(makefile, root, errors, text_cache, required=True) or ""
        lines = text.splitlines()
        relative_makefile = relative_path(makefile, root)
        for target in ("dev", "run", "serve"):
            body = makefile_recipe(lines, target)
            if body:
                make_candidates.append(
                    {
                        "source": f"{relative_makefile}:{target}",
                        "path": relative_makefile,
                        "command": redact(body),
                    }
                )
                break
    if make_candidates:
        return make_candidates

    for compose_name in sorted(COMPOSE_NAMES):
        compose = root_files.get(compose_name)
        if not compose:
            continue
        compose_data = load_cached_data(compose, root, errors, warnings, text_cache)
        if compose_data is None:
            continue
        services = compose_data.get("services") if isinstance(compose_data, dict) else None
        if not isinstance(services, dict):
            continue
        compose_candidates: list[dict[str, str]] = []
        for service_name in sorted(services):
            service = services[service_name]
            if not isinstance(service, dict):
                continue
            command = service.get("command")
            if isinstance(command, list):
                command = " ".join(str(item) for item in command)
            if not isinstance(command, str) or not command.strip():
                command = f"docker compose -f {compose_name} up {service_name}"
            compose_candidates.append(
                {
                    "source": f"{compose_name}:services.{service_name}.command",
                    "path": compose_name,
                    "command": redact(command),
                }
            )
        if compose_candidates:
            return compose_candidates

    defaults: list[tuple[str, str, str]] = []
    if "manage.py" in root_files:
        defaults.append(("manage.py:default", "manage.py", "python manage.py runserver"))
    else:
        for filename in ("main.py", "app.py"):
            if filename not in root_files:
                continue
            text = read_cached_text(root_files[filename], root, errors, text_cache, required=True)
            if text and python_imports_module(text, PYTHON_WEB_MODULES):
                defaults.append((f"{filename}:default", filename, f"python {filename}"))
                break
    go_command = go_start_command(files, root, text_cache, errors) if "go.mod" in root_files else None
    if go_command:
        defaults.append(("go.mod:default", "go.mod", go_command))
    cargo_command = cargo_start_command(files, root, text_cache, errors)
    if cargo_command:
        defaults.append(("Cargo.toml:default", "Cargo.toml", cargo_command))
    # Both commands are Spring Boot's, so a Java manifest without Spring Boot
    # evidence gets no candidate rather than an invocation that cannot work.
    for filename, command in (
        ("pom.xml", "mvn spring-boot:run"),
        ("build.gradle", "./gradlew bootRun"),
        ("build.gradle.kts", "./gradlew bootRun"),
    ):
        if filename not in root_files:
            continue
        text = read_cached_text(root_files[filename], root, errors, text_cache, required=True)
        if text and SPRING_BOOT_RE.search(text):
            defaults.append((f"{filename}:default", filename, command))
    return [
        {"source": source, "path": path, "command": redact(command)}
        for source, path, command in defaults[:1]
    ]


def inspect_project(
    catalog_root: Path,
    project_root: Path,
    *,
    detect_project: bool,
    detect_start_command: bool,
    scan_scaffold: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        requested_root = project_root.expanduser().absolute()
        if has_reparse_ancestor(requested_root):
            add_error(errors, "project root: reparse points are not inspected")
            project_root = requested_root
        else:
            project_root = requested_root.resolve()
    except (OSError, ValueError) as exc:
        add_error(errors, f"project root cannot be inspected ({exc})")
        return {
            "root": str(project_root),
            "classification": None,
            "classification_evidence": [],
            "manifests": [],
            "configs": [],
            "stacks": [],
            "start_commands": [],
            "scaffold_markers": [],
            "ambiguities": [],
            "errors": sorted(set(errors)),
            "warnings": [],
            "ok": False,
        }
    inspection: dict[str, Any] = {
        "root": project_root.as_posix(),
        "classification": None,
        "classification_evidence": [],
        "manifests": [],
        "configs": [],
        "stacks": [],
        "start_commands": [],
        "scaffold_markers": [],
        "ambiguities": [],
        "errors": errors,
        "warnings": warnings,
        "ok": True,
    }
    if errors:
        pass
    elif not project_root.exists():
        add_error(errors, "project root does not exist")
    elif not project_root.is_dir():
        add_error(errors, "project root is not a directory")
    else:
        files = walk_project(project_root, errors, warnings)
        manifests, configs = collect_evidence(files, project_root)
        inspection["manifests"] = manifests
        inspection["configs"] = configs
        text_cache: dict[Path, str | None] = {}
        package: dict[str, Any] = {}
        package_records: list[tuple[Path, dict[str, Any]]] = []
        if detect_project or detect_start_command:
            package_paths = sorted(
                path
                for path in files
                if path.name.lower() == "package.json"
                and classify_path(relative_path(path, project_root)) == "production"
            )
            for path in package_paths:
                package_value = read_package(path, project_root, errors, text_cache)
                validate_package_scripts(package_value, errors)
                package_records.append((path, package_value))
                if path.parent == project_root:
                    package = package_value
        if detect_project:
            registry = load_registry(catalog_root, errors)
            stacks = detect_stacks(
                registry,
                files,
                project_root,
                package,
                text_cache,
                errors,
                packages=package_records or None,
            )
            classification, classification_evidence, ambiguities = classify_project(
                files,
                project_root,
                stacks,
                text_cache,
                errors,
                warnings,
                packages=package_records or None,
            )
            inspection["stacks"] = stacks
            inspection["classification"] = classification
            inspection["classification_evidence"] = classification_evidence
            inspection["ambiguities"] = ambiguities
        if detect_start_command:
            inspection["start_commands"] = _start_commands(
                package,
                errors,
                warnings,
                files=files,
                root=project_root,
                text_cache=text_cache,
                packages=package_records or None,
            )
        if scan_scaffold:
            inspection["scaffold_markers"] = find_scaffold_markers(files, project_root, errors)
        if (
            (detect_project or detect_start_command)
            and not errors
            and not (manifests or configs or inspection["stacks"] or inspection["start_commands"])
        ):
            add_warning(
                warnings,
                "no project evidence found: no manifests, configuration files or registered stacks "
                "under the inspected root; run from the project root or pass --project-root",
            )
    inspection["errors"] = sorted(set(errors))
    inspection["warnings"] = sorted(set(warnings))
    inspection["ok"] = not inspection["errors"]
    return inspection
