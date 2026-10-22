"""Start-command discovery through check_runtime.check(): where a project says how it starts.

``--detect-start-command`` records candidates and runs nothing. Every test writes
a small project tree and drives ``check()`` (``_runtime_fixtures``).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from _runtime_fixtures import (
    COMPOSE_PORTS,
    FixtureTreeCase,
    candidate,
    make_catalog,
    package_json,
    slugs,
)


class StartCommandTests(FixtureTreeCase):
    """--detect-start-command records where a project says how it starts, and runs nothing."""

    def starts(self, tree, **modes) -> list[dict[str, str]]:
        inspection = self.inspect_tree(tree, detect=False, start=True, **modes)
        self.assertClean(inspection)
        return inspection["start_commands"]

    def test_package_scripts_dev_then_start(self):
        tree = {"package.json": package_json(scripts={"start": "node server.js", "build": "vite build", "dev": "vite"})}
        self.assertEqual(
            self.starts(tree),
            [
                candidate("package.json:scripts.dev", "package.json", "vite"),
                candidate("package.json:scripts.start", "package.json", "node server.js"),
            ],
        )

    def test_only_dev_and_start_scripts_are_candidates(self):
        self.assertEqual(self.starts({"package.json": package_json(scripts={"build": "tsc", "test": "jest"})}), [])
        self.assertEqual(self.starts({"package.json": package_json(scripts={"dev": "  ", "start": ""})}), [])

    def test_every_package_in_a_workspace_contributes_in_path_order(self):
        tree = {
            "web/package.json": package_json(scripts={"start": "next start"}),
            "apps/api/package.json": package_json(scripts={"dev": "tsx watch src/index.ts"}),
        }
        self.assertEqual(
            self.starts(tree),
            [
                candidate("apps/api/package.json:scripts.dev", "apps/api/package.json", "tsx watch src/index.ts"),
                candidate("web/package.json:scripts.start", "web/package.json", "next start"),
            ],
        )

    def test_malformed_scripts_are_reported_and_the_rest_are_kept(self):
        inspection = self.inspect_tree(
            {"package.json": package_json(scripts={"dev": 5, "start": "node ."})}, detect=False, start=True
        )
        self.assertIn("package.json:scripts.dev: command must be a string", inspection["errors"])
        self.assertEqual(inspection["start_commands"], [candidate("package.json:scripts.start", "package.json", "node .")])
        self.assertFalse(inspection["ok"])
        inspection = self.inspect_tree({"package.json": '{"scripts": ["dev"]}'}, detect=False, start=True)
        self.assertIn("package.json: scripts must be an object", inspection["errors"])
        self.assertEqual(inspection["start_commands"], [])

    def test_a_null_scripts_field_is_a_package_without_scripts_in_every_mode(self):
        for modes in ({"detect": True}, {"detect": False, "start": True}, {"detect": True, "start": True}):
            with self.subTest(**modes):
                inspection = self.inspect_tree({"package.json": '{"scripts": null}'}, **modes)
                self.assertClean(inspection)
                self.assertEqual(inspection["start_commands"], [])

    def test_unreadable_package_manifests_are_errors(self):
        for label, text, message in (
            ("invalid json", '{"scripts": ', "package.json: invalid JSON at line 1"),
            ("not an object", "[1, 2]", "package.json: package manifest must be a JSON object"),
        ):
            with self.subTest(case=label):
                inspection = self.inspect_tree({"package.json": text}, detect=False, start=True)
                self.assertEqual(inspection["errors"], [message])
                self.assertFalse(inspection["ok"])

    def test_package_scripts_take_precedence_over_every_other_source(self):
        tree = {
            "package.json": package_json(scripts={"dev": "vite"}),
            "Makefile": "dev:\n\tpython app.py\n",
            "compose.yaml": COMPOSE_PORTS,
            "manage.py": "",
        }
        self.assertEqual(self.starts(tree), [candidate("package.json:scripts.dev", "package.json", "vite")])

    def test_makefile_targets_dev_then_run_then_serve(self):
        make = "serve:\n\tpython c.py\nrun:\n\tpython b.py\ndev:\n\tpython a.py\n"
        self.assertEqual(self.starts({"Makefile": make}), [candidate("Makefile:dev", "Makefile", "python a.py")])
        self.assertEqual(
            self.starts({"Makefile": "serve:\n\tpython c.py\nrun:\n\tpython b.py\n"}),
            [candidate("Makefile:run", "Makefile", "python b.py")],
        )
        self.assertEqual(
            self.starts({"Makefile": "serve:\n\tpython c.py\n"}), [candidate("Makefile:serve", "Makefile", "python c.py")]
        )

    def test_makefile_recipe_prefixes_and_inline_recipes(self):
        for label, make in {
            "silent": "dev:\n\t@python app.py\n",
            "ignore errors": "dev:\n\t-python app.py\n",
            "always run": "dev:\n\t+python app.py\n",
            "inline": "dev: ; python app.py\n",
            "spaces before the target": "  dev:\n\tpython app.py\n",
            "comment lines skipped": "dev:\n\t# start it\n\tpython app.py\n",
        }.items():
            with self.subTest(case=label):
                self.assertEqual(self.starts({"Makefile": make}), [candidate("Makefile:dev", "Makefile", "python app.py")])

    def test_a_makefile_recipe_that_only_starts_a_server_is_a_candidate(self):
        for command in ("fastapi dev src/service/api.py", "nest start", "ng serve", "python3 -m uvicorn app:app"):
            with self.subTest(command=command):
                self.assertEqual(
                    self.starts({"Makefile": f"dev:\n\t{command}\n"}), [candidate("Makefile:dev", "Makefile", command)]
                )

    def test_makefile_skips_recipes_that_start_nothing(self):
        self.assertEqual(self.starts({"Makefile": "dev:\n\t@echo hello\n\ttouch .stamp\n"}), [])
        self.assertEqual(
            self.starts({"Makefile": "dev:\n\t@echo hello\n\tnode server.js\n"}),
            [candidate("Makefile:dev", "Makefile", "node server.js")],
        )

    def test_makefile_target_delegates_to_its_prerequisites(self):
        make = "dev: serve\n\nserve: build\n\tuvicorn app:app\n\nbuild:\n\t@echo build\n"
        self.assertEqual(self.starts({"Makefile": make}), [candidate("Makefile:dev", "Makefile", "uvicorn app:app")])

    def test_makefile_prerequisite_cycles_terminate(self):
        self.assertEqual(self.starts({"Makefile": "dev: run\nrun: dev\n"}), [])

    def test_a_target_defined_twice_is_searched_in_every_definition(self):
        """A first `dev:` with nothing to start must not hide a later one that starts the app."""
        make = "dev: setup\n\t@echo starting\n\nsetup:\n\t@echo setup\n\ndev:\n\tpython -m http.server\n"
        self.assertEqual(
            self.starts({"Makefile": make}), [candidate("Makefile:dev", "Makefile", "python -m http.server")]
        )
        make = "run:\n\techo nothing\n\nrun:\n\tnode server.js\n"
        self.assertEqual(self.starts({"Makefile": make}), [candidate("Makefile:run", "Makefile", "node server.js")])

    def test_each_production_makefile_contributes_one_candidate(self):
        tree = {
            "Makefile": "dev:\n\tpython app.py\n",
            "services/api/Makefile": "run:\n\tgo run .\n",
            "docs/Makefile": "dev:\n\tsphinx-autobuild docs\n",
            "tests/Makefile": "dev:\n\tpython fixture.py\n",
        }
        self.assertEqual(
            self.starts(tree),
            [
                candidate("Makefile:dev", "Makefile", "python app.py"),
                candidate("services/api/Makefile:run", "services/api/Makefile", "go run ."),
            ],
        )

    def test_compose_services_without_other_sources(self):
        compose = (
            "services:\n"
            "  web:\n    image: node\n    command: npm start\n"
            "  db:\n    image: postgres\n"
            "  worker:\n    image: py\n    command: [\"python\", \"-m\", \"worker\"]\n"
            "  odd:\n    image: x\n    command: 7\n"
        )
        self.assertEqual(
            self.starts({"docker-compose.yml": compose}),
            [
                candidate("docker-compose.yml:services.db.command", "docker-compose.yml", "docker compose -f docker-compose.yml up db"),
                candidate("docker-compose.yml:services.odd.command", "docker-compose.yml", "docker compose -f docker-compose.yml up odd"),
                candidate("docker-compose.yml:services.web.command", "docker-compose.yml", "npm start"),
                candidate("docker-compose.yml:services.worker.command", "docker-compose.yml", "python -m worker"),
            ],
        )

    def test_the_first_compose_file_name_with_services_wins(self):
        tree = {
            "docker-compose.yml": "services:\n  b:\n    image: x\n",
            "compose.yml": "services:\n  a:\n    image: x\n",
        }
        self.assertEqual(
            self.starts(tree), [candidate("compose.yml:services.a.command", "compose.yml", "docker compose -f compose.yml up a")]
        )
        tree = {"compose.yaml": "version: '3'\n", "compose.yml": "services:\n  a:\n    image: x\n"}
        self.assertEqual([item["path"] for item in self.starts(tree)], ["compose.yml"])

    def test_makefile_wins_over_compose_and_compose_over_defaults(self):
        tree = {"Makefile": "dev:\n\tnode a.js\n", "compose.yaml": COMPOSE_PORTS, "manage.py": ""}
        self.assertEqual([item["source"] for item in self.starts(tree)], ["Makefile:dev"])
        tree = {"compose.yaml": COMPOSE_PORTS, "manage.py": ""}
        self.assertEqual([item["source"] for item in self.starts(tree)], ["compose.yaml:services.web.command"])

    def test_entrypoint_defaults(self):
        cases = {
            "django": ({"manage.py": ""}, candidate("manage.py:default", "manage.py", "python manage.py runserver")),
            "main.py": ({"main.py": "import fastapi\n"}, candidate("main.py:default", "main.py", "python main.py")),
            "app.py": ({"app.py": "import flask\n"}, candidate("app.py:default", "app.py", "python app.py")),
            "main.py without a web import loses to app.py": (
                {"main.py": "print(1)\n", "app.py": "import flask\n"},
                candidate("app.py:default", "app.py", "python app.py"),
            ),
            "go at the root": (
                {"go.mod": "module x\n", "main.go": "package main\nfunc main() {}\n"},
                candidate("go.mod:default", "go.mod", "go run ."),
            ),
            "go under cmd": (
                {"go.mod": "module x\n", "cmd/api/main.go": "package main\nfunc main() {}\n"},
                candidate("go.mod:default", "go.mod", "go run ./cmd/api"),
            ),
            "cargo single binary": (
                {"Cargo.toml": '[package]\nname = "svc"\n', "src/main.rs": "fn main() {}\n"},
                candidate("Cargo.toml:default", "Cargo.toml", "cargo run"),
            ),
        }
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.starts(tree), [expected])

    def test_entrypoint_defaults_that_the_project_does_not_have(self):
        for label, tree in {
            "python without a web import": {"main.py": "print(1)\n"},
            "go module without a main package": {"go.mod": "module x\n", "lib.go": "package lib\n"},
            "cargo library": {"Cargo.toml": '[package]\nname = "x"\n', "src/lib.rs": ""},
            "empty project": {"README.md": "hello\n"},
        }.items():
            with self.subTest(case=label):
                self.assertEqual(self.starts(tree), [])

    def test_only_the_first_entrypoint_default_is_reported(self):
        tree = {
            "manage.py": "",
            "go.mod": "module x\n",
            "main.go": "package main\nfunc main() {}\n",
            "Cargo.toml": '[package]\nname = "x"\n',
            "src/main.rs": "fn main() {}\n",
        }
        self.assertEqual([item["source"] for item in self.starts(tree)], ["manage.py:default"])
        del tree["manage.py"]
        self.assertEqual([item["source"] for item in self.starts(tree)], ["go.mod:default"])

    def test_cargo_start_command_names_the_binary_when_there_is_more_than_one(self):
        manifest = '[package]\nname = "svc"\n'
        cases = {
            "main and a bin": (
                {"Cargo.toml": manifest, "src/main.rs": "fn main() {}\n", "src/bin/tool.rs": "fn main() {}\n"},
                "cargo run --bin svc",
            ),
            "two bins": (
                {"Cargo.toml": manifest, "src/bin/a.rs": "fn main() {}\n", "src/bin/b.rs": "fn main() {}\n"},
                "cargo run --bin a",
            ),
            "directory bin": ({"Cargo.toml": manifest, "src/bin/tool/main.rs": "fn main() {}\n"}, "cargo run"),
            "default-run names a target": (
                {
                    "Cargo.toml": '[package]\nname = "svc"\ndefault-run = "tool"\n',
                    "src/main.rs": "fn main() {}\n",
                    "src/bin/tool.rs": "fn main() {}\n",
                },
                "cargo run",
            ),
            "declared bin": (
                {
                    "Cargo.toml": manifest + '\n[[bin]]\nname = "srv"\npath = "app/srv.rs"\n',
                    "app/srv.rs": "fn main() {}\n",
                    "src/main.rs": "fn main() {}\n",
                },
                "cargo run --bin svc",
            ),
        }
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual([item["command"] for item in self.starts(tree)], [expected])

    def test_invalid_cargo_manifest_is_reported_and_yields_no_candidate(self):
        inspection = self.inspect_tree(
            {"Cargo.toml": "[package\nname = ", "src/main.rs": "fn main() {}\n"}, detect=False, start=True
        )
        self.assertEqual(inspection["start_commands"], [])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("Cargo.toml: invalid TOML"))

    def test_java_defaults_need_spring_boot_evidence(self):
        boot_pom = "<parent><artifactId>spring-boot-starter-parent</artifactId></parent>"
        boot_gradle = "plugins { id 'org.springframework.boot' version '3.3.0' }"
        cases = {
            "boot pom": ({"pom.xml": boot_pom}, [candidate("pom.xml:default", "pom.xml", "mvn spring-boot:run")]),
            "boot gradle": (
                {"build.gradle": boot_gradle},
                [candidate("build.gradle:default", "build.gradle", "./gradlew bootRun")],
            ),
            "boot kotlin gradle": (
                {"build.gradle.kts": 'plugins { id("org.springframework.boot") }'},
                [candidate("build.gradle.kts:default", "build.gradle.kts", "./gradlew bootRun")],
            ),
            "camel-case version property": (
                {"build.gradle": "ext { springBootVersion = '3.3.0' }"},
                [candidate("build.gradle:default", "build.gradle", "./gradlew bootRun")],
            ),
            "plain maven library": ({"pom.xml": "<project><artifactId>lib</artifactId></project>"}, []),
            "plain gradle library": ({"build.gradle": "plugins { id 'java-library' }"}, []),
            "non-boot spring": ({"pom.xml": "<artifactId>spring-webmvc</artifactId>"}, []),
            "jetty without spring boot": ({"pom.xml": "<artifactId>jetty-server</artifactId>"}, []),
            "boot gradle behind a plain pom": (
                {"pom.xml": "<project/>", "build.gradle": boot_gradle},
                [candidate("build.gradle:default", "build.gradle", "./gradlew bootRun")],
            ),
            "maven wins when both are boot": (
                {"pom.xml": boot_pom, "build.gradle": boot_gradle},
                [candidate("pom.xml:default", "pom.xml", "mvn spring-boot:run")],
            ),
        }
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.starts(tree), expected)

    def test_a_project_with_no_start_evidence_warns_that_no_project_was_found(self):
        inspection = self.inspect_tree({"notes.txt": "hello\n"}, detect=False, start=True)
        self.assertEqual(inspection["start_commands"], [])
        self.assertEqual(len(inspection["warnings"]), 1)
        self.assertTrue(inspection["warnings"][0].startswith("no project evidence found"))
        self.assertTrue(inspection["ok"])

    def test_start_detection_never_loads_the_registry(self):
        with tempfile.TemporaryDirectory() as holder:
            catalog = make_catalog(Path(holder), overlays=False)
            inspection = self.inspect_tree(
                {"package.json": package_json(scripts={"dev": "vite"})}, detect=False, start=True, catalog=catalog
            )
        self.assertClean(inspection)
        self.assertEqual(len(inspection["start_commands"]), 1)


class ManifestReaderTests(FixtureTreeCase):
    """The language and container manifests the detector reads beyond package.json."""

    def starts(self, tree) -> list[dict[str, str]]:
        return self.inspect_tree(tree, detect=False, start=True)["start_commands"]

    def stacks_of(self, tree) -> list[str]:
        return slugs(self.inspect_tree(tree))

    def test_go_entrypoints_are_read_as_go_source(self):
        gin = "module x\n\nrequire github.com/gin-gonic/gin v1.10.0\n"
        cases = {
            "license block comment first": ("/*\n * Licensed.\n */\npackage main\n\nfunc main() {}\n", True),
            "spaced main declaration": ("package main\n\nfunc main ( ) { }\n", True),
            "escaped quote in a string": ('package main\n\nvar s = "a \\" b"\n\nfunc main() {}\n', True),
            "raw string before main": ("package main\n\nvar s = `text`\n\nfunc main() {}\n", True),
            "package clause only inside a raw string": ("package api\n\nvar s = `package main\nfunc main()`\n", False),
            "unterminated block comment hides the rest": ("/* package main\nfunc main() {}\n", False),
            "main function only inside a block comment": ("package main\n/* func main() {} */\n", False),
            "method named main": ("package main\n\nfunc (s S) main() {}\n", False),
        }
        for name, (source, detected) in cases.items():
            with self.subTest(case=name):
                found = self.stacks_of({"go.mod": gin, "main.go": source})
                self.assertEqual(found, ["go-gin"] if detected else [])

    def test_go_entrypoint_candidates_are_the_root_and_direct_cmd_directories(self):
        gin = "module x\n\nrequire github.com/gin-gonic/gin v1.10.0\n"
        main = "package main\n\nfunc main() {}\n"
        self.assertEqual(self.stacks_of({"go.mod": gin, "cmd/api/main.go": main}), ["go-gin"])
        self.assertEqual(self.stacks_of({"go.mod": gin, "cmd/main.go": main}), [])
        self.assertEqual(self.stacks_of({"go.mod": gin, "internal/app/main.go": main}), [])
        self.assertEqual(self.stacks_of({"go.mod": gin, "tests/main.go": main}), [])
        self.assertEqual(self.stacks_of({"go.mod": gin, "cmd/api/main_test.go": main}), [])

    def test_cargo_binary_declarations(self):
        manifest = '[package]\nname = "svc"\n'
        both = {"src/main.rs": "fn main() {}\n", "src/bin/tool.rs": "fn main() {}\n"}
        cases = {
            "declared path with a leading ./": (
                {"Cargo.toml": manifest + '\n[[bin]]\nname = "srv"\npath = "./app/srv.rs"\n', "app/srv.rs": "fn main() {}\n", "src/main.rs": "fn main() {}\n"},
                "cargo run --bin svc",
            ),
            "declared paths that leave the package are ignored": (
                {
                    "Cargo.toml": manifest
                    + '\n[[bin]]\nname = "a"\npath = "../outside.rs"\n\n[[bin]]\nname = "b"\npath = "/abs/b.rs"\n\n[[bin]]\nname = "c"\npath = "C:/c.rs"\n',
                    "src/main.rs": "fn main() {}\n",
                },
                "cargo run",
            ),
            "a bin with only a name maps to src/bin": (
                {"Cargo.toml": manifest + '\n[[bin]]\nname = "tool"\n', **both},
                "cargo run --bin svc",
            ),
            "a declared bin renames the default target": (
                {"Cargo.toml": manifest + '\n[[bin]]\nname = "srv"\npath = "src/main.rs"\n', **both},
                "cargo run --bin srv",
            ),
            "default-run that names no target": (
                {"Cargo.toml": '[package]\nname = "svc"\ndefault-run = "missing"\n', **both},
                "cargo run --bin svc",
            ),
            "a bin table that is not an array": (
                {"Cargo.toml": manifest + '\n[bin]\nname = "x"\n', "src/main.rs": "fn main() {}\n"},
                "cargo run",
            ),
            "a package with no name falls back to the directory name": (
                {"Cargo.toml": "[package]\n", **both},
                None,
            ),
        }
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name):
                commands = [item["command"] for item in self.starts(tree)]
                if expected is None:
                    self.assertEqual(len(commands), 1)
                    self.assertTrue(commands[0].startswith("cargo run --bin "))
                else:
                    self.assertEqual(commands, [expected])

    def test_compose_port_syntaxes(self):
        forms = {
            "long syntax": "    ports:\n      - target: 80\n        published: 8080\n",
            "bare string": '    ports: "8080:80"\n',
            "integer item": "    ports:\n      - 8080\n",
            "unquoted short mapping": "    ports:\n      - 8080:80\n",
            "bracketed ipv6 host": '    ports:\n      - "[::1]:8080:80"\n',
            "single mapping": "    ports:\n      target: 80\n",
        }
        for name, ports in forms.items():
            with self.subTest(syntax=name):
                inspection = self.inspect_tree({"compose.yaml": "services:\n  web:\n    image: x\n" + ports})
                self.assertClean(inspection)
                self.assertEqual(inspection["classification"], "container-orchestrated")
        for name, ports in {
            "no port at all": "    ports:\n      - published: 8080\n",
            "port zero": '    ports:\n      - "0:80"\n',
            "a number that is not a port": "    ports:\n      - 99999\n",
            "boolean": "    ports: true\n",
        }.items():
            with self.subTest(syntax=name):
                inspection = self.inspect_tree({"compose.yaml": "services:\n  web:\n    image: x\n" + ports})
                self.assertEqual(inspection["classification"], "library/CLI")

    def test_compose_services_that_are_not_mappings_are_ignored(self):
        inspection = self.inspect_tree({"compose.yaml": "services:\n  web: nginx\n  db:\n    image: x\n    ports:\n      - '5432:5432'\n"})
        self.assertEqual(inspection["classification"], "container-orchestrated")
        self.assertEqual(self.starts({"compose.yaml": "services:\n  web: nginx\n"}), [])
        self.assertEqual(self.starts({"compose.yaml": "version: '3'\n"}), [])

    def test_a_makefile_target_with_an_empty_inline_recipe_still_follows_its_prerequisites(self):
        make = "dev: serve ;\n\nserve:\n\tuvicorn app:app\n"
        self.assertEqual(self.starts({"Makefile": make}), [candidate("Makefile:dev", "Makefile", "uvicorn app:app")])


if __name__ == "__main__":
    unittest.main()
