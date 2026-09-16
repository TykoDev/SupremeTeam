#!/usr/bin/env python3
"""Batched-REVISE mechanics and the redesign-review contract.

Covers the variant_set record, keys that accept no fallback, per-key evidence
digests with changed/unchanged reporting against a prior verdict, and the
owner-grouped revise packet (gates.yaml revise_policy).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RedesignPackage:
    """A flat schema-2 redesign-review package with four hashed variants."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.hashes: dict[str, str] = {}
        self.proof = self.file("evidence/proof.md", "# Proof\n\nObserved: parity 100%.\n")
        for name in ("inventory/design-inventory.json", "reports/taste-grilling.md", "artifacts/taste-snapshot.json",
                     "reports/design-directions.md", "evidence/render.md"):
            self.file(name, f"# {name}\n\nObserved.\n")
        self.variants = []
        for i in range(1, 5):
            variant = {"id": f"v{i}", "name": f"Variant {i}", "direction": f"direction-{i}"}
            for field, ext in (("spec", "variant.md"), ("tokens", "tokens.css"), ("components", "components.html"), ("app", "app.html")):
                variant[field] = self.file(f"artifacts/variants/v{i}/{ext}", f"/* {ext} v{i} */\n")
            self.variants.append(variant)

    def file(self, rel: str, text: str) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.hashes[rel] = sha256(path)
        return rel

    def manifest(self) -> dict:
        return {
            "schema_version": 2, "boundary": "redesign-review", "owner": "redesign",
            "submission_id": "redesign-1", "revision": "r1", "revisions": ["r1"],
            "evidence": {
                "design_inventory": "inventory/design-inventory.json",
                "taste_grilling": "reports/taste-grilling.md",
                "taste_snapshot": "artifacts/taste-snapshot.json",
                "design_directions": "reports/design-directions.md",
                "variant_set": {"artifacts": [v["spec"] for v in self.variants], "variants": self.variants, "count": 4},
                "parity_evidence": {"artifacts": ["evidence/proof.md"], "result": {"status": "pass"},
                                    "inputs": [{"path": "inventory/design-inventory.json", "sha256": self.hashes["inventory/design-inventory.json"]}]},
                "rendered_verification": {"artifacts": ["evidence/render.md"], "breakpoints": ["320", "1440"], "themes": ["light", "dark"],
                                          "inputs": [{"path": "artifacts/variants/v1/app.html", "sha256": self.hashes["artifacts/variants/v1/app.html"]}],
                                          "result": {"status": "pass"}},
                "accessibility_evidence": {"items": [{"id": "a11y-1", "severity": "Minor", "status": "open"}]},
                "recommendation": "v2, because it satisfies the density and typography preferences within the contrast floor",
                "residual_risk": "none observed",
            },
            "artifact_hashes": dict(self.hashes),
        }

    def write(self, data: dict, name: str = "manifest.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path


def run(manifest: Path, *extra: str, boundary: str = "redesign-review") -> tuple[subprocess.CompletedProcess, dict]:
    proc = subprocess.run([sys.executable, str(CHECK), "--boundary", boundary, "--package", str(manifest), *extra],
                          text=True, capture_output=True, check=False)
    return proc, (json.loads(proc.stdout) if proc.stdout.strip() else {"engine": proc.stderr})


class VariantSetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pkg = RedesignPackage(Path(tmp.name).resolve())

    def test_complete_redesign_package_passes(self):
        proc, out = run(self.pkg.write(self.pkg.manifest()))
        self.assertEqual(proc.returncode, 0, out)
        self.assertTrue(out["pass"])
        self.assertEqual(out["revise_packet"]["by_owner"], {})
        self.assertIn("variant_set", out["evidence_digests"])

    def test_three_variants_duplicate_ids_and_unhashed_files_fail(self):
        data = self.pkg.manifest()
        data["evidence"]["variant_set"]["variants"] = data["evidence"]["variant_set"]["variants"][:3]
        data["evidence"]["variant_set"]["count"] = 3
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("requires exactly 4 variants, found 3" in f for f in out["failures"]), out["failures"])
        data = self.pkg.manifest()
        data["evidence"]["variant_set"]["variants"][1]["id"] = "v1"
        data["evidence"]["variant_set"]["variants"][2]["app"] = "artifacts/variants/v3/missing.html"
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("duplicate id v1" in f for f in out["failures"]), out["failures"])
        self.assertTrue(any("app is not a hashed artifact" in f for f in out["failures"]), out["failures"])

    def test_rendered_verification_accepts_no_fallback_at_redesign_review(self):
        data = self.pkg.manifest()
        data["evidence"]["rendered_verification"] = {"applicable": False, "reason": "no visible surface changed - rendered verification not applicable",
                                                     "scope": "whole run", "decided_by": "redesign"}
        _, out = run(self.pkg.write(data))
        self.assertIn("evidence not waivable: rendered_verification", out["failures"])
        data["evidence"]["rendered_verification"] = "no visible surface changed - rendered verification not applicable"
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("rendered_verification" in f for f in out["failures"]), out["failures"])
        self.assertFalse(out["pass"])
        # The same fallback still works where the spec allows it.
        data["evidence"]["taste_snapshot"] = {"applicable": False, "reason": "no saved Taste profile available", "scope": "whole run", "decided_by": "taste"}
        data["evidence"]["rendered_verification"] = self.pkg.manifest()["evidence"]["rendered_verification"]
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 0, out)


class RevisePacketTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pkg = RedesignPackage(Path(tmp.name).resolve())

    def test_failures_are_grouped_by_owner_and_key(self):
        data = self.pkg.manifest()
        data["evidence"].pop("design_inventory")                       # design-mapper
        data["evidence"]["variant_set"]["variants"][0]["tokens"] = ""  # prototyper
        data["evidence"]["accessibility_evidence"] = {"items": [{"id": "a", "severity": "Critical", "status": "open"}]}  # frontier
        data["artifact_hashes"]["evidence/proof.md"] = "0" * 64        # submitter (hash mismatch)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 1)
        packet = out["revise_packet"]
        self.assertIn("missing evidence: design_inventory", packet["by_owner"]["design-mapper"])
        self.assertTrue(any("variant_set.variants[0] requires tokens" in f for f in packet["by_owner"]["prototyper"]))
        self.assertTrue(any("accessibility_evidence[0]" in f for f in packet["by_owner"]["frontier"]))
        self.assertTrue(any("artifact hash mismatch" in f for f in packet["by_owner"]["redesign"]))
        self.assertEqual(set(packet["by_key"]) & {"design_inventory", "variant_set", "accessibility_evidence"},
                         {"design_inventory", "variant_set", "accessibility_evidence"})
        self.assertTrue(any("artifact hash mismatch" in f for f in packet["unassigned"]))

    def test_prior_verdict_reports_changed_and_unchanged_keys(self):
        first = self.pkg.write(self.pkg.manifest())
        proc, out = run(first, "--verdict-out", str(self.pkg.root / "verdict.json"))
        self.assertEqual(proc.returncode, 0, out)
        self.assertIsNone(out["changed_evidence"])
        data = self.pkg.manifest()
        # A resubmission is a new revision; reusing r1 with different content is idempotency drift.
        data.update({"submission_id": "redesign-2", "revision": "r2", "revisions": ["r2"]})
        data["evidence"]["recommendation"] = "v3, after the user chose density over typography"
        self.pkg.file("artifacts/variants/v2/app.html", "/* app.html v2 revised */\n")
        data["artifact_hashes"] = dict(self.pkg.hashes)
        second = self.pkg.write(data, "manifest-2.json")
        proc, out = run(second, "--prior", str(self.pkg.root / "verdict.json"))
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(out["changed_evidence"], ["recommendation", "variant_set"])
        self.assertIn("design_inventory", out["unchanged_evidence"])
        self.assertIn("parity_evidence", out["unchanged_evidence"])
        self.assertFalse(out["prior_reusable"])

    def test_gate_spec_declares_owner_for_every_required_key(self):
        spec = json.loads((SKILLS / "gates.yaml").read_text(encoding="utf-8"))
        for name, boundary in spec["boundaries"].items():
            with self.subTest(boundary=name):
                self.assertEqual(set(spec["evidence_owners"][name]), set(boundary["required_evidence"]))
        self.assertEqual(spec["revise_policy"]["cycle_cap"], 2)
        self.assertEqual(spec["evidence_type_params"]["variant_set"]["required_count"], 4)


if __name__ == "__main__":
    unittest.main()
