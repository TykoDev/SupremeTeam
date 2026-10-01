"""The inventories and preconditions that documents state are checked against the tree and the specs.

``validate_manifests.py`` compares the documents' totals (`53 skills`) with the roster, but the
sections a total is made of were never added up: a heading that states no count, or a count that
disagrees with its own table, left the total standing while the parts did not sum to it. The
engineer's precondition is the other kind of drift: it asked for a stack lock that
``pipelines.yaml`` orders after the implementation spec, so the stage could only be satisfied by
going back to a later stage.

The first group reads the checkout's AGENTS.md and docs/skills.md, so it skips in an installed
copy, which carries only ``skills/``.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from _catalog import SKILLS, load_spec

REPO = SKILLS.parent
IN_A_CHECKOUT = (REPO / "AGENTS.md").is_file() and (REPO / "docs").is_dir()
CHECKOUT_ONLY = unittest.skipUnless(IN_A_CHECKOUT, "installed copy: only skills/ is present")

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

    def test_the_layout_sentence_sums_to_the_total_it_states(self):
        text = read(REPO / "AGENTS.md")
        sentence = re.search(r"\*\*(\d+) skills\*\*:(.*?)\.\s+Plus", text, re.S)
        self.assertIsNotNone(sentence, "AGENTS.md lost its '**N skills**: Group n, ... Plus' sentence")
        total, groups = int(sentence.group(1)), [int(n) for n in re.findall(r"\b(\d+)\b", sentence.group(2))]
        self.assertEqual(sum(groups), total, f"the groups state {groups}")
        self.assertEqual(total, len(skills_on_disk()))


class EngineerPreconditionTests(unittest.TestCase):
    """What the engineer needs before it slices must come from a stage that runs before it."""

    def later_steps(self) -> list:
        stages = load_spec("pipelines.yaml")["pipelines"]["design"]["stages"]
        own = next(index for index, stage in enumerate(stages) if stage["owner"] == "engineer")
        return [stage["step"] for stage in stages[own + 1:]]

    def preconditions(self) -> dict:
        """Where the engineer states what it needs: workflow step 1, and the preconditions table."""
        skill = (SKILLS / "design" / "engineer" / "SKILL.md").read_text(encoding="utf-8")
        item = re.search(r"^1\. (Confirm the package is sliceable.*)$", skill, re.M)
        self.assertIsNotNone(item, "engineer workflow step 1 moved or was reworded")
        sentence = re.split(r"(?<=\.)\s+(?=[A-Z])", item.group(1))[0]
        workflow = (SKILLS / "design" / "engineer" / "references" / "workflow.md").read_text(encoding="utf-8")
        section = re.search(r"^## Preconditions\s*$(.*?)^## ", workflow, re.M | re.S)
        self.assertIsNotNone(section, "engineer references/workflow.md lost its Preconditions section")
        table = "\n".join(line for line in section.group(1).splitlines() if line.startswith("|"))
        return {"SKILL.md workflow step 1": sentence, "references/workflow.md preconditions table": table}

    def test_the_engineer_is_not_the_last_stage(self):
        self.assertTrue(self.later_steps())

    def test_no_precondition_names_an_artifact_a_later_stage_produces(self):
        for step in self.later_steps():
            name = re.compile(re.sub(r"[-_]", r"[\\s_-]*", step), re.I)
            for where, text in self.preconditions().items():
                with self.subTest(step=step, where=where):
                    self.assertIsNone(name.search(text),
                                      f"engineer {where} names '{step}', which pipelines.yaml orders after it")


if __name__ == "__main__":
    unittest.main()
