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
  * records the sha256 of each registered hook script, and of every Python module
    in its directory, in ``.harness-state/hook-hashes.json`` so verify_registration
    can report a file that changed afterwards; ``--record-hashes`` re-records them
    on demand;
  * never replaces a symbolic link with a regular file: a user-level config that is
    a link (a dotfiles manager's) is written through, with a note saying so, and a
    project-level one, which a cloned repository can supply, is refused;
  * is idempotent: a second run reports "no changes".

Exit 0 = nothing to do or applied, 1 = changes needed but --apply not given,
2 = refused/engine error.
"""
from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import _fsutil
import _state
import verify_registration as verify

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
        ("copilot", "user"): home / ".config/github-copilot/hooks.json",
        ("copilot", "project"): project / ".github/hooks.json",
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


def launcher_token(python: str) -> str:
    """Quote an interpreter whose path contains spaces.

    A launcher that carries its own arguments (``py -3.13``, ``python -X utf8``) is
    left alone: quoting it would collapse two tokens into one path that does not
    exist. An unquoted ``C:/Program Files/Python313/python.exe`` would otherwise be
    split into a launcher and a stray argument, and verify_registration would report
    the hook as not executable.

    The test is the shape of the value, not whether the file exists here, so
    registering an interpreter for another machine behaves the same way.
    """
    if not python or '"' in python or " " not in python:
        return python
    if any(part.startswith("-") for part in python.split(" ")[1:]):
        return python
    return '"' + python + '"'


def launcher_parts(python: str) -> list[str]:
    """The interpreter command followed by the arguments that belong to it.

    Uses the same shape test as ``launcher_token``, for hosts that start the
    interpreter without a shell and so need the command and its arguments apart.
    """
    if not python or " " not in python:
        return [python]
    if '"' in python:
        return verify._tokens(python)
    parts = python.split()
    return parts if any(part.startswith("-") for part in parts[1:]) else [python]


def utf8_flags(python: str) -> list[str]:
    """``-X utf8`` unless the launcher already sets it."""
    parts = launcher_parts(python)
    if "-Xutf8" in parts or any(a == "-X" and b == "utf8" for a, b in zip(parts, parts[1:], strict=False)):
        return []
    return ["-X", "utf8"]


def command_for(script: str, python: str) -> str:
    return " ".join([launcher_token(python), *utf8_flags(python), f'"{HOOK_DIR / script}"'])


def plan(config: dict, host: str, python: str) -> tuple[dict, list[str]]:
    desired = dict(config)
    hooks = desired.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("existing 'hooks' key is not an object; refusing to rewrite it")
    states = verify.hook_states([config], host)
    added: list[str] = []
    for key, script in verify.REQUIRED:
        state = states[key]
        if state["registered"] and not state["missing_tools"]:
            continue
        event = verify.EVENTS[host][key]
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"existing hooks.{event} is not a list; refusing to rewrite it")
        handler = {"type": "command", "command": command_for(script, python)}
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


def _atomic_write(path: Path, data: bytes, mode: int | None) -> None:
    """Replace ``path`` through a per-process temp file that is created with ``mode``.

    ``mode`` None leaves the permission bits to the process umask; an explicit mode
    is applied again after creation because the umask can only have narrowed it. The
    bytes are flushed to disk first and the replace is retried the way every other
    writer in this directory retries it, because a host holding its own config open
    makes a Windows replace fail transiently. A write that needs no particular mode
    goes through ``_fsutil.atomic_write`` itself.
    """
    if mode is None:
        _fsutil.atomic_write(path, data)
        return
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        _fsutil.replace_with_retry(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


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


def write_with_backup(path: Path, text: str, *, private: bool = False) -> Path | None:
    """Write ``text`` to ``path`` atomically, keeping a timestamped copy of the old file.

    An existing file keeps its permission bits and so does its backup, which is never
    wider than the original. A new file is owner-only when ``private`` (user-level host
    configuration, which can come to hold tokens) and gets the umask default otherwise.
    Returns the backup path when one was made.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    mode = 0o600 if private else None
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
        backup = path.with_name(path.name + ".bak-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        _atomic_write(backup, path.read_bytes(), mode)
    _atomic_write(path, text.encode("utf-8"), mode)
    return backup


def record_hashes(states: dict, host: str) -> Path:
    """Merge the sha256 of every registered hook script, and of the modules in each script's directory, into the project's hash record."""
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
    _atomic_write(path, (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8"), None)
    return path


def _record_current(host: str) -> int:
    """``--record-hashes``: record the scripts the host's existing registration launches."""
    objects = [value for value in (verify._read(path) for path in verify._paths(host)) if isinstance(value, dict)]
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
    try:
        desired, added = plan(json.loads(json.dumps(config)), args.host, args.python)
    except ValueError as exc:
        print(json.dumps({"ok": False, "path": str(path), "error": str(exc)}))
        return 2
    after_text = json.dumps(desired, indent=2) + "\n"
    if not added:
        print(json.dumps({"ok": True, "path": str(path), "changes": [], "applied": False, "note": "no changes: every required hook is already registered and executable"}))
        return 0
    warnings = scope_warnings(args.host, args.scope, link)
    if path != link:
        warnings.append(f"{link} is a symbolic link: writing through it to {path}")
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    diff = "".join(difflib.unified_diff(before_text.splitlines(True), after_text.splitlines(True), fromfile=str(path), tofile=str(path) + " (proposed)"))
    if not args.apply:
        print(diff)
        print(json.dumps({"ok": True, "path": str(path), "changes": added, "applied": False, "warnings": warnings, "note": "dry run; re-run with --apply to write"}))
        return 1
    try:
        backup = write_with_backup(path, after_text, private=args.scope == "user")
        record = record_hashes(verify.hook_states([desired], args.host), args.host)
    except OSError as exc:
        print(json.dumps({"ok": False, "path": str(path), "error": f"write failed: {exc}"}))
        return 2
    print(json.dumps({"ok": True, "path": str(path), "changes": added, "applied": True, "backup": str(backup) if backup else None,
                      "hash_record": str(record), "warnings": warnings}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
