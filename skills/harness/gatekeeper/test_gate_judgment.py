#!/usr/bin/env python3
"""A gatekeeper's judgment stands on the source of truth (gates.yaml judgment_policy).

check.py --judgment reads the gate's own record of its verdict and findings and
fails it when a finding could not be checked: it cites a decision or acceptance
id the intake log or plan does not contain, a contract file that does not exist,
or an artifact the package does not hash; it names a key or an owner the spec
does not; the verdict does not follow from the findings; the judging gate is the
submitter; or a resubmission to the same gate raises a new blocking finding on
evidence that did not change. These pin each of those, the floor that keeps a
submitter from becoming its own gate, and that a rejected record is never
written as a verdict.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_gate_engine import CHECK, GATE_SPEC, SKILLS, engine
from data_formats import content_sha256, load_data
from contract_floor import gate_floor_errors
import _fixtures

#: The intake log and the plan carry the fixed source-of-truth tables (D-1..D-4, AC-1).
GRILLING = _fixtures.source_of_truth("src/app.py")
PLAN = GRILLING


class DesignPackage:
    """A flat schema-2 design-to-build package that passes the mechanical check."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.hashes: dict[str, str] = {}
        self.file("intake/report_grilling.md", GRILLING)
        self.file("design/architecture.md", "# Architecture\n\nComponents: api, store.\n")
        self.file("design/plan.md", PLAN)
        self.file("design/research.md", "# Research\n\nSources: AC-1 is quoted here too.\n")
        spec = load_data(GATE_SPEC)

        def waived(key: str) -> dict:
            return {"applicable": False, "reason": spec["fallback_values"][key][0],
                    "scope": "whole run", "decided_by": "commander"}

        self.data = {
            "schema_version": 2, "boundary": "design-to-build", "owner": "commander",
            "submission_id": "d1", "revision": "r1", "revisions": ["r1"],
            "evidence": {
                "decisions": "intake/report_grilling.md", "architecture": "design/architecture.md",
                "interfaces": {"artifacts": ["design/architecture.md"], "change": "none", "items": []},
                "plan": "design/plan.md", "acceptance": "design/plan.md",
                "security_seed": {"applicable": False, "scope": "whole run", "decided_by": "security-builder",
                                  "architecture_revision": "r1", "reason": "no trust boundary", "boundaries": []},
                "stack_lock": waived("stack_lock"), "taste_snapshot": waived("taste_snapshot"),
                "ui_evidence": waived("ui_evidence"),
            },
            "artifact_hashes": self.hashes,
        }

    def file(self, rel: str, text: str) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.hashes[rel] = content_sha256(path)
        return rel

    def write(self, name: str = "manifest.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(self.data), encoding="utf-8")
        return path


def finding(**overrides) -> dict:
    item = {"id": "J-1", "severity": "Major", "key": "plan",
            "statement": "AC-1 names no slice owner for the store migration D-2 commits to",
            "basis": {"kind": "acceptance", "ref": "AC-1", "artifact": "design/plan.md"},
            "evidence": ["design/plan.md"]}
    item.update(overrides)
    return item


def judgment(verdict: str = "REVISE", findings: list | None = None, **overrides) -> dict:
    record = {"boundary": "design-to-build", "submission_id": "d1", "revision": "r1",
              "gate": "gatekeeper-design", "verdict": verdict,
              "findings": [finding()] if findings is None else findings}
    record.update(overrides)
    return record


class JudgmentCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.spec = engine.load_gate_spec(GATE_SPEC)
        self.design = DesignPackage(self.root)

    def judge(self, record: dict, mechanical: list[str] | None = None, prior: dict | None = None,
              changed: list[str] | None = None) -> tuple[dict, list[str]]:
        package = engine.Package(self.root / "manifest.json", self.design.data, "design-to-build", self.spec)
        package.check_artifacts()
        self.assertEqual(package.failures, [])
        return engine.check_judgment(package, record, mechanical or [], self.spec, prior, changed)

    def assertRejected(self, record: dict, fragment: str, **kwargs) -> None:
        summary, failures = self.judge(record, **kwargs)
        self.assertFalse(summary["valid"])
        self.assertTrue(any(fragment in failure for failure in failures), failures)


class GroundingTests(JudgmentCase):
    def test_a_grounded_revise_is_valid_and_routes_to_the_spec_owner(self):
        summary, failures = self.judge(judgment())
        self.assertEqual(failures, [])
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["by_owner"], {"planner": ["J-1"]})

    def test_each_basis_kind_has_a_grounded_form(self):
        grounded = [
            finding(id="J-1", key="decisions", basis={"kind": "decision", "ref": "D-2", "artifact": "intake/report_grilling.md"},
                    evidence=["intake/report_grilling.md"]),
            finding(id="J-2"),
            finding(id="J-3", key="interfaces", basis={"kind": "contract", "source": "design/architect/references/api-endpoint-design.md",
                                                     "ref": "error envelope"}, evidence=["manifest:evidence.interfaces"]),
            finding(id="J-4", key="architecture", basis={"kind": "contradiction"},
                    evidence=["design/architecture.md", "design/plan.md"]),
        ]
        summary, failures = self.judge(judgment(findings=grounded))
        self.assertEqual(failures, [])
        self.assertEqual(summary["by_owner"], {"admiral": ["J-1"], "architect": ["J-3", "J-4"], "planner": ["J-2"]})

    def test_a_decision_the_intake_log_does_not_hold_cannot_be_cited(self):
        self.assertRejected(judgment(findings=[finding(key="decisions", basis={
            "kind": "decision", "ref": "D-9", "artifact": "intake/report_grilling.md"})]),
            "cites D-9, which intake/report_grilling.md does not contain")

    def test_an_id_prefix_is_not_a_citation(self):
        """D-1 is in the log; D-10 is not, and must not be found inside D-1x text either way."""
        self.design.file("intake/report_grilling.md", GRILLING.replace("D-1 ", "D-10 "))
        self.design.data["artifact_hashes"] = self.design.hashes
        self.assertRejected(judgment(findings=[finding(key="decisions", basis={
            "kind": "decision", "ref": "D-1", "artifact": "intake/report_grilling.md"})]), "cites D-1")

    def test_a_citation_must_come_from_the_packages_own_source_of_truth(self):
        """research.md quotes AC-1, but the acceptance criteria are the plan's, not the research note's."""
        self.assertRejected(judgment(findings=[finding(basis={
            "kind": "acceptance", "ref": "AC-1", "artifact": "design/research.md"})]),
            "is not the package's acceptance/plan evidence")

    def test_a_citation_shaped_wrongly_or_unhashed_is_refused(self):
        self.assertRejected(judgment(findings=[finding(basis={"kind": "acceptance", "ref": "criterion 1",
                                                              "artifact": "design/plan.md"})]), "ref must be an id")
        self.assertRejected(judgment(findings=[finding(basis={"kind": "acceptance", "ref": "AC-1",
                                                              "artifact": "design/other.md"})]), "not a correctly hashed")

    def test_the_gates_own_preference_is_not_a_basis(self):
        for kind in ("opinion", "best-practice", None):
            with self.subTest(kind=kind):
                self.assertRejected(judgment(findings=[finding(basis={"kind": kind, "ref": "x"})]), "basis.kind must be")
        self.assertRejected(judgment(findings=[finding(basis="the gate prefers GraphQL")]), "basis.kind must be")

    def test_a_contract_basis_names_a_catalog_file_that_exists(self):
        for source in ("no-such-doctrine.md", "../README.md", "/etc/passwd", "harness/gatekeeper/check.py", None):
            with self.subTest(source=source):
                self.assertRejected(judgment(findings=[finding(basis={"kind": "contract", "source": source, "ref": "§1"})]),
                                    "contract basis source")
        self.assertRejected(judgment(findings=[finding(basis={"kind": "contract", "source": "gates.yaml"})]),
                            "contract basis requires ref")

    def test_a_contradiction_needs_two_artifacts(self):
        self.assertRejected(judgment(findings=[finding(basis={"kind": "contradiction"}, evidence=["design/plan.md"])]),
                            "contradiction basis requires two")

    def test_a_blocking_finding_points_at_hashed_package_evidence(self):
        self.assertRejected(judgment(findings=[finding(evidence=[])]), "Major requires at least one evidence anchor")
        self.assertRejected(judgment(findings=[finding(evidence=["design/unhashed.md"])]), "not a hashed package artifact")
        self.assertRejected(judgment(findings=[finding(evidence=["manifest:evidence.scope"])]), "names no evidence")
        summary, failures = self.judge(judgment("APPROVED", findings=[finding(severity="Minor", evidence=[])]))
        self.assertEqual(failures, [], "a Minor note needs no anchor and rides along on APPROVED")

    def test_a_gate_never_invents_a_key_or_reroutes_an_owner(self):
        self.assertRejected(judgment(findings=[finding(key="performance_budget")]), "is not required evidence")
        self.assertRejected(judgment(findings=[finding(owner="commander")]), "is not the spec owner 'planner'")

    def test_every_finding_carries_id_severity_and_statement(self):
        self.assertRejected(judgment(findings=[finding(id="")]), "requires id")
        self.assertRejected(judgment(findings=[finding(), finding()]), "duplicate id")
        self.assertRejected(judgment(findings=[finding(severity="High")]), "severity must be one of")
        self.assertRejected(judgment(findings=[finding(statement=" ")]), "requires statement")


class VerdictTests(JudgmentCase):
    def test_revise_needs_a_mechanical_failure_or_a_grounded_blocking_finding(self):
        self.assertRejected(judgment(findings=[finding(severity="Minor")]), "REVISE without")
        self.assertRejected(judgment(findings=[]), "REVISE without")
        summary, failures = self.judge(judgment(findings=[]), mechanical=["missing evidence: plan"])
        self.assertEqual(failures, [])

    def test_approved_never_sits_beside_a_blocking_finding_or_a_mechanical_failure(self):
        self.assertRejected(judgment("APPROVED"), "APPROVED with a Critical or Major finding")
        self.assertRejected(judgment("APPROVED", findings=[]), "APPROVED over mechanical failures",
                            mechanical=["missing evidence: plan"])

    def test_escalate_names_where_and_why(self):
        self.assertRejected(judgment("ESCALATE", findings=[]), "ESCALATE requires escalation")
        summary, failures = self.judge(judgment("ESCALATE", findings=[], escalation={
            "to": "admiral", "reason": "the intake never decided between REST and GraphQL for the export path"}))
        self.assertEqual(failures, [])

    def test_a_malformed_record_is_a_judgment_failure_not_an_engine_fault(self):
        for field, value in (("verdict", ["REVISE"]), ("gate", {"name": "gatekeeper-design"})):
            with self.subTest(field=field):
                self.assertRejected(judgment(**{field: value}), "judgment")
        for overrides in ({"severity": ["Major"]}, {"key": ["plan"]}, {"basis": {"kind": ["decision"]}},
                          {"owner": ["planner"]}, {"evidence": "design/plan.md"}):
            with self.subTest(overrides=overrides):
                self.assertRejected(judgment(findings=[finding(**overrides)]), "judgment finding")
        self.assertRejected(judgment(findings="J-1"), "findings must be a list")
        self.assertRejected(judgment(findings=["J-1"]), "must be a mapping")

    def test_unknown_verdict_and_wrong_identity_are_refused(self):
        self.assertRejected(judgment("PASS"), "verdict must be one of")
        self.assertRejected(judgment(revision="r2"), "judgment revision")
        self.assertRejected(judgment(submission_id="d0"), "judgment submission_id")
        self.assertRejected(judgment(boundary="build-to-review"), "judgment boundary")


class IndependenceTests(JudgmentCase):
    def test_only_the_boundarys_gates_may_judge_it(self):
        for gate in ("commander", "planner", "gatekeeper-build", "gatekeeper-code", None):
            with self.subTest(gate=gate):
                self.assertRejected(judgment(gate=gate), "may not judge design-to-build")
        for gate in ("gatekeeper-design", "gatekeeper-admiral"):
            with self.subTest(gate=gate):
                self.assertEqual(self.judge(judgment(gate=gate))[1], [])

    def test_the_floor_refuses_a_spec_that_lets_a_submitter_judge(self):
        for mutate in (lambda s: s["judgment_policy"]["phase_gates"].update({"build-to-review": "build-management"}),
                       lambda s: s["judgment_policy"].update({"cross_stage_gate": "admiral"}),
                       lambda s: s.pop("judgment_policy")):
            spec = copy.deepcopy(load_data(GATE_SPEC))
            mutate(spec)
            self.assertIn("gate safety floor: judgment_policy gates changed", gate_floor_errors(spec))

    def test_phase_gates_are_the_owners_of_each_pipelines_phase_gate_stage(self):
        pipelines = load_data(SKILLS / "pipelines.yaml")["pipelines"]
        declared = {pipeline["boundary"]: stage["owner"] for pipeline in pipelines.values()
                    for stage in pipeline["stages"] if stage.get("step") == "phase-gate"}
        self.assertEqual(self.spec["judgment_policy"]["phase_gates"], declared)

    def test_the_spec_lists_the_basis_kinds_the_engine_enforces(self):
        self.assertEqual(set(self.spec["judgment_policy"]["basis_kinds"]), set(engine.JUDGMENT_BASIS_KINDS))
        self.assertEqual(set(self.spec["judgment_policy"]["basis_rules"]), set(engine.JUDGMENT_BASIS_KINDS))


class DeltaTests(JudgmentCase):
    def prior(self, gate: str = "gatekeeper-design") -> dict:
        return {"judgment": {"gate": gate, "verdict": "REVISE", "valid": True, "findings": [finding(id="J-1")]}}

    def test_a_new_blocking_finding_on_unchanged_evidence_is_refused_on_resubmission(self):
        late = finding(id="J-2", key="architecture", basis={"kind": "contradiction"},
                       evidence=["design/architecture.md", "design/plan.md"])
        self.assertRejected(judgment(findings=[late]), "is new on unchanged evidence architecture",
                            prior=self.prior(), changed=["plan"])

    def test_carried_findings_and_findings_on_changed_evidence_stand(self):
        on_changed = finding(id="J-3")
        summary, failures = self.judge(judgment(findings=[finding(id="J-1"), on_changed]),
                                       prior=self.prior(), changed=["plan"])
        self.assertEqual(failures, [])

    def test_another_gates_prior_does_not_bind_the_delta(self):
        """gatekeeper-admiral reading the phase record judges the crossing; batch_fix is per gate."""
        late = finding(id="J-2", key="architecture", basis={"kind": "contradiction"},
                       evidence=["design/architecture.md", "design/plan.md"])
        summary, failures = self.judge(judgment(gate="gatekeeper-admiral", findings=[late]),
                                       prior=self.prior(), changed=[])
        self.assertEqual(failures, [])


class CommandLineTests(JudgmentCase):
    def run_check(self, *extra: str) -> subprocess.CompletedProcess:
        manifest = self.design.write()
        return subprocess.run([sys.executable, str(CHECK), "--boundary", "design-to-build",
                               "--package", str(manifest), *extra], capture_output=True, text=True)

    def write_judgment(self, record: dict, name: str = "verdict_design-to-build.judgment.json") -> Path:
        path = self.root / name
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def test_a_grounded_judgment_is_embedded_in_the_verdict_record(self):
        out = self.root / "verdict_design-to-build.json"
        result = self.run_check("--judgment", str(self.write_judgment(judgment())), "--verdict-out", str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertFalse(record["mechanical_only"])
        self.assertEqual(record["judgment"]["verdict"], "REVISE")
        self.assertEqual(record["revise_packet"]["judgment_by_owner"], {"planner": ["J-1"]})

        # The cross-stage gate reads the phase verdict from the gate's record, not the submitter's checkpoint.
        cross = self.run_check("--prior", str(out))
        self.assertEqual(json.loads(cross.stdout)["prior_record"]["judgment"],
                         {"gate": "gatekeeper-design", "verdict": "REVISE", "valid": True})

    def test_an_ungrounded_judgment_is_never_written_as_a_verdict(self):
        out = self.root / "verdict_design-to-build.json"
        bad = judgment(findings=[finding(basis={"kind": "decision", "ref": "D-7", "artifact": "intake/report_grilling.md"})])
        result = self.run_check("--judgment", str(self.write_judgment(bad)), "--verdict-out", str(out))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(out.exists())
        self.assertIn("verdict not written", result.stderr)
        self.assertFalse(json.loads(result.stdout)["judgment"]["valid"])

    def test_without_a_judgment_the_record_stays_mechanical(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["mechanical_only"])
        self.assertIsNone(report["judgment"])


if __name__ == "__main__":
    unittest.main()
