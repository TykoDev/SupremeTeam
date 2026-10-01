#!/usr/bin/env python3
"""In-process regression tests for the manifest engine (check.py).

The command-line tests in test_gate_manifests.py, test_gate_run_layout.py and
test_gate_revise.py pin end-to-end behaviour one package at a time. These drive a
``Package`` directly, which is what lets a matrix - every waivable key at every
boundary, every evidence type the spec declares - run in milliseconds instead of
paying one interpreter start per cell, and lets a fault be injected where a
subprocess could not reach it.
"""
from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import chdir, redirect_stderr, redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

SKILLS = Path(__file__).resolve().parents[2]
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"
GATE_SPEC = SKILLS / "gates.yaml"
sys.path.insert(0, str(SKILLS / "scripts"))
sys.path.insert(0, str(CHECK.parent))
import _gatecheck as gc  # noqa: E402
from data_formats import content_sha256  # noqa: E402


def load_engine():
    spec = importlib.util.spec_from_file_location("gate_check_engine", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


engine = load_engine()


class EngineCase(unittest.TestCase):
    """A scratch directory and a way to build a ``Package`` without touching disk twice."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.spec = engine.load_gate_spec(GATE_SPEC)

    def package(self, boundary: str, evidence: dict | None = None, **manifest):
        data = {"schema_version": 2, "boundary": boundary, "owner": self.spec["boundaries"][boundary]["submitter"],
                "submission_id": "s1", "revision": "r1", "revisions": ["r1"],
                "evidence": evidence or {}, "artifact_hashes": {}}
        data.update(manifest)
        return engine.Package(self.root / "manifest.json", data, boundary, self.spec)


class WaiverWordingTests(EngineCase):
    """A waiver is the sanctioned wording and nothing else (gates.yaml fallback_values)."""

    def waivable(self):
        """Every (boundary, key, sanctioned wordings) the spec lets a submitter waive."""
        for boundary, contract in self.spec["boundaries"].items():
            barred = set(contract.get("no_fallback") or [])
            declared = set(self.spec["fallback_values"]) | set(contract.get("fallback_values", {}))
            for key in sorted((declared & set(contract["required_evidence"])) - barred):
                yield boundary, key, contract.get("fallback_values", {}).get(key) or self.spec["fallback_values"][key]

    @staticmethod
    def record(reason):
        return {"applicable": False, "reason": reason, "scope": "whole run", "decided_by": "owner"}

    def test_a_reason_other_than_the_sanctioned_wording_never_waives_a_key(self):
        cells = 0
        for boundary, key, allowed in self.waivable():
            unsanctioned = ("covered elsewhere", "skipped", allowed[0].upper(), allowed[0] + " ", " " + allowed[0])
            for reason in unsanctioned:
                with self.subTest(boundary=boundary, key=key, reason=reason):
                    package = self.package(boundary)
                    self.assertTrue(package.applicability_record(key, self.record(reason)))
                    self.assertEqual(len(package.failures), 1, package.failures)
                    self.assertTrue(package.failures[0].startswith(f"applicability reason not sanctioned: {key} "),
                                    package.failures)
                    cells += 1
        self.assertGreater(cells, 60, "the matrix silently emptied")

    def test_an_empty_or_non_string_reason_is_an_incomplete_record(self):
        for boundary, key, allowed in self.waivable():
            for reason in ("", "   ", None, 7, False, [allowed[0]], {"text": allowed[0]}):
                with self.subTest(boundary=boundary, key=key, reason=reason):
                    package = self.package(boundary)
                    self.assertTrue(package.applicability_record(key, self.record(reason)))
                    self.assertEqual(package.failures, [f"applicability record incomplete: {key} requires reason"])

    def test_each_sanctioned_wording_waives_its_key_at_its_boundary(self):
        cells = 0
        for boundary, key, allowed in self.waivable():
            for wording in allowed:
                with self.subTest(boundary=boundary, key=key, wording=wording):
                    package = self.package(boundary)
                    self.assertTrue(package.applicability_record(key, self.record(wording)))
                    self.assertEqual(package.failures, [])
                    cells += 1
        self.assertGreater(cells, 15, "the matrix silently emptied")

    def test_a_boundary_list_replaces_the_global_wording_rather_than_adding_to_it(self):
        """At redesign-review rendered_verification stands down on the selection wordings only."""
        package = self.package("redesign-review")
        global_wording = self.spec["fallback_values"]["rendered_verification"][0]
        self.assertTrue(package.applicability_record("rendered_verification", self.record(global_wording)))
        self.assertEqual(len(package.failures), 1, package.failures)
        self.assertTrue(package.failures[0].startswith("applicability reason not sanctioned: rendered_verification "))

    def test_the_wording_is_owned_by_the_key_not_borrowed_from_another(self):
        package = self.package("build-to-review")
        borrowed = self.spec["fallback_values"]["stack_lock"][0]
        self.assertTrue(package.applicability_record("security_evidence", self.record(borrowed)))
        self.assertEqual(len(package.failures), 1, package.failures)
        self.assertTrue(package.failures[0].startswith("applicability reason not sanctioned: security_evidence "))

    def test_a_key_the_boundary_does_not_list_is_not_waivable_whatever_the_wording(self):
        package = self.package("build-to-review")
        self.assertTrue(package.applicability_record("implementation", self.record("anything at all")))
        self.assertEqual(package.failures, ["evidence not waivable: implementation"])


class NewFailureRoutingTests(EngineCase):
    """A REVISE routes each failure to the owner of the key it names, by finding the key in the message."""

    def route(self, boundary: str, package: engine.Package) -> dict:
        contract = self.spec["boundaries"][boundary]
        return engine.revise_packet(sorted(package.failures), list(contract["required_evidence"]),
                                    self.spec["evidence_owners"][boundary], contract["submitter"])

    def test_a_refused_waiver_goes_to_the_key_owner(self):
        package = self.package("security-review")
        package.applicability_record("vulnerability_scan", WaiverWordingTests.record("covered elsewhere"))
        packet = self.route("security-review", package)
        self.assertEqual(list(packet["by_key"]), ["vulnerability_scan"])
        self.assertEqual(list(packet["by_owner"]), ["security-review"])

    def test_a_contradictory_record_goes_to_the_key_owner(self):
        package = self.package("build-to-review")
        package.check_result_record("tests", "probe", {"artifacts": ["log.txt"], "result": {"status": "pass"}, "exit_code": 1})
        packet = self.route("build-to-review", package)
        self.assertEqual((list(packet["by_key"]), list(packet["by_owner"])), (["tests"], ["test-builder"]))

    def test_a_handoff_digest_mismatch_goes_to_the_handoff_owner_not_the_profile_owner(self):
        package = self.package("taste-review", {"effective_profile": {"entries": [], "digest": "a" * 64}})
        package.check_taste_record("consumer_handoff", "consumer_handoff",
                                   {"consuming_pipeline": "design", "effective_profile_digest": "b" * 64,
                                    "applicability_summary": "UI"})
        self.assertEqual(list(self.route("taste-review", package)["by_key"]), ["consumer_handoff"])

    def test_a_missing_overlay_goes_to_the_stack_lock_owner(self):
        digest = StackLockTests.registry(self, overlay_file=False)
        package = self.package("design-to-build")
        package.check_stack_lock("stack_lock", {"slug": "demo", "versions": [19], "overlay_sha256": digest})
        self.assertEqual(list(self.route("design-to-build", package)["by_owner"]), ["commander"])

    def test_the_run_schema_failure_names_no_key_so_it_goes_to_the_submitter(self):
        run = self.root / "skillset-saves" / "runs" / "run-a" / "review"
        run.mkdir(parents=True)
        package = engine.Package(run / "manifest.json", {"boundary": "review-to-delivery"}, "review-to-delivery", self.spec)
        packet = self.route("review-to-delivery", package)
        self.assertEqual(packet["by_key"], {})
        self.assertEqual(list(packet["by_owner"]), ["code-chief"])
        self.assertTrue(any(f.startswith("manifest inside a run must declare schema_version 2") for f in packet["unassigned"]),
                        packet["unassigned"])


class PolicyFieldTests(EngineCase):
    """A field that means "someone named this" counts only when it is a real string.

    ``str(item.get(f, ""))`` made an explicit JSON null the truthy word "None", so
    a Major deferred with owner null, a Critical waived with reason null, or a
    REVISE with a null challenge passed the finding policy.
    """

    NOT_FILLED = (None, "", "   ", 0, 1, False, True, [], ["owner"], {}, {"name": "owner"})

    def failures_of(self, check: str, *args) -> list[str]:
        package = self.package("review-to-delivery")
        getattr(package, check)(*args)
        return package.failures

    def test_a_deferred_major_needs_a_real_owner_and_a_real_reopen_trigger(self):
        real = {"id": "F1", "severity": "Major", "status": "deferred",
                "owner": "build-management", "reopen_trigger": "before release"}
        self.assertEqual(self.failures_of("check_findings", "findings", {"items": [real]}), [])
        for field in ("owner", "reopen_trigger"):
            for bad in self.NOT_FILLED:
                with self.subTest(field=field, bad=bad):
                    self.assertEqual(
                        self.failures_of("check_findings", "findings", {"items": [{**real, field: bad}]}),
                        ["findings[0] unresolved Major finding blocks the gate (status deferred)"])
            absent = {k: v for k, v in real.items() if k != field}
            self.assertEqual(
                self.failures_of("check_findings", "findings", {"items": [absent]}),
                ["findings[0] unresolved Major finding blocks the gate (status deferred)"])

    def test_a_not_applicable_finding_needs_a_real_reason(self):
        for severity in ("Critical", "Major", "Minor"):
            item = {"id": "F1", "severity": severity, "status": "not-applicable", "reason": "scope excludes it"}
            self.assertEqual(self.failures_of("check_findings", "findings", {"items": [item]}), [])
            for bad in self.NOT_FILLED:
                with self.subTest(severity=severity, bad=bad):
                    self.assertEqual(
                        self.failures_of("check_findings", "findings", {"items": [{**item, "reason": bad}]}),
                        ["findings[0] not-applicable requires a reason"])

    def test_a_non_approved_verdict_needs_a_real_challenge_by_and_reason(self):
        challenge = {"by": "code-chief", "reason": "finding disputed with evidence"}
        self.assertEqual(self.failures_of("check_verdict", "review_verdict",
                                          {"recommendation": "REVISE", "challenge": challenge}), [])
        expected = ["review_verdict recommendation REVISE without a challenge record"]
        for field in ("by", "reason"):
            for bad in self.NOT_FILLED:
                with self.subTest(field=field, bad=bad):
                    self.assertEqual(
                        self.failures_of("check_verdict", "review_verdict",
                                         {"recommendation": "REVISE", "challenge": {**challenge, field: bad}}),
                        expected)
        for bad in (None, "why not", ["by", "reason"]):
            with self.subTest(challenge=bad):
                self.assertEqual(self.failures_of("check_verdict", "review_verdict",
                                                  {"recommendation": "ESCALATE", "challenge": bad}),
                                 ["review_verdict recommendation ESCALATE without a challenge record"])

    def test_effective_profile_entries_need_real_id_scope_and_source(self):
        digest = "a" * 64
        entry = {"id": "p1", "source_scope": "repository", "source_id": "run-1"}
        good = {"entries": [entry], "digest": digest}
        self.assertEqual(self.failures_of("check_taste_record", "effective_profile", "effective_profile", good), [])
        for field in entry:
            for bad in self.NOT_FILLED:
                with self.subTest(field=field, bad=bad):
                    failures = self.failures_of("check_taste_record", "effective_profile", "effective_profile",
                                                {**good, "entries": [{**entry, field: bad}]})
                    self.assertEqual(failures, ["effective_profile.entries[0] requires id, source_scope, and source_id"])

    def test_scan_tool_command_and_observed_at_need_real_strings(self):
        record = {"artifacts": ["scan.stdout.txt"], "tool": "pip-audit", "command": "pip-audit -r requirements.txt",
                  "observed_at": "2026-09-05T00:00:00Z", "exit_code": 0, "result": {"status": "pass"}}
        for field in ("tool", "command", "observed_at"):
            for bad in self.NOT_FILLED:
                with self.subTest(field=field, bad=bad):
                    failures = self.failures_of("check_result_record", "vulnerability_scan", "scan", {**record, field: bad})
                    self.assertIn(f"vulnerability_scan scan record requires {field}", failures)

    def test_an_inferred_render_needs_a_real_limitation(self):
        record = {"captures": ["capture.png"], "breakpoints": ["375"], "themes": ["light"],
                  "result": {"status": "inferred"}, "inputs": []}
        for bad in self.NOT_FILLED:
            with self.subTest(bad=bad):
                failures = self.failures_of("check_result_record", "rendered_verification", "render",
                                            {**record, "limitation": bad})
                self.assertIn("rendered_verification inferred render requires a limitation statement", failures)

    def test_a_variant_needs_a_real_id_and_real_file_fields(self):
        params = self.spec["evidence_type_params"]["selected_variant"]
        entry = {"id": "m2", "name": "Direction 2", "direction": "d2", **{f: "artifacts/x.css" for f in params["file_fields"]}}
        for bad in self.NOT_FILLED:
            with self.subTest(bad=bad):
                package = self.package("redesign-review")
                package.check_variant_set("selected_variant", {"variants": [{**entry, "id": bad}], "count": 1})
                self.assertIn("selected_variant.variants[0] requires id", package.failures)
                self.assertFalse(any("duplicate id" in f for f in package.failures), package.failures)
                package = self.package("redesign-review")
                package.check_variant_set("selected_variant", {"variants": [{**entry, "spec": bad}], "count": 1})
                self.assertIn("selected_variant.variants[0] requires spec", package.failures)

    def test_a_built_variant_with_no_real_id_is_not_the_chosen_one(self):
        package = self.package("redesign-review", {
            "selection": {"decision": "variant", "chosen": "None", "recommended": "None"},
            "selected_variant": {"variants": [{"id": None}]}})
        package.check_selection_dependencies("selection")
        self.assertTrue(any("was built for '' but selection chose 'None'" in f for f in package.failures), package.failures)


class ResultRecordConsistencyTests(EngineCase):
    """A typed record is the submitter's own statement; the gate refuses the contradiction it can see."""

    EXTRA = {
        "probe": {},
        "scan": {"tool": "pip-audit", "command": "pip-audit -r requirements.txt", "observed_at": "2026-09-05T00:00:00Z"},
        "render": {"breakpoints": ["375", "1280"], "themes": ["light", "dark"]},
    }

    def record(self, kind: str, **fields) -> dict:
        return {"artifacts": ["evidence/log.txt"], "result": {"status": "pass"}, **self.EXTRA[kind], **fields}

    def check(self, kind: str, record: dict, key: str = "tests") -> engine.Package:
        package = self.package("build-to-review")
        package.check_result_record(key, kind, record)
        return package

    def test_a_pass_beside_a_non_zero_exit_code_is_refused_for_every_result_kind(self):
        for kind in self.EXTRA:
            for code in (1, 2, 7, 137, -1):
                with self.subTest(kind=kind, code=code):
                    package = self.check(kind, self.record(kind, exit_code=code))
                    self.assertIn(f"tests result pass contradicts exit_code {code}", package.failures)

    def test_a_pass_with_a_zero_or_an_absent_exit_code_is_not_contradicted(self):
        for fields in ({"exit_code": 0}, {}, {"exit_code": None}):
            with self.subTest(fields=fields):
                package = self.check("probe", self.record("probe", **fields))
                self.assertFalse(any("exit_code" in f for f in package.failures), package.failures)

    def test_an_exit_code_that_is_not_an_integer_is_refused(self):
        for kind in self.EXTRA:
            for bad in ("0", 0.0, 1.5, True, False, [0], {"code": 0}):
                with self.subTest(kind=kind, bad=bad):
                    package = self.check(kind, self.record(kind, exit_code=bad))
                    self.assertIn("tests exit_code must be an integer", package.failures)

    def test_a_scan_that_passes_must_carry_an_exit_code_of_zero(self):
        self.assertIn("tests scan record with result pass requires exit_code 0",
                      self.check("scan", self.record("scan", exit_code=None)).failures)
        clean = self.check("scan", self.record("scan", exit_code=0,
                                               inputs=[]))  # inputs fail separately; exit_code must not
        self.assertFalse(any("exit_code" in f for f in clean.failures), clean.failures)

    def test_a_non_passing_status_reports_only_its_own_failure(self):
        package = self.check("scan", self.record("scan", exit_code=None, result={"status": "unavailable"}))
        self.assertIn("tests result not passing: unavailable", package.failures)
        self.assertFalse(any("exit_code" in f for f in package.failures), package.failures)

    def bound_record(self, kind: str = "probe") -> dict:
        source = self.root / "src.py"
        source.write_text("x = 1\n", encoding="utf-8")
        return self.record(kind, inputs=[{"path": "src.py", "sha256": content_sha256(source)}])

    def test_a_probe_that_binds_no_inputs_is_listed_as_attested(self):
        package = self.check("probe", self.record("probe"))
        self.assertEqual(package.failures, [])
        self.assertEqual(package.warnings, ["tests binds no inputs: attested, not tied to the source it describes"])

    def test_a_probe_with_verified_inputs_is_not_listed(self):
        package = self.check("probe", self.bound_record())
        self.assertEqual((package.failures, package.warnings), ([], []))

    def test_a_probe_input_that_drifted_fails_as_stale_evidence(self):
        record = self.bound_record()
        (self.root / "src.py").write_text("x = 2\n", encoding="utf-8")
        self.assertEqual(self.check("probe", record).failures, ["tests input hash drift (stale evidence): src.py"])

    def test_scan_and_render_records_fail_instead_of_warning_when_they_bind_nothing(self):
        for kind in ("scan", "render"):
            with self.subTest(kind=kind):
                package = self.check(kind, self.record(kind, exit_code=0))
                self.assertIn("tests record must bind inputs (path + sha256) to the inspected source", package.failures)
                self.assertEqual(package.warnings, [])


class StackLockTests(EngineCase):
    """A stack lock names an overlay the registry offers, at versions it offers, with the file present."""

    def registry(self, *, overlay_file: bool = True, versions: object = (19, 15), extra: dict | None = None) -> str:
        """A one-overlay registry under the scratch directory; returns the overlay's real digest."""
        tech_stacks = self.root / "catalog" / "tech-stacks"
        tech_stacks.mkdir(parents=True, exist_ok=True)
        overlay = tech_stacks / "demo.md"
        overlay.write_text("# Demo overlay\n\nPinned guidance.\n", encoding="utf-8")
        digest = content_sha256(overlay)
        if not overlay_file:
            overlay.unlink()
        entry = {"slug": "demo", "path": "tech-stacks/demo.md", "framework": "Demo", "sha256": digest}
        if versions is not None:
            entry["versions"] = list(versions)
        registry = tech_stacks / "registry.yaml"
        registry.write_text(json.dumps({"schema_version": 1, "kind": "supremeteam-tech-stack-registry",
                                        "overlays": [entry], **(extra or {})}), encoding="utf-8")
        self.spec["_registry_path"] = str(registry)
        return digest

    def checked(self, record: dict):
        package = self.package("design-to-build")
        package.check_stack_lock("stack_lock", record)
        return package

    def failures(self, record: dict) -> list[str]:
        return self.checked(record).failures

    def test_a_lock_on_an_offered_overlay_and_versions_passes(self):
        digest = self.registry()
        for versions in ([19], [19, 15], ["19"], [15, "19"]):
            with self.subTest(versions=versions):
                self.assertEqual(self.failures({"slug": "demo", "versions": versions, "overlay_sha256": digest}), [])

    def test_every_declared_version_must_be_offered_not_just_one(self):
        digest = self.registry()
        for versions, unoffered in (([19, 99], [99]), ([99, 19], [99]), (["18", 19, "17"], ["18", "17"]), ([99], [99])):
            with self.subTest(versions=versions):
                self.assertEqual(
                    self.failures({"slug": "demo", "versions": versions, "overlay_sha256": digest}),
                    [f"stack_lock versions {unoffered} not offered by registry entry demo"])

    def test_a_registry_entry_that_offers_no_versions_cannot_vouch_for_any(self):
        digest = self.registry(versions=None)
        self.assertEqual(self.failures({"slug": "demo", "versions": [19], "overlay_sha256": digest}),
                         ["stack_lock versions [19] not offered by registry entry demo"])

    def test_a_missing_overlay_file_fails_instead_of_verifying_only_the_registry_string(self):
        digest = self.registry(overlay_file=False)
        self.assertEqual(self.failures({"slug": "demo", "versions": [19], "overlay_sha256": digest}),
                         ["stack_lock overlay file for demo is missing: tech-stacks/demo.md"])

    def test_an_overlay_file_changed_since_the_registry_recorded_it_still_fails(self):
        digest = self.registry()
        (self.root / "catalog" / "tech-stacks" / "demo.md").write_text("# Edited\n", encoding="utf-8")
        self.assertEqual(self.failures({"slug": "demo", "versions": [19], "overlay_sha256": digest}),
                         ["stack_lock overlay file digest does not match declared overlay_sha256"])


    # QR-13: the registry recorded `support_ends` and `verified_at`, and nothing read them. A lock on
    # a stack past its date still passes (picking a supported version is the owner's decision, not
    # the gate's), so the only way the reader hears of it is the result's warnings.

    TODAY = date(2026, 10, 1)

    def setUp(self):
        super().setUp()
        # One fixed date for the engine and the test: two reads of the clock disagree for a moment at 00:00 UTC.
        patch = mock.patch.object(engine, "utc_today", return_value=self.TODAY)
        patch.start()
        self.addCleanup(patch.stop)

    def lock(self, **extra) -> object:
        digest = self.registry(extra=extra)
        return self.checked({"slug": "demo", "versions": [19], "overlay_sha256": digest})

    def days_ago(self, days: int) -> str:
        return (self.TODAY - timedelta(days=days)).isoformat()

    def test_a_lock_on_a_stack_past_its_end_of_support_passes_with_a_warning(self):
        package = self.lock(support_ends={"demo": "2000-01-01"})
        self.assertEqual(package.failures, [])
        self.assertEqual(len(package.warnings), 1, package.warnings)
        self.assertIn("support for the demo stack ended on 2000-01-01", package.warnings[0])

    def test_a_stack_still_in_support_or_another_stacks_date_is_not_a_warning(self):
        for extra in ({"support_ends": {"demo": "2999-12-31"}}, {"support_ends": {"other": "2000-01-01"}}, {}):
            with self.subTest(extra=extra):
                package = self.lock(**extra)
                self.assertEqual((package.failures, package.warnings), ([], []))

    def test_the_last_day_of_support_is_not_yet_past(self):
        self.assertEqual(self.lock(support_ends={"demo": self.TODAY.isoformat()}).warnings, [])
        self.assertEqual(len(self.lock(support_ends={"demo": self.days_ago(1)}).warnings), 1)

    def test_an_end_of_support_that_is_not_a_date_is_reported_not_ignored(self):
        for value in ("soon", "2026-13-40", "31/07/2026", 20260731):
            with self.subTest(value=value):
                package = self.lock(support_ends={"demo": value})
                self.assertEqual(package.failures, [])
                self.assertEqual([w for w in package.warnings if "is not a YYYY-MM-DD date" in w], package.warnings)

    def test_a_registry_not_verified_within_its_own_ttl_warns(self):
        package = self.lock(verified_at=self.days_ago(200), verification_ttl_days=180)
        self.assertEqual(package.failures, [])
        self.assertEqual(len(package.warnings), 1, package.warnings)
        self.assertIn("more than 180 days ago", package.warnings[0])

    def test_a_registry_verified_within_its_ttl_does_not_warn(self):
        for age in (0, 179, 180):
            with self.subTest(age=age):
                self.assertEqual(self.lock(verified_at=self.days_ago(age), verification_ttl_days=180).warnings, [])

    def test_a_registry_that_declares_no_ttl_is_not_held_to_one(self):
        self.assertEqual(self.lock(verified_at="2000-01-01").warnings, [])

    def test_a_ttl_the_gate_cannot_apply_is_reported(self):
        for extra in ({"verification_ttl_days": 180}, {"verification_ttl_days": 180, "verified_at": "yesterday"},
                      {"verification_ttl_days": 0, "verified_at": "2026-10-01"}, {"verification_ttl_days": True, "verified_at": "2026-10-01"},
                      {"verification_ttl_days": "180", "verified_at": "2026-10-01"}):
            with self.subTest(extra=extra):
                package = self.lock(**extra)
                self.assertEqual(package.failures, [])
                self.assertEqual(len(package.warnings), 1, package.warnings)
                self.assertIn("freshness was not checked", package.warnings[0])

    def test_the_shipped_registry_warns_for_the_stack_whose_support_has_ended(self):
        """vue-nuxt locks Nuxt 3, whose end of life passed on 2026-07-31; the other overlays carry no date."""
        shipped = engine.load_data(engine.REGISTRY_PATH)
        by_slug = {entry["slug"]: entry for entry in shipped["overlays"]}
        for slug, expect_warning in (("vue-nuxt", True), ("angular", False)):
            with self.subTest(slug=slug):
                self.spec.pop("_registry_path", None)
                entry = by_slug[slug]
                package = self.checked({"slug": slug, "versions": list(entry["versions"][:1]), "overlay_sha256": entry["sha256"]})
                self.assertEqual(package.failures, [])
                self.assertEqual(any("ended on 2026-07-31" in warning for warning in package.warnings), expect_warning)


class ConsumerHandoffBindingTests(EngineCase):
    """gates.yaml calls the handoff digest "the immutable effective-profile sha256"; compare them."""

    PROFILE = "a" * 64
    HANDOFF = {"consuming_pipeline": "design", "applicability_summary": "UI choices"}

    def failures(self, handed: object, evidence: dict | None) -> list[str]:
        package = self.package("taste-review", evidence)
        package.check_taste_record("consumer_handoff", "consumer_handoff",
                                   {**self.HANDOFF, "effective_profile_digest": handed})
        return package.failures

    def profile(self, digest: object = PROFILE) -> dict:
        return {"effective_profile": {"entries": [], "digest": digest}}

    def test_the_handoff_must_carry_the_effective_profile_digest(self):
        self.assertEqual(self.failures("b" * 64, self.profile()),
                         ["consumer_handoff effective_profile_digest does not match the effective_profile digest"])

    def test_an_equal_digest_passes_whatever_its_hex_case(self):
        for handed in (self.PROFILE, self.PROFILE.upper()):
            self.assertEqual(self.failures(handed, self.profile()), [])
        self.assertEqual(self.failures(self.PROFILE, self.profile(self.PROFILE.upper())), [])

    def test_nothing_is_compared_when_either_side_is_not_a_digest(self):
        """Malformed values keep their own failure; the mismatch is reported only for two real digests."""
        self.assertEqual(self.failures("not-a-digest", self.profile()),
                         ["consumer_handoff record requires sha256 effective_profile_digest"])
        for evidence in (None, {}, self.profile("not-a-digest"), {"effective_profile": "text"}):
            self.assertEqual(self.failures(self.PROFILE, evidence), [], evidence)


class EvidenceKindTests(EngineCase):
    """A kind the engine cannot validate is an engine error: it must never switch a key's checks off."""

    def test_every_kind_the_shipped_spec_declares_is_one_the_engine_dispatches(self):
        self.assertLessEqual(set(self.spec["evidence_types"].values()), engine.EVIDENCE_KINDS)

    def test_no_kind_is_a_rule_nothing_applies(self):
        """QR-14: `audit` had a rule and a validator and no key mapped to it, which reads as coverage the gate never gives."""
        mapped = set(self.spec["evidence_types"].values())
        self.assertEqual(set(self.spec["evidence_type_rules"]), mapped)
        self.assertEqual(engine.EVIDENCE_KINDS, mapped)

    def test_every_known_kind_reaches_a_validator(self):
        for kind in sorted(engine.EVIDENCE_KINDS):
            with self.subTest(kind=kind):
                self.package("build-to-review").check_typed("tests", kind, "not a record")

    def test_a_kind_with_no_validator_is_an_engine_error_not_a_silent_pass(self):
        with self.assertRaisesRegex(engine.Engine, "evidence type 'scann' for tests has no validator"):
            self.package("build-to-review").check_typed("tests", "scann", {"artifacts": ["log.txt"]})

    def test_the_loader_refuses_a_spec_that_names_an_unknown_kind(self):
        spec = json.loads(GATE_SPEC.read_text(encoding="utf-8"))
        spec["evidence_types"]["tests"] = "scann"
        path = self.root / "gates.yaml"
        path.write_text(json.dumps(spec), encoding="utf-8")
        with self.assertRaisesRegex(engine.Engine, r"unknown kinds \['scann'\]"):
            engine.load_gate_spec(path)

    def test_the_command_line_exits_two_and_prints_no_result_for_such_a_spec(self):
        spec = json.loads(GATE_SPEC.read_text(encoding="utf-8"))
        spec["evidence_types"]["vulnerability_scan"] = "scann"
        gates = self.root / "gates.yaml"
        gates.write_text(json.dumps(spec), encoding="utf-8")
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({"schema_version": 2, "boundary": "security-review", "owner": "cso",
                                        "submission_id": "s1", "revision": "r1", "revisions": ["r1"],
                                        "artifact_hashes": {}, "evidence": {}}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(CHECK), "--boundary", "security-review", "--package", str(manifest),
                               "--gates", str(gates)], capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertIn("unknown kinds ['scann']", json.loads(proc.stderr)["engine_error"])


class BlockedPhraseTests(EngineCase):
    """One list, one case rule, and a rule the gate cannot apply stops the gate.

    check.py carried its own shorter list, matched the code-rot markers without
    regard to case, and the shared engine silently dropped a pattern that did not
    compile and a phrase file that did not exist.
    """

    LITERALS = ("trust me", "works on my machine", "100% complete", "no issues whatsoever", "lorem ipsum",
                "placeholder content", "as an ai language model", "i cannot actually")

    def setUp(self):
        super().setUp()
        # The wrappers refuse a package outside any project, so the scratch directory is one.
        (self.root / ".git").mkdir()

    def phrase_file(self, text: str | None) -> Path:
        path = self.root / "phrases.txt"
        if text is not None:
            path.write_text(text, encoding="utf-8")
        return path

    def run_wrapper(self, *extra: str) -> tuple[int, dict]:
        package = self.root / "pkg"
        package.mkdir(exist_ok=True)
        (package / "summary.md").write_text("# Report\n\nThe change adds a validated endpoint.\n", encoding="utf-8")
        manifest = gc.Manifest(boundary="test", sub_orchestrator="test", artifacts=())
        out = io.StringIO()
        with chdir(self.root), redirect_stdout(out):
            code = gc.main_with_manifest(manifest, [str(package), "--json", *extra])
        return code, json.loads(out.getvalue())

    def test_the_boundary_validator_reads_the_same_list_as_the_package_validator(self):
        literals, markers = gc.compile_blocked_phrases(gc.DEFAULT_BLOCKED_PHRASES)
        self.assertEqual(engine.BLOCKED_LITERALS, literals)
        self.assertEqual([m.pattern for m in engine.BLOCKED_MARKERS], [m.pattern for m in markers])
        self.assertEqual(tuple(literals), self.LITERALS)

    def test_every_default_phrase_blocks_in_prose_whatever_its_case(self):
        for phrase in self.LITERALS:
            for text in (phrase, phrase.upper(), f"The change is {phrase.title()}, honestly."):
                with self.subTest(text=text):
                    self.assertTrue(engine.has_blocked_phrase(text))

    def test_the_code_rot_markers_are_case_sensitive_words(self):
        for marker in ("TODO", "FIXME", "XXX", "HACK"):
            with self.subTest(marker=marker):
                self.assertTrue(engine.has_blocked_phrase(f"# {marker} wire this up"))
                self.assertFalse(engine.has_blocked_phrase(f"{marker}S and PRE{marker}"))
        for prose in ("todo", "hack", "fixme", "xxx", "Todo", "Hack", "a quick hack for the demo", "the todo list"):
            with self.subTest(prose=prose):
                self.assertFalse(engine.has_blocked_phrase(prose))

    def test_quoted_and_code_text_stays_exempt_for_every_shared_phrase(self):
        text = "The report quotes `works on my machine` and:\n\n> trust me\n\n```\nlorem ipsum\nTODO\n```\n"
        self.assertFalse(engine.has_blocked_phrase(engine.strip_code(text)))
        self.assertTrue(engine.has_blocked_phrase(engine.strip_code(text + "\nWorks on my machine.\n")))

    def test_a_pattern_that_does_not_compile_stops_the_gate(self):
        with self.assertRaisesRegex(ValueError, r"blocked-phrase entry 're:\(TODO' is not a valid regular expression"):
            gc.compile_blocked_phrases(["re:(TODO"])
        report = gc.Report(boundary="test", package_path=str(self.root))
        with self.assertRaises(ValueError):
            gc.scan_blocked_phrases(self.root, report, ["re:(TODO"])
        self.assertNotIn("BLOCKED_PHRASE_CLEAN", {f.code for f in report.findings})

    def test_a_missing_phrase_file_stops_the_gate(self):
        with self.assertRaisesRegex(ValueError, "blocked-phrases file not found"):
            gc.load_blocked_phrases(self.root / "typo.txt")
        with self.assertRaisesRegex(ValueError, "blocked-phrases file not found"):
            gc.load_blocked_phrases(self.root)

    def test_an_extra_file_extends_the_default_list(self):
        path = self.phrase_file("# reviewed wording\n\ninternal only\nre:\\bWIP\\b\n")
        self.assertEqual(gc.load_blocked_phrases(path), [*gc.DEFAULT_BLOCKED_PHRASES, "internal only", r"re:\bWIP\b"])
        self.assertEqual(gc.load_blocked_phrases(None), list(gc.DEFAULT_BLOCKED_PHRASES))

    def test_the_wrapper_exits_two_with_an_error_record_when_the_phrase_list_is_unusable(self):
        for text in (None, "re:(TODO\n"):
            with self.subTest(text=text):
                code, record = self.run_wrapper("--blocked-phrases", str(self.phrase_file(text)))
                self.assertEqual(code, 2)
                self.assertEqual(record["gate_status"], "ERROR")
                self.assertIn("blocked-phrase", record["error"])

    def test_a_valid_extra_phrase_is_still_applied_by_the_wrapper(self):
        package = self.root / "pkg"
        package.mkdir()
        (package / "summary.md").write_text("# Report\n\nThis is internal only.\n", encoding="utf-8")
        manifest = gc.Manifest(boundary="test", sub_orchestrator="test", artifacts=())
        out = io.StringIO()
        with chdir(self.root), redirect_stdout(out):
            code = gc.main_with_manifest(manifest, [str(package), "--json", "--blocked-phrases",
                                                    str(self.phrase_file("internal only\n"))])
        self.assertEqual(code, 1)
        self.assertIn("BLOCKED_PHRASE", {f["code"] for f in json.loads(out.getvalue())["findings"]})


class UnhashableValueTests(EngineCase):
    """A list or object where a word belongs is a finding, not a crash."""

    UNHASHABLE = (["Major"], {"level": "Major"}, [["Major"]], [{}])

    def test_unhashable_severity_and_status_are_findings(self):
        for bad in self.UNHASHABLE:
            with self.subTest(bad=bad):
                package = self.package("review-to-delivery")
                package.check_findings("findings", {"items": [{"id": "F", "severity": bad, "status": "open"}]})
                self.assertEqual(package.failures, [f"findings[0] severity must be one of {sorted(engine.FINDING_SEVERITIES)}"])
                package = self.package("review-to-delivery")
                package.check_findings("findings", {"items": [{"id": "F", "severity": "Major", "status": bad}]})
                self.assertEqual(package.failures, [f"findings[0] status must be one of {sorted(engine.FINDING_STATUSES)}"])

    def test_unhashable_recommendation_is_a_finding_in_both_forms(self):
        for bad in self.UNHASHABLE:
            for form in (bad, {"recommendation": bad}):
                with self.subTest(form=form):
                    package = self.package("review-to-delivery")
                    package.check_verdict("review_verdict", form)
                    self.assertEqual(package.failures,
                                     [f"review_verdict must carry a recommendation in {sorted(engine.VERDICTS)}"])

    def test_the_command_line_answers_with_a_json_revise_not_a_traceback(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({
            "schema_version": 2, "boundary": "review-to-delivery", "owner": "code-chief", "submission_id": "s1",
            "revision": "r1", "revisions": ["r1"], "artifact_hashes": {},
            "evidence": {"review_verdict": ["APPROVED"],
                         "findings": {"items": [{"id": "F", "severity": ["Major"], "status": {"x": 1}}]},
                         "residual_risk": "none", "revision_lineage": "r1"}}), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(CHECK), "--boundary", "review-to-delivery", "--package", str(manifest)],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        failures = json.loads(proc.stdout)["failures"]
        self.assertTrue(any(f.startswith("review_verdict must carry a recommendation") for f in failures), failures)
        self.assertTrue(any(f.startswith("findings[0] severity must be one of") for f in failures), failures)


class EngineFaultTests(EngineCase):
    """Any fault inside the engine is the documented exit 2, never exit 1 with a traceback."""

    def run_main(self, manifest: Path) -> tuple[int, str, str]:
        argv = ["check.py", "--boundary", "review-to-delivery", "--package", str(manifest)]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", argv), redirect_stdout(out), redirect_stderr(err):
            code = engine.main()
        return code, out.getvalue(), err.getvalue()

    def manifest(self) -> Path:
        path = self.root / "manifest.json"
        path.write_text(json.dumps({"schema_version": 2, "boundary": "review-to-delivery", "owner": "code-chief",
                                    "submission_id": "s1", "revision": "r1", "revisions": ["r1"],
                                    "artifact_hashes": {}, "evidence": {}}), encoding="utf-8")
        return path

    def test_an_unexpected_exception_is_an_engine_error(self):
        for fault in (TypeError("unhashable type: 'list'"), AttributeError("'NoneType' has no attribute 'get'"),
                      KeyError("boundary"), RecursionError("maximum recursion depth exceeded")):
            with self.subTest(fault=type(fault).__name__):
                with mock.patch.object(engine.Package, "check_evidence", side_effect=fault):
                    code, out, err = self.run_main(self.manifest())
                self.assertEqual(code, 2)
                self.assertEqual(out, "", "an engine error must not print a result that reads like a verdict")
                error = json.loads(err)
                self.assertEqual(error["boundary"], "review-to-delivery")
                self.assertTrue(error["engine_error"].startswith(f"internal error: {type(fault).__name__}"), error)

    def test_a_bad_input_keeps_its_plain_message(self):
        code, out, err = self.run_main(self.root / "no-such-manifest.json")
        self.assertEqual(code, 2)
        self.assertNotIn("internal error", json.loads(err)["engine_error"])


class DigestFormatTests(EngineCase):
    """A sha256 is exactly 64 hex digits: `$` let a trailing newline through."""

    GOOD = "a" * 64

    def test_only_a_bare_64_digit_hex_string_is_a_digest(self):
        self.assertTrue(engine.is_sha256(self.GOOD))
        self.assertTrue(engine.is_sha256(self.GOOD.upper()), "hex case is folded, as before")
        for bad in (self.GOOD + "\n", "\n" + self.GOOD, self.GOOD + " ", self.GOOD[:-1], self.GOOD + "a",
                    "g" * 64, "", None, 5, [self.GOOD], {"sha256": self.GOOD}):
            with self.subTest(bad=bad):
                self.assertFalse(engine.is_sha256(bad))

    def test_an_artifact_digest_with_a_trailing_newline_is_invalid(self):
        (self.root / "evidence.md").write_text("# Evidence\n", encoding="utf-8")
        package = self.package("review-to-delivery", artifact_hashes={
            "evidence.md": content_sha256(self.root / "evidence.md") + "\n"})
        package.check_artifacts()
        self.assertEqual(package.failures, ["invalid artifact digest: evidence.md"])

    def test_a_taste_digest_with_a_trailing_newline_is_refused(self):
        record = {"added": [], "updated": [], "deprecated": [], "revoked": [], "unchanged": ["p1"],
                  "before_digest": self.GOOD, "after_digest": self.GOOD}
        package = self.package("taste-review")
        package.check_taste_record("preference_diff", "preference_diff", record)
        self.assertEqual(package.failures, [])
        package.check_taste_record("preference_diff", "preference_diff", {**record, "after_digest": self.GOOD + "\n"})
        self.assertEqual(package.failures, ["preference_diff record requires sha256 after_digest"])

    def test_a_persistence_hash_with_a_trailing_newline_is_refused(self):
        record = {"requested_destinations": ["preferences/taste.md"], "committed_revisions": [1],
                  "hashes": {"taste.md": self.GOOD + "\n"}, "atomicity_status": "committed", "rollback_result": "none"}
        package = self.package("taste-review")
        package.check_taste_record("persistence_result", "persistence_result", record)
        self.assertEqual(package.failures, ["persistence_result record requires a non-empty hashes map of sha256 values"])


class PathReferenceTests(EngineCase):
    """A path reference is a declared path field or an artifact-backed value, not any string that has a dot."""

    def evidence_failures(self, evidence: dict, boundary: str = "review-to-delivery") -> list[str]:
        proof = self.root / "proof.md"
        proof.write_text("# Proof\n\nObserved.\n", encoding="utf-8")
        package = self.package(boundary, evidence, artifact_hashes={"proof.md": content_sha256(proof)})
        package.check_artifacts()
        package.check_evidence()
        return [f for f in package.failures if "path" in f or "artifact" in f]

    def test_a_version_or_a_hostname_on_a_prose_key_is_not_a_file(self):
        for prose in ("1.4.2", "v1.2.0", "api.example.com", "10.0.0.1"):
            with self.subTest(prose=prose):
                failures = self.evidence_failures({
                    "executed_probes": {"artifacts": ["proof.md"], "result": {"status": "pass"}},
                    "residual_risk": prose, "revision_lineage": [prose, "r1"]})
                self.assertEqual([f for f in failures if "unhashed" in f], [])

    def test_a_revision_ref_may_be_a_version_number(self):
        package = self.package("build-to-review", {"approved_design_revision": "1.4.2"}, artifact_hashes={})
        package.check_artifacts()
        package.check_evidence()
        self.assertFalse(any("approved_design_revision" in f and "path" in f for f in package.failures), package.failures)

    def test_a_declared_path_field_still_needs_a_hashed_artifact_whatever_it_looks_like(self):
        for ref in ("missing.md", "1.4.2", "api.example.com"):
            with self.subTest(ref=ref):
                failures = self.evidence_failures({
                    "executed_probes": {"artifacts": ["proof.md", ref], "result": {"status": "pass"}}})
                self.assertIn(f"evidence references unhashed path: executed_probes -> {ref}", failures)

    def test_a_bare_value_on_an_artifact_backed_key_is_still_a_file_reference(self):
        failures = self.evidence_failures({"decisions": "1.4.2"}, "design-to-build")
        self.assertIn("evidence references unhashed path: decisions -> 1.4.2", failures)

    def test_an_absolute_drive_or_unc_reference_is_refused_not_read_as_prose(self):
        for ref in ("/var/log/tests.log", "C:/logs/tests.log", "C:\\logs\\tests.log", "//server/share/tests.log",
                    "\\\\server\\share\\tests.log", "/tests.log"):
            with self.subTest(ref=ref):
                failures = self.evidence_failures({
                    "executed_probes": {"artifacts": ["proof.md", ref], "result": {"status": "pass"}}})
                self.assertIn(f"evidence references unhashed path: executed_probes -> {ref}", failures)

    def test_shapes_that_are_not_files_stay_prose(self):
        for text in ("https://example.com/a.md", "10:15.30", "desktop, mobile, both themes", "see proof.md", "r1 <- design r1",
                     "", "no extension", "C:", "trailing."):
            with self.subTest(text=text):
                self.assertFalse(engine.is_path_like(text))


if __name__ == "__main__":
    unittest.main()
