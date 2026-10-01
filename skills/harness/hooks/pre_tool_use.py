#!/usr/bin/env python3
"""Registered PreToolUse entry point for the Supreme Team guard.

`guard_hook.py` enforces the boundary in `.harness-state/guard-state.json`;
`guard_state.py` is its sole sanctioned writer. This entry point preserves
existing host registrations while the guard has a dedicated executable script.

It is the one file the host runs that must work on any Python, so it checks the
interpreter before it imports anything that needs the supported floor: on an older
Python the guard cannot run, and the hook says so on stderr and lets the action
proceed (fail open) instead of dying with an import traceback.
"""

import sys

MINIMUM = (3, 13)


def run() -> None:
    """Run the guard. Every fault, and an interpreter below the floor, fail open."""
    try:
        if sys.version_info < MINIMUM:
            sys.stderr.write(
                "supremeteam guard hook: Python %d.%d or newer is required and this is Python %d.%d, "
                "so the guard is NOT enforcing anything. Register the hook with a newer interpreter "
                "(python skills/harness/hooks/repair_registration.py).\n"
                % (MINIMUM[0], MINIMUM[1], sys.version_info[0], sys.version_info[1])
            )
            return
        from guard_hook import main

        main()
    except Exception as exc:
        # A harness fault must not block the host loop, but it is counted so readiness can say so.
        try:
            import _state

            _state.record_fault("PreToolUse", exc)
        except Exception:
            pass


if __name__ == "__main__":
    run()
    sys.exit(0)
