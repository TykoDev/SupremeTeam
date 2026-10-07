"""Functional audit regressions; no performance baseline or timing budget."""
from __future__ import annotations

import json
import subprocess
import sys
from unittest import mock

from test_run_state import RunStateCase, SAVE_RUN, _saves, save_run
from save_taxonomy import protocol_state_for


class QualityAuditStateTests(RunStateCase):
    def test_status_without_a_run_id_classifies_before_creating_any_files(self):
        proc = subprocess.run([sys.executable, str(SAVE_RUN), "status", "--project-root", str(self.project)],
                              text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "missing")
        self.assertFalse((self.project / "skillset-saves").exists())
        self.create()
        proc = subprocess.run([sys.executable, str(SAVE_RUN), "status", "--project-root", str(self.project)],
                              text=True, capture_output=True, check=False)
        record = json.loads(proc.stdout)
        self.assertEqual(record["status"], "active")
        self.assertEqual(record["owner"], "admiral")
        self.assertEqual(record["run_id"], "run-1")

    def test_mutations_still_require_a_run_id(self):
        proc = subprocess.run([sys.executable, str(SAVE_RUN), "create", "--project-root", str(self.project)],
                              text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--run-id is required", proc.stderr)
        self.assertFalse((self.project / "skillset-saves").exists())

    def test_engaged_skills_are_a_typed_append_once_list(self):
        extra = save_run.parse_extra(['skills_engaged=["session-memory", "commander", "commander"]'])
        self.store().create("admiral", ["README.md"], "skill", "next", extra)
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "commander"])
        self.store().checkpoint("admiral", 1, [], "active", "next",
                                save_run.parse_extra(['skills_engaged=["taste", "commander"]']))
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "commander", "taste"])

    def test_terminal_writes_preserve_engagement_history(self):
        self.store().create("admiral", ["README.md"], "skill", "next",
                            save_run.parse_extra(['skills_engaged=["session-memory"]']))
        self.store().finish("admiral", "blocked", "missing evidence",
                            save_run.parse_extra(['skills_engaged=["taste"]']))
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "taste"])

    def test_legacy_json_string_is_migrated_without_losing_skills(self):
        self.store().create("admiral", ["README.md"], "skill", "next",
                            {"skills_engaged": '["session-memory"]'})
        self.store().checkpoint("admiral", 1, [], "active", "next",
                                save_run.parse_extra(['skills_engaged=["taste"]']))
        self.assertEqual(self.state()["skills_engaged"], ["session-memory", "taste"])

    def test_invalid_engaged_skills_are_refused_before_persistence(self):
        for value in ('"taste"', '{}', '[null]', '[1]', '[""]', 'not-json'):
            with self.subTest(value=value), self.assertRaises(save_run.Refused):
                save_run.parse_extra(["skills_engaged=" + value])

    def test_phase_labels_map_to_declared_protocol_states(self):
        expected = {"INTAKE": "INTAKE", "DESIGN": "DESIGN", "REDESIGN": "DESIGN", "BUILD": "BUILD",
                    "INVESTIGATION": "BUILD", "SKILL_CREATION": "BUILD", "CREATE": "BUILD", "IMPROVE": "BUILD",
                    "OPTIMIZE": "BUILD", "PACKAGE": "BUILD", "REVIEW": "REVIEW", "SECURITY": "REVIEW", "QA": "REVIEW",
                    "DELIVERY": "GATE", "RELEASE": "GATE"}
        for prefix, active in expected.items():
            for suffix, protocol in (("_ACTIVE", active), ("_GATE_PENDING", "GATE"), ("_GATE_REVISE", "REVISE")):
                with self.subTest(prefix=prefix, suffix=suffix):
                    self.assertEqual(protocol_state_for(prefix + suffix), protocol)
        for phase in ("TASTE_ACTIVE", "TASTE_GATE_PENDING", "TASTE_GATE_REVISE"):
            self.assertEqual(protocol_state_for(phase), phase)
        self.assertEqual(protocol_state_for("RUN_COMPLETE"), "COMPLETE")
        self.assertEqual(protocol_state_for("DISPUTED_AWAITING_USER"), "ESCALATE")
        with self.assertRaises(save_run.Refused):
            save_run.parse_extra(["phase_state=UNKNOWN_ACTIVE"])
        with self.assertRaises(save_run.Refused):
            save_run.parse_extra(["protocol_state=RELEASE"])

    def test_writer_persists_mapping_and_terminal_state(self):
        self.store().create("admiral", ["README.md"], "skill", "next",
                            save_run.parse_extra(["phase_state=DESIGN_ACTIVE"]))
        self.assertEqual(self.state()["protocol_state"], "DESIGN")
        self.store().checkpoint("admiral", 1, [], "active", "next",
                                save_run.parse_extra(["phase_state=PACKAGE_GATE_PENDING"]))
        self.assertEqual(self.state()["protocol_state"], "GATE")
        self.store().finish("admiral", "blocked", "missing evidence", {})
        self.assertEqual(self.state()["protocol_state"], "BLOCKED")

    def test_stale_or_unreadable_pinned_lock_is_not_coherent_handoff_proof(self):
        self.create()
        self.age_records(31)
        self.assertTrue(self.lock()["session_pin"])
        self.assertEqual(_saves.inspect_saves(self.project)["status"], "stale")
        self.assertFalse(_saves.has_active_run(self.project))
        with mock.patch.object(_saves, "inspect_saves", return_value={"status": "corrupt", "access_denied": ["lock"]}):
            # Conservative protection is not a positive active/orphaned classification.
            self.assertTrue(_saves.has_active_run(self.project))
            self.assertNotIn(_saves.inspect_saves(self.project)["status"], {"active", "orphaned"})
