#!/usr/bin/env python3
"""Atomic file replacement and advisory locking for the hook-directory writers.

``save_run.py``, ``guard_state.py`` and the hook state helpers each carried their
own copy of "write to a staging file, then replace", with different guarantees:
only the run-record writer retried the transient Windows sharing violation,
flushed to disk, or left no staging file behind on failure. This module is the one
copy, taken from the strongest variant, and the one lock policy: an operating
system advisory lock, which a crashed holder cannot leave behind, so no
stale-lock guess is ever needed.

Stdlib only and no import of any other hook module, so every one of them can
depend on it. Nothing here swallows an error except where the docstring says so;
the hooks that must fail open wrap their calls, and the writers that must not
(``save_run.py``, ``guard_state.py``) translate ``OSError`` into their own refusal.
"""
from __future__ import annotations

import errno
import os
import time
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None

_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_BINARY = getattr(os, "O_BINARY", 0)


class LockTimeout(Exception):
    """Another process held the lock for the whole wait."""


def why(exc: OSError) -> str:
    """The operating system's reason without the path, which would put an absolute path in a record."""
    return exc.strerror or type(exc).__name__


def replace_with_retry(tmp: Path, path: Path, attempts: int = 8) -> None:
    """``os.replace`` with short retries: on Windows a reader (host hook, indexer,
    antivirus) holding the target open makes the replace fail transiently with
    PermissionError / WinError 5."""
    delay = 0.05
    for attempt in range(attempts):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.8)


def _fsync(handle) -> None:
    try:
        os.fsync(handle.fileno())
    except OSError:
        pass  # a file system without fsync still got the bytes


def atomic_write(path: Path, data: "str | bytes", *, mode: "int | None" = None, notes: "list[str] | None" = None,
                 in_place: bool = True) -> None:
    """Replace ``path`` with ``data`` in one step, or leave it as it was; raises ``OSError``.

    The staging file is named per process, so writers that overlap never truncate
    each other's half-written bytes, and it is opened exclusively without following
    a link, so a staging name planted as a symlink is not written through. It is
    removed again on any failure, an interrupt included. A target whose ACL denies
    the rename (a file another sandbox user created) is overwritten in place after
    the retries, and that non-atomic step is appended to ``notes`` so it is visible
    rather than silent. ``in_place=False`` raises the denial instead and leaves the
    target untouched, for a file that has to be replaced whole or not at all.

    ``mode`` None leaves the permission bits to the process umask. An explicit mode
    is the one the file ends with, applied again after creation because the umask can
    only have narrowed it, and it is already in force when the bytes are written, so a
    file meant to be private is never readable between its creation and its chmod."""
    path = Path(path)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _BINARY, 0o666 if mode is None else mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            _fsync(handle)
        if mode is not None:
            os.chmod(tmp, mode)
        try:
            replace_with_retry(tmp, path)
        except PermissionError as exc:
            if not in_place or not path.exists():
                raise
            with open(path, "wb") as handle:
                handle.write(payload)
                handle.flush()
                _fsync(handle)
            try:
                tmp.unlink()
            except OSError:
                pass
            if notes is not None:
                notes.append(f"{path.name}: replaced in place (target ACL denies rename: {exc.__class__.__name__})")
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _try_lock(fd: int, fcntl_module, msvcrt_module) -> bool:
    """Take the exclusive lock without waiting: True if taken, False if another
    process holds it. Raises OSError when the file system cannot lock at all."""
    if fcntl_module is None and msvcrt_module is None:
        raise OSError(errno.ENOSYS, "no file locking on this platform")
    try:
        if fcntl_module is not None:
            fcntl_module.flock(fd, fcntl_module.LOCK_EX | fcntl_module.LOCK_NB)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt_module.locking(fd, msvcrt_module.LK_NBLCK, 1)
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return False
        raise
    return True


def _unlock(fd: int, fcntl_module, msvcrt_module) -> None:
    try:
        if fcntl_module is not None:
            fcntl_module.flock(fd, fcntl_module.LOCK_UN)
        else:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt_module.locking(fd, msvcrt_module.LK_UNLCK, 1)
    except OSError:
        pass  # closing the descriptor releases the lock either way


class AdvisoryLock:
    """Exclusive advisory lock on ``path``.

    The operating system drops the lock when its holder exits, so a killed writer
    cannot wedge anything. A file system that offers no locking, or a lock file
    that cannot be created, degrades to the unlocked behaviour with a note in
    ``notes``; only a lock another process actually holds past ``wait`` seconds is
    a timeout. By default that raises ``LockTimeout`` (a writer that must not race
    refuses); with ``fail_open`` the caller proceeds without the lock (a hook must
    never hold up the host). ``held`` says which happened.

    ``backends`` returns the ``(fcntl, msvcrt)`` modules to lock with, so a caller
    that owns those names, or a test standing in for another platform, can supply
    them."""

    def __init__(self, path: Path, wait: float, *, label: "str | None" = None, kind: str = "lock",
                 create_dir: bool = False, fail_open: bool = False, notes: "list[str] | None" = None,
                 backends=None) -> None:
        self.path = Path(path)
        self.wait = wait
        self.label = label or self.path.name
        self.kind = kind
        self.create_dir = create_dir
        self.fail_open = fail_open
        self.notes = notes
        self._backends = backends
        self.fd: "int | None" = None
        self.held = False

    def _modules(self) -> tuple:
        return self._backends() if self._backends else (fcntl, msvcrt)

    def _note(self, text: str) -> None:
        if self.notes is not None:
            self.notes.append(text)

    def _timed_out(self) -> None:
        raise LockTimeout(f"another process holds {self.label} after waiting {self.wait:g}s")

    def __enter__(self) -> "AdvisoryLock":
        try:
            if self.create_dir:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | _BINARY, 0o644)
        except OSError as exc:
            self._note(f"{self.kind} unavailable ({why(exc)}); this operation ran without mutual exclusion")
            return self
        fcntl_module, msvcrt_module = self._modules()
        deadline = time.monotonic() + self.wait
        delay = 0.005
        while True:
            try:
                self.held = _try_lock(self.fd, fcntl_module, msvcrt_module)
            except OSError as exc:
                self._note(f"{self.kind} unsupported here ({why(exc)}); this operation ran without mutual exclusion")
                break
            if self.held:
                return self
            if time.monotonic() >= deadline:
                self._close()
                if self.fail_open:
                    return self
                self._timed_out()
            time.sleep(delay)
            delay = min(delay * 2, 0.05)
        self._close()
        return self

    def __exit__(self, *exc_info: object) -> bool:
        if self.fd is not None:
            if self.held:
                _unlock(self.fd, *self._modules())
            self._close()
        return False

    def _close(self) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
