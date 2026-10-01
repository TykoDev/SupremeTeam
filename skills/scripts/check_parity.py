#!/usr/bin/env python3
"""Mechanical functional-parity check for a redesign mock or variant.

Reads a design inventory (``design-inventory.json``, schema 1) and scans one
rendered surface - a static mock (``mock.html``) or the selected living
prototype (``app.html``) - plus its component catalog (``components.html``) for
the parity markers the prototyper must place:

    routes        data-route="<id>"                        in the scanned surface
    states        data-state="<state>" inside the route view,
                  or data-route-state="<route id>:<state>"
    components    data-component="<id>"                    in components.html and the surface
    interactions  data-interaction="<id>"                  in the surface
    flows         data-flow="<id>"                         in the surface

Two levels, because a mock and a prototype are asked for different things:

    --level full   (default) every list is scored: routes, components,
                   interactions, flows, and route states. This is the living
                   prototype's contract - full parity with the inventory.
    --level mock   only routes and components are scored. A mock is a static
                   draft with no router, no state and no wired behaviour, so
                   interactions, flows and states are counted and reported as
                   informational and can never fail the level. Components are
                   satisfied by appearing in either file, since a mock spreads
                   the catalog across ``components.html`` and ``mock.html``.

``--min-coverage`` applies to the scored lists at either level, so a mock still
has to draw every route and show every component.

The record also states the ``level`` it ran at and whether the scanned surface
declares itself a mock: ``mock_root`` is true when an element above the screens
carries ``data-mock="true"``, which is how a reader tells a mock from a living
prototype without opening it.

It writes a typed ``probe`` record (gates.yaml) whose ``inputs`` bind the
inventory and the scanned files by sha256, so a changed inventory or surface
makes the record fail the gate as input hash drift.

    python skills/scripts/check_parity.py --inventory <design-inventory.json> \
        --app <mock.html|app.html> --components <components.html> \
        --out <redesign/evidence/parity-<id>.json> \
        [--level mock|full] [--project-root .] [--min-coverage 1.0]

Exit 0 when coverage meets the threshold, 1 when scored ids are missing, 2 on an
input or engine error. The JSON summary is printed to stdout.

An inventory must list at least one route and one component, and a route's
``states`` must be a list. Anything else exits 2: an empty expectation set would
score coverage 1.0 and pass a surface that renders nothing.
"""
from __future__ import annotations

import argparse
import html.parser
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from data_formats import content_sha256  # noqa: E402

ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
PARITY_LISTS = ("routes", "components", "interactions", "flows")
#: Lists an inventory must not leave empty. They are the two scored at every level,
#: so an empty one lets a surface that draws nothing score full coverage.
REQUIRED_LISTS = ("routes", "components")
#: Elements with no end tag. html.parser reports no end event for them, so they
#: must never open a scope on the route stack.
VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
                       "source", "track", "wbr"})
#: Elements whose contents are not rendered markup.
SKIPPED_TAGS = frozenset({"script", "style", "template"})
#: Every list the report carries, in report order.
REPORT_LISTS = PARITY_LISTS + ("states",)
#: Lists that count toward coverage at each level. What is not scored is still
#: measured and reported, marked informational, and never fails the level.
SCORED_LISTS = {
    "full": REPORT_LISTS,
    "mock": ("routes", "components"),
}


class ParityError(ValueError):
    """Input or engine failure: exit 2, never a pass."""


def sha256(path: Path) -> str:
    """Canonical digest: text folded to LF, binary byte-for-byte (data_formats.content_sha256)."""
    return content_sha256(path)


class MarkerScanner(html.parser.HTMLParser):
    """Collect parity markers from rendered markup only (no comments, no scripts)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.routes: set[str] = set()
        self.components: set[str] = set()
        self.interactions: set[str] = set()
        self.flows: set[str] = set()
        self.route_states: set[tuple[str, str]] = set()
        #: True when an element above the screens declares data-mock="true".
        #: "Above the screens" is what makes it the app root: a marker inside a
        #: `data-route` view, or after the first one was opened, describes that
        #: screen and not the document.
        self.mock_root = False
        #: Open elements as (tag, route id or None), innermost last.
        self._route_stack: list[tuple[str, str | None]] = []

    def _open(self, tag: str, route: str | None) -> None:
        if tag not in VOID_TAGS:
            self._route_stack.append((tag, route))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_TAGS or any(open_tag in SKIPPED_TAGS for open_tag, _ in self._route_stack):
            self._open(tag, None)
            return
        values = {name: (value or "").strip() for name, value in attrs}
        route = values.get("data-route")
        if (values.get("data-mock") == "true" and not route and not self.routes
                and not any(r for _, r in self._route_stack if r)):
            self.mock_root = True
        if route:
            self.routes.add(route)
        self._open(tag, route or None)
        current = route or next((r for _, r in reversed(self._route_stack) if r), None)
        state = values.get("data-state")
        if state and current:
            self.route_states.add((current, state))
        pair = values.get("data-route-state")
        if pair and ":" in pair:
            r, s = pair.split(":", 1)
            self.route_states.add((r.strip(), s.strip()))
        for attr, bucket in (("data-component", self.components), ("data-interaction", self.interactions),
                             ("data-flow", self.flows)):
            value = values.get(attr)
            if value:
                bucket.add(value)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        # Close back to the nearest open element of this name, so an element whose end
        # tag is optional or omitted cannot leave its route open. A stray end tag with
        # no open element (or a void element's) closes nothing.
        for index in range(len(self._route_stack) - 1, -1, -1):
            if self._route_stack[index][0] == tag:
                del self._route_stack[index:]
                return


def load_inventory(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ParityError(f"inventory unreadable: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ParityError("inventory must be a schema_version 1 object")
    for name in PARITY_LISTS:
        items = data.get(name)
        if not isinstance(items, list):
            raise ParityError(f"inventory {name} must be a list")
        if name in REQUIRED_LISTS and not items:
            raise ParityError(f"inventory {name} must list at least one id: an empty list scores coverage 1.0")
        seen: set[str] = set()
        for item in items:
            ident = str((item or {}).get("id", "")) if isinstance(item, dict) else ""
            if not ID_RE.match(ident):
                raise ParityError(f"inventory {name} entry has an invalid id: {ident!r}")
            if ident in seen:
                raise ParityError(f"inventory {name} has duplicate id {ident!r}")
            seen.add(ident)
            if name == "routes" and item.get("states") is not None and not isinstance(item["states"], list):
                raise ParityError(f"inventory route {ident!r} states must be a list")
    return data


def scan(path: Path) -> MarkerScanner:
    scanner = MarkerScanner()
    try:
        scanner.feed(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        raise ParityError(f"cannot read {path}: {exc}") from exc
    return scanner


def evaluate(inventory: dict, app: MarkerScanner, catalog: MarkerScanner,
             level: str = "full") -> dict:
    scored = SCORED_LISTS[level]
    expected = {name: [item["id"] for item in inventory[name]] for name in PARITY_LISTS}
    expected_states = [(route["id"], str(state)) for route in inventory["routes"]
                       for state in (route.get("states") or [])]
    # A living prototype must carry every component in both the catalog and the
    # app. A mock spreads the catalog across components.html and mock.html, and
    # the contract is that each component appears somewhere across the two.
    components = (catalog.components | app.components) if level == "mock" else (catalog.components & app.components)
    found = {
        "routes": app.routes,
        "components": components,
        "interactions": app.interactions,
        "flows": app.flows,
    }
    report: dict[str, dict] = {}
    total_expected = total_found = 0
    for name in PARITY_LISTS:
        missing = sorted(i for i in expected[name] if i not in found[name])
        report[name] = {"expected": len(expected[name]), "found": len(expected[name]) - len(missing), "missing": missing}
        if name not in scored:
            report[name]["informational"] = True
            continue
        total_expected += len(expected[name])
        total_found += len(expected[name]) - len(missing)
    missing_states = sorted(f"{r}:{s}" for r, s in expected_states if (r, s) not in app.route_states)
    report["states"] = {"expected": len(expected_states), "found": len(expected_states) - len(missing_states), "missing": missing_states}
    if "states" in scored:
        total_expected += len(expected_states)
        total_found += len(expected_states) - len(missing_states)
    else:
        report["states"]["informational"] = True
    catalog_only_missing = sorted(i for i in expected["components"] if i not in catalog.components)
    app_only_missing = sorted(i for i in expected["components"] if i not in app.components)
    report["components"]["missing_in_catalog"] = catalog_only_missing
    report["components"]["missing_in_app"] = app_only_missing
    coverage = 1.0 if total_expected == 0 else total_found / total_expected
    return {"coverage": round(coverage, 4), "lists": report, "expected": total_expected,
            "found": total_found, "level": level, "scored": list(scored),
            "informational": [name for name in REPORT_LISTS if name not in scored]}


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a redesign mock or variant for parity against the design inventory.")
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--app", required=True, help="the scanned surface: mock.html at --level mock, app.html at --level full")
    parser.add_argument("--components", required=True)
    parser.add_argument("--out", required=True, help="typed probe record to write (JSON)")
    parser.add_argument("--level", choices=sorted(SCORED_LISTS), default="full",
                        help="full scores every list; mock scores routes and components and reports the rest as informational")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--min-coverage", type=float, default=1.0)
    args = parser.parse_args()
    root = Path(args.project_root)
    inventory_path, app_path, catalog_path = Path(args.inventory), Path(args.app), Path(args.components)
    try:
        inventory = load_inventory(inventory_path)
        surface = scan(app_path)
        summary = evaluate(inventory, surface, scan(catalog_path), args.level)
    except ParityError as exc:
        print(json.dumps({"ok": False, "engine_error": str(exc)}), file=sys.stderr)
        return 2
    passed = summary["coverage"] >= args.min_coverage
    out = Path(args.out)
    record = {
        "kind": "probe",
        "tool": "check_parity.py",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": [relative(out, root)],
        "inputs": [
            {"path": relative(inventory_path, root), "sha256": sha256(inventory_path)},
            {"path": relative(app_path, root), "sha256": sha256(app_path)},
            {"path": relative(catalog_path, root), "sha256": sha256(catalog_path)},
        ],
        "min_coverage": args.min_coverage,
        "coverage": summary["coverage"],
        "level": args.level,
        "scored": summary["scored"],
        "informational": summary["informational"],
        "mock_root": surface.mock_root,
        "lists": summary["lists"],
        "result": {"status": "pass" if passed else "fail",
                   "summary": f"{summary['found']}/{summary['expected']} scored inventory ids present "
                              f"at level {args.level}"},
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(out)
    except OSError as exc:
        print(json.dumps({"ok": False, "engine_error": f"cannot write record: {exc}"}), file=sys.stderr)
        return 2
    print(json.dumps({"ok": passed, "record": relative(out, root), "coverage": summary["coverage"],
                      "level": args.level, "mock_root": surface.mock_root,
                      "missing": {name: data["missing"] for name, data in summary["lists"].items()
                                  if data["missing"] and not data.get("informational")},
                      "informational": {name: data["missing"] for name, data in summary["lists"].items()
                                        if data["missing"] and data.get("informational")}},
                     indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
