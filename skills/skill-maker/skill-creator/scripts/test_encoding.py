"""Regression tests for Windows code pages: UTF-8 stated everywhere, and no text a pipe cannot encode.

On Windows Python defaults text files to cp1252 and a piped stdout to the same, so a script
that leaves either to the locale works on a developer's Linux box and fails in an agent's
tool call. Neither can be observed here directly, so each is provoked:

* implicit_encodings() records every text-mode open made from a skill-creator script that
  leaves the encoding to the locale (Path.read_text/write_text reach io.text_encoding
  with None exactly when the caller omitted it);
* windows_pipe() is a stdout that, like a cp1252 pipe, raises on what it cannot encode.
"""
import builtins
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile
import traceback
import unittest
from unittest.mock import patch

CREATOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CREATOR))
from scripts import aggregate_benchmark, generate_report, improve_description, package_skill, run_eval, run_loop  # noqa: E402
from scripts.utils import parse_skill_md  # noqa: E402

_spec = importlib.util.spec_from_file_location("generate_review_encoding_test", CREATOR / "eval-viewer" / "generate_review.py")
generate_review = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_review)

CJK = "日本語"  # not encodable in cp1252
SKILL_MD = "---\nname: sample\ndescription: Does a thing\n---\nSmart “quotes” and a dash — in the body\n"


@contextlib.contextmanager
def implicit_encodings():
    """Yield a list that collects 'file:line' for each locale-dependent text open made from the scripts."""
    found: list[str] = []
    real_text_encoding, real_open = io.text_encoding, builtins.open

    def from_scripts() -> list[str]:
        # Real files only: a synthetic name such as <frozen runpy> resolves under the working directory.
        frames = [f for f in traceback.extract_stack() if Path(f.filename).is_absolute()]
        return [f"{Path(f.filename).name}:{f.lineno}" for f in frames
                if CREATOR in Path(f.filename).resolve().parents and not Path(f.filename).name.startswith("test_")]

    def text_encoding(encoding, stacklevel=2):
        if encoding is None:
            found.extend(from_scripts())
        return real_text_encoding(encoding, stacklevel + 1)

    def spy_open(file, mode="r", buffering=-1, encoding=None, *args, **kwargs):
        if "b" not in mode and encoding is None:
            found.extend(from_scripts())
        return real_open(file, mode, buffering, encoding, *args, **kwargs)

    with patch.object(io, "text_encoding", text_encoding), patch("builtins.open", spy_open):
        yield found


class _KeptBuffer(io.BytesIO):
    """A buffer that survives its text wrapper being discarded, so the bytes can be read afterwards."""

    def close(self):
        pass


@contextlib.contextmanager
def windows_pipe():
    """Yield the raw bytes written to a cp1252 stdout that raises on anything it cannot encode."""
    raw = _KeptBuffer()
    pipe = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", write_through=True)
    with patch.object(sys, "stdout", pipe), patch.object(sys, "stderr", io.StringIO()):
        yield raw


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.skill = self.root / "sample"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")

    def run_script(self, main, *argv):
        """A script's main() as a command line; its exit code (None when it just returns)."""
        with patch.object(sys, "argv", ["script", *map(str, argv)]):
            try:
                main()
            except SystemExit as exit_:
                return exit_.code
        return None

    def benchmark_dir(self) -> Path:
        directory = self.root / "bench"
        for config in ("with_skill", CJK):
            write_json(directory / "eval-1" / config / "run-1" / "grading.json",
                       {"summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
                        "expectations": [{"text": CJK, "passed": True, "evidence": CJK}]})
            write_json(directory / "eval-1" / config / "run-1" / "timing.json", {"total_tokens": 5, "total_duration_seconds": 2})
        return directory


class ExplicitEncodingTests(Fixture):
    def test_parse_skill_md_states_utf8(self):
        with implicit_encodings() as found:
            name, _, content = parse_skill_md(self.skill)
        self.assertEqual("sample", name)
        self.assertIn("“quotes”", content)
        self.assertEqual([], found)

    def test_aggregate_benchmark_reads_and_writes_utf8(self):
        with implicit_encodings() as found, contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(self.run_script(aggregate_benchmark.main, self.benchmark_dir()))
        self.assertEqual([], found)

    def test_generate_report_reads_and_writes_utf8(self):
        results = self.root / "results.json"
        write_json(results, {"history": [{"iteration": 1, "description": CJK, "train_passed": 1, "train_total": 1,
                                          "train_results": [{"query": CJK, "should_trigger": True, "pass": True, "triggers": 1, "runs": 1}]}]})
        with implicit_encodings() as found, windows_pipe():
            self.assertIsNone(self.run_script(generate_report.main, results, "-o", self.root / "report.html"))
        self.assertEqual([], found)
        self.assertIn("✓", (self.root / "report.html").read_text(encoding="utf-8"))

    def test_the_viewer_reads_and_writes_utf8(self):
        run = self.root / "ws" / "eval-1" / "with_skill"
        (run / "outputs").mkdir(parents=True)
        (run / "outputs" / "n.md").write_text(CJK, encoding="utf-8")
        write_json(run / "grading.json", {"expectations": []})
        with implicit_encodings() as found, windows_pipe():
            code = self.run_script(generate_review.main, self.root / "ws", "--static", self.root / "v.html")
        self.assertEqual(0, code)
        self.assertEqual([], found)

    def test_packaging_states_utf8(self):
        with implicit_encodings() as found, windows_pipe():
            self.assertEqual(0, self.run_script(package_skill.main, self.skill, self.root / "out"))
        self.assertEqual([], found)

    def test_run_eval_reads_its_inputs_as_utf8(self):
        evals = self.root / "evals.json"
        write_json(evals, [{"query": CJK, "should_trigger": True}])
        report = {"skill_name": "sample", "description": "d", "results": [],
                  "summary": {"total": 0, "passed": 0, "failed": 0, "unmeasured": 0, "errors": 0}}
        with implicit_encodings() as found, patch.object(run_eval, "run_eval", return_value=report), \
                patch.object(run_eval, "find_project_root", return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(self.run_script(run_eval.main, "--eval-set", evals, "--skill-path", self.skill))
        self.assertEqual([], found)

    def test_run_loop_writes_its_reports_and_results_as_utf8(self):
        evals = self.root / "evals.json"
        write_json(evals, [{"query": f"{CJK} {i}", "should_trigger": bool(i % 2)} for i in range(6)])
        rounds = iter([False, True])

        def evaluate(eval_set, **kwargs):
            passed = next(rounds)
            results = [{"query": e["query"], "should_trigger": e["should_trigger"], "trigger_rate": 1.0, "triggers": 1,
                        "runs": 1, "errors": 0, "pass": passed} for e in eval_set]
            return {"results": results, "summary": {}}

        with implicit_encodings() as found, patch.object(run_loop, "run_eval", evaluate), \
                patch.object(run_loop, "find_project_root", return_value=self.root), \
                patch.object(run_loop, "improve_description", return_value=CJK), patch.object(run_loop.webbrowser, "open"), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = self.run_script(run_loop.main, "--eval-set", evals, "--skill-path", self.skill, "--model", "m",
                                   "--report", self.root / "live.html", "--results-dir", self.root / "res")
        self.assertIsNone(code)
        self.assertEqual([], found)
        self.assertIn(CJK, (self.root / "live.html").read_bytes().decode("utf-8"))
        saved = next((self.root / "res").iterdir())
        self.assertTrue((saved / "results.json").is_file())
        self.assertIn(CJK, (saved / "report.html").read_bytes().decode("utf-8"))

    def test_the_improver_logs_and_reads_utf8(self):
        with implicit_encodings() as found, patch.object(improve_description, "_call_claude", return_value=f"<new_description>{CJK}</new_description>"):
            improve_description.improve_description("sample", "body", "old", {"results": [], "summary": {"passed": 0, "total": 0}},
                                                    [], "m", log_dir=self.root / "logs", iteration=1)
        self.assertEqual([], found)
        self.assertTrue((self.root / "logs" / "improve_iter_1.json").is_file())


class WindowsPipeTests(Fixture):
    """Nothing the scripts print themselves, and nothing they quote from the user, may raise on a cp1252 pipe."""

    def test_the_packager_prints_only_text_a_pipe_can_encode(self):
        with windows_pipe() as raw:
            result = package_skill.package_skill(self.skill, self.root / "out")
        self.assertIsNotNone(result)
        raw.getvalue().decode("cp1252")

    def test_the_packagers_failure_lines_are_encodable_too(self):
        with windows_pipe() as raw:
            self.assertIsNone(package_skill.package_skill(self.root / "missing", self.root / "out"))
            (self.skill / "SKILL.md").write_text("no frontmatter", encoding="utf-8")
            self.assertIsNone(package_skill.package_skill(self.skill, self.root / "out"))
            (self.skill / ".env").write_text("SECRET", encoding="utf-8")
            (self.skill / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
            self.assertIsNone(package_skill.package_skill(self.skill, self.root / "out"))
        raw.getvalue().decode("cp1252")

    def test_the_packager_survives_a_file_name_the_pipe_cannot_encode(self):
        (self.skill / "references").mkdir()
        (self.skill / "references" / f"{CJK}.md").write_text("x", encoding="utf-8")
        with windows_pipe() as raw:
            code = self.run_script(package_skill.main, self.skill, self.root / "out")
        self.assertEqual(0, code)
        self.assertIn(CJK, raw.getvalue().decode("utf-8"))

    def test_the_validator_survives_quoting_the_skill_back(self):
        (self.skill / "SKILL.md").write_text(f"---\nname: {CJK}\ndescription: ok\n---\n", encoding="utf-8")
        with windows_pipe() as raw:
            with self.assertRaises(SystemExit) as exit_, patch.object(sys, "argv", ["quick_validate", str(self.skill)]):
                runpy.run_module("scripts.quick_validate", run_name="__main__")
        self.assertEqual(1, exit_.exception.code)
        self.assertIn(CJK, raw.getvalue().decode("utf-8"))

    def test_the_benchmark_summary_survives_a_configuration_name_the_pipe_cannot_encode(self):
        with windows_pipe() as raw:
            self.assertIsNone(self.run_script(aggregate_benchmark.main, self.benchmark_dir()))
        self.assertIn(CJK.title(), raw.getvalue().decode("utf-8"))

    def test_the_report_can_go_to_a_pipe(self):
        results = self.root / "results.json"
        write_json(results, {"history": [{"iteration": 1, "description": CJK, "train_passed": 1, "train_total": 1,
                                          "train_results": [{"query": CJK, "should_trigger": True, "pass": True, "triggers": 1, "runs": 1}]}]})
        with windows_pipe() as raw:
            self.assertIsNone(self.run_script(generate_report.main, results))
        self.assertIn("✓", raw.getvalue().decode("utf-8"))

    def test_the_viewer_path_survives_a_pipe(self):
        run = self.root / "ws" / "eval-1" / "with_skill"
        (run / "outputs").mkdir(parents=True)
        target = self.root / f"viewer-{CJK}.html"
        with windows_pipe() as raw:
            code = self.run_script(generate_review.main, self.root / "ws", "--static", target)
        self.assertEqual(0, code)
        self.assertIn(CJK, raw.getvalue().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
