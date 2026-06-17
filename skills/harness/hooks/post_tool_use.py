#!/usr/bin/env python3
"""
Trajectory Regulation hook (LIFE-HARNESS Layer 4) for SupremeTeam.

Runs as a host ``PostToolUse``/post-tool hook. It watches the evolving trajectory
for degenerate, non-progressing patterns and injects a recovery hint as
additional context — the deterministic, per-step expression of the coarse-grained
trajectory control that gatekeepers and session-memory already provide.

Detected patterns (all mechanically certain from trajectory signatures, per
doctrine section 3 — never from guessed intent):
  - repeated identical FAILING command (>= 3 times)
  - empty-output streak (>= 3 consecutive empty results)
  - two-state oscillation (A,B,A,B over the last four steps)

Contract: prints the PostToolUse additionalContext envelope to
stdout and exits 0. On any internal error it exits 0 silently (fail open). It
never blocks — by definition the action already executed.
"""

import hashlib
import json
import sys

import _state

_REPEAT_FAIL_THRESHOLD = 3
_EMPTY_STREAK_THRESHOLD = 3


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
    return hashlib.sha1(key.encode("utf-8", "ignore")).hexdigest()[:16]


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

    This is the doctrine-§3 "mechanically certain" path: when the host reports an
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


def _emit(hint: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "[harness:trajectory-regulation] " + hint,
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def main() -> None:
    data = _state.read_hook_input()
    session_id = data.get("session_id", "default")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

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
    # blocking advice there would fire on a competent trajectory (doctrine §0).
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

    # No degenerate pattern — stay silent.


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
