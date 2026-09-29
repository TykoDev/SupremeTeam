#!/usr/bin/env python3
"""Read and classify the canonical Supreme Team ``skillset-saves`` contract.

This module is deliberately shared by readiness and prompt-submit hooks.  The
hooks remain fail-open, but they no longer infer an active run from arbitrary
text.  A run is active only when its pointer, state, lock, revision lineage,
heartbeat, and referenced evidence agree.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from data_formats import DataFormatError, parse_yaml  # noqa: E402
from save_taxonomy import (  # noqa: E402
    ACTIVE_STATUSES, FUTURE_SKEW_SECONDS, JOURNAL, POINTER, SCHEMA_VERSION, STALE_AFTER_SECONDS, TERMINAL_STATUSES,
)

STALE_REASON = f"lock heartbeat is stale (older than {STALE_AFTER_SECONDS // 60} minutes or in the future)"

# What to do about each classification, so `status` can say it instead of
# leaving the reader to find the paragraph of save-protocol.md that does.
NEXT_STEPS = {
    "missing": "no run exists yet: after intake, run save_run.py create --run-id <id> --evidence <path>",
    "uninitialized": "a run directory exists with no run record: run save_run.py create --run-id <id> --evidence <path>",
    "active": "resume the run and checkpoint with --expect-revision",
    "orphaned": "run save_run.py heartbeat --run-id <id>, which rewrites the pointer from the run",
    "stale": "reclaim the lock with save_run.py recover --run-id <id> --reason <why>",
    "interrupted": "run save_run.py recover --run-id <id> --rollback",
    "conflicting": "close all but one held run with complete, block, or release",
    "corrupt": "preserve the record and escalate; never overwrite it",
    "inactive": "start a new run, or resume a released run with checkpoint",
    "complete": "start a new run, or revise this one with checkpoint --reopen",
    "unreadable": "confirm skillset-saves/runs holds readable run records, then escalate",
}


@dataclass(frozen=True)
class SaveRecord:
    run_id: str
    revision: str
    status: str
    session_pin: bool
    owner: str
    heartbeat: datetime | None
    state_path: Path
    lock_path: Path
    evidence_paths: tuple[str, ...]
    coherent: bool
    stale: bool
    reason: str
    # A run directory with no record at all: intake wrote its report, create has not run.
    pending: bool = False
    # Registered evidence that no longer exists, reported only where it was checked.
    evidence_missing: tuple[str, ...] = ()


def _mapping(path: Path) -> dict[str, Any] | None:
    try:
        value = parse_yaml(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, DataFormatError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return None


def _revision(value: Any) -> str:
    text = _string(value)
    return text if text.isdigit() and int(text) > 0 else ""


def parse_timestamp(value: Any) -> datetime | None:
    text = _string(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def heartbeat_is_stale(beat: datetime, now: datetime) -> bool:
    """Older than the window, or so far ahead of the clock that it cannot be believed.

    A future heartbeat never ages, so honouring one would pin a run for ever and
    leave `recover` refusing it as fresh."""
    age = (now - beat).total_seconds()
    return age > STALE_AFTER_SECONDS or age < -FUTURE_SKEW_SECONDS


def _list_of_strings(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items = tuple(_string(item) for item in value)
    return items if all(items) else None


def _unsafe_evidence(paths: tuple[str, ...]) -> str:
    for value in paths:
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            return f"unsafe evidence path {value!r}"
    return ""


def _resolve_evidence(project_root: Path, paths: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """Return ``(escape reason, paths that do not exist)`` for project-relative evidence."""
    root = project_root.resolve()
    missing = []
    for value in paths:
        try:
            resolved = (root / value).resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            return f"evidence path escapes project root {value!r}", ()
        if not resolved.exists():
            missing.append(value)
    return "", tuple(missing)


def _pointer(root: Path) -> tuple[str, str, datetime | None, str]:
    path = root / POINTER
    data = _mapping(path)
    if data is None:
        return "", "", None, "pointer missing or malformed"
    if data.get("schema_version") != SCHEMA_VERSION:
        return "", "", None, "pointer schema_version is invalid"
    run_id = _string(data.get("run_id"))
    revision = _revision(data.get("revision"))
    updated = parse_timestamp(data.get("updated_at"))
    if not run_id or not revision or updated is None:
        return "", "", None, "pointer requires run_id, revision, and updated_at"
    return run_id, revision, updated, "pointer valid"


def pointed_heartbeat(project_root: Path) -> datetime | None:
    """The lock heartbeat of the run the latest pointer names, or None when either is unreadable.

    Two small reads, so a hook that only needs to know whether a refresh is due
    can skip classifying every saved run."""
    saves = project_root.resolve() / "skillset-saves"
    run_id = _pointer(saves)[0]
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        return None
    lock = _mapping(saves / "runs" / run_id / "_lock.md")
    return parse_timestamp(lock.get("heartbeat")) if lock else None


def _record(project_root: Path, run_dir: Path, now: datetime, *, verify_evidence: bool = False) -> SaveRecord:
    """Classify one run directory.

    Evidence existence is checked for a held run, whose coherence depends on it,
    and where ``verify_evidence`` asks. A closed run is not held to evidence that
    was later pruned, and skipping the stat calls keeps a long history cheap."""
    state_path = run_dir / "_state.md"
    lock_path = run_dir / "_lock.md"
    pending = not state_path.exists() and not lock_path.exists() and not (run_dir / JOURNAL).exists()
    state = _mapping(state_path)
    lock = _mapping(lock_path)
    run_id = run_dir.name
    state_run_id = _string(state.get("run_id")) if state else ""
    revision = _revision(state.get("revision")) if state else ""
    status = _string(state.get("status")).lower() if state else ""
    pin = _bool(state.get("session_pin")) if state else None
    state_owner = _string(state.get("active_owner")) if state else ""
    evidence = _list_of_strings(state.get("evidence_paths")) if state else None
    heartbeat = parse_timestamp(lock.get("heartbeat")) if lock else None
    lock_revision = _revision(lock.get("revision")) if lock else ""
    lock_owner = _string(lock.get("owner")) if lock else ""
    lock_status = _string(lock.get("status")).lower() if lock else ""
    lock_pin = _bool(lock.get("session_pin")) if lock else None

    reason = "coherent"
    coherent = True
    stale = False
    missing: tuple[str, ...] = ()
    if pending:
        coherent, reason = False, "run directory holds no state or lock; create has not run"
    elif not state or state.get("schema_version") != SCHEMA_VERSION:
        coherent, reason = False, "state is missing or schema-invalid"
    elif state_run_id != run_id:
        coherent, reason = False, "state run_id does not match directory"
    elif not revision or not status or status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        coherent, reason = False, "state status or revision is invalid"
    elif pin is None or not state_owner:
        coherent, reason = False, "state requires boolean session_pin and active_owner"
    elif evidence is None or not evidence:
        coherent, reason = False, "state requires non-empty evidence_paths"
    elif parse_timestamp(state.get("timestamp")) is None:
        coherent, reason = False, "state timestamp is invalid"
    elif not lock or lock.get("schema_version") != SCHEMA_VERSION:
        coherent, reason = False, "lock is missing or schema-invalid"
    elif _string(lock.get("run_id")) != run_id:
        coherent, reason = False, "lock run_id does not match directory"
    elif not lock_owner or lock_owner != state_owner:
        coherent, reason = False, "lock owner does not match active_owner"
    elif not lock_revision or lock_revision != revision:
        coherent, reason = False, "state and lock revisions differ"
    elif heartbeat is None:
        coherent, reason = False, "lock heartbeat is invalid"
    elif lock_status not in {"held", "released"}:
        coherent, reason = False, "lock status is invalid"
    elif lock_pin is None:
        coherent, reason = False, "lock requires boolean session_pin"
    elif unsafe := _unsafe_evidence(evidence):
        coherent, reason = False, unsafe
    else:
        held = status in ACTIVE_STATUSES
        escape, missing = _resolve_evidence(project_root, evidence) if held or verify_evidence else ("", ())
        if escape:
            coherent, reason = False, escape
        elif missing and held:
            coherent, reason = False, f"missing evidence path {missing[0]!r}"
        elif held and (not pin or lock_status != "held" or lock_pin is not True):
            coherent, reason = False, "active state must hold a pinned lock"
        elif status in TERMINAL_STATUSES and (pin or lock_status != "released" or lock_pin is not False):
            coherent, reason = False, "terminal state must release an unpinned lock"
        elif held and heartbeat is not None:
            stale = heartbeat_is_stale(heartbeat, now)
            if stale:
                reason = STALE_REASON

    return SaveRecord(
        run_id=run_id,
        revision=revision,
        status=status,
        session_pin=pin is True,
        owner=state_owner or lock_owner,
        heartbeat=heartbeat,
        state_path=state_path,
        lock_path=lock_path,
        evidence_paths=evidence or (),
        coherent=coherent,
        stale=stale,
        reason=reason,
        pending=pending,
        evidence_missing=missing if coherent else (),
    )


def _closed(record: SaveRecord) -> dict[str, Any]:
    """Classification of a coherent run that holds no session pin."""
    complete = record.status == "complete"
    detail = f"latest run {record.run_id} is complete" if complete else f"latest run {record.run_id} is not active ({record.status})"
    result: dict[str, Any] = {"status": "complete" if complete else "inactive", "detail": detail,
                              "run_id": record.run_id, "run_status": record.status}
    if record.evidence_missing:
        result["evidence_missing"] = list(record.evidence_missing)
        result["detail"] += f"; {len(record.evidence_missing)} registered evidence path(s) no longer exist"
    return result


def inspect_saves(project_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Return a deterministic classification and evidence for saved state."""
    now = now or datetime.now(timezone.utc)
    root = project_root.resolve() / "skillset-saves"
    if not root.exists():
        return {"status": "missing", "detail": "skillset-saves does not exist", "run_id": ""}
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return {"status": "missing", "detail": "skillset-saves/runs does not exist", "run_id": ""}

    pointer_exists = (root / POINTER).exists()
    pointer_run_id, pointer_revision, pointer_updated_at, pointer_reason = _pointer(root)
    if pointer_exists and not pointer_run_id:
        return {"status": "corrupt", "detail": pointer_reason, "run_id": ""}
    if pointer_run_id and (Path(pointer_run_id).name != pointer_run_id or pointer_run_id in {".", ".."}):
        return {"status": "corrupt", "detail": "pointer run_id is not a safe directory name", "run_id": ""}
    if pointer_run_id and not (runs_dir / pointer_run_id).is_dir():
        return {"status": "corrupt", "detail": f"pointer target run {pointer_run_id} does not exist", "run_id": ""}

    run_dirs = sorted((path for path in runs_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
    records = [_record(project_root.resolve(), path, now, verify_evidence=path.name == pointer_run_id) for path in run_dirs]
    active = [record for record in records if record.coherent and record.status in ACTIVE_STATUSES and not record.stale]
    stale = [record for record in records if record.coherent and record.status in ACTIVE_STATUSES and record.stale]
    corrupt = [record for record in records if not record.coherent and not record.pending]
    pending = [record for record in records if record.pending]
    pointer_record = next((record for record in records if record.run_id == pointer_run_id), None)
    if pointer_run_id and pointer_record is None:
        return {"status": "corrupt", "detail": f"pointer target run {pointer_run_id} has no readable state", "run_id": pointer_run_id}
    if pointer_record is not None and not pointer_record.coherent:
        return {"status": "corrupt", "detail": pointer_record.reason, "run_id": pointer_record.run_id}
    if pointer_record is not None and pointer_revision != pointer_record.revision:
        return {
            "status": "corrupt",
            "detail": f"pointer revision {pointer_revision} does not match run revision {pointer_record.revision}",
            "run_id": pointer_record.run_id,
        }
    pointer_stale = pointer_updated_at is not None and heartbeat_is_stale(pointer_updated_at, now)

    held_runs = active + stale
    if len(held_runs) > 1:
        ids = ", ".join(record.run_id for record in held_runs)
        return {"status": "conflicting", "detail": f"multiple coherent held runs: {ids}", "run_id": ""}
    if active:
        record = active[0]
        if pointer_run_id == record.run_id and pointer_revision == record.revision and not pointer_stale:
            return {"status": "active", "detail": f"latest run {record.run_id} is coherent and pinned",
                    "run_id": record.run_id, "run_status": record.status}
        detail = (
            f"latest pointer is stale for coherent active run {record.run_id}"
            if pointer_stale
            else f"coherent active run {record.run_id} is not addressed by the latest pointer"
        )
        return {"status": "orphaned", "detail": detail, "run_id": record.run_id, "run_status": record.status}
    if stale:
        record = stale[0]
        return {"status": "stale", "detail": f"run {record.run_id}: {STALE_REASON}",
                "run_id": record.run_id, "run_status": record.status}
    if corrupt and not any(record.coherent for record in records):
        return {"status": "corrupt", "detail": corrupt[0].reason, "run_id": corrupt[0].run_id}
    if pointer_record is not None:
        return _closed(pointer_record)
    if any(record.coherent for record in records):
        return {"status": "inactive", "detail": "runs exist but none are active", "run_id": ""}
    if pending:
        return {"status": "uninitialized", "detail": f"run directory {pending[0].run_id} holds no state or lock; create has not run",
                "run_id": pending[0].run_id}
    return {"status": "unreadable", "detail": "skillset-saves exists but no readable run state was found", "run_id": ""}


def inspect_run(project_root: Path, run_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """Classify one run on its own, whatever else the save root holds.

    ``state`` is absent, uninitialized, corrupt, stale, active, or the run's own
    terminal status (complete, blocked, released)."""
    now = now or datetime.now(timezone.utc)
    root = project_root.resolve()
    run_dir = root / "skillset-saves" / "runs" / run_id
    if not run_dir.is_dir():
        return {"run_id": run_id, "state": "absent", "detail": f"run {run_id} has no directory"}
    record = _record(root, run_dir, now, verify_evidence=True)
    if record.pending:
        state = "uninitialized"
    elif not record.coherent:
        state = "corrupt"
    elif record.status in ACTIVE_STATUSES:
        state = "stale" if record.stale else "active"
    else:
        state = record.status
    result: dict[str, Any] = {"run_id": run_id, "state": state, "detail": record.reason}
    if record.status:
        result["run_status"] = record.status
    if record.revision:
        result["revision"] = int(record.revision)
    if record.evidence_missing:
        result["evidence_missing"] = list(record.evidence_missing)
    return result


def classify_saves(project_root: Path, *, now: datetime | None = None) -> tuple[str, str]:
    """Compatibility wrapper for readiness's human-readable output."""
    result = inspect_saves(project_root, now=now)
    return str(result["status"]), str(result["detail"])


def has_active_run(project_root: Path) -> bool:
    """Return true only for a coherent fresh active or recoverable orphaned run."""
    status, _ = classify_saves(project_root)
    return status in {"active", "orphaned"}
