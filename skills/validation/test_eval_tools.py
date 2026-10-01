"""Regression tests for run_eval.py and trigger_eval.py: a failed session is not a measurement.

These two scripts run the claude CLI and cost money, so nothing here does: subprocess.run is
stubbed at the boundary, and the catalog trigger_eval reads is a temporary one. The scripts
are loaded by path, under their own names, so they cannot collide with the copy in
skill-maker/skill-creator/scripts.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HAVE_YAML = importlib.util.find_spec("yaml") is not None


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_eval = load("validation_run_eval_under_test", "run_eval.py")
trigger_eval = load("validation_trigger_eval_under_test", "trigger_eval.py") if HAVE_YAML else None


def completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["claude"], returncode, stdout=stdout, stderr=stderr)


def init_event(*skills: str) -> str:
    return json.dumps({"type": "system", "subtype": "init", "skills": list(skills)}) + "\n" + json.dumps({"type": "result"}) + "\n"


def call_main(module, *argv: str, run=None, extra_patches=()):
    """module.main() with subprocess.run stubbed; returns (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(sys, "argv", [module.__name__, *argv]))
        stack.enter_context(patch.object(module.subprocess, "run", **run))
        for extra in extra_patches:
            stack.enter_context(extra)
        stack.enter_context(contextlib.redirect_stdout(out))
        stack.enter_context(contextlib.redirect_stderr(err))
        try:
            code = module.main()
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


class RegistrationTests(unittest.TestCase):
    """Two sessions, one without the catalog and one with; only the difference is the catalog's."""

    def main(self, *argv, **run):
        # install_catalog would copy the whole catalog into a temp directory; the count is all main() reads.
        return call_main(run_eval, *argv, run=run, extra_patches=[patch.object(run_eval, "install_catalog", return_value=5)])

    def test_two_completed_sessions_report_what_the_catalog_adds(self):
        replies = [completed(init_event("code-review", "simplify")), completed(init_event("code-review", "simplify", "admiral", "browse"))]
        code, out, _ = self.main("--registration", side_effect=replies)
        self.assertEqual(0, code)
        self.assertIn("attributable to this catalog: 2", out)

    def test_a_session_that_exits_nonzero_is_not_reported_as_zero_registered_skills(self):
        code, out, err = self.main("--registration", return_value=completed("", returncode=1, stderr="Invalid API key"))
        self.assertEqual(1, code)
        self.assertNotIn("not registered at all", out)
        self.assertIn("nothing was measured", err)
        self.assertIn("Invalid API key", err)

    def test_a_session_that_emits_no_init_event_is_not_reported_as_zero_registered_skills(self):
        code, out, err = self.main("--registration", return_value=completed(json.dumps({"type": "result"}) + "\n"))
        self.assertEqual(1, code)
        self.assertNotIn("not registered at all", out)
        self.assertIn("no system init event", err)

    def test_a_missing_cli_and_a_timeout_are_reported_not_raised(self):
        for label, failure in (("missing", FileNotFoundError("claude")), ("timeout", subprocess.TimeoutExpired("claude", 5))):
            with self.subTest(label):
                code, _, err = self.main("--registration", side_effect=failure)
                self.assertEqual(1, code)
                self.assertIn("nothing was measured", err)

    def test_a_host_that_registers_no_skills_is_a_measurement(self):
        # An init event with an empty list is an answer; only its absence is not.
        replies = [completed(init_event()), completed(init_event())]
        code, out, _ = self.main("--registration", side_effect=replies)
        self.assertEqual(0, code)
        self.assertIn("host alone registers: 0", out)

    def test_a_failed_run_writes_no_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "report.json"
            code, _, _ = self.main("--out", str(target), return_value=completed("", returncode=2))
            self.assertEqual(1, code)
            self.assertFalse(target.exists())


class SurfaceTests(unittest.TestCase):
    """The docstring and the flags may not promise runs the tool does not make."""

    def test_the_flags_that_did_nothing_are_gone_and_registration_still_works(self):
        for flag in (["--queries", "12"], ["--turns", "3"]):
            with self.subTest(flag), contextlib.redirect_stderr(io.StringIO()):
                code, _, _ = call_main(run_eval, *flag, run={"return_value": completed(init_event())})
                self.assertEqual(2, code, f"{flag[0]} should be an unknown argument")
        code, _, _ = call_main(run_eval, "--registration", run={"side_effect": [completed(init_event("a")), completed(init_event("a"))]},
                               extra_patches=[patch.object(run_eval, "install_catalog", return_value=1)])
        self.assertEqual(0, code)

    def test_the_docstring_promises_no_routing_run(self):
        self.assertNotIn("--queries", run_eval.__doc__)
        self.assertNotIn("routing runs", run_eval.__doc__)
        self.assertIn("Registration is the only thing measured", run_eval.__doc__)

    def test_helpers_nothing_called_are_gone(self):
        self.assertFalse(hasattr(run_eval, "invoked_skill"))
        self.assertFalse(hasattr(run_eval, "cost_of"))


CATALOG_SKILL = """---
name: alpha
description: Does alpha things. Use when the user wants alpha.
---

## Use This Skill When

- "run the alpha thing"
- "do the alpha for me"

## Next
"""


@unittest.skipUnless(HAVE_YAML, "trigger_eval.py requires PyYAML")
class TriggerEvalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.catalog = Path(tmp.name)
        (self.catalog / "alpha").mkdir()
        (self.catalog / "alpha" / "SKILL.md").write_text(CATALOG_SKILL, encoding="utf-8")
        self.report = self.catalog / "report.json"

    def run_main(self, replies, *argv):
        """main() over the temporary catalog; replies are what each claude call returns (or raises)."""
        call = patch.object(trigger_eval, "_claude", side_effect=replies)
        code, out, err = call_main(trigger_eval, "--out", str(self.report), *argv, run={"return_value": completed()},
                                   extra_patches=[patch.object(trigger_eval, "SKILLS", self.catalog), call])
        return code, out, err, json.loads(self.report.read_text(encoding="utf-8")) if self.report.exists() else None

    @staticmethod
    def answers(*skills):
        return "\n".join(f"{i}. {skill}" for i, skill in enumerate(skills, 1)), 0.01

    def test_a_clean_run_scores_every_query_and_exits_zero(self):
        code, out, _, report = self.run_main([self.answers("alpha", "alpha")])
        self.assertEqual(0, code)
        self.assertEqual((1.0, 2, 0, 0), (report["accuracy"], report["scored"], report["unscored"], report["failed_batches"]))
        self.assertIn("accuracy 2/2 = 100.0%", out)

    def test_when_every_batch_fails_accuracy_is_undefined_not_zero(self):
        code, out, err, report = self.run_main([RuntimeError("claude exited 1: Invalid API key")] * 4)
        self.assertEqual(1, code)
        self.assertIsNone(report["accuracy"])
        self.assertEqual((0, 2, 1), (report["scored"], report["unscored"], report["failed_batches"]))
        self.assertNotIn("accuracy 0/0", out)
        self.assertIn("accuracy is undefined", out)
        self.assertIn("1 of 1 batches failed", err)

    def test_a_failed_batch_leaves_its_queries_unscored_and_the_rest_counted(self):
        code, out, err, report = self.run_main([RuntimeError("timed out"), self.answers("alpha")], "--batch", "1")
        self.assertEqual(1, code)
        self.assertEqual((1.0, 1, 1, 1, 2), (report["accuracy"], report["scored"], report["unscored"], report["failed_batches"], report["batches"]))
        self.assertIn("accuracy 1/1 = 100.0%", out)
        self.assertIn("1 of 2 batches failed", err)
        self.assertEqual(1, sum("error" in r for r in report["results"]))

    def test_a_misroute_is_still_a_measurement(self):
        code, _, _, report = self.run_main([self.answers("beta", "alpha")])
        self.assertEqual(0, code)
        self.assertEqual((0.5, 2), (report["accuracy"], report["scored"]))

    def test_an_error_payload_is_not_read_as_routing_answers(self):
        payload = json.dumps({"type": "result", "is_error": True, "result": "Invalid API key - please run /login"})
        with patch.object(trigger_eval.subprocess, "run", return_value=completed(payload)):
            with self.assertRaisesRegex(RuntimeError, "Invalid API key"):
                trigger_eval._claude("prompt", None, 5)

    def test_a_skill_whose_frontmatter_is_not_valid_yaml_stops_the_run_before_any_call(self):
        broken = self.catalog / "broken"
        broken.mkdir()
        (broken / "SKILL.md").write_text("---\nname: broken\ndescription: Use when: it is unquoted\n---\n", encoding="utf-8")
        code, out, err, report = self.run_main(AssertionError("no model call may be made"))
        self.assertEqual(1, code)
        self.assertIn("broken", err)
        self.assertIn("not valid YAML", err)
        self.assertIsNone(report)

    def test_frontmatter_without_yaml_errors_still_reads_as_before(self):
        self.assertEqual({}, trigger_eval.frontmatter("no frontmatter here"))
        self.assertEqual({"name": "x"}, trigger_eval.frontmatter("---\nname: x\n---\nbody"))
        with self.assertRaises(ValueError):
            trigger_eval.frontmatter("---\ndescription: Use when: X\n---\nbody")


if __name__ == "__main__":
    unittest.main()
