"""Contract tests for the standard-library Taste preference writer."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("taste_prefs.py")


class TastePreferencesTests(unittest.TestCase):
    def setUp(self):
        project_tmp = tempfile.TemporaryDirectory(); global_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup); self.addCleanup(global_tmp.cleanup)
        self.project, self.global_home = Path(project_tmp.name), Path(global_tmp.name)
        self.env = {**os.environ, "SUPREMETEAM_HOME": str(self.global_home), "SUPREMETEAM_OWNER": "test-owner"}

    def run_cli(self, *args: str) -> tuple[int, dict]:
        process = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(self.project), *args], text=True, capture_output=True, env=self.env)
        return process.returncode, json.loads(process.stdout)

    def test_project_lifecycle_history_and_stale_writer(self):
        code, result = self.run_cli("set", "--scope", "project", "--id", "ui.density", "--value", '"compact"')
        self.assertEqual(code, 0, result)
        record = json.loads((self.project / "skillset-saves/preferences/taste.json").read_text())
        self.assertEqual(record["revision"], 1); self.assertEqual(record["entries"]["ui.density"]["state"], "active")
        code, result = self.run_cli("deprecate", "--scope", "project", "--expect-revision", "0", "--id", "ui.density")
        self.assertEqual(code, 1); self.assertEqual(result["error"]["code"], "stale_revision")
        code, result = self.run_cli("revoke", "--scope", "project", "--expect-revision", "1", "--id", "ui.density")
        self.assertEqual(code, 0, result)
        record = json.loads((self.project / "skillset-saves/preferences/taste.json").read_text())
        self.assertIn("ui.density", record["tombstones"])
        self.assertEqual(len(list((self.project / "skillset-saves/preferences/_history").glob("*.json"))), 1)

    def test_both_writes_and_effective_project_override(self):
        code, result = self.run_cli("set", "--scope", "both", "--id", "format.style", "--value", '"brief"')
        self.assertEqual(code, 0, result)
        self.assertTrue((self.project / "skillset-saves/preferences/taste.md").exists())
        self.assertTrue((self.global_home / "preferences/taste.json").exists())
        code, result = self.run_cli("effective")
        self.assertEqual(code, 0); self.assertEqual(result["entries"]["format.style"]["source_scope"], "project")

    def test_sensitive_values_rejected_or_redacted_and_corruption_preserved(self):
        code, result = self.run_cli("set", "--scope", "project", "--id", "unsafe", "--value", '"person@example.com"')
        self.assertEqual(code, 1); self.assertEqual(result["error"]["code"], "sensitive_input")
        code, result = self.run_cli("set", "--scope", "project", "--redact", "--id", "safe", "--value", '"person@example.com"')
        self.assertEqual(code, 0, result)
        target = self.project / "skillset-saves/preferences/taste.json"
        target.write_bytes(b"not-json\x00recovery")
        code, result = self.run_cli("reset", "--scope", "project", "--expect-revision", "1")
        self.assertEqual(code, 1); self.assertEqual(result["error"]["code"], "corrupt_record")
        self.assertEqual(target.read_bytes(), b"not-json\x00recovery")


if __name__ == "__main__":
    unittest.main()
