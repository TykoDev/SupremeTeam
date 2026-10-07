"""Bounded literal Python I/O targets. Never evaluate code or resolve runtime values."""
from __future__ import annotations

import ast
import re

MAX_SOURCE = 16_384
# How many `exec("...")` literals deep the pass reads; past that the program is an unplaced write.
MAX_NESTING = 3
_REMOVE = {"unlink", "remove", "rmdir", "removedirs", "rmtree"}
_FIRST = _REMOVE | {"mkdir", "makedirs", "truncate", "chmod", "chown", "utime", "touch"}
_RENAME = {"rename", "replace"}
_COPY = {"copy", "copyfile", "copy2", "copytree", "move", "link", "symlink"}
_METHOD = {"write_text", "write_bytes", "touch", "mkdir", "rmdir", "unlink", "chmod"}
# The destination argument of an archive extraction (`tarfile`, `zipfile`): absent, it is the working directory with an
# inventory this pass cannot read, so the write stays unplaced.
_EXTRACT = {"extractall": 0, "extract": 1}
_COMMAND_KEYWORDS = {"args", "cmd", "command"}
# Modules whose `open` is a function taking `(file, mode)`; a call through one is not a `Path.open(mode)`.
_OPENERS = {"io", "builtins", "gzip", "bz2", "lzma", "codecs", "tarfile", "shelve", "dbm", "tokenize", "wave", "fileinput"}
_MODE = re.compile(r"^[rwaxbtU+]{1,4}$")
_OS_WRITE_FLAG = re.compile(r"\bO_(?:WRONLY|RDWR|CREAT|APPEND|TRUNC|EXCL)\b")
_OS_FLAG_TEXT = re.compile(r"^[\w.\s|()]*$")
_PYTHON_EVAL = {"exec", "eval"}


def literal_path(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute)):
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        if name in {"Path", "PurePath", "PosixPath", "WindowsPath"} and len(node.args) == 1 and not node.keywords:
            return literal_path(node.args[0])
    return None


def _literal_strings(node) -> "list | None":
    """The strings a literal argument holds: a string, or a list or tuple of strings; None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)) and node.elts and all(
            isinstance(item, ast.Constant) and isinstance(item.value, str) for item in node.elts):
        return [item.value for item in node.elts]
    return None


def literal_command(node):
    """The literal text of the command a call hands a shell, or None when any part of it is built at run time.

    The command is the positional arguments (a string, or a list or tuple of strings joined by spaces, which is how an
    argument list runs), else an ``args``, ``cmd`` or ``command`` keyword. Other keywords (``shell=True``, ``cwd=``)
    do not name the command and are not read. Nothing else is interpreted.
    """
    sources = list(node.args) or [kw.value for kw in node.keywords if kw.arg in _COMMAND_KEYWORDS][:1]
    if not sources:
        return None
    # `os.execvp("rm", ["rm", "-rf", "x"])` names the program and then its argv, which already starts with it.
    if len(sources) >= 2 and isinstance(sources[0], ast.Constant) and isinstance(sources[1], (ast.List, ast.Tuple)):
        sources = sources[1:]
    words: list = []
    for source in sources:
        strings = _literal_strings(source)
        if strings is None:
            return None
        words.extend(strings)
    return " ".join(words)


def _mode_writes(mode) -> "bool | None":
    """True when a literal mode opens for writing, False when it reads, None when the mode is built at run time."""
    if mode is None:
        return False
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return any(c in mode.value for c in "wax+")
    return None


def _open_targets(node, attr: bool, receiver, module: str, argument) -> list:
    """The targets of an ``open`` call: ``open(file, mode)``, a module's ``open``, ``os.open(path, flags)`` or a
    ``Path.open(mode)`` method. A receiver that is a bare name is read as a module when the first argument is a path
    rather than a mode; a receiver with a run-time first argument is taken as a ``Path`` opened for writing."""
    if attr and module == "os":
        flags = argument(1, "flags")
        text = ast.unparse(flags) if flags is not None else ""
        if flags is not None and "O_" in text and _OS_FLAG_TEXT.match(text) and not _OS_WRITE_FLAG.search(text):
            return []
        return [(literal_path(argument(0, "path")), "python")]
    method = attr and module not in _OPENERS
    if method and isinstance(receiver, ast.Name):
        first = argument(0, "mode")
        if isinstance(first, ast.Constant) and isinstance(first.value, str) and not _MODE.match(first.value):
            method = False
    if any(kw.arg is None for kw in node.keywords):
        writes = None
    else:
        writes = _mode_writes(argument(0 if method else 1, "mode"))
    if writes is False:
        return []
    path = receiver if method else argument(0, "file")
    return [(literal_path(path), "python")]


def python_targets(source: str, mutates_func, runs_command=None, depth: int = 0):
    """Return (path-or-None, via) for recognizable writes; None means unplaced.

    ``mutates_func`` says whether a call (``"shutil.rmtree("``) is a file API the lists above do not name;
    ``runs_command`` whether a call by that name (``"os.system("``) hands a command to a shell. A command the program
    hands over as literal text is returned as ``(text, "launch")`` for the shell analyser to judge; one built at run
    time is an unplaced write. ``exec`` and ``eval`` of a literal are read as Python, ``MAX_NESTING`` deep.

    Aliases and arbitrary calls are not interpreted. The scanner retains its
    existing conservative mutation fallback for syntax/size gaps and other APIs.
    """
    if len(source) > MAX_SOURCE or depth > MAX_NESTING:
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return None
    targets = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, (ast.Name, ast.Attribute)):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        attr = isinstance(node.func, ast.Attribute)
        receiver = node.func.value if attr else None
        module = receiver.id if isinstance(receiver, ast.Name) else ""
        args = node.args
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        def argument(index, key=None, args=args, keywords=keywords):
            return args[index] if len(args) > index else keywords.get(key)
        if name == "open":
            targets.extend(_open_targets(node, attr, receiver, module, argument))
        elif name in _METHOD and attr and module not in {"os", "shutil"}:
            targets.append((literal_path(receiver), "rm" if name in _REMOVE else "python"))
        elif name in _FIRST:
            targets.append((literal_path(argument(0, "path")), "rm" if name in _REMOVE else "python"))
        elif name in _RENAME:
            paths = [receiver, argument(0, "target")] if attr and module not in {"os", "shutil"} else [argument(0, "src"), argument(1, "dst")]
            targets.extend((literal_path(path), "mv") for path in paths)
        elif name in _COPY:
            if name == "move":
                targets.append((literal_path(argument(0, "src")), "mv"))
            targets.append((literal_path(argument(1, "dst")), "cp -r"))
        elif name in _EXTRACT and attr:
            destination = argument(_EXTRACT[name], "path")
            targets.append((literal_path(destination) if destination is not None else None, "archive-extract"))
        elif name in _PYTHON_EVAL and not attr:
            program = argument(0, "source")
            nested = None
            if isinstance(program, ast.Constant) and isinstance(program.value, str):
                nested = python_targets(program.value, mutates_func, runs_command, depth + 1)
            if nested is None:
                targets.append((None, "python"))
            else:
                targets.extend(nested)
        else:
            try:
                function = ast.unparse(node.func) + "("
            except RecursionError:
                targets.append((None, "python"))
                continue
            if runs_command is not None and runs_command((module + "." if module else "") + name + "("):
                command = literal_command(node)
                targets.append((command, "launch") if command is not None else (None, "python"))
            elif mutates_func(function):
                targets.append((None, "python"))
    return targets
