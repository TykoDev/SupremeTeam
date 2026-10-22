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
produces passing packages proves the generator works, not the gate, so
``GateRefusalTests`` spoils one of these packages and asserts the gate notices.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import _catalog
from _catalog import REPO, SKILLS
from data_formats import content_sha256, parse_yaml

sys.path.insert(0, str(SKILLS / "harness" / "gatekeeper"))
import _fixtures

# The specs are read the way the gate reads them, with data_formats, so this module
# runs on a host without PyYAML instead of skipping the one end-to-end gate test.
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"
GATES = _catalog.load_spec("gates.yaml")
PIPELINES = _catalog.load_spec("pipelines.yaml")
REGISTRY = _catalog.load_spec("tech-stacks/registry.yaml")

#: The first registry overlay, used to build a stack_lock the gate will accept.
#: Reading it rather than hardcoding means the fixture follows the registry, and
#: a digest that stops matching its own overlay file fails here first.
OVERLAY = REGISTRY["overlays"][0]

ARTIFACT_REL = "phase/evidence.md"
#: One body every source-of-truth record can read: a grilling log, an acceptance
#: table, an interface note, a diff naming this very file, and a test log.
ARTIFACT_BODY = _fixtures.source_of_truth(ARTIFACT_REL)
#: The upstream revision every revision_ref binds to, and that human_go repeats.
UPSTREAM_REVISION = "r-3"


def _digest_of(path: Path) -> str:
    return content_sha256(path)


def _typed_record(kind: str, artifact: str, digest: str, key: str = "") -> object:
    """A record of ``kind`` the checker accepts.

    Every field here was added because the checker demanded it by name. The
    comments mark the ones that are not obvious from the spec prose.

    ``key`` matters for the two kinds the gate spec parameterises per evidence
    key: a ``variant_set`` is four mocks under ``mocks`` for ``mock_set`` and one
    built variant under ``variants`` for ``selected_variant``, and a
    ``selection`` has to name an id the mock set actually declares.
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
        # Shape, list name and count all come from the spec, so the fixture
        # follows the spec rather than restating four-of-everything.
        params = (GATES.get("evidence_type_params") or {}).get(key) or {}
        list_field = params.get("list_field", "variants")
        fields = params.get("file_fields", ["spec", "tokens", "components", "app"])
        count = int(params.get("required_count", 1))
        entries = [{"id": f"v{i}", "name": f"Direction {i}", "direction": f"d{i}",
                    **{field: artifact for field in fields}} for i in range(1, count + 1)]
        return {"artifacts": [artifact], list_field: entries, "count": count}
    if kind == "selection":
        params = (GATES.get("evidence_type_params") or {}).get(key) or {}
        option = (GATES.get("evidence_type_params") or {}).get(params.get("option_key", ""), {})
        built = (GATES.get("evidence_type_params") or {}).get(params.get("built_key", ""), {})
        # The chosen id has to be one the mock set declares *and* the one the
        # built variant carries, so it is read off the same generator above.
        chosen = f"v{int(built.get('required_count', 1))}" if option else "v1"
        return {"schema_version": 2, "artifacts": [artifact],
                "decision": params.get("variant_decision", "variant"),
                "chosen": chosen, "recommended": chosen, "decided_by": "workflow probe",
                "decided_at": "2026-09-16T00:00:00Z", "basis": "synthetic decision"}
    if kind == "security_seed":
        return {"applicable": False, "scope": "synthetic design", "decided_by": "security-builder",
                "architecture_revision": "r-3", "reason": "no boundary introduced", "boundaries": []}
    if kind == "human_go":
        return {"decision": "go", "approver": "synthetic owner", "approval_reference": "GO-1",
                "revision": "r-3", "decided_at": "2026-09-16T00:00:00Z"}
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
                "added": ["p-1"], "removed": [], "changed": [], "deprecated": [],
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
    hashes = {ARTIFACT_REL: digest}
    source = _fixtures.records(ARTIFACT_REL, ARTIFACT_REL, digest)
    params = GATES.get("evidence_type_params") or {}
    for key in spec["required_evidence"]:
        kind = types.get(key)
        if kind in source:
            evidence[key] = source[kind]
        elif kind == "revision_ref":
            # The record binds the upstream cross-stage verdict, so the fixture
            # writes an approved upstream package for the gate to re-hash.
            upstream = root / "upstream"
            verdict, verdict_digest = _fixtures.approved_upstream(
                root, upstream, params[key]["upstream_boundary"], UPSTREAM_REVISION, "workflow-probe",
                {f"../{ARTIFACT_REL}": artifact}, evidence={"acceptance": f"../{ARTIFACT_REL}"})
            evidence[key] = {"revision": UPSTREAM_REVISION, "verdict": verdict}
            hashes[verdict] = verdict_digest
        elif kind:
            evidence[key] = _typed_record(kind, ARTIFACT_REL, digest, key)
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
        "artifact_hashes": hashes,
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


class GateRefusalTests(unittest.TestCase):
    """The gate notices when a package this module builds is spoiled.

    Without this, the satisfiability test above only proves the fixture builder
    works. The case starts from a package the gate accepts and breaks one thing,
    the artifact under its recorded digest. The other refusals a package can
    meet (missing evidence, a bare fallback at schema 2, a wrong submitter, a
    barred waiver) are the gate's own tests, in `harness/gatekeeper/`.
    """

    BOUNDARY = "build-to-review"

    def _spoiled(self, mutate):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = build_package(self.BOUNDARY, root)
            mutate(package, root)
            return run_gate(self.BOUNDARY, package, root)

    def test_tampered_artifact_digest_is_refused(self):
        def tamper(pkg, root):
            (root / ARTIFACT_REL).write_text("altered after hashing\n", encoding="utf-8")
        verdict = self._spoiled(tamper)
        self.assertFalse(verdict.get("pass"))
        self.assertTrue(any("hash" in f or "digest" in f for f in verdict.get("failures", [])),
                        verdict.get("failures"))


class RunLifecycleTests(unittest.TestCase):
    """One complete run, start to gate to close.

    `test_run_state.py` exercises each save operation in isolation — a
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
            (root / "README.md").write_text("# fixture\n", encoding="utf-8")

            opened = self._save(root, "create", "--run-id", "wf-probe", "--owner", owner, "--evidence", "README.md")
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


class WorkedExampleTests(unittest.TestCase):
    """D-3: the Taste package example in handoff-templates.md passes the real checker."""

    def test_the_taste_package_example_passes_once_digests_are_filled(self):
        text = (SKILLS / "contracts" / "handoff-templates.md").read_text(encoding="utf-8")
        block = re.search(r"## Taste package example.*?```yaml\n(.*?)```", text, re.S)
        self.assertIsNotNone(block, "handoff-templates.md lost its Taste package example")
        package = parse_yaml(block.group(1))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in package["artifact_hashes"]:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}\n" if rel.endswith(".json") else "# record\n", encoding="utf-8")
                package["artifact_hashes"][rel] = content_sha256(path)
            # The example abbreviates every digest as "<sha256>"; a real package carries full values.
            filled = json.loads(json.dumps(package).replace('"<sha256>"', json.dumps("a" * 64)))
            verdict = run_gate("taste-review", filled, root)
        self.assertEqual(verdict["failures"], [])


if __name__ == "__main__":
    unittest.main()
