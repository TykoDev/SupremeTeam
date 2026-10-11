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
* **cursor, opencode, pi** need a plugin package or extension rather than a hook
  config entry. Those are written too, but the harness verifier cannot inspect
  them, so they are reported as ``verifiable: no``. The pi extension reports
  in the pi session itself, at every session start, whether it can run the hooks. Nothing here claims a hook will fire;
  whether the host actually invokes it is a host-observed fact.

Writes are scoped, previewable, and recoverable: ``--scope`` picks exactly one
config file (``user`` is the global one and the default, because the installer puts
the hook scripts under the user's skills directory), ``--dry-run`` prints a unified
diff and writes nothing, an existing file that is not valid UTF-8 JSON is refused
rather than overwritten, and every overwrite keeps a timestamped ``.bak-`` copy
before replacing the file atomically. File and backup keep the permission bits the
original had; a new user-level file is owner-only. A config file that is a symbolic
link is never replaced by a regular file: the user-level one (or one named with
``--claude-settings`` and its siblings) is written through to the link's target, and one at
project or local scope is refused.

Run from a terminal, it first prints that same preview and asks before writing
anything; ``--yes`` skips the question. With no terminal (CI, a pipe) it writes
straight away, as before. Each registration also records the sha256 of the hook
scripts under ``.harness-state/`` of the project it was run from, so
``verify_registration.py`` can report a script that changed later.

Exit 0 when every selected host is registered (or already was, or a dry run
previewed cleanly), 2 when a write was refused or a written hook did not verify,
3 when the operator declined at the prompt and nothing was written.
"""

from __future__ import annotations

import argparse
import difflib
import importlib
import json
import os
import sys
from pathlib import Path


class Refused(Exception):
    """A write this script declined to make. Reported to the operator, exit code 2."""


EXIT_REFUSED = 2
EXIT_DECLINED = 3

# Hosts whose registration this script can verify after writing it.
NATIVE_HOSTS = ("codex", "claude", "copilot")
# Hosts that need a plugin package the harness verifier cannot inspect.
PLUGIN_HOSTS = ("cursor", "opencode", "pi")
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


def _read_text(path: Path) -> str:
    """Read an existing file as UTF-8, refusing when it is some other encoding."""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise Refused(
            f"{path} is not UTF-8 text ({exc.reason} at byte {exc.start}); refusing to overwrite it. "
            "Windows PowerShell 5.1 redirection writes UTF-16: save the file as UTF-8, then re-run."
        ) from exc


def _read_config(path: Path) -> dict:
    """Read one JSON config, refusing to proceed when it exists but does not parse."""
    text = _read_text(path)
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


def _write_text(path: Path, before: str, after: str, dry_run: bool, repair, private: bool) -> Path | None:
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
    return repair.write_with_backup(path, after, private=private)


def _native_target(args: argparse.Namespace, host: str, repair) -> tuple[Path, bool]:
    """Resolve one native host's config file (an explicit override, else --scope) and whether it was overridden."""
    override = {"codex": args.codex_hooks, "claude": args.claude_settings, "copilot": args.copilot_hooks}[host]
    if override:
        return Path(override).expanduser(), True
    try:
        return repair.target_path(host, args.scope), False
    except ValueError as exc:
        raise Refused(str(exc)) from exc


def register_native(args: argparse.Namespace, host: str, verify, repair) -> dict:
    """Register the required hooks for one JSON-configured host, then verify them."""
    link, overridden = _native_target(args, host, repair)
    try:
        path = repair.resolve_config(link, through_links=overridden or args.scope == "user")
    except ValueError as exc:
        raise Refused(str(exc)) from exc
    before = _read_text(path)
    config = _read_config(path)
    try:
        desired, added = repair.plan(json.loads(json.dumps(config)), host, args.python_command)
    except ValueError as exc:
        raise Refused(f"{path}: {exc}") from exc

    after = json.dumps(desired, indent=2) + "\n"
    backup = None
    if added:
        backup = _write_text(path, before, after, args.dry_run, repair, private=args.scope == "user")
    elif args.dry_run:
        print(f"  (no change to {path})")

    result = {
        "host": host,
        "path": str(path),
        "verifiable": True,
        "added": added,
        "backup": str(backup) if backup else None,
        "applied": bool(added) and not args.dry_run,
        "notes": ([] if overridden else repair.scope_warnings(host, args.scope, link))
        + ([repair.link_warning(link, path)] if path != link else []),
    }
    if args.dry_run:
        result["hooks"] = {}
        result["registered"] = None
        return result

    # Re-read what is now on disk and ask the harness verifier, rather than
    # trusting that writing the file was the same thing as registering a hook.
    states = verify.hook_states([_read_config(path)], host)
    hooks = {}
    for key, script in verify.REQUIRED:
        state = states[key]
        hooks[script] = {"event": verify.EVENTS[host][key], "executable": state["registered"], "reason": state["reason"]}
    result["hooks"] = hooks
    result["registered"] = all(entry["executable"] for entry in hooks.values())
    if result["registered"]:
        result["hash_record"] = str(repair.record_hashes(states, host))
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
        before = _read_text(path)
        after = json.dumps(obj, indent=2) + "\n"
        if before != after:
            _write_text(path, before, after, args.dry_run, repair, private=True)
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


# The environment a bridge hands the hook interpreter. A host's whole environment is not
# passed on: PYTHONPATH, PYTHONHOME or PYTHONSTARTUP inherited from the shell that
# started the host would load other code into the guard before it decides anything.
# What the hooks read is kept: the system and home directories, the temporary
# directory, the data-root variables, the project-directory variables a command can
# spell (``_state.PROJECT_ENV``), the pi agent directory Rule F protects, and every
# ``SUPREMETEAM_`` setting the person who started the host chose.
HOOK_ENV_NAMES = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PROGRAMFILES", "PROGRAMDATA",
    "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "USER", "USERNAME", "LOGNAME",
    "TMPDIR", "TMP", "TEMP", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "CODEX_HOME", "AGENTS_HOME", "PI_CODING_AGENT_DIR",
)
HOOK_ENV_PREFIXES = ("SUPREMETEAM_",)


def hook_env_names(repair) -> list[str]:
    """Every variable a bridge passes on by name, upper-cased (Windows names are case-insensitive)."""
    names = [*HOOK_ENV_NAMES, *repair._state.PROJECT_ENV]
    return sorted({name.upper() for name in names})


def _hook_env_js(repair, typed: bool) -> str:
    """The JavaScript (or, ``typed``, TypeScript) function that builds the hook interpreter's environment."""
    def ts(annotation: str) -> str:
        return annotation if typed else ""

    return f"""const hookEnvNames{ts(": ReadonlySet<string>")} = new Set({json.dumps(hook_env_names(repair))});
const hookEnvPrefixes{ts(": readonly string[]")} = {json.dumps(list(HOOK_ENV_PREFIXES))};

function hookEnvironment(cwd{ts(": string")}){ts(": Record<string, string>")} {{
  const env{ts(": Record<string, string>")} = {{}};
  for (const [name, value] of Object.entries(process.env)) {{
    const upper = name.toUpperCase();
    if (value !== undefined && (hookEnvNames.has(upper) || hookEnvPrefixes.some((prefix) => upper.startsWith(prefix)))) {{
      env[name] = value;
    }}
  }}
  env.SUPREMETEAM_PROJECT_DIR = cwd;
  return env;
}}"""


def opencode_plugin_source(python_command: str, hook_root: str, repair) -> str:
    """The OpenCode plugin. ``spawnSync`` takes an executable and its arguments apart,
    so a launcher such as ``py -3`` is split here and its arguments are passed on."""
    command, *leading = repair.launcher_parts(python_command)
    arguments = [*leading, *repair.utf8_flags(python_command)]
    root = hook_root.replace("\\", "/")
    return f"""import {{ spawnSync }} from "node:child_process";

const pythonCommand = {_js_string(command)};
const pythonArgs = {json.dumps(arguments)};
const hookRoot = {_js_string(root)};

let launchFailure = null;
let launchFailureReported = false;

{_hook_env_js(repair, typed=False)}

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
    [...pythonArgs, `${{hookRoot}}/${{script}}`],
    {{
      input: JSON.stringify(payload),
      encoding: "utf8",
      env: hookEnvironment(cwd || process.cwd()),
    }},
  );
  if (result.error) {{
    launchFailure = launchFailure || String(result.error.message || result.error);
    return null;
  }}
  if (result.status) {{
    launchFailure = launchFailure || `${{script}} exited with status ${{result.status}}: ${{String(result.stderr || "").trim().slice(0, 300)}}`;
  }}
  if (!result.stdout.trim()) return null;
  try {{
    return JSON.parse(result.stdout);
  }} catch {{
    return null;
  }}
}}

async function reportLaunchFailure(ctx) {{
  if (!launchFailure || launchFailureReported || !ctx.client?.app?.log) return;
  launchFailureReported = true;
  await ctx.client.app.log({{
    body: {{
      service: "supremeteam-hooks",
      level: "warn",
      message: `The harness hooks are not running (${{pythonCommand}}): ${{launchFailure}}`,
    }},
  }});
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
    await reportLaunchFailure(ctx);
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
    await reportLaunchFailure(ctx);
    const context = result?.hookSpecificOutput?.additionalContext;
    if (context && ctx.client?.app?.log) {{
      await ctx.client.app.log({{
        body: {{ service: "supremeteam-hooks", level: "warn", message: context }},
      }});
    }}
  }},
}});
"""


def register_opencode(args: argparse.Namespace, repair) -> dict:
    """Write the OpenCode plugin. OpenCode loads JavaScript, not a hook config entry."""
    path = Path(args.opencode_plugin).expanduser()
    plugin = opencode_plugin_source(args.python_command, str(args.hook_root), repair)
    before = _read_text(path)
    changed = before != plugin
    if changed:
        _write_text(path, before, plugin, args.dry_run, repair, private=True)
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


# Runs under the registered interpreter at every pi session start (``sys.argv``: hook root, floor, scripts):
# prints the Python version, whether it meets the floor, and which hook scripts are missing.
_PI_PROBE = (
    "import json, os, sys; root, floor, scripts = sys.argv[1], sys.argv[2], sys.argv[3:]; "
    "print(json.dumps({'version': '.'.join(map(str, sys.version_info[:3])), "
    "'meets_floor': sys.version_info[:2] >= tuple(int(p) for p in floor.split('.')), "
    "'missing': [s for s in scripts if not os.path.isfile(os.path.join(root, s))]}))"
)


def pi_extension_path(override: str | None = None) -> Path:
    """Where pi loads a global extension from: ``$PI_CODING_AGENT_DIR/extensions``, else ``~/.pi/agent/extensions``."""
    if override:
        return Path(override).expanduser()
    agent = os.environ.get("PI_CODING_AGENT_DIR")
    base = Path(agent).expanduser() if agent else Path.home() / ".pi" / "agent"
    return base / "extensions" / "supremeteam-guard.ts"


def pi_extension_source(python_command: str, hook_root: str, repair, floor: str) -> str:
    """The pi extension: a TypeScript module pi loads from its extensions directory.

    It bridges pi's ``tool_call``, ``tool_result`` and ``input`` events to the three
    hook scripts with the payload contract the other hosts use, so the decisions stay
    the Python guard's. A deny becomes ``{ block: true, reason }``; anything that goes
    wrong in the bridge (the interpreter cannot start, the hook exits non-zero or
    prints something that is not JSON, an exception) fails open and is reported once
    per session. Every hook call carries pi's own session id, the hook interpreter
    gets ``hookEnvironment`` rather than pi's whole environment, and at each session
    start a probe runs the interpreter and reports in the session whether the guard is
    enforcing. The module is strictly typed against pi's published extension API.
    """
    command, *leading = repair.launcher_parts(python_command)
    arguments = [*leading, *repair.utf8_flags(python_command)]
    root = hook_root.replace("\\", "/")
    scripts = [script for _, script in repair.verify.REQUIRED]
    return f"""// Supreme Team guard for pi. Generated by scripts/install_hooks.py --target pi; re-run it to change this file.
// The decisions are made by the Python hooks under hookRoot; this module only carries pi's events to them.
import {{ spawnSync }} from "node:child_process";
import type {{ ExtensionAPI, ExtensionContext }} from "@earendil-works/pi-coding-agent";

const pythonCommand: string = {_js_string(command)};
const pythonArgs: readonly string[] = {json.dumps(arguments)};
const hookRoot: string = {_js_string(root)};
const minimumPython: string = {_js_string(floor)};
const hookScripts: readonly string[] = {json.dumps(scripts)};
const service = "supremeteam-guard";
const hookTimeoutMs = 60_000;
const probeSource: string = {_js_string(_PI_PROBE)};

{_hook_env_js(repair, typed=True)}

interface HookOutput {{
  hookSpecificOutput?: {{
    permissionDecision?: string;
    permissionDecisionReason?: string;
    additionalContext?: string;
  }};
}}

interface Probe {{
  version: string;
  meets_floor: boolean;
  missing: string[];
}}

let failure: string | null = null;
let failureReported = false;
let pendingContext: string | null = null;

function toToolName(name: string): string {{
  const lower = name.toLowerCase();
  if (lower === "bash") return "Bash";
  if (lower === "edit") return "Edit";
  if (lower === "write") return "Write";
  return name;
}}

function sessionId(ctx: ExtensionContext): string {{
  try {{
    const id = ctx.sessionManager.getSessionId();
    if (id) return `pi:${{id}}`;
  }} catch {{
    // An ephemeral or replaced session has no id; fall through to this process's own.
  }}
  return `pi:pid-${{process.pid}}`;
}}

function launch(args: readonly string[], input: string, cwd: string): {{ stdout: string; problem: string | null }} {{
  const result = spawnSync(pythonCommand, [...pythonArgs, ...args], {{
    input,
    encoding: "utf8",
    cwd,
    env: hookEnvironment(cwd),
    timeout: hookTimeoutMs,
    windowsHide: true,
  }});
  if (result.error) return {{ stdout: "", problem: String(result.error.message || result.error) }};
  const stdout = String(result.stdout || "");
  if (result.status !== 0) {{
    const stderr = String(result.stderr || "").trim().slice(0, 300);
    return {{ stdout, problem: `exited with status ${{result.status ?? result.signal}}: ${{stderr}}` }};
  }}
  return {{ stdout, problem: null }};
}}

function runHook(script: string, payload: Record<string, unknown>, cwd: string): HookOutput | null {{
  const {{ stdout, problem }} = launch([`${{hookRoot}}/${{script}}`], JSON.stringify(payload), cwd);
  if (problem) failure = failure || `${{script}} ${{problem}}`;
  if (!stdout.trim()) return null;
  try {{
    const parsed: unknown = JSON.parse(stdout);
    return parsed && typeof parsed === "object" ? (parsed as HookOutput) : null;
  }} catch {{
    failure = failure || `${{script}} printed output that is not JSON`;
    return null;
  }}
}}

function reportFailure(ctx: ExtensionContext): void {{
  if (!failure || failureReported) return;
  failureReported = true;
  ctx.ui.notify(`SupremeTeam guard is not enforcing (${{pythonCommand}}): ${{failure}}`, "warning");
}}

function bridgeFault(ctx: ExtensionContext, error: unknown): void {{
  failure = failure || `bridge error: ${{error instanceof Error ? error.message : String(error)}}`;
  reportFailure(ctx);
}}

function probe(ctx: ExtensionContext): void {{
  const {{ stdout, problem }} = launch(["-c", probeSource, hookRoot, minimumPython, ...hookScripts], "", ctx.cwd);
  let found: Probe | null = null;
  try {{
    found = problem ? null : (JSON.parse(stdout) as Probe);
  }} catch {{
    found = null;
  }}
  let fault: string | null = problem;
  if (!fault && !found) fault = "the readiness probe printed no report";
  if (!fault && found && !found.meets_floor) fault = `Python ${{found.version}} is below the ${{minimumPython}} floor`;
  if (!fault && found && found.missing.length) fault = `missing under ${{hookRoot}}: ${{found.missing.join(", ")}}`;
  if (fault) {{
    failure = fault;
    failureReported = false;
    ctx.ui.setStatus(service, "SupremeTeam guard: off");
    reportFailure(ctx);
    return;
  }}
  failure = null;
  failureReported = false;
  ctx.ui.setStatus(service, "SupremeTeam guard: on");
  ctx.ui.notify(`SupremeTeam guard active: Python ${{found?.version}} runs the hooks in ${{hookRoot}}`, "info");
}}

export default function supremeTeamGuard(pi: ExtensionAPI): void {{
  pi.on("session_start", async (_event, ctx) => {{
    try {{
      probe(ctx);
    }} catch (error) {{
      bridgeFault(ctx, error);
    }}
  }});

  pi.on("tool_call", async (event, ctx) => {{
    try {{
      const result = runHook(
        "pre_tool_use.py",
        {{ session_id: sessionId(ctx), cwd: ctx.cwd, tool_name: toToolName(event.toolName), tool_input: event.input }},
        ctx.cwd,
      );
      reportFailure(ctx);
      const hook = result?.hookSpecificOutput;
      if (hook?.permissionDecision === "deny") {{
        return {{ block: true, reason: hook.permissionDecisionReason || "Blocked by the SupremeTeam harness." }};
      }}
    }} catch (error) {{
      bridgeFault(ctx, error);
    }}
    return undefined;
  }});

  pi.on("tool_result", async (event, ctx) => {{
    try {{
      const result = runHook(
        "post_tool_use.py",
        {{
          session_id: sessionId(ctx),
          cwd: ctx.cwd,
          tool_name: toToolName(event.toolName),
          tool_input: event.input,
          tool_response: {{ content: event.content, details: event.details, is_error: event.isError }},
        }},
        ctx.cwd,
      );
      reportFailure(ctx);
      const context = result?.hookSpecificOutput?.additionalContext;
      if (context) return {{ content: [...event.content, {{ type: "text" as const, text: `[SupremeTeam] ${{context}}` }}] }};
    }} catch (error) {{
      bridgeFault(ctx, error);
    }}
    return undefined;
  }});

  pi.on("input", async (event, ctx) => {{
    try {{
      if (event.source !== "extension") {{
        const result = runHook("user_prompt_submit.py", {{ session_id: sessionId(ctx), cwd: ctx.cwd, prompt: event.text }}, ctx.cwd);
        reportFailure(ctx);
        pendingContext = result?.hookSpecificOutput?.additionalContext || null;
      }}
    }} catch (error) {{
      bridgeFault(ctx, error);
    }}
    return {{ action: "continue" as const }};
  }});

  pi.on("before_agent_start", async () => {{
    const content = pendingContext;
    pendingContext = null;
    if (!content) return undefined;
    return {{ message: {{ customType: service, content, display: false }} }};
  }});
}}
"""


def register_pi(args: argparse.Namespace, repair, verify) -> dict:
    """Write the pi extension. pi loads TypeScript extensions from its agent directory, not a hook config entry."""
    path = pi_extension_path(args.pi_extension)
    source = pi_extension_source(args.python_command, str(args.hook_root), repair, verify.declared_minimum())
    before = _read_text(path)
    changed = before != source
    if changed:
        _write_text(path, before, source, args.dry_run, repair, private=True)
    elif args.dry_run:
        print(f"  (no change to {path})")
    return {
        "host": "pi",
        "path": str(path),
        "verifiable": False,
        "added": [str(path)] if changed else [],
        "applied": changed and not args.dry_run,
        "registered": None,
        "note": "pi loads a TypeScript extension; verify_registration.py cannot inspect it. "
                "The next pi session reports 'SupremeTeam guard active' or why it is not enforcing.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register Supreme Team harness hooks in a host's native configuration.",
        epilog=(
            "codex, claude and copilot are verified after writing. cursor, opencode and pi need a "
            "plugin package or extension the harness verifier cannot inspect."
        ),
    )
    parser.add_argument("--target", action="append", choices=HOSTS, required=True,
                        help="host to register; repeat for more than one")
    parser.add_argument("--hook-root", type=Path, required=True,
                        help="installed skills/harness/hooks directory the commands will point at")
    parser.add_argument("--python-command", default=sys.executable or "python",
                        help="interpreter to register (a path, or a launcher with arguments such as 'py -3'); "
                             "default: the interpreter running this script")
    parser.add_argument("--scope", choices=["user", "project", "local"], default="user",
                        help="which config file to write for codex/claude/copilot: user is the global file, "
                             "project and local belong to the project around the working directory (default: user)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the unified diff for every file and write nothing")
    parser.add_argument("--yes", action="store_true",
                        help="do not ask before writing (a terminal run otherwise previews and asks)")
    parser.add_argument("--json", action="store_true", help="append a machine-readable report")
    parser.add_argument("--codex-hooks", default=None, help="override the codex config path")
    parser.add_argument("--claude-settings", default=None, help="override the claude config path")
    parser.add_argument("--copilot-hooks", default=None, help="override the copilot config path")
    parser.add_argument("--cursor-plugin",
                        default=str(Path.home() / ".cursor" / "plugins" / "local" / "supremeteam-hooks"))
    parser.add_argument("--opencode-plugin",
                        default=str(Path.home() / ".config" / "opencode" / "plugins" / "supremeteam-hooks.js"))
    parser.add_argument("--pi-extension", default=None,
                        help="override the pi extension path (default: $PI_CODING_AGENT_DIR/extensions, else "
                             "~/.pi/agent/extensions, /supremeteam-guard.ts)")
    return parser.parse_args()


def _run_targets(args: argparse.Namespace, targets: list[str], verify, repair) -> list[dict]:
    """Register (or, on a dry run, preview) every target and print what happened."""
    results = []
    for host in targets:
        print(f"\n[{host}]")
        try:
            if host in NATIVE_HOSTS:
                result = register_native(args, host, verify, repair)
            elif host == "cursor":
                result = register_cursor(args, repair)
            elif host == "pi":
                result = register_pi(args, repair, verify)
            else:
                result = register_opencode(args, repair)
        except Refused as exc:
            print(f"  REFUSED: {exc}")
            results.append({"host": host, "registered": False, "refused": True, "error": str(exc)})
            continue
        except OSError as exc:
            print(f"  FAILED: {exc}")
            results.append({"host": host, "registered": False, "error": str(exc)})
            continue
        results.append(result)

        # The interpreter is registered as given, so say now if it cannot run the hooks.
        warning = verify.interpreter_warning(verify.interpreter_report(repair.command_for("pre_tool_use.py", args.python_command)))
        print(f"  config: {result['path']}")
        for note in [*result.get("notes", []), *([warning] if warning else [])]:
            print(f"  note: {note}")
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
            if result.get("hash_record"):
                print(f"  hook hashes recorded in: {result['hash_record']}")
        else:
            print(f"  written, but not machine-verifiable. {result['note']}")
    return results


def _interactive() -> bool:
    try:
        return bool(sys.stdin and sys.stdout and sys.stdin.isatty() and sys.stdout.isatty())
    except ValueError:
        return False


def _confirm(question: str) -> bool:
    try:
        return input(question).strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def main() -> int:
    args = parse_args()
    args.hook_root = args.hook_root.expanduser().resolve()
    try:
        verify, repair = _load_harness(args.hook_root)
    except Refused as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED

    targets: list[str] = []
    for target in args.target:
        if target not in targets:
            targets.append(target)

    if not args.dry_run and not args.yes and _interactive():
        print("Preview of the changes. Nothing is written until you confirm.")
        preview = argparse.Namespace(**{**vars(args), "dry_run": True})
        if any(r.get("added") for r in _run_targets(preview, targets, verify, repair)):
            if not _confirm("\nWrite these changes? [y/N] "):
                print("Declined: nothing was written.")
                return EXIT_DECLINED
            print("\nWriting:")

    results = _run_targets(args, targets, verify, repair)

    print("\nobserved: unverified - whether the host fires a hook is not proven by writing config.")
    print("Open /hooks or restart the target host if it requires hook review or reload.")
    if not args.dry_run and any(host in NATIVE_HOSTS for host in targets):
        print("Confirm independently with: python skills/harness/hooks/verify_registration.py --host auto")

    if args.json:
        print("JSON_REPORT: " + json.dumps({"dry_run": args.dry_run, "scope": args.scope, "hosts": results}, sort_keys=True))

    failed = [r["host"] for r in results if r.get("registered") is False]
    if failed:
        print(f"\nRegistration did not verify for: {', '.join(failed)}")
        return EXIT_REFUSED
    return 0


if __name__ == "__main__":
    sys.exit(main())
