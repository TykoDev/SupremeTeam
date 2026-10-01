"""Find the executable entrypoint of a Python, Go or Rust project and the command that starts it."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from project_files import classify_path, read_cached_text, relative_path
from redaction import add_error


PYTHON_WEB_MODULES = frozenset(
    {"fastapi", "flask", "django", "starlette", "quart", "sanic", "http.server", "uvicorn"}
)
PYTHON_FASTAPI_MODULES = frozenset({"fastapi", "starlette"})


def python_imports_module(text: str, modules: frozenset[str]) -> bool:
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
        relative_path(path, root).lower(): relative_path(path, root)
        for path in files
        if classify_path(relative_path(path, root)) == "production"
    }
    text = read_cached_text(cargo_path, root, errors, text_cache, required=True)
    if text is None:
        return [], None
    try:
        # tomllib is 3.11+; importing it here keeps the interpreter-floor report
        # reachable on older interpreters instead of dying at import time.
        import tomllib
    except ImportError:
        add_error(errors, "Cargo.toml: cannot be parsed (tomllib requires Python 3.11 or newer)")
        return [], None
    try:
        manifest = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, RecursionError) as exc:
        add_error(errors, f"Cargo.toml: invalid TOML ({exc})")
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


def cargo_binary_entry(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    targets, _ = _cargo_binary_targets(files, root, text_cache, errors)
    return targets[0][0] if targets else None


def cargo_start_command(
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


def go_entrypoint(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    relative_files = {
        relative_path(path, root)
        for path in files
        if classify_path(relative_path(path, root)) == "production"
    }
    candidates = sorted(relative for relative in relative_files if relative.lower() == "main.go")
    candidates.extend(
        relative
        for relative in sorted(relative_files)
        if len(Path(relative).parts) == 3
        and relative.lower().startswith("cmd/")
        and Path(relative).name.lower() == "main.go"
    )
    relative_paths = {relative_path(path, root): path for path in files}
    for relative in candidates:
        path = relative_paths.get(relative)
        if path is None:
            continue
        text = read_cached_text(path, root, errors, text_cache, required=True)
        if text is not None and _go_package_is_main(text):
            return relative
    return None


def go_start_command(
    files: list[Path],
    root: Path,
    text_cache: dict[Path, str | None],
    errors: list[str],
) -> str | None:
    entry = go_entrypoint(files, root, text_cache, errors)
    if entry is None:
        return None
    directory = Path(entry).parent.as_posix()
    return "go run ." if directory == "." else f"go run ./{directory}"
