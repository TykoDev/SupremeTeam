"""Bounded, read-only access to a project tree: the walk, text reads, and path classification."""

from __future__ import annotations

import bisect
import os
import re
import stat
from pathlib import Path
from typing import Any

from data_formats import DataFormatError, parse_yaml
from redaction import add_error, add_warning


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


def relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def is_sensitive(path: Path, root: Path | None = None) -> bool:
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


def is_text_path(path: Path) -> bool:
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


def has_reparse_ancestor(path: Path) -> bool:
    current = path
    while True:
        if _is_reparse_point(current):
            return True
        parent = current.parent
        if parent == current:
            return False
        current = parent


def safe_regular_file(path: Path, root: Path) -> bool:
    if _has_reparse_component(path, root):
        return False
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return path.is_file() and not _is_reparse_point(path)


def _skip_reparse_directory(path: Path, root: Path, warnings: list[str]) -> bool:
    if not _is_reparse_point(path):
        return False
    add_warning(warnings, f"{relative_path(path, root)}: skipped, reparse points are not inspected")
    return True


def walk_project(root: Path, errors: list[str], warnings: list[str]) -> list[Path]:
    files: list[Path] = []
    file_count = 0
    directory_count = 0
    total_bytes = 0

    if _is_reparse_point(root):
        add_error(errors, "project root: reparse points are not inspected")
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

    def stopped(limit: str) -> bool:
        add_warning(
            warnings,
            f"project inspection {limit} limit exceeded; the walk stopped early and results may be incomplete",
        )
        return False

    def visit(current_path: Path, current_depth: int) -> bool:
        nonlocal directory_count, file_count, total_bytes
        if directory_count >= MAX_INSPECTION_DIRECTORY_COUNT:
            return stopped("directory-count")
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
                    if _skip_reparse_directory(candidate, root, warnings):
                        continue
                    try:
                        is_directory = entry.is_dir(follow_symlinks=False)
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError as exc:
                        add_warning(warnings, f"{relative_path(candidate, root)}: skipped, cannot inspect entry ({exc})")
                        continue
                    if is_directory:
                        if current_depth + 1 > MAX_INSPECTION_DEPTH:
                            add_warning(
                                warnings,
                                f"{relative_path(candidate, root)}: skipped, inspection depth limit exceeded",
                            )
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
                    if not safe_regular_file(path, root):
                        continue
                    file_overflow = keep_smallest(
                        file_candidates,
                        (name, path),
                        MAX_INSPECTION_FILE_COUNT - file_count,
                    ) or file_overflow
        except OSError as exc:
            if current_depth == 0:
                add_error(errors, f"cannot inspect {current_path}: {exc}")
            else:
                add_warning(warnings, f"{relative_path(current_path, root)}: skipped, cannot read directory ({exc})")

        for _, path in file_candidates:
            if file_count >= MAX_INSPECTION_FILE_COUNT:
                return stopped("file-count")
            try:
                size = path.stat().st_size
            except OSError as exc:
                add_warning(warnings, f"{relative_path(path, root)}: skipped, cannot inspect file ({exc})")
                continue
            if total_bytes + size > MAX_INSPECTION_TOTAL_BYTES:
                return stopped("total-byte")
            files.append(path)
            file_count += 1
            total_bytes += size
        if file_overflow:
            return stopped("file-count")

        for _, path in directory_candidates:
            if not visit(path, current_depth + 1):
                return False
        if directory_overflow:
            return stopped("directory-count")
        return True

    visit(root, 0)
    return files


def read_text(
    path: Path,
    root: Path,
    errors: list[str],
    *,
    required: bool = False,
) -> str | None:
    if is_sensitive(path, root) or not is_text_path(path):
        return None
    relative = relative_path(path, root)
    if path.is_symlink():
        if required:
            add_error(errors, f"{relative}: reparse points are not inspected")
        return None
    if _is_reparse_point(path) or not safe_regular_file(path, root):
        if required:
            add_error(errors, f"{relative}: reparse points and out-of-root files are not inspected")
        return None
    try:
        if path.stat().st_size > MAX_INSPECTION_FILE_BYTES:
            if required:
                add_error(errors, f"{relative}: file exceeds the inspection size limit")
            return None
        # utf-8-sig: Windows editors write a byte order mark that Node itself accepts,
        # and json.loads rejects, so a marked package.json must not read as invalid.
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        if required:
            add_error(errors, f"{relative}: cannot read text ({exc})")
        return None


def read_cached_text(
    path: Path,
    root: Path,
    errors: list[str],
    cache: dict[Path, str | None],
    *,
    required: bool = False,
) -> str | None:
    if path not in cache:
        cache[path] = read_text(path, root, errors, required=required)
    elif required and cache[path] is None:
        read_text(path, root, errors, required=True)
    return cache[path]


def load_cached_data(
    path: Path,
    root: Path,
    errors: list[str],
    warnings: list[str],
    text_cache: dict[Path, str | None],
) -> Any | None:
    text = read_cached_text(path, root, errors, text_cache, required=True)
    if text is None:
        return None
    try:
        return parse_yaml(text)
    except (DataFormatError, UnicodeError, ValueError, RecursionError) as exc:
        # The stdlib reader covers a YAML subset (no anchors or merge keys), so a
        # file it rejects is skipped rather than reported as a broken project.
        add_warning(warnings, f"{relative_path(path, root)}: not parsed, its services are not considered ({exc})")
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


def collect_evidence(files: list[Path], root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    manifests: list[dict[str, str]] = []
    configs: list[dict[str, str]] = []
    for path in files:
        if is_sensitive(path, root):
            continue
        relative = relative_path(path, root)
        manifest_kind = _manifest_kind(path)
        if manifest_kind:
            manifests.append({"path": relative, "kind": manifest_kind})
            continue
        config_kind = _config_kind(path)
        if config_kind:
            configs.append({"path": relative, "kind": config_kind})
    return manifests, configs


def classify_path(relative: str) -> str:
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
