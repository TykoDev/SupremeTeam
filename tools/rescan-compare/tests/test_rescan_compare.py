import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

import rescan_compare  # noqa: E402


def report(runs, findings):
    return {"runs": runs, "findings": findings}


class CompareTests(unittest.TestCase):
    def test_identical_reports_are_equal(self):
        a = report(["run-a", "run-b"], [{"id": "F-1", "severity": "Major"}])
        b = report(["run-b", "run-a"], [{"id": "F-1", "severity": "Major"}])
        result = rescan_compare.compare(a, b)
        self.assertTrue(result["equal"])
        self.assertEqual(result["runs"]["compared"], 2)
        self.assertEqual(result["findings"]["compared"], 1)

    def test_a_missing_run_is_a_difference(self):
        a = report(["run-a", "run-b"], [])
        b = report(["run-a"], [])
        result = rescan_compare.compare(a, b)
        self.assertFalse(result["equal"])
        self.assertEqual(result["runs"]["missing_in_after"], ["run-b"])

    def test_an_extra_run_is_a_difference(self):
        a = report(["run-a"], [])
        b = report(["run-a", "run-c"], [])
        result = rescan_compare.compare(a, b)
        self.assertFalse(result["equal"])
        self.assertEqual(result["runs"]["extra_in_after"], ["run-c"])

    def test_a_missing_finding_is_a_difference(self):
        a = report([], [{"id": "F-1", "severity": "Major"}, {"id": "F-2", "severity": "Info"}])
        b = report([], [{"id": "F-2", "severity": "Info"}])
        result = rescan_compare.compare(a, b)
        self.assertFalse(result["equal"])
        self.assertEqual(result["findings"]["missing_in_after"], [{"id": "F-1", "severity": "Major"}])

    def test_a_severity_change_is_a_difference(self):
        a = report([], [{"id": "F-1", "severity": "Major"}, {"id": "F-2", "severity": "Info"}])
        b = report([], [{"id": "F-1", "severity": "Minor"}, {"id": "F-2", "severity": "Info"}])
        result = rescan_compare.compare(a, b)
        self.assertFalse(result["equal"])
        self.assertEqual(result["findings"]["missing_in_after"], [{"id": "F-1", "severity": "Major"}])
        self.assertEqual(result["findings"]["extra_in_after"], [{"id": "F-1", "severity": "Minor"}])

    def test_findings_are_identified_by_what_they_say_when_the_report_carries_it(self):
        """run-audit's ids are positions: a tampered copy with one different Major in the same slot read as equal."""
        major = {"id": "F-1", "severity": "Major", "where": "runs/a/build/manifest.json", "statement": "evidence missing: r.md"}
        other = {**major, "statement": "evidence missing: other.md"}
        result = rescan_compare.compare(report([], [major]), report([], [other]))
        self.assertFalse(result["equal"])
        self.assertEqual(result["findings"]["missing_in_after"], [major])
        self.assertEqual(result["findings"]["extra_in_after"], [other])
        renumbered = {**major, "id": "F-7"}
        self.assertTrue(rescan_compare.compare(report([], [major]), report([], [renumbered]))["equal"])
        inserted = {"id": "F-1", "severity": "Critical", "where": "x", "statement": "new"}
        shifted = rescan_compare.compare(report([], [major]), report([], [inserted, {**major, "id": "F-2"}]))
        self.assertEqual((shifted["findings"]["missing_in_after"], shifted["findings"]["extra_in_after"]), ([], [inserted]))

    def test_run_entries_may_be_id_mappings(self):
        a = report([{"id": "run-a"}], [])
        b = report(["run-a"], [])
        self.assertTrue(rescan_compare.compare(a, b)["equal"])

    def test_malformed_reports_raise_report_error(self):
        with self.assertRaises(rescan_compare.ReportError):
            rescan_compare.compare({"runs": "run-a", "findings": []}, report([], []))
        with self.assertRaises(rescan_compare.ReportError):
            rescan_compare.compare(report([], [{"id": "F-1"}]), report([], []))
        with self.assertRaises(rescan_compare.ReportError):
            rescan_compare.compare(report([], [{"id": "F-1", "severity": "huge"}]), report([], []))


class CliTests(unittest.TestCase):
    def write(self, tmp, name, payload):
        path = Path(tmp) / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return str(path)

    def test_exit_codes_follow_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            same_a = self.write(tmp, "a.json", report(["run-a"], [{"id": "F-1", "severity": "Major"}]))
            same_b = self.write(tmp, "b.json", report(["run-a"], [{"id": "F-1", "severity": "Major"}]))
            diff = self.write(tmp, "c.json", report([], [{"id": "F-1", "severity": "Major"}]))
            bad = self.write(tmp, "d.json", {"runs": 7, "findings": []})
            self.assertEqual(rescan_compare.main([same_a, same_b]), 0)
            self.assertEqual(rescan_compare.main([same_a, diff]), 1)
            self.assertEqual(rescan_compare.main([same_a, bad]), 2)
            self.assertEqual(rescan_compare.main([same_a, str(Path(tmp) / "absent.json")]), 2)

    def test_out_file_carries_the_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = self.write(tmp, "a.json", report(["run-a"], []))
            after = self.write(tmp, "b.json", report(["run-a", "run-c"], []))
            out = Path(tmp) / "report.json"
            self.assertEqual(rescan_compare.main([before, after, "--out", str(out)]), 1)
            written = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(written["equal"])
            self.assertEqual(written["runs"]["extra_in_after"], ["run-c"])

    def test_version_reports_the_package_version(self):
        with self.assertRaises(SystemExit) as caught:
            rescan_compare.main(["--version"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
