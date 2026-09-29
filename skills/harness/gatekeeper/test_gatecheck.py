#!/usr/bin/env python3
"""Regression tests for the SupremeTeam gatekeeper deterministic gate engine.

Covers the mechanical checks the ``gatekeeper-*`` scripts rely on: frontmatter
parsing, required-artifact pass/fail, conditional artifacts, project-root
containment, mixed-revision detection, skip-record validation, blocked-phrase
hits, idempotency drift, harness-doctrine §5 structure, and fail-loud behavior on
a missing package. ``test_gate_wrappers.py`` runs the wrapper scripts themselves.

Run from the repo root:
    python -m unittest discover -s SupremeTeam/harness/gatekeeper -p "test_*.py"
"""

import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

import _gatecheck as gc  # noqa: E402


def _project_root() -> Path:
    """Nearest marked ancestor of the working directory (save-ownership.yaml generated_roots)."""
    start = Path.cwd().resolve()
    return next((c for c in (start, *start.parents)
                 if any((c / m).exists() for m in ("skillset-saves", ".harness-state", ".git"))), start)


_TMP_ROOT = _project_root() / ".harness-state" / "test-work" / "gatekeeper"


@contextmanager
def _package():
    _TMP_ROOT.mkdir(parents=True, exist_ok=True)
    pkg = _TMP_ROOT / f"case-{uuid.uuid4().hex}"
    pkg.mkdir(parents=True, exist_ok=False)
    try:
        yield pkg
    finally:
        shutil.rmtree(pkg, ignore_errors=True)
        try:
            _TMP_ROOT.rmdir()
        except OSError:
            pass


def _write(pkg: Path, name: str, body: str) -> None:
    (pkg / name).write_text(body, encoding="utf-8")


def _manifest(*specs) -> gc.Manifest:
    return gc.Manifest(boundary="test", sub_orchestrator="test", artifacts=specs)


def _codes(report) -> set:
    return {f.code for f in report.findings}


class ArtifactPresenceTests(unittest.TestCase):
    def test_json_and_html_artifacts_satisfy_a_spec(self):
        """Evidence records are JSON and prototypes are HTML; presence must see them."""
        spec = _manifest(
            gc.ArtifactSpec(key="parity", label="parity record", patterns=("*parity*.json",)),
            gc.ArtifactSpec(key="app", label="prototype", patterns=("*app*.html",), content_marker=r"data-route"),
        )
        with _package() as pkg:
            (pkg / "evidence").mkdir()
            _write(pkg, "evidence/parity-v1.json", '{"result": {"status": "pass"}}')
            _write(pkg, "app.html", "<main data-route='route.home'></main>")
            report = gc.run_gate(pkg, spec)
            self.assertNotIn("ARTIFACT_MISSING", _codes(report))
            self.assertEqual(sum(1 for f in report.findings if f.code == "ARTIFACT_PRESENT"), 2)


class FrontmatterTests(unittest.TestCase):
    def test_parses_scalars_lists_and_nesting(self):
        text = (
            "---\n"
            "run_id: abc_123\n"
            "revision: 2\n"
            "verdict: APPROVED\n"
            "requested_endpoints: [design, build, review]\n"
            "active_delegation:\n"
            "  target: commander\n"
            "  timeout_seconds: 600\n"
            "---\n"
            "body text\n"
        )
        fm = gc.parse_frontmatter(text)
        self.assertEqual(fm["run_id"], "abc_123")
        self.assertEqual(fm["revision"], 2)
        self.assertEqual(fm["requested_endpoints"], ["design", "build", "review"])
        self.assertEqual(fm["active_delegation"]["target"], "commander")

    def test_no_frontmatter_returns_empty(self):
        self.assertEqual(gc.parse_frontmatter("# just a heading\n"), {})

    def test_block_list_form(self):
        text = "---\nitems:\n  - one\n  - two\n---\n"
        self.assertEqual(gc.parse_frontmatter(text)["items"], ["one", "two"])


class RequiredArtifactTests(unittest.TestCase):
    def test_missing_required_artifact_fails(self):
        with _package() as pkg:
            _write(pkg, "readme.md", "nothing useful")
            manifest = _manifest(gc.ArtifactSpec(
                key="impl", label="implementation", patterns=("*implementation*.md",)))
            report = gc.run_gate(pkg, manifest)
        self.assertIn("ARTIFACT_MISSING", _codes(report))
        self.assertTrue(report.has_blocking)
        self.assertEqual(report.exit_code(), 1)

    def test_present_required_artifact_passes(self):
        with _package() as pkg:
            _write(pkg, "deliverable_implementation.md",
                   "# Impl\nchanged file: app.py module updated")
            manifest = _manifest(gc.ArtifactSpec(
                key="impl", label="implementation",
                patterns=("*implementation*.md",), content_marker=r"changed file"))
            report = gc.run_gate(pkg, manifest)
        self.assertIn("ARTIFACT_PRESENT", _codes(report))
        self.assertFalse(report.has_blocking)

    def test_conditional_artifact_absent_is_unchecked_not_fail(self):
        with _package() as pkg:
            _write(pkg, "plan.md", "the plan")
            manifest = _manifest(gc.ArtifactSpec(
                key="api", label="API contracts", patterns=("*api*.md",),
                requirement="conditional"))
            report = gc.run_gate(pkg, manifest)
        self.assertIn("ARTIFACT_CONDITIONAL", _codes(report))
        self.assertFalse(report.has_blocking)
        self.assertTrue(report.unchecked)


class LineageTests(unittest.TestCase):
    def test_mixed_revisions_flagged(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: 1\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: 2\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("MIXED_REVISIONS", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_single_revision_coherent(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: 3\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: 3\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("REVISION_COHERENT", _codes(report))


class SkipRecordTests(unittest.TestCase):
    def test_incomplete_skip_record_fails(self):
        with _package() as pkg:
            _write(pkg, "_skip-record.md", "---\npipeline: review\n---\nno reason")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("SKIP_RECORD_INCOMPLETE", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_complete_skip_record_passes(self):
        with _package() as pkg:
            _write(pkg, "_skip-record.md",
                   "---\npipeline: review\nskipped_at: 2026-06-06\n"
                   "reason: not in scope\napproved_by: user\n---\n")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("SKIP_RECORD_OK", _codes(report))


class BlockedPhraseTests(unittest.TestCase):
    def test_blocked_phrase_is_blocking(self):
        with _package() as pkg:
            _write(pkg, "summary.md", "This is 100% complete, trust me.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("BLOCKED_PHRASE", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_code_rot_marker_is_blocking(self):
        with _package() as pkg:
            _write(pkg, "notes.md", "implementation done\n# TODO wire up auth")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("BLOCKED_PHRASE", _codes(report))

    def test_clean_package_reports_clean(self):
        with _package() as pkg:
            _write(pkg, "summary.md", "The change adds a validated endpoint.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("BLOCKED_PHRASE_CLEAN", _codes(report))


class IdempotencyTests(unittest.TestCase):
    def test_reused_submission_id_with_new_revision_is_drift(self):
        # The prior verdict lives OUTSIDE the package (a previous phase dir).
        with _package() as pkg, _package() as side:
            _write(pkg, "pkg.md", "---\nsubmission_id: S1\nrevision: 4\n---\n")
            prior = side / "prior.md"
            prior.write_text("---\nsubmission_id: S1\nrevision: 3\n"
                             "verdict: REVISE\n---\n", encoding="utf-8")
            report = gc.run_gate(pkg, _manifest(), prior_path=prior)
        self.assertIn("SILENT_DRIFT", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_same_submission_and_revision_is_reusable(self):
        with _package() as pkg, _package() as side:
            _write(pkg, "pkg.md", "---\nsubmission_id: S2\nrevision: 5\n---\n")
            prior = side / "prior.md"
            prior.write_text("---\nsubmission_id: S2\nrevision: 5\n"
                             "verdict: APPROVED\n---\n", encoding="utf-8")
            report = gc.run_gate(pkg, _manifest(), prior_path=prior)
        self.assertIn("VERDICT_REUSABLE", _codes(report))


class HarnessDoctrineTests(unittest.TestCase):
    def test_intervention_without_layer_or_regression_fails(self):
        with _package() as pkg:
            _write(pkg, "change.md",
                   "We add a new PreToolUse hook that blocks risky writes.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("DOCTRINE_GAP", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_intervention_with_layer_and_regression_is_unchecked(self):
        with _package() as pkg:
            _write(pkg, "change.md",
                   "We add a PostToolUse hook at Layer 4. Regression: confirmed "
                   "it does not block a valid command.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("DOCTRINE_NOTE_PRESENT", _codes(report))
        self.assertFalse(report.has_blocking)

    def test_package_without_intervention_is_inert(self):
        with _package() as pkg:
            _write(pkg, "plan.md", "A normal design plan with no runtime hooks.")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("NO_RUNTIME_INTERVENTION", _codes(report))


class RedesignMockFirstLayoutTests(unittest.TestCase):
    """`gatekeeper-design/scripts/check_redesign.py`'s own layout check.

    The shared engine matches artifacts by glob, which cannot count four mock
    directories or notice a living prototype built for a decision that chose
    none. That check lives in the gate script, and this is the only suite that
    runs it.
    """

    @staticmethod
    def _module():
        import importlib.util
        path = (ENGINE_DIR.parents[1] / "design" / "gatekeeper-design" / "scripts"
                / "check_redesign.py")
        spec = importlib.util.spec_from_file_location("check_redesign_under_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _draw(pkg: Path, mocks: int, decision: str | None, builds=()):
        for index in range(1, mocks + 1):
            mock = pkg / "artifacts" / "mocks" / f"m{index}"
            mock.mkdir(parents=True, exist_ok=True)
            (mock / "mock.html").write_text(
                f'<html><body data-mock="true"><main data-route="r{index}"></main></body></html>\n',
                encoding="utf-8")
        reports = pkg / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        if decision is not None:
            (reports / "selection.md").write_text(
                f"---\ndecision: {decision}\n---\n\n# Selection\n\nRecorded.\n", encoding="utf-8")
        for name in builds:
            built = pkg / "artifacts" / "variants" / name
            built.mkdir(parents=True, exist_ok=True)
            (built / "app.html").write_text("<html><body></body></html>\n", encoding="utf-8")

    def _report(self, pkg: Path):
        module = self._module()
        report = gc.Report(boundary="layout", package_path=str(pkg))
        module.check_mock_first_layout(pkg, report)
        return report

    def test_four_mocks_a_selection_and_one_build_pass(self):
        with _package() as pkg:
            self._draw(pkg, 4, "variant", builds=("m2",))
            report = self._report(pkg)
        self.assertEqual({"MOCK_SET_COMPLETE", "SELECTION_RECORDED", "SELECTED_BUILD_PRESENT"},
                         _codes(report))
        self.assertFalse(report.has_blocking)

    def test_a_short_mock_field_fails(self):
        with _package() as pkg:
            self._draw(pkg, 3, "variant", builds=("m2",))
            report = self._report(pkg)
        self.assertIn("MOCK_SET_INCOMPLETE", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_a_missing_selection_fails(self):
        with _package() as pkg:
            self._draw(pkg, 4, None)
            report = self._report(pkg)
        self.assertIn("SELECTION_MISSING", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_a_deferral_that_shipped_a_prototype_fails(self):
        with _package() as pkg:
            self._draw(pkg, 4, "deferred", builds=("m1",))
            report = self._report(pkg)
        self.assertIn("UNSELECTED_BUILD_PRESENT", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_a_deferral_with_no_prototype_passes(self):
        with _package() as pkg:
            self._draw(pkg, 4, "deferred")
            report = self._report(pkg)
        self.assertIn("NO_BUILD_AS_DECIDED", _codes(report))
        self.assertFalse(report.has_blocking)

    def test_four_built_prototypes_fail_even_on_a_variant_decision(self):
        """The shape the mock-first pipeline exists to prevent."""
        with _package() as pkg:
            self._draw(pkg, 4, "variant", builds=("m1", "m2", "m3", "m4"))
            report = self._report(pkg)
        self.assertIn("SELECTED_BUILD_COUNT", _codes(report))
        self.assertTrue(report.has_blocking)

    def test_an_unreadable_decision_is_unchecked_not_a_pass(self):
        with _package() as pkg:
            self._draw(pkg, 4, None, builds=("m2",))
            (pkg / "reports" / "selection.md").write_text(
                "# Selection\n\nThe team talked it over.\n", encoding="utf-8")
            report = self._report(pkg)
        self.assertIn("SELECTION_DECISION_UNREAD", _codes(report))
        self.assertIn("BUILD_WITHOUT_READABLE_DECISION", _codes(report))
        self.assertFalse(report.has_blocking)
        self.assertEqual("NEEDS_JUDGMENT", report.gate_status())

    def test_a_body_line_states_the_decision_when_frontmatter_does_not(self):
        with _package() as pkg:
            self._draw(pkg, 4, None)
            (pkg / "reports" / "selection.md").write_text(
                "# Selection\n\n- **Decision:** merge\n", encoding="utf-8")
            report = self._report(pkg)
        self.assertIn("SELECTION_RECORDED", _codes(report))
        self.assertIn("NO_BUILD_AS_DECIDED", _codes(report))


def _symlink(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as exc:
        raise unittest.SkipTest(f"symlinks are unavailable here: {exc}") from exc


@contextmanager
def _scratch():
    with tempfile.TemporaryDirectory() as raw:
        yield Path(raw).resolve()


class ProjectRootTests(unittest.TestCase):
    def test_the_nearest_marked_ancestor_wins_and_the_start_itself_counts(self):
        with _scratch() as base:
            outer, inner = base / "outer", base / "outer" / "inner"
            (outer / ".git").mkdir(parents=True)
            (inner / "deep").mkdir(parents=True)
            (inner / "skillset-saves").mkdir()
            self.assertEqual(gc.find_project_root(inner / "deep"), inner)
            self.assertEqual(gc.find_project_root(inner), inner)
            self.assertEqual(gc.find_project_root(outer), outer)

    def test_each_marker_kind_marks_a_project(self):
        """A worktree's .git is a file, and .harness-state alone marks a project."""
        with _scratch() as base:
            (base / "file-git").mkdir()
            (base / "file-git" / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
            (base / "state").mkdir()
            (base / "state" / ".harness-state").mkdir()
            self.assertEqual(gc.find_project_root(base / "file-git"), base / "file-git")
            self.assertEqual(gc.find_project_root(base / "state"), base / "state")

    def test_no_marker_means_no_root(self):
        with _scratch() as base:
            if gc.find_project_root(base) is not None:
                self.skipTest("a project marker exists above the temporary directory")
            self.assertIsNone(gc.find_project_root(base))

    def test_the_marker_tuple_is_the_documented_three(self):
        self.assertEqual(set(gc.ROOT_MARKERS), {"skillset-saves", ".harness-state", ".git"})


class PackageContainmentTests(unittest.TestCase):
    """resolve_package_dir: the guard every wrapper shares."""

    @staticmethod
    def _project(base: Path, name: str = "project"):
        project = base / name
        (project / ".git").mkdir(parents=True)
        package = project / "skillset-saves" / "runs" / "r-1" / "review"
        package.mkdir(parents=True)
        return project, package

    def test_a_package_inside_the_working_projects_root_resolves(self):
        with _scratch() as base:
            project, package = self._project(base)
            self.assertEqual(gc.resolve_package_dir(str(package), cwd=project), package)
            self.assertEqual(gc.resolve_package_dir(str(package), cwd=package), package)
            self.assertEqual(gc.resolve_package_dir(str(project), cwd=project), project)

    def test_a_package_outside_is_refused_however_it_is_named(self):
        with _scratch() as base:
            project, package = self._project(base)
            outside = base / "outside" / "pkg"
            outside.mkdir(parents=True)
            link = project / "skillset-saves" / "runs" / "r-2"
            _symlink(outside, link)
            named = {
                "directly": str(outside),
                "with ..": str(package / ".." / ".." / ".." / ".." / ".." / "outside" / "pkg"),
                "through a symlink": str(link),
            }
            for how, raw in named.items():
                with self.subTest(how=how):
                    with self.assertRaisesRegex(gc.PackageRefused, "outside the project"):
                        gc.resolve_package_dir(raw, cwd=project)

    def test_the_project_is_the_working_directorys_not_the_packages(self):
        with _scratch() as base:
            here, _ = self._project(base, "here")
            _, theirs = self._project(base, "theirs")
            with self.assertRaisesRegex(gc.PackageRefused, "outside the project"):
                gc.resolve_package_dir(str(theirs), cwd=here)

    def test_a_working_directory_in_no_project_falls_back_to_the_packages_own(self):
        with _scratch() as base:
            _, package = self._project(base)
            bare = base / "bare"
            bare.mkdir()
            if gc.find_project_root(bare) is not None:
                self.skipTest("a project marker exists above the temporary directory")
            self.assertEqual(gc.resolve_package_dir(str(package), cwd=bare), package)

    def test_no_project_anywhere_is_refused(self):
        with _scratch() as base:
            loose = base / "loose"
            loose.mkdir()
            if gc.find_project_root(loose) is not None:
                self.skipTest("a project marker exists above the temporary directory")
            with self.assertRaisesRegex(gc.PackageRefused, "cannot locate a project root"):
                gc.resolve_package_dir(str(loose), cwd=base)

    def test_a_missing_path_and_a_file_are_refused(self):
        with _scratch() as base:
            project, package = self._project(base)
            note = package / "note.md"
            note.write_text("x", encoding="utf-8")
            for raw in (str(package / "nope"), str(note)):
                with self.assertRaisesRegex(gc.PackageRefused, "not a directory"):
                    gc.resolve_package_dir(raw, cwd=project)

    def test_a_path_the_platform_cannot_read_is_refused_not_raised(self):
        """Exit 2 is the guard's answer; a traceback would exit 1, which reads as a package defect."""
        with _scratch() as base:
            project, _ = self._project(base)
            for raw in ("a\0b", "x" * 5000):
                with self.subTest(raw=raw[:8]):
                    with self.assertRaises(gc.PackageRefused):
                        gc.resolve_package_dir(raw, cwd=project)


class FailLoudTests(unittest.TestCase):
    def test_missing_package_is_critical_fail(self):
        report = gc.run_gate(_TMP_ROOT / "does-not-exist", _manifest())
        self.assertIn("PACKAGE_NOT_FOUND", _codes(report))
        self.assertEqual(report.exit_code(), 1)

    def test_empty_package_is_critical_fail(self):
        with _package() as pkg:
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("PACKAGE_EMPTY", _codes(report))
        self.assertEqual(report.exit_code(), 1)


if __name__ == "__main__":
    unittest.main()
