#!/usr/bin/env python3
"""Run a vulnerability scanner and record a typed, gate-checkable scan record.

The record distinguishes a clean scan from every way a scan can fail to
happen. Nothing here interprets scanner output as "no vulnerabilities" unless
the scanner itself exited cleanly.

    python skills/scripts/scan_record.py \
        --project-root . \
        --out skillset-saves/runs/<run>/security/evidence/scan-pip-audit.json \
        --input requirements.txt \
        -- pip-audit -r requirements.txt --strict

Result status mapping:

    pass         command found, exit code 0
    fail         command found, exit code in --fail-exit-codes (default: 1)
    error        command found, any other exit code, or it timed out
    unavailable  the executable could not be found
    not-run      --no-run was given (records the request without executing)

The record captures: tool, tool version (when --version-command is given),
command, exit code, observed_at, duration, inputs bound by sha256 to the
inspected manifests/lockfiles, target revision (git HEAD when available),
stdout/stderr paths (raw output retained beside the record), and limitations.
Exit code of this wrapper: 0 when the record was written (whatever the scan
status), 2 on wrapper error. Consumers read ``result.status``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head(project_root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(project_root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a vulnerability scan as typed evidence.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--out", required=True, help="path of the JSON record; raw output is stored beside it")
    parser.add_argument("--input", action="append", default=[], help="project-relative manifest/lockfile the scan inspects (repeatable)")
    parser.add_argument("--tool", help="tool name (default: first command token)")
    parser.add_argument("--version-command", help="command that prints the tool version, e.g. 'pip-audit --version'")
    parser.add_argument("--fail-exit-codes", default="1", help="comma-separated exit codes that mean findings were reported")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--no-run", action="store_true", help="record a not-run request without executing the scanner")
    parser.add_argument("--limitation", action="append", default=[], help="known coverage limitation (repeatable)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="scanner command after --")
    args = parser.parse_args()

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print(json.dumps({"engine_error": "scanner command is required after --"}), file=sys.stderr)
        return 2
    project_root = Path(args.project_root).resolve()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    tool = args.tool or Path(command[0]).name
    fail_codes = {int(c) for c in args.fail_exit_codes.split(",") if c.strip()}

    inputs = []
    for value in args.input:
        target = (project_root / value).resolve()
        try:
            target.relative_to(project_root)
        except ValueError:
            print(json.dumps({"engine_error": f"input escapes project root: {value}"}), file=sys.stderr)
            return 2
        if not target.is_file():
            print(json.dumps({"engine_error": f"input missing: {value}"}), file=sys.stderr)
            return 2
        inputs.append({"path": Path(value).as_posix(), "sha256": sha256_file(target)})

    version = None
    if args.version_command and not args.no_run:
        try:
            probe = subprocess.run(args.version_command, shell=True, text=True, capture_output=True, check=False, timeout=60)
            version = (probe.stdout or probe.stderr).strip().splitlines()[0] if (probe.stdout or probe.stderr).strip() else None
        except (OSError, subprocess.TimeoutExpired):
            version = None

    observed_at = datetime.now(timezone.utc).isoformat()
    stdout_path = out.with_name(out.stem + ".stdout.txt")
    stderr_path = out.with_name(out.stem + ".stderr.txt")
    status, exit_code, duration, limitations = "not-run", None, 0.0, list(args.limitation)
    if not args.no_run:
        executable = shutil.which(command[0]) or (command[0] if Path(command[0]).is_file() else None)
        if executable is None:
            status = "unavailable"
            limitations.append(f"executable not found on PATH: {command[0]}")
            stdout_path.write_text("", encoding="utf-8")
            stderr_path.write_text(f"executable not found: {command[0]}\n", encoding="utf-8")
        else:
            started = time.monotonic()
            try:
                proc = subprocess.run([executable, *command[1:]], cwd=str(project_root), text=True, capture_output=True, check=False, timeout=args.timeout)
                duration = round(time.monotonic() - started, 3)
                exit_code = proc.returncode
                stdout_path.write_text(proc.stdout or "", encoding="utf-8")
                stderr_path.write_text(proc.stderr or "", encoding="utf-8")
                if exit_code == 0:
                    status = "pass"
                elif exit_code in fail_codes:
                    status = "fail"
                else:
                    status = "error"
                    limitations.append(f"scanner exited with unexpected code {exit_code}")
            except subprocess.TimeoutExpired as exc:
                duration = round(time.monotonic() - started, 3)
                status = "error"
                limitations.append(f"scanner timed out after {args.timeout}s")
                stdout_path.write_text(exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""), encoding="utf-8")
                stderr_path.write_text(exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""), encoding="utf-8")
            except OSError as exc:
                status = "error"
                limitations.append(f"scanner could not start: {exc}")
                stdout_path.write_text("", encoding="utf-8")
                stderr_path.write_text(str(exc), encoding="utf-8")
    else:
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("not run\n", encoding="utf-8")

    record = {
        "type": "scan",
        "tool": tool,
        "tool_version": version,
        "command": " ".join(command),
        "exit_code": exit_code,
        "observed_at": observed_at,
        "duration_seconds": duration,
        "target_revision": git_head(project_root),
        "inputs": inputs,
        "artifacts": [stdout_path.name, stderr_path.name],
        "result": {"status": status},
        "limitations": limitations,
        "note": "status pass means the scanner exited 0; unavailable, error, and not-run are data gaps and never a clean scan",
    }
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, out)
    print(json.dumps({"record": str(out), "status": status, "exit_code": exit_code}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
