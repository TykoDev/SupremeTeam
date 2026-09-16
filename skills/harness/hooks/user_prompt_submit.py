#!/usr/bin/env python3
"""
Entry-Routing hook for Supreme Team.

Runs as a host ``UserPromptSubmit``/prompt-submit hook. On every fresh user turn it
injects a short routing reminder steering delivery-lifecycle work to ``admiral``,
the primary entry orchestrator (see ../../routing-doctrine.md). This is the only
deterministic place the catalog can reinforce entry routing, because skills are
instructions inside the host loop and do not own it (../../harness-doctrine.md).

Posture (harness-doctrine.md):
  - Principles: stdlib only, fail open. Any internal error exits 0 with no output,
    so the prompt proceeds unmodified -- a harness fault never blocks the host.
  - advisory, not coercive. The hook injects context; it never blocks the prompt.

Behavior:
  - Active run detected          -> reinforce the session pin (route to the run).
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
from _saves import has_active_run

_ROUTE_REMINDER = (
    "Supreme Team entry routing: no active run detected. `admiral` is the "
    "primary entry orchestrator and front door for the delivery lifecycle. First "
    "assess the Tier 0 fast path in routing-doctrine.md: minor, understood, "
    "reversible tasks run directly with focused verification, without a pipeline "
    "or full security audit. Security-sensitive work is excluded. Route other "
    "delivery-lifecycle requests -- design, redesign of an existing UI, build, "
    "review, security audit, investigation, product QA, explicit Taste preference "
    "management, release, checkpoint/resume, and skill/team creation -- through "
    "`admiral` first so one intake, save-protocol run, and gatekeeper govern the "
    "pipeline. Standalone tools (safety guardrails, browser automation, and an "
    "explicitly requested qa or ship tool) may run directly. See routing-doctrine.md."
)

_ACTIVE_REMINDER = (
    "Supreme Team entry routing: a run is active (session pin held). Treat "
    "this input as session input to the active run and route it to the active "
    "sub-orchestrator per admiral's Session Routing contract; do not fork a "
    "parallel skill that bypasses the run."
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
    return _state.project_root() / "skillset-saves"


def _active_run() -> bool:
    """Return true only for a coherent, fresh canonical saved run."""
    try:
        return has_active_run(_saves_root().parent)
    except Exception:
        return False


def main() -> None:
    data = _state.read_hook_input()
    _state.record_observation("UserPromptSubmit", data)
    _state.refresh_run_heartbeat(data, "UserPromptSubmit")
    prompt = str(data.get("prompt", "") or "")

    # Empty prompt: nothing to route.
    if not prompt.strip():
        return

    # Explicit slash command: deterministic host routing. Stay silent and let the
    # target skill's own Entry Routing check (routing-doctrine.md sec 3) apply.
    if prompt.lstrip().startswith("/"):
        return

    if _active_run():
        _emit(_ACTIVE_REMINDER)
    else:
        _emit(_ROUTE_REMINDER)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail open: never let a harness fault block the host loop.
        sys.exit(0)
