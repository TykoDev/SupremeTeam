"""Regression coverage for the YAML subset reader: block scalars keep their own lines.

The parser dropped comment-looking lines, stripped a `` #`` tail and collapsed blank
lines before it knew it was inside a block scalar, where all three are content.
SKILL.md frontmatter descriptions are folded block scalars parsed through it, so a
description mentioning an issue number was validated as truncated text.
"""
from __future__ import annotations

import unittest

from data_formats import DataFormatError, parse_frontmatter, parse_yaml

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment without PyYAML
    yaml = None


class BlockScalarTests(unittest.TestCase):
    def test_a_literal_block_keeps_hash_lines_hash_tails_and_blank_lines(self):
        text = "a: |\n  one\n  # not a comment\n  two # tail\n\n  three\nb: 1\n"
        self.assertEqual(parse_yaml(text), {"a": "one\n# not a comment\ntwo # tail\n\nthree", "b": 1})

    def test_a_folded_block_joins_lines_and_turns_a_blank_line_into_a_paragraph_break(self):
        text = "a: >-\n  first line\n  second # tail\n\n  # hashed paragraph\n  last\nb: 1\n"
        self.assertEqual(parse_yaml(text), {"a": "first line second # tail\n# hashed paragraph last", "b": 1})

    def test_several_blank_lines_in_a_folded_block_are_that_many_newlines(self):
        self.assertEqual(parse_yaml("a: >\n  x\n\n\n  y\n"), {"a": "x\n\ny"})

    def test_relative_indentation_inside_a_literal_block_is_kept(self):
        text = "a: |\n  def f():\n      return 1\n  end\nb: 2\n"
        self.assertEqual(parse_yaml(text), {"a": "def f():\n    return 1\nend", "b": 2})

    def test_the_header_comment_is_not_part_of_the_value(self):
        self.assertEqual(parse_yaml("a: |  # note\n  body # keep\nb: 3\n"), {"a": "body # keep", "b": 3})

    def test_a_dedented_comment_after_the_block_is_a_comment_again(self):
        self.assertEqual(parse_yaml("a: |\n  text\n\n# real comment\nb: 1\n"), {"a": "text", "b": 1})

    def test_a_block_inside_a_nested_mapping_and_inside_a_list_item(self):
        self.assertEqual(parse_yaml("top:\n  desc: >-\n    hello #1\n    world\n  other: 2\n"),
                         {"top": {"desc": "hello #1 world", "other": 2}})
        self.assertEqual(parse_yaml("items:\n  - name: x\n    desc: |\n      l1\n      # l2\n  - name: y\n"),
                         {"items": [{"name": "x", "desc": "l1\n# l2"}, {"name": "y"}]})

    def test_outside_a_block_comments_and_blank_lines_are_still_dropped(self):
        text = "a: 1  # c\n# full\nb: 'x # y'\n\nc:\n  - 1 # c\n"
        self.assertEqual(parse_yaml(text), {"a": 1, "b": "x # y", "c": [1]})

    def test_a_tab_indented_block_line_is_still_refused(self):
        with self.assertRaises(DataFormatError):
            parse_yaml("a: |\n\ttext\n")

    def test_frontmatter_descriptions_keep_issue_references(self):
        text = "---\nname: demo\ndescription: >-\n  Use for #123 issues  # not a comment\n  # also text\n---\nbody\n"
        self.assertEqual(parse_frontmatter(text),
                         {"name": "demo", "description": "Use for #123 issues  # not a comment # also text"})

    @unittest.skipIf(yaml is None, "PyYAML is optional; the cases above pin the expected values")
    def test_block_scalars_agree_with_pyyaml(self):
        """An independent reader settles what the hand-written expectations above claim."""
        samples = (
            "a: |\n  one\n  # not a comment\n  two # tail\n\n  three\nb: 1\n",
            "a: >-\n  first line\n  second # tail\n\n  # hashed paragraph\n  last\nb: 1\n",
            "a: >\n  x\n\n\n  y\n",
            "a: |\n  def f():\n      return 1\n  end\nb: 2\n",
            "a: |  # note\n  body # keep\nb: 3\n",
            "a: |\n  text\n\n# real comment\nb: 1\n",
            "top:\n  desc: >-\n    hello #1\n    world\n  other: 2\n",
            "items:\n  - name: x\n    desc: |\n      l1\n      # l2\n  - name: y\n",
            "a: |+\n  x\n\nb: 1\n",
            "a: |-\n  x\nb: 1\n",
        )

        def trimmed(value):
            # The reader always trims trailing whitespace, whatever the chomping indicator says.
            if isinstance(value, str):
                return value.rstrip()
            if isinstance(value, dict):
                return {k: trimmed(v) for k, v in value.items()}
            if isinstance(value, list):
                return [trimmed(v) for v in value]
            return value

        for text in samples:
            with self.subTest(text=text):
                self.assertEqual(parse_yaml(text), trimmed(yaml.safe_load(text)))


if __name__ == "__main__":
    unittest.main()
