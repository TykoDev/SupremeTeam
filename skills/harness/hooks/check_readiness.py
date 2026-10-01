#!/usr/bin/env python3
"""
Supreme Team runtime readiness diagnostic.

Checks the intake prerequisites that the `admiral` orchestrator cares about
before delegation and reports them as *independent capabilities*:

1. Python is new enough for the runtime helpers.
2. Harness hooks are registered for the selected host (configured, resolvable,
   executable, matchers covering the tools each hook needs, interpreter found and
   new enough) and whether the host has actually fired them: each hook records
   real host invocations (payload with a session id) under
   ``.harness-state/observations/``; readiness reports ``observed``, ``partial``,
   ``simulated`` (synthetic payloads only), or ``unverified``, and how many
   internal faults a hook that fires has recorded.
3. ``skillset-saves`` exists and, when requested, contains an active pinned run.

``Ready`` covers the core: Python, a hook check that reached a definite answer,
and, when requested, an active run. Hooks are optional, so "not registered" does
not make the project not ready; ``--require-hooks`` makes it so, and then also
rejects a partial matcher and an interpreter that is missing or too old.
Anything the hook check can only call ``unknown`` (no readable host
configuration) is not a definite answer and does block.

This script is stdlib-only and diagnostic-only. It never registers hooks, creates
save state or ``.harness-state/``, installs Python, or mutates host
configuration. When hooks are missing it names the explicit, previewable repair
command instead.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from _saves import NEXT_STEPS, classify_saves
import _state
from verify_registration import HOSTS, declared_minimum, interpreter_warning, repair_command


def run_hook_verifier(host: str, project_root: Path) -> tuple[str, int, str, dict]:
    verifier = Path(__file__).resolve().with_name("verify_registration.py")
    command = [sys.executable, str(verifier), "--host", host, "--json"]
    # The verifier resolves the project from its environment, so it is handed the
    # root readiness was asked about, and its output is read as UTF-8 on any platform.
    env = {**os.environ, "SUPREMETEAM_PROJECT_DIR": str(project_root), "PYTHONUTF8": "1"}
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False, env=env)
    if result.returncode == 0:
        status = "registered"
    elif result.returncode == 1:
        status = "missing"
    else:
        status = "unknown"
    report: dict = {}
    detail_lines = []
    for line in result.stdout.splitlines():
        if line.startswith("JSON_REPORT: "):
            try:
                report = json.loads(line[len("JSON_REPORT: "):])
            except ValueError:
                report = {}
        else:
            detail_lines.append(line)
    output = "\n".join(part for part in ("\n".join(detail_lines).strip(), result.stderr.strip()) if part)
    return status, result.returncode, output, report


_EVENT_FOR_KEY = {"pre": "PreToolUse", "post": "PostToolUse", "prompt": "UserPromptSubmit"}


def _observation_records(project_root: Path) -> dict:
    """The per-event records the hooks wrote, read without creating anything."""
    directory = _state.existing_state_dir(project_root)
    records = {}
    for path in (directory / "observations").glob("*.json") if directory else ():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            records[path.stem] = data
    return records


def _fault_count(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _observations_for(project_root: Path, hook_states: dict) -> dict:
    """Host-observed firing, read from .harness-state/observations written by the hooks.

    ``observed`` means a payload carrying a host session id reached the hook;
    ``simulated`` means only synthetic invocations were seen; ``unverified``
    means no record exists. The summary is ``observed`` only when every core
    event has a real observation. A record may also carry ``faults`` and
    ``last_fault`` (the hook failed open that many times); both are optional.
    """
    records = _observation_records(project_root)
    events = {}
    for key, event in _EVENT_FOR_KEY.items():
        record = records.get(event, {})
        if isinstance(record.get("observed"), dict) and record["observed"]:
            events[event] = {"state": "observed", **record["observed"]}
        elif isinstance(record.get("simulated"), dict) and record["simulated"]:
            events[event] = {"state": "simulated", **record["simulated"]}
        else:
            events[event] = {"state": "unverified"}
        faults = _fault_count(record.get("faults"))
        if faults:
            events[event]["faults"] = faults
            last = record.get("last_fault")
            if isinstance(last, dict):
                events[event]["last_fault"] = {"type": str(last.get("type", "")), "at": str(last.get("at", ""))}
        for name, state in hook_states.items():
            if name.endswith(":" + key):
                state["observed"] = events[event]["state"]
    states = {e["state"] for e in events.values()}
    summary = "observed" if states == {"observed"} else "simulated" if "observed" not in states and "simulated" in states else "partial" if "observed" in states else "unverified"
    return {"summary": summary, "events": events, "faults": sum(e.get("faults", 0) for e in events.values())}


def _firing_lines(events: dict) -> list[str]:
    lines = []
    for event, entry in events.items():
        faults = entry.get("faults", 0)
        if not faults:
            continue
        last = entry.get("last_fault") or {}
        lasted = f" (last: {last.get('type') or 'unknown'} at {last.get('at') or 'unknown time'})"
        lines.append(f"{event}: firing with {faults} fault{'s' if faults != 1 else ''}{lasted}")
    return lines


def python_status(min_major: int, min_minor: int) -> tuple[str, str]:
    current = sys.version_info
    ok = (current.major, current.minor) >= (min_major, min_minor)
    label = f"{current.major}.{current.minor}.{current.micro}"
    if ok:
        return "ok", f"Python {label} satisfies >= {min_major}.{min_minor}"
    return "too_old", f"Python {label} is older than required >= {min_major}.{min_minor}"


def _hook_warnings(hook_states: dict) -> list[str]:
    """What is wrong with hooks that are registered, without making them unregistered."""
    warnings: list[str] = []
    changed = sorted({name.split(":", 1)[0] + ":" + Path(state["script"]).name for name, state in hook_states.items()
                      if state["registered"] and state["integrity"] == "changed" and state["script"]})
    for name, state in hook_states.items():
        if not state["registered"]:
            continue
        warning = interpreter_warning(state["interpreter"])
        if warning and warning not in warnings:
            warnings.append(warning)
        if state["coverage"] == "partial":
            warnings.append(f"{name}: the registered matcher misses {', '.join(state['missing_tools'])}")
    if changed:
        warnings.append(f"hook scripts changed since registration ({', '.join(changed)}); expected after a deliberate edit, "
                        "re-record with repair_registration.py --host <host> --record-hashes")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Supreme Team runtime readiness.")
    parser.add_argument("--host", choices=["auto", "all", *HOSTS], default="auto")
    parser.add_argument("--project-root", default=None,
                        help="Workspace root containing skillset-saves and the host config to inspect (default: the nearest project root above the working directory).")
    parser.add_argument("--min-python", default=None,
                        help="Minimum Python major.minor version (default: runtime-manifest.yaml).")
    parser.add_argument("--require-active-run", action="store_true", help="Fail when skillset-saves has no active pinned run.")
    parser.add_argument("--require-hooks", action="store_true",
                        help="Fail unless the hooks are registered with full matcher coverage and a usable interpreter (default: hooks are optional).")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    minimum = args.min_python or declared_minimum()
    try:
        min_major, min_minor = (int(part) for part in minimum.split(".", 1))
    except Exception as exc:
        raise SystemExit(f"Invalid --min-python value {minimum!r}; expected major.minor") from exc

    project_root = (Path(args.project_root).expanduser() if args.project_root else _state.project_root()).resolve()
    py_status, py_detail = python_status(min_major, min_minor)
    hook_status, hook_code, hook_output, hook_report = run_hook_verifier(args.host, project_root)
    saves_status, saves_detail = classify_saves(project_root)
    # An active run needs no instruction; every other classification has a next step, the one `save_run.py status` prints.
    saves_next = "" if saves_status == "active" else NEXT_STEPS.get(saves_status, "")

    # Independent capabilities: a missing hook degrades deterministic
    # enforcement; it does not remove the ability to read saves or run the
    # validators. Reporting them apart keeps "hooks missing" from being read as
    # "cannot do any work".
    hook_states = {}
    for host_name, host_report in hook_report.items():
        for key, state in (host_report.get("hooks") or {}).items():
            hook_states[f"{host_name}:{key}"] = {
                "configured": bool(state.get("configured")),
                "resolvable": bool(state.get("resolvable")),
                "executable": bool(state.get("executable")),
                "registered": bool(state.get("registered")),
                "coverage": state.get("coverage"),
                "missing_tools": state.get("missing_tools") or [],
                "script": state.get("script"),
                "integrity": state.get("integrity"),
                "interpreter": state.get("interpreter"),
                "observed": state.get("observed", "unverified"),
            }
    observations = _observations_for(project_root, hook_states)
    registered = [s for s in hook_states.values() if s["registered"]]
    interpreters = [s["interpreter"] for s in registered if s["interpreter"]]
    coverage = "partial" if any(s["coverage"] == "partial" for s in registered) else "full" if registered else "unverified"
    if any(i["meets_floor"] is False for i in interpreters):
        interpreter = "too_old"
    elif any(not i["on_path"] for i in interpreters):
        interpreter = "not_found"
    else:
        interpreter = "ok" if interpreters and all(i["meets_floor"] for i in interpreters) else "unverified"
    capabilities = {
        "python_runtime": py_status == "ok",
        "hooks_configured": bool(hook_states) and all(s["configured"] for s in hook_states.values()),
        "hooks_executable": hook_status == "registered",
        "hooks_coverage": coverage,
        "hooks_interpreter": interpreter,
        "hooks_observed": observations["summary"],
        "hooks_faults": observations["faults"],
        "saves_readable": saves_status not in {"missing", "unreadable"},
        "active_run": saves_status == "active",
        "deterministic_validators": True,
    }

    warnings = _hook_warnings(hook_states) + _firing_lines(observations["events"])
    repair_host = args.host if args.host in HOSTS else next(iter(hook_report)) if len(hook_report) == 1 else "<host>"
    needs_repair = hook_status != "registered" or coverage == "partial"
    repair_hint = (f"{repair_command(repair_host, '--scope', 'project')} "
                   "(dry run; add --apply only with owner authorization)") if needs_repair else None

    blockers = []
    if py_status != "ok":
        blockers.append(py_detail)
    if hook_status == "unknown":
        blockers.append("hook registration could not be determined (no readable host configuration for the selected host); "
                        "a check with no answer is not a pass")
    elif args.require_hooks:
        if hook_status != "registered":
            blockers.append("hooks are not registered (--require-hooks)")
        elif coverage == "partial":
            blockers.append("a registered matcher does not cover every tool the hook needs (--require-hooks)")
        elif interpreter in {"too_old", "not_found"}:
            blockers.append(f"the registered interpreter is {interpreter.replace('_', ' ')} (--require-hooks)")
    if args.require_active_run and saves_status != "active":
        blockers.append(f"no active pinned run (saves are {saves_status}; --require-active-run)")
    ready = not blockers

    report = {
        "python": {"status": py_status, "detail": py_detail},
        "hooks": {"status": hook_status, "exit_code": hook_code, "detail": hook_output, "required": args.require_hooks,
                  "selected_hosts": list(hook_report), "states": hook_states, "observations": observations["events"]},
        "saves": {"status": saves_status, "detail": saves_detail, "next_step": saves_next, "project_root": str(project_root)},
        "capabilities": capabilities,
        "warnings": warnings,
        "blockers": blockers,
        "repair_hint": repair_hint,
        "ready": ready,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        hosts = ", ".join(hook_report) or "no host selected"
        print("Supreme Team runtime readiness check")
        print(f"Python: {py_status} - {py_detail}")
        print(f"Hooks: {hook_status} - verifier exit {hook_code} (hosts: {hosts}; {'required' if args.require_hooks else 'optional'})")
        print(f"Saves: {saves_status} - {saves_detail}")
        if saves_next:
            print(f"  next: {saves_next}")
        print("Capabilities: " + ", ".join(f"{key}={value}" for key, value in capabilities.items()))
        if hook_status != "registered":
            print("\nHook verifier output:")
            print(hook_output)
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"  - {warning}")
        if repair_hint:
            print(f"\nRepair (read-only preview): {repair_hint}")
        if blockers:
            print("\nNot ready because:")
            for blocker in blockers:
                print(f"  - {blocker}")
        print(f"\nReady: {'yes' if ready else 'no'}")

    return 0 if ready else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"check_readiness: error ({exc})")
        sys.exit(2)
