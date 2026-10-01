#!/usr/bin/env python3
"""Verify Supreme Team hook registration for Codex, Claude Code, or Copilot.

For every required hook the verifier reports independent states:

  configured  a command registered under the correct event names this
              script's resolved path (after ~ and environment expansion);
  resolvable  that script file exists on disk;
  executable  the command actually launches it: a Python launcher whose first
              positional argument is the script (``python -c``, ``python -m``,
              a wrapper that merely mentions the path, or a launcher option that
              swallows the path do not count).

A hook is REGISTERED when all three hold and at least one registered matcher
selects a tool the hook needs. Three more facts are reported next to it. None
turns a registration into a failure, because each has a legitimate cause:

  coverage     whether the matchers select every tool the hook needs. A narrower
               matcher is ``partial``; ``repair_registration.py`` adds a group
               for the missing tools.
  interpreter  the Python the command launches: found on PATH or not, and its
               version against the floor in runtime-manifest.yaml. The version is
               read by running that interpreter once with ``-I -S -c``; one inside
               the project directory is never run.
  integrity    whether the hook script still matches the sha256 recorded when it
               was registered. ``changed`` after a deliberate edit is expected.

Whether the host actually fires the hook is a separate, host-observed fact this
verifier never claims; it is reported as ``observed: unverified``.

``--host auto`` checks every host that has an environment signal or any config
file, and names them. A host chosen that way with no config file is MISSING, and
with no host at all so is the whole check. ``--host all`` checks the three hosts
regardless. Naming one host whose config cannot be read at all is UNKNOWN.

Exit 0 when every selected host is fully registered, 1 when readable config is
missing required hooks (or ``--host auto`` finds no host), and 2 when the
host/config cannot be determined. ``--json`` adds a machine-readable report after
the text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import _state

REQUIRED = [("pre", "pre_tool_use.py"), ("post", "post_tool_use.py"), ("prompt", "user_prompt_submit.py")]
_EVENT_MAP = {"pre": "PreToolUse", "post": "PostToolUse", "prompt": "UserPromptSubmit"}
EVENTS = {"claude": _EVENT_MAP, "codex": _EVENT_MAP, "copilot": _EVENT_MAP}
HOSTS = tuple(EVENTS)

# The tools each hook has to see. The verifier checks registered matchers against
# these and repair_registration.py writes them, so the two cannot disagree.
MATCHERS = {
    "pre_tool_use.py": "Bash|PowerShell|Edit|Write|NotebookEdit",
    "post_tool_use.py": "Bash|PowerShell",
    "user_prompt_submit.py": None,
}

# Codex realizes file edits through its own patch tool, which the portable matcher
# above does not name. Keeping the extension here means the verifier, the repair
# and scripts/install_hooks.py always require and write the same matcher for the
# same host, so a repair after an install cannot silently narrow the registered scope.
HOST_EXTRA_TOOLS = {
    "codex": {"pre_tool_use.py": ("apply_patch",), "post_tool_use.py": ("apply_patch",)},
}

# Python options that consume the following token.
_OPTS_WITH_ARG = {"-W", "-X", "--check-hash-based-pycs", "-Q"}
_PY_SELECTOR = re.compile(r"-\d(?:\.\d+)?(?:-\d\d)?")
_PROJECT_VARS = ("CLAUDE_PROJECT_DIR", "SUPREMETEAM_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE")
_HOST_SIGNALS = {"codex": ("CODEX_",), "claude": ("CLAUDE",), "copilot": ("COPILOT", "GITHUB_COPILOT")}

# sha256 of each registered hook script, written under .harness-state/ when the
# hook is registered. repair_registration.py is the writer.
HASH_RECORD = "hook-hashes.json"

_PROBE = "import sys; print(*sys.version_info[:3])"
_PROBED: dict[tuple, tuple | None] = {}


def _norm(value) -> str:
    # normcase is case-insensitive on Windows and preserves case on POSIX.  A
    # vendored path with the wrong case must not pass on a case-sensitive host.
    return os.path.normcase(str(value).replace("\\", "/"))


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


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
    project = str(_state.project_root())

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
    result = {"configured": False, "resolvable": False, "executable": False, "interpreter_on_path": None, "script": None, "reason": ""}
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
    result["script"] = str(existing[0]) if existing else None
    if not _python_launcher(launcher):
        result["reason"] = f"launcher {launcher!r} is not a Python interpreter"
        return result
    # Find the first positional argument after interpreter options.
    script_token = None
    index = 0
    args = tokens[1:]
    while index < len(args):
        token = args[index]
        if Path(launcher).name.lower().startswith("py") and _PY_SELECTOR.fullmatch(token):
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


def required_tools(script: str, host: str) -> list[str]:
    matcher = matcher_for(script, host)
    return matcher.split("|") if matcher else []


def matcher_selects(matcher, tool: str) -> bool:
    """Whether a registered matcher fires for ``tool``: absent, empty and ``*`` select
    every tool, anything else is a regular expression over the whole tool name."""
    if matcher is None:
        return True
    if not isinstance(matcher, str):
        return False
    if matcher in ("", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return tool in matcher.split("|")


def _entries(objects: list[dict], event: str) -> list[tuple[str, object]]:
    """Every registered ``(command, matcher)`` pair for one event."""
    found = []
    for obj in objects:
        groups = (obj.get("hooks") or {}).get(event) or [] if isinstance(obj, dict) else []
        for group in groups if isinstance(groups, list) else []:
            hooks = group.get("hooks") or [] if isinstance(group, dict) else []
            matcher = group.get("matcher") if isinstance(group, dict) else None
            for hook in hooks if isinstance(hooks, list) else []:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    found.append((hook["command"], matcher))
    return found


def declared_minimum(default: str = "3.13") -> str:
    """Read the Python floor from runtime-manifest.yaml, the runtime contract.

    A hardcoded second opinion would let a check report "too old" on a version
    the manifest declares supported, so the manifest wins and this fallback only
    covers a manifest that is missing or unreadable.
    """
    manifest = Path(__file__).resolve().parents[2] / "runtime-manifest.yaml"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        major, minor = (int(part) for part in str(data["runtime"]["python"]["minimum"]).split(".", 1))
        return f"{major}.{minor}"
    except Exception:
        return default


def _probe_version(path: str, selectors: list[str]) -> tuple | None:
    """The version of the interpreter at ``path``, or None when it cannot be read.

    A diagnostic must not run a binary that a cloned repository could have
    planted, so an interpreter inside the project directory is never executed.
    """
    key = (path, tuple(selectors))
    if key not in _PROBED:
        _PROBED[key] = _run_probe(path, selectors)
    return _PROBED[key]


def _run_probe(path: str, selectors: list[str]) -> tuple | None:
    try:
        resolved = Path(path).resolve()
        if resolved == Path(sys.executable).resolve():
            return tuple(sys.version_info[:3])
        if _state.project_root().resolve() in resolved.parents:
            return None
        done = subprocess.run([str(path), *selectors, "-I", "-S", "-c", _PROBE], capture_output=True, text=True,
                              timeout=5, stdin=subprocess.DEVNULL, check=False)
        major, minor, micro = (int(part) for part in done.stdout.split())
        return major, minor, micro
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def interpreter_report(command: str) -> dict:
    """Which Python a registered command launches, and whether it meets the floor."""
    tokens = _tokens(command)
    while tokens and re.match(r"^\w+=", tokens[0]):
        tokens.pop(0)
    launcher = tokens[0] if tokens else ""
    name = Path(launcher).name.lower()
    selectors = []
    if name in ("py", "py.exe"):
        for token in tokens[1:]:
            if not _PY_SELECTOR.fullmatch(token):
                break
            selectors.append(token)
    expanded = _expand(launcher)
    found = shutil.which(expanded) or (expanded if Path(expanded).is_file() else None)
    version = _probe_version(found, selectors) if found else None
    if version is None:
        named = re.search(r"python(\d+)\.(\d+)", name) or (re.fullmatch(r"-(\d)\.(\d+).*", selectors[0]) if selectors else None)
        version = (int(named.group(1)), int(named.group(2))) if named else None
    floor = tuple(int(part) for part in declared_minimum().split("."))
    return {
        "launcher": launcher,
        "path": found,
        "on_path": found is not None,
        "version": ".".join(str(part) for part in version) if version else None,
        "floor": ".".join(str(part) for part in floor),
        "meets_floor": None if version is None else tuple(version[:2]) >= floor,
    }


def interpreter_warning(report: dict | None) -> str | None:
    if not report:
        return None
    if report["meets_floor"] is False:
        return (f"interpreter {report['launcher']!r} is Python {report['version']}, below the {report['floor']} floor; "
                "the hooks will fail open and enforce nothing (point the registered command at a newer Python, "
                "or remove the three entries and register again)")
    if not report["on_path"]:
        return f"interpreter {report['launcher']!r} was not found on this PATH; the host must supply it"
    return None


def _blank(reason: str) -> dict:
    return {"configured": False, "resolvable": False, "executable": False, "interpreter_on_path": None, "script": None,
            "reason": reason, "command": None, "matcher": None, "missing_tools": [], "coverage": None,
            "registered": False, "interpreter": None}


def hook_states(objects: list[dict], host: str) -> dict[str, dict]:
    """Classify every required hook of one host against already-loaded config objects.

    The one place that decides what REGISTERED means, shared by this verifier,
    ``repair_registration.plan`` and ``scripts/install_hooks.py``.
    """
    states = {}
    for key, script in REQUIRED:
        needed = required_tools(script, host)
        best = _blank("no command registered")
        runnable = []
        for command, matcher in _entries(objects, EVENTS[host][key]):
            candidate = analyse(command, script)
            candidate.update(command=command, matcher=matcher)
            if candidate["executable"]:
                runnable.append(candidate)
            elif candidate["configured"] and not best["configured"]:
                best = {**_blank(""), **candidate}
        if runnable:
            best = {**_blank(""), **runnable[0]}
            covered = [tool for tool in needed if any(matcher_selects(c["matcher"], tool) for c in runnable)]
            best["missing_tools"] = [tool for tool in needed if tool not in covered]
            best["coverage"] = "not_applicable" if not needed else "full" if not best["missing_tools"] else "partial" if covered else "none"
            best["registered"] = best["coverage"] != "none"
            if not best["registered"]:
                best["reason"] = (f"matcher {', '.join(repr(c['matcher']) for c in runnable)} selects none of the tools "
                                  f"this hook needs ({', '.join(needed)})")
            best["interpreter"] = interpreter_report(best["command"])
        states[key] = best
    return states


def hook_hash(path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def load_hash_record() -> dict:
    """The recorded script hashes, read without creating the state directory."""
    directory = _state.existing_state_dir()
    data = _read(directory / HASH_RECORD) if directory else None
    hooks = data.get("hooks") if isinstance(data, dict) else None
    return hooks if isinstance(hooks, dict) else {}


def hash_key(script) -> str:
    return _norm(Path(script).resolve())


def integrity_for(script: str | None, record: dict) -> str | None:
    """``unchanged``, ``changed`` or ``unrecorded`` for one registered script."""
    if not script:
        return None
    recorded = record.get(hash_key(script))
    if not isinstance(recorded, dict) or not recorded.get("sha256"):
        return "unrecorded"
    return "unchanged" if recorded["sha256"] == hook_hash(script) else "changed"


def _paths(host: str) -> list[Path]:
    home = Path.home()
    project = _state.project_root()
    if host == "claude":
        return [home / ".claude/settings.json", project / ".claude/settings.json", project / ".claude/settings.local.json"]
    if host == "codex":
        return [home / ".codex/hooks.json", project / ".codex/hooks.json"]
    return [home / ".config/github-copilot/hooks.json", project / ".github/hooks.json"]


def _check(host: str):
    loaded = [(p, _read(p)) for p in _paths(host)]
    objects = [value for _, value in loaded if isinstance(value, dict)]
    result = hook_states(objects, host)
    record = load_hash_record()
    for state in result.values():
        state["observed"] = "unverified"
        state["integrity"] = integrity_for(state["script"], record) if state["registered"] else None
    return host, loaded, result, list(REQUIRED)


def resolve_hosts(selection: str) -> dict[str, str]:
    """The hosts to check, each with why. ``auto`` keeps the hosts that have an
    environment signal or any config file, so a host the operator does not use is
    not reported as an unregistered one."""
    if selection == "all":
        return {host: "all hosts requested" for host in HOSTS}
    if selection != "auto":
        return {selection: "requested"}
    chosen = {}
    for host in HOSTS:
        reasons = []
        if any(name.startswith(prefix) for name in os.environ for prefix in _HOST_SIGNALS[host]):
            reasons.append("environment signal")
        if any(_exists(path) for path in _paths(host)):
            reasons.append("config found")
        if reasons:
            chosen[host] = " and ".join(reasons)
    return chosen


def _hook_detail(state: dict) -> str:
    notes = []
    if not state["registered"]:
        notes.append(f"configured={str(state['configured']).lower()} resolvable={str(state['resolvable']).lower()}; {state['reason']}")
    elif state["coverage"] == "partial":
        notes.append(f"partial coverage: the matcher misses {', '.join(state['missing_tools'])}")
    return f"  ({'; '.join(notes)})" if notes else ""


def _print(host, loaded, result, required, absent_is_missing=False):
    print(f"\n[{host}]\nConfig files inspected:")
    for path, value in loaded:
        print(f"  - {path}  [{'read' if value is not None else 'absent' if not path.exists() else 'unreadable'}]")
    if not any(value is not None for _, value in loaded):
        # A host chosen by --host auto is one the operator uses, so having no
        # config file at all is a definite "nothing registered". Naming a host
        # that has no readable config stays UNKNOWN: the verifier cannot tell.
        if not (absent_is_missing and not any(_exists(path) for path, _ in loaded)):
            print("  status: UNKNOWN - no relevant host config could be read.")
            return None
    ok = True
    warnings: list[str] = []
    changed: list[str] = []
    for key, script in required:
        state = result[key]
        ok = ok and state["registered"]
        print(f"  [{'OK ' if state['registered'] else 'MISSING'}] {EVENTS[host][key]} -> {script}{_hook_detail(state)}")
        warning = interpreter_warning(state["interpreter"])
        if warning and warning not in warnings:
            warnings.append(warning)
        if state["integrity"] == "changed":
            changed.append(script)
    for warning in warnings:
        print(f"  warning: {warning}")
    if changed:
        print(f"  note: {', '.join(changed)} changed since registration (expected after a deliberate edit); "
              f"record the new hash with: python skills/harness/hooks/repair_registration.py --host {host} --record-hashes")
    print("  observed: unverified - host firing is not proven by config inspection")
    warned = warnings or any(result[key]["coverage"] == "partial" for key, _ in required)
    print(f"  status: {'REGISTERED' if ok else 'MISSING'}{' (with warnings)' if ok and warned else ''}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Supreme Team hook registration (read-only).")
    parser.add_argument("--host", choices=["auto", "all", *HOSTS], default="auto",
                        help="auto checks the hosts that have an environment signal or a config file (default)")
    parser.add_argument("--json", action="store_true", help="append a machine-readable report")
    args = parser.parse_args()
    chosen = resolve_hosts(args.host)
    print("Supreme Team harness hook registration check")
    if args.host == "auto":
        listing = ", ".join(f"{host} ({why})" for host, why in chosen.items()) or "none (no host environment signal and no host config file)"
        print(f"Selected host scope: auto -> {listing}")
    else:
        print(f"Selected host scope: {args.host}")
    checks = [_check(host) for host in chosen]
    statuses = [_print(*check, absent_is_missing=args.host == "auto") for check in checks]
    if not chosen:
        print("\n[auto]\n  status: MISSING - no host configuration was found, so no hook is registered anywhere.")
    if args.json:
        report = {h: {"status": "registered" if s is True else "missing" if s is False else "unknown",
                      "hooks": {k: v for k, v in r.items()},
                      "config_files": [{"path": str(p), "state": "read" if v is not None else "absent" if not p.exists() else "unreadable"} for p, v in l]}
                  for (h, l, r, _), s in zip(checks, statuses, strict=True)}
        print("JSON_REPORT: " + json.dumps(report, sort_keys=True))
    if chosen and all(status is True for status in statuses):
        return 0
    pending = [check[0] for check, status in zip(checks, statuses, strict=True) if status is not True]
    print("\nREGISTER_PROMPT: Supreme Team harness hooks are not fully registered for the selected host scope.")
    print(f"Register the {len(REQUIRED)} commands in the active host's native hook configuration.")
    print("The scripts live in skills/harness/hooks/; see that directory's README.md for exact examples,")
    print("or preview a scoped repair with: python skills/harness/hooks/repair_registration.py "
          f"--host {pending[0] if len(pending) == 1 else '<host>'} --scope project")
    return 1 if not chosen or any(status is False for status in statuses) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"verify_registration: error ({exc}); status UNKNOWN")
        raise SystemExit(2) from exc
