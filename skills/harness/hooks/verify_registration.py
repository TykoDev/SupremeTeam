#!/usr/bin/env python3
"""Verify Supreme Team hook registration for Codex, Claude Code, or Copilot.

For every required hook the verifier reports independent states:

  configured  a command registered under the correct event names this
              script's resolved path (after ~ and environment expansion);
  resolvable  that script file exists on disk;
  executable  the command actually launches it: a Python launcher whose first
              positional argument is the script (``python -c``, ``python -m``,
              a wrapper that merely mentions the path, or a launcher option that
              swallows the path do not count).

A hook is REGISTERED when all three hold and at least one registered matcher
selects a tool the hook needs. Three more facts are reported next to it. None
turns a registration into a failure, because each has a legitimate cause:

  coverage     whether the matchers select every tool the hook needs. A narrower
               matcher is ``partial``; ``repair_registration.py`` adds a group
               for the missing tools.
  interpreter  the Python the command launches: found on PATH or not, and its
               version against the floor in runtime-manifest.yaml. The version is
               read by running that interpreter once with ``-I -S -c``; one inside
               the project directory is never run.
  integrity    whether the hook script, every other module in its directory, and
               the modules the hooks import from ``skills/scripts``, still match
               the sha256 recorded when it was registered. The directory is
               listed, not named, so a module added to it later is covered too.
               ``changed`` after a deliberate edit or an upgrade is expected. The
               record belongs to the project the registration ran from: any other
               project reads ``unrecorded``, where an edit of the hook files is not
               noticed, until it records its own, and the output names the record
               compared against.

``executable`` is also a statement about the shell. A host hands a hook command to
a shell, and the same text does not start in every one: Git Bash consumes the
backslashes of an unquoted Windows path, PowerShell reads a command that begins
with a quote as a string, and Antigravity cannot pass a quote at all.
``shell_defects`` reads the command text against the rules of each shell the host
can use on this platform (``host_shells``), and a command with a defect is
configured and resolvable but not executable. ``--probe`` goes further and starts
each registered command the way its host does, with ``--selftest`` appended, and
reports whether it ran, per shell. It runs the registered commands, so it is opt-in.

Whether the host actually fires the hook is a separate, host-observed fact this
verifier never claims; it is reported as ``observed: unverified``.

``--host auto`` checks every host that has an environment signal or any config
file, and names them. A host chosen that way with no config file is MISSING, and
with no host at all so is the whole check. ``--host all`` checks the three hosts
regardless. Naming one host whose config cannot be read at all is UNKNOWN.

Exit 0 when every selected host is fully registered, 1 when readable config is
missing required hooks (or ``--host auto`` finds no host), and 2 when the
host/config cannot be determined. ``--json`` adds a machine-readable report after
the text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath

try:
    import _bootstrap

    _bootstrap.ensure_paths()
    import _state
    from data_formats import load_data
except ImportError as exc:  # a catalog file this script imports is missing: say which, never a traceback
    if __name__ != "__main__":
        raise
    print(f"verify_registration: error ({exc}); status UNKNOWN. A catalog file it imports is missing; reinstall the catalog.")
    raise SystemExit(2) from exc

REQUIRED = [("pre", "pre_tool_use.py"), ("post", "post_tool_use.py"), ("prompt", "user_prompt_submit.py")]
_EVENT_MAP = {"pre": "PreToolUse", "post": "PostToolUse", "prompt": "UserPromptSubmit"}
# GitHub Copilot drops what a command hook prints for a prompt, so the routing reminder is registered on the start of
# the session, whose context it reads. The names are PascalCase on purpose: with them Copilot sends the payload the
# hooks already read (`tool_name`, `tool_input`, `cwd`) and reports its tools under the names Claude Code uses; the
# camelCase events carry `toolName` and `toolArgs`, which the guard does not read.
_COPILOT_EVENTS = {"pre": "PreToolUse", "post": "PostToolUse", "prompt": "SessionStart"}
# Google Antigravity has no prompt event: `PreInvocation` fires before every model call, and the bridge gives the
# routing reminder on the first one after a new prompt.
_ANTIGRAVITY_EVENTS = {"pre": "PreToolUse", "post": "PostToolUse", "prompt": "PreInvocation"}
EVENTS = {"claude": _EVENT_MAP, "codex": _EVENT_MAP, "copilot": _COPILOT_EVENTS, "antigravity": _ANTIGRAVITY_EVENTS}
HOSTS = tuple(EVENTS)

# A host whose payloads and answers are its own, so one bridge script is registered for every event in place of the
# three hooks, with the event as its argument (`antigravity_bridge.py PreToolUse`). The bridge runs the hooks.
BRIDGE = "antigravity_bridge.py"
HOST_SCRIPT = {"antigravity": BRIDGE}
# The bridge a maintainer installed by hand before the catalog had one. A registration that runs it is replaced.
LEGACY_BRIDGE = "supremeteam_agy_bridge.py"
# Antigravity's hook file is groups by name, each with its events. The registrar owns this one and keeps the others.
ANTIGRAVITY_GROUP = "supremeteam"
GROUPED_HOSTS = frozenset({"antigravity"})

# Hooks a host should run besides the three it has to: `context_events.py` on the two events around a context
# compaction, so that a run in flight is dumped before one and named after it. A missing one is a warning and never a
# failure, so a host version that does not know the event still installs and verifies. Copilot has none: its
# pre-compaction hook is a notification, whether a session start follows a compaction there is not documented, and an
# event name it might not accept is not worth writing into the file of a host that fails closed.
RECOMMENDED = [("compact", "context_events.py"), ("resume", "context_events.py")]
_CONTEXT_EVENTS = {"compact": "PreCompact", "resume": "SessionStart"}
RECOMMENDED_EVENTS = {"claude": _CONTEXT_EVENTS, "codex": _CONTEXT_EVENTS, "copilot": {}, "antigravity": {}}
# Scripts whose registered command names its host on every host (`--host claude`): the hook prints what that host
# reads at that event and nothing where it is not known to read anything.
NAMES_HOST = frozenset({"context_events.py"})

# The tools each hook has to see. The verifier checks registered matchers against
# these and repair_registration.py writes them, so the two cannot disagree.
MATCHERS = {
    "pre_tool_use.py": "Bash|PowerShell|Edit|Write|NotebookEdit",
    "post_tool_use.py": "Bash|PowerShell",
    "user_prompt_submit.py": None,
}

# Codex realizes file edits through its own patch tool, which the portable matcher
# above does not name. Keeping the extension here means the verifier, the repair
# and scripts/install_hooks.py always require and write the same matcher for the
# same host, so a repair after an install cannot silently narrow the registered scope.
HOST_EXTRA_TOOLS = {
    "codex": {"pre_tool_use.py": ("apply_patch",), "post_tool_use.py": ("apply_patch",)},
}

# GitHub Copilot, with the PascalCase events: its shell tools are reported as `Bash`, `create` as `Write`, and `edit`,
# `str_replace_editor` and `apply_patch` as `Edit` (its hooks reference). These are the names a registration has to
# select there; `PowerShell` and `NotebookEdit` are not names it uses.
HOST_TOOLS = {
    "copilot": {"pre_tool_use.py": ("Bash", "Edit", "Write"), "post_tool_use.py": ("Bash",)},
    # Antigravity's own tool names, as its CLI 1.4.12 sent them in real sessions.
    "antigravity": {"pre_tool_use.py": ("run_command", "write_file", "edit_file"), "post_tool_use.py": ("run_command",)},
}
# Names the registrar writes beside the required ones: Copilot's own tool names, in case it reports a tool
# untranslated. That mapping is documented and has not been seen in a session; a matcher that missed the name the
# host really uses would leave the guard out of the call without a word.
WRITTEN_EXTRA_TOOLS = {
    "copilot": {"pre_tool_use.py": ("bash", "powershell", "create", "edit", "str_replace_editor", "apply_patch"),
                "post_tool_use.py": ("bash", "powershell")},
    # The names Antigravity's documentation gives its edit tools, which the CLI did not use. The bridge reads both.
    "antigravity": {"pre_tool_use.py": ("write_to_file", "replace_file_content", "multi_replace_file_content")},
}

# A host whose hook file is one flat list of handlers per event, each with its own `matcher` and with the command in a
# field per platform (`bash`, `powershell`; `command` when the platform's field is absent). Claude Code and Codex
# nest handlers in matcher groups and keep the command in `command`.
FLAT_HOSTS = frozenset({"copilot"})
# Arguments the registrar appends to a host's command, and the verifier requires: the hooks answer GitHub Copilot in
# the shape it reads only when told to (`_state.output_host`). Without them a deny is not a deny there.
HOST_ARGUMENTS = {"copilot": ("--host", "copilot")}
# A host where a pre-tool hook that cannot start denies the tool call (any exit but 0 and a timeout). A registration
# for it is never written unprobed.
FAIL_CLOSED_HOSTS = frozenset({"copilot"})
# The file the registrar writes in Copilot's hook directories. It is ours alone, so nobody else's hook file is edited.
COPILOT_FILE = "supremeteam.json"
COPILOT_TIMEOUT_SECONDS = 30
_COPILOT_FILE_LIMIT = 32

# Python options that consume the following token.
_OPTS_WITH_ARG = {"-W", "-X", "--check-hash-based-pycs", "-Q"}
_PY_SELECTOR = re.compile(r"-\d(?:\.\d+)?(?:-\d\d)?")
_HOST_SIGNALS = {"codex": ("CODEX_",), "claude": ("CLAUDE",), "copilot": ("COPILOT", "GITHUB_COPILOT"),
                 "antigravity": ("ANTIGRAVITY",)}

RUNTIME_MANIFEST = Path(__file__).resolve().parents[2] / "runtime-manifest.yaml"

# sha256 of each registered hook script, of every module beside it and of the
# skills/scripts modules the hooks import, written under .harness-state/ when the
# hook is registered. repair_registration.py is the writer.
HASH_RECORD = "hook-hashes.json"

# The skills folders the installers write, relative to the home directory. A host
# runs the hooks of one of them and the others mirror it, so a registration that
# points at any of them is a registration of this harness.
INSTALL_ROOTS = (".agents/skills", ".codex/skills", ".claude/skills", ".cursor/skills", ".config/opencode/skills")

_PROBE = "import sys; print(*sys.version_info[:3])"
_PROBED: dict[tuple, tuple | None] = {}


# Hosts registered through a plugin package or an extension this verifier cannot read. Each tells the user its own
# state: pi at every session start ("SupremeTeam guard active", or why it is not enforcing), Cursor and OpenCode
# through their plugin lists. Readiness names the ones whose file is present, so that a guard which runs there is
# not reported as no guard at all, and says that it has not inspected them.
PLUGIN_HOSTS = {
    "cursor": ("plugin package", "its plugin list shows whether the package loaded"),
    "opencode": ("plugin", "it logs once when the interpreter cannot start"),
    "pi": ("extension", "it reports 'SupremeTeam guard active', or why it is not enforcing, at every session start"),
}


def plugin_host_files() -> dict[str, Path]:
    """Where each plugin host's registration lives on this machine (``scripts/install_hooks.py`` writes them)."""
    home = Path.home()
    agent = os.environ.get("PI_CODING_AGENT_DIR")
    return {
        "cursor": home / ".cursor" / "plugins" / "local" / "supremeteam-hooks" / "hooks" / "hooks.json",
        "opencode": home / ".config" / "opencode" / "plugins" / "supremeteam-hooks.js",
        "pi": (Path(agent).expanduser() if agent else home / ".pi" / "agent") / "extensions" / "supremeteam-guard.ts",
    }


def plugin_hosts() -> dict[str, dict]:
    """The plugin hosts whose registration file exists: ``{host: {path, kind, reports}}``. Presence is all that is
    claimed; nothing here says the host loaded the file."""
    found = {}
    for host, path in plugin_host_files().items():
        if _exists(path):
            kind, reports = PLUGIN_HOSTS[host]
            found[host] = {"path": str(path), "kind": kind, "reports": reports}
    return found


def copilot_home() -> Path:
    """Copilot CLI's configuration directory: ``$COPILOT_HOME`` when that is set, else ``~/.copilot``."""
    override = os.environ.get("COPILOT_HOME")
    return Path(override).expanduser() if override else Path.home() / ".copilot"


def copilot_hook_dirs() -> list[Path]:
    """The two directories Copilot reads hook files from: the user's and the repository's."""
    return [copilot_home() / "hooks", _state.project_root() / ".github" / "hooks"]


def legacy_paths(host: str) -> list[Path]:
    """Files an earlier version registered ``host`` in that the host does not read. Copilot reads ``*.json`` inside its
    two hook directories; ``~/.config/github-copilot/hooks.json`` and ``.github/hooks.json`` are neither."""
    if host != "copilot":
        return []
    return [Path.home() / ".config/github-copilot/hooks.json", _state.project_root() / ".github/hooks.json"]


def command_field(windows: "bool | None" = None) -> str:
    """The field of a flat handler that holds the command for this platform."""
    return "powershell" if (os.name == "nt" if windows is None else windows) else "bash"


def flat_command(entry: dict, windows: "bool | None" = None) -> "str | None":
    """The command a flat-host handler runs on this platform: its platform field, else ``command``, as the host
    falls back. None when it has neither, or is not a command handler."""
    if not isinstance(entry, dict) or str(entry.get("type") or "command") != "command":
        return None
    for field in (command_field(windows), "command"):
        if isinstance(entry.get(field), str) and entry[field].strip():
            return entry[field]
    return None


def host_arguments(script: str, host: str) -> tuple:
    """The arguments the registrar puts after ``script`` on ``host``: the ones the host needs (``HOST_ARGUMENTS``), else
    the host's own name for a script that asks for it (``NAMES_HOST``), else none."""
    return tuple(HOST_ARGUMENTS.get(host) or ((_state.HOST_ARGUMENT, host) if script in NAMES_HOST else ()))


def registered_script(host: str, script: str) -> str:
    """The script a registration of ``script`` names on ``host``: the host's bridge where it has one, else itself."""
    return HOST_SCRIPT.get(host, script)


def registration_arguments(script: str, host: str, event: "str | None" = None) -> tuple:
    """The arguments a registered command carries after its script: the event, for a host whose bridge serves every
    event; otherwise what ``host_arguments`` gives."""
    if host in HOST_SCRIPT:
        return (event,) if event else ()
    return host_arguments(script, host)


def antigravity_files() -> dict[str, Path]:
    """Antigravity's global hook file, its global skills list, and the workspace hook file of this project."""
    config = Path.home() / ".gemini" / "config"
    return {"hooks": config / "hooks.json", "skills": config / "skills.json", "workspace": _state.project_root() / ".agents" / "hooks.json"}


def common_install() -> Path:
    """The skills folder every host reads, where the installers put the catalog."""
    return Path.home() / ".agents" / "skills"


def recommended(host: str) -> list[tuple[str, str, str]]:
    """``(key, script, event)`` for each recommended hook of ``host``."""
    return [(key, script, RECOMMENDED_EVENTS.get(host, {})[key]) for key, script in RECOMMENDED
            if key in RECOMMENDED_EVENTS.get(host, {})]


def _carries(tokens: list, arguments: tuple) -> bool:
    """Whether a command's words hold ``arguments`` in a row; true when there are none to hold."""
    wanted = list(arguments)
    return not wanted or any(tokens[index:index + len(wanted)] == wanted for index in range(len(tokens)))


def has_host_arguments(tokens: list, host: str) -> bool:
    """Whether a command's words carry the arguments ``host`` needs (``HOST_ARGUMENTS``); true for a host that needs none."""
    return _carries(tokens, HOST_ARGUMENTS.get(host, ()))


def _norm(value) -> str:
    # normcase is case-insensitive on Windows and preserves case on POSIX.  A
    # vendored path with the wrong case must not pass on a case-sensitive host.
    return os.path.normcase(str(value).replace("\\", "/"))


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _roots() -> list[Path]:
    """The hook directories a registered command may name: this one, ``SUPREMETEAM_HOOK_ROOT``, and the copy in each
    install root of the home directory, so a check run from a mirror recognises the registration the installer wrote."""
    roots = [Path(__file__).resolve().parent]
    explicit = os.environ.get("SUPREMETEAM_HOOK_ROOT")
    if explicit:
        roots.insert(0, Path(explicit).expanduser().resolve())
    for relative in INSTALL_ROOTS:
        installed = (Path.home() / relative / "harness" / "hooks").resolve()
        if installed not in roots and all((installed / script).is_file() for _, script in REQUIRED):
            roots.append(installed)
    return roots


def repair_command(host: str, *options: str) -> str:
    """The command that runs the repair tool beside this verifier, wherever this copy lives.

    A checkout-relative ``skills/harness/hooks/...`` path does not exist in an
    installed copy, and a bare ``python`` may be missing or below the floor, so the
    command names this script's directory and the interpreter running it."""
    parts = [sys.executable, str(Path(__file__).resolve().with_name("repair_registration.py")), "--host", host, *options]
    return " ".join(f'"{part}"' if " " in part else part for part in parts)


def _tokens(command: str) -> list[str]:
    """Split shell-like command text without treating Windows backslashes as escapes."""
    raw = re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\S+', command)
    return [token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'" else token
            for token in raw]


def _python_launcher(token: str) -> bool:
    name = Path(token.strip('"\'')).name.lower()
    return bool(re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?|py(?:\.exe)?", name))


def _expand(token: str) -> str:
    """Expand ~, $VAR, ${VAR}, and %VAR%; unset project variables fall back to
    the project directory so a config written for the host still verifies."""
    project = str(_state.project_root())

    def sub(match):
        name = match.group(1) or match.group(2) or match.group(3)
        value = os.environ.get(name)
        if value is None and name in _state.PROJECT_ENV:
            value = project
        return value if value is not None else match.group(0)

    expanded = re.sub(r"\$\{(\w+)\}|\$(\w+)|%(\w+)%", sub, token)
    return os.path.expanduser(expanded)


def _place(token: str) -> Path:
    """Where an expanded command word points: a relative one is read from the project root, as a host started there
    runs it, never from the directory this check happens to run in, so the verdict does not depend on it."""
    path = Path(token)
    return (path if path.is_absolute() else _state.project_root() / path).resolve()


def handler_tokens(handler: dict) -> list[str]:
    """The words one registered handler starts.

    ``command`` is split as text. With an ``args`` list the host starts ``command`` directly and no shell reads it, so
    ``command`` is one word however many spaces its path holds. A leading PowerShell call operator (``&``) is not a word."""
    command = handler.get("command") if isinstance(handler, dict) else None
    if not isinstance(command, str):
        return []
    args = handler.get("args")
    if isinstance(args, list):
        return [command, *(str(arg) for arg in args)]
    tokens = _tokens(command)
    return tokens[1:] if tokens[:1] == ["&"] else tokens


def analyse(command: str, script: str, tokens: "list[str] | None" = None) -> dict:
    """Classify one registered command against one expected hook script. ``tokens`` are its words when the caller
    has them from a handler (``handler_tokens``); otherwise the command text is split."""
    result = {"configured": False, "resolvable": False, "executable": False, "interpreter_on_path": None, "script": None, "reason": ""}
    tokens = list(tokens) if tokens is not None else handler_tokens({"command": command})
    # Skip leading VAR=value assignments.
    while tokens and re.match(r"^\w+=", tokens[0]):
        tokens.pop(0)
    if not tokens:
        result["reason"] = "empty command"
        return result
    launcher = tokens[0]
    expected = {_norm((root / script).resolve()) for root in _roots()}
    placed = [_place(t) for t in (_expand(t) for t in tokens[1:]) if t]
    if not ({_norm(path) for path in placed} & expected):
        result["reason"] = "script path not referenced"
        return result
    result["configured"] = True
    existing = [path for path in placed if _norm(path) in expected and path.is_file()]
    result["resolvable"] = bool(existing)
    result["script"] = str(existing[0]) if existing else None
    if not _python_launcher(launcher):
        result["reason"] = f"launcher {launcher!r} is not a Python interpreter"
        return result
    # Find the first positional argument after interpreter options.
    script_token = None
    index = 0
    args = tokens[1:]
    while index < len(args):
        token = args[index]
        if Path(launcher).name.lower().startswith("py") and _PY_SELECTOR.fullmatch(token):
            index += 1  # py launcher version selector
            continue
        if token in {"-c", "-m"}:
            result["reason"] = f"interpreter option {token} means the script argument is not executed"
            return result
        if token in _OPTS_WITH_ARG:
            index += 2
            continue
        if token.startswith("-") and token != "-":
            index += 1
            continue
        script_token = token
        break
    if script_token is None:
        result["reason"] = "no script argument in executable position"
        return result
    resolved = _norm(_place(_expand(script_token)))
    if resolved not in expected:
        result["reason"] = "script path appears as data, not as the executed script"
        return result
    if not Path(_expand(script_token)).is_absolute():
        # A host runs the command from whatever directory the session is in, and Python exits 2 when it cannot open
        # the script, which Claude Code reads from a PreToolUse hook as a block: from a subdirectory every tool call fails.
        result["reason"] = ("script path is relative, so it runs only from the project root; register it by absolute "
                            "path or through $CLAUDE_PROJECT_DIR (repair_registration.py writes the absolute path)")
        return result
    if not result["resolvable"]:
        result["reason"] = "script file does not exist at the configured path"
        return result
    launcher_path = Path(_expand(launcher))
    result["interpreter_on_path"] = bool(shutil.which(launcher) or (launcher_path.is_absolute() and launcher_path.is_file()))
    result["executable"] = True
    result["reason"] = "ok" if result["interpreter_on_path"] else "ok (interpreter not found on this PATH; host may supply it)"
    return result


# --- which shell reads the command ------------------------------------------------------------------
#
# Observed in real sessions on Windows (Claude Code 2.1.322, Codex CLI 0.166.0, Antigravity CLI 1.4.12): Claude Code
# hands a hook command to Git Bash, to PowerShell when the handler says ``"shell": "powershell"``, and starts it directly
# when the handler carries ``args``; Antigravity hands it to ``cmd /C`` with its quotes escaped. Codex's and Cursor's
# shell is not established, so both ``cmd`` and PowerShell are assumed. On POSIX every host uses ``sh``.

SELFTEST = "--selftest"
_SHELL_KINDS = {"sh": "posix", "git-bash": "posix", "pwsh": "powershell", "powershell": "powershell", "cmd": "cmd",
                "cmd /C": "antigravity", "direct": "direct"}


def git_bash() -> "str | None":
    """The bash Claude Code runs hooks through on Windows, or None.

    ``CLAUDE_CODE_GIT_BASH_PATH`` when it names a file, else the bash of the Git for Windows that ``git`` on PATH belongs
    to, else its default folders. Never ``bash`` from PATH: on Windows that is often ``System32\\bash.exe``, which starts
    WSL, and Claude Code does not use it."""
    if os.name != "nt":
        return None
    candidates = [os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")]
    git = shutil.which("git")
    if git:
        folder = Path(git).resolve().parent
        candidates += [folder.parent / "bin" / "bash.exe", folder.parent.parent / "bin" / "bash.exe", folder / "bash.exe"]
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / ("Programs/Git" if variable == "LocalAppData" else "Git") / "bin" / "bash.exe")
    for candidate in candidates:
        try:
            if candidate and Path(candidate).is_file():
                return str(candidate)
        except OSError:
            continue
    return None


def powershells() -> list[tuple[str, str]]:
    """``(label, path)`` of each PowerShell on this Windows machine: PowerShell 7 (``pwsh``) and Windows PowerShell."""
    if os.name != "nt":
        return []
    found = []
    seven = shutil.which("pwsh")
    if not seven:
        default = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PowerShell" / "7" / "pwsh.exe"
        seven = str(default) if default.is_file() else None
    if seven:
        found.append(("pwsh", seven))
    five = shutil.which("powershell")
    if five:
        found.append(("powershell", five))
    return found


def host_shells(host: str, handler: "dict | None" = None, windows: "bool | None" = None) -> tuple:
    """The kinds of shell (``posix``, ``powershell``, ``cmd``, ``antigravity``) that may read a handler's command on
    ``host``. Empty for a handler the host starts directly (``args``)."""
    windows = os.name == "nt" if windows is None else windows
    handler = handler if isinstance(handler, dict) else {}
    if isinstance(handler.get("args"), list):
        return ()
    if not windows:
        return ("posix",)
    if host == "claude":
        pinned = {"bash": "posix", "powershell": "powershell"}.get(str(handler.get("shell") or "").lower())
        if pinned:
            return (pinned,)
        return ("posix",) if git_bash() else ("powershell",)
    if host == "antigravity":
        return ("antigravity",)
    if host == "copilot":
        return ("powershell",)
    return ("cmd", "powershell")


def shell_defects(command: str, shell: str) -> list[str]:
    """Why ``command`` cannot start under one kind of shell, read from its text alone. Empty when nothing is wrong.

    Three rules, each a failure seen in a real shell:

    * ``posix``: every word has to read the same under POSIX rules as it was written. Git Bash consumes the backslashes
      of an unquoted ``C:\\Users\\...`` path, so the interpreter it looks for does not exist and the hook never starts.
    * ``powershell``: a command may not begin with a quote unless it begins with the call operator. PowerShell reads
      ``"C:/Program Files/Py/python.exe" -X utf8 ...`` as a string expression followed by a syntax error.
    * ``antigravity``: no quote at all. Antigravity for Windows escapes them on the way to ``cmd /C``, and the
      interpreter receives ``\\"C:\\...`` as its argument.

    A leading call operator is PowerShell syntax, so it is a defect under ``posix`` and ``cmd``."""
    text = command.strip()
    literal = _tokens(text)
    if not literal:
        return []
    if shell == "posix":
        if literal[0] == "&":
            return ["the command begins with the PowerShell call operator (&), which a POSIX shell cannot run"]
        try:
            read = shlex.split(text, posix=True)
        except ValueError:
            return ["a POSIX shell cannot parse the command (an unbalanced quote)"]
        if read != literal:
            index = next((i for i, (a, b) in enumerate(zip(read, literal, strict=False)) if a != b), min(len(read), len(literal)))
            written = literal[index] if index < len(literal) else ""
            seen = read[index] if index < len(read) else ""
            return [f"a POSIX shell (Git Bash on Windows) reads {written!r} as {seen!r}: it takes the backslashes of an "
                    "unquoted path as escapes, so the command never starts. Register it with forward slashes"]
        return []
    if shell == "powershell":
        if text[0] in "\"'":
            return ["the command begins with a quote, which PowerShell reads as a string and not as a program to start; "
                    "leave the interpreter unquoted or begin with the call operator (&)"]
        return []
    if shell == "cmd":
        if literal[0] == "&":
            return ["the command begins with the PowerShell call operator (&), which cmd cannot run"]
        return []
    if shell == "antigravity":
        if '"' in text or "'" in text:
            return ["the command contains a quote: Antigravity escapes quotes on the way to cmd /C, so the interpreter "
                    "receives a path that does not exist. Register paths that hold no space, unquoted"]
        return []
    return []


def handler_defects(handler: dict, host: str) -> list[str]:
    """``shell_defects`` of one handler under every shell ``host`` may read it with on this platform."""
    command = handler.get("command") if isinstance(handler, dict) else None
    if not isinstance(command, str):
        return []
    found: list[str] = []
    for shell in host_shells(host, handler):
        for defect in shell_defects(command, shell):
            if defect not in found:
                found.append(defect)
    return found


# A probe runs only a plain interpreter-and-script command: anything a shell would read as a second command is refused.
_SHELL_OPERATORS = re.compile(r"[;|<>`\n\r&]|\$\(")
_PROBE_TIMEOUT = 30.0
_PROBE_CACHE: dict[tuple, dict] = {}


def _probe_refusal(handler: dict, tokens: list[str]) -> "str | None":
    """Why a registered command is not started by the probe, or None when it may be."""
    if not tokens:
        return "no command"
    if not isinstance(handler.get("args"), list):
        text = re.sub(r'"[^"]*"|\'[^\']*\'', " ", handler["command"].strip())
        if _SHELL_OPERATORS.search(text[1:] if text.startswith("&") else text):
            return "the command holds shell operators; a probe starts only a plain interpreter-and-script command"
    launcher = _expand(tokens[0])
    found = shutil.which(launcher) or (launcher if Path(launcher).is_file() else None)
    if not found:
        return f"interpreter {tokens[0]!r} was not found on this machine"
    try:
        if _state.project_root().resolve() in Path(found).resolve().parents:
            return "the interpreter is inside the project directory, and a diagnostic does not run a binary a repository could have planted"
    except OSError:
        return "the interpreter path cannot be resolved"
    return None


def _probe_runs(host: str, handler: dict, text: str) -> list[tuple[str, object]]:
    """``(shell label, what to start)`` for each way ``host`` may run the command ``text`` on this platform."""
    if os.name != "nt":
        return [("sh", ["sh", "-c", text])]
    shells = [(label, [path, "-NoProfile", "-NonInteractive", "-Command", text]) for label, path in powershells()]
    if host == "claude":
        pinned = str(handler.get("shell") or "").lower()
        if pinned == "powershell":
            return shells[:1]
        bash = git_bash()
        runs = [("git-bash", [bash, "-c", text])] if bash else []
        return runs if pinned == "bash" else runs + shells
    if host == "antigravity":
        # One argument under the standard argument-escaping rules, which is what Antigravity 1.4.12 does: a quote
        # in the command arrives escaped, and the command does not start.
        return [("cmd /C", ["cmd.exe", "/C", text])]
    if host == "copilot":
        return shells
    return [("cmd", f'cmd /d /s /c "{text}"'), *shells]


def _run_selftest(label: str, what, timeout: float) -> dict:
    # A command registered through a project variable (`$CLAUDE_PROJECT_DIR/...`) is given the project the way a host
    # gives it; a variable the environment already sets is left as it is.
    env = dict(os.environ)
    try:
        project = str(_state.project_root())
    except Exception:
        project = None
    for name in _state.PROJECT_ENV if project else ():
        env.setdefault(name, project)
    try:
        done = subprocess.run(what, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              stdin=subprocess.DEVNULL, check=False, env=env)
    except subprocess.TimeoutExpired:
        return {"shell": label, "executes": False, "detail": f"no answer within {timeout:g} seconds"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"shell": label, "executes": False, "detail": f"could not be started ({type(exc).__name__})"}
    lines = (done.stdout or "").strip().splitlines()
    if done.returncode == 0 and lines[-1:] == ["ok"]:
        return {"shell": label, "executes": True, "detail": "ok"}
    said = ((done.stderr or "").strip() or (done.stdout or "").strip()).splitlines()
    return {"shell": label, "executes": False,
            "detail": f"exit {done.returncode}" + (f": {_state.safe_text(said[-1], 200)}" if said else ", no output")}


def probe(handler: dict, host: str, *, first_shell_only: bool = False, counted_only: bool = False,
          timeout: float = _PROBE_TIMEOUT) -> list[dict]:
    """Start one registered hook the way ``host`` does, with ``--selftest`` appended, once per shell.

    Each result is ``{"shell", "executes", "detail"}``. ``executes`` is None when the command was not started: it holds
    shell operators, its interpreter is not on this machine (a registration written for another one), or the
    interpreter sits inside the project. The self-test imports what the hooks import, prints ``ok`` and reads and
    writes nothing, so a probe changes no state. ``counted_only`` leaves out the shells whose failure would not count
    (``probe_failures``), which is what a registrar needs; a diagnostic shows every shell. Results are kept for the
    life of the process."""
    tokens = handler_tokens(handler)
    refusal = _probe_refusal(handler, tokens)
    if refusal:
        return [{"shell": "none", "executes": None, "detail": "not probed: " + refusal}]
    if isinstance(handler.get("args"), list):
        runs: list[tuple[str, object]] = [("direct", [*tokens, SELFTEST])]
    else:
        runs = _probe_runs(host, handler, handler["command"].strip() + " " + SELFTEST)
        if counted_only:
            kinds = set(host_shells(host, handler))
            runs = [run for run in runs if _SHELL_KINDS.get(run[0]) in kinds]
    if not runs:
        return [{"shell": "none", "executes": None, "detail": "not probed: no shell this host uses was found on this machine"}]
    results = []
    for label, what in runs[:1] if first_shell_only else runs:
        key = (label, what if isinstance(what, str) else tuple(what))
        if key not in _PROBE_CACHE:
            _PROBE_CACHE[key] = _run_selftest(label, what, timeout)
        results.append(dict(_PROBE_CACHE[key]))
    return results


def probe_failures(results: list[dict], host: str, handler: "dict | None" = None) -> list[dict]:
    """The probe results that mean the hook does not start on ``host``: a failure under a shell the host uses here
    (``host_shells``), or of a direct start. A failure under a shell the host has no reason to use is reported, not counted."""
    kinds = set(host_shells(host, handler)) | {"direct"}
    return [result for result in results if result["executes"] is False and _SHELL_KINDS.get(result["shell"]) in kinds]


def required_tools(script: str, host: str) -> list[str]:
    """The tool names a registration of ``script`` has to select on ``host``; empty for an event with no tools."""
    if MATCHERS.get(script) is None:
        return []
    if host in HOST_TOOLS:
        return list(HOST_TOOLS[host].get(script, ()))
    tools = MATCHERS[script].split("|")
    for tool in HOST_EXTRA_TOOLS.get(host, {}).get(script, ()):
        if tool not in tools:
            tools.append(tool)
    return tools


def matcher_for(script: str, host: str) -> str | None:
    """The tool matcher the registrar writes for one hook on one host, or None for an unmatched event: the required
    names, then any the host may use in their place (``WRITTEN_EXTRA_TOOLS``)."""
    tools = required_tools(script, host)
    for tool in WRITTEN_EXTRA_TOOLS.get(host, {}).get(script, ()):
        if tool not in tools:
            tools.append(tool)
    return "|".join(tools) or None


def matcher_selects(matcher, tool: str) -> bool:
    """Whether a registered matcher fires for ``tool``: absent, empty and ``*`` select
    every tool, anything else is a regular expression over the whole tool name."""
    if matcher is None:
        return True
    if not isinstance(matcher, str):
        return False
    if matcher in ("", "*"):
        return True
    try:
        return re.fullmatch(matcher, tool) is not None
    except re.error:
        return tool in matcher.split("|")


def _handlers(objects: list[dict], event: str, host: "str | None" = None) -> list[tuple[dict, object]]:
    """Every registered ``(handler, matcher)`` pair for one event. The handler is the object in the config itself, so a
    repair can change it in place.

    For a flat host (``FLAT_HOSTS``) the handler is a copy of the entry with ``command`` set to the text the host runs
    on this platform (``flat_command``), so that everything that reads a handler reads one shape; the registrar
    replaces such an entry whole and never in place."""
    found = []
    for obj in objects:
        registered = obj.get("hooks") if isinstance(obj, dict) else None
        groups = registered.get(event) if isinstance(registered, dict) else None
        if host in FLAT_HOSTS:
            for entry in groups if isinstance(groups, list) else []:
                text = flat_command(entry)
                if text is not None:
                    found.append(({**entry, "command": text}, entry.get("matcher")))
            continue
        if host in GROUPED_HOSTS:
            # {group: {"enabled": bool, event: [matcher group | handler]}}: a tool event holds matcher groups, and an
            # event without tools (PreInvocation) holds handlers directly. A group switched off registers nothing.
            for group in obj.values() if isinstance(obj, dict) else ():
                if not isinstance(group, dict) or group.get("enabled") is False:
                    continue
                for entry in group.get(event) if isinstance(group.get(event), list) else []:
                    if not isinstance(entry, dict):
                        continue
                    nested = entry.get("hooks")
                    for hook in nested if isinstance(nested, list) else [entry]:
                        if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                            found.append((hook, entry.get("matcher") if isinstance(nested, list) else None))
            continue
        for group in groups if isinstance(groups, list) else []:
            hooks = group.get("hooks") or [] if isinstance(group, dict) else []
            matcher = group.get("matcher") if isinstance(group, dict) else None
            for hook in hooks if isinstance(hooks, list) else []:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    found.append((hook, matcher))
    return found


def _entries(objects: list[dict], event: str) -> list[tuple[str, object]]:
    """Every registered ``(command, matcher)`` pair for one event."""
    return [(handler["command"], matcher) for handler, matcher in _handlers(objects, event)]


def declared_minimum(default: str = "3.13") -> str:
    """Read the Python floor from runtime-manifest.yaml, the runtime contract.

    A hardcoded second opinion would let a check report "too old" on a version
    the manifest declares supported, so the manifest wins and this fallback only
    covers a manifest that is missing or unreadable. The file is read with the
    catalog's own loader, so it may be JSON or block YAML and a reformat of it is
    not mistaken for an unreadable manifest.
    """
    try:
        data = load_data(RUNTIME_MANIFEST)
        major, minor = (int(part) for part in str(data["runtime"]["python"]["minimum"]).split(".", 1))
        return f"{major}.{minor}"
    except Exception:
        return default


def _probe_version(path: str, selectors: list[str]) -> tuple | None:
    """The version of the interpreter at ``path``, or None when it cannot be read.

    A diagnostic must not run a binary that a cloned repository could have
    planted, so an interpreter inside the project directory is never executed.
    """
    key = (path, tuple(selectors))
    if key not in _PROBED:
        _PROBED[key] = _run_probe(path, selectors)
    return _PROBED[key]


def _run_probe(path: str, selectors: list[str]) -> tuple | None:
    try:
        resolved = Path(path).resolve()
        if resolved == Path(sys.executable).resolve():
            return tuple(sys.version_info[:3])
        if _state.project_root().resolve() in resolved.parents:
            return None
        done = subprocess.run([str(path), *selectors, "-I", "-S", "-c", _PROBE], capture_output=True, text=True,
                              timeout=5, stdin=subprocess.DEVNULL, check=False)
        major, minor, micro = (int(part) for part in done.stdout.split())
        return major, minor, micro
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def interpreter_report(command: str, tokens: "list[str] | None" = None) -> dict:
    """Which Python a registered command launches, and whether it meets the floor. ``tokens`` as for ``analyse``."""
    tokens = list(tokens) if tokens is not None else handler_tokens({"command": command})
    while tokens and re.match(r"^\w+=", tokens[0]):
        tokens.pop(0)
    launcher = tokens[0] if tokens else ""
    name = Path(launcher).name.lower()
    selectors = []
    if name in ("py", "py.exe"):
        for token in tokens[1:]:
            if not _PY_SELECTOR.fullmatch(token):
                break
            selectors.append(token)
    expanded = _expand(launcher)
    found = shutil.which(expanded) or (expanded if Path(expanded).is_file() else None)
    version = _probe_version(found, selectors) if found else None
    if version is None:
        named = re.search(r"python(\d+)\.(\d+)", name) or (re.fullmatch(r"-(\d)\.(\d+).*", selectors[0]) if selectors else None)
        version = (int(named.group(1)), int(named.group(2))) if named else None
    floor = tuple(int(part) for part in declared_minimum().split("."))
    return {
        "launcher": launcher,
        "path": found,
        "on_path": found is not None,
        "version": ".".join(str(part) for part in version) if version else None,
        "floor": ".".join(str(part) for part in floor),
        "meets_floor": None if version is None else tuple(version[:2]) >= floor,
    }


def interpreter_warning(report: dict | None) -> str | None:
    if not report:
        return None
    if report["meets_floor"] is False:
        return (f"interpreter {report['launcher']!r} is Python {report['version']}, below the {report['floor']} floor; "
                "the hooks will fail open and enforce nothing (point the registered command at a newer Python, "
                "or remove the three entries and register again)")
    if not report["on_path"]:
        return f"interpreter {report['launcher']!r} was not found on this PATH; the host must supply it"
    return None


def _blank(reason: str) -> dict:
    return {"configured": False, "resolvable": False, "executable": False, "interpreter_on_path": None, "script": None,
            "reason": reason, "command": None, "args": None, "handler": None, "shell_defects": [], "matcher": None,
            "missing_tools": [], "coverage": None, "registered": False, "interpreter": None, "changed_files": []}


def hook_states(objects: list[dict], host: str) -> dict[str, dict]:
    """Classify every required hook of one host against already-loaded config objects.

    The one place that decides what REGISTERED means, shared by this verifier,
    ``repair_registration.plan`` and ``scripts/install_hooks.py``.
    """
    return {key: _classify(objects, host, EVENTS[host][key], registered_script(host, script), required_tools(script, host),
                           registration_arguments(script, host, EVENTS[host][key]))
            for key, script in REQUIRED}


def recommended_states(objects: list[dict], host: str) -> dict[str, dict]:
    """The same classification for the hooks ``host`` should also run (``recommended``). Each state carries its
    ``event`` and ``hook``; none of them decides whether the host is registered."""
    return {key: {**_classify(objects, host, event, script, [], registration_arguments(script, host, event)),
                  "event": event, "hook": script}
            for key, script, event in recommended(host)}


def _classify(objects: list[dict], host: str, event: str, script: str, needed: list, arguments: tuple = ()) -> dict:
    """The state of one hook script under one event of one host, over already-loaded config objects. ``arguments``
    are the words the command has to carry after the script for the hook to mean anything on that host."""
    best = _blank("no command registered")
    runnable = []
    for handler, matcher in _handlers(objects, event, host):
        command = handler["command"]
        candidate = analyse(command, script, handler_tokens(handler))
        candidate.update(command=command, args=handler["args"] if isinstance(handler.get("args"), list) else None,
                         handler=handler, matcher=matcher, shell_defects=[])
        if candidate["executable"] and not _carries(handler_tokens(handler), arguments):
            wanted = " ".join(arguments)
            if host in HOST_SCRIPT:
                # The bridge serves every event and is told which by its argument: without it, it answers nothing.
                candidate.update(executable=False, reason=f"the command does not name its event ('{wanted}') after "
                                                          f"{script}, so the bridge does not know what it was run for")
            else:
                # The hook would start and answer in a shape this host does not read: a deny that denies nothing.
                candidate.update(executable=False, reason=f"the command does not carry '{wanted}', so the hook answers in a "
                                                          f"shape {host} does not read and a deny is not a deny there")
        if candidate["executable"]:
            # The words are right; now the shell that reads them. A command it cannot start is not a registration.
            defects = handler_defects(handler, host)
            if defects:
                candidate.update(executable=False, shell_defects=defects, reason=defects[0])
        if candidate["executable"]:
            runnable.append(candidate)
        elif candidate["configured"] and not best["configured"]:
            best = {**_blank(""), **candidate}
    if runnable:
        best = {**_blank(""), **runnable[0]}
        covered = [tool for tool in needed if any(matcher_selects(c["matcher"], tool) for c in runnable)]
        best["missing_tools"] = [tool for tool in needed if tool not in covered]
        best["coverage"] = "not_applicable" if not needed else "full" if not best["missing_tools"] else "partial" if covered else "none"
        best["registered"] = best["coverage"] != "none"
        if not best["registered"]:
            best["reason"] = (f"matcher {', '.join(repr(c['matcher']) for c in runnable)} selects none of the tools "
                              f"this hook needs ({', '.join(needed)})")
        best["interpreter"] = interpreter_report(best["command"], handler_tokens(best["handler"]))
    return best


def hook_hash(path) -> str | None:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def _hashed(name: str) -> bool:
    """True when ``module_hashes`` records a module of this name: anything but a test module or ``_testkit.py``."""
    return not name.startswith("test_") and name != "_testkit.py"


def module_hashes(directory) -> dict[str, str]:
    """sha256 of every Python module a hook can import from ``directory``, found by listing it, and of the modules
    the hooks import from the ``skills/scripts`` beside it, named ``scripts/<file>``.

    Naming the modules in ``directory`` would leave out the next one added, and the guard lives in the
    modules the three entry scripts import, not in the entry scripts. Test modules and the support they share
    (``_testkit.py``) are left out: no hook loads them, and editing one is not tampering. ``skills/scripts`` holds
    tools no hook runs, so only the files ``_bootstrap.enforcement_files`` names are recorded from it."""
    directory = Path(directory)
    found = {}
    for path in sorted(directory.glob("*.py")):
        digest = hook_hash(path) if _hashed(path.name) else None
        if digest:
            found[path.name] = digest
    for path in _bootstrap.enforcement_files(directory):
        digest = hook_hash(path) if path.parent != directory else None
        if digest:
            found[f"{path.parent.name}/{path.name}"] = digest
    return found


def _load_record(section: str) -> dict:
    directory = _state.existing_state_dir()
    data = _read(directory / HASH_RECORD) if directory else None
    found = data.get(section) if isinstance(data, dict) else None
    return found if isinstance(found, dict) else {}


def record_path() -> Path:
    """The hash record this project is compared against, whether or not it exists yet."""
    directory = _state.existing_state_dir()
    return (directory or _state.project_root() / ".harness-state") / HASH_RECORD


def load_hash_record() -> dict:
    """The recorded script hashes, read without creating the state directory."""
    return _load_record("hooks")


def load_module_record() -> dict:
    """The recorded hashes of each hook directory's modules, by directory."""
    return _load_record("directories")


def hash_key(script) -> str:
    return _norm(Path(script).resolve())


def changed_files(script: str | None, record: dict, modules: dict | None = None) -> list[str] | None:
    """Names that differ from what was recorded: the script, and each module beside it that changed, appeared or went.

    A recorded name ``module_hashes`` no longer records (``_testkit.py``, in a record an older release made) is not a
    change. None when neither the script nor its directory was recorded."""
    if not script:
        return None
    differing: set[str] = set()
    recorded = False
    own = record.get(hash_key(script))
    if isinstance(own, dict) and own.get("sha256"):
        recorded = True
        if own["sha256"] != hook_hash(script):
            differing.add(Path(script).name)
    directory = Path(script).parent
    beside = (modules or {}).get(hash_key(directory))
    files = beside.get("files") if isinstance(beside, dict) else None
    if isinstance(files, dict):
        recorded = True
        current = module_hashes(directory)
        differing |= {name for name in files.keys() | current.keys() if _hashed(name) and files.get(name) != current.get(name)}
    return sorted(differing) if recorded else None


def integrity_for(script: str | None, record: dict, modules: dict | None = None) -> str | None:
    """``unchanged``, ``changed`` or ``unrecorded`` for one registered script and the directory it sits in."""
    if not script:
        return None
    differing = changed_files(script, record, modules)
    return "unrecorded" if differing is None else "changed" if differing else "unchanged"


def _paths(host: str) -> list[Path]:
    home = Path.home()
    project = _state.project_root()
    if host == "claude":
        return [home / ".claude/settings.json", project / ".claude/settings.json", project / ".claude/settings.local.json"]
    if host == "codex":
        return [home / ".codex/hooks.json", project / ".codex/hooks.json"]
    if host == "antigravity":
        files = antigravity_files()
        return [files["hooks"], files["workspace"]]
    # Copilot runs the hooks of every `*.json` in its two hook directories, so each of them is read: the file the
    # registrar writes first, then the others (a bounded number), in name order.
    found: list[Path] = []
    for directory in copilot_hook_dirs():
        found.append(directory / COPILOT_FILE)
        try:
            others = sorted(path for path in directory.glob("*.json") if path.name != COPILOT_FILE and path.is_file())
        except OSError:
            others = []
        found.extend(others[:_COPILOT_FILE_LIMIT])
    return found


def other_registrations(host: str, path: Path) -> list[dict]:
    """What ``host`` reads besides the file at ``path``, as registration objects: a hook registered there is
    registered, and writing it to ``path`` as well would run it twice. For Codex the inline ``[hooks]`` tables of the
    ``config.toml`` beside ``hooks.json``; for Copilot the other ``*.json`` files of the same hook directory."""
    if host == "codex":
        inline = codex_inline_hooks(path)
        return [inline] if inline else []
    if host == "copilot":
        try:
            others = sorted(item for item in path.parent.glob("*.json") if item.name != path.name and item.is_file())
        except OSError:
            return []
        return [value for value in (_read(item) for item in others[:_COPILOT_FILE_LIMIT]) if isinstance(value, dict)]
    return []


def codex_inline_hooks(hooks_json: Path) -> "dict | None":
    """The ``[hooks]`` tables of the Codex ``config.toml`` beside ``hooks_json``, as a registration object, or None.

    Codex reads hooks from ``hooks.json`` and from inline ``[hooks]`` tables in ``config.toml`` at the same level, and
    merges the two with a warning. A hook registered inline is registered, and one written to both runs twice."""
    try:
        import tomllib

        data = tomllib.loads(hooks_json.with_name("config.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError, ImportError):
        return None
    hooks = data.get("hooks") if isinstance(data, dict) else None
    return {"hooks": hooks} if isinstance(hooks, dict) and hooks else None


def _loaded(host: str) -> list[tuple[Path, object]]:
    """Every config file of ``host`` with what it holds (None when absent or unreadable). For Codex a ``config.toml``
    with inline ``[hooks]`` tables is listed after the ``hooks.json`` it sits beside."""
    loaded: list[tuple[Path, object]] = []
    for path in _paths(host):
        loaded.append((path, _read(path)))
        inline = codex_inline_hooks(path) if host == "codex" else None
        if inline:
            loaded.append((path.with_name("config.toml"), inline))
    return loaded


def _apply_probe(state: dict, host: str) -> None:
    """Start the command behind one hook state and record the answer. A command that does not start under a shell the
    host uses is not a registration, whatever its text looks like."""
    handler = state.get("handler")
    if not isinstance(handler, dict) or not state["configured"] or not state["resolvable"]:
        return
    state["probe"] = probe(handler, host)
    failed = probe_failures(state["probe"], host, handler)
    if failed and state["registered"]:
        state.update(executable=False, registered=False,
                     reason=f"the command does not start under {failed[0]['shell']} ({failed[0]['detail']})")


def _check(host: str, probed: bool = False):
    loaded = _loaded(host)
    objects = [value for _, value in loaded if isinstance(value, dict)]
    result = hook_states(objects, host)
    record, modules = load_hash_record(), load_module_record()
    for state in result.values():
        state["probe"] = None
        if probed:
            _apply_probe(state, host)
        state["observed"] = "unverified"
        state["integrity"] = integrity_for(state["script"], record, modules) if state["registered"] else None
        state["changed_files"] = (changed_files(state["script"], record, modules) or []) if state["registered"] else []
    return host, loaded, result, list(REQUIRED)


def resolve_hosts(selection: str) -> dict[str, str]:
    """The hosts to check, each with why. ``auto`` keeps the hosts that have an
    environment signal or any config file, so a host the operator does not use is
    not reported as an unregistered one."""
    if selection == "all":
        return {host: "all hosts requested" for host in HOSTS}
    if selection != "auto":
        return {selection: "requested"}
    chosen = {}
    for host in HOSTS:
        reasons = []
        if any(name.startswith(prefix) for name in os.environ for prefix in _HOST_SIGNALS[host]):
            reasons.append("environment signal")
        if any(_exists(path) for path in [*_paths(host), *legacy_paths(host)]):
            reasons.append("config found")
        if reasons:
            chosen[host] = " and ".join(reasons)
    return chosen


def selected_states(selection: str = "auto") -> dict[str, dict]:
    """The hook states of each host ``selection`` picks, read from its config files as ``hook_states`` reads them."""
    return {host: hook_states([value for _, value in _loaded(host) if isinstance(value, dict)], host)
            for host in resolve_hosts(selection)}


def enforcement(states: dict[str, dict]) -> dict:
    """Whether the guard's refusals are live, from each selected host's hook states (``{host: {key: state}}``).

    ``live``: every host registers ``pre_tool_use.py`` with full tool coverage. ``off``: none registers it, so every
    guard, freeze and read-only record and the destructive-command rule are advice, not refusals. ``partial``: some host,
    or some tool, is left out. Readiness and ``guard_state.py`` print this one answer, so neither reads as protection that
    is not there."""
    pre = {host: (hooks or {}).get("pre") or {} for host, hooks in states.items()}
    live = [host for host, state in pre.items() if state.get("registered") and state.get("coverage") == "full"]
    if pre and len(live) == len(pre):
        return {"status": "live", "detail": f"pre_tool_use.py is registered with full tool coverage for {', '.join(live)}"}
    if not any(state.get("registered") for state in pre.values()):
        return {"status": "off", "detail": (f"no host registers pre_tool_use.py ({', '.join(pre) or 'no host found'}), so "
                                            "guard, freeze, read-only and destructive-command rules are advice, not refusals")}
    left = ", ".join(host for host in pre if host not in live)
    return {"status": "partial", "detail": f"pre_tool_use.py is missing or misses a tool for {left}, so a tool call there is "
                                           "not refused"}


RECOMMENDED_WHY = ("without it a context compaction during a run writes no dump and gives no resume note; add it with "
                   "repair_registration.py")


def skills_entry_defects(config: object) -> list[str]:
    """The entries of Antigravity's ``skills.json`` that it does not read: a path that is not absolute. Antigravity
    rejects ``~/.agents/skills`` in its log and lists no skill from it, without telling the user."""
    entries = config.get("entries") if isinstance(config, dict) else None
    paths = [entry.get("path") for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []
    return [str(path) for path in paths
            if isinstance(path, str) and path.strip() and not (PureWindowsPath(path).is_absolute() or path.startswith("/"))]


def lists_common_install(config: object) -> bool:
    """Whether a ``skills.json`` names the common install by an absolute path."""
    def folded(value) -> str:
        # `_norm` folds case where the platform does, and on Windows gives backslashes back: compare one spelling.
        return _norm(value).replace("\\", "/").rstrip("/")

    entries = config.get("entries") if isinstance(config, dict) else None
    wanted = folded(common_install())
    for entry in entries if isinstance(entries, list) else ():
        path = entry.get("path") if isinstance(entry, dict) else None
        if isinstance(path, str) and (PureWindowsPath(path).is_absolute() or path.startswith("/")) and folded(path) == wanted:
            return True
    return False


def antigravity_notes() -> list[str]:
    """What readiness has to say about Antigravity's skills list, which decides whether it sees the catalog at all."""
    files = antigravity_files()
    config = _read(files["skills"])
    notes = ["prompt routing on antigravity is given through PreInvocation, once per prompt: it has no prompt event, and "
             "the bridge (antigravity_bridge.py) runs the three hooks"]
    for path in skills_entry_defects(config):
        notes.append(f"defect: {files['skills']} names {path!r}, which is not an absolute path. Antigravity ignores such an "
                     "entry without telling the user, so it lists no skill from that folder; registering again writes the "
                     "absolute path")
    if not lists_common_install(config):
        notes.append(f"{files['skills']} does not name {common_install().as_posix()} by an absolute path, so Antigravity does "
                     "not list the catalog's skills; registering at user scope adds the entry")
    return notes


def context_pressure_note() -> str:
    """Whether a run in flight can be advised as the context window fills on Claude Code, and by what."""
    sidecar = any(isinstance(value, dict) and isinstance(value.get("statusLine"), dict)
                  and "context_statusline.py" in str(value["statusLine"].get("command") or "") for _, value in _loaded("claude"))
    if sidecar:
        return ("context pressure: the status-line sidecar (context_statusline.py) is configured, so a run in flight is "
                "advised at the thresholds of runtime-manifest.yaml context_pressure")
    if os.environ.get("SUPREMETEAM_CONTEXT_WINDOW"):
        return ("context pressure: read from the session transcript against SUPREMETEAM_CONTEXT_WINDOW; the status-line "
                "sidecar is not configured")
    return ("context pressure: no usage source, so a run is not advised as the context window fills. Configure the "
            "status-line sidecar (repair_registration.py --host claude --scope <scope> --statusline --apply), or give the "
            "window with SUPREMETEAM_CONTEXT_WINDOW or runtime-manifest.yaml context_pressure.window_tokens")


def host_notes(host: str) -> list[str]:
    """What an operator has to know about ``host`` that no hook state says."""
    if host == "claude":
        return [context_pressure_note()]
    if host == "antigravity":
        return antigravity_notes()
    if host != "copilot":
        return []
    notes = ["prompt routing on copilot is given at session start only: it drops what a command hook prints for a "
             "prompt, so user_prompt_submit.py is registered on SessionStart and gives the reminder once per session"]
    for path, directory in zip(legacy_paths(host), copilot_hook_dirs(), strict=True):
        if _exists(path):
            notes.append(f"{path} is where an earlier version registered Copilot hooks, and Copilot does not read it "
                         f"(it reads *.json in {directory}). Registering again sets the file aside when it holds "
                         "nothing but Supreme Team entries")
    return notes


def _hook_detail(state: dict) -> str:
    notes = []
    if not state["registered"]:
        notes.append(f"configured={str(state['configured']).lower()} resolvable={str(state['resolvable']).lower()}; {state['reason']}")
    elif state["coverage"] == "partial":
        notes.append(f"partial coverage: the matcher misses {', '.join(state['missing_tools'])}")
    return f"  ({'; '.join(notes)})" if notes else ""


def _probe_text(entry: dict) -> str:
    """One probe result as readiness prints it: ``git-bash yes``, ``powershell no (exit 1: ...)``, ``not probed: ...``."""
    if entry["executes"] is None:
        return entry["detail"]
    return f"{entry['shell']} yes" if entry["executes"] else f"{entry['shell']} no ({entry['detail']})"


def _print(host, loaded, result, required, absent_is_missing=False):
    print(f"\n[{host}]\nConfig files inspected:")
    for path, value in loaded:
        print(f"  - {path}  [{'read' if value is not None else 'absent' if not path.exists() else 'unreadable'}]")
    if not any(value is not None for _, value in loaded):
        # A host chosen by --host auto is one the operator uses, so having no
        # config file at all is a definite "nothing registered". Naming a host
        # that has no readable config stays UNKNOWN: the verifier cannot tell.
        if not (absent_is_missing and not any(_exists(path) for path, _ in loaded)):
            print("  status: UNKNOWN - no relevant host config could be read.")
            return None
    ok = True
    warnings: list[str] = []
    changed: list[str] = []
    for key, script in required:
        state = result[key]
        ok = ok and state["registered"]
        print(f"  [{'OK ' if state['registered'] else 'MISSING'}] {EVENTS[host][key]} -> {script}{_hook_detail(state)}")
        if state.get("probe"):
            print("      executes: " + "; ".join(_probe_text(entry) for entry in state["probe"]))
        warning = interpreter_warning(state["interpreter"])
        if warning and warning not in warnings:
            warnings.append(warning)
        if state["integrity"] == "changed":
            changed.extend(name for name in state["changed_files"] or [script] if name not in changed)
    for state in recommended_states([value for _, value in loaded if isinstance(value, dict)], host).values():
        if state["registered"]:
            print(f"  [OK ] {state['event']} -> {state['hook']}  (recommended)")
        else:
            print(f"  [-- ] {state['event']} -> {state['hook']}  (recommended, not registered: {RECOMMENDED_WHY})")
    for warning in warnings:
        print(f"  warning: {warning}")
    for note in host_notes(host):
        print(f"  note: {note}")
    recorded = record_path()
    states = {result[key]["integrity"] for key, _ in required if result[key]["registered"]}
    if changed:
        print(f"  note: {', '.join(sorted(changed))} changed since registration, by the record in {recorded} (expected after a "
              f"deliberate edit or an upgrade; if you made neither, restore the files). Record the new hashes with: "
              f"{repair_command(host, '--record-hashes')}")
    elif "unrecorded" in states:
        print(f"  integrity: not checked, {recorded} holds no record of these hook files. A registration records them in the "
              f"project it ran from, so an edit of them is not noticed from here until this project records them: "
              f"{repair_command(host, '--record-hashes')}")
    elif states == {"unchanged"}:
        print(f"  integrity: the hook files match the record in {recorded}")
    print("  observed: unverified - host firing is not proven by config inspection")
    warned = warnings or any(result[key]["coverage"] == "partial" for key, _ in required)
    print(f"  status: {'REGISTERED' if ok else 'MISSING'}{' (with warnings)' if ok and warned else ''}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Supreme Team hook registration (read-only).")
    parser.add_argument("--host", choices=["auto", "all", *HOSTS], default="auto",
                        help="auto checks the hosts that have an environment signal or a config file (default)")
    parser.add_argument("--json", action="store_true", help="append a machine-readable report")
    parser.add_argument("--probe", action="store_true",
                        help="start each registered command the way its host does, with --selftest appended, and report "
                             "whether it ran, per shell. This runs the registered commands")
    args = parser.parse_args()
    chosen = resolve_hosts(args.host)
    print("Supreme Team harness hook registration check")
    if args.host == "auto":
        listing = ", ".join(f"{host} ({why})" for host, why in chosen.items()) or "none (no host environment signal and no host config file)"
        print(f"Selected host scope: auto -> {listing}")
    else:
        print(f"Selected host scope: {args.host}")
    checks = [_check(host, probed=args.probe) for host in chosen]
    statuses = [_print(*check, absent_is_missing=args.host == "auto") for check in checks]
    if not chosen:
        print("\n[auto]\n  status: MISSING - no host configuration was found, so no hook is registered anywhere.")
    if args.json:
        report = {h: {"status": "registered" if s is True else "missing" if s is False else "unknown",
                      "hash_record": str(record_path()), "notes": host_notes(h),
                      "recommended": {key: {"event": state["event"], "hook": state["hook"], "registered": state["registered"],
                                            "reason": state["reason"]}
                                      for key, state in recommended_states([v for _, v in files if isinstance(v, dict)], h).items()},
                      "hooks": {k: v for k, v in r.items()},
                      "config_files": [{"path": str(p), "state": "read" if v is not None else "absent" if not p.exists() else "unreadable"} for p, v in files]}
                  for (h, files, r, _), s in zip(checks, statuses, strict=True)}
        print("JSON_REPORT: " + json.dumps(report, sort_keys=True))
    if chosen and all(status is True for status in statuses):
        return 0
    pending = [check[0] for check, status in zip(checks, statuses, strict=True) if status is not True]
    print("\nREGISTER_PROMPT: Supreme Team harness hooks are not fully registered for the selected host scope.")
    print(f"Register the {len(REQUIRED)} commands in the active host's native hook configuration.")
    print("The scripts live in skills/harness/hooks/; see that directory's README.md for exact examples,")
    print("or preview a scoped repair with: "
          + repair_command(pending[0] if len(pending) == 1 else "<host>", "--scope", "project"))
    return 1 if not chosen or any(status is False for status in statuses) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"verify_registration: error ({exc}); status UNKNOWN")
        raise SystemExit(2) from exc
