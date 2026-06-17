#!/usr/bin/env python3
"""
Harness hook registration verifier for SupremeTeam.

Checks host-native hook configuration for the current host (or a requested host)
and confirms that it points at SupremeTeam's harness hook scripts, not merely at
same-named files from another package.

Exit codes:
  0  required hooks are registered for the selected host
  1  host config was readable but one or more hooks are missing/mismatched
  2  host could not be inferred or no relevant config could be read
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REQUIRED = [
    ("pre", "pre_tool_use.py"),
    ("post", "post_tool_use.py"),
    ("prompt", "user_prompt_submit.py"),
]

HOST_EVENTS = {
    "claude": {
        "pre": "PreToolUse",
        "post": "PostToolUse",
        "prompt": "UserPromptSubmit",
    },
    "codex": {
        "pre": "PreToolUse",
        "post": "PostToolUse",
        "prompt": "UserPromptSubmit",
    },
    "cursor": {
        "pre": "preToolUse",
        "post": "postToolUse",
        "prompt": "beforeSubmitPrompt",
    },
}


def _norm(value: str | Path) -> str:
    return str(value).replace("\\", "/").lower()


def _read_json(path: Path):
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _candidate_hook_roots() -> list[Path]:
    here = Path(__file__).resolve().parent
    cwd = Path(os.environ.get("SUPREMETEAM_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    home = Path.home()
    roots = [
        here,
        cwd / "skills" / "harness" / "hooks",
        cwd / "harness" / "hooks",
        home / ".agents" / "skills" / "harness" / "hooks",
        home / ".claude" / "skills" / "harness" / "hooks",
        home / ".cursor" / "skills" / "harness" / "hooks",
        home / ".config" / "opencode" / "skills" / "harness" / "hooks",
    ]
    env_root = os.environ.get("SUPREMETEAM_HOOK_ROOT")
    if env_root:
        roots.insert(0, Path(env_root))
    return roots


def _command_matches_script(command: str, script: str) -> bool:
    cmd = _norm(command)
    if script.lower() not in cmd:
        return False

    for root in _candidate_hook_roots():
        expected = _norm(root / script)
        if expected in cmd:
            return True

    # Accept common installed layouts even when paths contain unresolved host
    # placeholders, but reject unrelated packages such as critlabs-suite.
    accepted_fragments = (
        "/supremeteam/",
        "/.agents/skills/harness/hooks/",
        "/.claude/skills/harness/hooks/",
        "/.cursor/skills/harness/hooks/",
        "/.config/opencode/skills/harness/hooks/",
    )
    return any(fragment in cmd for fragment in accepted_fragments)


def _commands_from_standard_hooks(settings_objs: list[dict], event: str) -> list[str]:
    commands: list[str] = []
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
                    commands.append(hook["command"])
    return commands


def _commands_from_cursor_hooks(settings_objs: list[dict], event: str) -> list[str]:
    commands: list[str] = []
    for obj in settings_objs:
        if not isinstance(obj, dict):
            continue
        groups = (obj.get("hooks") or {}).get(event) or []
        if not isinstance(groups, list):
            continue
        for hook in groups:
            if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                commands.append(hook["command"])
    return commands


def _claude_paths() -> list[Path]:
    home = Path.home()
    base = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    return [
        home / ".claude" / "settings.json",
        base / ".claude" / "settings.json",
        base / ".claude" / "settings.local.json",
    ]


def _codex_paths() -> list[Path]:
    home = Path.home()
    base = Path(os.getcwd())
    return [
        home / ".codex" / "hooks.json",
        base / ".codex" / "hooks.json",
    ]


def _cursor_paths() -> list[Path]:
    home = Path.home()
    base = Path(os.getcwd())
    return [
        home / ".cursor" / "plugins" / "local" / "supremeteam-hooks" / "hooks" / "hooks.json",
        base / ".cursor" / "plugins" / "local" / "supremeteam-hooks" / "hooks" / "hooks.json",
    ]


def _opencode_paths() -> list[Path]:
    home = Path.home()
    base = Path(os.getcwd())
    return [
        home / ".config" / "opencode" / "plugins" / "supremeteam-hooks.js",
        base / ".opencode" / "plugins" / "supremeteam-hooks.js",
    ]


def _infer_host() -> str:
    env = os.environ
    if any(name.startswith("CODEX_") for name in env):
        return "codex"
    if any(name.startswith("CLAUDE") for name in env):
        return "claude"
    if any(name.startswith("CURSOR") for name in env):
        return "cursor"
    if any(name.startswith("OPENCODE") for name in env):
        return "opencode"
    return "all"


def _check_standard_host(host: str, paths: list[Path]) -> tuple[str, list[tuple[Path, object]], dict[str, bool]]:
    loaded = [(p, _read_json(p)) for p in paths]
    objs = [obj for _, obj in loaded if isinstance(obj, dict)]
    result: dict[str, bool] = {}
    for key, script in REQUIRED:
        event = HOST_EVENTS[host][key]
        commands = _commands_from_standard_hooks(objs, event)
        result[key] = any(_command_matches_script(command, script) for command in commands)
    return host, loaded, result


def _check_cursor() -> tuple[str, list[tuple[Path, object]], dict[str, bool]]:
    loaded = [(p, _read_json(p)) for p in _cursor_paths()]
    objs = [obj for _, obj in loaded if isinstance(obj, dict)]
    result: dict[str, bool] = {}
    for key, script in REQUIRED:
        event = HOST_EVENTS["cursor"][key]
        commands = _commands_from_cursor_hooks(objs, event)
        result[key] = any(_command_matches_script(command, script) for command in commands)
    return "cursor", loaded, result


def _check_opencode() -> tuple[str, list[tuple[Path, object]], dict[str, bool]]:
    loaded = []
    text = ""
    for path in _opencode_paths():
        try:
            value = path.read_text(encoding="utf-8") if path.exists() else None
        except Exception:
            value = None
        loaded.append((path, value))
        if isinstance(value, str):
            text += "\n" + value
    result = {key: _command_matches_script(text, script) for key, script in REQUIRED}
    return "opencode", loaded, result


def _check_host(host: str):
    if host == "claude":
        return _check_standard_host("claude", _claude_paths())
    if host == "codex":
        return _check_standard_host("codex", _codex_paths())
    if host == "cursor":
        return _check_cursor()
    if host == "opencode":
        return _check_opencode()
    raise ValueError(host)


def _state_label(path: Path, value: object) -> str:
    if value is None:
        return "absent" if not path.exists() else "unreadable"
    return "read"


def _print_result(host: str, loaded: list[tuple[Path, object]], result: dict[str, bool]) -> bool | None:
    print(f"\n[{host}]")
    print("Config files inspected:")
    for path, value in loaded:
        print(f"  - {path}  [{_state_label(path, value)}]")

    if not any(value is not None for _, value in loaded):
        print("  status: UNKNOWN - no relevant host config could be read.")
        return None

    all_ok = True
    for key, script in REQUIRED:
        ok = result.get(key) is True
        all_ok = all_ok and ok
        event = HOST_EVENTS.get(host, {}).get(key, "plugin")
        print(f"  [{'OK ' if ok else 'MISSING'}] {event} -> {script}")

    print("  status: REGISTERED" if all_ok else "  status: MISSING")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SupremeTeam harness hook registration.")
    parser.add_argument("--host", choices=["auto", "all", "codex", "claude", "cursor", "opencode"], default="auto")
    args = parser.parse_args()

    host = _infer_host() if args.host == "auto" else args.host
    hosts = ["codex", "claude", "cursor", "opencode"] if host == "all" else [host]

    print("SupremeTeam harness hook registration check")
    print(f"Selected host scope: {host}")

    statuses = []
    for selected in hosts:
        statuses.append(_print_result(*_check_host(selected)))

    if any(status is True for status in statuses):
        if host == "all":
            return 0
        return 0

    print("\nREGISTER_PROMPT: SupremeTeam harness hooks are not fully registered for the selected host scope.")
    print("Action: rerun the installer with hook registration enabled, for example:")
    print("  Windows: powershell -ExecutionPolicy Bypass -File .\\scripts\\install.ps1 -RegisterHooks")
    print("  macOS/Linux: bash ./scripts/install.sh --register-hooks")
    print("For a specific host, add -Target Codex/Claude/Cursor/OpenCode or --target codex/claude/cursor/opencode.")
    print("After writing hook config, open /hooks or restart the host if it requires hook review or reload.")

    if any(status is False for status in statuses):
        return 1
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"verify_registration: error ({exc}); status UNKNOWN")
        sys.exit(2)
