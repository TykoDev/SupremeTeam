#!/usr/bin/env python3
"""Check the package runtime contract without installing or mutating anything."""

from __future__ import annotations

import argparse
import ast
import bisect
import hashlib
import importlib.util
import json
import math
import os
import re
import shlex
import stat
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from data_formats import DataFormatError, load_data, parse_yaml


SKIPPED_DIRECTORIES = frozenset({".git", "node_modules", ".venv", "target", "__pycache__"})
SENSITIVE_DIRECTORIES = frozenset({".aws", ".azure", ".gnupg", ".ssh"})
SKIPPED_DIRECTORY_NAMES = frozenset(name.lower() for name in SKIPPED_DIRECTORIES)
SENSITIVE_DIRECTORY_NAMES = frozenset(name.lower() for name in SENSITIVE_DIRECTORIES)
SENSITIVE_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.development",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "secrets.json",
        "service-account.json",
        "id_rsa",
        "id_ed25519",
    }
)
SENSITIVE_SUFFIXES = frozenset({".cer", ".crt", ".der", ".key", ".pem", ".p12", ".pfx"})
TEXT_SUFFIXES = frozenset(
    {
        ".adoc",
        ".bash",
        ".c",
        ".cfg",
        ".conf",
        ".cpp",
        ".cjs",
        ".cs",
        ".cts",
        ".css",
        ".go",
        ".gradle",
        ".h",
        ".hpp",
        ".html",
        ".ini",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".kts",
        ".md",
        ".mjs",
        ".mod",
        ".mts",
        ".py",
        ".rb",
        ".rst",
        ".rs",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".csproj",
        ".fsproj",
        ".vbproj",
        ".xml",
        ".yml",
        ".yaml",
        ".zsh",
    }
)
TEXT_FILE_NAMES = frozenset({"Dockerfile", "Makefile", "Procfile", "Jenkinsfile"})
TEXT_FILE_NAMES_LOWER = frozenset(name.lower() for name in TEXT_FILE_NAMES)
TEST_DIRECTORY_NAMES = frozenset(
    {"__fixtures__", "__tests__", "e2e", "fixtures", "integration", "spec", "specs", "test", "test-fixtures", "testdata", "tests", "unit"}
)
MAX_INSPECTION_FILE_BYTES = 1_000_000
MAX_INSPECTION_FILE_COUNT = 1_000
MAX_INSPECTION_DIRECTORY_COUNT = 1_000
MAX_INSPECTION_TOTAL_BYTES = 10_000_000
MAX_INSPECTION_DEPTH = 32
OPTIONAL_MODULES = {"PyYAML": "yaml"}

MANIFEST_NAMES = {
    "package.json": "package manifest",
    "pyproject.toml": "Python package manifest",
    "requirements.txt": "Python requirements manifest",
    "setup.cfg": "Python package manifest",
    "setup.py": "Python package manifest",
    "go.mod": "Go module manifest",
    "cargo.toml": "Rust package manifest",
    "pom.xml": "Maven manifest",
    "build.gradle": "Gradle manifest",
    "build.gradle.kts": "Gradle manifest",
}
COMPOSE_NAMES = {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}
REGISTRY_ROW_KEYS = frozenset({"slug", "path", "framework", "versions", "source", "sha256"})
REGISTRY_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REGISTRY_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

CONFIG_NAMES = {
    "angular.json": "Angular configuration",
    "deno.json": "Deno configuration",
    "deno.jsonc": "Deno configuration",
    "tsconfig.json": "TypeScript configuration",
    "dockerfile": "container configuration",
    "makefile": "build configuration",
    "procfile": "process configuration",
    ".env.example": "environment template",
}
CONFIG_PREFIXES = (
    "appsettings",
    "application.",
    "astro.config.",
    "eslint.config.",
    "next.config.",
    "nuxt.config.",
    "rollup.config.",
    "svelte.config.",
    "vite.config.",
    "webpack.config.",
)

START_SCRIPT_ORDER = ("dev", "start")
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
COMMAND_OPTIONS_WITH_VALUES = frozenset(
    {
        "--cache",
        "--cache-folder",
        "--config",
        "--config-dir",
        "--cwd",
        "--dir",
        "--filter",
        "--package",
        "--prefix",
        "--registry",
        "--script-shell",
        "--userconfig",
        "--workspace",
        "--workspace-root",
        "-w",
        "-c",
        "-f",
    }
)
PACKAGE_MANAGER_OPTIONS_WITH_VALUES = {
    "bun": frozenset({"--config", "--cwd", "--filter", "--package"}),
    "npm": frozenset(
        {"--cache", "--cache-folder", "--globalconfig", "--package", "--prefix", "--registry", "--userconfig", "--workspace", "--workspace-root", "-w"}
    ),
    "pnpm": frozenset({"--dir", "--filter", "--package", "--workspace-concurrency", "--workspace-root", "-c", "-f"}),
    "yarn": frozenset({"--cache-folder", "--cwd", "--modules-folder", "--mutex", "--package", "--registry", "-c"}),
}
ENV_OPTIONS_WITH_VALUES = frozenset({"--chdir", "--split-string", "--unset", "-S", "-c", "-u"})
EXEC_OPTIONS_WITH_VALUES = frozenset({"--argv0", "-a"})
COMMAND_LOOKUP_OPTIONS = frozenset({"--help", "--version", "-V", "-v", "-h"})
SECRET_KEYS = r"(?:password|passwd|passphrase|secret(?:[_-]?key)?|webhook[_-]?secret|token|auth[_-]?(?:key|token)?|api[_-]?key|authorization|private[_-]?key|client[_-]?secret|database[_-]?(?:password|url)|access[_-]?token|access[_-]?key(?:[_-]?id)?|shared[_-]?access[_-]?(?:key|signature)|sig|refresh[_-]?token|session(?:s|[_-]?(?:id|token))?|cookie(?:s)?|set[_-]?cookie|bearer|credential(?:s)?|csrf(?:[_-]?token)?|jwt|signature|signed[_-]?url|connection[_-]?string|signing[_-]?key|encryption[_-]?key|secret[_-]?access[_-]?key|storage[_-]?account[_-]?key|service[_-]?account[_-]?key|secret[_-]?key[_-]?base64|azure[_-]?storage[_-]?account[_-]?key|cloud[_-]?(?:access|secret)(?:[_-]?access)?[_-]?key|aws[_-]?(?:access[_-]?key(?:[_-]?id)?|secret[_-]?access[_-]?key|session[_-]?token)|github[_-]?token|npm[_-]?token|redis[_-]?url|mongo(?:db)?[_-]?(?:url|uri))"
SECRET_VALUE = r"(?:(?:bearer|basic|token)\s+[^\s,;&|\"'}]+|\\?[\"](?:\\.|[^\"\\])*\\?[\"]|\\?['\"](?:\\.|[^'\"\\])*\\?['\"]|[^\s,;&|\"'}]+)"
SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?i)(\\?[\"']?{SECRET_KEYS}\\?[\"']?)"
    r"(\s*[:=]\s*)"
    rf"(?P<secret_value>{SECRET_VALUE})"
)
SECRET_FLAG_RE = re.compile(
    rf"(?i)(--?{SECRET_KEYS})"
    r"(?=\s|=)(?:\s*=\s*|\s+)"
    rf"{SECRET_VALUE}"
)
AUTH_SCHEME_RE = re.compile(r"(?i)\b(?:bearer|basic|token|digest)\b(?=\s+)")
REDACTION_DEPTH_LIMIT = 100
STRUCTURED_SECRET_KEYS = frozenset(
    {
        "password", "passwd", "passphrase", "secret", "secretkey", "webhooksecret",
        "token", "apikey", "authorization", "privatekey", "clientsecret",
        "databasepassword", "databaseurl", "dbpassword", "dburl", "accesstoken", "accesskey",
        "accesskeyid", "sastoken", "sharedaccesskey", "sharedaccesssignature",
        "refreshtoken", "session", "sessions", "sessionid", "sessiontoken",
        "cookie", "cookies", "setcookie", "bearer", "auth", "authkey", "authtoken",
        "credential", "credentials", "csrftoken", "jwt", "signature", "sig", "signedurl",
        "connectionstring", "signingkey", "encryptionkey", "secretaccesskey",
        "storageaccountkey", "serviceaccountkey", "secretkeybase64",
        "azurestorageaccountkey", "cloudaccesskey", "cloudsecretaccesskey",
        "awsaccesskey", "awsaccesskeyid", "awssecretaccesskey", "awssessiontoken",
        "githubtoken", "npmtoken", "redisurl", "mongourl", "mongouri",
        "xamzsignature", "xamzsecuritytoken",
        "xapikey", "xauthtoken", "xaccesstoken",
    }
)
URL_SECRET_QUERY_KEYS = frozenset(
    {
        "sig", "signature", "signedurl", "accesskey", "accesskeyid", "sharedaccesskey", "sharedaccesssignature", "secretaccesskey",
        "awsaccesskeyid", "xamzcredential", "xamzsignature", "token", "apikey",
        "authorization",
    }
)
URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+")
URL_QUERY_RE = re.compile(r"(?i)([?&])([^=&#\s]+)=([^&#\s\"']*)")
PYTHON_WEB_MODULES = frozenset(
    {"fastapi", "flask", "django", "starlette", "quart", "sanic", "http.server", "uvicorn"}
)
PYTHON_FASTAPI_MODULES = frozenset({"fastapi", "starlette"})

MARKER_PATTERN = re.compile(
    r"(?i)\b(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB|NOT\s+IMPLEMENTED|COMING\s+SOON|"
    r"TEMPORARY|TEMP|DUMMY|FAKE|SAMPLE|REMOVE\s+(?:THIS|ME|BEFORE)|CHANGE\s*ME)\b"
)
COMMENT_MARKER_PATTERN = re.compile(
    r"(?i)(?:^|\s)(?:#|//|/\*)\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB|"
    r"NOT\s+IMPLEMENTED|COMING\s+SOON|TEMPORARY|TEMP|DUMMY|FAKE|SAMPLE|"
    r"REMOVE\s+(?:THIS|ME|BEFORE)|CHANGE\s*ME)\b"
)


def _python_imports_module(text: str, modules: frozenset[str]) -> bool:
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {alias.name for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = {node.module}
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
            else:
                continue
            if any(
                name == module or name.startswith(module + ".")
                for name in imported
                for module in modules
            ):
                return True
    except (SyntaxError, ValueError, RecursionError):
        return False
    return False


def _version(value: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError("invalid Python version")
    match = re.fullmatch(r"(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("invalid Python version")
    return int(match.group(1)), int(match.group(2))


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _is_sensitive(path: Path, root: Path | None = None) -> bool:
    try:
        parts = path.relative_to(root).parts if root is not None else path.parts
    except ValueError:
        parts = path.parts
    lowered_parts = {part.lower() for part in parts}
    name = path.name.lower()
    return (
        bool(lowered_parts & SENSITIVE_DIRECTORIES)
        or name in SENSITIVE_FILE_NAMES
        or path.suffix.lower() in SENSITIVE_SUFFIXES
    )


def _is_text_path(path: Path) -> bool:
    return path.name.lower() in TEXT_FILE_NAMES_LOWER or path.suffix.lower() in TEXT_SUFFIXES


def _is_reparse_point(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except (OSError, ValueError):
        return False


def _has_reparse_component(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    if _is_reparse_point(current):
        return True
    for part in relative.parts:
        current /= part
        if _is_reparse_point(current):
            return True
    return False


def _has_reparse_ancestor(path: Path) -> bool:
    current = path
    while True:
        if _is_reparse_point(current):
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def _safe_regular_file(path: Path, root: Path) -> bool:
    if _has_reparse_component(path, root):
        return False
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return path.is_file() and not _is_reparse_point(path)


def _add_error(errors: list[str], message: str) -> None:
    message = _redact(message)
    if message not in errors:
        errors.append(message)


def _skip_reparse_directory(path: Path, root: Path, errors: list[str]) -> bool:
    if path.is_symlink():
        _add_error(errors, f"{_relative(path, root)}: reparse points are not inspected")
        return True
    if _is_reparse_point(path):
        _add_error(errors, f"{_relative(path, root)}: reparse points are not inspected")
        return True
    return False


def _walk_project(root: Path, errors: list[str]) -> list[Path]:
    files: list[Path] = []
    file_count = 0
    directory_count = 0
    total_bytes = 0

    if _is_reparse_point(root):
        _add_error(errors, "project root: reparse points are not inspected")
        return files

    def keep_smallest(
        entries: list[tuple[str, Path]],
        entry: tuple[str, Path],
        limit: int,
    ) -> bool:
        if limit <= 0:
            return True
        if len(entries) < limit:
            bisect.insort(entries, entry)
            return False
        if entry[0] < entries[-1][0]:
            entries.pop()
            bisect.insort(entries, entry)
        return True

    def visit(current_path: Path, current_depth: int) -> bool:
        nonlocal directory_count, file_count, total_bytes
        if directory_count >= MAX_INSPECTION_DIRECTORY_COUNT:
            _add_error(errors, "project inspection directory-count limit exceeded")
            return False
        directory_count += 1
        directory_candidates: list[tuple[str, Path]] = []
        file_candidates: list[tuple[str, Path]] = []
        directory_overflow = False
        file_overflow = False
        try:
            with os.scandir(current_path) as entries:
                for entry in entries:
                    name = entry.name
                    if name.lower() in SKIPPED_DIRECTORY_NAMES or name.lower() in SENSITIVE_DIRECTORY_NAMES:
                        continue
                    candidate = current_path / name
                    if _skip_reparse_directory(candidate, root, errors):
                        continue
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError as exc:
                        _add_error(errors, f"cannot inspect {candidate}: {exc}")
                        continue
                    if is_directory:
                        if current_depth + 1 > MAX_INSPECTION_DEPTH:
                            _add_error(errors, f"{_relative(candidate, root)}: inspection depth limit exceeded")
                            continue
                        directory_overflow = keep_smallest(
                            directory_candidates,
                            (name, candidate),
                            MAX_INSPECTION_DIRECTORY_COUNT - directory_count,
                        ) or directory_overflow
                        continue
                    if not is_file:
                        continue
                    path = candidate
                    if not _safe_regular_file(path, root):
                        continue
                    file_overflow = keep_smallest(
                        file_candidates,
                        (name, path),
                        MAX_INSPECTION_FILE_COUNT - file_count,
                    ) or file_overflow
        except OSError as exc:
            _add_error(errors, f"cannot inspect {current_path}: {exc}")

        for _, path in file_candidates:
            if file_count >= MAX_INSPECTION_FILE_COUNT:
                _add_error(errors, "project inspection file-count limit exceeded")
                return False
            try:
                size = path.stat().st_size
            except OSError as exc:
                _add_error(errors, f"{_relative(path, root)}: cannot inspect file ({exc})")
                continue
            if total_bytes + size > MAX_INSPECTION_TOTAL_BYTES:
                _add_error(errors, "project inspection total-byte limit exceeded")
                return False
            files.append(path)
            file_count += 1
            total_bytes += size
        if file_overflow:
            _add_error(errors, "project inspection file-count limit exceeded")
            return False

        for _, path in directory_candidates:
            if not visit(path, current_depth + 1):
                return False
        if directory_overflow:
            _add_error(errors, "project inspection directory-count limit exceeded")
            return False
        return True

    visit(root, 0)
    return files


def _read_text(
    path: Path,
    root: Path,
    errors: list[str],
    *,
    required: bool = False,
) -> str | None:
    if _is_sensitive(path, root) or not _is_text_path(path):
        return None
    relative = _relative(path, root)
    if path.is_symlink():
        if required:
            _add_error(errors, f"{relative}: reparse points are not inspected")
        return None
    if _is_reparse_point(path) or not _safe_regular_file(path, root):
        if required:
            _add_error(errors, f"{relative}: reparse points and out-of-root files are not inspected")
        return None
    try:
        if path.stat().st_size > MAX_INSPECTION_FILE_BYTES:
            if required:
                _add_error(errors, f"{relative}: file exceeds the inspection size limit")
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        if required:
            _add_error(errors, f"{relative}: cannot read text ({exc})")
        return None


def _manifest_kind(path: Path) -> str | None:
    name = path.name.lower()
    if name in MANIFEST_NAMES:
        return MANIFEST_NAMES[name]
    if name in COMPOSE_NAMES:
        return "compose manifest"
    if path.suffix.lower() in {".csproj", ".fsproj", ".vbproj"}:
        return ".NET project manifest"
    return None


def _config_kind(path: Path) -> str | None:
    name = path.name.lower()
    if name in CONFIG_NAMES:
        return CONFIG_NAMES[name]
    if name in COMPOSE_NAMES:
        return None
    if any(name.startswith(prefix) for prefix in CONFIG_PREFIXES):
        return "project configuration"
    return None


def _collect_evidence(files: list[Path], root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    manifests: list[dict[str, str]] = []
    configs: list[dict[str, str]] = []
    for path in files:
        if _is_sensitive(path, root):
            continue
        relative = _relative(path, root)
        manifest_kind = _manifest_kind(path)
        if manifest_kind:
            manifests.append({"path": relative, "kind": manifest_kind})
            continue
        config_kind = _config_kind(path)
        if config_kind:
            configs.append({"path": relative, "kind": config_kind})
    return manifests, configs


def _auth_value_end(value: str, start: int) -> int:
    index = start
    while index < len(value) and value[index].isspace():
        index += 1
    if index == len(value):
        return start
    if value.startswith((r'\"', r"\'"), index):
        quote = value[index + 1]
        closing = value.find("\\" + quote, index + 2)
        return len(value) if closing == -1 else closing + 2
    if value[index] in {"'", '"'}:
        quote = value[index]
        index += 1
        escaped = False
        while index < len(value):
            char = value[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return index + 1
            index += 1
        return len(value)

    body_start = index
    while index < len(value):
        char = value[index]
        if char in ",;|&\"'}\r\n":
            break
        if char.isspace():
            if char in "\r\n":
                break
            lookahead = index
            while lookahead < len(value) and value[lookahead] in " \t":
                lookahead += 1
            if lookahead < len(value):
                remainder = value[lookahead:]
                if re.match(
                    r"(?i)(?:--?[A-Za-z_][A-Za-z0-9_-]*|(?:Bearer|Basic|Token|Digest)\b|"
                    r"[A-Za-z_][A-Za-z0-9_-]*\s*[:=])",
                    remainder,
                ):
                    break
        index += 1
    return index if index > body_start else start


def _redact_auth_schemes(value: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in AUTH_SCHEME_RE.finditer(value):
        if match.start() < cursor:
            continue
        pieces.append(value[cursor:match.end()])
        remainder = value[match.end():]
        if (
            match.group(0).strip().lower() == "token"
            and re.match(
                r"(?i)\s+(?:must|is|was|were|should|cannot|can\s+not|can't|isn't|is\s+not)\b",
                remainder,
            )
        ) or re.match(
            r"(?i)\s+(?:authentication|authorization|auth|credentials?|field|header|scheme|token|value)\s+"
            r"(?:is|are|required|was|were|must|should|cannot|can\s+not|can't)\b",
            remainder,
        ):
            cursor = match.end()
            continue
        end = _auth_value_end(value, match.end())
        if end > match.end():
            pieces.append(" <redacted>")
        cursor = end
    pieces.append(value[cursor:])
    return "".join(pieces)


def _redact_url(match: re.Match[str]) -> str:
    value = re.sub(r"(?i)(://)[^/?#\s@]+@", r"\1<redacted>@", match.group(0), count=1)

    def redact_query(query_match: re.Match[str]) -> str:
        key = query_match.group(2)
        query_value = query_match.group(3)
        normalized = re.sub(r"[^a-z0-9]", "", unquote(key).lower())
        if normalized in URL_SECRET_QUERY_KEYS and query_value != "<redacted>":
            return f"{query_match.group(1)}{key}=<redacted>"
        return query_match.group(0)

    return URL_QUERY_RE.sub(redact_query, value)


def _redact_urls(value: str) -> str:
    return URL_RE.sub(_redact_url, value)


def _redact_assignment(match: re.Match[str], value: str) -> str:
    diagnostic_value = match.group("secret_value").strip().strip("'\"").lower()
    if diagnostic_value in {"field", "value", "authentication", "authorization", "credentials", "header", "scheme"} and re.match(
        r"(?i)\s+(?:is|required|was|were|must|should|cannot|can\s+not|can't|isn't|is\s+not|missing|invalid)\b",
        value[match.end():],
    ):
        return match.group(0)
    return f"{match.group(1)}{match.group(2)}<redacted>"


def _redact_sequence(value: list[Any], depth: int) -> list[Any]:
    result: list[Any] = []
    redact_next = False
    for item in value:
        if redact_next:
            result.append("<redacted>")
            redact_next = False
            continue
        if isinstance(item, str):
            token = item.strip().strip("'\"")
            normalized = re.sub(r"[^a-z0-9]", "", token.lstrip("-").lower())
            if token.lower() in {"bearer", "basic", "token", "digest"} or (
                token.startswith("-") and normalized in STRUCTURED_SECRET_KEYS
            ):
                redact_next = True
            result.append(_redact(item, parse_structured=False))
        else:
            result.append(_redact_value(item, depth + 1))
    return result


def _redact(value: str, *, parse_structured: bool = True) -> str:
    if parse_structured:
        try:
            parsed = json.loads(value)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            try:
                return json.dumps(_redact_value(parsed), ensure_ascii=False, sort_keys=True)
            except (ValueError, RecursionError):
                pass
    value = _redact_urls(value)
    value = _redact_auth_schemes(value)
    value = SECRET_FLAG_RE.sub(r"\1=<redacted>", value)
    value = SECRET_ASSIGNMENT_RE.sub(lambda match: _redact_assignment(match, value), value)
    return value


def _redact_value(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return _redact(value, parse_structured=False)
    if isinstance(value, list):
        if depth >= REDACTION_DEPTH_LIMIT:
            return "<nested value omitted>"
        return _redact_sequence(value, depth)
    if isinstance(value, dict):
        if depth >= REDACTION_DEPTH_LIMIT:
            return "<nested value omitted>"
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in STRUCTURED_SECRET_KEYS:
                result[str(key)] = "<redacted>"
            else:
                result[str(key)] = _redact_value(item, depth + 1)
        return result
    if isinstance(value, float) and not math.isfinite(value):
        return "<non-finite>"
    return value


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
        _add_error(errors, "runtime manifest root must be a mapping")
        return "unknown", None, [], {}, errors

    runtime = manifest.get("runtime")
    if not isinstance(runtime, dict):
        _add_error(errors, "runtime manifest runtime must be a mapping")
        return "unknown", None, [], {}, errors
    python = runtime.get("python")
    if not isinstance(python, dict):
        _add_error(errors, "runtime manifest runtime.python must be a mapping")
        return "unknown", None, [], {}, errors

    minimum = python.get("minimum")
    try:
        minimum_version = _version(minimum)
    except ValueError:
        _add_error(errors, "runtime manifest runtime.python.minimum must be major.minor")
        minimum = "unknown"
        minimum_version = None

    optional_value = python.get("optional_dependencies", [])
    optional: list[dict[str, Any]] = []
    if not isinstance(optional_value, list):
        _add_error(errors, "runtime manifest optional_dependencies must be a list")
    else:
        for index, dependency in enumerate(optional_value):
            if not isinstance(dependency, dict):
                _add_error(errors, f"runtime manifest optional dependency {index} must be a mapping")
                continue
            name = dependency.get("name")
            if not isinstance(name, str) or not name.strip():
                _add_error(errors, f"runtime manifest optional dependency {index} requires a name")
                continue
            if "version" in dependency and not isinstance(dependency["version"], str):
                _add_error(errors, f"runtime manifest optional dependency {index} version must be a string")
            if "fallback" in dependency and not isinstance(dependency["fallback"], str):
                _add_error(errors, f"runtime manifest optional dependency {index} fallback must be a string")
            optional.append(dependency)

    launchers_value = manifest.get("launchers", {})
    launchers: dict[str, Any] = {}
    if not isinstance(launchers_value, dict):
        _add_error(errors, "runtime manifest launchers must be a mapping")
    else:
        launchers = launchers_value
        for name, command in launchers.items():
            if not isinstance(name, str) or not isinstance(command, str):
                _add_error(errors, "runtime manifest launcher names and commands must be strings")

    return minimum, minimum_version, optional, launchers, errors


def _read_package(
    path: Path,
    root: Path,
    errors: list[str],
    cache: dict[Path, str | None],
) -> dict[str, Any]:
    text = _read_cached_text(path, root, errors, cache, required=True)
    if text is None:
        return {}
    try:
        value = json.loads(text)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, json.JSONDecodeError):
            detail = f"invalid JSON at line {exc.lineno}"
        else:
            detail = f"invalid JSON ({exc})"
        _add_error(errors, f"{_relative(path, root)}: {detail}")
        return {}
    if not isinstance(value, dict):
        _add_error(errors, f"{_relative(path, root)}: package manifest must be a JSON object")
        return {}
    return value


def _read_cached_text(
    path: Path,
    root: Path,
    errors: list[str],
    cache: dict[Path, str | None],
    *,
    required: bool = False,
) -> str | None:
    if path not in cache:
        cache[path] = _read_text(path, root, errors, required=required)
    elif required and cache[path] is None:
        _read_text(path, root, errors, required=True)
    return cache[path]


def _load_cached_data(
    path: Path,
    root: Path,
    errors: list[str],
    text_cache: dict[Path, str | None],
) -> Any | None:
    text = _read_cached_text(path, root, errors, text_cache, required=True)
    if text is None:
        return None
    try:
        return parse_yaml(text)
    except (DataFormatError, UnicodeError, ValueError, RecursionError) as exc:
        _add_error(errors, f"{_relative(path, root)}: {exc}")
        return None


def _load_registry(catalog_root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    path = catalog_root / "tech-stacks" / "registry.yaml"
    if path.exists() and not _safe_regular_file(path, catalog_root):
        _add_error(errors, "tech-stacks/registry.yaml: must be a regular file")
        return {}
    if not path.exists():
        return {}
    text = _read_text(path, catalog_root, errors, required=True)
    if text is None:
        return {}
    try:
        value = parse_yaml(text)
    except (DataFormatError, UnicodeError, ValueError, RecursionError) as exc:
        _add_error(errors, f"tech-stacks/registry.yaml: {exc}")
        return {}
    if not isinstance(value, dict):
        _add_error(errors, "tech-stacks/registry.yaml: root must be a mapping")
        return {}
    registry_valid = True
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        _add_error(errors, "tech-stacks/registry.yaml: schema_version must be 1")
        registry_valid = False
    if value.get("kind") != "supremeteam-tech-stack-registry":
        _add_error(errors, "tech-stacks/registry.yaml: kind is invalid")
        registry_valid = False
    if not isinstance(value.get("overlays"), list):
        _add_error(errors, "tech-stacks/registry.yaml: overlays must be a list")
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value["overlays"]):
        if not isinstance(item, dict):
            _add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} must be a mapping")
            continue
        missing = sorted(REGISTRY_ROW_KEYS - set(item))
        extra = sorted(set(item) - REGISTRY_ROW_KEYS)
        if missing:
            _add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} missing fields {missing}")
        if extra:
            _add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} has unexpected fields {extra}")
        slug = item.get("slug")
        if not isinstance(slug, str) or not REGISTRY_SLUG_RE.fullmatch(slug):
            _add_error(errors, f"tech-stacks/registry.yaml: overlay row {index} has an invalid slug")
            continue
        if slug in rows:
            _add_error(errors, f"tech-stacks/registry.yaml: duplicate slug {slug!r}")
            continue

        row_valid = not missing and not extra
        expected_path = f"tech-stacks/{slug}.md"
        expected_source = f"_refs/global/tech-stacks/{slug}.md"
        if item.get("path") != expected_path:
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} path must be {expected_path}")
            row_valid = False
        if not isinstance(item.get("framework"), str) or not item["framework"].strip():
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} framework must be a string")
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
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} versions must be a non-empty finite number list")
            row_valid = False
        if item.get("source") != expected_source:
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} source must be {expected_source}")
            row_valid = False
        digest = item.get("sha256")
        if not isinstance(digest, str) or not REGISTRY_DIGEST_RE.fullmatch(digest):
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} sha256 must be a lowercase SHA-256 digest")
            row_valid = False

        overlay = catalog_root / expected_path
        source = catalog_root.parent / expected_source
        if not _safe_regular_file(overlay, catalog_root):
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} overlay file is missing or not regular")
            row_valid = False
        elif isinstance(digest, str) and REGISTRY_DIGEST_RE.fullmatch(digest):
            try:
                actual_digest = hashlib.sha256(overlay.read_bytes()).hexdigest()
            except OSError as exc:
                _add_error(errors, f"tech-stacks/registry.yaml: {slug} overlay cannot be read ({exc})")
                row_valid = False
            else:
                if actual_digest != digest:
                    _add_error(errors, f"tech-stacks/registry.yaml: {slug} overlay digest does not match sha256")
                    row_valid = False
        # The `source` column records provenance in the `_refs` authoring
        # workspace, which is not shipped with the catalog. Enforce it only
        # when that workspace is present; the shipped overlay plus its pinned
        # sha256 above remain the authority either way.
        source_workspace = catalog_root.parent / "_refs" / "global" / "tech-stacks"
        if source_workspace.is_dir() and not _safe_regular_file(source, catalog_root.parent):
            _add_error(errors, f"tech-stacks/registry.yaml: {slug} source file is missing or not regular")
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
        _script_uses_command(scripts, tool)
        for tool in ("vite", "next", "astro", "nuxt", "svelte", "webpack", "parcel")
    ) or _script_uses_subcommand(scripts, "ng", "serve")
    backend = bool(dependencies & (BACKEND_PACKAGE_NAMES | SSR_PACKAGE_NAMES)) or any(
        _script_uses_command(scripts, tool)
        for tool in ("uvicorn", "gunicorn", "flask", "django", "nest")
    ) or any(
        _script_uses_python_module(scripts, module)
        for module in ("uvicorn", "gunicorn", "flask", "django", "fastapi")
    ) or _script_uses_node_server(scripts)
    return frontend, backend


def _script_token_name(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1]
    name = re.split(r"[/\\]", token)[-1].lower()
    return re.sub(r"\.(?:cmd|exe|bat)$", "", name)


def _shell_tokens(value: str) -> list[str]:
    quoted_operators = {
        ";": "__SUPREMETEAM_QUOTED_SEMICOLON__",
        "&": "__SUPREMETEAM_QUOTED_AMPERSAND__",
        "|": "__SUPREMETEAM_QUOTED_PIPE__",
    }
    masked: list[str] = []
    quote: str | None = None
    escaped = False
    for char in value:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            masked.append(quoted_operators.get(char, char))
        elif char in {"'", '"'}:
            quote = char
            masked.append(char)
        elif char in "\r\n":
            masked.append(";")
        else:
            masked.append(char)
    lexer = shlex.shlex("".join(masked), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    return list(lexer)


def _expand_env_split(tokens: list[str]) -> list[str]:
    if not tokens or _script_token_name(tokens[0]) != "env":
        return tokens
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--" or not token.startswith("-"):
            break
        option = token.split("=", 1)[0].lower()
        if option in {"-s", "--split-string"}:
            if "=" in token:
                command = token.split("=", 1)[1]
                end = index + 1
            elif index + 1 < len(tokens):
                command = tokens[index + 1]
                end = index + 2
            else:
                return tokens
            return tokens[:index] + _shell_tokens(command) + tokens[end:]
        index += 1
    return tokens


def _script_segments(scripts: dict[str, str]) -> list[list[str]]:
    segments: list[list[str]] = []
    for value in scripts.values():
        try:
            tokens = _expand_env_split(_shell_tokens(value))
        except ValueError:
            continue
        segment: list[str] = []
        for token in [*tokens, ";"]:
            if token in {";", "&", "&&", "||", "|"}:
                if segment:
                    segments.append(segment)
                segment = []
            else:
                segment.append(token)
    return segments


def _skip_command_options(
    tokens: list[str],
    index: int,
    options_with_values: frozenset[str] = COMMAND_OPTIONS_WITH_VALUES,
) -> int:
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return index + 1
        if not token.startswith("-"):
            break
        option = token.split("=", 1)[0].lower()
        index += 1
        if "=" not in token and option in options_with_values and index < len(tokens):
            index += 1
    return index


def _has_lookup_option(
    tokens: list[str],
    index: int,
    options_with_values: frozenset[str] = COMMAND_OPTIONS_WITH_VALUES,
) -> bool:
    while index < len(tokens):
        token = tokens[index]
        if token == "--" or not token.startswith("-"):
            return False
        option = token.split("=", 1)[0].lower()
        if option in COMMAND_LOOKUP_OPTIONS:
            return True
        index += 1
        if "=" not in token and option in options_with_values and index < len(tokens):
            index += 1
    return False


def _script_command_index(tokens: list[str], index: int = 0, depth: int = 0) -> int:
    if depth > 8:
        return len(tokens)
    while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
        index += 1
    if index >= len(tokens):
        return index

    name = _script_token_name(tokens[index])
    if name == "env":
        index = _skip_command_options(tokens, index + 1, ENV_OPTIONS_WITH_VALUES)
        while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
            index += 1
        return _script_command_index(tokens, index, depth + 1)
    if name == "command":
        if _has_lookup_option(tokens, index + 1):
            return len(tokens)
        index = _skip_command_options(tokens, index + 1)
        return _script_command_index(tokens, index, depth + 1)
    if name == "exec":
        index = _skip_command_options(tokens, index + 1, EXEC_OPTIONS_WITH_VALUES)
        return _script_command_index(tokens, index, depth + 1)
    if name in {"npx", "bunx"}:
        if _has_lookup_option(tokens, index + 1):
            return len(tokens)
        index = _skip_command_options(tokens, index + 1)
        return _script_command_index(tokens, index, depth + 1)
    if name in {"bun", "npm", "pnpm", "yarn"}:
        options_with_values = PACKAGE_MANAGER_OPTIONS_WITH_VALUES[name]
        if _has_lookup_option(tokens, index + 1, options_with_values):
            return len(tokens)
        subcommand_index = _skip_command_options(tokens, index + 1, options_with_values)
        if subcommand_index >= len(tokens) or _script_token_name(tokens[subcommand_index]) not in {"exec", "dlx", "run"}:
            return len(tokens)
        if _has_lookup_option(tokens, subcommand_index + 1, options_with_values):
            return len(tokens)
        index = _skip_command_options(tokens, subcommand_index + 1, options_with_values)
        return _script_command_index(tokens, index, depth + 1)
    return index


def _script_uses_command(scripts: dict[str, str], command: str) -> bool:
    return any(
        index < len(tokens) and _script_token_name(tokens[index]) == command
        for tokens in _script_segments(scripts)
        for index in [_script_command_index(tokens)]
    )


def _script_uses_python_module(scripts: dict[str, str], module: str) -> bool:
    for tokens in _script_segments(scripts):
        index = _script_command_index(tokens)
        if index >= len(tokens) or _script_token_name(tokens[index]) not in {"python", "python3", "py"}:
            continue
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if token == "-m" and index + 1 < len(tokens):
                name = _script_token_name(tokens[index + 1])
                if name == module or name.startswith(module + "."):
                    return True
                break
            if not token.startswith("-"):
                break
            index += 1
    return False


def _script_uses_subcommand(scripts: dict[str, str], command: str, subcommand: str) -> bool:
    for tokens in _script_segments(scripts):
        raw_index = 0
        while raw_index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[raw_index]):
            raw_index += 1
        raw_name = _script_token_name(tokens[raw_index]) if raw_index < len(tokens) else ""
        options_with_values = PACKAGE_MANAGER_OPTIONS_WITH_VALUES.get(raw_name, COMMAND_OPTIONS_WITH_VALUES)
        lookup_only = raw_name in PACKAGE_MANAGER_OPTIONS_WITH_VALUES and _has_lookup_option(
            tokens, raw_index + 1, options_with_values
        )
        if raw_name == command and not lookup_only:
            raw_subcommand_index = _skip_command_options(tokens, raw_index + 1, options_with_values)
            if (
                raw_subcommand_index < len(tokens)
                and _script_token_name(tokens[raw_subcommand_index]) == subcommand
            ):
                if _has_lookup_option(tokens, raw_subcommand_index + 1, options_with_values):
                    continue
                return True
        index = _script_command_index(tokens)
        if index < len(tokens) and _script_token_name(tokens[index]) == command:
            if index + 1 < len(tokens) and _script_token_name(tokens[index + 1]) == subcommand:
                return True
    return False


def _script_uses_node_server(scripts: dict[str, str]) -> bool:
    node_options_with_values = frozenset(
        {"--eval", "--import", "--input-type", "--loader", "--print", "--require", "-e", "-p", "-r"}
    )
    for tokens in _script_segments(scripts):
        index = _script_command_index(tokens)
        if index >= len(tokens) or _script_token_name(tokens[index]) != "node":
            continue
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if token == "--":
                index += 1
                break
            if not token.startswith("-"):
                name = _script_token_name(token)
                return bool(re.search(r"(?i)(?:^|[/_.-])(server|api)(?:$|[/_.-])", name))
            option = token.split("=", 1)[0].lower()
            index += 1
            if "=" not in token and option in node_options_with_values:
                index += 1
    return False


def _validate_package_scripts(package: dict[str, Any], errors: list[str]) -> None:
    if "scripts" not in package:
        return
    scripts = package["scripts"]
    if not isinstance(scripts, dict):
        _add_error(errors, "package.json: scripts must be an object")
        return
    for name, command in scripts.items():
        if not isinstance(command, str):
            _add_error(errors, f"package.json:scripts.{name}: command must be a string")


def _makefile_runtime_recipe(recipe: str) -> bool:
    scripts = {"makefile": recipe}
    return (
        any(
            _script_uses_command(scripts, command)
            for command in (
                "bun", "cargo", "deno", "dotnet", "flask", "go", "gradle", "gunicorn",
                "java", "mvn", "node", "parcel", "pnpm", "python", "ruby", "uvicorn",
                "astro", "next", "nuxt", "svelte", "vite", "webpack", "yarn",
            )
        )
        or any(
            _script_uses_subcommand(scripts, manager, subcommand)
            for manager in ("bun", "npm", "pnpm", "yarn")
            for subcommand in ("dlx", "exec", "run")
        )
    )


def _makefile_recipe(lines: list[str], target: str, seen: set[str] | None = None) -> str | None:
    seen = set() if seen is None else seen
    if target in seen:
        return None
    seen.add(target)
    target_pattern = re.compile(rf"^\s*{re.escape(target)}\s*:(?P<inline>.*)$")
    for index, line in enumerate(lines):
        match = target_pattern.match(line)
        if not match:
            continue
        inline = match.group("inline").strip()
        if ";" in inline:
            recipe = inline.split(";", 1)[1].strip()
            if recipe:
                return re.sub(r"^[@+-]+\s*", "", recipe)
            prerequisites = inline.split(";", 1)[0].strip().split()
        else:
            prerequisites = inline.split()
        recipes: list[str] = []
        for candidate in lines[index + 1:]:
            if not candidate.strip():
                continue
            if not candidate[:1].isspace():
                break
            if candidate.lstrip().startswith("#"):
                continue
            recipe = re.sub(r"^[@+-]+\s*", "", candidate.strip())
            if recipe:
                recipes.append(recipe)
        for recipe in recipes:
            if _makefile_runtime_recipe(recipe):
                return recipe
        for prerequisite in prerequisites:
            recipe = _makefile_recipe(lines, prerequisite, seen)
            if recipe:
                return recipe
        return None
        return None
    return None


def _makefile_runtime_signals(text: str) -> tuple[bool, bool]:
    frontend = False
    backend = False
    lines = text.splitlines()
    for target in ("dev", "run", "serve"):
        recipe = _makefile_recipe(lines, target)
        if not recipe:
            continue
        scripts = {"makefile": recipe}
        frontend = frontend or any(_script_uses_command(scripts, tool) for tool in ("vite", "next", "astro", "nuxt", "svelte", "webpack", "parcel"))
        backend = backend or any(_script_uses_command(scripts, tool) for tool in ("uvicorn", "gunicorn", "flask", "django", "fastapi"))
        backend = backend or any(
            _script_uses_python_module(scripts, module)
            for module in ("uvicorn", "gunicorn", "flask", "django", "fastapi")
        )
        backend = backend or _script_uses_node_server(scripts)
    return frontend, backend


def _cargo_binary_targets(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> tuple[list[tuple[str, str]], str | None]:
    cargo_path = next(
        (path for path in files if path.parent == root and path.name.lower() == "cargo.toml"),
        None,
    )
    if cargo_path is None:
        return [], None
    relative_files = {
        _relative(path, root).lower(): _relative(path, root)
        for path in files
        if _path_class(_relative(path, root)) == "production"
    }
    text = _read_cached_text(cargo_path, root, errors, text_cache, required=True)
    if text is None:
        return [], None
    try:
        manifest = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, RecursionError) as exc:
        _add_error(errors, f"Cargo.toml: invalid TOML ({exc})")
        return [], None
    package = manifest.get("package")
    default_run = package.get("default-run") if isinstance(package, dict) else None
    package_name = package.get("name") if isinstance(package, dict) else None
    if not isinstance(package_name, str) or not package_name.strip():
        package_name = root.name

    targets: list[tuple[str, str]] = []
    target_indices: dict[str, int] = {}

    def add_target(relative: str, name: str, *, override_name: bool = False) -> None:
        normalized = relative.lower()
        if normalized not in relative_files:
            return
        if normalized in target_indices:
            if override_name:
                index = target_indices[normalized]
                targets[index] = (relative_files[normalized], name)
            return
        target_indices[normalized] = len(targets)
        targets.append((relative_files[normalized], name))

    if "src/main.rs" in relative_files:
        add_target("src/main.rs", package_name)
    for relative in sorted(relative_files):
        path = Path(relative)
        if path.suffix.lower() != ".rs" or not relative.lower().startswith("src/bin/"):
            continue
        if path.parent.as_posix().lower() == "src/bin":
            add_target(relative, path.stem)
        elif path.name.lower() == "main.rs" and path.parent.parent.as_posix().lower() == "src/bin":
            add_target(relative, path.parent.name)

    binaries = manifest.get("bin", [])
    if not isinstance(binaries, list):
        return targets, default_run if isinstance(default_run, str) else None

    def normalize_manifest_path(path: str) -> str | None:
        normalized = Path(path).as_posix()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if (
            not normalized
            or normalized.startswith(("../", "/"))
            or re.match(r"^[A-Za-z]:/", normalized)
        ):
            return None
        return normalized.lower()

    for binary in binaries:
        if not isinstance(binary, dict):
            continue
        path = binary.get("path")
        name = binary.get("name")
        if not isinstance(name, str) or not name.strip():
            name = Path(path).stem if isinstance(path, str) and path.strip() else None
        if not isinstance(path, str) or not path.strip():
            if not isinstance(name, str) or not name.strip():
                continue
            path = f"src/bin/{name}.rs"
        normalized = normalize_manifest_path(path)
        if normalized is not None:
            add_target(
                normalized,
                name if isinstance(name, str) else Path(normalized).stem,
                override_name=True,
            )
    return targets, default_run if isinstance(default_run, str) else None


def _cargo_binary_entry(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    targets, _ = _cargo_binary_targets(files, root, text_cache, errors)
    return targets[0][0] if targets else None


def _cargo_start_command(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    targets, default_run = _cargo_binary_targets(files, root, text_cache, errors)
    if not targets:
        return None
    if default_run and any(name == default_run for _, name in targets):
        return "cargo run"
    if len(targets) == 1:
        return "cargo run"
    return f"cargo run --bin {targets[0][1]}"


def _go_package_is_main(text: str) -> bool:
    code: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(text):
        char = text[index]
        if quote is not None:
            if quote == "`":
                if char == quote:
                    quote = None
                code.append("\n" if char == "\n" else " ")
                index += 1
                continue
            if char == "\\":
                code.extend((" ", " "))
                index += 2
                continue
            if char == quote:
                quote = None
            code.append("\n" if char == "\n" else " ")
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index)
            if newline == -1:
                break
            code.append("\n")
            index = newline + 1
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            if close == -1:
                code.extend("\n" if char == "\n" else " " for char in text[index:])
                break
            code.extend("\n" if char == "\n" else " " for char in text[index:close + 2])
            index = close + 2
            continue
        if char in {"'", '"', "`"}:
            quote = char
            code.append(" ")
            index += 1
            continue
        code.append(char)
        index += 1
    sanitized = "".join(code)
    return bool(re.search(r"(?m)^\s*package\s+main\b", sanitized)) and bool(
        re.search(r"\bfunc\s+main\s*\(\s*\)", sanitized)
    )


def _go_entrypoint(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    relative_files = {
        _relative(path, root)
        for path in files
        if _path_class(_relative(path, root)) == "production"
    }
    candidates = sorted(relative for relative in relative_files if relative.lower() == "main.go")
    candidates.extend(
        relative
        for relative in sorted(relative_files)
        if len(Path(relative).parts) == 3
        and relative.lower().startswith("cmd/")
        and Path(relative).name.lower() == "main.go"
    )
    relative_paths = {_relative(path, root): path for path in files}
    for relative in candidates:
        path = relative_paths.get(relative)
        if path is None:
            continue
        text = _read_cached_text(path, root, errors, text_cache, required=True)
        if text is not None and _go_package_is_main(text):
            return relative
    return None


def _go_start_command(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    entry = _go_entrypoint(files, root, text_cache, errors)
    if entry is None:
        return None
    directory = Path(entry).parent.as_posix()
    return "go run ." if directory == "." else f"go run ./{directory}"


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


def _start_commands(
    package: dict[str, Any],
    errors: list[str],
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
        package_relative = _relative(package_path, root)
        if not isinstance(scripts, dict):
            _add_error(errors, f"{package_relative}: scripts must be an object")
            continue
        for name in START_SCRIPT_ORDER:
            if name not in scripts:
                continue
            command = scripts[name]
            if not isinstance(command, str):
                _add_error(errors, f"{package_relative}:scripts.{name}: command must be a string")
                continue
            if command.strip():
                candidates.append(
                    {
                        "source": f"{package_relative}:scripts.{name}",
                        "path": package_relative,
                        "command": _redact(command),
                    }
                )
    if candidates:
        return candidates

    root_files = {
        path.name.lower(): path
        for path in files
        if path.parent == root and not _is_sensitive(path, root)
    }
    makefiles = sorted(
        path
        for path in files
        if (
            path.name.lower() == "makefile"
            and not _is_sensitive(path, root)
            and _path_class(_relative(path, root)) == "production"
        )
    )
    make_candidates: list[dict[str, str]] = []
    for makefile in makefiles:
        text = _read_cached_text(makefile, root, errors, text_cache, required=True) or ""
        lines = text.splitlines()
        relative_makefile = _relative(makefile, root)
        for target in ("dev", "run", "serve"):
            body = _makefile_recipe(lines, target)
            if body:
                make_candidates.append(
                    {
                        "source": f"{relative_makefile}:{target}",
                        "path": relative_makefile,
                        "command": _redact(body),
                    }
                )
                break
    if make_candidates:
        return make_candidates

    for compose_name in sorted(COMPOSE_NAMES):
        compose = root_files.get(compose_name)
        if not compose:
            continue
        compose_data = _load_cached_data(compose, root, errors, text_cache)
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
                    "command": _redact(command),
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
            text = _read_cached_text(root_files[filename], root, errors, text_cache, required=True)
            if text and _python_imports_module(text, PYTHON_WEB_MODULES):
                defaults.append((f"{filename}:default", filename, f"python {filename}"))
                break
    go_command = _go_start_command(files, root, text_cache, errors) if "go.mod" in root_files else None
    if go_command:
        defaults.append(("go.mod:default", "go.mod", go_command))
    cargo_command = _cargo_start_command(files, root, text_cache, errors)
    if cargo_command:
        defaults.append(("Cargo.toml:default", "Cargo.toml", cargo_command))
    if "pom.xml" in root_files:
        defaults.append(("pom.xml:default", "pom.xml", "mvn spring-boot:run"))
    if "build.gradle" in root_files or "build.gradle.kts" in root_files:
        filename = "build.gradle" if "build.gradle" in root_files else "build.gradle.kts"
        defaults.append((f"{filename}:default", filename, "./gradlew bootRun"))
    return [
        {"source": source, "path": path, "command": _redact(command)}
        for source, path, command in defaults[:1]
    ]


def _stack_evidence(path: str, reason: str) -> dict[str, str]:
    return {"path": path, "reason": reason}


def _detect_stacks(
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
        merged: dict[str, dict[str, Any]] = {}
        for package_path, package_value in packages:
            package_root = package_path.parent
            scoped_files = []
            for path in files:
                try:
                    path.relative_to(package_root)
                except ValueError:
                    continue
                scoped_files.append(path)
            for stack in _detect_stacks(
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
                            "path": _relative(evidence_path, root),
                            "reason": evidence["reason"],
                        }
                    )
        result = []
        for slug in sorted(merged):
            row = merged[slug]
            row["evidence"] = sorted(
                {(item["path"], item["reason"]): item for item in row["evidence"]}.values(),
                key=lambda item: (item["path"], item["reason"]),
            )
            result.append(row)
        return result

    relative_paths = {
        _relative(path, root): path
        for path in files
        if _path_class(_relative(path, root)) == "production"
    }
    root_paths = {
        relative: path
        for relative, path in relative_paths.items()
        if "/" not in relative
    }
    dependencies = _package_dependencies(package)
    scripts = _package_scripts(package)
    matches: dict[str, list[dict[str, str]]] = {}

    def add(slug: str, *evidence: dict[str, str]) -> None:
        if slug not in registry:
            _add_error(errors, f"detected stack {slug} has no registry entry")
            return
        matches.setdefault(slug, []).extend(evidence)

    def root_named(name: str) -> str | None:
        for relative in root_paths:
            if relative.lower() == name.lower():
                return relative
        return None

    def paths_starting(prefix: str) -> list[str]:
        return sorted(
            relative
            for relative in relative_paths
            if Path(relative).name.lower().startswith(prefix.lower())
        )

    package_relative = root_named("package.json")
    vite_configs = paths_starting("vite.config.")
    vite_script = _script_uses_command(scripts, "vite")
    if "vite" in dependencies or vite_script or vite_configs:
        if package_relative and ("vite" in dependencies or vite_script):
            add("vite-spa", _stack_evidence(package_relative, "package.json contains Vite evidence"))
        for relative in vite_configs:
            add("vite-spa", _stack_evidence(relative, "Vite project configuration"))

    next_configs = paths_starting("next.config.")
    if "next" in dependencies or next_configs:
        evidence_path = package_relative or next_configs[0]
        add("react-nextjs", _stack_evidence(evidence_path, "package.json or Next.js configuration contains Next.js evidence"))

    angular_config = root_named("angular.json")
    if "@angular/core" in dependencies or angular_config:
        add("angular", _stack_evidence(package_relative or angular_config, "package.json or angular.json contains Angular evidence"))

    astro_configs = paths_starting("astro.config.")
    if "astro" in dependencies or astro_configs:
        add("astro", _stack_evidence(package_relative or astro_configs[0], "package.json or Astro configuration contains Astro evidence"))

    svelte_configs = paths_starting("svelte.config.")
    if "@sveltejs/kit" in dependencies or svelte_configs:
        add("svelte-sveltekit", _stack_evidence(package_relative or svelte_configs[0], "package.json or Svelte configuration contains SvelteKit evidence"))

    nuxt_configs = paths_starting("nuxt.config.")
    if "nuxt" in dependencies or nuxt_configs:
        add("vue-nuxt", _stack_evidence(package_relative or nuxt_configs[0], "package.json or Nuxt configuration contains Nuxt evidence"))

    if package_relative:
        if "@tanstack/start" in dependencies:
            add("react-tanstack", _stack_evidence(package_relative, "package.json contains TanStack Start evidence"))

        if (
            root_named("tsconfig.json")
            and ("typescript" in dependencies or any(Path(relative).suffix.lower() in {".ts", ".tsx"} for relative in relative_paths))
            and not matches.keys() & FRONTEND_STACKS
        ):
            add("node-typescript", _stack_evidence(package_relative, "TypeScript package and source evidence"))

    if any(Path(relative).name.lower() in {"bun.lock", "bun.lockb", "bunfig.toml"} for relative in root_paths):
        if root_named("tsconfig.json") or any(Path(relative).suffix.lower() in {".ts", ".tsx"} for relative in relative_paths):
            add("bun-typescript", _stack_evidence(
                next(relative for relative in root_paths if Path(relative).name.lower() in {"bun.lock", "bun.lockb", "bunfig.toml"}),
                "Bun lock or configuration with TypeScript evidence",
            ))

    deno_relative = next(
        (relative for relative in root_paths if Path(relative).name.lower() in {"deno.json", "deno.jsonc"}),
        None,
    )
    if deno_relative:
        add("deno-typescript", _stack_evidence(deno_relative, "Deno configuration"))

    for filename in ("main.py", "app.py"):
        relative = root_named(filename)
        if not relative:
            continue
        path = root_paths[relative]
        text = _read_cached_text(path, root, errors, text_cache, required=True)
        if text and _python_imports_module(text, PYTHON_FASTAPI_MODULES):
            add("python-fastapi", _stack_evidence(relative, "Python web runtime import evidence"))

    go_mod = root_named("go.mod")
    go_entry = _go_entrypoint(files, root, text_cache, errors)
    if go_mod and go_entry:
        text = _read_cached_text(root_paths[go_mod], root, errors, text_cache, required=True) or ""
        if re.search(r"(?i)(?:gin-gonic/gin|/gin\b)", text):
            add("go-gin", _stack_evidence(go_mod, "Go module declares Gin"), _stack_evidence(go_entry, "Go executable entrypoint"))

    cargo = root_named("cargo.toml")
    rust_entry = _cargo_binary_entry(files, root, text_cache, errors) if cargo else None
    if cargo and rust_entry:
        text = _read_cached_text(root_paths[cargo], root, errors, text_cache, required=True) or ""
        if re.search(r"(?i)\baxum\b", text):
            add("rust-axum", _stack_evidence(cargo, "Cargo manifest declares Axum"), _stack_evidence(rust_entry, "Rust executable entrypoint"))

    csproj = next(
        (relative for relative in root_paths if Path(relative).suffix.lower() in {".csproj", ".fsproj", ".vbproj"}),
        None,
    )
    if csproj:
        text = _read_cached_text(root_paths[csproj], root, errors, text_cache, required=True) or ""
        if re.search(r"(?i)(?:Microsoft\.AspNetCore|Microsoft.NET.Sdk.Web|AspNetCore)", text):
            add("dotnet-aspnet", _stack_evidence(csproj, ".NET web project manifest"))

    result: list[dict[str, Any]] = []
    for slug in sorted(matches):
        evidence = sorted(
            {
                (item["path"], item["reason"]): item
                for item in matches[slug]
            }.values(),
            key=lambda item: (item["path"], item["reason"]),
        )
        row = registry[slug]
        result.append(
            {
                "slug": slug,
                "framework": row.get("framework"),
                "versions": row.get("versions", []),
                "evidence": evidence,
            }
        )
    return result


def _path_class(relative: str) -> str:
    parts = [part.lower() for part in relative.split("/")]
    name = parts[-1]
    if (
        name.startswith("readme")
        or Path(name).suffix.lower() in {".adoc", ".md", ".rst"}
        or bool(set(parts[:-1]) & {"doc", "docs", "documentation", "example", "examples"})
    ):
        return "documentation"
    if (
        bool(set(parts[:-1]) & TEST_DIRECTORY_NAMES)
        or name in {"test.py", "tests.py", "spec.py", "specs.py"}
        or name.startswith(("test_", "test.", "spec_", "spec."))
        or name.endswith(("_test.py", "_test.js", "_test.ts", "_test.tsx", "_spec.py", "_spec.rb"))
        or bool(re.search(r"(?:^|[._-])(test|spec)(?:[._-]|$)", name))
    ):
        return "test"
    if bool(set(parts[:-1]) & {"build", "coverage", "dist", "generated", "out", "vendor"}):
        return "generated-or-vendored"
    return "production"


def _language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}:
        return "javascript"
    if suffix == ".go":
        return "go"
    if suffix == ".rs":
        return "rust"
    if suffix == ".cs":
        return "csharp"
    if suffix == ".java":
        return "java"
    if suffix == ".rb":
        return "ruby"
    if suffix in {".sh", ".bash", ".zsh"} or path.name.lower() == "makefile":
        return "shell"
    return None


def _canonical_marker(value: str) -> str:
    return " ".join(value.upper().split())


def _without_quoted_strings(line: str) -> str:
    return _without_quoted_strings_lines([line])[0]


def _without_quoted_strings_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    quote: str | None = None
    block_comment = False
    escaped = False
    for line in lines:
        clean_line: list[str] = []
        index = 0
        while index < len(line):
            if block_comment:
                close = line.find("*/", index)
                if close == -1:
                    clean_line.extend(line[index:])
                    index = len(line)
                    continue
                clean_line.extend(line[index:close + 2])
                index = close + 2
                block_comment = False
                continue
            if quote:
                if len(quote) == 3 and line.startswith(quote, index):
                    clean_line.extend(" " for _ in quote)
                    index += len(quote)
                    quote = None
                    escaped = False
                    continue
                char = line[index]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif len(quote) == 1 and char == quote:
                    quote = None
                clean_line.append(" ")
                index += 1
                continue
            if line[index] == "#" or line.startswith("//", index):
                clean_line.extend(line[index:])
                break
            if line.startswith("/*", index):
                clean_line.extend("/*")
                index += 2
                block_comment = True
                continue
            if line.startswith("'''", index) or line.startswith('"""', index):
                quote = line[index:index + 3]
                clean_line.extend(" " for _ in quote)
                index += 3
            elif line[index] in {"'", '"', "`"}:
                quote = line[index]
                clean_line.append(" ")
                index += 1
            else:
                clean_line.append(line[index])
                index += 1
        result.append("".join(clean_line))
    return result


def _line_matches(line: str, language: str | None, code_line: str | None = None) -> list[str]:
    markers: list[str] = []

    def add(value: str) -> None:
        marker = _canonical_marker(value)
        if marker not in markers:
            markers.append(marker)

    code_line = code_line if code_line is not None else _without_quoted_strings(line)
    comment_match = COMMENT_MARKER_PATTERN.search(code_line)
    if comment_match:
        add(comment_match.group(1))
    for match in MARKER_PATTERN.finditer(code_line):
        add(match.group(1))

    patterns: list[tuple[re.Pattern[str], str]] = []
    if language == "python":
        patterns = [
            (re.compile(r"\braise\s+NotImplementedError\b"), "NOT IMPLEMENTED"),
            (re.compile(r"\bdef\s+\w+\([^)]*\):\s*(?:pass|\.\.\.)\s*$"), "EMPTY FUNCTION"),
            (re.compile(r"\bexcept(?:\s+\w+)?\s*:\s*pass\s*$"), "EMPTY ERROR HANDLER"),
            (re.compile(r"(?<!\w)print\("), "DEBUG STATEMENT"),
        ]
    elif language == "javascript":
        patterns = [
            (re.compile(r"throw\s+new\s+Error\s*\(\s*[\"']not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\bfunction\s+\w+\([^)]*\)(?:\s*:\s*[^{}]+)?\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"=>\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"(?m)^\s*(?:(?:(?:public|private|protected|static|abstract|async|get|set|override)\s+)*"
                         r"(?!if\b|for\b|while\b|switch\b|catch\b)[A-Za-z_$][\w$]*\s*\([^)]*\)"
                         r"(?:\s*:\s*[^{}]+)?)\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), "EMPTY ERROR HANDLER"),
            (re.compile(r"console\.(?:log|debug|info|warn|error)\("), "DEBUG STATEMENT"),
        ]
    elif language == "go":
        patterns = [
            (re.compile(r"panic\s*\(\s*[\"']not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?\w+\([^)]*\)\s*(?:\([^)]*\)\s*)?\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"fmt\.Print(?:ln|f)?\("), "DEBUG STATEMENT"),
            (re.compile(r"^\s*(?:defer\s+)?recover\(\)\s*;?\s*$"), "EMPTY ERROR HANDLER"),
        ]
    elif language == "rust":
        patterns = [
            (re.compile(r"\b(?:todo|unimplemented)!\(\)"), "NOT IMPLEMENTED"),
            (re.compile(r"\bdbg!\("), "DEBUG STATEMENT"),
            (re.compile(r"\blet\s+_\s*=\s*"), "IGNORED RESULT"),
        ]
    elif language == "csharp":
        patterns = [
            (re.compile(r"\bthrow\s+new\s+NotImplementedException\b"), "NOT IMPLEMENTED"),
            (re.compile(r"\bthrow\s+new\s+NotSupportedException\([^)]*not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\b(?:public|private|protected|internal)\b[^{};]*\([^)]*\)\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"Console\.Write(?:Line)?\("), "DEBUG STATEMENT"),
        ]
    elif language == "java":
        patterns = [
            (re.compile(r"\bthrow\s+new\s+UnsupportedOperationException\([^)]*not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\b(?:public|private|protected)\b[^{};]*\([^)]*\)\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"System\.out\.print"), "DEBUG STATEMENT"),
        ]
    elif language == "ruby":
        patterns = [
            (re.compile(r"\braise\s+NotImplementedError\b"), "NOT IMPLEMENTED"),
            (re.compile(r"^\s*def\s+\w+[^;]*;\s*(?:nil|\.\.\.)\s*;\s*end\s*$"), "EMPTY FUNCTION"),
            (re.compile(r"\b(?:puts|p)\s+"), "DEBUG STATEMENT"),
        ]
    elif language == "shell":
        patterns = [
            (re.compile(r"\b(?:echo|printf)\b.*\b(?:TODO|PLACEHOLDER|STUB)\b", re.I), "UNFINISHED OUTPUT"),
        ]
    for pattern, marker in patterns:
        if pattern.search(code_line):
            add(marker)

    if re.search(r"(?i)lorem\s+ipsum|dolor\s+sit\s+amet", code_line):
        add("FILLER PROSE")
    if re.search(r"(?i)\b(?:example|test)\.(?:com|org|net)\b", code_line):
        add("PLACEHOLDER DOMAIN")
    if re.search(r"(?i)\b(?:password|secret)\s*[:=]\s*[\"']?(?:password|secret)", code_line):
        add("DEFAULT SECRET")
    if re.search(r"(?i)\b(?:key)\s*[:=]\s*[\"']?changeme\b", code_line):
        add("DEFAULT SECRET")
    if re.search(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)\b", code_line):
        add("LOCALHOST ADDRESS")
    for pattern, marker in (
        (re.compile(r"\breturn\s*\[\s*\](?![\w.])"), "RETURN []"),
        (re.compile(r"\breturn\s*\{\s*\}(?![\w.])"), "RETURN {}"),
        (re.compile(r"\breturn\s+null\b", re.I), "RETURN NULL"),
        (re.compile(r"\breturn\s+None\b"), "RETURN NONE"),
        (re.compile(r"\breturn\s+0(?![\w.])"), "RETURN 0"),
    ):
        if pattern.search(code_line):
            add(marker)
    if language == "shell" and re.match(r"^\s*exit\s+0\b", code_line):
        add("EXIT 0")
    return markers


def _comment_only(line: str, language: str | None) -> bool:
    stripped = line.strip()
    if language == "python":
        return stripped.startswith("#")
    return stripped.startswith(("//", "/*", "*", "*/"))


def _block_matches(
    lines: list[str],
    index: int,
    language: str | None,
    code_lines: list[str] | None = None,
) -> list[tuple[str, str]]:
    detection_lines = code_lines if code_lines is not None else lines
    line = detection_lines[index]
    source_line = lines[index]

    if language == "python" and re.match(
        r"^\s*(?:async\s+)?def\s+\w+\([^)]*\)(?:\s*->\s*[^:\n]+)?\s*:\s*(?:pass|\.\.\.)(?:\s*#.*)?$",
        line,
    ):
        return [("EMPTY FUNCTION", source_line)]

    if language == "python" and re.match(
        r"^\s*(?:async\s+)?def\s+\w+\([^)]*\)(?:\s*->\s*[^:\n]+)?\s*:\s*(?:#.*)?$",
        line,
    ):
        header_indent = len(line) - len(line.lstrip())
        body_index = index + 1
        while body_index < len(detection_lines) and (
            not detection_lines[body_index].strip() or detection_lines[body_index].lstrip().startswith("#")
        ):
            body_index += 1
        if body_index < len(detection_lines):
            body_line = detection_lines[body_index]
            body_indent = len(body_line) - len(body_line.lstrip())
            if body_indent > header_indent and re.fullmatch(
                r"(?:pass|\.\.\.)(?:\s*#.*)?",
                body_line.strip(),
            ):
                next_index = body_index + 1
                has_more_body = False
                while next_index < len(detection_lines):
                    candidate = detection_lines[next_index]
                    if not candidate.strip() or _comment_only(candidate, language):
                        next_index += 1
                        continue
                    if len(candidate) - len(candidate.lstrip()) > header_indent:
                        has_more_body = True
                        break
                    if candidate.strip():
                        break
                    next_index += 1
                if not has_more_body:
                    return [("EMPTY FUNCTION", "\n".join(lines[index:body_index + 1]))]

    def empty_brace_block(header_pattern: str) -> tuple[str, str] | None:
        inline = re.match(
            r"^(?P<header>.*\{)\s*(?P<body>//.*|/\*.*\*/)?\s*\}\s*;?\s*$",
            line,
        )
        if inline and (inline.group("body") is None or _comment_only(inline.group("body"), language)):
            if re.match(header_pattern, inline.group("header")):
                return "EMPTY FUNCTION", source_line
        if not re.match(header_pattern, line):
            return None
        open_index = index
        if "{" not in line:
            open_index = next(
                (
                    candidate
                    for candidate in range(index + 1, min(len(detection_lines), index + 21))
                    if detection_lines[candidate].strip()
                ),
                -1,
            )
            if open_index == -1 or detection_lines[open_index].strip() != "{":
                return None
        close_index = next(
            (
                candidate
                for candidate in range(open_index + 1, min(len(detection_lines), open_index + 21))
                if detection_lines[candidate].strip() in {"}", "};"}
            ),
            None,
        )
        if close_index is None:
            return None
        if any(
            detection_lines[candidate].strip() and not _comment_only(detection_lines[candidate], language)
            for candidate in range(open_index + 1, close_index)
        ):
            return None
        return "EMPTY FUNCTION", "\n".join(lines[index:close_index + 1])

    if language == "javascript":
        block = empty_brace_block(
            r"^\s*(?:"
            r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+\w+\([^)]*\)(?:\s*:\s*[^{}]+)?|"
            r"(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)"
            r"(?:\s*:\s*[^{}]+)?\s*=>|"
            r"(?:(?:public|private|protected|static|abstract|async|get|set|override)\s+)*"
            r"(?!if\b|for\b|while\b|switch\b|catch\b)[A-Za-z_$][\w$]*\s*\([^)]*\)"
            r"(?:\s*:\s*[^{}]+)?"
            r")\s*(?:\{\s*)?$"
        )
        if block:
            return [block]

    if language == "go":
        block = empty_brace_block(
            r"^\s*func\s+(?:\([^)]*\)\s*)?\w+\([^)]*\)(?:\s*\([^)]*\))?(?:\s+[^{}]+)?\s*(?:\{\s*)?$"
        )
        if block:
            return [block]

    if language in {"csharp", "java"}:
        visibility = "public|private|protected|internal" if language == "csharp" else "public|private|protected"
        block = empty_brace_block(
            rf"^\s*(?:{visibility})\b[^{{}};]*\([^)]*\)\s*(?:\{{\s*)?$"
        )
        if block:
            return [block]

    if language == "ruby" and re.match(r"^\s*def\s+\w+", detection_lines[index]):
        end = next(
            (
                candidate
                for candidate in range(index + 1, min(len(detection_lines), index + 21))
                if detection_lines[candidate].strip() == "end"
            ),
            None,
        )
        if end is not None:
            body = [
                line.strip()
                for line in detection_lines[index + 1:end]
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if body in (["nil"], ["..."]):
                return [("EMPTY FUNCTION", "\n".join(lines[index:end + 1]))]

    if language == "shell" and re.match(
        r"^\s*(?:(?:function\s+)?[A-Za-z_][A-Za-z0-9_-]*\s*(?:\(\s*\))?)\s*\{\s*$",
        detection_lines[index],
    ):
        end = next(
            (
                candidate
                for candidate in range(index + 1, min(len(detection_lines), index + 21))
                if detection_lines[candidate].strip() == "}"
            ),
            None,
        )
        if end is not None:
            body = [
                line.strip()
                for line in detection_lines[index + 1:end]
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if body and all(item in {":", "true"} for item in body):
                return [("EMPTY FUNCTION", "\n".join(lines[index:end + 1]))]
    if language == "shell":
        inline = re.match(
            r"^\s*(?:(?:function\s+)?[A-Za-z_][A-Za-z0-9_-]*\s*(?:\(\s*\))?)\s*"
            r"\{(?P<body>.*?)\}\s*$",
            line,
        )
        if inline:
            body = [item.strip() for item in inline.group("body").split(";") if item.strip()]
            if body and all(item in {":", "true"} for item in body):
                return [("EMPTY FUNCTION", source_line)]
    return []


def _scan_scaffold(files: list[Path], root: Path, errors: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cache: dict[Path, str | None] = {}
    for path in files:
        if _is_sensitive(path, root) or not _is_text_path(path):
            continue
        relative = _relative(path, root)
        text = _read_cached_text(path, root, errors, cache, required=True)
        if text is None:
            continue
        path_class = _path_class(relative)
        language = _language(path)
        lines = text.splitlines()
        code_lines = _without_quoted_strings_lines(lines)
        for line_index, line in enumerate(lines):
            matches = [(marker, line) for marker in _line_matches(line, language, code_lines[line_index])]
            matches.extend(_block_matches(lines, line_index, language, code_lines))
            seen: set[str] = set()
            for marker, raw_context in matches:
                if marker in seen:
                    continue
                seen.add(marker)
                context = _redact(raw_context.strip())
                findings.append(
                    {
                        "file": relative,
                        "line": line_index + 1,
                        "marker": marker,
                        "message": context,
                        "context": context,
                        "path_class": path_class,
                        "production_finding": path_class == "production",
                    }
                )
    findings.sort(key=lambda item: (item["file"], item["line"], item["marker"], item["message"]))
    return findings


def _classify_project(
    files: list[Path],
    root: Path,
    package: dict[str, Any],
    stacks: list[dict[str, Any]],
    text_cache: dict[Path, str | None],
    errors: list[str],
    *,
    packages: list[tuple[Path, dict[str, Any]]] | None = None,
) -> tuple[str, list[dict[str, str]], list[str]]:
    relative_paths = {_relative(path, root): path for path in files}
    root_paths = {
        relative: path for relative, path in relative_paths.items() if "/" not in relative
    }
    stack_slugs = {str(item["slug"]) for item in stacks}
    classification_evidence: list[dict[str, str]] = []
    ambiguities: list[str] = []

    compose = next(
        (
            (relative, path)
            for relative, path in root_paths.items()
            if Path(relative).name.lower() in COMPOSE_NAMES
        ),
        None,
    )
    if compose:
        compose_data = _load_cached_data(compose[1], root, errors, text_cache)
        services = compose_data.get("services") if isinstance(compose_data, dict) else None
        if isinstance(services, dict):
            classification_evidence.append(_stack_evidence(compose[0], "compose services definition"))
            if any(_compose_service_has_ports(service) for service in services.values()):
                return "container-orchestrated", classification_evidence, ambiguities
            ambiguities.append("compose services were found without a ports mapping")

    makefile_paths = sorted(
        path
        for path in files
        if (
            path.name.lower() == "makefile"
            and not _is_sensitive(path, root)
            and _path_class(_relative(path, root)) == "production"
        )
    )
    makefile_frontend = False
    makefile_backend = False
    makefile_evidence: list[dict[str, str]] = []
    for path in makefile_paths:
        relative = _relative(path, root)
        makefile_text = _read_cached_text(path, root, errors, text_cache, required=True) or ""
        frontend, backend = _makefile_runtime_signals(makefile_text)
        makefile_frontend = makefile_frontend or frontend
        makefile_backend = makefile_backend or backend
        if frontend or backend:
            makefile_evidence.append(_stack_evidence(relative, "Makefile runtime command"))

    root_package_path = next(
        ((relative, path) for relative, path in root_paths.items() if Path(relative).name.lower() == "package.json"),
        None,
    )
    if packages and (len(packages) > 1 or root_package_path is None):
        frontend = bool(stack_slugs & FRONTEND_STACKS) or makefile_frontend
        backend = makefile_backend
        for package_path, package_value in packages:
            package_frontend, package_backend = _package_classification_signals(package_value)
            frontend = frontend or package_frontend
            backend = backend or package_backend
            classification_evidence.append(
                _stack_evidence(_relative(package_path, root), "package.json service manifest")
            )
        classification_evidence.extend(makefile_evidence)
        if frontend and backend:
            return "full-stack", classification_evidence, ambiguities
        if frontend:
            return "frontend-only", classification_evidence, ambiguities
        if backend:
            return "backend-only", classification_evidence, ambiguities

    package_path = root_package_path
    if package_path:
        scripts = _package_scripts(package)
        dependencies = _package_dependencies(package)
        frontend = bool(stack_slugs & FRONTEND_STACKS) or bool(
            dependencies & (FRONTEND_PACKAGE_NAMES | FRONTEND_TOOL_PACKAGE_NAMES | SSR_PACKAGE_NAMES)
        ) or any(
            _script_uses_command(scripts, tool)
            for tool in ("vite", "next", "astro", "nuxt", "svelte", "webpack", "parcel")
        ) or _script_uses_subcommand(scripts, "ng", "serve") or makefile_frontend
        backend = bool(dependencies & (BACKEND_PACKAGE_NAMES | SSR_PACKAGE_NAMES)) or any(
            _script_uses_command(scripts, tool)
            for tool in ("uvicorn", "gunicorn", "flask", "django", "nest")
        ) or any(
            _script_uses_python_module(scripts, module)
            for module in ("uvicorn", "gunicorn", "flask", "django", "fastapi")
        ) or _script_uses_node_server(scripts) or makefile_backend
        classification_evidence.extend(makefile_evidence)
        classification_evidence.append(_stack_evidence(package_path[0], "root package.json"))
        if frontend and backend:
            return "full-stack", classification_evidence, ambiguities
        if frontend:
            return "frontend-only", classification_evidence, ambiguities
        if backend:
            return "backend-only", classification_evidence, ambiguities
        return "library/CLI", classification_evidence, ambiguities

    if stack_slugs & FRONTEND_STACKS:
        classification_evidence.extend(makefile_evidence)
        if makefile_backend:
            return "full-stack", classification_evidence, ambiguities
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
        return "frontend-only", classification_evidence, ambiguities

    manage = next((relative for relative in root_paths if Path(relative).name.lower() == "manage.py"), None)
    if manage:
        classification_evidence.append(_stack_evidence(manage, "Django management entrypoint"))
        return "backend-only", classification_evidence, ambiguities

    web_entry = None
    for filename in ("main.py", "app.py"):
        relative = next((item for item in root_paths if Path(item).name.lower() == filename), None)
        if relative:
            text = _read_cached_text(root_paths[relative], root, errors, text_cache, required=True) or ""
            if _python_imports_module(text, PYTHON_WEB_MODULES):
                web_entry = relative
                break
    if web_entry:
        classification_evidence.append(_stack_evidence(web_entry, "Python web runtime import"))
        return "backend-only", classification_evidence, ambiguities

    go_mod = next((relative for relative in root_paths if Path(relative).name.lower() == "go.mod"), None)
    go_entry = _go_entrypoint(files, root, text_cache, errors)
    if go_mod and go_entry:
        classification_evidence.extend(
            (_stack_evidence(go_mod, "Go module manifest"), _stack_evidence(go_entry, "Go executable entrypoint"))
        )
        text = _read_cached_text(relative_paths[go_entry], root, errors, text_cache, required=True) or ""
        return ("backend-only" if re.search(r"(?i)(?:net/http|gin-gonic|echo|fiber)", text) else "library/CLI"), classification_evidence, ambiguities

    cargo = next((relative for relative in root_paths if Path(relative).name.lower() == "cargo.toml"), None)
    rust_entry = _cargo_binary_entry(files, root, text_cache, errors) if cargo else None
    if cargo and rust_entry:
        classification_evidence.extend(
            (_stack_evidence(cargo, "Rust package manifest"), _stack_evidence(rust_entry, "Rust executable entrypoint"))
        )
        manifest_text = _read_cached_text(root_paths[cargo], root, errors, text_cache, required=True) or ""
        entry_text = _read_cached_text(relative_paths[rust_entry], root, errors, text_cache, required=True) or ""
        text = f"{manifest_text}\n{entry_text}"
        return ("backend-only" if re.search(r"(?i)\b(?:axum|actix|warp|rocket|hyper)\b", text) else "library/CLI"), classification_evidence, ambiguities

    java_manifest = next(
        (relative for relative in root_paths if Path(relative).name.lower() in {"pom.xml", "build.gradle", "build.gradle.kts"}),
        None,
    )
    if java_manifest:
        classification_evidence.append(_stack_evidence(java_manifest, "Java build manifest"))
        text = _read_cached_text(root_paths[java_manifest], root, errors, text_cache, required=True) or ""
        return ("backend-only" if re.search(r"(?i)(?:spring|servlet|jetty|micronaut)", text) else "library/CLI"), classification_evidence, ambiguities

    if makefile_frontend or makefile_backend:
        classification_evidence.extend(makefile_evidence)
        if makefile_frontend and makefile_backend:
            return "full-stack", classification_evidence, ambiguities
        return "frontend-only" if makefile_frontend else "backend-only", classification_evidence, ambiguities

    ambiguities.append("no supported runtime classification signal was found")
    return "library/CLI", classification_evidence, ambiguities


def _inspect_project(
    catalog_root: Path,
    project_root: Path,
    *,
    detect_project: bool,
    detect_start_command: bool,
    scan_scaffold: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    try:
        requested_root = project_root.expanduser().absolute()
        if _has_reparse_ancestor(requested_root):
            _add_error(errors, "project root: reparse points are not inspected")
            project_root = requested_root
        else:
            project_root = requested_root.resolve()
    except (OSError, ValueError) as exc:
        _add_error(errors, f"project root cannot be inspected ({exc})")
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
        "ok": True,
    }
    if errors:
        pass
    elif not project_root.exists():
        _add_error(errors, "project root does not exist")
    elif not project_root.is_dir():
        _add_error(errors, "project root is not a directory")
    else:
        files = _walk_project(project_root, errors)
        manifests, configs = _collect_evidence(files, project_root)
        inspection["manifests"] = manifests
        inspection["configs"] = configs
        text_cache: dict[Path, str | None] = {}
        if detect_project:
            for path in files:
                if not _is_sensitive(path, project_root) and _is_text_path(path):
                    _read_cached_text(path, project_root, errors, text_cache, required=True)
        package: dict[str, Any] = {}
        package_records: list[tuple[Path, dict[str, Any]]] = []
        if detect_project or detect_start_command:
            package_paths = sorted(
                path
                for path in files
                if path.name.lower() == "package.json"
                and _path_class(_relative(path, project_root)) == "production"
            )
            for path in package_paths:
                package_value = _read_package(path, project_root, errors, text_cache)
                _validate_package_scripts(package_value, errors)
                package_records.append((path, package_value))
                if path.parent == project_root:
                    package = package_value
        if detect_project:
            registry = _load_registry(catalog_root, errors)
            stacks = _detect_stacks(
                registry,
                files,
                project_root,
                package,
                text_cache,
                errors,
                packages=package_records or None,
            )
            classification, classification_evidence, ambiguities = _classify_project(
                files,
                project_root,
                package,
                stacks,
                text_cache,
                errors,
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
                files=files,
                root=project_root,
                text_cache=text_cache,
                packages=package_records or None,
            )
        if scan_scaffold:
            inspection["scaffold_markers"] = _scan_scaffold(files, project_root, errors)
    inspection["errors"] = sorted(set(errors))
    inspection["ok"] = not inspection["errors"]
    return inspection


def check(
    root: Path,
    *,
    project_root: Path | None = None,
    detect_project: bool = False,
    detect_start_command: bool = False,
    scan_scaffold: bool = False,
) -> dict:
    requested_root = root.expanduser().absolute()
    if _has_reparse_ancestor(requested_root):
        errors: list[str] = []
        _add_error(errors, "catalog root: reparse points are not inspected")
        return _redact_value(_runtime_error_report(errors))
    root = requested_root.resolve()
    manifest_path = root / "runtime-manifest.yaml"
    try:
        manifest = load_data(manifest_path)
    except (DataFormatError, UnicodeError, ValueError, RecursionError) as exc:
        errors: list[str] = []
        _add_error(errors, str(exc))
        return _redact_value(_runtime_error_report(errors))
    minimum_value, minimum, optional_dependencies, launchers, manifest_errors = _runtime_manifest_inputs(manifest)
    if manifest_errors or minimum is None:
        return _redact_value(
            _runtime_error_report(
                manifest_errors,
                minimum=minimum_value,
                optional=optional_dependencies,
                launchers=launchers,
            )
        )
    current = (sys.version_info.major, sys.version_info.minor)
    python_ok = current >= minimum
    errors = []
    optional = []
    for dependency in optional_dependencies:
        name = str(dependency.get("name", ""))
        module = OPTIONAL_MODULES.get(name)
        if module is None:
            _add_error(errors, f"unsupported optional dependency probe: {name}")
            available = False
        else:
            available = importlib.util.find_spec(module) is not None
        optional.append({"name": name, "version": dependency.get("version"), "available": available, "fallback": dependency.get("fallback")})
    report = {
        "python": {"current": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", "minimum": minimum_value, "status": "ok" if python_ok else "too_old"},
        "optional_dependencies": optional,
        "launchers": launchers,
        "ok": python_ok and not errors,
        "errors": sorted(set(errors + ([] if python_ok else [f"Python {sys.version_info.major}.{sys.version_info.minor} is below required {minimum_value}"]))),
    }
    if detect_project or detect_start_command or scan_scaffold:
        inspection = _inspect_project(
            root,
            project_root if project_root is not None else root,
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
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--project-root", help="project directory to inspect read-only")
    parser.add_argument("--detect-project", action="store_true", help="detect project evidence and registered stacks")
    parser.add_argument("--detect-start-command", action="store_true", help="record package start-command candidates without running them")
    parser.add_argument("--scan-scaffold", action="store_true", help="scan conservative scaffold markers without changing files")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-optional", action="store_true", help="fail when an optional dependency is unavailable")
    args = parser.parse_args()
    report = check(
        Path(args.root),
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
            for ambiguity in inspection.get("ambiguities", []):
                print(f"Inspection note: {ambiguity}")
        print(f"Ready: {'yes' if report['ok'] else 'no'}")
        for error in report.get("errors", []):
            print(f"Error: {error}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
