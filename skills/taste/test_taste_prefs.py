"""Contract tests for the standard-library Taste preference writer.

`TastePreferencesTests` drives the script as a subprocess. The other classes call
`taste_prefs.main` in-process so they can prove every subcommand, refusal path, and
scope combination quickly; `test_taste_store.py` covers the storage engine (lock,
commit and rollback, root resolution) and the safety validators.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


SCRIPT = Path(__file__).with_name("taste_prefs.py")
_SPEC = importlib.util.spec_from_file_location("taste_prefs", SCRIPT)
taste = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(taste)


def proposal(**changes):
    """A value that satisfies the doctrine section 4 fields a new proposal must carry."""
    return {"category": "density", "normalized_rule": "Prefer compact table rows", "strength": "soft", "source": "explicit", **changes}


class TastePreferencesTests(unittest.TestCase):
    def setUp(self):
        project_tmp = tempfile.TemporaryDirectory()
        global_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup)
        self.addCleanup(global_tmp.cleanup)
        self.project, self.global_home = Path(project_tmp.name), Path(global_tmp.name)
        self.env = {**os.environ, "SUPREMETEAM_HOME": str(self.global_home), "SUPREMETEAM_OWNER": "test-owner"}

    def run_cli(self, *args: str) -> tuple[int, dict]:
        process = subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(self.project), *args], text=True, capture_output=True, env=self.env)
        return process.returncode, json.loads(process.stdout)

    def test_project_lifecycle_history_and_stale_writer(self):
        code, result = self.run_cli("set", "--scope", "project", "--id", "ui.density", "--value", '"compact"')
        self.assertEqual(code, 0, result)
        record = json.loads((self.project / "skillset-saves/preferences/taste.json").read_text())
        self.assertEqual(record["revision"], 1)
        self.assertEqual(record["entries"]["ui.density"]["state"], "active")
        code, result = self.run_cli("deprecate", "--scope", "project", "--expect-revision", "0", "--id", "ui.density")
        self.assertEqual(code, 1)
        self.assertEqual(result["error"]["code"], "stale_revision")
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
        self.assertEqual(code, 0)
        self.assertEqual(result["entries"]["format.style"]["source_scope"], "project")

    def test_sensitive_values_rejected_or_redacted_and_corruption_preserved(self):
        code, result = self.run_cli("set", "--scope", "project", "--id", "unsafe", "--value", '"person@example.com"')
        self.assertEqual(code, 1)
        self.assertEqual(result["error"]["code"], "sensitive_input")
        code, result = self.run_cli("set", "--scope", "project", "--redact", "--id", "safe", "--value", '"person@example.com"')
        self.assertEqual(code, 0, result)
        target = self.project / "skillset-saves/preferences/taste.json"
        target.write_bytes(b"not-json\x00recovery")
        code, result = self.run_cli("reset", "--scope", "project", "--expect-revision", "1")
        self.assertEqual(code, 1)
        self.assertEqual(result["error"]["code"], "corrupt_record")
        self.assertEqual(target.read_bytes(), b"not-json\x00recovery")


class CliContractTests(unittest.TestCase):
    """What a caller of the script sees: one JSON document on stdout and an exit code."""

    def setUp(self):
        project_tmp, global_tmp = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup)
        self.addCleanup(global_tmp.cleanup)
        self.project = Path(project_tmp.name)
        self.env = {**os.environ, "SUPREMETEAM_HOME": global_tmp.name, "SUPREMETEAM_OWNER": "test-owner"}

    def run_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--project-root", str(self.project), *args], text=True, capture_output=True, env=self.env)

    def test_success_and_refusal_are_single_json_documents_with_distinct_exit_codes(self):
        done = self.run_script("set", "--scope", "project", "--id", "a", "--value", '"x"')
        self.assertEqual(done.returncode, 0, done.stderr)
        payload = json.loads(done.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["command"], "set")
        refused = self.run_script("confirm", "--scope", "project", "--expect-revision", "1", "--id", "missing")
        self.assertEqual(refused.returncode, 1)
        self.assertFalse(json.loads(refused.stdout)["ok"])
        self.assertEqual(refused.stderr, "")

    def test_a_usage_error_exits_two_with_usage_on_stderr_and_nothing_on_stdout(self):
        for args in (["set", "--id", "a", "--value", "1"], ["bogus"], ["export", "--scope", "project"], []):
            with self.subTest(args=args):
                result = self.run_script(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("usage:", result.stderr)

    def test_every_subcommand_the_writer_documents_is_registered(self):
        commands = set(taste.READS) | taste.MUTATIONS
        self.assertEqual(len(commands), 14)
        self.assertTrue(set(taste.READS).isdisjoint(taste.MUTATIONS))
        for command in sorted(commands):
            with self.subTest(command=command):
                result = self.run_script(command, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"taste_prefs.py {command}", result.stdout)


class WriterCase(unittest.TestCase):
    """A throwaway project and global root, reached through the environment the writer reads."""

    def setUp(self):
        project_tmp, global_tmp = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory()
        self.addCleanup(project_tmp.cleanup)
        self.addCleanup(global_tmp.cleanup)
        self.project = Path(project_tmp.name).resolve()
        self.global_home = Path(global_tmp.name).resolve()
        environment = mock.patch.dict(os.environ, {"SUPREMETEAM_HOME": str(self.global_home), "SUPREMETEAM_OWNER": "test-owner"})
        environment.start()
        self.addCleanup(environment.stop)

    def preferences(self, scope: str) -> Path:
        return self.project / "skillset-saves" / "preferences" if scope == "project" else self.global_home / "preferences"

    def cli(self, *args: str, root: Path | None = None) -> tuple[int, dict]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = taste.main(["--project-root", str(root or self.project), *args])
        return code, json.loads(out.getvalue())

    def ok(self, *args: str, root: Path | None = None) -> dict:
        code, payload = self.cli(*args, root=root)
        self.assertEqual(code, 0, payload)
        self.assertTrue(payload["ok"])
        return payload

    def refused(self, *args: str) -> dict:
        code, payload = self.cli(*args)
        self.assertEqual(code, 1, payload)
        self.assertFalse(payload["ok"])
        return payload["error"]

    def record(self, scope: str) -> dict:
        return json.loads((self.preferences(scope) / "taste.json").read_text(encoding="utf-8"))

    def revision(self, scope: str) -> int:
        target = self.preferences(scope) / "taste.json"
        return json.loads(target.read_text(encoding="utf-8"))["revision"] if target.exists() else 0

    def snapshot(self, *scopes: str) -> dict[Path, bytes]:
        """Every file under the named stores, so a refused write can be shown to change nothing."""
        return {path: path.read_bytes() for scope in scopes for path in sorted(self.preferences(scope).rglob("*")) if path.is_file()}

    def put(self, scope: str, entry_id: str, value: object, command: str = "set") -> dict:
        """Write one entry, supplying the revision each existing store is at."""
        args = [command, "--scope", scope, "--id", entry_id, "--value", json.dumps(value)]
        for name in ("project", "global") if scope == "both" else (scope,):
            if (self.preferences(name) / "taste.json").exists():
                args += ["--expect-revision", f"{name}={self.revision(name)}"]
        return self.ok(*args)

    def expect(self, *scopes: str) -> list[str]:
        return [item for scope in scopes for item in ("--expect-revision", f"{scope}={self.revision(scope)}")]

    def write_store(self, scope: str, entries: dict, revision: int = 1) -> dict:
        """Write a store directly, as an earlier version of the writer or a hand edit could have."""
        record = taste.blank(self.project, scope)
        record["entries"], record["revision"] = entries, revision
        record["canonical_record_digest"] = taste.digest(record)
        target = self.preferences(scope) / "taste.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(taste.canonical_bytes(record))
        return record

    def import_file(self, content: object, name: str = "incoming.json") -> str:
        path = self.project / name
        path.write_text(json.dumps(content), encoding="utf-8")
        return str(path)


class StatusTests(WriterCase):
    def test_a_missing_store_is_reported_as_revision_zero_without_creating_anything(self):
        stores = self.ok("status", "--scope", "project")["stores"]
        self.assertEqual(list(stores), ["project"])
        self.assertFalse(stores["project"]["exists"])
        self.assertEqual(stores["project"]["revision"], 0)
        self.assertEqual(Path(stores["project"]["path"]), self.preferences("project") / "taste.json")
        self.assertTrue(stores["project"]["digest"].startswith("sha256:"))
        self.assertFalse((self.project / "skillset-saves").exists())

    def test_status_reports_the_revision_and_digest_of_each_store(self):
        self.put("project", "a", "1")
        self.put("project", "b", "2")
        self.put("global", "a", "3")
        stores = self.ok("status", "--scope", "both")["stores"]
        self.assertEqual({scope: stores[scope]["revision"] for scope in stores}, {"project": 2, "global": 1})
        for scope in ("project", "global"):
            self.assertTrue(stores[scope]["exists"])
            self.assertEqual(stores[scope]["digest"], self.record(scope)["canonical_record_digest"])
            self.assertEqual(Path(stores[scope]["path"]), self.preferences(scope) / "taste.json")

    def test_the_default_scope_is_both_and_a_scope_limits_the_report(self):
        self.assertEqual(sorted(self.ok("status")["stores"]), ["global", "project"])
        self.assertEqual(list(self.ok("status", "--scope", "global")["stores"]), ["global"])


class ListTests(WriterCase):
    def test_list_returns_every_entry_of_every_state_per_scope(self):
        self.put("project", "active-one", "a")
        self.put("project", "proposed-one", proposal(), command="propose")
        self.put("project", "old-one", "o")
        self.ok("deprecate", "--scope", "project", "--id", "old-one", *self.expect("project"))
        self.put("global", "global-one", "g")
        entries = self.ok("list")["entries"]
        self.assertEqual({key: entry["state"] for key, entry in entries["project"].items()}, {"active-one": "active", "proposed-one": "proposed", "old-one": "deprecated"})
        self.assertEqual(list(entries["global"]), ["global-one"])
        self.assertEqual(entries["project"]["active-one"]["value"], "a")
        self.assertEqual(set(entries["project"]["active-one"]), {"state", "value", "updated_at"})

    def test_list_of_missing_stores_is_empty_rather_than_an_error(self):
        self.assertEqual(self.ok("list")["entries"], {"project": {}, "global": {}})

    def test_list_scope_limits_the_stores(self):
        self.put("global", "g", "1")
        self.assertEqual(list(self.ok("list", "--scope", "global")["entries"]), ["global"])


class EffectiveTests(WriterCase):
    def test_only_active_entries_are_effective(self):
        self.put("project", "active-one", "a")
        self.put("project", "proposed-one", proposal(), command="propose")
        self.put("project", "deprecated-one", "d")
        self.ok("deprecate", "--scope", "project", "--id", "deprecated-one", *self.expect("project"))
        self.put("project", "revoked-one", "r")
        self.ok("revoke", "--scope", "project", "--id", "revoked-one", *self.expect("project"))
        self.assertEqual(list(self.ok("effective")["entries"]), ["active-one"])

    def test_a_project_entry_shadows_the_global_entry_with_the_same_id(self):
        self.put("global", "tone", "global voice")
        self.put("global", "only-global", "g")
        self.put("project", "tone", "project voice")
        entries = self.ok("effective", "--scope", "both")["entries"]
        self.assertEqual((entries["tone"]["value"], entries["tone"]["source_scope"]), ("project voice", "project"))
        self.assertEqual(entries["only-global"]["source_scope"], "global")

    def test_a_scope_limits_which_stores_are_resolved(self):
        self.put("global", "tone", "global voice")
        self.put("project", "tone", "project voice")
        self.assertEqual(self.ok("effective", "--scope", "global")["entries"]["tone"]["value"], "global voice")
        self.assertEqual(self.ok("effective", "--scope", "project")["entries"]["tone"]["source_scope"], "project")

    def test_the_effective_entry_shape_that_design_runs_read_is_stable(self):
        self.put("project", "a", {"category": "density"})
        entry = self.ok("effective", "--scope", "project")["entries"]["a"]
        self.assertEqual(set(entry), {"state", "value", "updated_at", "source_scope"})
        self.assertEqual((entry["state"], entry["value"], entry["source_scope"]), ("active", {"category": "density"}, "project"))


class DiffTests(WriterCase):
    def test_entries_that_agree_are_not_reported_when_only_updated_at_differs(self):
        self.write_store("project", {"x": {"state": "active", "value": "v", "updated_at": "2026-01-01T00:00:00Z"}})
        self.write_store("global", {"x": {"state": "active", "value": "v", "updated_at": "2026-02-02T00:00:00Z"}})
        self.assertEqual(self.ok("diff", "--scope", "both")["differences"], [])

    def test_entries_that_agree_are_not_reported_after_writing_both_scopes(self):
        self.put("both", "format.style", "brief")
        self.assertEqual(self.ok("diff", "--scope", "both")["differences"], [])

    def test_entries_that_agree_are_not_reported_after_promote_or_specialize(self):
        self.put("project", "promoted", "p")
        self.ok("promote", "--scope", "global", "--id", "promoted")
        self.put("global", "specialized", "g")
        self.ok("specialize", "--scope", "project", "--id", "specialized", *self.expect("project"))
        self.assertEqual(self.ok("diff")["differences"], [])

    def test_value_state_and_one_sided_differences_are_reported_in_id_order(self):
        self.put("both", "same", "v")
        self.put("project", "only-project", "p")
        self.put("global", "only-global", "g")
        self.put("project", "shared", "one")
        self.put("global", "shared", "two")
        self.put("project", "state", "s")
        self.put("global", "state", "s")
        self.ok("deprecate", "--scope", "global", "--id", "state", *self.expect("global"))
        differences = self.ok("diff")["differences"]
        self.assertEqual([item["id"] for item in differences], ["only-global", "only-project", "shared", "state"])
        by_id = {item["id"]: item for item in differences}
        self.assertIsNone(by_id["only-project"]["global"])
        self.assertIsNone(by_id["only-global"]["project"])
        self.assertEqual((by_id["shared"]["project"]["value"], by_id["shared"]["global"]["value"]), ("one", "two"))
        self.assertEqual((by_id["state"]["project"]["state"], by_id["state"]["global"]["state"]), ("active", "deprecated"))

    def test_a_diff_is_between_the_two_stores_so_a_single_scope_is_refused(self):
        for scope in ("project", "global"):
            with self.subTest(scope=scope):
                self.assertEqual(self.refused("diff", "--scope", scope)["code"], "invalid_scope")
        self.assertEqual(self.ok("diff")["differences"], [])

    def test_a_corrupt_store_on_either_side_refuses_the_diff(self):
        self.put("both", "a", "1")
        (self.preferences("global") / "taste.json").write_bytes(b"{")
        self.assertEqual(self.refused("diff")["code"], "corrupt_record")


class ExportTests(WriterCase):
    def export(self, *extra: str) -> tuple[dict, dict]:
        output = self.project / "export.json"
        payload = self.ok("export", "--output", str(output), *extra)
        return payload, json.loads(output.read_text(encoding="utf-8"))

    def test_export_writes_active_entries_with_each_store_digest_as_provenance(self):
        self.put("project", "kept", "a")
        self.put("project", "candidate", proposal(), command="propose")
        self.put("global", "shared", "g")
        payload, document = self.export()
        self.assertEqual(Path(payload["output"]), (self.project / "export.json").resolve())
        self.assertTrue(payload["redacted"])
        self.assertEqual(payload["redactions"], [])
        self.assertEqual((document["schema"], document["schema_version"]), ("supremeteam-taste-export", 1))
        self.assertEqual(sorted(document["entries"]), ["kept", "shared"])
        self.assertEqual(document["provenance"], {scope: self.record(scope)["canonical_record_digest"] for scope in ("project", "global")})
        self.assertEqual(document["entries"]["shared"]["source_scope"], "global")

    def test_export_scope_limits_the_stores_and_the_provenance(self):
        self.put("project", "p", "1")
        self.put("global", "g", "2")
        _, document = self.export("--scope", "global")
        self.assertEqual(list(document["entries"]), ["g"])
        self.assertEqual(list(document["provenance"]), ["global"])

    def test_export_redacts_what_a_store_written_before_the_validators_holds_and_lists_it(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
        stamp = "2026-01-01T00:00:00Z"

        def entry(value):
            return {"state": "active", "value": value, "updated_at": stamp}

        self.write_store("project", {
            "plain": entry("compact"),
            "legacy.key": entry(secret),
            "notes": entry("mail person@example.com please"),
            "contact.phone": entry("555-0100"),
            "mixed": entry({"password": "hunter2", "density": "compact"}),
            "long": entry("x" * 1500),
        })
        payload, document = self.export("--scope", "project")
        entries = document["entries"]
        self.assertEqual(entries["plain"]["value"], "compact")
        self.assertEqual(entries["legacy.key"]["value"], "[REDACTED]")
        self.assertEqual(entries["notes"]["value"], "[REDACTED]")
        self.assertNotIn("contact.phone", entries)
        self.assertEqual(entries["mixed"]["value"], {"density": "compact"})
        self.assertEqual(entries["long"]["value"], "x" * 1000 + "[REDACTED:TRUNCATED]")
        expected = [
            {"path": "$.contact.phone", "action": "dropped"},
            {"path": "$.legacy.key.value", "action": "redacted"},
            {"path": "$.long.value", "action": "truncated"},
            {"path": "$.mixed.value.password", "action": "dropped"},
            {"path": "$.notes.value", "action": "redacted"},
        ]
        self.assertEqual(sorted(payload["redactions"], key=lambda item: item["path"]), expected)
        leaked = json.dumps(payload) + json.dumps(document)
        for text in (secret, "person@example.com", "555-0100", "hunter2"):
            self.assertNotIn(text, leaked)

    def test_the_redact_flag_is_accepted_and_changes_nothing_because_export_always_redacts(self):
        self.put("project", "a", "compact")
        without, plain = self.export()
        with_flag, flagged = self.export("--redact")
        self.assertTrue(without["redacted"] and with_flag["redacted"])
        self.assertEqual(plain["entries"], flagged["entries"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as helped:
            taste.main(["export", "--help"])
        self.assertEqual(helped.exception.code, 0)
        self.assertIn("always redacted", " ".join(out.getvalue().split()))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as refused:
            taste.main(["--project-root", str(self.project), "export", "--output", str(self.project / "x.json"), "--no-redact"])
        self.assertEqual(refused.exception.code, 2)

    def test_an_export_can_be_imported_into_another_store(self):
        self.put("project", "density", "compact")
        self.put("global", "tone", {"voice": "brief"})
        output = self.project / "export.json"
        self.ok("export", "--output", str(output))
        fresh = self.project / "fresh"
        fresh.mkdir()
        self.ok("import", "--scope", "project", "--input", str(output), root=fresh)
        imported = json.loads((fresh / "skillset-saves/preferences/taste.json").read_text(encoding="utf-8"))["entries"]
        self.assertEqual({key: item["value"] for key, item in imported.items()}, {"density": "compact", "tone": {"voice": "brief"}})


class ProposeAndConfirmTests(WriterCase):
    def test_a_proposal_is_stored_as_proposed_and_is_not_effective_until_confirmed(self):
        result = self.ok("propose", "--scope", "project", "--id", "tables.density", "--value", json.dumps(proposal(confidence=0.6)))
        self.assertEqual(result["command"], "propose")
        entry = self.record("project")["entries"]["tables.density"]
        self.assertEqual(entry["state"], "proposed")
        self.assertEqual(entry["value"]["confidence"], 0.6)
        self.assertEqual(self.ok("effective", "--scope", "project")["entries"], {})

    def test_confirm_moves_a_proposed_entry_to_active_and_leaves_its_value_alone(self):
        self.put("project", "tables.density", proposal(source="confirmed-inference", confidence=0.6), command="propose")
        before = self.record("project")["entries"]["tables.density"]["value"]
        self.ok("confirm", "--scope", "project", "--id", "tables.density", *self.expect("project"))
        entry = self.record("project")["entries"]["tables.density"]
        self.assertEqual(entry["state"], "active")
        self.assertEqual(entry["value"], before)
        self.assertEqual(self.record("project")["revision"], 2)
        self.assertEqual(list(self.ok("effective", "--scope", "project")["entries"]), ["tables.density"])

    def test_confirm_refuses_a_missing_entry_and_an_entry_that_is_not_proposed(self):
        self.put("project", "already", "x")
        before = self.snapshot("project")
        self.assertEqual(self.refused("confirm", "--scope", "project", "--id", "missing", *self.expect("project"))["code"], "not_found")
        error = self.refused("confirm", "--scope", "project", "--id", "already", *self.expect("project"))
        self.assertEqual((error["code"], error["id"]), ("invalid_state", "already"))
        self.assertEqual(self.snapshot("project"), before)

    def test_confirm_refuses_a_deprecated_entry(self):
        self.put("project", "old", "x")
        self.ok("deprecate", "--scope", "project", "--id", "old", *self.expect("project"))
        self.assertEqual(self.refused("confirm", "--scope", "project", "--id", "old", *self.expect("project"))["code"], "invalid_state")

    def test_propose_and_confirm_apply_to_both_stores_under_both(self):
        self.put("both", "shared", proposal(), command="propose")
        self.assertEqual({scope: self.record(scope)["entries"]["shared"]["state"] for scope in ("project", "global")}, {"project": "proposed", "global": "proposed"})
        self.ok("confirm", "--scope", "both", "--id", "shared", *self.expect("project", "global"))
        self.assertEqual({scope: self.record(scope)["entries"]["shared"]["state"] for scope in ("project", "global")}, {"project": "active", "global": "active"})


class SetTests(WriterCase):
    def test_set_creates_an_active_entry_and_the_first_write_is_revision_one(self):
        result = self.ok("set", "--scope", "project", "--id", "density", "--value", '"Prefer compact layouts"')
        self.assertEqual(result["stores"]["project"]["revision"], 1)
        record = self.record("project")
        self.assertEqual(result["stores"]["project"]["digest"], record["canonical_record_digest"])
        self.assertEqual(record["entries"]["density"]["state"], "active")
        self.assertEqual(record["entries"]["density"]["value"], "Prefer compact layouts")

    def test_a_value_is_parsed_as_json_and_falls_back_to_the_raw_text(self):
        values = {"quoted": '"compact"', "bare": "compact", "number": "42", "flag": "true", "nothing": "null", "object": '{"a": [1, 2]}', "list": '["x", "y"]', "spaced": "prefer compact tables"}
        for entry_id, raw in values.items():
            self.ok("set", "--scope", "project", "--id", entry_id, "--value", raw, *(self.expect("project") if self.revision("project") else []))
        stored = {key: item["value"] for key, item in self.record("project")["entries"].items()}
        self.assertEqual(stored, {"quoted": "compact", "bare": "compact", "number": 42, "flag": True, "nothing": None, "object": {"a": [1, 2]}, "list": ["x", "y"], "spaced": "prefer compact tables"})

    def test_set_supersedes_in_place_and_snapshots_the_prior_revision(self):
        self.put("project", "density", "compact")
        first = (self.preferences("project") / "taste.json").read_bytes()
        self.put("project", "density", "spacious")
        record = self.record("project")
        self.assertEqual((record["revision"], record["entries"]["density"]["value"]), (2, "spacious"))
        history = list((self.preferences("project") / "_history").glob("*.json"))
        self.assertEqual([path.read_bytes() for path in history], [first])

    def test_set_needs_a_stable_lowercase_id_and_a_value(self):
        for entry_id in ("Density", "-density", ".density", "has space", "a" * 129, "dens!ty"):
            with self.subTest(entry_id=entry_id):
                self.assertEqual(self.refused("set", "--scope", "project", f"--id={entry_id}", "--value", '"x"')["code"], "invalid_id")
        self.assertEqual(self.refused("set", "--scope", "project", "--value", '"x"')["code"], "invalid_id")
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "density")["code"], "missing_value")
        self.assertEqual(self.snapshot("project"), {})

    def test_the_longest_id_and_a_dotted_id_are_accepted(self):
        self.put("project", "a" * 128, "x")
        self.put("project", "ui.tables_v2-dense", "y")
        self.assertEqual(sorted(self.record("project")["entries"]), sorted(["a" * 128, "ui.tables_v2-dense"]))

    def test_set_after_revoke_clears_the_tombstone(self):
        self.put("project", "density", "compact")
        self.ok("revoke", "--scope", "project", "--id", "density", *self.expect("project"))
        self.assertIn("density", self.record("project")["tombstones"])
        self.put("project", "density", "compact again")
        record = self.record("project")
        self.assertEqual(record["tombstones"], {})
        self.assertEqual(record["entries"]["density"]["value"], "compact again")

    def test_set_both_writes_two_independent_stores_with_their_own_revisions(self):
        self.put("project", "warmup", "x")
        self.put("both", "shared", "v")
        self.assertEqual((self.revision("project"), self.revision("global")), (2, 1))
        self.put("global", "only-global", "g")
        self.assertEqual((self.revision("project"), self.revision("global")), (2, 2))
        self.assertEqual(self.record("global")["scope"], {"kind": "global", "id": "host-user-data"})
        self.assertEqual(self.record("project")["scope"]["kind"], "project")
        self.assertTrue(self.record("project")["scope"]["id"].startswith("sha256:"))

    def test_a_project_only_write_leaves_the_global_store_absent_and_the_reverse(self):
        self.put("project", "a", "1")
        self.assertFalse((self.global_home / "preferences").exists())
        self.put("global", "b", "2")
        self.assertEqual(sorted(self.record("global")["entries"]), ["b"])
        self.assertEqual(sorted(self.record("project")["entries"]), ["a"])


class DeprecateAndRevokeTests(WriterCase):
    def test_deprecate_keeps_the_entry_but_leaves_effective_resolution(self):
        self.put("project", "density", "compact")
        result = self.ok("deprecate", "--scope", "project", "--id", "density", *self.expect("project"))
        self.assertEqual(result["stores"]["project"]["revision"], 2)
        self.assertEqual(self.record("project")["entries"]["density"]["state"], "deprecated")
        self.assertEqual(self.record("project")["entries"]["density"]["value"], "compact")
        self.assertEqual(self.ok("effective", "--scope", "project")["entries"], {})
        self.assertIn("density", self.ok("list", "--scope", "project")["entries"]["project"])

    def test_deprecate_and_revoke_refuse_an_unknown_id_and_change_nothing(self):
        self.put("project", "density", "compact")
        before = self.snapshot("project")
        for command in ("deprecate", "revoke"):
            with self.subTest(command=command):
                error = self.refused(command, "--scope", "project", "--id", "missing", *self.expect("project"))
                self.assertEqual((error["code"], error["id"]), ("not_found", "missing"))
        self.assertEqual(self.snapshot("project"), before)

    def test_revoke_removes_the_entry_and_records_a_tombstone_with_the_prior_entry_digest(self):
        self.put("project", "density", {"category": "density"})
        prior = self.record("project")["entries"]["density"]
        self.ok("revoke", "--scope", "project", "--id", "density", *self.expect("project"))
        record = self.record("project")
        self.assertEqual(record["entries"], {})
        tombstone = record["tombstones"]["density"]
        self.assertEqual(tombstone["prior_entry_digest"], "sha256:" + hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest())
        self.assertRegex(tombstone["revoked_at"], r"^\d{4}-\d\d-\d\dT.*Z$")
        self.assertEqual(self.ok("effective", "--scope", "project")["entries"], {})

    def test_the_rendered_view_lists_a_revoked_entry_as_a_tombstone(self):
        self.put("project", "density", "compact")
        self.ok("revoke", "--scope", "project", "--id", "density", *self.expect("project"))
        text = (self.preferences("project") / "taste.md").read_text(encoding="utf-8")
        self.assertIn("_No active entries._", text)
        self.assertIn("- `density` — revoked at `", text)


class PromoteAndSpecializeTests(WriterCase):
    def test_promote_copies_a_project_entry_into_global_and_leaves_the_source_alone(self):
        self.put("project", "density", {"category": "density", "normalized_rule": "compact"})
        before = self.snapshot("project")
        result = self.ok("promote", "--scope", "global", "--id", "density")
        self.assertEqual(list(result["stores"]), ["global"])
        promoted = self.record("global")["entries"]["density"]
        self.assertEqual((promoted["state"], promoted["value"]), ("active", {"category": "density", "normalized_rule": "compact"}))
        self.assertEqual(self.snapshot("project"), before)

    def test_promote_into_an_existing_global_store_needs_its_revision_and_supersedes_the_id(self):
        self.put("project", "density", "compact")
        self.put("global", "density", "old")
        self.assertEqual(self.refused("promote", "--scope", "global", "--id", "density")["code"], "revision_required")
        self.ok("promote", "--scope", "global", "--id", "density", *self.expect("global"))
        self.assertEqual(self.record("global")["entries"]["density"]["value"], "compact")
        self.assertEqual(self.revision("global"), 2)

    def test_promote_writes_global_scope_and_specialize_writes_project_scope(self):
        self.put("project", "a", "1")
        self.put("global", "b", "2")
        self.assertEqual(self.refused("promote", "--scope", "project", "--id", "a", *self.expect("project"))["code"], "invalid_scope")
        self.assertEqual(self.refused("specialize", "--scope", "global", "--id", "b", *self.expect("global"))["code"], "invalid_scope")

    def test_promote_and_specialize_refuse_an_id_missing_from_their_source(self):
        self.put("project", "a", "1")
        self.put("global", "b", "2")
        self.assertEqual(self.refused("promote", "--scope", "global", "--id", "b", *self.expect("global"))["code"], "not_found")
        self.assertEqual(self.refused("specialize", "--scope", "project", "--id", "a", *self.expect("project"))["code"], "not_found")

    def test_specialize_copies_a_global_entry_into_project_and_project_then_shadows_it(self):
        self.put("global", "density", "global value")
        result = self.ok("specialize", "--scope", "project", "--id", "density")
        self.assertEqual(list(result["stores"]), ["project"])
        self.assertEqual(self.record("project")["entries"]["density"]["value"], "global value")
        self.put("project", "density", "project value")
        self.assertEqual(self.ok("effective")["entries"]["density"]["source_scope"], "project")
        self.assertEqual(self.record("global")["entries"]["density"]["value"], "global value")

    def test_promote_clears_a_tombstone_for_the_copied_id(self):
        self.put("project", "density", "compact")
        self.put("global", "density", "old")
        self.ok("revoke", "--scope", "global", "--id", "density", *self.expect("global"))
        self.assertIn("density", self.record("global")["tombstones"])
        self.ok("promote", "--scope", "global", "--id", "density", *self.expect("global"))
        self.assertEqual(self.record("global")["tombstones"], {})

    def test_promote_under_both_checks_and_advances_the_source_store_too(self):
        self.put("project", "density", "compact")
        original = self.record("project")["entries"]["density"]
        result = self.ok("promote", "--scope", "both", "--id", "density", "--expect-revision", "project=1")
        self.assertEqual({scope: info["revision"] for scope, info in result["stores"].items()}, {"project": 2, "global": 1})
        source = self.record("project")["entries"]["density"]
        self.assertEqual((source["state"], source["value"]), (original["state"], original["value"]))
        self.assertEqual(len(list((self.preferences("project") / "_history").glob("*.json"))), 1)
        self.assertEqual(self.record("global")["entries"]["density"]["value"], "compact")

    def test_promote_under_both_with_a_stale_source_revision_writes_neither_store(self):
        self.put("project", "density", "compact")
        self.put("project", "other", "x")
        before = self.snapshot("project")
        error = self.refused("promote", "--scope", "both", "--id", "density", "--expect-revision", "project=1")
        self.assertEqual((error["code"], error["scope"], error["expected"], error["actual_revision"]), ("stale_revision", "project", 1, 2))
        self.assertEqual(self.snapshot("project"), before)
        self.assertEqual(self.snapshot("global"), {})

    def test_specialize_under_both_advances_the_global_source_store_too(self):
        self.put("global", "density", "g")
        result = self.ok("specialize", "--scope", "both", "--id", "density", "--expect-revision", "global=1")
        self.assertEqual({scope: info["revision"] for scope, info in result["stores"].items()}, {"project": 1, "global": 2})
        self.assertEqual(self.record("project")["entries"]["density"]["value"], "g")


class ImportTests(WriterCase):
    def test_import_reads_a_bare_map_an_envelope_and_value_wrapped_items(self):
        cases = {
            "bare": ({"a": "one", "b": {"nested": True}}, {"a": "one", "b": {"nested": True}}),
            "envelope": ({"entries": {"c": "three"}}, {"c": "three"}),
            "wrapped": ({"entries": {"d": {"value": "four", "state": "deprecated", "updated_at": "then"}}}, {"d": "four"}),
        }
        for name, (content, expected) in cases.items():
            with self.subTest(name=name):
                fresh = self.project / name
                fresh.mkdir()
                self.ok("import", "--scope", "project", "--input", self.import_file(content, f"{name}.json"), root=fresh)
                stored = json.loads((fresh / "skillset-saves/preferences/taste.json").read_text(encoding="utf-8"))["entries"]
                self.assertEqual({key: item["value"] for key, item in stored.items()}, expected)
                self.assertEqual({item["state"] for item in stored.values()}, {"active"})

    def test_import_merges_with_existing_entries_and_clears_tombstones_of_imported_ids(self):
        self.put("project", "kept", "old")
        self.put("project", "gone", "old")
        self.ok("revoke", "--scope", "project", "--id", "gone", *self.expect("project"))
        self.ok("import", "--scope", "project", "--input", self.import_file({"gone": "back", "fresh": "new"}), *self.expect("project"))
        record = self.record("project")
        self.assertEqual({key: item["value"] for key, item in record["entries"].items()}, {"kept": "old", "gone": "back", "fresh": "new"})
        self.assertEqual(record["tombstones"], {})

    def test_import_under_both_writes_the_same_entries_to_both_stores(self):
        self.ok("import", "--scope", "both", "--input", self.import_file({"a": "1"}))
        for scope in ("project", "global"):
            self.assertEqual(self.record(scope)["entries"]["a"]["value"], "1")

    def test_import_refuses_input_it_cannot_read_as_a_bounded_map_of_entries(self):
        broken = self.project / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        cases = {
            "missing file": str(self.project / "absent.json"),
            "not json": str(broken),
            "a list": self.import_file(["a", "b"], "list.json"),
            "a scalar": self.import_file("text", "scalar.json"),
            "entries that are not a map": self.import_file({"entries": ["a"]}, "shape.json"),
            "over the entry cap": self.import_file({f"id{n}": n for n in range(1001)}, "many.json"),
        }
        for name, path in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.refused("import", "--scope", "project", "--input", path)["code"], "invalid_import")
        self.assertEqual(self.snapshot("project"), {})

    def test_import_accepts_exactly_one_thousand_entries(self):
        self.ok("import", "--scope", "project", "--input", self.import_file({f"id{n}": n for n in range(1000)}))
        self.assertEqual(len(self.record("project")["entries"]), 1000)

    def test_import_refuses_an_invalid_stable_id_and_names_it(self):
        error = self.refused("import", "--scope", "project", "--input", self.import_file({"good": "1", "Bad Id": "2"}))
        self.assertEqual((error["code"], error["id"]), ("invalid_id", "Bad Id"))
        self.assertEqual(self.snapshot("project"), {})

    def test_import_needs_a_recognised_schema_when_the_file_declares_one(self):
        cases = {
            "unknown version": {"schema": "supremeteam-taste-export", "schema_version": 99, "entries": {"a": "1"}},
            "unknown schema": {"schema": "someone-elses", "schema_version": 1, "entries": {"a": "1"}},
            "schema without version": {"schema": "supremeteam-taste-export", "entries": {"a": "1"}},
            "version without schema": {"schema_version": 1, "entries": {"a": "1"}},
            "unhashable version": {"schema": "supremeteam-taste-export", "schema_version": [1], "entries": {"a": "1"}},
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                error = self.refused("import", "--scope", "project", "--input", self.import_file(content))
                self.assertEqual(error["code"], "invalid_schema")
                self.assertEqual(error["expected"], ["supremeteam-taste-preferences", "supremeteam-taste-export"])
        self.assertEqual(self.snapshot("project"), {})

    def test_import_accepts_a_store_record_the_writer_produced(self):
        self.put("project", "density", "compact")
        store = json.loads((self.preferences("project") / "taste.json").read_text(encoding="utf-8"))
        fresh = self.project / "fresh"
        fresh.mkdir()
        self.ok("import", "--scope", "project", "--input", self.import_file(store), root=fresh)
        stored = json.loads((fresh / "skillset-saves/preferences/taste.json").read_text(encoding="utf-8"))["entries"]
        self.assertEqual(stored["density"]["value"], "compact")

    def test_import_applies_the_safety_validators_to_every_value(self):
        error = self.refused("import", "--scope", "project", "--input", self.import_file({"a": "fine", "b": "person@example.com"}))
        self.assertEqual(error["code"], "sensitive_input")
        self.assertEqual(self.snapshot("project"), {})
        self.ok("import", "--scope", "project", "--redact", "--input", self.import_file({"a": "fine", "b": "person@example.com", "c": {"email": "x", "density": "compact"}}))
        stored = {key: item["value"] for key, item in self.record("project")["entries"].items()}
        self.assertEqual(stored, {"a": "fine", "b": "[REDACTED]", "c": {"density": "compact"}})

    def test_import_refuses_an_id_that_embeds_a_secret_without_echoing_it(self):
        secret_id = "sk-abcdefghijklmnopqrstuvwxyz123456"
        error = self.refused("import", "--scope", "project", "--redact", "--input", self.import_file({"fine": "1", secret_id: "2"}))
        self.assertEqual((error["code"], error["field"], error["index"]), ("sensitive_input", "id", 1))
        self.assertNotIn(secret_id, json.dumps(error))


class ResetTests(WriterCase):
    def test_reset_tombstones_every_entry_and_empties_the_store(self):
        self.put("project", "a", "1")
        self.put("project", "b", {"x": 1})
        entries = self.record("project")["entries"]
        result = self.ok("reset", "--scope", "project", *self.expect("project"))
        self.assertEqual(result["stores"]["project"]["revision"], 3)
        record = self.record("project")
        self.assertEqual(record["entries"], {})
        self.assertEqual(sorted(record["tombstones"]), ["a", "b"])
        for key, entry in entries.items():
            digest = "sha256:" + hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
            self.assertEqual(record["tombstones"][key]["prior_entry_digest"], digest)
        self.assertEqual(self.ok("effective")["entries"], {})
        self.assertIn("_No active entries._", (self.preferences("project") / "taste.md").read_text(encoding="utf-8"))

    def test_reset_of_one_scope_leaves_the_other_untouched(self):
        self.put("project", "a", "1")
        self.put("global", "b", "2")
        before = self.snapshot("project")
        self.ok("reset", "--scope", "global", *self.expect("global"))
        self.assertEqual(self.record("global")["entries"], {})
        self.assertEqual(self.snapshot("project"), before)

    def test_reset_under_both_resets_both_stores(self):
        self.put("both", "a", "1")
        self.ok("reset", "--scope", "both", *self.expect("project", "global"))
        for scope in ("project", "global"):
            self.assertEqual((self.record(scope)["entries"], sorted(self.record(scope)["tombstones"])), ({}, ["a"]))

    def test_every_mutation_advances_the_revision_even_when_nothing_is_left_to_reset(self):
        self.put("project", "a", "1")
        self.ok("reset", "--scope", "project", *self.expect("project"))
        self.ok("reset", "--scope", "project", *self.expect("project"))
        self.assertEqual(self.revision("project"), 3)


class ScopeAndRevisionTests(WriterCase):
    def test_a_mutation_without_a_scope_is_a_usage_error(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as raised:
            taste.main(["--project-root", str(self.project), "set", "--id", "a", "--value", "1"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--scope", err.getvalue())

    def test_an_existing_store_needs_an_expected_revision_and_a_new_one_does_not(self):
        self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        error = self.refused("set", "--scope", "project", "--id", "b", "--value", "2")
        self.assertEqual((error["code"], error["scope"], error["actual_revision"]), ("revision_required", "project", 1))
        self.assertEqual(sorted(self.record("project")["entries"]), ["a"])

    def test_a_stale_revision_names_the_scope_and_both_revisions_and_changes_nothing(self):
        self.put("project", "a", "1")
        self.put("project", "b", "2")
        before = self.snapshot("project")
        error = self.refused("set", "--scope", "project", "--id", "c", "--value", "3", "--expect-revision", "1")
        self.assertEqual((error["code"], error["scope"], error["expected"], error["actual_revision"]), ("stale_revision", "project", 1, 2))
        self.assertEqual(self.snapshot("project"), before)

    def test_a_shared_revision_applies_to_every_scope_and_a_scoped_one_to_just_that_scope(self):
        self.put("both", "a", "1")
        self.put("project", "b", "2")
        self.assertEqual((self.revision("project"), self.revision("global")), (2, 1))
        self.assertEqual(self.refused("set", "--scope", "both", "--id", "c", "--value", "3", "--expect-revision", "2")["scope"], "global")
        self.ok("set", "--scope", "both", "--id", "c", "--value", "3", "--expect-revision", "project=2", "--expect-revision", "global=1")
        self.assertEqual((self.revision("project"), self.revision("global")), (3, 2))
        self.ok("set", "--scope", "both", "--id", "d", "--value", "4", "--expect-revision", "3", "--expect-revision", "global=2")
        self.assertEqual((self.revision("project"), self.revision("global")), (4, 3))

    def test_malformed_expected_revisions_are_refused(self):
        self.put("project", "a", "1")
        for value in ("abc", "-1", "1.5", "project=abc", "project=", "elsewhere=1", "global=1", "=1"):
            with self.subTest(value=value):
                error = self.refused("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", value)
                self.assertEqual(error["code"], "invalid_revision")
        self.assertEqual(self.revision("project"), 1)

    def test_both_refuses_the_whole_write_when_one_scope_is_stale(self):
        self.put("both", "a", "1")
        before = self.snapshot("project", "global")
        error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", "--expect-revision", "project=1", "--expect-revision", "global=0")
        self.assertEqual((error["code"], error["scope"]), ("stale_revision", "global"))
        self.assertEqual(self.snapshot("project", "global"), before)

    def test_a_new_store_may_be_written_with_an_expected_revision_of_zero(self):
        self.ok("set", "--scope", "project", "--id", "a", "--value", "1", "--expect-revision", "0")
        self.assertEqual(self.revision("project"), 1)

    def test_a_global_root_inside_the_checkout_is_refused_and_the_project_store_still_works(self):
        inside = self.project / "prefs-home"
        with mock.patch.dict(os.environ, {"SUPREMETEAM_HOME": str(inside)}):
            error = self.refused("set", "--scope", "global", "--id", "a", "--value", "1")
            self.assertEqual(error["code"], "unsafe_global_path")
            self.assertEqual(self.refused("status", "--scope", "both")["code"], "unsafe_global_path")
            self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertFalse(inside.exists())
        with mock.patch.dict(os.environ, {"SUPREMETEAM_HOME": str(self.project)}):
            self.assertEqual(self.refused("status", "--scope", "global")["code"], "unsafe_global_path")


class RecordTests(WriterCase):
    def test_the_digest_is_the_sha256_of_the_canonical_bytes_without_the_digest_field(self):
        self.put("project", "density", {"b": 1, "a": "compact é"})
        record = self.record("project")
        digestless = {key: value for key, value in record.items() if key != "canonical_record_digest"}
        canonical = (json.dumps(digestless, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        self.assertEqual(record["canonical_record_digest"], "sha256:" + hashlib.sha256(canonical).hexdigest())
        self.assertEqual((self.preferences("project") / "taste.json").read_bytes(), (json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode())

    def test_a_record_carries_its_schema_scope_and_owner(self):
        self.put("project", "a", "1")
        record = self.record("project")
        self.assertEqual((record["schema"], record["schema_version"]), ("supremeteam-taste-preferences", 1))
        self.assertEqual(record["owner"], {"id": "test-owner", "source": "SUPREMETEAM_OWNER"})
        self.assertEqual(sorted(record), sorted(["schema", "schema_version", "scope", "revision", "generated_at", "entries", "tombstones", "previous_revision_digest", "owner", "canonical_record_digest"]))

    def test_revisions_chain_through_the_previous_revision_digest(self):
        digests = []
        for n in range(3):
            self.put("project", f"e{n}", str(n))
            digests.append(self.record("project")["canonical_record_digest"])
            self.assertEqual(self.record("project")["revision"], n + 1)
        self.put("project", "e3", "3")
        history = self.preferences("project") / "_history"
        first = json.loads(next(history.glob("revision-00000001-*.json")).read_text(encoding="utf-8"))
        second = json.loads(next(history.glob("revision-00000002-*.json")).read_text(encoding="utf-8"))
        self.assertIsNone(first["previous_revision_digest"])
        self.assertEqual(second["previous_revision_digest"], digests[0])
        self.assertEqual(self.record("project")["previous_revision_digest"], digests[2])

    def test_history_keeps_every_superseded_revision_byte_for_byte_under_its_revision_and_digest(self):
        written = {}
        for n in range(1, 4):
            self.put("project", "density", f"v{n}")
            written[n] = (self.preferences("project") / "taste.json").read_bytes()
        files = sorted((self.preferences("project") / "_history").glob("*.json"))
        self.assertEqual(len(files), 2)
        for n, path in zip((1, 2), files, strict=True):
            digest = json.loads(written[n])["canonical_record_digest"].split(":")[1][:12]
            self.assertEqual(path.name, f"revision-{n:08d}-{digest}.json")
            self.assertEqual(path.read_bytes(), written[n])

    def test_the_first_write_creates_no_history(self):
        self.put("project", "a", "1")
        self.assertFalse((self.preferences("project") / "_history").exists())

    def test_the_journal_has_one_line_for_each_committed_revision(self):
        self.put("both", "a", "1")
        self.put("both", "b", "2")
        for scope in ("project", "global"):
            lines = [json.loads(line) for line in (self.preferences(scope) / "taste.journal.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([line["revision"] for line in lines], [1, 2])
            self.assertEqual(lines[-1]["digest"], self.record(scope)["canonical_record_digest"])
            self.assertEqual(lines[-1]["generated_at"], self.record(scope)["generated_at"])
            self.assertEqual(sorted(lines[-1]), ["digest", "generated_at", "revision"])

    def test_a_refused_write_adds_nothing_to_the_journal_or_history(self):
        self.put("project", "a", "1")
        before = self.snapshot("project")
        self.refused("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", "9")
        self.refused("set", "--scope", "project", "--id", "b", "--value", "person@example.com", *self.expect("project"))
        self.assertEqual(self.snapshot("project"), before)

    def test_the_rendered_view_is_a_deterministic_reflection_of_the_record(self):
        self.put("project", "zeta", "last")
        self.put("project", "alpha", {"k": "v"})
        record = self.record("project")
        text = (self.preferences("project") / "taste.md").read_text(encoding="utf-8")
        self.assertEqual(text, taste.render(record))
        self.assertEqual(taste.render(record), taste.render(json.loads(json.dumps(record))))
        self.assertIn(f"- Revision: `{record['revision']}`", text)
        self.assertIn(f"- Digest: `{record['canonical_record_digest']}`", text)
        self.assertIn("- Scope: `project`", text)
        self.assertLess(text.index("### `alpha`"), text.index("### `zeta`"))
        self.assertIn('- Value: `{"k": "v"}`', text)
        self.assertIn("_No revoked entries._", text)

    def test_a_write_leaves_no_temporary_files_or_locks_beside_the_store(self):
        self.put("both", "a", "1")
        self.put("both", "b", "2")
        for scope in ("project", "global"):
            names = sorted(path.name for path in self.preferences(scope).iterdir())
            self.assertEqual(names, ["_history", "taste.journal.jsonl", "taste.json", "taste.md"])


class CorruptRecordTests(WriterCase):
    """A record that exists but cannot be trusted is refused whole, with its bytes preserved."""

    def corrupt(self, change) -> bytes:
        """Write a valid store, then damage it: `change` edits the parsed record or returns replacement bytes."""
        shutil.rmtree(self.project / "skillset-saves", ignore_errors=True)
        self.put("project", "a", "1")
        target = self.preferences("project") / "taste.json"
        record = json.loads(target.read_text(encoding="utf-8"))
        replacement = change(record)
        target.write_bytes(replacement if isinstance(replacement, bytes) else json.dumps(record).encode())
        return target.read_bytes()

    def test_each_kind_of_validation_failure_is_a_corrupt_record_that_keeps_its_reason(self):
        def tamper_entry(record):
            record["entries"]["a"]["value"] = "tampered"

        def wrong_scope(record):
            record["scope"]["kind"] = "global"

        def missing_key(record):
            del record["tombstones"]

        def negative_revision(record):
            record["revision"] = -1

        def entries_not_a_map(record):
            record["entries"] = []

        def other_schema(record):
            record["schema"] = "other"

        def other_version(record):
            record["schema_version"] = 2

        cases = {
            "digest no longer matches": (tamper_entry, "digest_mismatch"),
            "wrong scope kind": (wrong_scope, "invalid_record"),
            "missing required key": (missing_key, "invalid_record"),
            "negative revision": (negative_revision, "invalid_record"),
            "entries is not a map": (entries_not_a_map, "invalid_record"),
            "unknown schema": (other_schema, "invalid_schema"),
            "unknown schema version": (other_version, "invalid_schema"),
        }
        target = self.preferences("project") / "taste.json"
        for name, (change, reason) in cases.items():
            with self.subTest(name=name):
                preserved = self.corrupt(change)
                for args in (("status", "--scope", "project"), ("list", "--scope", "project"), ("effective", "--scope", "project"), ("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", "1")):
                    error = self.refused(*args)
                    self.assertEqual(error["code"], "corrupt_record", args)
                    self.assertEqual(error["reason"], reason)
                    self.assertTrue(error["detail"])
                    self.assertEqual(Path(error["path"]), target)
                    self.assertIn("repair or move", error["recovery"])
                self.assertEqual(target.read_bytes(), preserved)

    def test_a_record_that_is_not_an_object_is_a_corrupt_record(self):
        for name, content in {"list": b"[]", "string": b'"text"', "null": b"null", "number": b"7"}.items():
            with self.subTest(name=name):
                self.corrupt(lambda record, content=content: content)
                error = self.refused("list", "--scope", "project")
                self.assertEqual((error["code"], error["reason"]), ("corrupt_record", "invalid_schema"))

    def test_an_unreadable_record_is_a_corrupt_record_without_a_validation_reason(self):
        for name, content in {"not json": b"not-json\x00recovery", "truncated": b'{"schema": ', "empty": b"", "not utf-8": b"\xff\xfe\x00"}.items():
            with self.subTest(name=name):
                preserved = self.corrupt(lambda record, content=content: content)
                error = self.refused("status", "--scope", "project")
                self.assertEqual(error["code"], "corrupt_record")
                self.assertNotIn("reason", error)
                self.assertIn("unreadable", error["message"])
                self.assertEqual((self.preferences("project") / "taste.json").read_bytes(), preserved)

    def test_a_corrupt_scope_does_not_block_reading_the_intact_scope(self):
        self.put("both", "a", "1")
        (self.preferences("project") / "taste.json").write_bytes(b"{")
        self.assertEqual(list(self.ok("list", "--scope", "global")["entries"]["global"]), ["a"])
        self.assertEqual(list(self.ok("effective", "--scope", "global")["entries"]), ["a"])
        self.assertEqual(self.refused("effective", "--scope", "both")["code"], "corrupt_record")
        self.assertEqual(self.refused("status")["code"], "corrupt_record")

    def test_a_corrupt_store_refuses_a_both_write_without_touching_the_intact_store(self):
        self.put("both", "a", "1")
        (self.preferences("global") / "taste.json").write_bytes(b"{")
        before = self.snapshot("project")
        error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", "--expect-revision", "project=1", "--expect-revision", "global=1")
        self.assertEqual(error["code"], "corrupt_record")
        self.assertEqual(self.snapshot("project"), before)
        self.assertFalse((self.preferences("global") / "taste.lock").exists())
        self.assertFalse((self.preferences("project") / "taste.lock").exists())


def minutes_ago(minutes: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def dead_pid() -> int:
    """The pid of a process that has exited and been reaped."""
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


class LockTests(WriterCase):
    """A mutation holds a lock file; a writer killed while holding it must not wedge the store for good."""

    def lock_path(self, scope: str) -> Path:
        return self.preferences(scope) / "taste.lock"

    def leave_lock(self, scope: str, **fields) -> dict:
        """Leave a lock file as another writer would."""
        holder = {"pid": os.getpid(), "host": taste.host_id(), "created_at": taste.now(), "token": "another-writer", **fields}
        self.lock_path(scope).parent.mkdir(parents=True, exist_ok=True)
        self.lock_path(scope).write_text(json.dumps(holder), encoding="utf-8")
        return holder

    def journal(self, scope: str) -> list[dict]:
        path = self.preferences(scope) / "taste.journal.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []

    def test_a_live_holder_refuses_the_write_and_is_reported(self):
        holder = self.leave_lock("project")
        error = self.refused("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual(error["code"], "locked")
        self.assertEqual(error["holder_pid"], os.getpid())
        self.assertEqual(error["stale_after_seconds"], taste.LOCK_STALE_AFTER)
        self.assertIn(error["age_seconds"], range(0, 60))
        self.assertEqual(Path(error["path"]), self.lock_path("project"))
        self.assertEqual(json.loads(self.lock_path("project").read_text(encoding="utf-8")), holder)
        self.assertFalse((self.preferences("project") / "taste.json").exists())

    def test_the_lock_is_released_after_a_write_and_after_a_refusal(self):
        self.put("project", "a", "1")
        self.assertFalse(self.lock_path("project").exists())
        self.refused("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", "9")
        self.assertFalse(self.lock_path("project").exists())

    def test_a_lock_held_on_the_second_scope_leaves_no_lock_on_the_first(self):
        holder = self.leave_lock("global")
        self.assertEqual(self.refused("set", "--scope", "both", "--id", "a", "--value", "1")["code"], "locked")
        self.assertFalse(self.lock_path("project").exists())
        self.assertEqual(json.loads(self.lock_path("global").read_text(encoding="utf-8")), holder)
        self.assertFalse((self.preferences("project") / "taste.json").exists())

    @unittest.skipIf(sys.platform == "win32", "the writer cannot probe another process on Windows")
    def test_a_lock_whose_holder_process_is_gone_is_reclaimed_with_an_audit_note(self):
        pid = dead_pid()
        holder = self.leave_lock("project", pid=pid)
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        prior = {"pid": pid, "created_at": holder["created_at"]}
        self.assertEqual(result["lock_reclaimed"], [{"scope": "project", "reason": "holder-dead", "prior": prior}])
        self.assertFalse(self.lock_path("project").exists())
        note, commit = self.journal("project")
        self.assertEqual({key: note[key] for key in ("event", "scope", "reason", "prior")}, {"event": "lock_reclaimed", "scope": "project", "reason": "holder-dead", "prior": prior})
        self.assertRegex(note["at"], r"Z$")
        self.assertEqual(commit["revision"], 1)
        self.assertEqual(self.record("project")["entries"]["a"]["value"], 1)

    @unittest.skipIf(sys.platform == "win32", "the writer cannot probe another process on Windows")
    def test_a_writer_killed_while_it_holds_the_lock_does_not_wedge_the_store(self):
        hang = (
            "import importlib.util, sys, time\n"
            "spec = importlib.util.spec_from_file_location('taste_prefs', sys.argv[1])\n"
            "taste = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(taste)\n"
            "taste.mutate = lambda *args, **kwargs: time.sleep(600)\n"
            "taste.main(['--project-root', sys.argv[2], 'set', '--scope', 'project', '--id', 'a', '--value', '1'])\n"
        )
        child = subprocess.Popen([sys.executable, "-c", hang, str(SCRIPT), str(self.project)])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        def holder_pid() -> object:
            # The file exists a moment before the holder is written into it, so an empty read is not yet an answer.
            try:
                return json.loads(self.lock_path("project").read_text(encoding="utf-8")).get("pid")
            except (OSError, ValueError):
                return None

        deadline = time.time() + 30
        while holder_pid() != child.pid and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(holder_pid(), child.pid)
        error = self.refused("set", "--scope", "project", "--id", "b", "--value", "2")
        self.assertEqual((error["code"], error["holder_pid"]), ("locked", child.pid))
        child.kill()
        child.wait()
        result = self.ok("set", "--scope", "project", "--id", "b", "--value", "2")
        self.assertEqual([(note["reason"], note["prior"]["pid"]) for note in result["lock_reclaimed"]], [("holder-dead", child.pid)])
        self.assertEqual(sorted(self.record("project")["entries"]), ["b"])
        self.assertFalse(self.lock_path("project").exists())

    def test_a_lock_older_than_the_bound_is_reclaimed_even_though_its_pid_is_alive(self):
        self.leave_lock("project", created_at=minutes_ago(9))
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "a", "--value", "1")["code"], "locked")
        self.leave_lock("project", created_at=minutes_ago(11))
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual([(note["scope"], note["reason"]) for note in result["lock_reclaimed"]], [("project", "expired")])

    def test_a_fresh_lock_from_another_host_is_never_judged_by_its_pid(self):
        self.leave_lock("project", host="another-host", pid=dead_pid())
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "a", "--value", "1")["code"], "locked")

    def test_a_lock_from_another_host_is_reclaimed_by_age_alone(self):
        self.leave_lock("project", host="another-host", pid=dead_pid(), created_at=minutes_ago(11))
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual([note["reason"] for note in result["lock_reclaimed"]], ["expired"])

    def test_a_lock_without_readable_content_is_judged_by_its_file_time(self):
        for number, content in enumerate(("", "{", "[1]", '"text"', "null")):
            with self.subTest(content=content):
                path = self.lock_path("project")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                error = self.refused("set", "--scope", "project", "--id", f"id{number}", "--value", "1", *(self.expect("project") if self.revision("project") else []))
                self.assertEqual(error["code"], "locked")
                self.assertNotIn("holder_pid", error)
                old = time.time() - 11 * 60
                os.utime(path, (old, old))
                result = self.put("project", f"id{number}", "1")
                self.assertEqual([(note["reason"], note["prior"]) for note in result["lock_reclaimed"]], [("expired", {})])

    def test_a_lock_in_the_format_of_the_previous_writer_is_reclaimed_by_age(self):
        path = self.lock_path("project")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pid": dead_pid(), "created_at": taste.now()}), encoding="utf-8")
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "a", "--value", "1")["code"], "locked")
        path.write_text(json.dumps({"pid": dead_pid(), "created_at": minutes_ago(11)}), encoding="utf-8")
        result = self.ok("set", "--scope", "project", "--id", "a", "--value", "1")
        self.assertEqual([note["reason"] for note in result["lock_reclaimed"]], ["expired"])

    def test_each_scope_records_its_own_reclaim_in_its_own_journal(self):
        self.leave_lock("project", created_at=minutes_ago(11))
        self.leave_lock("global", created_at=minutes_ago(12))
        result = self.ok("set", "--scope", "both", "--id", "a", "--value", "1")
        self.assertEqual([note["scope"] for note in result["lock_reclaimed"]], ["project", "global"])
        for scope in ("project", "global"):
            notes = [entry for entry in self.journal(scope) if entry.get("event") == "lock_reclaimed"]
            self.assertEqual([note["scope"] for note in notes], [scope])
            self.assertFalse(self.lock_path(scope).exists())

    def test_a_refused_write_still_reports_the_lock_it_reclaimed(self):
        self.put("project", "a", "1")
        self.leave_lock("project", created_at=minutes_ago(11))
        code, payload = self.cli("set", "--scope", "project", "--id", "b", "--value", "2", "--expect-revision", "9")
        self.assertEqual((code, payload["error"]["code"]), (1, "stale_revision"))
        self.assertEqual([note["reason"] for note in payload["lock_reclaimed"]], ["expired"])
        self.assertEqual([entry.get("event") for entry in self.journal("project")], [None, "lock_reclaimed"])
        self.assertFalse(self.lock_path("project").exists())

    def test_a_writer_whose_lock_was_reclaimed_mid_operation_writes_nothing(self):
        self.put("project", "a", "1")
        before = self.snapshot("project")
        real_mutate = taste.mutate

        def mutate_then_lose_the_lock(*args, **kwargs):
            result = real_mutate(*args, **kwargs)
            self.lock_path("project").write_text(json.dumps({"token": "the-reclaiming-writer"}), encoding="utf-8")
            return result

        with mock.patch.object(taste, "mutate", mutate_then_lose_the_lock):
            error = self.refused("set", "--scope", "project", "--id", "b", "--value", "2", *self.expect("project"))
        self.assertEqual(error["code"], "lock_lost")
        self.assertEqual(json.loads(self.lock_path("project").read_text(encoding="utf-8"))["token"], "the-reclaiming-writer")
        self.assertEqual({path: data for path, data in self.snapshot("project").items() if path != self.lock_path("project")}, before)


class RollbackTests(WriterCase):
    """A `--scope both` write commits two stores; a failure part-way must put both back."""

    def failing_replace(self, number: int):
        """Make the number-th replace made by the writer fail, counting the rollback's own restores too."""
        real = taste.replace_with_retry
        calls = []

        def replace(source, target, *args, **kwargs):
            calls.append(target)
            if len(calls) == number:
                raise OSError("injected failure")
            return real(source, target, *args, **kwargs)

        return mock.patch.object(taste, "replace_with_retry", replace)

    def state(self) -> dict:
        """The bytes of every file a commit must restore, by scope."""
        def read(scope, name):
            path = self.preferences(scope) / name
            return path.read_bytes() if path.exists() else None

        return {scope: {name: read(scope, name) for name in ("taste.json", "taste.md", "taste.journal.jsonl")} for scope in ("project", "global")}

    def leftovers(self) -> list[Path]:
        return [path for scope in ("project", "global") if self.preferences(scope).exists() for path in self.preferences(scope).iterdir() if path.name.startswith(".taste-") or path.name == "taste.lock"]

    def test_a_failure_at_any_point_of_a_both_write_restores_both_stores_and_their_journals(self):
        self.put("both", "a", "1")
        before = self.state()
        # The forward replaces run in this order: project json, project md, global json, global md.
        for number, failing in enumerate(("project json", "project md", "global json", "global md"), start=1):
            with self.subTest(failing=failing):
                with self.failing_replace(number):
                    error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", *self.expect("project", "global"))
                self.assertEqual((error["code"], error["reason"]), ("write_failed", "injected failure"))
                self.assertEqual(self.state(), before)
                self.assertEqual(self.leftovers(), [])
        self.put("both", "b", "2")
        self.assertEqual((self.revision("project"), self.revision("global")), (2, 2))
        self.assertEqual([line["revision"] for line in [json.loads(text) for text in (self.preferences("project") / "taste.journal.jsonl").read_text(encoding="utf-8").splitlines()]], [1, 2])

    def test_a_failed_first_write_of_a_pair_leaves_no_store_behind(self):
        with self.failing_replace(3):
            self.assertEqual(self.refused("set", "--scope", "both", "--id", "a", "--value", "1")["code"], "write_failed")
        self.assertEqual(self.snapshot("project", "global"), {})
        self.assertFalse(self.ok("status")["stores"]["project"]["exists"])
        self.put("both", "a", "1")
        self.assertEqual((self.revision("project"), self.revision("global")), (1, 1))

    def test_a_failure_while_journaling_restores_the_stores_too(self):
        self.put("both", "a", "1")
        before = self.state()
        real_open = Path.open
        global_journal = self.preferences("global") / "taste.journal.jsonl"

        def journal_unavailable(path, mode="r", *args, **kwargs):
            if path == global_journal and "a" in mode:
                raise OSError("journal unavailable")
            return real_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", journal_unavailable):
            error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", *self.expect("project", "global"))
        self.assertEqual((error["code"], error["reason"]), ("write_failed", "journal unavailable"))
        self.assertEqual(self.state(), before)
        self.assertEqual(self.leftovers(), [])

    def test_a_rollback_that_cannot_restore_a_file_reports_it_and_keeps_its_backup(self):
        self.put("both", "a", "1")
        before = self.state()
        project_md = self.preferences("project") / "taste.md"
        real = taste.replace_with_retry
        calls = []

        def replace(source, target, *args, **kwargs):
            calls.append(target)
            if len(calls) == 3:
                raise OSError("injected failure")
            if Path(source).name.startswith(".taste-rollback-") and Path(target) == project_md:
                raise OSError("restore refused")
            return real(source, target, *args, **kwargs)

        with mock.patch.object(taste, "replace_with_retry", replace):
            error = self.refused("set", "--scope", "both", "--id", "b", "--value", "2", *self.expect("project", "global"))
        self.assertEqual((error["code"], error["reason"]), ("write_failed", "injected failure"))
        self.assertIn("incomplete", error["message"])
        self.assertEqual([Path(item["path"]) for item in error["unrestored"]], [project_md])
        backup = Path(error["unrestored"][0]["backup"])
        self.assertEqual(backup.read_bytes(), before["project"]["taste.md"])
        after = self.state()
        self.assertNotEqual(after["project"]["taste.md"], before["project"]["taste.md"])
        for scope, name in (("project", "taste.json"), ("project", "taste.journal.jsonl"), ("global", "taste.json"), ("global", "taste.md"), ("global", "taste.journal.jsonl")):
            self.assertEqual(after[scope][name], before[scope][name], (scope, name))

    def test_a_transient_permission_error_on_replace_does_not_fail_the_write(self):
        real, calls = os.replace, []

        def replace(source, target):
            calls.append(target)
            if len(calls) == 1:
                raise PermissionError("held open by another process")
            return real(source, target)

        with mock.patch.object(taste.os, "replace", replace), mock.patch.object(taste.time, "sleep") as slept:
            self.put("project", "a", "1")
        self.assertEqual(slept.call_args_list, [mock.call(0.05)])
        self.assertEqual(self.record("project")["entries"]["a"]["value"], "1")
        self.assertEqual(self.leftovers(), [])


WORKER = r'''
import contextlib, importlib.util, io, json, sys, time
script, project, worker, writes = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
spec = importlib.util.spec_from_file_location("taste_prefs", script)
taste = importlib.util.module_from_spec(spec)
spec.loader.exec_module(taste)


def run(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        taste.main(["--project-root", project, *args])
    return json.loads(out.getvalue())


done, deadline = 0, time.time() + 60
while done < writes and time.time() < deadline:
    args = ["set", "--scope", "both", "--id", f"w{worker}-{done}", "--value", json.dumps(done)]
    for scope in ("project", "global"):
        store = run("status", "--scope", scope)["stores"][scope]
        if store["exists"]:
            args += ["--expect-revision", f"{scope}={store['revision']}"]
    result = run(*args)
    if result["ok"]:
        done += 1
    elif result["error"]["code"] not in ("locked", "stale_revision", "revision_required"):
        print(json.dumps(result))
        sys.exit(1)
    else:
        time.sleep(0.005)
sys.exit(0 if done == writes else 2)
'''


class ConcurrencyTests(unittest.TestCase):
    """Real processes contending for one store: every acknowledged write survives and none is torn."""

    WORKERS, WRITES = 6, 6

    def test_concurrent_writers_lose_no_acknowledged_write_and_keep_both_chains_intact(self):
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as global_dir:
            project, global_home = Path(project_dir).resolve(), Path(global_dir).resolve()
            env = {**os.environ, "SUPREMETEAM_HOME": str(global_home), "SUPREMETEAM_OWNER": "test-owner"}
            workers = [subprocess.Popen([sys.executable, "-c", WORKER, str(SCRIPT), str(project), str(n), str(self.WRITES)], env=env, stdout=subprocess.PIPE, text=True) for n in range(self.WORKERS)]
            outputs = [worker.communicate(timeout=120)[0] for worker in workers]
            self.assertEqual([worker.returncode for worker in workers], [0] * self.WORKERS, outputs)
            total = self.WORKERS * self.WRITES
            for scope, base in (("project", project / "skillset-saves" / "preferences"), ("global", global_home / "preferences")):
                with self.subTest(scope=scope):
                    current = json.loads((base / "taste.json").read_text(encoding="utf-8"))
                    self.assertEqual(current["revision"], total)
                    self.assertEqual(sorted(current["entries"]), sorted(f"w{n}-{i}" for n in range(self.WORKERS) for i in range(self.WRITES)))
                    self.assertEqual(taste.validate(current, scope), current)
                    journal = [json.loads(line) for line in (base / "taste.journal.jsonl").read_text(encoding="utf-8").splitlines()]
                    self.assertEqual([line["revision"] for line in journal], list(range(1, total + 1)))
                    revisions = {}
                    for path in (base / "_history").glob("*.json"):
                        record = json.loads(path.read_text(encoding="utf-8"))
                        revisions[record["revision"]] = record
                    revisions[total] = current
                    self.assertEqual(sorted(revisions), list(range(1, total + 1)))
                    for revision in range(2, total + 1):
                        self.assertEqual(revisions[revision]["previous_revision_digest"], revisions[revision - 1]["canonical_record_digest"])
                    self.assertEqual(sorted(path.name for path in base.iterdir()), ["_history", "taste.journal.jsonl", "taste.json", "taste.md"])


class SafetyCliTests(WriterCase):
    """The validators as a caller meets them: what is written, refused, redacted, and tolerated."""

    SECRETS = ("sk-abcdefghijklmnopqrstuvwxyz123456", "sk_" "live_abcdefghijklmnopqrstuvwx", "gh" "p_abcdefghijklmnopqrstuvwxyz0123456789", "person@example.com", "Bearer abcdefghijklmnop1234", "-----BEGIN PRIVATE KEY-----")

    def test_ordinary_design_vocabulary_is_written_as_a_value(self):
        phrases = ["skeleton-loading-states", "skeuomorphic-glass-theme", "sketchy-hand-drawn-icons", "prefer skeleton-loading states over spinners", "skeleton_placeholders", "sketch-style-illustrations", "Bearer of bad news is fine"]
        for number, phrase in enumerate(phrases):
            self.put("project", f"vocabulary.n{number}", phrase)
        self.assertEqual({item["value"] for item in self.record("project")["entries"].values()}, set(phrases))

    def test_ordinary_design_vocabulary_is_written_as_a_field_name(self):
        keys = ["design-tokens", "phone-layout", "email-density", "cookie-banner", "address-bar", "prompt-style"]
        self.put("project", "vocabulary.fields", {key: "x" for key in keys})
        self.assertEqual(sorted(self.record("project")["entries"]["vocabulary.fields"]["value"]), sorted(keys))

    def test_real_secrets_and_personal_identifiers_are_still_refused_as_values_and_never_echoed(self):
        for secret in self.SECRETS:
            with self.subTest(secret=secret):
                error = self.refused("set", "--scope", "project", "--id", "a", "--value", json.dumps(f"note {secret} end"))
                self.assertEqual((error["code"], error["field"]), ("sensitive_input", "$"))
                self.assertNotIn(secret, json.dumps(error))
        self.assertEqual(self.snapshot("project"), {})

    def test_redact_replaces_a_secret_value_and_drops_a_sensitive_field(self):
        self.ok("set", "--scope", "project", "--redact", "--id", "a", "--value", json.dumps({"note": "mail person@example.com", "password": "x", "density": "compact"}))
        self.assertEqual(self.record("project")["entries"]["a"]["value"], {"note": "[REDACTED]", "density": "compact"})

    def test_credential_and_personal_field_names_are_still_refused_inside_a_value(self):
        for key in ("password", "api_key", "user_email", "phone_number", "home_address", "access_token", "session_cookie", "system_prompt", "conversation_history", "full_name", "ssn"):
            with self.subTest(key=key):
                error = self.refused("set", "--scope", "project", "--id", "a", "--value", json.dumps({"outer": {key: "x"}}))
                self.assertEqual((error["code"], error["field"]), ("sensitive_input", f"$.outer.{key}"))
        self.assertEqual(self.snapshot("project"), {})

    def test_an_id_that_embeds_a_secret_or_names_a_credential_or_personal_datum_is_refused_when_written(self):
        for entry_id in ("user.email", "login.password", "contact.phone", "home.address", "user.name", "api-key", "sk-abcdefghijklmnopqrstuvwxyz123456", "gh" "p_abcdefghijklmnopqrstuvwxyz0123456789"):
            for command, value in (("set", '"x"'), ("propose", json.dumps(proposal()))):
                with self.subTest(entry_id=entry_id, command=command):
                    error = self.refused(command, "--scope", "project", f"--id={entry_id}", "--redact", "--value", value)
                    self.assertEqual((error["code"], error["field"]), ("sensitive_input", "id"))
                    self.assertNotIn(entry_id, json.dumps(error))
        self.assertEqual(self.snapshot("project"), {})

    def test_an_id_made_of_design_vocabulary_is_written_and_survives_an_export(self):
        ids = ["ui.design-tokens", "layout.phone-breakpoints", "nav.address-bar-position", "cli.prompt-style", "banner.cookie-consent-layout", "forms.email-input-style"]
        for entry_id in ids:
            self.put("project", entry_id, "compact")
        output = self.project / "export.json"
        payload = self.ok("export", "--output", str(output))
        self.assertEqual(payload["redactions"], [])
        self.assertEqual(sorted(json.loads(output.read_text(encoding="utf-8"))["entries"]), sorted(ids))

    def test_promote_and_specialize_refuse_a_stored_id_that_names_a_personal_datum_but_it_can_still_be_retired(self):
        stamp = "2026-01-01T00:00:00Z"
        entry = {"state": "active", "value": "x", "updated_at": stamp}
        self.write_store("project", {"contact.phone": entry})
        self.write_store("global", {"contact.phone": entry})
        for command, scope in (("promote", "global"), ("specialize", "project")):
            error = self.refused(command, "--scope", scope, "--id", "contact.phone", *self.expect(scope))
            self.assertEqual((error["code"], error["field"]), ("sensitive_input", "id"))
        self.assertIn("contact.phone", self.ok("list")["entries"]["project"])
        self.ok("deprecate", "--scope", "project", "--id", "contact.phone", *self.expect("project"))
        self.ok("revoke", "--scope", "project", "--id", "contact.phone", *self.expect("project"))
        self.assertIn("contact.phone", self.record("project")["tombstones"])

    def test_a_secret_in_overlong_text_cannot_slip_through_redaction(self):
        key = "sk-abcdefghijklmnopqrstuvwxyz123456"
        cases = {"at the start": "person@example.com " + "x" * 1100, "straddling the cut": "x" * 989 + " " + key + " " + "y" * 200}
        for number, (name, text) in enumerate(cases.items()):
            with self.subTest(name=name):
                overlong = self.refused("set", "--scope", "project", "--id", f"long{number}", "--value", json.dumps(text), *(self.expect("project") if self.revision("project") else []))
                self.assertEqual(overlong["code"], "unbounded_input")
                self.put_redacted(f"long{number}", text)
                self.assertEqual(self.record("project")["entries"][f"long{number}"]["value"], "[REDACTED]")
        stored = json.dumps(self.record("project"))
        self.assertNotIn("person@example.com", stored)
        self.assertNotIn(key[:12], stored)

    def put_redacted(self, entry_id: str, value: object) -> dict:
        return self.ok("set", "--scope", "project", "--redact", "--id", entry_id, "--value", json.dumps(value), *(self.expect("project") if self.revision("project") else []))

    def test_clean_overlong_text_is_truncated_under_redact_and_refused_without_it(self):
        text = "x" * 1500
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "long", "--value", json.dumps(text))["code"], "unbounded_input")
        self.put_redacted("long", text)
        self.assertEqual(self.record("project")["entries"]["long"]["value"], "x" * 1000 + "[REDACTED:TRUNCATED]")

    def test_lists_and_text_are_bounded(self):
        self.assertEqual(self.refused("set", "--scope", "project", "--id", "many", "--value", json.dumps(list(range(101))))["code"], "unbounded_input")
        self.put("project", "hundred", list(range(100)))
        self.put("project", "limit", "x" * 1000)

    def test_a_proposal_must_carry_the_doctrine_fields_and_a_set_need_not(self):
        error = self.refused("propose", "--scope", "project", "--id", "a", "--value", '"just text"')
        self.assertEqual(error["code"], "invalid_entry")
        error = self.refused("propose", "--scope", "project", "--id", "a", "--value", json.dumps(proposal(category="colour")))
        self.assertEqual((error["code"], error["field"], error["allowed"]), ("invalid_entry", "category", list(taste.CATEGORIES)))
        self.assertEqual(self.snapshot("project"), {})
        self.put("project", "a", proposal(), command="propose")
        self.put("project", "b", "just text")
        self.put("project", "c", {"anything": "goes"})

    def test_entries_stored_before_the_doctrine_fields_were_enforced_remain_usable(self):
        stamp = "2026-01-01T00:00:00Z"

        def entry(state, value):
            return {"state": state, "value": value, "updated_at": stamp}

        self.write_store("project", {"plain": entry("active", "compact"), "candidate": entry("proposed", "free text"), "odd": entry("active", {"category": "not-in-the-registry"}), "retire": entry("active", "x"), "old": entry("active", "y")})
        self.ok("list")
        self.ok("effective")
        self.assertEqual(self.ok("diff")["differences"][0]["id"], "candidate")
        self.ok("export", "--output", str(self.project / "export.json"))
        self.ok("confirm", "--scope", "project", "--id", "candidate", *self.expect("project"))
        self.ok("deprecate", "--scope", "project", "--id", "old", *self.expect("project"))
        self.ok("revoke", "--scope", "project", "--id", "retire", *self.expect("project"))
        self.ok("promote", "--scope", "global", "--id", "odd")
        self.assertEqual(sorted(self.ok("effective")["entries"]), ["candidate", "odd", "plain"])


if __name__ == "__main__":
    unittest.main()
