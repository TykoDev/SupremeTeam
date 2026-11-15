#!/usr/bin/env python3
"""Advice for a run in flight when the conversation's context window fills up.

Called by ``post_tool_use.py`` and ``user_prompt_submit.py`` (``advice``); it is not a hook of its own. A host's tool
and prompt payloads carry no usage figure, so how full the context is has to come from somewhere else. Two sources,
in this order:

* the status-line sidecar (``context_statusline.py``), when it is fresh: Claude Code hands its status line the
  percentage of the window in use and the size of the window, and the sidecar writes them to
  ``.harness-state/context-usage/<session>.usage.json``;
* the last assistant line of the transcript the payload names (``transcript_path``): it carries ``message.model``
  and ``message.usage``, and the input tokens of that turn (``input_tokens``, ``cache_read_input_tokens`` and
  ``cache_creation_input_tokens``) are what the context held. That is a fraction only when the window is known: from
  the sidecar, from ``SUPREMETEAM_CONTEXT_WINDOW``, or from ``context_pressure.window_tokens`` in
  ``runtime-manifest.yaml`` for the exact model id.

With no source, or a window that is not known, there is no figure and nothing is said: a guess would tell an agent to
dump at the wrong moment.

The thresholds are ``context_pressure`` in ``runtime-manifest.yaml`` (``warn``, ``dump``, ``handoff``). Crossing one
gives one note, once per session; the note is advice and nothing is ever denied. Only while a run holds the pin, never
for a call inside a sub-agent (the figures are the main conversation's), and at most every ``check_every_s`` seconds.
A sidecar or a transcript that cannot be read as what it should be says nothing and is counted as a fault.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import _state

LEVELS = ("warn", "dump", "handoff")
DEFAULTS = {"warn": 0.80, "dump": 0.90, "handoff": 0.95, "check_every_s": 30, "window_tokens": {}}
MANIFEST = Path(__file__).resolve().parents[2] / "runtime-manifest.yaml"
WINDOW_ENV = "SUPREMETEAM_CONTEXT_WINDOW"
# Beside ``context/``, where ``context_events.py`` keeps its markers: a marker is claimed by name, and these are not one.
DIRECTORY = "context-usage"
# A sidecar older than this is not what the context holds now; the transcript is asked instead.
SIDECAR_MAX_AGE = 120
# How much of the end of a transcript is read to find the last assistant line.
TRANSCRIPT_TAIL = 256 * 1024
# Usage that falls this far below the first threshold means the conversation was compacted or cleared: the levels
# are armed again.
REARM_BELOW = 0.25
TAG = "[harness:context-pressure] "


class Unreadable(ValueError):
    """A source that is there and is not what it should be."""


def settings() -> dict:
    """``context_pressure`` from the runtime manifest, held to its shape: three fractions in rising order and a
    positive interval. Anything else is the defaults, and the fault is the caller's to count."""
    import _bootstrap

    _bootstrap.ensure_paths()
    from data_formats import load_data

    declared = load_data(MANIFEST).get("context_pressure")
    if not isinstance(declared, dict):
        raise Unreadable("runtime-manifest.yaml has no context_pressure object")
    found = dict(DEFAULTS)
    for key in LEVELS:
        value = declared.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise Unreadable(f"context_pressure.{key} is not a fraction between 0 and 1")
        found[key] = float(value)
    if not found["warn"] <= found["dump"] <= found["handoff"]:
        raise Unreadable("context_pressure thresholds are not in rising order")
    every = declared.get("check_every_s")
    if isinstance(every, bool) or not isinstance(every, (int, float)) or every < 0:
        raise Unreadable("context_pressure.check_every_s is not a number of seconds")
    found["check_every_s"] = float(every)
    windows = declared.get("window_tokens")
    found["window_tokens"] = {str(model): int(size) for model, size in windows.items()
                              if isinstance(size, int) and not isinstance(size, bool) and size > 0} if isinstance(windows, dict) else {}
    return found


def session_file(data: dict, kind: str, create: bool = False) -> "Path | None":
    """``.harness-state/context-usage/<hashed session>.<kind>.json``. The directory is made only when a file is to be written."""
    directory = _state.state_dir(create=create) / DIRECTORY
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    elif not directory.is_dir():
        return None
    identity, _ = _state.trajectory_identity(data)
    return directory / f"{hashlib.sha256(str(identity).encode('utf-8', 'ignore')).hexdigest()[:20]}.{kind}.json"


def _number(value) -> "float | None":
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def sidecar(data: dict) -> "dict | None":
    """What the status line last wrote for this session: ``{"used", "window", "at"}``, or None when there is none.
    Raises ``Unreadable`` for a file that is not a sidecar."""
    path = session_file(data, "usage")
    if path is None or not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable("the status-line sidecar is not JSON") from exc
    if not isinstance(record, dict) or _number(record.get("at")) is None:
        raise Unreadable("the status-line sidecar is not a usage record")
    percentage, window = _number(record.get("used_percentage")), _number(record.get("window"))
    return {"used": percentage / 100 if percentage is not None and 0 <= percentage <= 1000 else None,
            "window": int(window) if window and window > 0 else None, "at": record["at"]}


def transcript_usage(data: dict) -> "tuple | None":
    """``(input tokens in context, model id)`` from the last assistant line of the payload's transcript that carries a
    usage record, or None when there is no transcript or no such line yet. A line of a sub-agent's side chain is not
    the main conversation's and is passed over. Raises ``Unreadable`` when nothing in the tail is JSON."""
    name = data.get("transcript_path")
    if not isinstance(name, str) or not name.strip():
        return None
    path = Path(name)
    try:
        if not path.is_file():
            return None
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - TRANSCRIPT_TAIL))
            tail = handle.read().decode("utf-8", "replace")
    except OSError as exc:
        raise Unreadable("the transcript cannot be read") from exc
    lines = [line for line in tail.splitlines() if line.strip()]
    if size > TRANSCRIPT_TAIL:
        lines = lines[1:]  # the first line of the tail is the end of a longer one
    parsed = 0
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        parsed += 1
        message = entry.get("message") if isinstance(entry, dict) else None
        if not isinstance(message, dict) or entry.get("isSidechain") is True:
            continue
        usage = message.get("usage")
        if entry.get("type", message.get("role")) not in ("assistant",) or not isinstance(usage, dict):
            continue
        counts = [_number(usage.get(key)) for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")]
        if counts[0] is None:
            continue
        return int(sum(count or 0 for count in counts)), str(message.get("model") or "")
    if lines and not parsed:
        raise Unreadable("the transcript holds no JSON line")
    return None


def _window(config: dict, model: str, from_sidecar: "int | None") -> "int | None":
    """The size of the context window: the environment's word, else the status line's, else the manifest's for this
    exact model id. None when nobody has said."""
    override = os.environ.get(WINDOW_ENV, "").strip()
    if override:
        try:
            if int(override) > 0:
                return int(override)
        except ValueError:
            pass
        raise Unreadable(f"{WINDOW_ENV} is not a positive number of tokens")
    return from_sidecar or config["window_tokens"].get(model)


def measure(data: dict, config: dict, now: "float | None" = None) -> "dict | None":
    """How full the context is: ``{"used": fraction, "source": "status line" | "transcript"}``, or None when there is
    no figure. Raises ``Unreadable`` for a source that is there and cannot be read as what it should be."""
    now = time.time() if now is None else now
    side = sidecar(data)
    if side and side["used"] is not None and 0 <= now - side["at"] <= SIDECAR_MAX_AGE:
        return {"used": side["used"], "source": "status line"}
    found = transcript_usage(data)
    if found is None:
        return None
    tokens, model = found
    window = _window(config, model, side["window"] if side else None)
    return {"used": tokens / window, "source": "transcript"} if window else None


def _pinned_run(root: Path) -> "str | None":
    """The id of the one run that holds the pin with a fresh lock, or None."""
    from _saves import inspect_saves

    held = [run for run in inspect_saves(root, only_held=True).get("held_runs") or () if run.get("fresh")]
    return str(held[0].get("run_id") or "") or None if len(held) == 1 else None


def _word(path: str) -> str:
    """A path as one word of a command an agent will paste into a shell: forward slashes, quoted when it holds a space."""
    text = str(path).replace("\\", "/")
    return f'"{text}"' if " " in text else text


def _dump_command(run_id: str) -> str:
    """The command that writes the dump, as it runs from here: the interpreter this hook is running under and the
    writer beside it. A checkout-relative ``python skills/harness/hooks/save_run.py`` exists in neither an installed
    copy nor a project that only uses one, and an agent told to dump now has to be able to."""
    writer = Path(__file__).resolve().with_name("save_run.py")
    return (f"{_word(sys.executable or 'python')} {_word(writer)} dump --run-id {run_id} --trigger context-pressure "
            "--narrative-from -")


def note(level: str, used: float, source: str, run_id: str, config: dict) -> str:
    """The advice for one level. ``run_id`` is a run id the writer accepted; nothing else in it comes from a file."""
    seen = f"The conversation is at {round(used * 100)}% of its context window (by the {source})"
    narrative = ("the objective, the decisions made and why, the files in flight, the open questions, and the exact "
                 "next action")
    if level == "warn":
        return (f"{TAG}{seen}, and run {run_id} is in flight. Finish the step in hand before starting a large read. "
                f"At {round(config['dump'] * 100)}% you will be asked to write a context dump.")
    if level == "dump":
        return (f"{TAG}{seen}. Write a context dump for run {run_id} now: pipe a narrative to '{_dump_command(run_id)}' "
                f"that covers {narrative}. The dump does not change the revision. Then continue from it.")
    return (f"{TAG}{seen}. Finish the step in hand and start nothing new. Write a context dump for run {run_id} "
            f"('{_dump_command(run_id)}', with a narrative that covers {narrative}), then let the host compact the "
            "conversation; the note that follows the compaction names the dump to read first.")


def advice(data: dict, event: str) -> "str | None":
    """The note to add to what the calling hook says, or None. Never raises; a fault is counted under ``event``."""
    try:
        if not isinstance(data, dict) or data.get("agent_id"):
            return None
        root = _state.state_root()
        if not (root / "skillset-saves" / "runs").is_dir():
            return None
        now = time.time()
        path = session_file(data, "watch")
        watch = _state.read_json(path, {}) if path is not None else {}
        watch = watch if isinstance(watch, dict) else {}
        last, every = _number(watch.get("checked_at")), _number(watch.get("every"))
        if last is not None and every is not None and 0 <= now - last < every:
            return None
        run_id = _pinned_run(root)
        if run_id is None:
            return None
        try:
            config = settings()
        except Exception as exc:
            _state.record_fault(event, exc)
            config = dict(DEFAULTS)
        advised = [level for level in watch.get("advised") or [] if level in LEVELS] if isinstance(watch.get("advised"), list) else []
        said = None
        try:
            reading = measure(data, config, now)
        except Unreadable as exc:
            _state.record_fault(event, exc)
            reading = None
        if reading is not None:
            used = reading["used"]
            if used <= config["warn"] - REARM_BELOW:
                advised = []
            reached = [level for level in LEVELS if used >= config[level]]
            if reached and reached[-1] not in advised:
                said = note(reached[-1], used, reading["source"], run_id, config)
                advised = list(LEVELS[:LEVELS.index(reached[-1]) + 1])
        _state.write_json(session_file(data, "watch", create=True), {"checked_at": now, "every": config["check_every_s"], "advised": advised})
        return said
    except Exception as exc:
        _state.record_fault(event, exc)
        return None
