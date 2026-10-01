#!/usr/bin/env python3
"""Periodically report oversized generated files and directories without changing them.

This hook scans only the two generated runtime roots. It never follows symlinks,
never removes files, and never suggests deleting protected run or guard records.
The scan has entry, depth, and wall-time limits so it stays cheap on every host
PostToolUse invocation. Its small throttle record belongs to the existing
``.harness-state/observations/`` hook-owned state class.

``maybe_scan`` is the integration API. A standalone invocation emits the normal
PostToolUse ``additionalContext`` envelope when action is warranted; ``--json``
provides a diagnostic result for manual inspection.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
import time
from pathlib import Path

import _fsutil
import _state

DEFAULT_THRESHOLD_BYTES = 256 * 1024 * 1024
DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60
DEFAULT_MAX_ENTRIES = 10_000
DEFAULT_MAX_DEPTH = 16
DEFAULT_MAX_SECONDS = 0.5
MAX_FINDINGS = 8
MAX_NAME = 100
STAMP = Path(".harness-state/observations/size-audit.json")

_CORE_FILES = {
    "skillset-saves/_latest.md",
    ".harness-state/guard-state.json",
    ".harness-state/observations/size-audit.json",
    "skillset-saves/preferences/taste.json",
    "skillset-saves/preferences/taste.md",
    "skillset-saves/preferences/taste.journal.jsonl",
    "skillset-saves/preferences/taste.lock",
}
_RUN_CORE_NAMES = {"_state.md", "_lock.md", "_audit-trail.md", "_journal.json"}


def _positive_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, default))
        return value if minimum <= value <= maximum else default
    except (TypeError, ValueError):
        return default


def _settings(threshold_bytes: int | None, interval_seconds: int | None) -> tuple[int, int]:
    threshold = threshold_bytes if threshold_bytes is not None else _positive_env(
        "SUPREMETEAM_SIZE_AUDIT_THRESHOLD_BYTES", DEFAULT_THRESHOLD_BYTES, 1024 * 1024, 1024**4
    )
    interval = interval_seconds if interval_seconds is not None else _positive_env(
        "SUPREMETEAM_SIZE_AUDIT_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS, 60, 7 * 24 * 3600
    )
    if threshold < 1 or interval < 0:
        raise ValueError("threshold must be positive and interval nonnegative")
    return threshold, interval


def _protected(relative: str, guard_globs: tuple[str, ...]) -> bool:
    if relative in _CORE_FILES:
        return True
    parts = relative.split("/")
    if len(parts) >= 4 and parts[:2] == ["skillset-saves", "runs"]:
        if parts[3] in _RUN_CORE_NAMES or "_history" in parts[3:]:
            return True
    if parts[:2] == ["skillset-saves", "preferences"] and "_history" in parts[2:]:
        return True
    return any(fnmatch.fnmatchcase(relative, glob.replace("\\", "/")) for glob in guard_globs)


def scan(
    root: Path,
    *,
    threshold_bytes: int = DEFAULT_THRESHOLD_BYTES,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    guard_globs: tuple[str, ...] = (),
) -> dict:
    """Return bounded, relative-path findings from existing generated roots."""
    root = Path(root)
    result = {"files": [], "directories": [], "scanned_entries": 0, "truncated": False, "errors": 0,
              "threshold_bytes": threshold_bytes}
    if threshold_bytes < 1 or max_entries < 1 or max_depth < 0 or max_seconds <= 0:
        raise ValueError("scan limits must be positive")
    deadline = time.monotonic() + max_seconds
    stack: list[tuple[Path, int]] = []
    directory_sizes: dict[str, int] = {}
    for name in (".harness-state", "skillset-saves"):
        path = root / name
        try:
            if not path.is_symlink() and path.is_dir():
                stack.append((path, 0))
        except OSError:
            result["errors"] += 1

    while stack:
        if time.monotonic() >= deadline or result["scanned_entries"] >= max_entries:
            result["truncated"] = True
            break
        directory, depth = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if time.monotonic() >= deadline or result["scanned_entries"] >= max_entries:
                        result["truncated"] = True
                        break
                    result["scanned_entries"] += 1
                    relative = Path(entry.path).relative_to(root).as_posix()
                    if _protected(relative, guard_globs):
                        continue
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if depth < max_depth:
                                stack.append((Path(entry.path), depth + 1))
                            else:
                                result["truncated"] = True
                        elif entry.is_file(follow_symlinks=False):
                            size = entry.stat(follow_symlinks=False).st_size
                            parts = relative.split("/")
                            for length in range(1, len(parts)):
                                prefix = "/".join(parts[:length])
                                directory_sizes[prefix] = directory_sizes.get(prefix, 0) + size
                            if size >= threshold_bytes:
                                result["files"].append({"path": relative, "bytes": size})
                    except OSError:
                        result["errors"] += 1
        except OSError:
            result["errors"] += 1
    result["files"].sort(key=lambda item: (-item["bytes"], item["path"]))
    if len(result["files"]) > MAX_FINDINGS:
        result["omitted_findings"] = len(result["files"]) - MAX_FINDINGS
        result["files"] = result["files"][:MAX_FINDINGS]
    result["directories"] = sorted(
        ({"path": path, "bytes": size} for path, size in directory_sizes.items()
         if size >= threshold_bytes),
        key=lambda item: (-item["bytes"], item["path"]),
    )
    if len(result["directories"]) > MAX_FINDINGS:
        result["omitted_directories"] = len(result["directories"]) - MAX_FINDINGS
        result["directories"] = result["directories"][:MAX_FINDINGS]
    return result


def _guard_globs(root: Path) -> tuple[str, ...]:
    """The effective frozen and blocked globs, read the way the guard reads them (``_state.load_guard_state``)."""
    try:
        state = _state.load_guard_state(root, "PostToolUse")
        return tuple(str(glob) for key in ("frozen_globs", "blocked_globs") for glob in state.get(key) or [] if glob)
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)
        return ()


def maybe_scan(
    root: Path | None = None,
    *,
    force: bool = False,
    now: float | None = None,
    threshold_bytes: int | None = None,
    interval_seconds: int | None = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_seconds: float = DEFAULT_MAX_SECONDS,
) -> dict | None:
    """Scan when due, returning a result or None; all runtime faults fail open."""
    try:
        root = Path(root) if root is not None else _state.project_root()
        if not any(not (root / name).is_symlink() and (root / name).is_dir()
                   for name in (".harness-state", "skillset-saves")):
            return None
        threshold, interval = _settings(threshold_bytes, interval_seconds)
        current = time.time() if now is None else now
        stamp = root / STAMP
        stamp_safe = not (root / ".harness-state").is_symlink() and not stamp.parent.is_symlink()
        if stamp_safe and not force and stamp.is_file() and not stamp.is_symlink():
            try:
                prior = json.loads(stamp.read_text(encoding="utf-8"))
                last = float(prior["checked_at"])
                if 0 <= current - last < interval:
                    return None
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                pass  # damaged throttle data must not suppress future scans
        result = scan(root, threshold_bytes=threshold, max_entries=max_entries,
                      max_depth=max_depth, max_seconds=max_seconds, guard_globs=_guard_globs(root))
        try:
            if stamp_safe and not stamp.is_symlink():
                stamp.parent.mkdir(parents=True, exist_ok=True)
                _fsutil.atomic_write(stamp, json.dumps({"checked_at": current}))
        except OSError:
            pass  # a throttle record that cannot be written only means the next call scans again
        return result
    except Exception as exc:
        _state.record_fault("PostToolUse", exc)
        return None


def _name(path: object) -> str:
    """A path from the scan as the model may read it: file names are written by whoever ran a command, so they are neutralised and capped."""
    return _state.safe_text(path, MAX_NAME)


def advisory_for(result: dict | None) -> str | None:
    if not result:
        return None
    files = result.get("files") or []
    directories = result.get("directories") or []
    if not files and not directories and not result.get("truncated"):
        return None
    threshold_mib = result["threshold_bytes"] / 1024**2
    shown = []
    if directories:
        names = ", ".join(f"{_name(item['path'])}/ ({item['bytes'] / 1024**2:.0f} MiB)" for item in directories[:3])
        suffix = f", {len(directories) - 3 + result.get('omitted_directories', 0)} more" \
            if len(directories) > 3 or result.get("omitted_directories") else ""
        shown.append(f"directories: {names}{suffix}")
    if files:
        names = ", ".join(f"{_name(item['path'])} ({item['bytes'] / 1024**2:.0f} MiB)" for item in files[:5])
        suffix = f", {len(files) - 5 + result.get('omitted_findings', 0)} more" \
            if len(files) > 5 or result.get("omitted_findings") else ""
        shown.append(f"files: {names}{suffix}")
    detail = "; ".join(shown) if shown else "no oversized paths in the bounded scan"
    limit = "; directory sizes are lower bounds because the scan was limited" if result.get("truncated") else ""
    return (f"[harness:size-audit] Generated paths at or above {threshold_mib:.0f} MiB: "
            f"{detail}{limit}. Review ownership and retention before cleaning; the hook changed no files.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--force", action="store_true", help="scan even when the periodic check is not due")
    parser.add_argument("--json", action="store_true", help="print the diagnostic result")
    args = parser.parse_args(argv)
    if not args.json and not sys.stdin.isatty():
        _state.read_hook_input("PostToolUse")  # drain a host payload before this standalone hook exits
    result = maybe_scan(args.project_root, force=args.force)
    if args.json:
        print(json.dumps(result if result is not None else {"skipped": "not-due"}))
        return
    advisory = advisory_for(result)
    if advisory:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": advisory}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
