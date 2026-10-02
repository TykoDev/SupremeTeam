"""The lint configuration, the CI job that runs it, and the markers that talk to it.

CR-17: the repository had no linter configuration, shipped unused imports and locals,
and carried `# noqa` markers for tools nobody ran. ruff is not a dependency of this
suite (the harness is stdlib only), so these read the configuration, the workflow and
the sources instead of running the linter; the CI `lint` job runs it.

These read the repository around ``skills/``, so they skip in an installed copy,
which carries only ``skills/``.
"""
from __future__ import annotations

import re
import tomllib
import unittest

import _catalog
from _catalog import SKILLS
from package_check import manifest_globs, matches

REPO = SKILLS.parent
IN_A_CHECKOUT = (REPO / "README.md").is_file() and (REPO / "docs").is_dir()
CHECKOUT_ONLY = unittest.skipUnless(IN_A_CHECKOUT, "installed copy: only skills/ is present")

#: Directories that hold generated or foreign files, which the linter and these tests both leave alone.
SKIPPED_DIRECTORIES = {".git", ".harness-state", ".claude", "skillset-saves", "__pycache__", ".venv"}


def rule_letters(code: str) -> str:
    return re.match(r"[A-Z]+", code).group(0)


def python_sources():
    for path in sorted(REPO.rglob("*.py")):
        if not SKIPPED_DIRECTORIES.intersection(path.relative_to(REPO).parts):
            yield path


@CHECKOUT_ONLY
class LintConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = tomllib.loads((REPO / "ruff.toml").read_text(encoding="utf-8"))

    def test_the_target_is_the_runtime_floor(self):
        minimum = _catalog.load_spec("runtime-manifest.yaml")["runtime"]["python"]["minimum"]
        self.assertEqual("py" + minimum.replace(".", ""), self.config["target-version"])

    def test_the_rules_that_find_defects_are_on(self):
        selected = set(self.config["lint"]["select"])
        missing = {"F", "E9", "B", "RUF100"} - selected
        self.assertEqual(set(), missing, "unused names, syntax errors, bugbear and stale noqa markers must stay checked")

    def test_the_cache_lands_where_no_package_ships_it(self):
        """A `.ruff_cache` at the root was counted by package_check and archived."""
        _, exclude = manifest_globs(_catalog.load_spec("package-manifest.yaml"))
        cache = self.config["cache-dir"]
        self.assertTrue(matches(f"{cache}/0.16.9/abc", exclude), f"{cache} is not excluded by package-manifest.yaml")
        self.assertFalse(cache.startswith(("/", "..")), cache)

    def test_every_noqa_marker_names_a_rule_the_configuration_enables(self):
        """A marker for a tool nobody runs (`WPS433`) claims a check that does not exist."""
        selected = self.config["lint"]["select"]
        offenders = []
        for path in python_sources():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for found in re.finditer(r"#\s*noqa:\s*([A-Z][A-Z0-9, ]*)", line):
                    for code in filter(None, re.split(r"[,\s]+", found.group(1))):
                        enabled = any(rule_letters(rule) == rule_letters(code) and code.startswith(rule) for rule in selected)
                        if not enabled:
                            offenders.append(f"{path.relative_to(REPO).as_posix()}:{number} {code}")
        self.assertEqual([], offenders)

    def test_the_noqa_check_tells_a_foreign_code_from_an_enabled_one(self):
        selected = self.config["lint"]["select"]

        def enabled(code):
            return any(rule_letters(rule) == rule_letters(code) and code.startswith(rule) for rule in selected)

        self.assertTrue(all(enabled(code) for code in ("E402", "F401", "B905", "PLE0101", "W605", "RUF100")))
        self.assertFalse(any(enabled(code) for code in ("WPS433", "E501", "S101", "T201", "N802")))


@CHECKOUT_ONLY
class LintJobTests(unittest.TestCase):
    def setUp(self):
        workflow = _catalog.load_data(REPO / ".github" / "workflows" / "ci.yml")
        self.job = workflow["jobs"]["lint"]
        self.runs = [step["run"] for step in self.job["steps"] if "run" in step]

    def test_the_job_is_not_conditional_and_cannot_fail_silently(self):
        for field in ("if", "continue-on-error", "strategy"):
            self.assertNotIn(field, self.job, f"a lint job with {field} can pass without linting")

    def test_ruff_is_installed_at_one_exact_version(self):
        installs = [run for run in self.runs if "pip install" in run]
        self.assertEqual(1, len(installs), installs)
        self.assertRegex(installs[0], r"^python -m pip install ruff==\d+\.\d+\.\d+$")

    def test_the_job_lints_the_whole_tree_the_configuration_covers(self):
        self.assertIn("ruff check .", self.runs)

    def test_the_job_runs_the_python_the_configuration_targets(self):
        minimum = _catalog.load_spec("runtime-manifest.yaml")["runtime"]["python"]["minimum"]
        setup = next(step for step in self.job["steps"] if str(step.get("uses", "")).startswith("actions/setup-python"))
        self.assertEqual(minimum, str(setup["with"]["python-version"]))


if __name__ == "__main__":
    unittest.main()
