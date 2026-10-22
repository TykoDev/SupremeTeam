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


if __name__ == "__main__":
    unittest.main()
