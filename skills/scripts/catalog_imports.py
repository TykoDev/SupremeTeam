#!/usr/bin/env python3
"""Which catalog modules each entry point needs, read from the code itself.

    python skills/scripts/catalog_imports.py [--root skills] [--json]

The catalog's scripts import each other by name: a hook imports ``_state``, a gate wrapper imports ``_gatecheck``,
most tools import ``data_formats``. A copy of the catalog with one of those files missing used to answer with a
traceback, or, in ``check_runtime.py``, with ``Ready: yes``. This module finds, for every entry point, the modules it
imports that are part of the catalog, and says which of them are absent. Nothing is listed by hand: an entry point is
any non-test Python file with an ``if __name__ == "__main__"`` guard, and its imports are read from its syntax tree,
so a script added tomorrow is covered the day it is added.

A module counts as *needed* by a file when the file imports it and no fallback is written for its absence. An import
inside a ``try`` whose ``ImportError`` handler carries on (``except ImportError: yaml = None``) is optional; one whose
handler ends the program (``raise``, ``sys.exit``, ``return``) is needed and merely says so readably.

A needed name is resolved to a file in the importing file's own directory, then in the shared import roots
(``scripts``, ``harness/hooks``, ``harness/gatekeeper``), then in the directories the file names in a
``parents[...] / "..."`` path expression. A name that resolves nowhere and that this interpreter cannot import either
is a *missing* module.

``python catalog_imports.py`` prints the missing modules, or that there are none; exit 0 when none, 1 when some,
2 when the catalog root cannot be read. Stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1]
# Directories every catalog script may import from, relative to the catalog root. A script puts them on sys.path
# itself (``_bootstrap.ensure_paths``, a gate wrapper's ``_engine``); they are named here once, as places to look.
SHARED_ROOTS = ("scripts", "harness/hooks", "harness/gatekeeper")
_SKIP_DIRS = frozenset({"__pycache__", "node_modules", ".git"})
_ENDING = (ast.Raise, ast.Return)
_IMPORT_ERRORS = frozenset({"ImportError", "ModuleNotFoundError", "Exception", "BaseException"})


# One reading of each file per process: its syntax tree is walked once, and every question about its imports is
# answered from what that found. Keyed on the file's size and modification time, so a file that changes is read again.
_READ: dict = {}


def _key(path: Path) -> tuple:
    try:
        status = path.stat()
        return (str(path), status.st_mtime_ns, status.st_size)
    except OSError:
        return (str(path), None, None)


def _parsed(path: Path) -> "ast.Module | None":
    key = _key(path)
    if key not in _READ:
        try:
            _READ[key] = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (OSError, SyntaxError, ValueError):
            _READ[key] = None
    return _READ[key]


def is_test(path: Path) -> bool:
    """A test module or test support: nothing a user runs, and nothing readiness depends on."""
    return path.name.startswith("test_") or path.name in ("_testkit.py", "_fixtures.py", "_runtime_fixtures.py", "_catalog.py", "conftest.py")


def is_entry_point(path: Path, tree: "ast.Module | None" = None) -> bool:
    """A file with a top-level ``if __name__ == "__main__":`` guard."""
    tree = tree or _parsed(path)
    if tree is None:
        return False
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) \
                and node.test.left.id == "__name__" and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in node.test.comparators):
            return True
    return False


def _handler_names(handler: ast.ExceptHandler) -> set:
    kind = handler.type
    if kind is None:
        return {"BaseException"}
    items = kind.elts if isinstance(kind, ast.Tuple) else [kind]
    return {item.id if isinstance(item, ast.Name) else getattr(item, "attr", "") for item in items}


def _ends_the_program(body: list) -> bool:
    """Whether a handler's last statement leaves: ``raise``, ``return``, ``sys.exit(...)`` or ``exit(...)``."""
    last = body[-1] if body else None
    if isinstance(last, _ENDING):
        return True
    call = last.value if isinstance(last, ast.Expr) else None
    if isinstance(call, ast.Call):
        func = call.func
        return (isinstance(func, ast.Attribute) and func.attr in ("exit", "_exit")) or (isinstance(func, ast.Name) and func.id in ("exit", "quit"))
    return False


_NO_LOAD = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _scan(path: Path) -> "tuple | None":
    """One walk over a file's syntax tree: ``(imports, optional lines, path joins)``, or None when it cannot be read.

    ``imports`` is ``[(dotted names, line, runs at load time)]`` for every absolute import; an import inside a
    function or a class does not run when the file loads. ``optional lines`` are the lines of every ``try`` body that
    has a fallback for a module that does not import. ``path joins`` are the string parts of every
    ``<expression> / "a" / "b"``."""
    key = ("scan", *_key(path))
    if key in _READ:
        return _READ[key]
    tree = _parsed(path)
    if tree is None:
        _READ[key] = None
        return None
    imports, optional, joins = [], set(), []
    pending = [(node, True) for node in tree.body]
    while pending:
        node, loads = pending.pop()
        if isinstance(node, ast.Import):
            imports.append(([alias.name for alias in node.names], node.lineno, loads))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                # The dotted name is kept: `from scripts.utils import x` needs scripts/utils.py, not the whole package.
                imports.append(([node.module], node.lineno, loads))
        elif isinstance(node, ast.Try):
            catching = [handler for handler in node.handlers if _handler_names(handler) & _IMPORT_ERRORS]
            if catching and not all(_ends_the_program(handler.body) for handler in catching):
                for statement in node.body:
                    optional.update(range(statement.lineno, (statement.end_lineno or statement.lineno) + 1))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts, current = [], node
            while isinstance(current, ast.BinOp) and isinstance(current.op, ast.Div) and isinstance(current.right, ast.Constant) \
                    and isinstance(current.right.value, str):
                parts.insert(0, current.right.value)
                current = current.left
            if parts:
                joins.append(parts)
        inner = loads and not isinstance(node, _NO_LOAD)
        pending.extend((child, inner) for child in ast.iter_child_nodes(node))
    _READ[key] = (imports, optional, joins)
    return _READ[key]


def imported_names(path: Path, load_time: bool = False) -> dict:
    """``{module name: optional?}`` for every absolute import in ``path``, wherever in the file it stands.

    A function-local import counts: the scripts import lazily on purpose. A module imported both with and without
    a fallback is needed. ``load_time`` keeps only the imports that run when the file is loaded, which are the ones
    whose absence stops the script before it reads an argument."""
    scanned = _scan(path)
    if scanned is None:
        return {}
    imports, optional, _ = scanned
    found: dict = {}
    for names, line, loads in imports:
        if load_time and not loads:
            continue
        for name in names:
            found[name] = found.get(name, True) and line in optional
    return found


def _named_directories(path: Path, root: Path) -> list:
    """Directories ``path`` builds from its own location and puts on ``sys.path``: ``parents[2] / "taste"``,
    ``Path(__file__).resolve().parent.parent / "scripts"``. Read from the text of the path expressions."""
    key = ("directories", str(root), *_key(path))
    if key in _READ:
        return list(_READ[key])
    scanned = _scan(path)
    found = []
    for parts in (scanned[2] if scanned else []):
        for base in (path.parent, *path.parents):
            candidate = base.joinpath(*parts)
            if candidate.is_dir() and candidate not in found:
                found.append(candidate)
            if base == root:
                break
    _READ[key] = found
    return list(found)


def search_path(path: Path, root: Path = SKILLS) -> list:
    """Where a module imported by ``path`` may live, in the order it is looked for."""
    # The file's own directory, and the directory above it for a script that is a module of a package
    # (`from scripts.utils import ...` run as `python -m scripts.run_eval`).
    places = [path.parent, path.parent.parent, *(root / shared for shared in SHARED_ROOTS)]
    for directory in _named_directories(path, root):
        if directory not in places:
            places.append(directory)
    return places


def resolve(name: str, path: Path, root: Path = SKILLS) -> "Path | None":
    """The catalog file that ``import name`` in ``path`` loads, or None when the catalog holds none. ``name`` may be
    dotted (``scripts.utils``): the submodule's file is the answer, and a package named with no submodule resolves to
    its directory."""
    parts = name.split(".")
    for directory in search_path(path, root):
        module = directory.joinpath(*parts).with_suffix(".py")
        if module.is_file():
            return module
        package = directory.joinpath(*parts)
        if package.is_dir() and any(package.glob("*.py")):
            return package
        if len(parts) > 1 and (directory / parts[0]).is_dir() and any((directory / parts[0]).glob("*.py")):
            return None  # the package is here and this submodule of it is not: a missing file, looked for nowhere else
    return None


def package_of(path: Path, root: Path = SKILLS) -> "str | None":
    """The package ``path`` is a module of, when it imports through that package (``from scripts.utils import ...`` in
    ``scripts/run_eval.py``): such a script is run as ``python -m scripts.run_eval`` from the directory above."""
    package = path.parent.name
    if any(name.split(".")[0] == package for name in imported_names(path)) and (path.parent.parent / package) == path.parent:
        return package
    return None


def optional_packages(root: Path = SKILLS) -> set:
    """Import names of the third-party packages ``runtime-manifest.yaml`` declares optional
    (``runtime.python.optional_dependencies[].import``). A script that needs one and says so is not a catalog with a
    file missing. The manifest is written as JSON, so it is read without the catalog's own reader; one that cannot be
    read declares nothing."""
    try:
        data = json.loads((root / "runtime-manifest.yaml").read_text(encoding="utf-8-sig"))
        entries = data["runtime"]["python"]["optional_dependencies"]
    except (OSError, ValueError, KeyError, TypeError):
        return set()
    names: set = set()
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        if entry.get("import"):
            names.add(str(entry["import"]))
        elif entry.get("name"):
            # A manifest written before the field existed names only the distribution (PyYAML): its usual import
            # names are the name itself and the name without a leading "py".
            lowered = str(entry["name"]).lower()
            names.update({lowered, lowered.removeprefix("py")})
    return names


def _importable(name: str) -> bool:
    name = name.split(".")[0]
    if name in sys.stdlib_module_names or name in sys.builtin_module_names:
        return True
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def needs(path: Path, root: Path = SKILLS, load_time: bool = False) -> tuple:
    """``(present, missing)`` for one file: the catalog files it needs that are there, and the names it needs that
    are neither in the catalog nor importable by this interpreter."""
    present, missing = [], []
    third_party = optional_packages(root)
    for name, optional in sorted(imported_names(path, load_time).items()):
        if optional or name.split(".")[0] in third_party:
            continue
        found = resolve(name, path, root)
        if found is not None:
            present.append(found)
        elif not _importable(name):
            missing.append(name)
    return present, missing


def closure(path: Path, root: Path = SKILLS, load_time: bool = False) -> tuple:
    """Every catalog module ``path`` needs, directly or through a module it imports, and every missing name with
    the file that imports it: ``(sorted files, {name: [importing files]})``. With ``load_time``, only what is
    imported while the files load."""
    seen: dict = {}
    missing: dict = {}
    pending = [path]
    while pending:
        current = pending.pop()
        present, absent = needs(current, root, load_time)
        for name in absent:
            missing.setdefault(name, []).append(current)
        for module in present:
            files = [module] if module.is_file() else sorted(file for file in module.glob("*.py") if not is_test(file))
            for file in files:
                if file not in seen and file != path:
                    seen[file] = True
                    pending.append(file)
    return sorted(seen), missing


def unguarded_imports(path: Path, root: Path = SKILLS) -> list:
    """Catalog modules ``path`` imports as a bare statement of its module body, where a missing file is a traceback:
    ``[(line, name)]``. An import inside a ``try`` or a function is not one."""
    tree = _parsed(path)
    if tree is None:
        return []
    found = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        found.extend((node.lineno, name) for name in names if resolve(name, path, root) is not None)
    return found


def entry_points(root: Path = SKILLS) -> list:
    """Every non-test Python file under ``root`` with a ``__main__`` guard."""
    found = []
    for path in sorted(root.rglob("*.py")):
        if _SKIP_DIRS & set(path.relative_to(root).parts) or is_test(path):
            continue
        if is_entry_point(path):
            found.append(path)
    return found


def missing_modules(root: Path = SKILLS) -> dict:
    """``{entry point (relative): [{"module", "imported_by"}]}`` for every entry point that needs a module the
    catalog does not hold. Empty for a complete catalog."""
    report: dict = {}
    for script in entry_points(root):
        _, missing = closure(script, root)
        if missing:
            report[script.relative_to(root).as_posix()] = [
                {"module": name.replace(".", "/"), "imported_by": sorted({file.relative_to(root).as_posix() for file in files})}
                for name, files in sorted(missing.items())]
    return report


def required_files(root: Path = SKILLS) -> list:
    """Every catalog file some entry point needs, relative to ``root``: what a package has to carry for its scripts to run."""
    needed: set = set()
    for script in entry_points(root):
        needed.add(script)
        needed.update(closure(script, root)[0])
    return sorted(path.relative_to(root).as_posix() for path in needed)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="List the catalog modules the catalog's own scripts import and cannot find.")
    parser.add_argument("--root", default=str(SKILLS), help="the catalog root (the skills directory; default: the one this script is in)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        return 2
    report = missing_modules(root)
    if args.json:
        print(json.dumps({"root": str(root), "entry_points": len(entry_points(root)), "missing": report}, indent=2))
    elif not report:
        print(f"Every module the {len(entry_points(root))} entry points under {root} import is present.")
    else:
        for script, entries in report.items():
            for entry in entries:
                print(f"MISSING: {entry['module']}.py, needed by {script} (imported in {', '.join(entry['imported_by'])}). Reinstall the catalog.")
    return 1 if report else 0


if __name__ == "__main__":
    raise SystemExit(main())
