#!/usr/bin/env python3
"""Regression tests for the Supreme Team boundary validator and gate spec.

Flat-package contract: a manifest outside the canonical save layout, where the
evidence root is the manifest's own directory. Run-layout behaviour (sibling
evidence, typed records, verdict reuse) lives in test_gate_run_layout.py.
"""
from __future__ import annotations
import hashlib, json, re, subprocess, sys, tempfile, unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"
GATE_SPEC = SKILLS / "gates.yaml"
GATE_DOC = SKILLS.parent / "docs" / "gatekeepers.md"

ARTIFACT = "evidence.md"


def load_spec():
    return json.loads(GATE_SPEC.read_text(encoding="utf-8"))


class BoundaryManifestTests(unittest.TestCase):
    def run_check(self, boundary, package, artifact="# Evidence\nObserved.\n", prior=None,
                  corrupt_hash=False, gates=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name); art = root / ARTIFACT; art.write_text(artifact, encoding="utf-8")
        package.setdefault("artifact_hashes", {})[art.name] = (
            "0" * 64 if corrupt_hash else hashlib.sha256(art.read_bytes()).hexdigest()
        )
        manifest = root / "package.json"; manifest.write_text(json.dumps(package), encoding="utf-8")
        cmd = [sys.executable, str(CHECK), "--boundary", boundary, "--package", str(manifest)]
        if prior:
            prior_path = root / "prior.json"; prior_path.write_text(json.dumps(prior), encoding="utf-8")
            cmd += ["--prior", str(prior_path)]
        if gates:
            cmd += ["--gates", gates]
        return subprocess.run(cmd, text=True, capture_output=True, check=False)

    def package(self, boundary, overrides=None):
        """Build a passing package for a boundary straight from the gate spec:
        artifact-backed keys point at the hashed evidence artifact, everything
        else is a truthy inline claim."""
        spec = load_spec()["boundaries"][boundary]
        artifact_keys = set(spec.get("artifact_evidence", []))
        evidence = {}
        for key in spec["required_evidence"]:
            evidence[key] = ARTIFACT if key in artifact_keys else True
        if overrides:
            evidence.update(overrides)
        evidence = {k: v for k, v in evidence.items() if v is not None}
        return {"submission_id": "s1", "revision": "r1", "revisions": ["r1"],
                "verdict_revision": "r1", "evidence": evidence}

    def assert_passes(self, boundary, package=None):
        r = self.run_check(boundary, package or self.package(boundary))
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)
        self.assertTrue(json.loads(r.stdout)["pass"])

    def assert_missing(self, boundary, key):
        r = self.run_check(boundary, self.package(boundary, {key: None}))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn(f"missing evidence: {key}", json.loads(r.stdout)["failures"])

    # --- positive coverage: every boundary in the spec passes a complete package
    def test_every_boundary_passes_a_complete_package(self):
        for boundary in load_spec()["boundaries"]:
            with self.subTest(boundary=boundary):
                self.assert_passes(boundary)

    # --- every sanctioned fallback is accepted at the boundary that declares it
    def test_every_sanctioned_fallback_is_accepted(self):
        spec = load_spec()
        for boundary, contract in spec["boundaries"].items():
            required = set(contract["required_evidence"])
            for key, values in spec["fallback_values"].items():
                if key not in required:
                    continue
                for value in values:
                    with self.subTest(boundary=boundary, key=key):
                        self.assert_passes(boundary, self.package(boundary, {key: value}))

    # --- missing-evidence coverage, one required key per boundary
    def test_missing_required_evidence_fails(self):
        for boundary, key in (
            ("design-to-build", "ui_evidence"),
            ("design-to-build", "stack_lock"),
            ("build-to-review", "security_evidence"),
            ("review-to-delivery", "rendered_verification"),
            ("security-review", "threat_model"),
            ("investigation-review", "evidence_chain"),
            ("qa-review", "test_matrix"),
            ("skill-maker-to-delivery", "link_report"),
            ("deploy-readiness", "rollback_plan"),
        ):
            with self.subTest(boundary=boundary, key=key):
                self.assert_missing(boundary, key)

    # --- artifact-backed evidence
    def test_bare_string_evidence_is_not_artifact_backed(self):
        r = self.run_check("review-to-delivery",
                           self.package("review-to-delivery", {"rendered_verification": "looked fine"}))
        self.assertEqual(r.returncode, 1)
        self.assertIn("evidence not artifact-backed: rendered_verification",
                      json.loads(r.stdout)["failures"])

    def test_true_valued_artifact_key_is_not_artifact_backed(self):
        r = self.run_check("investigation-review",
                           self.package("investigation-review", {"reproduction": True}))
        self.assertEqual(r.returncode, 1)
        self.assertIn("evidence not artifact-backed: reproduction", json.loads(r.stdout)["failures"])

    def test_artifact_list_value_is_accepted(self):
        p = self.package("review-to-delivery",
                         {"rendered_verification": [ARTIFACT, "desktop, mobile, both themes"]})
        self.assert_passes("review-to-delivery", p)

    def test_schema_2_rejects_bare_fallback_and_unsanctioned_waiver(self):
        spec = load_spec()
        sanctioned = spec["fallback_values"]["security_evidence"][0]
        p = self.package("build-to-review", {"security_evidence": sanctioned})
        p.update({"schema_version": 2, "boundary": "build-to-review", "owner": "build-management"})
        r = self.run_check("build-to-review", p)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("bare fallback string not accepted at schema 2" in f
                            for f in json.loads(r.stdout)["failures"]))
        p["evidence"]["security_evidence"] = {
            "applicable": False, "reason": "no trust boundary touched",
            "scope": "docs only", "decided_by": "security-builder"}
        p["evidence"]["tests"] = {"artifacts": [ARTIFACT], "result": {"status": "pass"}}
        p["evidence"]["runtime"] = {"artifacts": [ARTIFACT], "result": {"status": "pass"}}
        p["evidence"]["approved_design_revision"] = "r0"
        r = self.run_check("build-to-review", p)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_non_waivable_key_rejects_an_applicability_record(self):
        p = self.package("build-to-review", {
            "implementation": {"applicable": False, "reason": "x", "scope": "y", "decided_by": "z"}})
        r = self.run_check("build-to-review", p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("evidence not waivable: implementation", json.loads(r.stdout)["failures"])

    # --- lineage, hashes, scanning
    def test_mixed_and_stale_revision_fail(self):
        p = self.package("review-to-delivery")
        p["revisions"] = ["r1", "r2"]; p["verdict_revision"] = "r0"
        r = self.run_check("review-to-delivery", p); out = json.loads(r.stdout)
        self.assertEqual(r.returncode, 1); self.assertTrue(out["mixed_revisions"])
        self.assertIn("stale verdict revision", out["failures"])

    def test_hash_mismatch_blocked_phrase_and_broken_link_fail(self):
        r = self.run_check("design-to-build", self.package("design-to-build"),
                           "# Evidence\nTODO trust me [missing](gone.md)\n")
        out = json.loads(r.stdout); self.assertEqual(r.returncode, 1)
        self.assertTrue(any("blocked phrase" in f for f in out["failures"]))
        self.assertTrue(any("broken link" in f for f in out["failures"]))
        mismatch = self.run_check("design-to-build", self.package("design-to-build"), corrupt_hash=True)
        self.assertIn("artifact hash mismatch", " ".join(json.loads(mismatch.stdout)["failures"]))

    def test_hash_mismatched_artifact_is_still_scanned(self):
        r = self.run_check("design-to-build", self.package("design-to-build"),
                           "# Evidence\nTODO pending\n", corrupt_hash=True)
        out = json.loads(r.stdout); self.assertEqual(r.returncode, 1)
        self.assertTrue(any("artifact hash mismatch" in f for f in out["failures"]))
        self.assertTrue(any("blocked phrase" in f for f in out["failures"]))

    def test_unchanged_revision_drift_fails(self):
        prior = self.package("design-to-build"); prior["artifact_hashes"] = {ARTIFACT: "different"}
        r = self.run_check("design-to-build", self.package("design-to-build"), prior=prior)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(json.loads(r.stdout)["idempotency_drift"])

    def test_empty_revisions_fails(self):
        p = self.package("design-to-build"); p["revisions"] = []
        r = self.run_check("design-to-build", p)
        out = json.loads(r.stdout); self.assertEqual(r.returncode, 1)
        self.assertIn("revisions must contain exactly one value", out["failures"])

    def test_submitter_mismatch_is_rejected(self):
        p = self.package("design-to-build"); p["owner"] = "build-management"
        r = self.run_check("design-to-build", p)
        self.assertEqual(r.returncode, 1)
        self.assertTrue(any("submitter mismatch" in f for f in json.loads(r.stdout)["failures"]))

    # --- engine errors
    def test_unknown_boundary_exits_two_with_engine_error_json(self):
        r = self.run_check("no-such-boundary", self.package("design-to-build"))
        self.assertEqual(r.returncode, 2, r.stdout)
        err = json.loads(r.stderr)
        self.assertEqual(err["boundary"], "no-such-boundary")
        self.assertIn("unknown boundary", err["engine_error"])

    def test_missing_gate_spec_exits_two(self):
        r = self.run_check("design-to-build", self.package("design-to-build"),
                           gates=str(SKILLS / "no-such-gates.yaml"))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("engine_error", json.loads(r.stderr))


class GateSpecContractTests(unittest.TestCase):
    def test_gate_spec_shape(self):
        spec = load_spec()
        self.assertEqual(spec["schema_version"], 1)
        self.assertEqual(spec["kind"], "supremeteam-gate-spec")
        self.assertEqual(spec["verdicts"], ["APPROVED", "REVISE", "ESCALATE"])
        for name, boundary in spec["boundaries"].items():
            with self.subTest(boundary=name):
                self.assertTrue(boundary["required_evidence"])
                self.assertTrue(boundary.get("submitter"))
                self.assertTrue(boundary.get("guards"))
                artifact_keys = set(boundary.get("artifact_evidence", []))
                self.assertLessEqual(artifact_keys, set(boundary["required_evidence"]))
        for key, values in spec.get("fallback_values", {}).items():
            self.assertTrue(values, key)

    def test_every_typed_key_and_fallback_belongs_to_a_boundary(self):
        spec = load_spec()
        declared = {key for b in spec["boundaries"].values() for key in b["required_evidence"]}
        self.assertLessEqual(set(spec["evidence_types"]), declared)
        self.assertLessEqual(set(spec["fallback_values"]), declared)

    def test_documented_boundary_table_matches_gate_spec(self):
        """The human-readable table in docs/gatekeepers.md must not drift from gates.yaml."""
        spec = load_spec()["boundaries"]
        text = GATE_DOC.read_text(encoding="utf-8")
        table = {}
        for line in text.splitlines():
            match = re.match(r"^\|\s*`?([a-z][a-z-]+)`?\s*\|(.+)\|\s*$", line)
            if not match:
                continue
            name = match.group(1)
            if name not in spec:
                continue
            table[name] = set(re.findall(r"`([a-z_]+)`", match.group(2)))
        self.assertEqual(set(table), set(spec), "docs/gatekeepers.md boundaries differ from gates.yaml")
        for name, boundary in spec.items():
            with self.subTest(boundary=name):
                self.assertEqual(table[name], set(boundary["required_evidence"]),
                                 f"docs/gatekeepers.md evidence keys for {name} differ from gates.yaml")


if __name__ == "__main__": unittest.main()
