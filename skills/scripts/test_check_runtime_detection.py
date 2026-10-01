"""Behavioural fixture-tree tests for skills/scripts/check_runtime.py.

Every test writes a small project tree into a temporary directory and drives the
public entry points, ``check()`` and the command line, so the suite pins what the
inspector reports and not how its functions are arranged. That is what lets the
module be reorganised later without losing its safety net. Two private names are
touched on purpose and are the ones a split must keep importable from
``check_runtime``: ``_redact`` and ``_redact_value``.

The catalog (``runtime-manifest.yaml`` plus ``tech-stacks/``) is a temporary copy
of the real registry and overlays with a minimal manifest, so the tests verify the
real overlay digests without reading the catalog's own runtime manifest.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent
SCRIPT = SCRIPTS / "check_runtime.py"
CATALOG_SOURCE = SCRIPTS.parent

import check_runtime  # noqa: E402
from data_formats import load_data  # noqa: E402

REGISTRY = load_data(CATALOG_SOURCE / "tech-stacks" / "registry.yaml")
REGISTERED_SLUGS = sorted(row["slug"] for row in REGISTRY["overlays"])
BASE_MANIFEST = {
    "schema_version": 1,
    "kind": "supremeteam-runtime-manifest",
    "runtime": {"python": {"minimum": "3.9", "optional_dependencies": []}},
    "launchers": {"linux": "python3"},
}


def write_tree(root: Path, tree: dict[str, str | bytes]) -> None:
    for relative, content in tree.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8", newline="\n")


def make_catalog(parent: Path, *, manifest: object = None, registry: object = None, overlays: bool = True) -> Path:
    """A catalog root holding a manifest and a copy of the real tech-stack overlays."""
    catalog = parent / "catalog"
    catalog.mkdir()
    (catalog / "runtime-manifest.yaml").write_text(
        json.dumps(BASE_MANIFEST if manifest is None else manifest), encoding="utf-8"
    )
    if overlays:
        shutil.copytree(CATALOG_SOURCE / "tech-stacks", catalog / "tech-stacks")
    if registry is not None:
        (catalog / "tech-stacks").mkdir(exist_ok=True)
        (catalog / "tech-stacks" / "registry.yaml").write_text(json.dumps(registry), encoding="utf-8")
    return catalog


def package_json(*, dependencies=None, dev=None, scripts=None, **extra) -> str:
    data: dict = {"name": "fixture", **extra}
    if dependencies:
        data["dependencies"] = dependencies
    if dev:
        data["devDependencies"] = dev
    if scripts:
        data["scripts"] = scripts
    return json.dumps(data)


def slugs(inspection: dict) -> list[str]:
    return [stack["slug"] for stack in inspection["stacks"]]


def evidence(inspection: dict, slug: str) -> list[dict[str, str]]:
    return next(stack["evidence"] for stack in inspection["stacks"] if stack["slug"] == slug)


class FixtureTreeCase(unittest.TestCase):
    catalog: Path

    @classmethod
    def setUpClass(cls) -> None:
        holder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(holder.cleanup)
        cls.catalog = make_catalog(Path(holder.name))

    def project(self, tree: dict[str, str | bytes]) -> Path:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = Path(holder.name).resolve()
        write_tree(root, tree)
        return root

    def check_root(self, root: Path, *, detect=True, start=False, scaffold=False, catalog=None) -> dict:
        return check_runtime.check(
            catalog or self.catalog,
            project_root=root,
            detect_project=detect,
            detect_start_command=start,
            scan_scaffold=scaffold,
        )

    def report(self, tree, **modes) -> dict:
        return self.check_root(self.project(tree), **modes)

    def inspect_tree(self, tree, **modes) -> dict:
        return self.report(tree, **modes)["project_inspection"]

    def assertClean(self, inspection: dict) -> None:
        self.assertEqual(inspection["errors"], [])
        self.assertTrue(inspection["ok"])


#: One minimal project per registered stack: the smallest tree the detector accepts,
#: and the evidence rows it must report for it.
STACK_FIXTURES: dict[str, tuple[dict[str, str], list[dict[str, str]]]] = {
    "angular": (
        {"package.json": package_json(dependencies={"@angular/core": "^19.0.0"})},
        [{"path": "package.json", "reason": "package.json or angular.json contains Angular evidence"}],
    ),
    "astro": (
        {"package.json": package_json(dependencies={"astro": "^5.0.0"})},
        [{"path": "package.json", "reason": "package.json or Astro configuration contains Astro evidence"}],
    ),
    "bun-typescript": (
        {"bun.lock": "", "tsconfig.json": "{}"},
        [{"path": "bun.lock", "reason": "Bun lock or configuration with TypeScript evidence"}],
    ),
    "deno-typescript": (
        {"deno.json": "{}"},
        [{"path": "deno.json", "reason": "Deno configuration"}],
    ),
    "dotnet-aspnet": (
        {"Api.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"></Project>'},
        [{"path": "Api.csproj", "reason": ".NET web project manifest"}],
    ),
    "go-gin": (
        {
            "go.mod": "module example.com/api\n\nrequire github.com/gin-gonic/gin v1.10.0\n",
            "main.go": "package main\n\nfunc main() {}\n",
        },
        [
            {"path": "go.mod", "reason": "Go module declares Gin"},
            {"path": "main.go", "reason": "Go executable entrypoint"},
        ],
    ),
    "node-typescript": (
        {"package.json": package_json(dev={"typescript": "^5.0.0"}), "tsconfig.json": "{}"},
        [{"path": "package.json", "reason": "TypeScript package and source evidence"}],
    ),
    "python-fastapi": (
        {"main.py": "from fastapi import FastAPI\n\napp = FastAPI()\n"},
        [{"path": "main.py", "reason": "Python web runtime import evidence"}],
    ),
    "react-nextjs": (
        {"package.json": package_json(dependencies={"next": "^15.0.0", "react": "^19.0.0"})},
        [{"path": "package.json", "reason": "package.json or Next.js configuration contains Next.js evidence"}],
    ),
    "react-tanstack": (
        {"package.json": package_json(dependencies={"@tanstack/react-start": "^1.0.0"})},
        [{"path": "package.json", "reason": "package.json contains TanStack Start evidence"}],
    ),
    "rust-axum": (
        {
            "Cargo.toml": '[package]\nname = "api"\n\n[dependencies]\naxum = "0.8"\n',
            "src/main.rs": "fn main() {}\n",
        },
        [
            {"path": "Cargo.toml", "reason": "Cargo manifest declares Axum"},
            {"path": "src/main.rs", "reason": "Rust executable entrypoint"},
        ],
    ),
    "svelte-sveltekit": (
        {"package.json": package_json(dev={"@sveltejs/kit": "^2.0.0"})},
        [{"path": "package.json", "reason": "package.json or Svelte configuration contains SvelteKit evidence"}],
    ),
    "vite-spa": (
        {"package.json": package_json(dev={"vite": "^7.0.0"})},
        [{"path": "package.json", "reason": "package.json contains Vite evidence"}],
    ),
    "vue-nuxt": (
        {"package.json": package_json(dependencies={"nuxt": "^3.14.0"})},
        [{"path": "package.json", "reason": "package.json or Nuxt configuration contains Nuxt evidence"}],
    ),
}


class RegisteredStackTests(FixtureTreeCase):
    def test_every_registered_stack_has_a_detection_fixture(self):
        """A fifteenth overlay needs detector code; this fails until it has a fixture."""
        self.assertEqual(sorted(STACK_FIXTURES), REGISTERED_SLUGS)

    def test_each_registered_stack_is_detected_with_its_evidence(self):
        rows = {row["slug"]: row for row in REGISTRY["overlays"]}
        for slug, (tree, expected) in STACK_FIXTURES.items():
            with self.subTest(stack=slug):
                inspection = self.inspect_tree(tree)
                self.assertClean(inspection)
                self.assertEqual(slugs(inspection), [slug])
                self.assertEqual(evidence(inspection, slug), expected)
                stack = inspection["stacks"][0]
                self.assertEqual(stack["framework"], rows[slug]["framework"])
                self.assertEqual(stack["versions"], rows[slug]["versions"])

    def test_detection_does_not_run_without_the_flag(self):
        inspection = self.inspect_tree(STACK_FIXTURES["vite-spa"][0], detect=False, start=True)
        self.assertEqual(inspection["stacks"], [])
        self.assertIsNone(inspection["classification"])

    def test_configuration_files_alone_detect_the_framework_stacks(self):
        cases = {
            "react-nextjs": "next.config.mjs",
            "angular": "angular.json",
            "astro": "astro.config.mjs",
            "svelte-sveltekit": "svelte.config.js",
            "vue-nuxt": "nuxt.config.ts",
            "vite-spa": "vite.config.ts",
        }
        for slug, config in cases.items():
            with self.subTest(stack=slug):
                inspection = self.inspect_tree({config: "export default {}\n"})
                self.assertClean(inspection)
                self.assertEqual(slugs(inspection), [slug])
                self.assertEqual([item["path"] for item in evidence(inspection, slug)], [config])
                self.assertIn(config, [item["path"] for item in inspection["configs"]])

    def test_vite_evidence_comes_from_dependency_script_or_configuration(self):
        for label, tree in {
            "devDependency": {"package.json": package_json(dev={"vite": "^7"})},
            "dependency": {"package.json": package_json(dependencies={"vite": "^7"})},
            "script": {"package.json": package_json(scripts={"dev": "vite --host"})},
        }.items():
            with self.subTest(via=label):
                inspection = self.inspect_tree(tree)
                self.assertEqual(evidence(inspection, "vite-spa"), STACK_FIXTURES["vite-spa"][1])
        both = self.inspect_tree({"package.json": package_json(dev={"vite": "^7"}), "vite.config.ts": ""})
        self.assertEqual(
            evidence(both, "vite-spa"),
            [
                {"path": "package.json", "reason": "package.json contains Vite evidence"},
                {"path": "vite.config.ts", "reason": "Vite project configuration"},
            ],
        )

    def test_tanstack_start_is_detected_by_either_package_name(self):
        for package in ("@tanstack/react-start", "@tanstack/start"):
            with self.subTest(package=package):
                inspection = self.inspect_tree(
                    {"package.json": package_json(dependencies={package: "^1", "react": "^19"}, dev={"vite": "^7"})}
                )
                self.assertClean(inspection)
                # The Start overlay pins Vite, so the SPA overlay is not also a lock candidate.
                self.assertEqual(slugs(inspection), ["react-tanstack"])
        self.assertEqual(
            slugs(self.inspect_tree({"package.json": package_json(dependencies={"@tanstack/solid-start": "^1"})})),
            [],
        )

    def test_vite_spa_survives_beside_tanstack_start_in_a_sibling_package(self):
        inspection = self.inspect_tree(
            {
                "apps/site/package.json": package_json(dependencies={"@tanstack/react-start": "^1"}, dev={"vite": "^7"}),
                "apps/site/vite.config.ts": "",
                "apps/admin/package.json": package_json(dev={"vite": "^7"}),
            }
        )
        self.assertEqual(slugs(inspection), ["react-tanstack", "vite-spa"])
        self.assertEqual([item["path"] for item in evidence(inspection, "vite-spa")], ["apps/admin/package.json"])

    def test_dependency_names_match_case_insensitively_across_all_dependency_fields(self):
        for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            with self.subTest(field=field):
                manifest = json.dumps({"name": "x", field: {"Next": "^15"}})
                self.assertEqual(slugs(self.inspect_tree({"package.json": manifest})), ["react-nextjs"])

    def test_node_typescript_needs_a_tsconfig_and_yields_to_frontend_stacks(self):
        no_tsconfig = self.inspect_tree({"package.json": package_json(dev={"typescript": "^5"})})
        self.assertEqual(slugs(no_tsconfig), [])
        by_source = self.inspect_tree(
            {"package.json": package_json(), "tsconfig.json": "{}", "src/index.ts": "export {}\n"}
        )
        self.assertEqual(slugs(by_source), ["node-typescript"])
        with_frontend = self.inspect_tree(
            {
                "package.json": package_json(dependencies={"next": "^15"}, dev={"typescript": "^5"}),
                "tsconfig.json": "{}",
            }
        )
        self.assertEqual(slugs(with_frontend), ["react-nextjs"])
        no_package = self.inspect_tree({"tsconfig.json": "{}", "src/index.ts": "export {}\n"})
        self.assertEqual(slugs(no_package), [])

    def test_bun_typescript_needs_a_bun_marker_and_typescript_evidence(self):
        for marker in ("bun.lock", "bun.lockb", "bunfig.toml"):
            with self.subTest(marker=marker):
                inspection = self.inspect_tree({marker: "", "src/server.ts": "export {}\n"})
                self.assertEqual(slugs(inspection), ["bun-typescript"])
                self.assertEqual(evidence(inspection, "bun-typescript")[0]["path"], marker)
        self.assertEqual(slugs(self.inspect_tree({"bun.lock": ""})), [])
        self.assertEqual(slugs(self.inspect_tree({"tsconfig.json": "{}"})), [])

    def test_deno_configuration_variants(self):
        for name in ("deno.json", "deno.jsonc"):
            with self.subTest(name=name):
                self.assertEqual(slugs(self.inspect_tree({name: "{}"})), ["deno-typescript"])

    def test_python_web_stack_needs_a_fastapi_or_starlette_import(self):
        for source in ("import fastapi\n", "from starlette.applications import Starlette\n"):
            with self.subTest(source=source):
                self.assertEqual(slugs(self.inspect_tree({"app.py": source})), ["python-fastapi"])
        for source in ("import flask\n", "print('hello')\n", "def broken(:\n"):
            with self.subTest(source=source):
                self.assertEqual(slugs(self.inspect_tree({"main.py": source})), [])

    def test_go_gin_needs_a_main_package_with_a_main_function(self):
        gin_mod = "module x\n\nrequire github.com/gin-gonic/gin v1.10.0\n"
        entry = "package main\n\nfunc main() {}\n"
        self.assertEqual(slugs(self.inspect_tree({"go.mod": gin_mod, "main.go": entry})), ["go-gin"])
        self.assertEqual(
            evidence(self.inspect_tree({"go.mod": gin_mod, "cmd/api/main.go": entry}), "go-gin"),
            [
                {"path": "cmd/api/main.go", "reason": "Go executable entrypoint"},
                {"path": "go.mod", "reason": "Go module declares Gin"},
            ],
        )
        for label, tree in {
            "library package": {"go.mod": gin_mod, "main.go": "package api\n\nfunc main() {}\n"},
            "no main function": {"go.mod": gin_mod, "main.go": "package main\n"},
            "main only in a comment": {"go.mod": gin_mod, "main.go": "// package main\n// func main() {}\n"},
            "main only in a string": {"go.mod": gin_mod, "main.go": 'package api\nvar s = "package main func main()"\n'},
            "no gin": {"go.mod": "module x\n", "main.go": entry},
            "no go.mod": {"main.go": entry},
            "nested entrypoint too deep": {"go.mod": gin_mod, "cmd/a/b/main.go": entry},
        }.items():
            with self.subTest(case=label):
                self.assertEqual(slugs(self.inspect_tree(tree)), [])

    def test_rust_axum_needs_a_binary_target_declared_or_conventional(self):
        manifest = '[package]\nname = "svc"\n\n[dependencies]\naxum = "0.8"\n'
        by_convention = self.inspect_tree({"Cargo.toml": manifest, "src/bin/worker.rs": "fn main() {}\n"})
        self.assertEqual(slugs(by_convention), ["rust-axum"])
        self.assertEqual(evidence(by_convention, "rust-axum")[1]["path"], "src/bin/worker.rs")
        declared = self.inspect_tree(
            {"Cargo.toml": manifest + '\n[[bin]]\nname = "svc"\npath = "app/entry.rs"\n', "app/entry.rs": "fn main() {}\n"}
        )
        self.assertEqual(evidence(declared, "rust-axum")[1]["path"], "app/entry.rs")
        self.assertEqual(slugs(self.inspect_tree({"Cargo.toml": manifest, "src/lib.rs": ""})), [])
        no_axum = self.inspect_tree({"Cargo.toml": '[package]\nname = "svc"\n', "src/main.rs": "fn main() {}\n"})
        self.assertEqual(slugs(no_axum), [])

    def test_dotnet_stack_needs_aspnet_evidence_in_a_project_file(self):
        for name, body in {
            "Web.csproj": '<Project Sdk="Microsoft.NET.Sdk.Web"/>',
            "Api.fsproj": "<Project><ItemGroup><PackageReference Include='Microsoft.AspNetCore.App'/></ItemGroup></Project>",
            "Old.vbproj": "<Project>AspNetCore</Project>",
        }.items():
            with self.subTest(project=name):
                self.assertEqual(slugs(self.inspect_tree({name: body})), ["dotnet-aspnet"])
        self.assertEqual(slugs(self.inspect_tree({"Lib.csproj": '<Project Sdk="Microsoft.NET.Sdk"/>'})), [])

    def test_several_stacks_at_one_root_are_all_reported_in_slug_order(self):
        inspection = self.inspect_tree(
            {
                "package.json": package_json(dev={"vite": "^7"}),
                "deno.json": "{}",
                "main.py": "import fastapi\n",
            }
        )
        self.assertClean(inspection)
        self.assertEqual(slugs(inspection), ["deno-typescript", "python-fastapi", "vite-spa"])

    def test_evidence_rows_are_deduplicated_and_sorted(self):
        inspection = self.inspect_tree(
            {
                "package.json": package_json(dev={"vite": "^7"}),
                "vite.config.ts": "",
                "vite.config.js": "",
            }
        )
        self.assertEqual(
            evidence(inspection, "vite-spa"),
            [
                {"path": "package.json", "reason": "package.json contains Vite evidence"},
                {"path": "vite.config.js", "reason": "Vite project configuration"},
                {"path": "vite.config.ts", "reason": "Vite project configuration"},
            ],
        )

    def test_only_production_files_count_as_evidence(self):
        ignored = {
            "docs/site/next.config.js": "",
            "examples/demo/package.json": package_json(dependencies={"next": "^15"}),
            "tests/fixtures/vite.config.ts": "",
            "test/app/angular.json": "{}",
            "dist/astro.config.mjs": "",
            "build/nuxt.config.ts": "",
            "vendor/svelte.config.js": "",
            "README.md": "next.config.js\n",
        }
        inspection = self.inspect_tree(ignored)
        self.assertEqual(slugs(inspection), [])
        self.assertEqual(inspection["classification"], "library/CLI")

    def test_dependency_and_cache_directories_are_never_entered(self):
        inspection = self.inspect_tree(
            {
                "node_modules/left-pad/package.json": package_json(dependencies={"next": "^15"}),
                ".venv/lib/main.py": "import fastapi\n",
                "target/debug/build/Cargo.toml": "",
                "__pycache__/main.py": "import fastapi\n",
                ".git/hooks/deno.json": "{}",
            }
        )
        self.assertEqual(slugs(inspection), [])
        self.assertEqual(inspection["manifests"], [])

    def test_unregistered_stack_is_an_error_not_a_silent_omission(self):
        registry = copy.deepcopy(REGISTRY)
        registry["overlays"] = [row for row in registry["overlays"] if row["slug"] != "vite-spa"]
        with tempfile.TemporaryDirectory() as holder:
            catalog = make_catalog(Path(holder), registry=registry)
            inspection = self.inspect_tree(STACK_FIXTURES["vite-spa"][0], catalog=catalog)
        self.assertEqual(slugs(inspection), [])
        self.assertIn("detected stack vite-spa has no registry entry", inspection["errors"])
        self.assertFalse(inspection["ok"])


class NestedPackageTests(FixtureTreeCase):
    """A repository whose only package.json files are nested still has a root."""

    GIN_MOD = "module example.com/api\n\nrequire github.com/gin-gonic/gin v1.10.0\n"
    GIN_MAIN = 'package main\n\nimport "github.com/gin-gonic/gin"\n\nfunc main() { gin.Default() }\n'

    def test_root_backend_evidence_survives_a_nested_package_json(self):
        inspection = self.inspect_tree(
            {
                "go.mod": self.GIN_MOD,
                "main.go": self.GIN_MAIN,
                "web/package.json": package_json(dev={"vite": "^7"}),
            }
        )
        self.assertClean(inspection)
        self.assertEqual(slugs(inspection), ["go-gin", "vite-spa"])
        self.assertEqual(
            evidence(inspection, "go-gin"),
            [
                {"path": "go.mod", "reason": "Go module declares Gin"},
                {"path": "main.go", "reason": "Go executable entrypoint"},
            ],
        )
        self.assertEqual(
            evidence(inspection, "vite-spa"),
            [{"path": "web/package.json", "reason": "package.json contains Vite evidence"}],
        )
        self.assertEqual(inspection["classification"], "full-stack")

    def test_each_root_level_stack_is_found_beside_a_nested_package(self):
        nested = {"web/package.json": package_json(dev={"vite": "^7"})}
        for slug, (tree, _) in STACK_FIXTURES.items():
            if slug in {"vite-spa", "node-typescript"} or "package.json" in tree:
                continue
            with self.subTest(root_stack=slug):
                inspection = self.inspect_tree({**tree, **nested})
                self.assertClean(inspection)
                self.assertEqual(slugs(inspection), sorted([slug, "vite-spa"]))

    def test_nested_packages_do_not_lend_their_configuration_to_the_root_scope(self):
        inspection = self.inspect_tree(
            {
                "go.mod": self.GIN_MOD,
                "main.go": self.GIN_MAIN,
                "web/package.json": package_json(dependencies={"@tanstack/react-start": "^1"}, dev={"vite": "^7"}),
                "web/vite.config.ts": "",
            }
        )
        self.assertEqual(slugs(inspection), ["go-gin", "react-tanstack"])

    def test_root_scope_still_sees_configuration_no_package_claims(self):
        inspection = self.inspect_tree(
            {
                "tools/vite.config.ts": "",
                "web/package.json": package_json(dependencies={"next": "^15"}),
            }
        )
        self.assertEqual(slugs(inspection), ["react-nextjs", "vite-spa"])
        self.assertEqual([item["path"] for item in evidence(inspection, "vite-spa")], ["tools/vite.config.ts"])

    def test_the_same_stack_in_two_packages_merges_its_evidence(self):
        inspection = self.inspect_tree(
            {
                "apps/web/package.json": package_json(dev={"vite": "^7"}),
                "apps/admin/package.json": package_json(dev={"vite": "^7"}),
            }
        )
        self.assertEqual(slugs(inspection), ["vite-spa"])
        self.assertEqual(
            [item["path"] for item in evidence(inspection, "vite-spa")],
            ["apps/admin/package.json", "apps/web/package.json"],
        )

    def test_root_package_and_nested_packages_are_all_detected(self):
        inspection = self.inspect_tree(
            {
                "package.json": package_json(dependencies={"next": "^15"}),
                "services/ui/package.json": package_json(dependencies={"astro": "^5"}),
            }
        )
        self.assertEqual(slugs(inspection), ["astro", "react-nextjs"])
        self.assertEqual(
            [item["path"] for item in evidence(inspection, "astro")], ["services/ui/package.json"]
        )

    def test_packages_under_tests_and_docs_are_not_packages(self):
        inspection = self.inspect_tree(
            {
                "go.mod": self.GIN_MOD,
                "main.go": self.GIN_MAIN,
                "tests/fixtures/app/package.json": package_json(dev={"vite": "^7"}),
                "docs/site/package.json": package_json(dependencies={"astro": "^5"}),
            }
        )
        self.assertEqual(slugs(inspection), ["go-gin"])
        self.assertEqual(inspection["classification"], "backend-only")


COMPOSE_PORTS = "services:\n  web:\n    image: nginx:1\n    ports:\n      - \"8080:80\"\n"
COMPOSE_NO_PORTS = "services:\n  worker:\n    image: busybox\n    command: sleep 1000\n"
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

    def test_a_compose_file_the_reader_cannot_parse_is_a_warning_not_a_failure(self):
        compose = "x-app: &app\n  image: node\nservices:\n  web:\n    <<: *app\n    ports:\n      - \"3000:3000\"\n"
        inspection = self.inspect_tree(
            {"compose.yaml": compose, "package.json": package_json(dependencies={"react": "^19"})}
        )
        self.assertClean(inspection)
        self.assertEqual(inspection["classification"], "frontend-only")
        self.assertEqual(len(inspection["warnings"]), 1)
        self.assertTrue(inspection["warnings"][0].startswith("compose.yaml: not parsed"))


def candidate(source: str, path: str, command: str) -> dict[str, str]:
    return {"source": source, "path": path, "command": command}


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


def symlink_or_skip(case: unittest.TestCase, target: Path, link: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=directory)
    except (OSError, NotImplementedError) as exc:
        case.skipTest(f"cannot create symlinks here: {exc}")


VITE_TREE = {"package.json": package_json(dev={"vite": "^7"})}
#: The inspection limits by their documented values. The tests build trees that cross
#: them instead of patching the module's constants, so they hold wherever the walker lives.
INSPECTION_LIMITS = {"files": 1_000, "directories": 1_000, "depth": 32, "bytes": 10_000_000}
#: Directories the project's own tooling regenerates: never evidence, often thousands of files.
GENERATED_DIRECTORIES = {
    ".next", ".nuxt", ".svelte-kit", ".output", ".turbo", "htmlcov", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


class WalkAndLimitTests(FixtureTreeCase):
    """Benign project traits are reported and skipped; an unusable root or a walk cut short fails the run."""

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

    def test_the_scaffold_scan_does_report_the_text_files_it_cannot_read(self):
        """A scan claims absence of markers, so a file it skipped is an error, not a warning."""
        inspection = self.inspect_tree(
            {"big.sql": "-- " + "x" * 1_100_000, "notes.txt": b"caf\xe9"}, detect=False, scaffold=True
        )
        self.assertFalse(inspection["ok"])
        self.assertIn("big.sql: file exceeds the inspection size limit", inspection["errors"])
        self.assertTrue(any(error.startswith("notes.txt: cannot read text") for error in inspection["errors"]))

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
        fillers = {f"z{number:04d}.txt": "# TODO\n" for number in range(INSPECTION_LIMITS["files"] + 1)}
        report = self.report({**VITE_TREE, **fillers}, scaffold=True)
        inspection = report["project_inspection"]
        self.assertFalse(inspection["ok"])
        self.assertFalse(report["ok"])
        self.assertEqual(len(inspection["errors"]), 1)
        self.assertTrue(inspection["errors"][0].startswith("project inspection file-count limit exceeded; the walk stopped early"))
        self.assertIn("inspection is incomplete", inspection["errors"][0])
        self.assertEqual(slugs(inspection), ["vite-spa"])
        scanned = {row["file"] for row in inspection["scaffold_markers"]}
        self.assertIn("z0998.txt", scanned)
        self.assertNotIn("z0999.txt", scanned)
        self.assertNotIn("z1000.txt", scanned)

    def test_the_directory_count_limit_makes_the_inspection_incomplete(self):
        root = self.project({"a/package.json": package_json(dev={"vite": "^7"})})
        for number in range(INSPECTION_LIMITS["directories"] + 1):
            (root / f"d{number:04d}").mkdir()
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
        fillers = {f"a{number:04d}.txt": "text\n" for number in range(INSPECTION_LIMITS["files"] + 1)}
        report = self.report({**fillers, "z/package.json": package_json(dev={"vite": "^7"})})
        inspection = report["project_inspection"]
        self.assertEqual(inspection["stacks"], [])
        self.assertEqual(inspection["manifests"], [])
        self.assertFalse(report["ok"])
        self.assertEqual(inspection["warnings"], [])
        self.assertIn("file-count limit exceeded", inspection["errors"][0])

    def test_generated_output_does_not_use_up_the_walk(self):
        """A build directory that sorts before the manifests, a Next.js .next/, must not hide them."""
        generated = {f".next/static/chunk{number:04d}.js": "x" for number in range(INSPECTION_LIMITS["files"] + 200)}
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

    def test_scaffold_scanning_alone_does_not_warn_about_missing_project_evidence(self):
        inspection = self.inspect_tree({"src/util.py": "x = 1\n"}, detect=False, scaffold=True)
        self.assertEqual(inspection["warnings"], [])

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


class RegistryTests(FixtureTreeCase):
    """The registry is the authority for stack_lock, so a defect in it must be loud."""

    def with_registry(self, mutate, *, tamper=None, tree=None) -> dict:
        registry = copy.deepcopy(REGISTRY)
        mutate(registry)
        with tempfile.TemporaryDirectory() as holder:
            catalog = make_catalog(Path(holder), registry=registry)
            if tamper:
                tamper(catalog)
            return self.inspect_tree(tree or VITE_TREE, catalog=catalog)

    def vite_row(self, registry) -> dict:
        return next(row for row in registry["overlays"] if row["slug"] == "vite-spa")

    def test_the_real_registry_and_overlays_verify(self):
        inspection = self.inspect_tree(VITE_TREE)
        self.assertClean(inspection)
        self.assertEqual(slugs(inspection), ["vite-spa"])

    def test_row_defects_are_named_and_remove_only_that_row(self):
        cases = {
            "missing field": (lambda row: row.pop("sha256"), "overlay row {index} missing fields ['sha256']"),
            "extra field": (lambda row: row.update(extra=1), "overlay row {index} has unexpected fields ['extra']"),
            "wrong path": (lambda row: row.update(path="tech-stacks/other.md"), "vite-spa path must be tech-stacks/vite-spa.md"),
            "blank framework": (lambda row: row.update(framework=" "), "vite-spa framework must be a string"),
            "empty versions": (lambda row: row.update(versions=[]), "vite-spa versions must be a non-empty finite number list"),
            "boolean version": (lambda row: row.update(versions=[True]), "vite-spa versions must be a non-empty finite number list"),
            "text version": (lambda row: row.update(versions=["8"]), "vite-spa versions must be a non-empty finite number list"),
            "wrong source": (
                lambda row: row.update(source="_refs/other.md"),
                "vite-spa source must be _refs/global/tech-stacks/vite-spa.md",
            ),
            "malformed digest": (lambda row: row.update(sha256="ABC"), "vite-spa sha256 must be a lowercase SHA-256 digest"),
            "stale digest": (lambda row: row.update(sha256="0" * 64), "vite-spa overlay does not match its pinned digest"),
        }
        tree = {"package.json": package_json(dependencies={"@angular/core": "^19"}, dev={"vite": "^7"})}
        for name, (mutate, message) in cases.items():
            with self.subTest(defect=name):
                index = [row["slug"] for row in REGISTRY["overlays"]].index("vite-spa")
                inspection = self.with_registry(lambda registry, mutate=mutate: mutate(self.vite_row(registry)), tree=tree)
                self.assertIn("tech-stacks/registry.yaml: " + message.format(index=index), inspection["errors"])
                self.assertIn("detected stack vite-spa has no registry entry", inspection["errors"])
                self.assertEqual(slugs(inspection), ["angular"])
                self.assertFalse(inspection["ok"])

    def test_invalid_slugs_and_duplicates_are_rejected(self):
        def bad_slug(registry):
            self.vite_row(registry)["slug"] = "Not A Slug"

        inspection = self.with_registry(bad_slug)
        self.assertTrue(any("has an invalid slug" in error for error in inspection["errors"]))
        registry_duplicate = copy.deepcopy(REGISTRY["overlays"][0])

        def duplicate(registry):
            registry["overlays"].append(registry_duplicate)

        inspection = self.with_registry(duplicate, tree={"package.json": package_json(dependencies={"@angular/core": "^19"})})
        self.assertIn("tech-stacks/registry.yaml: duplicate slug 'angular'", inspection["errors"])
        self.assertEqual(slugs(inspection), ["angular"])

    def test_a_row_that_is_not_a_mapping_is_rejected(self):
        inspection = self.with_registry(lambda registry: registry["overlays"].append("angular"))
        self.assertIn(
            f"tech-stacks/registry.yaml: overlay row {len(REGISTRY['overlays'])} must be a mapping", inspection["errors"]
        )
        self.assertEqual(slugs(inspection), ["vite-spa"])

    def test_registry_level_defects_reject_every_row(self):
        cases = {
            "schema version": (lambda registry: registry.update(schema_version=2), "schema_version must be 1"),
            "kind": (lambda registry: registry.update(kind="other"), "kind is invalid"),
            "overlays": (lambda registry: registry.update(overlays={}), "overlays must be a list"),
        }
        for name, (mutate, message) in cases.items():
            with self.subTest(defect=name):
                inspection = self.with_registry(mutate)
                self.assertIn("tech-stacks/registry.yaml: " + message, inspection["errors"])
                self.assertIn("detected stack vite-spa has no registry entry", inspection["errors"])
                self.assertEqual(slugs(inspection), [])

    def test_a_registry_that_is_not_a_mapping_or_cannot_be_parsed_is_an_error(self):
        for label, body, message in (
            ("list root", "[1, 2]", "tech-stacks/registry.yaml: root must be a mapping"),
            ("unparsable", "a: b: c\n  - d", "tech-stacks/registry.yaml:"),
        ):
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as holder:
                    catalog = make_catalog(Path(holder))
                    (catalog / "tech-stacks" / "registry.yaml").write_text(body, encoding="utf-8")
                    inspection = self.inspect_tree(VITE_TREE, catalog=catalog)
                self.assertTrue(any(error.startswith(message) for error in inspection["errors"]), inspection["errors"])
                self.assertEqual(slugs(inspection), [])

    def test_an_overlay_edited_after_pinning_fails_its_digest(self):
        def tamper(catalog):
            with (catalog / "tech-stacks" / "vite-spa.md").open("a", encoding="utf-8") as overlay:
                overlay.write("\n- An unreviewed line.\n")

        inspection = self.with_registry(lambda registry: None, tamper=tamper)
        self.assertIn("tech-stacks/registry.yaml: vite-spa overlay does not match its pinned digest", inspection["errors"])
        self.assertEqual(slugs(inspection), [])

    def test_a_missing_overlay_file_rejects_its_row(self):
        inspection = self.with_registry(
            lambda registry: None, tamper=lambda catalog: (catalog / "tech-stacks" / "vite-spa.md").unlink()
        )
        self.assertIn("tech-stacks/registry.yaml: vite-spa overlay file is missing or not regular", inspection["errors"])
        self.assertEqual(slugs(inspection), [])

    def test_provenance_sources_are_enforced_only_when_the_authoring_workspace_exists(self):
        def workspace(catalog):
            (catalog.parent / "_refs" / "global" / "tech-stacks").mkdir(parents=True)

        inspection = self.with_registry(lambda registry: None, tamper=workspace)
        self.assertIn("tech-stacks/registry.yaml: vite-spa source file is missing or not regular", inspection["errors"])
        self.assertEqual(slugs(inspection), [])

    def test_no_registry_file_means_detected_stacks_are_unregistered(self):
        with tempfile.TemporaryDirectory() as holder:
            catalog = make_catalog(Path(holder), overlays=False)
            inspection = self.inspect_tree(VITE_TREE, catalog=catalog)
        self.assertEqual(inspection["errors"], ["detected stack vite-spa has no registry entry"])
        self.assertEqual(slugs(inspection), [])

    def test_a_registry_that_is_not_a_regular_file_is_refused(self):
        with tempfile.TemporaryDirectory() as holder:
            catalog = make_catalog(Path(holder))
            registry = catalog / "tech-stacks" / "registry.yaml"
            real = Path(holder) / "elsewhere.yaml"
            registry.replace(real)
            symlink_or_skip(self, real, registry)
            inspection = self.inspect_tree(VITE_TREE, catalog=catalog)
        self.assertIn("tech-stacks/registry.yaml: must be a regular file", inspection["errors"])
        self.assertEqual(slugs(inspection), [])


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
