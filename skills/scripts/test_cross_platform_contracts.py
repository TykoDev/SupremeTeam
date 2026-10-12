#!/usr/bin/env python3
"""Cross-platform data contracts: what a YAML scalar means, and what counts as inside the repository.

The re-run surfaced two host-shaped gaps: a Windows path written in YAML lost its
backslashes to a Python-literal reader, and ``/etc/ci.yml`` passed a "relative path"
check on a machine where ``Path.is_absolute`` asks for a drive letter. Both are
pinned here in the alternative spellings the first suite did not hold.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from data_formats import DataFormatError, load_data, parse_scalar, parse_yaml  # noqa: E402
import validate_manifests  # noqa: E402

RUNTIME = HERE.parent / "runtime-manifest.yaml"


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


class WorkflowPathTests(unittest.TestCase):
    """``ci.workflow`` names a file inside the repository in every host spelling of "outside"."""

    def runtime(self) -> dict:
        return copy.deepcopy(load_data(RUNTIME))

    def workflow_errors(self, workflow: str) -> list:
        runtime = self.runtime()
        runtime["ci"]["workflow"] = workflow
        errors: list = []
        validate_manifests.check_ci_declaration(runtime, errors)
        return errors

    def test_every_absolute_spelling_is_refused(self):
        for spelling in ("/etc/ci.yml", "\\etc\\ci.yml", "C:/other/ci.yml", "D:\\ci.yml", "//host/share/ci.yml", "../ci.yml", ""):
            with self.subTest(spelling=spelling):
                errors = self.workflow_errors(spelling)
                self.assertTrue(any("ci.workflow must be a relative path" in error for error in errors), errors)

    def test_the_shipped_relative_workflow_still_passes(self):
        errors = self.workflow_errors(str(load_data(RUNTIME)["ci"]["workflow"]))
        self.assertFalse([error for error in errors if "ci.workflow" in error], errors)

    def test_a_relative_workflow_beside_the_manifest_passes(self):
        errors = self.workflow_errors(".github/workflows/ci.yml")
        self.assertFalse([error for error in errors if "ci.workflow" in error], errors)


if __name__ == "__main__":
    unittest.main()
