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

Behavior, checked in this order (the first match decides):
  - Empty prompt                 -> stay silent.
  - /audit-improve as first word -> run the read-only harness audit through
                                     ``audit_improve.maybe_audit(force=True)``, which
                                     skips the cooldown and writes no marker, and
                                     inject its summary, active run or not; a fault
                                     there is counted and the hook stays silent.
  - Any other slash command      -> stay silent (deterministic host routing; the
                                     target skill's own Entry Routing check applies).
  - Active run detected          -> reinforce the session pin (route to the run).
  - Otherwise                    -> inject the "route through admiral" reminder.

Output contract: prints the UserPromptSubmit additionalContext envelope to stdout
and exits 0. On any error it exits 0 silently (fail open) and counts the fault by type
in the hook's observation record (`_state.record_fault`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _missing_module(event: str, exc: BaseException) -> None:
    """A module this hook imports is not there. A registered hook fails open: exit 0 and no reminder, with the fault
    counted when ``_state`` still loads and said on stderr when it does not. ``--selftest`` and an import of this file
    by another program are not host events, so they get the error itself."""
    if __name__ != "__main__" or "--selftest" in sys.argv[1:]:
        return
    try:
        import _state as state

        state.record_fault(event, exc)
    except BaseException:
        try:
            sys.stderr.write("supremeteam %s hook: a module it imports is missing (%s) and the fault could not be "
                             "recorded; the hook did nothing. Reinstall the catalog and run "
                             "skills/harness/hooks/check_readiness.py.\n" % (event, exc))
        except Exception:
            pass
    sys.exit(0)


try:
    import _state
    import run_heartbeat
except ImportError as _exc:  # a catalog file this hook imports is missing
    _missing_module("UserPromptSubmit", _exc)
    raise

_ROUTE_REMINDER = (
    "Supreme Team entry routing: no active run detected. `admiral` is the "
    "primary entry orchestrator and front door for the delivery lifecycle. First "
    "assess the Tier 0 fast path in skills/routing-doctrine.md: minor, understood, "
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


def _emit(context: str, event: str = "UserPromptSubmit") -> None:
    """Print the context in the shape the host reads (``_state.context_output``: the command line's ``--host``)."""
    print(json.dumps(_state.context_output(event, context)))
    sys.exit(0)


def _session_start(data: dict) -> bool:
    """Whether the host ran this hook for the start of a session and not for a prompt.

    GitHub Copilot drops what a command hook prints for a prompt, so the registrar puts this hook on its
    ``SessionStart`` event, whose context it does read: the reminder is given once per session there, not once per
    prompt. The payload names the event; it carries no prompt to route."""
    return str(data.get("hook_event_name") or data.get("hookEventName") or "").strip().lower() == "sessionstart"


def _saves_root() -> Path:
    return _state.state_root() / "skillset-saves"


def _active_run() -> bool:
    """Whether a run holds the session pin, as `_saves.has_active_run` answers it: a run whose lock is fresh, whatever
    the pointer says, or a record this account cannot read, which may be one. A fault answers no, and is counted."""
    try:
        import _bootstrap

        _bootstrap.ensure_paths()
        from _saves import has_active_run

        return has_active_run(_saves_root().parent)
    except Exception as exc:
        _state.record_fault("UserPromptSubmit", exc)
        return False


def main() -> None:
    data = _state.read_hook_input("UserPromptSubmit")
    _state.record_observation("UserPromptSubmit", data)
    run_heartbeat.refresh(data, "UserPromptSubmit")
    prompt = str(data.get("prompt", "") or "")

    if _session_start(data):
        # No prompt to read and no second chance: say which of the two states the session starts in.
        _emit(_ACTIVE_REMINDER if _active_run() else _ROUTE_REMINDER, "SessionStart")

    # Empty prompt: nothing to route.
    if not prompt.strip():
        return

    if prompt.strip().split(maxsplit=1)[0] == "/audit-improve":
        try:
            import audit_improve

            report = audit_improve.maybe_audit(force=True)
            _emit(audit_improve.advisory_for(report))
        except Exception as exc:
            _state.record_fault("UserPromptSubmit", exc)
            return

    # Explicit slash command: deterministic host routing. Stay silent and let the
    # target skill's own Entry Routing check (routing-doctrine.md sec 3) apply.
    if prompt.lstrip().startswith("/"):
        return

    if _active_run():
        _emit(_ACTIVE_REMINDER)
    else:
        _emit(_ROUTE_REMINDER)


def run() -> None:
    """The registered entry: a fault never blocks the host loop (exit 0, no output); it is counted by type."""
    try:
        main()
    except Exception as exc:
        _state.record_fault("UserPromptSubmit", exc)


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        # Not a host event: prove the registered command starts and every module a hook runs imports, and fail
        # loud when one does not (verify_registration.probe reads the exit status and the "ok"). The argument is
        # looked for anywhere on the line: a command registered with `--host <name>` is probed with it in place.
        import _bootstrap

        _bootstrap.selftest()
        sys.exit(0)
    run()
    sys.exit(0)
