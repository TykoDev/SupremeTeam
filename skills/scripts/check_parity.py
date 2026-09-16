#!/usr/bin/env python3
"""Mechanical functional-parity check for a redesign variant.

Reads a design inventory (``design-inventory.json``, schema 1) and scans a
variant's living prototype (``app.html``) and component catalog
(``components.html``) for the parity markers the prototyper must place:

    routes        data-route="<id>"                        in app.html
    states        data-state="<state>" inside the route view,
                  or data-route-state="<route id>:<state>"  in app.html
    components    data-component="<id>"                    in components.html and app.html
    interactions  data-interaction="<id>"                  in app.html
    flows         data-flow="<id>"                         in app.html

It writes a typed ``probe`` record (gates.yaml) whose ``inputs`` bind the
inventory and the prototype files by sha256, so a changed inventory or prototype
makes the record fail the gate as input hash drift.

    python skills/scripts/check_parity.py --inventory <design-inventory.json> \
        --app <app.html> --components <components.html> \
        --out <redesign/evidence/parity-<variant>.json> [--project-root .] [--min-coverage 1.0]

Exit 0 when coverage meets the threshold, 1 when ids are missing, 2 on an
input or engine error. The JSON summary is printed to stdout.
"""
from __future__ import annotations

import argparse
import hashlib
import html.parser
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ID_RE = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
PARITY_LISTS = ("routes", "components", "interactions", "flows")


class ParityError(ValueError):
    """Input or engine failure: exit 2, never a pass."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MarkerScanner(html.parser.HTMLParser):
    """Collect parity markers from rendered markup only (no comments, no scripts)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.routes: set[str] = set()
        self.components: set[str] = set()
        self.interactions: set[str] = set()
        self.flows: set[str] = set()
        self.route_states: set[tuple[str, str]] = set()
        self._route_stack: list[str | None] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "template"}:
            self._skip_depth += 1
        if self._skip_depth:
            self._route_stack.append(None)
            return
        values = {name: (value or "").strip() for name, value in attrs}
        route = values.get("data-route")
        if route:
            self.routes.add(route)
        self._route_stack.append(route or None)
        current = next((r for r in reversed(self._route_stack) if r), None)
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
        if self._route_stack:
            self._route_stack.pop()
        if tag in {"script", "style", "template"} and self._skip_depth:
            self._skip_depth -= 1


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
        seen: set[str] = set()
        for item in items:
            ident = str((item or {}).get("id", "")) if isinstance(item, dict) else ""
            if not ID_RE.match(ident):
                raise ParityError(f"inventory {name} entry has an invalid id: {ident!r}")
            if ident in seen:
                raise ParityError(f"inventory {name} has duplicate id {ident!r}")
            seen.add(ident)
    return data


def scan(path: Path) -> MarkerScanner:
    scanner = MarkerScanner()
    try:
        scanner.feed(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        raise ParityError(f"cannot read {path}: {exc}") from exc
    return scanner


def evaluate(inventory: dict, app: MarkerScanner, catalog: MarkerScanner) -> dict:
    expected = {name: [item["id"] for item in inventory[name]] for name in PARITY_LISTS}
    expected_states = [(route["id"], str(state)) for route in inventory["routes"]
                       for state in (route.get("states") or [])]
    found = {
        "routes": app.routes,
        "components": catalog.components & app.components,
        "interactions": app.interactions,
        "flows": app.flows,
    }
    report: dict[str, dict] = {}
    total_expected = total_found = 0
    for name in PARITY_LISTS:
        missing = sorted(i for i in expected[name] if i not in found[name])
        report[name] = {"expected": len(expected[name]), "found": len(expected[name]) - len(missing), "missing": missing}
        total_expected += len(expected[name])
        total_found += len(expected[name]) - len(missing)
    missing_states = sorted(f"{r}:{s}" for r, s in expected_states if (r, s) not in app.route_states)
    report["states"] = {"expected": len(expected_states), "found": len(expected_states) - len(missing_states), "missing": missing_states}
    total_expected += len(expected_states)
    total_found += len(expected_states) - len(missing_states)
    catalog_only_missing = sorted(i for i in expected["components"] if i not in catalog.components)
    app_only_missing = sorted(i for i in expected["components"] if i not in app.components)
    report["components"]["missing_in_catalog"] = catalog_only_missing
    report["components"]["missing_in_app"] = app_only_missing
    coverage = 1.0 if total_expected == 0 else total_found / total_expected
    return {"coverage": round(coverage, 4), "lists": report, "expected": total_expected, "found": total_found}


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a redesign variant for functional parity against the design inventory.")
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--components", required=True)
    parser.add_argument("--out", required=True, help="typed probe record to write (JSON)")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--min-coverage", type=float, default=1.0)
    args = parser.parse_args()
    root = Path(args.project_root)
    inventory_path, app_path, catalog_path = Path(args.inventory), Path(args.app), Path(args.components)
    try:
        inventory = load_inventory(inventory_path)
        summary = evaluate(inventory, scan(app_path), scan(catalog_path))
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
        "lists": summary["lists"],
        "result": {"status": "pass" if passed else "fail",
                   "summary": f"{summary['found']}/{summary['expected']} inventory ids present"},
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
                      "missing": {name: data["missing"] for name, data in summary["lists"].items() if data["missing"]}},
                     indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
