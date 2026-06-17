#!/usr/bin/env python3
"""
Register Supreme Team runtime harness hooks for supported agent hosts.

This helper is intentionally stdlib-only. The shell installers call it only when
the user explicitly opts in with -RegisterHooks / --register-hooks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


HOSTS = ("codex", "claude", "cursor", "opencode")
HOOKS = (
    ("PreToolUse", "Bash|PowerShell|Edit|Write|NotebookEdit|apply_patch", "pre_tool_use.py", "SupremeTeam: checking pending tool use"),
    ("PostToolUse", "Bash|PowerShell|apply_patch", "post_tool_use.py", "SupremeTeam: checking trajectory"),
    ("UserPromptSubmit", None, "user_prompt_submit.py", "SupremeTeam: checking entry routing"),
)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Cannot parse JSON at {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Expected a JSON object at {path}.")
    return data


def _write_json(path: Path, obj: dict, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _command(python_command: str, hook_root: Path, script: str) -> str:
    return f"{_quote(python_command)} {_quote(str(hook_root / script))}"


def _hook_handler(python_command: str, hook_root: Path, script: str, status: str | None = None) -> dict:
    handler = {
        "type": "command",
        "command": _command(python_command, hook_root, script),
    }
    if status:
        handler["statusMessage"] = status
    return handler


def _upsert_event(config: dict, event: str, matcher: str | None, handler: dict) -> None:
    hooks = config.setdefault("hooks", {})
    groups = hooks.setdefault(event, [])
    if not isinstance(groups, list):
        raise SystemExit(f"Cannot update hooks.{event}; expected a list.")

    command = handler["command"]
    for group in groups:
        if not isinstance(group, dict):
            continue
        if matcher is not None and group.get("matcher") != matcher:
            continue
        if matcher is None and "matcher" in group:
            continue
        existing = group.setdefault("hooks", [])
        if not isinstance(existing, list):
            continue
        if any(isinstance(h, dict) and h.get("command") == command for h in existing):
            return
        existing.append(handler)
        return

    group = {"hooks": [handler]}
    if matcher is not None:
        group["matcher"] = matcher
    groups.append(group)


def register_claude(args: argparse.Namespace) -> Path:
    path = Path(args.claude_settings).expanduser()
    obj = _read_json(path)
    for event, matcher, script, status in HOOKS:
        # Claude Code's matcher is exact-or-regex depending on syntax. Keep the
        # canonical Claude tool names for file edits and shell commands.
        claude_matcher = matcher.replace("|apply_patch", "") if matcher else None
        _upsert_event(obj, event, claude_matcher, _hook_handler(args.python_command, args.hook_root, script, status))
    _write_json(path, obj, args.dry_run)
    return path


def register_codex(args: argparse.Namespace) -> Path:
    path = Path(args.codex_hooks).expanduser()
    obj = _read_json(path)
    for event, matcher, script, status in HOOKS:
        _upsert_event(obj, event, matcher, _hook_handler(args.python_command, args.hook_root, script, status))
    _write_json(path, obj, args.dry_run)
    return path


def register_cursor(args: argparse.Namespace) -> Path:
    root = Path(args.cursor_plugin).expanduser()
    manifest = {
        "name": "supremeteam-hooks",
        "version": "1.0.0",
        "description": "Supreme Team runtime harness hooks for Cursor.",
        "hooks": "./hooks/hooks.json",
    }
    hooks = {
        "hooks": {
            "preToolUse": [
                {
                    "matcher": "Bash|PowerShell|Edit|Write|NotebookEdit|apply_patch",
                    "command": _command(args.python_command, args.hook_root, "pre_tool_use.py"),
                }
            ],
            "postToolUse": [
                {
                    "matcher": "Bash|PowerShell|apply_patch",
                    "command": _command(args.python_command, args.hook_root, "post_tool_use.py"),
                }
            ],
            "beforeSubmitPrompt": [
                {
                    "command": _command(args.python_command, args.hook_root, "user_prompt_submit.py"),
                }
            ],
        }
    }
    _write_json(root / ".cursor-plugin" / "plugin.json", manifest, args.dry_run)
    _write_json(root / "hooks" / "hooks.json", hooks, args.dry_run)
    return root


def _js_string(value: str) -> str:
    return json.dumps(value)


def register_opencode(args: argparse.Namespace) -> Path:
    path = Path(args.opencode_plugin).expanduser()
    hook_root = str(args.hook_root).replace("\\", "/")
    plugin = f"""import {{ spawnSync }} from "node:child_process";

const pythonCommand = {_js_string(args.python_command)};
const hookRoot = {_js_string(hook_root)};

function toToolName(name) {{
  const lower = String(name || "").toLowerCase();
  if (lower === "bash" || lower === "shell") return "Bash";
  if (lower === "powershell") return "PowerShell";
  if (lower === "edit" || lower === "write") return "Write";
  return String(name || "");
}}

function runHook(script, payload, cwd) {{
  const result = spawnSync(
    pythonCommand,
    [`${{hookRoot}}/${{script}}`],
    {{
      input: JSON.stringify(payload),
      encoding: "utf8",
      env: {{ ...process.env, SUPREMETEAM_PROJECT_DIR: cwd || process.cwd() }},
    }},
  );
  if (result.error || !result.stdout.trim()) return null;
  try {{
    return JSON.parse(result.stdout);
  }} catch {{
    return null;
  }}
}}

export const SupremeTeamHooks = async (ctx) => ({{
  "tool.execute.before": async (input, output) => {{
    const cwd = input?.cwd || ctx.directory || ctx.worktree || process.cwd();
    const payload = {{
      session_id: input?.sessionID || input?.session_id || "opencode",
      tool_name: toToolName(input?.tool || output?.tool),
      tool_input: output?.args || input?.args || {{}},
    }};
    const result = runHook("pre_tool_use.py", payload, cwd);
    const hook = result?.hookSpecificOutput;
    if (hook?.permissionDecision === "deny") {{
      throw new Error(hook.permissionDecisionReason || "Blocked by SupremeTeam harness.");
    }}
  }},
  "tool.execute.after": async (input, output) => {{
    const cwd = input?.cwd || ctx.directory || ctx.worktree || process.cwd();
    const payload = {{
      session_id: input?.sessionID || input?.session_id || "opencode",
      tool_name: toToolName(input?.tool || output?.tool),
      tool_input: input?.args || {{}},
      tool_response: output || {{}},
    }};
    const result = runHook("post_tool_use.py", payload, cwd);
    const context = result?.hookSpecificOutput?.additionalContext;
    if (context && ctx.client?.app?.log) {{
      await ctx.client.app.log({{
        body: {{ service: "supremeteam-hooks", level: "warn", message: context }},
      }});
    }}
  }},
}});
"""
    if args.dry_run:
        print(f"DRY-RUN write {path}")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(plugin, encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register Supreme Team harness hooks.")
    parser.add_argument("--target", action="append", choices=HOSTS, required=True)
    parser.add_argument("--hook-root", type=Path, required=True)
    parser.add_argument("--python-command", default=sys.executable or "python")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--codex-hooks", default=str(Path.home() / ".codex" / "hooks.json"))
    parser.add_argument("--claude-settings", default=str(Path.home() / ".claude" / "settings.json"))
    parser.add_argument("--cursor-plugin", default=str(Path.home() / ".cursor" / "plugins" / "local" / "supremeteam-hooks"))
    parser.add_argument("--opencode-plugin", default=str(Path.home() / ".config" / "opencode" / "plugins" / "supremeteam-hooks.js"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.hook_root = args.hook_root.expanduser().resolve()
    if not (args.hook_root / "pre_tool_use.py").exists():
        raise SystemExit(f"Hook root does not contain pre_tool_use.py: {args.hook_root}")

    registrars = {
        "claude": register_claude,
        "codex": register_codex,
        "cursor": register_cursor,
        "opencode": register_opencode,
    }

    seen = []
    for target in args.target:
        if target not in seen:
            seen.append(target)

    for target in seen:
        path = registrars[target](args)
        print(f"{target}: registered Supreme Team hooks at {path}")

    print("Open /hooks or restart the target host if it requires hook review or reload.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
