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

    pass         command found, exit code 0 and no --fail-on-output pattern matched
    fail         command found, exit code in --fail-exit-codes (default: 1), or
                 exit code 0 with output matching a --fail-on-output pattern
    error        command found, any other exit code, or it timed out
    unavailable  the executable could not be found
    not-run      --no-run was given (records the request without executing)

``pass`` records that the scanner exited 0, which is not proof that it found
nothing: a scanner that exits 0 with findings printed (semgrep without --error,
trivy without --exit-code) needs its own exit-code flag or a --fail-on-output
pattern that matches its findings line.

The record captures: tool, tool version and the argv that printed it (when
--version-command is given), command (shlex.join of argv) and argv itself, exit
code, observed_at, duration, inputs bound by sha256 to the inspected
manifests/lockfiles, target revision (git HEAD when available), the stdout and
stderr artifacts (raw output retained beside the record), and limitations. A
--version-command that cannot start (a missing executable, or a Windows path whose
backslashes POSIX quoting read as escapes) is named in the limitations, so a null
tool version always has a reason on the record.
Artifact names are relative to the manifest that will embed the record, so the
record passes the gate unedited: the run phase directory when --out sits inside
skillset-saves/runs/<run>/<phase>/, else the record's own directory, else
--manifest-root.
Exit code of this wrapper: 0 when the record was written (whatever the scan
status), 2 on wrapper error, including an unusable argument. A destination that
cannot hold the record or the raw output beside it is a wrapper error, not a scan
result: the sidecars are the ``artifacts`` the record names, so nothing is
written rather than a record that points at output that does not exist.
Consumers read ``result.status``.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from data_formats import content_sha256  # noqa: E402


def sha256_file(path: Path) -> str:
    """Canonical digest: text folded to LF, binary byte-for-byte (data_formats.content_sha256)."""
    return content_sha256(path)


def discard(path: Path) -> None:
    """Drop a temp file a failed write or replace left behind, masking nothing."""
    try:
        path.unlink()
    except OSError:
        pass


def git_head(project_root: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(project_root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def resolve_executable(name: str) -> str | None:
    """Where a command name resolves (PATH lookup, PATHEXT on Windows), or None."""
    return shutil.which(name) or (name if Path(name).is_file() else None)


def manifest_root(out: Path, override: str | None) -> Path:
    """The directory artifact names are written relative to: the embedding manifest's own.

    check.py resolves every artifact name against the manifest's directory, and
    the manifest of a run phase sits at skillset-saves/runs/<run>/<phase>/, so a
    record written under that phase names its output as ``evidence/<file>``.
    """
    if override:
        return Path(override).resolve()
    for ancestor in out.parents:
        if ancestor.parent.parent.name == "runs" and ancestor.parent.parent.parent.name == "skillset-saves":
            return ancestor
    return out.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a vulnerability scan as typed evidence.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--out", required=True, help="path of the JSON record; raw output is stored beside it")
    parser.add_argument("--input", action="append", default=[], help="project-relative manifest/lockfile the scan inspects (repeatable)")
    parser.add_argument("--tool", help="tool name (default: first command token)")
    parser.add_argument("--version-command", help="command that prints the tool version, e.g. 'pip-audit --version'; split with POSIX shell quoting rules (so write a Windows path with / or doubled backslashes) and run as an argument list, never through a shell; a version command that cannot start is named in the record's limitations")
    parser.add_argument("--fail-exit-codes", default="1", help="comma-separated integer exit codes that mean findings were reported")
    parser.add_argument("--fail-on-output", action="append", default=[], metavar="REGEX", help="record fail instead of pass when the scanner exits 0 but its stdout or stderr matches REGEX (repeatable), for scanners that print findings and exit 0")
    parser.add_argument("--manifest-root", help="directory of the manifest that will embed this record; artifact names are written relative to it (default: the run phase directory when --out is inside skillset-saves/runs/<run>/<phase>/, else the record's own directory)")
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
    try:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(json.dumps({"engine_error": f"record destination unusable: {exc}"}), file=sys.stderr)
        return 2
    tool = args.tool or Path(command[0]).name
    try:
        fail_codes = {int(c) for c in args.fail_exit_codes.split(",") if c.strip()}
    except ValueError:
        print(json.dumps({"engine_error": f"--fail-exit-codes must be comma-separated integers: {args.fail_exit_codes!r}"}), file=sys.stderr)
        return 2
    try:
        output_patterns = [re.compile(pattern) for pattern in args.fail_on_output]
    except re.error as exc:
        print(json.dumps({"engine_error": f"--fail-on-output is not a valid regular expression: {exc}"}), file=sys.stderr)
        return 2
    try:
        version_argv = shlex.split(args.version_command) if args.version_command else []
    except ValueError as exc:
        print(json.dumps({"engine_error": f"--version-command is not a valid command line: {exc}"}), file=sys.stderr)
        return 2
    stdout_path = out.with_name(out.stem + ".stdout.txt")
    stderr_path = out.with_name(out.stem + ".stderr.txt")
    root = manifest_root(out, args.manifest_root)
    try:
        artifact_names = [path.relative_to(root).as_posix() for path in (stdout_path, stderr_path)]
    except ValueError:
        print(json.dumps({"engine_error": f"the record and its raw output must sit under the manifest root: {root}"}), file=sys.stderr)
        return 2

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

    version, version_gap = None, None
    if version_argv and not args.no_run:
        probe_executable = resolve_executable(version_argv[0])
        if probe_executable is None:
            # POSIX quoting reads a backslash as an escape, so an unquoted Windows path arrives mangled and
            # the version would otherwise go missing without a word.
            hint = ""
            if "\\" in args.version_command:
                hint = " (a backslash escapes the next character: write the path with / or double each backslash)"
            version_gap = f"version command not run: executable not found on PATH: {version_argv[0]}{hint}"
        else:
            try:
                probe = subprocess.run([probe_executable, *version_argv[1:]], text=True, capture_output=True, check=False, timeout=60)
                output = (probe.stdout or probe.stderr).strip()
                version = output.splitlines()[0] if output else None
            except (OSError, subprocess.TimeoutExpired) as exc:
                version_gap = f"version command failed: {type(exc).__name__}"

    observed_at = datetime.now(timezone.utc).isoformat()
    status, exit_code, duration, limitations = "not-run", None, 0.0, list(args.limitation)
    if version_gap:
        limitations.append(version_gap)
    raw_stdout, raw_stderr = "", "not run\n"
    if not args.no_run:
        executable = resolve_executable(command[0])
        if executable is None:
            status = "unavailable"
            limitations.append(f"executable not found on PATH: {command[0]}")
            raw_stdout, raw_stderr = "", f"executable not found: {command[0]}\n"
        else:
            started = time.monotonic()
            try:
                proc = subprocess.run([executable, *command[1:]], cwd=str(project_root), text=True, capture_output=True, check=False, timeout=args.timeout)
                duration = round(time.monotonic() - started, 3)
                exit_code = proc.returncode
                raw_stdout, raw_stderr = proc.stdout or "", proc.stderr or ""
                if exit_code == 0:
                    matched = next((rx.pattern for rx in output_patterns if rx.search(raw_stdout) or rx.search(raw_stderr)), None)
                    if matched is None:
                        status = "pass"
                    else:
                        status = "fail"
                        limitations.append(f"scanner exited 0 but its output matched --fail-on-output {matched!r}")
                elif exit_code in fail_codes:
                    status = "fail"
                else:
                    status = "error"
                    limitations.append(f"scanner exited with unexpected code {exit_code}")
            except subprocess.TimeoutExpired as exc:
                duration = round(time.monotonic() - started, 3)
                status = "error"
                limitations.append(f"scanner timed out after {args.timeout}s")
                raw_stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                raw_stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            except OSError as exc:
                status = "error"
                limitations.append(f"scanner could not start: {exc}")
                raw_stdout, raw_stderr = "", str(exc)

    try:
        stdout_path.write_text(raw_stdout, encoding="utf-8")
        stderr_path.write_text(raw_stderr, encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"engine_error": f"raw output destination unusable: {exc}"}), file=sys.stderr)
        return 2

    record = {
        "type": "scan",
        "tool": tool,
        "tool_version": version,
        "version_command": shlex.join(version_argv) if version_argv else None,
        "command": shlex.join(command),
        "argv": command,
        "exit_code": exit_code,
        "observed_at": observed_at,
        "duration_seconds": duration,
        "target_revision": git_head(project_root),
        "inputs": inputs,
        "artifacts": artifact_names,
        "result": {"status": status},
        "limitations": limitations,
        "note": "status pass means the scanner exited 0 and matched no --fail-on-output pattern, which is not proof it found nothing; unavailable, error, and not-run are data gaps and never a clean scan",
    }
    tmp = out.with_suffix(out.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        discard(tmp)
        print(json.dumps({"engine_error": f"record could not be written: {exc}"}), file=sys.stderr)
        return 2
    try:
        os.replace(tmp, out)
    except OSError as exc:
        discard(tmp)
        print(json.dumps({"engine_error": f"record could not be moved into place: {exc}"}), file=sys.stderr)
        return 2
    print(json.dumps({"record": str(out), "status": status, "exit_code": exit_code}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
