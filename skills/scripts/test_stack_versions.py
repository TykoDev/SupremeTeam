"""The version grammar a tech-stack minimum and a stack lock are both held to (WP-13).

The registry used to pin exact majors as unlabelled numbers and the gate compared them as text, so a project on a
newer supported release could not pass and ``3.10`` was one YAML reader away from ``3.1``. A minimum and a version in
use are text now, and this is how they are read and compared.
"""
from __future__ import annotations

import unittest

import stack_versions as versions


class GrammarTests(unittest.TestCase):
    def test_a_version_is_its_dotted_numbers_and_whether_it_is_a_release(self):
        for text, expected in (("19", ((19,), 1)), ("v24.1.0", ((24, 1, 0), 1)), ("V6.0", ((6, 0), 1)), ("2024", ((2024,), 1)),
                               ("0.115.2", ((0, 115, 2), 1)), (" 1.27 ", ((1, 27), 1)),
                               ("19.0.0-rc.1", ((19, 0, 0), 0)), ("3.13.0rc1", ((3, 13, 0), 0)), ("1.27beta2", ((1, 27), 0)),
                               ("1.0.0+build.5", ((1, 0, 0), 1))):
            with self.subTest(text=text):
                self.assertEqual(versions.parse(text), expected)
                self.assertTrue(versions.is_version(text))

    def test_what_is_not_one_version_in_use_is_refused(self):
        """A lock says which version the project uses, not which would do."""
        for text in ("^19", "~19.1", "24.x", "19.*", ">=3.11", "<4", "1 || 2", "19 - 20", "latest", "lts", "", " ", "19.", ".5",
                     "nineteen", "19,20", "19/20"):
            with self.subTest(text=text):
                self.assertFalse(versions.is_version(text))
                with self.assertRaises(versions.VersionError) as raised:
                    versions.parse(text)
                self.assertIn("is not one version", str(raised.exception))

    def test_a_number_is_refused_because_it_does_not_keep_its_spelling(self):
        for value in (19, 3.10, True, None, ["19"], {"v": "19"}):
            with self.subTest(value=value):
                with self.assertRaises(versions.VersionError) as raised:
                    versions.parse(value)
                self.assertIn("is not text", str(raised.exception))
        self.assertEqual(str(3.10), "3.1", "which is why a version is text")

    def test_a_component_name_is_lower_case_letters_digits_and_dashes(self):
        for name in ("node", "rust-edition", "tanstack-start", "c3"):
            self.assertTrue(versions.is_component(name), name)
        for name in ("Node", "node js", "-node", "", "node_js", None, 3):
            self.assertFalse(versions.is_component(name), name)


class ComparisonTests(unittest.TestCase):
    def test_below_pads_with_zeros_and_compares_numbers_not_text(self):
        for version, minimum, expected in (("6", "6.0", False), ("6.0", "6", False), ("6.0.0", "6", False), ("5.9.3", "6.0", True),
                                           ("1.9", "1.27", True), ("1.27", "1.9", False), ("22.11.0", "24", True),
                                           ("24.0.0", "24", False), ("26.1.0", "24", False), ("0.114.9", "0.115", True),
                                           ("v19.2.0", "19", False), ("2021", "2024", True)):
            with self.subTest(version=version, minimum=minimum):
                self.assertEqual(versions.below(version, minimum), expected)

    def test_a_pre_release_orders_below_its_release_and_above_the_one_before(self):
        self.assertTrue(versions.below("19.0.0-rc.1", "19.0.0"))
        self.assertTrue(versions.below("19.0.0-rc.1", "19"))
        self.assertFalse(versions.below("19.0.0", "19.0.0-rc.1"))
        self.assertFalse(versions.below("19.0.0-rc.1", "18.3.1"))
        self.assertFalse(versions.below("19.0.0+build.5", "19.0.0"), "build metadata changes nothing")
        self.assertFalse(versions.below("19.0.0-rc.1", "19.0.0-rc.1"))

    def test_beyond_stops_at_the_precision_of_the_limit(self):
        """`verified_through: 6` means the whole 6 line: 6.9.3 is inside it and 7.0 is past it."""
        for version, limit, expected in (("7.0", "6", True), ("6.9.3", "6", False), ("6", "6", False), ("3", "2", True),
                                         ("2.49.1", "2", False), ("6.1", "6.0", True), ("6.0.9", "6.0", False), ("5.9", "6", False),
                                         ("7.0.0-beta.1", "6", True)):
            with self.subTest(version=version, limit=limit):
                self.assertEqual(versions.beyond(version, limit), expected)

    def test_a_comparison_refuses_a_side_that_is_not_a_version(self):
        for call in (lambda: versions.below("^19", "19"), lambda: versions.below("19", "latest"),
                     lambda: versions.beyond("19", ">=6"), lambda: versions.beyond(19, "6")):
            with self.assertRaises(versions.VersionError):
                call()


if __name__ == "__main__":
    unittest.main()
