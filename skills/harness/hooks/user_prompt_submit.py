#!/usr/bin/env python3
"""
Entry-Routing hook for SupremeTeam.

Runs as a Claude Code ``UserPromptSubmit`` hook. On every fresh user turn it
injects a short routing reminder steering delivery-lifecycle work to ``admiral``,
the primary entry orchestrator (see ../../routing-doctrine.md). This is the only
deterministic place the catalog can reinforce entry routing, because skills are
instructions inside the host loop and do not own it (../../harness-doctrine.md).

Posture (harness-doctrine.md):
  - section 3: stdlib only, fail open. Any internal error exits 0 with no output,
    so the prompt proceeds unmodified -- a harness fault never blocks the host.
  - advisory, not coercive. The hook injects context; it never blocks the prompt.

Behavior:
  - Active Admiral run detected  -> reinforce the session pin (route to the run).
  - Explicit slash command       -> stay silent (deterministic host routing; the
                                     target skill's own Entry Routing check applies).
  - Otherwise                    -> inject the "route through admiral" reminder.

Output contract: prints the UserPromptSubmit additionalContext envelope to stdout
and exits 0. On any error it exits 0 silently (fail open).
"""

import os
import sys
from pathlib import Path

import _state

_ROUTE_REMINDER = (
    "SupremeTeam entry routing: no active Admiral run detected. `admiral` is the "
    "primary entry orchestrator and front door for the delivery lifecycle. Route "
    "delivery-lifecycle requests -- design, build, review, ship, root-cause "
    "investigation, checkpoint/resume, gate validation, and skill/team creation -- "
    "through `admiral` first so one intake, save-protocol run, and gatekeeper govern "
    "the pipeline. Standalone utility tools (safety-guardrails, browser-automation, "
    "release-and-deployment, testing-and-qa, update-config) may run directly. "
    "See routing-doctrine.md."
)

_ACTIVE_REMINDER = (
    "SupremeTeam entry routing: an Admiral run is active (session pin held). Treat "
    "this input as Admiral session input and route it to the active sub-orchestrator "
    "per Admiral's Session Routing contract; do not fork a parallel skill that "
    "bypasses the run."
)


def _emit(context: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    print(__import__("json").dumps(out))
    sys.exit(0)


def _saves_root() -> Path:
    base = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return Path(base) / "skillset-saves"


def _state_text_is_active(text: str) -> bool:
    """True when a ``_state.md`` body shows a pinned, non-terminal run.

    A run is active when it holds the session pin and has not reached a terminal
    state (DELIVERED / RUN_COMPLETE). DISPUTED_AWAITING_USER is *not* terminal --
    the run still owns the session.
    """
    low = text.lower()
    pinned = "session_pin: true" in low or "session_pin:true" in low
    if not pinned:
        return False
    return not ("delivered" in low or "run_complete" in low)


def _latest_run_id(root: Path) -> str:
    """Parse ``latest_run_id`` from ``skillset-saves/_latest.md`` (the pointer).

    Returns "" when the pointer is absent or unparseable. Per save-protocol.md
    section 2 this file holds only ``latest_run_id`` / ``updated_at`` -- it carries
    no ``session_pin``, so it can only be used to *locate* the real state file.
    """
    try:
        text = (root / "_latest.md").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("latest_run_id:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def _active_admiral_run() -> bool:
    """Best-effort detection of an active Admiral run.

    Per save-protocol.md sections 1-2 the mutable run state lives at
    ``skillset-saves/runs/{run-id}/_state.md`` -- the only file that carries
    ``session_pin`` -- while root ``_latest.md`` is just a pointer
    (``latest_run_id``). Detection therefore:

    1. dereferences the ``_latest.md`` pointer to the nested ``_state.md``, then
    2. falls back to scanning ``runs/*/_state.md`` when the pointer is missing or
       stale (an orphaned-but-resumable run), then
    3. keeps a legacy check for a flat root ``_state.md`` for defensiveness.

    Fail-open: any error or ambiguity returns False, so the default is to nudge
    toward ``admiral`` (the intended "always route through admiral" behavior).
    """
    try:
        root = _saves_root()
        if not root.exists():
            return False

        # 1. Primary: follow the _latest.md pointer to the nested state file.
        run_id = _latest_run_id(root)
        if run_id:
            p = root / "runs" / run_id / "_state.md"
            if p.exists() and _state_text_is_active(
                p.read_text(encoding="utf-8", errors="ignore")
            ):
                return True

        # 2. Fallback: pointer missing/stale -- scan for any active pinned run so
        #    an orphaned run (lost _latest.md) is still recovered.
        runs_dir = root / "runs"
        if runs_dir.is_dir():
            for state_file in runs_dir.glob("*/_state.md"):
                try:
                    if _state_text_is_active(
                        state_file.read_text(encoding="utf-8", errors="ignore")
                    ):
                        return True
                except Exception:
                    continue

        # 3. Legacy/defensive: a flat root _state.md (not the documented layout).
        flat = root / "_state.md"
        if flat.exists() and _state_text_is_active(
            flat.read_text(encoding="utf-8", errors="ignore")
        ):
            return True

        return False
    except Exception:
        return False


def main() -> None:
    data = _state.read_hook_input()
    prompt = str(data.get("prompt", "") or "")

    # Empty prompt: nothing to route.
    if not prompt.strip():
        return

    # Explicit slash command: deterministic host routing. Stay silent and let the
    # target skill's own Entry Routing check (routing-doctrine.md sec 3) apply.
    if prompt.lstrip().startswith("/"):
        return

    if _active_admiral_run():
        _emit(_ACTIVE_REMINDER)
    else:
        _emit(_ROUTE_REMINDER)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail open: never let a harness fault block the host loop.
        sys.exit(0)
