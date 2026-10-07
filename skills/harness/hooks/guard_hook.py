#!/usr/bin/env python3
"""
Action Realization hook (LIFE-HARNESS Layer 3) for Supreme Team.

Runs as a host ``PreToolUse``/pre-tool hook. It validates a generated action
*before* the host executes it and BLOCKS the ones that would deterministically
fail or violate an active guard/freeze boundary. This is the deterministic
enforcement of the recorded `.harness-state/guard-state.json` guard/freeze boundary.

Doctrine (../../harness-doctrine.md):
  - Principles: local & minimal, evidence-triggered, fail open.
  - Principles: inert on a competent action. Every rule below fires only on a
    mechanically certain signal (a destructive command, or a path inside a
    recorded boundary that a command or tool is about to write) — never on
    ambiguous intent — so a strong backbone is unaffected.

How a decision is made. A shell command is analysed (``_cmdscan``): the commands
that would run after ``sudo``/``sh -c``/``$(...)``/``xargs`` are unwrapped, and the
paths they write, by redirect or by a file-mutating command. Each path is then
located (``_paths``): every spelling of it, relative to the project root, and the
boundary it is compared with is normalised the same way. That is text analysis,
not a sandbox: a program that builds its path at run time, a script file, a tool
the analyser has no entry for, or a link made inside the same command cannot be
seen, and an interpreter's inline code is searched for protected paths rather than
understood. A command that cannot be tokenised falls back to textual rules that are
never weaker than the ones this module started from.

Each rule is a function of a ``Call`` that returns a reason to deny or None, so each
is tested alone and a fault in one is counted and does not skip the others.

Block contract: prints the PreToolUse deny envelope to stdout and
exits 0. On any internal error it exits 0 silently (fail open), letting the
action proceed, after counting the fault by type in the hook's observation record.
"""
from __future__ import annotations

import functools
import glob as _glob
import itertools
import json
import os
import posixpath
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

import _cmdscan
import _paths
import _state
import run_heartbeat

HOOK_DIR = Path(__file__).resolve().parent

# --- Rule A: destructive commands -----------------------------------------------------------

# Literal, unambiguous destructive shell patterns. Conservative on purpose: only
# catch commands that are almost never a legitimate agent action. The textual rules
# are the ones Rule A started with, written so their cost is linear in the command
# (a lookahead that rescans the rest of the line from every `git push` was quadratic:
# a 72 KB command took 12 s). The structural rules below catch the spellings these miss.
_TEXT_SIMPLE = (
    (re.compile(r"\brm\s+(?:-\S+\s+)*--no-preserve-root", re.I), "recursive delete with --no-preserve-root"),
    (re.compile(r"\bformat(?:\.com)?\s+[A-Za-z]:(?:\s|$)", re.I), "format of a drive"),
    (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), "shell fork bomb"),
    (re.compile(r"\bmkfs(\.\w+)?\s+/dev/", re.I), "filesystem format of a device"),
    (re.compile(r">\s*/dev/(sd|nvme|hd)\w*", re.I), "redirect over a raw block device"),
    (re.compile(r"\bchmod\s+-R\s+0?00\s+/(\s|$)", re.I), "recursive chmod 000 on root"),
)
_STATEMENT = re.compile(r"[\n;|&]")
# PowerShell / cmd equivalents of a recursive drive, root, or home wipe. The target must be a *bare* root
# (C:\, /, ~, $HOME); a path underneath it does not match, so `Remove-Item -Recurse -Force .\build` stays allowed.
_TEXT_PS = re.compile(r"\b(?:Remove-Item|ri|rd|rmdir|del|erase)\b", re.I)
_TEXT_PS_RECURSE = re.compile(r"\s-(?:Recurse|r)\b", re.I)
_TEXT_PS_TARGET = re.compile(r"\s['\"]?(?:[A-Za-z]:[\\/]?|/|~|\$HOME|\$env:USERPROFILE)['\"]?(?:\s|$|;)", re.I)
_TEXT_RD = re.compile(r"\brd\s+/s\b", re.I)
_TEXT_RD_DRIVE = re.compile(r"\s[A-Za-z]:\\?(?:\s|$)", re.I)
_TEXT_DD = re.compile(r"\bdd\b", re.I)
_TEXT_DD_TARGET = re.compile(r"\bof=/dev/(sd|nvme|hd)", re.I)
# Force-push to a protected branch: a force flag and a protected-branch ref token anywhere after `git push`
# on the line, in either order. The branch token must be a standalone ref (bounded by space/`:`/`/`) so
# `main-thing` does not trip it.
_TEXT_PUSH = re.compile(r"\bgit\s+push\b", re.I)
_TEXT_FORCE = re.compile(r"--force\b|--force-with-lease\b|(?:^|\s)-f(?=\s|$)", re.I)
_TEXT_PROTECTED = re.compile(r"(?:^|[\s:/])(?:main|master)(?:[\s:]|$)", re.I)

# `rm` with a recursive flag in any spelling (-rf, -fr, -Rf, -r -f, --recursive)
# against a bare root, home, or glob target. Flags are parsed rather than
# pattern-matched so flag order and combination cannot slip past the guard.
_RM_CALL = re.compile(r"(?:^|[\s;&|(`])rm\s+((?:-{1,2}[\w-]+\s+)+)((?:[^\s;&|]+\s*)+)")
_ROOT_TARGET = re.compile(r"^['\"]?(?:/|/\*|~|~/\*|\$HOME|\$HOME/\*|\$env:USERPROFILE|\*)['\"]?$")


def _rm_wipes_root(cmd: str) -> bool:
    for match in _RM_CALL.finditer(cmd):
        flags = match.group(1).split()
        recursive = any(
            flag == "--recursive" or (flag.startswith("-") and not flag.startswith("--") and any(c in "rR" for c in flag[1:]))
            for flag in flags
        )
        if not recursive:
            continue
        for target in match.group(2).split():
            if not target.startswith("-") and _ROOT_TARGET.match(target):
                return True
    return False


def _textual_dangerous(text: str) -> "str | None":
    """The first textual destructive rule ``text`` trips, or None."""
    for pattern, label in _TEXT_SIMPLE:
        if pattern.search(text):
            return label
    for line in text.split("\n"):
        dd = _TEXT_DD.search(line)
        if dd and _TEXT_DD_TARGET.search(line, dd.end()):
            return "raw disk overwrite via dd"
        push = _TEXT_PUSH.search(line)
        if push and _TEXT_FORCE.search(line, push.end()) and _TEXT_PROTECTED.search(line, push.end()):
            return "force-push to a protected branch (main/master)"
    for statement in _STATEMENT.split(text):
        anchor = _TEXT_PS.search(statement)
        if anchor and _TEXT_PS_RECURSE.search(statement, anchor.end()) and _TEXT_PS_TARGET.search(statement, anchor.end()):
            return "recursive delete of a drive, root, or home target"
        rd = _TEXT_RD.search(statement)
        if rd and _TEXT_RD_DRIVE.search(statement, rd.end()):
            return "recursive removal of a drive root"
    if _rm_wipes_root(text):
        return "recursive delete of a root/home/glob target"
    return None


_TOP_LEVEL = frozenset({"home", "usr", "etc", "bin", "sbin", "lib", "lib64", "var", "boot", "root", "opt", "srv", "sys", "proc",
                        "dev", "mnt", "media", "users", "system", "library", "applications", "volumes"})
_DEVICE = re.compile(r"^/dev/(?:sd|nvme|hd|vd|xvd|mmcblk|disk|rdisk|md|loop)\w*", re.I)
_PROTECTED_BRANCH = frozenset({"main", "master"})
_DELETE_COMMANDS = frozenset({"remove-item", "ri", "rd", "rmdir", "del", "erase"})


def _home() -> str:
    return posixpath.normpath((os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")).replace("\\", "/"))


def _wipe_target(text: str) -> bool:
    """True for a bare filesystem root, drive root, home directory, top-level system directory, or a bare ``*``."""
    raw = text.strip().strip("'\"")
    if not raw:
        return False
    if raw in ("*", "./*"):
        return True
    if re.fullmatch(r"%(?:USERPROFILE|HOMEPATH|HOMEDRIVE)%[\\/]*\*?", raw, re.I):
        return True
    path = re.sub(r"/{2,}", "/", raw.replace("\\", "/"))
    if re.fullmatch(r"[A-Za-z]:/*\*?", path):
        return True
    bare = path[:-2] if path.endswith("/*") else path
    if bare in ("", "/"):
        return path.startswith("/")
    normal = posixpath.normpath(bare)
    if normal in ("/", "~", "$HOME", "${HOME}"):
        return True
    if (normal.lower() == _home().lower()) if _paths.case_insensitive_fs() else (normal == _home()):
        return True
    return bool(re.fullmatch(r"/[^/]+", normal)) and normal[1:].lower() in _TOP_LEVEL


def _flags(argv) -> list:
    out = []
    for arg in argv:
        if arg == "--":
            break
        if arg.startswith("-") and len(arg) > 1:
            out.append(arg)
    return out


def _operands(argv) -> list:
    out = []
    ended = False
    for arg in argv:
        if ended:
            out.append(arg)
        elif arg == "--":
            ended = True
        elif not (arg.startswith("-") and len(arg) > 1):
            out.append(arg)
    return out


def _recursive(flags) -> bool:
    return any(f == "--recursive" or (not f.startswith("--") and any(c in "rR" for c in f[1:])) for f in flags)


def _ps_recursive(argv) -> bool:
    for arg in argv:
        low = arg.lower()
        if low == "/s":
            return True
        if low.startswith("-") and len(low) > 1 and "recurse".startswith(low[1:].split(":")[0]):
            return True
    return False


# A push destination that names no branch: the current one, whichever it is.
_CURRENT_BRANCH = frozenset({"HEAD", "@"})


def _git_push_label(argv) -> "str | None":
    """A push that rewrites or deletes a protected branch, or may: one aimed at ``main``/``master`` with a force flag, a
    ``+`` refspec or a delete; ``--mirror``, which makes every remote ref match the local ones and deletes the rest; and a
    forced push that names no branch (``git push -f``, ``git push --force origin``, ``-f origin HEAD``, ``--all -f``),
    whose destination is the current or upstream branch, which may be ``main``. ``git push --force origin feature`` names
    its branch and passes."""
    sub, operands, _, flags = _cmdscan.git_parts(argv)
    if sub != "push":
        return None
    force = any(f == "--force" or f.startswith("--force-with-lease") for f in flags) or any(
        not f.startswith("--") and "f" in f[1:] for f in flags)
    deleting = "--delete" in flags or any(not f.startswith("--") and "d" in f[1:] for f in flags)
    if "--mirror" in flags:
        return "mirror push (rewrites or deletes every remote ref, protected branches included)"
    refspecs = operands[1:]
    unnamed = not refspecs or "--all" in flags or "--branches" in flags or any(
        operand.text.lstrip("+").split(":", 1)[0] in _CURRENT_BRANCH and ":" not in operand.text for operand in refspecs)
    if force and unnamed:
        return "force-push that names no branch (the current or upstream branch may be main/master)"
    for operand in operands:
        text = operand.text
        plus = text.startswith("+")
        destination = (text.lstrip("+").rsplit(":", 1)[-1]).removeprefix("refs/heads/")
        if destination in _PROTECTED_BRANCH and (force or plus or deleting or text.startswith(":")):
            return "force-push to a protected branch (main/master)"
    return None


def _structural_label(command) -> "str | None":
    """The destructive rule one parsed command trips, matched on its argv rather than on text."""
    verb, argv = command.verb, command.argv
    if verb == "rm":
        if "--no-preserve-root" in argv:
            return "recursive delete with --no-preserve-root"
        if _recursive(_flags(argv)) and any(_wipe_target(t) for t in _operands(argv)):
            return "recursive delete of a root/home/glob target"
    elif verb in _DELETE_COMMANDS:
        if _ps_recursive(argv) and any(_wipe_target(t) for t in argv if not t.startswith("-") and not re.fullmatch(r"/[A-Za-z?]", t)):
            return "recursive delete of a drive, root, or home target"
    elif verb == "find":
        if "-delete" in argv:
            starts = []
            for arg in argv:
                if arg in ("-H", "-L", "-P") or arg.startswith("-O"):
                    continue
                if arg.startswith(("-", "(", "!")):
                    break
                starts.append(arg)
            if any(_wipe_target(t) for t in (starts or ["."])):
                return "recursive delete of a root/home/glob target"
    elif verb == "git":
        return _git_push_label(argv)
    elif verb == "chmod":
        flags = _flags(argv)
        operands = _operands(argv)
        if _recursive(flags) and operands and re.fullmatch(r"0{2,4}", operands[0]) and any(_wipe_target(t) for t in operands[1:]):
            return "recursive chmod 000 on root"
    elif verb.startswith("mkfs"):
        if any(arg.startswith("/dev/") for arg in argv):
            return "filesystem format of a device"
    elif verb == "dd":
        if any(arg.startswith("of=") and _DEVICE.match(arg[3:]) for arg in argv):
            return "raw disk overwrite via dd"
    elif verb == "format":
        if any(re.fullmatch(r"[A-Za-z]:", arg) for arg in argv):
            return "format of a drive"
    return None


# A word that a destructive rule needs, for the command lines an inline program runs: only those are analysed.
_DESTRUCTIVE_WORD = re.compile(r"(?<![\w.-])(?:rm|find|git|chmod|mkfs[\w.]*|dd|format|remove-item|ri|rd|rmdir|del|erase)"
                               r"(?![\w-])|/dev/", re.I)
# How deep a program's command line is read for another program's (``python -c 'os.system("perl -e ...")'``).
_PROGRAM_DEPTH = 3


def _analysis_label(analysis, depth: int = 0) -> "str | None":
    """The destructive rule a command line's analysis trips: its commands, those a launcher, a script block or a shell
    fed by a literal ``echo`` runs (``watch 'rm -rf /'``, ``echo 'rm -rf /' | sh``), and the command lines an inline
    program hands a shell (``perl -e 'system("rm -rf /")'``, ``python3 -c 'os.system("rm -rf /")'``)."""
    for current in _analyses(analysis):
        for command in current.commands:
            label = _structural_label(command)
            if label:
                return label
        for write in current.writes:
            if _DEVICE.match(write.path):
                return "redirect over a raw block device"
        if depth >= _PROGRAM_DEPTH:
            continue
        for code in current.code:
            commands = _cmdscan.program_commands(code)
            if not commands:
                continue
            label = _textual_dangerous("\n".join(commands))
            if label:
                return label
            for line in commands:
                if _DESTRUCTIVE_WORD.search(line):
                    label = _analysis_label(_cmdscan.analyse(line), depth + 1)
                    if label:
                        return label
    return None


def _dangerous_label(call: "Call") -> "str | None":
    return _textual_dangerous(call.command) or _analysis_label(call.analysis)


def _dangerous_lifted(guard: dict) -> bool:
    """True while destructive-pattern blocking is deliberately lifted.

    Only the owned grant guard_state.py writes can lift the block. A legacy bare
    ``true`` is unbounded and ownerless, so it no longer grants an exception.
    An expired, malformed or over-long grant leaves the block in force.
    """
    grant = guard.get("allow_dangerous")
    if not isinstance(grant, dict):
        return False
    if any(not isinstance(grant.get(key), str) or not grant[key].strip()
           for key in ("owner", "reason", "scope", "created_at")):
        return False
    expires = grant.get("expires_at")
    if not expires:
        # guard_state.py always records an expiry, so a grant without one is
        # malformed. Fail closed: an unbounded lift is the state this rule exists
        # to prevent.
        return False
    try:
        created = datetime.strptime(grant["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        deadline = datetime.strptime(str(expires), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    now = datetime.now(timezone.utc)
    # The writer refuses a grant longer than the cap, so a longer one was written by hand.
    return created <= now < deadline and (deadline - now).total_seconds() <= _state.MAX_GRANT_MINUTES * 60


_DANGEROUS_REASON = (
    "Blocked by harness Action Realization layer: {label}. "
    "If this is genuinely intended, the owner must lift the guard with "
    "'python skills/harness/hooks/guard_state.py allow-dangerous --owner <owner> "
    "--reason <why> --scope <operation>' (bounded by an expiry), or use a narrower command."
)


def rule_dangerous(call: "Call") -> "str | None":
    """Rule A: dangerous shell patterns, unless an owned, unexpired grant lifts the block."""
    if not call.shell or _dangerous_lifted(call.guard):
        return None
    label = _dangerous_label(call)
    return _DANGEROUS_REASON.format(label=label) if label else None


# --- the call a rule inspects ----------------------------------------------------------------

_SHELL_TOOLS = frozenset({"bash", "powershell", "pwsh", "shell"})
_WRITE_TOOLS = frozenset({"edit", "write", "notebookedit", "multiedit", "apply_patch"})
# Tools whose input names a filesystem path we can match against a boundary.
_PATH_KEYS = ("file_path", "filePath", "path", "notebook_path", "target_file")
_PATCH_FILE = re.compile(r"^\*\*\* (?:Update File|Add File|Delete File|Move to):\s*(.+?)\s*$", re.MULTILINE)
_WORD = re.compile(r"[^\s'\"`;&|<>(){}\[\],=]+")
_SEPARATORS = re.compile(r"[\\/]+")
# A backslash-n, -r or -t that ends a word in the command text (`printf 'rm a/b\n' | sh`): the path before it is the path.
_WORD_END_ESCAPE = re.compile(r"\\[nrt](?=[\s'\"`]|$)")
_GLOB_LIMIT = 100
# Commands that remove, move or rewrite a whole tree: aimed at a directory above a boundary they reach into it.
_REMOVE_VIA = frozenset({"rm", "rmdir", "mv", "shred", "unlink", "remove-item", "move-item", "rename-item", "rename", "find"})
# Commands that put files into a directory whose names the command line does not fix, so aimed at a directory they
# reach everything under it: a sync (`rsync`, and `--delete` removes what the source lacks), an archive extract
# (`tar -x -C`, `unzip -d`, `7z x -o`), a recursive or contents copy (`cp -r`, `cp x/. dir`, labelled `<verb> -r` by
# the analyser), `Copy-Item`, and the in-place editors `find -exec` aims at a directory (`find src -exec sed -i`).
# A plain `cp file dir/` is not here: the analyser names the file it lands as (`dir/file`), and that is judged.
_DEPOSIT_VIA = frozenset({"rsync", "tar", "unzip", "7z", "copy-item", "cp -r", "ln -r", "scp -r", "install -r",
                          "sed", "perl", "awk", "gawk", "truncate", "archive-extract",
                          "git clone", "git init", "git worktree", "git submodule", "git format-patch"})
_TREE_VIA = _REMOVE_VIA | _DEPOSIT_VIA | frozenset({"git checkout", "git restore", "git clean", "git rm", "git mv",
                                                    "git apply", "git stash"})
# Rule C reads the same trees, less the git commands that leave ignored files alone; `git clean` (`-x` reaches them)
# stays.
_RECORD_TREE_VIA = _REMOVE_VIA | _DEPOSIT_VIA | frozenset({"git clean"})
# The archive extracts: member destinations are inspected at the root. While a
# run is active Rule F also treats unknown archives as reaching every boundary.
_EXTRACT_VIA = frozenset({"tar", "unzip", "7z", "archive-extract"})


def _written_paths(tool_input: dict, *, include_patch: bool = False) -> list:
    paths = []
    for key in _PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append(value)
    if include_patch:
        for key in ("patch", "input", "content"):
            patch = tool_input.get(key)
            if isinstance(patch, str):
                paths.extend(match.group(1) for match in _PATCH_FILE.finditer(patch))
    return paths


class Call:
    """One tool call and everything a rule may ask about it, each computed once."""

    def __init__(self, tool_name, tool_input, guard: dict, root, cwd=None) -> None:
        self.tool = str(tool_name or "").strip().lower()
        self.input = tool_input if isinstance(tool_input, dict) else {}
        self.guard = guard
        self.root = Path(root)
        self.shell = self.tool in _SHELL_TOOLS
        self.writer = self.tool in _WRITE_TOOLS
        self.powershell = self.tool in ("powershell", "pwsh")
        host_cwd = _paths.clean(cwd) if isinstance(cwd, str) and cwd.strip() else ""
        root_text = _paths.posix(self.root)
        self.starts = [host_cwd, root_text] if host_cwd and _paths.is_absolute(host_cwd) and host_cwd != root_text else [root_text]
        self._located: dict = {}
        self._shell_targets: dict = {}
        self._resolver = _paths.Resolver()
        # Rule C's reading of a root-aimed ``find``: the record paths listed once per call, and how many it has tested.
        self.record_paths: dict = {}
        self.find_spent = 0

    @functools.cached_property
    def command(self) -> str:
        value = self.input.get("command")
        if isinstance(value, (list, tuple)):
            return " ".join(shlex.quote(str(part)) for part in value)
        return str(value or "")

    @functools.cached_property
    def analysis(self):
        # The project-directory variables the host exports are the values a command's `$CLAUDE_PROJECT_DIR/...` takes.
        env = {name: os.environ.get(name) for name in _state.PROJECT_ENV}
        return _cmdscan.analyse(self.command, powershell=self.powershell, env=env)

    def locate(self, text: str, bases) -> "_paths.Target":
        key = (text, tuple(bases))
        if key not in self._located:
            self._located[key] = _paths.locate(text, self.root, list(bases), self._resolver)
        return self._located[key]

    @functools.cached_property
    def edit_targets(self) -> list:
        paths = _written_paths(self.input, include_patch=self.tool == "apply_patch")
        return [self.locate(path, self.starts) for path in paths]

    def _bases(self, write, strict: bool) -> list:
        starts = self.starts[:1] if strict else self.starts
        words = write.cwds[-1:] if strict else write.cwds
        derived = [word if _paths.is_absolute(word) else posixpath.join(start, word) for word in words for start in starts]
        return derived if strict and words else [*starts, *derived]

    def shell_targets(self, strict: bool = False, analysis=None) -> list:
        """``(write, [Target])`` for every write the analyser found (in ``analysis``, the call's own by default).

        Deny rules consider every directory a ``cd`` may have left the shell in; the allow-list rule
        only the one it last set. A wildcard word is also expanded against the disk."""
        analysis = analysis or self.analysis
        key = (id(analysis), strict)
        if key not in self._shell_targets:
            found = []
            for write in analysis.writes:
                bases = self._bases(write, strict)
                texts = [write.path]
                if write.glob and not write.unresolved:
                    for base in bases:
                        pattern = write.path if _paths.is_absolute(write.path) else posixpath.join(base, write.path)
                        try:
                            texts.extend(itertools.islice(_glob.iglob(pattern), _GLOB_LIMIT))
                        except (OSError, ValueError):
                            continue
                found.append((write, [self.locate(text, bases) for text in dict.fromkeys(texts)]))
            self._shell_targets[key] = found
        return self._shell_targets[key]


# A variable the analysis cannot resolve, leading a path word: `$OUT/`, `${OUT}/`, `$env:OUT\`.
_VARIABLE_LEAD = re.compile(r"^\$(?:env:)?[A-Za-z_]\w*[\\/]+", re.I)


def _path_words(text: str) -> list:
    """The path words of ``text``, and for one led by a variable (`$OUT/src/payments/a`) the path after it too: the
    variable could stand for the project, so the rest is judged as a path in it."""
    words = []
    for word in _WORD.findall(re.sub(r"\$\{(\w+)\}", r"$\1", text)):
        words.append(word)
        rest = _VARIABLE_LEAD.sub("", word)
        if rest and rest != word:
            words.append(rest)
    return words


def _mentioned(texts, call: "Call", boundaries) -> "_paths.Boundary | None":
    """The first boundary a path word in ``texts`` lies on: how interpreter code and unparseable commands are searched."""
    pieces = [(boundary, boundary.fragments()) for boundary in boundaries]
    seen: set = set()
    for text in texts:
        for word in _path_words(text):
            low = _SEPARATORS.sub("/", word.lower())  # a Windows spelling (`src\payments\a`) holds the same fragments
            if low in seen:
                continue
            seen.add(low)
            target = None
            for boundary, fragments in pieces:
                if fragments and not any(fragment in low for fragment in fragments):
                    continue
                target = target or call.locate(word, call.starts)
                if boundary.matches(target):
                    return boundary
    return None


def _at_or_above_root(call: "Call", target: "_paths.Target") -> bool:
    """True when ``target`` is the project root or a directory above it."""
    roots = call.locate(_paths.posix(call.root), []).abs
    return any(root == form or root.startswith(form.rstrip("/") + "/") for form in target.abs for root in roots)


def _shell_hit(call: "Call", boundaries, tree_via=_TREE_VIA, analysis=None, root_extracts: bool = True) -> "_paths.Boundary | None":
    """The first boundary a shell write lies on, or one a tree-wide command aimed above it reaches into.

    ``analysis`` is the command line's own by default; pass one of the nested analyses (see ``_analyses``) to judge
    the writes of a command a launcher or script block runs. With ``root_extracts`` false a root extract is not
    treated as a tree-wide write: callers inspect its member destinations with ``_root_archive_hit`` instead.
    Rule C refuses unknown root archives over existing records; Rule F also refuses them during an active run."""
    for write, targets in call.shell_targets(analysis=analysis):
        above = write.via in tree_via
        for target in targets:
            reach = above and (root_extracts or write.via not in _EXTRACT_VIA or not _at_or_above_root(call, target))
            for boundary in boundaries:
                if boundary.matches(target) or (reach and boundary.covers(target)):
                    return boundary
    return None


def _analyses(analysis):
    """The analysis of the command line and, below it, those of the commands a launcher or script block runs
    (``parallel``, ``entr``, ``watch``, a PowerShell ``{ ... }``): findings the analyser keeps apart from the line's own."""
    pending = [analysis]
    while pending:
        current = pending.pop()
        yield current
        pending.extend(current.hidden)


# --- Rule B: frozen and blocked boundaries ---------------------------------------------------------

# A shell command counts as a *write* into a boundary only if the analyser sees it write there
# (a redirect, or a file-mutating command's target). A read-only command (cat/grep/ls/Get-Content)
# that merely *references* a frozen path is NOT a write and must pass: blocking it would violate the
# doctrine's Principles (inert on a competent action). When mutation cannot be determined the
# command is treated as non-mutating and proceeds (fail open per Principles).
#
# The commands a launcher or script block runs (`watch 'rm src/payments/a'`, `parallel rm ::: src/payments/a`, a
# PowerShell `{ Remove-Item ... }`) are judged exactly as the command line is. A write whose target the analyser cannot
# place (`echo 'rm src/payments/a' | sh`, `cat src/payments/list | xargs rm`, a diff fed to `patch`, `rm "$f"`) is
# judged by the text: it is refused when the command also spells a boundary path, which is the substring rule this
# analyser replaced, kept for the one case where the analysis cannot say.
_SHELL_MUTATION = re.compile(
    r">>?|>\|"                                                      # output redirection
    r"|(?<![\w.-])(?:rm|mv|cp|ln|dd|tee|truncate|shred|install|"    # mutating coreutils
    r"mkdir|rmdir|touch|chmod|chown|unlink|rename|curl|wget|rsync|scp|tar|unzip|zip|patch|python[0-9.]*|py|node|perl|ruby|php|"
    r"awk|gawk|sed|find|xargs|sort|gzip|gunzip|xz|bzip2|gpg)(?![\w-])"
    r"|\bgit\s+(?:add|commit|checkout|restore|reset|rm|mv|apply|stash|clean|push|merge|pull|rebase|cherry-pick|revert|switch|am)\b"
    r"|(?<![\w.-])(?:Set-Content|Add-Content|Clear-Content|Out-File|Tee-Object|Export-Csv|Invoke-WebRequest|Expand-Archive|"
    r"Remove-Item|Move-Item|Copy-Item|New-Item|Rename-Item)(?![\w-])"  # PS cmdlets
    r"|(?<![\w.-])(?:ni|ri|rni|mi|ci|sc|ac|clc)(?![\w-])",          # PS aliases
    re.IGNORECASE,
)
# What a redirect looks like when it is not a write: descriptor duplication and the null device.
_NOT_A_WRITE = re.compile(r"\d*[<>]&\s*(?:\d+|-)|&?\d*>>?\s*/dev/(?:null|stdout|stderr|tty)\b|\b\d*>\s*nul\b", re.I)


def _textual_mutates(cmd: str) -> bool:
    return bool(_SHELL_MUTATION.search(_NOT_A_WRITE.sub(" ", cmd)))


# The words the substring rule counted as a mutation, for a command whose program the analyser cannot read: a shell or
# interpreter on a pipe says nothing of what it writes, so the text has to spell one of these (and the cmd verbs that do
# what `rm`, `mv` and `cp` do, for `echo 'del a' | cmd`). `_SHELL_MUTATION` also counts every interpreter and `sort`, which
# would refuse `cat src/payments/run.py | python3`.
_SPELLED_MUTATION = re.compile(
    r">>?|>\|"
    r"|(?<![\w.-])(?:rm|mv|cp|ln|dd|tee|truncate|shred|install|mkdir|rmdir|touch|chmod|chown|unlink|rename|"
    r"del|erase|rd|ren|move|copy|xcopy|robocopy)(?![\w-])"
    r"|\bsed\s+-[a-z]*i|\bperl\s+-[a-z]*i\b"
    r"|\bgit\s+(?:add|commit|checkout|restore|reset|rm|mv|apply|stash|clean|push)\b"
    r"|(?<![\w.-])(?:Set-Content|Add-Content|Clear-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|Rename-Item)(?![\w-])"
    r"|(?<![\w.-])(?:ni|ri|rni|mi|ci|sc|ac|clc)(?![\w-])",
    re.IGNORECASE,
)


def _unplaced_command(call: "Call", analyses) -> "str | None":
    """The command text to search for a protected path, when it holds a write the analyser cannot place; else None.

    Such a write could land anywhere, so it cannot be shown to stay outside a boundary. The substring rule that preceded
    the analyser refused a command that spelled a boundary path next to a mutating word; this keeps that reason where
    the analysis cannot give a better one:

    * a write the analyser found but cannot place (operands on standard input, the files named inside a diff, a redirect
      or file open inside an inline program, a path built at run time) is a write whatever the words say;
    * a program it cannot read (a shell or interpreter on a pipe, text it could not parse) is a write only if the text also
      spells a mutating word, or a program write the analyser knows from inline code (``os.remove(...)``), so
      ``cat src/payments/run.sh | bash`` is not refused."""
    unnamed = [entry for analysis in analyses for entry in analysis.unnamed]
    found = any(not entry.opaque for entry in unnamed) or any(write.unresolved for analysis in analyses for write in analysis.writes)
    opaque = any(entry.opaque for entry in unnamed)
    if found or (opaque and (_SPELLED_MUTATION.search(_NOT_A_WRITE.sub(" ", call.command)) or _cmdscan.program_text_writes(call.command))):
        return _WORD_END_ESCAPE.sub(" ", call.command)
    return None


def _frozen_boundaries(call: "Call") -> list:
    globs = list(call.guard.get("frozen_globs") or []) + list(call.guard.get("blocked_globs") or [])
    return [_paths.Boundary(glob, call.root) for glob in globs if isinstance(glob, str) and glob]


def _boundary_kind(call: "Call", boundary) -> tuple:
    """``(kind, lift)`` for the denial: a glob recorded in ``blocked_globs`` (and not also frozen) is a block."""
    frozen = call.guard.get("frozen_globs") or []
    blocked = call.guard.get("blocked_globs") or []
    if boundary.glob in blocked and boundary.glob not in frozen:
        return "blocked", "block"
    return "frozen", "freeze"


def rule_frozen(call: "Call") -> "str | None":
    """Rule B: a write into a frozen or blocked boundary is denied; a read never is."""
    boundaries = _frozen_boundaries(call)
    if not boundaries:
        return None
    if call.writer:
        for target in call.edit_targets:
            for boundary in boundaries:
                if boundary.matches(target):
                    kind, lift = _boundary_kind(call, boundary)
                    return (f"Blocked by harness Action Realization layer: target is inside a {kind} "
                            f"boundary ({_state.safe_text(boundary.glob)}). Lift the {lift} via the unfreeze skill before editing here.")
        return None
    if not call.shell:
        return None
    if call.analysis.ok:
        hit = None
        analyses = list(_analyses(call.analysis))
        for analysis in analyses:
            code = analysis.code if any(not item.opaque for item in analysis.unnamed) else []
            hit = (_shell_hit(call, boundaries, analysis=analysis, root_extracts=False)
                   or _root_archive_hit(call, boundaries, analysis)
                   or _mentioned(code, call, boundaries))
            if hit:
                break
        text = _unplaced_command(call, analyses) if hit is None else None
        if text is not None:
            hit = _mentioned([text], call, boundaries)
    else:
        hit = _mentioned([call.command], call, boundaries) if _textual_mutates(call.command) else None
    if hit:
        kind, lift = _boundary_kind(call, hit)
        return (f"Blocked by harness Action Realization layer: a mutating command targets a "
                f"{kind} boundary ({_state.safe_text(hit.glob)}). Lift the {lift} via the unfreeze skill before proceeding.")
    return None


# --- Rule D: read-only run ---------------------------------------------------------------------------

# While an unreleased read_only record exists (recorded by the `guard` skill through guard_state.py
# read-only, for an investigation or audit that must not change the product surface), the only
# writable locations are the record's allow globs (the run's own save path) and the harness state
# directory. EVERY write target of a command must lie inside them: naming one allowed path
# somewhere in a mutating command proves nothing about the others, and neither does a write whose target the
# command does not name (operands on standard input, a file opened inside an inline program). save_run.py keeps
# writing the run records because a script's arguments are never write targets, and Rule C still protects
# guard-state.json itself.
_GIT_REPO_WRITERS = frozenset({"add", "commit", "checkout", "restore", "reset", "rm", "mv", "apply", "stash", "clean", "push",
                               "merge", "pull", "rebase", "cherry-pick", "revert", "switch", "am"})
_GIT_PATHSPEC = frozenset({"add", "checkout", "restore", "reset", "rm", "mv", "clean", "apply", "stash", "commit"})


def _read_only_reason(records) -> str:
    run_ids = ", ".join(_state.safe_text(r.get("run_id", "?"), 60) for r in records)
    return (
        f"Blocked by harness Action Realization layer: run {run_ids} is recorded read-only. "
        "Only the run's own save path may change; record the decision, then release the boundary with "
        "'python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <owner>' "
        "before changing anything else."
    )


# A write the command names no target for is not inside the run's paths whatever it writes: the contract is that every
# target lies inside, and one the analyser cannot place cannot satisfy it.
_UNNAMED_REASON = (
    " A write whose target is not in the command (operands that arrive on standard input, as with `xargs rm`, a program "
    "read from a pipe, the files named inside a diff, or a redirect or file open inside an awk, sed, perl, python, ruby "
    "or node program) cannot be shown to be inside them: name each target in the shell command itself, as an operand "
    "or a redirect."
)


def _unscoped_git(analysis) -> bool:
    """A git command that changes the repository or tree and names no path to judge (``git add -A``, ``git push``).

    An index-only command (``git restore --staged .``) names pathspecs but writes no file, so it is the repository
    it changes and counts here. ``git apply --check`` and its kin only report, and change nothing."""
    for command in analysis.commands:
        if command.verb != "git":
            continue
        sub, operands, _, flags = _cmdscan.git_parts(command.argv)
        if _cmdscan.git_dry_run(sub, flags):
            continue
        index = command.argv.index(sub) if sub in command.argv else len(command.argv)
        if _cmdscan.git_ref_mutates(sub, command.argv[index + 1:]):
            return True
        if sub in _GIT_REPO_WRITERS and not (sub in _GIT_PATHSPEC and operands and not _cmdscan.git_index_only(sub, flags)):
            return True
    return False


def _dry_vias(analysis) -> frozenset:
    """The write labels of ``git apply`` and ``patch`` when every one of them only checks: the file such a command names
    is read, not written."""
    checks: dict = {}
    for command in analysis.commands:
        if command.verb == "patch":
            checks["patch"] = checks.get("patch", True) and _cmdscan.patch_dry_run(command.argv)
        elif command.verb == "git":
            sub, _, _, flags = _cmdscan.git_parts(command.argv)
            if sub == "apply":
                checks["git apply"] = checks.get("git apply", True) and _cmdscan.git_dry_run(sub, flags)
    return frozenset(via for via, dry in checks.items() if dry)


# Package managers change the dependency directory, a lockfile or the machine without naming a path, so a read-only
# run may not run them. Each maps to the subcommands that install, remove or update; scripts they run are not seen.
_JS_PACKAGE = frozenset({"install", "i", "ci", "add", "remove", "rm", "uninstall", "un", "update", "up", "upgrade", "link", "prune",
                         "dedupe", "rebuild"})
_SYSTEM_PACKAGE = frozenset({"install", "remove", "purge", "uninstall", "upgrade", "dist-upgrade", "autoremove"})
_PACKAGE_MANAGERS = {
    **dict.fromkeys(("npm", "pnpm", "yarn", "bun"), _JS_PACKAGE),
    **dict.fromkeys(("pip", "pip3"), frozenset({"install", "uninstall"})),
    "pipx": frozenset({"install", "uninstall", "upgrade", "inject", "reinstall"}),
    "uv": frozenset({"add", "remove", "sync", "lock"}),
    **dict.fromkeys(("apt", "apt-get", "aptitude", "dnf", "yum", "zypper", "apk", "brew", "choco", "scoop", "winget", "port"), _SYSTEM_PACKAGE),
    "gem": frozenset({"install", "uninstall", "update"}),
    "cargo": frozenset({"install", "add", "remove", "update"}),
    "go": frozenset({"get", "install"}),
    "composer": frozenset({"install", "require", "remove", "update"}),
    "bundle": frozenset({"install", "add", "update", "remove"}),
    "poetry": frozenset({"install", "add", "remove", "update", "lock"}),
    **dict.fromkeys(("conda", "mamba"), frozenset({"install", "remove", "update", "create", "uninstall"})),
}
# Runners that fetch and execute a package: only the ones told to install something (`npx playwright install`).
_PACKAGE_RUNNERS = frozenset({"npx", "pnpx", "bunx", "uvx"})
_INSTALL_WORDS = frozenset({"install", "i", "add", "uninstall", "update"})


def _changes_packages(command) -> bool:
    verb, operands = command.verb, _operands(command.argv)
    if (verb == "uv" or (re.fullmatch(r"python[0-9.]*|py", verb) and "-m" in command.argv)) and operands[:1] in (["pip"], ["pip3"]):
        verb, operands = "pip", operands[1:]
    if verb in _PACKAGE_RUNNERS:
        return any(word in _INSTALL_WORDS for word in operands)
    if verb not in _PACKAGE_MANAGERS:
        return False
    if verb == "yarn" and not operands:  # a bare `yarn` installs; only its version and help flags do not
        return not {"--version", "-v", "--help", "-h"} & set(command.argv)
    return any(word in _PACKAGE_MANAGERS[verb] for word in operands[:3])


def _installs_packages(analysis) -> bool:
    """A package manager command that installs, removes or updates packages (``npm install``, ``sudo apt-get install -y jq``)."""
    return any(_changes_packages(command) for command in analysis.commands)


def rule_read_only(call: "Call") -> "str | None":
    """Rule D: while a run is recorded read-only, every write must land inside its allow list."""
    records = call.guard.get("read_only") or []
    if not records:
        return None
    allow = _state.read_only_allow(records)
    fold = _paths.case_insensitive_fs()
    if call.writer:
        if any(not _paths.inside_allowed(target, allow, call.root, fold=fold) for target in call.edit_targets):
            return _read_only_reason(records)
        return None
    if not call.shell:
        return None
    if not call.analysis.ok:
        if _textual_mutates(call.command) and _mentioned([call.command], call, [_paths.Boundary(g, call.root) for g in allow]) is None:
            return _read_only_reason(records)
        return None
    analyses = list(_analyses(call.analysis))
    # A command with a write it names no target for says so whichever write is refused first (`echo 'rm x' | sh` is read
    # for the program the pipe carries, and the shell on the pipe is still a program the command does not hold).
    reason = _read_only_reason(records) + (_UNNAMED_REASON if any(analysis.unnamed for analysis in analyses) else "")
    for analysis in analyses:
        dry = _dry_vias(analysis)
        for write, targets in call.shell_targets(strict=True, analysis=analysis):
            if write.via in dry:
                continue
            if write.unresolved or any(not _paths.inside_allowed(target, allow, call.root, fold=fold) for target in targets):
                return reason
        if _unscoped_git(analysis) or _installs_packages(analysis):
            return reason
    return reason if any(analysis.unnamed for analysis in analyses) else None


# --- Rule C: single writers --------------------------------------------------------------------------

# Core save-protocol files with a single sanctioned writer (save_run.py). `_write.lock` is the writer mutex: a hand edit
# that replaces or removes it while a writer holds it gives the next writer another file to lock.
_CORE_SAVE_FILE = re.compile(
    r"(?:^|/)skillset-saves/(?:_latest\.md|_write\.lock|runs/[^/]+/(?:_state\.md|_lock\.md|_audit-trail\.md|_journal\.json|_history/[^/]+))$", re.I
)
_CORE_SAVE_REASON = (
    "Blocked by harness Action Realization layer: core save files are written only by "
    "skills/harness/hooks/save_run.py (create/checkpoint/heartbeat/complete/release/recover) "
    "so revision lineage, history snapshots, and the audit trail stay coherent."
)
# Durable project Taste state has one sanctioned writer.
_TASTE_SAVE_PATH = re.compile(
    r"(?:^|/)skillset-saves/preferences/(?:taste\.(?:json|md)|taste\.journal\.jsonl|taste\.lock|_history(?:/.*)?)$", re.I
)
_TASTE_SAVE_REASON = (
    "Blocked by harness Action Realization layer: durable project Taste records, views, "
    "history, journals, and locks are written only by skills/taste/taste_prefs.py. "
    "Use that command's mutation subcommands instead of an edit tool."
)
# The guard/freeze boundary record itself. Without this rule the boundary is
# self-liftable: a single write clearing frozen_globs, or setting
# allow_dangerous, disables the rules below before they ever run. One sanctioned
# writer (guard_state.py) keeps a release attributable and reversible.
_GUARD_STATE_PATH = re.compile(r"(?:^|/)\.harness-state/guard-state\.json$", re.I)
_GUARD_STATE_NAME = re.compile(r"guard-state\.json", re.I)
_GUARD_STATE_REASON = (
    "Blocked by harness Action Realization layer: the guard/freeze boundary record is "
    "written only by skills/harness/hooks/guard_state.py "
    "(freeze/block/release/allow-dangerous/revoke-dangerous/read-only). Editing it directly "
    "would lift an owned boundary with no owner check and no released_at trail."
)
# The same files named anywhere inside a command that could not be tokenised.
_CORE_SAVE_TOKEN = re.compile(
    r"skillset-saves/(?:_latest\.md|_write\.lock|runs/[^\s\"'/]+/(?:_state\.md|_lock\.md|_audit-trail\.md|_journal\.json|_history/))", re.I
)
# The directories above a protected file: removing or moving one removes the file.
_PROTECTED_DIRS = re.compile(r"(?:^|/)\.harness-state/?$|(?:^|/)skillset-saves(?:/runs(?:/[^/]+(?:/_history)?)?|/preferences)?/?$", re.I)
_PROTECTED_FRAGMENTS = ("skillset-saves", ".harness-state")


def _protected_reason(target: "_paths.Target", above: bool = False) -> "str | None":
    forms = [*target.abs, *target.rel, *("/" + form for form in target.rel)]
    for form in forms:
        if _CORE_SAVE_FILE.search(form):
            return _CORE_SAVE_REASON
        if _TASTE_SAVE_PATH.search(form):
            return _TASTE_SAVE_REASON
        if _GUARD_STATE_PATH.search(form):
            return _GUARD_STATE_REASON
    if above:
        for form in forms:
            if _PROTECTED_DIRS.search(form):
                return _GUARD_STATE_REASON if ".harness-state" in form.lower() else _CORE_SAVE_REASON
    return None


# --- Rule C at the project root: what a command aimed above the record directories would put into them ----------

# The directories under the project root that hold single-writer records, and the record that makes each one count:
# a command aimed at the root reaches them only when one of these exists, so a project with no guard record and no
# saves is never refused here.
_RECORD_HOMES = ((".harness-state", ("guard-state.json",)),
                 ("skillset-saves", ("_latest.md", "_write.lock", "runs", "preferences")))
_ROOT_RECORDS_REASON = (
    "Blocked by harness Action Realization layer: this command is aimed at the project root and would {how} {names}, "
    "which hold records with one writer each (save_run.py, taste_prefs.py, guard_state.py). Aim it at a named "
    "directory, exclude those directories (git clean -e, rsync --exclude), or extract the archive elsewhere and copy "
    "what you need."
)
_ARCHIVE_MEMBER_LIMIT = 200_000
_DELETE_FLAG = re.compile(r"^--del(?:ete(?:-\w+)?)?$")


def _homes_present(root: Path) -> list:
    """The record directories under ``root`` that hold a record now."""
    present = []
    for home, records in _RECORD_HOMES:
        try:
            if any((root / home / name).exists() for name in records):
                present.append(home)
        except OSError:
            present.append(home)
    return present


def _below_root(call: "Call", target: "_paths.Target") -> "str | None":
    """The path from ``target`` down to the project root (``""`` at the root, ``proj/`` from its parent), or None when
    ``target`` is not the root or above it."""
    roots = call.locate(_paths.posix(call.root), []).abs
    for form in target.abs:
        for root in roots:
            if root == form:
                return ""
            prefix = form.rstrip("/") + "/"
            if root.startswith(prefix):
                return root[len(prefix):] + "/"
    return None


def _command_bases(call: "Call", cwds) -> list:
    # Root-reach probes use a real final directory, not also the original
    # root: `cd sub && git clean` does not clean the directory it left.
    bases = [word if _paths.is_absolute(word) else posixpath.join(call.starts[0], word)
             for word in cwds[-1:]]
    # A failed `cd missing; ...` leaves the shell at its starting directory.
    # Without a real final directory, retain that candidate rather than turn
    # the false-positive fix into a root-clean bypass.
    if bases and all(os.path.isdir(base) for base in bases):
        return bases
    return [*call.starts[:1], *bases]


def _member_home(name: str, prefix: str, homes) -> "str | None":
    """The record directory an archive member or copied entry ``name`` lands in, ``prefix`` below where it is unpacked."""
    path = posixpath.normpath(name.replace("\\", "/").lstrip("/")).lower()
    for home in homes:
        top = (prefix + home).lower()
        if path == top or path.startswith(top + "/"):
            return home
    return None


def _archive_members(path: str) -> "list | None":
    """The member names of a tar or zip archive on disk, or None when it cannot be read (absent, another format, too big)."""
    import tarfile
    import zipfile

    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                # ZIP Unix symlinks can redirect a later member into a record.
                if any((entry.external_attr >> 16) & 0o170000 == 0o120000 for entry in entries):
                    return None
                names = [entry.filename for entry in entries]
        elif tarfile.is_tarfile(path):
            names = []
            with tarfile.open(path) as archive:
                for member in archive:
                    # Links and special entries require extraction semantics we
                    # cannot safely simulate; do not trust their member names.
                    if not (member.isfile() or member.isdir()):
                        return None
                    names.append(member.name)
                    if len(names) > _ARCHIVE_MEMBER_LIMIT:
                        return None
        else:
            return None
    except (OSError, EOFError, tarfile.TarError, zipfile.BadZipFile, ValueError):
        return None
    if len(names) > _ARCHIVE_MEMBER_LIMIT or any(
            name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name) or
            ".." in name.replace("\\", "/").split("/") for name in names):
        return None
    return names


def _extract_members(call: "Call", command, archive, bases) -> "list | None":
    # Renaming/stripping and absolute-name modes invalidate the name inventory.
    # Stage these extracts outside the project instead of guessing their output.
    if command.verb not in {"tar", "unzip", "7z"}:
        return None
    if command.verb == "tar" and any(
            word.startswith(("--strip", "--trans", "--xform", "--abs", "-s")) or (not word.startswith("--") and
                             re.fullmatch(r"-?[A-Za-z]+", word) and "P" in word)
            for word in command.argv):
        return None
    return _archive_members(call.locate(archive, bases).abs[0]) if archive else None


def _root_archive_hit(call: "Call", boundaries, analysis):
    """Read member destinations for root extracts instead of ignoring them.

    Unknown root inventories cannot prove avoidance of a covered boundary.
    Rule C additionally protects records and Rule F protects active hooks.
    This bounded inventory is not a sandbox or a runtime path proof.
    """
    for command in analysis.commands:
        extract = _cmdscan.extract_parts(command.verb, command.argv)
        if extract is None:
            continue
        archive, destination = extract
        bases = _command_bases(call, command.cwds)
        if not _at_or_above_root(call, call.locate(destination, bases)):
            continue
        members = _extract_members(call, command, archive, bases)
        if members is None:
            target = call.locate(destination, bases)
            for boundary in boundaries:
                if boundary.covers(target):
                    return boundary
            continue
        for name in members:
            target = call.locate(posixpath.join(destination, name), bases)
            for boundary in boundaries:
                if boundary.matches(target):
                    return boundary
    return None


def _source_reaches(source: str, contents: bool, prefix: str, home: str) -> bool:
    """True when copying ``source`` (a path on disk) to a destination ``prefix`` above the project root would land on
    ``home`` (a record directory under the root): its entries do for a contents copy (``x/.``, an ``rsync`` source with
    a trailing slash), its own name does otherwise."""
    if contents:
        return os.path.exists(os.path.join(source, prefix, home))
    name = os.path.basename(source.rstrip("/\\"))
    first, _, rest = (prefix + home).partition("/")
    return name.lower() == first.lower() and (not rest or os.path.exists(os.path.join(source, rest)))


def _excluded(home: str, patterns) -> bool:
    import fnmatch

    # A descendant pattern does not exclude its parent directory. Negation and
    # ordered rule languages are not proof of protection, so stay conservative.
    if any(pattern.startswith("!") for pattern in patterns):
        return False
    return any(fnmatch.fnmatchcase(home, pattern.strip("/"))
               for pattern in patterns if pattern.strip("/") and "/" not in pattern.strip("/"))


def _git_ignores(root: Path, home: str) -> bool:
    """True when the project's own ignore files name ``home`` (then `git clean -d` without `-x` leaves it alone)."""
    for name in (".gitignore", ".git/info/exclude"):
        try:
            lines = (root / name).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if _excluded(home, [line.strip() for line in lines if line.strip() and not line.startswith(("#", "!"))]):
            return True
    return False


# What a record directory holds, below it: the files each single writer owns and the directories above them.
_RUN_FILES = ("_state.md", "_lock.md", "_audit-trail.md", "_journal.json", "_history")
_PREFERENCE_FILES = ("taste.json", "taste.md", "taste.journal.jsonl", "taste.lock", "_history")
_LISTING_LIMIT = 256


def _listed(directory: Path) -> list:
    """Up to ``_LISTING_LIMIT`` entry names of ``directory`` (none when it cannot be read)."""
    try:
        return [entry.name for entry in itertools.islice(os.scandir(directory), _LISTING_LIMIT)]
    except OSError:
        return []


def _record_paths(root: Path, home: str) -> list:
    """The project-relative paths of ``home`` (a record directory) that a name or path test could single out: the
    directory, every record file in it, the directories above them, each run (listed, bounded) and its history."""
    if home == ".harness-state":
        return [".harness-state", ".harness-state/guard-state.json"]
    paths = ["skillset-saves", "skillset-saves/_latest.md", "skillset-saves/_write.lock", "skillset-saves/runs",
             "skillset-saves/preferences", *(f"skillset-saves/preferences/{name}" for name in _PREFERENCE_FILES),
             *(f"skillset-saves/preferences/_history/{name}" for name in _listed(root / home / "preferences" / "_history"))]
    runs = root / home / "runs"
    for run in ["run", *_listed(runs)]:
        base = f"skillset-saves/runs/{run}"
        paths += [base, *(f"{base}/{name}" for name in _RUN_FILES),
                  *(f"{base}/_history/{name}" for name in ["entry", *_listed(runs / run / "_history")])]
    return paths


# ``find`` tests that take one argument, and the ones that take two; any other word starting with ``-`` takes none.
_FIND_ONE = frozenset({"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-type", "-xtype",
                       "-size", "-mtime", "-atime", "-ctime", "-mmin", "-amin", "-cmin", "-newer", "-anewer", "-cnewer",
                       "-perm", "-user", "-group", "-uid", "-gid", "-links", "-inum", "-samefile", "-lname", "-ilname",
                       "-fstype", "-used", "-context", "-printf", "-fprint", "-fprint0", "-fls", "-maxdepth", "-mindepth",
                       "-regextype", "-files0-from"})
_FIND_TWO = frozenset({"-fprintf"})
_FIND_EXEC = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
# What ``-exec`` may run that removes or rewrites the file it is given, anywhere in its words (``sh -c 'rm "$1"' _ {}``).
_FIND_REMOVER = re.compile(r"(?<![\w.-])(?:rm|unlink|shred|rmdir|mv|truncate)(?![\w-])")
_EMACS_REGEX = re.compile(r"\\[(){}|]")
_EITHER = frozenset({True, False})
# How many record paths one call may test against ``find`` expressions. A command past it (thousands of root-aimed
# ``find -delete`` in one line) is read as reaching the records rather than costing time without bound.
_FIND_BUDGET = 100_000


class _FindExpression:
    """A ``find`` expression read for one question: may it remove a given path? Each node gives the values it may take
    for that path and whether a removing action (``-delete``, ``-exec rm``) may run. Name and path tests are decided
    exactly; every other test may be true or false, so the answer errs toward "may remove"."""

    def __init__(self, words: list) -> None:
        self.words, self.i = words, 0
        self.tree = self._or()
        if self.i < len(self.words):
            raise ValueError("unbalanced")

    def _peek(self) -> "str | None":
        return self.words[self.i] if self.i < len(self.words) else None

    def _or(self):
        node = self._and()
        while self._peek() in ("-o", "-or", ","):
            op = "," if self.words[self.i] == "," else "or"
            self.i += 1
            node = (op, node, self._and())
        return node

    def _and(self):
        node = self._not()
        while self._peek() not in (None, "-o", "-or", ",", ")"):
            if self._peek() in ("-a", "-and"):
                self.i += 1
            node = ("and", node, self._not())
        return node

    def _not(self):
        if self._peek() in ("!", "-not"):
            self.i += 1
            return ("not", self._not())
        if self._peek() == "(":
            self.i += 1
            node = self._or()
            if self._peek() != ")":
                raise ValueError("unbalanced")
            self.i += 1
            return node
        return self._primary()

    def _primary(self):
        if self._peek() is None:
            raise ValueError("missing primary")
        word = self.words[self.i]
        self.i += 1
        if word in _FIND_EXEC:
            command = []
            while self._peek() not in (None, ";", "+"):
                command.append(self.words[self.i])
                self.i += 1
            self.i += 1
            return ("remove",) if _FIND_REMOVER.search(" ".join(command)) else ("unknown",)
        count = 2 if word in _FIND_TWO else 1 if word in _FIND_ONE else 0
        args = self.words[self.i:self.i + count]
        if len(args) < count:
            raise ValueError("missing argument")
        self.i += count
        if word == "-delete":
            return ("remove",)
        if word in ("-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex"):
            return ("test", word, args[0])
        if word == "-false":
            return ("const", frozenset({False}))
        if word in ("-true", "-print", "-print0", "-prune", "-quit", "-ls", "-fprint", "-fprint0", "-fls", "-printf", "-fprintf",
                    "-maxdepth", "-mindepth", "-depth", "-d", "-xdev", "-mount", "-follow", "-noleaf", "-regextype",
                    "-ignore_readdir_race", "-noignore_readdir_race", "-daystart", "-warn", "-nowarn", "-files0-from"):
            return ("const", frozenset({True}))
        return ("unknown",)

    @staticmethod
    def _test(name: str, pattern: str, path: str) -> frozenset:
        import fnmatch

        fold = name.startswith("-i")
        subject = posixpath.basename(path) if name.endswith("name") and "whole" not in name else path
        if fold:
            subject, pattern = subject.lower(), pattern.lower()
        if name.endswith("regex"):
            if _EMACS_REGEX.search(pattern):
                return _EITHER
            try:
                return frozenset({re.fullmatch(pattern, subject, re.S) is not None})
            except re.error:
                return _EITHER
        return frozenset({fnmatch.fnmatchcase(subject, pattern)})

    def removes(self, path: str) -> bool:
        return self._eval(self.tree, path)[1]

    def _eval(self, node, path: str) -> tuple:
        kind = node[0]
        if kind == "remove":
            return frozenset({True}), True
        if kind == "unknown":
            return _EITHER, False
        if kind == "const":
            return node[1], False
        if kind == "test":
            return self._test(node[1], node[2], path), False
        if kind == "not":
            values, removes = self._eval(node[1], path)
            return frozenset(not value for value in values), removes
        left, left_removes = self._eval(node[1], path)
        if kind == ",":
            right, right_removes = self._eval(node[2], path)
            return right, left_removes or right_removes
        # `-a` runs its right side when the left is true, `-o` when it is false.
        go_on = (True if kind == "and" else False) in left
        right, right_removes = self._eval(node[2], path) if go_on else (frozenset(), False)
        stop = frozenset({False}) if kind == "and" else frozenset({True})
        return (left & stop) | right, left_removes or right_removes


def _find_reach(call: "Call", command, bases, homes) -> "tuple | None":
    """``(how, homes)`` for a ``find`` aimed at the project root or above it whose expression may remove a record:
    ``find . -name guard-state.json -delete``, ``find . -type f -delete``, ``find . -name '*.md' -exec rm {} +``. One
    whose name and path tests single out none of them (``find . -name '*.pyc' -delete``) passes."""
    argv = list(command.argv)
    i = 0
    while i < len(argv) and (argv[i] in ("-H", "-L", "-P") or argv[i].startswith("-O")):
        i += 1
    starts = []
    while i < len(argv) and not argv[i].startswith(("-", "(", "!")):
        starts.append(argv[i])
        i += 1
    words = argv[i:]
    if not any(word == "-delete" or word in _FIND_EXEC for word in words):
        return None
    try:
        expression = _FindExpression(words)
    except ValueError:
        expression = None
    records = call.record_paths
    hit = set()
    for start in starts or ["."]:
        prefix = _below_root(call, call.locate(start, bases))
        if prefix is None:
            continue
        lead = start.rstrip("/") or "/"
        for home in homes:
            if home in hit:
                continue
            if home not in records:
                records[home] = _record_paths(call.root, home)
            call.find_spent += len(records[home])
            if expression is None or call.find_spent > _FIND_BUDGET:
                hit.add(home)
                continue
            for rel in records[home]:
                if expression.removes((lead if lead == "/" else lead + "/") + prefix + rel):
                    hit.add(home)
                    break
    return ("delete files in", sorted(hit)) if hit else None


def _stash_reach(call: "Call", command, bases, homes) -> "tuple | None":
    """``(how, homes)`` for a ``git stash`` that takes untracked files away with it: ``-u``/``--include-untracked`` removes
    a record directory git does not ignore, ``-a``/``--all`` one it ignores as well, and both only where their pathspecs
    reach (none, or one at the project root or above it, or inside the directory)."""
    parts = _cmdscan.git_stash_parts(command.argv)
    if parts is None:
        return None
    pathspecs, directories, flags = parts
    letters = "".join(f[1:] for f in flags if not f.startswith("--"))
    longs = [f for f in flags if f.startswith("--")]
    everything = "a" in letters or any(len(f) >= 3 and "--all".startswith(f) for f in longs)
    untracked = everything or "u" in letters or any(len(f) >= 5 and "--include-untracked".startswith(f) for f in longs)
    if not untracked:
        return None
    bases = [posixpath.join(base, d) if not _paths.is_absolute(d) else d for d in directories for base in bases] or bases
    reached = set()
    if not pathspecs or "--pathspec-from-file" in flags:
        reached.update(homes)
    for spec in pathspecs:
        if spec.startswith(":") or any(c in spec for c in "*?["):
            reached.update(homes)  # a magic or wildcard pathspec can match anywhere
            continue
        target = call.locate(spec, bases)
        if _below_root(call, target) is not None:
            reached.update(homes)
        reached.update(home for rel in target.rel for home in [_member_home(rel, "", homes)] if home)
    hit = sorted(home for home in reached if everything or not _git_ignores(call.root, home))
    return ("stash away (and so delete)", hit) if hit else None


def _root_command_reach(call: "Call", command) -> "tuple | None":
    """``(how, homes)`` when ``command`` is aimed at the project root and would remove or replace a record directory."""
    homes = _homes_present(call.root)
    if not homes:
        return None
    bases = _command_bases(call, command.cwds)
    verb = command.verb
    if verb == "find":
        return _find_reach(call, command, bases, homes)
    if verb == "git" and _cmdscan.git_stash_parts(command.argv) is not None:
        return _stash_reach(call, command, bases, homes)
    if verb == "git":
        parts = _cmdscan.git_clean_parts(command.argv)
        if parts is None:
            return None
        pathspecs, directories, flags, excludes = parts
        letters = "".join(f[1:] for f in flags if not f.startswith("--"))
        if "n" in letters or "--dry-run" in flags or not ("f" in letters or "--force" in flags or "i" in letters):
            return None
        if "d" not in letters and not pathspecs:
            return None
        bases = [posixpath.join(base, d) if not _paths.is_absolute(d) else d for d in directories for base in bases] or bases
        reached = set()
        for spec in pathspecs or ["."]:
            # Magic may be top-anchored regardless of cwd. Wildcards are Git
            # pathspecs even when shell-quoted, not literal filesystem paths.
            if spec.startswith(":"):
                reached.update(homes)
            elif any(c in spec for c in "*?["):
                lead = re.split(r"[*?\[]", spec, maxsplit=1)[0]
                target = call.locate(lead.rsplit("/", 1)[0] if "/" in lead else ".", bases)
                if _below_root(call, target) is not None:
                    reached.update(homes)
                reached.update(home for rel in target.rel for home in [_member_home(rel, "", homes)] if home)
            else:
                target = call.locate(spec, bases)
                if _below_root(call, target) is not None:
                    reached.update(homes)
                reached.update(home for rel in target.rel for home in [_member_home(rel, "", homes)] if home)
        if not reached:
            return None
        ignored_too = "x" in letters or "X" in letters
        hit = [home for home in homes if home in reached and not _excluded(home, excludes)
               and (ignored_too or not _git_ignores(call.root, home))]
        return ("remove", hit) if hit else None
    extract = _cmdscan.extract_parts(verb, command.argv)
    if extract is not None:
        archive, destination = extract
        target = call.locate(destination, bases)
        prefix = _below_root(call, target)
        members = _extract_members(call, command, archive, bases)
        if prefix is None:
            # A readable archive with unsafe modes/links may escape even a
            # named subdirectory. Missing archives there stay an analysis limit.
            local = call.locate(archive, bases).abs[0] if archive else None
            if members is None and target.rel and local and os.path.isfile(local):
                return "unpack an archive with unproven destinations over", homes
            return None
        if members is None:
            return "unpack an archive the guard cannot read over", homes
        hit = set()
        for name in members:
            target = call.locate(posixpath.join(destination, name), bases)
            hit.update(home for rel in target.rel for home in [_member_home(rel, "", homes)] if home)
            if _protected_reason(target):
                hit.update(homes)
        hit = sorted(hit)
        return ("unpack files into", hit) if hit else None
    copy = _cmdscan.copy_parts(verb, command.argv)
    if copy is None:
        return None
    sources, destination, flags, excludes = copy
    prefix = _below_root(call, call.locate(destination, bases))
    if prefix is None:
        return None
    homes = [home for home in homes if not _excluded(home, excludes)]
    if verb == "rsync" and any(_DELETE_FLAG.match(flag) for flag in flags):
        return ("delete what the source lacks from", homes) if homes else None
    hit = set()
    for source in sources:
        # A source the command does not fix (a variable, a remote host:path, a glob that matches nothing, a path that is
        # not there) could hold anything, so it is read as reaching every record directory.
        if "$" in source or "`" in source or (re.match(r"^[^/\\]+:", source) and not re.match(r"^[A-Za-z]:", source)):
            hit.update(homes)
            continue
        local = call.locate(source, bases).abs[0]
        contents = (source.endswith(("/.", "\\.")) or
                    (verb == "rsync" and source.endswith(("/", "\\"))) or
                    (verb in {"cp", "ln"} and ("--no-target-directory" in flags or
                     any(not flag.startswith("--") and "T" in flag[1:] for flag in flags))))
        candidates = _glob.glob(local) if any(c in source for c in "*?[") else [local]
        if not candidates or not all(os.path.exists(c) for c in candidates):
            hit.update(homes)
            continue
        hit.update(home for home in homes for c in candidates if _source_reaches(c, contents, prefix, home))
    return ("copy over", sorted(hit)) if hit else None


def _root_records_reason(call: "Call", analysis) -> "str | None":
    """Rule C for a command aimed at the project root (or above it) instead of at the directory that holds a record."""
    for command in analysis.commands:
        if command.verb not in ("git", "tar", "unzip", "7z", "7za", "7zr", "cp", "ln", "install", "scp", "rsync", "find") and _cmdscan.extract_parts(command.verb, command.argv) is None:
            continue
        reach = _root_command_reach(call, command)
        if reach:
            how, homes = reach
            return _ROOT_RECORDS_REASON.format(how=how, names=" and ".join(f"{home}/" for home in homes))
    return None


def _code_protected(texts, call: "Call") -> "str | None":
    seen: set = set()
    for text in texts:
        if _GUARD_STATE_NAME.search(text):
            return _GUARD_STATE_REASON
        for word in _WORD.findall(text):
            low = word.lower()
            if low in seen or not any(fragment in low for fragment in _PROTECTED_FRAGMENTS):
                continue
            seen.add(low)
            reason = _protected_reason(call.locate(word, call.starts))
            if reason:
                return reason
    return None


def _normal_text(text: str) -> str:
    return re.sub(r"/{2,}", "/", text.replace("\\", "/")).replace("/./", "/")


def rule_single_writer(call: "Call") -> "str | None":
    """Rule C: the core run files, project Taste state and the guard record have one writer each."""
    if call.writer:
        for target in call.edit_targets:
            reason = _protected_reason(target)
            if reason:
                return reason
        return None
    if not call.shell:
        return None
    if call.analysis.ok:
        analyses = list(_analyses(call.analysis))
        for analysis in analyses:
            for write, targets in call.shell_targets(analysis=analysis):
                for target in targets:
                    reason = _protected_reason(target, above=write.via in _RECORD_TREE_VIA)
                    if reason:
                        return reason
            code = analysis.code if any(not item.opaque for item in analysis.unnamed) else []
            reason = _code_protected(code, call) or _root_records_reason(call, analysis)
            if reason:
                return reason
        # The same reading as Rule B: a write the analyser cannot place in a command that spells a protected file.
        text = _unplaced_command(call, analyses)
        return _code_protected([text], call) if text is not None else None
    if not _textual_mutates(call.command):
        return None
    text = _normal_text(call.command)
    if _CORE_SAVE_TOKEN.search(text):
        return _CORE_SAVE_REASON
    if _GUARD_STATE_NAME.search(text):
        return _GUARD_STATE_REASON
    return None


# --- Rule F: the enforcer and its registration -------------------------------------------------------

# The hook scripts and the host files that register them are not edited while the guard is in use: an
# edit there switches every rule off for good and survives the session. "In use" is a pinned run or any
# recorded boundary, so developing the hooks in a plain checkout is never blocked; a maintainer working on
# them inside a run starts the host with SUPREMETEAM_HARNESS_DEV=1, which only the human who launches the
# host can set. The sanctioned registration writers (repair_registration.py, install_hooks.py) are
# scripts, so their arguments are never write targets and they keep working.
_REGISTRATION = (".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json", ".github/hooks.json")
_USER_REGISTRATION = ("~/.claude/settings.json", "~/.claude/settings.local.json", "~/.codex/hooks.json",
                      "~/.config/github-copilot/hooks.json", "~/.cursor/plugins/local/supremeteam-hooks/**",
                      "~/.config/opencode/plugins/supremeteam-hooks.js")
_HARNESS_REASON = (
    "Blocked by harness Action Realization layer: the hook scripts and the host files that register them are not "
    "edited while a run is pinned or a boundary is recorded, because an edit there would switch the guard off. "
    "Register through skills/harness/hooks/repair_registration.py, or edit them in a maintenance session "
    "(start the host with SUPREMETEAM_HARNESS_DEV=1). A setting in one of those files that is not a hook "
    "(a permission, an environment entry) is the owner's to change: say what and why."
)


def _harness_boundaries(root) -> list:
    """The hooks directory, the ``skills/scripts`` modules the hooks import (``_bootstrap.SCRIPT_FILES``: an edit to
    one runs inside the guard as surely as an edit to the guard, and a ``raise SystemExit(0)`` there switched it off
    with no fault counted) and the registration files."""
    import _bootstrap

    scripts = [str(HOOK_DIR.parents[1] / "scripts" / name).replace("\\", "/") for name in _bootstrap.SCRIPT_FILES]
    globs = [str(HOOK_DIR).replace("\\", "/") + "/**", *scripts, *_REGISTRATION,
             *(os.path.expanduser(p) for p in _USER_REGISTRATION)]
    return [_paths.Boundary(glob, root) for glob in globs]


def _run_active(call: "Call") -> bool:
    """True while an Admiral run is pinned in the project (``_saves.has_active_run``)."""
    import _bootstrap

    _bootstrap.ensure_paths()
    from _saves import has_active_run

    return has_active_run(call.root)


def _protection_engaged(call: "Call") -> bool:
    if any(call.guard.get(key) for key in ("frozen_globs", "blocked_globs", "read_only")):
        return True
    return _run_active(call)


def rule_harness_files(call: "Call") -> "str | None":
    """Rule F: hook scripts and host registration files are protected while the guard is in use."""
    if os.environ.get("SUPREMETEAM_HARNESS_DEV") == "1" or not (call.writer or call.shell):
        return None
    boundaries = _harness_boundaries(call.root)
    if call.writer:
        hit = any(boundary.matches(target) for target in call.edit_targets for boundary in boundaries)
    elif call.analysis.ok:
        # Read as Rule B reads a write: the commands a launcher runs, and a write the analyser cannot place
        # (`> "$OUT/.claude/settings.json"`) when the command spells a protected path.
        # Known member destinations are checked whenever protection is engaged;
        # an active run additionally refuses unknown extracts over the hooks.
        analyses = list(_analyses(call.analysis))
        hit = any(_shell_hit(call, boundaries, analysis=analysis, root_extracts=False)
                  or _root_archive_hit(call, boundaries, analysis)
                  or _mentioned(analysis.code if any(not item.opaque for item in analysis.unnamed) else [], call, boundaries)
                  for analysis in analyses)
        if not hit and _run_active(call):
            hit = any(_shell_hit(call, boundaries, analysis=analysis) for analysis in analyses)
        text = None if hit else _unplaced_command(call, analyses)
        if text is not None:
            hit = _mentioned([text], call, boundaries) is not None
    else:
        hit = _textual_mutates(call.command) and _mentioned([call.command], call, boundaries) is not None
    return _HARNESS_REASON if hit and _protection_engaged(call) else None


# --- Rule G: a write the analyser cannot place -------------------------------------------------------------

# A directory chain (``cd`` after ``cd``, or one long absolute ``cd``) is followed only so far
# (``_cmdscan.MAX_CWD``): past that the directory of every later write is unknown, so the write could land on
# anything a rule protects. The cost of following a relative chain is quadratic and nobody works that way, so the
# command is refused whole instead of being let through.
_UNPLACED_REASON = (
    "Blocked by harness Action Realization layer: the command changes directory through more than {limit} "
    "characters of path and then writes, so the guard cannot tell where the write lands. "
    "Use short paths from one directory, or split the command."
)


def rule_unplaced_write(call: "Call") -> "str | None":
    """Rule G: recognized mutations must have placed targets at a protected boundary."""
    if not call.shell:
        return None
    if call.analysis.lost_directory and call.analysis.writes:
        return _UNPLACED_REASON.format(limit=_cmdscan.MAX_CWD)
    # Rule D already applies the stricter read-only allow-list and its own reason.
    if call.guard.get("read_only"):
        return None
    analyses = list(_analyses(call.analysis))
    uncertain = any(write.unresolved for analysis in analyses for write in analysis.writes) or any(
        not entry.opaque for analysis in analyses for entry in analysis.unnamed) or (
        any(entry.opaque for analysis in analyses for entry in analysis.unnamed) and
        _cmdscan.program_text_writes(call.command))
    if not uncertain:
        return None
    boundaries = _frozen_boundaries(call)
    if not boundaries and not _homes_present(call.root) and not _run_active(call):
        return None
    # Keep the specific boundary/single-writer denial when the text names one.
    if _mentioned([call.command], call, boundaries) or _code_protected([call.command], call):
        return None
    if any(_root_records_reason(call, analysis) for analysis in analyses):
        return None
    harness_reason = rule_harness_files(call)
    if harness_reason:
        return harness_reason
    return ("Blocked by harness Action Realization layer: an unplaced write target could reach an active "
            "boundary or single-writer record. Runtime-built destinations and stdin/diff/program writes "
            "without proven targets are not allowed here. Use a path tool or name literal destinations; "
            "use save_run.py, taste_prefs.py or guard_state.py for their owned records.")


# --- Rule E: coverage destination advisory --------------------------------------------------------------
#
# Each pattern is a command that writes coverage data with no destination named,
# which is how `.coverage`/`.coverage.*`/`htmlcov/`/`.nyc_output/` accumulate at
# the project root. Parallel mode without a combine is the one that explodes: it
# writes one `.coverage.<host>.<pid>.<rand>` per process and nothing ever merges
# them. Advisory only — the action is allowed either way.
_COVERAGE_RUN = re.compile(r"(?:^|[\s;&|(])coverage\s+run(?![\w-])")
_PARALLEL_FLAG = re.compile(r"(?:^|\s)(?:-p|--parallel-mode)(?=\s|$)")
_COVERAGE_COMBINE = re.compile(r"(?:^|[\s;&|(])coverage\s+combine(?![\w-])")
_PYTEST_CALL = re.compile(r"(?:^|[\s;&|(])(?:py\.test|pytest)(?![\w-])|(?:^|\s)-m\s+pytest(?![\w-])")
_PYTEST_COV = re.compile(r"--cov(?![\w-])|--cov=")
_NYC_CALL = re.compile(r"(?:^|[\s;&|(])(?:npx\s+|pnpm\s+(?:dlx\s+)?|yarn\s+|bunx\s+)?(?:nyc|c8)(?=\s)")
_VITEST_CALL = re.compile(r"(?:^|[\s;&|(])(?:npx\s+|pnpm\s+(?:dlx\s+)?|yarn\s+|bunx\s+)?vitest(?![\w-])")


def _coverage_advisory(cmd: str) -> "str | None":
    """Return the residue risk this command carries, or None when it names a destination."""
    if not cmd:
        return None
    if _COVERAGE_RUN.search(cmd) and _PARALLEL_FLAG.search(cmd) and not _COVERAGE_COMBINE.search(cmd):
        return ("`coverage run` in parallel/per-process mode with no `coverage combine` in the same "
                "command: this writes one .coverage.<host>.<pid>.<rand> file per process and nothing "
                "merges them")
    if _PYTEST_CALL.search(cmd) and _PYTEST_COV.search(cmd) and "--cov-report" not in cmd:
        return "`pytest --cov` with no `--cov-report` destination: the data file lands at the project root"
    if _NYC_CALL.search(cmd) and "--report-dir" not in cmd and "--temp-dir" not in cmd:
        return "`nyc`/`c8` with no `--report-dir` or `--temp-dir`: coverage/ and .nyc_output/ land at the project root"
    if _VITEST_CALL.search(cmd) and "--coverage" in cmd and "reportsDirectory" not in cmd:
        return "`vitest --coverage` with no `--coverage.reportsDirectory`: the report lands at the project root"
    return None


_COVERAGE_ADVICE = (
    "Resolve the destination first with "
    "`python skills/scripts/output_paths.py --project-root . --run-id <run> --phase <phase> "
    "--kind coverage --name .coverage --mkdir`, which is "
    "skillset-saves/runs/<run>/<phase>/evidence/coverage/. Then point the tool at it: "
    "COVERAGE_FILE=<dest>/.coverage or --data-file, --cov-report=<fmt>:<dest>/..., "
    "--report-dir=<dest> --temp-dir=<dest>/tmp, --coverage.reportsDirectory=<dest>. "
    "Never use parallel/per-process mode unless the same command ends with `coverage combine` "
    "into that destination, and never loop coverage per test file. "
    "When the step ends, nothing named .coverage, .coverage.*, .coverage/, htmlcov/, or "
    ".nyc_output/ may remain at the project root; a coverage percentage is not evidence, the "
    "hashed data file or report in evidence/coverage/ is. "
    "post_tool_use.py relocates whatever is left anyway, so naming the destination up front "
    "is the cheaper path."
)


def rule_coverage(call: "Call") -> "str | None":
    """Rule E: advice, never a deny, for a coverage command that names no destination."""
    if not call.shell:
        return None
    risk = _coverage_advisory(call.command)
    return f"{risk}. {_COVERAGE_ADVICE}" if risk else None


# --- driver ---------------------------------------------------------------------------------------------

# Rules run in this order; the first reason wins. A rule that faults is counted and skipped, so one
# defect never turns off the rest. Rule G is a flag the analyser set, so it goes before the rules that
# would spend their time locating every write of a command it denies anyway.
RULES = [("A", rule_dangerous), ("G", rule_unplaced_write), ("B", rule_frozen), ("D", rule_read_only), ("C", rule_single_writer),
         ("F", rule_harness_files)]


def _deny(reason: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(out))
    _exit()


def _exit() -> None:
    """The guard's own exit after it has spoken. ``DECIDED`` lets the entry script tell it from a ``SystemExit`` some
    module on the import path raised, which is a fault and not a decision."""
    global DECIDED
    DECIDED = True
    sys.exit(0)


# Set by ``_exit`` only: the guard printed its decision or advice and ended the process itself.
DECIDED = False


def _advise(notes: list) -> None:
    """Emit advisory context, one tagged note per line, and allow the action.

    Deliberately not a deny. Running coverage is legitimate work; what is not
    legitimate is leaving its output at the project root, a destination mistake
    the caller can still correct before the command runs. A guard record that
    cannot be read is the owner's to repair, and the call is not the place to
    stop work the rules that still run have no objection to.
    """
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n".join(notes),
        }
    }
    print(json.dumps(out))
    _exit()


_UNREADABLE_NOTE = (
    "[harness:guard-state] .harness-state/guard-state.json exists but cannot be read, so no frozen, blocked or "
    "read-only boundary is enforced for this call. The destructive-command, single-writer and hook-file rules "
    "still are. Tell the owner: the record has to be repaired or recreated through guard_state.py "
    "(an agent write to it is denied) and each boundary recorded again. Until then treat every boundary as "
    "not enforced."
)


def _guard_state() -> dict:
    """The guard record, or an empty one when it cannot be read: Rule A needs none of it, and a record that
    cannot be read must not switch every rule off. The fault is counted."""
    try:
        return _state.load_guard_state(event="PreToolUse")
    except Exception as exc:
        _state.record_fault("PreToolUse", exc)
        return {}


def _project_root() -> Path:
    """The project root, or the working directory when it cannot be found (a rule that needs the root then faults alone)."""
    try:
        return _state.project_root()
    except Exception as exc:
        _state.record_fault("PreToolUse", exc)
        return Path(".")


def main() -> None:
    data = _state.read_hook_input("PreToolUse")
    _state.record_observation("PreToolUse", data)
    if _state.TAXONOMY_FAULT is not None:
        _state.record_fault("PreToolUse", _state.TAXONOMY_FAULT)
    run_heartbeat.refresh(data, "PreToolUse")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    if str(tool_name).lower() == "apply_patch" and isinstance(tool_input, str):
        tool_input = {"patch": tool_input}
    if not isinstance(tool_input, dict):
        return
    call = Call(tool_name, tool_input, _guard_state(), _project_root(), data.get("cwd"))
    for _label, rule in RULES:
        try:
            reason = rule(call)
        except BaseException as exc:
            # No rule exits: a `SystemExit` here came from a module a rule imported, so it is a fault like any other
            # and the remaining rules still run.
            _state.record_fault("PreToolUse", exc)
            continue
        if reason:
            _deny(reason)
    notes = [_UNREADABLE_NOTE] if call.guard.get("unreadable") and (call.shell or call.writer) else []
    try:
        advice = rule_coverage(call)
    except BaseException as exc:
        _state.record_fault("PreToolUse", exc)
        advice = None
    if advice:
        notes.append("[harness:coverage-residue] " + advice)
    if notes:
        _advise(notes)
    # No rule fired and nothing to say: stay silent and let the action proceed.


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Fail open: never let a harness fault block the host loop.
        _state.record_fault("PreToolUse", exc)
        sys.exit(0)
