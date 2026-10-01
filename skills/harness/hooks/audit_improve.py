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

import _bootstrap
import _fsutil
import _state

_bootstrap.ensure_paths()
from data_formats import DataFormatError, parse_yaml  # noqa: E402
from save_taxonomy import ACTIVE_STATUSES, TERMINAL_STATUSES  # noqa: E402

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


class AuditScan:
    """Everything one audit collects, so each record class is read by a function of its own (CR-18).

    The parts below (``_audit_roots`` to ``_audit_trajectories``) each read one class of
    record and add to this object; ``_assemble`` turns it into the report. Nothing here
    writes: every read is bounded and a damaged record is noted by class and reason,
    never echoed."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.deadline = time.monotonic() + AUDIT_TIME_BUDGET_SECONDS
        self.findings: list[dict] = []
        self.coverage: dict[str, object] = {"run_limit": MAX_RUNS, "phase_file_limit_per_run": MAX_PHASE_FILES,
                                            "trajectory_file_limit": MAX_TRAJECTORIES, "record_byte_limit": MAX_RECORD,
                                            "time_budget_seconds": AUDIT_TIME_BUDGET_SECONDS}
        self.saves = self.root / "skillset-saves"
        self.harness = self.root / ".harness-state"
        self.saves_ok = False
        self.harness_ok = False
        self.pointer_id: str | None = None
        self.run_dirs: list[Path] = []
        self.run_statuses: Counter[str] = Counter()
        self.audit_events: Counter[str] = Counter()
        self.verdicts: Counter[str] = Counter()
        self.unreadable: Counter[str] = Counter()
        self.record_errors: list[dict] = []
        self.run_history: list[dict] = []
        self.journal_count = 0
        self.truncated_audit_tails = 0
        self.guard_summary: dict[str, int] = {}
        self.observation_counts: dict[str, int] = {}
        self.trajectories_truncated = False
        self.failed_steps = 0
        self.empty_steps = 0
        self.repeated_failures = 0
        self.trajectory_history: list[dict] = []

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def note_unreadable(self, kind: str, error: str, *, run: str | None = None, trajectory: str | None = None) -> None:
        self.unreadable[kind + ":" + error] += 1
        if len(self.record_errors) >= MAX_FILES:
            self.coverage["record_errors_truncated"] = True
            return
        item = {"record": kind, "reason": error}
        if run is not None:
            item["run"] = run
        if trajectory is not None:
            item["trajectory"] = trajectory
        self.record_errors.append(item)


def _audit_roots(scan: AuditScan) -> None:
    """The two runtime roots: present, a directory, and not a link."""
    scan.saves_ok = scan.saves.is_dir() and not _is_link(scan.saves)
    scan.harness_ok = scan.harness.is_dir() and not _is_link(scan.harness)
    if not scan.saves_ok:
        scan.findings.append({"code": "save_root_missing", "severity": "Info", "count": 1})
    if not scan.harness_ok:
        scan.findings.append({"code": "harness_root_missing", "severity": "Info", "count": 1})


def _audit_pointer(scan: AuditScan) -> None:
    """The latest-run pointer, and the run list it has to point into."""
    saves = scan.saves
    pointer, pointer_error = _mapping_record(saves / "_latest.md") if scan.saves_ok else (None, "missing_or_symlink")
    if scan.saves_ok and (saves / "_latest.md").exists() and pointer_error:
        scan.findings.append({"code": "pointer_unreadable", "severity": "Major", "reason": pointer_error})
    pointer_id = pointer.get("run_id") if isinstance(pointer, dict) else None
    if pointer_id is not None and (not isinstance(pointer_id, str) or Path(pointer_id).name != pointer_id or pointer_id in {".", ".."}):
        scan.findings.append({"code": "pointer_run_id_invalid", "severity": "Major", "count": 1})
        pointer_id = None
    scan.pointer_id = pointer_id
    scan.run_dirs, runs_truncated = _run_dirs(scan.root, scan.deadline) if scan.saves_ok else ([], False)
    scan.coverage["runs_scanned"] = 0
    scan.coverage["runs_truncated"] = runs_truncated
    if runs_truncated:
        scan.findings.append({"code": "run_scan_truncated", "severity": "Info", "count": 1})
    if pointer_id and not any(path.name == pointer_id for path in scan.run_dirs) and not runs_truncated:
        scan.findings.append({"code": "pointer_target_missing", "severity": "Major", "count": 1})


def _audit_run_state(scan: AuditScan, run: Path, run_key: str) -> None:
    """A run's state and lock records: readable, a known status, the same revision."""
    state, state_error = _mapping_record(run / "_state.md")
    lock, lock_error = _mapping_record(run / "_lock.md")
    for kind, error in (("state", state_error), ("lock", lock_error)):
        if error:
            scan.note_unreadable(kind, error, run=run_key)
    if isinstance(state, dict):
        status = state.get("status")
        if isinstance(status, str) and status in ACTIVE_STATUSES | TERMINAL_STATUSES:
            scan.run_statuses[status] += 1
        else:
            scan.unreadable["state:invalid_status"] += 1
        if isinstance(lock, dict) and state.get("revision") != lock.get("revision"):
            scan.findings.append({"code": "revision_mismatch", "severity": "Major", "run": run_key})


def _audit_run_trail(scan: AuditScan, run: Path, run_key: str, run_events: Counter) -> None:
    """A run's audit trail, read from its tail: only failure-shaped event names are counted."""
    lines, error, tail_truncated = _tail_lines(run / "_audit-trail.md")
    scan.truncated_audit_tails += int(tail_truncated)
    if error:
        scan.note_unreadable("audit", error, run=run_key)
        return
    for line in lines:
        try:
            event = json.loads(line).get("event")
            if isinstance(event, str) and event in AUDIT_EVENTS:
                scan.audit_events[event] += 1
                run_events[event] += 1
        except (ValueError, AttributeError):
            scan.note_unreadable("audit", "invalid_line", run=run_key)


def _audit_run_verdicts(scan: AuditScan, run: Path, run_key: str, run_verdicts: Counter) -> None:
    """A run's gate verdict files: only the failing verdict names are counted."""
    phase_files, truncated = _files(run, max_files=MAX_PHASE_FILES, max_dirs=MAX_PHASE_DIRS, deadline=scan.deadline)
    if truncated:
        scan.coverage["phase_files_truncated"] = True
    for path in phase_files:
        if scan.expired():
            scan.coverage["time_truncated"] = True
            break
        if not path.name.startswith("verdict_") or path.suffix != ".json":
            continue
        value, error = _json_record(path)
        if error:
            scan.note_unreadable("verdict", error, run=run_key)
        elif isinstance(value, dict):
            verdict = value.get("verdict") or value.get("decision")
            if isinstance(verdict, str) and verdict.upper() in FAIL_VERDICTS:
                scan.verdicts[verdict.upper()] += 1
                run_verdicts[verdict.upper()] += 1


def _audit_run(scan: AuditScan, run: Path) -> None:
    """One run: its records, its publish journal, its audit trail and its verdicts."""
    scan.coverage["runs_scanned"] += 1
    run_key = _id(run.name)
    run_events: Counter[str] = Counter()
    run_verdicts: Counter[str] = Counter()
    run_record: dict[str, object] = {"run": run_key}
    _audit_run_state(scan, run, run_key)
    if (run / "_journal.json").exists():
        scan.journal_count += 1
        run_record["publish_journal"] = True
        scan.findings.append({"code": "publish_journal_present", "severity": "Major", "run": run_key})
    _audit_run_trail(scan, run, run_key, run_events)
    _audit_run_verdicts(scan, run, run_key, run_verdicts)
    if run_events:
        run_record["audit_events"] = dict(sorted(run_events.items()))
    if run_verdicts:
        run_record["gate_verdicts"] = dict(sorted(run_verdicts.items()))
    if len(run_record) > 1:
        scan.run_history.append(run_record)


def _audit_runs(scan: AuditScan) -> None:
    """Every listed run, until the time budget runs out."""
    for run in scan.run_dirs:
        if scan.expired():
            scan.coverage["time_truncated"] = True
            break
        _audit_run(scan, run)


def _audit_guard(scan: AuditScan) -> None:
    """The guard record, summarised as counts of live entries per boundary kind (never the globs)."""
    guard_path = scan.harness / "guard-state.json"
    if not (scan.harness_ok and guard_path.exists()):
        return
    guard, error = _json_record(guard_path)
    if error or not isinstance(guard, dict):
        scan.note_unreadable("guard", error or "wrong_shape")
        return
    for key in ("frozen_globs", "blocked_globs", "read_only"):
        entries = guard.get(key)
        if isinstance(entries, list):
            scan.guard_summary[key] = sum(1 for item in entries if isinstance(item, (str, dict))
                                          and not (isinstance(item, dict) and _state.is_released(item)))


def _audit_observations(scan: AuditScan) -> None:
    """The per-event hook observation counts; a linked observation directory is reported, not followed."""
    observations_dir = scan.harness / "observations"
    observations_ok = scan.harness_ok and not _is_link(observations_dir)
    if scan.harness_ok and _is_link(observations_dir):
        scan.findings.append({"code": "observation_root_symlink", "severity": "Major", "count": 1})
    for event in ("PreToolUse", "PostToolUse", "UserPromptSubmit"):
        path = observations_dir / (event + ".json")
        if not observations_ok or not path.exists():
            continue
        value, error = _json_record(path)
        if error or not isinstance(value, dict):
            scan.note_unreadable("observation", error or "wrong_shape")
            continue
        observed = value.get("observed")
        if isinstance(observed, dict) and isinstance(observed.get("count"), int):
            scan.observation_counts[event] = max(0, observed["count"])


def _audit_trajectory(scan: AuditScan, path: Path) -> None:
    """One trajectory file: its last 40 steps, counted as failed, empty and repeatedly failing."""
    value, error = _json_record(path)
    if error or not isinstance(value, list):
        scan.note_unreadable("trajectory", error or "wrong_shape", run=_id(path.parent.name), trajectory=_id(path.name))
        return
    previous = None
    file_failed = file_empty = file_repeated = 0
    for entry in value[-40:]:
        if not isinstance(entry, dict):
            continue
        failed = entry.get("failed") is True
        scan.failed_steps += int(failed)
        scan.empty_steps += int(entry.get("empty") is True)
        file_failed += int(failed)
        file_empty += int(entry.get("empty") is True)
        sig = entry.get("sig") if isinstance(entry.get("sig"), str) else None
        if failed and sig and sig == previous:
            scan.repeated_failures += 1
            file_repeated += 1
        previous = sig if failed else None
    if file_failed or file_repeated:
        scan.trajectory_history.append({"run": _id(path.parent.name), "trajectory": _id(path.name), "failed_steps": file_failed,
                                        "empty_steps": file_empty, "consecutive_failed_signatures": file_repeated})


def _audit_trajectories(scan: AuditScan) -> None:
    """The per-session trajectory files, bounded in count and time."""
    trajectory_files, scan.trajectories_truncated = (
        _files(scan.harness / "trajectories", max_files=MAX_TRAJECTORIES, deadline=scan.deadline) if scan.harness_ok else ([], False))
    for path in trajectory_files:
        if scan.expired():
            scan.coverage["time_truncated"] = True
            break
        if path.suffix == ".json":
            _audit_trajectory(scan, path)
    scan.coverage["trajectory_files_scanned"] = len(trajectory_files)
    scan.coverage["trajectories_truncated"] = scan.trajectories_truncated


def _assemble(scan: AuditScan) -> dict:
    """The report: the findings the whole scan implies, in a fixed order, and the fixed envelope."""
    if scan.expired():
        scan.coverage["time_truncated"] = True
    if scan.coverage.get("time_truncated"):
        scan.findings.append({"code": "audit_time_truncated", "severity": "Info", "count": 1})
    if scan.trajectories_truncated:
        scan.findings.append({"code": "trajectory_scan_truncated", "severity": "Info", "count": 1})
    if scan.unreadable:
        scan.findings.append({"code": "unreadable_records", "severity": "Major", "counts": dict(sorted(scan.unreadable.items()))})
    if scan.audit_events or scan.verdicts or scan.failed_steps:
        scan.findings.append({"code": "failure_history", "severity": "Info", "audit_events": dict(sorted(scan.audit_events.items())),
                              "gate_verdicts": dict(sorted(scan.verdicts.items())), "failed_steps": scan.failed_steps,
                              "empty_steps": scan.empty_steps, "consecutive_failed_signatures": scan.repeated_failures})
    if scan.journal_count:
        scan.coverage["publish_journals"] = scan.journal_count
    if scan.truncated_audit_tails:
        scan.coverage["audit_tails_truncated"] = scan.truncated_audit_tails
        scan.findings.append({"code": "audit_tail_truncated", "severity": "Info", "count": scan.truncated_audit_tails})
    return {"schema_version": 1, "kind": "supremeteam-audit-improve", "read_only": True,
            "coverage": scan.coverage, "run_statuses": dict(sorted(scan.run_statuses.items())),
            "guard_state": scan.guard_summary, "hook_observations": scan.observation_counts,
            "run_history": scan.run_history, "trajectory_history": scan.trajectory_history,
            "record_errors": scan.record_errors,
            "findings": scan.findings,
            "handoff": "The read-only audit may run directly. Correlate these counts with source and run evidence. Route a supported improvement through admiral and skill-maker for a reviewed proposal. Do not infer a defective skill from a count alone or mutate saved state from this report."}


def audit(root: Path) -> dict:
    """Return bounded, content-redacted evidence from the two runtime roots."""
    scan = AuditScan(root)
    _audit_roots(scan)
    _audit_pointer(scan)
    _audit_runs(scan)
    _audit_guard(scan)
    _audit_observations(scan)
    _audit_trajectories(scan)
    return _assemble(scan)


def maybe_audit(root: Path | None = None, *, force: bool = False, now: float | None = None) -> dict | None:
    """Return actionable evidence at most once per cooldown window.

    ``force`` is for an explicit user trigger and bypasses the cooldown without
    writing a marker. Automatic calls write only a small timestamp under the
    harness-observations ownership class, never a run or skill record.
    """
    if root is None:
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
            _fsutil.atomic_write(marker, json.dumps({"last_at": moment}))
        except OSError:
            pass  # no marker only means the next call may audit again
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
