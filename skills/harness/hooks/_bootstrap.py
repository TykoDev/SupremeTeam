#!/usr/bin/env python3
"""The import roots the hook scripts share, set in one place.

The hooks live in ``skills/harness/hooks`` and use the stdlib-only helpers in
``skills/scripts`` (``data_formats``, ``save_taxonomy``). A script run by path
already has its own directory first on ``sys.path``; this puts the other root
there too, so a module imports what it needs by its real name instead of through
a re-export that happens to carry the path side effect.
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
SCRIPTS = HOOKS.parents[1] / "scripts"

# Every file a registered hook runs to decide: the three entry scripts, the guard and its analysers, and the helpers
# they import (the import closure of the entry scripts; test_guard_harness_files pins it). A record of their hashes is
# what makes visible an edit that Rule F cannot see because it was made outside a session; hashing only the three entry
# scripts leaves the files that hold the rules unwatched.
HOOK_FILES = ("_bootstrap.py", "_cmdscan.py", "_fsutil.py", "_paths.py", "_saves.py", "_state.py", "audit_improve.py", "guard_hook.py",
              "post_tool_use.py", "pre_tool_use.py", "save_run.py", "size_audit.py", "user_prompt_submit.py")
SCRIPT_FILES = ("data_formats.py", "save_taxonomy.py")


def enforcement_files() -> list:
    """The absolute path of every file a registered hook runs to decide, for a record of their hashes."""
    return [HOOKS / name for name in HOOK_FILES] + [SCRIPTS / name for name in SCRIPT_FILES]


def ensure_paths() -> None:
    """Put the hooks directory and ``skills/scripts`` on ``sys.path``, once each."""
    for root in (HOOKS, SCRIPTS):
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
