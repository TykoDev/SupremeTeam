#!/usr/bin/env python3
"""The audit is a pipeline of small parts, one per record class, and the report did not change (CR-18).

``audit()`` was one 207-line function with about a hundred branches, so no part of it could be
tested alone and nine of its finding codes were never asserted anywhere. It is now a collector
(``AuditScan``) and one function per record class, assembled in the old order. Two kinds of test
hold it: a golden report on a fixture that touches every class pins the whole output byte for byte
(it passes on the code before the split as well, which is the proof nothing moved), and a unit test
per part builds the smallest fixture for that part and calls it alone.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

HOOKS = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS))
import audit_improve as subject  # noqa: E402


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")


def build_everything(root: Path) -> None:
    """A project whose saved state and hook state touch every record class the audit reads."""
    saves = root / "skillset-saves"
    harness = root / ".harness-state"
    write(saves / "_latest.md", {"run_id": "r-main", "revision": 1})
    main = saves / "runs" / "r-main"
    write(main / "_state.md", {"status": "active", "revision": 1})
    write(main / "_lock.md", {"status": "held", "revision": 2})
    write(main / "_journal.json", {})
    write(main / "_audit-trail.md", "\n".join([
        json.dumps({"event": "refused", "error": "SECRET"}), json.dumps({"event": "refused"}),
        json.dumps({"event": "degraded"}), json.dumps({"event": "created"}), "not json", json.dumps([1]), ""]))
    write(main / "build" / "verdict_a.json", {"verdict": "revise"})
    write(main / "build" / "verdict_b.json", {"decision": "PASS"})
    write(main / "build" / "verdict_bad.json", "not json")
    write(main / "build" / "verdict_text.json", '"just a string"')
    write(main / "review" / "verdict_c.json", {"decision": "BLOCKED"})
    write(main / "notes.md", "skipped")
    nostate = saves / "runs" / "r-nostate"
    write(nostate / "_state.md", "- a\n- b\n")
    badstatus = saves / "runs" / "r-badstatus"
    write(badstatus / "_state.md", {"status": "weird", "revision": 1})
    write(badstatus / "_lock.md", {"status": "held", "revision": 1})
    done = saves / "runs" / "r-done"
    write(done / "_state.md", {"status": "complete", "revision": 3})
    write(done / "_lock.md", {"status": "released", "revision": 3})
    write(done / "_audit-trail.md", "X" * 300 + "\n" + json.dumps({"event": "rollback"}) + "\n")
    write(harness / "guard-state.json", {
        "frozen_globs": ["docs/**", {"glob": "src/**"}, {"glob": "old/**", "released_at": "2026-01-01T00:00:00Z"}],
        "blocked_globs": [{"glob": "secrets/**"}], "read_only": [{"run_id": "r-main", "allow": ["x/**"]}], "allow_dangerous": {}})
    write(harness / "observations" / "PreToolUse.json", {"observed": {"count": 7}})
    write(harness / "observations" / "PostToolUse.json", [1])
    write(harness / "observations" / "UserPromptSubmit.json", "not json")
    write(harness / "trajectories" / "sess-a.json", [
        {"sig": "s1", "failed": True, "empty": False}, {"sig": "s1", "failed": True, "empty": True},
        {"sig": "s2", "failed": False, "empty": True}, "junk"])
    write(harness / "trajectories" / "sess-b.json", {"x": 1})
    write(harness / "trajectories" / "notes.txt", "skipped")


def canonical(report: dict) -> dict:
    """The report with ``record_errors`` in a fixed order: a directory listing's order is the file system's, not the audit's."""
    return {**report, "record_errors": sorted(report["record_errors"], key=lambda item: json.dumps(item, sort_keys=True))}


def full_report(root: Path) -> dict:
    with patch.object(subject, "MAX_AUDIT_TAIL", 120):
        return subject.audit(root)


class Project(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def codes(self, scan) -> list:
        return [item["code"] for item in scan.findings]

    def finding(self, scan, code: str) -> dict:
        return next(item for item in scan.findings if item["code"] == code)


class GoldenReportTests(Project):
    def test_the_report_on_a_fixture_touching_every_class_is_unchanged(self):
        build_everything(self.root)
        report = canonical(full_report(self.root))
        self.assertEqual(json.dumps(report), json.dumps(GOLDEN))

    def test_the_report_on_an_empty_project_is_unchanged(self):
        self.assertEqual(json.dumps(subject.audit(self.root)), json.dumps(GOLDEN_EMPTY))


class RootsTests(Project):
    def test_a_project_with_neither_root_reports_both_as_info(self):
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        self.assertEqual(self.codes(scan), ["save_root_missing", "harness_root_missing"])
        self.assertEqual({item["severity"] for item in scan.findings}, {"Info"})
        self.assertFalse(scan.saves_ok)
        self.assertFalse(scan.harness_ok)

    def test_a_root_that_is_a_link_counts_as_missing(self):
        target = self.root / "elsewhere"
        target.mkdir()
        try:
            (self.root / "skillset-saves").symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        (self.root / ".harness-state").mkdir()
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        self.assertEqual(self.codes(scan), ["save_root_missing"])
        self.assertTrue(scan.harness_ok)

    def test_both_roots_present_report_nothing(self):
        (self.root / "skillset-saves").mkdir()
        (self.root / ".harness-state").mkdir()
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        self.assertEqual(scan.findings, [])


class PointerTests(Project):
    def scan_pointer(self, text=None, *, runs=()):
        saves = self.root / "skillset-saves"
        (self.root / ".harness-state").mkdir(exist_ok=True)
        (saves / "runs").mkdir(parents=True, exist_ok=True)
        for name in runs:
            (saves / "runs" / name).mkdir(exist_ok=True)
        if text is not None:
            write(saves / "_latest.md", text)
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_pointer(scan)
        return scan

    def test_no_pointer_is_not_a_finding(self):
        scan = self.scan_pointer(runs=("r1",))
        self.assertEqual(scan.findings, [])
        self.assertIsNone(scan.pointer_id)

    def test_a_pointer_that_cannot_be_read_names_the_reason_only(self):
        scan = self.scan_pointer("- a\n- b\n")
        self.assertEqual(self.finding(scan, "pointer_unreadable"), {"code": "pointer_unreadable", "severity": "Major", "reason": "wrong_shape"})
        with patch.object(subject, "MAX_RECORD", 5):
            scan = self.scan_pointer('{"run_id": "r1"}')
        self.assertEqual(self.finding(scan, "pointer_unreadable")["reason"], "too_large")

    def test_a_run_id_that_is_not_a_plain_name_is_dropped_and_reported(self):
        for value in ("../outside", "a/b", "..", ".", 5, ["r1"]):
            with self.subTest(value=value):
                scan = self.scan_pointer({"run_id": value}, runs=("r1",))
                self.assertEqual(self.finding(scan, "pointer_run_id_invalid"), {"code": "pointer_run_id_invalid", "severity": "Major", "count": 1})
                self.assertIsNone(scan.pointer_id)
                self.assertNotIn("pointer_target_missing", self.codes(scan))

    def test_a_valid_pointer_is_kept(self):
        scan = self.scan_pointer({"run_id": "r1"}, runs=("r1",))
        self.assertEqual(scan.pointer_id, "r1")
        self.assertEqual(scan.findings, [])

    def test_a_pointer_to_a_run_that_does_not_exist_is_major(self):
        scan = self.scan_pointer({"run_id": "ghost"}, runs=("r1",))
        self.assertEqual(self.finding(scan, "pointer_target_missing"), {"code": "pointer_target_missing", "severity": "Major", "count": 1})

    def test_a_truncated_run_listing_cannot_prove_the_target_missing(self):
        with patch.object(subject, "MAX_RUNS", 1):
            scan = self.scan_pointer({"run_id": "zzz"}, runs=("a", "b"))
        self.assertIn("run_scan_truncated", self.codes(scan))
        self.assertNotIn("pointer_target_missing", self.codes(scan))
        self.assertTrue(scan.coverage["runs_truncated"])
        self.assertEqual(self.finding(scan, "run_scan_truncated")["severity"], "Info")

    def test_the_run_list_is_sorted_and_bounded(self):
        with patch.object(subject, "MAX_RUNS", 2):
            scan = self.scan_pointer({"run_id": "a"}, runs=("c", "b", "a"))
        self.assertEqual(len(scan.run_dirs), 2)
        self.assertEqual([p.name for p in scan.run_dirs], sorted(p.name for p in scan.run_dirs))


class RunTests(Project):
    def scan_runs(self, **runs):
        saves = self.root / "skillset-saves"
        (saves / "runs").mkdir(parents=True, exist_ok=True)
        for name, files in runs.items():
            (saves / "runs" / name).mkdir(exist_ok=True)
            for rel, value in files.items():
                write(saves / "runs" / name / rel, value)
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_pointer(scan)
        subject._audit_runs(scan)
        return scan

    def test_state_and_lock_revisions_that_disagree_are_major_for_that_run_only(self):
        scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 2}},
                              b={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1}})
        mismatches = [f for f in scan.findings if f["code"] == "revision_mismatch"]
        self.assertEqual(mismatches, [{"code": "revision_mismatch", "severity": "Major", "run": subject._id("a")}])
        self.assertEqual(dict(scan.run_statuses), {"active": 2})

    def test_a_status_outside_the_save_taxonomy_is_counted_as_unreadable(self):
        scan = self.scan_runs(a={"_state.md": {"status": "weird"}, "_lock.md": {"revision": 1}})
        self.assertEqual(scan.unreadable["state:invalid_status"], 1)
        self.assertEqual(dict(scan.run_statuses), {})

    def test_a_missing_or_wrong_shaped_record_is_noted_with_the_hashed_run(self):
        scan = self.scan_runs(a={"_state.md": "- a\n- b\n"})
        self.assertEqual(scan.record_errors, [{"record": "state", "reason": "wrong_shape", "run": subject._id("a")},
                                              {"record": "lock", "reason": "missing_or_symlink", "run": subject._id("a")},
                                              {"record": "audit", "reason": "missing_or_symlink", "run": subject._id("a")}])

    def test_a_publish_journal_is_major_and_counted(self):
        scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1}, "_journal.json": {}})
        self.assertEqual(self.finding(scan, "publish_journal_present"), {"code": "publish_journal_present", "severity": "Major", "run": subject._id("a")})
        self.assertEqual(scan.journal_count, 1)
        self.assertEqual(scan.run_history, [{"run": subject._id("a"), "publish_journal": True}])

    def test_only_failure_shaped_audit_events_are_counted_and_bad_lines_are_noted(self):
        trail = "\n".join([json.dumps({"event": "refused"}), json.dumps({"event": "created"}), json.dumps({"event": "rollback"}),
                           "garbage", json.dumps([1]), json.dumps({"event": 7}), ""])
        scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1}, "_audit-trail.md": trail})
        self.assertEqual(dict(scan.audit_events), {"refused": 1, "rollback": 1})
        self.assertEqual(scan.unreadable["audit:invalid_line"], 2)
        self.assertEqual(scan.run_history, [{"run": subject._id("a"), "audit_events": {"refused": 1, "rollback": 1}}])

    def test_an_oversized_audit_trail_is_read_from_its_tail_and_reported(self):
        trail = "X" * 400 + "\n" + json.dumps({"event": "degraded"}) + "\n"
        with patch.object(subject, "MAX_AUDIT_TAIL", 100):
            scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1}, "_audit-trail.md": trail})
        self.assertEqual(scan.truncated_audit_tails, 1)
        self.assertEqual(dict(scan.audit_events), {"degraded": 1})

    def test_failing_verdicts_are_counted_by_name_and_other_verdicts_are_not(self):
        files = {"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1},
                 "build/verdict_a.json": {"verdict": "revise"}, "build/verdict_b.json": {"decision": "PASS"},
                 "review/verdict_c.json": {"decision": "BLOCKED"}, "build/other.json": {"verdict": "FAIL"},
                 "build/verdict_d.md": {"verdict": "FAIL"}}
        scan = self.scan_runs(a=files)
        self.assertEqual(dict(scan.verdicts), {"REVISE": 1, "BLOCKED": 1})
        self.assertEqual(scan.run_history, [{"run": subject._id("a"), "gate_verdicts": {"BLOCKED": 1, "REVISE": 1}}])

    def test_an_unreadable_verdict_is_noted_not_counted(self):
        scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1},
                                 "build/verdict_a.json": "not json", "build/verdict_b.json": '"text"'})
        reasons = sorted(item["reason"] for item in scan.record_errors if item["record"] == "verdict")
        self.assertEqual(reasons, ["unreadable_or_invalid", "wrong_shape"])
        self.assertEqual(dict(scan.verdicts), {})

    def test_a_run_without_findings_leaves_no_history_entry(self):
        scan = self.scan_runs(a={"_state.md": {"status": "complete", "revision": 1}, "_lock.md": {"revision": 1}})
        self.assertEqual(scan.run_history, [])
        self.assertEqual(scan.coverage["runs_scanned"], 1)

    def test_an_exhausted_time_budget_stops_the_run_loop_and_says_so(self):
        scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}, "_lock.md": {"revision": 1}})
        self.assertEqual(scan.coverage["runs_scanned"], 1)
        scan.coverage["runs_scanned"] = 0
        scan.deadline = time.monotonic() - 1
        subject._audit_runs(scan)
        self.assertTrue(scan.coverage["time_truncated"])
        self.assertEqual(scan.coverage["runs_scanned"], 0)

    def test_an_exhausted_budget_cuts_the_run_listing_itself(self):
        with patch.object(subject, "AUDIT_TIME_BUDGET_SECONDS", -1.0):
            scan = self.scan_runs(a={"_state.md": {"status": "active", "revision": 1}})
        self.assertEqual(scan.run_dirs, [])
        self.assertTrue(scan.coverage["runs_truncated"])

    def test_record_errors_are_capped_and_the_cap_is_reported(self):
        runs = {f"r{index:03d}": {"_state.md": "- a\n- b\n"} for index in range(12)}
        with patch.object(subject, "MAX_FILES", 5):
            scan = self.scan_runs(**runs)
        self.assertEqual(len(scan.record_errors), 5)
        self.assertTrue(scan.coverage["record_errors_truncated"])
        self.assertEqual(scan.unreadable["state:wrong_shape"], 5)


class GuardTests(Project):
    def scan_guard(self, value=None, *, text=None):
        (self.root / ".harness-state").mkdir(exist_ok=True)
        if value is not None or text is not None:
            write(self.root / ".harness-state" / "guard-state.json", value if text is None else text)
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_guard(scan)
        return scan

    def test_active_entries_are_counted_per_key_and_released_ones_are_not(self):
        scan = self.scan_guard({
            "frozen_globs": ["a/**", {"glob": "b/**"}, {"glob": "c/**", "released_at": "2026-01-01T00:00:00Z"}, 5],
            "blocked_globs": [{"glob": "d/**", "released": True}],
            "read_only": [{"run_id": "r"}], "allow_dangerous": {"owner": "x"}})
        self.assertEqual(scan.guard_summary, {"frozen_globs": 2, "blocked_globs": 0, "read_only": 1})

    def test_the_summary_follows_the_one_released_predicate(self):
        scan = self.scan_guard({"blocked_globs": [{"glob": "d/**", "released": True}, {"glob": "e/**"}]})
        self.assertEqual(scan.guard_summary, {"blocked_globs": 1})

    def test_a_damaged_record_is_noted_never_echoed(self):
        scan = self.scan_guard(text="{not json")
        self.assertEqual(scan.record_errors, [{"record": "guard", "reason": "unreadable_or_invalid"}])
        self.assertEqual(scan.guard_summary, {})
        scan = self.scan_guard(text="[1]")
        self.assertEqual(scan.record_errors, [{"record": "guard", "reason": "wrong_shape"}])

    def test_no_record_and_no_harness_root_are_silent(self):
        self.assertEqual(self.scan_guard().record_errors, [])
        scan = subject.AuditScan(self.root / "nowhere")
        subject._audit_roots(scan)
        subject._audit_guard(scan)
        self.assertEqual(scan.guard_summary, {})


class ObservationTests(Project):
    def scan_observations(self, files=None):
        directory = self.root / ".harness-state" / "observations"
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in (files or {}).items():
            write(directory / name, value)
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_observations(scan)
        return scan

    def test_counts_are_read_per_event_and_clamped_at_zero(self):
        scan = self.scan_observations({"PreToolUse.json": {"observed": {"count": 7}}, "PostToolUse.json": {"observed": {"count": -4}},
                                       "UserPromptSubmit.json": {"observed": {"count": "x"}}})
        self.assertEqual(scan.observation_counts, {"PreToolUse": 7, "PostToolUse": 0})

    def test_a_damaged_observation_is_noted(self):
        scan = self.scan_observations({"PreToolUse.json": "not json", "PostToolUse.json": [1]})
        self.assertEqual(scan.record_errors, [{"record": "observation", "reason": "unreadable_or_invalid"},
                                              {"record": "observation", "reason": "wrong_shape"}])

    def test_a_linked_observation_directory_is_major_and_not_followed(self):
        harness = self.root / ".harness-state"
        elsewhere = self.root / "elsewhere"
        write(elsewhere / "PreToolUse.json", {"observed": {"count": 9}})
        harness.mkdir()
        try:
            (harness / "observations").symlink_to(elsewhere, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_observations(scan)
        self.assertEqual(self.finding(scan, "observation_root_symlink"), {"code": "observation_root_symlink", "severity": "Major", "count": 1})
        self.assertEqual(scan.observation_counts, {})

    def test_the_fault_counters_are_not_part_of_the_report(self):
        scan = self.scan_observations({"PreToolUse.json": {"observed": {"count": 2}, "faults": 3, "last_fault": {"type": "X", "at": "t"}}})
        self.assertEqual(scan.observation_counts, {"PreToolUse": 2})


class TrajectoryTests(Project):
    def scan_trajectories(self, files=None):
        directory = self.root / ".harness-state" / "trajectories"
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in (files or {}).items():
            write(directory / name, value)
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_trajectories(scan)
        return scan

    def test_failed_empty_and_repeated_steps_are_counted_per_file_and_in_total(self):
        scan = self.scan_trajectories({"a.json": [
            {"sig": "x", "failed": True}, {"sig": "x", "failed": True, "empty": True}, {"sig": "y", "failed": False, "empty": True}, "junk"]})
        self.assertEqual((scan.failed_steps, scan.empty_steps, scan.repeated_failures), (2, 2, 1))
        self.assertEqual(scan.trajectory_history, [{"run": subject._id("trajectories"), "trajectory": subject._id("a.json"),
                                                    "failed_steps": 2, "empty_steps": 2, "consecutive_failed_signatures": 1}])

    def test_a_file_with_no_failure_leaves_no_history(self):
        scan = self.scan_trajectories({"a.json": [{"sig": "x", "failed": False, "empty": True}]})
        self.assertEqual(scan.trajectory_history, [])
        self.assertEqual(scan.empty_steps, 1)

    def test_only_the_last_forty_steps_of_a_file_are_read(self):
        steps = [{"sig": "x", "failed": True}] * 60
        scan = self.scan_trajectories({"a.json": steps})
        self.assertEqual(scan.failed_steps, 40)

    def test_a_damaged_file_is_noted_and_other_suffixes_are_skipped(self):
        scan = self.scan_trajectories({"a.json": {"x": 1}, "b.json": "not json", "c.txt": "skipped"})
        self.assertEqual(sorted(item["reason"] for item in scan.record_errors), ["unreadable_or_invalid", "wrong_shape"])
        self.assertTrue(all(item["record"] == "trajectory" for item in scan.record_errors))
        self.assertEqual(scan.coverage["trajectory_files_scanned"], 3)

    def test_a_trajectory_listing_cut_short_is_reported(self):
        with patch.object(subject, "MAX_TRAJECTORIES", 1):
            scan = self.scan_trajectories({"a.json": [], "b.json": []})
        self.assertTrue(scan.trajectories_truncated)
        self.assertEqual(scan.coverage["trajectories_truncated"], True)

    def test_without_a_harness_root_nothing_is_scanned(self):
        scan = subject.AuditScan(self.root)
        subject._audit_roots(scan)
        subject._audit_trajectories(scan)
        self.assertEqual(scan.coverage["trajectory_files_scanned"], 0)


class AssemblyTests(Project):
    def finish(self, scan):
        return subject._assemble(scan)

    def test_a_clean_scan_reports_no_finding_and_the_fixed_envelope(self):
        report = self.finish(subject.AuditScan(self.root))
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["kind"], "supremeteam-audit-improve")
        self.assertIs(report["read_only"], True)
        self.assertEqual(list(report), ["schema_version", "kind", "read_only", "coverage", "run_statuses", "guard_state", "hook_observations",
                                        "run_history", "trajectory_history", "record_errors", "findings", "handoff"])

    def test_the_time_budget_finding_follows_the_coverage_flag(self):
        scan = subject.AuditScan(self.root)
        scan.coverage["time_truncated"] = True
        self.assertIn("audit_time_truncated", [f["code"] for f in self.finish(scan)["findings"]])
        with patch.object(subject, "AUDIT_TIME_BUDGET_SECONDS", -1.0):
            scan = subject.AuditScan(self.root)
        report = self.finish(scan)
        self.assertTrue(report["coverage"]["time_truncated"])
        self.assertIn("audit_time_truncated", [f["code"] for f in report["findings"]])

    def test_trajectory_truncation_and_unreadable_records_become_findings_in_order(self):
        scan = subject.AuditScan(self.root)
        scan.trajectories_truncated = True
        scan.unreadable["state:too_large"] += 2
        scan.failed_steps = 1
        scan.journal_count = 1
        scan.truncated_audit_tails = 3
        codes = [f["code"] for f in self.finish(scan)["findings"]]
        self.assertEqual(codes, ["trajectory_scan_truncated", "unreadable_records", "failure_history", "audit_tail_truncated"])

    def test_failure_history_carries_every_counter(self):
        scan = subject.AuditScan(self.root)
        scan.audit_events["refused"] += 2
        scan.verdicts["REVISE"] += 1
        scan.failed_steps, scan.empty_steps, scan.repeated_failures = 4, 2, 1
        history = next(f for f in self.finish(scan)["findings"] if f["code"] == "failure_history")
        self.assertEqual(history, {"code": "failure_history", "severity": "Info", "audit_events": {"refused": 2}, "gate_verdicts": {"REVISE": 1},
                                   "failed_steps": 4, "empty_steps": 2, "consecutive_failed_signatures": 1})

    def test_publish_journals_and_truncated_tails_reach_coverage(self):
        scan = subject.AuditScan(self.root)
        scan.journal_count = 2
        scan.truncated_audit_tails = 1
        report = self.finish(scan)
        self.assertEqual(report["coverage"]["publish_journals"], 2)
        self.assertEqual(report["coverage"]["audit_tails_truncated"], 1)

    def test_audit_runs_the_parts_in_the_documented_order(self):
        calls = []
        names = ("_audit_roots", "_audit_pointer", "_audit_runs", "_audit_guard", "_audit_observations", "_audit_trajectories")
        patches = [patch.object(subject, name, lambda scan, name=name: calls.append(name)) for name in names]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        subject.audit(self.root)
        self.assertEqual(calls, list(names))


GOLDEN = json.loads(r"""
{
 "schema_version": 1,
 "kind": "supremeteam-audit-improve",
 "read_only": true,
 "coverage": {
  "run_limit": 24,
  "phase_file_limit_per_run": 80,
  "trajectory_file_limit": 80,
  "record_byte_limit": 262144,
  "time_budget_seconds": 2.0,
  "runs_scanned": 4,
  "runs_truncated": false,
  "trajectory_files_scanned": 3,
  "trajectories_truncated": false,
  "publish_journals": 1,
  "audit_tails_truncated": 1
 },
 "run_statuses": {
  "active": 1,
  "complete": 1
 },
 "guard_state": {
  "frozen_globs": 2,
  "blocked_globs": 1,
  "read_only": 1
 },
 "hook_observations": {
  "PreToolUse": 7
 },
 "run_history": [
  {
   "run": "78b58a8aaaea",
   "audit_events": {
    "rollback": 1
   }
  },
  {
   "run": "bb4e3b156e99",
   "publish_journal": true,
   "audit_events": {
    "degraded": 1,
    "refused": 2
   },
   "gate_verdicts": {
    "BLOCKED": 1,
    "REVISE": 1
   }
  }
 ],
 "trajectory_history": [
  {
   "run": "f2b202672903",
   "trajectory": "1b90b16f00fc",
   "failed_steps": 2,
   "empty_steps": 2,
   "consecutive_failed_signatures": 1
  }
 ],
 "record_errors": [
  {
   "record": "audit",
   "reason": "invalid_line",
   "run": "bb4e3b156e99"
  },
  {
   "record": "audit",
   "reason": "invalid_line",
   "run": "bb4e3b156e99"
  },
  {
   "record": "audit",
   "reason": "missing_or_symlink",
   "run": "da23be19d5e5"
  },
  {
   "record": "audit",
   "reason": "missing_or_symlink",
   "run": "f4c54e3fb304"
  },
  {
   "record": "lock",
   "reason": "missing_or_symlink",
   "run": "f4c54e3fb304"
  },
  {
   "record": "observation",
   "reason": "unreadable_or_invalid"
  },
  {
   "record": "verdict",
   "reason": "unreadable_or_invalid",
   "run": "bb4e3b156e99"
  },
  {
   "record": "observation",
   "reason": "wrong_shape"
  },
  {
   "record": "state",
   "reason": "wrong_shape",
   "run": "f4c54e3fb304"
  },
  {
   "record": "trajectory",
   "reason": "wrong_shape",
   "run": "f2b202672903",
   "trajectory": "7c100e51ac90"
  },
  {
   "record": "verdict",
   "reason": "wrong_shape",
   "run": "bb4e3b156e99"
  }
 ],
 "findings": [
  {
   "code": "revision_mismatch",
   "severity": "Major",
   "run": "bb4e3b156e99"
  },
  {
   "code": "publish_journal_present",
   "severity": "Major",
   "run": "bb4e3b156e99"
  },
  {
   "code": "unreadable_records",
   "severity": "Major",
   "counts": {
    "audit:invalid_line": 2,
    "audit:missing_or_symlink": 2,
    "lock:missing_or_symlink": 1,
    "observation:unreadable_or_invalid": 1,
    "observation:wrong_shape": 1,
    "state:invalid_status": 1,
    "state:wrong_shape": 1,
    "trajectory:wrong_shape": 1,
    "verdict:unreadable_or_invalid": 1,
    "verdict:wrong_shape": 1
   }
  },
  {
   "code": "failure_history",
   "severity": "Info",
   "audit_events": {
    "degraded": 1,
    "refused": 2,
    "rollback": 1
   },
   "gate_verdicts": {
    "BLOCKED": 1,
    "REVISE": 1
   },
   "failed_steps": 2,
   "empty_steps": 2,
   "consecutive_failed_signatures": 1
  },
  {
   "code": "audit_tail_truncated",
   "severity": "Info",
   "count": 1
  }
 ],
 "handoff": "The read-only audit may run directly. Correlate these counts with source and run evidence. Route a supported improvement through admiral and skill-maker for a reviewed proposal. Do not infer a defective skill from a count alone or mutate saved state from this report."
}
""")
GOLDEN_EMPTY = json.loads(r"""
{
 "schema_version": 1,
 "kind": "supremeteam-audit-improve",
 "read_only": true,
 "coverage": {
  "run_limit": 24,
  "phase_file_limit_per_run": 80,
  "trajectory_file_limit": 80,
  "record_byte_limit": 262144,
  "time_budget_seconds": 2.0,
  "runs_scanned": 0,
  "runs_truncated": false,
  "trajectory_files_scanned": 0,
  "trajectories_truncated": false
 },
 "run_statuses": {},
 "guard_state": {},
 "hook_observations": {},
 "run_history": [],
 "trajectory_history": [],
 "record_errors": [],
 "findings": [
  {
   "code": "save_root_missing",
   "severity": "Info",
   "count": 1
  },
  {
   "code": "harness_root_missing",
   "severity": "Info",
   "count": 1
  }
 ],
 "handoff": "The read-only audit may run directly. Correlate these counts with source and run evidence. Route a supported improvement through admiral and skill-maker for a reviewed proposal. Do not infer a defective skill from a count alone or mutate saved state from this report."
}
""")


if __name__ == "__main__":
    unittest.main()
