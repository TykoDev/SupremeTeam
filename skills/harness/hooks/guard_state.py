#!/usr/bin/env python3
"""Sole sanctioned writer for the guard/freeze boundary record.

``.harness-state/guard-state.json`` is the durable record the Action
Realization layer reads before every tool call (``pre_tool_use.py``). Until this
script existed it was the only durable state class in the catalog with no single
writer, which made the boundary self-liftable: one edit-tool write could clear a
freeze or set ``allow_dangerous`` and disable destructive-pattern blocking
outright. ``pre_tool_use.py`` now denies direct writes to the record and routes
them here, the same way core run records route through ``save_run.py`` and Taste
records through ``taste_prefs.py``.

What this writer guarantees that a hand edit did not:

* every freeze/block entry carries ``owner``, so ``unfreeze``'s authority check
  has data to check against;
* a release sets ``released_at`` and never deletes the entry, so the audit trail
  the guard skills promise survives;
* ``allow_dangerous`` carries an owner, a reason, a scope, and an expiry, so
  lifting the destructive-pattern block is a bounded, attributable act rather
  than a permanent global flag;
* corrupt bytes are never overwritten — a damaged record is reported, not
  silently replaced.

Usage::

    guard_state.py freeze  --glob G --owner O [--scope S] [--run-id R] [--approver A ...]
    guard_state.py block   --glob G --owner O [--scope S] [--run-id R] [--approver A ...]
    guard_state.py release --glob G --requester Q [--reason TEXT]
    guard_state.py allow-dangerous --owner O --reason TEXT --scope S [--minutes N]
    guard_state.py revoke-dangerous --requester Q
    guard_state.py read-only --run-id R --owner O --allow G [--allow G ...] [--scope S]
    guard_state.py release-read-only --run-id R --requester Q [--reason TEXT]
    guard_state.py status [--json]

Exit codes: ``0`` ok, ``1`` refused (authority, validation, or corrupt record),
``2`` usage error. Refusals print a reason to stderr and change nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _state  # noqa: E402  (path set above so the hook helpers resolve)

RECORD = "guard-state.json"
DEFAULT_DANGEROUS_MINUTES = 30
LIST_KEYS = ("frozen_globs", "blocked_globs", "read_only")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _path() -> Path:
    return _state.state_dir() / RECORD


def _refuse(message: str) -> None:
    print(f"refused: {message}", file=sys.stderr)
    raise SystemExit(1)


def _load() -> dict:
    """Read the record, refusing rather than overwriting damaged bytes."""
    path = _path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        _refuse(f"cannot read {path}: {exc}")
    if not raw.strip():
        return {}
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        _refuse(
            f"{path} is not valid JSON ({exc}). This writer never overwrites a corrupt "
            "boundary record, and pre_tool_use.py denies edit-tool writes to it, so the "
            "repair happens outside the agent's tool loop: an owner fixes or removes the "
            "file directly. Until then every boundary in it is unreadable and the hook "
            "falls back to the built-in destructive-pattern guard alone."
        )
    if not isinstance(state, dict):
        _refuse(f"{path} must contain a JSON object, found {type(state).__name__}.")
    for key in LIST_KEYS:
        if key in state and not isinstance(state[key], list):
            _refuse(f"{path}: '{key}' must be a list.")
    return state


def _save(state: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _records(state: dict, key: str) -> list:
    return [e for e in (state.get(key) or []) if isinstance(e, (str, dict))]


def _active(entry) -> bool:
    """A bare string is always active; a record is active until released."""
    if isinstance(entry, str):
        return bool(entry)
    return not (entry.get("released_at") or entry.get("released") is True)


def _entry_glob(entry) -> str:
    return entry if isinstance(entry, str) else str(entry.get("glob") or "")


def _authorized(entry: dict, requester: str) -> bool:
    """A release is authorized by the recording owner or a named approver."""
    if entry.get("owner") == requester:
        return True
    return requester in [str(a) for a in (entry.get("approvers") or [])]


# --- commands ---------------------------------------------------------------

def cmd_add(args, key: str) -> int:
    state = _load()
    entries = _records(state, key)
    for entry in entries:
        if _entry_glob(entry) == args.glob and _active(entry):
            _refuse(
                f"{args.glob} is already inside an active boundary in {key}. "
                "Release it first, or record a different glob."
            )
    entries.append({
        "glob": args.glob,
        "owner": args.owner,
        "scope": args.scope or "unscoped",
        "created_at": _now(),
        "run_id": args.run_id,
        "approvers": list(args.approver or []),
        "released_at": None,
    })
    state[key] = entries
    _save(state)
    print(json.dumps({"ok": True, "action": key, "glob": args.glob,
                      "owner": args.owner, "path": str(_path())}))
    return 0


def cmd_release(args) -> int:
    state = _load()
    hits = []
    for key in ("frozen_globs", "blocked_globs"):
        for entry in _records(state, key):
            if _entry_glob(entry) == args.glob and _active(entry):
                hits.append((key, entry))
    if not hits:
        _refuse(f"no active boundary matches {args.glob}.")

    for key, entry in hits:
        if isinstance(entry, str):
            _refuse(
                f"{args.glob} was recorded as a bare glob with no owner, so authority "
                "cannot be verified. Re-record it through this writer (guard_state.py "
                f"{'freeze' if key == 'frozen_globs' else 'block'} --glob ... --owner ...) "
                "before releasing it."
            )
        if not _authorized(entry, args.requester):
            _refuse(
                f"{args.requester} is neither the owner ({entry.get('owner')}) nor a named "
                f"approver of the boundary on {args.glob}. A boundary is lifted only by its "
                "owner or a delegate recorded at freeze time."
            )

    for _key, entry in hits:
        entry["released_at"] = _now()
        entry["released_by"] = args.requester
        entry["release_reason"] = args.reason or "not stated"
    _save(state)
    print(json.dumps({"ok": True, "action": "release", "glob": args.glob,
                      "released_by": args.requester, "records": len(hits)}))
    return 0


def cmd_allow_dangerous(args) -> int:
    state = _load()
    minutes = max(1, int(args.minutes))
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    state["allow_dangerous"] = {
        "owner": args.owner,
        "reason": args.reason,
        "scope": args.scope,
        "created_at": _now(),
        "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save(state)
    print(json.dumps({"ok": True, "action": "allow-dangerous", "owner": args.owner,
                      "scope": args.scope, "expires_at": state["allow_dangerous"]["expires_at"],
                      "note": "destructive-pattern blocking is lifted globally until this expires"}))
    return 0


def cmd_revoke_dangerous(args) -> int:
    state = _load()
    current = state.get("allow_dangerous")
    if not current:
        _refuse("allow_dangerous is not set.")
    if isinstance(current, dict) and not _authorized(current, args.requester):
        _refuse(
            f"{args.requester} is not the owner ({current.get('owner')}) of the "
            "allow_dangerous grant."
        )
    state["allow_dangerous"] = False
    _save(state)
    print(json.dumps({"ok": True, "action": "revoke-dangerous", "requester": args.requester}))
    return 0


def cmd_read_only(args) -> int:
    state = _load()
    entries = _records(state, "read_only")
    for entry in entries:
        if isinstance(entry, dict) and entry.get("run_id") == args.run_id and _active(entry):
            _refuse(f"run {args.run_id} already has an active read_only record.")
    entries.append({
        "run_id": args.run_id,
        "owner": args.owner,
        "scope": args.scope or "read-only run",
        "allow": list(args.allow),
        "created_at": _now(),
        "released_at": None,
    })
    state["read_only"] = entries
    _save(state)
    print(json.dumps({"ok": True, "action": "read-only", "run_id": args.run_id,
                      "owner": args.owner, "allow": list(args.allow)}))
    return 0


def cmd_release_read_only(args) -> int:
    state = _load()
    hits = [e for e in _records(state, "read_only")
            if isinstance(e, dict) and e.get("run_id") == args.run_id and _active(e)]
    if not hits:
        _refuse(f"no active read_only record for run {args.run_id}.")
    for entry in hits:
        if not _authorized(entry, args.requester):
            _refuse(
                f"{args.requester} is not the owner ({entry.get('owner')}) of the "
                f"read_only record on run {args.run_id}."
            )
    for entry in hits:
        entry["released_at"] = _now()
        entry["released_by"] = args.requester
        entry["release_reason"] = args.reason or "not stated"
    _save(state)
    print(json.dumps({"ok": True, "action": "release-read-only", "run_id": args.run_id,
                      "released_by": args.requester}))
    return 0


def cmd_status(args) -> int:
    state = _load()
    report = {
        "path": str(_path()),
        "exists": _path().exists(),
        "frozen_globs": [_entry_glob(e) for e in _records(state, "frozen_globs") if _active(e)],
        "blocked_globs": [_entry_glob(e) for e in _records(state, "blocked_globs") if _active(e)],
        "read_only_runs": [e.get("run_id") for e in _records(state, "read_only")
                           if isinstance(e, dict) and _active(e)],
        "allow_dangerous": state.get("allow_dangerous") or False,
        "unowned_entries": [
            _entry_glob(e)
            for key in ("frozen_globs", "blocked_globs")
            for e in _records(state, key)
            if _active(e) and (isinstance(e, str) or not e.get("owner"))
        ],
    }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"record: {report['path']} (exists: {report['exists']})")
        print(f"frozen:  {report['frozen_globs'] or '-'}")
        print(f"blocked: {report['blocked_globs'] or '-'}")
        print(f"read-only runs: {report['read_only_runs'] or '-'}")
        print(f"allow_dangerous: {report['allow_dangerous']}")
        if report["unowned_entries"]:
            print(f"WARNING unowned (not releasable by authority check): {report['unowned_entries']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guard_state.py",
        description="Sole sanctioned writer for .harness-state/guard-state.json.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, key in (("freeze", "frozen_globs"), ("block", "blocked_globs")):
        p = sub.add_parser(name, help=f"record an owned boundary in {key}")
        p.add_argument("--glob", required=True)
        p.add_argument("--owner", required=True, help="contributor accountable for the boundary")
        p.add_argument("--scope", help="why the boundary exists")
        p.add_argument("--run-id")
        p.add_argument("--approver", action="append",
                       help="delegate permitted to release (repeatable)")
        p.set_defaults(func=lambda a, _k=key: cmd_add(a, _k))

    p = sub.add_parser("release", help="set released_at on a boundary (never deletes)")
    p.add_argument("--glob", required=True)
    p.add_argument("--requester", required=True)
    p.add_argument("--reason")
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("allow-dangerous", help="lift destructive-pattern blocking, with an expiry")
    p.add_argument("--owner", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--scope", required=True, help="the operation this grant is for")
    p.add_argument("--minutes", type=int, default=DEFAULT_DANGEROUS_MINUTES)
    p.set_defaults(func=cmd_allow_dangerous)

    p = sub.add_parser("revoke-dangerous", help="restore destructive-pattern blocking")
    p.add_argument("--requester", required=True)
    p.set_defaults(func=cmd_revoke_dangerous)

    p = sub.add_parser("read-only", help="confine a run to its own save path")
    p.add_argument("--run-id", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--allow", action="append", required=True,
                   help="glob the run may still write (repeatable)")
    p.add_argument("--scope")
    p.set_defaults(func=cmd_read_only)

    p = sub.add_parser("release-read-only", help="lift a read-only run boundary")
    p.add_argument("--run-id", required=True)
    p.add_argument("--requester", required=True)
    p.add_argument("--reason")
    p.set_defaults(func=cmd_release_read_only)

    p = sub.add_parser("status", help="report the effective boundary")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
