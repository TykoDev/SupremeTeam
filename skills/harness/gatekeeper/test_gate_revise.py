#!/usr/bin/env python3
"""Batched-REVISE mechanics and the mock-first redesign-review contract.

Covers the two variant_set records (four mocks, one built variant), the typed
selection record and the cross-key rule it drives, keys that accept no fallback,
per-key evidence digests with changed/unchanged reporting against a prior
verdict, and the owner-grouped revise packet (gates.yaml revise_policy).
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
sys.path.insert(0, str(SKILLS / "scripts"))
from data_formats import content_sha256  # noqa: E402

DEFERRED = "selection deferred - no variant built"
MERGED = "merge brief recorded - implemented as a fifth direction in the design pipeline"


def sha256(path: Path) -> str:
    return content_sha256(path)


class RedesignPackage:
    """A flat schema-2 redesign-review package: four hashed mocks, one build.

    The shape the mock-first pipeline produces. `m2` is both the recommended and
    the chosen mock, so the selected variant is built for `m2` alone; the other
    three directions are never implemented.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.hashes: dict[str, str] = {}
        self.proof = self.file("evidence/proof.md", "# Proof\n\nObserved: parity 100%.\n")
        for name in ("inventory/design-inventory.json", "reports/taste-grilling.md", "artifacts/taste-snapshot.json",
                     "reports/design-directions.md", "reports/selection.md",
                     "evidence/mock-parity.json", "evidence/mock-render.md", "evidence/render.md"):
            self.file(name, f"# {name}\n\nObserved.\n")
        self.mocks = []
        for i in range(1, 5):
            mock = {"id": f"m{i}", "name": f"Direction {i}", "direction": f"direction-{i}"}
            for field, ext in (("spec", "variant.md"), ("tokens", "tokens.css"),
                               ("components", "components.html"), ("mock", "mock.html")):
                mock[field] = self.file(f"artifacts/mocks/m{i}/{ext}", f"/* {ext} m{i} */\n")
            self.mocks.append(mock)
        self.chosen = "m2"
        self.variants = [{"id": self.chosen, "name": "Direction 2", "direction": "direction-2"}]
        for field, ext in (("spec", "variant.md"), ("tokens", "tokens.css"),
                           ("components", "components.html"), ("app", "app.html")):
            self.variants[0][field] = self.file(f"artifacts/variants/{self.chosen}/{ext}", f"/* {ext} built */\n")

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
                "mock_set": {"artifacts": [m["spec"] for m in self.mocks], "mocks": self.mocks, "count": 4},
                "mock_parity": {"artifacts": ["evidence/mock-parity.json"], "result": {"status": "pass"},
                                "inputs": [{"path": "inventory/design-inventory.json", "sha256": self.hashes["inventory/design-inventory.json"]}]},
                "mock_rendering": {"artifacts": ["evidence/mock-render.md"], "breakpoints": ["320", "1440"],
                                   "themes": ["light", "dark"],
                                   "inputs": [{"path": "artifacts/mocks/m1/mock.html", "sha256": self.hashes["artifacts/mocks/m1/mock.html"]}],
                                   "result": {"status": "pass"}},
                "selection": self.selection(),
                "selected_variant": {"artifacts": [self.variants[0]["spec"]], "variants": self.variants, "count": 1},
                "parity_evidence": {"artifacts": ["evidence/proof.md"], "result": {"status": "pass"},
                                    "inputs": [{"path": "inventory/design-inventory.json", "sha256": self.hashes["inventory/design-inventory.json"]}]},
                "rendered_verification": {"artifacts": ["evidence/render.md"], "breakpoints": ["320", "1440"], "themes": ["light", "dark"],
                                          "inputs": [{"path": f"artifacts/variants/{self.chosen}/app.html", "sha256": self.hashes[f"artifacts/variants/{self.chosen}/app.html"]}],
                                          "result": {"status": "pass"}},
                "accessibility_evidence": {"items": [{"id": "a11y-1", "severity": "Minor", "status": "open"}]},
                "recommendation": "m2, because it satisfies the density and typography preferences within the contrast floor",
                "residual_risk": "none observed",
            },
            "artifact_hashes": dict(self.hashes),
        }

    def selection(self, decision: str = "variant", chosen: str | None = "m2") -> dict:
        return {"schema_version": 2, "artifacts": ["reports/selection.md"], "decision": decision,
                "chosen": chosen, "recommended": "m2", "decided_by": "user",
                "decided_at": "2026-09-17T00:00:00Z",
                "basis": "density and typography preferences within the contrast floor"}

    def stood_down(self, data: dict, wording: str) -> None:
        """Put the four dependent keys where a non-variant decision leaves them."""
        for key in ("selected_variant", "parity_evidence", "rendered_verification",
                    "accessibility_evidence"):
            data["evidence"][key] = {"applicable": False, "reason": wording,
                                     "scope": "whole run", "decided_by": "redesign"}

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
        for key in ("mock_set", "selection", "selected_variant"):
            self.assertIn(key, out["evidence_digests"])

    def test_three_mocks_duplicate_ids_and_unhashed_files_fail(self):
        data = self.pkg.manifest()
        data["evidence"]["mock_set"]["mocks"] = data["evidence"]["mock_set"]["mocks"][:3]
        data["evidence"]["mock_set"]["count"] = 3
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("requires exactly 4 mocks, found 3" in f for f in out["failures"]), out["failures"])
        data = self.pkg.manifest()
        data["evidence"]["mock_set"]["mocks"][1]["id"] = "m1"
        data["evidence"]["mock_set"]["mocks"][2]["mock"] = "artifacts/mocks/m3/missing.html"
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("duplicate id m1" in f for f in out["failures"]), out["failures"])
        self.assertTrue(any("mock is not a hashed artifact" in f for f in out["failures"]), out["failures"])

    def test_the_selected_variant_is_counted_separately_and_must_be_one(self):
        data = self.pkg.manifest()
        data["evidence"]["selected_variant"]["variants"] = data["evidence"]["selected_variant"]["variants"] * 2
        data["evidence"]["selected_variant"]["count"] = 2
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("selected_variant requires exactly 1 variants, found 2" in f
                            for f in out["failures"]), out["failures"])

    def test_mock_rendering_accepts_no_fallback_at_redesign_review(self):
        data = self.pkg.manifest()
        data["evidence"]["mock_rendering"] = {"applicable": False, "reason": "no browser available",
                                              "scope": "whole run", "decided_by": "design-qa"}
        _, out = run(self.pkg.write(data))
        self.assertIn("evidence not waivable: mock_rendering", out["failures"])
        # rendered_verification, by contrast, is waivable here - a merge or a
        # deferral legitimately has no living prototype to render.
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("deferred", None)
        self.pkg.stood_down(data, DEFERRED)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 0, out["failures"])


class SelectionContractTests(unittest.TestCase):
    """The decision is the hinge: it decides what four other keys may carry."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pkg = RedesignPackage(Path(tmp.name).resolve())

    def test_a_deferral_stands_the_four_dependent_keys_down(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("deferred", None)
        self.pkg.stood_down(data, DEFERRED)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 0, out["failures"])

    def test_a_merge_stands_them_down_on_the_merge_wording(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("merge", None)
        self.pkg.stood_down(data, MERGED)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 0, out["failures"])

    def test_the_wrong_sanctioned_wording_for_the_decision_is_refused(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("merge", None)
        self.pkg.stood_down(data, DEFERRED)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any(f.startswith("selected_variant must stand down on") for f in out["failures"]),
                        out["failures"])

    def test_a_deferral_that_still_claims_a_built_variant_is_refused(self):
        """Standing down is not optional once the decision names no variant."""
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("deferred", None)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("selected_variant must stand down on" in f for f in out["failures"]),
                        out["failures"])

    def test_a_variant_decision_may_not_stand_any_dependent_key_down(self):
        data = self.pkg.manifest()
        data["evidence"]["parity_evidence"] = {"applicable": False, "reason": DEFERRED,
                                               "scope": "whole run", "decided_by": "redesign"}
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any(f.startswith("parity_evidence stands down on") for f in out["failures"]),
                        out["failures"])

    def test_the_built_variant_must_be_the_chosen_one(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("variant", "m3")
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(any("was built for 'm2' but selection chose 'm3'" in f for f in out["failures"]),
                        out["failures"])

    def test_chosen_and_recommended_must_name_a_mock_in_the_set(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("variant", "m9")
        data["evidence"]["selection"]["recommended"] = "m8"
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("selection chosen 'm9' is not one of the mock_set ids" in f
                            for f in out["failures"]), out["failures"])
        self.assertTrue(any("selection recommended 'm8' is not one of the mock_set ids" in f
                            for f in out["failures"]), out["failures"])

    def test_a_non_variant_decision_may_not_name_a_chosen_mock(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = self.pkg.selection("merge", "m2")
        self.pkg.stood_down(data, MERGED)
        _, out = run(self.pkg.write(data))
        self.assertIn("selection decision 'merge' requires chosen: null", out["failures"])

    def test_an_incomplete_selection_record_is_refused(self):
        data = self.pkg.manifest()
        data["evidence"]["selection"] = {"artifacts": ["reports/selection.md"], "decision": "sideways",
                                         "chosen": None, "recommended": "m2"}
        _, out = run(self.pkg.write(data))
        self.assertTrue(any("selection decision must be one of" in f for f in out["failures"]), out["failures"])
        for field in ("decided_by", "decided_at", "basis"):
            self.assertIn(f"selection record requires {field}", out["failures"])


class RevisePacketTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pkg = RedesignPackage(Path(tmp.name).resolve())

    def test_failures_are_grouped_by_owner_and_key(self):
        data = self.pkg.manifest()
        data["evidence"].pop("design_inventory")                   # design-mapper
        data["evidence"]["mock_set"]["mocks"][0]["tokens"] = ""    # prototyper
        data["evidence"]["selection"] = self.pkg.selection("variant", "m4")  # redesign
        data["evidence"]["accessibility_evidence"] = {"items": [{"id": "a", "severity": "Critical", "status": "open"}]}  # frontier
        data["artifact_hashes"]["evidence/proof.md"] = "0" * 64    # submitter (hash mismatch)
        proc, out = run(self.pkg.write(data))
        self.assertEqual(proc.returncode, 1)
        packet = out["revise_packet"]
        self.assertIn("missing evidence: design_inventory", packet["by_owner"]["design-mapper"])
        self.assertTrue(any("mock_set.mocks[0] requires tokens" in f for f in packet["by_owner"]["prototyper"]))
        self.assertTrue(any("selected_variant was built for" in f for f in packet["by_owner"]["prototyper"]))
        self.assertTrue(any("accessibility_evidence[0]" in f for f in packet["by_owner"]["frontier"]))
        self.assertTrue(any("artifact hash mismatch" in f for f in packet["by_owner"]["redesign"]))
        self.assertEqual(set(packet["by_key"]) & {"design_inventory", "mock_set", "selected_variant", "accessibility_evidence"},
                         {"design_inventory", "mock_set", "selected_variant", "accessibility_evidence"})
        self.assertTrue(any("artifact hash mismatch" in f for f in packet["unassigned"]))

    def test_prior_verdict_reports_changed_and_unchanged_keys(self):
        first = self.pkg.write(self.pkg.manifest())
        proc, out = run(first, "--verdict-out", str(self.pkg.root / "verdict.json"))
        self.assertEqual(proc.returncode, 0, out)
        self.assertIsNone(out["changed_evidence"])
        data = self.pkg.manifest()
        # A resubmission is a new revision; reusing r1 with different content is idempotency drift.
        data.update({"submission_id": "redesign-2", "revision": "r2", "revisions": ["r2"]})
        data["evidence"]["recommendation"] = "m2, after the user chose density over typography"
        self.pkg.file("artifacts/mocks/m3/mock.html", "/* mock.html m3 revised */\n")
        data["artifact_hashes"] = dict(self.pkg.hashes)
        second = self.pkg.write(data, "manifest-2.json")
        proc, out = run(second, "--prior", str(self.pkg.root / "verdict.json"))
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(out["changed_evidence"], ["mock_set", "recommendation"])
        self.assertIn("design_inventory", out["unchanged_evidence"])
        self.assertIn("parity_evidence", out["unchanged_evidence"])
        self.assertFalse(out["prior_reusable"])

    def test_gate_spec_declares_owner_for_every_required_key(self):
        spec = json.loads((SKILLS / "gates.yaml").read_text(encoding="utf-8"))
        for name, boundary in spec["boundaries"].items():
            with self.subTest(boundary=name):
                self.assertEqual(set(spec["evidence_owners"][name]), set(boundary["required_evidence"]))
        self.assertEqual(spec["revise_policy"]["cycle_cap"], 2)
        params = spec["evidence_type_params"]
        self.assertEqual(params["mock_set"]["required_count"], 4)
        self.assertEqual(params["selected_variant"]["required_count"], 1)
        self.assertEqual(sorted(params["selection"]["dependent_keys"]),
                         ["accessibility_evidence", "parity_evidence", "rendered_verification",
                          "selected_variant"])


if __name__ == "__main__":
    unittest.main()
