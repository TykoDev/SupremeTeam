"""A spec cannot rewrite its own safety floor.

contract_floor.py holds the gate floor apart from gates.yaml, so no edit to the spec
can lower it. Pipeline ordering is validate_manifests.py's check; its tests are in
test_validate_manifests.py. The producers and the probe writer the gates rely on are
facts of the shipped specs, pinned in validation/test_pipeline_contracts.py and
validation/test_save_contracts.py.
"""
from __future__ import annotations

import copy
import unittest
from pathlib import Path

import contract_floor
from contract_floor import gate_floor_errors
from data_formats import load_data

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

    def test_floor_covers_every_shipped_type_and_backing(self):
        """A typed key or an artifact backing added to gates.yaml without a floor entry is one the spec could drop again
        with no floor error, so the floor has to name everything the shipped spec does."""
        self.assertEqual(self.spec["evidence_types"], contract_floor.TYPES)
        self.assertEqual(set(self.spec["boundaries"]), set(contract_floor.REQUIRED))
        for name, boundary in self.spec["boundaries"].items():
            with self.subTest(boundary=name):
                self.assertEqual(sorted(boundary["required_evidence"]), sorted(contract_floor.REQUIRED[name].split()))
                self.assertEqual(sorted(boundary["artifact_evidence"]), sorted(contract_floor.ARTIFACTS[name].split()))
        links = {key: record for key, record in self.spec["evidence_type_params"].items() if "upstream_boundary" in record}
        self.assertEqual(links, contract_floor.REVISION_LINKS)
        self.assertEqual({key for key, kind in self.spec["evidence_types"].items() if kind == "revision_ref"},
                         set(contract_floor.REVISION_LINKS), "every revision_ref key has a pinned upstream link")

    def test_removing_any_one_typed_kind_is_rejected(self):
        for key in self.spec["evidence_types"]:
            with self.subTest(removed=key):
                spec = copy.deepcopy(self.spec)
                del spec["evidence_types"][key]
                self.assertIn("gate safety floor: typed evidence weakened", gate_floor_errors(spec))
            with self.subTest(retyped=key):
                spec = copy.deepcopy(self.spec)
                spec["evidence_types"][key] = "text"
                self.assertIn("gate safety floor: typed evidence weakened", gate_floor_errors(spec))

    def test_removing_any_one_required_key_or_artifact_backing_is_rejected(self):
        for name, boundary in self.spec["boundaries"].items():
            for field in ("required_evidence", "artifact_evidence"):
                for key in boundary[field]:
                    with self.subTest(boundary=name, field=field, removed=key):
                        spec = copy.deepcopy(self.spec)
                        spec["boundaries"][name][field].remove(key)
                        self.assertIn(f"gate safety floor: {name}.{field} weakened", gate_floor_errors(spec))

    def test_the_five_backings_and_five_kinds_the_floor_once_missed_are_pinned(self):
        """Issue 4: deleting all of these from a copy of the spec used to yield no floor error."""
        spec = copy.deepcopy(self.spec)
        for key in ("decisions", "acceptance", "interfaces", "implementation", "traceability"):
            del spec["evidence_types"][key]
        for name, keys in (("design-to-build", ("acceptance", "interfaces")),
                           ("build-to-review", ("approved_design_revision", "implementation")),
                           ("deploy-readiness", ("approved_delivery",))):
            for key in keys:
                spec["boundaries"][name]["artifact_evidence"].remove(key)
        errors = gate_floor_errors(spec)
        self.assertIn("gate safety floor: typed evidence weakened", errors)
        for name in ("design-to-build", "build-to-review", "deploy-readiness"):
            self.assertIn(f"gate safety floor: {name}.artifact_evidence weakened", errors)

    def test_changing_or_removing_an_upstream_link_is_rejected(self):
        mutations = (
            ("approved_design_revision", lambda record: record.pop("upstream_boundary")),
            ("approved_design_revision", lambda record: record.update(upstream_boundary="build-to-review")),
            ("approved_design_revision", lambda record: record.pop("acceptance_key")),
            ("approved_design_revision", lambda record: record.update(acceptance_key="plan")),
            ("approved_delivery", lambda record: record.pop("upstream_boundary")),
            ("approved_delivery", lambda record: record.update(upstream_boundary="deploy-readiness")),
        )
        for index, (key, mutate) in enumerate(mutations):
            with self.subTest(key=key, mutation=index):
                spec = copy.deepcopy(self.spec)
                mutate(spec["evidence_type_params"][key])
                self.assertIn(f"gate safety floor: {key} upstream link changed", gate_floor_errors(spec))
        for key in contract_floor.REVISION_LINKS:
            with self.subTest(removed=key):
                spec = copy.deepcopy(self.spec)
                del spec["evidence_type_params"][key]
                self.assertIn(f"gate safety floor: {key} upstream link changed", gate_floor_errors(spec))

    def test_the_revise_cycle_cap_is_pinned(self):
        for value in (2, 4, 0, None, "3", True):
            with self.subTest(cycle_cap=value):
                spec = copy.deepcopy(self.spec)
                spec["revise_policy"]["cycle_cap"] = value
                self.assertIn("gate safety floor: revise_policy.cycle_cap must be 3", gate_floor_errors(spec))
        for replacement in ({}, None, []):
            with self.subTest(revise_policy=replacement):
                spec = copy.deepcopy(self.spec)
                spec["revise_policy"] = replacement
                self.assertIn("gate safety floor: revise_policy.cycle_cap must be 3", gate_floor_errors(spec))

    def test_every_required_key_keeps_an_owner(self):
        for name, keys in contract_floor.REQUIRED.items():
            for key in keys.split():
                for mutate in (lambda table, key=key: table.pop(key), lambda table, key=key: table.update({key: ""}),
                               lambda table, key=key: table.update({key: None})):
                    with self.subTest(boundary=name, key=key):
                        spec = copy.deepcopy(self.spec)
                        mutate(spec["evidence_owners"][name])
                        self.assertIn(f"gate safety floor: {name} evidence_owners does not name an owner for every required key",
                                      gate_floor_errors(spec))
        for replacement in ({}, None, []):
            with self.subTest(evidence_owners=replacement):
                spec = copy.deepcopy(self.spec)
                spec["evidence_owners"] = replacement
                self.assertTrue(gate_floor_errors(spec))

    def test_a_spec_that_requires_more_than_the_floor_still_passes(self):
        """The floor is a minimum: a new required key, with its backing, kind and owner, is stronger and is not an error."""
        spec = copy.deepcopy(self.spec)
        spec["boundaries"]["qa-review"]["required_evidence"].append("soak_test")
        spec["boundaries"]["qa-review"]["artifact_evidence"].append("soak_test")
        spec["evidence_owners"]["qa-review"]["soak_test"] = "qa"
        self.assertEqual(gate_floor_errors(spec), [])


if __name__ == "__main__":
    unittest.main()
