"""Match a project against the tech-stack registry and classify it as frontend, backend or both."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from data_formats import DataFormatError, content_sha256, parse_yaml
from language_entrypoints import (
    PYTHON_FASTAPI_MODULES,
    PYTHON_WEB_MODULES,
    cargo_binary_entry,
    go_entrypoint,
    python_imports_module,
)
from project_files import (
    COMPOSE_NAMES,
    classify_path,
    is_sensitive,
    load_cached_data,
    read_cached_text,
    read_text,
    relative_path,
    safe_regular_file,
)
from redaction import add_error
from script_commands import (
    makefile_runtime_signals,
    script_uses_command,
    script_uses_node_server,
    script_uses_python_module,
    script_uses_subcommand,
)


REGISTRY_ROW_KEYS = frozenset({"slug", "path", "framework", "versions", "source", "sha256"})
REGISTRY_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REGISTRY_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

FRONTEND_STACKS = frozenset(
    {
        "angular",
        "astro",
        "react-nextjs",
        "react-tanstack",
        "svelte-sveltekit",
        "vite-spa",
        "vue-nuxt",
    }
)
BACKEND_PACKAGE_NAMES = frozenset(
    {
        "@nestjs/core",
        "express",
        "fastify",
        "hapi",
        "koa",
        "restify",
    }
)
FRONTEND_PACKAGE_NAMES = frozenset(
    {
        "@angular/core",
        "react",
        "solid-js",
        "svelte",
        "vue",
    }
)
FRONTEND_TOOL_PACKAGE_NAMES = frozenset({"parcel", "vite", "webpack"})
TANSTACK_START_PACKAGES = frozenset({"@tanstack/react-start", "@tanstack/start"})
SSR_PACKAGE_NAMES = frozenset(
    {
        "@remix-run/node",
        "@remix-run/react",
        "@sveltejs/kit",
        "astro",
        "next",
        "nuxt",
        "remix",
    }
)


def read_package(
    path: Path,
    root: Path,
    errors: list[str],
    cache: dict[Path, str | None],
) -> dict[str, Any]:
    text = read_cached_text(path, root, errors, cache, required=True)
    if text is None:
        return {}
    try:
        value = json.loads(text)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, json.JSONDecodeError):
            detail = f"invalid JSON at line {exc.lineno}"
        else:
            detail = f"invalid JSON ({exc})"
        add_error(errors, f"{relative_path(path, root)}: {detail}")
        return {}
    if not isinstance(value, dict):
        add_error(errors, f"{relative_path(path, root)}: package manifest must be a JSON object")
        return {}
    return value


def load_registry(catalog_root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    path = catalog_root / "tech-stacks" / "registry.yaml"
    if path.exists() and not safe_regular_file(path, catalog_root):
        add_error(errors, "tech-stacks/registry.yaml: must be a regular file")
        return {}
    if not path.exists():
        return {}
    text = read_text(path, catalog_root, errors, required=True)
    if text is None:
        return {}
    try:
        value = parse_yaml(text)
    except (DataFormatError, UnicodeError, ValueError, RecursionError) as exc:
        add_error(errors, f"tech-stacks/registry.yaml: {exc}")
        return {}
    if not isinstance(value, dict):
        add_error(errors, "tech-stacks/registry.yaml: root must be a mapping")
        return {}
    registry_valid = True
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        add_error(errors, "tech-stacks/registry.yaml: schema_version must be 1")
        registry_valid = False
    if value.get("kind") != "supremeteam-tech-stack-registry":
        add_error(errors, "tech-stacks/registry.yaml: kind is invalid")
        registry_valid = False
    if not isinstance(value.get("overlays"), list):
        add_error(errors, "tech-stacks/registry.yaml: overlays must be a list")
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value["overlays"]):
        if not isinstance(item, dict):
            add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} must be a mapping")
            continue
        missing = sorted(REGISTRY_ROW_KEYS - set(item))
        extra = sorted(set(item) - REGISTRY_ROW_KEYS)
        if missing:
            add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} missing fields {missing}")
        if extra:
            add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} has unexpected fields {extra}")
        slug = item.get("slug")
        if not isinstance(slug, str) or not REGISTRY_SLUG_RE.fullmatch(slug):
            add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} has an invalid slug")
            continue
        if slug in rows:
            add_error(errors, f"tech-stacks/registry.yaml: duplicate slug {slug!r}")
            continue

        row_valid = not missing and not extra
        expected_path = f"tech-stacks/{slug}.md"
        expected_source = f"_refs/global/tech-stacks/{slug}.md"
        if item.get("path") != expected_path:
            add_error(errors, f"tech-stacks/registry.yaml: {slug} path must be {expected_path}")
            row_valid = False
        if not isinstance(item.get("framework"), str) or not item["framework"].strip():
            add_error(errors, f"tech-stacks/registry.yaml: {slug} framework must be a string")
            row_valid = False
        versions = item.get("versions")
        if (
            not isinstance(versions, list)
            or not versions
            or any(
                not isinstance(version, (int, float))
                or isinstance(version, bool)
                or (isinstance(version, float) and not math.isfinite(version))
                for version in versions
            )
        ):
            add_error(errors, f"tech-stacks/registry.yaml: {slug} versions must be a non-empty finite number list")
            row_valid = False
        if item.get("source") != expected_source:
            add_error(errors, f"tech-stacks/registry.yaml: {slug} source must be {expected_source}")
            row_valid = False
        digest = item.get("sha256")
        if not isinstance(digest, str) or not REGISTRY_DIGEST_RE.fullmatch(digest):
            add_error(errors, f"tech-stacks/registry.yaml: {slug} sha256 must be a lowercase SHA-256 digest")
            row_valid = False

        overlay = catalog_root / expected_path
        source = catalog_root.parent / expected_source
        if not safe_regular_file(overlay, catalog_root):
            add_error(errors, f"tech-stacks/registry.yaml: {slug} overlay file is missing or not regular")
            row_valid = False
        elif isinstance(digest, str) and REGISTRY_DIGEST_RE.fullmatch(digest):
            try:
                # Registry digests are line-ending agnostic (LF-folded text), the
                # same fold harness/gatekeeper/check.py applies to stack_lock.
                actual_digest = content_sha256(overlay)
            except OSError as exc:
                add_error(errors, f"tech-stacks/registry.yaml: {slug} overlay cannot be read ({exc})")
                row_valid = False
            else:
                if actual_digest != digest:
                    # "digest" ends the message on purpose: followed by more words the
                    # redactor reads it as an HTTP auth scheme and scrubs the rest.
                    add_error(errors, f"tech-stacks/registry.yaml: {slug} overlay does not match its pinned digest")
                    row_valid = False
        # The `source` column records provenance in the `_refs` authoring
        # workspace, which is not shipped with the catalog. Enforce it only
        # when that workspace is present; the shipped overlay plus its pinned
        # sha256 above remain the authority either way.
        source_workspace = catalog_root.parent / "_refs" / "global" / "tech-stacks"
        if source_workspace.is_dir() and not safe_regular_file(source, catalog_root.parent):
            add_error(errors, f"tech-stacks/registry.yaml: {slug} source file is missing or not regular")
            row_valid = False
        if row_valid:
            rows[slug] = item
    if not registry_valid:
        return {}
    return rows


def _package_dependencies(package: dict[str, Any]) -> set[str]:
    dependencies: set[str] = set()
    for field in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        value = package.get(field)
        if isinstance(value, dict):
            dependencies.update(str(name).lower() for name in value)
    return dependencies


def _package_scripts(package: dict[str, Any]) -> dict[str, str]:
    scripts = package.get("scripts", {})
    if not isinstance(scripts, dict):
        return {}
    return {str(name): value for name, value in scripts.items() if isinstance(value, str) and value.strip()}


def _package_classification_signals(package: dict[str, Any]) -> tuple[bool, bool]:
    dependencies = _package_dependencies(package)
    scripts = _package_scripts(package)
    frontend = bool(dependencies & (FRONTEND_PACKAGE_NAMES | FRONTEND_TOOL_PACKAGE_NAMES | SSR_PACKAGE_NAMES)) or any(
        script_uses_command(scripts, tool)
        for tool in ("vite", "next", "astro", "nuxt", "svelte", "webpack", "parcel")
    ) or script_uses_subcommand(scripts, "ng", "serve")
    backend = bool(dependencies & (BACKEND_PACKAGE_NAMES | SSR_PACKAGE_NAMES)) or any(
        script_uses_command(scripts, tool)
        for tool in ("uvicorn", "gunicorn", "flask", "django", "nest")
    ) or any(
        script_uses_python_module(scripts, module)
        for module in ("uvicorn", "gunicorn", "flask", "django", "fastapi")
    ) or script_uses_node_server(scripts)
    return frontend, backend


def validate_package_scripts(package: dict[str, Any], errors: list[str]) -> None:
    if "scripts" not in package:
        return
    scripts = package["scripts"]
    if not isinstance(scripts, dict):
        add_error(errors, "package.json: scripts must be an object")
        return
    for name, command in scripts.items():
        if not isinstance(command, str):
            add_error(errors, f"package.json:scripts.{name}: command must be a string")


def _compose_service_has_ports(service: Any) -> bool:
    if not isinstance(service, dict):
        return False

    def valid_port(value: Any) -> bool:
        if isinstance(value, int) and not isinstance(value, bool):
            return 1 <= value <= 65535
        if not isinstance(value, str):
            return False
        value = value.strip().strip("'\"")
        if not re.fullmatch(r"\d{1,5}(?:-\d{1,5})?", value):
            return False
        bounds = [int(part) for part in value.split("-")]
        return all(1 <= bound <= 65535 for bound in bounds) and (
            len(bounds) == 1 or bounds[0] <= bounds[1]
        )

    def valid_short_mapping(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        value = value.strip().strip("'\"")
        base, separator, protocol = value.rpartition("/")
        if separator:
            if protocol.lower() not in {"tcp", "udp", "sctp"}:
                return False
            value = base
        if not value:
            return False
        parts = value.rsplit(":", 2)
        if len(parts) == 1:
            return valid_port(parts[0])
        if len(parts) == 2:
            host, target = parts
            return bool(host.strip()) and valid_port(target) and (
                valid_port(host) or "." in host or host.startswith("[")
            )
        host, published, target = parts
        return bool(host.strip()) and valid_port(published) and valid_port(target)

    def valid_mapping(value: dict[Any, Any]) -> bool:
        target = value.get("target")
        if valid_port(target):
            return True
        # The dependency-free YAML parser represents an unquoted short port
        # mapping such as `8000:8000` as a one-entry mapping.
        return len(value) == 1 and any(valid_port(item) for item in value)

    ports = service.get("ports")
    if isinstance(ports, str):
        return valid_short_mapping(ports)
    if isinstance(ports, list):
        return any(
            (isinstance(item, str) and valid_short_mapping(item))
            or (isinstance(item, int) and not isinstance(item, bool) and 1 <= item <= 65535)
            or (isinstance(item, dict) and valid_mapping(item))
            for item in ports
        )
    if isinstance(ports, dict):
        return valid_mapping(ports)
    return False


def _stack_evidence(path: str, reason: str) -> dict[str, str]:
    return {"path": path, "reason": reason}


@dataclass
class _Scope:
    """The files of one package scope and the stack evidence collected from them."""

    registry: dict[str, dict[str, Any]]
    files: list[Path]
    root: Path
    text_cache: dict[Path, str | None]
    errors: list[str]
    relative_paths: dict[str, Path]
    root_paths: dict[str, Path]
    dependencies: set[str]
    scripts: dict[str, str]
    matches: dict[str, list[dict[str, str]]]

    def add(self, slug: str, *evidence: dict[str, str]) -> None:
        if slug not in self.registry:
            add_error(self.errors, f"detected stack {slug} has no registry entry")
            return
        self.matches.setdefault(slug, []).extend(evidence)

    def root_named(self, name: str) -> str | None:
        for relative in self.root_paths:
            if relative.lower() == name.lower():
                return relative
        return None

    def paths_starting(self, prefix: str) -> list[str]:
        return sorted(
            relative
            for relative in self.relative_paths
            if Path(relative).name.lower().startswith(prefix.lower())
        )

    def read(self, path: Path) -> str | None:
        return read_cached_text(path, self.root, self.errors, self.text_cache, required=True)


def _sorted_evidence(items: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        {(item["path"], item["reason"]): item for item in items}.values(),
        key=lambda item: (item["path"], item["reason"]),
    )


def _detect_frontend_stacks(scope: _Scope, package_relative: str | None) -> None:
    dependencies = scope.dependencies
    vite_configs = scope.paths_starting("vite.config.")
    vite_script = script_uses_command(scope.scripts, "vite")
    if "vite" in dependencies or vite_script or vite_configs:
        if package_relative and ("vite" in dependencies or vite_script):
            scope.add("vite-spa", _stack_evidence(package_relative, "package.json contains Vite evidence"))
        for relative in vite_configs:
            scope.add("vite-spa", _stack_evidence(relative, "Vite project configuration"))

    next_configs = scope.paths_starting("next.config.")
    if "next" in dependencies or next_configs:
        evidence_path = package_relative or next_configs[0]
        scope.add("react-nextjs", _stack_evidence(evidence_path, "package.json or Next.js configuration contains Next.js evidence"))

    angular_config = scope.root_named("angular.json")
    if "@angular/core" in dependencies or angular_config:
        scope.add("angular", _stack_evidence(package_relative or angular_config, "package.json or angular.json contains Angular evidence"))

    astro_configs = scope.paths_starting("astro.config.")
    if "astro" in dependencies or astro_configs:
        scope.add("astro", _stack_evidence(package_relative or astro_configs[0], "package.json or Astro configuration contains Astro evidence"))

    svelte_configs = scope.paths_starting("svelte.config.")
    if "@sveltejs/kit" in dependencies or svelte_configs:
        scope.add("svelte-sveltekit", _stack_evidence(package_relative or svelte_configs[0], "package.json or Svelte configuration contains SvelteKit evidence"))

    nuxt_configs = scope.paths_starting("nuxt.config.")
    if "nuxt" in dependencies or nuxt_configs:
        scope.add("vue-nuxt", _stack_evidence(package_relative or nuxt_configs[0], "package.json or Nuxt configuration contains Nuxt evidence"))

    if package_relative and dependencies & TANSTACK_START_PACKAGES:
        scope.add("react-tanstack", _stack_evidence(package_relative, "package.json contains TanStack Start evidence"))
        if "react-tanstack" in scope.matches:
            # TanStack Start is the Vite application and its overlay pins Vite, so a
            # separate Vite SPA lock would name the wrong framework.
            scope.matches.pop("vite-spa", None)


def _detect_javascript_runtimes(scope: _Scope, package_relative: str | None) -> None:
    relative_paths = scope.relative_paths
    root_paths = scope.root_paths
    if (
        package_relative
        and scope.root_named("tsconfig.json")
        and ("typescript" in scope.dependencies or any(Path(relative).suffix.lower() in {".ts", ".tsx"} for relative in relative_paths))
        and not scope.matches.keys() & FRONTEND_STACKS
    ):
        scope.add("node-typescript", _stack_evidence(package_relative, "TypeScript package and source evidence"))

    if any(Path(relative).name.lower() in {"bun.lock", "bun.lockb", "bunfig.toml"} for relative in root_paths):
        if scope.root_named("tsconfig.json") or any(Path(relative).suffix.lower() in {".ts", ".tsx"} for relative in relative_paths):
            scope.add("bun-typescript", _stack_evidence(
                next(relative for relative in root_paths if Path(relative).name.lower() in {"bun.lock", "bun.lockb", "bunfig.toml"}),
                "Bun lock or configuration with TypeScript evidence",
            ))

    deno_relative = next(
        (relative for relative in root_paths if Path(relative).name.lower() in {"deno.json", "deno.jsonc"}),
        None,
    )
    if deno_relative:
        scope.add("deno-typescript", _stack_evidence(deno_relative, "Deno configuration"))


def _detect_backend_stacks(scope: _Scope) -> None:
    for filename in ("main.py", "app.py"):
        relative = scope.root_named(filename)
        if not relative:
            continue
        text = scope.read(scope.root_paths[relative])
        if text and python_imports_module(text, PYTHON_FASTAPI_MODULES):
            scope.add("python-fastapi", _stack_evidence(relative, "Python web runtime import evidence"))

    go_mod = scope.root_named("go.mod")
    go_entry = go_entrypoint(scope.files, scope.root, scope.text_cache, scope.errors)
    if go_mod and go_entry:
        text = scope.read(scope.root_paths[go_mod]) or ""
        if re.search(r"(?i)(?:gin-gonic/gin|/gin\b)", text):
            scope.add("go-gin", _stack_evidence(go_mod, "Go module declares Gin"), _stack_evidence(go_entry, "Go executable entrypoint"))

    cargo = scope.root_named("cargo.toml")
    rust_entry = cargo_binary_entry(scope.files, scope.root, scope.text_cache, scope.errors) if cargo else None
    if cargo and rust_entry:
        text = scope.read(scope.root_paths[cargo]) or ""
        if re.search(r"(?i)\baxum\b", text):
            scope.add("rust-axum", _stack_evidence(cargo, "Cargo manifest declares Axum"), _stack_evidence(rust_entry, "Rust executable entrypoint"))

    csproj = next(
        (relative for relative in scope.root_paths if Path(relative).suffix.lower() in {".csproj", ".fsproj", ".vbproj"}),
        None,
    )
    if csproj:
        text = scope.read(scope.root_paths[csproj]) or ""
        if re.search(r"(?i)(?:Microsoft\.AspNetCore|Microsoft.NET.Sdk.Web|AspNetCore)", text):
            scope.add("dotnet-aspnet", _stack_evidence(csproj, ".NET web project manifest"))


def _detect_in_scope(
    registry: dict[str, dict[str, Any]],
    files: list[Path],
    root: Path,
    package: dict[str, Any],
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> list[dict[str, Any]]:
    relative_paths = {
        relative_path(path, root): path
        for path in files
        if classify_path(relative_path(path, root)) == "production"
    }
    scope = _Scope(
        registry=registry,
        files=files,
        root=root,
        text_cache=text_cache,
        errors=errors,
        relative_paths=relative_paths,
        root_paths={
            relative: path
            for relative, path in relative_paths.items()
            if "/" not in relative
        },
        dependencies=_package_dependencies(package),
        scripts=_package_scripts(package),
        matches={},
    )
    package_relative = scope.root_named("package.json")
    _detect_frontend_stacks(scope, package_relative)
    _detect_javascript_runtimes(scope, package_relative)
    _detect_backend_stacks(scope)

    result: list[dict[str, Any]] = []
    for slug in sorted(scope.matches):
        row = registry[slug]
        result.append(
            {
                "slug": slug,
                "framework": row.get("framework"),
                "versions": row.get("versions", []),
                "evidence": _sorted_evidence(scope.matches[slug]),
            }
        )
    return result


def _detect_across_packages(
    registry: dict[str, dict[str, Any]],
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
    packages: list[tuple[Path, dict[str, Any]]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    package_roots = {package_path.parent for package_path, _ in packages}
    scopes = [(package_path.parent, package_value) for package_path, package_value in packages]
    if root not in package_roots:
        # Root-level evidence (go.mod, Cargo.toml, main.py, a csproj) belongs to the
        # project even when only nested packages carry a package.json, so the
        # files no package claims are detected as a scope of their own.
        scopes.append((root, {}))
    for package_root, package_value in scopes:
        scoped_files = [
            path
            for path in files
            if path.is_relative_to(package_root)
            and (
                package_root in package_roots
                or not any(path.is_relative_to(claimed) for claimed in package_roots)
            )
        ]
        for stack in _detect_in_scope(
            registry,
            scoped_files,
            package_root,
            package_value,
            text_cache,
            errors,
        ):
            target = merged.setdefault(
                stack["slug"],
                {
                    "slug": stack["slug"],
                    "framework": stack.get("framework"),
                    "versions": stack.get("versions", []),
                    "evidence": [],
                },
            )
            for evidence in stack.get("evidence", []):
                evidence_path = package_root / str(evidence["path"])
                target["evidence"].append(
                    {
                        "path": relative_path(evidence_path, root),
                        "reason": evidence["reason"],
                    }
                )
    result = []
    for slug in sorted(merged):
        row = merged[slug]
        row["evidence"] = _sorted_evidence(row["evidence"])
        result.append(row)
    return result


def detect_stacks(
    registry: dict[str, dict[str, Any]],
    files: list[Path],
    root: Path,
    package: dict[str, Any],
    text_cache: dict[Path, str | None],
    errors: list[str],
    *,
    packages: list[tuple[Path, dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    if packages is not None:
        return _detect_across_packages(registry, files, root, text_cache, errors, packages)
    return _detect_in_scope(registry, files, root, package, text_cache, errors)


def classify_project(
    files: list[Path],
    root: Path,
    stacks: list[dict[str, Any]],
    text_cache: dict[Path, str | None],
    errors: list[str],
    warnings: list[str],
    *,
    packages: list[tuple[Path, dict[str, Any]]] | None = None,
) -> tuple[str, list[dict[str, str]], list[str]]:
    relative_paths = {relative_path(path, root): path for path in files}
    root_paths = {
        relative: path for relative, path in relative_paths.items() if "/" not in relative
    }
    stack_slugs = {str(item["slug"]) for item in stacks}
    package_records = packages or []
    classification_evidence: list[dict[str, str]] = []
    ambiguities: list[str] = []
    # Every source of evidence adds to these signals before anything is decided, so
    # the first manifest found cannot hide what the rest of the tree says.
    frontend = bool(stack_slugs & FRONTEND_STACKS)
    backend = False
    published_ports = False
    manifest_seen = bool(package_records)

    compose = next(
        (
            (relative, path)
            for relative, path in root_paths.items()
            if Path(relative).name.lower() in COMPOSE_NAMES
        ),
        None,
    )
    if compose:
        compose_data = load_cached_data(compose[1], root, errors, warnings, text_cache)
        services = compose_data.get("services") if isinstance(compose_data, dict) else None
        if isinstance(services, dict):
            classification_evidence.append(_stack_evidence(compose[0], "compose services definition"))
            published_ports = any(_compose_service_has_ports(service) for service in services.values())
            if not published_ports:
                ambiguities.append("compose services were found without a ports mapping")

    makefile_paths = sorted(
        path
        for path in files
        if (
            path.name.lower() == "makefile"
            and not is_sensitive(path, root)
            and classify_path(relative_path(path, root)) == "production"
        )
    )
    for path in makefile_paths:
        relative = relative_path(path, root)
        makefile_text = read_cached_text(path, root, errors, text_cache, required=True) or ""
        makefile_frontend, makefile_backend = makefile_runtime_signals(makefile_text)
        frontend = frontend or makefile_frontend
        backend = backend or makefile_backend
        if makefile_frontend or makefile_backend:
            classification_evidence.append(_stack_evidence(relative, "Makefile runtime command"))

    single_root_package = len(package_records) == 1 and package_records[0][0].parent == root
    for package_path, package_value in package_records:
        package_frontend, package_backend = _package_classification_signals(package_value)
        frontend = frontend or package_frontend
        backend = backend or package_backend
        classification_evidence.append(
            _stack_evidence(
                relative_path(package_path, root),
                "root package.json" if single_root_package else "package.json service manifest",
            )
        )

    if stack_slugs & FRONTEND_STACKS and not package_records:
        frontend_evidence = next(
            (
                relative
                for relative in sorted(relative_paths)
                if Path(relative).name.lower().startswith(
                    ("vite.config.", "next.config.", "astro.config.", "svelte.config.", "nuxt.config.")
                )
            ),
            next(iter(sorted(relative_paths)), "registered stack evidence"),
        )
        classification_evidence.append(_stack_evidence(frontend_evidence, "registered frontend stack evidence"))

    manage = next((relative for relative in root_paths if Path(relative).name.lower() == "manage.py"), None)
    if manage:
        backend = True
        classification_evidence.append(_stack_evidence(manage, "Django management entrypoint"))

    web_entry = None
    for filename in ("main.py", "app.py"):
        relative = next((item for item in root_paths if Path(item).name.lower() == filename), None)
        if relative:
            text = read_cached_text(root_paths[relative], root, errors, text_cache, required=True) or ""
            if python_imports_module(text, PYTHON_WEB_MODULES):
                web_entry = relative
                break
    if web_entry:
        backend = True
        classification_evidence.append(_stack_evidence(web_entry, "Python web runtime import"))

    go_mod = next((relative for relative in root_paths if Path(relative).name.lower() == "go.mod"), None)
    go_entry = go_entrypoint(files, root, text_cache, errors)
    if go_mod and go_entry:
        manifest_seen = True
        classification_evidence.extend(
            (_stack_evidence(go_mod, "Go module manifest"), _stack_evidence(go_entry, "Go executable entrypoint"))
        )
        text = read_cached_text(relative_paths[go_entry], root, errors, text_cache, required=True) or ""
        backend = backend or bool(re.search(r"(?i)(?:net/http|gin-gonic|echo|fiber)", text))

    cargo = next((relative for relative in root_paths if Path(relative).name.lower() == "cargo.toml"), None)
    rust_entry = cargo_binary_entry(files, root, text_cache, errors) if cargo else None
    if cargo and rust_entry:
        manifest_seen = True
        classification_evidence.extend(
            (_stack_evidence(cargo, "Rust package manifest"), _stack_evidence(rust_entry, "Rust executable entrypoint"))
        )
        manifest_text = read_cached_text(root_paths[cargo], root, errors, text_cache, required=True) or ""
        entry_text = read_cached_text(relative_paths[rust_entry], root, errors, text_cache, required=True) or ""
        backend = backend or bool(
            re.search(r"(?i)\b(?:axum|actix|warp|rocket|hyper)\b", f"{manifest_text}\n{entry_text}")
        )

    java_manifest = next(
        (relative for relative in root_paths if Path(relative).name.lower() in {"pom.xml", "build.gradle", "build.gradle.kts"}),
        None,
    )
    if java_manifest:
        manifest_seen = True
        classification_evidence.append(_stack_evidence(java_manifest, "Java build manifest"))
        text = read_cached_text(root_paths[java_manifest], root, errors, text_cache, required=True) or ""
        backend = backend or bool(re.search(r"(?i)(?:spring|servlet|jetty|micronaut)", text))

    # A compose file that publishes ports says how the project is deployed, not what
    # it contains, so it decides only when nothing about the application itself does.
    if frontend and backend:
        return "full-stack", classification_evidence, ambiguities
    if frontend:
        return "frontend-only", classification_evidence, ambiguities
    if backend:
        return "backend-only", classification_evidence, ambiguities
    if published_ports:
        return "container-orchestrated", classification_evidence, ambiguities
    if not manifest_seen:
        ambiguities.append("no supported runtime classification signal was found")
    return "library/CLI", classification_evidence, ambiguities
