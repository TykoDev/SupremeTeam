#!/usr/bin/env python3
"""Scoped, previewable repair of Supreme Team hook registration.

Readiness stays read-only. This is the explicit, owner-invoked repair step:

    python skills/harness/hooks/repair_registration.py --host claude --scope project           # dry run: prints the diff
    python skills/harness/hooks/repair_registration.py --host claude --scope project --apply   # writes, keeps a backup

Behaviour:
  * touches exactly one config file (chosen by --host/--scope), never the
    global file unless --scope user is requested explicitly;
  * adds only the hook entries that verify_registration's analyser reports as
    not executable, preserving every unrelated key, matcher, and hook;
  * refuses to write when the existing file is not valid JSON (a blind rewrite
    would drop someone else's configuration);
  * writes atomically (temp file + replace) after copying the previous file
    to ``<file>.bak-<timestamp>``;
  * is idempotent: a second run reports "no changes".

Exit 0 = nothing to do or applied, 1 = changes needed but --apply not given,
2 = refused/engine error.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_registration as verify  # noqa: E402

HOOK_DIR = Path(__file__).resolve().parent
MATCHERS = {
    "pre_tool_use.py": "Bash|PowerShell|Edit|Write|NotebookEdit",
    "post_tool_use.py": "Bash|PowerShell",
    "user_prompt_submit.py": None,
}

# Codex realizes file edits through its own patch tool, which the portable matcher
# above does not name. Keeping the extension here means this module and
# scripts/install_hooks.py always write the same matcher for the same host, so a
# repair after an install cannot silently narrow the registered scope.
HOST_EXTRA_TOOLS = {
    "codex": {"pre_tool_use.py": ("apply_patch",), "post_tool_use.py": ("apply_patch",)},
}

# Shown by hosts that surface a hook status line while the hook runs.
STATUS_MESSAGES = {
    "pre_tool_use.py": "SupremeTeam: checking pending tool use",
    "post_tool_use.py": "SupremeTeam: checking trajectory",
    "user_prompt_submit.py": "SupremeTeam: checking entry routing",
}


def matcher_for(script: str, host: str) -> str | None:
    """Return the tool matcher for one hook on one host, or None for an unmatched event."""
    base = MATCHERS.get(script)
    if base is None:
        return None
    tools = base.split("|")
    for tool in HOST_EXTRA_TOOLS.get(host, {}).get(script, ()):
        if tool not in tools:
            tools.append(tool)
    return "|".join(tools)


def target_path(host: str, scope: str) -> Path:
    home = Path.home()
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("SUPREMETEAM_PROJECT_DIR") or Path.cwd())
    table = {
        ("claude", "user"): home / ".claude/settings.json",
        ("claude", "project"): project / ".claude/settings.json",
        ("claude", "local"): project / ".claude/settings.local.json",
        ("codex", "user"): home / ".codex/hooks.json",
        ("codex", "project"): project / ".codex/hooks.json",
        ("copilot", "user"): home / ".config/github-copilot/hooks.json",
        ("copilot", "project"): project / ".github/hooks.json",
    }
    if (host, scope) not in table:
        raise ValueError(f"scope {scope!r} is not defined for host {host!r}")
    return table[(host, scope)]


def launcher_token(python: str) -> str:
    """Quote an interpreter whose path contains spaces.

    A launcher that carries its own arguments (``py -3.13``, ``python -X utf8``) is
    left alone: quoting it would collapse two tokens into one path that does not
    exist. An unquoted ``C:/Program Files/Python313/python.exe`` would otherwise be
    split into a launcher and a stray argument, and verify_registration would report
    the hook as not executable.

    The test is the shape of the value, not whether the file exists here, so
    registering an interpreter for another machine behaves the same way.
    """
    if not python or '"' in python or " " not in python:
        return python
    if any(part.startswith("-") for part in python.split(" ")[1:]):
        return python
    return '"' + python + '"'


def command_for(script: str, python: str) -> str:
    return f'{launcher_token(python)} "{HOOK_DIR / script}"'


def plan(config: dict, host: str, python: str) -> tuple[dict, list[str]]:
    desired = dict(config)
    hooks = desired.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("existing 'hooks' key is not an object; refusing to rewrite it")
    required = list(verify.REQUIRED)
    added: list[str] = []
    for key, script in required:
        event = verify.EVENTS[host][key]
        existing = verify._commands([config], event)
        if any(verify.analyse(command, script)["executable"] for command in existing):
            continue
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"existing hooks.{event} is not a list; refusing to rewrite it")
        handler = {"type": "command", "command": command_for(script, python)}
        status = STATUS_MESSAGES.get(script)
        if status:
            handler["statusMessage"] = status
        entry = {"hooks": [handler]}
        matcher = matcher_for(script, host)
        if matcher:
            entry = {"matcher": matcher, **entry}
        groups.append(entry)
        added.append(f"{event} -> {script}")
    return desired, added


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or apply a scoped Supreme Team hook registration repair.")
    parser.add_argument("--host", choices=["claude", "codex", "copilot"], required=True)
    parser.add_argument("--scope", choices=["user", "project", "local"], default="project")
    parser.add_argument("--python", default="python", help="interpreter launcher to register (e.g. 'py -3.13')")
    parser.add_argument("--apply", action="store_true", help="write the change (default is a dry run)")
    args = parser.parse_args()
    try:
        path = target_path(args.host, args.scope)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    before_text = ""
    config: dict = {}
    if path.exists():
        before_text = path.read_text(encoding="utf-8")
        try:
            config = json.loads(before_text) if before_text.strip() else {}
        except ValueError as exc:
            print(json.dumps({"ok": False, "path": str(path), "error": f"existing file is not valid JSON ({exc}); refusing to overwrite"}))
            return 2
        if not isinstance(config, dict):
            print(json.dumps({"ok": False, "path": str(path), "error": "existing config root is not an object"}))
            return 2
    try:
        desired, added = plan(json.loads(json.dumps(config)), args.host, args.python)
    except ValueError as exc:
        print(json.dumps({"ok": False, "path": str(path), "error": str(exc)}))
        return 2
    after_text = json.dumps(desired, indent=2) + "\n"
    if not added:
        print(json.dumps({"ok": True, "path": str(path), "changes": [], "applied": False, "note": "no changes: every required hook is already registered and executable"}))
        return 0
    diff = "".join(difflib.unified_diff(before_text.splitlines(True), after_text.splitlines(True), fromfile=str(path), tofile=str(path) + " (proposed)"))
    if not args.apply:
        print(diff)
        print(json.dumps({"ok": True, "path": str(path), "changes": added, "applied": False, "note": "dry run; re-run with --apply to write"}))
        return 1
    backup = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            backup = path.with_name(path.name + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            shutil.copyfile(path, backup)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(after_text, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        print(json.dumps({"ok": False, "path": str(path), "error": f"write failed: {exc}", "backup": str(backup) if backup else None}))
        return 2
    print(json.dumps({"ok": True, "path": str(path), "changes": added, "applied": True, "backup": str(backup) if backup else None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
