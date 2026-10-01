#!/usr/bin/env python3
"""Registered PreToolUse entry point for the Supreme Team guard.

`guard_hook.py` enforces the boundary in `.harness-state/guard-state.json`;
`guard_state.py` is its sole sanctioned writer. This entry point preserves
existing host registrations while the guard has a dedicated executable script.

It is the one file the host runs that must work on any Python, so it parses on any
Python 3 and never decides for the guard whether an interpreter is good enough: it
tries the guard. The guard runs on interpreters below the supported floor wherever
nothing it uses is missing, and a protection must not switch off because of a version
number. Only a real failure to import or run the guard (a syntax error, an import
error, any fault) fails open, and then it is not silent: the fault is counted for
readiness and, below the floor, the interpreter and the floor are named on stderr.
"""

import sys

MINIMUM = (3, 13)


def _fail_open(exc: BaseException) -> None:
    """Let the action proceed after a fault, counted for readiness and, below the floor, explained."""
    if sys.version_info < MINIMUM:
        try:
            sys.stderr.write(
                "supremeteam guard hook: the guard could not run on Python %d.%d (%s); Python %d.%d or newer is "
                "supported, so the guard is NOT enforcing this call. Register the hook with a newer interpreter "
                "(python skills/harness/hooks/repair_registration.py).\n"
                % (sys.version_info[0], sys.version_info[1], type(exc).__name__, MINIMUM[0], MINIMUM[1])
            )
        except Exception:
            pass
    try:
        import _state

        _state.record_fault("PreToolUse", exc)
    except Exception:
        pass


def run() -> None:
    """Run the guard. A fault fails open, counted; a deny is the guard's own exit and is never caught here."""
    try:
        from guard_hook import main

        main()
    except Exception as exc:
        # A harness fault must not block the host loop, but it is counted so readiness can say so.
        _fail_open(exc)


if __name__ == "__main__":
    run()
    sys.exit(0)
