#!/usr/bin/env python3
"""Refresh the pinned run's lock heartbeat from real host activity.

The save protocol makes a lock stale after 30 idle minutes, but a long stretch of
tool work between two checkpoints is not idleness. Every registered hook therefore
calls ``refresh`` on each host event, and it refreshes the heartbeat when all of
these hold:

* the payload carries a host ``session_id`` (synthetic invocations never touch save
  state);
* the run the latest pointer names has no fresh heartbeat. A fresh one means nothing is
  due, and that check is two small reads, not a scan of every saved run;
* the scan that does classify every run has not run in the last ``SCAN_EVERY``
  seconds, because an idle project with a long history would otherwise pay for it on
  every host event;
* ``skillset-saves`` holds exactly one coherent active or orphaned run;
* its lock is held, pinned, not interrupted, and *not yet stale*: a stale lock is
  reclaimed only through ``save_run.py recover --reason`` so the reclaim leaves audit
  evidence, and the hook never revives one;
* the heartbeat is older than ``REFRESH_AFTER``.

The write goes through ``save_run.RunStore.heartbeat`` (the single sanctioned writer) as
the lock's recorded owner, with ``heartbeat_source`` set to ``hook:<event>``. A hook must
never hold up the host, so it waits only ``save_run.HOOK_LOCK_WAIT`` for the writer lock
and skips the refresh when another writer holds it; the writer re-checks the run under
the lock.

This is its own module so ``_state``, the lowest module of the hook directory, does not
import the run-record writer, which imports it. ``_saves`` and ``save_run`` are imported
where they are used: the common call returns before it needs either.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import _state

# Refresh at most once per this many seconds so a busy session does not rewrite
# the lock on every tool call.
REFRESH_AFTER = 5 * 60
# Classify every saved run at most this often looking for one to refresh.
SCAN_EVERY = 60


def refresh(data: dict, event: str) -> dict | None:
    """Refresh the pinned run's lock heartbeat when one is due. Never raises; returns the writer result or None."""
    try:
        session = str((data or {}).get("session_id") or "").strip()
        if not session:
            return None
        root = _state.project_root()
        runs = root / "skillset-saves" / "runs"
        if not runs.is_dir():
            return None
        from _saves import heartbeat_is_stale, inspect_saves, parse_timestamp, pointed_heartbeat

        now = datetime.now(timezone.utc)
        pointed = pointed_heartbeat(root)
        if pointed is not None and 0 <= (now - pointed).total_seconds() < REFRESH_AFTER:
            return None
        scanned = _state.state_dir() / "observations" / "heartbeat-scan.json"
        marker = _state.read_json(scanned, {})
        last = marker.get("checked_at") if isinstance(marker, dict) else None
        if isinstance(last, (int, float)) and 0 <= time.time() - last < SCAN_EVERY:
            return None
        _state.write_json(scanned, {"checked_at": time.time()})
        result = inspect_saves(root)
        run_id = str(result.get("run_id") or "")
        if result.get("status") not in {"active", "orphaned"} or not run_id:
            return None
        run_dir = runs / run_id
        if (run_dir / "_journal.json").exists():
            return None
        lock = _state.read_mapping(run_dir / "_lock.md")
        if not isinstance(lock, dict) or str(lock.get("status")) != "held" or lock.get("session_pin") is not True:
            return None
        beat = parse_timestamp(lock.get("heartbeat"))
        if beat is None or heartbeat_is_stale(beat, now) or (now - beat).total_seconds() < REFRESH_AFTER:
            return None
        import save_run

        store = save_run.RunStore(root, run_id)
        return store.heartbeat(str(lock.get("owner") or "admiral"), source=f"hook:{event}",
                               wait=save_run.HOOK_LOCK_WAIT, min_age=REFRESH_AFTER)
    except Exception as exc:
        _state.record_fault(event, exc)  # a heartbeat that cannot be kept lets a live run go stale, so it is counted
        return None
