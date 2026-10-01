"""Regression coverage for validate_manifests.py: the declared CI has to exist.

``runtime-manifest.yaml`` declared a windows, macos and linux matrix for as long as
the repository existed, and the validator only checked that the three names were
there. No workflow ran, so no suite ran anywhere automatically and the validator
could never fail for the missing CI. These tests pin the other half: the workflow
the manifest names must exist and cover every declared platform, launcher,
Python version, PyYAML variant and command. Each negative case spoils one
property of a good workflow and names the gap the validator must report.

The documentation mirrors used to be literal prose needles (the English "Ten
pipelines", two table rows), so editing a sentence broke the build and adding a
pipeline needed an edit to the validator. They are table and count checks now, and
the cases below pin that a re-wrapped row or a spelled-out number passes while a
missing row fails.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import package_check
import validate_manifests
from data_formats import load_data

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - environment without PyYAML
    yaml = None

SCRIPTS = Path(__file__).resolve().parent
SKILLS = SCRIPTS.parent
REPO = SKILLS.parent
VALIDATOR = SCRIPTS / "validate_manifests.py"
# An install carries only skills/, so the tests that read README, docs/, AGENTS.md or
# .github/ skip there on the validator's own test for an installed copy.
CHECKOUT_ONLY = unittest.skipUnless(validate_manifests.is_repository(SKILLS),
                                    "installed copy: README, docs/, AGENTS.md, .github/ and scripts/ are not present")
RUNNERS = {"windows": "windows-latest", "macos": "macos-latest", "linux": "ubuntu-latest"}


def real_runtime() -> dict:
    return load_data(SKILLS / "runtime-manifest.yaml")


def good_workflow(runtime: dict) -> dict:
    """A workflow built from the manifest alone, so it follows the manifest."""
    commands = runtime["commands"]
    platforms = {item["platform"]: item["launcher"] for item in runtime["ci_matrix"]}
    install = next(dep["install"] for dep in runtime["runtime"]["python"]["optional_dependencies"]
                   if dep["name"] == "PyYAML")
    steps = [
        {"uses": "actions/checkout@v4"},
        {"name": "pyyaml", "if": "matrix.pyyaml == 'with'", "run": install},
        {"name": "launcher", "run": "${{ matrix.launcher }} skills/scripts/check_runtime.py"},
    ]
    steps += [{"name": name, "run": commands[name]} for name in runtime["ci"]["commands"]]
    return {
        "name": "CI",
        "on": {"push": {"branches": ["dev"]}, "pull_request": None},
        "jobs": {"suites": {
            "runs-on": "${{ matrix.os }}",
            "strategy": {"matrix": {
                "os": [RUNNERS[platform] for platform in platforms],
                "python": list(runtime["runtime"]["python"]["supported"]),
                "pyyaml": list(runtime["ci"]["pyyaml"]),
                "include": [{"os": RUNNERS[platform], "launcher": launcher}
                            for platform, launcher in platforms.items()],
            }},
            "steps": steps,
        }},
    }


def workflow_errors(runtime: dict, workflow: dict | None, *, text: str | None = None) -> list[str]:
    """Run ``check_ci_workflow`` against a workflow written into a scratch repository."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        if workflow is not None or text is not None:
            target = repo / runtime["ci"]["workflow"]
            target.parent.mkdir(parents=True)
            target.write_text(text if text is not None else json.dumps(workflow), encoding="utf-8")
        errors: list[str] = []
        validate_manifests.check_ci_workflow(runtime, repo, errors)
        return errors


class RepositoryTests(unittest.TestCase):
    """The repository's own manifest and workflow, which CI runs on every platform."""

    @CHECKOUT_ONLY
    def test_the_repository_validates_clean_and_runs_the_repository_checks(self):
        report = validate_manifests.validate(SKILLS)
        self.assertEqual([], report["errors"])
        self.assertTrue(report["ok"])
        self.assertTrue(report["repository_checks"], "a checkout must run the CI and documentation checks, not skip them")

    @CHECKOUT_ONLY
    def test_the_real_workflow_covers_the_manifest(self):
        errors: list[str] = []
        validate_manifests.check_ci_workflow(real_runtime(), REPO, errors)
        self.assertEqual([], errors)

    def test_every_manifest_command_is_run_by_ci_or_explained(self):
        runtime = real_runtime()
        errors: list[str] = []
        validate_manifests.check_ci_declaration(runtime, errors)
        self.assertEqual([], errors)
        run, skipped = set(runtime["ci"]["commands"]), set(runtime["ci"]["not_run"])
        self.assertEqual(set(runtime["commands"]), run | skipped)
        self.assertFalse(run & skipped)

    @CHECKOUT_ONLY
    def test_every_suite_command_points_at_a_directory_that_holds_tests(self):
        suites = {name: command for name, command in real_runtime()["commands"].items()
                  if command.startswith("python -m unittest discover")}
        self.assertEqual({"hooks", "gates", "validation", "scripts", "taste", "installers", "skill_creator"}, set(suites))
        for name, command in suites.items():
            directory = re.search(r"-s (\S+)", command).group(1)
            with self.subTest(suite=name):
                self.assertTrue((REPO / directory).is_dir(), f"{name} points at {directory}, which does not exist")
                self.assertTrue(list((REPO / directory).rglob("test_*.py")), f"{directory} holds no test module")

    @CHECKOUT_ONLY
    def test_the_documents_list_every_command_ci_runs(self):
        """A contributor following README, CONTRIBUTING or docs/harness.md runs what CI runs.

        The archive form is `package_check` with an output option, so the plain
        form already names it.
        """
        runtime = real_runtime()
        listed = [name for name in runtime["ci"]["commands"] if name != "package_archive"]
        for document in ("README.md", "CONTRIBUTING.md", "docs/harness.md"):
            text = validate_manifests._command_text((REPO / document).read_text(encoding="utf-8"))
            for name in listed:
                command = validate_manifests._command_text(runtime["commands"][name])
                with self.subTest(document=document, command=name):
                    self.assertTrue(command in text, f"{document} does not list {name}: {command}")


@CHECKOUT_ONLY
class WorkflowPolicyTests(unittest.TestCase):
    """What the owner asked of the workflow beyond covering the manifest."""

    @classmethod
    def setUpClass(cls):
        cls.path = REPO / real_runtime()["ci"]["workflow"]
        cls.workflow = load_data(cls.path)
        cls.text = cls.path.read_text(encoding="utf-8")

    def steps(self):
        return self.workflow["jobs"]["suites"]["steps"]

    def test_the_token_is_read_only(self):
        self.assertEqual({"contents": "read"}, self.workflow["permissions"])

    def test_triggers_run_on_pull_requests_and_never_on_pull_request_target(self):
        triggers = set(self.workflow["on"])
        self.assertLessEqual({"push", "pull_request"}, triggers)
        self.assertNotIn("pull_request_target", triggers, "that trigger hands a fork's code a write token")

    def test_actions_are_pinned_to_a_version_and_come_from_github(self):
        uses = [step["uses"] for step in self.steps() if "uses" in step]
        self.assertTrue(uses)
        for action in uses:
            with self.subTest(action=action):
                self.assertRegex(action, r"^actions/[\w.-]+@(v\d+(\.\d+){0,2}|[0-9a-f]{40})$")

    def test_nothing_is_cached_and_the_checkout_keeps_no_credentials(self):
        for step in self.steps():
            with self.subTest(step=step.get("name") or step.get("uses")):
                self.assertFalse(str(step.get("uses", "")).startswith("actions/cache"))
                self.assertNotIn("cache", step.get("with") or {})
        checkout = next(step for step in self.steps() if str(step.get("uses", "")).startswith("actions/checkout"))
        self.assertIs(False, checkout["with"]["persist-credentials"])

    def test_a_failing_leg_does_not_hide_the_others_and_a_hang_is_bounded(self):
        job = self.workflow["jobs"]["suites"]
        self.assertIs(False, job["strategy"]["fail-fast"])
        self.assertLessEqual(int(job["timeout-minutes"]), 60)

    def test_the_pyyaml_variant_reaches_the_tests_that_check_it(self):
        """The validation suite fails a leg whose PyYAML does not match what the leg promises."""
        self.assertEqual("${{ matrix.pyyaml }}", self.workflow["jobs"]["suites"]["env"]["SUPREMETEAM_PYYAML"])
        helper = (SKILLS / "validation" / "_catalog.py").read_text(encoding="utf-8")
        self.assertIn('"SUPREMETEAM_PYYAML"', helper)

    @unittest.skipIf(yaml is None, "PyYAML is optional; the repository parser already loaded the file")
    def test_pyyaml_and_the_repository_parser_read_the_same_workflow(self):
        """GitHub reads this file with a full YAML parser, the validator with the stdlib subset."""
        theirs = yaml.safe_load(self.text)
        theirs["on"] = theirs.pop(True)  # YAML 1.1 reads the bare key `on` as the boolean true
        self.assertEqual(self.workflow, json.loads(json.dumps(theirs)))


class WorkflowCoverageTests(unittest.TestCase):
    """A good workflow passes and each missing property is named."""

    def setUp(self):
        self.runtime = real_runtime()
        self.good = good_workflow(self.runtime)

    def job(self, workflow):
        return workflow["jobs"]["suites"]

    def gaps(self, workflow=None, runtime=None):
        return workflow_errors(runtime or self.runtime, workflow or self.good)

    def assertGap(self, errors, fragment):
        self.assertTrue(any(fragment in error for error in errors), f"no error mentions {fragment!r}: {errors}")

    def test_a_workflow_built_from_the_manifest_passes(self):
        self.assertEqual([], self.gaps())

    def test_a_missing_workflow_file_fails(self):
        errors = workflow_errors(self.runtime, None)
        self.assertGap(errors, "does not exist")
        self.assertGap(errors, self.runtime["ci"]["workflow"])

    def test_an_unreadable_workflow_fails(self):
        self.assertGap(workflow_errors(self.runtime, None, text="jobs: [unterminated"), "unreadable")

    def test_a_workflow_without_jobs_fails(self):
        self.assertGap(self.gaps({"on": {"push": None, "pull_request": None}}), "jobs must be a non-empty mapping")

    def test_a_workflow_that_never_triggers_fails(self):
        workflow = copy.deepcopy(self.good)
        workflow["on"] = {"workflow_dispatch": None}
        errors = self.gaps(workflow)
        self.assertGap(errors, "never runs on push")
        self.assertGap(errors, "never runs on pull_request")

    def test_each_declared_platform_must_have_a_runner(self):
        for platform, runner in RUNNERS.items():
            workflow = copy.deepcopy(self.good)
            matrix = self.job(workflow)["strategy"]["matrix"]
            matrix["os"].remove(runner)
            with self.subTest(platform=platform):
                self.assertGap(self.gaps(workflow), f"no matrix.os runner for {platform}")

    def test_a_runner_the_manifest_does_not_declare_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["strategy"]["matrix"]["os"].append("self-hosted")
        self.assertGap(self.gaps(workflow), "matrix.os runner 'self-hosted' maps to no declared platform")

    def test_every_supported_python_must_be_in_the_matrix(self):
        for version in self.runtime["runtime"]["python"]["supported"]:
            workflow = copy.deepcopy(self.good)
            self.job(workflow)["strategy"]["matrix"]["python"].remove(version)
            with self.subTest(version=version):
                self.assertGap(self.gaps(workflow), "matrix.python is")

    def test_a_python_version_the_manifest_does_not_support_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["strategy"]["matrix"]["python"].append("3.12")
        self.assertGap(self.gaps(workflow), "matrix.python is")

    def test_both_pyyaml_variants_must_run(self):
        for variant in ("with", "without"):
            workflow = copy.deepcopy(self.good)
            self.job(workflow)["strategy"]["matrix"]["pyyaml"].remove(variant)
            with self.subTest(variant=variant):
                self.assertGap(self.gaps(workflow), "matrix.pyyaml is")

    def test_the_pyyaml_install_must_be_limited_to_the_legs_that_ask_for_it(self):
        workflow = copy.deepcopy(self.good)
        install = next(step for step in self.job(workflow)["steps"] if step.get("name") == "pyyaml")
        del install["if"]
        self.assertGap(self.gaps(workflow), "only for the matrix.pyyaml legs that ask for it")

    def test_a_missing_pyyaml_install_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["steps"] = [step for step in self.job(workflow)["steps"] if step.get("name") != "pyyaml"]
        self.assertGap(self.gaps(workflow), "only for the matrix.pyyaml legs that ask for it")

    def test_the_declared_launcher_must_match_the_manifest(self):
        workflow = copy.deepcopy(self.good)
        for entry in self.job(workflow)["strategy"]["matrix"]["include"]:
            if entry["os"] == RUNNERS["windows"]:
                entry["launcher"] = "python"
        self.assertGap(self.gaps(workflow), "launcher for windows is 'python'; the manifest declares 'py -3'")

    def test_a_launcher_that_no_step_uses_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["steps"] = [step for step in self.job(workflow)["steps"] if step.get("name") != "launcher"]
        self.assertGap(self.gaps(workflow), "no step runs the declared launcher")

    def test_every_ci_command_must_have_a_step(self):
        for name in self.runtime["ci"]["commands"]:
            workflow = copy.deepcopy(self.good)
            command = self.runtime["commands"][name]
            self.job(workflow)["steps"] = [step for step in self.job(workflow)["steps"] if step.get("run") != command]
            with self.subTest(command=name):
                self.assertGap(self.gaps(workflow), f"no step runs {name}")

    def test_a_shell_quoted_command_still_counts(self):
        workflow = copy.deepcopy(self.good)
        for step in self.job(workflow)["steps"]:
            step["run"] = step.get("run", "").replace('"test_*.py"', "'test_*.py'")
        self.assertEqual([], self.gaps(workflow))

    def test_a_command_that_differs_from_the_manifest_does_not_count(self):
        workflow = copy.deepcopy(self.good)
        for step in self.job(workflow)["steps"]:
            if step.get("name") == "taste":
                step["run"] = step["run"].replace("skills/taste", "skills/tast")
        self.assertGap(self.gaps(workflow), "no step runs taste")

    def test_a_conditional_or_failure_tolerant_command_step_fails(self):
        for field, value in (("if", "github.ref == 'refs/heads/dev'"), ("continue-on-error", True)):
            workflow = copy.deepcopy(self.good)
            next(step for step in self.job(workflow)["steps"] if step.get("name") == "hooks")[field] = value
            with self.subTest(field=field):
                self.assertGap(self.gaps(workflow), "hooks runs conditionally or may fail")

    def test_a_job_that_may_fail_silently_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["continue-on-error"] = True
        self.assertGap(self.gaps(workflow), "lets the job fail without failing the workflow")

    def test_a_job_that_can_be_skipped_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["if"] = "github.ref == 'refs/heads/main'"
        self.assertGap(self.gaps(workflow), "a job-level if can skip the whole matrix")

    def test_an_exclude_that_drops_a_leg_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["strategy"]["matrix"]["exclude"] = [{"os": RUNNERS["windows"], "python": "3.14"}]
        self.assertGap(self.gaps(workflow), "matrix excludes legs")

    def test_a_job_that_ignores_the_matrix_runner_fails(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["runs-on"] = "ubuntu-latest"
        self.assertGap(self.gaps(workflow), "runs-on must be ${{ matrix.os }}")

    def test_the_whole_matrix_must_sit_in_one_job(self):
        """Platforms in one job and commands in another would pass a union check."""
        workflow = copy.deepcopy(self.good)
        platforms_only = copy.deepcopy(self.job(workflow))
        platforms_only["steps"] = [{"uses": "actions/checkout@v4"}]
        commands_only = copy.deepcopy(self.job(workflow))
        commands_only["strategy"]["matrix"]["os"] = [RUNNERS["linux"]]
        workflow["jobs"] = {"platforms": platforms_only, "commands": commands_only}
        errors = self.gaps(workflow)
        self.assertTrue(errors, "no single job runs every command on every platform, yet the check passed")

    @CHECKOUT_ONLY
    def test_edits_to_the_real_workflow_text_are_caught_through_the_stdlib_parser(self):
        """The fixtures above are JSON; the real file is block YAML, which the stdlib subset reads."""
        text = (REPO / self.runtime["ci"]["workflow"]).read_text(encoding="utf-8")
        self.assertEqual([], workflow_errors(self.runtime, None, text=text))
        without_taste = re.sub(r"      - name: taste\n        run: .*\n\n", "", text)
        self.assertNotEqual(text, without_taste, "the real workflow no longer has a taste step this test can remove")
        self.assertGap(workflow_errors(self.runtime, None, text=without_taste), "no step runs taste")
        self.assertGap(workflow_errors(self.runtime, None, text=text.replace('"3.14"', '"3.12"')), "matrix.python is")
        without_windows = text.replace("os: [ubuntu-latest, windows-latest, macos-latest]", "os: [ubuntu-latest, macos-latest]")
        self.assertNotEqual(text, without_windows)
        self.assertGap(workflow_errors(self.runtime, None, text=without_windows), "no matrix.os runner for windows")

    def test_the_errors_name_the_workflow_and_the_job(self):
        workflow = copy.deepcopy(self.good)
        self.job(workflow)["strategy"]["matrix"]["python"].pop()
        self.assertTrue(all(error.startswith(".github/workflows/ci.yml: job suites: ") for error in self.gaps(workflow)))


class CiDeclarationTests(unittest.TestCase):
    """The manifest side: every command is run by CI or says why it is not."""

    def setUp(self):
        self.runtime = real_runtime()

    def errors(self, runtime=None):
        found: list[str] = []
        validate_manifests.check_ci_declaration(runtime or self.runtime, found)
        return found

    def assertGap(self, errors, fragment):
        self.assertTrue(any(fragment in error for error in errors), f"no error mentions {fragment!r}: {errors}")

    def test_the_real_declaration_is_clean(self):
        self.assertEqual([], self.errors())

    def test_a_manifest_without_a_ci_block_fails(self):
        del self.runtime["ci"]
        self.assertGap(self.errors(), "ci must be a mapping")

    def test_a_workflow_path_must_stay_inside_the_repository(self):
        for path in ("/etc/ci.yml", "../ci.yml", ""):
            runtime = copy.deepcopy(self.runtime)
            runtime["ci"]["workflow"] = path
            with self.subTest(path=path):
                self.assertGap(self.errors(runtime), "ci.workflow must be a relative path")

    def test_a_command_that_is_neither_run_nor_explained_fails(self):
        self.runtime["commands"]["new_suite"] = "python -m unittest discover -s elsewhere"
        self.assertGap(self.errors(), "'new_suite' is neither run by CI nor explained")

    def test_a_ci_command_must_exist(self):
        self.runtime["ci"]["commands"].append("ghost")
        self.assertGap(self.errors(), "names 'ghost', which is not in commands")

    def test_a_command_with_a_placeholder_cannot_be_a_ci_command(self):
        self.runtime["ci"]["commands"].append("gate_check")
        del self.runtime["ci"]["not_run"]["gate_check"]
        self.assertGap(self.errors(), "'gate_check', whose command holds a placeholder")

    def test_a_command_cannot_be_both_run_and_exempt(self):
        self.runtime["ci"]["not_run"]["hooks"] = "because"
        self.assertGap(self.errors(), "'hooks' is both run by CI and listed under ci.not_run")

    def test_an_exemption_needs_a_reason(self):
        self.runtime["ci"]["not_run"]["readiness"] = " "
        self.assertGap(self.errors(), "gives no reason for 'readiness'")

    def test_an_exemption_must_name_a_command(self):
        self.runtime["ci"]["not_run"]["ghost"] = "no such command"
        self.assertGap(self.errors(), "ci.not_run names 'ghost'")

    def test_ci_must_run_with_and_without_pyyaml(self):
        self.runtime["ci"]["pyyaml"] = ["with"]
        self.assertGap(self.errors(), "ci.pyyaml must name both with and without")

    def test_the_pyyaml_variants_need_an_install_command(self):
        self.runtime["runtime"]["python"]["optional_dependencies"][0]["install"] = ""
        self.assertGap(self.errors(), "install command")

    def test_the_python_floor_must_be_a_supported_version(self):
        self.runtime["runtime"]["python"]["supported"] = ["3.14"]
        found: list[str] = []
        validate_manifests.check_runtime(self.runtime, SKILLS, found)
        self.assertGap(found, "supported must include the minimum")

    def test_ci_matrix_launchers_must_agree_with_the_launcher_table(self):
        self.runtime["ci_matrix"][0]["launcher"] = "python"
        found: list[str] = []
        validate_manifests.check_runtime(self.runtime, SKILLS, found)
        self.assertGap(found, "ci_matrix launcher for windows differs from launchers.windows")

    def test_a_removed_suite_command_is_reported_as_missing(self):
        for name in ("scripts", "taste", "installers", "skill_creator"):
            runtime = copy.deepcopy(self.runtime)
            del runtime["commands"][name]
            found: list[str] = []
            validate_manifests.check_runtime(runtime, SKILLS, found)
            with self.subTest(command=name):
                self.assertGap(found, f"missing command {name}")

    def test_the_manifest_says_which_suites_need_a_checkout(self):
        """RR-ci-docs-2: it named the installers suite only, while four more read README, docs/ or .github/."""
        prose = " ".join(self.runtime["authority"]["commands"].split())
        found = re.search(r"(The installers suite needs a repository checkout.*?) The strings are written", prose)
        self.assertIsNotNone(found, "authority.commands no longer says which suites need a checkout")
        for suite in ("installers", "hooks", "gates", "scripts", "validation"):
            with self.subTest(suite=suite):
                self.assertIn(suite, found.group(1))

    def test_pyyaml_is_declared_for_every_script_that_requires_it(self):
        used_by = next(dep["used_by"] for dep in self.runtime["runtime"]["python"]["optional_dependencies"]
                       if dep["name"] == "PyYAML")
        test_support = ("test_", "_catalog.py")
        importers = sorted(
            path.relative_to(SKILLS).as_posix() for path in SKILLS.rglob("*.py")
            if not path.name.startswith(test_support) and re.search(r"^\s*import yaml\b", path.read_text(encoding="utf-8"), re.M))
        self.assertEqual(importers, sorted(used_by))


class DocumentationMirrorTests(unittest.TestCase):
    """The mirrors read tables and counts, not sentences."""

    PIPELINES = {
        "design": {"owner": "commander", "boundary": "design-to-build"},
        "taste": {"owner": "taste", "boundary": "taste-review"},
    }
    BOUNDARIES = {"design-to-build", "taste-review"}

    def texts(self, **overrides):
        base = {
            "AGENTS.md": "## The 53 skills\n**53 skills**\n\n| Pipeline | Owner | Closes at |\n|---|---|---|\n"
                         "| `design` | `commander` | `design-to-build` |\n| `taste` | `taste` | `taste-review` |\n",
            "README.md": "53 skills · 2 pipelines",
            "docs/architecture.md": "Two pipelines, one front door.\n\n| Pipeline | Owner | Boundary | Does |\n|---|---|---|---|\n"
                                    "| `design` | commander | `design-to-build` | things |\n"
                                    "| `taste` | taste | `taste-review` | other things |\n",
            "docs/skills.md": "53 of them.\n\n## Taste (2)\n",
            "docs/gatekeepers.md": "| `design-to-build` | DESIGN to BUILD | commander |\n| `taste-review` | TASTE | taste |\n",
            "docs/directory-structure.md": "Gate spec: 2 boundaries\nPipeline map: 2 pipelines\n",
        }
        base.update(overrides)
        return base

    def gaps(self, texts=None, skills=53, taste=2, pipelines=None, boundaries=None):
        return validate_manifests.documentation_gaps(
            texts or self.texts(), skills, taste, pipelines or self.PIPELINES, boundaries or self.BOUNDARIES)

    def test_documents_that_agree_with_the_specs_pass(self):
        self.assertEqual([], self.gaps())

    def test_a_number_may_be_a_digit_or_a_word_in_any_case(self):
        for phrase in ("2 pipelines", "Two pipelines", "two pipelines", "TWO PIPELINES"):
            document = self.texts()["docs/architecture.md"].replace("Two pipelines", phrase)
            with self.subTest(phrase=phrase):
                self.assertEqual([], self.gaps(self.texts(**{"docs/architecture.md": document})))

    def test_a_wrong_count_in_words_fails(self):
        texts = self.texts(**{"docs/architecture.md": self.texts()["docs/architecture.md"].replace("Two pipelines", "Three pipelines")})
        self.assertTrue(any("docs/architecture.md states no count of pipelines" in gap for gap in self.gaps(texts)))

    def test_a_table_row_may_be_rewrapped_padded_or_unticked(self):
        texts = self.texts(**{"AGENTS.md": "## The 53 skills\n**53 skills**\n"
                                           "|  design  |   commander   |  design-to-build  |\n"
                                           "| taste | taste | taste-review |\n"})
        self.assertEqual([], self.gaps(texts))

    def test_a_pipeline_without_a_row_fails_in_every_table_that_lists_pipelines(self):
        pipelines = {**self.PIPELINES, "audit": {"owner": "auditor", "boundary": "audit-review"}}
        gaps = self.gaps(pipelines=pipelines)
        for document in ("AGENTS.md", "docs/architecture.md"):
            with self.subTest(document=document):
                self.assertTrue(any(document in gap and "audit | auditor | audit-review" in gap for gap in gaps), gaps)

    def test_a_row_with_the_wrong_owner_fails(self):
        texts = self.texts(**{"docs/architecture.md": self.texts()["docs/architecture.md"].replace("| commander |", "| builder |")})
        self.assertTrue(any("design | commander | design-to-build" in gap for gap in self.gaps(texts)))

    def test_a_boundary_without_a_row_fails(self):
        texts = self.texts(**{"docs/gatekeepers.md": "| `design-to-build` | DESIGN to BUILD | commander |\n"})
        self.assertTrue(any("docs/gatekeepers.md has no table row starting 'taste-review'" in gap for gap in self.gaps(texts)))

    def test_the_skill_count_is_derived_from_the_tree(self):
        gaps = self.gaps(skills=54)
        for needle in ("## The 54 skills", "**54 skills**", "54 skills · 2 pipelines", "54 of them."):
            self.assertTrue(any(needle in gap for gap in gaps), (needle, gaps))

    def test_the_taste_section_count_is_derived_from_the_tree(self):
        self.assertTrue(any("## Taste (3)" in gap for gap in self.gaps(taste=3)))

    def test_a_page_that_quotes_its_own_needle_does_not_satisfy_it(self):
        """RR-ci-docs-1: docs/skills.md explained the check by quoting `53 of them.`, which a substring search found."""
        page = ("54 of them. The check compares only the total (`53 of them.`) and the `## Taste (2)` heading.\n"
                "\n## Taste (3)\n")
        gaps = self.gaps(self.texts(**{"docs/skills.md": page}))
        self.assertTrue(any("docs/skills.md" in gap and "'53 of them.'" in gap for gap in gaps), gaps)
        self.assertTrue(any("docs/skills.md" in gap and "'## Taste (2)'" in gap for gap in gaps), gaps)

    def test_a_number_that_only_starts_with_the_expected_one_is_not_the_total(self):
        page = "530 of them.\n\n## Taste (20)\n"
        self.assertEqual(2, len([gap for gap in self.gaps(self.texts(**{"docs/skills.md": page})) if "docs/skills.md" in gap]))

    def test_a_missing_document_is_left_to_the_unreadable_report(self):
        texts = self.texts()
        del texts["README.md"]
        self.assertEqual([], self.gaps(texts))

    @CHECKOUT_ONLY
    def test_every_document_the_check_reads_exists_in_the_repository(self):
        for name in validate_manifests.DOCUMENTATION_MIRRORS:
            with self.subTest(document=name):
                self.assertTrue((REPO / name).is_file())


class PackageManifestProseTests(unittest.TestCase):
    """BG-22: the manifest said eight residue classes after the code had grown to ten."""

    def setUp(self):
        manifest = load_data(SKILLS / "package-manifest.yaml")
        self.prose = " ".join(str(manifest["enforcement"]["machine_checked"]).split())

    def test_the_residue_classes_it_names_are_the_ones_package_check_has(self):
        found = re.search(r"against (\w+) residue classes \(([^)]*)\)", self.prose)
        self.assertIsNotNone(found, "the manifest no longer says how many residue classes package_check matches")
        count, names = found.group(1), [name.strip() for name in found.group(2).split(",")]
        self.assertEqual(list(package_check.RESIDUE_CLASSES), names)
        self.assertEqual(validate_manifests.NUMBER_WORDS[len(package_check.RESIDUE_CLASSES)], count)

    def test_the_required_assets_it_counts_are_the_ones_package_check_has(self):
        found = re.search(r"confirms (\w+) required assets", self.prose)
        self.assertIsNotNone(found, "the manifest no longer says how many required assets package_check confirms")
        self.assertEqual(validate_manifests.NUMBER_WORDS[len(package_check.REQUIRED_ASSET_GLOBS)], found.group(1))


class CommandLineTests(unittest.TestCase):
    """CR-23: three scripts take a directory and each means a different one, so this one says which."""

    def run_validator(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(VALIDATOR), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def test_help_says_what_the_argument_is(self):
        proc = self.run_validator("--help")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        flat = " ".join(proc.stdout.split())
        self.assertIn("usage:", flat)
        self.assertIn("the skills/ directory to validate", flat)
        self.assertIn("not the repository root", flat)
        self.assertNotIn('"errors"', proc.stdout, "--help was read as a directory to validate")

    def test_the_argument_is_still_the_catalog_directory_and_defaults_to_this_one(self):
        explicit, default = self.run_validator(str(SKILLS)), self.run_validator()
        self.assertEqual((0, 0), (explicit.returncode, default.returncode), explicit.stdout + default.stdout)
        self.assertEqual(json.loads(default.stdout), json.loads(explicit.stdout))

    def test_a_flag_it_does_not_have_is_refused_not_read_as_a_directory(self):
        proc = self.run_validator("--root", str(SKILLS))
        self.assertEqual(2, proc.returncode, proc.stdout)
        self.assertIn("unrecognized arguments", proc.stderr)


class LayoutTests(unittest.TestCase):
    """A repository checkout runs the repository checks; an installed copy skips them, visibly."""

    @classmethod
    def setUpClass(cls):
        cls.holder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.holder.cleanup)
        cls.base = Path(cls.holder.name)
        shutil.copytree(SKILLS, cls.base / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".harness-state"))

    def layout(self, name: str) -> Path:
        """A fresh directory whose ``skills`` is a copy of the catalog."""
        root = self.base / name
        shutil.copytree(self.base / "skills", root / "skills", dirs_exist_ok=True)
        return root

    def run_cli(self, skills: Path) -> tuple[int, dict]:
        proc = subprocess.run([sys.executable, str(VALIDATOR), str(skills)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        return proc.returncode, json.loads(proc.stdout)

    def test_an_installed_copy_is_valid_and_says_the_repository_checks_were_skipped(self):
        report = validate_manifests.validate(self.layout("installed") / "skills")
        self.assertEqual([], report["errors"])
        self.assertFalse(report["repository_checks"])

    def test_the_command_line_accepts_an_installed_copy(self):
        code, report = self.run_cli(self.layout("installed-cli") / "skills")
        self.assertEqual((0, True), (code, report["ok"]))

    def test_a_checkout_without_its_workflow_fails_the_validator(self):
        root = self.layout("no-workflow")
        (root / "README.md").write_text("# fixture\n", encoding="utf-8")
        report = validate_manifests.validate(root / "skills")
        self.assertTrue(report["repository_checks"])
        self.assertFalse(report["ok"])
        self.assertTrue(any("ci.workflow .github/workflows/ci.yml does not exist" in e for e in report["errors"]), report["errors"])

    def test_the_command_line_fails_for_a_checkout_without_its_workflow(self):
        root = self.layout("no-workflow-cli")
        (root / "docs").mkdir()
        code, report = self.run_cli(root / "skills")
        self.assertEqual((1, False), (code, report["ok"]))
        self.assertTrue(any("does not exist, so no CI runs the declared matrix" in e for e in report["errors"]))

    def test_the_repository_level_tests_skip_in_an_installed_copy(self):
        """RR-ci-docs-2: this module ships in installs, where README, docs/ and .github/ are not, and failed there."""
        installed = self.layout("installed-suite")
        names = ("RepositoryTests", "WorkflowPolicyTests", "DocumentationMirrorTests",
                 "test_edits_to_the_real_workflow_text", "test_a_complete_checkout_layout_passes")
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-v", "-s", str(installed / "skills" / "scripts"),
             "-p", "test_validate_manifests.py", *[arg for name in names for arg in ("-k", name)]],
            cwd=installed, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, proc.returncode, proc.stderr[-2000:])
        self.assertRegex(proc.stderr, r"OK \(skipped=\d+\)")
        self.assertIn("installed copy", proc.stderr + proc.stdout)

    @CHECKOUT_ONLY
    def test_a_complete_checkout_layout_passes(self):
        root = self.layout("complete")
        for name in ("AGENTS.md", "README.md", *[f"docs/{n}.md" for n in ("architecture", "skills", "gatekeepers", "directory-structure")]):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / name, target)
        shutil.copytree(REPO / ".github", root / ".github")
        report = validate_manifests.validate(root / "skills")
        self.assertEqual([], report["errors"])
        self.assertTrue(report["repository_checks"])

    def test_the_catalog_does_not_have_to_be_called_skills(self):
        """Manifest paths written as skills/... resolve inside the directory being validated."""
        root = self.base / "renamed"
        shutil.copytree(self.base / "skills", root / "catalog")
        report = validate_manifests.validate(root / "catalog")
        self.assertEqual([], report["errors"])


if __name__ == "__main__":
    unittest.main()
