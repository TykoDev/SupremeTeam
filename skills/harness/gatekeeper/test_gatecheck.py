#!/usr/bin/env python3
"""Regression tests for the SupremeTeam gatekeeper deterministic gate engine.

Covers the mechanical checks the ``gatekeeper-*`` scripts rely on: frontmatter
parsing, required-artifact pass/fail, conditional artifacts and the contracts they
derive from, one-file-per-slot matching on names, whole words and packet fields,
links out of the package, project-root containment, mixed-revision detection,
skip-record validation, blocked-phrase hits, idempotency drift against Markdown and
JSON priors, harness-doctrine §5 structure, and fail-loud behavior on a missing
package. ``test_gate_wrappers.py`` runs the wrapper scripts themselves.

Run from the repo root:
    python -m unittest discover -s SupremeTeam/harness/gatekeeper -p "test_*.py"
"""

import json
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(ENGINE_DIR.parents[1] / "scripts"))

import _gatecheck as gc  # noqa: E402
import data_formats  # noqa: E402


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


def _slot(key: str, patterns, **more) -> gc.ArtifactSpec:
    return gc.ArtifactSpec(key=key, label=key, patterns=patterns, **more)


def _slots(report) -> dict:
    """Slot label -> present | missing | conditional, read off the findings."""
    status = {}
    for f in report.findings:
        if f.code == "ARTIFACT_PRESENT":
            status[f.message.removesuffix(" present.")] = "present"
        elif f.code == "ARTIFACT_MISSING":
            status[f.message.removeprefix("Required artifact missing: ").split(" (expected", 1)[0]] = "missing"
        elif f.code == "ARTIFACT_CONDITIONAL":
            status[f.message.split(" not found.", 1)[0]] = "conditional"
    return status


PACKET = "Outcome:     lens, r1, 0 findings\nFindings:    (none)\n"


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


class PackageMatchingTests(unittest.TestCase):
    """A slot is filled by one file whose name and structure both fit."""

    def _run(self, pkg: Path, *specs) -> dict:
        return _slots(gc.run_gate(pkg, _manifest(*specs)))

    def test_directory_names_never_match_a_pattern(self):
        with _package() as pkg:
            _write(pkg, "x.md", "pass")
            (pkg / "latest").mkdir()
            (pkg / "latest" / "x.md").write_text("pass", encoding="utf-8")
            status = self._run(pkg, _slot("tests", ("*test*.md",), content_marker="pass"))
        self.assertEqual(status, {"tests": "missing"})

    def test_a_word_inside_a_longer_one_under_a_directory_that_fits_is_not_a_test_report(self):
        """SEC-T-06's trigger: tests/bypass-notes.md meets `*test*.md` by its directory and `pass` by "bypass"."""
        with _package() as pkg:
            (pkg / "tests").mkdir()
            (pkg / "tests" / "bypass-notes.md").write_text("notes on the bypass", encoding="utf-8")
            status = self._run(pkg, _slot("tests", ("*test*.md",), content_marker="tests?|coverage|pass|fail|suite"))
        self.assertEqual(status, {"tests": "missing"})

    def test_a_marker_matches_whole_words_only(self):
        with _package() as pkg:
            _write(pkg, "tests.md", "The password, the compass and a bypass are not a result.")
            spec = _slot("tests", ("*test*.md",), content_marker="pass")
            self.assertEqual(self._run(pkg, spec), {"tests": "missing"})
            _write(pkg, "tests.md", "Tests ran; pass_rate 100 and pass-count 12.")
            self.assertEqual(self._run(pkg, spec), {"tests": "present"})

    def test_a_hollow_file_does_not_fill_a_packet_slot(self):
        with _package() as pkg:
            _write(pkg, "bug.md", "bug")
            status = self._run(pkg, _slot("lens_bug", ("*bug*.md",), fields=("Outcome", "Findings")))
        self.assertEqual(status, {"lens_bug": "missing"})

    def test_packet_fields_are_field_lines(self):
        spec = _slot("lens", ("*lens*.md",), fields=("Outcome", "Findings"))
        accepted = {
            "plain": PACKET,
            "fenced": "```text\n" + PACKET + "```\n",
            "bold": "- **Outcome:** ok\n- **Findings:** none\n",
            "quoted": "> Outcome: ok\n> Findings: none\n",
            "frontmatter": "---\nOutcome: ok\nFindings: none\n---\n",
        }
        for shape, body in accepted.items():
            with self.subTest(shape=shape), _package() as pkg:
                _write(pkg, "lens.md", body)
                self.assertEqual(self._run(pkg, spec), {"lens": "present"})
        with self.subTest(shape="prose"), _package() as pkg:
            _write(pkg, "lens.md", "The Outcome: was fine and the Findings: none.\n")
            self.assertEqual(self._run(pkg, spec), {"lens": "missing"})

    def test_one_file_fills_one_slot(self):
        """A single stand-in that names four lenses and carries the packet fields fills one."""
        with _package() as pkg:
            _write(pkg, "deliverable_security-bug-code-quality.md", PACKET)
            specs = [_slot(name, (f"*{name}*.md",), fields=("Outcome", "Findings"))
                     for name in ("bug", "code", "quality", "security")]
            status = self._run(pkg, *specs)
        self.assertEqual(sorted(status.values()), ["missing", "missing", "missing", "present"])

    def test_overlapping_candidates_are_rerouted_so_every_slot_can_be_filled(self):
        with _package() as pkg:
            _write(pkg, "alpha-beta.md", "x")
            _write(pkg, "beta.md", "x")
            status = self._run(pkg, _slot("first", ("*alpha*.md", "*beta*.md")),
                               _slot("second", ("*alpha*.md",)))
        self.assertEqual(status, {"first": "present", "second": "present"})

    def test_a_chain_of_overlaps_reroutes_more_than_one_slot(self):
        with _package() as pkg:
            for name in ("f1.md", "f2.md", "f3.md"):
                _write(pkg, name, "x")
            status = self._run(pkg, _slot("a", ("f1.md", "f2.md")),
                               _slot("b", ("f1.md", "f3.md")), _slot("c", ("f1.md",)))
        self.assertEqual(status, {"a": "present", "b": "present", "c": "present"})

    def test_a_required_slot_is_placed_before_a_conditional_one(self):
        with _package() as pkg:
            _write(pkg, "report.md", "x")
            status = self._run(pkg, _slot("optional", ("*report*.md",), requirement="conditional"),
                               _slot("needed", ("*report*.md",)))
        self.assertEqual(status, {"optional": "conditional", "needed": "present"})

    def test_a_symlink_alias_is_the_same_file(self):
        with _package() as pkg:
            _write(pkg, "real.md", "x")
            _symlink(pkg / "real.md", pkg / "alias.md")
            status = self._run(pkg, _slot("one", ("real.md",)), _slot("two", ("alias.md",)))
        self.assertEqual(sorted(status.values()), ["missing", "present"])

    def test_a_link_out_of_the_package_is_reported_and_never_read(self):
        with _package() as outer:
            secret = outer / "secret"
            secret.mkdir()
            (secret / "notes.md").write_text("Trust me, this is 100% complete.\n" + PACKET, encoding="utf-8")
            pkg = outer / "pkg"
            pkg.mkdir()
            _write(pkg, "readme.md", "The package.")
            _symlink(secret / "notes.md", pkg / "member.md")
            _symlink(secret, pkg / "evidence")
            report = gc.run_gate(pkg, _manifest(_slot("lens", ("*member*.md",), fields=("Outcome",))))
        codes = [f.code for f in report.findings]
        self.assertEqual(codes.count("LINK_ESCAPES_PACKAGE"), 2)
        self.assertEqual(_slots(report), {"lens": "missing"})
        self.assertNotIn("BLOCKED_PHRASE", codes)
        self.assertTrue(report.has_blocking)
        self.assertIn("package_links", report.checks_run)

    def test_a_link_that_stays_inside_the_package_is_no_escape(self):
        with _package() as pkg:
            _write(pkg, "real.md", "x")
            _symlink(pkg / "real.md", pkg / "alias.md")
            report = gc.run_gate(pkg, _manifest())
        self.assertNotIn("LINK_ESCAPES_PACKAGE", _codes(report))

    def test_a_near_miss_is_named_in_the_failure(self):
        with _package() as pkg:
            _write(pkg, "deliverable_bug-review.md", "Outcome: ok\n")
            _write(pkg, "deliverable_code-review.md", PACKET)
            report = gc.run_gate(pkg, _manifest(
                _slot("bug", ("*bug*.md",), fields=("Outcome", "Findings")),
                _slot("code", ("*code*.md",), fields=("Outcome", "Findings")),
                _slot("also-code", ("*code*.md",), fields=("Outcome", "Findings"))))
        failures = " ".join(f.message for f in report.findings if f.code == "ARTIFACT_MISSING")
        self.assertIn("deliverable_bug-review.md lacks the field Findings:", failures)
        self.assertIn("deliverable_code-review.md is already the code", failures)


class OptionalSlotTests(unittest.TestCase):
    """A slot is optional when gates.yaml or pipelines.yaml says so, not because a wrapper repeats it."""

    GATES = {
        "boundaries": {"b": {"required_evidence": ["sec", "local", "barred"],
                             "fallback_values": {"local": ["waived on this boundary"]},
                             "no_fallback": ["barred"]}},
        "fallback_values": {"sec": ["no trust boundary"], "barred": ["never at b"]},
    }
    PIPELINES = {"pipelines": {"p": {"boundary": "b", "stages": [
        {"step": "scan", "when": "a trust boundary changed"},
        {"step": "always"},
        {"step": "later", "when": "visible behaviour changed"},
    ]}}}

    def _check(self, *, loader=None, pipeline="p", **spec_more) -> gc.Report:
        contracts = gc.Contracts(self.GATES, self.PIPELINES)
        manifest = gc.Manifest(boundary="t", sub_orchestrator="t", pipeline=pipeline,
                               artifacts=(_slot("slot", ("*slot*.md",), **spec_more),))
        target = mock.patch.object(gc.Contracts, "load", loader or mock.Mock(return_value=contracts))
        with _package() as pkg, target:
            _write(pkg, "readme.md", "nothing here")
            return gc.run_gate(pkg, manifest)

    def _finding(self, report):
        return next(f for f in report.findings if f.code.startswith("ARTIFACT_"))

    def test_a_waivable_key_makes_the_slot_conditional(self):
        report = self._check(evidence_key="sec")
        finding = self._finding(report)
        self.assertEqual((finding.code, finding.status), ("ARTIFACT_CONDITIONAL", gc.UNCHECKED))
        self.assertIn('gates.yaml lets a submitter waive sec at b ("no trust boundary")', finding.message)
        self.assertFalse(report.has_blocking)

    def test_a_boundary_level_waiver_counts(self):
        self.assertEqual(self._finding(self._check(evidence_key="local")).code, "ARTIFACT_CONDITIONAL")

    def test_no_fallback_bars_the_waiver(self):
        self.assertEqual(self._finding(self._check(evidence_key="barred")).code, "ARTIFACT_MISSING")

    def test_a_stage_with_a_when_makes_the_slot_conditional(self):
        finding = self._finding(self._check(stages=("scan",)))
        self.assertEqual(finding.code, "ARTIFACT_CONDITIONAL")
        self.assertIn('pipelines.yaml runs scan only when "a trust boundary changed"', finding.message)

    def test_every_producing_stage_must_be_conditional(self):
        self.assertEqual(self._finding(self._check(stages=("scan", "later"))).code, "ARTIFACT_CONDITIONAL")
        self.assertEqual(self._finding(self._check(stages=("scan", "always"))).code, "ARTIFACT_MISSING")

    def test_an_unknown_stage_or_key_relaxes_nothing(self):
        self.assertEqual(self._finding(self._check(stages=("renamed",))).code, "ARTIFACT_MISSING")
        self.assertEqual(self._finding(self._check(evidence_key="renamed")).code, "ARTIFACT_MISSING")

    def test_both_contracts_are_cited_when_both_apply(self):
        message = self._finding(self._check(evidence_key="sec", stages=("scan",))).message
        self.assertIn("gates.yaml lets a submitter waive", message)
        self.assertIn("pipelines.yaml runs scan only when", message)

    def test_a_declared_conditional_slot_stays_conditional(self):
        report = self._check(requirement="conditional")
        self.assertEqual(self._finding(report).code, "ARTIFACT_CONDITIONAL")
        self.assertIn("required only when in scope", self._finding(report).message)

    def test_a_present_file_is_a_pass_even_for_an_optional_slot(self):
        contracts = gc.Contracts(self.GATES, self.PIPELINES)
        manifest = gc.Manifest(boundary="t", sub_orchestrator="t", pipeline="p",
                               artifacts=(_slot("slot", ("*slot*.md",), stages=("scan",)),))
        with _package() as pkg, mock.patch.object(gc.Contracts, "load", return_value=contracts):
            _write(pkg, "slot.md", "here")
            self.assertEqual(_slots(gc.run_gate(pkg, manifest)), {"slot": "present"})

    def test_unreadable_contracts_keep_the_declared_requirement_and_say_so(self):
        failing = mock.Mock(side_effect=gc.ContractsUnreadable("gates.yaml: gone"))
        report = self._check(loader=failing, stages=("scan",))
        codes = {f.code: f for f in report.findings}
        self.assertEqual(codes["ARTIFACT_MISSING"].status, gc.FAIL)
        self.assertEqual(codes["CONTRACTS_UNREADABLE"].status, gc.UNCHECKED)
        self.assertIn("gates.yaml: gone", codes["CONTRACTS_UNREADABLE"].message)

    def test_contracts_are_not_read_when_no_slot_cites_one_or_no_pipeline_is_named(self):
        loader = mock.Mock(side_effect=AssertionError("must not be read"))
        self._check(loader=loader)
        self._check(loader=loader, pipeline=None, stages=("scan",))
        loader.assert_not_called()

    def test_load_reads_a_catalog_and_answers_from_it(self):
        with _scratch() as base, mock.patch.object(sys, "path", list(sys.path)):
            (base / "gates.yaml").write_text(json.dumps(self.GATES), encoding="utf-8")
            (base / "pipelines.yaml").write_text(json.dumps(self.PIPELINES), encoding="utf-8")
            contracts = gc.Contracts.load(base)
        self.assertEqual(contracts.boundary_of("p"), "b")
        self.assertEqual(contracts.waiver("b", "sec"), "no trust boundary")
        self.assertIsNone(contracts.waiver("b", "barred"))
        self.assertEqual(contracts.stage_condition("p", "scan"), "a trust boundary changed")
        self.assertIsNone(contracts.stage_condition("p", "always"))

    def test_load_fails_loudly_on_a_broken_catalog(self):
        with _scratch() as base, mock.patch.object(sys, "path", list(sys.path)):
            (base / "gates.yaml").write_text("{not json", encoding="utf-8")
            (base / "pipelines.yaml").write_text("{}", encoding="utf-8")
            with self.assertRaises(gc.ContractsUnreadable):
                gc.Contracts.load(base)
            (base / "gates.yaml").write_text("[]", encoding="utf-8")
            with self.assertRaises(gc.ContractsUnreadable):
                gc.Contracts.load(base)


class RevisionLabelTests(unittest.TestCase):
    """Gate manifests label revisions r1, r2; handoff templates count 1, 2."""

    def test_mixed_revision_labels_are_flagged(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: r1\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: r2\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("MIXED_REVISIONS", _codes(report))
        self.assertNotIn("REVISION_ABSENT", _codes(report))

    def test_one_label_is_coherent_and_named(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: r1\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: r1\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        coherent = next(f for f in report.findings if f.code == "REVISION_COHERENT")
        self.assertIn("revision r1", coherent.message)

    def test_a_number_and_its_quoted_spelling_are_one_revision(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: 3\n---\nbody")
            _write(pkg, "b.md", '---\nrevision: "3"\n---\nbody')
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("REVISION_COHERENT", _codes(report))

    def test_a_list_or_a_flag_is_no_revision(self):
        with _package() as pkg:
            _write(pkg, "a.md", "---\nrevision: [1, 2]\n---\nbody")
            _write(pkg, "b.md", "---\nrevision: true\n---\nbody")
            report = gc.run_gate(pkg, _manifest())
        self.assertIn("REVISION_ABSENT", _codes(report))


class HiddenLineageTests(unittest.TestCase):
    """G-2: a byte-order mark before the frontmatter or a quoted key hid a file's
    revision and submission id, so a mixed package reported REVISION_COHERENT."""

    SPELLINGS = (
        ("bom", "\ufeff---\nrevision: r2\nsubmission_id: S2\n---\nbody"),
        ("double-quoted keys", '---\n"revision": r2\n"submission_id": S2\n---\nbody'),
        ("single-quoted keys", "---\n'revision': r2\n'submission_id': S2\n---\nbody"),
        ("bom and quoted keys", "\ufeff---\n\"revision\": r2\n'submission_id': S2\n---\nbody"),
    )

    def test_a_bom_or_a_quoted_key_does_not_hide_a_second_revision(self):
        for name, body in self.SPELLINGS:
            with self.subTest(spelling=name), _package() as pkg:
                _write(pkg, "a.md", "---\nrevision: r1\nsubmission_id: S1\n---\nbody")
                _write(pkg, "b.md", body)
                report = gc.run_gate(pkg, _manifest())
                codes = _codes(report)
                self.assertIn("MIXED_REVISIONS", codes)
                self.assertIn("MIXED_SUBMISSION_IDS", codes)
                self.assertNotIn("REVISION_COHERENT", codes)
                self.assertTrue(report.has_blocking)

    def test_the_parser_reads_the_key_not_its_quotes(self):
        self.assertEqual(gc.parse_frontmatter("\ufeff---\nrevision: 3\n---\n"), {"revision": 3})
        self.assertEqual(gc.parse_frontmatter('---\n"revision": 3\n\'a: b\': c\n---\n'),
                         {"revision": 3, "a: b": "c"})

    def test_a_bom_does_not_hide_a_json_prior_record(self):
        with _package() as pkg, _package() as side:
            _write(pkg, "a.md", "---\nsubmission_id: S3\nrevision: r2\n---\n")
            prior = side / "prior.json"
            prior.write_text("\ufeff" + json.dumps({"submission_id": "S3", "revision": "r1"}), encoding="utf-8")
            report = gc.run_gate(pkg, _manifest(), prior_path=prior)
        self.assertIn("SILENT_DRIFT", _codes(report))


class EmptyEvidenceTests(unittest.TestCase):
    """G-5: a zero-byte or whitespace-only file filled a slot that asks for no marker."""

    def test_an_empty_or_blank_file_fills_no_slot_and_fails(self):
        for body in ("", "   \n\t\n", "\ufeff", "\ufeff \r\n"):
            for requirement in ("required", "conditional"):
                with self.subTest(body=body, requirement=requirement), _package() as pkg:
                    _write(pkg, "report_tests.md", body)
                    _write(pkg, "other.md", "---\nrevision: r1\n---\nbody")
                    spec = gc.ArtifactSpec(key="tests", label="tests", patterns=("*tests*.md",),
                                           requirement=requirement)
                    report = gc.run_gate(pkg, _manifest(spec))
                    codes = _codes(report)
                    self.assertIn("ARTIFACT_EMPTY", codes)
                    self.assertNotIn("ARTIFACT_PRESENT", codes)
                    self.assertTrue(report.has_blocking)
                    self.assertEqual(report.exit_code(), 1)

    def test_a_file_with_content_is_unaffected(self):
        with _package() as pkg:
            _write(pkg, "report_tests.md", "\ufeff# Tests\n")
            spec = gc.ArtifactSpec(key="tests", label="tests", patterns=("*tests*.md",))
            report = gc.run_gate(pkg, _manifest(spec))
        self.assertIn("ARTIFACT_PRESENT", _codes(report))
        self.assertNotIn("ARTIFACT_EMPTY", _codes(report))


class RuntimeFloorTests(unittest.TestCase):
    """G-12: below the floor the wrappers named no floor; they crashed on Path.is_junction."""

    def test_the_floor_comes_from_the_runtime_manifest(self):
        with _scratch() as base:
            manifest = base / "runtime-manifest.yaml"
            manifest.write_text(json.dumps({"runtime": {"python": {"minimum": "3.13"}}}), encoding="utf-8")
            self.assertIsNone(gc.runtime_floor_error((3, 13), manifest))
            self.assertIsNone(gc.runtime_floor_error((3, 14), manifest))
            message = gc.runtime_floor_error((3, 11), manifest)
            self.assertIn("Python 3.11 is below the runtime floor 3.13", message)

    def test_an_unreadable_floor_refuses_to_run(self):
        with _scratch() as base:
            manifest = base / "runtime-manifest.yaml"
            for text in (None, "{broken", json.dumps({"runtime": {}}),
                         json.dumps({"runtime": {"python": {"minimum": "three"}}})):
                with self.subTest(text=text):
                    if text is None:
                        manifest.unlink(missing_ok=True)
                    else:
                        manifest.write_text(text, encoding="utf-8")
                    self.assertIn("cannot read the Python floor", gc.runtime_floor_error((3, 13), manifest))

    def test_the_shipped_floor_is_read(self):
        self.assertIsNone(gc.runtime_floor_error(tuple(sys.version_info)))
        self.assertIn("below the runtime floor", gc.runtime_floor_error((3, 11)))

    def test_a_wrapper_below_the_floor_exits_2_before_reading_the_package(self):
        with _package() as pkg, mock.patch.object(sys, "version_info", (3, 11, 9, "final", 0)), \
                mock.patch.object(gc, "run_gate", side_effect=AssertionError("must not run")), \
                mock.patch("sys.stderr") as err, mock.patch("sys.stdout") as out:
            self.assertEqual(gc.main_with_manifest(_manifest(), [str(pkg)]), 2)
        written = "".join(call.args[0] for call in err.write.call_args_list)
        self.assertIn("below the runtime floor", written)
        out.write.assert_not_called()


class PriorRecordTests(unittest.TestCase):
    """--prior reads Markdown frontmatter and the JSON the boundary validator writes."""

    def _idempotency(self, package_files: dict, prior_text: str, name: str = "prior.json"):
        with _package() as pkg, _package() as side:
            for rel, body in package_files.items():
                _write(pkg, rel, body)
            prior = side / name
            prior.write_text(prior_text, encoding="utf-8")
            report = gc.run_gate(pkg, _manifest(), prior_path=prior)
        return report, {f.code: f for f in report.findings}

    def test_a_json_verdict_record_is_reusable_for_the_same_submission_and_revision(self):
        record = json.dumps({"submission_id": "S3", "revision": "r2", "pass": True,
                             "package_fingerprint": "f", "mechanical_only": True})
        report, found = self._idempotency({"a.md": "---\nsubmission_id: S3\nrevision: r2\n---\n"}, record)
        self.assertIn("VERDICT_REUSABLE", found)
        self.assertIn("verdict=mechanical pass", found["VERDICT_REUSABLE"].message)
        self.assertNotIn("NEW_SUBMISSION", found)

    def test_a_json_verdict_record_detects_drift(self):
        record = json.dumps({"submission_id": "S3", "revision": "r1"})
        report, found = self._idempotency({"a.md": "---\nsubmission_id: S3\nrevision: r2\n---\n"}, record)
        self.assertIn("SILENT_DRIFT", found)
        self.assertTrue(report.has_blocking)

    def test_a_json_verdict_record_for_another_submission_is_new(self):
        record = json.dumps({"submission_id": "OTHER", "revision": "r1"})
        _, found = self._idempotency({"a.md": "---\nsubmission_id: S3\nrevision: r1\n---\n"}, record)
        self.assertIn("NEW_SUBMISSION", found)

    def test_the_packages_own_manifest_declares_its_identity(self):
        """Lens packets carry no frontmatter; the phase manifest.json is where the id lives."""
        manifest = json.dumps({"submission_id": "S3", "revision": "r2"})
        record = json.dumps({"submission_id": "S3", "revision": "r2"})
        _, found = self._idempotency({"manifest.json": manifest, "packet.md": PACKET}, record)
        self.assertIn("VERDICT_REUSABLE", found)

    def test_an_undeclared_identity_is_undetermined_not_a_fresh_pass(self):
        record = json.dumps({"submission_id": "S3", "revision": "r1"})
        report, found = self._idempotency({"packet.md": PACKET}, record)
        self.assertIn("IDEMPOTENCY_UNDETERMINED", found)
        self.assertEqual(found["IDEMPOTENCY_UNDETERMINED"].status, gc.UNCHECKED)
        self.assertNotIn("NEW_SUBMISSION", found)
        self.assertFalse(report.has_blocking)

    def test_an_unreadable_prior_is_undetermined(self):
        for text in ("not a record at all", "[1, 2]", "{broken", ""):
            with self.subTest(text=text):
                _, found = self._idempotency({"a.md": "---\nsubmission_id: S3\nrevision: r1\n---\n"}, text)
                self.assertIn("IDEMPOTENCY_UNDETERMINED", found)
                self.assertNotIn("NEW_SUBMISSION", found)

    def test_a_matching_id_with_an_unreadable_revision_is_undetermined(self):
        record = json.dumps({"submission_id": "S3"})
        _, found = self._idempotency({"a.md": "---\nsubmission_id: S3\nrevision: r1\n---\n"}, record)
        self.assertIn("IDEMPOTENCY_UNDETERMINED", found)
        self.assertNotIn("NEW_SUBMISSION", found)

    def test_a_pending_submission_id_declares_nothing(self):
        record = json.dumps({"submission_id": "PENDING", "revision": "r1"})
        _, found = self._idempotency({"a.md": "---\nsubmission_id: PENDING\nrevision: r1\n---\n"}, record)
        self.assertIn("IDEMPOTENCY_UNDETERMINED", found)

    def test_a_markdown_prior_still_works(self):
        prior = "---\nsubmission_id: S3\nrevision: r2\nverdict: APPROVED\n---\n"
        _, found = self._idempotency({"a.md": "---\nsubmission_id: S3\nrevision: r2\n---\n"}, prior, "prior.md")
        self.assertIn("verdict=APPROVED", found["VERDICT_REUSABLE"].message)


class LayerCitationTests(unittest.TestCase):
    """harness-doctrine §5: the citation the failure message asks for satisfies the check."""

    def _report(self, body: str):
        with _package() as pkg:
            _write(pkg, "change.md", body)
            return gc.run_gate(pkg, _manifest())

    def test_a_section_number_in_the_words_of_the_failure_message_counts(self):
        for citation in ("(§1)", "see §1", "§ 4", "harness-doctrine", "Layer 3"):
            with self.subTest(citation=citation):
                report = self._report(f"A new PreToolUse hook, {citation}. Regression: none observed.")
                self.assertIn("DOCTRINE_NOTE_PRESENT", _codes(report))
                self.assertNotIn("DOCTRINE_GAP", _codes(report))

    def test_a_section_outside_the_doctrine_does_not(self):
        for citation in ("§ 10", "§6", "xLayer 2", "the harness-doctrines"):
            with self.subTest(citation=citation):
                report = self._report(f"A new PreToolUse hook, {citation}. Regression: none observed.")
                self.assertIn("DOCTRINE_GAP", _codes(report))


class VersionTokenTests(unittest.TestCase):
    """A version keeps its spelling: 3.10 is not 3.1, and the registry compares text."""

    def test_a_spelling_that_does_not_round_trip_stays_text(self):
        parsed = data_formats.parse_yaml("versions: [3.10, 1.20, 3.12, 0.115, 2]\nbare: 3.10\n")
        self.assertEqual(parsed["versions"], ["3.10", "1.20", 3.12, 0.115, 2])
        self.assertEqual(parsed["bare"], "3.10")

    def test_a_canonical_number_is_still_a_number(self):
        for text, value in (("1.5", 1.5), ("0.115", 0.115), ("-2.0", -2.0), ("10.0", 10.0), ("12", 12)):
            with self.subTest(text=text):
                self.assertEqual(data_formats.parse_scalar(text), value)

    def test_the_registry_versions_read_back_as_spelled(self):
        registry = ENGINE_DIR.parents[1] / "tech-stacks" / "registry.yaml"
        spelled = [[token.strip() for token in line.split("[", 1)[1].rstrip("]\n ").split(",")]
                   for line in registry.read_text(encoding="utf-8").splitlines()
                   if line.strip().startswith("versions:")]
        parsed = [[str(v) for v in overlay["versions"]]
                  for overlay in data_formats.load_data(registry)["overlays"]]
        self.assertEqual(parsed, spelled)


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
