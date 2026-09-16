#!/usr/bin/env python3
"""
Shared state helper for the Supreme Team runtime-harness hooks.

Implements the Action Realization (Layer 3) and Trajectory Regulation (Layer 4)
storage used by ``pre_tool_use.py`` and ``post_tool_use.py``. Stdlib only — no
third-party dependencies. The supported Supreme Team install baseline is Python
3.13+ so readiness checks, hook registration, and hook execution all share one
interpreter requirement.

Design posture (see ../../harness-doctrine.md, Principles): every function here
FAILS OPEN. Any I/O or parse error returns a safe empty/default value and never
raises into the hook, so a harness fault can never block the host loop.

Layout under ``.harness-state/``::

    guard-state.json                 owner-controlled protections (no TTL)
    trajectories/<run>/<identity>.json   scoped per project, run, and session

Trajectory identity: the host ``session_id`` when supplied; otherwise a
session id from the environment; otherwise the host *process* identity
(parent pid + creation-bound token) so independent invocations without a
session id never share one global history. The identity is hashed, never
sanitised by deleting characters.
"""

import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Maximum trajectory signatures retained per identity (bounded memory).
_MAX_TRAJ = 40
# Trajectory files older than this are pruned on the next append.
_TRAJ_RETENTION_SECONDS = 7 * 24 * 3600
_LEGACY_TRAJ_PREFIX = "traj-"

_SESSION_ENV = ("SUPREMETEAM_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "COPILOT_SESSION_ID", "GITHUB_RUN_ID")


# A project root is recognised by one of these markers. Walking up from the
# working directory keeps runtime state at the project root even when a
# script is invoked from a subdirectory (save-ownership.yaml generated_roots).
_ROOT_MARKERS = ("skillset-saves", ".harness-state", ".git")
_PROJECT_ENV = ("SUPREMETEAM_PROJECT_DIR", "CLAUDE_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE")


def find_project_root(start: "str | Path | None" = None) -> Path:
    """Nearest ancestor of ``start`` (default: cwd) holding a root marker, else ``start``."""
    try:
        origin = Path(start or os.getcwd()).resolve()
    except Exception:
        return Path(start or os.getcwd())
    for candidate in (origin, *origin.parents):
        try:
            if any((candidate / marker).exists() for marker in _ROOT_MARKERS):
                return candidate
        except Exception:
            continue
    return origin


def project_root() -> Path:
    """Explicit host or Supreme Team project variable first, then the nearest marked ancestor of cwd."""
    for name in _PROJECT_ENV:
        value = os.environ.get(name)
        if value:
            return Path(value)
    return find_project_root()


def state_dir() -> Path:
    """Return the harness state directory, creating it if possible.

    Prefers ``$SUPREMETEAM_PROJECT_DIR/.harness-state`` so guard/freeze records
    and trajectory state live with the project; falls back through known host
    project-directory variables, then the nearest ancestor of the working
    directory that holds ``skillset-saves/``, ``.harness-state/``, or ``.git``,
    then the working directory itself, then a *project-namespaced* directory
    under the OS temp root (never one shared temp directory across unrelated
    projects).
    """
    base = project_root()
    try:
        d = base / ".harness-state"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        namespace = hashlib.sha1(str(base).encode("utf-8", "ignore")).hexdigest()[:16]
        d = Path(tempfile.gettempdir()) / "supremeteam-harness-state" / namespace
        try:
            d.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return d


def _read_json(path: Path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, obj) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(obj), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass  # fail open — losing state never blocks the host


def read_hook_input() -> dict:
    """Read and parse the JSON hook payload from stdin. Never raises."""
    import sys

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


# --- Guard / Freeze boundary (written by the guard & freeze skills) ----------

def _effective_globs(entries) -> list:
    """Accept bare glob strings and freeze *records*.

    A record is ``{"glob": "src/payments/**", "owner": ..., "scope": ...,
    "created_at": ..., "run_id": ..., "released_at": null}``. A record stays
    effective until its owner records ``released_at`` (or ``released: true``);
    age alone never expires a protection.
    """
    result = []
    for entry in entries or []:
        if isinstance(entry, str) and entry:
            result.append(entry)
        elif isinstance(entry, dict):
            glob = entry.get("glob")
            released = bool(entry.get("released_at")) or entry.get("released") is True
            if isinstance(glob, str) and glob and not released:
                result.append(glob)
    return result


def load_guard_state() -> dict:
    """Load the active guard/freeze boundary.

    Schema (``.harness-state/guard-state.json``), all keys optional::

        {
          "frozen_globs":   ["src/payments/**", {"glob": "infra/*.tf", "owner": "ops", "scope": "release freeze", "created_at": "...", "released_at": null}],
          "blocked_globs":  ["**/secrets/**"],
          "allow_dangerous": false
        }

    Returns an empty dict when no boundary is set (the common case), so the hook
    is inert until a guard/freeze skill explicitly records a boundary. The
    returned ``frozen_globs``/``blocked_globs`` are the *effective* glob strings;
    the raw records are exposed under ``freeze_records`` for reporting.
    """
    state = _read_json(state_dir() / "guard-state.json", {})
    if not isinstance(state, dict):
        return {}
    normalized = dict(state)
    normalized["freeze_records"] = [e for e in (state.get("frozen_globs") or []) if isinstance(e, dict)] + \
        [e for e in (state.get("blocked_globs") or []) if isinstance(e, dict)]
    normalized["frozen_globs"] = _effective_globs(state.get("frozen_globs"))
    normalized["blocked_globs"] = _effective_globs(state.get("blocked_globs"))
    # A read-only run (explore pipeline): records with run_id, owner, scope,
    # created_at, released_at, and the allow globs of the run's own save path.
    # Effective until released; never expired by age.
    normalized["read_only"] = [
        e for e in (state.get("read_only") or [])
        if isinstance(e, dict) and not e.get("released_at")
    ]
    return normalized


# --- Per-session trajectory tracking (Layer 4) -------------------------------

def _active_run_id() -> str:
    """Best-effort run scope from the save pointer; never raises."""
    try:
        pointer = project_root() / "skillset-saves" / "_latest.md"
        if not pointer.is_file():
            return "no-run"
        text = pointer.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except ValueError:
            data = {}
            for line in text.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    data[key.strip()] = value.strip()
        run_id = str(data.get("run_id", "")).strip()
        if run_id and Path(run_id).name == run_id and run_id not in {".", ".."}:
            return run_id
    except Exception:
        pass
    return "no-run"


def trajectory_identity(data: dict) -> tuple:
    """Return ``(identity, source)`` for the current invocation.

    Preference order: host payload ``session_id``; a session id from the
    environment; the host process identity. The process identity is the
    parent pid combined with the state directory, which keeps two unrelated
    host sessions apart even when neither supplies a session id.
    """
    session = str((data or {}).get("session_id") or "").strip()
    if session:
        return session, "payload"
    for name in _SESSION_ENV:
        value = str(os.environ.get(name) or "").strip()
        if value:
            return f"{name}:{value}", "environment"
    try:
        ppid = os.getppid()
    except Exception:
        ppid = 0
    return f"process:{ppid}", "process"


def _traj_path(identity: str) -> Path:
    key = hashlib.sha1(str(identity or "anonymous").encode("utf-8", "ignore")).hexdigest()[:20]
    return state_dir() / "trajectories" / _active_run_id() / f"{key}.json"


def _prune_old(directory: Path) -> None:
    try:
        cutoff = time.time() - _TRAJ_RETENTION_SECONDS
        count = 0
        for path in directory.rglob("*.json"):
            count += 1
            if count > 200:
                break
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except Exception:
                continue
    except Exception:
        pass


class _FileLock:
    """Tiny O_EXCL lock so concurrent appends do not interleave. Fails open."""

    def __init__(self, path: Path) -> None:
        self.path = path.with_name(path.name + ".lock")
        self.fd = None

    def __enter__(self):
        deadline = time.monotonic() + 0.25
        while True:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 5:
                        self.path.unlink()  # abandoned lock
                        continue
                except Exception:
                    pass
                if time.monotonic() > deadline:
                    return self  # fail open: proceed without the lock
                time.sleep(0.01)
            except Exception:
                return self

    def __exit__(self, *exc):
        try:
            if self.fd is not None:
                os.close(self.fd)
                self.path.unlink()
        except Exception:
            pass
        return False


# --- Active-run heartbeat refresh --------------------------------------------

# Refresh at most once per this many seconds so a busy session does not rewrite
# the lock on every tool call.
_HEARTBEAT_REFRESH_AFTER = 5 * 60


def refresh_run_heartbeat(data: dict, event: str) -> dict | None:
    """Refresh the pinned run's lock heartbeat from real host activity.

    The save protocol makes a lock stale after 30 idle minutes, but a long
    stretch of tool work between two checkpoints is not idleness. Every hook
    therefore refreshes the heartbeat when all of these hold:

    * the payload carries a host ``session_id`` (synthetic invocations never
      touch save state);
    * ``skillset-saves`` holds exactly one coherent active or orphaned run;
    * its lock is held, pinned, not interrupted, and *not yet stale* -- a stale
      lock is reclaimed only through ``save_run.py recover --reason`` so the
      reclaim leaves audit evidence; the hook never revives one;
    * the heartbeat is older than ``_HEARTBEAT_REFRESH_AFTER``.

    The write goes through ``save_run.RunStore.heartbeat`` (the single
    sanctioned writer) as the lock's recorded owner, with ``heartbeat_source``
    set to ``hook:<event>``. Never raises; returns the writer result or None.
    """
    try:
        session = str((data or {}).get("session_id") or "").strip()
        if not session:
            return None
        root = project_root()
        runs = root / "skillset-saves" / "runs"
        if not runs.is_dir():
            return None
        hook_dir = str(Path(__file__).resolve().parent)
        if hook_dir not in sys.path:
            sys.path.insert(0, hook_dir)
        from _saves import STALE_AFTER_SECONDS, _mapping, inspect_saves  # noqa: WPS433

        result = inspect_saves(root)
        run_id = str(result.get("run_id") or "")
        if result.get("status") not in {"active", "orphaned"} or not run_id:
            return None
        run_dir = runs / run_id
        if (run_dir / "_journal.json").exists():
            return None
        lock = _mapping(run_dir / "_lock.md")
        if not isinstance(lock, dict) or str(lock.get("status")) != "held" or lock.get("session_pin") is not True:
            return None
        beat = datetime.fromisoformat(str(lock.get("heartbeat")).replace("Z", "+00:00"))
        if beat.tzinfo is None:
            beat = beat.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - beat).total_seconds()
        if age < _HEARTBEAT_REFRESH_AFTER or age > STALE_AFTER_SECONDS:
            return None
        import save_run  # noqa: WPS433

        store = save_run.RunStore(root, run_id)
        return store.heartbeat(str(lock.get("owner") or "admiral"), source=f"hook:{event}")
    except Exception:
        return None


# --- Host-observed hook firing ----------------------------------------------

def record_observation(event: str, data: dict) -> None:
    """Record that the host actually invoked this hook.

    Only a payload that carries a host ``session_id`` counts as a real host
    event; synthetic test invocations (no session id) are recorded separately
    so readiness can distinguish ``observed`` from ``simulated``. Never raises.
    """
    try:
        session = str((data or {}).get("session_id") or "").strip()
        kind = "observed" if session else "simulated"
        path = state_dir() / "observations" / f"{event}.json"
        current = _read_json(path, {})
        if not isinstance(current, dict):
            current = {}
        entry = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
            "session_hash": hashlib.sha1(session.encode("utf-8", "ignore")).hexdigest()[:12] if session else None,
            "tool_name": str((data or {}).get("tool_name") or "") or None,
            "count": int((current.get(kind) or {}).get("count", 0)) + 1,
        }
        current[kind] = entry
        _write_json(path, current)
    except Exception:
        pass


def load_observations() -> dict:
    """Return {event: {"observed": {...}|None, "simulated": {...}|None}}."""
    result = {}
    try:
        directory = state_dir() / "observations"
        if directory.is_dir():
            for path in directory.glob("*.json"):
                data = _read_json(path, {})
                if isinstance(data, dict):
                    result[path.stem] = {"observed": data.get("observed"), "simulated": data.get("simulated")}
    except Exception:
        pass
    return result


def load_trajectory(identity: str) -> list:
    data = _read_json(_traj_path(identity), [])
    return data if isinstance(data, list) else []


def append_trajectory(identity: str, entry: dict) -> list:
    """Append one step signature and return the bounded recent history."""
    path = _traj_path(identity)
    with _FileLock(path):
        history = load_trajectory(identity)
        history.append(entry)
        history = history[-_MAX_TRAJ:]
        _write_json(path, history)
    _prune_old(path.parent.parent)
    return history
