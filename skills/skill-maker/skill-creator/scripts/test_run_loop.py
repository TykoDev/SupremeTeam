"""Regression tests for run_loop: degenerate arguments, the train/test split and failed evaluations.

run_eval and improve_description are stubbed, so no claude process is started.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_loop
from scripts.generate_report import generate_html

ORIGINAL = "Original description."


def positives(n):
    return [{"query": f"yes {i}", "should_trigger": True} for i in range(n)]


def negatives(n):
    return [{"query": f"no {i}", "should_trigger": False} for i in range(n)]


class ScriptedEval:
    """Stands in for run_eval: each call returns the next round, mapping query -> 'pass' | 'fail' | 'none' | 'partial'."""

    def __init__(self, *rounds):
        self.rounds = list(rounds)
        self.calls = 0

    def __call__(self, eval_set, **kwargs):
        states = self.rounds[min(self.calls, len(self.rounds) - 1)]
        self.calls += 1
        results = []
        for item in eval_set:
            state = states.get(item["query"], "pass")
            passed = {"pass": True, "partial": True, "fail": False, "none": None}[state]
            runs = {"none": 0, "partial": 2}.get(state, 3)
            results.append({"query": item["query"], "should_trigger": item["should_trigger"],
                            "trigger_rate": None if passed is None else float(bool(passed) == item["should_trigger"]),
                            "triggers": runs if bool(passed) == item["should_trigger"] and runs else 0,
                            "runs": runs, "errors": 3 - runs, "pass": passed})
        unmeasured = sum(1 for r in results if r["pass"] is None)
        passed_count = sum(1 for r in results if r["pass"])
        return {"skill_name": "sample", "description": kwargs["description"], "results": results,
                "summary": {"total": len(results), "passed": passed_count,
                            "failed": len(results) - passed_count - unmeasured, "unmeasured": unmeasured,
                            "errors": sum(r["errors"] for r in results)}}


class LoopCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.skill = self.root / "sample"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text(f"---\nname: sample\ndescription: {ORIGINAL}\n---\nbody\n", encoding="utf-8")

    def loop(self, evaluation, eval_set=None, improver=None, **overrides):
        settings = dict(eval_set=eval_set if eval_set is not None else positives(1) + negatives(1), skill_path=self.skill,
                        description_override=None, num_workers=1, timeout=1, max_iterations=3, runs_per_query=3,
                        trigger_threshold=0.5, holdout=0, model="m", verbose=False)
        settings.update(overrides)
        improver = improver or patch.object(run_loop, "improve_description", return_value="A new description.")
        with patch.object(run_loop, "run_eval", evaluation), patch.object(run_loop, "find_project_root", return_value=self.root), \
                improver as improve_stub:
            return run_loop.run_loop(**settings), improve_stub

    def cli(self, *extra, evaluation=None):
        """main() over a stubbed evaluation: (exit code, stdout, stderr, the evaluation stub)."""
        (self.root / "evals.json").write_text(json.dumps(positives(2) + negatives(2)), encoding="utf-8")
        argv = ["run_loop", "--eval-set", str(self.root / "evals.json"), "--skill-path", str(self.skill),
                "--model", "m", "--report", "none", *extra]
        out, err, code = io.StringIO(), io.StringIO(), 0
        evaluation = evaluation or ScriptedEval({})
        with patch.object(sys, "argv", argv), patch.object(run_loop, "run_eval", evaluation), \
                patch.object(run_loop, "find_project_root", return_value=self.root), \
                patch.object(run_loop, "improve_description", return_value="new"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                run_loop.main()
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue(), evaluation


class SplitTests(unittest.TestCase):
    def test_a_lone_positive_query_stays_in_train(self):
        train, test = run_loop.split_eval_set(positives(1) + negatives(5), 0.4)
        self.assertEqual(1, sum(e["should_trigger"] for e in train))
        self.assertEqual(0, sum(e["should_trigger"] for e in test))

    def test_each_class_keeps_a_query_in_train_however_large_the_holdout(self):
        for holdout in (0.4, 0.9, 0.99):
            with self.subTest(holdout=holdout):
                train, test = run_loop.split_eval_set(positives(4) + negatives(3), holdout)
                self.assertGreaterEqual(sum(e["should_trigger"] for e in train), 1)
                self.assertGreaterEqual(sum(not e["should_trigger"] for e in train), 1)
                self.assertEqual(7, len(train) + len(test))

    def test_an_ordinary_split_still_holds_one_of_each_class_out(self):
        train, test = run_loop.split_eval_set(positives(5) + negatives(5), 0.4)
        self.assertEqual((2, 2), (sum(e["should_trigger"] for e in test), sum(not e["should_trigger"] for e in test)))
        self.assertEqual(6, len(train))

    def test_a_missing_class_is_not_an_error(self):
        train, test = run_loop.split_eval_set(negatives(3), 0.4)
        self.assertEqual(3, len(train) + len(test))


class ArgumentTests(LoopCase):
    def test_zero_iterations_is_refused_before_anything_runs(self):
        evaluation = ScriptedEval({})
        with self.assertRaisesRegex(ValueError, "max_iterations"):
            self.loop(evaluation, max_iterations=0)
        self.assertEqual(0, evaluation.calls)

    def test_a_holdout_that_empties_train_or_is_negative_is_refused(self):
        for holdout in (1.0, 1.5, -0.1, float("nan")):
            with self.subTest(holdout=holdout), self.assertRaisesRegex(ValueError, "holdout"):
                self.loop(ScriptedEval({}), holdout=holdout)

    def test_the_command_line_reports_bad_values_as_usage_errors(self):
        for flag, value in (("--max-iterations", "0"), ("--holdout", "1"), ("--holdout", "-0.5")):
            with self.subTest(flag=flag, value=value):
                code, out, err, evaluation = self.cli(flag, value)
                self.assertEqual(2, code)
                self.assertEqual("", out)
                self.assertIn("usage:", err)
                self.assertEqual(0, evaluation.calls)


class FailedEvaluationTests(LoopCase):
    def test_a_query_with_no_completed_run_ends_the_loop_with_an_error_and_no_improvement(self):
        result, improver = self.loop(ScriptedEval({"yes 0": "none"}))
        self.assertIn("iteration 1", result["error"])
        self.assertIn("no completed run", result["error"])
        self.assertEqual("eval_failed (iteration 1)", result["exit_reason"])
        self.assertEqual(0, result["iterations_run"])
        self.assertEqual(ORIGINAL, result["best_description"])
        self.assertIsNone(result["best_score"])
        improver.assert_not_called()

    def test_runs_that_partly_failed_do_not_stop_the_loop(self):
        result, _ = self.loop(ScriptedEval({"yes 0": "partial"}))
        self.assertIsNone(result["error"])
        self.assertEqual("all_passed (iteration 1)", result["exit_reason"])

    def test_an_improver_that_gives_up_keeps_the_measured_history(self):
        from scripts.improve_description import DescriptionError
        failing = patch.object(run_loop, "improve_description", side_effect=DescriptionError("no usable description"))
        result, _ = self.loop(ScriptedEval({"yes 0": "fail"}), improver=failing)
        self.assertIn("could not propose a new description", result["error"])
        self.assertEqual("improve_failed (iteration 1)", result["exit_reason"])
        self.assertEqual(1, result["iterations_run"])
        self.assertEqual(ORIGINAL, result["best_description"])
        self.assertEqual("1/2", result["best_score"])

    def test_a_clean_run_reports_no_error(self):
        result, _ = self.loop(ScriptedEval({"yes 0": "fail"}, {}))
        self.assertIsNone(result["error"])
        self.assertEqual("all_passed (iteration 2)", result["exit_reason"])
        self.assertEqual("A new description.", result["best_description"])

    def test_the_command_line_prints_what_was_measured_and_exits_nonzero(self):
        code, out, err, _ = self.cli(evaluation=ScriptedEval({"yes 0": "none"}))
        self.assertEqual(1, code)
        self.assertEqual("eval_failed (iteration 1)", json.loads(out)["exit_reason"])
        self.assertIn("no completed run", err)


class ReportTests(LoopCase):
    def test_the_live_report_is_written_when_the_holdout_is_disabled(self):
        # --holdout 0 leaves every history entry with test_results null; the report used to raise on it.
        report = self.root / "live.html"
        result, _ = self.loop(ScriptedEval({"yes 0": "fail"}, {}), live_report_path=report)
        self.assertIsNone(result["error"])
        self.assertIn("all_passed", result["exit_reason"])
        self.assertIn("Skill Description Optimization", report.read_text(encoding="utf-8"))


class EmptyHistoryReportTests(unittest.TestCase):
    def test_a_report_for_a_loop_that_measured_nothing_is_an_empty_page(self):
        for data in ({"history": []}, {}, {"history": [], "best_score": None, "holdout": 0.4}):
            with self.subTest(data=data):
                page = generate_html(data, skill_name="sample")
                self.assertIn("<table>", page)
                self.assertIn("N/A", page)


if __name__ == "__main__":
    unittest.main()
