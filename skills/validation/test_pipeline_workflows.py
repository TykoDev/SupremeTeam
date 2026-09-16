"""End-to-end pipeline workflow contracts.

Every other test in this suite reads documents and compares them. These run the
actual gate: for each of the ten pipelines, a package is constructed in the shape
that pipeline's stages would produce, written to disk with real files and real
digests, and submitted to ``harness/gatekeeper/check.py``.

The reason this is worth its runtime: a boundary can be internally consistent and
still be *unsatisfiable*. Two rules can each look correct and jointly admit no
package — a key required and also barred from fallback while no stage produces
it, a typed record whose required fields contradict its artifact-backing rule.
Nothing in the catalog would report that, because every document would be
individually true. The only way to find it is to try to pass the gate.

It nearly happened: while deriving these fixtures the checker rejected candidate
packages on eleven distinct grounds across four boundaries, each one a field the
spec prose did not spell out. The shapes below are the checker's answer, not the
documentation's, and if the two ever diverge this file fails rather than the
documentation quietly going stale.

Negative cases matter more than the positive ones. A generator that only ever
produces passing packages proves the generator works, not the gate. Each
``Refuses`` test removes exactly one property from an otherwise-valid package and
asserts the gate notices.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment without PyYAML
    yaml = None

SKILLS = Path(__file__).resolve().parent.parent
REPO = SKILLS.parent
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"

if yaml is None:  # pragma: no cover
    raise unittest.SkipTest("PyYAML is required for the pipeline workflow contracts")

GATES = yaml.safe_load((SKILLS / "gates.yaml").read_text(encoding="utf-8"))
PIPELINES = yaml.safe_load((SKILLS / "pipelines.yaml").read_text(encoding="utf-8"))
OWNERSHIP = yaml.safe_load((SKILLS / "ownership.yaml").read_text(encoding="utf-8"))
REGISTRY = yaml.safe_load((SKILLS / "tech-stacks" / "registry.yaml").read_text(encoding="utf-8"))

#: The first registry overlay, used to build a stack_lock the gate will accept.
#: Reading it rather than hardcoding means the fixture follows the registry, and
#: a digest that stops matching its own overlay file fails here first.
OVERLAY = REGISTRY["overlays"][0]

ARTIFACT_REL = "phase/evidence.md"
ARTIFACT_BODY = "# evidence\n\nSynthetic but real: this file is hashed.\n"


def _digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _typed_record(kind: str, artifact: str, digest: str) -> object:
    """A record of ``kind`` the checker accepts.

    Every field here was added because the checker demanded it by name. The
    comments mark the ones that are not obvious from the spec prose.
    """
    base = {
        "artifacts": [artifact],
        "result": {"status": "pass", "summary": "synthetic evidence"},
        "inputs": [{"path": artifact, "sha256": digest}],
        "observed_at": "2026-09-16T00:00:00Z",
    }
    if kind == "scan":
        # `observed_at` is required for scan records specifically.
        return {**base, "tool": "probe-scanner", "command": "probe-scanner --all", "exit_code": 0}
    if kind == "render":
        # design-doctrine.md §4 fixes six responsive tiers; the checker only
        # requires the lists to be non-empty, so covering all six here keeps the
        # fixture honest against the doctrine as well as the code.
        return {**base,
                "breakpoints": ["320", "375", "640", "1024", "1440", "1920"],
                "themes": ["light", "dark"]}
    if kind == "findings":
        return {"items": [{"id": "F-01", "severity": "Minor", "status": "resolved"}]}
    if kind == "variant_set":
        variants = [{"id": f"v{i}", "name": f"Direction {i}", "direction": f"d{i}",
                     "spec": artifact, "tokens": artifact,
                     "components": artifact, "app": artifact} for i in range(1, 5)]
        return {"artifacts": [artifact], "variants": variants, "count": 4}
    if kind == "revision_ref":
        # A scalar identifier, not a record: it names an upstream revision.
        return "r-3"
    if kind == "verdict":
        return {"recommendation": "APPROVED", "revision": 1}
    if kind == "stack_lock":
        # `versions` is a list, and the slug and digest are checked against the
        # tech-stack registry and the overlay file on disk.
        return {"slug": OVERLAY["slug"],
                "versions": [OVERLAY["versions"][0]],
                "overlay_sha256": OVERLAY["sha256"]}
    if kind == "confirmation":
        return {"artifacts": [artifact], "actor": "user", "confirmed_scope": "project",
                "candidate_ids": ["p-1"], "source_run": "probe-run",
                "timestamp": "2026-09-16T00:00:00Z"}
    if kind == "conflict_analysis":
        return {"artifacts": [artifact], "conflicting_ids": [], "unresolved_conflicts": [],
                "accessibility_policy_collisions": [],
                "precedence_decision": "project over global"}
    if kind == "consumer_handoff":
        return {"consuming_pipeline": "design", "effective_profile_digest": "0" * 64,
                "applicability_summary": "one profile applied"}
    if kind == "effective_profile":
        return {"artifacts": [artifact], "digest": "0" * 64,
                "entries": [{"id": "p-1", "source_scope": "project", "source_id": "s-1"}]}
    if kind == "persistence_result":
        return {"artifacts": [artifact], "atomicity_status": "committed",
                "rollback_result": "not-required", "requested_destinations": ["project"],
                "committed_revisions": [1], "hashes": {artifact: digest}}
    if kind == "preference_diff":
        return {**base, "before_digest": "0" * 64, "after_digest": "1" * 64,
                "added": [], "removed": [], "changed": [], "deprecated": [],
                "revoked": [], "unchanged": [], "updated": []}
    return base


def build_package(boundary: str, root: Path) -> dict:
    """A package the gate should accept at ``boundary``."""
    spec = GATES["boundaries"][boundary]
    types = GATES.get("evidence_types") or {}
    artifact = root / ARTIFACT_REL
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(ARTIFACT_BODY, encoding="utf-8")
    digest = _digest_of(artifact)

    artifact_backed = set(spec.get("artifact_evidence") or [])
    evidence = {}
    for key in spec["required_evidence"]:
        kind = types.get(key)
        if kind:
            evidence[key] = _typed_record(kind, ARTIFACT_REL, digest)
        elif key in artifact_backed:
            evidence[key] = ARTIFACT_REL
        else:
            evidence[key] = f"narrative statement for {key}"

    return {
        "schema_version": 2,
        "boundary": boundary,
        "owner": spec.get("submitter") or "owner",
        "run_id": "workflow-probe",
        "submission_id": "workflow-probe-r1",
        "revision": 1,
        "revisions": [1],
        "artifact_hashes": {ARTIFACT_REL: digest},
        "evidence": evidence,
    }


def run_gate(boundary: str, package: dict, root: Path) -> dict:
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps(package, indent=1), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--boundary", boundary, "--package", str(manifest)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - engine crash
        raise AssertionError(
            f"gate produced no JSON for {boundary}: {proc.stdout[:300]} {proc.stderr[:300]}"
        ) from exc


class BoundarySatisfiabilityTests(unittest.TestCase):
    """Every declared boundary admits at least one passing package.

    A boundary nobody can satisfy is a pipeline that cannot close, and no
    document-level check would ever say so.
    """

    def test_every_boundary_accepts_a_well_formed_package(self):
        unsatisfiable = []
        for boundary in GATES["boundaries"]:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                verdict = run_gate(boundary, build_package(boundary, root), root)
                if not verdict.get("pass"):
                    unsatisfiable.append(f"{boundary}: {verdict.get('failures')}")
        self.assertEqual([], unsatisfiable, "\n".join(unsatisfiable))

    def test_every_pipeline_names_a_boundary_that_exists(self):
        missing = [
            f"{name} declares boundary {data.get('boundary')!r}, which gates.yaml does not define"
            for name, data in PIPELINES["pipelines"].items()
            if data.get("boundary") not in GATES["boundaries"]
        ]
        self.assertEqual([], missing, "\n".join(missing))

    def test_every_boundary_is_closed_by_exactly_one_pipeline(self):
        owners: dict[str, list[str]] = {}
        for name, data in PIPELINES["pipelines"].items():
            boundary = data.get("boundary")
            if boundary:
                owners.setdefault(boundary, []).append(name)
        problems = [f"{b} is closed by {p}" for b, p in owners.items() if len(p) > 1]
        problems += [f"{b} is closed by no pipeline" for b in GATES["boundaries"] if b not in owners]
        self.assertEqual([], problems, "\n".join(problems))


class GateRefusalTests(unittest.TestCase):
    """The gate notices when a valid package is spoiled one property at a time.

    Without these, the satisfiability test above only proves the fixture builder
    works. Each case starts from a package known to pass and breaks exactly one
    thing, so a failure here names the guarantee that stopped holding.
    """

    BOUNDARY = "build-to-review"

    def _spoiled(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = build_package(self.BOUNDARY, root)
            mutate(package, root)
            return run_gate(self.BOUNDARY, package, root)

    def test_baseline_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            verdict = run_gate(self.BOUNDARY, build_package(self.BOUNDARY, root), root)
        self.assertTrue(verdict.get("pass"), verdict.get("failures"))

    def test_missing_required_evidence_is_refused(self):
        key = GATES["boundaries"][self.BOUNDARY]["required_evidence"][0]
        verdict = self._spoiled(lambda pkg, root: pkg["evidence"].pop(key))
        self.assertFalse(verdict.get("pass"))
        self.assertIn(f"missing evidence: {key}", verdict.get("failures", []))

    def test_bare_fallback_string_is_refused_at_schema_two(self):
        """The sanctioned wording alone is not a waiver at schema 2."""
        waivable = GATES.get("fallback_values") or {}
        key = next(k for k in GATES["boundaries"][self.BOUNDARY]["required_evidence"]
                   if k in waivable)
        wording = waivable[key][0]
        verdict = self._spoiled(lambda pkg, root: pkg["evidence"].__setitem__(key, wording))
        self.assertFalse(verdict.get("pass"))
        self.assertIn(f"bare fallback string not accepted at schema 2: {key} "
                      "(use an applicability record)", verdict.get("failures", []))

    def test_applicability_record_is_accepted_for_a_waivable_key(self):
        waivable = GATES.get("fallback_values") or {}
        key = next(k for k in GATES["boundaries"][self.BOUNDARY]["required_evidence"]
                   if k in waivable)
        record = {"applicable": False, "reason": waivable[key][0],
                  "scope": "synthetic probe", "decided_by": "test"}
        verdict = self._spoiled(lambda pkg, root: pkg["evidence"].__setitem__(key, record))
        self.assertTrue(verdict.get("pass"), verdict.get("failures"))

    def test_tampered_artifact_digest_is_refused(self):
        def tamper(pkg, root):
            (root / ARTIFACT_REL).write_text("altered after hashing\n", encoding="utf-8")
        verdict = self._spoiled(tamper)
        self.assertFalse(verdict.get("pass"))
        self.assertTrue(any("hash" in f or "digest" in f for f in verdict.get("failures", [])),
                        verdict.get("failures"))

    def test_wrong_submitter_is_refused(self):
        verdict = self._spoiled(lambda pkg, root: pkg.__setitem__("owner", "not-the-submitter"))
        self.assertFalse(verdict.get("pass"))
        self.assertTrue(any("submitter mismatch" in f for f in verdict.get("failures", [])),
                        verdict.get("failures"))

    def test_no_fallback_key_cannot_be_waived(self):
        """A boundary's `no_fallback` list beats the global waiver map."""
        barred = None
        for boundary, spec in GATES["boundaries"].items():
            for key in spec.get("no_fallback") or []:
                if key in (GATES.get("fallback_values") or {}):
                    barred = (boundary, key)
                    break
            if barred:
                break
        if not barred:
            self.skipTest("no boundary bars a key that the global map would otherwise waive")
        boundary, key = barred
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = build_package(boundary, root)
            package["evidence"][key] = {
                "applicable": False, "reason": (GATES["fallback_values"][key])[0],
                "scope": "synthetic probe", "decided_by": "test"}
            verdict = run_gate(boundary, package, root)
        self.assertFalse(verdict.get("pass"))
        self.assertIn(f"evidence not waivable: {key}", verdict.get("failures", []))


class RunLifecycleTests(unittest.TestCase):
    """One complete run, start to gate to close.

    `test_hooks_lifecycle.py` exercises each save operation in isolation — a
    checkpoint on a completed run, a stale lock, an interrupted journal. Nothing
    walked the whole arc: open a run, checkpoint once per pipeline stage, submit
    the package the stages produced, take a verdict, and close. That arc is what
    an orchestrator actually performs, and its failure mode is not any single
    operation but the seam between them: a revision that does not advance, a
    lock left held, an audit trail that loses a stage.
    """

    SAVE_RUN = SKILLS / "harness" / "hooks" / "save_run.py"
    PIPELINE = "build"

    def _save(self, root: Path, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, str(self.SAVE_RUN), "--project-root", str(root), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - writer crash
            raise AssertionError(
                f"save_run.py emitted no JSON for {args}: "
                f"{proc.stdout[:300]} {proc.stderr[:300]}") from exc

    def test_a_run_opens_advances_through_its_stages_passes_its_gate_and_closes(self):
        pipeline = PIPELINES["pipelines"][self.PIPELINE]
        boundary = pipeline["boundary"]
        owner = pipeline["owner"]
        stages = [s for s in pipeline["stages"] if s.get("owner")]
        self.assertGreater(len(stages), 2, "the build pipeline should have several stages")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skillset-saves").mkdir()  # the project-root marker

            opened = self._save(root, "create", "--run-id", "wf-probe", "--owner", owner)
            self.assertEqual("ok", opened.get("result"), opened)
            revision = opened.get("revision")
            self.assertIsInstance(revision, int, opened)

            # One checkpoint per stage, each asserting the revision it expects.
            # A stage that silently lands on the wrong revision is the failure
            # this loop exists to surface.
            for stage in stages:
                result = self._save(
                    root, "checkpoint", "--run-id", "wf-probe", "--owner", owner,
                    "--expect-revision", str(revision),
                    "--set", f"phase_state={self.PIPELINE.upper()}_ACTIVE",
                    "--next-action", f"delegate {stage['step']}")
                self.assertEqual("ok", result.get("result"),
                                 f"checkpoint failed at stage {stage['step']}: {result}")
                self.assertEqual(revision + 1, result.get("revision"),
                                 f"revision did not advance by one at {stage['step']}")
                revision = result["revision"]

            # The package those stages would have produced, judged by the real gate.
            package_root = root / "package"
            package_root.mkdir()
            verdict = run_gate(boundary, build_package(boundary, package_root), package_root)
            self.assertTrue(verdict.get("pass"),
                            f"the {self.PIPELINE} pipeline's own boundary refused its package: "
                            f"{verdict.get('failures')}")

            closed = self._save(root, "complete", "--run-id", "wf-probe", "--owner", owner,
                                "--next-action", "delivered")
            self.assertEqual("ok", closed.get("result"), closed)

            state = (root / "skillset-saves" / "runs" / "wf-probe" / "_state.md")
            self.assertTrue(state.is_file(), "the run record was never published")
            body = state.read_text(encoding="utf-8", errors="replace")
            self.assertIn("complete", body, "the closed run does not record its status")

            audit = (root / "skillset-saves" / "runs" / "wf-probe" / "_audit-trail.md")
            self.assertTrue(audit.is_file(), "no audit trail was written")
            trail = audit.read_text(encoding="utf-8", errors="replace")
            self.assertGreaterEqual(
                trail.count("checkpoint"), len(stages),
                "the audit trail lost a stage: one checkpoint event per stage is expected")

    def test_a_checkpoint_against_a_stale_revision_is_refused(self):
        """The optimistic-concurrency guard the whole arc depends on."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skillset-saves").mkdir()
            opened = self._save(root, "create", "--run-id", "wf-stale", "--owner", "build-management")
            stale = opened["revision"]
            first = self._save(root, "checkpoint", "--run-id", "wf-stale",
                               "--owner", "build-management", "--expect-revision", str(stale))
            self.assertEqual("ok", first.get("result"), first)
            replay = self._save(root, "checkpoint", "--run-id", "wf-stale",
                                "--owner", "build-management", "--expect-revision", str(stale))
            self.assertEqual("refused", replay.get("result"),
                             "a second writer on the same revision must be refused")


class StageCoverageTests(unittest.TestCase):
    """Pipeline stages and gate evidence have to describe the same run.

    A boundary requires evidence keys; a pipeline declares the stages that run
    before it. If the two drift, a pipeline is documented as complete while its
    gate asks for something no stage produces.
    """

    def test_every_stage_owner_is_a_real_skill(self):
        known = {p.parent.relative_to(SKILLS).as_posix() for p in SKILLS.rglob("SKILL.md")}
        leaves = {name.rsplit("/", 1)[-1] for name in known}
        unknown = []
        for pipeline, data in PIPELINES["pipelines"].items():
            for stage in data.get("stages", []):
                for field in ("owner", "delegate"):
                    who = stage.get(field)
                    if who and who not in known and who not in leaves:
                        unknown.append(f"{pipeline}/{stage.get('step')} {field}={who!r} is not a skill")
        self.assertEqual([], unknown, "\n".join(unknown))

    def test_every_declared_stage_artifact_has_an_owner_in_ownership(self):
        artifacts = {entry["id"] for entry in OWNERSHIP.get("artifacts", [])
                     if isinstance(entry, dict) and "id" in entry}
        if not artifacts:
            self.skipTest("ownership.yaml exposes no artifact ids in the expected shape")
        unknown = []
        for pipeline, data in PIPELINES["pipelines"].items():
            for stage in data.get("stages", []):
                artifact = stage.get("artifact")
                if artifact and artifact not in artifacts:
                    unknown.append(
                        f"{pipeline}/{stage.get('step')} produces {artifact!r}, "
                        "which ownership.yaml does not declare")
        self.assertEqual([], unknown, "\n".join(unknown))

    def test_phase_gate_stages_match_what_the_gate_model_claims(self):
        """`gate_model` names which pipelines carry a phase-gate stage.

        Six of the ten deliberately carry none — their boundary is judged once,
        by `gatekeeper-admiral`, and `pipelines.yaml` `gate_model` says so in
        prose. That prose is the only place the distinction is recorded, so it
        is worth comparing: a pipeline that gains or loses a phase gatekeeper
        without the model being updated is exactly the drift this suite exists
        to catch. The first version of this test asserted every pipeline ends at
        a gatekeeper and was simply wrong about the catalog.
        """
        model = str(PIPELINES.get("gate_model") or "")
        self.assertIn("only four model the gate as a stage", model,
                      "gate_model no longer states how many pipelines carry a phase-gate stage")

        claimed = set()
        for sentence in model.split("."):
            if "carry an explicit phase-gate stage" in sentence:
                claimed = {name for name in PIPELINES["pipelines"]
                           if f"{name}," in sentence or f"{name} " in sentence}
                break
        self.assertTrue(claimed, "could not read the phase-gated pipeline names out of gate_model")

        actual = set()
        for pipeline, data in PIPELINES["pipelines"].items():
            for stage in data.get("stages") or []:
                if "gatekeeper" in str(stage.get("owner", "")):
                    actual.add(pipeline)
        self.assertEqual(
            claimed, actual,
            f"gate_model claims {sorted(claimed)} carry a phase-gate stage; "
            f"pipelines.yaml actually gives one to {sorted(actual)}")


if __name__ == "__main__":
    unittest.main()
