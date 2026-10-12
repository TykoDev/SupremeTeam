#!/usr/bin/env python3
"""The source of truth is read, not trusted (gates.yaml decision_log, acceptance_table,
interface_set, change_set, trace_map, revision_ref).

Each case starts from a build-to-review or design-to-build package that passes and
breaks one property the new records hold: an intake log missing a section or an
owner, an acceptance table without ids, an interface id no artifact names, a changed
file that drifted or that the diff does not name, an approved criterion nobody
traced, a change nobody traced, a test the log never ran, and an upstream approval
that is missing, not APPROVED, for another revision, or whose package changed after
it was approved.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_gate_engine import GATE_SPEC, engine
import _fixtures
from data_formats import content_sha256

SOURCE = _fixtures.source_of_truth("src/app.py")


class SourceCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.spec = engine.load_gate_spec(GATE_SPEC)

    def write(self, rel: str, text: str) -> str:
        return _fixtures.write(self.root, rel, text)

    def check(self, boundary: str, evidence: dict, hashes: dict) -> list[str]:
        data = {"schema_version": 2, "boundary": boundary, "owner": self.spec["boundaries"][boundary]["submitter"],
                "submission_id": "s1", "revision": "r1", "revisions": ["r1"], "run_id": "run-x",
                "evidence": evidence, "artifact_hashes": hashes}
        package = engine.Package(self.root / "manifest.json", data, boundary, self.spec)
        package.check_artifacts()
        package.check_evidence()
        return package.failures


class DesignSourceTests(SourceCase):
    def design(self, grilling: str = SOURCE, plan: str = SOURCE, interfaces: dict | None = None) -> list[str]:
        hashes = {"intake/log.md": self.write("intake/log.md", grilling),
                  "design/plan.md": self.write("design/plan.md", plan),
                  "design/arch.md": self.write("design/arch.md", "# Architecture\n\nIF-1 is GET /items.\n")}
        waive = lambda key: {"applicable": False, "reason": self.spec["fallback_values"][key][0],  # noqa: E731
                             "scope": "run", "decided_by": "commander"}
        evidence = {"decisions": "intake/log.md", "architecture": "design/arch.md", "plan": "design/plan.md",
                    "acceptance": "design/plan.md",
                    "interfaces": interfaces or {"artifacts": ["design/arch.md"], "change": "changed",
                                                 "items": [{"id": "IF-1", "kind": "endpoint", "name": "GET /items"}]},
                    "security_seed": {"applicable": False, "scope": "run", "decided_by": "security-builder",
                                      "architecture_revision": "r1", "reason": "none", "boundaries": []},
                    "stack_lock": waive("stack_lock"), "taste_snapshot": waive("taste_snapshot"),
                    "ui_evidence": waive("ui_evidence")}
        return self.check("design-to-build", evidence, hashes)

    def assertFails(self, failures: list[str], fragment: str) -> None:
        self.assertTrue(any(fragment in f for f in failures), failures)

    def test_the_fixture_passes(self):
        self.assertEqual(self.design(), [])

    def test_each_intake_section_is_required(self):
        for title in ("Resolved decisions", "Deferred decisions", "Rejected options", "Non-goals and YAGNI deferrals"):
            with self.subTest(title=title):
                self.assertFails(self.design(grilling=SOURCE.replace(f"## {title}", "## Something else")),
                                 f"lacks the section '{title}'")

    def test_intake_rows_are_complete_and_identified(self):
        self.assertFails(self.design(grilling=SOURCE.replace("| API lead | build |", "| - | build |")), "leaves ['Owner'] empty")
        self.assertFails(self.design(grilling=SOURCE.replace("| D-3 |", "| D-1 |")), "id D-1 repeats")
        self.assertFails(self.design(grilling=SOURCE.replace("| D-3 |", "| 3 |")), "is not D-<n>")
        self.assertFails(self.design(grilling=SOURCE.replace("| REST | user |", "| REST | gut feeling |")), "source 'gut feeling'")
        self.assertFails(self.design(grilling=SOURCE.replace("| Chosen | Source |", "| Choice | Source |")), "lacks the columns ['Chosen']")
        no_resolved = SOURCE.replace("| D-1 | API style | REST | user |\n", "")
        self.assertFails(self.design(grilling=no_resolved), "'Resolved decisions' needs at least 1 row")

    def test_a_table_quoted_in_a_fence_is_not_the_log(self):
        fenced = "# Log\n\n```\n" + SOURCE + "```\n"
        self.assertFails(self.design(grilling=fenced), "lacks the section 'Resolved decisions'")

    def test_the_acceptance_table_is_read(self):
        self.assertFails(self.design(plan=SOURCE.replace("## Acceptance criteria", "## Criteria")),
                         "no artifact with a 'Acceptance criteria' section")
        self.assertFails(self.design(plan=SOURCE.replace("| AC-1 |", "| 1 |")), "is not AC-<n>")
        self.assertFails(self.design(plan=SOURCE.replace("| API lead |\n\n## Interfaces", "| - |\n\n## Interfaces")),
                         "leaves ['Acceptor'] empty")

    def test_interfaces_name_ids_their_artifacts_hold(self):
        self.assertFails(self.design(interfaces={"artifacts": ["design/arch.md"], "change": "changed",
                                                 "items": [{"id": "IF-2", "kind": "endpoint", "name": "GET /x"}]}),
                         "IF-2 appears in none of its artifacts")
        self.assertFails(self.design(interfaces={"artifacts": ["design/arch.md"], "change": "changed", "items": []}),
                         "requires at least one item")
        self.assertFails(self.design(interfaces={"artifacts": ["design/arch.md"], "change": "maybe", "items": []}),
                         "change must be")
        self.assertEqual(self.design(interfaces={"artifacts": ["design/arch.md"], "change": "none", "items": []}), [])


class BuildSourceTests(SourceCase):
    def build(self, mutate=None, upstream_mutate=None) -> list[str]:
        plan = self.root / "design" / "plan.md"
        self.write("design/plan.md", SOURCE)
        verdict, verdict_digest = _fixtures.approved_upstream(
            self.root, self.root / "design", "design-to-build", "r1", "run-x",
            {"plan.md": plan}, evidence={"acceptance": "plan.md"})
        source_digest = self.write("src/app.py", "print('items')\n")
        hashes = {verdict: verdict_digest, "build/log.md": self.write("build/log.md", SOURCE)}
        record = _fixtures.records("build/log.md", "src/app.py", source_digest)
        evidence = {"approved_design_revision": {"revision": "r1", "verdict": verdict},
                    "implementation": record["change_set"], "traceability": record["trace_map"],
                    "tests": {"artifacts": ["build/log.md"], "result": {"status": "pass"}},
                    "runtime": {"artifacts": ["build/log.md"], "result": {"status": "pass"}},
                    "security_evidence": {"items": []}}
        if upstream_mutate:
            upstream_mutate(self.root)
            hashes[verdict] = content_sha256(self.root / verdict)
        if mutate:
            mutate(evidence, hashes)
        return self.check("build-to-review", evidence, hashes)

    def assertFails(self, failures: list[str], fragment: str) -> None:
        self.assertTrue(any(fragment in f for f in failures), failures)

    def test_the_fixture_passes(self):
        self.assertEqual(self.build(), [])

    def edit_verdict(self, **fields):
        def apply(root: Path) -> None:
            path = root / "design" / "verdict_design-to-build.cross-stage.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            for name, value in fields.items():
                if name == "judgment":
                    record["judgment"].update(value)
                else:
                    record[name] = value
            path.write_text(json.dumps(record), encoding="utf-8")
        return apply

    def test_the_approval_must_be_a_valid_cross_stage_approved(self):
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(judgment={"verdict": "REVISE"})),
                         "is not a valid APPROVED judgment by gatekeeper-admiral")
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(judgment={"gate": "gatekeeper-design"})),
                         "is not a valid APPROVED judgment by gatekeeper-admiral")
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(judgment={"valid": False})),
                         "is not a valid APPROVED judgment")
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(boundary="review-to-delivery")), "not 'design-to-build'")
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(revision="r0")), "is not the approved revision")
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(run_id="run-y")), "belongs to run")
        self.assertFails(self.build(upstream_mutate=self.edit_verdict(**{"pass": False})), "records mechanical failures")

    def test_a_bare_revision_or_unhashed_verdict_is_not_an_approval(self):
        self.assertFails(self.build(lambda e, h: e.__setitem__("approved_design_revision", "r1")),
                         "must be a {revision, verdict} record")
        self.assertFails(self.build(lambda e, h: h.pop(e["approved_design_revision"]["verdict"])),
                         "is not a correctly hashed artifact")

    def test_an_upstream_package_changed_after_approval_fails(self):
        def edit_plan(root: Path) -> None:
            (root / "design" / "plan.md").write_text(SOURCE + "\nA late requirement.\n", encoding="utf-8")

        def edit_manifest(root: Path) -> None:
            path = root / "design" / "manifest.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["evidence"]["note"] = "added after approval"
            path.write_text(json.dumps(data), encoding="utf-8")
        self.assertFails(self.build(upstream_mutate=edit_plan), "approved artifact changed after approval: plan.md")
        self.assertFails(self.build(upstream_mutate=edit_manifest), "approved manifest changed after approval")

    def test_the_change_set_is_re_hashed_and_named_by_the_diff(self):
        def drift(e, h):
            (self.root / "src" / "app.py").write_text("print('changed later')\n", encoding="utf-8")
        self.assertFails(self.build(drift), "src/app.py hash drift")

        def unnamed(e, h):
            e["implementation"]["changed_files"].append({"path": "src/other.py", "sha256": "0" * 64})
        self.assertFails(self.build(unnamed), "src/other.py does not appear in the diff artifact")

        def deleted_but_present(e, h):
            e["implementation"]["changed_files"][0]["status"] = "deleted"
        self.assertFails(self.build(deleted_but_present), "is marked deleted but exists")

    def test_traceability_covers_every_approved_criterion_and_every_change(self):
        self.assertFails(self.build(lambda e, h: e["traceability"].__setitem__("items", [])),
                         "leaves approved acceptance AC-1 untraced")
        self.assertFails(self.build(lambda e, h: e["traceability"]["items"][0].__setitem__("acceptance", "AC-9")),
                         "AC-9' is not an approved acceptance id")
        self.assertFails(self.build(lambda e, h: e["traceability"]["items"][0].__setitem__("tests", ["test_never_ran"])),
                         "test 'test_never_ran' does not appear in the tests log")
        self.assertFails(self.build(lambda e, h: e["traceability"]["items"][0].__setitem__("changes", ["src/ghost.py"])),
                         "change src/ghost.py is not in the implementation change set")

        def extra_change(e, h):
            self.write("src/extra.py", "x = 1\n")
            self.write("build/log.md", SOURCE + "\n    --- a/src/extra.py\n")
            h["build/log.md"] = content_sha256(self.root / "build/log.md")
            e["implementation"]["changed_files"].append(
                {"path": "src/extra.py", "sha256": content_sha256(self.root / "src/extra.py")})
        self.assertFails(self.build(extra_change), "leaves changed file src/extra.py untraced")

        def supported(e, h):
            extra_change(e, h)
            e["traceability"]["supporting"] = [{"path": "src/extra.py", "reason": "shared helper"}]
        self.assertEqual(self.build(supported), [])


class TemplateDriftTests(unittest.TestCase):
    """The templates the producers copy are the shapes the engine parses."""

    def test_the_doctrine_template_is_a_passing_intake_log(self):
        text = (engine.SKILLS_ROOT / "grill-me-doctrine.md").read_text(encoding="utf-8")
        template = text.split("```markdown\n", 1)[1].split("```", 1)[0]
        self.assertEqual(engine.decision_log_defects(template, "grill-me template"), [])
        for title, columns, _ in engine.DECISION_SECTIONS:
            self.assertIn(f"## {title}", template)
            self.assertIn("| " + " | ".join(columns) + " |", template)

    def test_the_planner_table_header_is_the_one_the_engine_reads(self):
        text = (engine.SKILLS_ROOT / "design" / "planner" / "references" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("| " + " | ".join(engine.ACCEPTANCE_SECTION[1]) + " |", text)
        example = (engine.SKILLS_ROOT / "design" / "planner" / "references" / "examples.md").read_text(encoding="utf-8")
        # The example plan is quoted in a fence; unwrap it to read it as the plan it shows.
        unwrapped = "\n".join(line for line in example.splitlines() if not line.startswith("```"))
        rows, defects = engine.table_records(unwrapped, *engine.ACCEPTANCE_SECTION, "planner example")
        self.assertEqual(defects, [])
        self.assertEqual([row["ID"] for row in rows], ["AC-1", "AC-2", "AC-3", "AC-4"])


if __name__ == "__main__":
    unittest.main()
