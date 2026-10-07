"""A spec cannot rewrite its own safety floor or weaken pipeline ordering."""
from __future__ import annotations

import copy
import fnmatch
import unittest
from pathlib import Path

from contract_floor import gate_floor_errors
from data_formats import load_data
from validate_manifests import pipeline_dependency_errors, stage_dependencies

ROOT = Path(__file__).resolve().parents[1]


class GateFloorTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_data(ROOT / "gates.yaml")

    def test_shipped_spec_meets_independent_floor(self):
        self.assertEqual(gate_floor_errors(self.spec), [])

    def test_weakening_every_boundary_is_rejected(self):
        for boundary in self.spec["boundaries"]:
            for field in ("required_evidence", "artifact_evidence"):
                with self.subTest(boundary=boundary, field=field):
                    spec = copy.deepcopy(self.spec)
                    spec["boundaries"][boundary][field] = []
                    self.assertTrue(gate_floor_errors(spec))

    def test_types_finding_policy_and_waiver_bar_cannot_be_erased(self):
        for field in ("evidence_types", "finding_policy"):
            spec = copy.deepcopy(self.spec)
            spec[field] = {}
            self.assertTrue(gate_floor_errors(spec))
        spec = copy.deepcopy(self.spec)
        spec["boundaries"]["redesign-review"].pop("no_fallback")
        self.assertTrue(gate_floor_errors(spec))
        for key in ("security_seed", "human_go_required", "confirmation", "tests", "runtime"):
            spec = copy.deepcopy(self.spec)
            spec["fallback_values"][key] = ["n/a"]
            self.assertTrue(gate_floor_errors(spec))

    def test_malformed_required_values_fail_readably(self):
        self.spec["boundaries"]["design-to-build"]["required_evidence"] = [{}]
        self.assertTrue(gate_floor_errors(self.spec))


class PipelineDependencyAuditTests(unittest.TestCase):
    def setUp(self):
        self.pipelines = load_data(ROOT / "pipelines.yaml")["pipelines"]

    def test_all_ten_pipelines_have_complete_checked_dependencies(self):
        self.assertEqual(len(self.pipelines), 10)
        for name, pipeline in self.pipelines.items():
            with self.subTest(pipeline=name):
                self.assertEqual(pipeline_dependency_errors(name, pipeline), [])
                for stage in pipeline["stages"]:
                    contract = stage_dependencies(pipeline, stage)
                    self.assertIn("requires", contract)
                    self.assertIn("produces", contract)

    def test_scalar_dependencies_and_duplicate_steps_are_refused(self):
        for name, original in self.pipelines.items():
            for field in ("external_inputs", "requires", "produces"):
                with self.subTest(pipeline=name, field=field):
                    pipeline = copy.deepcopy(original)
                    if field == "external_inputs":
                        pipeline[field] = "request"
                    else:
                        stage_dependencies(pipeline, pipeline["stages"][0])[field] = "request"
                    self.assertTrue(pipeline_dependency_errors(name, pipeline))
            pipeline = copy.deepcopy(original)
            pipeline["stages"].append(copy.deepcopy(pipeline["stages"][0]))
            self.assertTrue(any("unique" in error for error in pipeline_dependency_errors(name, pipeline)))

    def test_deleting_or_forward_referencing_any_contract_fails(self):
        for name, original in self.pipelines.items():
            with self.subTest(pipeline=name):
                pipeline = copy.deepcopy(original)
                contract = stage_dependencies(pipeline, pipeline["stages"][0])
                contract.pop("requires")
                self.assertTrue(pipeline_dependency_errors(name, pipeline))
                pipeline = copy.deepcopy(original)
                stage_dependencies(pipeline, pipeline["stages"][0])["requires"] = ["not-yet-produced"]
                self.assertTrue(pipeline_dependency_errors(name, pipeline))

    def test_post_gate_stages_cannot_move_before_approval(self):
        for name, step in (("release", "land-and-deploy"), ("release", "document"),
                           ("investigation", "return-to-owning-phase")):
            pipeline = copy.deepcopy(self.pipelines[name])
            stage = next(stage for stage in pipeline["stages"] if stage["step"] == step)
            stage.pop("after_boundary")
            self.assertTrue(pipeline_dependency_errors(name, pipeline))
        pipeline = copy.deepcopy(self.pipelines["release"])
        pipeline["external_inputs"].append("approved-boundary")
        self.assertTrue(pipeline_dependency_errors("release", pipeline))

    def test_startup_probe_has_a_declared_owner(self):
        policy = load_data(ROOT / "save-ownership.yaml")
        matches = [entry for entry in policy["classes"]
                   if any(fnmatch.fnmatchcase("skillset-saves/_probe-audit.tmp", pattern) for pattern in entry["patterns"])]
        self.assertEqual([entry["id"] for entry in matches], ["persistence-probe"])
        self.assertEqual(matches[0]["writer"], "admiral")

    def test_required_evidence_has_unconditional_producers(self):
        release = self.pipelines["release"]
        self.assertNotIn("when", next(stage for stage in release["stages"] if stage["step"] == "setup"))
        qa = self.pipelines["qa"]
        for step in ("evidence-capture", "defect-record"):
            self.assertNotIn("when", next(stage for stage in qa["stages"] if stage["step"] == step))
        design = self.pipelines["design"]
        seed = next(stage for stage in design["stages"] if stage["step"] == "security-seed")
        self.assertNotIn("when", seed)
        snapshot = next(stage for stage in design["stages"] if stage["step"] == "taste-snapshot")
        self.assertEqual(snapshot["owner"], "taste")
        self.assertIn("taste-snapshot", snapshot["produces"])
        self.assertIn("taste-snapshot", design["stages"][-1]["requires"])


if __name__ == "__main__":
    unittest.main()
