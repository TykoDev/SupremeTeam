"""Regression tests for the remediation findings in prior-findings.md (r2).

Each class pins one repaired finding class so a future edit that reintroduces
the contradictory clause, the invalid status enum, or the count/cap drift fails
here. The engine constants and manifests are read as the authority; nothing in
this module restates a value that a shipped file already owns.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[2]

WORD_NUMBERS = {
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "thirty-two": 32, "thirty-three": 33, "thirty-four": 34,
    "thirty-seven": 37, "thirty-eight": 38, "thirty-nine": 39,
}


def read(relative: str) -> str:
    return (CATALOG / relative).read_text(encoding="utf-8")


class AuthorizationControlTests(unittest.TestCase):
    """M-1 / M-2: approval-control instructions must not authorise a bypass."""

    def test_ship_has_no_generic_affirmation_bypass(self):
        text = read("skills/ship/SKILL.md")
        self.assertNotIn(
            "bypass the wait state", text,
            "ship/SKILL.md must not treat a general affirmative prompt as the "
            "human go decision the deploy-readiness gate requires",
        )
        # The concrete requirement stays: approver, reference, revision, timestamp.
        self.assertIn("human_go_required", text)
        self.assertIn("exact revision", text)
        self.assertIn("approver", text)

    def test_ship_still_names_the_no_go_decision_failure(self):
        text = read("skills/ship/SKILL.md")
        self.assertIn("No owner go-decision is present", text)

    def test_setup_deploy_has_no_automatic_drift_repair(self):
        for relative in (
            "skills/setup-deploy/SKILL.md",
            "skills/setup-deploy/references/workflow.md",
        ):
            self.assertNotIn(
                "Automatically apply", read(relative),
                f"{relative} must not apply drift repairs without the "
                "owner-approved diff",
            )

    def test_setup_deploy_requires_a_named_owner_and_an_approved_diff(self):
        text = read("skills/setup-deploy/SKILL.md")
        self.assertIn("named owner", text)
        self.assertIn("approval", text)


class LensStatusEnumTests(unittest.TestCase):
    """M-3: lens packet status enums must be accepted by the gate engine."""

    LENSES = (
        "skills/review/design-qa/SKILL.md",
        "skills/review/mr-robot/SKILL.md",
        "skills/review/security-review/SKILL.md",
    )

    @staticmethod
    def engine_statuses() -> set[str]:
        engine = read("skills/harness/gatekeeper/check.py")
        match = re.search(r"FINDING_STATUSES\s*=\s*\{([^}]*)\}", engine)
        assert match, "FINDING_STATUSES not found in check.py"
        return {part.strip().strip("\"'") for part in match.group(1).split(",")}

    def test_engine_enum_is_the_six_documented_statuses(self):
        self.assertEqual(
            self.engine_statuses(),
            {"open", "in-progress", "resolved", "verified", "deferred", "not-applicable"},
        )

    def test_every_lens_packet_status_is_accepted_by_the_engine(self):
        statuses = self.engine_statuses()
        for relative in self.LENSES:
            match = re.search(r"<status: ([^>]*)>", read(relative))
            self.assertIsNotNone(match, f"{relative} carries no status template")
            declared = {part.strip() for part in match.group(1).split("|")}
            self.assertLessEqual(
                declared, statuses,
                f"{relative} teaches a status the gate rejects: "
                f"{sorted(declared - statuses)}",
            )


class DocCountAndCapTests(unittest.TestCase):
    """m-1 / m-2 / m-3: prose counts must equal the machine manifests."""

    def number_before(self, text: str, pattern: str) -> int:
        match = re.search(pattern, text, re.S)
        self.assertIsNotNone(match, pattern)
        return WORD_NUMBERS[match.group(1).lower()]

    def test_save_protocol_class_count_matches_save_ownership(self):
        declared = len(re.findall(r"^  - id:", read("skills/save-ownership.yaml"), re.M))
        stated = self.number_before(
            read("skills/save-protocol.md"), r"([A-Za-z-]+)\s+are declared;\s*the run-facing"
        )
        self.assertEqual(stated, declared)

    def test_gatekeeper_readme_artifact_backing_matches_gates(self):
        gates = json.loads(read("skills/gates.yaml"))
        keys = set()
        for boundary in gates["boundaries"].values():
            keys.update(boundary.get("artifact_evidence", []))
        readme = read("skills/harness/gatekeeper/README.md")
        stated = self.number_before(
            readme, r"([A-Za-z-]+) evidence keys are artifact-backed"
        )
        self.assertEqual(stated, len(keys))
        listing = readme[readme.index("artifact-backed"):]
        stop = re.search(r"Fifteen\s+keys accept", listing)
        self.assertIsNotNone(stop, "README waiver paragraph not found")
        listing = listing[: stop.start()]
        missing = sorted(key for key in keys if f"`{key}`" not in listing)
        self.assertEqual(missing, [], f"README omits artifact-backed keys: {missing}")

    def test_workflow_protocol_cap_statement_matches_the_spec_and_the_validator(self):
        gates = json.loads(read("skills/gates.yaml"))
        cap = gates["revise_policy"]["cycle_cap"]
        self.assertIn(
            f'policy.get("cycle_cap") != {cap}',
            read("skills/scripts/validate_manifests.py"),
        )
        protocol = read("skills/contracts/workflow-protocol.md")
        self.assertNotIn("validated as 2", protocol)
        self.assertIn(f"validated as {cap}", protocol)
        # Jules counts REVISE *rounds* against gates cycle_cap: 3.
        self.assertIn("The third REVISE round reaches", protocol)
        self.assertIn("counted per submitted revision", protocol)
        self.assertNotIn("second REVISE round reaches", protocol)
        self.assertNotIn("first submission plus at most", protocol)


class CycleCapPhrasingTests(unittest.TestCase):
    """m-4 (revised): Jules counts REVISE *rounds*; the declared cap is 3."""

    THIRD_CYCLE_KEEPERS = (
        "skills/build/bob-the-builder/SKILL.md",
        "skills/build/cross-check-build-confirm/SKILL.md",
        "skills/build/debugger/SKILL.md",
        "skills/build/health-check/SKILL.md",
        "skills/build/test-builder/SKILL.md",
        "skills/investigate/SKILL.md",
        "skills/review/cso/SKILL.md",
    )

    def test_third_cycle_language_survives_for_the_declared_cap(self):
        gates = json.loads(read("skills/gates.yaml"))
        cap = gates["revise_policy"]["cycle_cap"]
        self.assertEqual(cap, 3, "this suite pins Jules' declared cap of 3 rounds")
        for relative in self.THIRD_CYCLE_KEEPERS:
            self.assertIn("a third cycle escalates", read(relative),
                          f"{relative} must keep third-cycle escalation while the cap is {cap}")

    def test_no_leftover_second_round_escalation_against_cap_3(self):
        """Only the exact obsolete two-round escalation clauses are banned; documenting
        a legitimate second round stays allowed under the three-round policy."""
        exact_wrong = (
            "second REVISE round reaches",
            "second failed round escalates",
            "escalate on the second failed round",
            "stop after two failed revision attempts",
            "returns `REVISE` twice, exhausting",
            "returns `REVISE` twice on the same package",
            "A second `REVISE` ends the cycle",
            "A second `REVISE` on the same package ends",
            "`REVISE` a second time, exhausting",
            "second `REVISE` escalates",
            "second `REVISE` would have ended",
            "second cycle also returns `REVISE`",
            "Second REVISE on the same keys",
            "second `REVISE` **ends the cycle**",
        )
        two_round_both = re.compile(
            r"(?:second|twice|two failed)[^.\n]{0,60}"
            r"(?:both verdicts|both revise packets|both verdict records|both packets)")
        offenders = []
        root = CATALOG / "skills"
        for path in list(root.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), 1):
                if any(phrase in line for phrase in exact_wrong) or two_round_both.search(line):
                    offenders.append(f"{path.relative_to(CATALOG)}:{lineno}: {line.strip()[:90]}")
        self.assertEqual(offenders, [],
                         "obsolete two-round escalation clauses must state the third-round policy:\n  "
                         + "\n  ".join(offenders))

    def test_no_stale_both_phrasing_against_three_rounds(self):
        """Old two-round escalation rows that carried 'both verdicts/packets'."""
        obsolete = (
            "with both revise packets, both verdicts",
            "carrying both packets, both verdict records",
            "Escalate to Admiral with both revise packets, both verdict records",
            "with both revise packets, both verdict records",
        )
        offenders = []
        for path in Path(CATALOG / "skills").rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), 1):
                if any(phrase in line for phrase in obsolete):
                    offenders.append(f"{path.relative_to(CATALOG)}:{lineno}")
        self.assertEqual(offenders, [],
                         "escalation rows must carry all three packets and the corresponding verdict records")

    def test_cap_numbers_in_prose_match_the_spec(self):
        gates = json.loads(read("skills/gates.yaml"))
        cap = gates["revise_policy"]["cycle_cap"]
        root = CATALOG / "skills"
        bad = []
        for path in list(root.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"cycle_cap`(?:\s+is|\s+of|:)\s*(\d+)", text):
                if int(match.group(1)) != cap:
                    bad.append(f"{path.relative_to(CATALOG)}")
            for match in re.finditer(r"cycle_cap\s+of\s+(\d+)", text):
                if int(match.group(1)) != cap:
                    bad.append(f"{path.relative_to(CATALOG)}")
        self.assertEqual(sorted(set(bad)), [])


class RepairedWordingTests(unittest.TestCase):
    """m-6 / m-7 / m-8 / m-11 and i-1: wording defects stay repaired."""

    ABSENT = (
        ("skills/freeze/SKILL.md", "you like"),
        ("skills/freeze/SKILL.md", "what you will"),
        ("skills/guard/SKILL.md", "what you need"),
        ("skills/guard/SKILL.md", "what you expect"),
        ("skills/gatekeeper-admiral/SKILL.md", "leaves to you"),
        ("skills/design/gatekeeper-design/SKILL.md", "for you to act on"),
        ("skills/skill-maker/skill-creator/SKILL.md", "you started in"),
        ("skills/skill-maker/SKILL.md", "examples/ as needed"),
        ("skills/build/gatekeeper-build/SKILL.md",
         "is not waived at schema 2. - **The build is bound"),
    )

    def test_repaired_phrases_are_absent(self):
        for relative, phrase in self.ABSENT:
            self.assertNotIn(phrase, read(relative), f"{relative}: `{phrase}`")

    def test_prototyper_command_templates_have_no_nested_backticks(self):
        text = read("skills/design/prototyper/SKILL.md")
        self.assertNotIn("`relative`", text)
        self.assertEqual(text.count('<the resolver' + chr(39) + 's "relative" value>'), 2)


    def test_mcp_template_documents_protocol_version(self):
        text = read("skills/mcp-tools.md")
        self.assertIn("protocol_version", text)
        self.assertRegex(
            text, r"protocol_version[^\n]*\b(versions|schema)\b",
            "protocol_version must be defined where it is declared",
        )

    def test_repaired_descriptions_keep_the_pushy_cue(self):
        for relative in (
            "skills/skill-maker/skill-creator/SKILL.md",
            "skills/review/cso/SKILL.md",
            "skills/skill-maker/skill-reviewer/SKILL.md",
        ):
            text = read(relative)
            description = text.split("---")[1]
            self.assertIn(
                "even when", description,
                f"{relative} description lost its pushy cue",
            )
            self.assertLessEqual(len(description), 1024 + 64, relative)


class NamedLeftoverLocationsTests(unittest.TestCase):
    """The coordinator's named cap-leftover locations, pinned one by one."""

    def check(self, relative, absent=(), present=()):
        text = read(relative)
        for phrase in absent:
            self.assertNotIn(phrase, text, f"{relative}: stale `{phrase}`")
        for phrase in present:
            self.assertIn(phrase, text, f"{relative}: missing `{phrase}`")

    def test_investigate_failure_row(self):
        self.check("skills/investigate/SKILL.md",
                   absent=("a second time, exhausting", "both revise packets, both verdicts"),
                   present=("a third time, exhausting", "all three revise packets"))

    def test_qa_gate_package(self):
        self.check("skills/qa/SKILL.md",
                   absent=("rather than opening a third cycle",),
                   present=("rather than opening a fourth cycle",))
        self.check("skills/qa/references/gate-package.md",
                   absent=("A second `REVISE` on the same package ends", "Opening a third cycle"),
                   present=("A third `REVISE` on the same package ends", "Opening a fourth cycle"))

    def test_ship_skill_failure_row(self):
        self.check("skills/ship/SKILL.md",
                   absent=("`REVISE` a second time", "a second `REVISE` ends the cycle",
                           "starting a third"),
                   present=("`REVISE` a third time", "starting a fourth",
                            "all three packets"))

    def test_ship_gate_submission(self):
        self.check("skills/ship/references/gate-submission.md",
                   absent=("A second `REVISE` ends the cycle", "with\nboth packets"),
                   present=("A third `REVISE` ends the cycle", "all three packets"))

    def test_ship_examples_show_a_third_failed_verdict(self):
        self.check("skills/ship/references/examples.md",
                   absent=("so the second `REVISE`", "both packets attached",
                           "both verdict records"),
                   present=("Third verdict:", "so the third `REVISE` **ends the cycle**",
                            "all three packets and all corresponding verdict records"))

    def test_redesign_failure_row_has_no_third_submission_clause(self):
        self.check("skills/design/redesign/SKILL.md",
                   absent=("and a third submission spends", "both verdicts"),
                   present=("there is no fourth submission", "all corresponding verdict records"))

    def test_commander_and_redesign_examples_headings(self):
        for relative in ("skills/design/commander/references/examples.md",
                         "skills/design/redesign/references/examples.md"):
            self.check(relative,
                       absent=("Second REVISE on the same keys", "both revise packets, both verdict records"),
                       present=("Third REVISE on the same keys", "all corresponding verdict records"))

    def test_no_cap_row_still_carries_both_verdicts(self):
        """A phase+cross verdict pair may be 'both'; only two-round escalation rows may not."""
        pattern = re.compile(r"(?:second|twice|two failed)[^.\n]{0,60}both verdicts")
        for path in Path(CATALOG / "skills").rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    self.fail(f"{path.relative_to(CATALOG)}:{lineno}: {line.strip()[:100]}")


class RelatedSetupDeployPreviewTests(unittest.TestCase):
    """Newly identified related finding: no verbatim echo of unparseable config."""

    def test_no_verbatim_quote_escape_hatch(self):
        for relative in ("skills/setup-deploy/SKILL.md",
                         "skills/setup-deploy/references/workflow.md"):
            text = read(relative)
            self.assertNotIn("quoted verbatim", text, relative)
            self.assertNotIn("verbatim so the owner sees", text, relative)
            self.assertIn("never echoed verbatim", text, relative)

    def test_replacement_preview_carries_path_hash_and_parse_error(self):
        text = read("skills/setup-deploy/SKILL.md")
        self.assertIn("path, its sha256, and the parser error", text)
        self.assertIn("redaction pass", text)
        self.assertIn("stays unchanged until that named owner approves", text)


class SkillMakerInventoryTests(unittest.TestCase):
    """Coordinator correction: inventory requirement, not blanket packaging rules."""

    def test_expected_return_names_an_inventory(self):
        text = read("skills/skill-maker/SKILL.md")
        self.assertIn("supporting-file inventory", text)
        for field in ("path,", "purpose,", "consumer or reference", "packaging location"):
            self.assertIn(field, text)
        self.assertNotIn("sits one level deep", text)
        self.assertNotIn("ships non-empty", text)


class DescriptionBudgetTests(unittest.TestCase):
    """Catalogue budget 600 per shipped FrontmatterBudgetTests (loader ceiling 1024)."""

    def description(self, relative):
        text = read(relative)
        front = text[3:text.index("\n---", 3)]
        match = re.search(r"description:\s*>-\n((?:\s{2}.*\n?)+)", front)
        assert match, relative
        return " ".join(line.strip() for line in match.group(1).splitlines())

    def test_repaired_descriptions_fit_the_budget_and_keep_the_cue(self):
        for relative in ("skills/review/cso/SKILL.md",
                         "skills/skill-maker/skill-creator/SKILL.md",
                         "skills/skill-maker/skill-reviewer/SKILL.md"):
            desc = self.description(relative)
            self.assertLessEqual(len(desc), 600, f"{relative} is {len(desc)} chars")
            self.assertIn("even when", desc, relative)


if __name__ == "__main__":
    unittest.main()
