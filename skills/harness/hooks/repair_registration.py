#!/usr/bin/env python3
"""Scoped, previewable repair of Supreme Team hook registration.

Readiness stays read-only. This is the explicit, owner-invoked repair step:

    python skills/harness/hooks/repair_registration.py --host claude --scope project           # dry run: prints the diff
    python skills/harness/hooks/repair_registration.py --host claude --scope project --apply   # writes, keeps a backup

Behaviour:
  * touches exactly one config file (chosen by --host/--scope), never the
    global file unless --scope user is requested explicitly;
  * adds only what verify_registration reports as missing: a hook that does not
    launch its script, or the group of tools a registered matcher leaves out.
    Every unrelated key, matcher and hook is preserved;
  * registers the interpreter running this script (an absolute path) unless
    --python names another, and starts it with ``-X utf8`` so a hook payload
    cannot fail to decode under a legacy code page;
  * refuses to write when the existing file is not valid UTF-8 JSON (a blind
    rewrite would drop someone else's configuration);
  * writes atomically (per-process temp file + replace) after copying the
    previous file to ``<file>.bak-<timestamp>``. The file and its backup keep the
    permission bits the original had;
  * records the sha256 of each registered hook script, of every Python module in
    its directory and of the ``skills/scripts`` modules the hooks import, in
    ``.harness-state/hook-hashes.json`` so verify_registration can report a file
    that changed afterwards; ``--record-hashes`` re-records them on demand;
  * never replaces a symbolic link with a regular file: a user-level config that is
    a link (a dotfiles manager's) is written through, with a note saying so, and a
    project-level one, which a cloned repository can supply, is refused;
  * is idempotent: a second run reports "no changes".

Exit 0 = nothing to do or applied, 1 = changes needed but --apply not given,
2 = a usage error, a refusal (a scope the host does not define, a config that
cannot be read as a UTF-8 JSON object with its hooks in the expected shape, a
link it will not replace, --record-hashes before the hooks are registered) or an
--apply write that raised OSError. Nothing else is caught: any other exception,
a failed --record-hashes write included, exits 1 with Python's traceback on
stderr and no JSON on stdout.
"""
from __future__ import annotations

import argparse
import difflib
import getpass
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

try:
    import _fsutil
    import _state
    import verify_registration as verify
except ImportError as exc:  # a catalog file this script imports is missing: say which, never a traceback
    if __name__ != "__main__":
        raise
    print(json.dumps({"ok": False, "error": f"repair_registration.py cannot run: {exc}. A catalog file it imports is missing; reinstall the catalog."}))
    raise SystemExit(2) from exc

HOOK_DIR = Path(__file__).resolve().parent
matcher_for = verify.matcher_for

# Shown by hosts that surface a hook status line while the hook runs.
STATUS_MESSAGES = {
    "pre_tool_use.py": "SupremeTeam: checking pending tool use",
    "post_tool_use.py": "SupremeTeam: checking trajectory",
    "user_prompt_submit.py": "SupremeTeam: checking entry routing",
}


def target_path(host: str, scope: str) -> Path:
    home = Path.home()
    project = _state.project_root()
    table = {
        ("claude", "user"): home / ".claude/settings.json",
        ("claude", "project"): project / ".claude/settings.json",
        ("claude", "local"): project / ".claude/settings.local.json",
        ("codex", "user"): home / ".codex/hooks.json",
        ("codex", "project"): project / ".codex/hooks.json",
        # Copilot reads every *.json in these two directories; the file written is ours alone.
        ("copilot", "user"): verify.copilot_home() / "hooks" / verify.COPILOT_FILE,
        ("copilot", "project"): project / ".github" / "hooks" / verify.COPILOT_FILE,
    }
    if (host, scope) not in table:
        raise ValueError(f"scope {scope!r} is not defined for host {host!r}")
    return table[(host, scope)]


def scope_warnings(host: str, scope: str, path: Path) -> list[str]:
    """What the operator should know before this file changes."""
    if scope == "user":
        return [f"user scope edits the global {host} configuration {path}, which every project on this machine reads"]
    if scope == "project":
        advice = "use --scope local for a per-machine file" if host == "claude" else "keep it out of the commit"
        return [f"project scope writes machine-absolute hook paths into {path}, a file projects usually commit; {advice}"]
    return []


ALLOW_ABSOLUTE = "--allow-absolute"


def absolute_refusal(host: str, scope: str, path: Path, allowed: bool = False) -> "str | None":
    """Why a project-scope registration with machine-absolute paths is not written for ``host``, or None.

    On a host that fails closed the usual warning is not enough. A repository's ``.github/hooks/*.json`` is read
    wherever the repository is checked out, Copilot's cloud agent included, and there the interpreter and the hook
    path of this machine do not exist: the pre-tool command exits non-zero, which that host reads as a deny, so every
    tool call in the repository is refused. The file is written only when the operator says so."""
    if scope != "project" or host not in verify.FAIL_CLOSED_HOSTS or allowed:
        return None
    return (f"project scope would write this machine's absolute interpreter and hook paths into {path}, which {host} reads "
            f"wherever the repository is checked out (its cloud agent too). A pre-tool hook that cannot start denies the "
            f"tool call on {host}, so every tool call would be refused there. Register at user scope (--scope user), or "
            f"pass {ALLOW_ABSOLUTE} to write the file anyway and keep it out of the commit")


def launcher_token(python: str) -> str:
    """Quote an interpreter whose path contains spaces.

    A launcher that carries its own arguments (``py -3.13``, ``python -X utf8``) is
    not quoted whole: quoting it would collapse two tokens into one path that does
    not exist. An unquoted ``C:/Program Files/Python313/python.exe`` would otherwise
    be split into a launcher and a stray argument, and verify_registration would
    report the hook as not executable. A spaced path that carries arguments
    (``C:/Program Files/Python313/python.exe -X dev``) has only its path quoted.

    The test is the shape of the value, not whether the file exists here, so
    registering an interpreter for another machine behaves the same way.
    """
    if not python or '"' in python or " " not in python:
        return python
    parts = launcher_parts(python)
    if len(parts) == 1:
        return '"' + python + '"'
    if " " in parts[0]:
        return " ".join(['"' + parts[0] + '"', *parts[1:]])
    return python


# Wrappers whose first argument is the program they start, so `env python3 -E` is two tokens, not one path.
_WRAPPERS = frozenset({"env", "env.exe", "nice", "nohup", "exec", "command"})


def _spaced_path(head: list[str]) -> bool:
    """Whether the words before a launcher's first option are one interpreter path that contains spaces.

    ``C:/Program Files/Python313/python.exe -X dev`` splits into ``C:/Program`` and
    ``Files/Python313/python.exe``: the first word already begins a path (it holds a
    separator or a drive), so the spaces are inside the path, and the first word is
    not a wrapper that starts the next one. A non-Python interpreter in a spaced
    directory (``C:\\Program Files\\nodejs\\node.exe --no-warnings``) is the same
    shape and merges the same way. ``/usr/bin/env python3 -E`` and ``py -3`` stay
    apart; so does a bare word that merely continues one (``python bin -E``).
    """
    if len(head) < 2 or Path(head[0].replace("\\", "/")).name.lower() in _WRAPPERS:
        return False
    if "/" in head[0] or "\\" in head[0] or re.match(r"^[A-Za-z]:", head[0]):
        return True
    last = head[-1]
    return ("/" in last or "\\" in last) and verify._python_launcher(last.replace("\\", "/"))


def launcher_parts(python: str) -> list[str]:
    """The interpreter command followed by the arguments that belong to it.

    Uses the same shape test as ``launcher_token``, for hosts that start the
    interpreter without a shell and so need the command and its arguments apart.
    A spaced interpreter path followed by options stays one command
    (``_spaced_path``) rather than being cut at its first space.
    """
    if not python or " " not in python:
        return [python]
    if '"' in python:
        return verify._tokens(python)
    words = list(re.finditer(r"\S+", python))
    parts = [word.group() for word in words]
    first = next((i for i, part in enumerate(parts) if i and part.startswith("-")), None)
    if first is None:
        return [python]
    if _spaced_path(parts[:first]):
        return [python[words[0].start():words[first - 1].end()], *parts[first:]]
    return parts


def utf8_flags(python: str) -> list[str]:
    """``-X utf8`` unless the launcher already sets it."""
    parts = launcher_parts(python)
    if "-Xutf8" in parts or any(a == "-X" and b == "utf8" for a, b in zip(parts, parts[1:], strict=False)):
        return []
    return ["-X", "utf8"]


# --- the command a host can start (Windows) ----------------------------------------------------------
#
# A hook command is text a shell reads, and on Windows the hosts do not share a shell: Claude Code uses Git Bash,
# Codex and Copilot PowerShell or cmd, Antigravity ``cmd /C`` with the quotes escaped. One form starts in all of them
# but the last: the interpreter unquoted, the hook path quoted, forward slashes throughout. It works because its first
# word is never quoted (PowerShell reads a command that begins with a quote as a string) and holds no backslash (Git
# Bash consumes them). Every form here was run through Git Bash, PowerShell 7, Windows PowerShell 5.1 and cmd, and
# through real Claude Code sessions; test_registration_shells.py repeats the matrix.

class CommandRefused(ValueError):
    """No command that starts on the host can be written for these paths. The message names the ways out."""


_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_EXTENDED_PREFIX = "\\\\?\\"
_REFUSAL_ADVICE = ("Install to a destination and an interpreter whose paths hold no space, or name a launcher with "
                   "--python (for example --python \"py -3.13\").")
# What each host is given on Windows: the form, and the fallback when no launcher without a space qualifies
# (None refuses). OpenCode and pi start the interpreter without a shell through their own bridges and are not here.
WINDOWS_FORMS = {"claude": ("standard", "parts"), "codex": ("standard", None), "cursor": ("standard", None),
                 "copilot": ("standard", "call"), "antigravity": ("bare", None)}


def windows_shaped(path: str) -> bool:
    """A drive-letter path or a backslash UNC path. A backslash by itself proves nothing: it is a legal character in a
    POSIX file name, so only these two shapes are converted."""
    return bool(_DRIVE_PATH.match(path)) or path.startswith("\\\\")


def forward_slashes(path: str) -> str:
    """``path`` with forward slashes when it is Windows-shaped, unchanged otherwise.

    An extended-length prefix (``\\\\?\\C:\\...``) is dropped when the rest is an ordinary drive path. Any other
    extended path (``\\\\?\\UNC\\...``, a device) is refused: no shell command can name it."""
    if path.startswith(_EXTENDED_PREFIX):
        rest = path[len(_EXTENDED_PREFIX):]
        if not _DRIVE_PATH.match(rest):
            raise CommandRefused(f"{path} is an extended-length path that is not a plain drive path, and no shell command "
                                 f"can name it. {_REFUSAL_ADVICE}")
        path = rest
    return PureWindowsPath(path).as_posix() if windows_shaped(path) else path


def standard_form(launcher: list[str], script: str) -> str:
    """``C:/Py/python.exe -X utf8 "C:/Users/Jane Doe/.agents/skills/harness/hooks/pre_tool_use.py"``: the interpreter
    unquoted, the hook path quoted. Starts in Git Bash, both PowerShells and cmd."""
    if " " in launcher[0]:
        raise CommandRefused(f"the interpreter path {launcher[0]!r} holds a space, and the standard form leaves it unquoted")
    return " ".join([*launcher, f'"{script}"'])


def bare_form(launcher: list[str], script: str) -> str:
    """``C:/Py/python.exe -X utf8 C:/h/pre_tool_use.py``: nothing quoted. The one form Antigravity can run."""
    for part in (launcher[0], script):
        if " " in part or '"' in part or "'" in part:
            raise CommandRefused(f"{part!r} holds a space or a quote, and this host cannot run a command that contains a "
                                 f"quote. {_REFUSAL_ADVICE}")
    return " ".join([*launcher, script])


def call_form(launcher: list[str], script: str) -> str:
    """``& "C:/Program Files/Py/python.exe" -X utf8 "C:/h/pre_tool_use.py"``: PowerShell only."""
    return " ".join(["&", f'"{launcher[0]}"', *launcher[1:], f'"{script}"'])


def parts_form(launcher: list[str], script: str) -> dict:
    """``{"command": interpreter, "args": [...]}``: started directly, with no shell to read it."""
    return {"command": launcher[0], "args": [*launcher[1:], script]}


def py_launcher_for(interpreter: str) -> "str | None":
    """``py -<major>.<minor>`` when the ``py`` launcher is on PATH and that selector starts this very interpreter, else None.

    A launcher is how a command avoids naming an interpreter whose path holds a space. It qualifies only when it
    resolves to the same file: for a virtual environment it does not, and registering the base interpreter in its place
    would run the hooks on another set of packages."""
    launcher = shutil.which("py")
    if not launcher:
        return None
    version = verify._probe_version(interpreter, [])
    if not version:
        return None
    selector = f"-{version[0]}.{version[1]}"
    try:
        done = subprocess.run([launcher, selector, "-I", "-S", "-c", "import sys; print(sys.executable)"],
                              capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL, check=False)
        same = done.returncode == 0 and os.path.samefile(done.stdout.strip(), interpreter)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return f"py {selector}" if same else None


def hook_handler(script: str, python: str, host: str = "claude", *, windows: "bool | None" = None,
                 hook_dir: "str | Path | None" = None, py_launcher=None) -> dict:
    """The fields that start one hook on ``host``: ``{"command": text}``, with ``args`` beside it for the no-shell form.

    On POSIX the command is what it always was. On Windows the form is the host's row of ``WINDOWS_FORMS``, and the
    first word has to hold no space: the interpreter's own path, else ``py -<major>.<minor>`` when the launcher starts
    the same interpreter (``py_launcher``, ``py_launcher_for`` by default), else the host's fallback. Raises
    ``CommandRefused`` when the host has none. ``windows`` and ``hook_dir`` default to this machine and this directory;
    naming them builds the command for another."""
    return _with_host_arguments(_start_fields(script, python, host, windows=windows, hook_dir=hook_dir, py_launcher=py_launcher),
                                host)


def _start_fields(script: str, python: str, host: str, *, windows: "bool | None", hook_dir: "str | Path | None",
                  py_launcher) -> dict:
    """``hook_handler`` before the host's own arguments are added."""
    windows = os.name == "nt" if windows is None else windows
    directory = str(HOOK_DIR if hook_dir is None else hook_dir)
    if not windows:
        hook = str(HOOK_DIR / script) if hook_dir is None else f"{directory.rstrip('/')}/{script}"
        if host == "antigravity":
            return {"command": bare_form([*launcher_parts(python), *utf8_flags(python)], hook)}
        return {"command": " ".join([launcher_token(python), *utf8_flags(python), f'"{hook}"'])}
    hook = forward_slashes(directory).rstrip("/") + "/" + script
    interpreter, *extra = launcher_parts(python)
    interpreter = forward_slashes(interpreter)
    flags = utf8_flags(python)
    form, fallback = WINDOWS_FORMS.get(host, ("standard", None))
    launcher = [interpreter, *extra, *flags]
    if " " in interpreter:
        selector = (py_launcher or py_launcher_for)(interpreter)
        if selector:
            launcher = [*selector.split(), *extra, *flags]
        elif fallback == "parts":
            return parts_form(launcher, hook)
        elif fallback == "call":
            return {"command": call_form(launcher, hook)}
        else:
            raise CommandRefused(f"the interpreter path {interpreter!r} holds a space, no py launcher starts that interpreter, "
                                 f"and {host} needs a command whose first word is unquoted. {_REFUSAL_ADVICE}")
    return {"command": bare_form(launcher, hook) if form == "bare" else standard_form(launcher, hook)}


def _with_host_arguments(handler: dict, host: str) -> dict:
    """``handler`` with the arguments ``host`` needs after the script (``verify.HOST_ARGUMENTS``): ``--host copilot``
    makes the hooks answer in the shape Copilot reads."""
    extra = list(verify.HOST_ARGUMENTS.get(host, ()))
    if not extra:
        return handler
    if "args" in handler:
        return {**handler, "args": [*handler["args"], *extra]}
    return {**handler, "command": " ".join([handler["command"], *extra])}


def command_for(script: str, python: str, host: str = "claude", **options) -> str:
    """The command text that starts one hook on ``host`` (``hook_handler``), for a host whose config holds only text.
    Raises ``CommandRefused`` when the only form that starts there is the no-shell one."""
    handler = hook_handler(script, python, host, **options)
    if "args" in handler:
        raise CommandRefused(f"the interpreter path {handler['command']!r} holds a space and no py launcher starts that "
                             f"interpreter, so only a command with separate arguments starts it. {_REFUSAL_ADVICE}")
    return handler["command"]


def _own_handlers(config: dict, host: str, key: str, script: str) -> list[dict]:
    """The handlers under one event that launch ``script`` by the words they hold, whatever a shell makes of them."""
    return [handler for handler, _ in verify._handlers([config], verify.EVENTS[host][key], host)
            if verify.analyse(handler["command"], script, verify.handler_tokens(handler))["executable"]]


def _replace_defective(config: dict, host: str, python: str) -> list[str]:
    """Rewrite, in place, each Supreme Team handler whose command cannot start in the host's shell.

    The entry keeps its group, its matcher and every other field; only how the hook is started changes. Appending a
    working group beside it instead would leave the broken command registered, failing on every tool call. An entry
    that does not launch one of our scripts is never touched."""
    replaced = []
    if host in verify.FLAT_HOSTS:
        return replaced  # a flat host's entries are replaced whole by its own planner
    for key, script in verify.REQUIRED:
        for handler in _own_handlers(config, host, key, script):
            defects = verify.handler_defects(handler, host)
            if not defects:
                continue
            fresh = hook_handler(script, python, host)
            handler.pop("args", None)
            handler.update(fresh)
            replaced.append(f"{verify.EVENTS[host][key]} -> {script} (replaces a command that cannot start: {defects[0]})")
    return replaced


_FLAT_COMMAND_FIELDS = ("bash", "powershell", "command")


def _launches(entry, script: str) -> bool:
    """Whether a flat-host entry names ``script`` in any of its command fields, on whichever platform it was written."""
    if not isinstance(entry, dict):
        return False
    return any(isinstance(entry.get(field), str) and verify.analyse(entry[field], script)["configured"]
               for field in _FLAT_COMMAND_FIELDS)


def flat_entry(script: str, python: str, host: str) -> dict:
    """The handler the registrar writes for one hook on a flat host: the command in this platform's field, the matcher
    on the handler, and an explicit timeout (on Copilot a hook that times out lets the call through)."""
    entry = {"type": "command"}
    matcher = matcher_for(script, host)
    if matcher:
        entry["matcher"] = matcher
    entry[verify.command_field()] = command_for(script, python, host)
    entry["timeoutSec"] = verify.COPILOT_TIMEOUT_SECONDS
    return entry


def _plan_flat(config: dict, host: str, python: str, also: "list[dict] | None") -> tuple[dict, list[str]]:
    """``plan`` for a flat host. The file is ours, so each required hook ends as exactly one entry in the shape
    written today; an entry that launches something else is left as it is. An entry of ours written on the other
    platform keeps that platform's command beside the new one."""
    desired = {"version": 1, **config}
    hooks = desired.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("existing 'hooks' key is not an object; refusing to rewrite it")
    elsewhere = verify.hook_states(list(also or []), host)
    field = verify.command_field()
    other = "bash" if field == "powershell" else "powershell"
    added = []
    for key, script in verify.REQUIRED:
        event = verify.EVENTS[host][key]
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise ValueError(f"existing hooks.{event} is not a list; refusing to rewrite it")
        ours = [entry for entry in entries if _launches(entry, script)]
        if not ours and elsewhere[key]["registered"] and not elsewhere[key]["missing_tools"]:
            continue  # registered by another file of the same directory: a second entry would run it twice
        fresh = flat_entry(script, python, host)
        kept = next((entry[other] for entry in ours if isinstance(entry.get(other), str)), None)
        if kept:
            fresh[other] = kept
        if ours == [fresh]:
            continue
        position = next((index for index, entry in enumerate(entries) if _launches(entry, script)), len(entries))
        entries[:] = [entry for entry in entries if not _launches(entry, script)]
        entries.insert(min(position, len(entries)), fresh)
        added.append(f"{event} -> {script}" + (" (replaces the entry registered before)" if ours else ""))
    if not added and config.get("version") != 1 and any(hooks.values()):
        added.append("version -> 1")
    return (desired, added) if added else (config, [])


def plan(config: dict, host: str, python: str, also: "list[dict] | None" = None) -> tuple[dict, list[str]]:
    """The config with every required hook registered, and what changed.

    ``also`` holds registrations the host reads from another file (Codex ``config.toml`` inline hooks, the other
    files of a Copilot hook directory; ``verify.other_registrations``): a hook registered there counts as registered
    and is not written a second time."""
    if host in verify.FLAT_HOSTS:
        return _plan_flat(config, host, python, also)
    desired = dict(config)
    hooks = desired.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("existing 'hooks' key is not an object; refusing to rewrite it")
    added = _replace_defective(desired, host, python)
    states = verify.hook_states([desired, *(also or [])], host)
    for key, script in verify.REQUIRED:
        state = states[key]
        if state["registered"] and not state["missing_tools"]:
            continue
        event = verify.EVENTS[host][key]
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"existing hooks.{event} is not a list; refusing to rewrite it")
        handler = {"type": "command", **hook_handler(script, python, host)}
        status = STATUS_MESSAGES.get(script)
        if status:
            handler["statusMessage"] = status
        entry = {"hooks": [handler]}
        # A registration that already fires keeps its matcher; the new group covers only the tools it leaves out.
        tools = state["missing_tools"] if state["executable"] else verify.required_tools(script, host)
        if tools:
            entry = {"matcher": "|".join(tools), **entry}
        groups.append(entry)
        added.append(f"{event} -> {script}" + (f" (adds {'|'.join(tools)} to a narrower matcher)" if state["registered"] else ""))
    return desired, added


def written_handlers(before: dict, after: dict, host: str) -> list[tuple[str, dict]]:
    """``(script, handler)`` for each Supreme Team handler ``after`` holds and ``before`` did not, in hook order."""
    found = []
    for key, script in verify.REQUIRED:
        old = _own_handlers(before, host, key, script) if isinstance(before.get("hooks"), dict) else []
        found.extend((script, handler) for handler in _own_handlers(after, host, key, script) if handler not in old)
    return found


def probe_written(before: dict, after: dict, host: str) -> tuple[list[str], list[str]]:
    """Start each command this change writes, the way the host will (``verify.probe``): ``(failures, notes)``.

    A registration that cannot start is worse than none, because readiness would report the guard as on: with a
    failure nothing is written. A command that could not be probed (its interpreter is not on this machine) is a note.
    The form is the same for every hook, so the first is tried in every shell the host may use and the others in the
    first one only."""
    failures, notes = [], []
    for index, (script, handler) in enumerate(written_handlers(before, after, host)):
        results = verify.probe(handler, host, first_shell_only=index > 0, counted_only=True)
        for result in verify.probe_failures(results, host, handler):
            failures.append(f"{script} does not start under {result['shell']}: {result['detail']}")
        for result in results:
            if result["executes"] is None and f"{script}: {result['detail']}" not in notes:
                notes.append(f"{script}: {result['detail']}")
    return failures, notes


def checked_start(before: dict, after: dict, host: str, skip: bool = False) -> tuple[list[str], list[str]]:
    """``probe_written``, held to what ``host`` does with a hook that cannot start: ``(failures, notes)``.

    ``skip`` (``--no-probe``) writes unprobed and is accepted for a host that fails open. On a host that fails closed
    (``verify.FAIL_CLOSED_HOSTS``) a pre-tool command that does not start denies every tool call, so there the probe
    is not optional, and a command that could not be probed is not written either."""
    if host not in verify.FAIL_CLOSED_HOSTS:
        return ([], []) if skip else probe_written(before, after, host)
    if skip:
        return ([f"--no-probe is not accepted for {host}: a pre-tool hook that cannot start denies every tool call "
                 "there, so a command is written only after it has been started"], [])
    failures, notes = probe_written(before, after, host)
    unprobed = [f"{note}; on {host} a command that was not started is not written" for note in notes]
    return failures + unprobed, []


# --- files an earlier version wrote that the host does not read ------------------------------------------

def _only_ours(config) -> bool:
    """Whether a legacy hook file holds nothing but Supreme Team registrations: only ``hooks`` (and ``version``) at the
    top, and under it only handlers that launch one of the three hook scripts."""
    if not isinstance(config, dict) or set(config) - {"hooks", "version"}:
        return False
    hooks = config.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        return False
    scripts = [script for _, script in verify.REQUIRED]
    for groups in hooks.values():
        if not isinstance(groups, list) or not groups:
            return False
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list) or not handlers or set(group) - {"hooks", "matcher"}:
                return False
            for handler in handlers:
                command = handler.get("command") if isinstance(handler, dict) else None
                if not isinstance(command, str) or not any(
                        verify.analyse(command, script, verify.handler_tokens(handler))["configured"] for script in scripts):
                    return False
    return True


def legacy_files(host: str, scope: str) -> list[tuple[Path, bool]]:
    """``(path, only_ours)`` for each file an earlier version registered ``host`` in at ``scope`` that is still there.
    Copilot reads neither ``~/.config/github-copilot/hooks.json`` nor ``.github/hooks.json``."""
    legacy = verify.legacy_paths(host)
    if not legacy:
        return []
    path = legacy[0] if scope == "user" else legacy[1]
    if not verify._exists(path) or path.is_symlink() or not path.is_file():
        return []
    return [(path, _only_ours(verify._read(path)))]


def set_legacy_aside(host: str, scope: str, apply: bool) -> list[str]:
    """Move a legacy hook file that holds nothing but our entries out of the way, beside itself under the name a
    registration backup gets, and say so; leave any other legacy file and say that. With ``apply`` false nothing
    moves and the note says what would."""
    notes = []
    for path, ours in legacy_files(host, scope):
        if not ours:
            notes.append(f"{path} is where an earlier version registered {host} hooks, and {host} does not read it. It holds "
                         "entries that are not Supreme Team's (or that this copy cannot recognise), so it is left as it is")
            continue
        target = path.with_name(path.name + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        if not apply:
            notes.append(f"{path} holds only Supreme Team entries and {host} does not read it: it would be moved to {target.name}")
            continue
        try:
            os.replace(path, target)
            notes.append(f"{path} held only Supreme Team entries and {host} does not read it: moved to {target}")
        except OSError as exc:
            notes.append(f"{path} holds only Supreme Team entries and {host} does not read it; it could not be moved "
                         f"({type(exc).__name__}) and can be deleted")
    return notes


def double_run_note(host: str) -> "str | None":
    """Copilot CLI also runs the hooks of a repository's ``.claude/settings.json`` and ``.claude/settings.local.json``.
    When Supreme Team hooks are registered there, each tool call runs them twice: once in the shape Copilot reads and
    once in Claude Code's."""
    if host != "copilot":
        return None
    project = _state.project_root()
    files = [path for path in (project / ".claude/settings.json", project / ".claude/settings.local.json")
             if isinstance(verify._read(path), dict)
             and any(state["registered"] for state in verify.hook_states([verify._read(path)], "claude").values())]
    if not files:
        return None
    return (f"{' and '.join(str(path) for path in files)} registers the hooks for Claude Code, and Copilot CLI runs a "
            "repository's Claude Code hooks as well: in this project each tool call starts them twice. The guard decides "
            "the same both times and the post-tool hook records the call once")


CODEX_TRUST_NOTE = ("Codex skips a new or changed hook until it is trusted: start Codex and run /hooks once. Until then the "
                    "guard does not run there, and readiness cannot see whether a hook is trusted")
PARTS_NOTE = ("the interpreter path holds a space and no py launcher starts that interpreter, so the hook is registered as a "
              "command with separate arguments, which the host starts without a shell. A host version that does not read "
              "'args' would start the interpreter alone; check_readiness.py --probe shows whether the hooks start")
CODEX_INLINE_NOTE = ("config.toml beside this file has inline [hooks] tables. Codex reads both files and merges them with a "
                     "warning; a hook already registered there is not written here a second time")


def resolve_config(path: Path, through_links: bool) -> Path:
    """The file a registration is read from and written to.

    Replacing a symbolic link with a regular file leaves its target as it was, so a
    sync of the dotfiles that own the target would bring the old content back and the
    registration would disappear without a word. A link the operator owns (the
    user-level config, or a path named on the command line) is written through. A
    project-level one is refused: a cloned repository can plant a link that points
    anywhere, and a dangling or non-file link has nothing safe to write through to."""
    if not path.is_symlink():
        return path
    try:
        target = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{path} is a symbolic link that does not lead to a file ({exc.strerror or type(exc).__name__}); "
                         "refusing to replace it") from exc
    if not target.is_file():
        raise ValueError(f"{path} is a symbolic link to {target}, which is not a file; refusing to replace it")
    if not through_links:
        raise ValueError(f"{path} is a symbolic link to {target}; refusing to replace it with a regular file, which would "
                         f"leave {target} unchanged. Add the hooks to {target} itself (a dry run prints the entries)")
    return target


def link_warning(link: Path, target: Path) -> str:
    """What the operator is told before a registration is written through a link."""
    return (f"{link} is a symbolic link: writing through it to {target}. The hook paths written are machine-absolute, "
            "so a file that is synced to other machines has to be registered on each of them")


def _restrict_to_owner(path: Path) -> None:
    """Owner-only on Windows, where chmod is only a read-only flag: drop inherited access and grant the current
    user full control. Best effort — the write has already succeeded, and a lock-down the system denies leaves the
    file no wider than before."""
    try:
        account = getpass.getuser()
        subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:F"],
                       capture_output=True, text=True, check=False, timeout=30)
    except Exception:
        pass


def write_with_backup(path: Path, text: str, *, private: bool = False) -> Path | None:
    """Write ``text`` to ``path`` atomically, keeping a timestamped copy of the old file.

    An existing file keeps its permission bits and so does its backup, which is never
    wider than the original. A new file is owner-only when ``private`` (user-level host
    configuration, which can come to hold tokens) and gets the umask default otherwise.
    On Windows "owner-only" is the access list, not the mode bits, and a ``private`` write sets
    it on the file it writes, an existing file included.
    Returns the backup path when one was made.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    mode = 0o600 if private else None
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        backup = path.with_name(path.name + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        _fsutil.atomic_write(backup, path.read_bytes(), mode=mode, in_place=False)
    _fsutil.atomic_write(path, text.encode("utf-8"), mode=mode, in_place=False)
    if private and os.name == "nt":
        _restrict_to_owner(path)
    return backup


def record_hashes(states: dict, host: str) -> Path:
    """Merge the sha256 of every registered hook script, and of the modules in and beside each script's directory (``verify.module_hashes``), into the project's hash record."""
    path = _state.state_dir() / verify.HASH_RECORD
    current = verify._read(path)
    sections = {name: dict(current[name]) if isinstance(current, dict) and isinstance(current.get(name), dict) else {}
                for name in ("hooks", "directories")}
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for state in states.values():
        digest = verify.hook_hash(state["script"]) if state["registered"] and state["script"] else None
        if digest:
            directory = Path(state["script"]).parent
            sections["hooks"][verify.hash_key(state["script"])] = {"path": state["script"], "sha256": digest, "host": host,
                                                                   "recorded_at": recorded_at}
            sections["directories"][verify.hash_key(directory)] = {"path": str(directory), "files": verify.module_hashes(directory),
                                                                   "host": host, "recorded_at": recorded_at}
    record = {"schema_version": 1, **sections}
    _fsutil.atomic_write(path, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return path


def _record_current(host: str) -> int:
    """``--record-hashes``: record the scripts the host's existing registration launches."""
    objects = [value for _, value in verify._loaded(host) if isinstance(value, dict)]
    states = verify.hook_states(objects, host)
    missing = [script for key, script in verify.REQUIRED if not states[key]["registered"]]
    if missing:
        print(json.dumps({"ok": False, "error": f"not registered for {host}: {', '.join(missing)}; register the hooks first"}))
        return 2
    print(json.dumps({"ok": True, "recorded": str(record_hashes(states, host))}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or apply a scoped Supreme Team hook registration repair.")
    parser.add_argument("--host", choices=["claude", "codex", "copilot"], required=True)
    parser.add_argument("--scope", choices=["user", "project", "local"], default="project")
    parser.add_argument("--python", default=sys.executable or "python",
                        help="interpreter to register: a path, or a launcher with arguments such as 'py -3.13' "
                             "(default: the interpreter running this script)")
    parser.add_argument("--apply", action="store_true", help="write the change (default is a dry run)")
    parser.add_argument("--record-hashes", action="store_true",
                        help="record the sha256 of the registered hook scripts and change no host config")
    parser.add_argument("--no-probe", action="store_true",
                        help="with --apply, write without first starting each new command the way the host will "
                             "(the default refuses to write a command that does not start; not accepted for copilot, "
                             "where a hook that cannot start denies every tool call)")
    parser.add_argument(ALLOW_ABSOLUTE, action="store_true",
                        help="write a copilot project-scope file although it holds this machine's absolute paths "
                             "(refused by default: where those paths do not exist, every tool call is denied)")
    args = parser.parse_args()
    if args.record_hashes:
        return _record_current(args.host)
    try:
        path = target_path(args.host, args.scope)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    link = path
    try:
        path = resolve_config(link, through_links=args.scope == "user")
    except ValueError as exc:
        print(json.dumps({"ok": False, "path": str(link), "error": str(exc)}))
        return 2
    before_text = ""
    config: dict = {}
    if path.exists():
        try:
            before_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(json.dumps({"ok": False, "path": str(path), "error": f"existing file cannot be read as UTF-8 text ({exc}); refusing to overwrite"}))
            return 2
        try:
            config = json.loads(before_text) if before_text.strip() else {}
        except ValueError as exc:
            print(json.dumps({"ok": False, "path": str(path), "error": f"existing file is not valid JSON ({exc}); refusing to overwrite"}))
            return 2
        if not isinstance(config, dict):
            print(json.dumps({"ok": False, "path": str(path), "error": "existing config root is not an object"}))
            return 2
    refusal = absolute_refusal(args.host, args.scope, link, args.allow_absolute)
    if refusal:
        print(json.dumps({"ok": False, "path": str(link), "error": refusal}))
        return 2
    others = verify.other_registrations(args.host, path)
    inline = others if args.host == "codex" else []
    try:
        desired, added = plan(json.loads(json.dumps(config)), args.host, args.python, others or None)
    except ValueError as exc:
        print(json.dumps({"ok": False, "path": str(path), "error": str(exc)}))
        return 2
    after_text = json.dumps(desired, indent=2) + "\n"
    if not added:
        legacy = set_legacy_aside(args.host, args.scope, args.apply)
        for note in legacy:
            print(f"warning: {note}", file=sys.stderr)
        print(json.dumps({"ok": True, "path": str(path), "changes": [], "applied": False, "warnings": legacy,
                          "note": "no changes: every required hook is already registered and executable"}))
        return 0
    warnings = scope_warnings(args.host, args.scope, link)
    if path != link:
        warnings.append(link_warning(link, path))
    if inline:
        warnings.append(CODEX_INLINE_NOTE)
    if args.host == "codex":
        warnings.append(CODEX_TRUST_NOTE)
    twice = double_run_note(args.host)
    if twice:
        warnings.append(twice)
    if not args.apply:
        warnings.extend(set_legacy_aside(args.host, args.scope, False))
    if any("args" in handler for _, handler in written_handlers(config, desired, args.host)):
        warnings.append(PARTS_NOTE)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    diff = "".join(difflib.unified_diff(before_text.splitlines(True), after_text.splitlines(True), fromfile=str(path), tofile=str(path) + " (proposed)"))
    if not args.apply:
        print(diff)
        print(json.dumps({"ok": True, "path": str(path), "changes": added, "applied": False, "warnings": warnings, "note": "dry run; re-run with --apply to write"}))
        return 1
    failures, probe_notes = checked_start(config, desired, args.host, skip=args.no_probe)
    if failures:
        print(json.dumps({"ok": False, "path": str(path), "changes": added, "applied": False,
                          "error": "refusing to write a registration that cannot start: " + "; ".join(failures)}))
        return 2
    try:
        backup = write_with_backup(path, after_text, private=args.scope == "user")
        record = record_hashes(verify.hook_states([desired, *others], args.host), args.host)
    except OSError as exc:
        print(json.dumps({"ok": False, "path": str(path), "error": f"write failed: {exc}"}))
        return 2
    moved = set_legacy_aside(args.host, args.scope, True)
    for note in moved:
        print(f"warning: {note}", file=sys.stderr)
    warnings = warnings + moved
    print(json.dumps({"ok": True, "path": str(path), "changes": added, "applied": True, "backup": str(backup) if backup else None,
                      "hash_record": str(record), "warnings": warnings, "probe": "skipped" if args.no_probe else "started",
                      "probe_notes": probe_notes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
