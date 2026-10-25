"""Gate verdicts cannot evade the third-REVISE user hold across retries/resume."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_gate_judgment import CHECK, DesignPackage, judgment
from _gatecycle import _fresh, advance


def result(gate="gatekeeper-design", revision="r1", verdict="REVISE"):
    return {"boundary": "design-to-build", "run_id": "run-a", "revision": revision,
            "submission_id": "d1", "package_fingerprint": revision, "checked_at": "2026-10-25T00:00:00Z",
            "judgment": {"gate": gate, "verdict": verdict}, "revise_packet": {"by_owner": {"planner": ["repair AC-1"]}}}


class StreakTests(unittest.TestCase):
    def test_each_gate_always_escalates_its_third_consecutive_revise_to_user(self):
        for gate in ("gatekeeper-design", "gatekeeper-build", "gatekeeper-code", "gatekeeper-admiral"):
            with self.subTest(gate=gate):
                state = _fresh(result(gate))
                for revision in ("r1", "r2", "r3"):
                    report = result(gate, revision)
                    state = advance(state, report)
                self.assertEqual(report["judgment"]["verdict"], "ESCALATE")
                self.assertEqual(report["judgment"]["escalation"]["to"], "user")
                self.assertEqual(report["revision_cycle"]["consecutive_revise"], 3)
                self.assertEqual(len(state["events"]), 3)

    def test_duplicate_revision_and_new_submission_id_cannot_reset_or_inflate_counter(self):
        state = _fresh(result())
        for ident, revision in (("a", "r1"), ("b", "r1"), ("c", "r2"), ("d", "r3")):
            report = result(revision=revision)
            report["submission_id"] = ident
            state = advance(state, report)
        self.assertTrue(state["held"])
        self.assertEqual(state["rounds"], ["r1", "r2", "r3"])

    def test_phase_approval_does_not_reset_the_shared_boundary_budget(self):
        state = _fresh(result())
        for gate, revision, verdict in (("gatekeeper-design", "r1", "REVISE"),
                                        ("gatekeeper-design", "r2", "APPROVED"),
                                        ("gatekeeper-admiral", "r2", "REVISE"),
                                        ("gatekeeper-design", "r3", "REVISE")):
            report = result(gate, revision, verdict)
            state = advance(state, report)
        self.assertTrue(state["held"])

    def test_cross_stage_approval_resets_a_streak_before_cap(self):
        report = result()
        state = advance(_fresh(report), report)
        state = advance(state, result("gatekeeper-admiral", "r2", "APPROVED"))
        self.assertEqual(state["rounds"], [])
        self.assertEqual(state["gates"], {})

    def test_a_user_hold_survives_even_an_approved_retry_and_can_only_reopen_with_new_reference(self):
        state = _fresh(result())
        for revision in ("r1", "r2", "r3"):
            state = advance(state, result(revision=revision))
        held = result(revision="r4", verdict="APPROVED")
        state = advance(state, held)
        self.assertEqual(held["judgment"]["verdict"], "ESCALATE")
        reopened = result(revision="r4")
        state = advance(state, reopened, "user-message-17")
        self.assertFalse(state["held"])
        self.assertEqual(state["rounds"], ["r4"])
        for revision in ("r5", "r6"):
            state = advance(state, result(revision=revision))
        with self.assertRaises(ValueError):
            advance(state, result(revision="r7"), "user-message-17")
        self.assertGreater(len(state["events"]), 3)


class DurableCycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.design = DesignPackage(self.root)

    def run_round(self, number, *, verdict="REVISE", out="verdict.json", extra=()):
        revision = f"r{number}"
        self.design.data.update(revision=revision, revisions=[revision], submission_id=f"d{number}")
        record = judgment(verdict, findings=[] if verdict == "APPROVED" else None,
                          revision=revision, submission_id=f"d{number}")
        source = self.root / "judgment.json"
        source.write_text(json.dumps(record), encoding="utf-8")
        return subprocess.run([sys.executable, str(CHECK), "--boundary", "design-to-build", "--package",
                               str(self.design.write()), "--judgment", str(source), "--verdict-out",
                               str(self.root / out), *extra], capture_output=True, text=True)

    def test_resume_and_changing_output_without_prior_cannot_evade_cap(self):
        for number in (1, 2, 3):
            proc = self.run_round(number, out=f"verdict-{number}.json")
            self.assertEqual(proc.returncode, 1 if number == 3 else 0, proc.stderr)
        report = json.loads(proc.stdout)
        self.assertEqual(report["judgment"]["verdict"], "ESCALATE")
        self.assertEqual(report["judgment"]["requested_verdict"], "REVISE")
        history = json.loads((self.root / report["revision_cycle"]["history"]).read_text())
        self.assertEqual(len(history["events"]), 3)
        self.assertIn("actions_by_owner", history["events"][0]["revise_packet"])
        self.assertEqual(self.run_round(4, verdict="APPROVED").returncode, 1)
        reopened = self.run_round(4, extra=("--reopen-reference", "user-message-18"))
        self.assertEqual(reopened.returncode, 0, reopened.stderr)
        self.assertEqual(json.loads(reopened.stdout)["revision_cycle"]["consecutive_revise"], 1)

    def test_corrupt_history_fails_loud_and_is_not_overwritten(self):
        history = self.root / "verdict_design-to-build.cycles.json"
        history.write_text("{broken", encoding="utf-8")
        proc = self.run_round(1)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(history.read_text(), "{broken")
        self.assertFalse((self.root / "verdict.json").exists())

    def test_lost_history_needs_a_user_decision_instead_of_resetting(self):
        self.assertEqual(self.run_round(1).returncode, 0)
        (self.root / "verdict_design-to-build.cycles.json").unlink()
        proc = self.run_round(2)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("history is missing", proc.stderr)
        proc = self.run_round(2, extra=("--reopen-reference", "user-history-recovery-1"))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_judgment_cannot_be_published_without_durable_history(self):
        source = self.root / "judgment.json"
        source.write_text(json.dumps(judgment()), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(CHECK), "--boundary", "design-to-build", "--package",
                               str(self.design.write()), "--judgment", str(source)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("requires --verdict-out", proc.stderr)

    def test_same_revision_cannot_hide_changed_evidence_without_prior(self):
        self.assertEqual(self.run_round(1).returncode, 0)
        self.design.file("design/architecture.md", "# Changed architecture\n\nNew store boundary.\n")
        proc = self.run_round(1)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("idempotency drift on recorded revision", proc.stderr)

    def test_mechanical_self_checks_do_not_create_history_or_count(self):
        proc = subprocess.run([sys.executable, str(CHECK), "--boundary", "design-to-build", "--package",
                               str(self.design.write())], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(list(self.root.glob("*.cycles.*")))

    def test_a_mechanical_precheck_cannot_erase_the_prior_judgment(self):
        self.assertEqual(self.run_round(1).returncode, 0)
        out = self.root / "verdict.json"
        before = out.read_bytes()
        proc = subprocess.run([sys.executable, str(CHECK), "--boundary", "design-to-build", "--package",
                               str(self.design.write()), "--verdict-out", str(out)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must not overwrite", proc.stderr)
        self.assertEqual(out.read_bytes(), before)

    def test_rejected_feedback_never_counts(self):
        original = copy.deepcopy(self.design.data)
        self.design.data["evidence"]["decisions"] = "intake/missing.md"
        proc = self.run_round(1)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(list(self.root.glob("*.cycles.json")))
        self.design.data = original


if __name__ == "__main__":
    unittest.main()
