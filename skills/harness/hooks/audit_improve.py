#!/usr/bin/env python3
"""Read-only harness evidence audit and explicit skill-maker handoff.

Manual: python audit_improve.py --run --project-root PROJECT
Hook:   invoked by the registered ``user_prompt_submit.py`` and ``post_tool_use.py`` hooks.

The hook does not execute an AI skill, edit a skill, or repair saved state. It
supplies bounded facts and a routing instruction to the host agent. A missing or
bad record is evidence to investigate, never authority to overwrite that record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from _saves import ACTIVE_STATUSES, TERMINAL_STATUSES, DataFormatError, parse_yaml

MAX_FILES = 240
MAX_DIRS = 80
MAX_RECORD = 256 * 1024
MAX_AUDIT_TAIL = 256 * 1024
MAX_RUNS = 24
MAX_TRAJECTORIES = 80
MAX_PHASE_FILES = 80
MAX_PHASE_DIRS = 20
AUDIT_TIME_BUDGET_SECONDS = 2.0
COOLDOWN_SECONDS = 6 * 3600
# Failure-shaped events of the save writer's trail; `refused` and `degraded` are
# the lines save_run.py appends for an operation it refused or could not finish.
AUDIT_EVENTS = {"refused", "degraded", "pointer-degraded", "rollforward", "rollback", "recover", "blocked", "reopen"}
FAIL_VERDICTS = {"REVISE", "ESCALATE", "BLOCKED", "FAIL", "FAILED"}
TRIGGER = "/audit-improve"


def _id(value: object) -> str:
    """Stable local correlation key; do not echo run names or error payloads."""
    return hashlib.sha256(str(value).encode("utf-8", "replace")).hexdigest()[:12]


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())
    except OSError:
        return True


def _json_record(path: Path) -> tuple[dict | list | None, str | None]:
    try:
        if _is_link(path) or not path.is_file():
            return None, "missing_or_symlink"
        if path.stat().st_size > MAX_RECORD:
            return None, "too_large"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, (dict, list)):
            return None, "wrong_shape"
        return value, None
    except (OSError, UnicodeError, ValueError):
        return None, "unreadable_or_invalid"


def _mapping_record(path: Path) -> tuple[dict | None, str | None]:
    """Read canonical JSON-or-YAML run records via the shared format parser."""
    try:
        if _is_link(path) or not path.is_file():
            return None, "missing_or_symlink"
        if path.stat().st_size > MAX_RECORD:
            return None, "too_large"
        value = parse_yaml(path.read_text(encoding="utf-8"))
        return (value, None) if isinstance(value, dict) else (None, "wrong_shape")
    except (OSError, UnicodeError, DataFormatError):
        return None, "unreadable_or_invalid"


def _tail_lines(path: Path) -> tuple[list[str], str | None, bool]:
    try:
        if _is_link(path) or not path.is_file():
            return [], "missing_or_symlink", False
        with path.open("rb") as handle:
            size = path.stat().st_size
            start = max(0, size - MAX_AUDIT_TAIL)
            handle.seek(start)
            data = handle.read(MAX_AUDIT_TAIL)
        lines = data.decode("utf-8", "replace").splitlines()
        return (lines[1:] if start else lines), None, start > 0
    except OSError:
        return [], "unreadable", False


def _files(directory: Path, *, max_files: int = MAX_FILES, max_dirs: int = MAX_DIRS, deadline: float | None = None):
    """Stream entries without following links or materializing a huge directory."""
    if _is_link(directory) or not directory.is_dir():
        return [], False
    found: list[Path] = []
    seen_dirs = 0
    seen_entries = 0
    truncated = False
    pending = [directory]
    while pending:
        if deadline is not None and time.monotonic() >= deadline:
            truncated = True
            break
        base = pending.pop()
        seen_dirs += 1
        if seen_dirs > max_dirs:
            truncated = True
            break
        try:
            with os.scandir(base) as entries:
                for entry in entries:
                    if deadline is not None and time.monotonic() >= deadline:
                        truncated = True
                        return found, truncated
                    seen_entries += 1
                    if seen_entries > max_files + max_dirs:
                        truncated = True
                        return found, truncated
                    path = Path(entry.path)
                    if _is_link(path):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        pending.append(path)
                    elif entry.is_file(follow_symlinks=False):
                        if len(found) >= max_files:
                            truncated = True
                            return found, truncated
                        found.append(path)
        except OSError:
            truncated = True
    return found, truncated


def _run_dirs(root: Path, deadline: float) -> tuple[list[Path], bool]:
    saves = root / "skillset-saves"
    runs = saves / "runs"
    if _is_link(saves) or _is_link(runs) or not runs.is_dir():
        return [], False
    result: list[Path] = []
    truncated = False
    try:
        with os.scandir(runs) as entries:
            for index, entry in enumerate(entries):
                if index >= MAX_FILES or time.monotonic() >= deadline:
                    truncated = True
                    break
                if entry.is_dir(follow_symlinks=False) and not entry.is_symlink():
                    if len(result) == MAX_RUNS:
                        truncated = True
                        break
                    result.append(Path(entry.path))
    except OSError:
        truncated = True
    return sorted(result, key=lambda p: p.name), truncated


def audit(root: Path) -> dict:
    """Return bounded, content-redacted evidence from the two runtime roots."""
    root = root.resolve()
    deadline = time.monotonic() + AUDIT_TIME_BUDGET_SECONDS
    findings: list[dict] = []
    coverage: dict[str, object] = {"run_limit": MAX_RUNS, "phase_file_limit_per_run": MAX_PHASE_FILES,
                                   "trajectory_file_limit": MAX_TRAJECTORIES, "record_byte_limit": MAX_RECORD,
                                   "time_budget_seconds": AUDIT_TIME_BUDGET_SECONDS}
    saves = root / "skillset-saves"
    harness = root / ".harness-state"
    saves_ok = saves.is_dir() and not _is_link(saves)
    harness_ok = harness.is_dir() and not _is_link(harness)
    if not saves_ok:
        findings.append({"code": "save_root_missing", "severity": "Info", "count": 1})
    if not harness_ok:
        findings.append({"code": "harness_root_missing", "severity": "Info", "count": 1})

    pointer, pointer_error = _mapping_record(saves / "_latest.md") if saves_ok else (None, "missing_or_symlink")
    if saves_ok and (saves / "_latest.md").exists() and pointer_error:
        findings.append({"code": "pointer_unreadable", "severity": "Major", "reason": pointer_error})
    pointer_id = pointer.get("run_id") if isinstance(pointer, dict) else None
    if pointer_id is not None and (not isinstance(pointer_id, str) or Path(pointer_id).name != pointer_id or pointer_id in {".", ".."}):
        findings.append({"code": "pointer_run_id_invalid", "severity": "Major", "count": 1})
        pointer_id = None
    run_dirs, runs_truncated = _run_dirs(root, deadline) if saves_ok else ([], False)
    coverage["runs_scanned"] = 0
    coverage["runs_truncated"] = runs_truncated
    if runs_truncated:
        findings.append({"code": "run_scan_truncated", "severity": "Info", "count": 1})
    if pointer_id and not any(path.name == pointer_id for path in run_dirs) and not runs_truncated:
        findings.append({"code": "pointer_target_missing", "severity": "Major", "count": 1})

    run_statuses: Counter[str] = Counter()
    audit_events: Counter[str] = Counter()
    verdicts: Counter[str] = Counter()
    unreadable: Counter[str] = Counter()
    record_errors: list[dict] = []
    def note_unreadable(kind: str, error: str, *, run: str | None = None,
                        trajectory: str | None = None) -> None:
        unreadable[kind + ":" + error] += 1
        if len(record_errors) >= MAX_FILES:
            coverage["record_errors_truncated"] = True
            return
        item = {"record": kind, "reason": error}
        if run is not None:
            item["run"] = run
        if trajectory is not None:
            item["trajectory"] = trajectory
        record_errors.append(item)
    run_history: list[dict] = []
    journal_count = 0
    truncated_audit_tails = 0
    for run in run_dirs:
        if time.monotonic() >= deadline:
            coverage["time_truncated"] = True
            break
        coverage["runs_scanned"] += 1
        run_key = _id(run.name)
        run_events: Counter[str] = Counter()
        run_verdicts: Counter[str] = Counter()
        run_record: dict[str, object] = {"run": run_key}
        state, state_error = _mapping_record(run / "_state.md")
        lock, lock_error = _mapping_record(run / "_lock.md")
        for kind, error in (("state", state_error), ("lock", lock_error)):
            if error:
                note_unreadable(kind, error, run=run_key)
        if isinstance(state, dict):
            status = state.get("status")
            if isinstance(status, str) and status in ACTIVE_STATUSES | TERMINAL_STATUSES:
                run_statuses[status] += 1
            else:
                unreadable["state:invalid_status"] += 1
            if isinstance(lock, dict) and state.get("revision") != lock.get("revision"):
                findings.append({"code": "revision_mismatch", "severity": "Major", "run": run_key})
        if (run / "_journal.json").exists():
            journal_count += 1
            run_record["publish_journal"] = True
            findings.append({"code": "publish_journal_present", "severity": "Major", "run": run_key})
        lines, error, tail_truncated = _tail_lines(run / "_audit-trail.md")
        truncated_audit_tails += int(tail_truncated)
        if error:
            note_unreadable("audit", error, run=run_key)
        else:
            for line in lines:
                try:
                    event = json.loads(line).get("event")
                    if isinstance(event, str) and event in AUDIT_EVENTS:
                        audit_events[event] += 1
                        run_events[event] += 1
                except (ValueError, AttributeError):
                    note_unreadable("audit", "invalid_line", run=run_key)
        phase_files, truncated = _files(run, max_files=MAX_PHASE_FILES, max_dirs=MAX_PHASE_DIRS, deadline=deadline)
        if truncated:
            coverage["phase_files_truncated"] = True
        for path in phase_files:
            if time.monotonic() >= deadline:
                coverage["time_truncated"] = True
                break
            if not path.name.startswith("verdict_") or path.suffix != ".json":
                continue
            value, error = _json_record(path)
            if error:
                note_unreadable("verdict", error, run=run_key)
            elif isinstance(value, dict):
                verdict = value.get("verdict") or value.get("decision")
                if isinstance(verdict, str) and verdict.upper() in FAIL_VERDICTS:
                    verdicts[verdict.upper()] += 1
                    run_verdicts[verdict.upper()] += 1
        if run_events:
            run_record["audit_events"] = dict(sorted(run_events.items()))
        if run_verdicts:
            run_record["gate_verdicts"] = dict(sorted(run_verdicts.items()))
        if len(run_record) > 1:
            run_history.append(run_record)

    guard_summary: dict[str, int] = {}
    guard_path = harness / "guard-state.json"
    if harness_ok and guard_path.exists():
        guard, error = _json_record(guard_path)
        if error or not isinstance(guard, dict):
            note_unreadable("guard", error or "wrong_shape")
        else:
            for key in ("frozen_globs", "blocked_globs", "read_only"):
                entries = guard.get(key)
                if isinstance(entries, list):
                    guard_summary[key] = sum(1 for item in entries if isinstance(item, (str, dict))
                                             and not (isinstance(item, dict) and item.get("released_at")))
    observation_counts: dict[str, int] = {}
    observations_dir = harness / "observations"
    observations_ok = harness_ok and not _is_link(observations_dir)
    if harness_ok and _is_link(observations_dir):
        findings.append({"code": "observation_root_symlink", "severity": "Major", "count": 1})
    for event in ("PreToolUse", "PostToolUse", "UserPromptSubmit"):
        path = observations_dir / (event + ".json")
        if not observations_ok or not path.exists():
            continue
        value, error = _json_record(path)
        if error or not isinstance(value, dict):
            note_unreadable("observation", error or "wrong_shape")
            continue
        observed = value.get("observed")
        if isinstance(observed, dict) and isinstance(observed.get("count"), int):
            observation_counts[event] = max(0, observed["count"])

    trajectories = harness / "trajectories"
    trajectory_files, trajectories_truncated = (
        _files(trajectories, max_files=MAX_TRAJECTORIES, deadline=deadline) if harness_ok else ([], False))
    failed_steps = empty_steps = repeated_failures = 0
    trajectory_history: list[dict] = []
    for path in trajectory_files:
        if time.monotonic() >= deadline:
            coverage["time_truncated"] = True
            break
        if path.suffix != ".json":
            continue
        value, error = _json_record(path)
        if error or not isinstance(value, list):
            note_unreadable("trajectory", error or "wrong_shape", run=_id(path.parent.name),
                            trajectory=_id(path.name))
            continue
        previous = None
        file_failed = file_empty = file_repeated = 0
        for entry in value[-40:]:
            if not isinstance(entry, dict):
                continue
            failed = entry.get("failed") is True
            failed_steps += int(failed)
            empty_steps += int(entry.get("empty") is True)
            file_failed += int(failed)
            file_empty += int(entry.get("empty") is True)
            sig = entry.get("sig") if isinstance(entry.get("sig"), str) else None
            if failed and sig and sig == previous:
                repeated_failures += 1
                file_repeated += 1
            previous = sig if failed else None
        if file_failed or file_repeated:
            trajectory_history.append({"run": _id(path.parent.name),
                                       "trajectory": _id(path.name),
                                       "failed_steps": file_failed,
                                       "empty_steps": file_empty,
                                       "consecutive_failed_signatures": file_repeated})
    coverage["trajectory_files_scanned"] = len(trajectory_files)
    coverage["trajectories_truncated"] = trajectories_truncated
    if time.monotonic() >= deadline:
        coverage["time_truncated"] = True
    if coverage.get("time_truncated"):
        findings.append({"code": "audit_time_truncated", "severity": "Info", "count": 1})
    if trajectories_truncated:
        findings.append({"code": "trajectory_scan_truncated", "severity": "Info", "count": 1})
    if unreadable:
        findings.append({"code": "unreadable_records", "severity": "Major", "counts": dict(sorted(unreadable.items()))})
    if audit_events or verdicts or failed_steps:
        findings.append({"code": "failure_history", "severity": "Info", "audit_events": dict(sorted(audit_events.items())),
                         "gate_verdicts": dict(sorted(verdicts.items())), "failed_steps": failed_steps,
                         "empty_steps": empty_steps, "consecutive_failed_signatures": repeated_failures})
    if journal_count:
        coverage["publish_journals"] = journal_count
    if truncated_audit_tails:
        coverage["audit_tails_truncated"] = truncated_audit_tails
        findings.append({"code": "audit_tail_truncated", "severity": "Info", "count": truncated_audit_tails})
    return {"schema_version": 1, "kind": "supremeteam-audit-improve", "read_only": True,
            "coverage": coverage, "run_statuses": dict(sorted(run_statuses.items())),
            "guard_state": guard_summary, "hook_observations": observation_counts,
            "run_history": run_history, "trajectory_history": trajectory_history,
            "record_errors": record_errors,
            "findings": findings,
            "handoff": "The read-only audit may run directly. Correlate these counts with source and run evidence. Route a supported improvement through admiral and skill-maker for a reviewed proposal. Do not infer a defective skill from a count alone or mutate saved state from this report."}


def maybe_audit(root: Path | None = None, *, force: bool = False, now: float | None = None) -> dict | None:
    """Return actionable evidence at most once per cooldown window.

    ``force`` is for an explicit user trigger and bypasses the cooldown without
    writing a marker. Automatic calls write only a small timestamp under the
    harness-observations ownership class, never a run or skill record.
    """
    if root is None:
        import _state
        root = _state.project_root()
    root = Path(root).resolve()
    moment = time.time() if now is None else now
    marker = root / ".harness-state" / "observations" / "audit-improve.json"
    if not force:
        prior, error = _json_record(marker)
        if error is None and isinstance(prior, dict):
            last = prior.get("last_at")
            if isinstance(last, (float, int)) and 0 <= moment - last < COOLDOWN_SECONDS:
                return None
    report = audit(root)
    if not force:
        history = next((f for f in report["findings"] if f["code"] == "failure_history"), None)
        failures = history.get("failed_steps", 0) if history else 0
        bad_verdicts = sum(history.get("gate_verdicts", {}).values()) if history else 0
        major = any(f["severity"] == "Major" for f in report["findings"])
        incomplete = any(report["coverage"].get(key) for key in (
            "runs_truncated", "phase_files_truncated", "trajectories_truncated",
            "time_truncated", "audit_tails_truncated"))
        if not (major or failures >= 3 or bad_verdicts or incomplete):
            return None
        try:
            if _is_link(root / ".harness-state") or _is_link(marker.parent):
                return report
            marker.parent.mkdir(parents=True, exist_ok=True)
            if _is_link(marker):
                return report
            temp = marker.with_name(marker.name + f".{os.getpid()}.tmp")
            temp.write_text(json.dumps({"last_at": moment}), encoding="utf-8")
            os.replace(temp, marker)
        except OSError:
            pass
    return report


def advisory_for(report: dict) -> str:
    """Short host-safe routing context; no raw error text or source payloads."""
    codes = ", ".join(item["code"] for item in report["findings"][:8]) or "no anomaly found"
    return ("SupremeTeam audit-improve trigger: read-only runtime audit completed. "
            f"Runs scanned: {report['coverage']['runs_scanned']}; findings: {codes}. "
            "Use skills/audit-improve/SKILL.md for direct read-only review. Route a supported "
            "improvement through admiral and skill-maker for source-verified development and review. The audit did not edit skills or run records. "
            "Run `python skills/harness/hooks/audit_improve.py --run` for full redacted JSON evidence.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="print a read-only JSON audit")
    parser.add_argument("--project-root", type=Path, help="project root (default: discovered from cwd or host variable)")
    args = parser.parse_args()
    if args.project_root:
        root = args.project_root
    else:
        import _state
        root = _state.project_root()
    if args.run:
        print(json.dumps(audit(root), sort_keys=True))
        return
    try:
        payload = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        return
    if not isinstance(payload, dict):
        return
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or prompt.strip().split(maxsplit=1)[0:1] != [TRIGGER]:
        return
    report = maybe_audit(root, force=True)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": advisory_for(report)}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if "--run" in sys.argv:
            print(json.dumps({"error": "audit_unavailable", "reason": type(exc).__name__}), file=sys.stderr)
            sys.exit(1)
        # Host hooks fail open without disclosing raw runtime records.
        sys.exit(0)
