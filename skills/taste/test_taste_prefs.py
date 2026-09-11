import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import taste_prefs

SCRIPT = Path(__file__).with_name("taste_prefs.py")

class TasteWriterTests(unittest.TestCase):
    def test_atomic_upsert_and_project_override_resolution(self):
        global_record = taste_prefs.upsert(taste_prefs.blank_record("global"), {"id": "density", "value": "roomy", "kind": "preference", "source": "explicit"})
        project_record = taste_prefs.upsert(taste_prefs.blank_record("project"), {"id": "density", "value": "compact", "kind": "preference", "source": "explicit"})
        resolved = taste_prefs.resolve(global_record, project_record)
        self.assertEqual(resolved["preferences"][0]["value"], "compact")
        self.assertEqual(resolved["preferences"][0]["effective_scope"], "project")

    def test_validation_rejects_duplicate_ids(self):
        record = taste_prefs.blank_record("global")
        item = {"id": "tone", "value": "direct"}
        record["preferences"] = [item, item]
        with self.assertRaisesRegex(taste_prefs.PreferenceError, "duplicate"):
            taste_prefs.validate_record(record)

    def test_inferred_write_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), "upsert", "--scope", "project", "--id", "tone", "--value", "direct", "--source", "inferred", "--project-root", directory], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("requires --confirm", result.stderr)
            self.assertFalse((Path(directory) / "skillset-saves/preferences/taste.md").exists())

    def test_promote_requires_confirmation_then_writes_global(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            global_file = root / "global.json"
            project_file = root / "project.json"
            taste_prefs.atomic_write(project_file, taste_prefs.upsert(taste_prefs.blank_record("project"), {"id": "tone", "value": "direct", "kind": "preference", "source": "explicit"}))
            base = [sys.executable, str(SCRIPT), "promote", "--id", "tone", "--global-file", str(global_file), "--project-file", str(project_file)]
            self.assertEqual(subprocess.run(base, capture_output=True).returncode, 2)
            self.assertEqual(subprocess.run(base + ["--confirm"], capture_output=True).returncode, 0)
            self.assertEqual(json.loads(global_file.read_text())["preferences"][0]["id"], "tone")

    def test_bulk_revoke_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(SCRIPT), "revoke", "--scope", "project", "--id", "one", "--id", "two", "--project-root", directory], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("bulk revocation requires --confirm", result.stderr)

    def test_global_reset_and_import_require_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            global_file = root / "global.json"
            for operation in (["reset", "--scope", "global"], ["import", "--scope", "global", "--input", str(root / "missing.json")]):
                result = subprocess.run([sys.executable, str(SCRIPT), *operation, "--global-file", str(global_file), "--project-file", str(root / "project.json")], text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("requires --confirm", result.stderr)

if __name__ == "__main__":
    unittest.main()
