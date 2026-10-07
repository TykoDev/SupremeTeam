"""Audit regressions for evidence containment, BOM manifests and confirmation scope."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from unittest import mock

from test_gate_engine import EngineCase, engine
from data_formats import load_data


class QualityAuditEvidenceTests(EngineCase):
    def test_input_links_cannot_leave_the_project(self):
        outside = self.root.parent / (self.root.name + "-source.txt")
        outside.write_text("external", encoding="utf-8")
        self.addCleanup(outside.unlink)
        try:
            (self.root / "source.txt").symlink_to(outside)
        except OSError:
            self.skipTest("host cannot create symlinks")
        package = self.package("build-to-review")
        package.check_result_record("tests", "probe", {
            "artifacts": ["proof.log"], "result": {"status": "pass"},
            "inputs": [{"path": "source.txt", "sha256": engine.digest(outside)}]})
        self.assertTrue(any("via link" in failure for failure in package.failures), package.failures)

    def test_input_containment_checks_parent_links_and_missing_targets(self):
        try:
            (self.root / "linked").symlink_to(self.root.parent, target_is_directory=True)
        except OSError:
            self.skipTest("host cannot create symlinks")
        package = self.package("build-to-review")
        self.assertIsNone(package.project_path("linked/missing.txt", "tests"))
        self.assertIsNone(package.project_path("C:/source.txt", "tests"))
        self.assertIsNone(package.project_path("../source.txt", "tests"))
        for path in ("source.txt", "nested/source.txt"):
            self.assertIsInstance(package.project_path(path, "tests"), Path)

    def test_internal_input_link_remains_valid(self):
        source = self.root / "source.txt"
        source.write_text("source", encoding="utf-8")
        try:
            (self.root / "alias.txt").symlink_to(source)
        except OSError:
            self.skipTest("host cannot create symlinks")
        package = self.package("build-to-review")
        self.assertIsNotNone(package.project_path("alias.txt", "tests"))
        self.assertEqual(package.failures, [])

    def test_utf8_bom_does_not_hide_manifest_fields(self):
        for text in (json.dumps({"schema_version": 2, "evidence": {"tests": "proof.log"}}),
                     "schema_version: 2\nevidence:\n  tests: proof.log\n"):
            manifest = self.root / "manifest.json"
            manifest.write_text("\ufeff" + text, encoding="utf-8")
            self.assertEqual(load_data(manifest), {"schema_version": 2, "evidence": {"tests": "proof.log"}})

    def test_confirmation_ids_exactly_cover_changed_preferences(self):
        diff = {"added": ["a"], "updated": ["u"], "deprecated": ["d"], "revoked": ["r"], "unchanged": ["old"],
                "before_digest": "a" * 64, "after_digest": "b" * 64}
        good = {"actor": "user", "timestamp": "2026-04-19T20:05:00Z", "confirmed_scope": "repository",
                "source_run": "r1", "candidate_ids": ["r", "d", "u", "a"]}
        for ids in (["a"], ["a", "u", "d", "r", "extra"], ["a", "u", "d", "r", "r"], ["old"]):
            with self.subTest(ids=ids):
                package = self.package("taste-review", {"preference_diff": diff})
                package.check_taste_record("confirmation", "confirmation", {**good, "candidate_ids": ids})
                self.assertTrue(any("candidate_ids" in failure for failure in package.failures), package.failures)
        package = self.package("taste-review", {"preference_diff": diff})
        package.check_taste_record("confirmation", "confirmation", good)
        self.assertEqual(package.failures, [])
        unchanged = {**diff, "added": [], "updated": [], "deprecated": [], "revoked": []}
        package = self.package("taste-review", {"preference_diff": unchanged})
        package.check_taste_record("confirmation", "confirmation", {**good, "candidate_ids": []})
        self.assertEqual(package.failures, [])

    def test_shipped_loader_refuses_a_weakened_spec(self):
        for field in ("required_evidence", "artifact_evidence"):
            spec = copy.deepcopy(self.spec)
            spec["boundaries"]["build-to-review"][field].pop()
            path = self.root / "shipped-gates.yaml"
            path.write_text(json.dumps(spec), encoding="utf-8")
            with mock.patch.object(engine, "GATE_SPEC_PATH", path), self.assertRaisesRegex(engine.Engine, "safety floor"):
                engine.load_gate_spec(path)

    def test_security_seed_assesses_both_boundary_and_no_boundary_cases(self):
        good = {"applicable": False, "scope": "local design", "decided_by": "security-builder",
                "architecture_revision": "r1", "reason": "no boundary introduced", "boundaries": []}
        for record in (good, {**good, "applicable": True, "boundaries": [{"id": "input", "control": "validate"}]}):
            package = self.package("design-to-build", {"security_seed": record})
            package.check_evidence()
            self.assertFalse(any("security_seed" in failure for failure in package.failures), package.failures)
        for record in ("n/a", True, {**good, "architecture_revision": None}, {**good, "applicable": True},
                       {**good, "applicable": False, "boundaries": [{"id": "input", "control": "validate"}]},
                       {**good, "applicable": True, "boundaries": [{"id": "input", "control": None}]}):
            package = self.package("design-to-build", {"security_seed": record})
            package.check_evidence()
            self.assertTrue(any("security_seed" in failure for failure in package.failures), package.failures)

    def test_human_go_is_typed_and_bound_to_the_delivery_revision(self):
        good = {"decision": "go", "approver": "release owner", "approval_reference": "GO-1",
                "revision": "r1", "decided_at": "2026-04-19T20:05:00Z"}
        package = self.package("deploy-readiness", {"approved_delivery": "r1"})
        package.check_typed("human_go_required", "human_go", good)
        self.assertEqual(package.failures, [])
        for record in (True, "CI passed", {**good, "decision": "no-go"}, {**good, "revision": "r0"},
                       {**good, "approval_reference": None}, {**good, "decided_at": "yesterday"},
                       {**good, "decided_at": "2026-04-19T20:05:00"}):
            package = self.package("deploy-readiness", {"approved_delivery": "r1"})
            package.check_typed("human_go_required", "human_go", record)
            self.assertTrue(package.failures)

    def test_confirmation_scope_and_timestamp_values_are_checked(self):
        good = {"actor": "user", "timestamp": "2026-04-19T20:05:00Z", "confirmed_scope": "repository",
                "source_run": "r1", "candidate_ids": []}
        for record in ({**good, "timestamp": "later"}, {**good, "timestamp": "2026-04-19"},
                       {**good, "confirmed_scope": "anywhere"}, {**good, "confirmed_scope": {}}):
            package = self.package("taste-review")
            package.check_taste_record("confirmation", "confirmation", record)
            self.assertTrue(package.failures)

    def test_nested_persistence_and_render_values_cannot_be_arbitrary_objects(self):
        good = {"requested_destinations": ["project"], "committed_revisions": [1], "hashes": {"profile": "a" * 64},
                "atomicity_status": "committed", "rollback_result": "not-required"}
        package = self.package("taste-review")
        package.check_taste_record("persistence_result", "persistence_result", good)
        self.assertEqual(package.failures, [])
        for record in ({**good, "requested_destinations": [{}]}, {**good, "committed_revisions": [-1]},
                       {**good, "committed_revisions": [False]}, {**good, "atomicity_status": "failed"},
                       {**good, "atomicity_status": {}}):
            package = self.package("taste-review")
            package.check_taste_record("persistence_result", "persistence_result", record)
            self.assertTrue(package.failures)
        for field in ("breakpoints", "themes"):
            package = self.package("review-to-delivery")
            record = {"artifacts": ["capture.png"], "breakpoints": [360, 1280], "themes": ["light"],
                      "inputs": [{"path": "source.txt", "sha256": "a" * 64}], "result": {"status": "pass"}}
            record[field] = [{}]
            package.check_result_record("rendered_verification", "render", record)
            self.assertTrue(any("invalid nested values" in failure for failure in package.failures))

    def test_wrapper_filenames_do_not_launder_research_or_cso_as_other_lenses(self):
        skills = Path(__file__).resolve().parents[2]
        slots = {}
        for name, path in (("design", skills / "design/gatekeeper-design/scripts/check.py"),
                           ("review", skills / "review/gatekeeper-code/scripts/check.py")):
            spec = importlib.util.spec_from_file_location("quality_wrapper_" + name, path)
            wrapper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wrapper)
            slots[name] = {slot.key: slot for slot in wrapper.MANIFEST.artifacts}
        import _gatecheck as gc
        brief = Path("requirements-brief.md")
        self.assertTrue(gc._named(brief, slots["design"]["research"].patterns))
        self.assertFalse(gc._named(brief, slots["design"]["ui_handoff"].patterns))
        cso = Path("security-review-package.md")
        self.assertTrue(gc._named(cso, slots["review"]["lens_cso"].patterns))
        self.assertFalse(gc._named(cso, slots["review"]["lens_security"].patterns))
        self.assertTrue(gc._named(Path("deliverable_security-review.md"), slots["review"]["lens_security"].patterns))
