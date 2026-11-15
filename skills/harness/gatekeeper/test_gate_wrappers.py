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
import re
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

import _fixtures as fixtures  # noqa: E402
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
    """A delivery ledger with one pending record, and the manifest of the review package it hands over: the record
    names a phase directory of its own run and that package's revision and submission id."""
    run = pkg.parent
    _write(run / "review" / "manifest.json",
           json.dumps({"schema_version": 2, "boundary": "review-to-delivery", "revision": 1, "submission_id": "review-1"}))
    _write(pkg / "reports" / "handoff_review-to-delivery.md",
           f"---\nsubmission_id: S1\nrevision: 1\npackage_path: skillset-saves/runs/{run.name}/review\n"
           "manifest_submission_id: review-1\nsubmission_status: PENDING\nverdict: PENDING\n---\n# Handoff\n")
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
        return
    except (OSError, NotImplementedError) as exc:
        first = exc
    if os.name == "nt" and target.is_dir():
        # A junction needs no privilege and resolves exactly as a directory symlink does.
        try:
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
            return
        except (OSError, ImportError):
            pass
    raise unittest.SkipTest(f"symlinks are unavailable here: {first}") from first


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
        probe = self.base / "symlink-probe"
        _symlink(self.outside, probe)  # decided before the loop: a skip inside it would strand a subTest generator
        probe.unlink()
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

    def test_an_interpreter_below_the_floor_is_told_the_floor(self):
        """G-12: under Python 3.11 every wrapper crashed on Path.is_junction instead
        of naming the floor runtime-manifest.yaml declares."""
        floor = gc.runtime_floor_error((0, 0), self.skills / "runtime-manifest.yaml")
        self.assertIsNotNone(floor)
        old = None
        for minor in range(12, 7, -1):
            found = shutil.which(f"python3.{minor}")
            if found and gc.runtime_floor_error((3, minor), self.skills / "runtime-manifest.yaml"):
                old = found
                break
        if old is None:
            self.skipTest("no interpreter below the runtime floor is installed")
        for wrapper, script in self._each():
            package = self._run_dir(wrapper)
            done = subprocess.run([old, str(script), str(package), "--json"], cwd=str(self.project),
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
            self.assertIn("below the runtime floor", done.stderr)
            self.assertNotIn("Traceback", done.stderr)
            self.assertNotIn("is_junction", done.stderr + done.stdout)
            self.assertEqual(done.stdout, "")

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
        self.assertEqual(tuple(gc.ROOT_MARKERS), tuple(state.ROOT_MARKERS))


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

    #: The lens skills that fix a packet template, by the slot their packet fills.
    LENS_SKILLS = {
        "lens_bug": ("bug-review",),
        "lens_code": ("code-review",),
        "lens_quality": ("quality-review",),
        "lens_security": ("security-review",),
        "lens_adversarial": ("mr-robot", "frontier"),
    }

    @classmethod
    def setUpClass(cls):
        cls.contracts = gc.Contracts.load()

    def test_a_lens_slot_asks_only_for_fields_its_skill_fixes(self):
        """The wrapper and the lens skill state the packet shape twice; a field one
        asks for and the other never promises turns a valid packet away."""
        slots = {spec.key: spec for spec in _manifest_of(WRAPPERS[0]).artifacts}
        for key, skills in self.LENS_SKILLS.items():
            self.assertTrue(slots[key].fields, f"{key} asks for no structure at all")
            for skill in skills:
                text = (SKILLS / "review" / skill / "SKILL.md").read_text(encoding="utf-8")
                for name in slots[key].fields:
                    with self.subTest(slot=key, skill=skill, field=name):
                        self.assertRegex(text, gc._field_line(name))

    def test_the_cso_slot_asks_for_what_review_cso_returns(self):
        """review/cso fixes no lens template, only the return of a gate-owning skill."""
        slots = {spec.key: spec for spec in _manifest_of(WRAPPERS[0]).artifacts}
        text = (SKILLS / "review" / "cso" / "SKILL.md").read_text(encoding="utf-8")
        stated = re.search(r"Return ([^.]*?)\s+when the skill owns\s+a gate", text)
        self.assertIsNotNone(stated, "review/cso no longer states the fields it returns")
        self.assertTrue(slots["lens_cso"].fields)
        for name in slots["lens_cso"].fields:
            self.assertIn(name, stated.group(1))

    def test_a_cso_packet_with_only_the_returned_fields_fills_its_slot(self):
        with tempfile.TemporaryDirectory() as raw:
            package = Path(raw).resolve() / "review"
            _review(package, True)
            _write(package / "deliverable_cso.md",
                   "# CSO\n\nOutcome:  cso, r1, release posture reviewed\nEvidence: threat model\n")
            report = gc.run_gate(package, _manifest_of(WRAPPERS[0]))
        codes = [f.code for f in report.findings]
        self.assertIn("deliverable_cso.md",
                      {f.location for f in report.findings if f.code == "ARTIFACT_PRESENT"})
        self.assertNotIn("ARTIFACT_CONDITIONAL", codes)
        self.assertNotIn("ARTIFACT_MISSING", codes)

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



def _fm(revision, body: str) -> str:
    return f"---\nrevision: {revision}\nsubmission_id: build-{revision}\n---\n{body}"


def _build_at(pkg: Path, revision=2, certificate: bool = True) -> None:
    """A build package whose files all declare ``revision``."""
    _write(pkg / "reports" / "report_implementation.md", _fm(revision, "# Implementation\nChanged files: app.py; the module was updated.\n"))
    _write(pkg / "reports" / "report_tests.md", _fm(revision, "# Test results\nThe suite passed: 12 tests, coverage recorded.\n"))
    if certificate:
        _write(pkg / "reports" / "report_completeness.md", _fm(revision, "# Completeness\nThe build is complete and certified.\n"))


class BuildGateCase(unittest.TestCase):
    """The build gate wrapper run on a package in a scratch project, with the supersede command at hand."""

    SCRIPT = SKILLS / "build" / "gatekeeper-build" / "scripts" / "check.py"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name).resolve()
        (self.project / ".git").mkdir()
        self.package = self.project / "skillset-saves" / "runs" / "r-1" / "build"
        scripts = str(SKILLS / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        import run_files
        self.run_files = run_files

    def check(self) -> tuple:
        done = _run(self.SCRIPT, str(self.package), "--json", cwd=self.project)
        self.assertIn(done.returncode, (0, 1), done.stderr + done.stdout)
        report = json.loads(done.stdout)
        return done.returncode, report, [f["code"] for f in report["findings"]]

    def finding(self, report: dict, code: str) -> dict:
        return next(f for f in report["findings"] if f["code"] == code)

    def supersede(self, path: str, by=2, **more) -> None:
        self.run_files.supersede(self.project, "r-1", "build", path, by, **more)


class SupersededCopiesTests(BuildGateCase):
    """WP-04 (issue 2): a preserved copy of an earlier revision is neither a lineage defect nor evidence.

    The contracts tell every owner to preserve superseded artifacts, and the engine read every file of the package.
    Reproduced against the build gate before the change: a kept ``report_completeness.r1.md`` beside the current
    certificate gave MIXED_REVISIONS; with no current certificate an old copy at ``archive/report_completeness.md``
    filled the completeness slot; and so did an unrelated ``reports/deploy-confirmation.md``."""

    def test_a_kept_copy_fails_lineage_until_it_is_superseded_and_passes_afterwards(self):
        _build_at(self.package, 2)
        _write(self.package / "reports" / "report_completeness.r1.md", _fm(1, "# Completeness\nComplete and certified at r1.\n"))
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("MIXED_REVISIONS", codes)
        self.assertIn("run_files.py supersede", self.finding(report, "MIXED_REVISIONS")["message"])
        self.supersede("reports/report_completeness.r1.md")
        code, report, codes = self.check()
        self.assertEqual(code, 0, report)
        self.assertNotIn("MIXED_REVISIONS", codes)
        self.assertIn("REVISION_COHERENT", codes)
        self.assertEqual(codes.count("SUPERSEDED_COPIES"), 1)
        copies = self.finding(report, "SUPERSEDED_COPIES")
        self.assertEqual(copies["status"], "PASS")
        self.assertIn("_superseded/rev-1/reports/report_completeness.r1.md", copies["message"])
        self.assertEqual(report["gate_status"], "NEEDS_JUDGMENT", "only the optional slots are left to the model")

    def test_a_resubmission_that_kept_its_previous_certificate_passes(self):
        """The ordinary sequence: supersede the r1 certificate, then write the r2 one at the same path."""
        _build_at(self.package, 1)
        self.supersede("reports/report_completeness.md")
        _build_at(self.package, 2)
        code, report, codes = self.check()
        self.assertEqual(code, 0, report)
        self.assertEqual([c for c in codes if c in ("MIXED_REVISIONS", "MIXED_SUBMISSION_IDS", "ARTIFACT_MISSING")], [])
        self.assertIn("COMPLETENESS_REVISION_OK", codes)
        self.assertEqual(self.finding(report, "ARTIFACT_PRESENT")["status"], "PASS")

    def test_an_old_copy_elsewhere_does_not_fill_the_completeness_slot(self):
        _build_at(self.package, 2, certificate=False)
        _write(self.package / "archive" / "report_completeness.md", _fm(2, "# Completeness\nComplete and certified.\n"))
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("ARTIFACT_MISSING", codes)
        missing = self.finding(report, "ARTIFACT_MISSING")
        self.assertIn("completeness certification", missing["message"])
        self.assertIn("expected at: reports/report_completeness.md", missing["message"])
        stray = self.finding(report, "ARTIFACT_NOT_CANONICAL")
        self.assertEqual((stray["status"], stray["location"]), ("UNCHECKED", "archive/report_completeness.md"))
        self.assertIn("reports/report_completeness.md", stray["message"])

    def test_an_unrelated_file_whose_name_matched_does_not_fill_it_either(self):
        _build_at(self.package, 2, certificate=False)
        _write(self.package / "reports" / "deploy-confirmation.md", _fm(2, "# Deploy\nThe deploy was confirmed and is complete.\n"))
        _write(self.package / "reports" / "cross-check-notes.md", _fm(2, "# Notes\nCross-check complete, certified.\n"))
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("ARTIFACT_MISSING", codes)
        self.assertNotIn("ARTIFACT_NOT_CANONICAL", codes)

    def test_a_superseded_copy_fills_no_slot(self):
        _build_at(self.package, 1)
        self.supersede("reports/report_completeness.md")
        _write(self.package / "reports" / "report_implementation.md", _fm(2, "# Implementation\nChanged files: app.py; the module.\n"))
        _write(self.package / "reports" / "report_tests.md", _fm(2, "# Test results\nThe suite passed: 12 tests.\n"))
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("ARTIFACT_MISSING", codes)
        self.assertIn("SUPERSEDED_COPIES", codes)

    def test_a_file_placed_under_superseded_by_hand_is_unindexed(self):
        _build_at(self.package, 2)
        _write(self.package / "_superseded" / "rev-1" / "reports" / "report_completeness.md", _fm(1, "# Completeness\nComplete.\n"))
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        finding = self.finding(report, "SUPERSEDED_UNINDEXED")
        self.assertEqual(finding["location"], "_superseded/rev-1/reports/report_completeness.md")
        self.assertIn("run_files.py supersede", finding["message"])
        self.assertNotIn("MIXED_REVISIONS", codes, "the planted copy is not read as part of the package either")

    def test_a_superseded_folder_deeper_in_the_package_is_unindexed_too(self):
        _build_at(self.package, 2)
        _write(self.package / "reports" / "_Superseded" / "old.md", _fm(1, "# Old\n"))
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertEqual(self.finding(report, "SUPERSEDED_UNINDEXED")["location"], "reports/_Superseded/old.md")

    def test_a_copy_changed_after_it_was_superseded_and_an_entry_with_no_file_fail(self):
        _build_at(self.package, 1)
        self.supersede("reports/report_completeness.md")
        _build_at(self.package, 2)
        copy = self.package / "_superseded" / "rev-1" / "reports" / "report_completeness.md"
        copy.write_text(copy.read_text(encoding="utf-8") + "edited afterwards\n", encoding="utf-8")
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("changed afterwards", self.finding(report, "SUPERSEDED_INDEX_MISMATCH")["message"])
        copy.unlink()
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("which is not there", self.finding(report, "SUPERSEDED_INDEX_MISMATCH")["message"])

    def test_an_index_that_cannot_be_read_fails(self):
        _build_at(self.package, 2)
        for text in ("{ not json", "[]", '{"entries": {}}'):
            _write(self.package / "_superseded" / "index.json", text)
            with self.subTest(index=text):
                code, report, codes = self.check()
                self.assertEqual(code, 1)
                self.assertIn("cannot be read as the index", self.finding(report, "SUPERSEDED_INDEX_MISMATCH")["message"])

    def test_a_blocked_phrase_in_a_superseded_copy_is_not_the_current_packages(self):
        _build_at(self.package, 1)
        _write(self.package / "reports" / "report_tests.md", _fm(1, "# Test results\nTODO: the suite passed, 12 tests.\n"))
        self.assertIn("BLOCKED_PHRASE", self.check()[2])
        self.supersede("reports/report_tests.md")
        self.supersede("reports/report_implementation.md")
        self.supersede("reports/report_completeness.md")
        _build_at(self.package, 2)
        code, report, codes = self.check()
        self.assertEqual(code, 0, report)
        self.assertNotIn("BLOCKED_PHRASE", codes)

    def test_a_package_with_no_superseded_folder_says_nothing_about_one(self):
        _build_at(self.package, 2)
        code, report, codes = self.check()
        self.assertEqual(code, 0)
        self.assertEqual([c for c in codes if c.startswith("SUPERSEDED")], [])
        self.assertIn("superseded_copies", report["checks_run"])

    def test_a_package_holding_only_superseded_copies_is_empty(self):
        _build_at(self.package, 1)
        for name in ("report_implementation.md", "report_tests.md", "report_completeness.md"):
            self.supersede(f"reports/{name}")
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("PACKAGE_EMPTY", codes)


class CompletenessRevisionTests(BuildGateCase):
    """The certificate certifies one revision: the package's."""

    def manifest(self, revision) -> None:
        _write(self.package / "manifest.json", json.dumps({"schema_version": 2, "boundary": "build-to-review", "revision": revision,
                                                           "submission_id": f"build-{revision}"}))

    def test_a_certificate_from_the_previous_revision_is_a_mismatch(self):
        _build_at(self.package, 2, certificate=False)
        _write(self.package / "reports" / "report_completeness.md", "# Completeness\nComplete and certified.\n")
        self.manifest(2)
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        finding = self.finding(report, "COMPLETENESS_REVISION_MISMATCH")
        self.assertIn("declares no revision", finding["message"])
        self.assertIn("revision 2 (manifest.json)", finding["message"])
        _write(self.package / "reports" / "report_completeness.md", _fm(1, "# Completeness\nComplete and certified.\n"))
        code, report, codes = self.check()
        self.assertIn("declares revision 1", self.finding(report, "COMPLETENESS_REVISION_MISMATCH")["message"])
        self.assertIn("run_files.py supersede", self.finding(report, "COMPLETENESS_REVISION_MISMATCH")["message"])

    def test_the_manifest_and_the_certificate_may_spell_the_same_revision_differently(self):
        for in_manifest, in_certificate in ((2, 2), ("r2", "r2"), (2, "r2")):
            with self.subTest(manifest=in_manifest, certificate=in_certificate):
                _write(self.package / "reports" / "report_implementation.md", "# Implementation\nChanged files: app.py; the module.\n")
                _write(self.package / "reports" / "report_tests.md", "# Test results\nThe suite passed: 12 tests.\n")
                _write(self.package / "reports" / "report_completeness.md", _fm(in_certificate, "# Completeness\nComplete and certified.\n"))
                self.manifest(in_manifest)
                code, report, codes = self.check()
                self.assertIn("COMPLETENESS_REVISION_OK", codes)
                self.assertNotIn("COMPLETENESS_REVISION_MISMATCH", codes)

    def test_without_a_manifest_the_other_artifacts_give_the_revision(self):
        _build_at(self.package, 3, certificate=False)
        _write(self.package / "reports" / "report_completeness.md", "# Completeness\nComplete and certified.\n")
        code, report, codes = self.check()
        self.assertEqual(code, 1)
        self.assertIn("revision 3 (the other artifacts)", self.finding(report, "COMPLETENESS_REVISION_MISMATCH")["message"])

    def test_a_package_that_declares_no_revision_anywhere_is_left_to_lineage(self):
        _build(self.package, True)
        code, report, codes = self.check()
        self.assertEqual(code, 0)
        self.assertIn("REVISION_ABSENT", codes)
        self.assertEqual([c for c in codes if c.startswith("COMPLETENESS_REVISION")], [])



class DeliveryLedgerTests(unittest.TestCase):
    """WP-05 (issue 1): admiral's ``delivery/reports/`` holds one handoff record per boundary, and the gate reads it
    as a ledger.

    Each record has its own submission id and revision, so the engine's rule of one revision and one submission id
    per package failed any directory with two records (MIXED_REVISIONS and MIXED_SUBMISSION_IDS, exit 1): no run with
    more than one boundary could pass the cross-stage shape check. The wrapper took no boundary either, so it could
    not tell the record being judged from the earlier ones."""

    SCRIPT = SKILLS / "gatekeeper-admiral" / "scripts" / "check.py"
    RUN = "r-1"
    DONE = [{"boundary": "design-to-build", "revision": 1}, {"boundary": "build-to-review", "revision": 2},
            {"boundary": "review-to-delivery", "revision": 3}]
    PENDING = {"boundary": "deploy-readiness", "revision": 4, "status": "PENDING"}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name).resolve()
        (self.project / ".git").mkdir()
        sys.path.insert(0, str(SKILLS / "scripts"))
        import run_files
        self.run_files = run_files

    def ledger(self, entries, package: bool = True) -> Path:
        delivery = fixtures.ledger(self.project, self.RUN, [dict(entry) for entry in entries])
        if package:
            _write(delivery / "reports" / "delivery-package.md", "# Delivery package\nWhat was approved and what is next.\n")
        return delivery

    def run_check(self, delivery: Path, *args: str) -> subprocess.CompletedProcess:
        return _run(self.SCRIPT, str(delivery), "--json", *args, cwd=self.project)

    def check(self, delivery: Path, *args: str) -> tuple:
        done = self.run_check(delivery, *args)
        self.assertIn(done.returncode, (0, 1), done.stderr + done.stdout)
        report = json.loads(done.stdout)
        return done.returncode, report, [f["code"] for f in report["findings"]]

    def finding(self, report: dict, code: str) -> dict:
        return next(f for f in report["findings"] if f["code"] == code)

    def test_a_run_with_four_boundaries_passes_at_the_one_being_judged(self):
        delivery = self.ledger([*self.DONE, self.PENDING])
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertEqual(code, 0, report)
        self.assertEqual(report["gate_status"], "STRUCTURE_OK", [f for f in report["findings"] if f["status"] != "PASS"])
        self.assertEqual([c for c in codes if c in ("MIXED_REVISIONS", "MIXED_SUBMISSION_IDS")], [])
        self.assertIn("the record being judged is deploy-readiness", self.finding(report, "HANDOFF_LEDGER_OK")["message"])
        present = [f["location"] for f in report["findings"] if f["code"] == "ARTIFACT_PRESENT"]
        self.assertEqual(sorted(present), ["reports/delivery-package.md", "reports/handoff_deploy-readiness.md"])

    def test_every_boundary_of_a_run_passes_in_turn(self):
        """Design, build, review and delivery: the ledger grows by one record at a time and passes each time."""
        entries = []
        for entry in [*self.DONE, {"boundary": "deploy-readiness", "revision": 4}]:
            delivery = self.ledger([*entries, {**entry, "status": "PENDING"}])
            with self.subTest(judged=entry["boundary"], records=len(entries) + 1):
                code, report, codes = self.check(delivery, "--boundary", entry["boundary"])
                self.assertEqual((code, report["gate_status"]), (0, "STRUCTURE_OK"), report)
            entries.append(entry)

    def test_the_one_pending_record_is_judged_without_being_named(self):
        delivery = self.ledger([*self.DONE, self.PENDING])
        code, report, codes = self.check(delivery)
        self.assertEqual((code, report["gate_status"]), (0, "STRUCTURE_OK"), report)
        self.assertIn("the record being judged is deploy-readiness", self.finding(report, "HANDOFF_LEDGER_OK")["message"])

    def test_two_pending_records_and_no_boundary_have_no_answer(self):
        delivery = self.ledger([self.DONE[0], {"boundary": "build-to-review", "revision": 2, "status": "PENDING"},
                                {"boundary": "review-to-delivery", "revision": 3, "status": "PENDING"}])
        done = self.run_check(delivery)
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertEqual(done.stdout, "")
        for name in ("reports/handoff_build-to-review.md", "reports/handoff_review-to-delivery.md", "--boundary"):
            self.assertIn(name, done.stderr)
        named = self.check(delivery, "--boundary", "review-to-delivery")
        self.assertIn("HANDOFF_STATUS", named[2], "named, the other pending record is an earlier one that was never recorded")

    def test_no_pending_record_among_several_has_no_answer_either(self):
        done = self.run_check(self.ledger(self.DONE))
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("Pass --boundary", done.stderr)

    def test_a_boundary_that_is_not_in_the_gate_spec_is_refused(self):
        done = self.run_check(self.ledger([self.PENDING]), "--boundary", "deploy-readyness")
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("is not a boundary in gates.yaml", done.stderr)
        self.assertIn("deploy-readiness", done.stderr)

    def test_a_boundary_with_no_record_is_a_missing_artifact(self):
        delivery = self.ledger(self.DONE)
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertEqual(code, 1)
        self.assertIn("expected at: reports/handoff_deploy-readiness.md", self.finding(report, "ARTIFACT_MISSING")["message"])

    def test_an_earlier_record_that_disagrees_with_its_verdict_record_names_the_file_and_the_field(self):
        cases = (({"recorded": {"judgment": {"gate": "gatekeeper-admiral", "verdict": "REVISE", "valid": True}}}, "verdict ("),
                 ({"record": {"verdict_id": "vid-forged"}}, "verdict_id ("),
                 ({"recorded": {"revision": 9}}, "revision ("),
                 ({"record": {"verdict_id": None}}, "verdict_id ("))
        for override, field in cases:
            entries = [self.DONE[0], {**self.DONE[1], **override}, self.DONE[2], self.PENDING]
            with self.subTest(field=field, override=override):
                code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
                self.assertEqual(code, 1)
                finding = self.finding(report, "HANDOFF_VERDICT_MISMATCH")
                self.assertEqual(finding["location"], "reports/handoff_build-to-review.md")
                self.assertIn("build/verdict_build-to-review.cross-stage.json", finding["message"])
                self.assertIn(field, finding["message"])

    def test_a_recorded_verdict_with_no_verdict_record_is_a_mismatch(self):
        delivery = self.ledger([*self.DONE, self.PENDING])
        (self.project / "skillset-saves" / "runs" / self.RUN / "build" / "verdict_build-to-review.cross-stage.json").unlink()
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertIn("does not exist", self.finding(report, "HANDOFF_VERDICT_MISMATCH")["message"])

    def test_an_earlier_record_that_was_not_approved_stops_the_run(self):
        for verdict in ("REVISE", "ESCALATE"):
            entries = [self.DONE[0], {**self.DONE[1], "verdict": verdict}, self.DONE[2], self.PENDING]
            with self.subTest(verdict=verdict):
                code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
                self.assertEqual(code, 1)
                self.assertEqual(self.finding(report, "HANDOFF_NOT_APPROVED")["location"], "reports/handoff_build-to-review.md")
                self.assertNotIn("HANDOFF_VERDICT_MISMATCH", codes, "the record agrees with the gate; the verdict is the defect")

    def test_a_package_path_in_another_run_or_outside_the_run_is_refused(self):
        other = self.project / "skillset-saves" / "runs" / "r-2" / "build"
        other.mkdir(parents=True)
        for path in ("skillset-saves/runs/r-2/build", "skillset-saves/runs/r-1/nowhere", "skillset-saves/runs/r-1", "src",
                     "skillset-saves/runs/r-1/build/reports", str(other)):
            entries = [self.DONE[0], {**self.DONE[1], "record": {"package_path": path}}, self.DONE[2], self.PENDING]
            with self.subTest(package_path=path):
                code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
                self.assertEqual(code, 1)
                self.assertEqual(self.finding(report, "HANDOFF_PACKAGE_PATH")["location"], "reports/handoff_build-to-review.md")

    def test_a_record_left_behind_by_a_rewind_is_stale_until_it_is_superseded(self):
        """The run rewound to design and build was judged again at revision 5 and 6; review's record is still revision 3."""
        entries = [{"boundary": "design-to-build", "revision": 5}, {"boundary": "build-to-review", "revision": 6, "status": "PENDING"},
                   self.DONE[2]]
        delivery = self.ledger(entries)
        code, report, codes = self.check(delivery, "--boundary", "build-to-review")
        self.assertEqual(code, 1)
        stale = self.finding(report, "HANDOFF_STALE_AFTER_REWIND")
        self.assertEqual(stale["location"], "reports/handoff_review-to-delivery.md")
        self.assertIn("run_files.py supersede", stale["message"])
        self.run_files.supersede(self.project, self.RUN, "delivery", "reports/handoff_review-to-delivery.md", 6)
        code, report, codes = self.check(delivery, "--boundary", "build-to-review")
        self.assertEqual((code, report["gate_status"]), (0, "STRUCTURE_OK"), report)
        self.assertIn("SUPERSEDED_COPIES", codes)

    def test_a_second_attempt_supersedes_the_first_record_of_its_boundary(self):
        delivery = self.ledger([self.DONE[0], {"boundary": "build-to-review", "revision": 2, "verdict": "REVISE"}])
        self.run_files.supersede(self.project, self.RUN, "delivery", "reports/handoff_build-to-review.md", 3)
        self.ledger([self.DONE[0], {"boundary": "build-to-review", "revision": 3, "status": "PENDING"}])
        code, report, codes = self.check(delivery, "--boundary", "build-to-review")
        self.assertEqual((code, report["gate_status"]), (0, "STRUCTURE_OK"), report)

    def test_a_boundary_whose_verdict_is_already_recorded_can_be_checked_again(self):
        delivery = self.ledger([*self.DONE, {"boundary": "deploy-readiness", "revision": 4}])
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertEqual((code, report["gate_status"]), (0, "STRUCTURE_OK"), report)

    def test_a_prior_verdict_of_an_earlier_boundary_is_not_reusable_for_this_one(self):
        delivery = self.ledger([*self.DONE, self.PENDING])
        earlier = self.project / "skillset-saves" / "runs" / self.RUN / "build" / "verdict_build-to-review.cross-stage.json"
        prior = self.project / "prior.md"
        _write(prior, f"---\nsubmission_id: {self.RUN}_handoff-2_attempt-1\nrevision: 2\nverdict: APPROVED\n---\n")
        for record in (prior, earlier):
            with self.subTest(prior=record.name):
                code, report, codes = self.check(delivery, "--boundary", "deploy-readiness", "--prior", str(record))
                self.assertNotIn("VERDICT_REUSABLE", codes)
        own = self.project / "own.md"
        _write(own, f"---\nsubmission_id: {self.RUN}_handoff-4_attempt-1\nrevision: 4\nverdict: APPROVED\n---\n")
        self.assertIn("VERDICT_REUSABLE", self.check(delivery, "--boundary", "deploy-readiness", "--prior", str(own))[2])

    def test_the_record_being_judged_has_to_match_the_package_it_hands_over(self):
        cases = (({"manifest": {"revision": 9}}, "revision"),
                 ({"record": {"manifest_submission_id": "release-0"}}, "manifest_submission_id"))
        for override, field in cases:
            with self.subTest(field=field):
                code, report, codes = self.check(self.ledger([*self.DONE, {**self.PENDING, **override}]), "--boundary", "deploy-readiness")
                self.assertEqual(code, 1)
                self.assertIn(field, self.finding(report, "HANDOFF_MANIFEST_MISMATCH")["message"])
        delivery = self.ledger([*self.DONE, self.PENDING])
        (self.project / "skillset-saves" / "runs" / self.RUN / "release" / "manifest.json").unlink()
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertIn("manifest.json does not exist", self.finding(report, "HANDOFF_MANIFEST_MISMATCH")["message"])

    def test_a_record_without_the_manifest_submission_id_is_unchecked_for_one_release(self):
        delivery = self.ledger([*self.DONE, {**self.PENDING, "record": {"manifest_submission_id": None}}])
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertEqual((code, report["gate_status"]), (0, "NEEDS_JUDGMENT"), report)
        missing = self.finding(report, "HANDOFF_FIELD_MISSING")
        self.assertEqual((missing["status"], missing["location"]), ("UNCHECKED", "reports/handoff_deploy-readiness.md"))

    def test_a_record_that_lacks_a_field_or_shares_a_submission_id_fails(self):
        for field in ("submission_id", "revision", "package_path", "submission_status", "verdict"):
            entries = [self.DONE[0], {**self.DONE[1], "record": {field: None}}, self.PENDING]
            with self.subTest(missing=field):
                code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
                self.assertEqual(code, 1)
                self.assertIn(field, self.finding(report, "HANDOFF_RECORD_INCOMPLETE")["message"])
        entries = [self.DONE[0], {**self.DONE[1], "record": {"submission_id": f"{self.RUN}_handoff-1_attempt-1"}}, self.PENDING]
        code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
        self.assertEqual(code, 1)
        self.assertIn("handoff_build-to-review.md", self.finding(report, "HANDOFF_DUPLICATE_SUBMISSION")["message"])

    def test_a_status_the_record_cannot_have(self):
        entries = [self.DONE[0], {**self.DONE[1], "status": "PENDING"}, self.PENDING]
        code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
        self.assertEqual(self.finding(report, "HANDOFF_STATUS")["location"], "reports/handoff_build-to-review.md")
        entries = [*self.DONE, {**self.PENDING, "record": {"submission_status": "DRAFT"}}]
        code, report, codes = self.check(self.ledger(entries), "--boundary", "deploy-readiness")
        self.assertEqual(self.finding(report, "HANDOFF_STATUS")["location"], "reports/handoff_deploy-readiness.md")

    def test_a_run_may_start_from_an_approved_package_with_no_upstream_record(self):
        delivery = self.ledger([self.DONE[2], self.PENDING])
        code, report, codes = self.check(delivery, "--boundary", "deploy-readiness")
        self.assertEqual((code, report["gate_status"]), (0, "STRUCTURE_OK"), report)

    def test_outside_the_save_layout_the_path_checks_are_unchecked(self):
        delivery = self.ledger([*self.DONE, self.PENDING])
        loose = self.project / "loose" / "delivery"
        shutil.copytree(delivery, loose)
        code, report, codes = self.check(loose, "--boundary", "deploy-readiness")
        self.assertEqual(code, 0, report)
        self.assertEqual(self.finding(report, "HANDOFF_PATHS_UNCHECKED")["status"], "UNCHECKED")
        self.assertNotIn("HANDOFF_PACKAGE_PATH", codes)

    def test_the_other_wrappers_take_no_boundary(self):
        done = _run(SKILLS / "build" / "gatekeeper-build" / "scripts" / "check.py", str(self.project), "--boundary", "build-to-review",
                    cwd=self.project)
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments", done.stderr)


if __name__ == "__main__":
    unittest.main()
