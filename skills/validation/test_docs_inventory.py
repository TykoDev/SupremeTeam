"""The inventories that documents state are checked against the tree, the specs and the code.

``validate_manifests.py`` compares the documents' totals (`53 skills`) with the roster, but the
sections a total is made of were never added up: a heading that states no count, or a count that
disagrees with its own table, left the total standing while the parts did not sum to it.

The gate prose is the second kind of drift: documents that say which typed record kinds exist, which keys
carry them, how many keys are artifact-backed or take a fallback, what a stack lock must satisfy and
what the validator leaves to the gatekeeper are compared with ``gates.yaml``, which the engine's own
tests tie to the code, and the finding statuses they list with the engine's ``FINDING_STATUSES``.

The tests that read the checkout's AGENTS.md, docs/, scripts/ or README skip in an installed
copy, which carries only ``skills/``.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _catalog import CHECKOUT_ONLY, HOOKS, IN_A_CHECKOUT, REPO, SKILLS, gatekeepers, load_spec, number_word, section

GATEKEEPER_SKILLS = gatekeepers()

HEADING = re.compile(r"^(#{2,6}) (.+?)\s*$", re.M)
FENCE = re.compile(r"^```.*?^```", re.M | re.S)
# A skill is named in bold in kebab case; the runtime tables bold file names, which carry dots and underscores.
SKILL_ROW = re.compile(r"^\| \*\*[a-z][a-z0-9-]*\*\* \|", re.M)
SKILL_PATH = re.compile(r"`(skills/[^`]+/SKILL\.md)`")
STATED_COUNT = (re.compile(r"\((\d+)(?:, [a-z ]+)?\)$"), re.compile(r"^The (\d+) skills$"))


def read(path: Path) -> str:
    return FENCE.sub("", path.read_text(encoding="utf-8"))


def stated_count(title: str) -> "int | None":
    for pattern in STATED_COUNT:
        match = pattern.search(title)
        if match:
            return int(match.group(1))
    return None


def sections(text: str) -> list:
    """(level, heading, body) for every heading; a body runs to the next heading of the same or a higher level."""
    marks = [(match.end(), len(match.group(1)), match.group(2), match.start()) for match in HEADING.finditer(text)]
    found = []
    for index, (body_start, level, title, _) in enumerate(marks):
        body_end = next((start for _, other, _, start in marks[index + 1:] if other <= level), len(text))
        found.append((level, title, text[body_start:body_end]))
    return found


def skill_sections(text: str) -> list:
    """(level, heading, stated count, skill rows) for every section whose body lists skills."""
    return [(level, title, stated_count(title), len(SKILL_ROW.findall(body)))
            for level, title, body in sections(text) if SKILL_ROW.search(body)]


def skills_on_disk() -> list:
    return sorted(path.relative_to(REPO).as_posix() for path in SKILLS.rglob("SKILL.md"))


def load_module(name: str, path: Path):
    """The module at ``path``, loaded by file the way the gate engine's own tests load ``check.py``."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gate_engine():
    return load_module("gate_check_engine", SKILLS / "harness" / "gatekeeper" / "check.py")


@CHECKOUT_ONLY
class SkillCountTests(unittest.TestCase):
    """AGENTS.md headings (level 3) and docs/skills.md headings (level 2) are the parts of the total."""

    DOCUMENTS = (("AGENTS.md", 3), ("docs/skills.md", 2))

    def test_every_section_states_the_count_of_the_skills_it_lists(self):
        for name, _ in self.DOCUMENTS:
            for _, title, stated, rows in skill_sections(read(REPO / name)):
                with self.subTest(document=name, section=title):
                    self.assertIsNotNone(stated, f"{name}: '{title}' lists {rows} skills and states no count")
                    self.assertEqual(stated, rows, f"{name}: '{title}' states {stated} but lists {rows}")

    def test_the_sections_add_up_to_the_skills_in_the_tree(self):
        on_disk = len(skills_on_disk())
        for name, level in self.DOCUMENTS:
            parts = [stated for lvl, _, stated, _ in skill_sections(read(REPO / name)) if lvl == level]
            with self.subTest(document=name):
                self.assertEqual(sum(count or 0 for count in parts), on_disk,
                                 f"{name}: its sections state {parts}, and the tree holds {on_disk} SKILL.md files")

    def test_agents_lists_every_skill_file_exactly_once(self):
        listed = SKILL_PATH.findall(read(REPO / "AGENTS.md"))
        self.assertEqual(sorted(listed), skills_on_disk())

    def test_the_skills_page_opens_with_the_number_of_skills_in_the_tree(self):
        """RR-ci-docs-1: nothing compared the page's opening total, so "54 of them." passed."""
        opening = re.search(r"^(\d+) of them\.", read(REPO / "docs" / "skills.md"), re.M)
        self.assertIsNotNone(opening, "docs/skills.md lost its opening 'N of them.' line")
        self.assertEqual(len(skills_on_disk()), int(opening.group(1)))

    def test_the_layout_sentence_sums_to_the_total_it_states(self):
        text = read(REPO / "AGENTS.md")
        sentence = re.search(r"\*\*(\d+) skills\*\*:(.*?)\.\s+Plus", text, re.S)
        self.assertIsNotNone(sentence, "AGENTS.md lost its '**N skills**: Group n, ... Plus' sentence")
        total, groups = int(sentence.group(1)), [int(n) for n in re.findall(r"\b(\d+)\b", sentence.group(2))]
        self.assertEqual(sum(groups), total, f"the groups state {groups}")
        self.assertEqual(total, len(skills_on_disk()))


class GateProseTests(unittest.TestCase):
    """What the documents say about typed records, the stack lock, artifact backing and finding statuses is what the
    spec and the engine say."""

    @classmethod
    def setUpClass(cls):
        cls.spec = load_spec("gates.yaml")
        cls.kinds = set(cls.spec["evidence_type_rules"])
        cls.keys_of = {}
        for key, kind in cls.spec["evidence_types"].items():
            cls.keys_of.setdefault(kind, set()).add(key)

    @staticmethod
    def names_in(text: str) -> set:
        return set(re.findall(r"`([a-z_]+)`", text))

    def test_handoff_templates_list_the_kinds_the_engine_validates(self):
        """RR-gate-1: the sentence still named `audit`, a kind the engine dropped and now refuses."""
        text = (SKILLS / "contracts" / "handoff-templates.md").read_text(encoding="utf-8")
        sentence = re.search(r"Typed records \((.*?)\) and the finding policy are defined in", text, re.S)
        self.assertIsNotNone(sentence, "handoff-templates.md lost its 'Typed records (...)' sentence")
        self.assertEqual(self.kinds, self.names_in(sentence.group(1)))

    def test_the_admirals_validator_summary_lists_the_kinds_the_engine_validates(self):
        text = (SKILLS / "gatekeeper-admiral" / "SKILL.md").read_text(encoding="utf-8")
        bullet = re.search(r"^- typed records are shaped correctly.* — (.*?)`references/boundary-evidence\.md`", text, re.M)
        self.assertIsNotNone(bullet, "gatekeeper-admiral/SKILL.md lost its typed-records bullet")
        self.assertEqual(self.kinds, self.names_in(bullet.group(1)))

    def test_no_contract_calls_an_unknown_word_a_record_kind(self):
        """A `X` or `Y` record names kinds or keys; a word that is neither is a kind someone removed."""
        vocabulary = self.kinds | set(self.spec["evidence_types"])
        pattern = re.compile(r"`([a-z_]+)` or `([a-z_]+)` records?\b")
        for path in sorted((SKILLS / "contracts").glob("*.md")) + [SKILLS / "gatekeeper-admiral" / "SKILL.md"]:
            for match in pattern.finditer(path.read_text(encoding="utf-8")):
                with self.subTest(document=path.name, phrase=match.group(0)):
                    self.assertLessEqual(set(match.groups()), vocabulary)

    def test_no_gate_document_names_the_removed_audit_kind(self):
        """RR-gate-1, RR-ci-docs-4: four lines still described `audit` as a kind the engine implements or accepts."""
        paths = sorted((SKILLS / "contracts").glob("*.md")) + [SKILLS / "gates.yaml", SKILLS / "harness" / "gatekeeper" / "README.md"]
        for name in GATEKEEPER_SKILLS:
            paths += sorted((SKILLS / name).rglob("*.md"))
        if IN_A_CHECKOUT:
            paths.append(REPO / "docs" / "gatekeepers.md")
        self.assertNotIn("audit", self.kinds)
        mentions = [path.relative_to(REPO).as_posix() for path in paths if "`audit`" in path.read_text(encoding="utf-8")]
        self.assertEqual([], mentions)

    def roster_rows(self, text: str, heading: str) -> dict:
        """kind -> the backticked names in its second cell, for the table in the ``## heading`` section."""
        body = section(text, heading)
        self.assertIsNotNone(body, f"no section '## {heading}'")
        rows = {}
        for row in re.finditer(r"^\|\s*`([a-z_]+)`\s*\|([^|]*)\|", body, re.M):
            if row.group(1) in self.kinds:
                rows[row.group(1)] = self.names_in(row.group(2))
        return rows

    def check_roster(self, rows: dict) -> None:
        for kind, keys in rows.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.keys_of[kind], keys)
        self.assertLessEqual({"probe", "render", "scan", "findings", "verdict", "stack_lock"}, set(rows))

    def test_the_admirals_typed_record_roster_matches_the_spec(self):
        """The roster left `mock_parity` out of the probe row and `mock_rendering` out of the render row."""
        text = (SKILLS / "gatekeeper-admiral" / "references" / "boundary-evidence.md").read_text(encoding="utf-8")
        self.check_roster(self.roster_rows(text, "2. Typed-record roster"))

    @CHECKOUT_ONLY
    def test_the_gates_page_typed_record_table_matches_the_spec(self):
        text = (REPO / "docs" / "gatekeepers.md").read_text(encoding="utf-8")
        self.check_roster(self.roster_rows(text, "Typed evidence records"))

    SUBMITTER_HEADER = re.compile(r"^\|\s*Boundary\s*\|\s*Guards\s*\|\s*Submitter\s*\|.*$", re.M)

    def submitters_in(self, text: str) -> dict:
        """boundary -> the Submitter cell of every row of every `Boundary | Guards | Submitter` table in ``text``."""
        boundaries = self.spec["boundaries"]
        found = {}
        for header in self.SUBMITTER_HEADER.finditer(text):
            for line in text[header.end():].lstrip("\n").split("\n\n", 1)[0].splitlines():
                cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
                if len(cells) >= 3 and cells[0] in boundaries:
                    found[cells[0]] = cells[2]
        return found

    def test_every_documented_submitter_is_the_one_the_spec_names(self):
        """QR-04: the drift test read the first cell only, so a wrong Submitter cell was invisible."""
        boundaries = set(self.spec["boundaries"])
        documents = {
            SKILLS / "contracts" / "workflow-protocol.md": boundaries,
            SKILLS / "gatekeeper-admiral" / "SKILL.md": boundaries,
            SKILLS / "design" / "gatekeeper-design" / "SKILL.md": {"design-to-build", "redesign-review"},
            SKILLS / "build" / "gatekeeper-build" / "SKILL.md": {"build-to-review"},
            SKILLS / "review" / "gatekeeper-code" / "SKILL.md": {"review-to-delivery"},
        }
        if IN_A_CHECKOUT:
            documents[REPO / "docs" / "gatekeepers.md"] = boundaries
        for path, expected in documents.items():
            with self.subTest(document=path.relative_to(REPO).as_posix()):
                rows = self.submitters_in(path.read_text(encoding="utf-8"))
                self.assertEqual(expected, set(rows))
                self.assertEqual({name: self.spec["boundaries"][name]["submitter"] for name in rows}, rows)

    def test_no_document_says_a_stack_locks_versions_intersect(self):
        """RR-gate-2: every declared version has to be one the registry entry offers; one match is not enough."""
        documents = sorted(SKILLS.rglob("*.md")) + (sorted((REPO / "docs").glob("*.md")) if IN_A_CHECKOUT else [])
        stale = [path.relative_to(REPO).as_posix() for path in documents
                 if re.search(r"versions\s+intersect", path.read_text(encoding="utf-8"))]
        self.assertEqual([], stale)

    def test_the_commander_and_the_design_gatekeeper_state_the_version_rule_the_engine_enforces(self):
        for path in (SKILLS / "design" / "commander" / "SKILL.md",
                     SKILLS / "design" / "commander" / "references" / "gate-evidence.md",
                     SKILLS / "design" / "gatekeeper-design" / "references" / "boundary-evidence.md"):
            with self.subTest(document=path.name):
                self.assertIn("every declared version is one the registry entry offers", path.read_text(encoding="utf-8"))

    def test_every_gatekeeper_says_a_typed_record_is_the_submitters_own_statement(self):
        """SEC-T-01: the gate does not compare an artifact with its record, and says what it does read."""
        statement = re.compile(r"submitter's\s+own\s+statement.*?never\s+compares\s+an\s+artifact's\s+content.*?"
                               r"`\.md`\s+and\s+`\.txt`\s+artifacts", re.S)
        for name in GATEKEEPER_SKILLS:
            with self.subTest(skill=name):
                self.assertRegex((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"), statement)

    def test_no_gate_document_says_the_validator_never_opens_an_artifact(self):
        """RR3-gate-1: check.py reads `.md` and `.txt` artifacts for blocked phrases and local links, so "never opens" is false."""
        claim = re.compile(r"(?:never\s+opens?|does\s+not\s+open|no\s+rule\s+opens)\s+(?:an\s+artifact|the\s+raw)", re.I)
        names = (*GATEKEEPER_SKILLS,)
        files = [SKILLS / name / "SKILL.md" for name in names]
        files += [SKILLS / "gates.yaml", SKILLS / "harness" / "gatekeeper" / "README.md", SKILLS / "harness" / "gatekeeper" / "check.py",
                  SKILLS / "contracts" / "evidence-standards.md", SKILLS / "contracts" / "universal-frameworks.md",
                  SKILLS / "review" / "security-review" / "references" / "scan-evidence.md"]
        for path in files:
            with self.subTest(document=path.name):
                self.assertIsNone(claim.search(path.read_text(encoding="utf-8")), f"{path} says the validator never opens an artifact")

    def test_the_design_gatekeeper_is_told_to_act_on_a_stack_lock_warning(self):
        """RR3-gate-2: the engine warns about an ended or unverified stack and passes; a procedure has to read the warning."""
        text = (SKILLS / "design" / "gatekeeper-design" / "SKILL.md").read_text(encoding="utf-8")
        row = next((line for line in text.splitlines() if line.startswith("|") and "stack-lock warning" in line), "")
        self.assertIn("support_ends", row, "no failure-mode row for a stack-lock warning")
        self.assertIn("verification_ttl_days", row)
        self.assertIn("Do not approve silently", row)

    def test_every_gatekeeper_says_what_a_schema_1_result_leaves_unchecked(self):
        """SEC-T-05: a flat schema-1 package outside a run passes, so the gatekeeper is told to read the result."""
        for name in GATEKEEPER_SKILLS:
            with self.subTest(skill=name):
                text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                row = next((line for line in text.splitlines()
                            if line.startswith("|") and "manifest_schema_version: 1" in line), "")
                self.assertIn("Return `REVISE`", row, f"{name} has no failure-mode row for manifest_schema_version: 1")
                self.assertIn("schema-2", row)

    @CHECKOUT_ONLY
    def test_the_gates_page_says_a_flat_schema_1_pass_is_the_structural_half(self):
        text = " ".join((REPO / "docs" / "gatekeepers.md").read_text(encoding="utf-8").split())
        self.assertIn("flat package outside a run", text)
        self.assertIn("typed records and the finding policy were not checked", text)
        self.assertIn("a bare sanctioned wording passes there without an applicability record", text)

    def test_gatekeeper_readme_artifact_backing_matches_gates(self):
        """The engine README counts and lists the artifact-backed keys, then counts the keys a fallback can stand in for."""
        backed, waivable = set(), set(self.spec["fallback_values"])
        for boundary in self.spec["boundaries"].values():
            backed.update(boundary.get("artifact_evidence", []))
            waivable.update(boundary.get("fallback_values", {}))
        readme = (SKILLS / "harness" / "gatekeeper" / "README.md").read_text(encoding="utf-8")
        paragraph = re.search(r"([A-Za-z-]+) evidence keys are artifact-backed(.*?)\b([A-Za-z-]+)\s+keys accept a sanctioned",
                              readme, re.S)
        self.assertIsNotNone(paragraph, "the README lost its artifact-backed keys paragraph")
        self.assertEqual(number_word(len(backed)), paragraph.group(1).lower())
        self.assertEqual(number_word(len(waivable)), paragraph.group(3).lower())
        missing = sorted(key for key in backed if f"`{key}`" not in paragraph.group(2))
        self.assertEqual(missing, [], f"README omits artifact-backed keys: {missing}")

    #: The review lenses whose finding packets carry a status template.
    LENSES = ("review/design-qa/SKILL.md", "review/mr-robot/SKILL.md", "review/security-review/SKILL.md")

    def test_every_documented_status_list_is_the_engines(self):
        """A document that lists the finding statuses `check.py` accepts lists `FINDING_STATUSES` and counts them."""
        statuses = gate_engine().FINDING_STATUSES
        claim = re.compile(r"a status from the ([a-z-]+) `[./]*harness/gatekeeper/check\.py` accepts \(([^)]*)\)")
        found = 0
        for path in sorted(SKILLS.rglob("*.md")):
            for count, listed in claim.findall(path.read_text(encoding="utf-8")):
                found += 1
                with self.subTest(document=path.relative_to(SKILLS).as_posix()):
                    self.assertEqual(number_word(len(statuses)), count)
                    self.assertEqual(statuses, set(re.findall(r"`([a-z-]+)`", listed)))
        self.assertTrue(found, "no document lists the statuses check.py accepts")

    def test_every_lens_packet_status_is_accepted_by_the_engine(self):
        statuses = gate_engine().FINDING_STATUSES
        for relative in self.LENSES:
            match = re.search(r"<status: ([^>]*)>", (SKILLS / relative).read_text(encoding="utf-8"))
            self.assertIsNotNone(match, f"{relative} carries no status template")
            declared = {part.strip() for part in match.group(1).split("|")}
            self.assertLessEqual(declared, statuses,
                                 f"{relative} teaches a status the gate rejects: {sorted(declared - statuses)}")


@CHECKOUT_ONLY
class ExitCodeTableTests(unittest.TestCase):
    """CR-14: docs/harness.md tabulates every tool's exit codes as "a description, not a contract the tests hold".

    Two parts of it can be held cheaply: the caution that a mistyped option is argparse's own exit 2 with nothing
    on stdout (so a 2 from `save_run.py` is not by itself `degraded`), and the named constants of the two tools
    that define their codes.
    """

    TOOLS = (
        "skills/harness/gatekeeper/check.py", "skills/harness/hooks/save_run.py", "skills/scripts/package_check.py",
        "skills/scripts/validate_manifests.py", "skills/scripts/check_runtime.py", "skills/scripts/check_parity.py",
        "skills/scripts/scan_record.py", "skills/scripts/output_paths.py", "skills/scripts/content_hash.py",
        "skills/harness/hooks/verify_registration.py", "skills/harness/hooks/check_readiness.py",
        "skills/harness/hooks/repair_registration.py", "skills/harness/hooks/guard_state.py", "scripts/install_hooks.py",
        "skills/design/gatekeeper-design/scripts/check.py", "skills/build/gatekeeper-build/scripts/check.py",
        "skills/review/gatekeeper-code/scripts/check.py", "skills/gatekeeper-admiral/scripts/check.py",
    )

    def test_a_mistyped_option_is_exit_2_with_nothing_on_stdout_in_every_tabulated_tool(self):
        with tempfile.TemporaryDirectory() as scratch:
            for tool in self.TOOLS:
                with self.subTest(tool=tool):
                    proc = subprocess.run([sys.executable, str(REPO / tool), "--no-such-option"], cwd=scratch,
                                          capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False)
                    self.assertEqual(2, proc.returncode, proc.stderr[-300:])
                    self.assertEqual("", proc.stdout)

    def test_the_tabulated_tools_exist(self):
        text = (REPO / "docs" / "harness.md").read_text(encoding="utf-8")
        table = section(text, "Exit codes and streams")
        self.assertIsNotNone(table, "docs/harness.md lost its 'Exit codes and streams' section")
        names = re.findall(r"^\| `([^`]+\.py)`", table, re.M)
        self.assertGreaterEqual(len(names), 12)
        for name in names:
            with self.subTest(tool=name):
                found = [path for prefix in ("skills", "skills/harness", "skills/*", ".") for path in REPO.glob(f"{prefix}/{name}")]
                self.assertTrue(found, f"docs/harness.md tabulates {name}, which is not in the tree")

    def test_the_named_exit_codes_are_the_ones_the_table_gives(self):
        """Each named constant's value picks the column of the row that has to describe it."""
        if str(HOOKS) not in sys.path:
            sys.path.insert(0, str(HOOKS))
        save_run = load_module("save_run", HOOKS / "save_run.py")
        install = load_module("install_hooks", REPO / "scripts" / "install_hooks.py")
        text = (REPO / "docs" / "harness.md").read_text(encoding="utf-8")
        lines = section(text, "Exit codes and streams").splitlines()

        def cells(start: str) -> list:
            line = next(line for line in lines if line.startswith(start))
            return [cell.strip() for cell in line.strip().strip("|").split("|")]

        column = {heading: index for index, heading in enumerate(cells("| Tool |"))}
        named = {
            "hooks/save_run.py": ((save_run.EXIT_OK, "`ok`"), (save_run.EXIT_REFUSED, "`refused`"),
                                  (save_run.EXIT_DEGRADED, "`degraded`"), (save_run.EXIT_ENGINE, "engine error")),
            "scripts/install_hooks.py": ((install.EXIT_REFUSED, "a write was refused"), (install.EXIT_DECLINED, "declined")),
        }
        for tool, codes in named.items():
            row = cells(f"| `{tool}`")
            for code, description in codes:
                with self.subTest(tool=tool, code=code):
                    self.assertIn(str(code), column, f"docs/harness.md has no column for exit {code}")
                    self.assertTrue(row[column[str(code)]].startswith(description),
                                    f"exit {code} of {tool} is described as {row[column[str(code)]]!r}")


@CHECKOUT_ONLY
class InstallerProbeProseTests(unittest.TestCase):
    """RR-ci-docs-3: Install.md described the probe the installer had before it learned `python3.13`."""

    def documented(self) -> dict:
        text = " ".join((REPO / "Install.md").read_text(encoding="utf-8").split())
        found = re.search(r"The shell installer tries (.*?), in that order, and the PowerShell installer tries (.*?); each takes", text)
        self.assertIsNotNone(found, "Install.md lost the sentence that lists the installers' Python probes")
        return {"shell": re.findall(r"`([^`]+)`", found.group(1)), "powershell": re.findall(r"`([^`]+)`", found.group(2))}

    def test_install_md_lists_the_interpreters_each_installer_tries_in_order(self):
        shell = (REPO / "scripts" / "install.sh").read_text(encoding="utf-8")
        shell_names = re.search(r"find_compatible_python\(\) \{.*?for candidate in ([^;]+); do", shell, re.S).group(1).split()
        power = (REPO / "scripts" / "install.ps1").read_text(encoding="utf-8")
        body = re.search(r"function Find-CompatiblePythonCommand \{(.*?)foreach", power, re.S).group(1)
        power_names = [" ".join([command] + re.findall(r'"([^"]+)"', arguments))
                       for command, arguments in re.findall(r'Command = "([^"]+)"; Arguments = @\(([^)]*)\)', body)]
        self.assertEqual({"shell": shell_names, "powershell": power_names}, self.documented())


if __name__ == "__main__":
    unittest.main()
