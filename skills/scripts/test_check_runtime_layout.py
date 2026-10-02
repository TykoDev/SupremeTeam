"""Layout tests for the check_runtime module split (QR-PY-02, CR-18).

``check_runtime.py`` is the runtime-contract check and the command line. The project
inspector and the secret redactor live in sibling modules it imports. The behavioural
suites pin what the command reports; these tests pin the shape around it and the two
properties a split can lose without any of them noticing: the imports must not form a
cycle, and the modules must work as plain siblings in a copy of ``skills/scripts``
that holds nothing else (the installed layout).
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_check_runtime_detection as fixtures

SCRIPTS = fixtures.SCRIPTS

#: Everything check_runtime.py may define itself. A helper that is not part of the
#: contract check or the command line belongs in one of the inspector modules.
CLI_FUNCTIONS = {
    "_version",
    "_runtime_error_report",
    "_runtime_manifest_inputs",
    "_probe_optional_dependencies",
    "check",
    "main",
}
#: The review graded three functions of the old single file over 165 lines.
MAX_FUNCTION_LINES = 150


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def sibling_imports(path: Path) -> set[str]:
    """Names of the other modules in skills/scripts that this module imports."""
    names: set[str] = set()
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return {name for name in names if (SCRIPTS / f"{name}.py").is_file()}


def import_graph() -> dict[str, set[str]]:
    """check_runtime and every sibling module it reaches, with who imports whom."""
    graph: dict[str, set[str]] = {}
    pending = ["check_runtime"]
    while pending:
        name = pending.pop()
        if name in graph:
            continue
        graph[name] = sibling_imports(SCRIPTS / f"{name}.py")
        pending.extend(sorted(graph[name]))
    return graph


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, str] = {}

    def visit(node: str, path: list[str]) -> list[str] | None:
        state[node] = "open"
        for neighbour in sorted(graph.get(node, ())):
            if state.get(neighbour) == "open":
                return [*path, node, neighbour]
            if neighbour not in state:
                found = visit(neighbour, [*path, node])
                if found:
                    return found
        state[node] = "done"
        return None

    for node in sorted(graph):
        if node not in state:
            found = visit(node, [])
            if found:
                return found
    return None


class ModuleLayoutTests(unittest.TestCase):
    def test_the_command_line_module_defines_only_the_contract_check_and_the_command_line(self):
        defined = {node.name for node in parse(SCRIPTS / "check_runtime.py").body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(defined, CLI_FUNCTIONS)

    def test_the_inspector_modules_are_reached_through_the_command_line_module(self):
        graph = import_graph()
        self.assertGreater(len(graph), 4, sorted(graph))
        self.assertTrue({"redaction", "project_inspection", "stack_detection"} <= set(graph), sorted(graph))

    def test_the_sibling_imports_form_no_cycle(self):
        self.assertIsNone(find_cycle(import_graph()))

    def test_the_cycle_finder_reports_a_cycle_when_there_is_one(self):
        self.assertEqual(find_cycle({"a": {"b"}, "b": {"c"}, "c": {"a"}}), ["a", "b", "c", "a"])
        self.assertIsNone(find_cycle({"a": {"b", "c"}, "b": {"c"}, "c": set()}))

    def test_no_function_in_the_runtime_modules_is_longer_than_the_review_threshold(self):
        offenders = []
        for name in sorted(import_graph()):
            for node in ast.walk(parse(SCRIPTS / f"{name}.py")):
                if isinstance(node, ast.FunctionDef) and node.end_lineno - node.lineno + 1 > MAX_FUNCTION_LINES:
                    offenders.append(f"{name}.{node.name} ({node.end_lineno - node.lineno + 1} lines)")
        self.assertEqual(offenders, [])


class InstalledLayoutTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(script), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False
        )

    def test_the_command_runs_from_a_copy_that_holds_only_the_sibling_scripts(self):
        with tempfile.TemporaryDirectory() as holder_name:
            holder = Path(holder_name).resolve()
            skills = holder / "installed" / "skills"
            (skills / "scripts").mkdir(parents=True)
            for name in import_graph():
                shutil.copy2(SCRIPTS / f"{name}.py", skills / "scripts" / f"{name}.py")
            shutil.copy2(fixtures.CATALOG_SOURCE / "runtime-manifest.yaml", skills / "runtime-manifest.yaml")
            shutil.copytree(fixtures.CATALOG_SOURCE / "tech-stacks", skills / "tech-stacks")
            project = holder / "project"
            fixtures.write_tree(project, fixtures.VITE_TREE)
            modes = ["--project-root", str(project), "--detect-project", "--detect-start-command", "--scan-scaffold", "--json"]

            installed = self.run_script(skills / "scripts" / "check_runtime.py", *modes, cwd=holder)
            in_tree = self.run_script(fixtures.SCRIPT, *modes, "--catalog-root", str(skills), cwd=holder)

            self.assertNotIn("Traceback", installed.stderr)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            self.assertEqual(json.loads(installed.stdout)["project_inspection"]["stacks"][0]["slug"], "vite-spa")
            self.assertEqual((installed.returncode, installed.stdout, installed.stderr), (in_tree.returncode, in_tree.stdout, in_tree.stderr))


if __name__ == "__main__":
    unittest.main()
