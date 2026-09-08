#!/usr/bin/env python3
"""Contract tests for pipelines.yaml and its cross-references.

Every pipeline owner and stage owner must be a member of the team, every
boundary must exist in gates.yaml, every referenced artifact must be an
ownership.yaml artifact id, and every required script must exist on disk.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_manifests  # noqa: E402
from data_formats import load_data  # noqa: E402


def team_members() -> set[str]:
    """The roster, read through the same helper validate_manifests.py uses."""
    return validate_manifests.team_members(load_data(ROOT / "team-manifest.yaml"))


class PipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT / "pipelines.yaml").read_text(encoding="utf-8"))
        cls.gates = json.loads((ROOT / "gates.yaml").read_text(encoding="utf-8"))
        cls.ownership = load_data(ROOT / "ownership.yaml")
        cls.members = team_members()
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

    def test_gate_spec_submitters_are_team_members(self):
        for name, boundary in self.gates["boundaries"].items():
            with self.subTest(boundary=name):
                self.assertIn(boundary["submitter"], self.members)


class StageArtifactOwnershipTests(unittest.TestCase):
    """A stage that produces an artifact must be run by that artifact's owner.

    pipelines.yaml and ownership.yaml both name an owner, and nothing compared
    them: the review found two stages assigned to a skill ownership.yaml does not
    let write that artifact, which would have failed the one-writer rule at the
    gate rather than here.
    """

    def test_every_artifact_bearing_stage_is_owned_by_the_artifact_owner(self):
        ownership = load_data(ROOT / "ownership.yaml")
        pipelines = load_data(ROOT / "pipelines.yaml")
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


if __name__ == "__main__":
    unittest.main()