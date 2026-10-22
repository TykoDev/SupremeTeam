#!/usr/bin/env python3
"""Shared scaffolding for the hooks test modules.

``decide`` runs ``guard_hook.main`` in this process with a payload on stdin, so a
table of several hundred adversarial commands costs milliseconds instead of a
Python start-up each; ``run_hook`` runs the registered entry point as a real
subprocess for the cases that must prove the wiring (exit code, stdout, stderr).
Both read the project from ``CLAUDE_PROJECT_DIR`` exactly as a host does, and
both work on the code before and after a change, which is how a regression test
here proves it fails on the old guard.

Every other child process that runs hook code on a project, through ``run_cli``, ``save``
or ``run_broken`` or started by the test itself, gets an environment from ``clean_env``
or ``plain_env`` or is handed its project on its command line, and a test that runs
hook code in this process sets its project with ``in_project``. None of them takes
its project from the shell the suite started in: ``SUPREMETEAM_PROJECT_DIR``
outranks ``CLAUDE_PROJECT_DIR``, so a runner that kept it wrote into that project,
and the registration tests rewrote its ``.claude/settings.json``
(``test_state_hardening.ProjectIsolationTests``).

The rest are fixtures more than one module shares: a bash that can run the
installers, whether this account may make links, and the ways a record can be
unreadable or stand where it does not belong.
"""
from __future__ import annotations

import contextlib
import errno
import functools
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest import mock

HOOK_DIR = Path(__file__).resolve().parent
if str(HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(HOOK_DIR))

_PROJECT_VARS = ("SUPREMETEAM_PROJECT_DIR", "CLAUDE_PROJECT_DIR", "CODEX_WORKSPACE_DIR", "GITHUB_WORKSPACE")
_SESSION_VARS = ("SUPREMETEAM_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_SESSION_ID", "COPILOT_SESSION_ID", "GITHUB_RUN_ID")
# The prefixes of what a host or this harness exports: a plain terminal has none of them.
_HOST_SIGNALS = ("CLAUDE", "CODEX_", "COPILOT", "GITHUB_COPILOT", "SUPREMETEAM_")

NO_LINKS = "this account may not make symbolic links"


@contextlib.contextmanager
def project():
    """A scratch project directory with no markers; yields its resolved path."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp).resolve()


def write_guard(root: Path, state: dict) -> None:
    directory = root / ".harness-state"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "guard-state.json").write_text(json.dumps(state), encoding="utf-8")


def clean_env(root: Path, **extra: str) -> dict:
    """This process's environment with ``root`` as the only project and no session: what a host gives a hook."""
    env = os.environ.copy()
    for name in (*_PROJECT_VARS, *_SESSION_VARS):
        env.pop(name, None)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    env.update(extra)
    return env


def plain_env(home: Path, **extra: str) -> dict:
    """An ordinary terminal: no host signal, no harness setting, no project or session variable, and a scratch home."""
    env = {name: value for name, value in os.environ.items()
           if not name.startswith(_HOST_SIGNALS) and name not in (*_PROJECT_VARS, *_SESSION_VARS)}
    env["HOME"] = env["USERPROFILE"] = str(home)
    env.update(extra)
    return env


def in_project(root: Path, **extra: str):
    """For a ``with`` (or ``enterContext``): this process's environment as ``clean_env`` builds it, for hook code that
    runs here and reads its project from the environment."""
    return mock.patch.dict(os.environ, clean_env(root, **extra), clear=True)


def encode(payload) -> bytes:
    if isinstance(payload, bytes):
        return payload
    return (payload if isinstance(payload, str) else json.dumps(payload)).encode("utf-8")


def run_hook(script: str, payload, root: Path, *, python: "str | None" = None, text: bool = False,
             **env_extra: str) -> subprocess.CompletedProcess:
    """Run a registered hook script as a subprocess; ``payload`` may be bytes to send undecodable input.

    ``python`` names another interpreter than the one running the tests (see ``older_interpreters``); ``text`` gives
    stdout and stderr as text, read as the UTF-8 the hooks write."""
    proc = subprocess.run([python or sys.executable, str(HOOK_DIR / script)], input=encode(payload), capture_output=True,
                          env=clean_env(root, **env_extra), check=False)
    if text:
        return subprocess.CompletedProcess(proc.args, proc.returncode, proc.stdout.decode("utf-8", "replace"),
                                           proc.stderr.decode("utf-8", "replace"))
    return proc


def run_cli(script: "str | Path", *args: str, env: dict, cwd: "Path | None" = None, input: "str | None" = None,
            timeout: "float | None" = None) -> subprocess.CompletedProcess:
    """Run a script of this directory (or the path given) with its arguments, as text.

    ``env`` has no default, so a run never inherits the shell's project: build it with ``clean_env`` or ``plain_env``.
    Without ``input`` the script's stdin is empty, never the terminal or the pipe the suite was started on."""
    path = script if isinstance(script, Path) else HOOK_DIR / script
    return subprocess.run([sys.executable, str(path), *args], input=input, stdin=subprocess.DEVNULL if input is None else None,
                          text=True, capture_output=True, cwd=None if cwd is None else str(cwd), env=env, timeout=timeout,
                          check=False)


def save(root: Path, run_id: str, *args: str) -> tuple[int, dict]:
    """``save_run.py`` on ``root`` as a subprocess: its exit code and the JSON it printed (``{"raw": text}`` for none).

    The ``=`` form of ``--run-id``, so an id that starts with a dash is not read as an option."""
    proc = run_cli("save_run.py", *args, "--project-root", str(root), f"--run-id={run_id}", env=clean_env(root))
    text = (proc.stdout or proc.stderr).strip()
    try:
        return proc.returncode, json.loads(text[text.index("{"):])
    except ValueError:
        return proc.returncode, {"raw": text}


def write_run(root: Path, run_id: str, *, status: str = "active", pointer: bool = True, phase_state: "str | None" = None) -> None:
    """A coherent saved run written record by record: its state, its lock with a fresh heartbeat, and (``pointer``) the
    latest pointer naming it. An active run holds the session pin; any other status has released it."""
    from datetime import datetime, timezone

    saves = root / "skillset-saves"
    run = saves / "runs" / run_id
    run.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    state = {"schema_version": 1, "run_id": run_id, "status": status, "session_pin": status == "active", "execution_mode": "test",
             "active_owner": "test", "evidence_paths": ["skillset-saves"], "revision": 1, "timestamp": now}
    if phase_state:
        state["phase_state"] = phase_state
    (run / "_state.md").write_text(json.dumps(state), encoding="utf-8")
    (run / "_lock.md").write_text(json.dumps({"schema_version": 1, "run_id": run_id, "owner": "test", "revision": 1,
                                              "status": "held" if status == "active" else "released",
                                              "session_pin": status == "active", "heartbeat": now}), encoding="utf-8")
    if pointer:
        (saves / "_latest.md").write_text(json.dumps({"schema_version": 1, "run_id": run_id, "revision": 1, "updated_at": now}),
                                          encoding="utf-8")


def pin_a_run(root: Path, run_id: str = "r1") -> None:
    """Create a run in ``root``, with the README as its evidence, so the project has an active, pinned Admiral run."""
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    code, out = save(root, run_id, "create", "--evidence", "README.md")
    if code:
        raise AssertionError(f"save_run.py create exited {code}: {out}")


def run_broken(script: str, what: str, payload, root: Path, *, message: str = "SECRET-DETAIL",
               **env_extra: str) -> subprocess.CompletedProcess:
    """Run a registered hook script as ``__main__``, the way a host does, with ``_state.<what>`` made to raise
    ``RuntimeError(message)``; it runs in ``root``, so nothing it writes lands in the checkout."""
    code = ("import runpy, sys, _state\n"
            f"def broken(*a, **k):\n    raise RuntimeError({message!r})\n"
            f"_state.{what} = broken\n"
            f"sys.argv = [{script!r}]\nrunpy.run_path({str(HOOK_DIR / script)!r}, run_name='__main__')\n")
    return subprocess.run([sys.executable, "-c", code], input=encode(payload), capture_output=True, cwd=str(root),
                          env=clean_env(root, PYTHONPATH=str(HOOK_DIR), **env_extra), check=False)


def older_interpreters() -> list:
    """Interpreters below the running one that are installed here, as ``(label, path)``; empty where there are none.

    A host that registered a bare ``python`` may launch the hooks with any of them, so the entry-point tests run the
    real scripts under each. Anything that is not the interpreter it says it is, or is not older, is left out."""
    found = []
    for minor in (10, 11, 12):
        path = shutil.which(f"python3.{minor}")
        if not path or (3, minor) >= sys.version_info[:2]:
            continue
        probe = subprocess.run([path, "-c", "import sys; print(sys.version_info[0], sys.version_info[1])"],
                               capture_output=True, text=True, check=False)
        if probe.stdout.split() == ["3", str(minor)]:
            found.append((f"3.{minor}", path))
    return found


@functools.cache
def find_bash() -> "str | None":
    """The first bash on PATH that can open a Windows path, else Git for Windows' own.

    On Windows `System32\\bash.exe` and its `WindowsApps` alias start WSL, whose bash reads
    `C:\\...` as a relative name, so the install.sh tests failed wherever WSL came first on
    PATH. A default Git install puts only `Git\\cmd` on PATH; its bash sits in `Git\\bin`.
    """
    if os.name != "nt":
        return shutil.which("bash")
    windows = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows"))
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        found = shutil.which("bash", path=entry) if entry else None
        if found and not os.path.normcase(found).startswith(windows) and "windowsapps" not in os.path.normcase(found):
            return found
    git = shutil.which("git")
    bundled = Path(git).resolve().parent.parent / "bin" / "bash.exe" if git else None
    return str(bundled) if bundled and bundled.is_file() else None


@functools.cache
def can_link() -> bool:
    """Whether this account may make a link to a directory: Windows asks for a privilege most accounts lack."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            os.symlink(tmp, Path(tmp, "link"), target_is_directory=True)
        except (OSError, NotImplementedError):
            return False
        return True


def modes_are_enforced() -> bool:
    """False for a process that bypasses file modes (root, Windows): a record with no permission bits can still be read."""
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "probe"
        probe.write_text("x", encoding="utf-8")
        probe.chmod(0)
        try:
            probe.read_text(encoding="utf-8")
        except PermissionError:
            return True
        return False


@contextlib.contextmanager
def refusing(*tails: str):
    """Reads of the records ending in these paths raise PermissionError, as they do on POSIX for an account that owner-only records exclude."""
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if any(self.as_posix().endswith(tail) for tail in tails):
            raise PermissionError(errno.EACCES, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    with mock.patch.object(Path, "read_text", read_text):
        yield


# Each system's way of failing the read of a directory, so a test reads one as every system would, whichever runs it.
SYSTEMS = ("this system", "Windows", "POSIX")


@contextlib.contextmanager
def read_as(system: str, *tails: str):
    """Reads of the records ending in these paths fail as ``system`` fails the read of a directory: Windows with the
    PermissionError it gives a file this account may not read, POSIX with IsADirectoryError, this system as it does."""
    if system == "this system":
        yield
        return
    error, code = (PermissionError, errno.EACCES) if system == "Windows" else (IsADirectoryError, errno.EISDIR)
    real = Path.read_text

    def read_text(self, *args, **kwargs):
        if any(self.as_posix().endswith(tail) for tail in tails):
            raise error(code, os.strerror(code), str(self))
        return real(self, *args, **kwargs)

    with mock.patch.object(Path, "read_text", read_text):
        yield


def directory_kinds() -> dict[str, Callable[[Path], None]]:
    """The ways a directory can stand where a record belongs on this system, each made at the path it is given: a plain
    one, a junction and a junction whose directory is gone (Windows), and a link to a directory where this account may
    make one. A target sits beside the record, so the project's cleanup removes it."""
    def plain(path: Path) -> None:
        path.mkdir()

    def junction(path: Path, *, dangling: bool = False) -> None:
        import _winapi

        target = path.with_name(f"{path.name}.target")
        target.mkdir()
        _winapi.CreateJunction(str(target), str(path))
        if dangling:
            target.rmdir()

    def link(path: Path) -> None:
        target = path.with_name(f"{path.name}.target")
        target.mkdir()
        path.symlink_to(target, target_is_directory=True)

    kinds: dict[str, Callable[[Path], None]] = {"a directory": plain}
    if os.name == "nt":
        kinds["a junction"] = junction
        kinds["a dangling junction"] = functools.partial(junction, dangling=True)
    if can_link():
        kinds["a link to a directory"] = link
    return kinds


@contextlib.contextmanager
def unsearchable(*directories: str):
    """Everything below the directories ending in these paths is out of reach, as it is for an account that may not search them.

    `Path.exists` and `Path.is_dir` answer no for it, as they do where they are built on `os.path` instead of `stat`, so a
    probe that goes through them reads a run it cannot reach as no run."""
    real = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and any(f"{name}/" in Path(path).as_posix() for name in directories):
            raise PermissionError(errno.EACCES, "Permission denied", os.fspath(path))
        return real(path, *args, **kwargs)

    with (mock.patch.object(os, "stat", stat), mock.patch.object(Path, "exists", lambda self, **_: os.path.exists(self)),
          mock.patch.object(Path, "is_dir", lambda self, **_: os.path.isdir(self))):
        yield


@contextlib.contextmanager
def fast_decisions():
    """Leave out the two costs of an in-process decision that a table of commands never checks, about nine tenths of
    each: the observation record every call writes, and Rule F's boundaries, built here once per project, home and Pi
    agent directory instead of once per call. A test that asserts an observation or a Rule F boundary does without."""
    import _state
    import guard_hook

    real = guard_hook._harness_boundaries
    built: dict = {}

    def boundaries(root):
        key = (str(root), *(os.environ.get(name) for name in ("HOME", "USERPROFILE", "PI_CODING_AGENT_DIR")))
        if key not in built:
            built[key] = real(root)
        return built[key]

    with (mock.patch.object(_state, "record_observation", lambda event, data: None),
          mock.patch.object(guard_hook, "_harness_boundaries", boundaries)):
        yield


def decide(payload, root: Path, module: str = "guard_hook", entry: str = "main") -> str:
    """The stdout of ``<module>.<entry>()`` for ``payload``, run in this process ('' when it stays silent)."""
    import importlib

    target = importlib.import_module(module)
    saved_env = {name: os.environ.get(name) for name in (*_PROJECT_VARS, *_SESSION_VARS)}
    for name in (*_PROJECT_VARS, *_SESSION_VARS):
        os.environ.pop(name, None)
    os.environ["CLAUDE_PROJECT_DIR"] = str(root)
    stdin = io.TextIOWrapper(io.BytesIO(encode(payload)), encoding="utf-8")
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            real_stdin, sys.stdin = sys.stdin, stdin
            try:
                getattr(target, entry)()
            except SystemExit:
                pass
            finally:
                sys.stdin = real_stdin
    finally:
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return out.getvalue()


def denied(output: str) -> bool:
    return '"permissionDecision": "deny"' in output


def reason(output: str) -> str:
    return json.loads(output)["hookSpecificOutput"]["permissionDecisionReason"] if output.strip() else ""


def bash(command: str, tool: str = "Bash") -> dict:
    return {"tool_name": tool, "tool_input": {"command": command}}


def edit(path: str, tool: str = "Write") -> dict:
    return {"tool_name": tool, "tool_input": {"file_path": path, "content": "x"}}
