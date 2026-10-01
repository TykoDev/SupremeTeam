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


def _git_push_label(argv) -> "str | None":
    sub, operands, _, flags = _cmdscan.git_parts(argv)
    if sub != "push":
        return None
    force = any(f == "--force" or f.startswith("--force-with-lease") for f in flags) or any(
        not f.startswith("--") and "f" in f[1:] for f in flags)
    deleting = "--delete" in flags or any(not f.startswith("--") and "d" in f[1:] for f in flags)
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


def _dangerous_label(call: "Call") -> "str | None":
    text = call.command
    label = _textual_dangerous(text)
    if label:
        return label
    for command in call.analysis.commands:
        label = _structural_label(command)
        if label:
            return label
    for write in call.analysis.writes:
        if _DEVICE.match(write.path):
            return "redirect over a raw block device"
    return None


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
_GLOB_LIMIT = 100
# Commands that remove, move or rewrite a whole tree: aimed at a directory above a boundary they reach into it.
_TREE_VIA = frozenset({"rm", "rmdir", "mv", "shred", "unlink", "remove-item", "move-item", "rename-item", "rename", "find",
                       "git checkout", "git restore", "git clean", "git rm", "git mv", "git apply", "git stash"})
_REMOVE_VIA = frozenset({"rm", "rmdir", "mv", "shred", "unlink", "remove-item", "move-item", "rename-item", "rename", "find"})


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

    @functools.cached_property
    def command(self) -> str:
        value = self.input.get("command")
        if isinstance(value, (list, tuple)):
            return " ".join(shlex.quote(str(part)) for part in value)
        return str(value or "")

    @functools.cached_property
    def analysis(self):
        return _cmdscan.analyse(self.command, powershell=self.powershell)

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

    def shell_targets(self, strict: bool = False) -> list:
        """``(write, [Target])`` for every write the analyser found.

        Deny rules consider every directory a ``cd`` may have left the shell in; the allow-list rule
        only the one it last set. A wildcard word is also expanded against the disk."""
        if strict not in self._shell_targets:
            found = []
            for write in self.analysis.writes:
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
            self._shell_targets[strict] = found
        return self._shell_targets[strict]


def _mentioned(texts, call: "Call", boundaries) -> "_paths.Boundary | None":
    """The first boundary a path word in ``texts`` lies on: how interpreter code and unparseable commands are searched."""
    pieces = [(boundary, boundary.fragments()) for boundary in boundaries]
    seen: set = set()
    for text in texts:
        for word in _WORD.findall(text):
            low = word.lower()
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


def _shell_hit(call: "Call", boundaries, tree_via=_TREE_VIA) -> "_paths.Boundary | None":
    """The first boundary a shell write lies on, or one a tree-wide command aimed above it reaches into."""
    for write, targets in call.shell_targets():
        above = write.via in tree_via
        for target in targets:
            for boundary in boundaries:
                if boundary.matches(target) or (above and boundary.covers(target)):
                    return boundary
    return None


# --- Rule B: frozen and blocked boundaries ---------------------------------------------------------

# A shell command counts as a *write* into a boundary only if the analyser sees it write there
# (a redirect, or a file-mutating command's target). A read-only command (cat/grep/ls/Get-Content)
# that merely *references* a frozen path is NOT a write and must pass: blocking it would violate the
# doctrine's Principles (inert on a competent action). When mutation cannot be determined the
# command is treated as non-mutating and proceeds (fail open per Principles).
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


def _frozen_boundaries(call: "Call") -> list:
    globs = list(call.guard.get("frozen_globs") or []) + list(call.guard.get("blocked_globs") or [])
    return [_paths.Boundary(glob, call.root) for glob in globs if isinstance(glob, str) and glob]


def rule_frozen(call: "Call") -> "str | None":
    """Rule B: a write into a frozen or blocked boundary is denied; a read never is."""
    boundaries = _frozen_boundaries(call)
    if not boundaries:
        return None
    if call.writer:
        for target in call.edit_targets:
            for boundary in boundaries:
                if boundary.matches(target):
                    return (f"Blocked by harness Action Realization layer: target is inside a frozen "
                            f"boundary ({_state.safe_text(boundary.glob)}). Lift the freeze via the unfreeze skill before editing here.")
        return None
    if not call.shell:
        return None
    if call.analysis.ok:
        hit = _shell_hit(call, boundaries) or _mentioned(call.analysis.code, call, boundaries)
    else:
        hit = _mentioned([call.command], call, boundaries) if _textual_mutates(call.command) else None
    if hit:
        return (f"Blocked by harness Action Realization layer: a mutating command targets a "
                f"frozen boundary ({_state.safe_text(hit.glob)}). Lift the freeze via the unfreeze skill before proceeding.")
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


def _unscoped_git(call: "Call") -> bool:
    """A git command that changes the repository or tree and names no path to judge (``git add -A``, ``git push``).

    An index-only command (``git restore --staged .``) names pathspecs but writes no file, so it is the repository
    it changes and counts here. ``git apply --check`` and its kin only report, and change nothing."""
    for command in call.analysis.commands:
        if command.verb != "git":
            continue
        sub, operands, _, flags = _cmdscan.git_parts(command.argv)
        if _cmdscan.git_dry_run(sub, flags):
            continue
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


def _installs_packages(call: "Call") -> bool:
    """A package manager command that installs, removes or updates packages (``npm install``, ``sudo apt-get install -y jq``)."""
    return any(_changes_packages(command) for command in call.analysis.commands)


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
    dry = _dry_vias(call.analysis)
    for write, targets in call.shell_targets(strict=True):
        if write.via in dry:
            continue
        if write.unresolved or any(not _paths.inside_allowed(target, allow, call.root, fold=fold) for target in targets):
            return _read_only_reason(records)
    if _unscoped_git(call) or _installs_packages(call):
        return _read_only_reason(records)
    return _read_only_reason(records) + _UNNAMED_REASON if call.analysis.unnamed else None


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
        for write, targets in call.shell_targets():
            for target in targets:
                reason = _protected_reason(target, above=write.via in _REMOVE_VIA)
                if reason:
                    return reason
        return _code_protected(call.analysis.code, call)
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
    globs = [str(HOOK_DIR).replace("\\", "/") + "/**", *_REGISTRATION, *(os.path.expanduser(p) for p in _USER_REGISTRATION)]
    return [_paths.Boundary(glob, root) for glob in globs]


def _protection_engaged(call: "Call") -> bool:
    if any(call.guard.get(key) for key in ("frozen_globs", "blocked_globs", "read_only")):
        return True
    import _bootstrap

    _bootstrap.ensure_paths()
    from _saves import has_active_run

    return has_active_run(call.root)


def rule_harness_files(call: "Call") -> "str | None":
    """Rule F: hook scripts and host registration files are protected while the guard is in use."""
    if os.environ.get("SUPREMETEAM_HARNESS_DEV") == "1" or not (call.writer or call.shell):
        return None
    boundaries = _harness_boundaries(call.root)
    if call.writer:
        hit = any(boundary.matches(target) for target in call.edit_targets for boundary in boundaries)
    elif call.analysis.ok:
        hit = bool(_shell_hit(call, boundaries) or _mentioned(call.analysis.code, call, boundaries))
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
    """Rule G: a command that writes after its directory chain (relative or absolute) outgrew the analysis is denied."""
    if not call.shell or not (call.analysis.lost_directory and call.analysis.writes):
        return None
    return _UNPLACED_REASON.format(limit=_cmdscan.MAX_CWD)


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
    sys.exit(0)


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
    sys.exit(0)


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
        except Exception as exc:
            _state.record_fault("PreToolUse", exc)
            continue
        if reason:
            _deny(reason)
    notes = [_UNREADABLE_NOTE] if call.guard.get("unreadable") and (call.shell or call.writer) else []
    try:
        advice = rule_coverage(call)
    except Exception as exc:
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
