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


SCHEMA_VERSION = 1
STALE_AFTER_SECONDS = 30 * 60
ACTIVE_STATUSES = {"active", "paused", "awaiting-input"}
TERMINAL_STATUSES = {"complete", "blocked", "released"}


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


def _mapping(path: Path) -> dict[str, Any] | None:
    try:
        value = parse_yaml(path.read_text(encoding="utf-8"))
    except (OSError, DataFormatError):
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


def _timestamp(value: Any) -> datetime | None:
    text = _string(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _list_of_strings(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items = tuple(_string(item) for item in value)
    return items if all(items) else None


def _safe_evidence_paths(project_root: Path, paths: tuple[str, ...]) -> tuple[bool, str]:
    for value in paths:
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts:
            return False, f"unsafe evidence path {value!r}"
        try:
            resolved = (project_root / candidate).resolve()
            resolved.relative_to(project_root.resolve())
        except (OSError, ValueError):
            return False, f"evidence path escapes project root {value!r}"
        if not resolved.exists():
            return False, f"missing evidence path {value!r}"
    return True, "evidence paths present"


def _pointer(root: Path) -> tuple[str, str, datetime | None, str]:
    path = root / "_latest.md"
    data = _mapping(path)
    if data is None:
        return "", "", None, "pointer missing or malformed"
    if data.get("schema_version") != SCHEMA_VERSION:
        return "", "", None, "pointer schema_version is invalid"
    run_id = _string(data.get("run_id"))
    revision = _revision(data.get("revision"))
    updated = _timestamp(data.get("updated_at"))
    if not run_id or not revision or updated is None:
        return "", "", None, "pointer requires run_id, revision, and updated_at"
    return run_id, revision, updated, "pointer valid"


def _record(project_root: Path, run_dir: Path, now: datetime) -> SaveRecord:
    state_path = run_dir / "_state.md"
    lock_path = run_dir / "_lock.md"
    state = _mapping(state_path)
    lock = _mapping(lock_path)
    run_id = run_dir.name
    state_run_id = _string(state.get("run_id")) if state else ""
    revision = _revision(state.get("revision")) if state else ""
    status = _string(state.get("status")).lower() if state else ""
    pin = _bool(state.get("session_pin")) if state else None
    state_owner = _string(state.get("active_owner")) if state else ""
    evidence = _list_of_strings(state.get("evidence_paths")) if state else None
    heartbeat = _timestamp(lock.get("heartbeat")) if lock else None
    lock_revision = _revision(lock.get("revision")) if lock else ""
    lock_owner = _string(lock.get("owner")) if lock else ""
    lock_status = _string(lock.get("status")).lower() if lock else ""
    lock_pin = _bool(lock.get("session_pin")) if lock else None

    reason = "coherent"
    coherent = True
    stale = False
    if not state or state.get("schema_version") != SCHEMA_VERSION:
        coherent, reason = False, "state is missing or schema-invalid"
    elif state_run_id != run_id:
        coherent, reason = False, "state run_id does not match directory"
    elif not revision or not status or status not in ACTIVE_STATUSES | TERMINAL_STATUSES:
        coherent, reason = False, "state status or revision is invalid"
    elif pin is None or not state_owner:
        coherent, reason = False, "state requires boolean session_pin and active_owner"
    elif evidence is None or not evidence:
        coherent, reason = False, "state requires non-empty evidence_paths"
    elif _timestamp(state.get("timestamp")) is None:
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
    else:
        evidence_ok, evidence_reason = _safe_evidence_paths(project_root, evidence)
        if not evidence_ok:
            coherent, reason = False, evidence_reason
        elif status in ACTIVE_STATUSES and (not pin or lock_status != "held" or lock_pin is not True):
            coherent, reason = False, "active state must hold a pinned lock"
        elif status in TERMINAL_STATUSES and (pin or lock_status != "released" or lock_pin is not False):
            coherent, reason = False, "terminal state must release an unpinned lock"
        elif status in ACTIVE_STATUSES and heartbeat is not None:
            stale = (now - heartbeat).total_seconds() > STALE_AFTER_SECONDS
            if stale:
                reason = "lock heartbeat is older than 30 minutes"

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
    )


def inspect_saves(project_root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Return a deterministic classification and evidence for saved state."""
    now = now or datetime.now(timezone.utc)
    root = project_root.resolve() / "skillset-saves"
    if not root.exists():
        return {"status": "missing", "detail": "skillset-saves does not exist", "run_id": ""}
    runs_dir = root / "runs"
    if not runs_dir.is_dir():
        return {"status": "missing", "detail": "skillset-saves/runs does not exist", "run_id": ""}

    run_dirs = sorted((path for path in runs_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
    records = [_record(project_root.resolve(), path, now) for path in run_dirs]
    active = [record for record in records if record.coherent and record.status in ACTIVE_STATUSES and not record.stale]
    stale = [record for record in records if record.coherent and record.status in ACTIVE_STATUSES and record.stale]
    corrupt = [record for record in records if not record.coherent]
    pointer_path = root / "_latest.md"
    pointer_exists = pointer_path.exists()
    pointer_run_id, pointer_revision, pointer_updated_at, pointer_reason = _pointer(root)
    if pointer_exists and not pointer_run_id:
        return {"status": "corrupt", "detail": pointer_reason, "run_id": ""}
    if pointer_run_id and (Path(pointer_run_id).name != pointer_run_id or pointer_run_id in {".", ".."}):
        return {"status": "corrupt", "detail": "pointer run_id is not a safe directory name", "run_id": ""}
    if pointer_run_id and not (runs_dir / pointer_run_id).is_dir():
        return {"status": "corrupt", "detail": f"pointer target run {pointer_run_id} does not exist", "run_id": ""}
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
    pointer_stale = (
        pointer_updated_at is not None
        and (now - pointer_updated_at).total_seconds() > STALE_AFTER_SECONDS
    )

    held_runs = active + stale
    if len(held_runs) > 1:
        ids = ", ".join(record.run_id for record in held_runs)
        return {"status": "conflicting", "detail": f"multiple coherent held runs: {ids}", "run_id": ""}
    if active:
        record = active[0]
        if pointer_run_id == record.run_id and pointer_revision == record.revision and not pointer_stale:
            return {"status": "active", "detail": f"latest run {record.run_id} is coherent and pinned", "run_id": record.run_id}
        detail = (
            f"latest pointer is stale for coherent active run {record.run_id}"
            if pointer_stale
            else f"coherent active run {record.run_id} is not addressed by the latest pointer"
        )
        return {"status": "orphaned", "detail": detail, "run_id": record.run_id}
    if stale:
        record = stale[0]
        return {"status": "stale", "detail": f"run {record.run_id} has a heartbeat older than 30 minutes", "run_id": record.run_id}
    if corrupt and not any(record.coherent for record in records):
        return {"status": "corrupt", "detail": corrupt[0].reason, "run_id": corrupt[0].run_id}
    if records:
        if pointer_run_id:
            return {"status": "inactive", "detail": f"latest run {pointer_run_id} is not active", "run_id": pointer_run_id}
        return {"status": "inactive", "detail": "runs exist but none are active", "run_id": ""}
    return {"status": "unreadable", "detail": "skillset-saves exists but no readable run state was found", "run_id": ""}


def classify_saves(project_root: Path, *, now: datetime | None = None) -> tuple[str, str]:
    """Compatibility wrapper for readiness's human-readable output."""
    result = inspect_saves(project_root, now=now)
    return str(result["status"]), str(result["detail"])


def has_active_run(project_root: Path) -> bool:
    """Return true only for a coherent fresh active or recoverable orphaned run."""
    status, _ = classify_saves(project_root)
    return status in {"active", "orphaned"}
