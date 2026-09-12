#!/usr/bin/env python3
"""Run-layout regression tests for the boundary validator.

Every case here reproduced a defect against the pre-remediation checker:
same-run sibling evidence was rejected, revision/owner/boundary facts were not
enforced, result-bearing evidence was accepted by hash alone, a YAML comment in
the spec was an engine error, and quoted diagnostic markers were blocked.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"
GATE_SPEC = SKILLS / "gates.yaml"
sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import load_data  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def registry_entry() -> dict:
    return load_data(SKILLS / "tech-stacks" / "registry.yaml")["overlays"][0]


class RunLayoutFixture:
    """A canonical skillset-saves run with an intake grilling log."""

    def __init__(self, root: Path, run_id: str = "run-a", owner: str = "admiral"):
        self.project = root
        self.run_id = run_id
        self.run_dir = root / "skillset-saves" / "runs" / run_id
        (self.run_dir / "intake").mkdir(parents=True)
        (self.run_dir / "_state.md").write_text(json.dumps({
            "schema_version": 1, "run_id": run_id, "status": "active", "session_pin": True, "revision": 1,
            "active_owner": owner, "evidence_paths": [f"skillset-saves/runs/{run_id}/intake/report_grilling.md"],
            "timestamp": "2026-09-05T00:00:00+00:00"}), encoding="utf-8")
        self.grilling = self.run_dir / "intake" / "report_grilling.md"
        self.grilling.write_text("# Grilling\n\nResolved: ship it. Rejected: nothing.\n", encoding="utf-8")

    def phase(self, name: str) -> Path:
        directory = self.run_dir / name
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def write_manifest(self, phase: str, data: dict, name: str = "manifest.json") -> Path:
        path = self.phase(phase) / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def proof(self, phase: str, name: str = "proof.md", text: str = "# Proof\n\nObserved: probe executed, denied as expected.\n") -> Path:
        path = self.phase(phase) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


def run_cli(boundary: str, manifest: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(CHECK), "--boundary", boundary, "--package", str(manifest), *extra]
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def result(proc: subprocess.CompletedProcess) -> dict:
    return json.loads(proc.stdout) if proc.stdout.strip() else {"engine": proc.stderr}


class EvidenceRootTests(unittest.TestCase):
    """F1: same-run sibling evidence is admissible; escapes and other runs are not."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.fx = RunLayoutFixture(self.root)

    def design_manifest(self, decisions: str = "../intake/report_grilling.md", **overrides) -> dict:
        architecture = self.fx.proof("design", "reports/architecture.md", "# Architecture\n\nHexagonal service.\n")
        plan = self.fx.proof("design", "reports/plan.md", "# Plan\n\nThree increments.\n")
        data = {
            "schema_version": 2, "run_id": self.fx.run_id, "boundary": "design-to-build", "owner": "commander",
            "submission_id": "design-1", "revision": "r1", "revisions": ["r1"],
            "evidence": {
                "decisions": decisions, "architecture": "reports/architecture.md", "interfaces": "REST",
                "plan": "reports/plan.md", "acceptance": "smoke + contract tests",
                "security_seed": "no external trust boundary",
                "stack_lock": {"applicable": False, "reason": "no new runtime", "scope": "whole run", "decided_by": "commander"},
                "taste_snapshot": {"applicable": False, "reason": "no saved Taste profile available", "scope": "whole run", "decided_by": "commander"},
                "ui_evidence": {"applicable": False, "reason": "no user-facing surface", "scope": "whole run", "decided_by": "architect"},
            },
            "artifact_hashes": {"../intake/report_grilling.md": sha256(self.fx.grilling),
                                "reports/architecture.md": sha256(architecture), "reports/plan.md": sha256(plan)},
        }
        data.update(overrides)
        return data

    def test_same_run_sibling_evidence_passes(self):
        proc = run_cli("design-to-build", self.fx.write_manifest("design", self.design_manifest()))
        out = result(proc)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(out["evidence_root_kind"], "run")
        self.assertTrue(out["pass"])

    def test_legacy_v1_manifest_in_run_layout_also_accepts_sibling_evidence(self):
        data = self.design_manifest()
        for key in ("schema_version", "boundary", "owner"):
            data.pop(key)
        data["evidence"]["stack_lock"] = "no new runtime or framework - existing stack unchanged"
        data["evidence"]["taste_snapshot"] = "no saved Taste profile available"
        data["evidence"]["ui_evidence"] = "no user-facing surface - design system not engaged"
        proc = run_cli("design-to-build", self.fx.write_manifest("design", data))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(result(proc)["manifest_schema_version"], 1)

    def test_other_run_evidence_is_rejected(self):
        other = RunLayoutFixture(self.root, run_id="run-b")
        data = self.design_manifest(decisions="../../run-b/intake/report_grilling.md")
        data["artifact_hashes"].pop("../intake/report_grilling.md")
        data["artifact_hashes"]["../../run-b/intake/report_grilling.md"] = sha256(other.grilling)
        proc = run_cli("design-to-build", self.fx.write_manifest("design", data))
        out = result(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("references another run" in f for f in out["failures"]), out["failures"])

    def test_traversal_absolute_and_unc_paths_are_rejected(self):
        outside = self.root / "outside.md"
        outside.write_text("# outside\n", encoding="utf-8")
        for bad in ("../../../../outside.md", str(outside), "//server/share/x.md", "C:/x/outside.md"):
            with self.subTest(path=bad):
                data = self.design_manifest()
                data["artifact_hashes"][bad] = sha256(outside)
                proc = run_cli("design-to-build", self.fx.write_manifest("design", data))
                out = result(proc)
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertTrue(any("escapes" in f for f in out["failures"]), out["failures"])

    def test_run_id_mismatch_shrinks_root_to_package(self):
        proc = run_cli("design-to-build", self.fx.write_manifest("design", self.design_manifest(run_id="run-z")))
        out = result(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out["evidence_root_kind"], "package")
        self.assertTrue(any("run_id does not match" in f for f in out["failures"]))
        self.assertTrue(any("escapes package" in f for f in out["failures"]))

    def test_symlink_escape_is_rejected(self):
        outside = self.root / "secret.md"
        outside.write_text("# secret\n", encoding="utf-8")
        link = self.fx.phase("design") / "linked.md"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(f"cannot create symlink here: {exc}")
        data = self.design_manifest()
        data["artifact_hashes"]["linked.md"] = sha256(outside)
        proc = run_cli("design-to-build", self.fx.write_manifest("design", data))
        out = result(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("via link" in f for f in out["failures"]), out["failures"])

    def test_junction_escape_is_rejected_on_windows(self):
        if os.name != "nt":
            self.skipTest("junctions are Windows-only")
        outside_dir = self.root / "outside-dir"
        outside_dir.mkdir()
        (outside_dir / "x.md").write_text("# x\n", encoding="utf-8")
        junction = self.fx.phase("design") / "jn"
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside_dir)], text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            self.skipTest(f"cannot create junction: {proc.stderr or proc.stdout}")
        data = self.design_manifest()
        data["artifact_hashes"]["jn/x.md"] = sha256(outside_dir / "x.md")
        out = result(run_cli("design-to-build", self.fx.write_manifest("design", data)))
        self.assertTrue(any("via link" in f for f in out["failures"]), out["failures"])


class IdentityAndTypedEvidenceTests(unittest.TestCase):
    """F2/F7: lineage, submitter, typed result records, finding policy, waivers, parsing."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.fx = RunLayoutFixture(self.root)

    def review_manifest(self, **overrides) -> dict:
        proof = self.fx.proof("review")
        data = {
            "schema_version": 2, "run_id": self.fx.run_id, "boundary": "review-to-delivery", "owner": "code-chief",
            "submission_id": "review-1", "revision": "r1", "revisions": ["r1"],
            "evidence": {
                "review_verdict": "APPROVED", "findings": {"items": []},
                "executed_probes": {"artifacts": ["proof.md"], "result": {"status": "pass"}},
                "rendered_verification": {"applicable": False, "reason": "no visible surface changed",
                                          "scope": "api only", "decided_by": "design-qa"},
                "residual_risk": "none", "revision_lineage": "r1 <- design r1",
            },
            "artifact_hashes": {"proof.md": sha256(proof)},
        }
        data.update(overrides)
        return data

    def check(self, data: dict, boundary: str = "review-to-delivery", phase: str = "review", *extra: str):
        proc = run_cli(boundary, self.fx.write_manifest(phase, data), *extra)
        return proc, result(proc)

    def test_v2_review_package_passes(self):
        proc, _ = self.check(self.review_manifest())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_revision_must_equal_lineage_value(self):
        proc, out = self.check(self.review_manifest(revision="r2"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("revision not in revisions lineage", out["failures"])

    def test_wrong_owner_and_boundary_are_rejected(self):
        _, out = self.check(self.review_manifest(owner="bob-the-builder"))
        self.assertTrue(any("submitter mismatch" in f for f in out["failures"]))
        _, out = self.check(self.review_manifest(boundary="build-to-review"))
        self.assertTrue(any("boundary mismatch" in f for f in out["failures"]))

    def test_v2_requires_boundary_and_owner(self):
        data = self.review_manifest()
        data.pop("boundary")
        data.pop("owner")
        _, out = self.check(data)
        self.assertIn("missing boundary (required at schema 2)", out["failures"])
        self.assertIn("missing owner (required at schema 2)", out["failures"])

    def test_revise_recommendation_needs_challenge_record(self):
        data = self.review_manifest()
        data["evidence"]["review_verdict"] = "REVISE"
        _, out = self.check(data)
        self.assertTrue(any("without a challenge record" in f for f in out["failures"]))
        data["evidence"]["review_verdict"] = {"recommendation": "REVISE", "challenge": {"by": "code-chief", "reason": "finding disputed with evidence"}}
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 0, out)

    def test_open_major_and_critical_block_but_owner_deferral_passes(self):
        data = self.review_manifest()
        data["evidence"]["findings"] = {"items": [{"id": "F1", "severity": "Major", "status": "open"}]}
        _, out = self.check(data)
        self.assertTrue(any("unresolved Major" in f for f in out["failures"]))
        data["evidence"]["findings"] = {"items": [{"id": "F1", "severity": "Critical", "status": "resolved"}]}
        _, out = self.check(data)
        self.assertTrue(any("open Critical" in f for f in out["failures"]))
        data["evidence"]["findings"] = {"items": [
            {"id": "F1", "severity": "Major", "status": "deferred", "owner": "build-management", "reopen_trigger": "before release"},
            {"id": "F2", "severity": "Critical", "status": "verified"},
            {"id": "F3", "severity": "Minor", "status": "open"},
        ]}
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 0, out)

    def test_failed_probe_result_and_missing_second_reference_fail(self):
        data = self.review_manifest()
        data["evidence"]["executed_probes"] = {"artifacts": ["proof.md"], "result": {"status": "fail"}}
        _, out = self.check(data)
        self.assertTrue(any("result not passing: fail" in f for f in out["failures"]))
        data["evidence"]["executed_probes"] = {"artifacts": ["proof.md", "missing.md"], "result": {"status": "pass"}}
        _, out = self.check(data)
        self.assertTrue(any("unhashed path: executed_probes -> missing.md" in f for f in out["failures"]))

    def test_v1_list_with_unhashed_second_path_fails_but_annotation_is_fine(self):
        proof = self.fx.proof("review")
        data = {
            "submission_id": "rv", "revision": "r1", "revisions": ["r1"],
            "evidence": {"review_verdict": "APPROVED", "findings": True, "executed_probes": "proof.md",
                         "rendered_verification": ["proof.md", "missing-capture.png"],
                         "residual_risk": "none", "revision_lineage": "r1"},
            "artifact_hashes": {"proof.md": sha256(proof)},
        }
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("unhashed path: rendered_verification -> missing-capture.png" in f for f in out["failures"]))
        data["evidence"]["rendered_verification"] = ["proof.md", "desktop, mobile, both themes"]
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 0, out)

    def test_v2_render_record_requires_captures_inputs_and_status(self):
        surface = self.root / "app" / "index.html"
        surface.parent.mkdir()
        surface.write_text("<main>hi</main>", encoding="utf-8")
        capture = self.fx.proof("review", "capture-desktop-light.png", "png-bytes")
        probes = self.fx.proof("review", "probes.md", "# Probes\n\nExecuted, all pass.\n")

        def manifest(render):
            return {
                "schema_version": 2, "run_id": self.fx.run_id, "boundary": "review-to-delivery", "owner": "code-chief",
                "submission_id": "rv-1", "revision": "r1", "revisions": ["r1"],
                "evidence": {
                    "review_verdict": "APPROVED", "findings": {"items": []},
                    "executed_probes": {"artifacts": ["probes.md"], "result": {"status": "pass"}},
                    "rendered_verification": render,
                    "residual_risk": "none", "revision_lineage": "r1 <- build r1",
                },
                "artifact_hashes": {"capture-desktop-light.png": sha256(capture), "probes.md": sha256(probes)},
            }

        _, out = self.check(manifest("probes.md"))
        self.assertTrue(any("must be a typed render record" in f for f in out["failures"]), out["failures"])
        good = manifest({"captures": ["capture-desktop-light.png"], "breakpoints": ["375", "1280"], "themes": ["light", "dark"],
                         "result": {"status": "pass"}, "inputs": [{"path": "app/index.html", "sha256": sha256(surface)}]})
        proc, out = self.check(good)
        self.assertEqual(proc.returncode, 0, out)
        surface.write_text("<main>changed</main>", encoding="utf-8")
        _, out = self.check(good)
        self.assertTrue(any("input hash drift" in f for f in out["failures"]), out["failures"])
        failed = manifest({"captures": ["capture-desktop-light.png"], "breakpoints": ["1280"], "themes": ["light"],
                           "result": {"status": "fail"}, "inputs": []})
        _, out = self.check(failed)
        self.assertTrue(any("result not passing" in f for f in out["failures"]))

    def test_arbitrary_waiver_fails_and_applicability_record_passes(self):
        proof = self.fx.proof("build")
        base = {
            "schema_version": 2, "run_id": self.fx.run_id, "boundary": "build-to-review", "owner": "build-management",
            "submission_id": "b1", "revision": "r1", "revisions": ["r1"],
            "evidence": {"approved_design_revision": "r1", "implementation": "src changed",
                         "tests": {"artifacts": ["proof.md"], "result": {"status": "pass"}},
                         "runtime": {"artifacts": ["proof.md"], "result": {"status": "pass"}},
                         "traceability": "plan->impl", "security_evidence": "we looked, it is fine"},
            "artifact_hashes": {"proof.md": sha256(proof)},
        }
        _, out = self.check(base, "build-to-review", "build")
        self.assertTrue(any("security_evidence must be a findings record" in f for f in out["failures"]), out["failures"])
        bare = json.loads(json.dumps(base))
        bare["evidence"]["tests"] = "42 passed"
        bare["evidence"]["runtime"] = "started"
        _, out = self.check(bare, "build-to-review", "build")
        self.assertTrue(any("tests must be a typed probe record" in f for f in out["failures"]), out["failures"])
        self.assertIn("evidence not artifact-backed: runtime", out["failures"])
        base["evidence"]["security_evidence"] = "no trust-boundary change - security-builder not engaged"
        _, out = self.check(base, "build-to-review", "build")
        self.assertTrue(any("bare fallback string not accepted at schema 2" in f for f in out["failures"]))
        base["evidence"]["security_evidence"] = {"applicable": False, "reason": "no trust boundary touched", "scope": "src/ui only", "decided_by": "security-builder"}
        proc, out = self.check(base, "build-to-review", "build")
        self.assertEqual(proc.returncode, 0, out)
        base["evidence"]["implementation"] = {"applicable": False, "reason": "x", "scope": "y", "decided_by": "z"}
        _, out = self.check(base, "build-to-review", "build")
        self.assertIn("evidence not waivable: implementation", out["failures"])

    def test_stack_lock_record_is_validated_against_registry(self):
        entry = registry_entry()
        architecture = self.fx.proof("design", "reports/architecture.md", "# Architecture\n\nHexagonal service.\n")
        plan = self.fx.proof("design", "reports/plan.md", "# Plan\n\nThree increments.\n")
        data = {
            "schema_version": 2, "run_id": self.fx.run_id, "boundary": "design-to-build", "owner": "commander",
            "submission_id": "design-2", "revision": "r1", "revisions": ["r1"],
            "evidence": {
                "decisions": "../intake/report_grilling.md", "architecture": "reports/architecture.md",
                "interfaces": "REST", "plan": "reports/plan.md", "acceptance": "smoke + contract tests",
                "security_seed": "no external trust boundary",
                "stack_lock": {"slug": entry["slug"], "versions": entry["versions"], "overlay_sha256": entry["sha256"]},
                "taste_snapshot": {"applicable": False, "reason": "no saved Taste profile available", "scope": "whole run", "decided_by": "commander"},
                "ui_evidence": {"applicable": False, "reason": "no user-facing surface", "scope": "whole run", "decided_by": "architect"},
            },
            "artifact_hashes": {"../intake/report_grilling.md": sha256(self.fx.grilling),
                                "reports/architecture.md": sha256(architecture), "reports/plan.md": sha256(plan)},
        }
        proc, out = self.check(data, "design-to-build", "design")
        self.assertEqual(proc.returncode, 0, out)
        data["evidence"]["stack_lock"]["overlay_sha256"] = "0" * 64
        _, out = self.check(data, "design-to-build", "design")
        self.assertTrue(any("overlay_sha256 does not match" in f for f in out["failures"]))
        data["evidence"]["stack_lock"] = {"slug": "no-such-stack", "versions": ["1"], "overlay_sha256": entry["sha256"]}
        _, out = self.check(data, "design-to-build", "design")
        self.assertTrue(any("slug not in tech-stack registry" in f for f in out["failures"]))

    def test_scan_record_status_gates_security_review(self):
        threat = self.fx.proof("security", "threat.md", "# Threat model\n\nAssets and entry points listed.\n")
        deny = self.fx.proof("security", "deny.md", "# Deny paths\n\nProbe log attached.\n")
        stdout = self.fx.proof("security", "scan.stdout.txt", "0 vulnerabilities\n")
        lock = self.root / "requirements.txt"
        lock.write_text("requests==2.32.0\n", encoding="utf-8")

        def manifest(status: str) -> dict:
            return {
                "schema_version": 2, "run_id": self.fx.run_id, "boundary": "security-review", "owner": "cso",
                "submission_id": "sec-1", "revision": "r1", "revisions": ["r1"],
                "evidence": {
                    "scope": "api", "threat_model": "threat.md", "findings": {"items": []},
                    "vulnerability_scan": {"artifacts": ["scan.stdout.txt"], "tool": "pip-audit", "command": "pip-audit -r requirements.txt",
                                           "exit_code": 0 if status == "pass" else 1, "observed_at": "2026-09-05T00:00:00Z",
                                           "inputs": [{"path": "requirements.txt", "sha256": sha256(lock)}], "result": {"status": status}},
                    "denial_path_evidence": {"artifacts": ["deny.md"], "result": {"status": "pass"}},
                    "remediation_plan": "none needed", "residual_risk": "none",
                },
                "artifact_hashes": {"threat.md": sha256(threat), "deny.md": sha256(deny), "scan.stdout.txt": sha256(stdout)},
            }

        proc, out = self.check(manifest("pass"), "security-review", "security")
        self.assertEqual(proc.returncode, 0, out)
        for status in ("fail", "unavailable", "error", "not-run"):
            with self.subTest(status=status):
                _, out = self.check(manifest(status), "security-review", "security")
                self.assertTrue(any(f"result not passing: {status}" in f for f in out["failures"]), out["failures"])

    def test_yaml_comment_in_spec_parses(self):
        spec_copy = self.root / "gates.yaml"
        spec_copy.write_text("# Supreme Team gate spec (copy)\n" + GATE_SPEC.read_text(encoding="utf-8"), encoding="utf-8")
        proc, _ = self.check(self.review_manifest(), "review-to-delivery", "review", "--gates", str(spec_copy))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_quoted_diagnostic_marker_passes_but_prose_marker_fails(self):
        data = self.review_manifest()
        proof = self.fx.phase("review") / "proof.md"
        proof.write_text("# Audit\n\nWe removed the `TODO` marker from `app.py`.\n\n> original line: TODO fix auth\n\n```\nFIXME leftover in fixture\n```\n", encoding="utf-8")
        data["artifact_hashes"]["proof.md"] = sha256(proof)
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 0, out)
        proof.write_text("# Audit\n\nTODO finish the review.\n", encoding="utf-8")
        data["artifact_hashes"]["proof.md"] = sha256(proof)
        _, out = self.check(data)
        self.assertTrue(any("blocked phrase" in f for f in out["failures"]))

    def test_verdict_record_round_trip_and_spec_binding(self):
        data = self.review_manifest()
        manifest = self.fx.write_manifest("review", data)
        verdict = self.fx.phase("review") / "verdict_review-to-delivery.json"
        proc = run_cli("review-to-delivery", manifest, "--verdict-out", str(verdict))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(verdict.exists())
        out = result(run_cli("review-to-delivery", manifest, "--prior", str(verdict)))
        self.assertTrue(out["prior_reusable"])
        self.assertFalse(out["idempotency_drift"])
        data["evidence"]["residual_risk"] = "changed without a new revision"
        manifest = self.fx.write_manifest("review", data)
        proc = run_cli("review-to-delivery", manifest, "--prior", str(verdict))
        out = result(proc)
        self.assertTrue(out["idempotency_drift"])
        self.assertEqual(proc.returncode, 1)
        spec_copy = self.root / "gates.yaml"
        spec_copy.write_text("# altered\n" + GATE_SPEC.read_text(encoding="utf-8"), encoding="utf-8")
        manifest = self.fx.write_manifest("review", self.review_manifest())
        out = result(run_cli("review-to-delivery", manifest, "--prior", str(verdict), "--gates", str(spec_copy)))
        self.assertFalse(out["prior_reusable"])

    def test_malformed_artifact_map_and_evidence_are_controlled(self):
        data = self.review_manifest(artifact_hashes=["not", "a", "map"])
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing artifact hashes", out["failures"])
        data = self.review_manifest(evidence=["list"])
        proc, out = self.check(data)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("engine_error", json.loads(proc.stderr))


if __name__ == "__main__":
    unittest.main()
