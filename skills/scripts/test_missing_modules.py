"""A catalog with one file missing says which file, and never answers with a traceback (WP-06, issue 4).

With one module removed from a copy of the catalog, ``harness/gatekeeper/check.py`` and ``validate_manifests.py``
ended in a traceback with exit 1, which for both means "defects found"; ``check_runtime.py`` still printed
``Ready: yes``; and two of the three registered hooks crashed where the contract is to fail open.

Nothing here is listed by hand. An entry point is any non-test Python file with a ``__main__`` guard
(``catalog_imports.entry_points``), and for each one the cases are the catalog modules that load with it
(``catalog_imports.closure(..., load_time=True)``). A script added tomorrow is covered the day it is added, and a new
unguarded import fails the scan at the bottom.
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import catalog_imports as ci

SKILLS = Path(ci.__file__).resolve().parents[1]
# The exit status each kind of entry point documents for "could not run". A registered hook fails open; the run
# writer has its own engine-error status; everything else uses 2.
HOOKS = {"harness/hooks/pre_tool_use.py", "harness/hooks/post_tool_use.py", "harness/hooks/user_prompt_submit.py",
         "harness/hooks/guard_hook.py", "harness/hooks/context_events.py", "harness/hooks/antigravity_bridge.py"}
EXIT = {"harness/hooks/save_run.py": 3}
_HOST = ("CLAUDE", "CODEX_", "COPILOT", "GITHUB_COPILOT", "SUPREMETEAM_")


def plain_env() -> dict:
    env = {name: value for name, value in os.environ.items() if not name.upper().startswith(_HOST)}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class CatalogCopy(unittest.TestCase):
    """One copy of the catalog in a scratch project; a test hides a file in it and puts it back."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls._tmp.cleanup)
        cls.project = Path(cls._tmp.name).resolve() / "project"
        (cls.project / ".git").mkdir(parents=True)
        cls.skills = cls.project / "skills"
        shutil.copytree(SKILLS, cls.skills, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules"))

    def hidden(self, path: Path):
        """Context manager: ``path`` is absent inside the block."""
        aside = path.with_name(path.name + ".hidden")
        path.rename(aside)
        self.addCleanup(lambda: aside.rename(path) if aside.exists() else None)
        return _Restore(aside, path)

    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess:
        """Run an entry point the way it is meant to be started: by path, or as ``python -m <package>.<name>`` from
        the directory above when it imports through its own package."""
        package = ci.package_of(script, self.skills)
        command = [sys.executable, "-m", f"{package}.{script.stem}"] if package else [sys.executable, str(script)]
        return subprocess.run([*command, *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              cwd=str(script.parent.parent if package else self.project), stdin=subprocess.DEVNULL,
                              env=plain_env(), timeout=120, check=False)


class _Restore:
    def __init__(self, aside: Path, path: Path) -> None:
        self.aside, self.path = aside, path

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        if self.aside.exists():
            self.aside.rename(self.path)


class MissingModuleTests(CatalogCopy):
    def test_every_entry_point_names_the_module_it_cannot_load_and_never_prints_a_traceback(self):
        """Each module is hidden once, and every entry point that loads it is started while it is gone."""
        loaders: dict = {}
        for script in ci.entry_points(self.skills):
            for module in ci.closure(script, self.skills, load_time=True)[0]:
                loaders.setdefault(module, []).append(script)
        cases = sum(len(scripts) for scripts in loaders.values())
        self.assertGreater(cases, 60, "the discovery found the catalog's scripts and the modules they load")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            everything = sorted({script for scripts in loaders.values() for script in scripts})
            # What each script says with nothing missing. A module imported only on a path this environment does not
            # take (the stdlib YAML reader where PyYAML is installed) is not loaded, and the script answers as usual.
            usual = dict(zip(everything, pool.map(self.run_script, everything), strict=True))
            for module, scripts in sorted(loaders.items()):
                with self.hidden(module):
                    results = list(pool.map(self.run_script, scripts))
                for script, done in zip(scripts, results, strict=True):
                    relative = script.relative_to(self.skills).as_posix()
                    with self.subTest(script=relative, missing=module.relative_to(self.skills).as_posix()):
                        said = done.stdout + done.stderr
                        self.assertNotIn("Traceback (most recent call last)", said)
                        if "PyYAML is required" in said:
                            continue  # an optional package this script needs is absent here; it never reached its imports
                        if (done.returncode, said) == (usual[script].returncode, usual[script].stdout + usual[script].stderr):
                            continue  # not loaded in this environment
                        if relative in HOOKS:
                            self.assertEqual(done.returncode, 0, said)
                            continue
                        self.assertEqual(done.returncode, EXIT.get(relative, 2), said)
                        self.assertIn(module.stem, said)
                        self.assertIn("reinstall the catalog", said.lower())

    def test_the_gate_validator_answers_with_an_engine_error_as_json(self):
        script = self.skills / "harness" / "gatekeeper" / "check.py"
        for name in ("_gatecheck.py", "_gatecycle.py"):
            with self.subTest(missing=name), self.hidden(script.with_name(name)):
                done = self.run_script(script, "--boundary", "design-to-build", "--package", "manifest.json")
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertEqual(done.stdout, "")
                self.assertIn(name.removesuffix(".py"), json.loads(done.stderr)["engine_error"])
        for name in ("contract_floor.py", "data_formats.py"):
            with self.subTest(missing=name), self.hidden(self.skills / "scripts" / name):
                done = self.run_script(script, "--boundary", "design-to-build", "--package", "manifest.json")
                self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
                self.assertIn(name.removesuffix(".py"), json.loads(done.stderr)["engine_error"])

    def test_the_manifest_validator_reports_in_its_own_shape_and_does_not_exit_1(self):
        script = self.skills / "scripts" / "validate_manifests.py"
        with self.hidden(self.skills / "scripts" / "contract_floor.py"):
            done = self.run_script(script)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        report = json.loads(done.stdout)
        self.assertFalse(report["ok"])
        self.assertIn("contract_floor", report["errors"][0])

    def test_a_shape_wrapper_reports_contracts_it_cannot_read_and_does_not_crash(self):
        """The floor module is imported while the contracts load; without it they are unreadable, not a traceback."""
        package = self.project / "skillset-saves" / "runs" / "r-1" / "build"
        (package / "reports").mkdir(parents=True)
        (package / "reports" / "report_implementation.md").write_text("# Implementation\nChanged files: app.py.\n", encoding="utf-8")
        with self.hidden(self.skills / "scripts" / "contract_floor.py"):
            done = self.run_script(self.skills / "build" / "gatekeeper-build" / "scripts" / "check.py", str(package), "--json")
        self.assertIn(done.returncode, (0, 1), done.stdout + done.stderr)
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        self.assertIn("CONTRACTS_UNREADABLE", [finding["code"] for finding in json.loads(done.stdout)["findings"]])


class ReadinessTests(CatalogCopy):
    """``check_runtime.py`` no longer says Ready over a catalog one of whose scripts cannot start."""

    def check_runtime(self, *args: str) -> subprocess.CompletedProcess:
        return self.run_script(self.skills / "scripts" / "check_runtime.py", *args)

    def test_a_complete_catalog_is_ready(self):
        done = self.check_runtime()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Ready: yes", done.stdout)
        self.assertEqual(json.loads(self.check_runtime("--json").stdout)["missing_modules"], {})

    def test_a_module_a_script_needs_makes_it_not_ready_and_is_named(self):
        for module in ("harness/gatekeeper/_gatecycle.py", "harness/hooks/_cmdscan.py", "scripts/contract_floor.py",
                       "scripts/checkout.py", "harness/hooks/_fsutil.py"):
            with self.subTest(missing=module), self.hidden(self.skills / module):
                done = self.check_runtime()
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn("Ready: no", done.stdout)
                self.assertIn(Path(module).name, done.stdout)
                report = json.loads(self.check_runtime("--json").stdout)
                self.assertFalse(report["ok"])
                self.assertTrue(any(entry["module"] == Path(module).stem for entries in report["missing_modules"].values() for entry in entries))

    def test_the_walk_itself_being_absent_is_not_ready_either(self):
        with self.hidden(self.skills / "scripts" / "catalog_imports.py"):
            done = self.check_runtime()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("catalog_imports.py", done.stdout)
        self.assertIn("Ready: no", done.stdout)

    def test_a_module_check_runtime_needs_itself_is_an_error_and_not_ready(self):
        with self.hidden(self.skills / "scripts" / "redaction.py"):
            done = self.check_runtime()
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("redaction", done.stdout)
        self.assertIn("Ready: no", done.stdout)
        self.assertNotIn("Traceback", done.stdout + done.stderr)

    def test_a_package_that_leaves_out_an_imported_module_is_refused(self):
        script = self.skills / "scripts" / "package_check.py"
        clean = self.run_script(script, "--root", str(self.project))
        self.assertEqual(json.loads(clean.stdout)["missing_required"], [x for x in json.loads(clean.stdout)["missing_required"]
                                                                        if not x.startswith("skills/") or not x.endswith(".py")])
        with self.hidden(self.skills / "harness" / "hooks" / "_paths.py"):
            done = self.run_script(script, "--root", str(self.project))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertTrue(any("_paths.py, needed by skills/harness/hooks/" in entry for entry in json.loads(done.stdout)["missing_required"]))


class ImportWalkTests(unittest.TestCase):
    """``catalog_imports``: what counts as needed, and where a name is looked for."""

    def write(self, root: Path, relative: str, text: str) -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.write(self.root, "runtime-manifest.yaml", json.dumps({"runtime": {"python": {"optional_dependencies": [
            {"name": "PyYAML", "import": "yaml"}]}}}))

    def test_an_entry_point_is_a_file_with_a_main_guard_that_is_not_a_test(self):
        main = 'if __name__ == "__main__":\n    pass\n'
        self.write(self.root, "tool/run.py", main)
        self.write(self.root, "tool/helper.py", "x = 1\n")
        self.write(self.root, "tool/test_run.py", main)
        self.write(self.root, "tool/_testkit.py", main)
        self.write(self.root, "tool/__pycache__/run.py", main)
        self.assertEqual([path.relative_to(self.root).as_posix() for path in ci.entry_points(self.root)], ["tool/run.py"])

    def test_a_fallback_makes_an_import_optional_and_a_handler_that_leaves_does_not(self):
        script = self.write(self.root, "tool/run.py", (
            "import json\n"
            "try:\n    import yaml\nexcept ImportError:\n    yaml = None\n"
            "try:\n    import soft\nexcept ImportError:\n    soft = None\n"
            "try:\n    import hard\nexcept ImportError as exc:\n    raise SystemExit(2) from exc\n"
            "try:\n    import exits\nexcept ImportError:\n    import sys\n    sys.exit(2)\n"
            "def later():\n    import lazy\n"
            "import plain\n"))
        self.assertEqual(ci.imported_names(script), {"json": False, "yaml": True, "soft": True, "hard": False, "exits": False,
                                                     "sys": False, "lazy": False, "plain": False})
        dotted = self.write(self.root, "tool/dotted.py", "from pkg.sub import x\nimport os.path\n")
        self.assertEqual(ci.imported_names(dotted), {"pkg.sub": False, "os.path": False})
        self.assertNotIn("lazy", ci.imported_names(script, load_time=True))
        present, missing = ci.needs(script, self.root)
        self.assertEqual((present, missing), ([], ["exits", "hard", "lazy", "plain"]))

    def test_a_name_is_found_beside_the_script_then_in_the_shared_roots_then_where_the_script_points(self):
        beside = self.write(self.root, "tool/helper.py", "")
        shared = self.write(self.root, "scripts/shared_reader.py", "")
        self.write(self.root, "scripts/helper.py", "")
        pointed = self.write(self.root, "taste/store.py", "")
        package = self.write(self.root, "pkg/scripts/utils.py", "")
        script = self.write(self.root, "tool/run.py", "from pathlib import Path\nHERE = Path(__file__).resolve().parents[1] / 'taste'\n"
                                                      "import helper, shared_reader, store\n")
        self.assertEqual(ci.resolve("helper", script, self.root), beside)
        self.assertEqual(ci.resolve("shared_reader", script, self.root), shared)
        self.assertEqual(ci.resolve("store", script, self.root), pointed)
        self.assertIsNone(ci.resolve("nowhere", script, self.root))
        member = self.write(self.root, "pkg/scripts/run.py", "from scripts.utils import x\n")
        self.write(self.root, "pkg/scripts/test_utils.py", "")
        self.assertEqual(ci.resolve("scripts.utils", member, self.root), package)
        self.assertEqual(ci.resolve("scripts", member, self.root), package.parent)
        self.assertIsNone(ci.resolve("scripts.gone", member, self.root), "a submodule the package lacks is missing, not found elsewhere")
        self.assertEqual(ci.closure(member, self.root)[0], [package], "one submodule, not the package and never its tests")
        self.assertEqual(ci.package_of(member, self.root), "scripts")
        self.assertIsNone(ci.package_of(script, self.root))

    def test_the_closure_follows_modules_and_names_who_imports_a_missing_one(self):
        script = self.write(self.root, "tool/run.py", "import a\n")
        a = self.write(self.root, "tool/a.py", "import b\nimport gone\n")
        b = self.write(self.root, "tool/b.py", "import a\n")
        files, missing = ci.closure(script, self.root)
        self.assertEqual(files, [a, b])
        self.assertEqual(missing, {"gone": [a]})
        self.write(self.root, "tool/run.py", 'import a\nif __name__ == "__main__":\n    pass\n')
        self.assertEqual(ci.missing_modules(self.root), {"tool/run.py": [{"module": "gone", "imported_by": ["tool/a.py"]}]})
        self.assertEqual(ci.required_files(self.root), ["tool/a.py", "tool/b.py", "tool/run.py"])

    def test_a_declared_optional_package_is_not_a_missing_catalog_file(self):
        script = self.write(self.root, "tool/run.py", "try:\n    import yaml\nexcept ImportError:\n    raise SystemExit('PyYAML is required')\n")
        self.assertEqual(ci.optional_packages(self.root), {"yaml"})
        self.assertEqual(ci.needs(script, self.root), ([], []))
        (self.root / "runtime-manifest.yaml").write_text(json.dumps({"runtime": {"python": {"optional_dependencies": [
            {"name": "PyYAML"}]}}}), encoding="utf-8")
        self.assertEqual(ci.optional_packages(self.root), {"pyyaml", "yaml"}, "a manifest from before the import field")
        (self.root / "runtime-manifest.yaml").write_text("not json", encoding="utf-8")
        self.assertEqual(ci.optional_packages(self.root), set())

    def test_the_command_exits_1_and_names_each_missing_module(self):
        self.write(self.root, "tool/run.py", 'import gone\nif __name__ == "__main__":\n    pass\n')
        done = subprocess.run([sys.executable, ci.__file__, "--root", str(self.root)], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("MISSING: gone.py, needed by tool/run.py", done.stdout)
        done = subprocess.run([sys.executable, ci.__file__, "--root", str(self.root / "absent")], capture_output=True, text=True, check=False)
        self.assertEqual(done.returncode, 2)


class UnguardedImportScanTests(unittest.TestCase):
    """A new script cannot bring the defect back: no entry point imports a catalog module as a bare top-level statement."""

    def test_no_entry_point_has_an_unguarded_top_level_catalog_import(self):
        offenders = {script.relative_to(SKILLS).as_posix(): ci.unguarded_imports(script, SKILLS)
                     for script in ci.entry_points(SKILLS) if ci.unguarded_imports(script, SKILLS)}
        self.assertEqual(offenders, {}, "wrap these imports in try/except ImportError and say which file is missing")

    def test_the_scan_sees_a_bare_import_and_not_a_guarded_or_a_local_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "tool").mkdir()
            (root / "tool" / "helper.py").write_text("", encoding="utf-8")
            script = root / "tool" / "run.py"
            script.write_text("import os\nimport helper\ntry:\n    import helper\nexcept ImportError:\n    raise\n"
                              "def f():\n    import helper\n", encoding="utf-8")
            self.assertEqual(ci.unguarded_imports(script, root), [(2, "helper")])

    def test_the_catalog_is_complete(self):
        self.assertEqual(ci.missing_modules(SKILLS), {})


if __name__ == "__main__":
    unittest.main()
