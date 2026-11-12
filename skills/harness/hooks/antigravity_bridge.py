#!/usr/bin/env python3
"""Google Antigravity: carry its hook events to the three Supreme Team hooks, and their answers back.

Antigravity (the ``agy`` CLI, the IDE and the app) runs hooks from ``hooks.json`` with its own payload and its own
answers, so the three registered hooks cannot be named there directly. This bridge is registered in their place,
once per event, with the event as its argument:

    <python> -X utf8 <hooks>/antigravity_bridge.py PreToolUse | PostToolUse | PreInvocation

* ``PreToolUse``: the tool call is translated to the payload ``pre_tool_use.py`` reads and the guard is run. A deny
  becomes ``{"decision": "deny", "reason": ...}``; anything else is ``{"decision": "allow"}``, printed explicitly.
* ``PostToolUse``: the call and whether it failed go to ``post_tool_use.py``. Antigravity takes no context from this
  event, so what the hook says is queued for the next model call.
* ``PreInvocation``: fires before every model call, several times for one prompt. The first one after a new user
  prompt runs ``user_prompt_submit.py`` on that prompt; every one delivers what is queued, as an ``injectSteps``
  ephemeral message. The routing reminder is therefore given once per prompt.

What was seen in real sessions of Antigravity CLI 1.4.12, and is relied on here: the payload is camelCase
(``toolCall`` with ``name`` and ``args``, ``workspacePaths``, ``conversationId``, an absolute ``transcriptPath``); the
edit tools are ``write_file`` (``Path``, ``Content``) and ``edit_file`` (``Path``, ``Target``, ``Replacement``), not
the documented ``write_to_file``, ``replace_file_content`` and ``multi_replace_file_content`` (``TargetFile``), and
both sets are read; the shell tool is ``run_command`` with ``CommandLine`` and no working directory; and
``lastUserInput`` is on every event, tool events included, so nothing here searches the payload for a word. In plan
mode the prompt begins with ``/plan``; that marker is dropped before the routing hook reads the prompt, which would
otherwise take it for a slash command and stay silent.

The hooks run as child processes of the interpreter running this file, with the workspace as their project and only
the environment a hook reads. A fault in the bridge fails open and is counted: a pre-tool call is allowed, the other
events say nothing. A deny the guard returned is never dropped. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
EVENTS = ("PreToolUse", "PostToolUse", "PreInvocation")
# The environment a hook reads, and nothing else of the host's: never PYTHONPATH or PYTHONHOME.
HOOK_ENV_NAMES = frozenset({
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432", "PROGRAMDATA",
    "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "USER", "USERNAME", "LOGNAME",
    "TMPDIR", "TMP", "TEMP", "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "CODEX_HOME", "AGENTS_HOME", "PI_CODING_AGENT_DIR", "COPILOT_HOME",
})
HOOK_ENV_PREFIXES = ("SUPREMETEAM_",)
CHILD_TIMEOUT = 25
PENDING_LIMIT = 10
# Markers Antigravity puts in front of a prompt to select a mode. They are not slash commands of the catalog.
MODE_MARKERS = ("/plan",)
SHELL_TOOLS = frozenset({"run_command"})
WRITE_TOOLS = frozenset({"write_file", "write_to_file"})
EDIT_TOOLS = frozenset({"edit_file", "replace_file_content", "multi_replace_file_content"})

_USER_REQUEST = re.compile(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", re.DOTALL)


def read_payload() -> dict:
    """The event's JSON from standard input, or an empty mapping. Never raises."""
    try:
        stream = getattr(sys.stdin, "buffer", None)
        raw = stream.read().decode("utf-8", errors="replace") if stream is not None else sys.stdin.read()
        data = json.loads(raw.lstrip("﻿").strip() or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def workspace_of(data: dict) -> str:
    """The first workspace path of the payload, else the payload's ``cwd``, else this process's directory. The hook
    itself is started in the folder that holds ``hooks.json``, which is not the project."""
    paths = data.get("workspacePaths")
    for entry in paths if isinstance(paths, list) else ():
        if isinstance(entry, str) and entry.strip():
            return entry.strip()
    cwd = data.get("cwd")
    return cwd.strip() if isinstance(cwd, str) and cwd.strip() else os.getcwd()


def session_of(data: dict) -> str:
    return str(data.get("conversationId") or "antigravity")


def hook_env(workspace: str, session: str) -> dict:
    """The child's environment: what a hook reads from this one, with the workspace as the project."""
    env = {name: value for name, value in os.environ.items()
           if name.upper() in HOOK_ENV_NAMES or name.upper().startswith(HOOK_ENV_PREFIXES)}
    env["SUPREMETEAM_PROJECT_DIR"] = workspace
    env["SUPREMETEAM_SESSION_ID"] = session
    return env


def run_hook(script: str, payload: dict, workspace: str, session: str) -> dict:
    """Run one hook of this directory on ``payload`` and return the ``hookSpecificOutput`` it printed (empty when it
    said nothing, or said something that is not that)."""
    target = HOOK_DIR / script
    done = subprocess.run([sys.executable, "-X", "utf8", str(target)], input=json.dumps(payload), capture_output=True,
                          encoding="utf-8", errors="replace", env=hook_env(workspace, session),
                          cwd=workspace if os.path.isdir(workspace) else None, timeout=CHILD_TIMEOUT, check=False)
    try:
        answer = json.loads((done.stdout or "").strip() or "{}")
    except ValueError:
        return {}
    specific = answer.get("hookSpecificOutput") if isinstance(answer, dict) else None
    return specific if isinstance(specific, dict) else {}


def translate(tool_call: dict, workspace: str) -> tuple:
    """``(tool_name, tool_input, cwd)`` as the guard reads a call. A tool this bridge does not know is passed on
    under its own name with its own arguments, which the guard reads as neither a shell nor a write."""
    name = str(tool_call.get("name") or "").strip()
    lower = name.lower()
    args = tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {}
    if lower in SHELL_TOOLS:
        # Antigravity gives no working directory for a command; it starts in the workspace.
        return ("PowerShell" if os.name == "nt" else "Bash",
                {"command": str(args.get("CommandLine") or args.get("command") or "")},
                str(args.get("Cwd") or args.get("cwd") or workspace))
    path = str(args.get("Path") or args.get("TargetFile") or args.get("file_path") or "")
    if lower in WRITE_TOOLS:
        return "Write", {"file_path": path, "content": str(args.get("Content") or args.get("CodeContent") or "")}, workspace
    if lower in EDIT_TOOLS:
        chunks = args.get("ReplacementChunks")
        new = json.dumps(chunks, sort_keys=True) if isinstance(chunks, list) else str(args.get("Replacement") or args.get("ReplacementContent") or "")
        return "Edit", {"file_path": path, "old_string": str(args.get("Target") or args.get("TargetContent") or ""), "new_string": new}, workspace
    return name, dict(args), workspace


def _tool_payload(data: dict, workspace: str, session: str) -> "dict | None":
    tool_call = data.get("toolCall")
    if not isinstance(tool_call, dict):
        return None
    tool_name, tool_input, cwd = translate(tool_call, workspace)
    payload = {"session_id": session, "tool_name": tool_name, "tool_input": tool_input, "cwd": cwd}
    if isinstance(tool_call.get("id"), str) and tool_call["id"].strip():
        payload["tool_use_id"] = tool_call["id"].strip()
    return payload


# --- what is said between events --------------------------------------------------------------------------

def _state_file(workspace: str, session: str) -> Path:
    """The bridge's own record for one conversation, under the project's harness state."""
    os.environ["SUPREMETEAM_PROJECT_DIR"] = workspace
    import _state

    key = hashlib.sha256(session.encode("utf-8", "ignore")).hexdigest()[:20]
    return _state.state_dir() / "antigravity" / f"{key}.json"


def load_state(workspace: str, session: str) -> dict:
    try:
        data = json.loads(_state_file(workspace, session).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    state = data if isinstance(data, dict) else {}
    pending = state.get("pending") if isinstance(state.get("pending"), list) else []
    return {"turn": str(state.get("turn") or ""), "pending": [item for item in pending if isinstance(item, str) and item.strip()]}


def save_state(workspace: str, session: str, state: dict) -> None:
    import _state

    _state.write_json(_state_file(workspace, session), state)


def queue(workspace: str, session: str, text: str) -> None:
    """Keep what a hook said for the next model call: Antigravity takes context only at ``PreInvocation``."""
    text = (text or "").strip()
    if not text:
        return
    state = load_state(workspace, session)
    if text not in state["pending"]:
        state["pending"] = [*state["pending"], text][-PENDING_LIMIT:]
        save_state(workspace, session, state)


def clean_prompt(raw: str) -> str:
    """The user's own words: the text inside ``<USER_REQUEST>`` when the host wrapped it, with a leading mode marker
    (``/plan``) dropped."""
    found = _USER_REQUEST.search(raw or "")
    text = (found.group(1) if found else raw or "").strip()
    for marker in MODE_MARKERS:
        if text == marker:
            return ""
        if text.startswith(marker) and text[len(marker)].isspace():
            return text[len(marker):].strip()
    return text


def latest_turn(data: dict) -> tuple:
    """``(key, prompt)`` for the newest prompt the user typed. The key is the step of the transcript's last explicit
    user input, so that the calls a host makes for one prompt share it; without a readable transcript it is a digest
    of ``lastUserInput``."""
    last = str(data.get("lastUserInput") or "")
    transcript = str(data.get("transcriptPath") or "").strip()
    if transcript:
        try:
            step, content = None, ""
            with open(Path(transcript).expanduser(), encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if '"USER_INPUT"' not in line:
                        continue
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        continue
                    explicit = isinstance(entry, dict) and str(entry.get("source") or "USER_EXPLICIT") == "USER_EXPLICIT"
                    if not explicit or entry.get("type") != "USER_INPUT":
                        continue
                    step, content = entry.get("step_index"), str(entry.get("content") or "")
            if step is not None:
                return f"step:{step}", clean_prompt(content or last)
        except OSError:
            pass
    prompt = clean_prompt(last)
    if not prompt:
        return "", ""
    return "prompt:" + hashlib.sha256(prompt.encode("utf-8", "ignore")).hexdigest()[:16], prompt


# --- the three events ---------------------------------------------------------------------------------------

def pre_tool_use(data: dict) -> dict:
    workspace, session = workspace_of(data), session_of(data)
    payload = _tool_payload(data, workspace, session)
    if payload is None:
        return {"decision": "allow"}
    said = run_hook("pre_tool_use.py", payload, workspace, session)
    if said.get("permissionDecision") == "deny":
        return {"decision": "deny", "reason": str(said.get("permissionDecisionReason") or "Blocked by the Supreme Team guard.")}
    queue(workspace, session, str(said.get("additionalContext") or ""))
    return {"decision": "allow"}


def post_tool_use(data: dict) -> dict:
    workspace, session = workspace_of(data), session_of(data)
    payload = _tool_payload(data, workspace, session)
    if payload is None:
        return {}
    error = str(data.get("error") or "").strip()
    payload["tool_response"] = ({"is_error": True, "exit_code": 1, "error": error, "stderr": error} if error
                                else {"success": True, "exit_code": 0, "output": "(completed)"})
    queue(workspace, session, str(run_hook("post_tool_use.py", payload, workspace, session).get("additionalContext") or ""))
    return {}


def pre_invocation(data: dict) -> dict:
    workspace, session = workspace_of(data), session_of(data)
    state = load_state(workspace, session)
    messages = []
    key, prompt = latest_turn(data)
    if key and key != state["turn"]:
        state["turn"] = key
        if prompt:
            said = run_hook("user_prompt_submit.py", {"session_id": session, "prompt": prompt, "cwd": workspace}, workspace, session)
            routing = str(said.get("additionalContext") or "").strip()
            if routing:
                messages.append(routing)
    messages.extend(state["pending"])
    state["pending"] = []
    save_state(workspace, session, state)
    return {"injectSteps": [{"ephemeralMessage": "\n\n".join(messages)}]} if messages else {}


HANDLERS = {"PreToolUse": pre_tool_use, "PostToolUse": post_tool_use, "PreInvocation": pre_invocation}


def answer(event: str, data: dict) -> dict:
    """What the host is told for one event. A fault fails open (a pre-tool call is allowed) and is counted."""
    try:
        return HANDLERS[event](data) if event in HANDLERS else {}
    except BaseException as exc:
        try:
            os.environ.setdefault("SUPREMETEAM_PROJECT_DIR", workspace_of(data))
            import _state

            _state.record_fault(event if event in HANDLERS else "PreToolUse", exc)
        except BaseException:
            pass
        return {"decision": "allow"} if event == "PreToolUse" else {}


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if "--selftest" in arguments:
        # Not a host event: prove the registered command starts and every module a hook runs imports, and fail
        # loud when one does not (verify_registration.probe reads the exit status and the "ok").
        import _bootstrap

        _bootstrap.selftest()
        sys.exit(0)
    sys.stdout.write(json.dumps(answer(arguments[0] if arguments else "", read_payload())) + "\n")
    sys.stdout.flush()
    sys.exit(0)
