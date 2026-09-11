#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
import sys
import threading
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taste_prefs as tp  # noqa: E402


class TastePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.project_tmp = tempfile.TemporaryDirectory()
        self.home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.project_tmp.cleanup)
        self.addCleanup(self.home_tmp.cleanup)
        self.project, self.home = Path(self.project_tmp.name), Path(self.home_tmp.name)
        self.store = tp.TasteStore(self.project, home=self.home)

    def pref(self, key="color", value="blue", **extra):
        return {"key": key, "value": value, **extra}

    def test_new_project_and_isolated_global_store_creation(self):
        self.store.load("project", create=True)
        self.store.load("global", create=True)
        self.assertTrue((self.project / tp.PROJECT_RELATIVE).is_file())
        self.assertTrue((self.home / tp.GLOBAL_RELATIVE).is_file())

    def test_both_write_and_failure_rolls_back_with_record(self):
        evidence = self.project / "skillset-saves/runs/r1/preferences"
        result = self.store.write_both([self.pref()], [self.pref("font", "mono")],
                                       expected_project_revision=0, expected_global_revision=0,
                                       confirm=True, evidence_dir=evidence)
        self.assertEqual(result["project"]["revision"], 1)
        before = self.store.load("project")
        with self.assertRaises(RuntimeError):
            self.store.write_both([self.pref(value="red")], [self.pref("font", "sans")],
                                  expected_project_revision=1, expected_global_revision=1,
                                  confirm=True, evidence_dir=evidence,
                                  after_first=lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        self.assertEqual(self.store.load("project"), before)
        self.assertTrue(list(evidence.glob("rollback-both-*.json")))

    def test_inheritance_override_deny_and_explicit_precedence(self):
        global_p = {**tp.empty_profile("global"), "preferences": [self.pref(value="blue"), self.pref("font", "mono")]}
        project_p = {**tp.empty_profile("project"), "preferences": [self.pref(value="red"), self.pref("font", "deny")]}
        resolved = tp.resolve_effective(global_p, project_p, [self.pref(value="green")])
        self.assertEqual(resolved["preferences"], {"color": "green"})

    def test_duplicates_and_equal_precedence_conflicts(self):
        item = self.pref()
        self.assertEqual(len(tp.normalize_preferences([item, item])), 1)
        profile = tp.empty_profile("project")
        profile["preferences"] = [self.pref(value="red"), self.pref(value="blue")]
        effective = tp.resolve_effective(tp.empty_profile("global"), profile)
        self.assertNotIn("color", effective["preferences"])
        self.assertEqual(effective["conflicts"][0]["key"], "color")

    def test_confirmation_and_optimistic_revision_conflict(self):
        preview = self.store.write("project", [self.pref()], expected_revision=0)
        self.assertFalse(preview["confirmed"])
        self.assertFalse(self.store.path("project").exists())
        self.store.write("project", [self.pref()], expected_revision=0, confirm=True)
        with self.assertRaises(tp.RevisionConflict):
            self.store.write("project", [], expected_revision=0, confirm=True)

    def test_concurrent_mutation_attempts_allow_one_revision(self):
        barrier = threading.Barrier(2)
        outcomes = []
        def mutate(value):
            barrier.wait()
            try:
                self.store.write("project", [self.pref(value=value)], expected_revision=0, confirm=True)
                outcomes.append("written")
            except tp.RevisionConflict:
                outcomes.append("conflict")
        threads = [threading.Thread(target=mutate, args=(value,)) for value in ("red", "blue")]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertCountEqual(outcomes, ["written", "conflict"])
        self.assertEqual(self.store.load("project")["revision"], 1)

    def test_atomic_replacement_leaves_original_on_replace_failure(self):
        path = self.store.path("project")
        tp.atomic_replace(path, tp.empty_profile("project"))
        original = path.read_bytes()
        with mock.patch.object(tp.os, "replace", side_effect=OSError("simulated")):
            with self.assertRaises(OSError):
                tp.atomic_replace(path, {**tp.empty_profile("project"), "revision": 1})
        self.assertEqual(path.read_bytes(), original)

    def test_corrupt_json_and_schema_rejection_preserve_input(self):
        path = self.store.path("project"); path.parent.mkdir(parents=True)
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(tp.TasteError): self.store.load("project")
        self.assertEqual(path.read_text(), "{broken")
        path.write_text(json.dumps({"schema_version": 99, "revision": 0, "scope": "project", "preferences": []}))
        with self.assertRaises(tp.TasteError): self.store.load("project")

    def test_import_validation_redaction_and_lifecycle_transforms(self):
        raw = json.dumps({**tp.empty_profile("project"), "preferences": [self.pref("api-key", "secret token")]})
        imported = tp.import_profile(raw, "project")
        self.assertEqual(imported["preferences"][0]["value"], "[REDACTED]")
        p = tp.transform(tp.empty_profile("project"), "promote", "color", "blue")
        p = tp.transform(p, "specialize", "color", "red")
        p = tp.transform(p, "deprecate", "color")
        p = tp.transform(p, "revoke", "color")
        self.assertTrue(all(x["status"] == "revoked" for x in p["preferences"]))
        self.assertEqual(tp.transform(p, "reset")["preferences"], [])

    def test_stable_rendering_hashes_and_read_only_resolution(self):
        p = {**tp.empty_profile("project"), "preferences": [self.pref("font", "mono"), self.pref()]}
        self.assertEqual(tp.render_markdown(p), tp.render_markdown(p))
        self.assertEqual(tp.canonical_hash(p), tp.canonical_hash(json.loads(json.dumps(p))))
        before = json.dumps(p, sort_keys=True)
        tp.resolve_effective(tp.empty_profile("global"), p)
        self.assertEqual(json.dumps(p, sort_keys=True), before)

    def test_path_traversal_and_symlink_escape_are_rejected(self):
        with self.assertRaises(tp.TasteError): tp.normalize_key("../secret")
        outside = self.project / "outside"; outside.mkdir()
        saves = self.project / "skillset-saves"; saves.mkdir()
        (saves / "preferences").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(tp.TasteError): self.store.path("project")

    def test_legacy_absent_preview_confirmation_retention_and_idempotence(self):
        self.assertEqual(tp.migration_preview(self.project)["action"], "none")
        legacy = self.project / tp.LEGACY_RELATIVE; legacy.parent.mkdir(parents=True)
        legacy.write_text(tp.LEGACY_HEADER + "\n- color: blue\n", encoding="utf-8")
        self.assertFalse(tp.migrate_legacy(self.project)["confirmed"])
        done = tp.migrate_legacy(self.project, confirm=True)
        self.assertTrue(Path(done["evidence"]).exists())
        self.assertEqual(tp.migrate_legacy(self.project, confirm=True)["action"], "none")

    def test_arbitrary_markdown_is_not_migrated(self):
        legacy = self.project / tp.LEGACY_RELATIVE; legacy.parent.mkdir(parents=True)
        legacy.write_text("# My likes\n- use tabs\n", encoding="utf-8")
        with self.assertRaises(tp.TasteError): tp.migration_preview(self.project)


if __name__ == "__main__":
    unittest.main()
