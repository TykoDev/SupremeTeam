#!/usr/bin/env python3
"""Keep a pinned run recoverable across a context compaction.

Runs as a host ``PreCompact`` and ``SessionStart`` hook. When the host compacts a conversation, what the model knew
about the run in flight (its revision, who holds it, what comes next) survives only as far as the summary happens to
keep it. Nothing in the harness reacted to that. This hook does three things, and only while a run holds the pin:

* **Before the compaction** it has ``save_run.py`` write a context dump (``skillset-saves/runs/<run>/_context/
  dump-<n>.md``: the run state, with no agent involved and the revision unchanged), leaves a marker in
  ``.harness-state/context/<session>.json``, and on Claude Code prints instructions for the summary that name the
  run, the revision, the next action and the dump. Claude Code reads the standard output of a ``PreCompact`` hook
  that exits 0 as instructions for the summary, and blocks the compaction on exit 2: this hook exits 0 whatever
  happens.
* **At the session start that follows** (Claude Code: ``source`` is ``compact``) it gives the model the next action
  and the dump to read, as ``additionalContext``.
* **Whatever the host does**, the marker is also seen by the next ``post_tool_use.py`` or ``user_prompt_submit.py``
  call (``pending_note``), which gives the same note. Whoever sees the marker first claims it, so the note is given
  once. This covers a host whose session start after a compaction is unknown.

Outside a run it is silent and writes nothing: no dump, no marker, no observation record. A registered command may
name its host (``--host claude``); without that, Claude Code is recognised by the project variable it sets for a
hook. Verified end to end in Claude Code; Codex documents the two events and how it reads their output was not
checked, so nothing is printed there before a compaction and the note reaches it through the marker.

Exit code is always 0: the hook advises and records, it never blocks a compaction or a session.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path


def _missing_module(event: str, exc: BaseException) -> None:
    """A module this hook imports is not there. A registered hook fails open: exit 0 and nothing printed, with the fault
    counted when ``_state`` still loads and said on stderr when it does not. ``--selftest`` and an import of this file
    by another program are not host events, so they get the error itself."""
    if __name__ != "__main__" or "--selftest" in sys.argv[1:]:
        return
    try:
        import _state as state

        state.record_fault(event, exc)
    except BaseException:
        try:
            sys.stderr.write("supremeteam %s hook: a module it imports is missing (%s) and the fault could not be "
                             "recorded; the hook did nothing. Reinstall the catalog and run "
                             "skills/harness/hooks/check_readiness.py.\n" % (event, exc))
        except Exception:
            pass
    sys.exit(0)


try:
    import _state
except ImportError as _exc:  # a catalog file this hook imports is missing
    _missing_module("PreCompact", _exc)
    raise

MARKER_DIRECTORY = "context"
# A marker older than this describes a compaction nobody came back from; it is dropped unread.
MARKER_MAX_AGE = 6 * 60 * 60
# How long the dump waits for another writer of the saves. A compaction is not a tool call: the host is about to
# spend seconds summarising, so a short wait costs nothing, and a dump that was skipped is a note without a file.
DUMP_LOCK_WAIT = 2.0
# Claude Code takes up to 10,000 characters of instructions from a pre-compaction hook.
INSTRUCTION_LIMIT = 10_000
NOTE_TAG = "[harness:context-resume] "


def _event(data: dict) -> str:
    return str(data.get("hook_event_name") or data.get("hookEventName") or "").strip().lower()


def _for_claude() -> bool:
    """Whether the hook was started by Claude Code: the registered command says so, or, for a registration written by
    hand, the project variable Claude Code sets for every hook is there and no other host is named."""
    host = _state.output_host()
    return host == "claude" if host else bool(os.environ.get("CLAUDE_PROJECT_DIR"))


def pinned_run(root: Path) -> "tuple | None":
    """``(run_id, state, lock)`` of the one run that holds the pin, or None: no run, two of them, or a record this
    account cannot read. The same test the heartbeat refresh uses, so the two never disagree about which run is live."""
    if not (root / "skillset-saves" / "runs").is_dir():
        return None
    from _saves import inspect_saves, stopped_at_refusal

    result = inspect_saves(root)
    coherent = [run for run in result.get("held_runs") or () if run.get("state") in {"active", "stale"}]
    if len(coherent) != 1 or stopped_at_refusal(result):
        return None
    run_id = str(coherent[0].get("run_id") or "")
    run_dir = root / "skillset-saves" / "runs" / run_id
    state, lock = _state.read_mapping(run_dir / "_state.md"), _state.read_mapping(run_dir / "_lock.md")
    if not isinstance(state, dict) or not isinstance(lock, dict):
        return None
    return run_id, state, lock


def _marker(data: dict, create: bool = False) -> "Path | None":
    """Where this session's marker is. The directory is made only when a marker is about to be written."""
    directory = _state.state_dir(create=create) / MARKER_DIRECTORY
    if not create and not directory.is_dir():
        return None
    identity, _ = _state.trajectory_identity(data)
    return directory / (hashlib.sha256(str(identity).encode("utf-8", "ignore")).hexdigest()[:20] + ".json")


def _newest_dump(root: Path, run_id: str) -> "str | None":
    import save_run

    dumps = save_run.RunStore(root, run_id).dumps()
    return dumps[-1][1].relative_to(root.resolve()).as_posix() if dumps else None


def describe(run_id: str, state: dict, dump: "str | None", trigger: str = "") -> dict:
    """What a marker holds, and what a note is written from: the run as it stood, in a few bounded fields."""
    revision = state.get("revision")
    return {
        "run_id": run_id,
        "revision": revision if isinstance(revision, int) and not isinstance(revision, bool) else None,
        "phase_state": _state.safe_text(state.get("phase_state") or state.get("protocol_state") or "", 120),
        "delegated_to": _state.safe_text(state.get("delegated_to") or "", 120),
        "next_action": _state.safe_text(state.get("next_action") or "", 2000),
        "dump": dump,
        "trigger": _state.safe_text(trigger, 80),
        "at": time.time(),
    }


def resume_note(marker: dict) -> str:
    """The note a model reads after a compaction. Every value in it came from the run state through ``describe``."""
    run_id = _state.safe_text(marker.get("run_id") or "", 140)
    revision = marker.get("revision")
    dump = marker.get("dump")
    first = (f"read {_state.safe_text(dump, 400)} (the context dump written just before the compaction), then "
             if dump else "read ")
    return (
        f"{NOTE_TAG}The host compacted this conversation while Supreme Team run {run_id} was in flight"
        + (f" at revision {revision}" if revision is not None else "")
        + ". What you knew about the run before that may be gone from your context. Before anything else, "
        + f"{first}skillset-saves/runs/{run_id}/_state.md. "
        + (f"Next action recorded for the run: {_state.safe_text(marker.get('next_action'), 2000)}. "
           if marker.get("next_action") else "")
        + (f"It is delegated to {_state.safe_text(marker.get('delegated_to'), 120)}. " if marker.get("delegated_to") else "")
        + "Continue inside this run: do not start a second one, and checkpoint with the revision the state file gives."
    )


def instructions(marker: dict) -> str:
    """What Claude Code is asked to keep in the summary it is about to write."""
    run_id = _state.safe_text(marker.get("run_id") or "", 140)
    revision = marker.get("revision")
    lines = [
        f"Supreme Team run {run_id} is in flight in this session. Keep these facts in the summary, word for word:",
        f"- the run id: {run_id}",
        *([f"- its revision: {revision}"] if revision is not None else []),
        *([f"- its phase state: {marker['phase_state']}"] if marker.get("phase_state") else []),
        *([f"- who it is delegated to: {marker['delegated_to']}"] if marker.get("delegated_to") else []),
        *([f"- the next action recorded for it: {marker['next_action']}"] if marker.get("next_action") else []),
        *([f"- the context dump to read first after this compaction: {marker['dump']}"] if marker.get("dump") else []),
        f"- the state file: skillset-saves/runs/{run_id}/_state.md",
        "- that work continues inside this run and no second run is started.",
    ]
    return "\n".join(lines)[:INSTRUCTION_LIMIT]


def claim(data: dict) -> "dict | None":
    """Take this session's marker, if there is one: whoever renames it first has it, so one note is given. A marker
    that cannot be read, or that is too old to be about this conversation, is dropped."""
    path = _marker(data)
    if path is None:
        return None
    taken = path.with_name(f"{path.name}.{os.getpid()}.claimed")
    try:
        os.replace(path, taken)
    except OSError:
        return None
    try:
        marker = json.loads(taken.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        marker = None
    finally:
        try:
            taken.unlink()
        except OSError:
            pass
    if not isinstance(marker, dict) or not marker.get("run_id"):
        return None
    at = marker.get("at")
    if not isinstance(at, (int, float)) or isinstance(at, bool) or not 0 <= time.time() - at <= MARKER_MAX_AGE:
        return None
    return marker


def pending_note(data: dict) -> "str | None":
    """For the other hooks: the resume note when this session was compacted and nothing has said so yet, else None.

    The common call is one ``is_dir`` on a directory that is only there after a compaction. A call inside a sub-agent
    is left alone: the note is for the conversation that was compacted, not for a delegate with a context of its own."""
    try:
        if not isinstance(data, dict) or data.get("agent_id"):
            return None
        marker = claim(data)
        return resume_note(marker) if marker else None
    except Exception as exc:
        _state.record_fault("SessionStart", exc)
        return None


def before_compaction(data: dict) -> "str | None":
    """Dump the pinned run, leave the marker, and return the instructions for the summary (None outside a run)."""
    root = _state.state_root()
    run = pinned_run(root)
    if run is None:
        return None
    run_id, state, lock = run
    trigger = "pre-compact:" + _state.safe_text(data.get("trigger") or "unknown", 40)
    dump = None
    try:
        import save_run

        result = save_run.RunStore(root, run_id).dump("hook:PreCompact", trigger, wait=DUMP_LOCK_WAIT)
        dump = result.get("dump")
    except Exception as exc:
        # A run state that cannot be read, a busy writer, a full disk: the compaction goes ahead either way, so the
        # marker and the note still name the run, and the newest dump there is, if any.
        _state.record_fault("PreCompact", exc)
        try:
            dump = _newest_dump(root, run_id)
        except Exception:
            dump = None
    marker = describe(run_id, state, dump, trigger)
    path = _marker(data, create=True)
    if path is not None:
        _state.write_json(path, marker)
    return instructions(marker)


def after_compaction(data: dict) -> "str | None":
    """The resume note for a session start: from the marker when there is one, else, for a start the host says
    follows a compaction, from the run state as it is now. None when there is nothing to resume."""
    marker = claim(data)
    if marker is None and str(data.get("source") or "").strip().lower() == "compact":
        root = _state.state_root()
        run = pinned_run(root)
        if run is not None:
            marker = describe(run[0], run[1], _newest_dump(root, run[0]))
    return resume_note(marker) if marker else None


def main() -> None:
    data = _state.read_hook_input("PreCompact")
    event = _event(data)
    if event == "precompact":
        text = before_compaction(data)
        if text and _for_claude():
            print(text)
    elif event == "sessionstart":
        note = after_compaction(data)
        if note:
            print(json.dumps(_state.context_output("SessionStart", note)))


def run() -> None:
    """The registered entry: a fault never blocks a compaction or a session (exit 0, nothing printed); it is counted."""
    try:
        main()
    except BaseException as exc:
        # Exit 2 from a pre-compaction hook blocks the compaction on Claude Code, so nothing may leave here but 0:
        # a ``SystemExit`` some module raised is a fault like any other.
        _state.record_fault("PreCompact", exc)


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        # Not a host event: prove the registered command starts and every module a hook runs imports, and fail
        # loud when one does not (verify_registration.probe reads the exit status and the "ok").
        import _bootstrap

        _bootstrap.selftest()
        sys.exit(0)
    run()
    sys.exit(0)
