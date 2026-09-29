#!/usr/bin/env python3
"""In-process regression tests for the manifest engine (check.py).

The command-line tests in test_gate_manifests.py, test_gate_run_layout.py and
test_gate_revise.py pin end-to-end behaviour one package at a time. These drive a
``Package`` directly, which is what lets a matrix - every waivable key at every
boundary, every evidence type the spec declares - run in milliseconds instead of
paying one interpreter start per cell, and lets a fault be injected where a
subprocess could not reach it.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"
GATE_SPEC = SKILLS / "gates.yaml"


def load_engine():
    spec = importlib.util.spec_from_file_location("gate_check_engine", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load_engine()


class EngineCase(unittest.TestCase):
    """A scratch directory and a way to build a ``Package`` without touching disk twice."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.spec = engine.load_gate_spec(GATE_SPEC)

    def package(self, boundary: str, evidence: dict | None = None, **manifest):
        data = {"schema_version": 2, "boundary": boundary, "owner": self.spec["boundaries"][boundary]["submitter"],
                "submission_id": "s1", "revision": "r1", "revisions": ["r1"],
                "evidence": evidence or {}, "artifact_hashes": {}}
        data.update(manifest)
        return engine.Package(self.root / "manifest.json", data, boundary, self.spec)


class WaiverWordingTests(EngineCase):
    """A waiver is the sanctioned wording and nothing else (gates.yaml fallback_values)."""

    def waivable(self):
        """Every (boundary, key, sanctioned wordings) the spec lets a submitter waive."""
        for boundary, contract in self.spec["boundaries"].items():
            barred = set(contract.get("no_fallback") or [])
            declared = set(self.spec["fallback_values"]) | set(contract.get("fallback_values", {}))
            for key in sorted((declared & set(contract["required_evidence"])) - barred):
                yield boundary, key, contract.get("fallback_values", {}).get(key) or self.spec["fallback_values"][key]

    @staticmethod
    def record(reason):
        return {"applicable": False, "reason": reason, "scope": "whole run", "decided_by": "owner"}

    def test_a_reason_other_than_the_sanctioned_wording_never_waives_a_key(self):
        cells = 0
        for boundary, key, allowed in self.waivable():
            unsanctioned = ("covered elsewhere", "skipped", allowed[0].upper(), allowed[0] + " ", " " + allowed[0])
            for reason in unsanctioned:
                with self.subTest(boundary=boundary, key=key, reason=reason):
                    package = self.package(boundary)
                    self.assertTrue(package.applicability_record(key, self.record(reason)))
                    self.assertEqual(len(package.failures), 1, package.failures)
                    self.assertTrue(package.failures[0].startswith(f"applicability reason not sanctioned: {key} "),
                                    package.failures)
                    cells += 1
        self.assertGreater(cells, 60, "the matrix silently emptied")

    def test_an_empty_or_non_string_reason_is_an_incomplete_record(self):
        for boundary, key, allowed in self.waivable():
            for reason in ("", "   ", None, 7, False, [allowed[0]], {"text": allowed[0]}):
                with self.subTest(boundary=boundary, key=key, reason=reason):
                    package = self.package(boundary)
                    self.assertTrue(package.applicability_record(key, self.record(reason)))
                    self.assertEqual(package.failures, [f"applicability record incomplete: {key} requires reason"])

    def test_each_sanctioned_wording_waives_its_key_at_its_boundary(self):
        cells = 0
        for boundary, key, allowed in self.waivable():
            for wording in allowed:
                with self.subTest(boundary=boundary, key=key, wording=wording):
                    package = self.package(boundary)
                    self.assertTrue(package.applicability_record(key, self.record(wording)))
                    self.assertEqual(package.failures, [])
                    cells += 1
        self.assertGreater(cells, 15, "the matrix silently emptied")

    def test_a_boundary_list_replaces_the_global_wording_rather_than_adding_to_it(self):
        """At redesign-review rendered_verification stands down on the selection wordings only."""
        package = self.package("redesign-review")
        global_wording = self.spec["fallback_values"]["rendered_verification"][0]
        self.assertTrue(package.applicability_record("rendered_verification", self.record(global_wording)))
        self.assertEqual(len(package.failures), 1, package.failures)
        self.assertTrue(package.failures[0].startswith("applicability reason not sanctioned: rendered_verification "))

    def test_the_wording_is_owned_by_the_key_not_borrowed_from_another(self):
        package = self.package("build-to-review")
        borrowed = self.spec["fallback_values"]["stack_lock"][0]
        self.assertTrue(package.applicability_record("security_evidence", self.record(borrowed)))
        self.assertEqual(len(package.failures), 1, package.failures)
        self.assertTrue(package.failures[0].startswith("applicability reason not sanctioned: security_evidence "))

    def test_a_key_the_boundary_does_not_list_is_not_waivable_whatever_the_wording(self):
        package = self.package("build-to-review")
        self.assertTrue(package.applicability_record("implementation", self.record("anything at all")))
        self.assertEqual(package.failures, ["evidence not waivable: implementation"])


if __name__ == "__main__":
    unittest.main()
