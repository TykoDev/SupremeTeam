#!/usr/bin/env python3
"""Gate watch: re-run the boundary validator when a run's manifest or intake log is written.

Called from ``post_tool_use.py`` after every tool call. It lists the run manifests
(``skillset-saves/runs/<run>/<phase>/manifest.{json,yaml,yml}``) and intake grilling
logs (``skillset-saves/runs/<run>/intake/report_grilling.md``), compares each file's
size and modification time with what it saw last, and for each one that changed runs
``harness/gatekeeper/check.py`` - ``--boundary <declared boundary> --package <manifest>``
for a manifest, ``--intake-log <log>`` for a log. The decision-log tables, the typed
source-of-truth records and the upstream-approval binding are therefore checked the
moment a package is written, not first at the gate.

The result is advisory: by the time a PostToolUse hook runs the write has happened,
and like every hook here this one fails open. The authority is check.py itself, which
fails loud at every self-check and every gate. The hint names the file and its first
failures so the writer can fix them before submitting.

Bounded: at most ``SCAN_CAP`` files are listed and ``CHECK_CAP`` checked per call, each
with a ``TIMEOUT`` second limit; files past the cap are checked on a later call. The
size-and-mtime record lives in ``.harness-state/observations/gate-watch.json``
(save-ownership.yaml ``harness-observations``).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import _bootstrap
import _state

_bootstrap.ensure_paths()

SCAN_CAP = 200
CHECK_CAP = 2
TIMEOUT = 20
SHOWN_FAILURES = 6
MANIFEST_NAMES = ("manifest.json", "manifest.yaml", "manifest.yml")
INTAKE_LOG = "report_grilling.md"
CHECK = _bootstrap.HOOKS.parent / "gatekeeper" / "check.py"


def _record_path() -> Path:
    return _state.state_dir() / "observations" / "gate-watch.json"


def watched(root: Path) -> list[Path]:
    """The run manifests and intake logs under ``root``, sorted, at most SCAN_CAP."""
    runs = root / "skillset-saves" / "runs"
    if not runs.is_dir():
        return []
    found: list[Path] = []
    for run in sorted(p for p in runs.iterdir() if p.is_dir() and not p.is_symlink()):
        for phase in sorted(p for p in run.iterdir() if p.is_dir() and not p.is_symlink()):
            names = (INTAKE_LOG,) if phase.name == "intake" else MANIFEST_NAMES
            found += [phase / name for name in names if (phase / name).is_file()]
            if len(found) >= SCAN_CAP:
                return found[:SCAN_CAP]
    return found


def _stamp(path: Path) -> list:
    info = path.stat()
    return [info.st_mtime_ns, info.st_size]


def _command(path: Path) -> "list | str":
    """The check.py command for one watched file, or the reason none can run."""
    if path.name == INTAKE_LOG:
        return [sys.executable, str(CHECK), "--intake-log", str(path)]
    data = _state.read_mapping(path)
    boundary = data.get("boundary") if isinstance(data, dict) else None
    if not isinstance(boundary, str) or not boundary.strip():
        return "declares no boundary, so no gate can check it"
    return [sys.executable, str(CHECK), "--boundary", boundary.strip(), "--package", str(path)]


def check(path: Path, root: Path) -> "str | None":
    """One file's advisory line, or None when it passes."""
    command = _command(path)
    rel = path.relative_to(root).as_posix()
    if isinstance(command, str):
        return f"{rel} {command}."
    proc = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT, cwd=str(root),
                          stdin=subprocess.DEVNULL, check=False)
    if proc.returncode == 0:
        return None
    try:
        failures = json.loads(proc.stdout).get("failures") or []
    except (json.JSONDecodeError, AttributeError):
        failures = [_state.safe_text(proc.stderr or proc.stdout, 300) or f"check.py exited {proc.returncode}"]
    shown = "; ".join(_state.safe_text(f, 200) for f in failures[:SHOWN_FAILURES])
    more = f" (+{len(failures) - SHOWN_FAILURES} more)" if len(failures) > SHOWN_FAILURES else ""
    return f"{rel} fails check.py: {shown}{more}."


def advisory(root: "Path | None" = None) -> "str | None":
    """Check what changed since the last call; return the hint, or None when everything passed."""
    root = Path(root) if root is not None else _state.project_root()
    if not CHECK.is_file():
        return None
    files = watched(root)
    if not files:
        return None
    record_path = _record_path()
    record = _state.read_json(record_path, {})
    if not isinstance(record, dict):
        record = {}
    lines: list[str] = []
    checked = 0
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            stamp = _stamp(path)
        except OSError:
            continue
        if record.get(rel) == stamp:
            continue
        if checked >= CHECK_CAP:
            break
        checked += 1
        try:
            line = check(path, root)
        except subprocess.TimeoutExpired:
            line = f"{rel} was not checked: check.py exceeded {TIMEOUT}s; run it before submitting."
        record[rel] = stamp
        if line:
            lines.append(line)
    live = {path.relative_to(root).as_posix() for path in files}
    _state.write_json(record_path, {rel: stamp for rel, stamp in record.items() if rel in live})
    if not lines:
        return None
    return ("[harness:gate-watch] A gate package or intake log was written and does not pass the gate it "
            "will be submitted to. Fix it before submitting; check.py at the gate refuses it the same way.\n"
            + "\n".join(lines))
