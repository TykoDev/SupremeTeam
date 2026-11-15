#!/usr/bin/env python3
"""Status-line sidecar: write down how full the context window is, for the hooks to read.

A host's tool and prompt hooks are told nothing about context usage. Claude Code tells its status line: the JSON a
status-line command reads on standard input carries ``context_window.used_percentage`` and
``context_window.context_window_size``. Registered as the status line, this script writes the two figures to
``.harness-state/context-usage/<session>.usage.json`` and prints a short status; ``context_watch.py`` reads the file and
advises a run in flight when a threshold is crossed.

    "statusLine": {"type": "command", "command": "<python> -X utf8 \"<hooks>/context_statusline.py\""}

A settings file holds one status line. To keep one that is already configured, give its command after ``--``: the
same input is passed to it and its output is what is printed.

    <python> -X utf8 "<hooks>/context_statusline.py" -- sh ~/.claude/statusline.sh

The command after ``--`` is started directly, without a shell: wrap one that needs a shell (a pipe, a variable) as
``-- sh -c '<command>'``.

The sidecar is written only in a project that has saved runs, and at most every few seconds unless the figure moved.
Nothing here decides anything, and a fault prints nothing and exits 0: a status line that failed would only be an
empty row. The field names are the ones Claude Code documents; they have not been seen in a live session, because a
status line runs only in an interactive one.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

# Rewrite an unchanged figure at most this often; a status line runs on every update of the conversation.
REWRITE_AFTER = 5
WRAPPED_TIMEOUT = 10


def figures(data: dict) -> "tuple":
    """``(used percentage, window size, model id)`` from a status-line payload; each None when it is not there."""
    window = data.get("context_window") if isinstance(data.get("context_window"), dict) else {}
    used, size = window.get("used_percentage"), window.get("context_window_size")
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    return (float(used) if isinstance(used, (int, float)) and not isinstance(used, bool) else None,
            int(size) if isinstance(size, int) and not isinstance(size, bool) and size > 0 else None,
            str(model.get("id") or "") or None)


def record(data: dict) -> None:
    """Write the sidecar for this session, when there is a figure and the project has saved runs."""
    used, size, model = figures(data)
    if used is None:
        return
    workspace = data.get("workspace") if isinstance(data.get("workspace"), dict) else {}
    project = workspace.get("project_dir") or data.get("cwd")
    import _state

    if isinstance(project, str) and project and not any(os.environ.get(name) for name in _state.PROJECT_ENV):
        os.environ[_state.PROJECT_ENV[0]] = project
    if not (_state.state_root() / "skillset-saves" / "runs").is_dir():
        return
    import context_watch

    path = context_watch.session_file(data, "usage", create=True)
    old = _state.read_json(path, {})
    now = time.time()
    if isinstance(old, dict) and isinstance(old.get("at"), (int, float)) and 0 <= now - old["at"] < REWRITE_AFTER \
            and round(old.get("used_percentage") or -1) == round(used):
        return
    _state.write_json(path, {"used_percentage": used, "window": size, "model": model, "at": now})


def main(argv: list, raw: bytes) -> str:
    """Record the figures and return the text to print."""
    try:
        data = json.loads(raw.decode("utf-8", "replace").lstrip("﻿") or "{}")
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    try:
        record(data)
    except Exception:
        pass  # the sidecar is a convenience; the status line still prints
    if "--" in argv:
        command = argv[argv.index("--") + 1:]
        if command:
            try:
                done = subprocess.run(command, input=raw, capture_output=True, timeout=WRAPPED_TIMEOUT, check=False)
                return done.stdout.decode("utf-8", "replace")
            except (OSError, subprocess.SubprocessError):
                return ""
    used = figures(data)[0]
    return f"ctx {round(used)}%\n" if used is not None else "ctx --\n"


if __name__ == "__main__":
    try:
        stream = getattr(sys.stdin, "buffer", None)
        text = main(sys.argv[1:], stream.read() if stream is not None else sys.stdin.read().encode("utf-8"))
        out = getattr(sys.stdout, "buffer", None)
        if out is not None:
            out.write(text.encode("utf-8"))
        else:
            sys.stdout.write(text)
    except Exception:
        pass
    sys.exit(0)
