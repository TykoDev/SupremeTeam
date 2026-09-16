#!/usr/bin/env python3
"""
Supreme Team runtime readiness diagnostic.

Checks the intake prerequisites that the `admiral` orchestrator cares about
before delegation and reports them as *independent capabilities*:

1. Python is new enough for the runtime helpers.
2. Harness hooks are registered for the selected host (configured, resolvable,
   executable) and whether the host has actually fired them: each hook records
   real host invocations (payload with a session id) under
   ``.harness-state/observations/``; readiness reports ``observed``, ``partial``,
   ``simulated`` (synthetic payloads only), or ``unverified``.
3. ``skillset-saves`` exists and, when requested, contains an active pinned run.

This script is stdlib-only and diagnostic-only. It never registers hooks, creates
save state, installs Python, or mutates host configuration. When hooks are
missing it names the explicit, previewable repair command instead.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _saves import classify_saves
import _state


def run_hook_verifier(host: str) -> tuple[str, int, str, dict]:
    verifier = Path(__file__).resolve().with_name("verify_registration.py")
    command = [sys.executable, str(verifier), "--host", host, "--json"]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
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


def _observations_for(project_root: Path, hook_states: dict) -> dict:
    """Host-observed firing, read from .harness-state/observations written by the hooks.

    ``observed`` means a payload carrying a host session id reached the hook;
    ``simulated`` means only synthetic invocations were seen; ``unverified``
    means no record exists. The summary is ``observed`` only when every core
    event has a real observation.
    """
    import os
    previous = os.environ.get("SUPREMETEAM_PROJECT_DIR")
    os.environ["SUPREMETEAM_PROJECT_DIR"] = str(project_root)
    try:
        records = _state.load_observations()
    finally:
        if previous is None:
            os.environ.pop("SUPREMETEAM_PROJECT_DIR", None)
        else:
            os.environ["SUPREMETEAM_PROJECT_DIR"] = previous
    events = {}
    for key, event in _EVENT_FOR_KEY.items():
        record = records.get(event, {})
        if record.get("observed"):
            events[event] = {"state": "observed", **record["observed"]}
        elif record.get("simulated"):
            events[event] = {"state": "simulated", **record["simulated"]}
        else:
            events[event] = {"state": "unverified"}
        for name, state in hook_states.items():
            if name.endswith(":" + key):
                state["observed"] = events[event]["state"]
    states = {e["state"] for e in events.values()}
    summary = "observed" if states == {"observed"} else "simulated" if "observed" not in states and "simulated" in states else "partial" if "observed" in states else "unverified"
    return {"summary": summary, "events": events}


def declared_minimum(default: str = "3.13") -> str:
    """Read the Python floor from runtime-manifest.yaml, the runtime contract.

    A hardcoded second opinion here would let readiness report "too old" on a
    version the manifest declares supported, so the manifest wins and this
    fallback only covers a manifest that is missing or unreadable.
    """
    manifest = Path(__file__).resolve().parents[2] / "runtime-manifest.yaml"
    try:
        import json

        data = json.loads(manifest.read_text(encoding="utf-8"))
        value = data["runtime"]["python"]["minimum"]
        major, minor = (int(part) for part in str(value).split(".", 1))
        return f"{major}.{minor}"
    except Exception:
        return default


def python_status(min_major: int, min_minor: int) -> tuple[str, str]:
    current = sys.version_info
    ok = (current.major, current.minor) >= (min_major, min_minor)
    label = f"{current.major}.{current.minor}.{current.micro}"
    if ok:
        return "ok", f"Python {label} satisfies >= {min_major}.{min_minor}"
    return "too_old", f"Python {label} is older than required >= {min_major}.{min_minor}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Supreme Team runtime readiness.")
    parser.add_argument("--host", choices=["auto", "all", "codex", "claude", "copilot"], default="auto")
    parser.add_argument("--project-root", default=None,
                        help="Workspace root containing skillset-saves (default: the nearest project root above the working directory).")
    parser.add_argument("--min-python", default=None,
                        help="Minimum Python major.minor version (default: runtime-manifest.yaml).")
    parser.add_argument("--require-active-run", action="store_true", help="Fail when skillset-saves has no active pinned run.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    minimum = args.min_python or declared_minimum()
    try:
        min_major, min_minor = (int(part) for part in minimum.split(".", 1))
    except Exception as exc:
        raise SystemExit(f"Invalid --min-python value {minimum!r}; expected major.minor") from exc

    project_root = (Path(args.project_root).expanduser() if args.project_root else _state.project_root()).resolve()
    py_status, py_detail = python_status(min_major, min_minor)
    hook_status, hook_code, hook_output, hook_report = run_hook_verifier(args.host)
    saves_status, saves_detail = classify_saves(project_root)

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
                "observed": state.get("observed", "unverified"),
            }
    observations = _observations_for(project_root, hook_states)
    capabilities = {
        "python_runtime": py_status == "ok",
        "hooks_configured": bool(hook_states) and all(s["configured"] for s in hook_states.values()),
        "hooks_executable": hook_status == "registered",
        "hooks_observed": observations["summary"],
        "saves_readable": saves_status not in {"missing", "unreadable"},
        "active_run": saves_status == "active",
        "deterministic_validators": True,
    }

    report = {
        "python": {"status": py_status, "detail": py_detail},
        "hooks": {"status": hook_status, "exit_code": hook_code, "detail": hook_output, "states": hook_states, "observations": observations["events"]},
        "saves": {"status": saves_status, "detail": saves_detail, "project_root": str(project_root)},
        "capabilities": capabilities,
        "repair_hint": None if hook_status == "registered" else
            "python skills/harness/hooks/repair_registration.py --host <host> --scope project (dry run; add --apply only with owner authorization)",
    }

    ready = py_status == "ok" and hook_status == "registered"
    if args.require_active_run:
        ready = ready and saves_status == "active"
    report["ready"] = ready

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("Supreme Team runtime readiness check")
        print(f"Python: {py_status} - {py_detail}")
        print(f"Hooks: {hook_status} - verifier exit {hook_code}")
        print(f"Saves: {saves_status} - {saves_detail}")
        print("Capabilities: " + ", ".join(f"{key}={value}" for key, value in capabilities.items()))
        if hook_status != "registered":
            print("\nHook verifier output:")
            print(hook_output)
            print(f"\nRepair (read-only preview): {report['repair_hint']}")
        print(f"\nReady: {'yes' if ready else 'no'}")

    return 0 if ready else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"check_readiness: error ({exc})")
        sys.exit(2)
