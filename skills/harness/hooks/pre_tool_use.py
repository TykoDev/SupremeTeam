#!/usr/bin/env python3
"""Registered PreToolUse entry point for the Supreme Team guard.

`guard_hook.py` enforces the boundary in `.harness-state/guard-state.json`;
`guard_state.py` is its sole sanctioned writer. This entry point preserves
existing host registrations while the guard has a dedicated executable script.
"""

import sys

from guard_hook import main


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A harness fault must not block the host loop.
        sys.exit(0)
