#!/usr/bin/env python3
"""Register Supreme Team runtime harness hooks in a host's native configuration.

This helper is intentionally stdlib-only. The shell installers call it only when
the user explicitly opts in with -RegisterHooks / --register-hooks.

It does not define the hook set. The required hooks, their event names, their
matchers, the command format, and the per-host config paths all come from the
installed harness itself (``verify_registration.py`` and
``repair_registration.py`` under ``--hook-root``), so an install and a later
repair can never write different registrations for the same host.

Two classes of host:

* **codex, claude, copilot** write native JSON hook config. After writing, this
  script re-reads the file and asks the harness verifier whether each command is
  actually *executable* - a Python launcher whose first positional argument is
  the hook script. It reports "registered" only when that holds.
* **cursor, opencode** need a plugin package rather than a hook config entry.
  Those are written too, but the harness verifier cannot inspect them, so they
  are reported as ``verifiable: no``. Nothing here claims a hook will fire;
  whether the host actually invokes it is a host-observed fact.

Writes are scoped, previewable, and recoverable: ``--scope`` picks exactly one
config file, ``--dry-run`` prints a unified diff and writes nothing, an existing
file that is not valid JSON is refused rather than overwritten, and every
overwrite keeps a timestamped ``.bak-`` copy before replacing the file
atomically.

Exit 0 when every selected host is registered (or already was, or a dry run
previewed cleanly), 2 when a write was refused or a written hook did not verify.
"""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


class Refused(Exception):
    """A write this script declined to make. Reported to the operator, exit code 2."""


# Hosts whose registration this script can verify after writing it.
NATIVE_HOSTS = ("codex", "claude", "copilot")
# Hosts that need a plugin package the harness verifier cannot inspect.
PLUGIN_HOSTS = ("cursor", "opencode")
HOSTS = NATIVE_HOSTS + PLUGIN_HOSTS


def _load_harness(hook_root: Path):
    """Import the installed harness modules so the hook contract has one definition."""
    for required in ("verify_registration.py", "repair_registration.py", "pre_tool_use.py"):
        if not (hook_root / required).is_file():
            raise Refused(
                f"Hook root is missing {required}: {hook_root}\n"
                "Point --hook-root at an installed skills/harness/hooks directory."
            )
    sys.path.insert(0, str(hook_root))
    try:
        verify = importlib.import_module("verify_registration")
        repair = importlib.import_module("repair_registration")
    except Exception as exc:  # pragma: no cover - surfaced to the operator
        raise Refused(f"Cannot load the harness hook modules from {hook_root}: {exc}") from exc
    if Path(repair.HOOK_DIR) != hook_root:
        raise Refused(
            f"Loaded repair_registration from {repair.HOOK_DIR}, not from {hook_root}. "
            "Another copy is shadowing it on sys.path; re-run with that copy removed."
        )
    return verify, repair


def _read_config(path: Path) -> dict:
    """Read one JSON config, refusing to proceed when it exists but does not parse."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise Refused(
            f"{path} exists but is not valid JSON ({exc}); refusing to overwrite it. "
            "Fix or move the file, then re-run."
        ) from exc
    if not isinstance(data, dict):
        raise Refused(f"{path} does not contain a JSON object; refusing to overwrite it.")
    return data


def _write_text(path: Path, before: str, after: str, dry_run: bool) -> Path | None:
    """Write atomically after backing up, or print the diff when this is a dry run.

    Returns the backup path when one was made.
    """
    if dry_run:
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(True),
                after.splitlines(True),
                fromfile=str(path),
                tofile=f"{path} (proposed)",
            )
        )
        print(diff if diff.strip() else f"  (no change to {path})")
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = path.with_name(path.name + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        shutil.copyfile(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(after, encoding="utf-8")
    os.replace(tmp, path)
    return backup


def _native_target(args: argparse.Namespace, host: str, repair) -> Path:
    """Resolve one native host's config file: an explicit override, else --scope."""
    override = {"codex": args.codex_hooks, "claude": args.claude_settings, "copilot": args.copilot_hooks}[host]
    if override:
        return Path(override).expanduser()
    try:
        return repair.target_path(host, args.scope)
    except ValueError as exc:
        raise Refused(str(exc)) from exc


def register_native(args: argparse.Namespace, host: str, verify, repair) -> dict:
    """Register the required hooks for one JSON-configured host, then verify them."""
    path = _native_target(args, host, repair)
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    config = _read_config(path)
    try:
        desired, added = repair.plan(json.loads(json.dumps(config)), host, args.python_command)
    except ValueError as exc:
        raise Refused(f"{path}: {exc}") from exc

    after = json.dumps(desired, indent=2) + "\n"
    backup = None
    if added:
        backup = _write_text(path, before, after, args.dry_run)
    elif args.dry_run:
        print(f"  (no change to {path})")

    result = {
        "host": host,
        "path": str(path),
        "verifiable": True,
        "added": added,
        "backup": str(backup) if backup else None,
        "applied": bool(added) and not args.dry_run,
    }
    if args.dry_run:
        result["hooks"] = {}
        result["registered"] = None
        return result

    # Re-read what is now on disk and ask the harness verifier, rather than
    # trusting that writing the file was the same thing as registering a hook.
    written = _read_config(path)
    hooks: dict[str, dict] = {}
    for key, script in verify.REQUIRED:
        event = verify.EVENTS[host][key]
        best = {"executable": False, "reason": "no command registered"}
        for command in verify._commands([written], event):
            candidate = verify.analyse(command, script)
            if candidate["executable"]:
                best = candidate
                break
            if candidate.get("configured") and not best.get("configured"):
                best = candidate
        hooks[script] = {"event": event, "executable": bool(best.get("executable")), "reason": best.get("reason", "")}
    result["hooks"] = hooks
    result["registered"] = all(entry["executable"] for entry in hooks.values())
    return result


def register_cursor(args: argparse.Namespace, repair) -> dict:
    """Write the Cursor plugin package. Cursor's schema is not the native hook schema."""
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
                    "matcher": repair.matcher_for("pre_tool_use.py", "cursor"),
                    "command": repair.command_for("pre_tool_use.py", args.python_command),
                }
            ],
            "postToolUse": [
                {
                    "matcher": repair.matcher_for("post_tool_use.py", "cursor"),
                    "command": repair.command_for("post_tool_use.py", args.python_command),
                }
            ],
            "beforeSubmitPrompt": [
                {"command": repair.command_for("user_prompt_submit.py", args.python_command)}
            ],
        }
    }
    written = []
    for path, obj in ((root / ".cursor-plugin" / "plugin.json", manifest), (root / "hooks" / "hooks.json", hooks)):
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        after = json.dumps(obj, indent=2) + "\n"
        if before != after:
            _write_text(path, before, after, args.dry_run)
            written.append(str(path))
        elif args.dry_run:
            print(f"  (no change to {path})")
    return {
        "host": "cursor",
        "path": str(root),
        "verifiable": False,
        "added": written,
        "applied": bool(written) and not args.dry_run,
        "registered": None,
        "note": "Cursor uses a plugin package; verify_registration.py cannot inspect it.",
    }


def _js_string(value: str) -> str:
    return json.dumps(value)


def register_opencode(args: argparse.Namespace) -> dict:
    """Write the OpenCode plugin. OpenCode loads JavaScript, not a hook config entry."""
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
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    changed = before != plugin
    if changed:
        _write_text(path, before, plugin, args.dry_run)
    elif args.dry_run:
        print(f"  (no change to {path})")
    return {
        "host": "opencode",
        "path": str(path),
        "verifiable": False,
        "added": [str(path)] if changed else [],
        "applied": changed and not args.dry_run,
        "registered": None,
        "note": "OpenCode loads a JavaScript plugin; verify_registration.py cannot inspect it.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register Supreme Team harness hooks in a host's native configuration.",
        epilog=(
            "codex, claude and copilot are verified after writing. cursor and opencode need a "
            "plugin package the harness verifier cannot inspect."
        ),
    )
    parser.add_argument("--target", action="append", choices=HOSTS, required=True,
                        help="host to register; repeat for more than one")
    parser.add_argument("--hook-root", type=Path, required=True,
                        help="installed skills/harness/hooks directory the commands will point at")
    parser.add_argument("--python-command", default=sys.executable or "python",
                        help="interpreter to register (a path, or a launcher with arguments such as 'py -3')")
    parser.add_argument("--scope", choices=["user", "project", "local"], default="user",
                        help="which config file to write for codex/claude/copilot (default: user)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the unified diff for every file and write nothing")
    parser.add_argument("--json", action="store_true", help="append a machine-readable report")
    parser.add_argument("--codex-hooks", default=None, help="override the codex config path")
    parser.add_argument("--claude-settings", default=None, help="override the claude config path")
    parser.add_argument("--copilot-hooks", default=None, help="override the copilot config path")
    parser.add_argument("--cursor-plugin",
                        default=str(Path.home() / ".cursor" / "plugins" / "local" / "supremeteam-hooks"))
    parser.add_argument("--opencode-plugin",
                        default=str(Path.home() / ".config" / "opencode" / "plugins" / "supremeteam-hooks.js"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.hook_root = args.hook_root.expanduser().resolve()
    try:
        verify, repair = _load_harness(args.hook_root)
    except Refused as exc:
        print(f"REFUSED: {exc}")
        return 2

    targets: list[str] = []
    for target in args.target:
        if target not in targets:
            targets.append(target)

    results = []
    for host in targets:
        print(f"\n[{host}]")
        try:
            if host in NATIVE_HOSTS:
                result = register_native(args, host, verify, repair)
            elif host == "cursor":
                result = register_cursor(args, repair)
            else:
                result = register_opencode(args)
        except Refused as exc:
            print(f"  REFUSED: {exc}")
            results.append({"host": host, "registered": False, "refused": True, "error": str(exc)})
            continue
        except OSError as exc:
            print(f"  FAILED: {exc}")
            results.append({"host": host, "registered": False, "error": str(exc)})
            continue
        results.append(result)

        print(f"  config: {result['path']}")
        if result.get("backup"):
            print(f"  backup: {result['backup']}")
        if args.dry_run:
            print("  dry run: nothing written")
            continue
        if not result["added"]:
            print("  no changes: already registered")
        if result["verifiable"]:
            for script, state in result.get("hooks", {}).items():
                mark = "OK " if state["executable"] else "FAILED"
                detail = "" if state["executable"] else f"  ({state['reason']})"
                print(f"  [{mark}] {state['event']} -> {script}{detail}")
            print("  status: REGISTERED" if result["registered"] else "  status: NOT REGISTERED")
        else:
            print(f"  written, but not machine-verifiable. {result['note']}")

    print("\nobserved: unverified - whether the host fires a hook is not proven by writing config.")
    print("Open /hooks or restart the target host if it requires hook review or reload.")
    if not args.dry_run and any(host in NATIVE_HOSTS for host in targets):
        print("Confirm independently with: python skills/harness/hooks/verify_registration.py --host auto")

    if args.json:
        print("JSON_REPORT: " + json.dumps({"dry_run": args.dry_run, "scope": args.scope, "hosts": results}, sort_keys=True))

    if args.dry_run:
        return 0
    failed = [r["host"] for r in results if r.get("registered") is False]
    if failed:
        print(f"\nRegistration did not verify for: {', '.join(failed)}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
