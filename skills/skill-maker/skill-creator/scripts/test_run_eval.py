"""Regression tests for run_eval: a failed run is not a measurement, and the project root is never home.

The claude CLI is never run. run_single_query is driven against a child Python process
standing in for it (the subprocess boundary the existing tests already stub), and run_eval
against an in-process executor.
"""
import concurrent.futures
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import run_eval as run_eval_module
from scripts.run_eval import run_eval, run_single_query


def emit(*events: dict) -> str:
    """A child-process body that prints these stream-json events and exits."""
    return "import json\n" + "".join(f"print(json.dumps({event!r}))\n" for event in events)


RESULT_OK = emit({"type": "result", "is_error": False, "result": "done"})
RESULT_ERROR = emit({"type": "result", "is_error": True, "result": "Invalid API key - please run /login"})
ANSWERED = emit({"type": "stream_event", "event": {"type": "message_stop"}})
OTHER_TOOL_FIRST = emit({"type": "stream_event", "event": {
    "type": "content_block_start", "content_block": {"type": "tool_use", "name": "Bash"}}})
NOTHING = "pass"
CRASH = "import sys; sys.exit(3)"
HANG = "import time; time.sleep(10)"


def query_outcome(body: str, timeout: float = 5):
    original = subprocess.Popen

    def launch(*args, **kwargs):
        return original([sys.executable, "-c", body], **kwargs)

    with tempfile.TemporaryDirectory() as root, patch("scripts.run_eval.subprocess.Popen", side_effect=launch), \
            contextlib.redirect_stderr(io.StringIO()):
        return run_single_query("query", "sample", "Description", timeout, root)


class OutcomeTests(unittest.TestCase):
    """False means the model was seen not to invoke the skill. Anything unobserved is None."""

    def test_a_model_that_answers_without_the_skill_did_not_trigger(self):
        for label, body in (("result", RESULT_OK), ("message stop", ANSWERED), ("another tool first", OTHER_TOOL_FIRST)):
            with self.subTest(label):
                self.assertIs(False, query_outcome(body))

    def test_a_timeout_is_not_a_miss(self):
        self.assertIsNone(query_outcome(HANG, timeout=0.2))

    def test_a_cli_that_exits_without_a_result_is_not_a_miss(self):
        self.assertIsNone(query_outcome(NOTHING))
        self.assertIsNone(query_outcome(CRASH))

    def test_an_error_result_is_not_a_miss_and_says_why(self):
        original = subprocess.Popen
        with tempfile.TemporaryDirectory() as root, \
                patch("scripts.run_eval.subprocess.Popen", side_effect=lambda *a, **k: original([sys.executable, "-c", RESULT_ERROR], **k)), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertIsNone(run_single_query("query", "sample", "Description", 5, root))
        self.assertIn("Invalid API key", err.getvalue())


class InlineExecutor:
    """Runs submitted calls in this process, so the run_single_query stub is the one that runs."""

    def __init__(self, max_workers=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def submit(self, fn, *args, **kwargs):
        future = concurrent.futures.Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


def evaluate(outcomes: dict, should_trigger: dict | None = None, runs_per_query: int = 3, threshold: float = 0.5) -> dict:
    """run_eval with run_single_query replaced by canned per-query outcomes (or exceptions)."""
    seen: dict[str, int] = {}

    def canned(query, *args):
        outcome = outcomes[query][seen.setdefault(query, 0)]
        seen[query] += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    eval_set = [{"query": q, "should_trigger": (should_trigger or {}).get(q, True)} for q in outcomes]
    with tempfile.TemporaryDirectory() as root, patch.object(run_eval_module, "ProcessPoolExecutor", InlineExecutor), \
            patch.object(run_eval_module, "run_single_query", canned), contextlib.redirect_stderr(io.StringIO()):
        return run_eval(eval_set, "sample", "desc", 1, 1, Path(root), runs_per_query=runs_per_query, trigger_threshold=threshold)


class AccountingTests(unittest.TestCase):
    def only(self, report: dict) -> dict:
        self.assertEqual(1, len(report["results"]))
        return report["results"][0]

    def test_a_query_that_could_not_be_run_is_unmeasured_not_failed(self):
        report = evaluate({"q": [None, None, None]})
        result = self.only(report)
        self.assertIsNone(result["pass"])
        self.assertIsNone(result["trigger_rate"])
        self.assertEqual((0, 0, 3), (result["triggers"], result["runs"], result["errors"]))
        self.assertEqual({"total": 1, "passed": 0, "failed": 0, "unmeasured": 1, "errors": 3}, report["summary"])

    def test_a_should_not_trigger_query_does_not_pass_on_timeouts(self):
        # The old harness scored a timeout as "did not trigger", which is a pass here.
        result = self.only(evaluate({"q": [None, None, None]}, should_trigger={"q": False}))
        self.assertIsNone(result["pass"])

    def test_the_rate_is_taken_over_the_runs_that_completed(self):
        result = self.only(evaluate({"q": [True, None, RuntimeError("worker died")]}))
        self.assertEqual((1.0, 1, 1, 2, True), (result["trigger_rate"], result["triggers"], result["runs"], result["errors"], result["pass"]))

    def test_an_exception_in_a_worker_is_an_error_not_a_miss(self):
        result = self.only(evaluate({"q": [RuntimeError("boom"), False, False]}, should_trigger={"q": False}))
        self.assertEqual((0.0, 2, 1, True), (result["trigger_rate"], result["runs"], result["errors"], result["pass"]))

    def test_a_clean_run_has_no_errors_and_keeps_its_shape(self):
        report = evaluate({"yes": [True, True, False], "no": [False, False, False]}, should_trigger={"no": False})
        self.assertEqual({"total": 2, "passed": 2, "failed": 0, "unmeasured": 0, "errors": 0}, report["summary"])
        by_query = {r["query"]: r for r in report["results"]}
        self.assertEqual((2, 3, 0), (by_query["yes"]["triggers"], by_query["yes"]["runs"], by_query["yes"]["errors"]))


class MainTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.skill = self.root / "sample"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text("---\nname: sample\ndescription: Does a thing\n---\n", encoding="utf-8")
        self.eval_set = self.root / "evals.json"
        self.eval_set.write_text(json.dumps([{"query": "q", "should_trigger": True}]), encoding="utf-8")

    def run_main(self, summary_errors: int, *extra: str, finder: dict | None = None):
        """main() with run_eval stubbed; the project-root finder is stubbed too unless finder is {}."""
        report = {"skill_name": "sample", "description": "Does a thing", "results": [],
                  "summary": {"total": 1, "passed": 1, "failed": 0, "unmeasured": 0, "errors": summary_errors}}
        argv = ["run_eval", "--eval-set", str(self.eval_set), "--skill-path", str(self.skill), *extra]
        out, err, code = io.StringIO(), io.StringIO(), 0
        finder = {"return_value": self.root} if finder is None else finder
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", argv))
            run_stub = stack.enter_context(patch.object(run_eval_module, "run_eval", return_value=report))
            if finder:
                stack.enter_context(patch.object(run_eval_module, "find_project_root", **finder))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            try:
                run_eval_module.main()
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue(), run_stub

    def test_exit_status_is_zero_when_every_run_completed(self):
        code, out, _, _ = self.run_main(0)
        self.assertEqual(0, code)
        self.assertEqual("sample", json.loads(out)["skill_name"])

    def test_exit_status_is_nonzero_when_a_run_produced_no_outcome_but_the_json_is_still_printed(self):
        code, out, err, _ = self.run_main(2)
        self.assertEqual(1, code)
        self.assertIn("errors", json.loads(out)["summary"])
        self.assertIn("2 run(s) produced no outcome", err)

    def test_without_a_project_root_nothing_runs_and_nothing_is_written(self):
        from scripts.utils import ProjectRootError
        code, out, err, stub = self.run_main(0, finder={"side_effect": ProjectRootError("no project root found")})
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("--project-root", err)
        stub.assert_not_called()
        self.assertFalse((self.root / ".claude").exists())

    def test_the_project_root_option_reaches_the_evaluation(self):
        code, _, _, stub = self.run_main(0, "--project-root", str(self.root), finder={})
        self.assertEqual(0, code)
        self.assertEqual(self.root.resolve(), Path(stub.call_args.kwargs["project_root"]))


class HomeFallThroughTests(unittest.TestCase):
    """The finder run_eval exposes must not return the home directory.

    Every user's home holds a .claude/, so walking up from any directory below it
    used to stop there, and run_eval then wrote ~/.claude/commands and ran claude in ~.
    """

    def test_walking_up_from_below_home_does_not_end_in_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve() / "home"
            (home / ".claude").mkdir(parents=True)
            work = home / "work" / "tools"
            work.mkdir(parents=True)
            previous = os.getcwd()
            os.chdir(work)
            try:
                with patch.object(Path, "home", return_value=home):
                    try:
                        found = run_eval_module.find_project_root()
                    except Exception as raised:  # ProjectRootError in this version
                        self.assertEqual("ProjectRootError", type(raised).__name__)
                    else:
                        self.fail(f"returned {found} instead of refusing")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
