#!/usr/bin/env python3
"""
Trajectory Regulation hook (LIFE-HARNESS Layer 4) for Supreme Team.

Runs as a host ``PostToolUse``/post-tool hook. It watches the evolving trajectory
for degenerate, non-progressing patterns and injects a recovery hint as
additional context — the deterministic, per-step expression of the coarse-grained
trajectory control that gatekeepers and session-memory already provide.

Detected patterns (all mechanically certain from trajectory signatures, per
the doctrine's Principles heading — never from guessed intent):
  - repeated identical FAILING command (>= 3 times)
  - empty-output streak (>= 3 consecutive empty results)
  - two-state oscillation (A,B,A,B over the last four steps)

It also runs one mechanical repair after a command action: the coverage-residue
sweep (see `_sweep_coverage_residue`). Coverage data belongs to the run's
`evidence/coverage/`, so a step that leaves `.coverage`, `.coverage.*`,
`htmlcov/`, or `.nyc_output/` at the project root has its residue relocated
there on the very next tool call instead of accumulating — the observed failure
was a `.coverage` tree of over 3000 files in under two minutes.

The sweep is a write, so it obeys the same boundaries as any other: it moves nothing
inside a frozen or blocked glob, nothing at all outside a read-only run's allow list,
and it files residue under a run only while that run is active. The one subprocess it
starts (`coverage combine`) runs with no project directory on its import path.

Contract: prints the PostToolUse additionalContext envelope to
stdout and exits 0. On any internal error it exits 0 silently (fail open) and counts
the fault by type in the hook's observation record (`_state.record_fault`). It
never blocks — by definition the action already executed.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import _bootstrap
import _paths
import _state

_REPEAT_FAIL_THRESHOLD = 3
_EMPTY_STREAK_THRESHOLD = 3

# Command tools, matched case-insensitively. The sweep repairs residue a *shell
# step* left behind, so it runs only for these (README "Matcher scope"); an
# Edit/Write/Read post-tool event never writes a coverage data file.
_COMMAND_TOOLS = {"bash", "powershell", "shell"}

# Bounded work per call: at most this many project-root entries are examined and
# relocated. The cap is stated in the hint so a truncated sweep is never read as
# a clean root.
_RESIDUE_CAP = 5000
# Residue directories that are not named `.coverage*`.
_RESIDUE_DIRS = ("htmlcov", ".nyc_output")
# Never relocate anything out of the two generated roots: they are the
# destination, not the residue.
_GENERATED_ROOTS = ("skillset-saves", ".harness-state")
# Fallback when save-ownership.yaml cannot be read; `build` is the default phase.
_FALLBACK_PHASES = ("build", "qa", "review", "security", "investigation", "design",
                    "redesign", "intake", "taste", "delivery", "release", "skill-creation")
_DEFAULT_PHASE = "build"

_COVERAGE_RULE = (
    "Coverage data is run evidence, not project-root residue: resolve the destination with "
    "`python skills/scripts/output_paths.py --kind coverage --run-id <run> --phase <phase> "
    "--name .coverage --mkdir`, then point COVERAGE_FILE / --data-file / "
    "--cov-report=<fmt>:<dest>/... / --report-dir + --temp-dir / --coverage.reportsDirectory "
    "at it. Never run coverage in parallel or per-process mode (-p, --parallel-mode, "
    "parallel = True) unless the same command finishes with `coverage combine` into that "
    "destination, and never loop coverage per test file."
)


def _signature(tool_name: str, tool_input: dict) -> str:
    key = str(tool_name)
    if isinstance(tool_input, dict):
        # Fold in command + file_path, plus the edit payload so two *different*
        # edits to the same file do not collapse to one signature (which would
        # otherwise feed false repeat/oscillation signals if Edit/Write are ever
        # added to the post matcher — see README "Matcher scope").
        key += (
            "|" + str(tool_input.get("command", ""))
            + "|" + str(tool_input.get("file_path", ""))
            + "|" + str(tool_input.get("new_string", ""))
        )
    return hashlib.sha256(key.encode("utf-8", "ignore")).hexdigest()[:16]


def _response_text(data: dict) -> str:
    resp = data.get("tool_response", "")
    if isinstance(resp, dict):
        # Common shapes: {"stdout":..,"stderr":..} or {"output":..} or {"content":..}
        return " ".join(
            str(resp.get(k, "")) for k in ("stdout", "stderr", "output", "content", "error")
        )
    return str(resp or "")


def _explicit_failure(data: dict):
    """Read a mechanically certain success/failure signal from the structured
    tool_response if one is present. Returns True (failed), False (succeeded), or
    None (no structured signal — caller falls back to the text heuristic).

    This is the doctrine's "mechanically certain" Principles path: when the host reports an
    exit code or success flag, trust it instead of guessing from output text.
    """
    resp = data.get("tool_response")
    if not isinstance(resp, dict):
        return None
    for k in ("exit_code", "exitCode", "returncode", "returnCode", "code", "status"):
        v = resp.get(k)
        if isinstance(v, bool):
            continue  # a bool here is ambiguous; skip to the success-flag keys
        if isinstance(v, int):
            return v != 0
    for k in ("success", "ok"):
        if isinstance(resp.get(k), bool):
            return not resp[k]
    if resp.get("is_error") is True or resp.get("isError") is True:
        return True
    return None


# Anchored, multi-token failure markers. Deliberately specific so a *successful*
# command whose output merely contains "error"/"failed"/"warning" (e.g.
# "0 errors", a file named error_handler.py, "0 failed") does NOT register as a
# failure. Used only when no structured exit/success signal is available.
_FAILURE_MARKERS = (
    "traceback (most recent call last)",
    "command not found",
    "no such file or directory",
    "permission denied",
    "fatal:",
    "segmentation fault",
    "modulenotfounderror",
    "syntaxerror:",
    "unrecognized arguments",
    "is not recognized as",          # cmd/PowerShell
    "cannot find path",              # PowerShell
    "the term '",                    # PowerShell "is not recognized" preamble
)


def _looks_failed(text: str) -> bool:
    t = text.lower()
    return any(marker in t for marker in _FAILURE_MARKERS)


def _envelope(context: str) -> str:
    return json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    })


# Set by main() before the trajectory patterns are evaluated, so a sweep hint is
# never lost behind a recovery hint that exits first.
_pending_coverage_hint: "str | None" = None
_pending_maintenance_hints: list[str] = []


def _emit(hint: str) -> None:
    context = "[harness:trajectory-regulation] " + hint
    if _pending_coverage_hint:
        context += "\n" + _pending_coverage_hint
    if _pending_maintenance_hints:
        context += "\n" + "\n".join(_pending_maintenance_hints)
    print(_envelope(context))
    sys.exit(0)


# --- Coverage residue sweep ---------------------------------------------------


def _is_residue(name: str) -> bool:
    """True for the coverage residue classes, matched by name at the project root.

    `.coverage` is a file in serial mode and a directory under some runners;
    `.coverage.<host>.<pid>.<rand>` is one fragment per process in parallel mode
    (the signature of the observed explosion); `htmlcov/` and `.nyc_output/` are
    the HTML report and the JS per-worker temp tree.
    """
    return name == ".coverage" or name.startswith(".coverage.") or name in _RESIDUE_DIRS


def _inside_boundary(entry: Path, root: Path, globs: list) -> bool:
    """True when `entry` lies inside a frozen or blocked glob.

    The sweep moves files, which is a write, so it obeys exactly the boundary
    `pre_tool_use.py` would enforce against a manual `mv`: the same canonical
    path matching, so one boundary definition governs both the block and the sweep.
    """
    if not globs:
        return False
    target = _paths.locate(str(entry), root)
    return any(_paths.Boundary(glob, root).matches(target) for glob in globs)


def _phase_directories(catalog_root: Path) -> list:
    """Declared phase directories from save-ownership.yaml; falls back on error (and counts the fault)."""
    try:
        _bootstrap.ensure_paths()
        from data_formats import parse_yaml

        data = parse_yaml((catalog_root / "save-ownership.yaml").read_text(encoding="utf-8"))
        declared = [str(p) for p in (data.get("phase_directories") or []) if p]
        return declared or list(_FALLBACK_PHASES)
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)
        return list(_FALLBACK_PHASES)


def _run_phase(run_dir: Path, phases: list) -> str:
    """Map the run's recorded phase_state onto a declared phase directory.

    `_state.md` carries `phase_state: BUILD_ACTIVE`, `REDESIGN_GATE_PENDING`, and
    similar. The longest declared directory the normalised value starts with wins,
    so `redesign-...` never collapses to `design`. Anything unrecognised — a
    dispute state, a missing field, an unreadable record — is `build`, the phase
    that runs tests.
    """
    try:
        state = _state.read_mapping(run_dir / "_state.md") or {}
        marker = str(state.get("phase_state") or state.get("phase") or "").strip().lower().replace("_", "-")
        if marker:
            for phase in sorted(phases, key=len, reverse=True):
                if marker == phase or marker.startswith(phase + "-"):
                    return phase
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)
    return _DEFAULT_PHASE if _DEFAULT_PHASE in phases else (phases[0] if phases else _DEFAULT_PHASE)


def _active_run(root: Path) -> str:
    """The id of the run that owns this project right now, or '' when none does.

    Active means what the rest of the harness means by it (``_saves.inspect_saves``): a
    coherent run with a fresh lock, either pinned by the pointer or the only held run. A
    pointer that still names a run which has completed, been released or blocked, or
    whose lock went stale, does not make that run the owner of new evidence."""
    try:
        _bootstrap.ensure_paths()
        from _saves import inspect_saves

        found = inspect_saves(root)
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)
        return ""
    run_id = str(found.get("run_id") or "")
    if found.get("status") in ("active", "orphaned") and run_id and Path(run_id).name == run_id and run_id not in {".", ".."}:
        return run_id
    return ""


def _destination(root: Path) -> tuple:
    """Return ``(destination, relative_label, scoped)``.

    Scoped means an active run owns the residue: it lands in that run's
    `<phase>/evidence/coverage/`. With no active run (none at all, or only a closed
    one) the residue goes to the declared scratch class
    `.harness-state/test-work/coverage-residue/<ts>/` — relocated, never deleted, and
    never gate evidence. The label is shown to the model, so a run name is
    neutralised and capped first (`_state.safe_text`).
    """
    run_id = _active_run(root)
    if run_id:
        run_dir = root / "skillset-saves" / "runs" / run_id
        if run_dir.is_dir():
            catalog_root = Path(__file__).resolve().parents[2]
            phase = _run_phase(run_dir, _phase_directories(catalog_root))
            dest = run_dir / phase / "evidence" / "coverage"
            return dest, f"skillset-saves/runs/{_state.safe_text(run_id, 60)}/{_state.safe_text(phase, 40)}/evidence/coverage", True
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = root / ".harness-state" / "test-work" / "coverage-residue" / stamp
    return dest, f".harness-state/test-work/coverage-residue/{stamp}", False


def _unique(dest: Path, name: str) -> Path:
    """A free destination path for `name`; an earlier sweep's file is never overwritten."""
    target = dest / name
    index = 1
    while target.exists():
        target = dest / f"{name}.moved-{index}"
        index += 1
        if index > 1000:
            return dest / f"{name}.moved-{os.getpid()}-{int(time.time())}"
    return target


def _count_files(path: Path) -> int:
    if path.is_file():
        return 1
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += 1
            if total >= _RESIDUE_CAP:
                break
    except Exception:
        pass
    return total


def _combine(dest: Path, fragments: int) -> bool:
    """Combine relocated `.coverage.*` fragments into one data file in `dest`.

    Only with `--keep`, so the relocated fragments survive the combine: the sweep never
    destroys data it moved. The child is started the way a program run by a hook with
    someone else's files around it must be: `-P` keeps the current and script directories
    off `sys.path` (a `coverage.py` or `coverage/` planted in the destination would
    otherwise run with the hook's authority), the working directory is the interpreter's
    own directory so no `.coveragerc` or `pyproject.toml` from the project is read, and
    the fragments are named by path instead of found by the working directory. Whether
    `coverage` is installed is answered by the child itself: not installed is a plain
    False, the hint then says the fragments were not combined.
    """
    if fragments < 2:
        return False
    try:
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(dest / ".coverage")
        args = [sys.executable]
        if sys.version_info >= (3, 11):
            args.append("-P")
        args += ["-m", "coverage", "combine", "--keep"]
        if (dest / ".coverage").exists():
            args.append("--append")
        args.append(str(dest))
        done = subprocess.run(args, cwd=str(Path(sys.executable).parent), env=env, capture_output=True, text=True, timeout=60)
        return done.returncode == 0
    except Exception:
        return False  # a missing interpreter or a timeout is a failed combine, which the hint reports


def _scan_root(root: Path) -> tuple:
    """The residue entries at the project root and whether the bounded scan stopped early."""
    entries = []
    truncated = False
    for scanned, entry in enumerate(root.iterdir(), start=1):
        if scanned > _RESIDUE_CAP:
            truncated = True
            break
        if entry.name not in _GENERATED_ROOTS and _is_residue(entry.name):
            entries.append(entry)
    return entries, truncated


def _held_by_read_only(entries: list, dest: Path, records: list, root: Path) -> list:
    """The entries a read-only run may not move.

    A move deletes at the project root and creates in the destination, so both ends must
    lie inside the run's allow list (the same list the guard enforces, `read_only_allow`).
    """
    allow = _state.read_only_allow(records)
    fold = _paths.case_insensitive_fs()

    def writable(entry: Path) -> bool:
        return all(_paths.inside_allowed(_paths.locate(str(end), root), allow, root, fold=fold) for end in (entry, dest / entry.name))

    return [entry for entry in entries if not writable(entry)]


def _plural(count: int, one: str, many: str) -> str:
    return one if count == 1 else many


def _names(entries: list) -> str:
    return ", ".join(sorted({e.name if not e.name.startswith(".coverage.") else ".coverage.*" for e in entries}))


def _read_only_runs(records: list) -> str:
    return ", ".join(_state.safe_text(r.get("run_id", "?"), 40) for r in records if isinstance(r, dict)) or "?"


def _sweep_coverage_residue(tool_name: str) -> "str | None":
    """Relocate project-root coverage residue into the run. Never raises.

    Guarantees: bounded to `_RESIDUE_CAP` entries; silent when the root is clean;
    never touches `skillset-saves/` or `.harness-state/` themselves; never moves
    anything inside a frozen or blocked glob, nor anything a read-only run may not
    change (those are left in place and the hint says so); never deletes.
    """
    if str(tool_name or "").strip().lower() not in _COMMAND_TOOLS:
        return None
    try:
        root = _state.project_root().resolve()
        entries, truncated = _scan_root(root)
        if not entries:
            return None
        guard = _state.load_guard_state()
        globs = [str(g) for g in (list(guard.get("frozen_globs") or []) + list(guard.get("blocked_globs") or [])) if g]
        protected = [e for e in entries if _inside_boundary(e, root, globs)]
        movable = [e for e in entries if e not in protected]
        if not movable:
            return None
        dest, label, scoped = _destination(root)
        records = guard.get("read_only") or []
        held = _held_by_read_only(movable, dest, records, root) if records else []
        movable = [e for e in movable if e not in held]
        if not movable:
            return (f"[harness:coverage-residue] Found {len(held)} project-root coverage "
                    f"{_plural(len(held), 'entry', 'entries')} ({_names(held)}) and left "
                    f"{_plural(len(held), 'it', 'them')} in place: run {_read_only_runs(records)} is recorded read-only, so the sweep "
                    f"may not move root files. Nothing was moved or deleted. " + _COVERAGE_RULE)
        dest.mkdir(parents=True, exist_ok=True)
        moved_entries = 0
        moved_files = 0
        fragments = 0
        failed = 0
        first_failure = None
        for entry in movable:
            try:
                files = _count_files(entry)
                shutil.move(str(entry), str(_unique(dest, entry.name)))
                moved_entries += 1
                moved_files += files
                if entry.name.startswith(".coverage."):
                    fragments += 1
            except Exception as exc:
                failed += 1
                first_failure = first_failure or exc
        if first_failure is not None:
            _state.record_fault("PostToolUse", first_failure)  # once per call, however many entries failed
        if not moved_entries:
            return None
        combined = _combine(dest, fragments)
        hint = (
            f"[harness:coverage-residue] Moved {moved_entries} project-root coverage entr"
            f"{'y' if moved_entries == 1 else 'ies'} ({moved_files} file{'' if moved_files == 1 else 's'}) "
            f"into {label}/ — {_names(movable)}. "
        )
        if combined:
            hint += f"The {fragments} relocated .coverage.* fragments were combined there into .coverage (originals kept). "
        elif fragments >= 2:
            hint += f"{fragments} .coverage.* fragments were relocated without combining (the coverage module was unavailable or combine failed). "
        if not scoped:
            hint += "No active run owns this residue, so it went to the harness test-work scratch class instead of a run. "
        if protected:
            hint += f"{len(protected)} entr{'y' if len(protected) == 1 else 'ies'} inside a frozen or blocked boundary were left untouched. "
        if held:
            hint += (f"{len(held)} entr{'y' if len(held) == 1 else 'ies'} ({_names(held)}) left in place because run "
                     f"{_read_only_runs(records)} is recorded read-only. ")
        if failed:
            hint += f"{failed} entr{'y' if failed == 1 else 'ies'} could not be moved and remain at the root. "
        if truncated:
            hint += f"The sweep is bounded to {_RESIDUE_CAP} project-root entries per call, so the root may still hold more. "
        hint += "Nothing was deleted. " + _COVERAGE_RULE
        return hint
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)
        return None


def main() -> None:
    global _pending_coverage_hint, _pending_maintenance_hints

    data = _state.read_hook_input()
    _state.record_observation("PostToolUse", data)
    _state.refresh_run_heartbeat(data, "PostToolUse")
    # Scoped identity: host session id, else environment, else host process.
    # Independent invocations without a session id never share one history.
    session_id, _identity_source = _state.trajectory_identity(data)
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

    # Mechanical repair first: a command step that left coverage residue at the
    # project root has it relocated into the run before anything else is said.
    _pending_coverage_hint = _sweep_coverage_residue(tool_name)
    _pending_maintenance_hints = []
    try:
        import size_audit

        size_hint = size_audit.advisory_for(size_audit.maybe_scan())
        if size_hint:
            _pending_maintenance_hints.append(size_hint)
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)  # advisory maintenance must never delay or block the host action

    text = _response_text(data)
    explicit = _explicit_failure(data)
    failed = explicit if explicit is not None else _looks_failed(text)
    empty = len(text.strip()) == 0

    sig = _signature(tool_name, tool_input)
    history = _state.append_trajectory(
        session_id, {"sig": sig, "failed": failed, "empty": empty}
    )

    # Pattern 1: same command failing repeatedly.
    recent_same = [h for h in history[-_REPEAT_FAIL_THRESHOLD:] if h.get("sig") == sig]
    if len(recent_same) >= _REPEAT_FAIL_THRESHOLD and all(h.get("failed") for h in recent_same):
        try:
            import audit_improve

            report = audit_improve.maybe_audit()
            if report:
                _pending_maintenance_hints.append(audit_improve.advisory_for(report))
        except Exception as exc:
            _state.record_fault("PostToolUse", exc)
        _emit(
            f"This action has now failed {len(recent_same)} times in a row with the same input. "
            f"Stop retrying it verbatim — change the approach, inspect the error, or try a different tool."
        )

    # Pattern 2: empty-output streak.
    tail = history[-_EMPTY_STREAK_THRESHOLD:]
    if len(tail) >= _EMPTY_STREAK_THRESHOLD and all(h.get("empty") for h in tail):
        _emit(
            f"The last {_EMPTY_STREAK_THRESHOLD} actions returned empty output and made no visible progress. "
            f"Re-check assumptions (path, scope, prerequisite step) before continuing."
        )

    # Pattern 3: two-state oscillation A,B,A,B that is *not progressing*.
    # The non-progress gate (every one of the four steps failed or returned empty)
    # is essential: a healthy build->test->build->test loop is also A,B,A,B, and
    # blocking advice there would fire on a competent trajectory (doctrine Principles: inert on a competent trajectory).
    if len(history) >= 4:
        last4 = history[-4:]
        a, b, c, d = (h.get("sig") for h in last4)
        nonprogress = all(h.get("failed") or h.get("empty") for h in last4)
        if a == c and b == d and a != b and nonprogress:
            _emit(
                "Trajectory is oscillating between two non-progressing actions (each is failing or "
                "returning nothing). Break the loop: pick a concrete next step that neither of the "
                "last two actions attempted."
            )

    # No degenerate pattern. Report the sweep on its own if it repaired anything,
    # otherwise stay silent.
    if _pending_coverage_hint or _pending_maintenance_hints:
        print(_envelope("\n".join(hint for hint in [_pending_coverage_hint, *_pending_maintenance_hints] if hint)))
        sys.exit(0)


def run() -> None:
    """The registered entry: any internal fault fails open (exit 0, no output) and is counted by type."""
    try:
        main()
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)


if __name__ == "__main__":
    run()
    sys.exit(0)
