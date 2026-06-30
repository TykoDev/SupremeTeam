#!/usr/bin/env python3
"""
Shared state helper for the SupremeTeam runtime-harness hooks.

Implements the Action Realization (Layer 3) and Trajectory Regulation (Layer 4)
storage used by ``pre_tool_use.py`` and ``post_tool_use.py``. Stdlib only — no
third-party dependencies. The supported SupremeTeam install baseline is Python
3.13+ so readiness checks, hook registration, and hook execution all share one
interpreter requirement.

Design posture (see ../../harness-doctrine.md, section 3): every function here
FAILS OPEN. Any I/O or parse error returns a safe empty/default value and never
raises into the hook, so a harness fault can never block the host loop.
"""

import json
import os
import tempfile
from pathlib import Path

# Maximum trajectory signatures retained per session (bounded memory).
_MAX_TRAJ = 40


def state_dir() -> Path:
    """Return the harness state directory, creating it if possible.

    Prefers ``$SUPREMETEAM_PROJECT_DIR/.harness-state`` so guard/freeze records
    and trajectory state live with the project; falls back through known host
    project-directory variables and then the current working directory.
    """
    base = (
        os.environ.get("SUPREMETEAM_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CODEX_WORKSPACE_DIR")
        or os.environ.get("CURSOR_WORKSPACE_DIR")
        or os.environ.get("OPENCODE_WORKSPACE_DIR")
        or os.getcwd()
    )
    try:
        d = Path(base) / ".harness-state"
        d.mkdir(parents=True, exist_ok=True)
        return d
    except Exception:
        d = Path(tempfile.gettempdir()) / "supremeteam-harness-state"
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
        path.write_text(json.dumps(obj), encoding="utf-8")
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

def load_guard_state() -> dict:
    """Load the active guard/freeze boundary.

    Schema (``.harness-state/guard-state.json``), all keys optional::

        {
          "frozen_globs":   ["src/payments/**", "infra/*.tf"],
          "blocked_globs":  ["**/secrets/**"],
          "allow_dangerous": false
        }

    Returns an empty dict when no boundary is set (the common case), so the hook
    is inert until a guard/freeze skill explicitly records a boundary.
    """
    state = _read_json(state_dir() / "guard-state.json", {})
    return state if isinstance(state, dict) else {}


# --- Per-session trajectory tracking (Layer 4) -------------------------------

def _traj_path(session_id: str) -> Path:
    safe = "".join(c for c in (session_id or "default") if c.isalnum() or c in "-_")
    return state_dir() / f"traj-{safe or 'default'}.json"


def load_trajectory(session_id: str) -> list:
    data = _read_json(_traj_path(session_id), [])
    return data if isinstance(data, list) else []


def append_trajectory(session_id: str, entry: dict) -> list:
    """Append one step signature and return the bounded recent history."""
    history = load_trajectory(session_id)
    history.append(entry)
    history = history[-_MAX_TRAJ:]
    _write_json(_traj_path(session_id), history)
    return history
