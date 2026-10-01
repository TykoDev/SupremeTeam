#!/usr/bin/env python3
"""Orchestrator-owned save lifecycle for ``skillset-saves``.

The reader (``_saves.py``) classifies saved state; this module is the single
sanctioned *writer* for the core run files:

    skillset-saves/_latest.md
    skillset-saves/_write.lock
    skillset-saves/runs/<run-id>/_state.md
    skillset-saves/runs/<run-id>/_lock.md
    skillset-saves/runs/<run-id>/_audit-trail.md
    skillset-saves/runs/<run-id>/_history/rev-<n>.{state,lock}.json

Operations (all emit one JSON result on stdout and use the exit codes below):

    create      new run from at least one evidence path: probe the save root,
                acquire an exclusive pinned lock, publish revision 1, write the pointer.
    checkpoint  publish revision n+1 atomically (state + lock + pointer) after
                snapshotting revision n into _history/; registers evidence hashes,
                and --drop-evidence removes a registered path (with --reason).
                Resumes a released run (audit event ``resume``); reopens a
                complete/blocked run only with --reopen (audit event ``reopen``).
    heartbeat   refresh the lock heartbeat without changing the revision; refuses
                a released, stale, or interrupted lock. The harness hooks call this
                (source ``hook:<event>``) on real host activity so an attended run
                never goes stale between checkpoints.
    complete    terminal transition: status complete|blocked, pin released. Refused
                on a run that is already complete or blocked: a closed run re-enters
                through checkpoint --reopen.
    release     release the lock and pin without a terminal status (paused hand-back).
    recover     reclaim a *stale* lock (--reason): refuses a fresh lock or a competing
                owner, records the prior lock path, heartbeat, and bytes as evidence
                first. --rollback settles an interrupted publish instead.
    status      read-only classification (delegates to _saves.inspect_saves).

Exit codes: 0 = ok, 1 = refused (contract violation: competing owner, wrong
revision, unsafe path, busy lock), 2 = degraded (the write failed; nothing
coherent was published, the previous revision is intact), 3 = engine/input error.

Every mutation holds one exclusive lock (``_write.lock``, an operating-system
advisory lock, so a crashed writer never leaves it held) from reading the current
revision to its last write, and re-checks the revision inside it: overlapping
writers serialise and a stale ``--expect-revision`` is refused, not overwritten.
A writer that must succeed waits ``--lock-timeout`` seconds and then refuses; the
hook heartbeat waits a quarter second and skips, because a hook must never hold
up the host.

Writes are staged to per-process temporary files in the run directory and
published with ``os.replace``. A ``_journal.json`` records the in-flight revision
before the first replace and is removed after the last one, so an interrupted
checkpoint is visible (``status`` reports ``interrupted``) and ``recover
--rollback`` restores the last coherent revision from ``_history/``. The audit
event for a revision is appended once its state is published, before the journal
is cleared. Nothing is ever deleted: superseded revisions stay in ``_history/``
(a first revision that never finished publishing is retired there too) and every
event is appended to ``_audit-trail.md``, including operations that were refused
or degraded.

Freeze/guard records are out of scope here and are never touched.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

import _bootstrap

_bootstrap.ensure_paths()
from data_formats import content_sha256  # noqa: E402
from save_taxonomy import ACTIVE_STATUSES, HISTORY, JOURNAL, POINTER, SCHEMA_VERSION, TERMINAL_STATUSES, WRITE_LOCK  # noqa: E402
from _saves import NEXT_STEPS, heartbeat_is_stale, inspect_run, inspect_saves, parse_timestamp  # noqa: E402
import _fsutil  # noqa: E402
import _state  # noqa: E402

EXIT_OK, EXIT_REFUSED, EXIT_DEGRADED, EXIT_ENGINE = 0, 1, 2, 3
# How long a writer that must succeed waits for another writer, and how long the
# hook heartbeat waits before skipping.
WRITER_LOCK_TIMEOUT = 10.0
HOOK_LOCK_WAIT = 0.25
# Non-fatal write degradations observed during one invocation (reported in the result).
WRITE_NOTES: list[str] = []


class Refused(Exception):
    pass


class Degraded(Exception):
    pass


class LockBusy(Refused):
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
    """The reader's pattern, so a run the writer accepts is one the hooks can see."""
    if not _state.RUN_ID.fullmatch(run_id):
        raise Refused(f"unsafe run id {run_id!r}: use 1 to 128 letters, digits, '.', '_' or '-', starting with a letter, digit or '_'")
    return run_id


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_why = _fsutil.why


def atomic_write(path: Path, data: str | bytes) -> None:
    try:
        _fsutil.atomic_write(path, data, notes=WRITE_NOTES)
    except OSError as exc:
        raise Degraded(f"write failed for {path.name}: {_why(exc)}") from exc


def dump(obj: dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


class WriteLock(_fsutil.AdvisoryLock):
    """Exclusive advisory lock on the save root's writer mutex.

    The operating system drops the lock when its holder exits, so a killed
    writer cannot wedge the run, and no stale-owner guess is ever needed. A file
    system that offers no locking degrades to the unlocked behaviour with a note
    in the result; only a lock another process actually holds past ``wait``
    seconds raises LockBusy. The ``fcntl`` and ``msvcrt`` names stay here so the
    backend a test or a platform supplies is the one that locks."""

    def __init__(self, path: Path, wait: float, label: str, *, create_dir: bool = False) -> None:
        super().__init__(path, wait, label=label, kind="writer lock", create_dir=create_dir, notes=WRITE_NOTES,
                         backends=lambda: (fcntl, msvcrt))

    def _timed_out(self) -> None:
        raise LockBusy(f"another process holds the save write lock ({self.label}) after waiting {self.wait:g}s; "
                       f"retry, or look for a stuck save_run.py process")


class RunStore:
    def __init__(self, project_root: Path, run_id: str, lock_timeout: float = WRITER_LOCK_TIMEOUT) -> None:
        self.project_root = project_root.resolve()
        self.saves = self.project_root / "skillset-saves"
        self.runs = self.saves / "runs"
        self.run_id = safe_run_id(run_id)
        self.run_dir = self.runs / self.run_id
        self.state_path = self.run_dir / "_state.md"
        self.lock_path = self.run_dir / "_lock.md"
        self.audit_path = self.run_dir / "_audit-trail.md"
        self.journal_path = self.run_dir / JOURNAL
        self.history = self.run_dir / HISTORY
        self.pointer = self.saves / POINTER
        self.lock_timeout = lock_timeout

    def rel(self, path: Path) -> str:
        return path.relative_to(self.project_root).as_posix()

    def exclusive(self, wait: float | None = None, *, create: bool = False) -> Any:
        """Hold the writer mutex. Where nothing has been saved yet there is nothing to protect."""
        if not create and not self.saves.is_dir():
            return contextlib.nullcontext()
        return WriteLock(self.saves / WRITE_LOCK, self.lock_timeout if wait is None else wait,
                         self.rel(self.saves / WRITE_LOCK), create_dir=create)

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
            raise Degraded(f"persistence probe failed: {_why(exc)}") from exc
        return "ok"

    def normalize_evidence(self, value: str) -> str:
        """The one spelling a path is registered and hashed under."""
        if not value.strip():
            raise Refused("evidence path must not be empty")
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise Refused(f"evidence path must be project-relative without traversal: {value}")
        return candidate.as_posix()

    def evidence_hashes(self, paths: list[str], registered: tuple[str, ...] = ()) -> dict[str, str]:
        """Digest every normalised path; ``registered`` names those a checkpoint inherited, so
        the refusal for one of them says how to drop it."""
        hashes: dict[str, str] = {}
        missing: list[str] = []
        for value in paths:
            target = (self.project_root / value).resolve()
            try:
                target.relative_to(self.project_root)
            except ValueError as exc:
                raise Refused(f"evidence path escapes project root: {value}") from exc
            if not target.exists():
                missing.append(value)
            elif target.is_file():
                hashes[value] = sha256_file(target)
            else:
                hashes[value] = "directory"
        if missing:
            named = [p for p in missing if p not in registered]
            inherited = [p for p in missing if p in registered]
            reasons = []
            if named:
                reasons.append(f"evidence path missing: {', '.join(named)}")
            if inherited:
                reasons.append(f"registered evidence path missing: {', '.join(inherited)}; restore it, or record its "
                               f"removal with checkpoint --drop-evidence <path> --reason <why>")
            raise Refused("; ".join(reasons))
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
        beat = parse_timestamp(lock.get("heartbeat"))
        return beat is None or heartbeat_is_stale(beat, datetime.now(timezone.utc))

    def append_audit(self, event: str, payload: dict[str, Any]) -> None:
        line = json.dumps({"at": now_iso(), "event": event, **payload}, sort_keys=True)
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            with open(self.audit_path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")
        except OSError as exc:
            raise Degraded(f"audit append failed: {_why(exc)}") from exc

    def note_failure(self, event: str, operation: str, owner: str, reason: str) -> None:
        """Best-effort audit line for a refused or degraded operation.

        The harness audit reads these to see the failures it exists to audit. It
        never creates a run directory for one, and its own failure changes nothing."""
        if not self.run_dir.is_dir():
            return
        with contextlib.suppress(Degraded):
            self.append_audit(event, {"operation": operation, "owner": owner, "reason": reason})

    def snapshot(self, revision: int) -> None:
        if not self.state_path.exists() and not self.lock_path.exists():
            return
        try:
            self.history.mkdir(exist_ok=True)
        except OSError as exc:
            raise Degraded(f"history snapshot failed: {_why(exc)}") from exc
        for src, kind in ((self.state_path, "state"), (self.lock_path, "lock")):
            if not src.exists():
                continue
            dest = self.history / f"rev-{revision}.{kind}.json"
            if self.describes(read_json(dest), revision):
                continue
            try:
                data = src.read_bytes()
            except OSError as exc:
                raise Degraded(f"history snapshot failed: {_why(exc)}") from exc
            atomic_write(dest, data)

    def describes(self, record: dict[str, Any] | None, revision: int) -> bool:
        """True when a record parses and is this run's record at ``revision``."""
        return record is not None and record.get("run_id") == self.run_id and _as_int(record.get("revision")) == revision

    def publish(self, state: dict[str, Any], lock: dict[str, Any], *, pointer: bool = True,
                event: tuple[str, dict[str, Any]] | None = None) -> None:
        """Publish lock + state (the coherent core) and then the pointer.

        The audit event follows the published core and precedes the journal
        clear, so a failed publish never leaves an event for a revision that
        does not exist, and a crash before the clear leaves the journal to
        roll the revision forward. A failure before the core is complete leaves
        the journal in place (``status`` reports ``interrupted``; ``recover
        --rollback`` restores the prior revision). A failure of the pointer alone
        leaves a coherent but *orphaned* run: the journal is cleared and a
        Degraded result says so, because the reader still recognises the run and
        ``heartbeat`` rewrites the pointer."""
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
        if event:
            self.settle_event(revision, *event)
        self.clear_journal()
        if pointer_error:
            self.append_audit("pointer-degraded", {"revision": revision, "error": pointer_error})
            raise Degraded(f"revision {revision} state and lock published, pointer not updated ({pointer_error}); "
                           f"run is coherent but orphaned until heartbeat rewrites the pointer")

    def settle_event(self, revision: int, event: str, payload: dict[str, Any]) -> None:
        """Append the event for a revision whose files are already written, keeping the
        journal when the append fails so the gap is visible."""
        try:
            self.append_audit(event, payload)
        except Degraded as exc:
            raise Degraded(f"revision {revision} state and lock are published but the {event} audit event was not "
                           f"recorded ({exc}); the journal stays, so status reports interrupted and "
                           f"recover --rollback rolls the revision forward") from exc

    def clear_journal(self) -> None:
        try:
            self.journal_path.unlink()
        except OSError as exc:
            raise Degraded(f"journal cleanup failed: {_why(exc)}") from exc

    # ------------------------------------------------------------ operations
    def create(self, owner: str, evidence: list[str], execution_mode: str, next_action: str, extra: dict[str, Any]) -> dict[str, Any]:
        if not evidence:
            raise Refused("create needs at least one --evidence path: a run stands on the evidence it is created from "
                          "(for admiral, the intake report)")
        paths = sorted({self.normalize_evidence(value) for value in evidence})
        with self.exclusive(create=True):
            if self.journal_path.exists():
                raise Refused(f"run {self.run_id} has an interrupted publish (journal present); run recover --rollback first")
            if self.state_path.exists() or self.lock_path.exists():
                raise Refused(f"run {self.run_id} already exists; use checkpoint or recover")
            competing = self.competing_owner(owner)
            if competing:
                raise Refused(f"another run holds the session pin ({competing}); complete, release, or recover it first")
            hashes = self.evidence_hashes(paths)
            self.probe()
            stamp = now_iso()
            state = {
                "schema_version": SCHEMA_VERSION, "run_id": self.run_id, "status": "active", "session_pin": True,
                "revision": 1, "active_owner": owner, "evidence_paths": sorted(hashes), "timestamp": stamp,
                "execution_mode": execution_mode, "persistence_probe": "ok", "next_action": next_action,
                "artifact_hashes": hashes, "parent_revision": None, **extra,
            }
            lock = {"schema_version": SCHEMA_VERSION, "run_id": self.run_id, "owner": owner, "status": "held",
                    "session_pin": True, "revision": 1, "heartbeat": stamp, "acquired_at": stamp}
            self.publish(state, lock, event=("create", {"owner": owner, "revision": 1, "evidence": hashes}))
            return {"result": "ok", "operation": "create", "run_id": self.run_id, "revision": 1, "owner": owner}

    def checkpoint(self, owner: str, expect_revision: int | None, evidence: list[str], status: str, next_action: str | None,
                   extra: dict[str, Any], reopen: bool = False, drop_evidence: list[str] | None = None,
                   reason: str = "") -> dict[str, Any]:
        new_paths = [self.normalize_evidence(value) for value in evidence]
        dropped = [self.normalize_evidence(value) for value in drop_evidence or []]
        if dropped and not reason.strip():
            raise Refused("--drop-evidence removes gate evidence from the run, so it requires --reason")
        if set(new_paths) & set(dropped):
            raise Refused("a path cannot be registered and dropped in the same checkpoint")
        with self.exclusive():
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
            registered = tuple(sorted({self.normalize_evidence(str(value)) for value in state.get("evidence_paths", [])}))
            unknown = [value for value in dropped if value not in registered]
            if unknown:
                raise Refused(f"--drop-evidence names paths that are not registered: {', '.join(unknown)}")
            merged = sorted((set(registered) | set(new_paths)) - set(dropped))
            prior_hashes = dict(state.get("artifact_hashes") or {})
            hashes = {path: digest for path, digest in prior_hashes.items() if path in merged}
            hashes.update(self.evidence_hashes(merged, registered))
            stamp = now_iso()
            self.snapshot(current)
            new_state = {**state, **extra, "status": status, "session_pin": True, "revision": current + 1,
                         "parent_revision": current, "active_owner": owner, "evidence_paths": merged,
                         "artifact_hashes": hashes, "timestamp": stamp,
                         "next_action": next_action if next_action is not None else state.get("next_action")}
            new_lock = {**lock, "owner": owner, "status": "held", "session_pin": True, "revision": current + 1, "heartbeat": stamp}
            payload = {"owner": owner, "revision": current + 1, "parent_revision": current, "evidence": hashes}
            if event != "checkpoint":
                payload["from_status"] = current_status
            if dropped:
                payload["dropped_evidence"] = {value: prior_hashes.get(value) for value in dropped}
                payload["reason"] = reason
            self.publish(new_state, new_lock, event=(event, payload))
            result = {"result": "ok", "operation": event, "run_id": self.run_id, "revision": current + 1, "parent_revision": current}
            if dropped:
                result["dropped_evidence"] = dropped
            return result

    def heartbeat(self, owner: str, source: str = "cli", *, wait: float | None = None,
                  min_age: float | None = None) -> dict[str, Any]:
        """Refresh the lock heartbeat (and the pointer) without a new revision.

        Refuses a released lock, an interrupted publish, and a *stale* lock: a
        lock idle for longer than the staleness window is reclaimed only through
        ``recover --reason`` so the reclaim leaves evidence in the audit trail.

        Everything is decided inside the lock, from a fresh read: a checkpoint that
        published while this call waited is seen, never overwritten. ``min_age``
        skips the write when another writer already refreshed the heartbeat."""
        with self.exclusive(wait):
            state, lock = self.current()
            self.require_owner(owner, lock)
            if state is None:
                raise Refused("run state unreadable; recover before heartbeat")
            self.require_not_interrupted()
            if str(lock.get("status")) != "held":
                raise Refused("cannot heartbeat a released lock")
            if _as_int(lock.get("revision"), -1) != _as_int(state.get("revision"), -2):
                raise Refused("lock and state revisions differ; run status, then recover")
            if self.stale(lock):
                raise Refused("lock heartbeat is stale; reclaim it with recover --reason instead of a silent heartbeat")
            beat = parse_timestamp(lock.get("heartbeat"))
            if min_age is not None and beat is not None and 0 <= (datetime.now(timezone.utc) - beat).total_seconds() < min_age:
                return {"result": "ok", "operation": "heartbeat", "run_id": self.run_id, "heartbeat": lock.get("heartbeat"),
                        "source": source, "skipped": "heartbeat is already fresh"}
            stamp = now_iso()
            atomic_write(self.lock_path, dump({**lock, "heartbeat": stamp, "heartbeat_source": source}))
            atomic_write(self.pointer, dump({"schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                             "revision": int(state["revision"]), "updated_at": stamp}))
            return {"result": "ok", "operation": "heartbeat", "run_id": self.run_id, "heartbeat": stamp, "source": source}

    def finish(self, owner: str, status: str, next_action: str | None, extra: dict[str, Any]) -> dict[str, Any]:
        with self.exclusive():
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
            if current_status in {"complete", "blocked"}:
                # The same rule checkpoint applies: a closed run is reopened through REVISE, never
                # rewritten in place by a second complete or block.
                raise Refused(f"run is already {current_status}; a closed run re-enters through checkpoint --reopen, "
                              f"then it can be closed again")
            current = int(state.get("revision", 0))
            stamp = now_iso()
            self.snapshot(current)
            new_state = {**state, **extra, "status": status, "session_pin": False, "revision": current + 1,
                         "parent_revision": current, "timestamp": stamp,
                         "next_action": next_action if next_action is not None else state.get("next_action")}
            new_lock = {**lock, "status": "released", "session_pin": False, "revision": current + 1,
                        "heartbeat": stamp, "released_at": stamp}
            self.publish(new_state, new_lock, event=(status, {"owner": owner, "revision": current + 1, "parent_revision": current}))
            return {"result": "ok", "operation": status, "run_id": self.run_id, "revision": current + 1}

    def recover(self, owner: str, reason: str, rollback: bool) -> dict[str, Any]:
        with self.exclusive():
            state, lock = self.current()
            journaled = self.journal_path.exists()
            if rollback and not journaled:
                raise Refused("recover --rollback settles an interrupted publish and no _journal.json is present; "
                              "reclaim a stale lock with recover --reason instead")
            if not rollback and not reason.strip():
                raise Refused("recover requires --reason (evidence of why the lock is reclaimed)")
            if journaled and not rollback:
                raise Refused("interrupted checkpoint journal present; run recover --rollback before reclaiming the lock")
            if journaled:
                return self.settle_interrupted(owner, reason, state, lock)
            if lock is None:
                raise Refused("nothing to recover: no lock")
            return self.reclaim(owner, reason, state, lock)

    def recovery_evidence(self, lock: dict[str, Any] | None, reason: str) -> dict[str, Any]:
        return {"prior_lock_path": self.rel(self.lock_path), "prior_heartbeat": (lock or {}).get("heartbeat"),
                "prior_owner": (lock or {}).get("owner"),
                "prior_lock_sha256": sha256_file(self.lock_path) if self.lock_path.exists() else None, "reason": reason}

    def settle_interrupted(self, owner: str, reason: str, state: dict[str, Any] | None, lock: dict[str, Any] | None) -> dict[str, Any]:
        """Roll an interrupted publish forward when its core finished, otherwise back.

        Whichever it is, the lock leaves with a fresh heartbeat: the docs promise
        "roll back, then re-checkpoint", and an interruption left overnight would
        otherwise come back stale."""
        journal = read_json(self.journal_path) or {}
        journal_revision = _as_int(journal.get("revision"))
        target = journal_revision - 1
        evidence = self.recovery_evidence(lock, reason)
        stamp = now_iso()
        if (state is not None and lock is not None
                and _as_int(state.get("revision"), -1) == journal_revision
                and _as_int(lock.get("revision"), -2) == journal_revision):
            # Core publish completed; only the pointer/journal step was lost.
            atomic_write(self.lock_path, dump({**lock, "heartbeat": stamp, "heartbeat_source": "recover"}))
            atomic_write(self.pointer, dump({"schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                             "revision": journal_revision, "updated_at": stamp}))
            self.settle_event(journal_revision, "rollforward", {**evidence, "revision": journal_revision, "by": owner})
            self.clear_journal()
            return {"result": "ok", "operation": "rollforward", "run_id": self.run_id, "revision": journal_revision, "evidence": evidence}
        if journal_revision < 1:
            raise Refused("journal is unreadable or names no revision; escalate to the owner")
        if journal_revision == 1:
            return self.retire_unpublished_first_revision(owner, evidence)
        state_snap = self.history / f"rev-{target}.state.json"
        lock_snap = self.history / f"rev-{target}.lock.json"
        snap_state, snap_lock = read_json(state_snap), read_json(lock_snap)
        if self.describes(snap_state, target) and self.describes(snap_lock, target):
            restored_state, restored_lock = snap_state, snap_lock
            source = "history snapshot"
        elif state is not None and _as_int(state.get("revision"), -1) == target:
            # The state file is the last coherent revision; only the lock (or
            # the pointer) was left mid-publish. Rebuild the lock from state.
            restored_state = state
            restored_lock = {**(lock or {}), "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                             "owner": state.get("active_owner", owner),
                             "status": "held" if state.get("status") in ACTIVE_STATUSES else "released",
                             "session_pin": state.get("status") in ACTIVE_STATUSES, "revision": target}
            source = "state file (lock rebuilt)"
        elif state_snap.exists() or lock_snap.exists():
            raise Refused(f"history snapshot for revision {target} is unreadable or is not this run's record, and the state file "
                          f"is not at that revision; escalate to the owner")
        else:
            raise Refused(f"no coherent snapshot for revision {target}; escalate to the owner")
        atomic_write(self.lock_path, dump({**restored_lock, "heartbeat": stamp, "heartbeat_source": "recover"}))
        atomic_write(self.state_path, dump(restored_state))
        atomic_write(self.pointer, dump({"schema_version": SCHEMA_VERSION, "run_id": self.run_id,
                                         "revision": target, "updated_at": stamp}))
        self.settle_event(target, "rollback", {**evidence, "restored_revision": target, "by": owner, "source": source})
        self.clear_journal()
        return {"result": "ok", "operation": "rollback", "run_id": self.run_id, "revision": target, "evidence": evidence}

    def retire_unpublished_first_revision(self, owner: str, evidence: dict[str, Any]) -> dict[str, Any]:
        """A `create` that died before it finished has no earlier revision to restore.

        Whatever it wrote moves into _history/ under an ``unpublished`` name, so the
        bytes survive as evidence and the run id is free for `create` again."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        retired: dict[str, str] = {}
        try:
            self.history.mkdir(exist_ok=True)
            for path, kind in ((self.lock_path, "lock"), (self.state_path, "state")):
                if path.exists():
                    digest = sha256_file(path)
                    _fsutil.replace_with_retry(path, self.history / f"rev-1.{kind}.unpublished-{stamp}.json")
                    retired[kind] = digest
        except OSError as exc:
            raise Degraded(f"could not retire the unpublished first revision: {_why(exc)}") from exc
        self.settle_event(0, "rollback", {**evidence, "restored_revision": 0, "discarded_revision": 1, "by": owner,
                                          "source": "unpublished first revision", "retired": retired})
        self.clear_journal()
        return {"result": "ok", "operation": "rollback", "run_id": self.run_id, "revision": 0, "evidence": evidence}

    def reclaim(self, owner: str, reason: str, state: dict[str, Any] | None, lock: dict[str, Any]) -> dict[str, Any]:
        evidence = self.recovery_evidence(lock, reason)
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
        new_state = {**state, "revision": current + 1, "parent_revision": current, "active_owner": owner,
                     "timestamp": stamp, "recovered_from": evidence}
        new_lock = {**lock, "owner": owner, "status": "held", "session_pin": True, "revision": current + 1,
                    "heartbeat": stamp, "acquired_at": stamp}
        self.publish(new_state, new_lock, event=("recover", {**evidence, "by": owner, "revision": current + 1}))
        return {"result": "ok", "operation": "recover", "run_id": self.run_id, "revision": current + 1, "evidence": evidence}

    def status(self) -> dict[str, Any]:
        result = dict(inspect_saves(self.project_root))
        requested = inspect_run(self.project_root, self.run_id)
        result["operation"] = "status"
        result["run_id_requested"] = self.run_id
        result["interrupted"] = self.journal_path.exists()
        if result["interrupted"]:
            result["detail"] = f"interrupted checkpoint journal present: {self.rel(self.journal_path)}"
            result["status"] = "interrupted"
            requested["state"] = "interrupted"
        result["requested_run"] = requested
        state, lock = self.current()
        result["revision"] = state.get("revision") if state else None
        result["owner"] = lock.get("owner") if lock else None
        result["next_step"] = NEXT_STEPS.get(str(result["status"]), "")
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
    parser.add_argument("--evidence", action="append", default=[], help="project-relative evidence path (repeatable); create requires at least one")
    parser.add_argument("--drop-evidence", action="append", default=[], help="checkpoint: stop registering this evidence path (repeatable; needs --reason)")
    parser.add_argument("--expect-revision", type=int)
    parser.add_argument("--status", default="active", help="checkpoint status: active|paused|awaiting-input")
    parser.add_argument("--execution-mode", default="agent")
    parser.add_argument("--next-action", default=None)
    parser.add_argument("--reason", default="", help="recover: why the lock is reclaimed; checkpoint: why --drop-evidence removes evidence")
    parser.add_argument("--rollback", action="store_true", help="recover: settle an interrupted publish (roll forward or back to the last coherent revision)")
    parser.add_argument("--set", action="append", default=[], help="extra state field key=value (repeatable)")
    parser.add_argument("--reopen", action="store_true", help="checkpoint: deliberately reopen a complete/blocked run as a new revision (REVISE)")
    parser.add_argument("--lock-timeout", type=float, default=WRITER_LOCK_TIMEOUT,
                        help="seconds to wait for another writer before refusing (default: %(default)s)")
    args = parser.parse_args()
    store = None
    try:
        store = RunStore(Path(args.project_root) if args.project_root else _state.project_root(), args.run_id,
                         lock_timeout=max(0.0, args.lock_timeout))
        extra = parse_extra(args.set)
        if args.operation == "block" and args.reason:
            raise Refused("block does not record a reason, so --reason is refused instead of dropped; it belongs to recover "
                          "and checkpoint --drop-evidence. Say why the run is blocked with --next-action or --set key=value")
        if args.operation == "create":
            result = store.create(args.owner, args.evidence, args.execution_mode, args.next_action or "select earliest incomplete boundary", extra)
        elif args.operation == "checkpoint":
            result = store.checkpoint(args.owner, args.expect_revision, args.evidence, args.status, args.next_action, extra,
                                      reopen=args.reopen, drop_evidence=args.drop_evidence, reason=args.reason)
        elif args.operation == "heartbeat":
            result = store.heartbeat(args.owner)
        elif args.operation == "complete":
            result = store.finish(args.owner, "complete", args.next_action, extra)
        elif args.operation == "block":
            result = store.finish(args.owner, "blocked", args.next_action, extra)
        elif args.operation == "release":
            result = store.finish(args.owner, "released", args.next_action, extra)
        elif args.operation == "recover":
            result = store.recover(args.owner, args.reason, args.rollback)
        else:
            result = store.status()
        if WRITE_NOTES:
            result["write_notes"] = list(WRITE_NOTES)
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    except Refused as exc:
        if store is not None and args.operation != "status":
            store.note_failure("refused", args.operation, args.owner, str(exc))
        print(json.dumps({"result": "refused", "operation": args.operation, "run_id": args.run_id, "reason": str(exc)}, indent=2))
        return EXIT_REFUSED
    except Degraded as exc:
        if store is not None:
            store.note_failure("degraded", args.operation, args.owner, str(exc))
        print(json.dumps({"result": "degraded", "operation": args.operation, "run_id": args.run_id, "reason": str(exc),
                          "note": "the write did not complete; see reason for what was and was not published, then run status"}, indent=2))
        return EXIT_DEGRADED
    except (OSError, ValueError) as exc:
        print(json.dumps({"result": "engine_error", "operation": args.operation, "reason": str(exc)}, indent=2), file=sys.stderr)
        return EXIT_ENGINE


if __name__ == "__main__":
    raise SystemExit(main())
