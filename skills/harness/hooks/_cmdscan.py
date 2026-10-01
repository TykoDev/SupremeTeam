#!/usr/bin/env python3
"""Reduce a shell command to what it runs and what it writes, without running it.

The guard used to decide from raw command text with a verb list and a substring
match, so a redirect with no space, ``sed -E -i``, ``curl -o``, ``sh -c "..."``,
``$(...)`` and ``/bin/rm`` all passed. This module reads the command the way a shell
does and returns structure the guard rules apply to:

* ``commands``: every simple command that would run, after unwrapping ``sudo``,
  ``env``, ``nohup``, ``xargs``, ``eval``, ``sh -c``, ``find -exec``, ``$(...)``,
  backticks and heredocs fed to a shell, reduced to a lower-case verb (basename, no
  extension) and its argument words;
* ``writes``: every path a redirect or a file-mutating command would write, with the
  working directories a ``cd`` or ``git -C`` earlier in the line may have set;
* ``code``: the text of interpreter programs (``python -c``, ``node -e``, a heredoc to
  ``python -``, an ``awk`` program), which cannot be read for what they write, so the
  guard searches them for protected paths instead.

It is a text analysis, not a sandbox. It does not execute, resolve a path built at run
time, follow a script file, or know a tool it has no entry for; where it cannot tell it
says so (``unresolved``, ``glob``, ``ok``) and the guard falls back to the old textual
rules, which are never weaker. Cost is linear in the command and nesting stops at
``MAX_DEPTH``; text below that depth is handed back as ``code`` rather than dropped.

Stdlib only, no I/O, no import of another hook module.
"""
from __future__ import annotations

import base64
import binascii
import os
import posixpath
import re
from dataclasses import dataclass, field

MAX_DEPTH = 8
_MAX_NEST = 100
_MAX_BRACE = 64
# The longest working directory a chain of ``cd`` is followed to. Each directory is the one before it plus a
# segment, so a chain of N relative ``cd`` holds N strings of growing length and every write below them carries
# one: quadratic memory and, in the guard that resolves each, quadratic time. Past this length the directory is
# no longer followed and ``Analysis.lost_directory`` says so (the guard then refuses a write it cannot place).
MAX_CWD = 512


@dataclass(frozen=True)
class Command:
    verb: str
    argv: tuple
    cwds: tuple = ()


@dataclass(frozen=True)
class Write:
    path: str
    via: str
    cwds: tuple = ()
    glob: bool = False
    unresolved: bool = False


@dataclass
class Analysis:
    ok: bool = True
    # A ``cd`` led past ``MAX_CWD`` characters: the directory of the writes after it is not known.
    lost_directory: bool = False
    commands: list = field(default_factory=list)
    writes: list = field(default_factory=list)
    code: list = field(default_factory=list)


class _Unbalanced(Exception):
    """The text is not a complete command (an open quote or substitution)."""


class _Arg:
    __slots__ = ("text", "glob", "unresolved")

    def __init__(self, text: str, glob: bool = False, unresolved: bool = False) -> None:
        self.text, self.glob, self.unresolved = text, glob, unresolved


class _Word:
    """One shell word as parts: ``("l", text)``, ``("v", name, default)``, ``("s", inner)``, ``("a",)``."""

    __slots__ = ("parts", "glob", "plain")

    def __init__(self, parts: list, glob: bool, plain: bool) -> None:
        self.parts, self.glob, self.plain = parts, glob, plain


class _Redirect:
    __slots__ = ("op", "target", "body", "strip")

    def __init__(self, op: str) -> None:
        self.op = op
        self.target: "_Word | None" = None
        self.body: "str | None" = None
        self.strip = False


_BREAK_BASH = frozenset(" \t\r\n;&|()<>")
_BREAK_PS = frozenset(" \t\r\n;&|()>")
_RUN_BASH = re.compile(r"[^\s;&|()<>'\"\\$`*?\[{]+")
_RUN_PS = re.compile(r"[^\s;&|()>'\"`$*?\[]+")
_REDIR_BASH = re.compile(r"(?:&>>|&>)|\d*(?:>>|>\||>&|>|<<<|<<-|<<|<&|<>|<)")
_REDIR_PS = re.compile(r"(?:\d+|\*)?(?:>>|>&|>)")
_OP = re.compile(r"&&|\|\||\|&|;;&|;;|;&|\||&|;|\(|\)")
_DQ_BASH = re.compile(r'["\\$`]')
_DQ_PS = re.compile(r'["`$]')
_VAR_BASH = re.compile(r"[A-Za-z_]\w*|[0-9@*#?$!-]")
_VAR_PS = re.compile(r"(?:env:|script:|global:|local:)?[A-Za-z_]\w*|[?$^]")
_ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.S)
_COMMAND_START_WORDS = frozenset({"{", "}", "!", "then", "do", "else", "elif", "if", "while", "until", "time"})
_KEYWORDS = frozenset({"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for", "select", "case", "esac",
                       "{", "}", "!", "in"})
_NULL_TARGETS = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "/dev/zero", "nul", "$null", "con"})


# --- lexer ------------------------------------------------------------------

def _match_paren(text: str, i: int, nest: int = 0) -> int:
    """Index just past the ``)`` closing a ``(`` opened before ``i``; quotes and nested ``$(`` aware."""
    if nest > _MAX_NEST:
        raise _Unbalanced
    depth = 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == "'":
            j = text.find("'", i + 1)
            if j < 0:
                raise _Unbalanced
            i = j + 1
        elif c == '"':
            i = _skip_dquote(text, i + 1, nest + 1)
        elif c == "`":
            i = _match_backtick(text, i + 1)
        elif c == "(":
            depth += 1
            i += 1
        elif c == ")":
            depth -= 1
            i += 1
            if depth == 0:
                return i
        else:
            i += 1
    raise _Unbalanced


def _skip_dquote(text: str, i: int, nest: int) -> int:
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == '"':
            return i + 1
        elif c == "$" and text[i + 1:i + 2] == "(":
            i = _match_paren(text, i + 2, nest)
        elif c == "`":
            i = _match_backtick(text, i + 1)
        else:
            i += 1
    raise _Unbalanced


def _match_backtick(text: str, i: int) -> int:
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
        elif text[i] == "`":
            return i + 1
        else:
            i += 1
    raise _Unbalanced


def _match_brace(text: str, i: int) -> int:
    depth = 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise _Unbalanced


_ANSI = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "v": "\v",
         "\\": "\\", "'": "'", '"': '"', "?": "?"}


def _ansi_c(body: str) -> str:
    """The value of a ``$'...'`` string."""
    out: list = []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if c != "\\" or i + 1 >= n:
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1]
        hexa = re.match(r"[0-9A-Fa-f]{1,2}", body[i + 2:i + 4]) if nxt == "x" else None
        uni = re.match(r"[0-9A-Fa-f]{1,%d}" % (4 if nxt == "u" else 8), body[i + 2:i + 10]) if nxt in "uU" else None
        if nxt in _ANSI:
            out.append(_ANSI[nxt])
            i += 2
        elif hexa:
            out.append(chr(int(hexa.group(), 16)))
            i += 2 + len(hexa.group())
        elif nxt in "01234567":
            octal = re.match(r"[0-7]{1,3}", body[i + 1:i + 4]).group()
            out.append(chr(int(octal, 8)))
            i += 1 + len(octal)
        elif uni:
            out.append(chr(int(uni.group(), 16)) if int(uni.group(), 16) < 0x110000 else "?")
            i += 2 + len(uni.group())
        else:
            out.append(body[i:i + 2])
            i += 2
    return "".join(out)


def _flush(lit: list, parts: list) -> None:
    if lit:
        joined = "".join(lit)
        if joined:
            parts.append(("l", joined))
        lit.clear()


class _Lexer:
    """One pass over a command, producing words, redirects and operators."""

    def __init__(self, text: str, ps: bool) -> None:
        self.text, self.ps = text, ps
        self.n = len(text)
        self.breaks = _BREAK_PS if ps else _BREAK_BASH
        self.tokens: list = []
        self.pending: list = []

    def _arith_end(self, i: int) -> int:
        """Index past the ``))`` closing an arithmetic ``((`` or ``$((``, whose body is neither commands nor redirects."""
        depth = 2
        n = self.n
        while i < n:
            c = self.text[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        raise _Unbalanced

    def _dollar(self, i: int, in_quote: bool) -> tuple:
        """Parse an expansion at ``text[i] == '$'``; returns ``(part, next_index)``."""
        text = self.text
        nxt = text[i + 1:i + 2]
        if nxt == "(":
            if text[i + 2:i + 3] == "(":
                return ("a",), self._arith_end(i + 3)
            end = _match_paren(text, i + 2)
            return ("s", text[i + 2:end - 1]), end
        if nxt == "{":
            end = _match_brace(text, i + 2)
            body = text[i + 2:end - 1]
            name = re.match(r"[A-Za-z_]\w*|[0-9@*#?$!-]", body)
            if name and name.end() == len(body):
                return ("v", name.group(), None), end
            if name and body[name.end():name.end() + 2] == ":-":
                return ("v", name.group(), body[name.end() + 2:]), end
            return ("a",), end
        if nxt == "'" and not in_quote and not self.ps:
            j = i + 2
            while j < self.n and text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            if j >= self.n:
                raise _Unbalanced
            return ("l", _ansi_c(text[i + 2:j])), j + 1
        match = (_VAR_PS if self.ps else _VAR_BASH).match(text, i + 1)
        if match:
            return ("v", match.group(), None), match.end()
        return ("l", "$"), i + 1

    def _dquote(self, i: int, parts: list) -> int:
        """Parse the inside of a double-quoted string starting at ``i``; returns the index past the closing quote."""
        text, ps = self.text, self.ps
        special = _DQ_PS if ps else _DQ_BASH
        lit: list = []
        while True:
            m = special.search(text, i)
            if not m:
                raise _Unbalanced
            lit.append(text[i:m.start()])
            c = m.group()
            i = m.end()
            if c == '"':
                if ps and text[i:i + 1] == '"':
                    lit.append('"')
                    i += 1
                    continue
                break
            if c == "\\" or (ps and c == "`"):
                nxt = text[i:i + 1]
                if ps:
                    lit.append(nxt)
                    i += 1
                elif nxt in ('$', '"', "\\", "`"):
                    lit.append(nxt)
                    i += 1
                elif nxt == "\n":
                    i += 1
                else:
                    lit.append("\\")
            elif c == "`":
                end = _match_backtick(text, i)
                _flush(lit, parts)
                parts.append(("s", text[i:end - 1].replace("\\`", "`")))
                i = end
            else:
                part, i = self._dollar(i - 1, True)
                if part[0] == "l":
                    lit.append(part[1])
                else:
                    _flush(lit, parts)
                    parts.append(part)
        _flush(lit, parts)
        return i

    def _here_string(self, i: int) -> "tuple | None":
        """A PowerShell here-string ``@'...'@`` or ``@"..."@``: the literal text and the index past it."""
        text = self.text
        quote = text[i + 1:i + 2]
        if quote not in ("'", '"') or text[i + 2:i + 4].strip("\r\n") != "":
            return None
        end = text.find("\n" + quote + "@", i + 2)
        if end < 0:
            raise _Unbalanced
        return text[i + 2:end].strip("\r\n"), end + 3

    def _word(self, i: int) -> int:
        """Lex one word starting at ``i``, append it as a token, and return the index after it."""
        text, ps, n = self.text, self.ps, self.n
        run = _RUN_PS if ps else _RUN_BASH
        parts: list = []
        lit: list = []
        glob = False
        plain = True
        start = i
        while i < n:
            m = run.match(text, i)
            if m:
                lit.append(m.group())
                i = m.end()
                continue
            c = text[i]
            if c in self.breaks:
                break
            if c == "'":
                plain = False
                j = text.find("'", i + 1)
                if j < 0:
                    raise _Unbalanced
                chunk = text[i + 1:j]
                while ps and text[j + 1:j + 2] == "'":
                    k = text.find("'", j + 2)
                    if k < 0:
                        raise _Unbalanced
                    chunk += "'" + text[j + 2:k]
                    j = k
                lit.append(chunk)
                i = j + 1
            elif c == '"':
                plain = False
                _flush(lit, parts)
                i = self._dquote(i + 1, parts)
            elif c == "\\" and not ps:
                plain = False
                nxt = text[i + 1:i + 2]
                if nxt == "\n":
                    i += 2
                elif not nxt:
                    i += 1
                else:
                    lit.append(nxt)
                    i += 2
            elif c == "`" and ps:
                plain = False
                nxt = text[i + 1:i + 2]
                lit.append({"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(nxt, nxt))
                i += 2
            elif c == "`":
                plain = False
                end = _match_backtick(text, i + 1)
                _flush(lit, parts)
                parts.append(("s", text[i + 1:end - 1].replace("\\`", "`")))
                i = end
            elif c == "$":
                plain = False
                part, i = self._dollar(i, False)
                if part[0] == "l":
                    lit.append(part[1])
                else:
                    _flush(lit, parts)
                    parts.append(part)
            elif c in "*?[":
                glob = True
                lit.append(c)
                i += 1
            else:
                lit.append(c)
                i += 1
        if i == start:
            raise _Unbalanced
        _flush(lit, parts)
        if parts and parts[0][0] == "l" and parts[0][1].startswith("~") and plain:
            tail = parts[0][1][1:]
            if not tail or tail.startswith("/"):
                parts[0:1] = [("v", "HOME", None), ("l", tail)] if tail else [("v", "HOME", None)]
        self.tokens.append(("w", _Word(parts, glob, plain)))
        return i

    def _redirect(self, match: "re.Match", i: int) -> int:
        text = self.text
        raw = match.group()
        op = raw.lstrip("0123456789*")
        redirect = _Redirect(op)
        end = match.end()
        while end < self.n and text[end] in " \t":
            end += 1
        if op in ("<<", "<<-"):
            if end < self.n and text[end] not in "\n;&|()<>":
                word_end = self._delimiter_end(end)
                raw_delimiter = text[end:word_end]
                redirect.strip = op == "<<-"
                redirect.target = _Word([("l", re.sub(r"['\"\\]", "", raw_delimiter))], False,
                                        not any(ch in raw_delimiter for ch in "'\"\\"))
                self.pending.append(redirect)
                end = word_end
            self.tokens.append(("r", redirect))
            return end
        if end < self.n and text[end] not in "\n;&|()<>":
            before = len(self.tokens)
            end = self._word(end)
            redirect.target = self.tokens.pop()[1] if len(self.tokens) > before else None
        self.tokens.append(("r", redirect))
        return end

    def _delimiter_end(self, i: int) -> int:
        text, n = self.text, self.n
        quote = ""
        while i < n:
            c = text[i]
            if quote:
                if c == quote:
                    quote = ""
            elif c in "'\"":
                quote = c
            elif c == "\\":
                i += 1
            elif c in " \t\r\n;&|()<>":
                break
            i += 1
        return min(i, n)

    def _read_heredocs(self, i: int) -> int:
        text, n = self.text, self.n
        for redirect in self.pending:
            delimiter = redirect.target.parts[0][1] if redirect.target and redirect.target.parts else ""
            lines: list = []
            while i < n:
                end = text.find("\n", i)
                end = n if end < 0 else end
                line = text[i:end]
                i = min(end + 1, n)
                check = line.lstrip("\t") if redirect.strip else line
                if check.rstrip("\r") == delimiter:
                    break
                lines.append(line)
            redirect.body = "\n".join(lines)
        self.pending.clear()
        return i

    def run(self) -> list:
        text, n, ps = self.text, self.n, self.ps
        redirect_pattern = _REDIR_PS if ps else _REDIR_BASH
        i = 0
        command_start = True
        while i < n:
            c = text[i]
            if c in " \t\r":
                i += 1
                continue
            if c == "\n":
                self.tokens.append(("op", "\n"))
                i = self._read_heredocs(i + 1)
                command_start = True
                continue
            if c == "#":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if ps and text.startswith("<#", i):
                end = text.find("#>", i + 2)
                i = n if end < 0 else end + 2
                continue
            if not ps and c == "\\" and text[i + 1:i + 2] == "\n":
                i += 2
                continue
            if command_start and not ps and text.startswith("((", i):
                i = self._arith_end(i + 2)
                continue
            if command_start and not ps and text.startswith("[[", i) and text[i + 2:i + 3] in (" ", "\t"):
                end = text.find(" ]]", i + 2)
                if end >= 0:
                    i = end + 3
                    continue
            if c in "<>" and text[i + 1:i + 2] == "(":
                end = _match_paren(text, i + 2)
                self.tokens.append(("w", _Word([("s", text[i + 2:end - 1])], False, False)))
                i = end
                command_start = False
                continue
            here = self._here_string(i) if ps and c == "@" else None
            if here:
                self.tokens.append(("w", _Word([("l", here[0])], False, False)))
                i = here[1]
                command_start = False
                continue
            match = redirect_pattern.match(text, i)
            if match:
                i = self._redirect(match, i)
                continue
            match = _OP.match(text, i)
            if match:
                self.tokens.append(("op", match.group()))
                i = match.end()
                command_start = True
                continue
            i = self._word(i)
            word = self.tokens[-1][1]
            command_start = (len(word.parts) == 1 and word.parts[0][0] == "l" and word.parts[0][1] in _COMMAND_START_WORDS)
        self._read_heredocs(n)
        return self.tokens


# --- words to arguments ------------------------------------------------------

class _Ctx:
    def __init__(self, out: Analysis, ps: bool) -> None:
        self.out = out
        self.ps = ps
        self.vars: dict = {}
        self.cwds: list = []
        self.depth = 0
        self.text = ""
        self.seen: set = set()


def _home() -> str:
    return os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")


def _lookup(name: str, ctx: _Ctx) -> "str | None":
    key = name.lower() if ctx.ps else name
    if ctx.ps and key.startswith("env:"):
        key = key[4:]
    if key in ctx.vars:
        return ctx.vars[key]
    if key == "HOME" or (ctx.ps and key in ("home", "userprofile")):
        return _home()
    return None


def _split_top(body: str) -> list:
    items: list = []
    depth = 0
    last = 0
    for index, char in enumerate(body):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(body[last:index])
            last = index + 1
    items.append(body[last:])
    return items


def _brace(text: str, budget: list) -> list:
    """Brace expansion of ``{a,b}`` and ``{1..3}`` groups in ``text``; ``budget`` bounds the number of results."""
    pos = text.find("{")
    while pos >= 0:
        try:
            end = _match_brace(text, pos + 1)
        except _Unbalanced:
            break
        body = text[pos + 1:end - 1]
        items = _split_top(body)
        if len(items) == 1:
            span = re.fullmatch(r"(-?\d+)\.\.(-?\d+)", body)
            if not span or abs(int(span.group(2)) - int(span.group(1))) >= _MAX_BRACE:
                pos = text.find("{", pos + 1)
                continue
            low, high = int(span.group(1)), int(span.group(2))
            items = [str(v) for v in (range(low, high + 1) if low <= high else range(low, high - 1, -1))]
        expanded: list = []
        for item in items:
            if budget[0] <= 0:
                break
            expanded.extend(_brace(text[:pos] + item + text[end:], budget))
        return expanded or [text]
    budget[0] -= 1
    return [text]


def _expand(word: _Word, ctx: _Ctx) -> list:
    """The arguments one word stands for: variables resolved where known, substitutions analysed, braces expanded."""
    unresolved = False
    pieces: list = []
    for part in word.parts:
        kind = part[0]
        if kind == "l":
            pieces.append(part[1])
        elif kind == "v":
            value = _lookup(part[1], ctx)
            if value is None and part[2] is not None:
                value = part[2]
            if value is None:
                pieces.append("$" + part[1])
                unresolved = True
            else:
                pieces.append(value)
        elif kind == "s":
            _process(part[1], ctx, ctx.ps)
            pieces.append("$(...)")
            unresolved = True
        else:
            pieces.append("$((...))")
            unresolved = True
    text = "".join(pieces)
    if word.plain and "{" in text and ("," in text or ".." in text) and text.count("{") <= 16:
        return [_Arg(item, word.glob, unresolved) for item in _brace(text, [_MAX_BRACE])]
    return [_Arg(text, word.glob, unresolved)]


def _scan_substitutions(text: str, ctx: _Ctx) -> None:
    """Analyse the ``$(...)`` and backtick substitutions in text a shell would expand but not run (an unquoted heredoc)."""
    i, n = 0, len(text)
    try:
        while i < n:
            c = text[i]
            if c == "\\":
                i += 2
            elif c == "$" and text[i + 1:i + 2] == "(" and text[i + 2:i + 3] != "(":
                end = _match_paren(text, i + 2)
                _process(text[i + 2:end - 1], ctx, ctx.ps)
                i = end
            elif c == "`":
                end = _match_backtick(text, i + 1)
                _process(text[i + 1:end - 1], ctx, ctx.ps)
                i = end
            else:
                i += 1
    except _Unbalanced:
        ctx.out.ok = False


# --- per-verb write targets ------------------------------------------------------

_EXTENSIONS = (".exe", ".cmd", ".bat", ".com")


def _verb(text: str) -> str:
    name = re.split(r"[\\/]", text)[-1].lower()
    for extension in _EXTENSIONS:
        if name.endswith(extension):
            return name[: -len(extension)]
    return name


def _split(rest: list, with_arg=frozenset(), short=frozenset()) -> tuple:
    """Split arguments into flags, operands and the values of options that take one.

    ``with_arg`` names options whose value is the next word (or ``--name=value``);
    ``short`` is the single letters that take a value when they end a cluster
    (``-sSLo out``) or lead one with the value attached (``-oout``)."""
    flags: list = []
    operands: list = []
    values: dict = {}
    i, n = 0, len(rest)
    while i < n:
        arg = rest[i]
        text = arg.text
        if text == "--":
            operands.extend(rest[i + 1:])
            break
        if text.startswith("--"):
            name, equals, value = text.partition("=")
            flags.append(name)
            if equals:
                values[name] = _Arg(value, arg.glob, arg.unresolved)
            elif name in with_arg and i + 1 < n:
                values[name] = rest[i + 1]
                i += 1
        elif text.startswith("-") and len(text) > 1:
            flags.append(text)
            letters = text[1:]
            if text in with_arg and i + 1 < n:
                values[text] = rest[i + 1]
                i += 1
            elif letters[0] in short and len(letters) > 1 and ("-" + letters[0]) in with_arg:
                values["-" + letters[0]] = _Arg(letters[1:], arg.glob, arg.unresolved)
            elif letters[-1] in short and ("-" + letters[-1]) in with_arg and i + 1 < n:
                values["-" + letters[-1]] = rest[i + 1]
                i += 1
        else:
            operands.append(arg)
        i += 1
    return flags, operands, values


def _has_short(flags: list, letter: str) -> bool:
    return any(f.startswith("-") and not f.startswith("--") and letter in f[1:] for f in flags)


def _url_name(text: str) -> str:
    path = re.sub(r"[?#].*$", "", re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://[^/]*", "", text))
    return posixpath.basename(path.rstrip("/")) or "index.html"


def _t_all(with_arg=frozenset(), short=frozenset()):
    def handler(rest, ctx):
        return _split(rest, with_arg, short)[1]
    return handler


def _t_skip_first(rest, ctx):
    """chmod, chown, chgrp: the first operand is the mode or owner unless ``--reference`` names a file."""
    flags, operands, _ = _split(rest, frozenset({"--reference"}))
    return operands if any(f.startswith("--reference") for f in flags) else operands[1:]


def _t_last(with_arg=frozenset(), short=frozenset()):
    def handler(rest, ctx):
        flags, operands, values = _split(rest, with_arg | {"-t", "--target-directory"}, short | {"t"})
        for name in ("-t", "--target-directory"):
            if name in values:
                return [values[name]]
        return operands[-1:]
    return handler


def _t_install(rest, ctx):
    flags, operands, values = _split(rest, frozenset({"-m", "-o", "-g", "-t", "-S", "--mode", "--owner", "--group",
                                                      "--target-directory", "--suffix"}), frozenset("mogtS"))
    if "--directory" in flags or _has_short(flags, "d"):
        return operands
    for name in ("-t", "--target-directory"):
        if name in values:
            return [values[name]]
    return operands[-1:]


def _t_mv(rest, ctx):
    flags, operands, values = _split(rest, frozenset({"-t", "--target-directory", "-S", "--suffix"}), frozenset("tS"))
    return operands + [values[name] for name in ("-t", "--target-directory") if name in values]


def _t_dd(rest, ctx):
    return [_Arg(a.text[3:], a.glob, a.unresolved) for a in rest if a.text.startswith("of=")]


def _t_compress(rest, ctx):
    flags, operands, _ = _split(rest)
    if any(f in ("--stdout", "-t", "--test", "-l", "--list") for f in flags) or _has_short(flags, "c"):
        return []
    return operands


def _t_sort(rest, ctx):
    values = _split(rest, frozenset({"-o", "--output"}), frozenset("o"))[2]
    return [values[name] for name in ("-o", "--output") if name in values]


def _t_patch(rest, ctx):
    flags, operands, values = _split(rest, frozenset({"-o", "--output", "-i", "--input", "-p", "-d", "--directory", "-r",
                                                      "--reject-file", "-B", "-z", "-F", "-V"}), frozenset("oipdrBzFV"))
    return operands + [values[name] for name in ("-o", "--output") if name in values]


def _t_sed(rest, ctx):
    flags, operands, _ = _split(rest, frozenset({"-e", "-f", "--expression", "--file", "-l", "--line-length"}),
                                frozenset("efl"))
    in_place = any(f.startswith("--in-place") or (not f.startswith("--") and re.match(r"-[A-Za-z]*i", f)) for f in flags)
    if not in_place:
        return []
    has_script = any(f in ("-e", "-f", "--expression", "--file") or f.startswith(("--expression=", "--file="))
                     for f in flags)
    return operands if has_script else operands[1:]


def _perl_switches(rest: list) -> tuple:
    """Perl's switches: whether ``-i`` edits in place, the program text given with ``-e``, and the words after the switches."""
    in_place = False
    code: list = []
    i = 0
    while i < len(rest):
        text = rest[i].text
        if text == "--":
            i += 1
            break
        if not text.startswith("-") or len(text) == 1:
            break
        if not text.startswith(("-m", "-M")):
            if re.fullmatch(r"-[A-Za-z0-9]*i\S*", text):
                in_place = True
            if re.fullmatch(r"-[A-Za-z0-9]*[eE]", text) and i + 1 < len(rest):
                code.append(rest[i + 1].text)
                i += 1
        i += 1
    return in_place, code, rest[i:]


def _t_perl(rest, ctx):
    in_place, code, operands = _perl_switches(rest)
    if not in_place:
        return []
    return operands if code else operands[1:]


def _awk_args(rest: list) -> tuple:
    flags, operands, values = _split(rest, frozenset({"-F", "-v", "-f", "-i", "-e", "-E", "-W", "--source", "--file",
                                                      "--include", "--field-separator", "--assign"}), frozenset("FvfieEW"))
    has_file = any(f in ("-f", "--file") or f.startswith("--file=") for f in flags)
    return flags, operands, values, has_file


def _t_awk(rest, ctx):
    flags, operands, values, has_file = _awk_args(rest)
    include = values.get("-i") or values.get("--include")
    if include is None or include.text != "inplace":
        return []
    return operands if has_file else operands[1:]


_CURL_ARG = frozenset({"-o", "--output", "-D", "--dump-header", "-c", "--cookie-jar", "--trace", "--trace-ascii",
                       "--output-dir", "-X", "--request", "-H", "--header", "-d", "--data", "-u", "--user", "-A",
                       "--user-agent", "-e", "--referer", "-b", "--cookie", "-T", "--upload-file", "-w", "--write-out",
                       "-m", "--max-time", "--connect-timeout", "-x", "--proxy", "--retry", "-F", "--form", "-K",
                       "--config", "--cacert", "--cert", "--key"})


def _t_curl(rest, ctx):
    flags, operands, values = _split(rest, _CURL_ARG, frozenset("oDcXHduAebTwmxFK"))
    targets = [values[name] for name in ("-o", "--output", "-D", "--dump-header", "-c", "--cookie-jar", "--trace",
                                         "--trace-ascii") if name in values]
    if "--remote-name" in flags or _has_short(flags, "O"):
        targets += [_Arg(_url_name(a.text)) for a in operands]
    if "--output-dir" in values:
        targets.append(values["--output-dir"])
    return targets


_WGET_NAMED = ("-O", "--output-document", "-P", "--directory-prefix", "-o", "--output-file", "-a", "--append-output")


def _t_wget(rest, ctx):
    flags, operands, values = _split(
        rest, frozenset({*_WGET_NAMED, "-e", "--execute", "-t", "--tries", "-T", "--timeout", "-U", "--user-agent",
                         "--header", "--post-data", "-i", "--input-file", "-w", "--wait", "-Q", "--quota", "-l"}),
        frozenset("OPoaetTUiwQl"))
    named = [values[name] for name in _WGET_NAMED if name in values]
    if not any(name in values for name in ("-O", "--output-document", "-P", "--directory-prefix")):
        named += [_Arg(_url_name(a.text)) for a in operands if "://" in a.text]
    return named


def _t_tar(rest, ctx):
    words = list(rest)
    cluster = ""
    if words and not words[0].text.startswith("-") and re.fullmatch(r"[A-Za-z]+", words[0].text):
        cluster = words.pop(0).text
    flags, operands, values = _split(words, frozenset({"-f", "--file", "-C", "--directory", "-T", "--files-from", "-X",
                                                       "--exclude-from", "-I", "--use-compress-program"}), frozenset("fCTXI"))
    archive = values.get("-f") or values.get("--file")
    directory = values.get("-C") or values.get("--directory")
    queue = list(operands)
    for letter in cluster:
        if letter == "f" and queue:
            archive = queue.pop(0)
        elif letter == "C" and queue:
            directory = queue.pop(0)
    letters = cluster + "".join(f[1:] for f in flags if not f.startswith("--"))
    if "x" in letters or "--extract" in flags or "--get" in flags:
        return [directory or _Arg(".")]
    if (any(c in letters for c in "cru") or any(f in flags for f in ("--create", "--append", "--update"))) and archive:
        return [archive]
    return []


def _t_unzip(rest, ctx):
    flags, operands, values = _split(rest, frozenset({"-d", "-x", "-P"}), frozenset("dxP"))
    if any(f in ("-l", "-t", "-v", "-p", "-Z", "-z") for f in flags):
        return []
    return [values["-d"]] if "-d" in values else [_Arg(".")]


def _t_zip(rest, ctx):
    flags, operands, _ = _split(rest, frozenset({"-b", "-n", "-t", "-tt", "-P", "-O", "-x", "-i", "-d", "-fz"}),
                                frozenset("bntPOxi"))
    return operands[:1]


def _t_7z(rest, ctx):
    flags, operands, _ = _split(rest)
    if not operands:
        return []
    if operands[0].text in ("a", "u", "d", "rn"):
        return operands[1:2]
    if operands[0].text in ("x", "e"):
        return [_Arg(f[2:]) for f in flags if f.startswith("-o") and len(f) > 2] or [_Arg(".")]
    return []


def _t_gpg(rest, ctx):
    values = _split(rest, frozenset({"-o", "--output"}), frozenset("o"))[2]
    return [values[name] for name in ("-o", "--output") if name in values]


_GIT_PATHSPEC = frozenset({"add", "checkout", "restore", "reset", "rm", "mv", "clean", "apply", "stash", "commit"})
_GIT_GLOBAL_ARG = frozenset({"-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"})
_GIT_COMMIT_ARG = frozenset({"-m", "-F", "-C", "-c", "--message", "--file", "--author", "--date", "--reuse-message",
                             "--reedit-message", "--fixup", "--squash", "--cleanup", "-S", "--gpg-sign"})


def git_parts(argv) -> tuple:
    """``(subcommand, operands, directories, flags)`` of a git command line: global options skipped, ``-C`` kept."""
    args = [a if isinstance(a, _Arg) else _Arg(a) for a in argv]
    directories: list = []
    i = 0
    while i < len(args):
        text = args[i].text
        if not text.startswith("-"):
            break
        if text == "-C" and i + 1 < len(args):
            directories.append(args[i + 1].text)
            i += 2
        elif text in _GIT_GLOBAL_ARG and i + 1 < len(args):
            i += 2
        else:
            i += 1
    if i >= len(args):
        return "", [], directories, []
    sub = args[i].text
    flags, operands, _ = _split(args[i + 1:], _GIT_COMMIT_ARG if sub == "commit" else frozenset())
    return sub, operands, directories, flags


def _t_git(rest, ctx):
    sub, operands, directories, _ = git_parts(rest)
    if sub not in _GIT_PATHSPEC:
        return []
    return [(operand, tuple(directories), "git " + sub) for operand in operands]


def _t_find(rest, ctx):
    i = 0
    while i < len(rest) and (rest[i].text in ("-H", "-L", "-P") or rest[i].text.startswith("-O")):
        i += 1
    starts: list = []
    while i < len(rest) and not rest[i].text.startswith(("-", "(", "!")):
        starts.append(rest[i])
        i += 1
    starts = starts or [_Arg(".")]
    expression = rest[i:]
    targets: list = []
    delete = False
    j = 0
    while j < len(expression):
        text = expression[j].text
        if text == "-delete":
            delete = True
        elif text in ("-fprint", "-fprint0", "-fprintf", "-fls") and j + 1 < len(expression):
            targets.append(expression[j + 1])
            j += 1
        elif text in ("-exec", "-execdir", "-ok", "-okdir"):
            k = j + 1
            nested: list = []
            while k < len(expression) and expression[k].text not in (";", "+"):
                nested.append(expression[k])
                k += 1
            for start in starts:
                replaced = [_Arg(a.text.replace("{}", start.text), a.glob or start.glob, a.unresolved or start.unresolved)
                            for a in nested]
                _exec(replaced, ctx, None, None)
            j = k
        j += 1
    return (starts if delete else []) + targets


_ALL = _t_all()
_TARGETS = {
    "rm": _ALL, "unlink": _ALL, "rmdir": _ALL, "tee": _ALL, "sponge": _ALL, "rename": _ALL, "mknod": _ALL,
    "shred": _t_all(frozenset({"-n", "-s", "--iterations", "--size"}), frozenset("ns")),
    "touch": _t_all(frozenset({"-d", "-r", "-t", "--date", "--reference"}), frozenset("drt")),
    "mkdir": _t_all(frozenset({"-m", "--mode"}), frozenset("m")),
    "mkfifo": _t_all(frozenset({"-m", "--mode"}), frozenset("m")),
    "truncate": _t_all(frozenset({"-s", "-r", "--size", "--reference"}), frozenset("sr")),
    "mv": _t_mv, "chmod": _t_skip_first, "chown": _t_skip_first, "chgrp": _t_skip_first,
    "cp": _t_last(), "ln": _t_last(), "install": _t_install,
    "rsync": _t_last(frozenset({"-e", "--rsh", "--exclude", "--include", "--exclude-from", "--include-from", "-f",
                                "--filter", "--port", "--bwlimit", "--rsync-path", "--log-file", "-B", "-T"}),
                     frozenset("efBT")),
    "scp": _t_last(frozenset({"-i", "-P", "-F", "-o", "-l", "-S", "-c", "-J"}), frozenset("iPFolScJ")),
    "dd": _t_dd, "gzip": _t_compress, "gunzip": _t_compress, "bzip2": _t_compress, "bunzip2": _t_compress,
    "xz": _t_compress, "unxz": _t_compress, "zstd": _t_compress, "lzma": _t_compress,
    "sort": _t_sort, "patch": _t_patch, "sed": _t_sed, "perl": _t_perl, "awk": _t_awk, "gawk": _t_awk,
    "curl": _t_curl, "wget": _t_wget, "tar": _t_tar, "unzip": _t_unzip, "zip": _t_zip, "7z": _t_7z, "7za": _t_7z,
    "7zr": _t_7z, "gpg": _t_gpg, "git": _t_git, "find": _t_find,
}


# --- PowerShell and cmd.exe -----------------------------------------------------------

_CMD_SWITCH = re.compile(r"^/[A-Za-z?](?::\S*)?$")
_CMD_VERBS = frozenset({"rename", "xcopy", "robocopy"})
_PS_ALIASES = {
    "sc": "set-content", "ac": "add-content", "clc": "clear-content", "ni": "new-item", "ri": "remove-item",
    "rm": "remove-item", "rd": "remove-item", "rmdir": "remove-item", "del": "remove-item", "erase": "remove-item",
    "rni": "rename-item", "ren": "rename-item", "mi": "move-item", "mv": "move-item", "move": "move-item",
    "ci": "copy-item", "cpi": "copy-item", "cp": "copy-item", "copy": "copy-item", "md": "new-item",
    "mkdir": "new-item", "sp": "set-itemproperty", "epcsv": "export-csv", "tee": "tee-object",
    "iwr": "invoke-webrequest", "irm": "invoke-restmethod", "curl": "invoke-webrequest", "wget": "invoke-webrequest",
}
# cmdlet: (parameters that take a value, parameters that name a written path, rule for positional words)
_PS_SPECS = {
    "set-content": (("path", "literalpath", "value", "include", "exclude", "filter", "encoding", "stream"),
                    ("path", "literalpath"), "first"),
    "add-content": (("path", "literalpath", "value", "include", "exclude", "filter", "encoding", "stream"),
                    ("path", "literalpath"), "first"),
    "clear-content": (("path", "literalpath", "include", "exclude", "filter", "stream"), ("path", "literalpath"), "first"),
    "out-file": (("filepath", "literalpath", "inputobject", "encoding", "width"), ("filepath", "literalpath"), "first"),
    "new-item": (("path", "name", "itemtype", "value"), ("path", "name"), "first"),
    "remove-item": (("path", "literalpath", "include", "exclude", "filter", "stream"), ("path", "literalpath"), "all"),
    "rename-item": (("path", "literalpath", "newname"), ("path", "literalpath"), "first"),
    "move-item": (("path", "literalpath", "destination", "filter", "include", "exclude"),
                  ("path", "literalpath", "destination"), "pair"),
    "copy-item": (("path", "literalpath", "destination", "filter", "include", "exclude"), ("destination",), "second"),
    "set-itemproperty": (("path", "literalpath", "name", "value", "type"), ("path", "literalpath"), "first"),
    "tee-object": (("inputobject", "filepath", "literalpath", "variable"), ("filepath", "literalpath"), "first"),
    "export-csv": (("path", "literalpath", "inputobject", "delimiter", "encoding"), ("path", "literalpath"), "first"),
    "export-clixml": (("path", "literalpath", "inputobject", "depth", "encoding"), ("path", "literalpath"), "first"),
    "invoke-webrequest": (("uri", "outfile", "method", "body", "headers", "contenttype", "useragent"), ("outfile",), "none"),
    "invoke-restmethod": (("uri", "outfile", "method", "body", "headers", "contenttype", "useragent"), ("outfile",), "none"),
    "expand-archive": (("path", "literalpath", "destinationpath"), ("destinationpath",), "none"),
    "compress-archive": (("path", "literalpath", "destinationpath", "compressionlevel"), ("destinationpath",), "none"),
    "start-bitstransfer": (("source", "destination"), ("destination",), "none"),
    "set-acl": (("path", "literalpath", "aclobject"), ("path", "literalpath"), "first"),
}


def _ps_param(text: str, names: tuple) -> "tuple | None":
    """``(canonical name, inline value)`` when ``text`` is a parameter of the cmdlet (an exact or unique-prefix match)."""
    if not text.startswith("-") or len(text) < 2 or not text[1:2].isalpha():
        return None
    name, colon, value = text[1:].partition(":")
    lowered = name.lower()
    matched = [candidate for candidate in names if candidate == lowered] or [c for c in names if c.startswith(lowered)]
    return (matched[0], value if colon else None) if matched else None


def _t_powershell(verb: str, rest: list, ctx: _Ctx) -> list:
    value_params, path_params, rule = _PS_SPECS[verb]
    named: dict = {}
    positional: list = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        text = arg.text
        if _CMD_SWITCH.match(text):
            i += 1
            continue
        param = _ps_param(text, value_params)
        if param:
            name, inline = param
            if inline is not None:
                named.setdefault(name, []).append(_Arg(inline, arg.glob, arg.unresolved))
            elif i + 1 < len(rest) and not (rest[i + 1].text.startswith("-") and rest[i + 1].text[1:2].isalpha()):
                values = [rest[i + 1]]
                i += 1
                while values[-1].text.endswith(",") and i + 1 < len(rest):
                    values.append(rest[i + 1])
                    i += 1
                named.setdefault(name, []).extend(values)
        elif text.startswith("-") and text[1:2].isalpha():
            pass
        else:
            positional.append(arg)
        i += 1
    named_paths = [value for name in path_params if name in named for value in named[name]]
    sources = [value for name in ("path", "literalpath") if name in named for value in named[name]]
    if rule == "first":
        items = named_paths or positional[:1]
    elif rule == "all":
        items = named_paths or positional
    elif rule == "pair":
        items = (sources or positional[:1]) + (named.get("destination") or positional[1:2])
    elif rule == "second":
        items = named.get("destination") or (positional[:1] if sources else positional[1:2])
    else:
        items = named_paths
    expanded: list = []
    for item in items:
        pieces = [piece for piece in item.text.split(",") if piece.strip()] if "," in item.text else [item.text]
        expanded.extend(_Arg(piece.strip(), item.glob, item.unresolved) for piece in pieces)
    return expanded


def _t_cmd(verb: str, rest: list, ctx: _Ctx) -> list:
    operands = [a for a in rest if not _CMD_SWITCH.match(a.text)]
    return operands[-1:] if verb in ("xcopy", "robocopy") else operands


# --- launchers, shells and interpreters ---------------------------------------------------

_WRAPPERS = {
    # verb: (options that take a value, positional words to skip after the options, environment assignments allowed)
    "env": (frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}), 0, True),
    "command": (frozenset(), 0, False), "builtin": (frozenset(), 0, False),
    "exec": (frozenset({"-a"}), 0, False), "nohup": (frozenset(), 0, False),
    "sudo": (frozenset({"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-r", "-t", "-U", "--user", "--group", "--host",
                        "--prompt", "--close-from", "--chdir", "--chroot", "--role", "--type", "--other-user"}), 0, True),
    "doas": (frozenset({"-u", "-C"}), 0, False),
    "nice": (frozenset({"-n", "--adjustment"}), 0, False),
    "ionice": (frozenset({"-c", "-n", "-p", "-P", "-u", "--class", "--classdata"}), 0, False),
    "time": (frozenset({"-f", "--format", "-o", "--output"}), 0, False),
    "timeout": (frozenset({"-s", "--signal", "-k", "--kill-after"}), 1, False),
    "stdbuf": (frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}), 0, False),
    "setsid": (frozenset(), 0, False), "caffeinate": (frozenset({"-t", "-w"}), 0, False),
    "unbuffer": (frozenset(), 0, False), "chronic": (frozenset(), 0, False),
    "watch": (frozenset({"-n", "--interval"}), 0, False), "busybox": (frozenset(), 0, False),
    "taskset": (frozenset({"-c", "-p"}), 1, False), "flock": (frozenset({"-w", "-E", "--timeout"}), 1, False),
}
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ksh", "ash", "mksh", "csh", "tcsh", "fish"})
_POWERSHELLS = frozenset({"powershell", "pwsh"})
_PS_ARG_FLAGS = frozenset({"-executionpolicy", "-ep", "-windowstyle", "-w", "-version", "-v", "-outputformat", "-of",
                           "-inputformat", "-if", "-workingdirectory", "-wd", "-configurationname", "-custompipename",
                           "-settingsfile"})
_PYTHONS = re.compile(r"^(python[0-9.]*|pythonw|pypy[0-9]*|py)$")
_EVAL_FLAGS = {"node": ("-e", "--eval", "-p", "--print"), "nodejs": ("-e", "--eval", "-p", "--print"),
               "bun": ("-e", "--eval"), "ruby": ("-e",), "php": ("-r",), "lua": ("-e",), "luajit": ("-e",),
               "rscript": ("-e",), "osascript": ("-e",)}
_DOTNET_FILE = re.compile(r"\[(?:System\.)?IO\.(?:File|Directory)\]::\s*(?!Exists|Read|Get|Enumerate|OpenRead)\w+", re.I)
_CD = frozenset({"cd", "chdir", "pushd", "set-location", "sl", "push-location"})
_DECLARE = frozenset({"export", "declare", "local", "readonly", "typeset"})
_XARGS_ARG = frozenset({"-n", "-P", "-L", "-s", "-d", "-E", "-a", "--max-args", "--max-procs", "--max-lines",
                        "--max-chars", "--delimiter", "--eof", "--arg-file"})


def _skip_options(rest: list, with_arg: frozenset, positional: int, assignments: bool) -> list:
    i = 0
    while i < len(rest):
        text = rest[i].text
        if text == "--":
            i += 1
            break
        if assignments and _ASSIGN.match(text):
            i += 1
        elif text.startswith("-") and len(text) > 1:
            i += 2 if text in with_arg else 1
        else:
            break
    return rest[i + positional:]


def _shell(rest: list, ctx: _Ctx, body: "str | None") -> "list | None":
    """sh and friends: analyse ``-c`` text or a script on standard input; a script-file run comes back as a plain command."""
    i = 0
    while i < len(rest):
        text = rest[i].text
        if text.startswith("-") and not text.startswith("--") and "c" in text[1:]:
            if i + 1 < len(rest):
                _process(rest[i + 1].text, ctx, False)
            return None
        if text in ("-o", "+o", "--rcfile", "--init-file") and i + 1 < len(rest):
            i += 2
        elif text.startswith(("-", "+")):
            i += 1
        else:
            return rest[i:]
    if body is not None:
        _process(body, ctx, False)
    return None


def _powershell(rest: list, ctx: _Ctx, body: "str | None") -> "list | None":
    i = 0
    while i < len(rest):
        text = rest[i].text
        low = text.lower()
        if len(low) >= 2 and "-command".startswith(low) or low == "-cmd":
            tail = " ".join(a.text for a in rest[i + 1:])
            _process(body if tail.strip() == "-" and body is not None else tail, ctx, True)
            return None
        if low in ("-encodedcommand", "-ec", "-e", "-enc") and i + 1 < len(rest):
            try:
                _process(base64.b64decode(rest[i + 1].text).decode("utf-16-le"), ctx, True)
            except (binascii.Error, UnicodeDecodeError, ValueError):
                ctx.out.code.append(rest[i + 1].text)
            return None
        if low in ("-file", "-f"):
            return rest[i + 1:] or None
        if low in _PS_ARG_FLAGS and i + 1 < len(rest):
            i += 2
        elif text.startswith("-"):
            i += 1
        else:
            return rest[i:]
    if body is not None:
        _process(body, ctx, True)
    return None


def _cmd(rest: list, ctx: _Ctx) -> None:
    for index, arg in enumerate(rest):
        if arg.text.lower() in ("/c", "/k", "/r"):
            _process(" ".join(a.text for a in rest[index + 1:]), ctx, True)
            return


def _xargs(rest: list, upstream: "list | None") -> list:
    """The commands xargs runs: its command with the operands a literal upstream stage supplies appended, or one per operand for ``-I``."""
    i = 0
    replace = None
    while i < len(rest):
        text = rest[i].text
        if text in ("-I", "-i", "--replace") and i + 1 < len(rest):
            replace = rest[i + 1].text
            i += 2
        elif text.startswith("-I") and len(text) > 2:
            replace = text[2:]
            i += 1
        elif text in _XARGS_ARG and i + 1 < len(rest):
            i += 2
        elif text.startswith("-") and len(text) > 1:
            i += 1
        else:
            break
    nested = list(rest[i:])
    words = [_Arg(word) for word in (upstream or [])]
    if not words:
        return [nested]
    if replace:
        return [[_Arg(a.text.replace(replace, word.text), a.glob, a.unresolved) for a in nested] for word in words]
    return [nested + words]


def _inline_code(verb: str, rest: list, body: "str | None") -> list:
    """The program text an interpreter was handed on its command line or its standard input."""
    if _PYTHONS.match(verb):
        i = 0
        while i < len(rest):
            text = rest[i].text
            if text == "-":
                break
            single = text.startswith("-") and not text.startswith("--")
            if single and re.fullmatch(r"-[A-Za-z]*c", text) and i + 1 < len(rest):
                return [rest[i + 1].text]
            if single and text.startswith("-c") and len(text) > 2:
                return [text[2:]]
            if single and re.fullmatch(r"-[A-Za-z]*m", text):
                return []
            if text in ("-W", "-X", "-Q", "-Y") and i + 1 < len(rest):
                i += 2
            elif text.startswith("-"):
                i += 1
            else:
                return []
        return [body] if body is not None else []
    if verb == "perl":
        _, code, operands = _perl_switches(rest)
        return code or ([body] if body is not None and not operands else [])
    if verb in _EVAL_FLAGS:
        flags = _EVAL_FLAGS[verb]
        code: list = []
        i = 0
        while i < len(rest):
            text = rest[i].text
            if text in flags and i + 1 < len(rest):
                code.append(rest[i + 1].text)
                i += 2
                continue
            code.extend(text[len(flag) + 1:] for flag in flags if flag.startswith("--") and text.startswith(flag + "="))
            if not text.startswith("-") or len(text) == 1:
                break
            i += 1
        if code:
            return code
        return [body] if body is not None and not [a for a in rest if not a.text.startswith("-")] else []
    if verb in ("awk", "gawk", "mawk", "nawk"):
        _, operands, _, has_file = _awk_args(rest)
        return [] if has_file or not operands else [operands[0].text]
    return []


# --- driver ------------------------------------------------------------------------

def _is_null(target: _Arg) -> bool:
    return target.text.lower() in _NULL_TARGETS


def _note_write(ctx: _Ctx, path: str, via: str, cwds: tuple, glob: bool, unresolved: bool) -> None:
    key = (path, via, cwds, glob, unresolved)
    if key not in ctx.seen:
        ctx.seen.add(key)
        ctx.out.writes.append(Write(path, via, cwds, glob, unresolved))


def _recent(ctx: _Ctx) -> tuple:
    """The directories a ``cd`` may have left the shell in; the latest ones, which are the ones that can be current.

    Each appears once, in the order of its last visit, so the last one is always where the shell is."""
    recent: list = []
    for cwd in reversed(ctx.cwds[-3:]):
        if cwd not in recent:
            recent.append(cwd)
    return tuple(reversed(recent))


def _record_redirects(redirects: list, ctx: _Ctx) -> "str | None":
    """Record the writes redirects make; returns the text fed to the command on standard input, if any."""
    body = None
    for redirect in redirects:
        op = redirect.op
        if op in ("<<", "<<-"):
            if redirect.body is not None:
                body = redirect.body
                if redirect.target is not None and redirect.target.plain:
                    _scan_substitutions(redirect.body, ctx)
            continue
        if redirect.target is None:
            continue
        arguments = _expand(redirect.target, ctx)
        if op == "<<<":
            body = " ".join(a.text for a in arguments)
            continue
        if op in ("<", "<&"):
            continue
        if op == ">&" and arguments and re.fullmatch(r"\d+|-", arguments[0].text):
            continue
        for argument in arguments:
            if not _is_null(argument):
                _note_write(ctx, argument.text, op, _recent(ctx), argument.glob, argument.unresolved)
    return body


def _is_assignment(word: _Word) -> bool:
    return bool(word.parts) and word.parts[0][0] == "l" and re.match(r"[A-Za-z_]\w*=", word.parts[0][1]) is not None


def _assign(word: _Word, ctx: _Ctx) -> None:
    argument = _expand(word, ctx)[0]
    name, _, value = argument.text.partition("=")
    if not argument.unresolved:
        ctx.vars[name.lower() if ctx.ps else name] = value


def _ps_assignment(words: list, ctx: _Ctx) -> bool:
    """``$name = value`` or ``$name=value`` in PowerShell: remember the value when it is known."""
    first = words[0]
    if not first.parts or first.parts[0][0] != "v":
        return False
    if len(first.parts) == 1 and len(words) >= 3 and words[1].parts == [("l", "=")]:
        value_word = words[2]
    elif len(first.parts) >= 2 and first.parts[1][0] == "l" and first.parts[1][1].startswith("="):
        value_word = _Word([("l", first.parts[1][1][1:]), *first.parts[2:]], False, False)
    else:
        return False
    value = _expand(value_word, ctx)
    if value and not value[0].unresolved:
        ctx.vars[first.parts[0][1].lower()] = value[0].text
    return True


def _strip_keywords(args: list) -> list:
    while args and not args[0].unresolved:
        text = args[0].text
        if text in ("for", "select", "case"):
            return []
        if text == "function":
            args = args[2:]
        elif text in _KEYWORDS:
            args = args[1:]
        else:
            break
    return args


def _literal_words(verb: str, rest: list) -> "list | None":
    """The words a literal ``echo`` or ``printf`` prints, which an ``xargs`` downstream receives."""
    if any(a.unresolved for a in rest):
        return None
    words = [a.text for a in rest if not (verb == "echo" and re.fullmatch(r"-[neE]+", a.text))]
    if verb == "printf" and words:
        words[0] = re.sub(r"\\[nt0]", " ", words[0])
    return [piece for text in words for piece in text.split()]


def _run_stage(tokens: list, ctx: _Ctx, upstream: "list | None") -> "list | None":
    words = [value for kind, value in tokens if kind == "w"]
    redirects = [value for kind, value in tokens if kind == "r"]
    body = _record_redirects(redirects, ctx)
    if not words:
        return None
    if ctx.ps and _ps_assignment(words, ctx):
        return None
    index = 0
    while index < len(words) and not ctx.ps and _is_assignment(words[index]):
        index += 1
    if index == len(words):
        for word in words:
            _assign(word, ctx)
        return None
    args: list = []
    for word in words[index:]:
        args.extend(_expand(word, ctx))
    args = _strip_keywords(args)
    if not args:
        return None
    _exec(args, ctx, body, upstream)
    verb = _verb(args[0].text)
    return _literal_words(verb, args[1:]) if verb in ("echo", "printf", "write-output", "write-host") else None


def _exec(args: list, ctx: _Ctx, body: "str | None", upstream: "list | None") -> None:
    """Unwrap launchers until the command that actually runs, then record it, its writes and its code."""
    for _ in range(64):
        if not args:
            return
        first = args[0]
        verb = _verb(first.text)
        if not verb or (first.unresolved and first.text.startswith("$")):
            return
        rest = args[1:]
        if verb in ("eval", "invoke-expression", "iex"):
            _process(" ".join(a.text for a in rest), ctx, ctx.ps or verb != "eval", scoped=False)
            return
        if verb in _SHELLS or verb in _POWERSHELLS:
            plain = _shell(rest, ctx, body) if verb in _SHELLS else _powershell(rest, ctx, body)
            if plain is not None:
                _finish(args, ctx, body)
            return
        if verb == "cmd":
            _cmd(rest, ctx)
            return
        if verb == "xargs":
            for command in _xargs(rest, upstream):
                _exec(command, ctx, None, None)
            return
        wrapper = _WRAPPERS.get(verb)
        if wrapper is None or (verb == "command" and rest and rest[0].text in ("-v", "-V")):
            break
        args = _skip_options(rest, *wrapper)
    else:
        return
    _finish(args, ctx, body)


def _change_directory(rest: list, ctx: _Ctx) -> None:
    operands = [a for a in rest if not a.text.startswith("-") or a.text == "-"]
    if not operands or operands[0].unresolved or operands[0].text == "-":
        return
    target = operands[0].text.replace("\\", "/") if ctx.ps else operands[0].text
    current = ctx.cwds[-1] if ctx.cwds else ""
    absolute = target.startswith("/") or re.match(r"[A-Za-z]:", target) is not None
    moved = posixpath.normpath(target if absolute else posixpath.join(current, target))
    if len(moved) > MAX_CWD:
        ctx.out.lost_directory = True
    elif not ctx.cwds or ctx.cwds[-1] != moved:
        ctx.cwds.append(moved)


def _record_targets(verb: str, rest: list, ctx: _Ctx) -> None:
    canonical = _PS_ALIASES.get(verb, verb)
    if canonical in _PS_SPECS and (ctx.ps or verb not in _TARGETS):
        items, via = _t_powershell(canonical, rest, ctx), canonical
    elif verb in _TARGETS:
        items, via = _TARGETS[verb](rest, ctx), verb
    elif verb in _CMD_VERBS:
        items, via = _t_cmd(verb, rest, ctx), verb
    else:
        return
    for item in items:
        argument, directories, label = item if isinstance(item, tuple) else (item, (), via)
        if _is_null(argument):
            continue
        cwds = _recent(ctx)
        if directories:
            bases = ("",) + cwds
            cwds = tuple(dict.fromkeys(posixpath.normpath(posixpath.join(base, d)) if base else d
                                       for base in bases for d in directories))
        _note_write(ctx, argument.text, label, cwds, argument.glob, argument.unresolved)


def _finish(args: list, ctx: _Ctx, body: "str | None") -> None:
    verb = _verb(args[0].text)
    rest = args[1:]
    command = Command(verb, tuple(a.text for a in rest), _recent(ctx))
    if command not in ctx.seen:
        ctx.seen.add(command)
        ctx.out.commands.append(command)
    if verb in _CD:
        _change_directory(rest, ctx)
    elif verb in _DECLARE:
        for argument in rest:
            match = _ASSIGN.match(argument.text)
            if match and not argument.unresolved:
                ctx.vars[match.group(1).lower() if ctx.ps else match.group(1)] = match.group(2)
    _record_targets(verb, rest, ctx)
    ctx.out.code.extend(_inline_code(verb, rest, body))
    if _DOTNET_FILE.search(args[0].text):
        ctx.out.code.append(ctx.text)


def _run_tokens(tokens: list, ctx: _Ctx) -> None:
    stages: list = [[]]

    def flush() -> None:
        upstream = None
        for stage in stages:
            upstream = _run_stage(stage, ctx, upstream)
        stages[:] = [[]]

    marks: list = []
    for kind, value in tokens:
        if kind == "op":
            if value in ("|", "|&"):
                stages.append([])
                continue
            flush()
            if value == "(":
                marks.append(len(ctx.cwds))
            elif value == ")" and marks:
                del ctx.cwds[marks.pop():]
        else:
            stages[-1].append((kind, value))
    flush()


def _process(text: str, ctx: _Ctx, ps: bool, scoped: bool = True) -> None:
    """Analyse ``text`` as shell (or PowerShell) in the shared context; past ``MAX_DEPTH`` it is kept as code.

    A substitution or ``sh -c`` runs in a subshell, so a ``cd`` inside it is forgotten afterwards;
    ``eval`` runs in the current shell (``scoped`` false) and keeps it."""
    if ctx.depth >= MAX_DEPTH:
        ctx.out.code.append(text)
        return
    saved_ps, saved_text, mark = ctx.ps, ctx.text, len(ctx.cwds)
    ctx.ps, ctx.text = ps, text
    ctx.depth += 1
    try:
        tokens = _Lexer(text, ps).run()
        _run_tokens(tokens, ctx)
    except (_Unbalanced, RecursionError):
        ctx.out.ok = False
    finally:
        ctx.depth -= 1
        ctx.ps, ctx.text = saved_ps, saved_text
        if scoped:
            del ctx.cwds[mark:]


def analyse(text: str, *, powershell: bool = False) -> Analysis:
    """Analyse one command line (Bash by default, PowerShell when ``powershell``); never raises on odd input."""
    out = Analysis()
    _process(text, _Ctx(out, powershell), powershell)
    return out
