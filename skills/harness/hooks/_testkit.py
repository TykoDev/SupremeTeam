#!/usr/bin/env python3
"""Shared scaffolding for the guard test modules.

``decide`` runs ``guard_hook.main`` in this process with a payload on stdin, so a
table of several hundred adversarial commands costs milliseconds instead of a
Python start-up each; ``run_hook`` runs the registered entry point as a real
subprocess for the cases that must prove the wiring (exit code, stdout, stderr).
Both read the project from ``CLAUDE_PROJECT_DIR`` exactly as a host does, and
both work on the code before and after a change, which is how a regression test
here proves it fails on the old guard.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))

_PROJECT_VARS = ("SUPREMETEAM_PROJECT_DIR", "CLAUDE_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE")
_SESSION_VARS = ("SUPREMETEAM_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "COPILOT_SESSION_ID", "GITHUB_RUN_ID")


@contextlib.contextmanager
def project():
    """A scratch project directory with no markers; yields its resolved path."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp).resolve()


def write_guard(root: Path, state: dict) -> None:
    directory = root / ".harness-state"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "guard-state.json").write_text(json.dumps(state), encoding="utf-8")


def clean_env(root: Path, **extra: str) -> dict:
    env = os.environ.copy()
    for name in (*_PROJECT_VARS, *_SESSION_VARS):
        env.pop(name, None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env.update(extra)
    return env


def encode(payload) -> bytes:
    if isinstance(payload, bytes):
        return payload
    return (payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8")


def run_hook(script: str, payload, root: Path, **env_extra: str) -> subprocess.CompletedProcess:
    """Run a registered hook script as a subprocess; ``payload`` may be bytes to send undecodable input."""
    return subprocess.run([sys.executable, str(HOOK_DIR / script)], input=encode(payload), capture_output=True,
                          env=clean_env(root, **env_extra), check=False)


def decide(payload, root: Path, module: str = "guard_hook") -> str:
    """The stdout of ``<module>.main()`` for ``payload``, run in this process ('' when it stays silent)."""
    import importlib

    entry = importlib.import_module(module)
    saved_env = {name: os.environ.get(name) for name in (*_PROJECT_VARS, *_SESSION_VARS)}
    for name in (*_PROJECT_VARS, *_SESSION_VARS):
        os.environ.pop(name, None)
    os.environ["CLAUDE_PROJECT_DIR"] = str(root)
    stdin = io.TextIOWrapper(io.BytesIO(encode(payload)), encoding="utf-8")
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            real_stdin, sys.stdin = sys.stdin, stdin
            try:
                entry.main()
            except SystemExit:
                pass
            finally:
                sys.stdin = real_stdin
    finally:
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return out.getvalue()


def denied(output: str) -> bool:
    return '"permissionDecision": "deny"' in output


def reason(output: str) -> str:
    return json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"] if output.strip() else ""


def bash(command: str, tool: str = "Bash") -> dict:
    return {"tool_name": tool, "tool_input": {"command": command}}


def edit(path: str, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path, "content": "x"}}
