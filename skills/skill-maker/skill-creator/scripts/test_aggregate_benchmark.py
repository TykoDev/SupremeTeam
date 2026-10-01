"""Regression tests for aggregate_benchmark: the documented layout, honest gaps, loud failure."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import aggregate_benchmark as agg


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def grading(passed: int, total: int, **extra) -> dict:
    return {"expectations": [{"text": f"check {i}", "passed": i < passed, "evidence": "seen"} for i in range(total)],
            "summary": {"passed": passed, "failed": total - passed, "total": total,
                        "pass_rate": passed / total},
            **extra}


def run_main(*argv) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with patch.object(sys, "argv", ["aggregate_benchmark", *map(str, argv)]), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            agg.main()
        except SystemExit as exc:
            code = exc.code or 0
    return code, out.getvalue(), err.getvalue()


class DocumentedLayoutTests(unittest.TestCase):
    """references/real-evals.md: eval-<ID>/<config>/{outputs,grading.json,timing.json}, no run-* directory."""

    def make_workspace(self, root: Path) -> Path:
        iteration = root / "iteration-1"
        write_json(iteration / "eval-0-quarterly-report" / "eval_metadata.json",
                   {"eval_id": 0, "eval_name": "quarterly-report", "prompt": "p", "assertions": []})
        for config, passed in (("with_skill", 4), ("without_skill", 2)):
            run = iteration / "eval-0-quarterly-report" / config
            (run / "outputs").mkdir(parents=True)
            write_json(run / "grading.json", grading(passed, 4))
            write_json(run / "timing.json", {"total_tokens": 1000 * (passed + 1), "total_duration_seconds": 10.0 * passed})
        return iteration

    def test_configuration_directory_is_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            benchmark = agg.generate_benchmark(self.make_workspace(Path(tmp)))
        self.assertEqual(2, len(benchmark["runs"]))
        summary = benchmark["run_summary"]
        self.assertEqual(1.0, summary["with_skill"]["pass_rate"]["mean"])
        self.assertEqual(0.5, summary["without_skill"]["pass_rate"]["mean"])
        self.assertEqual("+0.50", summary["delta"]["pass_rate"])
        self.assertEqual([0], benchmark["metadata"]["evals_run"])
        self.assertEqual({"quarterly-report"}, {r["eval_name"] for r in benchmark["runs"]})

    def test_main_writes_a_benchmark_that_holds_the_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            iteration = self.make_workspace(Path(tmp))
            code, _, _ = run_main(iteration)
            self.assertEqual(0, code)
            written = json.loads((iteration / "benchmark.json").read_text(encoding="utf-8"))
            self.assertEqual(2, len(written["runs"]))
            self.assertIn("±", (iteration / "benchmark.md").read_text(encoding="utf-8"))

    def test_runs_per_configuration_is_counted_not_assumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            iteration = self.make_workspace(Path(tmp))
            self.assertEqual(1, agg.generate_benchmark(iteration)["metadata"]["runs_per_configuration"])
            for n in (1, 2, 3, 4):
                write_json(iteration / "eval-1" / "with_skill" / f"run-{n}" / "grading.json", grading(1, 1))
            self.assertEqual(4, agg.generate_benchmark(iteration)["metadata"]["runs_per_configuration"])

    def test_legacy_run_directories_still_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for config, passed in (("with_skill", 3), ("without_skill", 1)):
                for n in (1, 2):
                    write_json(root / "eval-1" / config / f"run-{n}" / "grading.json", grading(passed, 3))
            benchmark = agg.generate_benchmark(root)
        self.assertEqual(4, len(benchmark["runs"]))
        self.assertEqual([1, 2], sorted({r["run_number"] for r in benchmark["runs"]}))
        self.assertEqual(2, benchmark["metadata"]["runs_per_configuration"])


class NoRunsIsAFailureTests(unittest.TestCase):
    def test_eval_directories_without_grading_write_nothing_and_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "eval-0" / "with_skill" / "outputs").mkdir(parents=True)
            (root / "eval-0" / "without_skill" / "outputs").mkdir(parents=True)
            code, out, err = run_main(root)
            self.assertNotEqual(0, code)
            self.assertIn("no graded runs", err)
            self.assertEqual([], list(root.glob("benchmark.*")))
            self.assertNotIn("Generated", out)

    def test_directory_without_evals_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_main(tmp)
            self.assertNotEqual(0, code)
            self.assertEqual([], list(Path(tmp).glob("benchmark.*")))
            self.assertIn("No eval directories", err)


class HonestGapTests(unittest.TestCase):
    def test_configuration_with_no_graded_run_is_null_and_has_no_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "eval-1" / "with_skill" / "run-1" / "grading.json", grading(3, 3))
            (root / "eval-1" / "without_skill" / "run-1").mkdir(parents=True)
            with contextlib.redirect_stderr(io.StringIO()):
                benchmark = agg.generate_benchmark(root)
        summary = benchmark["run_summary"]
        self.assertIsNone(summary["without_skill"])
        self.assertEqual({"pass_rate": None, "time_seconds": None, "tokens": None}, summary["delta"])
        self.assertIn("n/a", agg.generate_markdown(benchmark))

    def test_stray_names_are_ignored_instead_of_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "eval-1" / "with_skill" / "run-1" / "grading.json", grading(1, 2))
            (root / "eval-1" / "with_skill" / "run-final").mkdir()
            (root / "eval-1" / "with_skill" / "run-1.log").write_text("log", encoding="utf-8")
            (root / "eval-1" / "inputs").mkdir()
            write_json(root / "eval-notes.json", {"note": "not an eval"})
            write_json(root / "eval-2" / "eval_metadata.json", {"eval_id": "two"})
            write_json(root / "eval-2" / "with_skill" / "grading.json", grading(2, 2))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                benchmark = agg.generate_benchmark(root)
        self.assertEqual([1, 2], benchmark["metadata"]["evals_run"])
        self.assertIn("run-final", err.getvalue())

    def test_pass_rate_is_derived_from_the_counts_when_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "eval-1" / "with_skill" / "run-1" / "grading.json",
                       {"summary": {"passed": 1, "failed": 3, "total": 4}})
            benchmark = agg.generate_benchmark(root)
        self.assertEqual(0.25, benchmark["runs"][0]["result"]["pass_rate"])

    def test_a_run_with_nothing_gradable_is_skipped_not_scored_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "eval-1" / "with_skill" / "run-1" / "grading.json", {"summary": {}})
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual([], agg.generate_benchmark(root)["runs"])


class TokenAndTimingTests(unittest.TestCase):
    """timing.json is the only place total_tokens is captured (schemas.md), so it is always read.

    These use run-N directories, the one layout old and new code both load, so each
    test isolates the timing behaviour instead of failing on the layout.
    """

    def run_with(self, grading_extra, timing):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "eval-1" / "with_skill" / "run-1"
            write_json(run / "grading.json", grading(1, 1, **grading_extra))
            if timing is not None:
                write_json(run / "timing.json", timing)
            return agg.generate_benchmark(Path(tmp))["runs"][0]["result"]

    def test_tokens_come_from_timing_json_when_grading_already_carries_a_duration(self):
        result = self.run_with(
            {"timing": {"total_duration_seconds": 191.0}, "execution_metrics": {"output_chars": 99999}},
            {"total_tokens": 84852, "total_duration_seconds": 23.3},
        )
        self.assertEqual(84852, result["tokens"])
        self.assertEqual(191.0, result["time_seconds"])

    def test_duration_falls_back_to_timing_json(self):
        result = self.run_with({}, {"total_tokens": 10, "total_duration_seconds": 23.3})
        self.assertEqual(23.3, result["time_seconds"])

    def test_unrecorded_values_are_null_and_output_chars_is_not_passed_off_as_tokens(self):
        result = self.run_with({"execution_metrics": {"output_chars": 12450}}, None)
        self.assertIsNone(result["tokens"])
        self.assertIsNone(result["time_seconds"])

    def test_metrics_nobody_recorded_have_no_statistics_and_no_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            for config in ("with_skill", "without_skill"):
                write_json(Path(tmp) / "eval-1" / config / "run-1" / "grading.json", grading(1, 1))
            summary = agg.generate_benchmark(Path(tmp))["run_summary"]
        self.assertIsNone(summary["with_skill"]["tokens"])
        self.assertIsNone(summary["with_skill"]["time_seconds"])
        self.assertIsNone(summary["delta"]["tokens"])
        self.assertEqual("+0.00", summary["delta"]["pass_rate"])


if __name__ == "__main__":
    unittest.main()
