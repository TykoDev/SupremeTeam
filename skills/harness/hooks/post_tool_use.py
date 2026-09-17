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

Contract: prints the PostToolUse additionalContext envelope to
stdout and exits 0. On any internal error it exits 0 silently (fail open). It
never blocks — by definition the action already executed.
"""

import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

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
    key = tool_name
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


def _emit(hint: str) -> None:
    context = "[harness:trajectory-regulation] " + hint
    if _pending_coverage_hint:
        context += "\n" + _pending_coverage_hint
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


def _boundary_variants(glob: str) -> list:
    """Guard-glob match forms, borrowed from the pre-tool hook so one boundary
    definition governs both the block and the sweep."""
    try:
        import pre_tool_use  # noqa: WPS433 — same package, no import-time side effects

        return pre_tool_use._glob_variants(glob)
    except Exception:
        g = str(glob).replace("\\", "/")
        return [g, g.rstrip("/") + "/**"]


def _inside_boundary(entry: Path, root: Path, globs: list) -> bool:
    """True when `entry` lies inside a frozen or blocked glob.

    The sweep moves files, which is a write, so it obeys exactly the boundary
    `pre_tool_use.py` would enforce against a manual `mv`. The `/_` probe suffix
    lets a directory entry match a subtree glob such as `htmlcov/**`.
    """
    if not globs:
        return False
    rel = entry.name
    absolute = entry.as_posix()
    candidates = (rel, rel + "/_", absolute, absolute + "/_")
    for glob in globs:
        for variant in _boundary_variants(glob):
            if any(fnmatch.fnmatch(candidate, variant) for candidate in candidates):
                return True
    return False


def _phase_directories(catalog_root: Path) -> list:
    """Declared phase directories from save-ownership.yaml; falls back on error."""
    try:
        from _saves import SCRIPT_ROOT  # noqa: WPS433 — puts skills/scripts on sys.path

        _ = SCRIPT_ROOT
        from data_formats import parse_yaml  # noqa: WPS433

        data = parse_yaml((catalog_root / "save-ownership.yaml").read_text(encoding="utf-8"))
        declared = [str(p) for p in (data.get("phase_directories") or []) if p]
        return declared or list(_FALLBACK_PHASES)
    except Exception:
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
        from _saves import _mapping  # noqa: WPS433

        state = _mapping(run_dir / "_state.md") or {}
        marker = str(state.get("phase_state") or state.get("phase") or "").strip().lower().replace("_", "-")
        if marker:
            for phase in sorted(phases, key=len, reverse=True):
                if marker == phase or marker.startswith(phase + "-"):
                    return phase
    except Exception:
        pass
    return _DEFAULT_PHASE if _DEFAULT_PHASE in phases else (phases[0] if phases else _DEFAULT_PHASE)


def _destination(root: Path) -> tuple:
    """Return ``(destination, relative_label, scoped)``.

    Scoped means an active run owns the residue: it lands in that run's
    `<phase>/evidence/coverage/`. With no active run the residue goes to the
    declared scratch class `.harness-state/test-work/coverage-residue/<ts>/` —
    relocated, never deleted, and never gate evidence.
    """
    run_id = _state._active_run_id()
    if run_id and run_id != "no-run":
        run_dir = root / "skillset-saves" / "runs" / run_id
        if run_dir.is_dir():
            catalog_root = Path(__file__).resolve().parents[2]
            phase = _run_phase(run_dir, _phase_directories(catalog_root))
            dest = run_dir / phase / "evidence" / "coverage"
            return dest, f"skillset-saves/runs/{run_id}/{phase}/evidence/coverage", True
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

    Runs only where the `coverage` module is importable, only inside the
    destination, and only with `--keep` so the relocated fragments survive the
    combine — the sweep never destroys data it moved.
    """
    if fragments < 2:
        return False
    try:
        import importlib.util

        if importlib.util.find_spec("coverage") is None:
            return False
        env = os.environ.copy()
        env["COVERAGE_FILE"] = str(dest / ".coverage")
        args = [sys.executable, "-m", "coverage", "combine", "--keep"]
        if (dest / ".coverage").exists():
            args.append("--append")
        done = subprocess.run(args, cwd=str(dest), env=env, capture_output=True, text=True, timeout=60)
        return done.returncode == 0
    except Exception:
        return False


def _sweep_coverage_residue(tool_name: str) -> "str | None":
    """Relocate project-root coverage residue into the run. Never raises.

    Guarantees: bounded to `_RESIDUE_CAP` entries; silent when the root is clean;
    never touches `skillset-saves/` or `.harness-state/` themselves; never moves
    anything inside a frozen or blocked glob; never deletes.
    """
    if str(tool_name or "").strip().lower() not in _COMMAND_TOOLS:
        return None
    try:
        root = _state.project_root().resolve()
    except Exception:
        return None
    try:
        entries = []
        scanned = 0
        truncated = False
        for entry in root.iterdir():
            scanned += 1
            if scanned > _RESIDUE_CAP:
                truncated = True
                break
            if entry.name in _GENERATED_ROOTS or not _is_residue(entry.name):
                continue
            entries.append(entry)
        if not entries:
            return None
        globs = []
        try:
            guard = _state.load_guard_state()
            globs = [str(g) for g in (list(guard.get("frozen_globs") or []) + list(guard.get("blocked_globs") or [])) if g]
        except Exception:
            globs = []
        protected = [e for e in entries if _inside_boundary(e, root, globs)]
        movable = [e for e in entries if e not in protected]
        if not movable:
            return None
        dest, label, scoped = _destination(root)
        dest.mkdir(parents=True, exist_ok=True)
        moved_entries = 0
        moved_files = 0
        fragments = 0
        failed = 0
        for entry in movable:
            try:
                files = _count_files(entry)
                shutil.move(str(entry), str(_unique(dest, entry.name)))
                moved_entries += 1
                moved_files += files
                if entry.name.startswith(".coverage."):
                    fragments += 1
            except Exception:
                failed += 1
                continue
        if not moved_entries:
            return None
        combined = _combine(dest, fragments)
        names = sorted({e.name if not e.name.startswith(".coverage.") else ".coverage.*" for e in movable})
        hint = (
            f"[harness:coverage-residue] Moved {moved_entries} project-root coverage entr"
            f"{'y' if moved_entries == 1 else 'ies'} ({moved_files} file{'' if moved_files == 1 else 's'}) "
            f"into {label}/ — {', '.join(names)}. "
        )
        if combined:
            hint += f"The {fragments} relocated .coverage.* fragments were combined there into .coverage (originals kept). "
        elif fragments >= 2:
            hint += f"{fragments} .coverage.* fragments were relocated without combining (the coverage module was unavailable or combine failed). "
        if not scoped:
            hint += "No active run owns this residue, so it went to the harness test-work scratch class instead of a run. "
        if protected:
            hint += f"{len(protected)} entr{'y' if len(protected) == 1 else 'ies'} inside a frozen or blocked boundary were left untouched. "
        if failed:
            hint += f"{failed} entr{'y' if failed == 1 else 'ies'} could not be moved and remain at the root. "
        if truncated:
            hint += f"The sweep is bounded to {_RESIDUE_CAP} project-root entries per call, so the root may still hold more. "
        hint += "Nothing was deleted. " + _COVERAGE_RULE
        return hint
    except Exception:
        return None


def main() -> None:
    global _pending_coverage_hint

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
    if _pending_coverage_hint:
        print(_envelope(_pending_coverage_hint))
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
