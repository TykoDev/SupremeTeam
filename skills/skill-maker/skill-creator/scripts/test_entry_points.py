"""The scripts start the way their docstrings say: as a module, and by path where the docstring says so.

aggregate_benchmark.py and generate_report.py ran by path at r1 and stopped doing so
when they began importing scripts.utils. quick_validate.py is declared by path in
pipelines.yaml. Each is started in a child process from a directory that is not the
skill-creator directory, which is where a by-path run has nothing on sys.path.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CREATOR = Path(__file__).resolve().parents[1]
SCRIPTS = CREATOR / "scripts"

GRADING = {
    "expectations": [{"text": "check", "passed": True, "evidence": "seen"}],
    "summary": {"passed": 1, "failed": 0, "total": 1, "pass_rate": 1.0},
}


class EntryPointCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.elsewhere = self.root / "elsewhere"
        self.elsewhere.mkdir()

    def by_path(self, script: str, *args) -> subprocess.CompletedProcess:
        return self.run_child(str(SCRIPTS / f"{script}.py"), *args, cwd=self.elsewhere)

    def as_module(self, script: str, *args) -> subprocess.CompletedProcess:
        return self.run_child("-m", f"scripts.{script}", *args, cwd=CREATOR)

    def run_child(self, *args, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, *map(str, args)], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


class AggregateBenchmarkEntryTests(EntryPointCase):
    def benchmark_dir(self) -> Path:
        for config in ("with_skill", "without_skill"):
            run = self.root / "iteration-1" / "eval-1" / config
            run.mkdir(parents=True, exist_ok=True)
            (run / "grading.json").write_text(json.dumps(GRADING), encoding="utf-8")
        return self.root / "iteration-1"

    def test_it_runs_by_path_and_as_a_module(self):
        for label, start in (("by path", self.by_path), ("as a module", self.as_module)):
            with self.subTest(form=label):
                directory = self.benchmark_dir()
                (directory / "benchmark.json").unlink(missing_ok=True)
                process = start("aggregate_benchmark", directory)
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                written = json.loads((directory / "benchmark.json").read_text(encoding="utf-8"))
                self.assertEqual(len(written["runs"]), 2)
                self.assertIn("Generated:", process.stdout)

    def test_it_fails_loudly_by_path_when_there_is_nothing_to_aggregate(self):
        empty = self.root / "empty"
        empty.mkdir()
        process = self.by_path("aggregate_benchmark", empty)
        self.assertEqual(process.returncode, 1)
        self.assertNotIn("Traceback", process.stderr)


class GenerateReportEntryTests(EntryPointCase):
    def test_it_runs_by_path_and_as_a_module(self):
        results = self.root / "results.json"
        results.write_text(json.dumps({"history": []}), encoding="utf-8")
        for label, start in (("by path", self.by_path), ("as a module", self.as_module)):
            with self.subTest(form=label):
                page = self.root / "report.html"
                page.unlink(missing_ok=True)
                process = start("generate_report", results, "-o", page, "--skill-name", "sample")
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                self.assertIn("<html", page.read_text(encoding="utf-8"))


class QuickValidateEntryTests(EntryPointCase):
    def test_it_runs_by_path_because_the_pipeline_declares_it_by_path(self):
        skill = self.root / "sample"
        skill.mkdir()
        (skill / "SKILL.md").write_text("---\nname: sample\ndescription: Does a thing\n---\nbody\n", encoding="utf-8")
        process = self.by_path("quick_validate", skill)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertEqual(process.stdout.strip(), "Skill is valid!")


if __name__ == "__main__":
    unittest.main()
