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
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

SKILLS = Path(__file__).resolve().parents[2]
CHECK = SKILLS / "harness" / "gatekeeper" / "check.py"
GATE_SPEC = SKILLS / "gates.yaml"
sys.path.insert(0, str(SKILLS / "scripts"))
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
        "probe": {}, "audit": {},
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
        for kind in ("probe", "audit"):
            for fields in ({"exit_code": 0}, {}, {"exit_code": None}):
                with self.subTest(kind=kind, fields=fields):
                    package = self.check(kind, self.record(kind, **fields))
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
        for kind in ("probe", "audit"):
            with self.subTest(kind=kind):
                package = self.check(kind, self.record(kind))
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
