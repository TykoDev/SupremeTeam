#!/usr/bin/env python3
"""Orchestrator-owned save lifecycle for ``skillset-saves``.

The reader (``_saves.py``) classifies saved state; this module is the single
sanctioned *writer* for the core run files:

    skillset-saves/_latest.md
    skillset-saves/runs/<run-id>/_state.md
    skillset-saves/runs/<run-id>/_lock.md
    skillset-saves/runs/<run-id>/_audit-trail.md
    skillset-saves/runs/<run-id>/_history/rev-<n>.{state,lock}.json

Operations (all emit one JSON result on stdout and use the exit codes below):

    create      new run: probe the save root, acquire an exclusive pinned lock,
                publish revision 1, write the pointer.
    checkpoint  publish revision n+1 atomically (state + lock + pointer) after
                snapshotting revision n into _history/; registers evidence hashes.
                Resumes a released run (audit event ``resume``); reopens a
                complete/blocked run only with --reopen (audit event ``reopen``).
    heartbeat   refresh the lock heartbeat without changing the revision; refuses
                a released, stale, or interrupted lock. The harness hooks call this
                (source ``hook:<event>``) on real host activity so an attended run
                never goes stale between checkpoints.
    complete    terminal transition: status complete|blocked, pin released.
    release     release the lock and pin without a terminal status (paused hand-back).
    recover     reclaim a *stale* lock: refuses a fresh lock or a competing owner,
                records the prior lock path, heartbeat, and bytes as evidence first.
    status      read-only classification (delegates to _saves.inspect_saves).

Exit codes: 0 = ok, 1 = refused (contract violation: competing owner, wrong
revision, unsafe path), 2 = degraded (the write failed; nothing coherent was
published, the previous revision is intact), 3 = engine/input error.

Writes are staged to temporary files in the run directory and published with
``os.replace``. A ``_journal.json`` records the in-flight revision before the
first replace and is removed after the last one, so an interrupted checkpoint
is visible (``status`` reports ``interrupted``) and ``recover --rollback``
restores the last coherent revision from ``_history/``. Nothing is ever
deleted: superseded revisions stay in ``_history/`` and every event is
appended to ``_audit-trail.md``.

Freeze/guard records are out of scope here and are never touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from data_formats import content_sha256  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _saves import ACTIVE_STATUSES, SCHEMA_VERSION, STALE_AFTER_SECONDS, TERMINAL_STATUSES, inspect_saves  # noqa: E402
import _state  # noqa: E402

EXIT_OK, EXIT_REFUSED, EXIT_DEGRADED, EXIT_ENGINE = 0, 1, 2, 3
CORE_FILES = ("_state.md", "_lock.md", "_audit-trail.md")
POINTER = "_latest.md"
# Non-fatal write degradations observed during one invocation (reported in the result).
WRITE_NOTES: list[str] = []


class Refused(Exception):
    pass


class Degraded(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    """Canonical evidence digest (text folded to LF, binary byte-for-byte).

    Shared with ``harness/gatekeeper/check.py`` so a hash registered at a
    checkpoint verifies at the gate on either line-ending convention.
    """
    return content_sha256(path)


def safe_run_id(run_id: str) -> str:
    if not run_id or run_id in {".", ".."} or Path(run_id).name != run_id or any(c in run_id for c in "\\/:*?\"<>|"):
        raise Refused(f"unsafe run id {run_id!r}")
    return run_id


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _replace_with_retry(tmp: Path, path: Path, attempts: int = 8) -> None:
    """os.replace with short retries: on Windows a reader (host hook, indexer,
    antivirus) holding the target open makes replace fail transiently with
    PermissionError / WinError 5."""
    delay = 0.05
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.8)


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        try:
            _replace_with_retry(tmp, path)
        except PermissionError as exc:
            # Windows: an existing target whose ACL denies DELETE (for example a
            # file created by another sandbox user) cannot be replaced, yet it can
            # be overwritten. Fall back to an in-place overwrite of the already
            # fsynced bytes and record the degradation in the write log so the
            # non-atomic step is visible rather than silent.
            if not path.exists():
                raise
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            try:
                tmp.unlink()
            except OSError:
                pass
            WRITE_NOTES.append(f"{path.name}: replaced in place (target ACL denies rename: {exc.__class__.__name__})")
    except OSError as exc:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise Degraded(f"write failed for {path.name}: {exc}") from exc


def dump(obj: dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


class RunStore:
    def __init__(self, project_root: Path, run_id: str) -> None:
        self.project_root = project_root.resolve()
        self.saves = self.project_root / "skillset-saves"
        self.runs = self.saves / "runs"
        self.run_id = safe_run_id(run_id)
        self.run_dir = self.runs / self.run_id
        self.state_path = self.run_dir / "_state.md"
        self.lock_path = self.run_dir / "_lock.md"
        self.audit_path = self.run_dir / "_audit-trail.md"
        self.journal_path = self.run_dir / "_journal.json"
        self.history = self.run_dir / "_history"
        self.pointer = self.saves / POINTER

    # ----------------------------------------------------------------- probes
    def probe(self) -> str:
        """Write/read/delete probe inside the save root. Raises Degraded."""
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            probe = self.run_dir / ".probe"
            probe.write_text("probe", encoding="utf-8")
            if probe.read_text(encoding="utf-8") != "probe":
                raise OSError("read-back mismatch")
            probe.unlink()
        except OSError as exc:
            raise Degraded(f"persistence probe failed: {exc}") from exc
        return "ok"

    def evidence_hashes(self, paths: list[str]) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for value in paths:
            candidate = Path(value)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise Refused(f"evidence path must be project-relative without traversal: {value}")
            target = (self.project_root / candidate).resolve()
            try:
                target.relative_to(self.project_root)
            except ValueError as exc:
                raise Refused(f"evidence path escapes project root: {value}") from exc
            if not target.exists():
                raise Refused(f"evidence path missing: {value}")
            if target.is_file():
                hashes[candidate.as_posix()] = sha256_file(target)
            else:
                hashes[candidate.as_posix()] = "directory"
        return hashes

    # --------------------------------------------------------------- records
    def current(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        return read_json(self.state_path), read_json(self.lock_path)

    def competing_owner(self, owner: str) -> str | None:
        """Another coherent held run in this save root blocks a new pin.

        A *stale* held run blocks too: creating or resuming beside it would
        leave two held runs, which the reader classifies as ``conflicting`` so
        neither could be pinned. Reclaim it with ``recover`` or close it first."""
        result = inspect_saves(self.project_root)
        if result["status"] in {"active", "orphaned", "conflicting", "stale"} and result.get("run_id") != self.run_id:
            return f"{result['status']}: {result['detail']}"
        return None

    def require_not_interrupted(self) -> None:
        if self.journal_path.exists():
            raise Refused("previous checkpoint was interrupted; run recover --rollback first")

    def require_owner(self, owner: str, lock: dict[str, Any] | None) -> None:
        if lock is None:
            raise Refused("run has no lock; create it first")
        if str(lock.get("owner")) != owner:
            raise Refused(f"lock is owned by {lock.get('owner')!r}, not {owner!r}")

    def stale(self, lock: dict[str, Any]) -> bool:
        try:
            beat = datetime.fromisoformat(str(lock.get("heartbeat")).replace("Z", "+00:00"))
        except ValueError:
            return True
        if beat.tzinfo is None:
            beat = beat.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - beat).total_seconds() > STALE_AFTER_SECONDS

    def append_audit(self, event: str, payload: dict[str, Any]) -> None:
        line = json.dumps({"at": now_iso(), "event": event, **payload}, sort_keys=True)
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            with open(self.audit_path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            raise Degraded(f"audit append failed: {exc}") from exc

    def snapshot(self, revision: int) -> None:
        if not self.state_path.exists() and not self.lock_path.exists():
            return
        try:
            self.history.mkdir(exist_ok=True)
            for src, kind in ((self.state_path, "state"), (self.lock_path, "lock")):
                if src.exists():
                    dest = self.history / f"rev-{revision}.{kind}.json"
                    if not dest.exists():
                        dest.write_bytes(src.read_bytes())
        except OSError as exc:
            raise Degraded(f"history snapshot failed: {exc}") from exc

    def publish(self, state: dict[str, Any], lock: dict[str, Any], *, pointer: bool = True) -> None:
        """Publish lock + state (the coherent core) and then the pointer.

        A failure before the core is complete leaves the journal in place
        (``status`` reports ``interrupted``; ``recover --rollback`` restores the
        prior revision). A failure of the pointer alone leaves a coherent but
        *orphaned* run: the journal is cleared and a Degraded result says so,
        because the reader still recognises the run and ``heartbeat`` rewrites
        the pointer."""
        revision = int(state["revision"])
        atomic_write(self.journal_path, dump({"revision": revision, "step": "begin", "at": now_iso()}))
        atomic_write(self.lock_path, dump(lock))
        atomic_write(self.state_path, dump(state))
        pointer_error = None
        if pointer:
            try:
                atomic_write(self.pointer, dump({
                    "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                    "revision": revision, "updated_at": state["timestamp"],
                }))
            except Degraded as exc:
                pointer_error = str(exc)
        try:
            self.journal_path.unlink()
        except OSError as exc:
            raise Degraded(f"journal cleanup failed: {exc}") from exc
        if pointer_error:
            self.append_audit("pointer-degraded", {"revision": revision, "error": pointer_error})
            raise Degraded(f"revision {revision} state and lock published, pointer not updated ({pointer_error}); "
                           f"run is coherent but orphaned until heartbeat rewrites the pointer")

    # ------------------------------------------------------------ operations
    def create(self, owner: str, evidence: list[str], execution_mode: str, next_action: str, extra: dict[str, Any]) -> dict[str, Any]:
        if self.state_path.exists() or self.lock_path.exists():
            raise Refused(f"run {self.run_id} already exists; use checkpoint or recover")
        competing = self.competing_owner(owner)
        if competing:
            raise Refused(f"another run holds the session pin ({competing}); complete, release, or recover it first")
        self.probe()
        hashes = self.evidence_hashes(evidence)
        stamp = now_iso()
        state = {
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id, "status": "active", "session_pin": True,
            "revision": 1, "active_owner": owner, "evidence_paths": sorted(hashes), "timestamp": stamp,
            "execution_mode": execution_mode, "persistence_probe": "ok", "next_action": next_action,
            "artifact_hashes": hashes, "parent_revision": None, **extra,
        }
        lock = {"schema_version": SCHEMA_VERSION, "run_id": self.run_id, "owner": owner, "status": "held",
                "session_pin": True, "revision": 1, "heartbeat": stamp, "acquired_at": stamp}
        self.append_audit("create", {"owner": owner, "revision": 1, "evidence": hashes})
        self.publish(state, lock)
        return {"result": "ok", "operation": "create", "run_id": self.run_id, "revision": 1, "owner": owner}

    def checkpoint(self, owner: str, expect_revision: int | None, evidence: list[str], status: str, next_action: str | None,
                   extra: dict[str, Any], reopen: bool = False) -> dict[str, Any]:
        state, lock = self.current()
        self.require_owner(owner, lock)
        if state is None:
            raise Refused("run state unreadable; recover before checkpointing")
        self.require_not_interrupted()
        current = int(state.get("revision", 0))
        if expect_revision is not None and expect_revision != current:
            raise Refused(f"revision conflict: expected {expect_revision}, found {current}")
        if status not in ACTIVE_STATUSES:
            raise Refused(f"checkpoint status must be one of {sorted(ACTIVE_STATUSES)}")
        current_status = str(state.get("status", "")).lower()
        event = "checkpoint"
        if current_status in {"complete", "blocked"}:
            # COMPLETE is a claim about the recorded boundary (workflow-protocol.md):
            # a post-completion change re-enters through REVISE deliberately, never
            # by a routine checkpoint that happens to land on a closed run.
            if not reopen:
                raise Refused(f"run is {current_status}; pass --reopen to start a new revision through REVISE, "
                              f"or create a new run")
            event = "reopen"
        elif str(lock.get("status")) == "released":
            event = "resume"
        if str(lock.get("status")) == "released":
            competing = self.competing_owner(owner)
            if competing:
                raise Refused(f"cannot {event} a released run while another run holds the session pin ({competing})")
        elif self.stale(lock):
            raise Refused("lock heartbeat is stale; reclaim it with recover --reason before checkpointing")
        merged_paths = sorted(set(state.get("evidence_paths", [])) | set(evidence))
        hashes = dict(state.get("artifact_hashes", {}))
        hashes.update(self.evidence_hashes(merged_paths))
        stamp = now_iso()
        self.snapshot(current)
        new_state = {**state, **extra, "status": status, "session_pin": True, "revision": current + 1,
                     "parent_revision": current, "active_owner": owner, "evidence_paths": merged_paths,
                     "artifact_hashes": hashes, "timestamp": stamp,
                     "next_action": next_action if next_action is not None else state.get("next_action")}
        new_lock = {**lock, "owner": owner, "status": "held", "session_pin": True, "revision": current + 1, "heartbeat": stamp}
        payload = {"owner": owner, "revision": current + 1, "parent_revision": current, "evidence": hashes}
        if event != "checkpoint":
            payload["from_status"] = current_status
        self.append_audit(event, payload)
        self.publish(new_state, new_lock)
        return {"result": "ok", "operation": event, "run_id": self.run_id, "revision": current + 1, "parent_revision": current}

    def heartbeat(self, owner: str, source: str = "cli") -> dict[str, Any]:
        """Refresh the lock heartbeat (and the pointer) without a new revision.

        Refuses a released lock, an interrupted publish, and a *stale* lock: a
        lock idle for longer than the staleness window is reclaimed only through
        ``recover --reason`` so the reclaim leaves evidence in the audit trail."""
        state, lock = self.current()
        self.require_owner(owner, lock)
        if state is None:
            raise Refused("run state unreadable; recover before heartbeat")
        self.require_not_interrupted()
        if str(lock.get("status")) != "held":
            raise Refused("cannot heartbeat a released lock")
        if self.stale(lock):
            raise Refused("lock heartbeat is stale; reclaim it with recover --reason instead of a silent heartbeat")
        stamp = now_iso()
        atomic_write(self.lock_path, dump({**lock, "heartbeat": stamp, "heartbeat_source": source}))
        atomic_write(self.pointer, dump({"schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                         "revision": int(state["revision"]), "updated_at": stamp}))
        return {"result": "ok", "operation": "heartbeat", "run_id": self.run_id, "heartbeat": stamp, "source": source}

    def finish(self, owner: str, status: str, next_action: str | None, extra: dict[str, Any]) -> dict[str, Any]:
        state, lock = self.current()
        self.require_owner(owner, lock)
        if state is None:
            raise Refused("run state unreadable")
        if status not in TERMINAL_STATUSES:
            raise Refused(f"terminal status must be one of {sorted(TERMINAL_STATUSES)}")
        self.require_not_interrupted()
        current_status = str(state.get("status", "")).lower()
        if status == "released" and current_status in {"complete", "blocked", "released"}:
            raise Refused(f"run is already {current_status}; release applies to an active run")
        current = int(state.get("revision", 0))
        stamp = now_iso()
        self.snapshot(current)
        new_state = {**state, **extra, "status": status, "session_pin": False, "revision": current + 1,
                     "parent_revision": current, "timestamp": stamp,
                     "next_action": next_action if next_action is not None else state.get("next_action")}
        new_lock = {**lock, "status": "released", "session_pin": False, "revision": current + 1,
                    "heartbeat": stamp, "released_at": stamp}
        self.append_audit(status, {"owner": owner, "revision": current + 1, "parent_revision": current})
        self.publish(new_state, new_lock)
        return {"result": "ok", "operation": status, "run_id": self.run_id, "revision": current + 1}

    def recover(self, owner: str, reason: str, rollback: bool) -> dict[str, Any]:
        state, lock = self.current()
        if lock is None:
            raise Refused("nothing to recover: no lock")
        evidence = {"prior_lock_path": str(self.lock_path), "prior_heartbeat": lock.get("heartbeat"),
                    "prior_owner": lock.get("owner"), "prior_lock_sha256": sha256_file(self.lock_path), "reason": reason}
        if self.journal_path.exists() and not rollback:
            raise Refused("interrupted checkpoint journal present; run recover --rollback before reclaiming the lock")
        if self.journal_path.exists() and rollback:
            journal = read_json(self.journal_path) or {}
            target = int(journal.get("revision", 0)) - 1
            state_snap = self.history / f"rev-{target}.state.json"
            lock_snap = self.history / f"rev-{target}.lock.json"
            journal_revision = int(journal.get("revision", 0))
            if (state is not None and lock is not None
                    and int(state.get("revision", -1)) == journal_revision
                    and int(lock.get("revision", -2)) == journal_revision):
                # Core publish completed; only the pointer/journal step was lost.
                self.append_audit("rollforward", {**evidence, "revision": journal_revision, "by": owner})
                atomic_write(self.pointer, dump({"schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                                 "revision": journal_revision, "updated_at": now_iso()}))
                self.journal_path.unlink()
                return {"result": "ok", "operation": "rollforward", "run_id": self.run_id, "revision": journal_revision, "evidence": evidence}
            if target < 1:
                raise Refused("journal names no prior revision; escalate to the owner")
            if state_snap.exists() and lock_snap.exists():
                restored_state = read_json(state_snap) or {}
                restored_lock = read_json(lock_snap) or {}
                source = "history snapshot"
            elif state is not None and int(state.get("revision", -1)) == target:
                # The state file is the last coherent revision; only the lock (or
                # the pointer) was left mid-publish. Rebuild the lock from state.
                restored_state = state
                restored_lock = {**(lock or {}), "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                 "owner": state.get("active_owner", owner),
                                 "status": "held" if state.get("status") in ACTIVE_STATUSES else "released",
                                 "session_pin": state.get("status") in ACTIVE_STATUSES,
                                 "revision": target, "heartbeat": now_iso()}
                source = "state file (lock rebuilt)"
            else:
                raise Refused(f"no coherent snapshot for revision {target}; escalate to the owner")
            self.append_audit("rollback", {**evidence, "restored_revision": target, "by": owner, "source": source})
            atomic_write(self.lock_path, dump(restored_lock))
            atomic_write(self.state_path, dump(restored_state))
            atomic_write(self.pointer, dump({"schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                             "revision": target, "updated_at": now_iso()}))
            self.journal_path.unlink()
            return {"result": "ok", "operation": "rollback", "run_id": self.run_id, "revision": target, "evidence": evidence}
        if str(lock.get("status")) == "held" and not self.stale(lock):
            if str(lock.get("owner")) != owner:
                raise Refused("lock is fresh and held by another owner; recovery refused")
            raise Refused("lock is fresh and held by this owner; use checkpoint or heartbeat, recovery is for a stale lock")
        if str(lock.get("status")) == "released":
            raise Refused("lock is released; use checkpoint from a new revision or create a new run")
        if state is None:
            raise Refused("state unreadable; escalate with both revisions instead of merging")
        competing = self.competing_owner(owner)
        if competing:
            raise Refused(f"another run is active ({competing}); recovery would create a conflicting active set")
        stamp = now_iso()
        current = int(state.get("revision", 0))
        self.snapshot(current)
        self.append_audit("recover", {**evidence, "by": owner, "revision": current + 1})
        new_state = {**state, "revision": current + 1, "parent_revision": current, "active_owner": owner,
                     "timestamp": stamp, "recovered_from": evidence}
        new_lock = {**lock, "owner": owner, "status": "held", "session_pin": True, "revision": current + 1,
                    "heartbeat": stamp, "acquired_at": stamp}
        self.publish(new_state, new_lock)
        return {"result": "ok", "operation": "recover", "run_id": self.run_id, "revision": current + 1, "evidence": evidence}

    def status(self) -> dict[str, Any]:
        result = dict(inspect_saves(self.project_root))
        result["operation"] = "status"
        result["run_id_requested"] = self.run_id
        result["interrupted"] = self.journal_path.exists()
        if result["interrupted"]:
            result["detail"] = f"interrupted checkpoint journal present: {self.journal_path}"
            result["status"] = "interrupted"
        state, lock = self.current()
        result["revision"] = state.get("revision") if state else None
        result["owner"] = lock.get("owner") if lock else None
        result["result"] = "ok"
        return result


def parse_extra(values: list[str]) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    for item in values or []:
        if "=" not in item:
            raise Refused(f"--set expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        if key in {"schema_version", "run_id", "status", "session_pin", "revision", "parent_revision", "active_owner", "evidence_paths", "timestamp", "artifact_hashes"}:
            raise Refused(f"--set may not override reserved field {key!r}")
        extra[key] = value
    return extra


def main() -> int:
    parser = argparse.ArgumentParser(description="Supreme Team save lifecycle writer.")
    parser.add_argument("operation", choices=["create", "checkpoint", "heartbeat", "complete", "block", "release", "recover", "status"])
    parser.add_argument("--project-root", default=None, help="project root (default: nearest marked ancestor of the working directory)")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--owner", default="admiral")
    parser.add_argument("--evidence", action="append", default=[], help="project-relative evidence path (repeatable)")
    parser.add_argument("--expect-revision", type=int)
    parser.add_argument("--status", default="active", help="checkpoint status: active|paused|awaiting-input")
    parser.add_argument("--execution-mode", default="agent")
    parser.add_argument("--next-action", default=None)
    parser.add_argument("--reason", default="", help="recover: why the lock is being reclaimed")
    parser.add_argument("--rollback", action="store_true", help="recover: restore the last coherent revision after an interrupted checkpoint")
    parser.add_argument("--set", action="append", default=[], help="extra state field key=value (repeatable)")
    parser.add_argument("--reopen", action="store_true", help="checkpoint: deliberately reopen a complete/blocked run as a new revision (REVISE)")
    args = parser.parse_args()
    try:
        store = RunStore(Path(args.project_root) if args.project_root else _state.project_root(), args.run_id)
        extra = parse_extra(args.set)
        if args.operation == "create":
            result = store.create(args.owner, args.evidence, args.execution_mode, args.next_action or "select earliest incomplete boundary", extra)
        elif args.operation == "checkpoint":
            result = store.checkpoint(args.owner, args.expect_revision, args.evidence, args.status, args.next_action, extra,
                                      reopen=args.reopen)
        elif args.operation == "heartbeat":
            result = store.heartbeat(args.owner)
        elif args.operation == "complete":
            result = store.finish(args.owner, "complete", args.next_action, extra)
        elif args.operation == "block":
            result = store.finish(args.owner, "blocked", args.next_action, extra)
        elif args.operation == "release":
            result = store.finish(args.owner, "released", args.next_action, extra)
        elif args.operation == "recover":
            if not args.reason and not args.rollback:
                raise Refused("recover requires --reason (evidence of why the lock is reclaimed)")
            result = store.recover(args.owner, args.reason, args.rollback)
        else:
            result = store.status()
        if WRITE_NOTES:
            result["write_notes"] = list(WRITE_NOTES)
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    except Refused as exc:
        print(json.dumps({"result": "refused", "operation": args.operation, "run_id": args.run_id, "reason": str(exc)}, indent=2))
        return EXIT_REFUSED
    except Degraded as exc:
        print(json.dumps({"result": "degraded", "operation": args.operation, "run_id": args.run_id, "reason": str(exc),
                          "note": "the write did not complete; see reason for what was and was not published, then run status"}, indent=2))
        return EXIT_DEGRADED
    except (OSError, ValueError) as exc:
        print(json.dumps({"result": "engine_error", "operation": args.operation, "reason": str(exc)}, indent=2), file=sys.stderr)
        return EXIT_ENGINE


if __name__ == "__main__":
    raise SystemExit(main())
