#!/usr/bin/env python3
"""Subprocess tests for the five gate wrapper scripts.

No test executed a wrapper before: ``test_gatecheck.py`` imports the engine and
loads ``check_redesign.py`` without running it, so the package-directory guard,
the argument handling, and the bootstrap were untested in every copy, while two of
the five refused the canonical ``skillset-saves/runs/<run>/<phase>`` path. Each
test here runs a real script as a child process against real files in temporary
directories, in the three places the catalog is used from: this checkout, a copy
vendored inside another project, and the installed layout (``~/.agents/skills``
beside the user's project).

Run from the repo root:
    python -m unittest discover -s skills/harness/gatekeeper -p "test_gate_wrappers.py"
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from typing import Callable, NamedTuple

ENGINE_DIR = Path(__file__).resolve().parent
SKILLS = ENGINE_DIR.parents[1]
REPO = SKILLS.parent
sys.path.insert(0, str(ENGINE_DIR))

import _gatecheck as gc  # noqa: E402

# A lens packet in the shape review/*/SKILL.md fixes, fenced the way the review
# run's own deliverables are.
PACKET = (
    "# {lens} deliverable\n\n```text\n"
    "Outcome:     {lens}, r1, 0 findings: 0 Critical, 0 Major, 0 Minor, 0 Info\n"
    "Evidence:    files traced\nFindings:    (none)\nOpen risks:  none\n"
    "Next action: none\nRevision:    r1\n```\n"
)


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _review(pkg: Path, full: bool) -> None:
    lenses = ["bug-review", "code-review", "quality-review"]
    if full:
        lenses += ["security-review", "frontier", "cso"]
    for lens in lenses:
        _write(pkg / f"deliverable_{lens}.md", PACKET.format(lens=lens))


def _delivery(pkg: Path, full: bool) -> None:
    _write(pkg / "reports" / "handoff_review-to-delivery.md",
           "---\nsubmission_id: S1\nrevision: 1\npackage_path: skillset-saves/runs/r-1/review\n"
           "verdict: PENDING\n---\n# Handoff\n")
    if full:
        _write(pkg / "reports" / "delivery-package.md", "# Delivery package\n")


def _build(pkg: Path, full: bool) -> None:
    _write(pkg / "reports" / "report_implementation.md",
           "# Implementation\nChanged files: app.py; the module was updated.\n")
    _write(pkg / "reports" / "report_tests.md",
           "# Test results\nThe suite passed: 12 tests, coverage recorded.\n")
    _write(pkg / "reports" / "report_completeness.md",
           "# Completeness\nThe build is complete and certified.\n")
    if full:
        _write(pkg / "reports" / "report_security.md",
               "# Security\nThe security-builder outcome: no findings, a clean bill.\n")
        _write(pkg / "reports" / "gatekeeper-verdict.md", "# Verdict lineage\nNone yet at this revision.\n")


def _design(pkg: Path, full: bool) -> None:
    _write(pkg / "reports" / "report_research.md",
           "# Requirements Brief\nResearch findings and evidence.\n")
    _write(pkg / "reports" / "report_plan.md", "# Delivery Plan\nMilestones and scope.\n")
    _write(pkg / "reports" / "architecture.md",
           "# Architecture\nA decision record for each component.\n")
    _write(pkg / "reports" / "report_implementation-spec.md",
           "# Implementation Spec\nInterface contracts.\n")
    if full:
        _write(pkg / "reports" / "report_stack-lock.md", "# Stack lock\nThe locked stack and its versions.\n")
        _write(pkg / "artifacts" / "taste-snapshot.md",
               "# Taste snapshot\nCanonical digest, source revisions, resolved entries, applicability.\n")
        _write(pkg / "reports" / "api-contracts.md", "# Endpoints\nOne contract per endpoint.\n")
        _write(pkg / "reports" / "design-system.md", "# Design system\nThe UI handoff.\n")


def _redesign(pkg: Path, full: bool) -> None:
    _write(pkg / "reports" / "design-inventory.md", "# Design inventory\nRoutes and components.\n")
    _write(pkg / "reports" / "taste-grilling.md",
           "# Taste grilling\nCategory by category, the preferences and decisions.\n")
    _write(pkg / "reports" / "directions.md",
           "# Directions\nFour directions, differentiated by taste.\n")
    _write(pkg / "reports" / "variant.md", "# Variant\nComponent Template and tokens.\n")
    _write(pkg / "reports" / "selection.md",
           "---\ndecision: deferred\n---\n# Selection\nThe recorded decision.\n")
    _write(pkg / "evidence" / "parity.json", '{"result": {"status": "pass"}}\n')
    _write(pkg / "reports" / "redesign-package.md",
           "# Redesign package\nThe recommendation and comparison matrix.\n")
    for mock in ("m1", "m2", "m3", "m4"):
        _write(pkg / "artifacts" / "mocks" / mock / "mock.html", "<html><body></body></html>\n")
    if full:
        _write(pkg / "evidence" / "rendered-verification.json", "{}\n")


class Wrapper(NamedTuple):
    name: str
    script: str            # under skills/
    phase: str             # the phase directory the package lives in
    write: Callable[[Path, bool], None]   # (package dir, fill every slot?)
    boundary: str          # what the report names
    present: int           # slots a full package fills
    minimal: int           # slots the required-only package fills
    optional: int          # slots the required-only package leaves to the model


WRAPPERS = (
    Wrapper("gatekeeper-code", "review/gatekeeper-code/scripts/check.py", "review",
            _review, "review-to-delivery", 6, 3, 3),
    Wrapper("gatekeeper-admiral", "gatekeeper-admiral/scripts/check.py", "delivery",
            _delivery, "cross-stage handoff (admiral)", 2, 1, 1),
    Wrapper("gatekeeper-build", "build/gatekeeper-build/scripts/check.py", "build",
            _build, "build-to-review", 5, 3, 2),
    Wrapper("gatekeeper-design", "design/gatekeeper-design/scripts/check.py", "design",
            _design, "design phase-exit", 8, 4, 4),
    Wrapper("check_redesign", "design/gatekeeper-design/scripts/check_redesign.py", "redesign",
            _redesign, "redesign phase-exit (redesign-review)", 8, 7, 1),
)


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=120)


def _copy_catalog(dest: Path) -> Path:
    shutil.copytree(SKILLS, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest


def _symlink(target: Path, link: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError) as exc:
        raise unittest.SkipTest(f"symlinks are unavailable here: {exc}") from exc


class Layout(NamedTuple):
    name: str
    skills: Path           # the catalog the script runs from
    project: Path          # the working directory: where the operator stands
    runs: Path             # where this layout's run directories go


class WrapperLayoutTests(unittest.TestCase):
    """Every wrapper checks the canonical package from every place it is used."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name).resolve()
        cls._scratch = REPO / ".harness-state" / "test-work" / "gate-wrappers" / uuid.uuid4().hex

        # This checkout: the catalog is <repo>/skills and the project is <repo>.
        checkout = Layout("checkout", SKILLS, REPO, cls._scratch / "skillset-saves" / "runs")

        # Vendored: the catalog sits inside the project, deeper than skills/, and
        # the project is marked by .git alone.
        vendored_project = base / "vendored" / "project"
        (vendored_project / ".git").mkdir(parents=True)
        vendored = Layout(
            "vendored",
            _copy_catalog(vendored_project / "third_party" / "supreme-team" / "skills"),
            vendored_project, vendored_project / "skillset-saves" / "runs")

        # Installed: ~/.agents/skills holds the catalog and the project is
        # elsewhere; the only marker is the skillset-saves the run creates.
        installed_project = base / "installed" / "work" / "project"
        installed_project.mkdir(parents=True)
        installed = Layout(
            "installed",
            _copy_catalog(base / "installed" / "home" / ".agents" / "skills"),
            installed_project, installed_project / "skillset-saves" / "runs")
        cls.layouts = (checkout, vendored, installed)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        shutil.rmtree(cls._scratch, ignore_errors=True)
        try:
            cls._scratch.parent.rmdir()
        except OSError:
            pass

    def test_every_wrapper_checks_the_canonical_package_in_every_layout(self):
        for layout in self.layouts:
            for wrapper in WRAPPERS:
                with self.subTest(layout=layout.name, wrapper=wrapper.name):
                    package = layout.runs / f"r-{uuid.uuid4().hex[:8]}" / wrapper.phase
                    wrapper.write(package, True)
                    relative = os.path.relpath(package, layout.project)
                    done = _run(layout.skills / wrapper.script, relative, "--json",
                                cwd=layout.project)
                    self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
                    report = json.loads(done.stdout)
                    codes = [f["code"] for f in report["findings"]]
                    self.assertEqual(report["boundary"], wrapper.boundary)
                    self.assertEqual(Path(report["package_path"]), package.resolve())
                    self.assertNotIn("ARTIFACT_MISSING", codes)
                    self.assertEqual(codes.count("ARTIFACT_PRESENT"), wrapper.present)

    def test_a_package_outside_the_working_projects_root_is_refused(self):
        """Anchoring on the operator's project, not the script, refuses in both directions."""
        vendored = self.layouts[1]
        other = Path(self._tmp.name).resolve() / "other-project"
        (other / ".git").mkdir(parents=True)
        package = other / "skillset-saves" / "runs" / "r-1" / "review"
        _review(package, True)
        done = _run(vendored.skills / WRAPPERS[0].script, str(package), "--json", cwd=vendored.project)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("outside the project", done.stderr)
        self.assertEqual(done.stdout, "")


class PackageGuardTests(unittest.TestCase):
    """The containment guard and the argument handling, one script at a time."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name).resolve()
        cls.project = cls.base / "project"
        (cls.project / ".git").mkdir(parents=True)
        cls.skills = _copy_catalog(cls.project / "skills")
        cls.outside = cls.base / "outside" / "pkg"
        _write(cls.outside / "deliverable_bug-review.md", PACKET.format(lens="bug-review"))
        cls.bare = cls.base / "bare"
        cls.bare.mkdir()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _require_unmarked_bare(self):
        if gc.find_project_root(self.bare) is not None:
            self.skipTest("a project marker exists above the temporary directory")

    def _each(self):
        for wrapper in WRAPPERS:
            with self.subTest(wrapper=wrapper.name):
                yield wrapper, self.skills / wrapper.script

    def _scripts(self):
        for _, script in self._each():
            yield script

    def _run_dir(self, wrapper: Wrapper) -> Path:
        package = self.project / "skillset-saves" / "runs" / uuid.uuid4().hex[:8] / wrapper.phase
        wrapper.write(package, True)
        return package

    def test_a_directory_outside_the_project_is_refused(self):
        for script in self._scripts():
            done = _run(script, str(self.outside), cwd=self.project)
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("outside the project", done.stderr)
            self.assertEqual(done.stdout, "")

    def test_dotdot_does_not_lead_out_of_the_project(self):
        for wrapper, script in self._each():
            package = self._run_dir(wrapper)
            sneaky = package / ".." / ".." / ".." / ".." / ".." / "outside" / "pkg"
            done = _run(script, str(sneaky), cwd=self.project)
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("outside the project", done.stderr)

    def test_a_symlink_out_of_the_project_does_not_lead_out_of_it(self):
        for wrapper, script in self._each():
            link = self.project / "skillset-saves" / "runs" / uuid.uuid4().hex[:8] / wrapper.phase
            link.parent.mkdir(parents=True)
            _symlink(self.outside, link)
            done = _run(script, str(link), cwd=self.project)
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("outside the project", done.stderr)

    def test_a_missing_directory_and_a_file_are_refused(self):
        for wrapper, script in self._each():
            package = self._run_dir(wrapper)
            for target in (package / "does-not-exist", next(package.rglob("*.*"))):
                done = _run(script, str(target), cwd=self.project)
                self.assertEqual(done.returncode, 2, done.stdout)
                self.assertIn("not a directory", done.stderr)

    def test_no_project_anywhere_is_refused(self):
        self._require_unmarked_bare()
        for script in self._scripts():
            done = _run(script, str(self.outside), cwd=self.bare)
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("cannot locate a project root", done.stderr)

    def test_a_working_directory_in_no_project_uses_the_packages_own(self):
        self._require_unmarked_bare()
        for wrapper, script in self._each():
            package = self._run_dir(wrapper)
            done = _run(script, str(package), "--json", cwd=self.bare)
            self.assertEqual(done.returncode, 0, done.stderr + done.stdout)

    def test_help_and_a_missing_package_are_argparse_answers_not_tracebacks(self):
        for script in self._scripts():
            helped = _run(script, "--help", cwd=self.project)
            self.assertEqual(helped.returncode, 0, helped.stderr)
            self.assertIn("--prior", helped.stdout)
            bare = _run(script, cwd=self.project)
            self.assertEqual(bare.returncode, 2)
            self.assertIn("package", bare.stderr)
            self.assertNotIn("Traceback", bare.stderr)

    def test_option_values_are_never_read_as_the_package(self):
        """`--prior <file> <pkg>`, `<pkg> --prior <file>` and an abbreviated flag all name the package."""
        wrapper = WRAPPERS[1]
        package = self._run_dir(wrapper)
        prior = self.base / "prior.md"
        prior.write_text("---\nsubmission_id: S1\nrevision: 1\nverdict: APPROVED\n---\n", encoding="utf-8")
        script = self.skills / wrapper.script
        for args in (("--prior", str(prior), str(package)), (str(package), "--prior", str(prior)),
                     ("--pri", str(prior), str(package))):
            with self.subTest(args=args[:2]):
                done = _run(script, *args, "--json", cwd=self.project)
                self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
                report = json.loads(done.stdout)
                self.assertEqual(Path(report["package_path"]), package.resolve())
                self.assertIn("VERDICT_REUSABLE", [f["code"] for f in report["findings"]])


class WrapperBootstrapTests(unittest.TestCase):
    """The guard and the root finder live once, in the engine."""

    def test_the_wrappers_hold_no_private_copy_of_the_guard(self):
        for wrapper in WRAPPERS:
            source = (SKILLS / wrapper.script).read_text(encoding="utf-8")
            with self.subTest(wrapper=wrapper.name):
                for name in ("_validate_package_dir", "_find_repo_root", "_find_catalog_root",
                             "_ROOT_MARKERS", "_VALUE_OPTS"):
                    self.assertNotIn(name, source)
                self.assertIn("main_with_manifest", source)

    def test_root_markers_match_the_hooks(self):
        """The engine cannot import the hooks (they fail open), so this is what keeps the two lists one."""
        hooks = SKILLS / "harness" / "hooks"
        spec = importlib.util.spec_from_file_location("hooks_state_under_test", hooks / "_state.py")
        state = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(state)
        self.assertEqual(tuple(gc.ROOT_MARKERS), tuple(state._ROOT_MARKERS))


class OptionalArtifactTests(unittest.TestCase):
    """An artifact a contract makes optional may be absent: the wrapper leaves it to the model."""

    def test_a_package_without_its_optional_artifacts_is_no_defect(self):
        scratch = REPO / ".harness-state" / "test-work" / "gate-wrappers" / uuid.uuid4().hex
        try:
            for wrapper in WRAPPERS:
                with self.subTest(wrapper=wrapper.name):
                    package = scratch / "skillset-saves" / "runs" / "r-1" / wrapper.phase
                    wrapper.write(package, False)
                    done = _run(SKILLS / wrapper.script, os.path.relpath(package, REPO), "--json", cwd=REPO)
                    self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
                    report = json.loads(done.stdout)
                    codes = [f["code"] for f in report["findings"]]
                    self.assertNotIn("ARTIFACT_MISSING", codes)
                    self.assertEqual(codes.count("ARTIFACT_PRESENT"), wrapper.minimal)
                    self.assertEqual(codes.count("ARTIFACT_CONDITIONAL"), wrapper.optional)
                    self.assertEqual(report["gate_status"], "NEEDS_JUDGMENT")
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
            try:
                scratch.parent.rmdir()
            except OSError:
                pass


class PriorVerdictRecordTests(unittest.TestCase):
    """--prior reads the record the boundary validator actually writes."""

    def test_wrapper_compares_against_a_verdict_record_check_py_wrote(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            project = base / "project"
            (project / ".git").mkdir(parents=True)
            package = project / "skillset-saves" / "runs" / "r-1" / "delivery"
            _delivery(package, True)
            handoff = package / "reports" / "handoff_review-to-delivery.md"
            handoff.write_text(handoff.read_text(encoding="utf-8").replace("revision: 1", "revision: r1"),
                               encoding="utf-8")

            manifest = base / "manifest.json"
            manifest.write_text(json.dumps({
                "schema_version": 1, "submission_id": "S1", "revision": "r1",
                "revisions": ["r1"], "evidence": {}, "artifact_hashes": {},
            }), encoding="utf-8")
            record = base / "verdict_review-to-delivery.json"
            written = _run(ENGINE_DIR / "check.py", "--boundary", "review-to-delivery",
                           "--package", str(manifest), "--verdict-out", str(record), cwd=base)
            self.assertIn(written.returncode, (0, 1), written.stderr)
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["submission_id"], "S1")

            script = SKILLS / WRAPPERS[1].script
            done = _run(script, str(package), "--prior", str(record), "--json", cwd=project)
            self.assertEqual(done.returncode, 0, done.stderr + done.stdout)
            self.assertIn("VERDICT_REUSABLE", [f["code"] for f in json.loads(done.stdout)["findings"]])

            handoff.write_text(handoff.read_text(encoding="utf-8").replace("revision: r1", "revision: r2"),
                               encoding="utf-8")
            done = _run(script, str(package), "--prior", str(record), "--json", cwd=project)
            self.assertEqual(done.returncode, 1, done.stderr + done.stdout)
            self.assertIn("SILENT_DRIFT", [f["code"] for f in json.loads(done.stdout)["findings"]])


def _manifest_of(wrapper: Wrapper):
    path = SKILLS / wrapper.script
    spec = importlib.util.spec_from_file_location(f"wrapper_{wrapper.name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MANIFEST


class WrapperManifestTests(unittest.TestCase):
    """The manifests cite the contracts that decide their optional slots."""

    #: Slots a wrapper may report UNCHECKED instead of FAIL, per wrapper. Each is
    #: optional because a contract says so (a gates.yaml waiver, a pipelines.yaml
    #: `when`) or because the script cannot know the scope; a change to that
    #: contract changes this set and this test names the wrapper to revisit.
    OPTIONAL = {
        "gatekeeper-code": {"lens_security", "lens_adversarial", "lens_cso"},
        "gatekeeper-build": {"security", "build_verdict"},
        "gatekeeper-design": {"stack_locks", "taste_snapshot", "api_contracts", "ui_handoff"},
        "check_redesign": {"rendered_verification"},
        "gatekeeper-admiral": {"delivery_or_package"},
    }

    @classmethod
    def setUpClass(cls):
        cls.contracts = gc.Contracts.load()

    def test_optional_slots_are_the_ones_the_contracts_make_optional(self):
        for wrapper in WRAPPERS:
            manifest = _manifest_of(wrapper)
            with self.subTest(wrapper=wrapper.name):
                optional = {
                    spec.key for spec in manifest.artifacts
                    if spec.requirement == "conditional"
                    or gc._optional_because(spec, manifest, self.contracts)}
                self.assertEqual(optional, self.OPTIONAL[wrapper.name])

    def test_every_cited_stage_and_key_exists(self):
        """A renamed stage would silently stop relaxing a slot, so a dangling name fails."""
        pipelines = self.contracts.pipelines["pipelines"]
        for wrapper in WRAPPERS:
            manifest = _manifest_of(wrapper)
            for spec in manifest.artifacts:
                with self.subTest(wrapper=wrapper.name, slot=spec.key):
                    if not (spec.stages or spec.evidence_key):
                        continue
                    self.assertTrue(manifest.pipeline, "a slot cites a contract but the manifest names no pipeline")
                    steps = {s["step"] for s in pipelines[manifest.pipeline]["stages"]}
                    self.assertLessEqual(set(spec.stages), steps)
                    boundary = self.contracts.boundary_of(manifest.pipeline)
                    required = self.contracts.gates["boundaries"][boundary]["required_evidence"]
                    if spec.evidence_key:
                        self.assertIn(spec.evidence_key, required)


if __name__ == "__main__":
    unittest.main()
