"""Regression coverage for the redesign parity checker.

Most tests call ``main()`` in this process with the arguments a command line
would carry. Two run the script itself, so the exit code and the JSON it prints
stay pinned end to end.
"""
from __future__ import annotations

import contextlib
import io
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import check_parity
import validate_manifests

SCRIPT = Path(__file__).resolve().parent / "check_parity.py"
SKILLS = SCRIPT.parents[1]

INVENTORY = {
    "schema_version": 1,
    "surface": "fixture",
    "routes": [
        {"id": "route.home", "path": "/", "states": ["loading", "success"], "components": ["component.button"]},
        {"id": "route.orders", "path": "/orders", "states": ["empty", "success"], "components": ["component.table"]},
    ],
    "components": [{"id": "component.button", "name": "Button"}, {"id": "component.table", "name": "Table"}],
    "interactions": [{"id": "interaction.open-order", "route": "route.orders"}],
    "flows": [{"id": "flow.review-order", "steps": [{"route": "route.orders", "state": "success"}]}],
}

CATALOG = "<html><body><section data-component='component.button'></section><section data-component='component.table'></section></body></html>"

#: A mock catalog carries only part of the component set; the rest is drawn in
#: mock.html. At --level mock the two files are read together.
MOCK_CATALOG = "<html><body><section data-component='component.button'></section></body></html>"

#: A static draft: one screen per route, no router, no state machine, no wired
#: interactions or flows, and a data-mock marker above the screens.
MOCK = """<html><body data-mock="true">
<main data-route="route.home"><button data-component="component.button">Go</button></main>
<main data-route="route.orders"><table data-component="component.table"><tr><td>#1</td></tr></table></main>
</body></html>"""

FULL_APP = """<html><body>
<main data-route="route.home"><div data-state="loading"></div><div data-state="success"><button data-component="component.button">Go</button></div></main>
<main data-route="route.orders"><div data-route-state="route.orders:empty"></div>
  <table data-component="component.table" data-state="success"><tr><td><a data-interaction="interaction.open-order" data-flow="flow.review-order">#1</a></td></tr></table>
</main>
<script>const fake = 'data-route="route.ghost" data-state="ghost"';</script>
<!-- data-route="route.commented" -->
</body></html>"""


def main_in_process(argv: list[str]) -> subprocess.CompletedProcess:
    """``check_parity.main`` run here, its exit code and output shaped like a finished subprocess."""
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = check_parity.main(argv)
    return subprocess.CompletedProcess(argv, code, stdout.getvalue(), stderr.getvalue())


def run(root: Path, app: str, catalog: str = CATALOG, inventory: dict | None = None, extra: tuple[str, ...] = (),
        *, cli: bool = False, bom: bool = False):
    """Write the inputs under ``root`` and check them, in this process or, with ``cli``, as the command line."""
    (root / "inv.json").write_text(json.dumps(inventory or INVENTORY), encoding="utf-8-sig" if bom else "utf-8")
    (root / "app.html").write_text(app, encoding="utf-8")
    (root / "components.html").write_text(catalog, encoding="utf-8")
    argv = ["--inventory", str(root / "inv.json"), "--app", str(root / "app.html"),
            "--components", str(root / "components.html"), "--out", str(root / "evidence" / "parity.json"),
            "--project-root", str(root), *extra]
    if cli:
        proc = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True, text=True, check=False)
    else:
        proc = main_in_process(argv)
    out = root / "evidence" / "parity.json"
    record = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    return proc, record


class ParityCheckerTests(unittest.TestCase):
    def test_full_coverage_passes_and_binds_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, record = run(root, FULL_APP, cli=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["record"], "evidence/parity.json")
            self.assertEqual(record["result"]["status"], "pass")
            self.assertEqual(record["coverage"], 1.0)
            self.assertEqual({i["path"] for i in record["inputs"]}, {"inv.json", "app.html", "components.html"})
            self.assertTrue(all(len(i["sha256"]) == 64 for i in record["inputs"]))
            self.assertEqual(record["artifacts"], ["evidence/parity.json"])

    def test_markers_in_scripts_and_comments_do_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = json.loads(json.dumps(INVENTORY))
            inventory["routes"].append({"id": "route.ghost", "path": "/g", "states": ["ghost"]})
            proc, record = run(root, FULL_APP, inventory=inventory)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("route.ghost", record["lists"]["routes"]["missing"])
            self.assertIn("route.ghost:ghost", record["lists"]["states"]["missing"])

    def test_missing_state_and_catalog_component_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FULL_APP.replace('data-route-state="route.orders:empty"', "")
            catalog = "<div data-component='component.button'></div>"
            proc, record = run(root, app, catalog=catalog)
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(record["result"]["status"], "fail")
            self.assertEqual(record["lists"]["states"]["missing"], ["route.orders:empty"])
            self.assertEqual(record["lists"]["components"]["missing"], ["component.table"])
            self.assertEqual(record["lists"]["components"]["missing_in_catalog"], ["component.table"])
            self.assertEqual(record["lists"]["components"]["missing_in_app"], [])

    def test_invalid_inventory_is_an_engine_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = json.loads(json.dumps(INVENTORY))
            bad["routes"].append({"id": "Route Home", "states": []})
            proc, record = run(root, FULL_APP, inventory=bad, cli=True)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("engine_error", json.loads(proc.stderr))
            self.assertEqual(record, {})

    def test_mock_level_scores_routes_and_components_only(self):
        """A static draft passes the mock level with no interactions or flows.

        The same file is a failure at the default level, which is the point of
        having two: a mock is not held to the living prototype's contract.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, record = run(root, MOCK, catalog=MOCK_CATALOG, extra=("--level", "mock"))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(record["result"]["status"], "pass")
            self.assertEqual(record["coverage"], 1.0)
            self.assertEqual(record["level"], "mock")
            self.assertEqual(record["scored"], ["routes", "components"])
            self.assertEqual(record["informational"], ["interactions", "flows", "states"])
            for name in ("interactions", "flows", "states"):
                self.assertTrue(record["lists"][name]["informational"])
                self.assertTrue(record["lists"][name]["missing"])
            self.assertEqual(json.loads(proc.stdout)["missing"], {})
            self.assertIn("states", json.loads(proc.stdout)["informational"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, record = run(root, MOCK, catalog=MOCK_CATALOG)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertEqual(record["level"], "full")
            self.assertLess(record["coverage"], 1.0)

    def test_mock_level_still_requires_every_route_and_component(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = MOCK.replace('<main data-route="route.orders">', "<main>")
            proc, record = run(root, app, catalog=MOCK_CATALOG, extra=("--level", "mock"))
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertEqual(record["result"]["status"], "fail")
            self.assertEqual(record["lists"]["routes"]["missing"], ["route.orders"])
            self.assertEqual(json.loads(proc.stdout)["missing"]["routes"], ["route.orders"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = MOCK.replace(' data-component="component.table"', "")
            proc, record = run(root, app, catalog=MOCK_CATALOG, extra=("--level", "mock"))
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertEqual(record["lists"]["components"]["missing"], ["component.table"])

    def test_the_mock_marker_is_recorded_either_way(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, record = run(root, MOCK, catalog=MOCK_CATALOG, extra=("--level", "mock"))
            self.assertTrue(record["mock_root"])
            # A marker inside a screen describes that screen, not the document.
            inside = MOCK.replace('<body data-mock="true">', "<body>").replace(
                '<main data-route="route.home">', '<main data-route="route.home" data-mock="true">')
            _, record = run(root, inside, catalog=MOCK_CATALOG, extra=("--level", "mock"))
            self.assertFalse(record["mock_root"])
            _, record = run(root, FULL_APP)
            self.assertFalse(record["mock_root"])
            self.assertEqual(record["level"], "full")

    def test_threshold_is_configurable_but_defaults_to_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = FULL_APP.replace('data-flow="flow.review-order"', "")
            proc, _ = run(root, app)
            self.assertEqual(proc.returncode, 1)
            proc, record = run(root, app, extra=("--min-coverage", "0.8"))
            self.assertEqual(proc.returncode, 0, proc.stdout)
            self.assertEqual(record["result"]["status"], "pass")
            self.assertLess(record["coverage"], 1.0)


class ParityRecordLineEndingTests(unittest.TestCase):
    """The probe record's input hashes are the same whether the inventory and
    surfaces were written with LF or CRLF, so a checkout conversion between the
    builder and the mapper never reads as input hash drift."""

    def _run(self, ending: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            inventory = root / "design-inventory.json"
            inventory.write_bytes(json.dumps(INVENTORY, indent=2).replace("\n", ending).encode("utf-8"))
            catalog = root / "components.html"
            catalog.write_bytes(CATALOG.replace("\n", ending).encode("utf-8"))
            app = root / "app.html"
            app.write_bytes(FULL_APP.replace("\n", ending).encode("utf-8"))
            out = root / "parity.json"
            proc = main_in_process(["--inventory", str(inventory), "--app", str(app), "--components", str(catalog),
                                    "--out", str(out), "--project-root", str(root)])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            return json.loads(out.read_text(encoding="utf-8"))

    def test_input_hashes_are_identical_for_lf_and_crlf_sources(self):
        lf = {i["path"]: i["sha256"] for i in self._run("\n")["inputs"]}
        crlf = {i["path"]: i["sha256"] for i in self._run("\r\n")["inputs"]}
        self.assertEqual(lf, crlf)
        self.assertEqual(len(lf), 3)


class RecordFileTests(unittest.TestCase):
    """The inventory is read whatever wrote it, and the record is written whole or not at all."""

    def test_an_inventory_with_a_byte_order_mark_is_read(self):
        """Windows PowerShell 5.1 writes UTF-8 with a byte order mark, which json.loads refuses."""
        with tempfile.TemporaryDirectory() as tmp:
            proc, record = run(Path(tmp), FULL_APP, bom=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(record["result"]["status"], "pass")

    def test_a_record_that_cannot_be_put_in_place_leaves_no_temporary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "evidence" / "parity.json").mkdir(parents=True)
            proc, record = run(root, FULL_APP)
            self.assertEqual(sorted(path.name for path in (root / "evidence").iterdir()), ["parity.json"])
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(record, {})
        self.assertTrue(json.loads(proc.stderr)["engine_error"].startswith("record could not be moved into place: "))


def scan_markup(markup: str) -> check_parity.MarkerScanner:
    scanner = check_parity.MarkerScanner()
    scanner.feed(markup)
    scanner.close()
    return scanner


class RouteScopeTests(unittest.TestCase):
    """A route's states are the ones drawn inside its own view, whatever the markup style."""

    def test_void_elements_do_not_keep_a_route_open(self):
        scanner = scan_markup(
            '<main data-route="route.home"><input><img src="a.png"><br><div data-state="loading"></div></main>'
            '<footer><div data-state="empty"></div></footer>'
        )
        self.assertEqual(scanner.route_states, {("route.home", "loading")})

    def test_every_void_element_is_recognised_in_both_spellings(self):
        for tag in sorted(check_parity.VOID_TAGS):
            for spelling in (f"<{tag}>", f"<{tag}/>", f"<{tag} />"):
                with self.subTest(markup=spelling):
                    scanner = scan_markup(
                        f'<main data-route="route.a">{spelling}<div data-state="inside"></div></main>'
                        '<div data-state="outside"></div>'
                    )
                    self.assertEqual(scanner.route_states, {("route.a", "inside")})

    def test_a_stray_end_tag_for_a_void_element_closes_nothing(self):
        scanner = scan_markup(
            '<main data-route="route.a"><input></input><div data-state="inside"></div></main>'
            '<div data-state="outside"></div>'
        )
        self.assertEqual(scanner.route_states, {("route.a", "inside")})

    def test_attributes_on_a_void_element_still_count_for_the_enclosing_route(self):
        scanner = scan_markup(
            '<main data-route="route.a"><input data-state="error" data-component="component.field"></main>'
        )
        self.assertEqual(scanner.route_states, {("route.a", "error")})
        self.assertEqual(scanner.components, {"component.field"})

    def test_a_void_element_that_declares_a_route_scopes_only_itself(self):
        scanner = scan_markup('<img data-route="route.x" data-state="idle"><div data-state="later"></div>')
        self.assertEqual(scanner.routes, {"route.x"})
        self.assertEqual(scanner.route_states, {("route.x", "idle")})

    def test_an_element_with_an_omitted_end_tag_does_not_keep_a_route_open(self):
        scanner = scan_markup(
            '<main data-route="route.a"><ul><li>one<li>two</ul><p>text</main>'
            '<div data-state="outside"></div>'
        )
        self.assertEqual(scanner.route_states, set())
        self.assertEqual(scanner.routes, {"route.a"})

    def test_nested_routes_credit_the_innermost_route(self):
        scanner = scan_markup(
            '<main data-route="route.outer"><section data-route="route.inner"><div data-state="a"></div></section>'
            '<div data-state="b"></div></main>'
        )
        self.assertEqual(scanner.route_states, {("route.inner", "a"), ("route.outer", "b")})

    def test_a_stray_end_tag_with_nothing_open_is_ignored(self):
        scanner = scan_markup('</div></main><main data-route="route.a"><div data-state="ok"></div></main>')
        self.assertEqual(scanner.route_states, {("route.a", "ok")})

    def test_template_script_and_style_contents_are_not_markup(self):
        scanner = scan_markup(
            '<main data-route="route.a"><template><input><div data-route="route.ghost" data-state="ghost"></div></template>'
            '<script>var x = "<div data-state=\'ghost2\'>"</script><style>.a{}</style>'
            '<div data-state="real"></div></main><div data-state="outside"></div>'
        )
        self.assertEqual(scanner.routes, {"route.a"})
        self.assertEqual(scanner.route_states, {("route.a", "real")})

    def test_the_mock_marker_survives_void_elements_before_the_first_route(self):
        scanner = scan_markup('<html><head><meta charset="utf-8"><link rel="stylesheet" href="a.css"></head>'
                              '<body data-mock="true"><main data-route="route.a"></main></body></html>')
        self.assertTrue(scanner.mock_root)
        inside = scan_markup('<main data-route="route.a"><br><div data-mock="true"></div></main>')
        self.assertFalse(inside.mock_root)

    def test_a_leaked_route_cannot_credit_a_missing_state_to_the_coverage_check(self):
        """End to end: the footer's state must not stand in for the state route.orders never drew."""
        app = FULL_APP.replace(
            '<div data-route-state="route.orders:empty"></div>', "<input><br>"
        ).replace("<script>", '<footer><div data-state="empty"></div></footer>\n<script>')
        with tempfile.TemporaryDirectory() as tmp:
            proc, record = run(Path(tmp), app)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertEqual(record["lists"]["states"]["missing"], ["route.orders:empty"])
        self.assertEqual(record["result"]["status"], "fail")


class InventoryValidationTests(unittest.TestCase):
    """An inventory that expects nothing would score full coverage for a surface that draws nothing."""

    def engine_error(self, inventory: dict, **extra) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            proc, record = run(Path(tmp), FULL_APP, inventory=inventory, **extra)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertEqual(record, {}, "an engine error writes no record")
        self.assertEqual(proc.stdout, "")
        return json.loads(proc.stderr)["engine_error"]

    def inventory(self, **overrides) -> dict:
        data = json.loads(json.dumps(INVENTORY))
        data.update(overrides)
        return data

    def test_an_empty_inventory_is_an_engine_error_not_a_pass(self):
        empty = {"schema_version": 1, "routes": [], "components": [], "interactions": [], "flows": []}
        self.assertIn("inventory routes must list at least one id", self.engine_error(empty))

    def test_empty_routes_or_components_are_engine_errors(self):
        self.assertIn("routes", self.engine_error(self.inventory(routes=[])))
        self.assertIn("components", self.engine_error(self.inventory(components=[])))

    def test_empty_inventories_are_rejected_at_both_levels(self):
        self.assertIn("routes", self.engine_error(self.inventory(routes=[]), extra=("--level", "mock")))
        self.assertIn("components", self.engine_error(self.inventory(components=[]), extra=("--level", "mock")))

    def test_route_states_must_be_a_list(self):
        for label, states in {"text": "loading", "number": 3, "mapping": {"loading": True}, "boolean": True}.items():
            with self.subTest(states=label):
                inventory = self.inventory(routes=[{"id": "route.home", "path": "/", "states": states}])
                message = self.engine_error(inventory)
                self.assertIn("route.home", message)
                self.assertIn("states must be a list", message)

    def test_routes_without_states_or_with_null_states_are_valid(self):
        for route in ({"id": "route.home", "path": "/"}, {"id": "route.home", "path": "/", "states": None}):
            with self.subTest(route=route):
                inventory = self.inventory(routes=[route], interactions=[], flows=[])
                with tempfile.TemporaryDirectory() as tmp:
                    proc, record = run(Path(tmp), MOCK, catalog=MOCK_CATALOG, inventory=inventory, extra=("--level", "mock"))
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self.assertEqual(record["lists"]["states"]["expected"], 0)

    def test_empty_interactions_and_flows_are_allowed(self):
        """A static surface has none, and the routes and components still have to be drawn."""
        inventory = self.inventory(interactions=[], flows=[])
        with tempfile.TemporaryDirectory() as tmp:
            proc, record = run(Path(tmp), FULL_APP, inventory=inventory)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(record["coverage"], 1.0)
        self.assertEqual(record["lists"]["interactions"]["expected"], 0)

    def test_inventory_lists_still_have_to_be_lists_with_valid_ids(self):
        self.assertIn("routes must be a list", self.engine_error(self.inventory(routes="route.home")))
        self.assertIn("invalid id", self.engine_error(self.inventory(components=[{"id": "Not An Id"}])))
        duplicate = self.inventory(components=[{"id": "component.a"}, {"id": "component.a"}])
        self.assertIn("duplicate id", self.engine_error(duplicate))


class DocumentedExampleTests(unittest.TestCase):
    """The check_parity commands the redesign skills document run as written against a complete run tree."""

    def test_parity_examples_use_real_run_inputs_and_outputs(self):
        installed, _ = validate_manifests.install_record(SKILLS)
        if installed is not None and "design" not in installed:
            self.skipTest("the design team, whose documents hold the examples, is not installed here")
        docs = ("design/design-mapper/references/examples.md", "design/prototyper/references/workflow.md")
        count = 0
        for document in docs:
            text = (SKILLS / document).read_text(encoding="utf-8")
            for line in text.splitlines():
                if not line.startswith("python skills/scripts/check_parity.py --"):
                    continue
                with self.subTest(document=document, command=line), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp).resolve()
                    args = shlex.split(line.replace("{run-id}", "doc-fixture"))[2:]
                    paths = {flag: root / args[args.index(flag) + 1] for flag in ("--inventory", "--app", "--components", "--out")}
                    for path in paths.values():
                        self.assertTrue(path.is_relative_to(root / "skillset-saves" / "runs" / "doc-fixture"))
                        path.parent.mkdir(parents=True, exist_ok=True)
                    paths["--inventory"].write_text(json.dumps(INVENTORY), encoding="utf-8")
                    paths["--components"].write_text(CATALOG, encoding="utf-8")
                    level = args[args.index("--level") + 1]
                    paths["--app"].write_text(MOCK if level == "mock" else FULL_APP, encoding="utf-8")
                    with contextlib.chdir(root):
                        self.assertEqual(main_in_process(args).returncode, 0)
                    record = json.loads(paths["--out"].read_text(encoding="utf-8"))
                    self.assertEqual(record["result"]["status"], "pass")
                    self.assertTrue(all(entry["path"].startswith("skillset-saves/runs/doc-fixture/") for entry in record["inputs"]))
                    count += 1
        self.assertEqual(count, 4, "documented commands must not silently disappear")


if __name__ == "__main__":
    unittest.main()
