"""Project classification through check_runtime.check(): frontend, backend, full-stack and the rest.

The label feeds commander's stack_lock. Package scripts, Makefile recipes and
compose files are read for what they run, so the tests write each source into a
small project tree and drive ``check()`` (``_runtime_fixtures``).
"""
from __future__ import annotations

import unittest

from _runtime_fixtures import (
    COMPOSE_NO_PORTS,
    COMPOSE_PORTS,
    FixtureTreeCase,
    package_json,
    slugs,
)

MAKE_FRONTEND = "dev:\n\tvite --host\n"
MAKE_BACKEND = "run:\n\tuvicorn app:app --reload\n"
GO_HTTP_MAIN = 'package main\n\nimport "net/http"\n\nfunc main() { http.ListenAndServe(":8080", nil) }\n'


class ClassificationTests(FixtureTreeCase):
    def classify(self, tree) -> dict:
        inspection = self.inspect_tree(tree)
        self.assertClean(inspection)
        return inspection

    def reasons(self, inspection: dict) -> list[str]:
        return [item["reason"] for item in inspection["classification_evidence"]]

    def test_classification_table(self):
        cases = {
            "compose publishing ports and nothing else": ({"compose.yaml": COMPOSE_PORTS}, "container-orchestrated"),
            "compose with no ports and nothing else": ({"compose.yaml": COMPOSE_NO_PORTS}, "library/CLI"),
            "makefile dev target runs vite": ({"Makefile": MAKE_FRONTEND}, "frontend-only"),
            "makefile run target runs uvicorn": ({"Makefile": MAKE_BACKEND}, "backend-only"),
            "makefile with both": ({"Makefile": MAKE_FRONTEND + "\n" + MAKE_BACKEND}, "full-stack"),
            "makefile with no runtime command": ({"Makefile": "dev:\n\t@echo hello\n"}, "library/CLI"),
            "root package with a backend framework": (
                {"package.json": package_json(dependencies={"express": "^5"})},
                "backend-only",
            ),
            "root package with a frontend framework": (
                {"package.json": package_json(dependencies={"react": "^19"})},
                "frontend-only",
            ),
            "root package with both": (
                {"package.json": package_json(dependencies={"react": "^19", "fastify": "^5"})},
                "full-stack",
            ),
            "root package with a server-rendering framework": (
                {"package.json": package_json(dependencies={"next": "^15"})},
                "full-stack",
            ),
            "root package whose script runs vite": (
                {"package.json": package_json(scripts={"dev": "vite"})},
                "frontend-only",
            ),
            "root package whose script serves with the angular cli": (
                {"package.json": package_json(scripts={"start": "ng serve"})},
                "frontend-only",
            ),
            "root package whose script starts a node server": (
                {"package.json": package_json(scripts={"start": "node server.js"})},
                "backend-only",
            ),
            "root package whose script starts uvicorn as a module": (
                {"package.json": package_json(scripts={"start": "python -m uvicorn app:app"})},
                "backend-only",
            ),
            "root package with no runtime signal": ({"package.json": package_json(dev={"prettier": "^3"})}, "library/CLI"),
            "django management script": ({"manage.py": "import os\n"}, "backend-only"),
            "fastapi entrypoint": ({"main.py": "from fastapi import FastAPI\n"}, "backend-only"),
            "http.server entrypoint": ({"app.py": "import http.server\n"}, "backend-only"),
            "python entrypoint with no web import": ({"main.py": "print('hi')\n"}, "library/CLI"),
            "go entrypoint serving http": ({"go.mod": "module x\n", "main.go": GO_HTTP_MAIN}, "backend-only"),
            "go entrypoint with no server": (
                {"go.mod": "module x\n", "main.go": "package main\n\nfunc main() {}\n"},
                "library/CLI",
            ),
            "cargo binary using axum": (
                {"Cargo.toml": '[package]\nname = "x"\n[dependencies]\naxum = "0.8"\n', "src/main.rs": "fn main() {}\n"},
                "backend-only",
            ),
            "cargo binary with no server": (
                {"Cargo.toml": '[package]\nname = "x"\n', "src/main.rs": "fn main() {}\n"},
                "library/CLI",
            ),
            "maven project using spring": (
                {"pom.xml": "<project><dependency>spring-boot-starter-web</dependency></project>"},
                "backend-only",
            ),
            "gradle project using jetty": ({"build.gradle": "dependencies { implementation 'jetty' }"}, "backend-only"),
            "kotlin gradle project with no server": ({"build.gradle.kts": "plugins { java }"}, "library/CLI"),
            "vite configuration with no package.json": ({"vite.config.ts": ""}, "frontend-only"),
            "angular configuration with no package.json": ({"angular.json": "{}"}, "frontend-only"),
        }
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(self.classify(tree)["classification"], expected)

    def test_a_project_with_no_signal_is_unclassified_and_says_so(self):
        inspection = self.classify({"notes.txt": "nothing here\n"})
        self.assertEqual(inspection["classification"], "library/CLI")
        self.assertEqual(inspection["ambiguities"], ["no supported runtime classification signal was found"])
        self.assertEqual(inspection["classification_evidence"], [])

    def test_a_manifest_with_no_web_signal_is_a_library_not_an_ambiguity(self):
        for tree in (
            {"package.json": package_json()},
            {"go.mod": "module x\n", "main.go": "package main\n\nfunc main() {}\n"},
            {"pom.xml": "<project/>"},
        ):
            with self.subTest(files=sorted(tree)):
                inspection = self.classify(tree)
                self.assertEqual(inspection["classification"], "library/CLI")
                self.assertEqual(inspection["ambiguities"], [])
                self.assertTrue(inspection["classification_evidence"])

    def test_evidence_names_the_file_behind_each_signal(self):
        cases = {
            "root package": (
                {"package.json": package_json(dependencies={"react": "^19"})},
                [("package.json", "root package.json")],
            ),
            "django": ({"manage.py": ""}, [("manage.py", "Django management entrypoint")]),
            "python web import": ({"app.py": "import flask\n"}, [("app.py", "Python web runtime import")]),
            "makefile": ({"Makefile": MAKE_FRONTEND}, [("Makefile", "Makefile runtime command")]),
            "compose": ({"compose.yaml": COMPOSE_PORTS}, [("compose.yaml", "compose services definition")]),
            "java": ({"pom.xml": "<project/>"}, [("pom.xml", "Java build manifest")]),
            "configuration only": (
                {"next.config.mjs": ""},
                [("next.config.mjs", "registered frontend stack evidence")],
            ),
            "go": (
                {"go.mod": "module x\n", "main.go": "package main\nfunc main() {}\n"},
                [("go.mod", "Go module manifest"), ("main.go", "Go executable entrypoint")],
            ),
            "rust": (
                {"Cargo.toml": '[package]\nname = "x"\n', "src/main.rs": "fn main() {}\n"},
                [("Cargo.toml", "Rust package manifest"), ("src/main.rs", "Rust executable entrypoint")],
            ),
        }
        for name, (tree, expected) in cases.items():
            with self.subTest(case=name):
                inspection = self.classify(tree)
                self.assertEqual(
                    [(item["path"], item["reason"]) for item in inspection["classification_evidence"]], expected
                )

    def test_root_tooling_manifest_does_not_hide_the_backend_beside_it(self):
        inspection = self.classify(
            {
                "package.json": package_json(dev={"prettier": "^3", "husky": "^9"}),
                "main.py": "from fastapi import FastAPI\n",
            }
        )
        self.assertEqual(slugs(inspection), ["python-fastapi"])
        self.assertEqual(inspection["classification"], "backend-only")
        self.assertEqual(self.reasons(inspection), ["root package.json", "Python web runtime import"])

    def test_frontend_bundler_beside_a_django_project_is_full_stack(self):
        inspection = self.classify(
            {
                "package.json": package_json(dev={"webpack": "^5"}, scripts={"build": "webpack"}),
                "manage.py": "import os\n",
            }
        )
        self.assertEqual(inspection["classification"], "full-stack")

    def test_a_root_go_backend_beside_a_nested_frontend_is_full_stack(self):
        inspection = self.classify(
            {
                "go.mod": "module x\n",
                "main.go": GO_HTTP_MAIN,
                "web/package.json": package_json(dependencies={"react": "^19"}),
            }
        )
        self.assertEqual(inspection["classification"], "full-stack")
        self.assertEqual(
            self.reasons(inspection),
            ["package.json service manifest", "Go module manifest", "Go executable entrypoint"],
        )

    def test_a_published_compose_port_does_not_outrank_the_application_evidence(self):
        database_only = "services:\n  db:\n    image: postgres:16\n    ports:\n      - \"5432:5432\"\n"
        inspection = self.classify(
            {
                "compose.yaml": database_only,
                "package.json": package_json(dependencies={"express": "^5"}),
            }
        )
        self.assertEqual(inspection["classification"], "backend-only")
        self.assertEqual(self.reasons(inspection), ["compose services definition", "root package.json"])

    def test_compose_publishing_ports_decides_when_the_application_says_nothing(self):
        inspection = self.classify({"compose.yaml": COMPOSE_PORTS, "package.json": package_json()})
        self.assertEqual(inspection["classification"], "container-orchestrated")
        self.assertEqual(inspection["ambiguities"], [])

    def test_compose_without_ports_is_recorded_as_an_ambiguity(self):
        inspection = self.classify({"compose.yaml": COMPOSE_NO_PORTS})
        self.assertEqual(
            inspection["ambiguities"],
            [
                "compose services were found without a ports mapping",
                "no supported runtime classification signal was found",
            ],
        )

    def test_compose_port_forms(self):
        published = {
            "short string": '"3000:3000"',
            "container port only": '"3000"',
            "with protocol": '"53:53/udp"',
            "range": '"3000-3005:3000-3005"',
            "with host address": '"127.0.0.1:8000:8000"',
        }
        for name, port in published.items():
            with self.subTest(port=name):
                compose = f"services:\n  web:\n    image: x\n    ports:\n      - {port}\n"
                self.assertEqual(self.classify({"compose.yml": compose})["classification"], "container-orchestrated")
        for name, port in {"invalid protocol": '"3000:3000/ftp"', "out of range": '"70000:80"', "text": '"web:api"'}.items():
            with self.subTest(port=name):
                compose = f"services:\n  web:\n    image: x\n    ports:\n      - {port}\n"
                self.assertEqual(self.classify({"compose.yml": compose})["classification"], "library/CLI")

    def test_workspace_of_packages_is_classified_from_all_of_them(self):
        web = package_json(dependencies={"react": "^19"})
        api = package_json(dependencies={"express": "^5"})
        both = self.classify({"apps/web/package.json": web, "apps/api/package.json": api})
        self.assertEqual(both["classification"], "full-stack")
        self.assertEqual(
            [(item["path"], item["reason"]) for item in both["classification_evidence"]],
            [
                ("apps/api/package.json", "package.json service manifest"),
                ("apps/web/package.json", "package.json service manifest"),
            ],
        )
        self.assertEqual(self.classify({"apps/web/package.json": web})["classification"], "frontend-only")
        self.assertEqual(self.classify({"apps/api/package.json": api})["classification"], "backend-only")
        root_and_nested = self.classify({"package.json": web, "services/api/package.json": api})
        self.assertEqual(root_and_nested["classification"], "full-stack")
        self.assertEqual(
            [item["reason"] for item in root_and_nested["classification_evidence"]],
            ["package.json service manifest", "package.json service manifest"],
        )

    def test_frontend_and_backend_signals_from_different_sources_combine(self):
        inspection = self.classify({"Makefile": MAKE_FRONTEND, "main.py": "import fastapi\n"})
        self.assertEqual(inspection["classification"], "full-stack")

    def test_a_server_command_classifies_the_same_in_a_package_script_and_a_makefile_recipe(self):
        """A recipe whose only command starts the server is how the project runs, as the same script is."""
        for command, expected in (
            ("fastapi dev src/service/api.py", "backend-only"),
            ("nest start", "backend-only"),
            ("ng serve", "frontend-only"),
            ("python3 -m uvicorn app:app", "backend-only"),
        ):
            for source, tree in (
                ("package script", {"package.json": package_json(scripts={"dev": command})}),
                ("Makefile recipe", {"Makefile": f"dev:\n\t{command}\n"}),
            ):
                with self.subTest(command=command, source=source):
                    self.assertEqual(self.classify(tree)["classification"], expected)

    def test_a_fastapi_service_started_from_a_makefile_is_a_backend(self):
        inspection = self.classify(
            {
                "pyproject.toml": '[project]\nname = "svc"\ndependencies = ["fastapi"]\n',
                "src/service/api.py": "from fastapi import FastAPI\n\napp = FastAPI()\n",
                "Makefile": "dev:\n\tfastapi dev src/service/api.py\n",
            }
        )
        self.assertEqual(inspection["classification"], "backend-only")
        self.assertEqual(self.reasons(inspection), ["Makefile runtime command"])
        self.assertEqual(inspection["ambiguities"], [])

    def test_a_compose_file_the_reader_cannot_parse_is_a_warning_not_a_failure(self):
        compose = "x-app: &app\n  image: node\nservices:\n  web:\n    <<: *app\n    ports:\n      - \"3000:3000\"\n"
        inspection = self.inspect_tree(
            {"compose.yaml": compose, "package.json": package_json(dependencies={"react": "^19"})}
        )
        self.assertClean(inspection)
        self.assertEqual(inspection["classification"], "frontend-only")
        self.assertEqual(len(inspection["warnings"]), 1)
        self.assertTrue(inspection["warnings"][0].startswith("compose.yaml: not parsed"))


class ScriptFormTests(FixtureTreeCase):
    """How the inspector reads what a package script actually runs."""

    RUNS_VITE = (
        "vite",
        "vite build --mode production",
        "./node_modules/.bin/vite",
        "npx vite",
        "npx --yes vite",
        "bunx vite dev",
        "bun run vite",
        "pnpm exec vite",
        "pnpm dlx vite",
        "yarn dlx vite",
        "npm exec vite",
        "npm exec -- vite",
        "pnpm --filter web exec vite",
        "pnpm -C web exec vite",
        "npm --prefix web exec vite",
        "yarn --cwd web dlx vite",
        "env NODE_ENV=production vite",
        "env -u DEBUG vite",
        "env -S 'vite --host'",
        "env --split-string=vite",
        "NODE_ENV=production vite",
        "FOO=1 BAR=2 vite",
        "exec vite",
        "exec -a renamed vite",
        "command vite",
        "rimraf dist && vite build",
        "cd web; vite",
        "prebuild\nvite",
    )
    NOT_VITE = (
        "vitest",
        "vite-node script.ts",
        "echo vite",
        "command -v vite",
        "npx --version",
        "npx -v vite",
        "npm run build",
        "npm install vite",
        "pnpm --help",
        "pnpm exec --help vite",
        "cat vite.config.js",
        "echo 'a; vite'",
    )

    def stacks_from_script(self, command: str) -> list[str]:
        return slugs(self.inspect_tree({"package.json": package_json(scripts={"dev": command})}))

    def label_from_script(self, command: str) -> str:
        return self.inspect_tree({"package.json": package_json(scripts={"start": command})})["classification"]

    def test_scripts_that_run_vite_are_vite_evidence(self):
        for command in self.RUNS_VITE:
            with self.subTest(script=command):
                self.assertEqual(self.stacks_from_script(command), ["vite-spa"])

    def test_scripts_that_only_mention_vite_are_not(self):
        for command in self.NOT_VITE:
            with self.subTest(script=command):
                self.assertEqual(self.stacks_from_script(command), [])

    def test_a_script_the_shell_reader_cannot_tokenise_is_skipped_not_fatal(self):
        inspection = self.inspect_tree({"package.json": package_json(scripts={"dev": "vite 'unterminated"})})
        self.assertClean(inspection)
        self.assertEqual(inspection["stacks"], [])

    def test_frontend_tool_scripts_classify_as_frontend(self):
        for command in ("vite", "next dev", "astro dev", "nuxt dev", "webpack serve", "parcel index.html", "ng serve", "npx ng serve"):
            with self.subTest(script=command):
                self.assertEqual(self.label_from_script(command), "frontend-only")

    def test_backend_scripts_classify_as_backend(self):
        backends = (
            "uvicorn app:app",
            "gunicorn app:app",
            "flask run",
            "nest start",
            "python -m uvicorn app:app",
            "python3 -m gunicorn app:app",
            "py -m flask run",
            "node server.js",
            "node --inspect server.js",
            "node -r ts-node/register server.ts",
            "node src/api.js",
            "node --watch api-server.mjs",
            "node ./bin/my_server.js",
            "env PORT=3000 node server.js",
        )
        for command in backends:
            with self.subTest(script=command):
                self.assertEqual(self.label_from_script(command), "backend-only")

    def test_scripts_that_do_not_name_a_server_are_not_backends(self):
        for command in (
            "node index.js",
            "node dist/main.js",
            "node -e \"require('x')\"",
            "node --require ./setup.js app.js",
            "nodemon server.js",
            "ts-node server.ts",
            "python app.py",
            "python -m http.server",
            "tsc --build",
        ):
            with self.subTest(script=command):
                self.assertEqual(self.label_from_script(command), "library/CLI")


if __name__ == "__main__":
    unittest.main()
