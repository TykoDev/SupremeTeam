#!/usr/bin/env python3
"""The sole writer for durable Supreme Team Taste preferences.

Canonical records are JSON; ``taste.md`` is a deterministic rendered view.  The
global root is ``SUPREMETEAM_HOME`` when set, then ``CODEX_HOME``/``AGENTS_HOME``,
then the platform user-data convention (XDG data, macOS Application Support, or
Windows local app data). It is rejected if it resolves inside the checkout. The
module deliberately uses only the Python standard library so hooks and recovery
tools can invoke it in the minimum supported runtime.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = "supremeteam-taste-preferences"
VERSION = 1
MUTATIONS = {"propose", "confirm", "set", "deprecate", "revoke", "promote", "specialize", "import", "reset"}
STATES = {"proposed", "active", "deprecated"}
# A mutation holds the lock for milliseconds, so a lock this old was abandoned.
LOCK_STALE_AFTER = 600
SENSITIVE_KEY = re.compile(r"(?:secret|password|passwd|credential|token|api[_-]?key|private[_-]?key|cookie|authorization|prompt|conversation|email|phone|address|full[_-]?name|user[_-]?name|social[_-]?security|ssn)", re.I)
SENSITIVE_VALUE = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]+|\b(?:sk|ghp|github_pat|xox[baprs])[-_A-Za-z0-9]{12,}|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)",
    re.I,
)
MAX_TEXT = 1000


class TasteError(Exception):
    def __init__(self, code: str, message: str, **details: Any):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details


def emit(ok: bool, **payload: Any) -> int:
    print(json.dumps({"ok": ok, **payload}, sort_keys=True))
    return 0 if ok else 1


def canonical_bytes(record: dict[str, Any], *, digestless: bool = False) -> bytes:
    value = copy.deepcopy(record)
    if digestless:
        value.pop("canonical_record_digest", None)
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def digest(record: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(record, digestless=True)).hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def global_root() -> Path:
    if os.environ.get("SUPREMETEAM_HOME"):
        return Path(os.environ["SUPREMETEAM_HOME"]).expanduser().resolve()
    for key in ("CODEX_HOME", "AGENTS_HOME"):
        if os.environ.get(key):
            return (Path(os.environ[key]).expanduser().resolve() / "supremeteam")
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or Path.home() / "AppData" / "Local")
        return (base / "SupremeTeam").resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "SupremeTeam").resolve()
    return (Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "supremeteam").resolve()


def paths(project_root: Path, scope: str) -> dict[str, Path]:
    project_root = project_root.resolve()
    base = project_root / "skillset-saves" / "preferences" if scope == "project" else global_root() / "preferences"
    if scope == "global" and (base.resolve() == project_root or project_root in base.resolve().parents):
        raise TasteError("unsafe_global_path", "global preference state may not be located inside a checkout", path=str(base))
    return {"json": base / "taste.json", "md": base / "taste.md", "history": base / "_history", "journal": base / "taste.journal.jsonl", "lock": base / "taste.lock"}


def scope_identity(project_root: Path, scope: str) -> dict[str, str]:
    if scope == "project":
        return {"kind": "project", "id": "sha256:" + hashlib.sha256(str(project_root.resolve()).encode()).hexdigest()}
    return {"kind": "global", "id": "host-user-data"}


def owner_identity() -> dict[str, str] | None:
    explicit = os.environ.get("SUPREMETEAM_OWNER")
    if explicit and re.fullmatch(r"[A-Za-z0-9._-]{1,80}", explicit):
        return {"id": explicit, "source": "SUPREMETEAM_OWNER"}
    # A stable opaque identifier is useful for concurrency provenance without
    # persisting account names, hostnames, home paths, or other personal data.
    try:
        material = f"{getpass.getuser()}\0{socket.gethostname()}".encode()
        return {"id": "sha256:" + hashlib.sha256(material).hexdigest(), "source": "local-opaque"}
    except Exception:
        return None


def blank(project_root: Path, scope: str) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": SCHEMA, "schema_version": VERSION, "scope": scope_identity(project_root, scope), "revision": 0, "generated_at": now(), "entries": {}, "tombstones": {}, "previous_revision_digest": None}
    owner = owner_identity()
    if owner:
        result["owner"] = owner
    result["canonical_record_digest"] = digest(result)
    return result


def validate_safe(value: Any, path: str = "$", *, redact: bool = False) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            if not isinstance(key, str) or SENSITIVE_KEY.search(key):
                if redact:
                    continue
                raise TasteError("sensitive_input", "sensitive or personal fields are not accepted", field=f"{path}.{key}")
            clean[key] = validate_safe(item, f"{path}.{key}", redact=redact)
        return clean
    if isinstance(value, list):
        if len(value) > 100:
            raise TasteError("unbounded_input", "lists are limited to 100 items", field=path)
        return [validate_safe(v, f"{path}[]", redact=redact) for v in value]
    if isinstance(value, str):
        if len(value) > MAX_TEXT:
            if redact:
                return value[:MAX_TEXT] + "[REDACTED:TRUNCATED]"
            raise TasteError("unbounded_input", f"text is limited to {MAX_TEXT} characters", field=path)
        if SENSITIVE_VALUE.search(value):
            if redact:
                return "[REDACTED]"
            raise TasteError("sensitive_input", "secret, credential, token, or personal identifier detected", field=path)
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TasteError("invalid_input", "preference values must be JSON data", field=path)


def validate(record: Any, expected_scope: str) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("schema_version") != VERSION:
        raise TasteError("invalid_schema", f"expected {SCHEMA} schema version {VERSION}")
    required = {"scope", "revision", "generated_at", "entries", "tombstones", "previous_revision_digest", "canonical_record_digest"}
    if not required <= record.keys() or record.get("scope", {}).get("kind") != expected_scope:
        raise TasteError("invalid_record", "record is missing required fields or has the wrong scope")
    if not isinstance(record["revision"], int) or record["revision"] < 0 or not isinstance(record["entries"], dict) or not isinstance(record["tombstones"], dict):
        raise TasteError("invalid_record", "revision, entries, or tombstones have an invalid type")
    if record["canonical_record_digest"] != digest(record):
        raise TasteError("digest_mismatch", "canonical record digest does not match the stored bytes")
    return record


def load(project_root: Path, scope: str) -> tuple[dict[str, Any], bool]:
    target = paths(project_root, scope)["json"]
    if not target.exists():
        return blank(project_root, scope), False
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
        return validate(record, scope), True
    except TasteError:
        raise
    except Exception as exc:
        raise TasteError("corrupt_record", "canonical record is unreadable; original bytes were preserved", path=str(target), recovery="repair or move the file explicitly before retrying") from exc


def render(record: dict[str, Any]) -> str:
    lines = ["# Supreme Team Taste Preferences", "", f"- Scope: `{record['scope']['kind']}`", f"- Revision: `{record['revision']}`", f"- Generated: `{record['generated_at']}`", f"- Digest: `{record['canonical_record_digest']}`", "", "## Entries", ""]
    if not record["entries"]:
        lines.append("_No active entries._")
    for entry_id, entry in sorted(record["entries"].items()):
        lines += [f"### `{entry_id}`", "", f"- State: `{entry['state']}`", f"- Value: `{json.dumps(entry['value'], sort_keys=True, ensure_ascii=False)}`", ""]
    lines += ["## Tombstones", ""]
    if not record["tombstones"]:
        lines.append("_No revoked entries._")
    for entry_id, item in sorted(record["tombstones"].items()):
        lines.append(f"- `{entry_id}` — revoked at `{item['revoked_at']}`")
    return "\n".join(lines) + "\n"


def host_id() -> str:
    """Opaque host identifier recorded in a lock; empty when the hostname is unavailable."""
    try:
        return hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16]
    except Exception:
        return ""


def pid_alive(pid: int) -> bool | None:
    """Whether a process exists on this host, or None where the platform cannot say."""
    if sys.platform == "win32":
        return None  # os.kill(pid, 0) raises a console event there instead of probing
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, OverflowError):  # a lock file is not trusted to hold a pid the platform accepts
        return None
    return True


def read_lock(path: Path) -> dict[str, Any]:
    """What a lock file records about its holder; empty when unreadable, as after a kill mid-write."""
    try:
        holder = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return holder if isinstance(holder, dict) else {}


def lock_age(path: Path, holder: dict[str, Any]) -> float | None:
    """Seconds since the lock was taken: the time it records, else the file's own."""
    try:
        taken = dt.datetime.fromisoformat(str(holder["created_at"]))
        return (dt.datetime.now(dt.timezone.utc) - taken).total_seconds()
    except (KeyError, ValueError, TypeError):
        pass
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def stale_reason(path: Path, holder: dict[str, Any]) -> str | None:
    """Why a lock is provably abandoned, or None when its holder may still be running."""
    pid, mine = holder.get("pid"), host_id()
    if type(pid) is int and pid > 0 and mine and holder.get("host") == mine and pid_alive(pid) is False:
        return "holder-dead"
    age = lock_age(path, holder)
    return "expired" if age is not None and age > LOCK_STALE_AFTER else None


def retrying(action: Any, attempts: int = 8) -> None:
    """Run a file operation with short retries: on Windows a reader holding the file open (host
    hook, indexer, antivirus, another writer checking the lock) makes a rename or delete fail
    transiently with PermissionError. The same policy as save_run._replace_with_retry,
    repeated because this module stays standalone."""
    delay = 0.05
    for attempt in range(attempts):
        try:
            action()
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.8)


def replace_with_retry(source: Path, target: Path, attempts: int = 8) -> None:
    retrying(lambda: os.replace(source, target), attempts)


def unlink_with_retry(path: Path) -> None:
    retrying(lambda: path.unlink(missing_ok=True))


def take(path: Path) -> str:
    """Create the lock file exclusively, record the holder in it, and return the token that proves it is ours."""
    token = uuid.uuid4().hex
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "host": host_id(), "created_at": now(), "token": token}).encode())
    except BaseException:
        os.close(fd)
        path.unlink(missing_ok=True)
        raise
    os.close(fd)
    return token


def reclaim(path: Path) -> dict[str, Any] | None:
    """Remove the lock at path if its holder is provably gone, and describe what was removed."""
    holder = read_lock(path)
    reason = stale_reason(path, holder)
    # A lock that changed between the two reads belongs to a writer that just took it.
    if reason is None or read_lock(path) != holder:
        return None
    unlink_with_retry(path)
    return {"reason": reason, "prior": {key: holder[key] for key in ("pid", "created_at") if isinstance(holder.get(key), (int, str)) and len(str(holder[key])) <= 64}}


def busy(path: Path) -> TasteError:
    holder = read_lock(path)
    details: dict[str, Any] = {"path": str(path), "stale_after_seconds": LOCK_STALE_AFTER}
    age = lock_age(path, holder)
    if age is not None:
        details["age_seconds"] = int(age)
    if type(holder.get("pid")) is int:
        details["holder_pid"] = holder["pid"]
    return TasteError("locked", "preference store is locked by another writer", **details)


class Held:
    """The lock files one writer owns. Each carries a token, so a lock is trusted or released only while it is still ours."""

    def __init__(self) -> None:
        self.locks: list[tuple[Path, str]] = []
        self.reclaimed: list[dict[str, Any]] = []

    def acquire(self, scope: str, target: dict[str, Path]) -> None:
        path = target["lock"]
        path.parent.mkdir(parents=True, exist_ok=True)
        removed = None
        try:
            token = take(path)
        except FileExistsError:
            removed = reclaim(path)
            if removed is None:
                raise busy(path) from None
            try:
                token = take(path)
            except FileExistsError:  # another writer took the freed lock first
                raise busy(path) from None
        self.locks.append((path, token))
        if removed:
            note = {"scope": scope, **removed}
            with target["journal"].open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": "lock_reclaimed", "at": now(), **note}, sort_keys=True) + "\n")
            self.reclaimed.append(note)

    def verify(self) -> None:
        for path, token in self.locks:
            if read_lock(path).get("token") != token:
                raise TasteError("lock_lost", "the store lock was reclaimed while this writer held it; nothing was written", path=str(path))

    def release(self) -> None:
        for path, token in self.locks:
            if read_lock(path).get("token") == token:
                unlink_with_retry(path)
        self.locks.clear()


def lock(destinations: dict[str, dict[str, Path]]) -> Held:
    held = Held()
    try:
        for scope, target in destinations.items():
            held.acquire(scope, target)
    except BaseException:
        held.release()
        raise
    return held


def stage(record: dict[str, Any], destination: dict[str, Path]) -> tuple[Path, Path]:
    destination["json"].parent.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    try:
        for suffix, content in ((".json.tmp", canonical_bytes(record)), (".md.tmp", render(record).encode())):
            fd, name = tempfile.mkstemp(prefix=".taste-", suffix=suffix, dir=destination["json"].parent)
            staged.append(Path(name))
            with os.fdopen(fd, "wb") as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
    except BaseException:
        for path in staged:
            path.unlink(missing_ok=True)
        raise
    return staged[0], staged[1]


def rollback(records: list[tuple[str, dict[str, Any], dict[str, Path], bool]], backups: list[dict[str, Path]], replaced: list[tuple[int, str]], journals: dict[int, int | None]) -> list[tuple[Path, Path | None]]:
    """Undo a partial commit. Returns each file that could not be restored with the backup that
    still holds its prior bytes. A journal only ever lists committed revisions, so its appended
    lines go first."""
    failed: list[tuple[Path, Path | None]] = []
    for index, size in journals.items():
        journal = records[index][2]["journal"]
        try:
            if size is None:
                journal.unlink(missing_ok=True)
            else:
                os.truncate(journal, size)
        except OSError:
            failed.append((journal, None))
    for index, key in reversed(replaced):
        dest = records[index][2]
        backup = backups[index].get(key)
        try:
            if backup:
                replace_with_retry(backup, dest[key])
            else:
                dest[key].unlink(missing_ok=True)
        except OSError:
            failed.append((dest[key], backup))
    return failed


def commit_pair(records: list[tuple[str, dict[str, Any], dict[str, Path], bool]], *, locks_held: bool = False) -> None:
    held, staged, backups, replaced, journals, keep = None, [], [], [], {}, set()
    try:
        if not locks_held:
            held = lock({scope: dest for scope, _, dest, _ in records})
        for _, record, dest, _ in records:
            pair = stage(record, dest); staged.append(pair)
            backup = {}
            for key in ("json", "md"):
                if dest[key].exists():
                    fd, name = tempfile.mkstemp(prefix=".taste-rollback-", dir=dest[key].parent); os.close(fd)
                    shutil.copy2(dest[key], name); backup[key] = Path(name)
            backups.append(backup)
        for index, (_, record, dest, existed) in enumerate(records):
            if existed:
                dest["history"].mkdir(parents=True, exist_ok=True)
                old = json.loads(dest["json"].read_text(encoding="utf-8"))
                history = dest["history"] / f"revision-{old['revision']:08d}-{old['canonical_record_digest'].split(':')[1][:12]}.json"
                if not history.exists():
                    shutil.copy2(dest["json"], history)
            replace_with_retry(staged[index][0], dest["json"]); replaced.append((index, "json"))
            replace_with_retry(staged[index][1], dest["md"]); replaced.append((index, "md"))
            journals[index] = dest["journal"].stat().st_size if dest["journal"].exists() else None
            with dest["journal"].open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"revision": record["revision"], "digest": record["canonical_record_digest"], "generated_at": record["generated_at"]}, sort_keys=True) + "\n")
    except Exception as exc:
        failed = rollback(records, backups, replaced, journals)
        keep.update(backup for _, backup in failed if backup)
        if isinstance(exc, TasteError):
            raise
        if failed:
            unrestored = [{"path": str(target), "backup": str(backup) if backup else None} for target, backup in failed]
            raise TasteError("write_failed", "atomic preference write failed and the rollback was incomplete; each unrestored file's prior bytes are in its backup", reason=str(exc), unrestored=unrestored) from exc
        raise TasteError("write_failed", "atomic preference write failed and replacements were rolled back", reason=str(exc)) from exc
    finally:
        for pair in staged:
            for path in pair: path.unlink(missing_ok=True)
        for backup in backups:
            for path in backup.values():
                if path not in keep: path.unlink(missing_ok=True)
        if held:
            held.release()


def parse_value(raw: str | None) -> Any:
    if raw is None:
        raise TasteError("missing_value", "--value is required")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def mutate(record: dict[str, Any], command: str, args: argparse.Namespace, source: dict[str, Any] | None = None) -> dict[str, Any]:
    result = copy.deepcopy(record)
    entry_id = args.entry_id
    if command in {"propose", "set"}:
        if not entry_id or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", entry_id):
            raise TasteError("invalid_id", "--id must be a stable lowercase identifier")
        value = validate_safe(parse_value(args.value), redact=args.redact)
        result["entries"][entry_id] = {"state": "proposed" if command == "propose" else "active", "value": value, "updated_at": now()}
        result["tombstones"].pop(entry_id, None)
    elif command in {"confirm", "deprecate"}:
        if entry_id not in result["entries"]:
            raise TasteError("not_found", "preference entry does not exist", id=entry_id)
        if command == "confirm" and result["entries"][entry_id]["state"] != "proposed":
            raise TasteError("invalid_state", "only proposed entries can be confirmed", id=entry_id)
        result["entries"][entry_id]["state"] = "active" if command == "confirm" else "deprecated"
        result["entries"][entry_id]["updated_at"] = now()
    elif command == "revoke":
        if entry_id not in result["entries"]:
            raise TasteError("not_found", "preference entry does not exist", id=entry_id)
        prior = result["entries"].pop(entry_id)
        result["tombstones"][entry_id] = {"revoked_at": now(), "prior_entry_digest": "sha256:" + hashlib.sha256(json.dumps(prior, sort_keys=True).encode()).hexdigest()}
    elif command in {"promote", "specialize"}:
        if not source or entry_id not in source["entries"]:
            raise TasteError("not_found", "source preference entry does not exist", id=entry_id)
        result["entries"][entry_id] = copy.deepcopy(source["entries"][entry_id]); result["entries"][entry_id]["updated_at"] = now()
        result["tombstones"].pop(entry_id, None)
    elif command == "import":
        try:
            incoming = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except Exception as exc:
            raise TasteError("invalid_import", "import must be a readable JSON file", path=args.input) from exc
        entries = incoming.get("entries", incoming) if isinstance(incoming, dict) else incoming
        if not isinstance(entries, dict) or len(entries) > 1000:
            raise TasteError("invalid_import", "import entries must be a JSON object with at most 1000 entries")
        for key, item in entries.items():
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", str(key)):
                raise TasteError("invalid_id", "import contains an invalid stable id", id=str(key))
            value = item.get("value") if isinstance(item, dict) and "value" in item else item
            result["entries"][key] = {"state": "active", "value": validate_safe(value, redact=args.redact), "updated_at": now()}
            result["tombstones"].pop(key, None)
    elif command == "reset":
        for key, item in list(result["entries"].items()):
            result["tombstones"][key] = {"revoked_at": now(), "prior_entry_digest": "sha256:" + hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()}
        result["entries"] = {}
    prior = record["canonical_record_digest"] if record["revision"] else None
    result["revision"] = record["revision"] + 1
    result["generated_at"] = now(); result["previous_revision_digest"] = prior
    result["canonical_record_digest"] = digest(result)
    return result


def selected_scopes(scope: str | None) -> list[str]:
    if scope == "both": return ["project", "global"]
    if scope in {"project", "global"}: return [scope]
    return ["project", "global"]


def expected_revisions(values: list[str] | None, scopes: list[str]) -> dict[str, int | None]:
    """Parse either one shared revision or scoped ``project=N`` values."""
    result: dict[str, int | None] = {scope: None for scope in scopes}
    for value in values or []:
        if "=" in value:
            scope, raw = value.split("=", 1)
            if scope not in result or not raw.isdigit():
                raise TasteError("invalid_revision", "use --expect-revision N or --expect-revision project=N/global=N")
            result[scope] = int(raw)
        elif value.isdigit():
            for scope in scopes: result[scope] = int(value)
        else:
            raise TasteError("invalid_revision", "expected revision must be a non-negative integer")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "list", "effective", "diff", "export"):
        p = sub.add_parser(command); p.add_argument("--scope", choices=("global", "project", "both"), default="both")
        if command == "export": p.add_argument("--output", required=True); p.add_argument("--redact", action="store_true", default=True)
    for command in sorted(MUTATIONS):
        p = sub.add_parser(command); p.add_argument("--scope", choices=("global", "project", "both"), required=True)
        p.add_argument("--expect-revision", action="append"); p.add_argument("--id", dest="entry_id"); p.add_argument("--value")
        p.add_argument("--input"); p.add_argument("--redact", action="store_true")
    args = parser.parse_args(argv); root = Path(args.project_root).resolve()
    held = None
    try:
        if args.command not in MUTATIONS:
            loaded = {scope: load(root, scope)[0] for scope in selected_scopes(args.scope)}
            if args.command == "status":
                return emit(True, stores={s: {"path": str(paths(root, s)["json"]), "exists": paths(root, s)["json"].exists(), "revision": r["revision"], "digest": r["canonical_record_digest"]} for s, r in loaded.items()})
            if args.command == "list": return emit(True, entries={s: r["entries"] for s, r in loaded.items()})
            effective = {}
            for scope in ("global", "project"):
                for key, item in loaded.get(scope, {}).get("entries", {}).items():
                    if item["state"] == "active": effective[key] = {**item, "source_scope": scope}
            if args.command == "effective": return emit(True, entries=effective)
            if args.command == "diff":
                project, global_ = load(root, "project")[0], load(root, "global")[0]
                ids = sorted(set(project["entries"]) | set(global_["entries"]))
                return emit(True, differences=[{"id": i, "project": project["entries"].get(i), "global": global_["entries"].get(i)} for i in ids if project["entries"].get(i) != global_["entries"].get(i)])
            export = {"schema": "supremeteam-taste-export", "schema_version": 1, "generated_at": now(), "provenance": {s: r["canonical_record_digest"] for s, r in loaded.items()}, "entries": validate_safe(effective, redact=True)}
            Path(args.output).write_text(json.dumps(export, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return emit(True, output=str(Path(args.output).resolve()), redacted=True)
        scopes = selected_scopes(args.scope)
        destinations = {scope: paths(root, scope) for scope in scopes}
        held = lock(destinations)
        try:
            # Re-read and compare revisions only after every destination lock is
            # held, preventing two writers from validating the same revision.
            current = {scope: load(root, scope) for scope in scopes}
            expectations = expected_revisions(args.expect_revision, scopes)
            for scope, (record, existed) in current.items():
                expected = expectations[scope]
                if existed and expected is None:
                    raise TasteError("revision_required", "--expect-revision is required for an existing store", scope=scope, actual_revision=record["revision"])
                if expected is not None and expected != record["revision"]:
                    raise TasteError("stale_revision", "expected revision does not match canonical store", scope=scope, expected=expected, actual_revision=record["revision"])
            if args.command == "promote" and args.scope not in {"global", "both"}: raise TasteError("invalid_scope", "promote writes global scope (or both)")
            if args.command == "specialize" and args.scope not in {"project", "both"}: raise TasteError("invalid_scope", "specialize writes project scope (or both)")
            source_scope = "project" if args.command == "promote" else "global"
            source = load(root, source_scope)[0] if args.command in {"promote", "specialize"} else None
            records = []
            for scope in scopes:
                updated = mutate(current[scope][0], args.command, args, source)
                validate(updated, scope)
                records.append((scope, updated, destinations[scope], current[scope][1]))
            held.verify()
            commit_pair(records, locks_held=True)
        finally:
            held.release()
        result: dict[str, Any] = {"command": args.command, "stores": {s: {"revision": r["revision"], "digest": r["canonical_record_digest"]} for s, r, _, _ in records}}
        if held.reclaimed:
            result["lock_reclaimed"] = held.reclaimed
        return emit(True, **result)
    except TasteError as exc:
        extra = {"lock_reclaimed": held.reclaimed} if held and held.reclaimed else {}
        return emit(False, error={"code": exc.code, "message": exc.message, **exc.details}, **extra)


if __name__ == "__main__":
    raise SystemExit(main())
