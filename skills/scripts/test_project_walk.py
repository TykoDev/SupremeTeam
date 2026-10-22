"""The project walk behind every inspection mode: what it skips, where it stops, and what it tolerates.

The file and directory count limits are lowered for the tests that cross them
here, so a tree that crosses one is tens of entries rather than a thousand; the
command-line tests in test_check_runtime_contract.py cross the real file limit
with real trees. Everything else drives ``check()`` on a small project tree
(``_runtime_fixtures``).
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest import mock

import check_runtime
import project_files
from _runtime_fixtures import (
    COMPOSE_NO_PORTS,
    COMPOSE_PORTS,
    VITE_TREE,
    FixtureTreeCase,
    candidate,
    package_json,
    slugs,
    symlink_or_skip,
)

#: The inspection limits by their documented values. The depth and byte limits are crossed
#: with real trees. The two count limits are checked against these values and then lowered
#: to LOWERED_COUNT for the tests that cross them.
INSPECTION_LIMITS = {"files": 1_000, "directories": 1_000, "depth": 32, "bytes": 10_000_000}
LOWERED_COUNT = 20
#: Directories the project's own tooling regenerates: never evidence, often thousands of files.
GENERATED_DIRECTORIES = {
    ".next", ".nuxt", ".svelte-kit", ".output", ".turbo", "htmlcov", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


class WalkAndLimitTests(FixtureTreeCase):
    """Benign project traits are reported and skipped; an unusable root or a walk cut short fails the run."""

    def lowered_count_limits(self):
        """The walk's file and directory count limits lowered, once they are seen at their documented values."""
        self.assertEqual(
            (project_files.MAX_INSPECTION_FILE_COUNT, project_files.MAX_INSPECTION_DIRECTORY_COUNT),
            (INSPECTION_LIMITS["files"], INSPECTION_LIMITS["directories"]),
        )
        return mock.patch.multiple(
            project_files, MAX_INSPECTION_FILE_COUNT=LOWERED_COUNT, MAX_INSPECTION_DIRECTORY_COUNT=LOWERED_COUNT
        )

    def test_symlinked_entries_are_skipped_with_a_warning_and_the_walk_continues(self):
        root = self.project({**VITE_TREE, "elsewhere/package.json": package_json(dependencies={"next": "^15"})})
        outside = self.project({"package.json": package_json(dependencies={"astro": "^5"})})
        symlink_or_skip(self, root / "package.json", root / "CLAUDE.md")
        symlink_or_skip(self, outside, root / "linked", directory=True)
        inspection = self.check_root(root)["project_inspection"]
        self.assertClean(inspection)
        self.assertEqual(
            inspection["warnings"],
            [
                "CLAUDE.md: skipped, reparse points are not inspected",
                "linked: skipped, reparse points are not inspected",
            ],
        )
        self.assertEqual(slugs(inspection), ["react-nextjs", "vite-spa"])

    def test_a_symlinked_project_root_is_refused(self):
        real = self.project(VITE_TREE)
        holder = self.project({})
        link = holder / "project"
        symlink_or_skip(self, real, link, directory=True)
        report = self.check_root(link)
        inspection = report["project_inspection"]
        self.assertEqual(inspection["errors"], ["project root: reparse points are not inspected"])
        self.assertFalse(inspection["ok"])
        self.assertFalse(report["ok"])
        self.assertIn("project inspection: project root: reparse points are not inspected", report["errors"])
        self.assertEqual(inspection["stacks"], [])

    def test_a_missing_or_non_directory_root_is_an_error(self):
        holder = self.project({"a-file.txt": ""})
        for name, message in (("absent", "project root does not exist"), ("a-file.txt", "project root is not a directory")):
            with self.subTest(root=name):
                report = self.check_root(holder / name)
                self.assertEqual(report["project_inspection"]["errors"], [message])
                self.assertFalse(report["ok"])

    def test_large_and_undecodable_files_detection_does_not_need_are_not_read(self):
        big_lockfile = json.dumps({"name": "x", "lockfileVersion": 3, "padding": "x" * 1_100_000})
        inspection = self.inspect_tree(
            {
                **VITE_TREE,
                "package-lock.json": big_lockfile,
                "dump.sql": "-- " + "x" * 1_100_000,
                "notes.txt": b"caf\xe9 in latin-1",
                "docs/legacy.md": b"\xff\xfe binary-ish",
            }
        )
        self.assertClean(inspection)
        self.assertEqual(inspection["warnings"], [])
        self.assertEqual(slugs(inspection), ["vite-spa"])

    def test_a_file_detection_consumes_is_an_error_when_it_cannot_be_read(self):
        oversized = json.dumps({"name": "x", "description": "x" * 1_100_000})
        inspection = self.inspect_tree({"package.json": oversized})
        self.assertEqual(inspection["errors"], ["package.json: file exceeds the inspection size limit"])
        self.assertFalse(inspection["ok"])
        inspection = self.inspect_tree({"main.py": b"import fastapi  # caf\xe9\n"})
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("main.py: cannot read text"))
        self.assertEqual(slugs(inspection), [])

    def test_the_file_count_limit_makes_the_inspection_incomplete_and_keeps_the_names_that_sort_first(self):
        # Every filler is a configuration file, so the configs list shows which ones the walk kept:
        # package.json and the fillers that sort first fill the limit.
        fillers = {f"rollup.config.{number:04d}.js": "" for number in range(LOWERED_COUNT + 1)}
        with self.lowered_count_limits():
            report = self.report({**VITE_TREE, **fillers})
        inspection = report["project_inspection"]
        self.assertFalse(inspection["ok"])
        self.assertFalse(report["ok"])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("project inspection file-count limit exceeded; the walk stopped early"))
        self.assertIn("inspection is incomplete", inspection["errors"][0])
        self.assertEqual(slugs(inspection), ["vite-spa"])
        walked = {item["path"] for item in inspection["configs"]}
        self.assertIn(f"rollup.config.{LOWERED_COUNT - 2:04d}.js", walked)
        self.assertNotIn(f"rollup.config.{LOWERED_COUNT - 1:04d}.js", walked)
        self.assertNotIn(f"rollup.config.{LOWERED_COUNT:04d}.js", walked)

    def test_the_directory_count_limit_makes_the_inspection_incomplete(self):
        root = self.project({"a/package.json": package_json(dev={"vite": "^7"})})
        for number in range(LOWERED_COUNT + 1):
            (root / f"d{number:04d}").mkdir()
        with self.lowered_count_limits():
            inspection = self.check_root(root)["project_inspection"]
        self.assertFalse(inspection["ok"])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("project inspection directory-count limit exceeded; the walk stopped early"))
        self.assertEqual([item["path"] for item in inspection["manifests"]], ["a/package.json"])

    def test_the_total_byte_limit_makes_the_inspection_incomplete(self):
        half = INSPECTION_LIMITS["bytes"] // 2
        tree = {"a.bin": b"\0" * (half + 1_000_000), **VITE_TREE, "z.bin": b"\0" * half}
        inspection = self.inspect_tree(tree)
        self.assertFalse(inspection["ok"])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("project inspection total-byte limit exceeded; the walk stopped early"))
        self.assertEqual([item["path"] for item in inspection["manifests"]], ["package.json"])
        self.assertEqual(slugs(inspection), ["vite-spa"])

    def test_the_depth_limit_makes_the_inspection_incomplete_and_the_walk_continues(self):
        deep = "/".join(["n"] * (INSPECTION_LIMITS["depth"] + 2))
        tree = {
            f"{deep}/package.json": package_json(dependencies={"astro": "^5"}),
            "z/package.json": package_json(dev={"vite": "^7"}),
        }
        inspection = self.inspect_tree(tree)
        self.assertFalse(inspection["ok"])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("n/n/n/"))
        self.assertIn(": inspection depth limit exceeded; the directory was not examined", inspection["errors"][0])
        self.assertEqual(slugs(inspection), ["vite-spa"])

    def test_a_walk_cut_short_does_not_blame_the_working_directory_for_the_missing_evidence(self):
        """Nothing found because the walk stopped is not a reason to run from the project root."""
        fillers = {f"a{number:04d}.txt": "text\n" for number in range(LOWERED_COUNT + 1)}
        with self.lowered_count_limits():
            report = self.report({**fillers, "z/package.json": package_json(dev={"vite": "^7"})})
        inspection = report["project_inspection"]
        self.assertEqual(inspection["stacks"], [])
        self.assertEqual(inspection["manifests"], [])
        self.assertFalse(report["ok"])
        self.assertEqual(inspection["warnings"], [])
        self.assertIn("file-count limit exceeded", inspection["errors"][0])

    def test_generated_output_does_not_use_up_the_walk(self):
        """A build directory that sorts before the manifests, a Next.js .next/, must not hide them."""
        generated = {f".next/static/chunk{number:04d}.js": "x" for number in range(LOWERED_COUNT + 200)}
        with self.lowered_count_limits():
            inspection = self.inspect_tree({**generated, "apps/web/package.json": package_json(dev={"vite": "^7"})})
        self.assertClean(inspection)
        self.assertEqual(inspection["warnings"], [])
        self.assertEqual(slugs(inspection), ["vite-spa"])

    def test_every_generated_directory_name_is_left_out_of_the_walk(self):
        for name in sorted(GENERATED_DIRECTORIES):
            with self.subTest(directory=name):
                inspection = self.inspect_tree(
                    {**VITE_TREE, f"{name}/package.json": package_json(dependencies={"astro": "^5"}), f"x/{name}/package.json": "{"}
                )
                self.assertClean(inspection)
                self.assertEqual([item["path"] for item in inspection["manifests"]], ["package.json"])

    def test_an_unreadable_subdirectory_is_a_warning_and_an_unreadable_root_is_an_error(self):
        root = self.project({**VITE_TREE, "locked/package.json": package_json(dependencies={"astro": "^5"})})
        real_scandir = os.scandir

        def scandir(path):
            if Path(path).name == "locked":
                raise PermissionError(13, "Permission denied")
            return real_scandir(path)

        with mock.patch.object(os, "scandir", scandir):
            inspection = self.check_root(root)["project_inspection"]
        self.assertClean(inspection)
        self.assertEqual(len(inspection["warnings"]), 1)
        self.assertTrue(inspection["warnings"][0].startswith("locked: skipped, cannot read directory"))
        self.assertEqual(slugs(inspection), ["vite-spa"])

        def refuse_root(path):
            if Path(path) == root:
                raise PermissionError(13, "Permission denied")
            return real_scandir(path)

        with mock.patch.object(os, "scandir", refuse_root):
            inspection = self.check_root(root)["project_inspection"]
        self.assertFalse(inspection["ok"])
        self.assertTrue(inspection["errors"][0].startswith("cannot inspect"))

    def test_an_empty_or_unrecognisable_project_warns_instead_of_reporting_silence(self):
        for label, tree in {
            "empty directory": {},
            "only source and documents": {"src/util.py": "x = 1\n", "README.md": "# hi\n"},
        }.items():
            with self.subTest(case=label):
                inspection = self.inspect_tree(tree)
                self.assertTrue(inspection["ok"])
                self.assertEqual(inspection["stacks"], [])
                self.assertEqual(len(inspection["warnings"]), 1)
                self.assertTrue(inspection["warnings"][0].startswith("no project evidence found"))

    def test_the_no_evidence_warning_is_not_raised_when_there_is_evidence_or_a_failure(self):
        for label, tree in {
            "manifest": {"package.json": package_json()},
            "configuration": {"tsconfig.json": "{}"},
            "compose": {"compose.yaml": COMPOSE_NO_PORTS},
            "registered stack": {"main.py": "import fastapi\n"},
        }.items():
            with self.subTest(case=label):
                self.assertEqual(self.inspect_tree(tree)["warnings"], [])
        broken = self.inspect_tree({"package.json": "{"})
        self.assertFalse(broken["ok"])
        self.assertEqual(broken["warnings"], [])

    def test_manifests_and_configs_are_listed_without_sensitive_files(self):
        inspection = self.inspect_tree(
            {
                "package.json": package_json(),
                "go.mod": "module x\n",
                "Cargo.toml": "",
                "pyproject.toml": "",
                "requirements.txt": "",
                "setup.py": "",
                "setup.cfg": "",
                "pom.xml": "",
                "build.gradle": "",
                "build.gradle.kts": "",
                "App.csproj": "",
                "compose.yaml": COMPOSE_NO_PORTS,
                "tsconfig.json": "{}",
                "Dockerfile": "FROM scratch\n",
                "Makefile": "",
                "Procfile": "web: node .\n",
                ".env.example": "KEY=\n",
                "vite.config.ts": "",
                ".env": "TOKEN=abc\n",
                "server.pem": "",
            }
        )
        manifests = {item["path"]: item["kind"] for item in inspection["manifests"]}
        configs = {item["path"]: item["kind"] for item in inspection["configs"]}
        self.assertEqual(manifests["package.json"], "package manifest")
        self.assertEqual(manifests["go.mod"], "Go module manifest")
        self.assertEqual(manifests["Cargo.toml"], "Rust package manifest")
        self.assertEqual(manifests["pyproject.toml"], "Python package manifest")
        self.assertEqual(manifests["requirements.txt"], "Python requirements manifest")
        self.assertEqual(manifests["pom.xml"], "Maven manifest")
        self.assertEqual(manifests["build.gradle.kts"], "Gradle manifest")
        self.assertEqual(manifests["App.csproj"], ".NET project manifest")
        self.assertEqual(manifests["compose.yaml"], "compose manifest")
        self.assertEqual(configs["tsconfig.json"], "TypeScript configuration")
        self.assertEqual(configs["Dockerfile"], "container configuration")
        self.assertEqual(configs["Makefile"], "build configuration")
        self.assertEqual(configs["Procfile"], "process configuration")
        self.assertEqual(configs[".env.example"], "environment template")
        self.assertEqual(configs["vite.config.ts"], "project configuration")
        self.assertNotIn("compose.yaml", configs)
        for sensitive in (".env", "server.pem"):
            self.assertNotIn(sensitive, manifests)
            self.assertNotIn(sensitive, configs)


class ToleranceTests(FixtureTreeCase):
    """Project traits that are unusual, not wrong, and hostile input that must not crash the inspector."""

    def test_a_utf8_byte_order_mark_is_tolerated_in_every_file_the_inspector_reads(self):
        bom = "\ufeff".encode("utf-8")
        tree = {
            "package.json": bom + package_json(dev={"vite": "^7"}, scripts={"dev": "vite"}).encode("utf-8"),
            "Makefile": bom + b"run:\n\tuvicorn app:app\n",
            "main.py": bom + b"from fastapi import FastAPI\n",
            "compose.yaml": bom + COMPOSE_PORTS.encode("utf-8"),
        }
        inspection = self.inspect_tree(tree, start=True)
        self.assertClean(inspection)
        self.assertEqual(slugs(inspection), ["python-fastapi", "vite-spa"])
        self.assertEqual([item["source"] for item in inspection["start_commands"]], ["package.json:scripts.dev"])
        makefile_only = self.inspect_tree({"Makefile": bom + b"run:\n\tuvicorn app:app\n"}, detect=False, start=True)
        self.assertEqual([item["source"] for item in makefile_only["start_commands"]], ["Makefile:run"])

    def test_windows_line_endings_are_tolerated(self):
        def crlf(text: str) -> bytes:
            return text.replace("\n", "\r\n").encode("utf-8")

        inspection = self.inspect_tree(
            {
                "package.json": crlf(json.dumps({"devDependencies": {"vite": "^7"}}, indent=2)),
                "Makefile": crlf("run:\n\tuvicorn app:app --reload\n"),
                "compose.yaml": crlf(COMPOSE_PORTS),
                "app.py": crlf("import fastapi\n"),
            },
            start=True,
        )
        self.assertClean(inspection)
        self.assertEqual(slugs(inspection), ["python-fastapi", "vite-spa"])
        makefile_only = self.inspect_tree({"Makefile": crlf("run:\n\tuvicorn app:app --reload\n")}, detect=False, start=True)
        self.assertEqual(makefile_only["start_commands"], [candidate("Makefile:run", "Makefile", "uvicorn app:app --reload")])

    def test_pathologically_nested_documents_are_reported_and_do_not_crash(self):
        nested = ("[" * 200_000 + "]" * 200_000).encode("utf-8")
        inspection = self.inspect_tree({"package.json": nested, "compose.yaml": nested})
        self.assertFalse(inspection["ok"])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("package.json: invalid JSON"))
        self.assertEqual(len(inspection["warnings"]), 1)
        self.assertTrue(inspection["warnings"][0].startswith("compose.yaml: not parsed"))

    def test_unexpected_shapes_inside_package_json_are_ignored_or_reported_not_fatal(self):
        odd = json.dumps(
            {"dependencies": ["next"], "devDependencies": None, "peerDependencies": "vite", "scripts": {"dev": "vite", "n": 1}}
        )
        inspection = self.inspect_tree({"package.json": odd}, start=True)
        self.assertEqual(slugs(inspection), ["vite-spa"])
        self.assertIn("package.json:scripts.n: command must be a string", inspection["errors"])
        self.assertEqual([item["source"] for item in inspection["start_commands"]], ["package.json:scripts.dev"])

    def test_a_project_root_that_cannot_be_resolved_is_an_error(self):
        class Unresolvable(type(Path())):
            def expanduser(self):
                raise OSError("no such working directory")

        report = check_runtime.check(self.catalog, project_root=Unresolvable("project"), detect_project=True)
        inspection = report["project_inspection"]
        self.assertEqual(inspection["errors"], ["project root cannot be inspected (no such working directory)"])
        self.assertFalse(inspection["ok"])
        self.assertFalse(report["ok"])
        self.assertEqual((inspection["stacks"], inspection["manifests"], inspection["warnings"]), ([], [], []))


if __name__ == "__main__":
    unittest.main()
