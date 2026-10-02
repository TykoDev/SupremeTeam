"""Regression tests for quick_validate: the verdict must not depend on whether PyYAML is installed.

The verdict is captured as gate evidence (`validation_report`), so a SKILL.md that PyYAML
rejects must not read "Skill is valid!" on a host that lacks it. The module picks its parser
at import, so each parser gets its own copy of it, loaded by path.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parent / "quick_validate.py"
HAVE_YAML = importlib.util.find_spec("yaml") is not None


def load(name: str, hide_yaml: bool):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"yaml": None} if hide_yaml else {}):
        spec.loader.exec_module(module)
    return module


STDLIB = load("quick_validate_stdlib_parser", hide_yaml=True)
FULL = load("quick_validate_pyyaml_parser", hide_yaml=False) if HAVE_YAML else None


def verdict(module, frontmatter: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nbody\n", encoding="utf-8")
        return module.validate_skill(tmp)


REJECTED = {
    "colon-space in a plain description": "name: sample\ndescription: Use when: the user asks about flaky tests",
    "trailing colon": "name: sample\ndescription: Use when:",
    "colon-space after a URL": "name: sample\ndescription: See https://example.com: the docs",
    "colon-space in another key": "name: sample\ndescription: ok\nlicense: MIT: see file",
}
ACCEPTED = {
    "double-quoted": 'name: sample\ndescription: "Use when: the user asks about flaky tests"',
    "single-quoted": "name: sample\ndescription: 'Use when: the user asks'",
    "folded block scalar": "name: sample\ndescription: >-\n  Fixes flaky tests. Use when: CI is red.\n  Also when: it is green.",
    "literal block scalar": "name: sample\ndescription: |\n  Use when: the user asks",
    "colon without a following space": "name: sample\ndescription: Meet at 10:30 or read http://x.example/a:b",
    "plain": "name: sample\ndescription: Fixes flaky tests and nothing else",
}


class FallbackParserTests(unittest.TestCase):
    def test_the_stdlib_parser_rejects_what_pyyaml_rejects(self):
        for label, frontmatter in REJECTED.items():
            with self.subTest(label):
                ok, message = verdict(STDLIB, frontmatter)
                self.assertFalse(ok, message)
                self.assertIn("mapping values are not allowed here", message)

    def test_the_stdlib_parser_still_accepts_valid_frontmatter(self):
        for label, frontmatter in ACCEPTED.items():
            with self.subTest(label):
                ok, message = verdict(STDLIB, frontmatter)
                self.assertTrue(ok, message)

    def test_the_message_names_the_key_and_the_fix(self):
        _, message = verdict(STDLIB, REJECTED["colon-space in a plain description"])
        self.assertIn("'description'", message)
        self.assertIn("quote it", message)

    def test_only_plain_top_level_values_are_checked(self):
        find = STDLIB._bare_colon_key
        self.assertIsNone(find("name: sample\n# note: a comment\ndescription: Fine # trailing: comment"))
        self.assertIsNone(find("metadata:\n  note: a: b\nname: sample"))
        self.assertIsNone(find('"odd: key": value'))
        self.assertIsNone(find("description: [a: b]"))
        self.assertEqual("description", find("description: Use when: X"))


class AllowedKeyTests(unittest.TestCase):
    """The catalog extension keys are the ones the catalog's skills use, and no others."""

    CATALOG = Path(__file__).resolve().parents[3]

    def test_a_key_no_skill_uses_is_not_quietly_accepted(self):
        for key in ("family", "role", "auth_context", "mcp_servers", "canonical"):
            with self.subTest(key=key):
                ok, message = verdict(STDLIB, f"name: sample\ndescription: ok\nversion: 1.0.0\n{key}: x")
                self.assertFalse(ok, message)
                self.assertIn(f"Unexpected key(s) in SKILL.md frontmatter: {key}", message)

    def test_the_one_catalog_extension_is_accepted(self):
        ok, message = verdict(STDLIB, "name: sample\ndescription: ok\nversion: 1.0.0")
        self.assertTrue(ok, message)

    def test_every_skill_in_the_catalog_still_validates(self):
        skills = sorted(self.CATALOG.rglob("SKILL.md"))
        self.assertGreater(len(skills), 40, "the catalog was not found where this test expects it")
        for skill in skills:
            with self.subTest(skill=skill.parent.name):
                ok, message = STDLIB.validate_skill(skill.parent)
                self.assertTrue(ok, message)


@unittest.skipUnless(HAVE_YAML, "PyYAML is not installed; there is no second parser to compare against")
class ParityTests(unittest.TestCase):
    def test_both_parsers_agree_on_every_case(self):
        for label, frontmatter in {**REJECTED, **ACCEPTED}.items():
            with self.subTest(label):
                self.assertEqual(verdict(FULL, frontmatter)[0], verdict(STDLIB, frontmatter)[0])


if __name__ == "__main__":
    unittest.main()
