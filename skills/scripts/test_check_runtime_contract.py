"""Runtime-contract and command-line tests for skills/scripts/check_runtime.py.

``check()`` compares the interpreter with the catalog's declared floor and reports
optional dependencies and launchers; the inspection modes it also fronts are
covered in ``test_check_runtime_detection.py``. These tests use temporary catalogs
so each manifest shape is reachable, and one smoke test runs the command the
manifest documents against the real catalog.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_runtime
import test_check_runtime_detection as fixtures

CURRENT = f"{sys.version_info.major}.{sys.version_info.minor}"


def manifest_with(*, minimum="3.9", optional=None, launchers=None, **extra) -> dict:
    python: dict = {"minimum": minimum}
    if optional is not None:
        python["optional_dependencies"] = optional
    manifest = {
        "schema_version": 1,
        "kind": "supremeteam-runtime-manifest",
        "runtime": {"python": python},
        "launchers": {"linux": "python3"} if launchers is None else launchers,
    }
    manifest.update(extra)
    return manifest


PYYAML = {"name": "PyYAML", "version": ">=6", "fallback": "skills/scripts/data_formats.py"}


class ManifestCatalogMixin:
    """A temporary catalog whose runtime manifest is the one the test supplies."""

    def manifest_catalog(self, manifest: object) -> Path:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        return fixtures.make_catalog(Path(holder.name), manifest=manifest, overlays=False)


class RuntimeContractTests(ManifestCatalogMixin, unittest.TestCase):
    def test_a_supported_interpreter_is_ready(self):
        report = check_runtime.check(self.manifest_catalog(manifest_with(minimum=CURRENT)))
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["python"]["status"], "ok")
        self.assertEqual(report["python"]["minimum"], CURRENT)
        self.assertEqual(
            report["python"]["current"], f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        self.assertEqual(report["launchers"], {"linux": "python3"})
        self.assertEqual(report["optional_dependencies"], [])
        self.assertNotIn("project_inspection", report)

    def test_an_interpreter_below_the_minimum_is_too_old_and_not_ready(self):
        report = check_runtime.check(self.manifest_catalog(manifest_with(minimum="99.0")))
        self.assertFalse(report["ok"])
        self.assertEqual(report["python"]["status"], "too_old")
        self.assertEqual(report["errors"], [f"Python {CURRENT} is below required 99.0"])

    def test_the_minimum_compares_major_and_minor_numerically(self):
        major, minor = sys.version_info.major, sys.version_info.minor
        self.assertTrue(check_runtime.check(self.manifest_catalog(manifest_with(minimum=f"{major}.{minor}")))["ok"])
        self.assertTrue(check_runtime.check(self.manifest_catalog(manifest_with(minimum=f"{major}.0")))["ok"])
        self.assertFalse(check_runtime.check(self.manifest_catalog(manifest_with(minimum=f"{major}.{minor + 1}")))["ok"])
        self.assertFalse(check_runtime.check(self.manifest_catalog(manifest_with(minimum=f"{major + 1}.0")))["ok"])

    def test_an_absent_optional_dependency_is_reported_and_does_not_fail_the_run(self):
        catalog = self.manifest_catalog(manifest_with(optional=[PYYAML]))
        with mock.patch("importlib.util.find_spec", return_value=None):
            report = check_runtime.check(catalog)
        self.assertTrue(report["ok"])
        self.assertEqual(
            report["optional_dependencies"],
            [{"name": "PyYAML", "version": ">=6", "available": False, "fallback": "skills/scripts/data_formats.py"}],
        )
        with mock.patch("importlib.util.find_spec", return_value=object()):
            self.assertTrue(check_runtime.check(catalog)["optional_dependencies"][0]["available"])

    def test_an_optional_dependency_the_script_cannot_probe_is_an_error(self):
        report = check_runtime.check(self.manifest_catalog(manifest_with(optional=[{"name": "left-pad"}])))
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"], ["unsupported optional dependency probe: left-pad"])
        self.assertEqual(report["optional_dependencies"][0]["available"], False)

    def test_each_manifest_defect_is_reported_and_never_raises(self):
        base = manifest_with(optional=[PYYAML])
        cases = {
            "root is not a mapping": ([1], "runtime manifest root must be a mapping"),
            "no runtime": ({"schema_version": 1}, "runtime manifest runtime must be a mapping"),
            "no python": ({"runtime": {}}, "runtime manifest runtime.python must be a mapping"),
            "patch level minimum": (
                manifest_with(minimum="3.13.1", optional=[PYYAML]),
                "runtime manifest runtime.python.minimum must be major.minor",
            ),
            "numeric minimum": (manifest_with(minimum=3.13), "runtime manifest runtime.python.minimum must be major.minor"),
            "missing minimum": (
                {"runtime": {"python": {}}},
                "runtime manifest runtime.python.minimum must be major.minor",
            ),
            "optional list is not a list": (
                manifest_with(optional={"name": "PyYAML"}),
                "runtime manifest optional_dependencies must be a list",
            ),
            "optional entry is not a mapping": (
                manifest_with(optional=["PyYAML"]),
                "runtime manifest optional dependency 0 must be a mapping",
            ),
            "optional entry has no name": (
                manifest_with(optional=[{"version": "1"}]),
                "runtime manifest optional dependency 0 requires a name",
            ),
            "optional version is not text": (
                manifest_with(optional=[{**PYYAML, "version": 6}]),
                "runtime manifest optional dependency 0 version must be a string",
            ),
            "optional fallback is not text": (
                manifest_with(optional=[{**PYYAML, "fallback": ["x"]}]),
                "runtime manifest optional dependency 0 fallback must be a string",
            ),
            "launchers is not a mapping": (
                {**base, "launchers": ["python3"]},
                "runtime manifest launchers must be a mapping",
            ),
            "launcher command is not text": (
                {**base, "launchers": {"linux": 3}},
                "runtime manifest launcher names and commands must be strings",
            ),
        }
        for name, (manifest, message) in cases.items():
            with self.subTest(defect=name):
                report = check_runtime.check(self.manifest_catalog(manifest))
                self.assertFalse(report["ok"])
                self.assertEqual(report["python"]["status"], "error")
                self.assertIn(message, report["errors"])
                for row in report["optional_dependencies"]:
                    self.assertIn("available", row)

    def test_the_error_report_lists_optional_dependencies_with_their_availability(self):
        catalog = self.manifest_catalog(manifest_with(minimum="3.13.1", optional=[PYYAML]))
        with mock.patch("importlib.util.find_spec", return_value=None):
            report = check_runtime.check(catalog)
        self.assertEqual(report["python"]["minimum"], "unknown")
        self.assertEqual(
            report["optional_dependencies"],
            [{"name": "PyYAML", "version": ">=6", "available": False, "fallback": "skills/scripts/data_formats.py"}],
        )
        self.assertEqual(report["launchers"], {"linux": "python3"})

    def test_a_missing_or_unparsable_manifest_is_an_error(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        report = check_runtime.check(Path(holder.name))
        self.assertFalse(report["ok"])
        self.assertEqual(report["python"], {"current": report["python"]["current"], "minimum": "unknown", "status": "error"})
        self.assertTrue(any("cannot read" in error for error in report["errors"]), report["errors"])
        (Path(holder.name) / "runtime-manifest.yaml").write_text("{ not: [valid", encoding="utf-8")
        report = check_runtime.check(Path(holder.name))
        self.assertFalse(report["ok"])
        self.assertEqual(report["python"]["status"], "error")

    def test_a_symlinked_catalog_root_is_refused(self):
        real = self.manifest_catalog(manifest_with())
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        link = Path(holder.name) / "catalog-link"
        fixtures.symlink_or_skip(self, real, link, directory=True)
        report = check_runtime.check(link)
        self.assertFalse(report["ok"])
        self.assertEqual(report["errors"], ["catalog root: reparse points are not inspected"])


class InspectionThroughCheckTests(fixtures.FixtureTreeCase):
    def test_the_inspection_defaults_to_the_current_directory(self):
        root = self.project(fixtures.VITE_TREE)
        with contextlib.chdir(root):
            report = check_runtime.check(self.catalog, detect_project=True)
        inspection = report["project_inspection"]
        self.assertEqual(inspection["root"], root.as_posix())
        self.assertEqual([stack["slug"] for stack in inspection["stacks"]], ["vite-spa"])

    def test_the_default_root_is_not_the_catalog(self):
        """The catalog holds no project, so inspecting it is the failure the default prevents."""
        root = self.project(fixtures.VITE_TREE)
        with contextlib.chdir(root):
            inspection = check_runtime.check(self.catalog, detect_project=True)["project_inspection"]
        self.assertNotEqual(Path(inspection["root"]), self.catalog.resolve())
        with contextlib.chdir(self.catalog):
            inspection = check_runtime.check(self.catalog, detect_project=True)["project_inspection"]
        self.assertEqual(inspection["stacks"], [])
        self.assertEqual(len(inspection["warnings"]), 1)

    def test_an_explicit_project_root_wins_over_the_current_directory(self):
        elsewhere = self.project({"package.json": fixtures.package_json(dependencies={"next": "^15"})})
        target = self.project(fixtures.VITE_TREE)
        with contextlib.chdir(elsewhere):
            inspection = check_runtime.check(self.catalog, project_root=target, detect_project=True)["project_inspection"]
        self.assertEqual(inspection["root"], target.as_posix())
        self.assertEqual([stack["slug"] for stack in inspection["stacks"]], ["vite-spa"])

    def test_the_three_modes_run_together_and_fill_their_own_fields(self):
        tree = {
            "package.json": fixtures.package_json(dev={"vite": "^7"}, scripts={"dev": "vite"}),
            "src/app.js": "// TODO wire this\n",
        }
        inspection = self.inspect_tree(tree, detect=True, start=True, scaffold=True)
        self.assertEqual(
            sorted(inspection),
            [
                "ambiguities", "classification", "classification_evidence", "configs", "errors", "manifests", "ok",
                "root", "scaffold_markers", "stacks", "start_commands", "warnings",
            ],
        )
        self.assertEqual([stack["slug"] for stack in inspection["stacks"]], ["vite-spa"])
        self.assertEqual(len(inspection["start_commands"]), 1)
        self.assertEqual([row["marker"] for row in inspection["scaffold_markers"]], ["TODO"])

    def test_inspection_errors_fail_the_run_and_warnings_do_not(self):
        broken = self.report({"package.json": "{"})
        self.assertFalse(broken["ok"])
        self.assertEqual(broken["errors"], ["project inspection: package.json: invalid JSON at line 1"])
        empty = self.report({})
        self.assertTrue(empty["ok"])
        self.assertEqual(empty["errors"], [])
        self.assertEqual(len(empty["project_inspection"]["warnings"]), 1)


class CommandLineCase(fixtures.FixtureTreeCase):
    def cli(self, *args: str, cwd: Path | None = None, catalog: Path | None = None) -> subprocess.CompletedProcess:
        command = [sys.executable, str(fixtures.SCRIPT)]
        if catalog is not None:
            command += ["--catalog-root", str(catalog)]
        return subprocess.run(
            [*command, *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=False
        )

    def lines(self, process: subprocess.CompletedProcess) -> list[str]:
        self.assertNotIn("Traceback", process.stderr)
        return process.stdout.splitlines()


class DocumentedCommandTests(CommandLineCase):
    """The commands the docs and the manifest name must do what the docs say."""

    def test_the_bare_stack_detection_command_inspects_the_directory_it_runs_in(self):
        root = self.project(fixtures.VITE_TREE)
        process = self.cli("--detect-project", cwd=root, catalog=self.catalog)
        lines = self.lines(process)
        self.assertEqual(process.returncode, 0, process.stdout)
        self.assertIn(f"Inspecting: {root.as_posix()}", lines)
        self.assertIn("Inspection: frontend-only; stacks=vite-spa; start candidates=0; scaffold markers=0", lines)
        self.assertIn("Ready: yes", lines)

    def test_the_documented_command_form_with_an_explicit_root_gives_the_same_answer(self):
        root = self.project(fixtures.VITE_TREE)
        bare = self.cli("--detect-project", cwd=root, catalog=self.catalog)
        explicit = self.cli("--project-root", ".", "--detect-project", cwd=root, catalog=self.catalog)
        self.assertEqual(bare.stdout, explicit.stdout)
        self.assertEqual(bare.returncode, explicit.returncode)

    def test_running_where_no_project_exists_warns_visibly(self):
        empty = self.project({})
        process = self.cli("--detect-project", cwd=empty, catalog=self.catalog)
        lines = self.lines(process)
        self.assertEqual(process.returncode, 0)
        self.assertIn(f"Inspecting: {empty.as_posix()}", lines)
        self.assertIn("Inspection: library/CLI; stacks=none; start candidates=0; scaffold markers=0", lines)
        warnings = [line for line in lines if line.startswith("Inspection warning: no project evidence found")]
        self.assertEqual(len(warnings), 1)
        self.assertIn("--project-root", warnings[0])

    def test_json_output_names_the_inspected_root_and_carries_the_warning(self):
        empty = self.project({})
        process = self.cli("--detect-project", "--json", cwd=empty, catalog=self.catalog)
        report = json.loads(process.stdout)
        self.assertEqual(report["project_inspection"]["root"], empty.as_posix())
        self.assertEqual(len(report["project_inspection"]["warnings"]), 1)
        self.assertTrue(report["ok"])

    def test_project_root_overrides_the_working_directory(self):
        elsewhere = self.project({"package.json": fixtures.package_json(dependencies={"next": "^15"})})
        target = self.project(fixtures.VITE_TREE)
        process = self.cli("--project-root", str(target), "--detect-project", cwd=elsewhere, catalog=self.catalog)
        lines = self.lines(process)
        self.assertIn(f"Inspecting: {target.as_posix()}", lines)
        self.assertTrue(any("stacks=vite-spa" in line for line in lines))

    def test_the_project_root_may_be_relative_to_the_working_directory(self):
        root = self.project({"apps/web/package.json": fixtures.package_json(dev={"vite": "^7"})})
        process = self.cli("--project-root", "apps/web", "--detect-project", cwd=root, catalog=self.catalog)
        self.assertIn(f"Inspecting: {(root / 'apps' / 'web').as_posix()}", self.lines(process))

    def test_start_command_candidates_are_printed_without_running_anything(self):
        marker = "ran-the-command"
        root = self.project({"package.json": fixtures.package_json(scripts={"dev": f"touch {marker}"})})
        process = self.cli("--project-root", ".", "--detect-start-command", cwd=root, catalog=self.catalog)
        lines = self.lines(process)
        self.assertEqual(process.returncode, 0)
        self.assertIn(f"Candidate package.json:scripts.dev: touch {marker}", lines)
        self.assertFalse((root / marker).exists())

    def test_the_scaffold_scan_reports_its_count(self):
        root = self.project({"app.py": "# TODO\n# FIXME\n"})
        process = self.cli("--project-root", ".", "--scan-scaffold", cwd=root, catalog=self.catalog)
        self.assertIn("Inspection: not classified; stacks=none; start candidates=0; scaffold markers=2", self.lines(process))

    def test_a_missing_project_root_fails_the_run(self):
        holder = self.project({})
        process = self.cli("--project-root", str(holder / "absent"), "--detect-project", cwd=holder, catalog=self.catalog)
        lines = self.lines(process)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Inspection error: project root does not exist", lines)
        self.assertIn("Ready: no", lines)
        self.assertIn("Error: project inspection: project root does not exist", lines)

    def test_json_mode_prints_one_sorted_document(self):
        root = self.project(fixtures.VITE_TREE)
        process = self.cli("--project-root", ".", "--detect-project", "--json", cwd=root, catalog=self.catalog)
        report = json.loads(process.stdout)
        self.assertEqual(process.stdout.rstrip("\n"), json.dumps(report, indent=2, sort_keys=True))
        self.assertEqual(process.returncode, 0)

    def test_the_runtime_check_command_documented_in_the_manifest_passes_on_the_real_catalog(self):
        process = self.cli("--json", cwd=fixtures.CATALOG_SOURCE.parent)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        report = json.loads(process.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["python"]["status"], "ok")
        self.assertNotIn("project_inspection", report)

    def test_the_old_root_spelling_and_the_new_one_are_interchangeable(self):
        root = self.project(fixtures.VITE_TREE)
        results = []
        for flag in ("--catalog-root", "--root"):
            process = subprocess.run(
                [sys.executable, str(fixtures.SCRIPT), flag, str(self.catalog), "--project-root", ".", "--detect-project", "--json"],
                cwd=root, capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            results.append(process.stdout)
        self.assertEqual(results[0], results[1])
        self.assertEqual([s["slug"] for s in json.loads(results[0])["project_inspection"]["stacks"]], ["vite-spa"])

    def test_the_help_names_both_roots_and_the_default(self):
        process = self.cli("--help")
        self.assertEqual(process.returncode, 0)
        help_text = " ".join(process.stdout.split())
        self.assertIn("--catalog-root", help_text)
        self.assertIn("--root is the older spelling", help_text)
        self.assertIn("catalog directory holding runtime-manifest.yaml and tech-stacks/", help_text)
        self.assertIn("(default: the current directory)", help_text)

    def test_an_unknown_flag_is_a_usage_error(self):
        process = self.cli("--detect-everything")
        self.assertEqual(process.returncode, 2)
        self.assertIn("unrecognized arguments", process.stderr)


class OutputFormatTests(ManifestCatalogMixin, CommandLineCase):
    def test_text_report_lists_optional_dependencies_and_readiness(self):
        catalog = self.manifest_catalog(manifest_with(minimum=CURRENT, optional=[PYYAML]))
        process = self.cli(catalog=catalog)
        lines = self.lines(process)
        self.assertEqual(lines[0], "Supreme Team runtime contract")
        self.assertTrue(lines[1].startswith("Python: ok ("))
        self.assertTrue(lines[2] in {"Optional PyYAML: available", "Optional PyYAML: missing; stdlib fallback documented"})
        self.assertEqual(lines[-1], "Ready: yes")
        self.assertEqual(process.returncode, 0)

    def test_an_interpreter_below_the_floor_prints_the_status_and_the_reason(self):
        process = self.cli(catalog=self.manifest_catalog(manifest_with(minimum="99.0")))
        lines = self.lines(process)
        self.assertEqual(process.returncode, 1)
        self.assertIn(f"Python: too_old ({sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})", lines)
        self.assertIn("Ready: no", lines)
        self.assertIn(f"Error: Python {CURRENT} is below required 99.0", lines)

    def test_a_manifest_defect_prints_the_defect_and_not_a_traceback(self):
        catalog = self.manifest_catalog(manifest_with(minimum="3.13.1", optional=[PYYAML]))
        for flags in ((), ("--json",), ("--require-optional",)):
            with self.subTest(flags=flags):
                process = self.cli(*flags, catalog=catalog)
                self.assertEqual(process.returncode, 1)
                self.assertNotIn("Traceback", process.stderr)
                self.assertIn("runtime manifest runtime.python.minimum must be major.minor", process.stdout)
        text = self.cli(catalog=catalog).stdout
        self.assertIn("Optional PyYAML:", text)

    def in_process(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["check_runtime.py", *args]), contextlib.redirect_stdout(out):
            code = check_runtime.main()
        return code, out.getvalue()

    def test_require_optional_turns_a_missing_dependency_into_a_failure(self):
        catalog = self.manifest_catalog(manifest_with(minimum=CURRENT, optional=[PYYAML]))
        with mock.patch("importlib.util.find_spec", return_value=None):
            code, output = self.in_process("--catalog-root", str(catalog))
            self.assertEqual(code, 0)
            self.assertIn("Optional PyYAML: missing; stdlib fallback documented", output)
            code, output = self.in_process("--catalog-root", str(catalog), "--require-optional")
        self.assertEqual(code, 1)
        self.assertIn("Ready: no", output)
        self.assertIn("Error: one or more optional dependencies are unavailable", output)


class InterpreterFloorTests(ManifestCatalogMixin, CommandLineCase):
    """The floor report must stay reachable on an interpreter that lacks newer modules."""

    def without_tomllib(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        scripts = str(fixtures.SCRIPTS)
        code = (
            "import runpy, sys\n"
            "sys.modules['tomllib'] = None\n"
            f"sys.path.insert(0, {scripts!r})\n"
            f"sys.argv = ['check_runtime.py', *{list(args)!r}]\n"
            f"runpy.run_path({str(fixtures.SCRIPT)!r}, run_name='__main__')\n"
        )
        return subprocess.run([sys.executable, "-c", code], cwd=cwd, capture_output=True, text=True, encoding="utf-8")

    def test_the_too_old_status_is_printed_without_the_toml_module(self):
        catalog = self.manifest_catalog(manifest_with(minimum="99.0"))
        process = self.without_tomllib("--catalog-root", str(catalog))
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Python: too_old", process.stdout)
        self.assertIn("Ready: no", process.stdout)

    def test_a_supported_interpreter_without_the_toml_module_still_reports_ready(self):
        process = self.without_tomllib("--catalog-root", str(self.manifest_catalog(manifest_with(minimum=CURRENT))))
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(process.returncode, 0)
        self.assertIn("Python: ok", process.stdout)

    def test_a_cargo_manifest_without_the_toml_module_is_an_error_not_a_crash(self):
        catalog = self.manifest_catalog(manifest_with(minimum=CURRENT))
        project = tempfile.TemporaryDirectory()
        self.addCleanup(project.cleanup)
        fixtures.write_tree(
            Path(project.name),
            {"Cargo.toml": '[package]\nname = "x"\n[dependencies]\naxum = "0.8"\n', "src/main.rs": "fn main() {}\n"},
        )
        process = self.without_tomllib(
            "--catalog-root", str(catalog), "--project-root", project.name, "--detect-project", "--detect-start-command"
        )
        self.assertNotIn("Traceback", process.stderr)
        self.assertEqual(process.returncode, 1)
        self.assertIn("Inspection error: Cargo.toml: cannot be parsed (tomllib requires Python 3.11 or newer)", process.stdout)


if __name__ == "__main__":
    unittest.main()
