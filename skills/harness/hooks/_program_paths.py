"""Bounded literal Python I/O targets. Never evaluate code or resolve runtime values."""
from __future__ import annotations

import ast
import re
import shlex

MAX_SOURCE = 16_384
# How many `exec("...")` literals deep the pass reads; past that the program is an unplaced write.
MAX_NESTING = 3
_REMOVE = {"unlink", "remove", "rmdir", "removedirs", "rmtree"}
_FIRST = _REMOVE | {"mkdir", "makedirs", "truncate", "chmod", "chown", "utime", "touch", "mkfifo", "mknod"}
_RENAME = {"rename", "replace", "renames"}
_COPY = {"copy", "copyfile", "copy2", "copytree", "move", "link", "symlink"}
_METHOD = {"write_text", "write_bytes", "touch", "mkdir", "rmdir", "unlink", "chmod"}
# `Path` methods (Python 3.14) that put the path under the directory they name.
_INTO = {"copy_into", "move_into"}
# The modules whose functions above take paths, and the functions above a `Path` also has as methods, which take where
# the path goes as their one argument. Every file form of those takes that target, so one called with no positional
# argument and no target keyword, which `**` may hold, is not a file operation.
_MODULES = {"os", "shutil"}
_PATH_METHODS = {"rename", "replace", "copy", "move"}
_TARGET_KEYWORDS = {"src", "dst", "target", None}
_PATH_TYPES = {"Path", "PurePath", "PosixPath", "WindowsPath"}
# The modules `os` takes its file functions from: a function imported by name from one is `os`'s (`from posix import
# remove as r`).
_OS_NATIVE = {"posix", "nt"}
# The functions that run a command, by the module that has them. A call of one is read by `runs_command`, and so is one
# imported by name (`from subprocess import run as r`) or called through `import subprocess as sp`.
_LAUNCHERS = {
    "os": {"system", "popen"} | {verb + form for verb in ("exec", "spawn")
                                 for form in ("l", "le", "lp", "lpe", "v", "ve", "vp", "vpe")},
    "subprocess": {"run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput"},
    "pty": {"spawn"},
}
# The modules through which a program reaches those functions, `exec` and `eval` (`builtins`, or `__builtins__`).
_RUNNERS = {*_LAUNCHERS, "builtins"}
# `getattr` called by its own name names a function (`_function`); reached any other way (`g = getattr`,
# `builtins.getattr`, `os.__getattribute__("remove")`, `inspect.getattr_static`) it may name any, so the use is an
# unplaced write.
_GETTERS = {"getattr", "__getattribute__", "getattr_static"}
# Functions that reach the attribute or method whose name they are given (`operator.attrgetter("remove")(os)`).
_BY_NAME = {"attrgetter", "methodcaller"}
# What `tempfile` creates, by where its `suffix` argument is, which `prefix` and `dir` follow. It writes in `dir`, or in
# the system's temporary directory, outside the project, when `dir` is absent or None.
_TEMPORARY = {"mkstemp": 0, "mkdtemp": 0, "TemporaryDirectory": 0, "NamedTemporaryFile": 4, "TemporaryFile": 4,
              "SpooledTemporaryFile": 5}
# A program that changes its own working directory (`os.chdir`, `contextlib.chdir`) writes its relative paths, and runs
# its commands, somewhere the pass does not follow.
_CHDIR = {"chdir", "fchdir"}
# The program's own namespace, as `globals()`, `locals()` and `vars()` look it up.
_PROGRAM = object()
# Values that are never a module or a path: a literal, an f-string, a container or a comprehension.
_NEVER_A_PATH = (ast.Constant, ast.JoinedStr, ast.List, ast.Tuple, ast.Set, ast.Dict, ast.ListComp, ast.SetComp,
                 ast.DictComp, ast.GeneratorExp)
# Names through which a program can bind a name where its syntax tree shows no binding: code it runs
# (`exec("lst = os")`); the namespace itself (`globals()["lst"] = os`, `setattr`, a frame's `f_globals`) and what
# reaches it by name or by reference (`getattr`, `operator.attrgetter`, `pydoc.locate`, `gc.get_referrers`); and the
# import system, which decides what an import binds (`sys.modules["copy"] = shutil` before `import copy`). Any
# double-underscore name (`__main__`, `__dict__`, `__import__`) and `from ... import *` count with them, and so does one
# of them imported under a name of its own (`from builtins import globals as g`) or named in a string
# (`operator.attrgetter("f_globals")`).
_UNSEEN_BINDING = {"exec", "eval", "compile", "globals", "locals", "vars", "setattr", "getattr", "f_globals",
                   "f_locals", "attrgetter", "methodcaller", "getattr_static", "locate", "resolve_name",
                   "get_referrers", "get_referents", "get_objects", "modules", "meta_path", "path_hooks",
                   "path_importer_cache"}
# The destination argument of an archive extraction (`tarfile`, `zipfile`): absent, it is the working directory with an
# inventory this pass cannot read, so the write stays unplaced.
_EXTRACT = {"extractall": 0, "extract": 1}
# The names above by which a call is read as a file operation. A program that uses such a function other than by calling
# it (`f = os.remove`, `map(os.remove, paths)`) may call it anywhere, so the use is an unplaced write.
_FILE_FUNCTIONS = _FIRST | _RENAME | _COPY | _METHOD | _INTO | set(_EXTRACT) | {"open"}
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
        if name in _PATH_TYPES and len(node.args) == 1 and not node.keywords:
            return literal_path(node.args[0])
    return None


def _binds_unseen(word: str) -> bool:
    """True when a name or an attribute is one through which a program can bind a name unseen (``_UNSEEN_BINDING``)."""
    return word in _UNSEEN_BINDING or (word.startswith("__") and word.endswith("__"))


def _imports(tree, depth: int = 0):
    """The ``import`` statements of a program and of the literal programs it may run, ``MAX_NESTING`` deep, which bind
    their names among the program's own. A string literal any call is handed first counts as such a program, since the
    callee may be ``exec`` under another name (``e = exec``)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) or (isinstance(node, ast.ImportFrom) and not node.level):
            yield node
        elif (depth < MAX_NESTING and isinstance(node, ast.Call) and node.args
              and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str) and len(node.args[0].value) <= MAX_SOURCE):
            try:
                program = ast.parse(node.args[0].value)
            except (SyntaxError, ValueError, RecursionError):
                continue
            yield from _imports(program, depth + 1)


def _bound_names(tree, bound: tuple) -> tuple:
    """Five kinds of names: those the program binds to a module above (``import shutil as sh``); those it binds only to
    a value whose methods touch no file, one that is never a module or a path (``lst = ["a"]``) or the ``copy`` module
    or one of its functions (``import copy``); those it binds any other way, which may be anything, as may a name it
    does not bind; as a dict, the functions it imports by name from a module above (``from os import *``, those of
    ``_FIRST``, ``_RENAME``, ``_COPY`` and ``_LAUNCHERS``), a launcher (``from subprocess import run``), ``exec`` or
    ``eval`` from ``builtins``, or ``open`` from one of ``_OPENERS``, with the module each comes from (``from shutil
    import rmtree as r`` makes ``r`` ``("shutil", "rmtree")``; one from ``_OS_NATIVE`` comes from ``os``); and, as a
    dict, the names ``import ... as`` binds to a module of ``_RUNNERS`` or ``_OS_NATIVE``, with the module
    (``import subprocess as sp``). Those the literal programs it may run import are included (``_imports``). A name is
    judged by every binding the program has, not by the order they run in, and a program that can bind a name unseen
    (``_UNSEEN_BINDING``) has none of the second kind. ``bound`` holds the first, third, fourth and fifth kinds of the
    program that ``exec``s this one."""
    modules, plain, other, counted = {*_MODULES, *bound[0]}, set(), set(bound[1]), set()
    functions, aliases, unseen = dict(bound[2]), dict(bound[3]), False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and isinstance(node.value, _NEVER_A_PATH):
            for target in node.targets if isinstance(node, ast.Assign) else (node.target,):
                if isinstance(target, ast.Name):
                    plain.add(target.id)
                    counted.add(id(target))
        elif isinstance(node, ast.Import) or (isinstance(node, ast.ImportFrom) and node.module == "copy"
                                              and not node.level):
            # Copying an object touches no file: `import copy`, `from copy import deepcopy`.
            for alias in node.names:
                if alias.name != "*" and (isinstance(node, ast.ImportFrom) or alias.name == "copy"):
                    plain.add(alias.asname or alias.name)
                    counted.add(id(alias))
    for node in _imports(tree):
        if isinstance(node, ast.Import):
            aliases.update((alias.asname, alias.name) for alias in node.names
                           if alias.asname and alias.name in _RUNNERS | _OS_NATIVE)
            continue
        module = "os" if node.module in _OS_NATIVE else node.module
        for alias in node.names:
            if alias.name == "*" and (module in _MODULES or module in _LAUNCHERS):
                names = (_FIRST | _RENAME | _COPY if module in _MODULES else set()) | _LAUNCHERS.get(module, set())
                functions.update((name, (module, name)) for name in names)
            elif module in _MODULES or (module in _OPENERS and alias.name == "open") or _runs(module, alias.name):
                functions[alias.asname or alias.name] = (module, alias.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.alias):
            name = node.asname or node.name.partition(".")[0]
            unseen = unseen or node.name == "*" or any(_binds_unseen(word) for word in node.name.split("."))
            if id(node) not in counted:
                other.add(name)
            if node.name in _MODULES or (not node.asname and name in _MODULES):
                modules.add(name)
        elif isinstance(node, (ast.Name, ast.Attribute)):
            # An attribute set on anything (`__main__.lst = os`) may be one of the program's own names.
            word = node.id if isinstance(node, ast.Name) else node.attr
            unseen = unseen or _binds_unseen(word)
            if not isinstance(node.ctx, ast.Load) and id(node) not in counted:
                other.add(word)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            other.update(node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            unseen = unseen or any(_binds_unseen(word) for word in node.value.split("."))
        else:
            # A function, class, parameter, `except ... as` or `match` capture binds the name its node carries.
            carried = (getattr(node, field, None) for field in ("name", "arg", "rest"))
            other.update(value for value in carried if isinstance(value, str))
    plain = frozenset() if unseen else frozenset(plain - other - modules)
    return frozenset(modules), plain, frozenset(other), functions, aliases


def _module_of(receiver, aliases: dict) -> str:
    """The module a receiver names: a name, through the ``import ... as`` that binds it (``sp`` after ``import
    subprocess as sp`` is ``subprocess``), with ``posix`` and ``nt`` read as ``os`` and ``__builtins__`` as
    ``builtins``; "" for any other receiver."""
    if not isinstance(receiver, ast.Name):
        return ""
    module = aliases.get(receiver.id, receiver.id)
    return "os" if module in _OS_NATIVE else "builtins" if module == "__builtins__" else module


def _runs(module: str, name) -> bool:
    """True when ``module.name`` runs a command (``_LAUNCHERS``) or a Python program (``builtins.exec``)."""
    return name in _LAUNCHERS.get(module, ()) or (module == "builtins" and name in _PYTHON_EVAL)


def _namespace(node):
    """Whose names a namespace holds: ``x`` for ``vars(x)`` and ``x.__dict__``, ``_PROGRAM`` for ``globals()``,
    ``locals()`` and ``vars()``; None for any other expression."""
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        if node.func.id == "vars" and len(node.args) == 1 and not isinstance(node.args[0], ast.Starred):
            return node.args[0]
        if node.func.id in ("globals", "locals", "vars") and not node.args:
            return _PROGRAM
    return None


def _lookup(node) -> "tuple | None":
    """``(namespace, key)`` of a lookup in a namespace (``_namespace``), by subscript or by ``.get(key)``; None for any
    other expression."""
    if isinstance(node, ast.Subscript):
        space, key = node.value, node.slice
    elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
          and node.args and not isinstance(node.args[0], ast.Starred)):
        space, key = node.func.value, node.args[0]
    else:
        return None
    return (space, key) if _namespace(space) is not None else None


def _function(node, functions: dict) -> "tuple | None":
    """``(receiver, name)`` of an expression that names a function: ``receiver.name``; ``getattr(receiver, "name")``;
    a lookup in a namespace, ``vars(receiver)["name"]`` or ``receiver.__dict__.get("name")``, or the program's own
    (``globals()["name"]``), which is that name; a name ``functions`` holds, one the program imports by name
    (``_bound_names``), whose receiver is its module, so ``r`` after ``from shutil import rmtree as r`` is
    ``shutil.rmtree``; or any other name, with no receiver. A ``getattr`` or a lookup whose name is built at run time
    has the name None. None for any other expression."""
    if isinstance(node, ast.Attribute):
        return node.value, node.attr
    if isinstance(node, ast.Name):
        module, name = functions.get(node.id, ("", node.id))
        return (ast.Name(module, ast.Load()) if module else None), name
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
        args = node.args
        receiver = args[0] if args and not isinstance(args[0], ast.Starred) else None
        if len(args) in (2, 3) and not node.keywords and not any(isinstance(arg, ast.Starred) for arg in args):
            name = args[1]
            return receiver, name.value if isinstance(name, ast.Constant) and isinstance(name.value, str) else None
        return receiver, None
    lookup = _lookup(node)
    if lookup is None:
        return None
    space, key = _namespace(lookup[0]), lookup[1]
    name = key.value if isinstance(key, ast.Constant) and isinstance(key.value, str) else None
    if space is _PROGRAM:
        return _function(ast.Name(name, ast.Load()), functions) if name is not None else (None, None)
    return space, name


def _file_function(receiver, name, mutates_func) -> bool:
    """True when ``receiver.name`` is a function a call of which is read as a file operation, by the lists above or by
    ``mutates_func``; a name with no receiver is one only as ``open``, and a name built at run time may be any."""
    if name is None:
        return True
    if receiver is None:
        return name == "open"
    module = receiver.id if isinstance(receiver, ast.Name) else ""
    return name in _FILE_FUNCTIONS or mutates_func(module + "." + name + "(")


def _one_target(node) -> bool:
    """True when the arguments fit a ``Path`` method above: one place the path goes, by position or as ``target``."""
    return (len(node.args), tuple(kw.arg for kw in node.keywords)) in {(1, ()), (0, ("target",))}


def _under(directory, source):
    """Where ``Path(source).copy_into(directory)`` writes: the source's name under the directory, or, for a source
    built at run time, the directory itself, a copy into which reaches its whole tree. None for a directory built at
    run time."""
    if directory is None:
        return None
    name = source.replace("\\", "/").rstrip("/").rpartition("/")[2] if source is not None else ""
    if name in ("", "."):
        return directory
    head = directory.rstrip("/\\")
    return f"{head}/{name}" if head else directory + name


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
    # `os.execvp("rm", ["rm", "-rf", "x"])` names the program and then its argv, whose first word is only the name the
    # program is given: what runs is the program with the rest of the argv (`os.execv("/bin/rm", ["ls", "x"])` removes).
    if len(sources) >= 2 and isinstance(sources[0], ast.Constant) and isinstance(sources[1], (ast.List, ast.Tuple)):
        rest = sources[1].elts[1:]
        sources = [sources[0], *([ast.List(rest, ast.Load())] if rest else []), *sources[2:]]
    words: list = []
    for source in sources:
        strings = _literal_strings(source)
        if strings is None:
            return None
        words.extend(strings)
    return " ".join(words)


def _is_none(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _word(node):
    """The name a name or an attribute carries; None for any other node."""
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None


def _reaches(word: str, mutates_func) -> bool:
    """True when an attribute of that name may be a function a call of which is read above, a file function, a
    launcher or ``exec``, or one through which a program binds a name unseen (``getattr``, ``__dict__``)."""
    return _binds_unseen(word) or any(
        _file_function(ast.Name(module, ast.Load()), word, mutates_func) or _runs(module, word)
        for module in (*_MODULES, *_RUNNERS))


def _names_nothing_read(node, mutates_func) -> bool:
    """True when a call of ``attrgetter`` or ``methodcaller`` is given only literal names (``methodcaller`` one, then
    the method's arguments) none of whose dotted parts ``_reaches`` a function."""
    names = node.args[:1] if _word(node.func) == "methodcaller" else node.args
    return bool(names) and all(
        isinstance(name, ast.Constant) and isinstance(name.value, str)
        and not any(_reaches(part, mutates_func) for part in name.value.split(".")) for name in names)


def _stays_in(part) -> bool:
    """True when a temporary file's ``prefix`` or ``suffix`` is absent or a literal with no path separator, so the file
    stays in its directory."""
    if part is None or _is_none(part):
        return True
    if isinstance(part, ast.Constant) and isinstance(part.value, (str, bytes)):
        text = part.value.decode("latin-1") if isinstance(part.value, bytes) else part.value
        return "/" not in text and "\\" not in text
    return False


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


def python_targets(source: str, mutates_func, runs_command=None, depth: int = 0, bound: tuple = ((), (), (), ())):
    """Return (path-or-None, via) for recognizable writes; None means unplaced.

    ``mutates_func`` says whether a call (``"shutil.rmtree("``) is a file API the lists above do not name;
    ``runs_command`` whether a call by that name (``"os.system("``) hands a command to a shell. A command the program
    hands over as literal text is returned as ``(text, "launch")`` for the shell analyser to judge, after a ``cd`` into
    the literal directory it runs in (``cwd=``); one built at run time is an unplaced write, and so is one run in a
    directory built at run time or by another program (``executable=``). ``exec`` and ``eval`` of a literal are read
    as Python, ``MAX_NESTING`` deep, however they are reached (``builtins.exec``, ``e = exec``).

    A call is read as a call of the function its expression names (``_function``): an attribute, a ``getattr`` or a
    namespace lookup (``vars(os)["remove"]``) with a literal name, a file function, a launcher or ``exec`` imported by
    name (``from shutil import rmtree as r``; ``from posix import remove`` is ``os.remove``; ``from subprocess import
    run``), or a launcher through ``import subprocess as sp``. A call of a function above is read as that file
    operation unless its receiver is never a module or a path: a literal, a container, a comprehension, or a name the
    program binds only to one of those or to the ``copy`` module (``_bound_names``), so ``"s".replace("a", "b")``,
    ``{}.copy()``, ``lst.remove("a")`` after ``lst = ["a"]`` and ``copy.copy(x)`` after ``import copy`` are not, while
    the same call on any other receiver still is (``o.remove("x")`` after ``o = os``, ``__import__("os").remove("x")``).
    Nor is a ``rename``, ``replace``, ``copy`` or ``move`` with no target (``datetime.now().replace(tzinfo=None)``).
    Its arguments are the module function's, except that a ``rename``, ``replace``, ``copy`` or ``move`` with one
    target, on a receiver that is not ``os``, ``shutil`` or a name ``import ... as`` binds to one, is the ``Path``
    method, which sends its receiver there, and ``copy_into`` and ``move_into`` send it, or the source
    ``Path.copy_into(source, directory)`` names first, under the directory they name; a temporary file
    (``tempfile.mkstemp(dir="d")``) goes anywhere in the directory it names. A function the lists or ``mutates_func``
    name used other than by calling it (``f = os.remove``, ``map(os.remove, paths)``), and so a launcher or ``exec``
    (``r = os.system``) other than a name bound to ``exec`` (``e = exec``, read as it); a ``getattr`` or a lookup whose
    name is built at run time, ``getattr`` reached other than by calling it by that name (``_GETTERS``), and the
    namespace of a module above used other than by a lookup (``d = vars(os)``); an ``attrgetter`` or ``methodcaller``
    given a name built at run time or one that may reach a function above; a file function given a directory
    descriptor (``dir_fd=``); and a temporary file in a directory or under a name built at run time are unplaced
    writes, as is every write of a program that changes its working directory (``_CHDIR``). Other values and arbitrary
    calls are not interpreted. The scanner retains its existing conservative mutation fallback for syntax/size gaps and
    other APIs, and a call none of the lists place falls to it.
    """
    if len(source) > MAX_SOURCE or depth > MAX_NESTING:
        return None
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return None
    modules, plain, other, functions, aliases = _bound_names(tree, bound)
    # Of the functions imported by name, a file function, a launcher or `exec` is read as its module's; any other keeps
    # the name it has.
    functions = {local: (module, name) for local, (module, name) in functions.items()
                 if _file_function(ast.Name(module, ast.Load()), name, mutates_func) or _runs(module, name)}
    called = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
    looked_up = {id(lookup[0]) for lookup in map(_lookup, ast.walk(tree)) if lookup is not None}

    def evaluator(reference) -> bool:
        # `exec` or `eval`, by its own name or as `builtins`'s.
        return reference[1] in _PYTHON_EVAL and (reference[0] is None
                                                 or _module_of(reference[0], aliases) == "builtins")

    # A name the program binds to `exec` or `eval` (`e = exec`, `e = builtins.exec`) is read as it. One bound so in a
    # literal program it runs is not: the program that runs it would not see the name.
    aliased: set = set()
    assignments = [node for node in ast.walk(tree) if not depth and isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)]
    while True:
        found = [(node, reference) for node in assignments
                 if id(node.value) not in aliased and node.targets[0].id not in functions
                 and (reference := _function(node.value, functions)) is not None and evaluator(reference)]
        if not found:
            break
        for node, reference in found:
            functions[node.targets[0].id] = ("builtins", reference[1])
            aliased.add(id(node.value))

    def harmless(holder) -> bool:
        # What a function is reached through, its receiver or its own bare name, is never a module or a path.
        return isinstance(holder, _NEVER_A_PATH) or (isinstance(holder, ast.Name) and holder.id in plain)

    targets, moved = [], False
    for node in ast.walk(tree):
        if ((isinstance(node, ast.Name) and node.id in _GETTERS and id(node) not in called)
                or (isinstance(node, ast.Attribute) and node.attr in _GETTERS)
                or (isinstance(node, ast.alias) and node.name in _GETTERS)):
            targets.append((None, "python"))  # `g = getattr`, `builtins.getattr(os, name)`, `os.__getattribute__(name)`
        if ((_word(node) in _BY_NAME and id(node) not in called)
                or (isinstance(node, ast.alias) and node.name in _BY_NAME and node.asname)
                or (isinstance(node, ast.Call) and _word(node.func) in _BY_NAME
                    and not _names_nothing_read(node, mutates_func))):
            targets.append((None, "python"))  # `operator.attrgetter("remove")(os)`, `f = operator.attrgetter`
        space = _namespace(node)
        if (isinstance(space, ast.Name) and id(node) not in looked_up
                and (space.id in modules or _module_of(space, aliases) in _RUNNERS)):
            targets.append((None, "python"))  # `d = vars(os)`, `os.__dict__.values()`
        reference = _function(node, functions) if id(node) not in called else None
        if isinstance(getattr(node, "ctx", None), (ast.Store, ast.Del)):
            reference = None
        if reference is not None and id(node) not in aliased:
            # A function used other than by calling it: `f = os.remove`, `map(os.remove, paths)`, `r = os.system`.
            holder = node if isinstance(node, ast.Name) else reference[0]
            runs = _runs(_module_of(reference[0], aliases), reference[1]) or evaluator(reference)
            if (_file_function(*reference, mutates_func) or runs) and not harmless(holder):
                targets.append((None, "rm" if reference[1] in _REMOVE else "python"))
        callee = _function(node.func, functions) if isinstance(node, ast.Call) else None
        # `os.chdir("src")`, `f = os.chdir`, `getattr(os, "chdir")("src")`
        moved = moved or any(found is not None and found[1] in _CHDIR for found in (reference, callee))
        if callee is None:
            continue
        receiver, name = callee
        holder = node.func if isinstance(node.func, ast.Name) else receiver
        if name is None:
            if not harmless(holder):
                targets.append((None, "python"))  # `getattr(os, name)(...)`
            continue
        attr = receiver is not None
        module = receiver.id if isinstance(receiver, ast.Name) else ""
        args = node.args
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        def argument(index, key=None, args=args, keywords=keywords):
            return args[index] if len(args) > index else keywords.get(key)
        if (any(word.endswith("dir_fd") and not _is_none(value) for word, value in keywords.items())
                and _file_function(receiver, name, mutates_func) and not harmless(holder)):
            # The path is under the directory a descriptor holds, not the working directory: `os.remove(p, dir_fd=d)`.
            targets.append((None, "rm" if name in _REMOVE else "python"))
        elif name == "open":
            targets.extend(_open_targets(node, attr, receiver, module, argument))
        elif name in _METHOD and attr and module not in modules:
            targets.append((literal_path(receiver), "rm" if name in _REMOVE else "python"))
        elif name in _FIRST | _RENAME | _COPY | _INTO and harmless(holder):
            pass  # a method of a string, a list or a dict, or a function of `copy`, which touches no file
        elif name in _PATH_METHODS and not args and not any(kw.arg in _TARGET_KEYWORDS for kw in node.keywords):
            pass  # no target, so no file form: `datetime.now().replace(tzinfo=None)`
        elif name in _FIRST:
            targets.append((literal_path(argument(0, "path")), "rm" if name in _REMOVE else "python"))
        elif name in _PATH_METHODS and attr and module not in modules and _one_target(node):
            if name != "copy":
                targets.append((literal_path(receiver), "mv"))
            targets.append((literal_path(argument(0, "target")), "mv" if name in _RENAME else "cp -r"))
        elif name in _INTO and attr:
            # Called on the class, the method names its source first: `Path.copy_into(Path("a"), "d")`.
            places = [*args, *(kw.value for kw in node.keywords if kw.arg == "target_dir")]
            source = places[0] if len(places) == 2 else receiver
            directory = places[-1] if len(places) in (1, 2) else None
            if name == "move_into":
                targets.append((literal_path(source), "mv"))
            targets.append((_under(literal_path(directory), literal_path(source)), "cp -r"))
        elif name in _RENAME:
            targets.extend((literal_path(path), "mv") for path in (argument(0, "src"), argument(1, "dst")))
        elif name in _COPY:
            if name == "move":
                targets.append((literal_path(argument(0, "src")), "mv"))
            targets.append((literal_path(argument(1, "dst")), "cp -r"))
        elif name in _EXTRACT and attr:
            destination = argument(_EXTRACT[name], "path")
            targets.append((literal_path(destination) if destination is not None else None, "archive-extract"))
        elif name in _TEMPORARY:
            suffix, prefix, directory = (argument(_TEMPORARY[name] + index, key)
                                         for index, key in enumerate(("suffix", "prefix", "dir")))
            if (any(isinstance(arg, ast.Starred) for arg in args) or any(kw.arg is None for kw in node.keywords)
                    or not (_stays_in(suffix) and _stays_in(prefix))):
                targets.append((None, "python"))  # `mkstemp(*a)`, `mkstemp(**kw)`, `mkstemp(prefix=p)`
            elif directory is not None and not _is_none(directory):
                targets.append((literal_path(directory), "cp -r"))  # somewhere in that directory
        elif evaluator(callee):
            program = argument(0, "source")
            nested = None
            if isinstance(program, ast.Constant) and isinstance(program.value, str):
                moved = moved or "chdir" in program.value  # the program it runs may change the directory
                nested = python_targets(program.value, mutates_func, runs_command, depth + 1,
                                        (modules, other, functions, aliases))
            if nested is None:
                targets.append((None, "python"))
            else:
                targets.extend(nested)
        else:
            try:
                function = ast.unparse(ast.Attribute(receiver, name, ast.Load()) if attr else ast.Name(name, ast.Load())) + "("
            except RecursionError:
                targets.append((None, "python"))
                continue
            runner = _module_of(receiver, aliases)
            if runs_command is not None and runs_command((runner + "." if runner else "") + name + "("):
                command = literal_command(node)
                directory = keywords.get("cwd")
                if command is None or "executable" in keywords or any(kw.arg is None for kw in node.keywords):
                    targets.append((None, "python"))
                elif directory is None or _is_none(directory):
                    targets.append((command, "launch"))
                elif literal_path(directory) is not None:
                    targets.append((f"cd {shlex.quote(literal_path(directory))} && {command}", "launch"))
                else:
                    targets.append((None, "python"))  # `subprocess.run(["rm", "x"], cwd=d)`
            elif mutates_func(function):
                targets.append((None, "python"))
    if moved:
        return [(None, "python" if via == "launch" else via) for _, via in targets]
    return targets
