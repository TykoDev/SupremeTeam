"""Regression tests for improve_description: an unusable reply is retried, then an error - never adopted.

The claude CLI is never run: _call_claude is stubbed, and the subprocess call inside it is patched.
"""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import improve_description as imp

GOOD = "Fixes flaky tests. Use when CI is red and nobody knows why."
RESULTS = {
    "results": [
        {"query": "ci is red again", "should_trigger": True, "pass": False, "triggers": 0, "runs": 3},
        {"query": "no run completed", "should_trigger": True, "pass": None, "triggers": 0, "runs": 0},
    ],
    "summary": {"passed": 0, "failed": 1, "total": 2},
}


def tagged(text: str) -> str:
    return f"<new_description>{text}</new_description>"


def improve(replies, log_dir=None):
    with patch.object(imp, "_call_claude", side_effect=replies) as stub:
        try:
            outcome = imp.improve_description("sample", "body", "old description", RESULTS, [], "model",
                                              log_dir=log_dir, iteration=2)
        except imp.DescriptionError as exc:
            outcome = exc
    return outcome, stub


class ReplyValidationTests(unittest.TestCase):
    def test_a_usable_first_reply_costs_one_call(self):
        outcome, stub = improve([tagged(f'"{GOOD}"')])
        self.assertEqual(GOOD, outcome)
        self.assertEqual(1, stub.call_count)

    def test_a_reply_without_the_tags_is_retried_not_adopted(self):
        outcome, stub = improve(["I'm sorry, I can't help with that.", tagged(GOOD)])
        self.assertEqual(GOOD, outcome)
        self.assertEqual(2, stub.call_count)
        self.assertIn("no non-empty <new_description> block", stub.call_args_list[1].args[0])

    def test_empty_tags_are_not_a_description(self):
        outcome, _ = improve([tagged('  ""  '), tagged(GOOD)])
        self.assertEqual(GOOD, outcome)

    def test_a_rewrite_that_is_still_too_long_is_rewritten_again(self):
        outcome, stub = improve([tagged("a" * 1200), tagged("b" * 1100), tagged("c" * 900)])
        self.assertEqual("c" * 900, outcome)
        self.assertEqual(3, stub.call_count)
        self.assertIn("1200 characters", stub.call_args_list[1].args[0])
        self.assertIn("1100 characters", stub.call_args_list[2].args[0])

    def test_a_description_that_never_becomes_usable_is_an_error_after_the_bound(self):
        for replies, reason in (
            (["no tags here"] * 4, "no non-empty <new_description> block"),
            ([tagged("x" * 1300)] * 4, "over the 1024 limit"),
        ):
            with self.subTest(reason):
                outcome, stub = improve(replies)
                self.assertIsInstance(outcome, imp.DescriptionError)
                self.assertIn(reason, str(outcome))
                self.assertEqual(1 + imp.MAX_REWRITES, stub.call_count)

    def test_the_transcript_is_logged_even_when_the_improver_gives_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome, _ = improve(["no tags"] * 4, log_dir=Path(tmp) / "logs")
            self.assertIsInstance(outcome, imp.DescriptionError)
            transcript = json.loads((Path(tmp) / "logs" / "improve_iter_2.json").read_text(encoding="utf-8"))
        self.assertEqual(imp.MAX_REWRITES, len(transcript["rewrites"]))
        self.assertIsNone(transcript["final_description"])

    def test_a_query_with_no_completed_run_is_not_offered_as_a_failure_to_fix(self):
        _, stub = improve([tagged(GOOD)])
        prompt = stub.call_args_list[0].args[0]
        self.assertIn("ci is red again", prompt)
        self.assertNotIn("no run completed", prompt)


class CallClaudeTests(unittest.TestCase):
    def call(self, **behaviour):
        with patch.object(imp.subprocess, "run", **behaviour) as run:
            try:
                return imp._call_claude("prompt — with a dash", "model"), run
            except RuntimeError as exc:
                return exc, run

    def test_prompt_and_reply_are_utf8_on_every_platform(self):
        text, run = self.call(return_value=MagicMock(returncode=0, stdout="reply", stderr=""))
        self.assertEqual("reply", text)
        self.assertEqual("utf-8", run.call_args.kwargs["encoding"])
        self.assertEqual("replace", run.call_args.kwargs["errors"])

    def test_a_timeout_and_a_missing_cli_are_reported_as_errors(self):
        outcome, _ = self.call(side_effect=subprocess.TimeoutExpired("claude", 300))
        self.assertIsInstance(outcome, RuntimeError)
        self.assertIn("timed out", str(outcome))
        outcome, _ = self.call(side_effect=FileNotFoundError("claude"))
        self.assertIsInstance(outcome, RuntimeError)
        self.assertIn("not found on PATH", str(outcome))

    def test_a_nonzero_exit_is_an_error_with_its_stderr(self):
        outcome, _ = self.call(return_value=MagicMock(returncode=2, stdout="", stderr="Invalid API key"))
        self.assertIsInstance(outcome, RuntimeError)
        self.assertIn("Invalid API key", str(outcome))


class MainTests(unittest.TestCase):
    def test_an_unusable_reply_is_an_error_message_and_a_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_text("---\nname: sample\ndescription: old\n---\n", encoding="utf-8")
            (root / "results.json").write_text(json.dumps({**RESULTS, "description": "old"}), encoding="utf-8")
            argv = ["improve_description", "--eval-results", str(root / "results.json"),
                    "--skill-path", str(root), "--model", "m"]
            err, code = io.StringIO(), 0
            with patch.object(sys, "argv", argv), patch.object(imp, "_call_claude", return_value="no tags"), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                try:
                    imp.main()
                except SystemExit as exit_:
                    code = exit_.code
        self.assertEqual(1, code)
        self.assertIn("no usable description", err.getvalue())


if __name__ == "__main__":
    unittest.main()
