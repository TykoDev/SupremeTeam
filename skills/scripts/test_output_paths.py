"""Regression coverage for output_paths.py: every output kind lands where the gates look for it.

A destination is part of the contract, so these tests pin the paths themselves:
the reports/ and coverage destinations of every declared pipeline phase, the
grilling log the intake gate reads, the preference files, and a destination inside
the project for every kind but guards and the global preferences. They also pin
what the resolver refuses: traversal, a segment that is not one safe name, a core
name that is not a run record, a phase report no class declares, and a product
path that would run code or enforce the guard, whether it is named outright or
reached through a link.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _runtime_fixtures import symlink_or_skip
from output_paths import global_data_root, resolve

SCRIPTS = Path(__file__).resolve().parent


class DestinationTests(unittest.TestCase):
    def test_preference_paths_are_explicit_and_global_stays_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as home:
            root = Path(directory).resolve()
            project_json, project_md = resolve(root, "project_preferences")
            self.assertEqual(project_json, root / "skillset-saves/preferences/taste.json")
            self.assertEqual(project_md, root / "skillset-saves/preferences/taste.md")
            with mock.patch.dict("os.environ", {"SUPREMETEAM_HOME": home}, clear=False):
                self.assertEqual(global_data_root(), Path(home).resolve())
                global_json, global_md = resolve(root, "global_preferences")
                self.assertNotIn(root, global_json.parents)
                self.assertEqual(global_md.parent, global_json.parent)

    def test_declared_pipelines_have_output_destinations(self):
        pipelines = json.loads((SCRIPTS.parent / "pipelines.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for phase in pipelines["pipelines"]:
                with self.subTest(phase=phase):
                    self.assertEqual(
                        resolve(root, "reports", run_id="audit", phase=phase, name="result.md"),
                        root / "skillset-saves" / "runs" / "audit" / phase / "reports" / "result.md",
                    )

    def test_coverage_kind_resolves_under_the_run_phase_evidence(self):
        """Coverage data is phase evidence in the run, never project-root residue.

        The observed failure was a `.coverage` tree of thousands of files at a
        target project's root; this destination is what a test step points
        COVERAGE_FILE, --report-dir, or --coverage.reportsDirectory at instead.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for phase, name in (("build", ".coverage"), ("qa", "html/index.html")):
                with self.subTest(phase=phase, name=name):
                    self.assertEqual(
                        resolve(root, "coverage", run_id="r1", phase=phase, name=name),
                        root / "skillset-saves" / "runs" / "r1" / phase / "evidence" / "coverage" / Path(name),
                    )
            # It is a subdirectory of the phase-evidence class, not a sibling of it.
            evidence = resolve(root, "evidence", run_id="r1", phase="build", name="tests.log")
            self.assertEqual(
                resolve(root, "coverage", run_id="r1", phase="build", name=".coverage").parent,
                evidence.parent / "coverage",
            )

    def test_coverage_kind_rejects_traversal_and_unknown_phases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for kwargs in (
                dict(run_id="r1", phase="build", name="../../escape"),
                dict(run_id="r1", phase="build", name=""),
                dict(run_id="r1", phase="not-a-phase", name=".coverage"),
                dict(run_id="", phase="build", name=".coverage"),
            ):
                with self.subTest(**kwargs):
                    with self.assertRaises(ValueError):
                        resolve(root, "coverage", **kwargs)


class ResolverContractTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def test_every_kind_resolves_inside_project(self):
        cases = {
            "manifest": dict(run_id="r1", phase="design"),
            "reports": dict(run_id="r1", phase="design", name="report_plan.md"),
            "artifacts": dict(run_id="r1", phase="design", name="tokens.css"),
            "phase_report": dict(run_id="r1", phase="intake", name="report_grilling.md"),
            "evidence": dict(run_id="r1", phase="security", name="scan-pip-audit.json"),
            "packages": dict(run_id="r1", phase="skill-creation", name="my-skill.skill"),
            "verdict": dict(run_id="r1", phase="review", boundary="review-to-delivery"),
            "core": dict(run_id="r1", name="_state.md"),
            "project_preferences": {},
            "trajectory": dict(run_id="r1", session="abc"),
            "product": dict(name="src/app.css"),
            "test_work": dict(name="case-1/README.md"),
            "eval_reports": dict(name="report.html"),
            "eval_workspace": dict(name="my-skill-workspace/iteration-1"),
            "standalone_packages": dict(name="my-skill.skill"),
        }
        for kind, arguments in cases.items():
            with self.subTest(kind=kind):
                target = resolve(self.root, kind, **arguments)
                for item in (target if isinstance(target, tuple) else (target,)):
                    self.assertTrue(item.resolve().is_relative_to(self.root), item)
        for kind, arguments in (("artifacts", dict(run_id="r1", phase="design", name="../escape.css")),
                                ("manifest", dict(run_id="../x", phase="design")),
                                ("core", dict(run_id="r1", name="manifest.json"))):
            with self.subTest(refused=kind):
                with self.assertRaises(ValueError):
                    resolve(self.root, kind, **arguments)

    def test_phase_report_kind_resolves_the_grilling_log_the_gate_references(self):
        """Following "resolve every destination with output_paths.py" used to put the
        grilling log in intake/reports/, where the manifest's ../intake/report_grilling.md
        reference finds nothing."""
        self.assertEqual(resolve(self.root, "phase_report", run_id="r1", phase="intake", name="report_grilling.md"),
                         self.root / "skillset-saves/runs/r1/intake/report_grilling.md")
        self.assertEqual(resolve(self.root, "reports", run_id="r1", phase="intake", name="report_grilling.md"),
                         self.root / "skillset-saves/runs/r1/intake/reports/report_grilling.md")

    def test_phase_report_cli_prints_the_documented_path(self):
        process = subprocess.run(
            [sys.executable, str(SCRIPTS / "output_paths.py"), "--project-root", str(self.root), "--kind", "phase_report",
             "--run-id", "r1", "--phase", "intake", "--name", "report_grilling.md", "--mkdir"],
            capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(json.loads(process.stdout)["relative"], "skillset-saves/runs/r1/intake/report_grilling.md")
        self.assertTrue((self.root / "skillset-saves/runs/r1/intake").is_dir())

    def test_help_carries_the_per_kind_destination_table(self):
        """The table of what each kind resolves to lived only in the module docstring."""
        process = subprocess.run([sys.executable, str(SCRIPTS / "output_paths.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("phase_report skillset-saves/runs/<run>/<phase>/<name>", process.stdout)

    def test_phase_report_refuses_names_no_class_declares(self):
        for phase, name in (("design", "notes.md"), ("design", "intake-brief.md"), ("intake", "report_x.txt"),
                            ("intake", "sub/report_x.md"), ("intake", "../report_x.md"), ("intake", "/tmp/report_x.md"),
                            ("intake", ""), ("design", "manifest.json")):
            with self.subTest(phase=phase, name=name):
                with self.assertRaises(ValueError):
                    resolve(self.root, "phase_report", run_id="r1", phase=phase, name=name)

    def test_segments_are_single_safe_segments_even_with_a_trailing_newline(self):
        """`$` matches before a final newline, so a value read with read_text() and not
        stripped named a directory that ends in one."""
        for kind, arguments in (("reports", dict(run_id="abc\n", phase="build", name="x.md")),
                                ("verdict", dict(run_id="r1", phase="build", boundary="a-to-b\n")),
                                ("trajectory", dict(run_id="r1", session="s1\n"))):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    resolve(self.root, kind, **arguments)

    def test_a_product_name_may_not_bless_a_path_that_runs_code_or_enforces_the_guard(self):
        """`--kind product` returned ok for the version-control hooks directory and for the guard's own scripts."""
        for name in (".git/hooks/pre-commit", ".git", ".GIT/config", "./.git/hooks/x", "skillset-saves/runs/r1/_state.md",
                     ".harness-state/guard-state.json", "skills/harness/hooks/pre_tool_use.py", "Skills/Harness/gatekeeper/check.py",
                     ".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json", ".github/hooks.json"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError) as raised:
                    resolve(self.root, "product", name=name)
                self.assertIn("no product output may target", str(raised.exception))

    def test_ordinary_product_names_still_resolve_including_near_misses_of_the_refused_ones(self):
        for name in ("src/app.py", "README.md", ".github/workflows/ci.yml", ".claude/commands/review.md", ".gitignore",
                     "docs/.git-notes.md", "skills/harness-notes.md", "skills/design/SKILL.md", "skillset-saves-old/x.md"):
            with self.subTest(name=name):
                self.assertEqual(resolve(self.root, "product", name=name), self.root / name)

    def test_a_link_into_a_refused_directory_is_refused_as_what_it_resolves_to(self):
        (self.root / ".git" / "hooks").mkdir(parents=True)
        symlink_or_skip(self, self.root / ".git", self.root / "innocent", directory=True)
        with self.assertRaises(ValueError):
            resolve(self.root, "product", name="innocent/hooks/pre-commit")

    def test_the_cli_reports_a_refused_product_name_as_an_error(self):
        process = subprocess.run([sys.executable, str(SCRIPTS / "output_paths.py"), "--project-root", str(self.root),
                                  "--kind", "product", "--name", ".git/hooks/pre-commit"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        self.assertFalse(json.loads(process.stdout)["ok"])

    def test_an_empty_or_relative_xdg_data_home_falls_back_to_the_home_default(self):
        """An empty value (common in containers and CI) made the data root ./supremeteam,
        inside the project when run from it."""
        default = (Path.home() / ".local" / "share" / "supremeteam").resolve()
        with mock.patch.object(sys, "platform", "linux"):
            for value in ("", "relative/data"):
                with self.subTest(value=value):
                    self.assertEqual(global_data_root({"XDG_DATA_HOME": value}), default)
            self.assertEqual(global_data_root({"XDG_DATA_HOME": str(self.root / "xdg")}),
                             (self.root / "xdg" / "supremeteam").resolve())


if __name__ == "__main__":
    unittest.main()
