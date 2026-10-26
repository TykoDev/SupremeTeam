"""Regression coverage for data_formats.py: the YAML subset reader and the line-ending-agnostic hash.

The parser dropped comment-looking lines, stripped a `` #`` tail and collapsed blank
lines before it knew it was inside a block scalar, where all three are content.
SKILL.md frontmatter descriptions are folded block scalars parsed through it, so a
description mentioning an issue number was validated as truncated text. A Windows
path written in YAML lost its backslashes to a Python-literal reader. Every sha256
the catalog records folds text to LF first, so an LF and a CRLF checkout verify
alike, and content_hash.py, the command specialists report hashes with, agrees.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from data_formats import (
    DataFormatError,
    content_sha256,
    normalize_line_endings,
    parse_frontmatter,
    parse_scalar,
    parse_yaml,
)

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment without PyYAML
    yaml = None

SCRIPTS = Path(__file__).resolve().parent


class NumberSpellingTests(unittest.TestCase):
    """RR-gate-5: a number is a float only when it prints back unchanged, which is wider than version numbers."""

    def test_a_spelling_that_does_not_print_back_unchanged_stays_text(self):
        for text in ("3.10", "1.20", ".5", "+1.5", "1.", "1.50", "-2.50", "1.5e+3"):
            with self.subTest(text=text):
                self.assertEqual(parse_scalar(text), text)

    def test_a_spelling_that_prints_back_unchanged_is_a_number(self):
        for text, value in (("1.5", 1.5), ("-0.25", -0.25), ("100.0", 100.0), ("7", 7), ("-3", -3)):
            with self.subTest(text=text):
                self.assertEqual(parse_scalar(text), value)

    def test_a_leading_zero_stays_text_because_pyyaml_reads_it_as_octal(self):
        for text in ("010", "007", "-010", "+08"):
            with self.subTest(text=text):
                self.assertEqual(parse_scalar(text), text)
        self.assertEqual((parse_scalar("0"), parse_scalar("-0"), parse_scalar("10")), (0, 0, 10))

    def test_one_document_per_file(self):
        self.assertEqual(parse_yaml("---\na: 1\n...\n"), {"a": 1})
        with self.assertRaises(DataFormatError):
            parse_yaml("a: 1\n---\nb: 2\n")

    @unittest.skipIf(yaml is None, "PyYAML is optional; the cases above pin the expected values")
    def test_pyyaml_reads_a_leading_zero_as_another_number(self):
        self.assertEqual(yaml.safe_load("010"), 8)
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load("a: 1\n---\nb: 2\n")

    @unittest.skipIf(yaml is None, "PyYAML is optional; the cases above pin the expected values")
    def test_the_difference_from_pyyaml_is_the_documented_one(self):
        """PyYAML reads the first group as floats and the second as text, for exactly the spellings above."""
        for text in ("3.10", ".5", "+1.5", "1.", "1.50", "1.5e+3"):
            with self.subTest(text=text):
                self.assertIsInstance(yaml.safe_load(text), float)
                self.assertIsInstance(parse_scalar(text), str)
        for text in ("1.5e3", "1e3"):
            with self.subTest(text=text):
                self.assertEqual(yaml.safe_load(text), parse_scalar(text))


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


class QuotedScalarTests(unittest.TestCase):
    """YAML quotes: single is literal, double escapes. A path survives both spellings."""

    def test_a_single_quoted_scalar_keeps_its_backslashes(self):
        for text, expected in ((r"'C:\Users\Jo Smith\proj'", r"C:\Users\Jo Smith\proj"),
                               ("'C:/Program Files/x'", "C:/Program Files/x"),
                               (r"'\\host\share\file'", r"\\host\share\file")):
            with self.subTest(text=text):
                self.assertEqual(parse_scalar(text), expected)

    def test_a_doubled_quote_is_the_only_single_quote_escape(self):
        self.assertEqual(parse_scalar("'it''s here'"), "it's here")
        self.assertEqual(parse_scalar("'a''''b'"), "a''b")

    def test_an_unpaired_quote_inside_single_quotes_is_refused(self):
        with self.assertRaises(DataFormatError):
            parse_scalar("'it's here'")

    def test_a_backslashed_path_round_trips_through_a_mapping(self):
        parsed = parse_yaml("workspace: 'C:\\Users\\Jo\\proj'\nhost: 'test-host'\n")
        self.assertEqual(parsed, {"workspace": "C:\\Users\\Jo\\proj", "host": "test-host"})

    def test_double_quoted_text_still_escapes(self):
        self.assertEqual(parse_scalar('"a\\nb"'), "a\nb")


class LineEndingAgnosticHashTests(unittest.TestCase):
    """The catalog must work on an LF and a CRLF checkout alike: every recorded
    sha256 folds text to LF first, binary is untouched, and the CLI that
    specialists use to report hashes agrees with the gate."""

    TEXT = "line one\nline two\n\nend\n"

    def test_text_hashes_agree_across_line_endings(self):
        lf = self.TEXT.encode("utf-8")
        crlf = self.TEXT.replace("\n", "\r\n").encode("utf-8")
        self.assertEqual(normalize_line_endings(crlf), lf)
        self.assertEqual(normalize_line_endings(lf), lf)
        with tempfile.TemporaryDirectory() as directory:
            a = Path(directory) / "a.md"
            a.write_bytes(lf)
            b = Path(directory) / "b.md"
            b.write_bytes(crlf)
            self.assertEqual(content_sha256(a), content_sha256(b))
            self.assertEqual(content_sha256(a), hashlib.sha256(lf).hexdigest())

    def test_binary_content_is_hashed_byte_for_byte(self):
        payload = b"PK\x03\x04\r\n\x00\x00binary\r\n"
        self.assertEqual(normalize_line_endings(payload), payload)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "archive.zip"
            path.write_bytes(payload)
            self.assertEqual(content_sha256(path), hashlib.sha256(payload).hexdigest())

    def test_content_hash_cli_matches_the_gate_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "evidence.md"
            path.write_bytes(self.TEXT.replace("\n", "\r\n").encode("utf-8"))
            proc = subprocess.run([sys.executable, str(SCRIPTS / "content_hash.py"), str(path), "--project-root", str(root)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = json.loads(proc.stdout)
            self.assertEqual(out["hashes"], {"evidence.md": hashlib.sha256(self.TEXT.encode("utf-8")).hexdigest()})
            proc = subprocess.run([sys.executable, str(SCRIPTS / "content_hash.py"), str(root / "missing.md")],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1)
            self.assertFalse(json.loads(proc.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
