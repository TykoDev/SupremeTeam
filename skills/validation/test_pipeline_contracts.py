#!/usr/bin/env python3
"""Contract tests for pipelines.yaml and its cross-references.

Every pipeline owner and stage owner must be a member of the team, every
boundary must exist in gates.yaml and be closed by exactly one pipeline, every
referenced artifact must be an ownership.yaml artifact id, and every required
script must exist on disk. Three facts of the stage lists are pinned as well: the
redesign pipeline records its selection before it builds a prototype, four stages
that produce evidence the release, qa and design boundaries require run
unconditionally, and `gate_model` names the pipelines that carry a phase-gate
stage.
"""

from __future__ import annotations

import re
import unittest

import _catalog
import validate_manifests

ROOT = _catalog.SKILLS
GATES = _catalog.load_spec("gates.yaml")
PIPELINES = _catalog.load_spec("pipelines.yaml")


class PipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = PIPELINES
        cls.gates = GATES
        cls.ownership = _catalog.load_spec("ownership.yaml")
        cls.members = _catalog.roster()
        cls.artifact_ids = {str(item.get("id")) for item in cls.ownership.get("artifacts", [])}

    def test_spec_shape(self):
        self.assertEqual(self.spec["schema_version"], 1)
        self.assertEqual(self.spec["kind"], "supremeteam-pipeline-spec")
        self.assertTrue(self.spec["pipelines"])

    def test_every_pipeline_owner_is_a_team_member(self):
        for name, pipeline in self.spec["pipelines"].items():
            with self.subTest(pipeline=name):
                self.assertIn(pipeline["owner"], self.members)

    def test_every_stage_owner_is_a_team_member(self):
        for name, pipeline in self.spec["pipelines"].items():
            for stage in pipeline["stages"]:
                with self.subTest(pipeline=name, step=stage.get("step")):
                    self.assertTrue(stage.get("step"))
                    self.assertIn(stage.get("owner"), self.members)

    def test_every_boundary_exists_in_gate_spec(self):
        boundaries = set(self.gates["boundaries"])
        for name, pipeline in self.spec["pipelines"].items():
            with self.subTest(pipeline=name):
                self.assertIn(pipeline["boundary"], boundaries)

    def test_every_gate_boundary_is_owned_by_some_pipeline(self):
        """No boundary may exist in gates.yaml without a pipeline that closes it,
        and no pipeline may close a boundary the gate spec does not define."""
        pipeline_boundaries = {p["boundary"] for p in self.spec["pipelines"].values()}
        self.assertEqual(pipeline_boundaries, set(self.gates["boundaries"]))

    def test_every_boundary_is_closed_by_exactly_one_pipeline(self):
        owners: dict[str, list[str]] = {}
        for name, data in PIPELINES["pipelines"].items():
            boundary = data.get("boundary")
            if boundary:
                owners.setdefault(boundary, []).append(name)
        problems = [f"{b} is closed by {p}" for b, p in owners.items() if len(p) > 1]
        problems += [f"{b} is closed by no pipeline" for b in GATES["boundaries"] if b not in owners]
        self.assertEqual([], problems, "\n".join(problems))

    def test_every_stage_artifact_is_an_ownership_artifact(self):
        for name, pipeline in self.spec["pipelines"].items():
            for stage in pipeline["stages"]:
                artifact = stage.get("artifact")
                if artifact is None:
                    continue
                with self.subTest(pipeline=name, artifact=artifact):
                    self.assertIn(artifact, self.artifact_ids)

    def test_every_required_script_exists(self):
        for name, pipeline in self.spec["pipelines"].items():
            for script in pipeline.get("scripts", []):
                with self.subTest(pipeline=name, script=script):
                    self.assertTrue(script.startswith("skills/"), script)
                    self.assertTrue((ROOT.parent / script).is_file(), script)

    def test_stage_dependencies_are_available_in_declared_order(self):
        """A stage cannot consume an artifact that only a later stage produces."""
        checked = 0
        for name, pipeline in self.spec["pipelines"].items():
            available = set(pipeline.get("external_inputs", []))
            for stage in pipeline["stages"]:
                contract = validate_manifests.stage_dependencies(pipeline, stage)
                if stage.get("after_boundary"):
                    available.add("approved-boundary")
                required = set(contract.get("requires", []))
                with self.subTest(pipeline=name, step=stage.get("step")):
                    self.assertLessEqual(required, available)
                    self.assertTrue(set(contract.get("produces", [])).isdisjoint(available))
                checked += len(required)
                available.update(contract.get("produces", []))
        self.assertGreater(checked, 0, "expected at least one machine-readable stage dependency")

    def test_validator_rejects_a_forward_dependency(self):
        pipeline = {
            "external_inputs": ["request"],
            "stages": [
                {"step": "spec", "requires": ["stack-lock"], "produces": ["implementation-spec"]},
                {"step": "lock", "requires": ["implementation-spec"], "produces": ["stack-lock"]},
            ],
        }
        errors = validate_manifests.pipeline_dependency_errors("design", pipeline)
        self.assertEqual(len(errors), 1)
        self.assertIn("design/spec requires unavailable inputs ['stack-lock']", errors[0])

    def test_gate_spec_submitters_are_team_members(self):
        for name, boundary in self.gates["boundaries"].items():
            with self.subTest(boundary=name):
                self.assertIn(boundary["submitter"], self.members)

    def test_taste_pipeline_contract_is_complete(self):
        taste = self.spec["pipelines"]["taste"]
        self.assertIn(taste["owner"], self.members)
        for stage in taste["stages"]:
            self.assertIn(stage["owner"], self.members)
            if stage.get("artifact"):
                self.assertIn(stage["artifact"], self.artifact_ids)
        owners = [name for name, pipeline in self.spec["pipelines"].items()
                  if pipeline["boundary"] == "taste-review"]
        self.assertEqual(owners, ["taste"])
        self.assertIn("taste-review", self.gates["boundaries"])
        for script in taste["scripts"]:
            self.assertTrue((ROOT.parent / script).is_file(), script)


class StageArtifactOwnershipTests(unittest.TestCase):
    """A stage that produces an artifact must be run by that artifact's owner.

    pipelines.yaml and ownership.yaml both name an owner, and nothing compared
    them: the review found two stages assigned to a skill ownership.yaml does not
    let write that artifact, which would have failed the one-writer rule at the
    gate rather than here.
    """

    def test_every_artifact_bearing_stage_is_owned_by_the_artifact_owner(self):
        ownership = _catalog.load_spec("ownership.yaml")
        pipelines = _catalog.load_spec("pipelines.yaml")
        owners = {a["id"]: a.get("owner") for a in ownership["artifacts"]}
        checked = 0
        for name, pipeline in pipelines["pipelines"].items():
            for stage in pipeline.get("stages", []):
                artifact = stage.get("artifact")
                if not artifact:
                    continue
                checked += 1
                self.assertIn(artifact, owners,
                              f"{name}/{stage['step']} produces undeclared artifact {artifact!r}")
                # A stage may delegate the work, but the owner still owns the write.
                self.assertEqual(
                    stage.get("owner"), owners[artifact],
                    f"{name}/{stage['step']} is owned by {stage.get('owner')!r} but "
                    f"ownership.yaml gives {artifact!r} to {owners[artifact]!r}",
                )
        self.assertGreater(checked, 10, "expected the pipelines to declare artifact-bearing stages")


class StageCoverageTests(unittest.TestCase):
    """Pipeline stages and gate evidence have to describe the same run.

    A boundary requires evidence keys; a pipeline declares the stages that run
    before it. Three facts of the stage lists are what the gate spec and
    `gate_model` rest on, and nothing else checks them: the redesign stages that
    produce the selected-variant evidence follow the selection, four stages that
    produce evidence the release, qa and design boundaries require carry no
    `when`, and the pipelines `gate_model` names are the ones that carry a
    phase-gate stage.
    """

    def test_the_redesign_pipeline_builds_mocks_before_it_builds_anything(self):
        """Order is judgement everywhere else; here it is the whole fix.

        Four living prototypes built before a choice is three implementations
        thrown away. The stage list is what stops that recurring, so the two
        facts it rests on are pinned: every stage that produces the
        selected-variant evidence runs after the stage that records the
        selection, and each of those stages is conditional on it.
        """
        stages = PIPELINES["pipelines"]["redesign"]["stages"]
        order = {stage["step"]: index for index, stage in enumerate(stages)}
        self.assertIn("selection", order, "the redesign pipeline records no selection")
        self.assertLess(order["mock-build"], order["selection"],
                        "the mocks are drawn before the choice, not after it")

        owners = GATES["evidence_owners"]["redesign-review"]
        after_the_choice = {owners[key] for key in
                            ("selected_variant", "parity_evidence", "rendered_verification")}
        late = [s for s in stages if s.get("owner") in after_the_choice
                and order[s["step"]] > order["selection"]]
        self.assertTrue(late, "no stage runs after the selection")
        for stage in late:
            with self.subTest(stage=stage["step"]):
                self.assertEqual("a variant was selected", stage.get("when"),
                                 f"{stage['step']} runs unconditionally, so a deferral "
                                 f"or a merge would still build a prototype")

    def test_required_evidence_has_unconditional_producers(self):
        """Four stages that produce evidence their boundary always requires run on every run.

        The release setup stage is `setup-deploy`'s, the owner of the deploy config
        and rollback plan `deploy-readiness` requires; `qa` captures the executed
        probes and records the defects `qa-review` requires; and the security seed
        is a key `design-to-build` requires. None of those stages may carry a
        `when`. The taste snapshot `design-to-build` also requires is taken by
        `taste` in a stage of its own, and the design phase gate waits for it.
        """
        pipelines = PIPELINES["pipelines"]
        release = pipelines["release"]
        self.assertNotIn("when", next(stage for stage in release["stages"] if stage["step"] == "setup"))
        qa = pipelines["qa"]
        for step in ("evidence-capture", "defect-record"):
            self.assertNotIn("when", next(stage for stage in qa["stages"] if stage["step"] == step))
        design = pipelines["design"]
        seed = next(stage for stage in design["stages"] if stage["step"] == "security-seed")
        self.assertNotIn("when", seed)
        snapshot = next(stage for stage in design["stages"] if stage["step"] == "taste-snapshot")
        self.assertEqual(snapshot["owner"], "taste")
        self.assertIn("taste-snapshot", snapshot["produces"])
        self.assertIn("taste-snapshot", design["stages"][-1]["requires"])

    def test_phase_gate_stages_match_what_the_gate_model_claims(self):
        """`gate_model` names which pipelines carry a phase-gate stage, and how many.

        Six of the ten deliberately carry none — their boundary is judged once,
        by `gatekeeper-admiral`, and `pipelines.yaml` `gate_model` says so in
        prose. That prose is the only place the distinction is recorded, so it
        is worth comparing: a pipeline that gains or loses a phase gatekeeper
        without the model being updated is exactly the drift this suite exists
        to catch. The first version of this test asserted every pipeline ends at
        a gatekeeper and was simply wrong about the catalog.
        """
        model = str(PIPELINES.get("gate_model") or "")
        stated = re.search(r"only ([a-z-]+) model the gate as a stage", model)
        self.assertIsNotNone(stated, "gate_model no longer states how many pipelines carry a phase-gate stage")

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
        self.assertEqual(_catalog.number_word(len(actual)), stated.group(1),
                         f"gate_model says {stated.group(1)} pipelines model the gate as a stage; {len(actual)} do")


if __name__ == "__main__":
    unittest.main()
