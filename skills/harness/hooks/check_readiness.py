#!/usr/bin/env python3
"""
SupremeTeam runtime readiness diagnostic.

Checks the three intake prerequisites that Admiral cares about before delegation:

1. Python is new enough for the runtime helpers.
2. Harness hooks are registered for the selected host.
3. ``skillset-saves`` exists and, when requested, contains an active pinned run.

This script is stdlib-only and diagnostic-only. It never registers hooks, creates
save state, installs Python, or mutates host configuration.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TERMINAL_STATES = {"DELIVERED", "RUN_COMPLETE"}


def _parse_frontmatter_value(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix.lower()):
            return stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return ""


def _state_is_active(text: str) -> bool:
    state = _parse_frontmatter_value(text, "state").upper()
    low = text.lower()
    pinned = "session_pin: true" in low or "session_pin:true" in low
    return pinned and state not in TERMINAL_STATES


def _read_text(path: Path) -> str | None:
    try:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def classify_saves(project_root: Path) -> tuple[str, str]:
    root = project_root / "skillset-saves"
    if not root.exists():
        return "missing", "skillset-saves does not exist"

    latest = _read_text(root / "_latest.md")
    if latest:
        run_id = _parse_frontmatter_value(latest, "latest_run_id")
        if run_id:
            state_text = _read_text(root / "runs" / run_id / "_state.md")
            if state_text and _state_is_active(state_text):
                return "active", f"latest run {run_id} is pinned and non-terminal"
            if state_text:
                return "inactive", f"latest run {run_id} is not active"

    runs_dir = root / "runs"
    if runs_dir.is_dir():
        for state_file in sorted(runs_dir.glob("*/_state.md"), reverse=True):
            state_text = _read_text(state_file)
            if state_text and _state_is_active(state_text):
                return "active", f"active run found by scan: {state_file.parent.name}"
        if any(runs_dir.glob("*/_state.md")):
            return "inactive", "runs exist but none are active"

    if latest is None and not runs_dir.exists():
        return "missing", "skillset-saves has no latest pointer or runs directory"
    return "unreadable", "skillset-saves exists but no readable run state was found"


def run_hook_verifier(host: str) -> tuple[str, int, str]:
    verifier = Path(__file__).resolve().with_name("verify_registration.py")
    result = subprocess.run(
        [sys.executable, str(verifier), "--host", host],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        status = "registered"
    elif result.returncode == 1:
        status = "missing"
    else:
        status = "unknown"
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    return status, result.returncode, output


def python_status(min_major: int, min_minor: int) -> tuple[str, str]:
    current = sys.version_info
    ok = (current.major, current.minor) >= (min_major, min_minor)
    label = f"{current.major}.{current.minor}.{current.micro}"
    if ok:
        return "ok", f"Python {label} satisfies >= {min_major}.{min_minor}"
    return "too_old", f"Python {label} is older than required >= {min_major}.{min_minor}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SupremeTeam runtime readiness.")
    parser.add_argument("--host", choices=["auto", "all", "codex", "claude", "cursor", "opencode"], default="auto")
    parser.add_argument("--project-root", default=".", help="Workspace root containing skillset-saves.")
    parser.add_argument("--min-python", default="3.13", help="Minimum Python major.minor version.")
    parser.add_argument("--require-active-run", action="store_true", help="Fail when skillset-saves has no active pinned run.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = parser.parse_args()

    try:
        min_major, min_minor = (int(part) for part in args.min_python.split(".", 1))
    except Exception as exc:
        raise SystemExit(f"Invalid --min-python value {args.min_python!r}; expected major.minor") from exc

    project_root = Path(args.project_root).expanduser().resolve()
    py_status, py_detail = python_status(min_major, min_minor)
    hook_status, hook_code, hook_output = run_hook_verifier(args.host)
    saves_status, saves_detail = classify_saves(project_root)

    report = {
        "python": {"status": py_status, "detail": py_detail},
        "hooks": {"status": hook_status, "exit_code": hook_code, "detail": hook_output},
        "saves": {"status": saves_status, "detail": saves_detail, "project_root": str(project_root)},
    }

    ready = py_status == "ok" and hook_status == "registered"
    if args.require_active_run:
        ready = ready and saves_status == "active"
    report["ready"] = ready

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("SupremeTeam runtime readiness check")
        print(f"Python: {py_status} - {py_detail}")
        print(f"Hooks: {hook_status} - verifier exit {hook_code}")
        print(f"Saves: {saves_status} - {saves_detail}")
        if hook_status != "registered":
            print("\nHook verifier output:")
            print(hook_output)
        print(f"\nReady: {'yes' if ready else 'no'}")

    return 0 if ready else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"check_readiness: error ({exc})")
        sys.exit(2)
