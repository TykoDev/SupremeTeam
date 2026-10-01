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
session id from the environment; otherwise the host *process* identity: the
parent pid, bound to that process's start time where the platform exposes it
cheaply (Linux ``/proc``; elsewhere the pid alone), so independent invocations
without a session id never share one global history. The identity is hashed,
never sanitised by deleting characters.

Fail-open leaves a trace: a fault a hook swallows is counted by exception type,
never by message, in the observation record of its event (``faults`` and
``last_fault``), so readiness can tell a hook that fires from one that works.
"""

import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap
import _fsutil

# Maximum trajectory signatures retained per identity (bounded memory).
_MAX_TRAJ = 40
# Trajectory files older than this are pruned on the next append.
_TRAJ_RETENTION_SECONDS = 7 * 24 * 3600

_SESSION_ENV = ("SUPREMETEAM_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "COPILOT_SESSION_ID", "GITHUB_RUN_ID")


# A project root is recognised by one of these markers. Walking up from the
# working directory keeps runtime state at the project root even when a
# script is invoked from a subdirectory (save-ownership.yaml generated_roots).
ROOT_MARKERS = ("skillset-saves", ".harness-state", ".git")
# The one documented order: an explicit Supreme Team variable beats a host's own
# workspace variable, and any variable beats the marker walk from the working
# directory. Every hook-directory reader and writer resolves the root here.
PROJECT_ENV = ("SUPREMETEAM_PROJECT_DIR", "CLAUDE_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE")

# The longest a destructive-command lift may last, in minutes. The writer refuses
# more and the reader treats a longer grant as malformed, so a hand-edited
# ten-year expiry never becomes a standing kill-switch.
MAX_GRANT_MINUTES = 8 * 60


def find_project_root(start: "str | Path | None" = None) -> Path:
    """Nearest ancestor of ``start`` (default: cwd) holding a root marker, else ``start``."""
    try:
        origin = Path(start or os.getcwd()).resolve()
    except Exception:
        return Path(start or os.getcwd())
    for candidate in (origin, *origin.parents):
        try:
            if any((candidate / marker).exists() for marker in ROOT_MARKERS):
                return candidate
        except Exception:
            continue
    return origin


def project_root() -> Path:
    """The project root: the first set variable of ``PROJECT_ENV`` in order, else the nearest marked ancestor of cwd."""
    for name in PROJECT_ENV:
        value = os.environ.get(name)
        if value:
            return Path(value)
    return find_project_root()


def _fallback_dir(base: Path) -> Path:
    namespace = hashlib.sha256(str(base).encode("utf-8", "ignore")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / "supremeteam-harness-state" / namespace


def state_dir(root: "str | Path | None" = None, *, create: bool = True) -> Path:
    """Return the harness state directory, creating it unless ``create`` is false.

    Prefers ``<project root>/.harness-state`` (the root resolves as
    ``project_root`` documents, or is the ``root`` given) so guard/freeze records
    and trajectory state live with the project; falls back to a *project-namespaced*
    private directory under the OS temp root when that cannot be created (never
    one shared temp directory across unrelated projects). A reader passes
    ``create=False``: looking at state never makes any, and it finds the fallback
    where a writer put it.
    """
    base = Path(root) if root is not None else project_root()
    primary = base / ".harness-state"
    if not create:
        try:
            if primary.is_dir():
                return primary
            fallback = _fallback_dir(base)
            return fallback if fallback.is_dir() else primary
        except Exception:
            return primary
    try:
        primary.mkdir(parents=True, exist_ok=True)
        return primary
    except Exception:
        fallback = _fallback_dir(base)
        try:
            fallback.mkdir(mode=0o700, parents=True, exist_ok=True)
        except Exception:
            pass
        return fallback


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
    except OSError:
        return True


def state_dir_trusted(root: "str | Path | None" = None) -> bool:
    """True unless the state directory is a link or belongs to another user.

    A grant that loosens a protection (``allow_dangerous``) is honoured only from
    a directory this user owns and nobody replaced with a link: planting one in a
    shared temp directory, or pointing ``.harness-state`` at a directory the agent
    controls, must not be a way to switch the guard off. Restrictions are never
    dropped for being untrusted. Ownership is checked where the platform has it.
    """
    try:
        path = state_dir(root, create=False)
        if not path.exists():
            return True
        if _is_link(path):
            return False
        if hasattr(os, "geteuid") and path.stat().st_uid != os.geteuid():
            return False
        return True
    except Exception:
        return False


def existing_state_dir(base: "str | Path | None" = None) -> "Path | None":
    """The harness state directory when one already exists, else None.

    A read-only counterpart of ``state_dir()`` for diagnostics: it looks in the
    same two places (the project's ``.harness-state`` and the temp fallback) and
    never creates either.
    """
    root = Path(base) if base else project_root()
    namespace = hashlib.sha256(str(root).encode("utf-8", "ignore")).hexdigest()[:16]
    for candidate in (root / ".harness-state", Path(tempfile.gettempdir()) / "supremeteam-harness-state" / namespace):
        try:
            if candidate.is_dir():
                return candidate
        except OSError:
            continue
    return None


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
        _fsutil.atomic_write(path, json.dumps(obj))
    except Exception:
        pass  # fail open — losing state never blocks the host


def read_hook_input(event: "str | None" = None) -> dict:
    """Read and parse the JSON hook payload from stdin. Never raises.

    The bytes are decoded as UTF-8 with replacement, never with the console code
    page: on Windows a host pipe is not UTF-8 by default, and one character a
    legacy code page cannot decode (an A-acute, say) must not make the payload
    unreadable and every rule skip. A payload that still does not parse is empty
    and, when the caller names its ``event``, counted as a fault of that event.
    """
    try:
        stream = getattr(sys.stdin, "buffer", None)
        raw = stream.read().decode("utf-8", errors="replace") if stream is not None else sys.stdin.read()
        raw = raw.lstrip("\ufeff")
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        if event:
            record_fault(event, exc)
        return {}


# --- Guard / Freeze boundary (written by the guard & freeze skills) ----------

def is_released(entry: dict) -> bool:
    """The one test for a retired boundary record: ``released_at`` is set, or ``released`` is true.

    The writer only ever sets ``released_at``; the second spelling is accepted so a
    hand-written record retires the same way in the hook and in the writer,
    whichever kind of boundary it is."""
    return bool(entry.get("released_at")) or entry.get("released") is True


def _effective_globs(entries) -> list:
    """Accept bare glob strings and freeze *records*.

    A record is ``{"glob": "src/payments/**", "owner": ..., "scope": ...,
    "created_at": ..., "run_id": ..., "released_at": null}``. A record stays
    effective until its owner retires it (``is_released``); age alone never
    expires a protection.
    """
    result = []
    for entry in entries or []:
        if isinstance(entry, str) and entry:
            result.append(entry)
        elif isinstance(entry, dict):
            glob = entry.get("glob")
            if isinstance(glob, str) and glob and not is_released(entry):
                result.append(glob)
    return result


def load_guard_state(root: "str | Path | None" = None) -> dict:
    """Load the active guard/freeze boundary.

    Schema (``.harness-state/guard-state.json``), all keys optional::

        {
          "frozen_globs":   [{"glob": "infra/*.tf", "owner": "ops", "scope": "release freeze", "created_at": "...", "approvers": [], "released_at": null}],
          "blocked_globs":  [{"glob": "**/secrets/**", "owner": "ops", "released_at": null}],
          "read_only":      [{"run_id": "r1", "owner": "ops", "allow": ["skillset-saves/runs/r1/**"], "released_at": null}],
          "allow_dangerous": {"owner": "ops", "reason": "...", "scope": "...", "expires_at": "..."}
        }

    Written only by ``guard_state.py``; ``pre_tool_use.py`` denies direct writes.
    A bare glob string is still honored for backward compatibility but carries no
    owner, so a release cannot be authority-checked against it.

    With no boundary set (the common case) every list is empty, so the hook is
    inert until a guard/freeze skill explicitly records a boundary. The returned
    ``frozen_globs``/``blocked_globs`` are the *effective* glob strings; the raw
    records are exposed under ``freeze_records`` for reporting. ``root`` reads
    another project's record, and nothing here creates a directory. A grant
    (``allow_dangerous``) read from an untrusted state directory is dropped; every
    restriction is kept (``state_dir_trusted``).
    """
    state = _read_json(state_dir(root, create=False) / "guard-state.json", {})
    if not isinstance(state, dict):
        return {}
    normalized = dict(state)
    if not state_dir_trusted(root):
        normalized.pop("allow_dangerous", None)
    normalized["freeze_records"] = [e for e in (state.get("frozen_globs") or []) if isinstance(e, dict)] + \
        [e for e in (state.get("blocked_globs") or []) if isinstance(e, dict)]
    normalized["frozen_globs"] = _effective_globs(state.get("frozen_globs"))
    normalized["blocked_globs"] = _effective_globs(state.get("blocked_globs"))
    # A read-only run (recorded by `guard` via guard_state.py): records with run_id, owner, scope,
    # created_at, released_at, and the allow globs of the run's own save path.
    # Effective until released; never expired by age.
    normalized["read_only"] = [
        e for e in (state.get("read_only") or [])
        if isinstance(e, dict) and not is_released(e)
    ]
    return normalized


# --- Per-session trajectory tracking (Layer 4) -------------------------------

# A run id the reader accepts as a scope: the writer allows more, but an id that
# reaches a directory name or a message the model reads is plain and bounded.
RUN_ID = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")


def safe_text(value: object, limit: int = 120) -> str:
    """Neutralise text from a state file before it is put in front of the model.

    Control, format and bidirectional-override characters become ``?``, every run of
    whitespace one space, a backtick a quote, and the result is capped at ``limit``
    characters. Anyone who can write a state file can otherwise place text in a
    channel the model reads as harness output."""
    text = value if isinstance(value, str) else str(value)
    mapped = []
    for char in text[: limit * 4]:
        if char == "`":
            mapped.append("'")
        elif char.isspace():
            mapped.append(" ")
        elif unicodedata.category(char) in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"):
            mapped.append("?")
        else:
            mapped.append(char)
    clean = " ".join("".join(mapped).split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


def active_run_id(root: "str | Path | None" = None) -> str:
    """Best-effort run scope from the save pointer; never raises."""
    try:
        pointer = (Path(root) if root is not None else project_root()) / "skillset-saves" / "_latest.md"
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
        if RUN_ID.match(run_id):
            return run_id
    except Exception:
        pass
    return "no-run"


def process_start_token(pid: int) -> "str | None":
    """The start time of ``pid`` as the kernel counts it, where the platform exposes it cheaply.

    A recycled pid has a different start time, so the token is what keeps an
    unrelated session from inheriting a dead one's trajectory. Linux reads
    ``/proc``; other platforms return None and the identity is the pid alone."""
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text(encoding="utf-8", errors="replace")
        return stat.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError, ValueError):
        return None


def trajectory_identity(data: dict) -> tuple:
    """Return ``(identity, source)`` for the current invocation.

    Preference order: host payload ``session_id``; a session id from the
    environment; the host process identity. The process identity is the parent
    pid with its start time (``process_start_token``), and the trajectory file
    sits under the project's state directory, which keeps two unrelated host
    sessions apart even when neither supplies a session id.
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
    token = process_start_token(ppid)
    return (f"process:{ppid}:{token}" if token else f"process:{ppid}"), "process"


def _traj_path(identity: str) -> Path:
    key = hashlib.sha256(str(identity or "anonymous").encode("utf-8", "ignore")).hexdigest()[:20]
    return state_dir() / "trajectories" / active_run_id() / f"{key}.json"


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


# --- Active-run heartbeat refresh --------------------------------------------

# Refresh at most once per this many seconds so a busy session does not rewrite
# the lock on every tool call.
_HEARTBEAT_REFRESH_AFTER = 5 * 60
# Classify every saved run at most this often looking for one to refresh.
_HEARTBEAT_SCAN_EVERY = 60


def refresh_run_heartbeat(data: dict, event: str) -> dict | None:
    """Refresh the pinned run's lock heartbeat from real host activity.

    The save protocol makes a lock stale after 30 idle minutes, but a long
    stretch of tool work between two checkpoints is not idleness. Every hook
    therefore refreshes the heartbeat when all of these hold:

    * the payload carries a host ``session_id`` (synthetic invocations never
      touch save state);
    * the run the latest pointer names has no fresh heartbeat. A fresh one means
      nothing is due, and that check is two small reads, not a scan of every
      saved run;
    * the scan that does classify every run has not run in the last
      ``_HEARTBEAT_SCAN_EVERY`` seconds, because an idle project with a long
      history would otherwise pay for it on every host event;
    * ``skillset-saves`` holds exactly one coherent active or orphaned run;
    * its lock is held, pinned, not interrupted, and *not yet stale* -- a stale
      lock is reclaimed only through ``save_run.py recover --reason`` so the
      reclaim leaves audit evidence; the hook never revives one;
    * the heartbeat is older than ``_HEARTBEAT_REFRESH_AFTER``.

    The write goes through ``save_run.RunStore.heartbeat`` (the single
    sanctioned writer) as the lock's recorded owner, with ``heartbeat_source``
    set to ``hook:<event>``. A hook must never hold up the host, so it waits
    only ``save_run.HOOK_LOCK_WAIT`` for the writer lock and skips the refresh
    when another writer holds it; the writer re-checks the run under the lock.
    Never raises; returns the writer result or None.
    """
    try:
        session = str((data or {}).get("session_id") or "").strip()
        if not session:
            return None
        root = project_root()
        runs = root / "skillset-saves" / "runs"
        if not runs.is_dir():
            return None
        _bootstrap.ensure_paths()
        from _saves import _mapping, heartbeat_is_stale, inspect_saves, parse_timestamp, pointed_heartbeat  # noqa: WPS433

        now = datetime.now(timezone.utc)
        pointed = pointed_heartbeat(root)
        if pointed is not None and 0 <= (now - pointed).total_seconds() < _HEARTBEAT_REFRESH_AFTER:
            return None
        scanned = state_dir() / "observations" / "heartbeat-scan.json"
        marker = _read_json(scanned, {})
        last = marker.get("checked_at") if isinstance(marker, dict) else None
        if isinstance(last, (int, float)) and 0 <= time.time() - last < _HEARTBEAT_SCAN_EVERY:
            return None
        _write_json(scanned, {"checked_at": time.time()})
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
        beat = parse_timestamp(lock.get("heartbeat"))
        if beat is None or heartbeat_is_stale(beat, now) or (now - beat).total_seconds() < _HEARTBEAT_REFRESH_AFTER:
            return None
        import save_run  # noqa: WPS433

        store = save_run.RunStore(root, run_id)
        return store.heartbeat(str(lock.get("owner") or "admiral"), source=f"hook:{event}",
                               wait=save_run.HOOK_LOCK_WAIT, min_age=_HEARTBEAT_REFRESH_AFTER)
    except Exception:
        return None


# --- Host-observed hook firing ----------------------------------------------

def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


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
            "at": _utc_now(),
            "session_hash": hashlib.sha256(session.encode("utf-8", "ignore")).hexdigest()[:12] if session else None,
            "tool_name": str((data or {}).get("tool_name") or "") or None,
            "count": int((current.get(kind) or {}).get("count", 0)) + 1,
        }
        current[kind] = entry
        _write_json(path, current)
    except Exception:
        pass


def record_fault(event: str, error: "BaseException | type | str") -> None:
    """Count a fault a hook swallowed to fail open: by exception type, never by content.

    ``observed`` only says a hook fired; ``faults`` and ``last_fault`` (``{"type",
    "at"}``) in the same record say whether it also worked. The type name is the
    whole payload, so a message, a path or a command can never leak into state.
    Never raises, and a state directory that cannot be written loses the count,
    which is the fail-open behaviour the count reports on."""
    try:
        kind = error if isinstance(error, str) else (error if isinstance(error, type) else type(error)).__name__
        kind = re.sub(r"[^A-Za-z0-9_.]", "_", kind)[:64] or "Exception"
        path = state_dir() / "observations" / f"{event}.json"
        current = _read_json(path, {})
        if not isinstance(current, dict):
            current = {}
        prior = current.get("faults")
        current["faults"] = (prior if isinstance(prior, int) and not isinstance(prior, bool) and prior >= 0 else 0) + 1
        current["last_fault"] = {"type": kind, "at": _utc_now()}
        _write_json(path, current)
    except Exception:
        pass


def load_observations(root: "str | Path | None" = None) -> dict:
    """Return {event: {"observed": {...}|None, "simulated": {...}|None, "faults": int, "last_fault": {...}|None}}.

    Reads only: nothing is created, and ``root`` names another project."""
    result = {}
    try:
        directory = state_dir(root, create=False) / "observations"
        if directory.is_dir():
            for path in directory.glob("*.json"):
                data = _read_json(path, {})
                if isinstance(data, dict):
                    faults = data.get("faults")
                    last = data.get("last_fault")
                    result[path.stem] = {
                        "observed": data.get("observed"),
                        "simulated": data.get("simulated"),
                        "faults": faults if isinstance(faults, int) and not isinstance(faults, bool) and faults >= 0 else 0,
                        "last_fault": last if isinstance(last, dict) else None,
                    }
    except Exception:
        pass
    return result


def load_trajectory(identity: str) -> list:
    data = _read_json(_traj_path(identity), [])
    return data if isinstance(data, list) else []


def append_trajectory(identity: str, entry: dict) -> list:
    """Append one step signature and return the bounded recent history."""
    path = _traj_path(identity)
    with _fsutil.AdvisoryLock(path.parent / ".append.lock", 0.25, create_dir=True, fail_open=True):
        history = load_trajectory(identity)
        history.append(entry)
        history = history[-_MAX_TRAJ:]
        _write_json(path, history)
    _prune_old(path.parent.parent)
    return history
