"""The stdlib-only claim of the hook, gate and script directories, checked by reading their imports.

`runtime-manifest.yaml` declares `stdlib_only_for_hooks_and_gates` and lists the
directories it covers under `stdlib_only_scope.covers`. A module there may import the
standard library and the catalog's own modules. A test module may also import an
optional package, but only inside a `try` that handles `ImportError`, so the suite
still runs on a clean interpreter.
"""
from __future__ import annotations

import ast
import sys
import unittest

from _catalog import SKILLS, load_spec

#: Every module name the catalog itself provides; `_bootstrap.py` puts these on `sys.path`.
LOCAL = {path.stem for path in SKILLS.rglob("*.py")} | {path.name for path in SKILLS.rglob("*") if path.is_dir()}
IMPORT_ERRORS = {"ImportError", "ModuleNotFoundError"}


def guarded(handler: ast.ExceptHandler) -> bool:
    caught = handler.type
    names = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    return any(isinstance(name, ast.Name) and name.id in IMPORT_ERRORS for name in names)


def foreign_imports(source: str, *, allow_guarded: bool) -> list[tuple[int, str]]:
    """(line, module) for each import that is neither stdlib nor the catalog's own."""
    tree = ast.parse(source)
    exempt: set[int] = set()
    if allow_guarded:
        for node in ast.walk(tree):
            if isinstance(node, ast.Try) and any(guarded(handler) for handler in node.handlers):
                exempt.update(id(inner) for statement in node.body for inner in ast.walk(statement))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [node.module]
        else:
            continue
        for module in modules:
            top = module.split(".")[0]
            if top not in sys.stdlib_module_names and top not in LOCAL and id(node) not in exempt:
                found.append((node.lineno, top))
    return found


class StdlibOnlyTests(unittest.TestCase):
    def test_the_covered_directories_import_only_the_stdlib_and_the_catalog(self):
        manifest = load_spec("runtime-manifest.yaml")
        self.assertIs(manifest["runtime"]["python"]["stdlib_only_for_hooks_and_gates"], True)
        covers = manifest["stdlib_only_scope"]["covers"]
        self.assertTrue(covers, "stdlib_only_scope.covers is empty")
        for entry in covers:
            directory = SKILLS.parent / entry
            self.assertTrue(directory.is_dir(), f"stdlib_only_scope covers a missing directory: {entry}")
            for path in sorted(directory.rglob("*.py")):
                is_test = path.name.startswith("test_")
                for line, module in foreign_imports(path.read_text(encoding="utf-8"), allow_guarded=is_test):
                    self.fail(f"{path.relative_to(SKILLS.parent).as_posix()}:{line} imports third-party {module!r}")

    def test_an_unguarded_third_party_import_is_caught(self):
        self.assertEqual(foreign_imports("import json\nimport requests\n", allow_guarded=False), [(2, "requests")])
        self.assertEqual(foreign_imports("from yaml import safe_load\n", allow_guarded=True), [(1, "yaml")])

    def test_a_guarded_import_passes_only_in_a_test_module(self):
        source = "try:\n    import yaml\nexcept ImportError:\n    yaml = None\n"
        self.assertEqual(foreign_imports(source, allow_guarded=True), [])
        self.assertEqual(foreign_imports(source, allow_guarded=False), [(2, "yaml")])
        unrelated = "try:\n    import yaml\nexcept ValueError:\n    pass\n"
        self.assertEqual(foreign_imports(unrelated, allow_guarded=True), [(2, "yaml")])


if __name__ == "__main__":
    unittest.main()
