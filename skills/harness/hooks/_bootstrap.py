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


def ensure_paths() -> None:
    """Put the hooks directory and ``skills/scripts`` on ``sys.path``, once each."""
    for root in (HOOKS, SCRIPTS):
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
