#!/usr/bin/env python3
"""Verify Supreme Team hook registration for Codex, Claude Code, or Copilot.

For every required hook the verifier reports three independent states:

  configured  a command registered under the correct event names this
              script's resolved path (after ~ and environment expansion);
  resolvable  that script file exists on disk;
  executable  the command actually launches it: a Python launcher whose first
              positional argument is the script (``python -c``, ``python -m``,
              a wrapper that merely mentions the path, or a launcher option that
              swallows the path do not count).

A hook is REGISTERED only when all three hold. Whether the host actually
fires the hook is a separate, host-observed fact this verifier never claims;
it is reported as ``observed: unverified``.

Exit 0 when the selected host scope is fully registered, 1 when readable
config is missing required hooks, and 2 when the host/config cannot be
determined. ``--json`` adds a machine-readable report after the text.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

REQUIRED = [("pre", "pre_tool_use.py"), ("post", "post_tool_use.py"), ("prompt", "user_prompt_submit.py")]
ENDOR_REQUIRED = [
]
_EVENT_MAP = {"pre": "PreToolUse", "post": "PostToolUse", "prompt": "UserPromptSubmit"}
EVENTS = {"claude": _EVENT_MAP, "codex": _EVENT_MAP, "copilot": _EVENT_MAP}

# Python options that consume the following token.
_OPTS_WITH_ARG = {"-W", "-X", "--check-hash-based-pycs", "-Q"}
_PROJECT_VARS = ("CLAUDE_PROJECT_DIR", "SUPREMETEAM_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE")


def _norm(value) -> str:
    # normcase is case-insensitive on Windows and preserves case on POSIX.  A
    # vendored path with the wrong case must not pass on a case-sensitive host.
    return os.path.normcase(str(value).replace("\\", "/"))


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _roots() -> list[Path]:
    roots = [Path(__file__).resolve().parent]
    explicit = os.environ.get("SUPREMETEAM_HOOK_ROOT")
    if explicit:
        roots.insert(0, Path(explicit).expanduser().resolve())
    return roots


def _tokens(command: str) -> list[str]:
    """Split shell-like command text without treating Windows backslashes as escapes."""
    raw = re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\S+', command)
    return [token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'" else token
            for token in raw]


def _python_launcher(token: str) -> bool:
    name = Path(token.strip('"\'')).name.lower()
    return bool(re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?|py(?:\.exe)?", name))


def _expand(token: str) -> str:
    """Expand ~, $VAR, ${VAR}, and %VAR%; unset project variables fall back to
    the project directory so a config written for the host still verifies."""
    project = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("SUPREMETEAM_PROJECT_DIR") or os.getcwd()

    def sub(match):
        name = match.group(1) or match.group(2) or match.group(3)
        value = os.environ.get(name)
        if value is None and name in _PROJECT_VARS:
            value = project
        return value if value is not None else match.group(0)

    expanded = re.sub(r"\$\{(\w+)\}|\$(\w+)|%(\w+)%", sub, token)
    return os.path.expanduser(expanded)


def analyse(command: str, script: str) -> dict:
    """Classify one registered command against one expected hook script."""
    result = {"configured": False, "resolvable": False, "executable": False, "interpreter_on_path": None, "reason": ""}
    tokens = _tokens(command)
    # Skip leading VAR=value assignments.
    while tokens and re.match(r"^\w+=", tokens[0]):
        tokens.pop(0)
    if not tokens:
        result["reason"] = "empty command"
        return result
    launcher = tokens[0]
    expected = {_norm((root / script).resolve()) for root in _roots()}
    expanded = [_expand(t) for t in tokens[1:]]
    referenced = {_norm(Path(t).resolve()) for t in expanded if t}
    if not (referenced & expected):
        result["reason"] = "script path not referenced"
        return result
    result["configured"] = True
    existing = [Path(t).resolve() for t in expanded if _norm(Path(t).resolve()) in expected and Path(t).resolve().is_file()]
    result["resolvable"] = bool(existing)
    if not _python_launcher(launcher):
        result["reason"] = f"launcher {launcher!r} is not a Python interpreter"
        return result
    # Find the first positional argument after interpreter options.
    script_token = None
    index = 0
    args = tokens[1:]
    while index < len(args):
        token = args[index]
        if Path(launcher).name.lower().startswith("py") and re.fullmatch(r"-\d(?:\.\d+)?(?:-\d\d)?", token):
            index += 1  # py launcher version selector
            continue
        if token in {"-c", "-m"}:
            result["reason"] = f"interpreter option {token} means the script argument is not executed"
            return result
        if token in _OPTS_WITH_ARG:
            index += 2
            continue
        if token.startswith("-") and token != "-":
            index += 1
            continue
        script_token = token
        break
    if script_token is None:
        result["reason"] = "no script argument in executable position"
        return result
    resolved = _norm(Path(_expand(script_token)).resolve())
    if resolved not in expected:
        result["reason"] = "script path appears as data, not as the executed script"
        return result
    if not result["resolvable"]:
        result["reason"] = "script file does not exist at the configured path"
        return result
    launcher_path = Path(_expand(launcher))
    result["interpreter_on_path"] = bool(shutil.which(launcher) or (launcher_path.is_absolute() and launcher_path.is_file()))
    result["executable"] = True
    result["reason"] = "ok" if result["interpreter_on_path"] else "ok (interpreter not found on this PATH; host may supply it)"
    return result


def _commands(objects: list[dict], event: str) -> list[str]:
    found = []
    for obj in objects:
        groups = (obj.get("hooks") or {}).get(event) or [] if isinstance(obj, dict) else []
        for group in groups if isinstance(groups, list) else []:
            hooks = group.get("hooks") or [] if isinstance(group, dict) else []
            for hook in hooks if isinstance(hooks, list) else []:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    found.append(hook["command"])
    return found


def _paths(host: str) -> list[Path]:
    home, cwd = Path.home(), Path.cwd()
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("SUPREMETEAM_PROJECT_DIR") or cwd)
    if host == "claude":
        return [home / ".claude/settings.json", project / ".claude/settings.json", project / ".claude/settings.local.json"]
    if host == "codex":
        return [home / ".codex/hooks.json", project / ".codex/hooks.json"]
    return [home / ".config/github-copilot/hooks.json", project / ".github/hooks.json"]


def _check(host: str):
    loaded = [(p, _read(p)) for p in _paths(host)]
    objects = [value for _, value in loaded if isinstance(value, dict)]
    required = list(REQUIRED)
    result = {}
    for key, script in required:
        best = {"configured": False, "resolvable": False, "executable": False, "interpreter_on_path": None, "reason": "no command registered"}
        for command in _commands(objects, EVENTS[host][key]):
            candidate = analyse(command, script)
            candidate["command"] = command
            if candidate["executable"]:
                best = candidate
                break
            if candidate["configured"] and not best.get("configured"):
                best = candidate
        best["observed"] = "unverified"
        result[key] = best
    return host, loaded, result, required


def _infer() -> str:
    names = os.environ
    if any(name.startswith("CODEX_") for name in names): return "codex"
    if any(name.startswith("CLAUDE") for name in names): return "claude"
    if any(name.startswith("COPILOT") or name.startswith("GITHUB_COPILOT") for name in names): return "copilot"
    return "all"


def _print(host, loaded, result, required):
    print(f"\n[{host}]\nConfig files inspected:")
    for path, value in loaded:
        print(f"  - {path}  [{'read' if value is not None else 'absent' if not path.exists() else 'unreadable'}]")
    if not any(value is not None for _, value in loaded):
        print("  status: UNKNOWN - no relevant host config could be read."); return None
    ok = True
    for key, script in required:
        state = result.get(key, {})
        present = state.get("executable") is True; ok = ok and present
        detail = ""
        if not present:
            flags = f"configured={str(state.get('configured', False)).lower()} resolvable={str(state.get('resolvable', False)).lower()}"
            detail = f"  ({flags}; {state.get('reason', '')})"
        elif state.get("interpreter_on_path") is False:
            detail = "  (interpreter not on this PATH)"
        print(f"  [{'OK ' if present else 'MISSING'}] {EVENTS[host][key]} -> {script}{detail}")
    print("  observed: unverified - host firing is not proven by config inspection")
    print("  status: REGISTERED" if ok else "  status: MISSING")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=["auto", "all", "codex", "claude", "copilot"], default="auto")
    parser.add_argument("--json", action="store_true", help="append a machine-readable report")
    args = parser.parse_args(); host = _infer() if args.host == "auto" else args.host
    hosts = ["codex", "claude", "copilot"] if host == "all" else [host]
    print("Supreme Team harness hook registration check"); print(f"Selected host scope: {host}")
    checks = [_check(selected) for selected in hosts]
    statuses = [_print(*check) for check in checks]
    if args.json:
        report = {h: {"status": "registered" if s is True else "missing" if s is False else "unknown",
                      "hooks": {k: v for k, v in r.items()},
                      "config_files": [{"path": str(p), "state": "read" if v is not None else "absent" if not p.exists() else "unreadable"} for p, v in l]}
                  for (h, l, r, _), s in zip(checks, statuses)}
        print("JSON_REPORT: " + json.dumps(report, sort_keys=True))
    if all(status is True for status in statuses): return 0
    print("\nREGISTER_PROMPT: Supreme Team harness hooks are not fully registered for the selected host scope.")
    count = 3
    print(f"Register the {count} commands in the active host's native hook configuration.")
    print("The scripts live in skills/harness/hooks/; see that directory's README.md for exact examples,")
    print("or preview a scoped repair with: python skills/harness/hooks/repair_registration.py --host <host> --scope project")
    return 1 if any(status is False for status in statuses) else 2


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print(f"verify_registration: error ({exc}); status UNKNOWN"); raise SystemExit(2)
