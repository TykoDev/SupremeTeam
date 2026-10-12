#!/usr/bin/env python3
"""Gate packages are checked by hooks as well as at the gate.

Rule C keeps a verdict record single-writer: only ``check.py --verdict-out`` writes
``verdict_<boundary>[.cross-stage].json``, so the APPROVED a later boundary's
revision_ref binds to was produced by the checks, never typed by hand. The
gatekeeper's judgment draft stays writable. ``gate_watch`` re-runs check.py when a
run manifest or intake log changes and reports what fails, once per change.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
sys.path.insert(0, str(HOOKS))
import _testkit as tk  # noqa: E402

VERDICT = "skillset-saves/runs/r1/design/verdict_design-to-build.json"
CROSS = "skillset-saves/runs/r1/design/verdict_design-to-build.cross-stage.json"
DRAFT = "skillset-saves/runs/r1/design/verdict_design-to-build.judgment.json"
CHECK = "python skills/harness/gatekeeper/check.py --boundary design-to-build --package skillset-saves/runs/r1/design/manifest.json"


class Project(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / ".git").mkdir()
        (self.root / "skillset-saves" / "runs" / "r1" / "design").mkdir(parents=True)
        (self.root / "skillset-saves" / "runs" / "r1" / "intake").mkdir(parents=True)


class VerdictWriterTests(Project):
    def test_a_verdict_record_is_never_written_by_hand(self):
        for payload in (tk.edit(str(self.root / VERDICT)), tk.edit(str(self.root / CROSS), tool="Edit"),
                        tk.bash(f"echo '{{}}' > {VERDICT}"), tk.bash(f"cp /tmp/approved.json {CROSS}"),
                        tk.bash(f"sed -i s/REVISE/APPROVED/ {VERDICT}"), tk.bash(f"rm {CROSS}")):
            with self.subTest(payload=payload["tool_input"]):
                out = tk.decide(payload, self.root)
                self.assertTrue(tk.denied(out), out)
                self.assertIn("check.py --verdict-out", tk.reason(out))

    def test_check_py_and_the_judgment_draft_remain_the_way_in(self):
        for payload in (tk.edit(str(self.root / DRAFT)),
                        tk.bash(f"{CHECK} --verdict-out {VERDICT}"),
                        tk.bash(f"{CHECK} --judgment {DRAFT} --verdict-out {CROSS}"),
                        tk.edit(str(self.root / "skillset-saves/runs/r1/design/manifest.json"))):
            with self.subTest(payload=payload["tool_input"]):
                self.assertFalse(tk.denied(tk.decide(payload, self.root)))


class GateWatchTests(Project):
    def setUp(self):
        super().setUp()
        saved = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        self.addCleanup(lambda: os.environ.__setitem__("CLAUDE_PROJECT_DIR", saved) if saved is not None
                        else os.environ.pop("CLAUDE_PROJECT_DIR", None))
        import gate_watch
        self.watch = gate_watch

    def manifest(self, data: dict) -> Path:
        path = self.root / "skillset-saves/runs/r1/design/manifest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_a_failing_manifest_is_reported_once_per_change(self):
        path = self.manifest({"schema_version": 2, "boundary": "design-to-build", "owner": "commander",
                              "run_id": "r1", "revision": "r1", "revisions": ["r1"], "evidence": {}})
        hint = self.watch.advisory(self.root)
        self.assertIsNotNone(hint)
        self.assertIn("skillset-saves/runs/r1/design/manifest.json fails check.py", hint)
        self.assertIn("missing evidence", hint)
        self.assertIsNone(self.watch.advisory(self.root), "an unchanged manifest is not re-checked")
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 10**9))
        self.assertIsNotNone(self.watch.advisory(self.root), "a changed manifest is checked again")

    def test_a_manifest_without_a_boundary_is_named(self):
        self.manifest({"evidence": {}})
        self.assertIn("declares no boundary", self.watch.advisory(self.root) or "")

    def test_an_intake_log_is_checked_against_the_decision_tables(self):
        log = self.root / "skillset-saves/runs/r1/intake/report_grilling.md"
        log.write_text("# Grilling\n\nResolved: ship it.\n", encoding="utf-8")
        hint = self.watch.advisory(self.root) or ""
        self.assertIn("report_grilling.md fails check.py", hint)
        self.assertIn("lacks the section 'Resolved decisions'", hint)

    def test_a_passing_intake_log_is_silent(self):
        sys.path.insert(0, str(HOOKS.parent / "gatekeeper"))
        import _fixtures
        log = self.root / "skillset-saves/runs/r1/intake/report_grilling.md"
        log.write_text(_fixtures.source_of_truth("src/app.py"), encoding="utf-8")
        self.assertIsNone(self.watch.advisory(self.root))

    def test_the_post_tool_hook_carries_the_hint(self):
        self.manifest({"schema_version": 2, "boundary": "design-to-build", "evidence": {}})
        out = tk.decide({"tool_name": "Write", "tool_input": {"file_path": "x"}, "tool_response": "ok"},
                        self.root, module="post_tool_use", entry="run")
        self.assertIn("[harness:gate-watch]", out)

    def test_the_watch_is_bounded(self):
        for index in range(self.watch.CHECK_CAP + 2):
            phase = self.root / f"skillset-saves/runs/r1/p{index}"
            phase.mkdir()
            (phase / "manifest.json").write_text("{}", encoding="utf-8")
        first = self.watch.advisory(self.root) or ""
        self.assertEqual(first.count("declares no boundary"), self.watch.CHECK_CAP)
        self.assertEqual((self.watch.advisory(self.root) or "").count("declares no boundary"), 2)


if __name__ == "__main__":
    unittest.main()
