#!/usr/bin/env python3
"""Safe, deterministic storage for Supreme Team Taste preferences.

The project profile lives at ``skillset-saves/preferences/taste.json`` and the
user profile at ``~/.supremeteam/preferences/taste.json``.  Writes are explicit,
revision checked, atomic, and optionally accompanied by immutable run evidence.
This module intentionally uses only the standard library so it can also be used
from harness hooks and installation diagnostics.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Callable, Iterable

SCHEMA_VERSION = 1
PROJECT_RELATIVE = Path("skillset-saves/preferences/taste.json")
LEGACY_RELATIVE = Path("skillset-saves/preferences/taste.md")
GLOBAL_RELATIVE = Path(".supremeteam/preferences/taste.json")
LEGACY_HEADER = "# Supreme Team Taste Preferences (legacy v1)"
SENSITIVE = re.compile(r"(?i)(password|secret|token|api[_-]?key|private[_-]?key|credential)")
SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class TasteError(ValueError):
    """A preference contract was refused without mutating durable state."""


class RevisionConflict(TasteError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _safe_root(root: Path) -> Path:
    expanded = root.expanduser().absolute()
    if expanded.is_symlink():
        raise TasteError(f"store root may not be a symlink: {expanded}")
    return expanded.resolve()


def store_path(project_root: Path, scope: str, *, home: Path | None = None) -> Path:
    if scope not in {"project", "global"}:
        raise TasteError("scope must be project or global")
    root = _safe_root(project_root if scope == "project" else (home or Path.home()))
    relative = PROJECT_RELATIVE if scope == "project" else GLOBAL_RELATIVE
    path = root / relative
    # Existing parent symlinks must not redirect preference state out of its root.
    current = root
    for part in relative.parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise TasteError(f"preference path contains a symlink: {current}")
    try:
        path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise TasteError("preference path escapes its store root") from exc
    return path


def empty_profile(scope: str) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "revision": 0, "scope": scope, "preferences": []}


def normalize_key(key: str) -> str:
    key = re.sub(r"[\s_]+", "-", str(key).strip().lower())
    if not SAFE_KEY.fullmatch(key):
        raise TasteError(f"invalid preference key: {key!r}")
    return key


def normalize_preferences(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize exact duplicates while retaining genuine conflicts."""
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict) or "key" not in raw or "value" not in raw:
            raise TasteError("each preference requires key and value")
        item = copy.deepcopy(raw)
        item["key"] = normalize_key(item["key"])
        item.setdefault("status", "active")
        item.setdefault("precedence", 0)
        signature = canonical_json(item)
        if signature not in seen:
            seen.add(signature)
            result.append(item)
    return sorted(result, key=lambda x: (x["key"], -int(x.get("precedence", 0)), canonical_json(x)))


def validate_profile(profile: Any, *, expected_scope: str | None = None) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise TasteError("profile must be a JSON object")
    if profile.get("schema_version") != SCHEMA_VERSION:
        raise TasteError(f"unsupported schema_version {profile.get('schema_version')!r}")
    if not isinstance(profile.get("revision"), int) or profile["revision"] < 0:
        raise TasteError("revision must be a non-negative integer")
    if profile.get("scope") not in {"project", "global"}:
        raise TasteError("profile scope must be project or global")
    if expected_scope and profile["scope"] != expected_scope:
        raise TasteError(f"profile scope is {profile['scope']!r}, expected {expected_scope!r}")
    profile = copy.deepcopy(profile)
    profile["preferences"] = normalize_preferences(profile.get("preferences", []))
    return profile


def read_profile(path: Path, scope: str, *, create: bool = False) -> dict[str, Any]:
    if not path.exists():
        profile = empty_profile(scope)
        if create:
            atomic_replace(path, profile)
        return profile
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        # Never repair or overwrite corrupt evidence implicitly.
        raise TasteError(f"corrupt preference JSON preserved at {path}: {exc}") from exc
    return validate_profile(raw, expected_scope=scope)


def atomic_replace(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


@contextmanager
def mutation_lock(path: Path, timeout: float = 2.0):
    """Cross-process lock; revision is re-read only after this is acquired."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(f".{path.name}.lock")
    deadline = time.monotonic() + timeout
    fd = None
    while fd is None:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RevisionConflict(f"concurrent mutation lock held for {path}")
            time.sleep(0.01)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        fd = None
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock.unlink(missing_ok=True)


def requires_confirmation(action: str) -> bool:
    return action in {"migrate", "import", "promote", "specialize", "deprecate", "revoke", "reset", "both"}


class TasteStore:
    def __init__(self, project_root: Path | str, *, home: Path | str | None = None):
        self.project_root = _safe_root(Path(project_root))
        self.home = _safe_root(Path(home)) if home is not None else _safe_root(Path.home())

    def path(self, scope: str) -> Path:
        return store_path(self.project_root, scope, home=self.home)

    def load(self, scope: str, *, create: bool = False) -> dict[str, Any]:
        return read_profile(self.path(scope), scope, create=create)

    def write(self, scope: str, preferences: Iterable[dict[str, Any]], *,
              expected_revision: int, confirm: bool = False,
              evidence_dir: Path | None = None) -> dict[str, Any]:
        path = self.path(scope)
        with mutation_lock(path):
            current = self.load(scope)
            if current["revision"] != expected_revision:
                raise RevisionConflict(f"revision conflict: expected {expected_revision}, found {current['revision']}")
            proposed = copy.deepcopy(current)
            proposed["preferences"] = normalize_preferences(preferences)
            proposed["revision"] += 1
            if not confirm:
                return {"confirmed": False, "before": current, "after": proposed,
                        "before_hash": canonical_hash(current), "after_hash": canonical_hash(proposed)}
            atomic_replace(path, proposed)
            self._evidence(evidence_dir, scope, current, proposed, "write")
            return proposed

    def write_both(self, project_preferences: Iterable[dict[str, Any]],
                   global_preferences: Iterable[dict[str, Any]], *,
                   expected_project_revision: int, expected_global_revision: int,
                   confirm: bool = False, evidence_dir: Path | None = None,
                   after_first: Callable[[], None] | None = None) -> dict[str, Any]:
        before_p, before_g = self.load("project"), self.load("global")
        if before_p["revision"] != expected_project_revision or before_g["revision"] != expected_global_revision:
            raise RevisionConflict("revision conflict during both write")
        after_p, after_g = copy.deepcopy(before_p), copy.deepcopy(before_g)
        after_p.update(revision=before_p["revision"] + 1, preferences=normalize_preferences(project_preferences))
        after_g.update(revision=before_g["revision"] + 1, preferences=normalize_preferences(global_preferences))
        preview = {"confirmed": False, "project": {"before": before_p, "after": after_p},
                   "global": {"before": before_g, "after": after_g}}
        if not confirm:
            return preview
        p_path, g_path = self.path("project"), self.path("global")
        existed_p, existed_g = p_path.exists(), g_path.exists()
        try:
            atomic_replace(p_path, after_p)
            if after_first:
                after_first()
            # Recheck the other half immediately before commit.
            if self.load("global")["revision"] != expected_global_revision:
                raise RevisionConflict("global revision changed during both write")
            atomic_replace(g_path, after_g)
        except Exception:
            if existed_p:
                atomic_replace(p_path, before_p)
            else:
                p_path.unlink(missing_ok=True)
            if existed_g:
                atomic_replace(g_path, before_g)
            else:
                g_path.unlink(missing_ok=True)
            self._evidence(evidence_dir, "both", {"project": before_p, "global": before_g},
                           {"project": after_p, "global": after_g}, "rollback")
            raise
        self._evidence(evidence_dir, "both", {"project": before_p, "global": before_g},
                       {"project": after_p, "global": after_g}, "write")
        return {"project": after_p, "global": after_g}

    @staticmethod
    def _evidence(directory: Path | None, scope: str, before: Any, after: Any, action: str) -> None:
        if directory is None:
            return
        directory = directory.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        record = {"schema_version": 1, "action": action, "scope": scope,
                  "before": before, "after": after,
                  "before_hash": canonical_hash(before), "after_hash": canonical_hash(after)}
        target = directory / f"{action}-{scope}-{canonical_hash(record)[:12]}.json"
        if not target.exists():
            atomic_replace(target, record)


def resolve_effective(global_profile: dict[str, Any], project_profile: dict[str, Any],
                      explicit: Iterable[dict[str, Any]] = ()) -> dict[str, Any]:
    """Resolve without writing. Explicit instructions outrank project and global."""
    candidates: list[dict[str, Any]] = []
    for rank, source in ((100, global_profile.get("preferences", [])),
                         (200, project_profile.get("preferences", [])), (300, explicit)):
        for raw in normalize_preferences(source):
            item = copy.deepcopy(raw)
            item["effective_precedence"] = rank + int(item.get("precedence", 0))
            candidates.append(item)
    resolved: dict[str, Any] = {}
    conflicts: list[dict[str, Any]] = []
    for key in sorted({x["key"] for x in candidates}):
        active = [x for x in candidates if x["key"] == key and x.get("status") not in {"deprecated", "revoked"}]
        if not active:
            continue
        highest = max(x["effective_precedence"] for x in active)
        winners = [x for x in active if x["effective_precedence"] == highest]
        values = {canonical_json(x["value"]) for x in winners}
        if len(values) > 1:
            conflicts.append({"key": key, "precedence": highest, "candidates": winners})
            continue
        winner = winners[0]
        if winner.get("value") is None or winner.get("value") == "deny" or winner.get("deny") is True:
            continue
        resolved[key] = winner["value"]
    return {"preferences": resolved, "conflicts": conflicts,
            "hash": canonical_hash({"preferences": resolved, "conflicts": conflicts})}


def transform(profile: dict[str, Any], action: str, key: str | None = None,
              value: Any = None) -> dict[str, Any]:
    result = validate_profile(profile)
    items = result["preferences"]
    normalized = normalize_key(key) if key else None
    if action == "reset":
        items = []
    elif action in {"deprecate", "revoke"}:
        found = False
        for item in items:
            if item["key"] == normalized:
                item["status"] = "deprecated" if action == "deprecate" else "revoked"
                found = True
        if not found:
            raise TasteError(f"unknown preference {normalized!r}")
    elif action in {"promote", "specialize"}:
        items.append({"key": normalized, "value": value, "status": "active",
                      "precedence": 10 if action == "specialize" else 0,
                      "provenance": action})
    else:
        raise TasteError(f"unknown transform {action!r}")
    result["preferences"] = normalize_preferences(items)
    return result


def import_profile(payload: str | bytes, scope: str) -> dict[str, Any]:
    try:
        raw = json.loads(payload)
    except (TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TasteError(f"invalid import JSON: {exc}") from exc
    profile = validate_profile(raw, expected_scope=scope)
    for item in profile["preferences"]:
        if SENSITIVE.search(item["key"]) or (isinstance(item["value"], str) and SENSITIVE.search(item["value"])):
            item["value"] = "[REDACTED]"
            item["status"] = "revoked"
    return profile


def render_markdown(profile: dict[str, Any]) -> str:
    profile = validate_profile(profile)
    lines = ["# Taste Preferences", "", f"Revision: {profile['revision']}", ""]
    for item in profile["preferences"]:
        value = canonical_json(item["value"])
        lines.append(f"- `{item['key']}` = `{value}` ({item['status']})")
    if not profile["preferences"]:
        lines.append("_No preferences recorded._")
    return "\n".join(lines) + "\n"


def parse_legacy(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != LEGACY_HEADER:
        raise TasteError("legacy file is not the documented legacy v1 format")
    result = []
    for line in lines[1:]:
        if not line.strip():
            continue
        match = re.fullmatch(r"- ([a-z0-9][a-z0-9._-]*): (.+)", line)
        if not match:
            raise TasteError("legacy file contains undocumented Markdown")
        result.append({"key": match.group(1), "value": match.group(2), "status": "active",
                       "precedence": 0, "provenance": "legacy-v1"})
    return normalize_preferences(result)


def migration_preview(project_root: Path | str) -> dict[str, Any]:
    root = _safe_root(Path(project_root))
    legacy, canonical = root / LEGACY_RELATIVE, root / PROJECT_RELATIVE
    if not legacy.exists():
        return {"action": "none", "reason": "legacy path absent"}
    if canonical.exists():
        return {"action": "none", "reason": "canonical record already exists", "legacy": str(legacy)}
    preferences = parse_legacy(legacy.read_text(encoding="utf-8"))
    profile = empty_profile("project")
    profile.update(revision=1, preferences=preferences)
    return {"action": "migrate", "confirmed": False, "legacy": str(legacy),
            "canonical": str(canonical), "profile": profile, "hash": canonical_hash(profile)}


def migrate_legacy(project_root: Path | str, *, confirm: bool = False) -> dict[str, Any]:
    preview = migration_preview(project_root)
    if preview["action"] == "none" or not confirm:
        return preview
    canonical = Path(preview["canonical"])
    evidence = canonical.parent / "migration-evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    source = Path(preview["legacy"])
    retained = evidence / f"taste-legacy-{hashlib.sha256(source.read_bytes()).hexdigest()[:12]}.md"
    if not retained.exists():
        shutil.copyfile(source, retained)
    atomic_replace(canonical, preview["profile"])
    return {**preview, "confirmed": True, "evidence": str(retained)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview and manage Taste preference stores")
    parser.add_argument("action", choices=("show", "init", "migrate"))
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--home")
    parser.add_argument("--scope", choices=("project", "global"), default="project")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        store = TasteStore(args.project_root, home=args.home)
        if args.action == "show":
            out = store.load(args.scope)
        elif args.action == "init":
            out = store.load(args.scope, create=args.confirm)
            out = {"confirmed": args.confirm, "profile": out, "path": str(store.path(args.scope))}
        else:
            out = migrate_legacy(args.project_root, confirm=args.confirm)
        print(json.dumps(out, indent=2, sort_keys=True))
        return 0
    except (OSError, TasteError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
