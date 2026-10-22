"""Stack detection through check_runtime.check(): which registered stacks a project holds, and why.

Every test writes a small project tree into a temporary directory and drives
``check()`` against a temporary catalog (``_runtime_fixtures``), so the tests pin
what the inspector reports and not how its functions are arranged. The registry
is the authority for stack_lock, so its defects are pinned here too.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from _runtime_fixtures import (
    CATALOG_SOURCE,
    VITE_TREE,
    FixtureTreeCase,
    evidence,
    make_catalog,
    package_json,
    slugs,
    symlink_or_skip,
)
from data_formats import load_data, normalize_line_endings

REGISTRY = load_data(CATALOG_SOURCE / "tech-stacks" / "registry.yaml")
REGISTERED_SLUGS = sorted(row["slug"] for row in REGISTRY["overlays"])


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

    def test_a_nested_package_error_names_that_package_once_in_every_mode(self):
        tree = {"apps/web/package.json": package_json(scripts={"dev": 5})}
        for modes in ({"detect": True}, {"detect": False, "start": True}, {"detect": True, "start": True}):
            with self.subTest(**modes):
                inspection = self.inspect_tree(tree, **modes)
                self.assertEqual(inspection["errors"], ["apps/web/package.json:scripts.dev: command must be a string"])
                self.assertFalse(inspection["ok"])

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

    def test_an_overlay_verifies_with_lf_and_with_crlf_line_endings(self):
        """Registry digests fold text to LF, so a CRLF checkout of an overlay still matches its pinned digest."""
        row = self.vite_row(REGISTRY)
        lf = normalize_line_endings((CATALOG_SOURCE / row["path"]).read_bytes())
        self.assertEqual(hashlib.sha256(lf).hexdigest(), row["sha256"], "registry digests are LF-folded")
        for ending in (b"\n", b"\r\n"):
            with self.subTest(ending=ending), tempfile.TemporaryDirectory() as holder:
                catalog = make_catalog(Path(holder))
                (catalog / row["path"]).write_bytes(lf.replace(b"\n", ending))
                inspection = self.inspect_tree(VITE_TREE, catalog=catalog)
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


if __name__ == "__main__":
    unittest.main()
