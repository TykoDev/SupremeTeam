#!/usr/bin/env python3
"""Atomic writer and resolver for global and project Taste preference records."""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SCOPES = ("global", "project")

class PreferenceError(ValueError):
    """A Taste record or requested mutation violates the writer contract."""


def blank_record(scope: str) -> dict[str, Any]:
    if scope not in SCOPES:
        raise PreferenceError(f"invalid scope: {scope}")
    return {"schema_version": SCHEMA_VERSION, "scope": scope, "revision": 0, "updated_at": None, "preferences": []}


def validate_record(record: Any, expected_scope: str | None = None) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise PreferenceError("record must be an object")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise PreferenceError(f"schema_version must be {SCHEMA_VERSION}")
    scope = record.get("scope")
    if scope not in SCOPES or (expected_scope and scope != expected_scope):
        raise PreferenceError(f"record scope must be {expected_scope or 'global or project'}")
    if not isinstance(record.get("revision"), int) or record["revision"] < 0:
        raise PreferenceError("revision must be a non-negative integer")
    preferences = record.get("preferences")
    if not isinstance(preferences, list):
        raise PreferenceError("preferences must be a list")
    seen: set[str] = set()
    for item in preferences:
        if not isinstance(item, dict):
            raise PreferenceError("each preference must be an object")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise PreferenceError("each preference requires a non-empty string id")
        if identifier in seen:
            raise PreferenceError(f"duplicate preference id: {identifier}")
        seen.add(identifier)
        if not isinstance(item.get("value"), str) or not item["value"].strip():
            raise PreferenceError(f"preference {identifier!r} requires a non-empty value")
        if item.get("kind", "preference") not in ("preference", "anti-preference"):
            raise PreferenceError(f"preference {identifier!r} has invalid kind")
        if item.get("source", "explicit") not in ("explicit", "inferred"):
            raise PreferenceError(f"preference {identifier!r} has invalid source")
        for key in ("examples", "counterexamples"):
            if key in item and (not isinstance(item[key], list) or not all(isinstance(x, str) for x in item[key])):
                raise PreferenceError(f"preference {identifier!r} {key} must be a string list")
    return record


def load_record(path: Path, scope: str) -> dict[str, Any]:
    if not path.exists():
        return blank_record(scope)
    try:
        return validate_record(json.loads(path.read_text(encoding="utf-8")), scope)
    except (OSError, json.JSONDecodeError) as exc:
        raise PreferenceError(f"cannot read {scope} record {path}: {exc}") from exc


def atomic_write(path: Path, record: dict[str, Any]) -> None:
    validate_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _stamp(record: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(record)
    result["revision"] += 1
    result["updated_at"] = datetime.now(timezone.utc).isoformat()
    return result


def upsert(record: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(candidate)
    probe = blank_record(record["scope"])
    probe["preferences"] = [candidate]
    validate_record(probe)
    result = _stamp(record)
    result["preferences"] = [p for p in result["preferences"] if p["id"] != candidate["id"]]
    result["preferences"].append(candidate)
    result["preferences"].sort(key=lambda item: item["id"])
    return result


def revoke(record: dict[str, Any], identifiers: list[str]) -> dict[str, Any]:
    result = _stamp(record)
    wanted = set(identifiers)
    result["preferences"] = [p for p in result["preferences"] if p["id"] not in wanted]
    return result


def resolve(global_record: dict[str, Any], project_record: dict[str, Any]) -> dict[str, Any]:
    validate_record(global_record, "global")
    validate_record(project_record, "project")
    merged = {item["id"]: {**copy.deepcopy(item), "effective_scope": "global"} for item in global_record["preferences"]}
    for item in project_record["preferences"]:
        merged[item["id"]] = {**copy.deepcopy(item), "effective_scope": "project"}
    return {"schema_version": SCHEMA_VERSION, "resolution": "project-over-global-by-id", "preferences": [merged[key] for key in sorted(merged)]}


def require_confirmation(args: argparse.Namespace, reason: str) -> None:
    if not args.confirm:
        raise PreferenceError(f"{reason} requires --confirm")


def default_paths(project_root: Path) -> tuple[Path, Path]:
    return Path.home() / ".agents" / "preferences" / "taste.json", project_root / "skillset-saves" / "preferences" / "taste.md"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("operation", choices=("inspect", "resolve", "upsert", "revoke", "reset", "promote", "import", "export"))
    p.add_argument("--scope", choices=SCOPES)
    p.add_argument("--id", action="append")
    p.add_argument("--value")
    p.add_argument("--kind", choices=("preference", "anti-preference"), default="preference")
    p.add_argument("--source", choices=("explicit", "inferred"), default="explicit")
    p.add_argument("--example", action="append", default=[])
    p.add_argument("--counterexample", action="append", default=[])
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--global-file", type=Path)
    p.add_argument("--project-file", type=Path)
    p.add_argument("--project-root", type=Path, default=Path.cwd())
    p.add_argument("--confirm", action="store_true", help="confirm inferred, widening, destructive, or bulk mutation")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    global_default, project_default = default_paths(args.project_root.resolve())
    paths = {"global": args.global_file or global_default, "project": args.project_file or project_default}
    records = {scope: load_record(path, scope) for scope, path in paths.items()}

    if args.operation == "resolve":
        result = resolve(records["global"], records["project"])
    elif args.operation == "inspect":
        result = records[args.scope] if args.scope else records
    elif args.operation == "export":
        result = resolve(records["global"], records["project"]) if not args.scope else records[args.scope]
    else:
        if not args.scope and args.operation not in ("promote",):
            raise PreferenceError(f"{args.operation} requires --scope")
        if args.operation == "upsert":
            if not args.id or len(args.id) != 1 or not args.value:
                raise PreferenceError("upsert requires exactly one --id and --value")
            if args.source == "inferred":
                require_confirmation(args, "an inferred preference")
            result = upsert(records[args.scope], {"id": args.id[0], "value": args.value, "kind": args.kind, "source": args.source, "examples": args.example, "counterexamples": args.counterexample})
            atomic_write(paths[args.scope], result)
        elif args.operation == "revoke":
            if not args.id:
                raise PreferenceError("revoke requires --id")
            if len(args.id) > 1:
                require_confirmation(args, "bulk revocation")
            result = revoke(records[args.scope], args.id)
            atomic_write(paths[args.scope], result)
        elif args.operation == "reset":
            if args.scope == "global":
                require_confirmation(args, "global reset")
            result = _stamp(blank_record(args.scope))
            atomic_write(paths[args.scope], result)
        elif args.operation == "promote":
            require_confirmation(args, "promotion to global scope")
            if not args.id or len(args.id) != 1:
                raise PreferenceError("promote requires exactly one --id")
            identifier = args.id[0]
            source = next((p for p in records["project"]["preferences"] if p["id"] == identifier), None)
            if source is None:
                raise PreferenceError(f"project preference not found: {identifier}")
            result = upsert(records["global"], source)
            atomic_write(paths["global"], result)
        elif args.operation == "import":
            require_confirmation(args, "bulk import")
            if not args.input:
                raise PreferenceError("import requires --input")
            incoming = validate_record(json.loads(args.input.read_text(encoding="utf-8")), args.scope)
            result = _stamp(incoming)
            atomic_write(paths[args.scope], result)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PreferenceError, OSError, json.JSONDecodeError) as exc:
        print(f"taste_prefs: {exc}", file=os.sys.stderr)
        raise SystemExit(2)
