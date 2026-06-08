#!/usr/bin/env python3
"""
Harness hook registration verifier for SupremeTeam.

Confirms that the three SupremeTeam harness hooks are registered in a host
`settings.json`, and — when any are missing — emits a ready-to-paste
registration block plus a `REGISTER_PROMPT` marker so the calling orchestrator
(admiral) can surface a prompt to the user.

Unlike the runtime hooks, this is a diagnostic run by `admiral` at startup
(see ../../routing-doctrine.md and the admiral Harness Hook Registration check),
not a `PreToolUse`/`UserPromptSubmit` interceptor. A SessionStart hook cannot
verify registration reliably — if hooks are not registered, the SessionStart
hook would not run either — so the check is an explicit intake step instead.

Exit codes:
  0  all three hooks are registered
  1  one or more hooks are missing (a registration prompt was printed)
  2  could not read any settings file (status unknown)

Stdlib only; runs on any host Python 3.8+.
"""

import json
import os
import sys
from pathlib import Path

# (hook event, unique script basename that must appear in a registered command).
REQUIRED = [
    ("PreToolUse", "pre_tool_use.py"),
    ("PostToolUse", "post_tool_use.py"),
    ("UserPromptSubmit", "user_prompt_submit.py"),
]

REGISTRATION_BLOCK = r"""{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|Edit|Write|NotebookEdit",
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/SupremeTeam/harness/hooks/pre_tool_use.py\"" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/SupremeTeam/harness/hooks/post_tool_use.py\"" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/SupremeTeam/harness/hooks/user_prompt_submit.py\"" }
        ]
      }
    ]
  }
}"""


def _settings_paths() -> list:
    """Candidate settings files, in load order (user -> project -> local)."""
    paths = []
    home = Path.home()
    paths.append(home / ".claude" / "settings.json")
    base = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    paths.append(base / ".claude" / "settings.json")
    paths.append(base / ".claude" / "settings.local.json")
    return paths


def _load(path: Path):
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _registered_commands(settings_objs: list, event: str) -> list:
    cmds = []
    for obj in settings_objs:
        if not isinstance(obj, dict):
            continue
        groups = (obj.get("hooks") or {}).get(event) or []
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hook in group.get("hooks") or []:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    cmds.append(hook["command"])
    return cmds


def main() -> int:
    paths = _settings_paths()
    loaded = [(p, _load(p)) for p in paths]
    present_objs = [obj for _, obj in loaded if obj is not None]

    print("SupremeTeam harness hook registration check")
    print("Settings files inspected:")
    for p, obj in loaded:
        state = "read" if obj is not None else ("absent" if not p.exists() else "unreadable")
        print(f"  - {p}  [{state}]")

    if not present_objs:
        print("\nstatus: UNKNOWN — no settings.json could be read.")
        print("Cannot confirm hook registration. Treat as unregistered and prompt the user.")
        return 2

    missing = []
    print("")
    for event, script in REQUIRED:
        cmds = _registered_commands(present_objs, event)
        hit = any(script in c for c in cmds)
        print(f"  [{'OK ' if hit else 'MISSING'}] {event} -> {script}")
        if not hit:
            missing.append((event, script))

    if not missing:
        print("\nstatus: REGISTERED - all three SupremeTeam hooks are present.")
        return 0

    names = ", ".join(f"{e}/{s}" for e, s in missing)
    print(f"\nstatus: MISSING - {len(missing)} hook(s) not registered: {names}")
    print("REGISTER_PROMPT: SupremeTeam harness hooks are not fully registered.")
    print("Action: ask the user to register them (the `update-config` skill owns")
    print("settings.json). Suggested project `.claude/settings.json` block:\n")
    print(REGISTRATION_BLOCK)
    print("\nOn Windows replace `python` with `py -3` if needed. After writing a NEW")
    print("settings file, the user must open `/hooks` once (or restart) so Claude Code")
    print("loads it — the settings watcher only tracks files that existed at startup.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never hard-crash a startup check
        print(f"verify_registration: error ({exc}); status UNKNOWN")
        sys.exit(2)
