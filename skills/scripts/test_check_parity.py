"""Regression coverage for the redesign parity checker."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check_parity.py"

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


def run(root: Path, app: str, catalog: str = CATALOG, inventory: dict | None = None, extra: tuple[str, ...] = ()):
    (root / "inv.json").write_text(json.dumps(inventory or INVENTORY), encoding="utf-8")
    (root / "app.html").write_text(app, encoding="utf-8")
    (root / "components.html").write_text(catalog, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--inventory", str(root / "inv.json"), "--app", str(root / "app.html"),
         "--components", str(root / "components.html"), "--out", str(root / "evidence" / "parity.json"),
         "--project-root", str(root), *extra],
        capture_output=True, text=True, check=False,
    )
    record = json.loads((root / "evidence" / "parity.json").read_text(encoding="utf-8")) if (root / "evidence" / "parity.json").exists() else {}
    return proc, record


class ParityCheckerTests(unittest.TestCase):
    def test_full_coverage_passes_and_binds_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc, record = run(root, FULL_APP)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
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
            proc, record = run(root, FULL_APP, inventory=bad)
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
            proc = subprocess.run([sys.executable, str(SCRIPT), "--inventory", str(inventory), "--app", str(app),
                                   "--components", str(catalog), "--out", str(out), "--project-root", str(root)],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            return json.loads(out.read_text(encoding="utf-8"))

    def test_input_hashes_are_identical_for_lf_and_crlf_sources(self):
        lf = {i["path"]: i["sha256"] for i in self._run("\n")["inputs"]}
        crlf = {i["path"]: i["sha256"] for i in self._run("\r\n")["inputs"]}
        self.assertEqual(lf, crlf)
        self.assertEqual(len(lf), 3)


if __name__ == "__main__":
    unittest.main()
