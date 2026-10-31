#!/usr/bin/env python3
"""Small, dependency-free data readers shared by catalog validators.

The catalog uses YAML for human-authored manifests and frontmatter, but the
runtime must remain usable on a clean host.  This module intentionally supports
the subset used by the package: mappings, nested mappings, lists, inline lists,
quoted/unquoted scalars, and block strings.  JSON is accepted first because JSON
is also valid YAML and is useful for fixtures that need exact types.

Where the subset reads a scalar differently from PyYAML, it reads it as text
rather than guess a type: ``yes``/``no``/``on``/``off`` stay words (PyYAML 1.1
booleans), a number with a leading zero stays text (``010`` is 8 to PyYAML),
``0x1F``, ``1_000``, ``.inf``, ``.nan``, ``12:30`` and dates stay text, and a
float stays text unless it prints back unchanged (``3.10`` is a version, see
``parse_scalar``).  Block scalars accept every chomping indicator and always drop
trailing whitespace, so ``|`` reads as ``|-`` (PyYAML keeps one final newline);
``validation/test_catalog_contracts.py`` ParserParityTests compares the two
readers on the shipped catalog under that rule.  One document per file: a second
``---`` after content is an error, where PyYAML's ``safe_load`` also refuses it.

What the subset does not support it refuses by name, with the line, rather than read
as something else: an anchor (``&a``), an alias (``*a``, so a merge key ``<<: *a`` too)
and a tag (``!!str``, ``!Ref``), which it once kept as text (``*a`` became the string
``'*a'``); a block scalar on a list item's own line (``- |``, ``- key: >-``), which it
once read as the text ``'|'`` followed by the block parsed as YAML; an indentation
indicator (``|2``); and a complex key (``? ``).  An unquoted glob that starts with ``*``
is an alias to YAML as well, so it has to be quoted.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any


class DataFormatError(ValueError):
    """Raised when a catalog data file cannot be parsed safely."""


def _mapping_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DataFormatError(f"duplicate mapping key: {key!r}")
        result[key] = value
    return result


def _split_inline(value: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote: str | None = None
    depth = 0
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(value[start:index].strip())
            start = index + 1
    if quote or depth != 0:
        raise DataFormatError("unterminated inline value")
    tail = value[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def _strip_comment(value: str) -> str:
    """Remove YAML comments without treating a # in a quoted value as a comment."""
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.rstrip()


#: What an unquoted value that starts with a YAML node property is, and what to write instead. PyYAML would resolve the
#: anchor, alias or tag; the subset used to keep the whole text (``*base`` became the string ``'*base'``), so it refuses.
_NODE_PROPERTIES = {
    "&": "YAML anchor {token!r} is not supported by the catalog's YAML subset; write the value out where it is used",
    "*": ("YAML alias {token!r} is not supported by the catalog's YAML subset (merge keys '<<' included); write the value "
          "it refers to out in full, or quote the value if it is text, as a glob such as '**/x' must be"),
    "!": "YAML tag {token!r} is not supported by the catalog's YAML subset; drop the tag, or quote the value if it is text",
}


def parse_scalar(value: str) -> Any:
    value = _strip_comment(value.strip())
    if not value:
        return ""
    if value[0] in _NODE_PROPERTIES:
        raise DataFormatError(_NODE_PROPERTIES[value[0]].format(token=value.split()[0]))
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("["):
        if not value.endswith("]"):
            raise DataFormatError("unterminated inline value")
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(part) for part in _split_inline(inner)]
    if value.startswith("{"):
        if not value.endswith("}"):
            raise DataFormatError("unterminated inline value")
        inner = value[1:-1].strip()
        result: dict[str, Any] = {}
        if not inner:
            return result
        for part in _split_inline(inner):
            if ":" not in part:
                raise DataFormatError("invalid inline mapping item")
            key, item = part.split(":", 1)
            key = str(parse_scalar(key))
            if key in result:
                raise DataFormatError(f"duplicate mapping key: {key!r}")
            result[key] = parse_scalar(item)
        return result
    if value[0] == value[-1] and value[0] in "'\"":
        if value[0] == "'":
            # YAML single quotes are literal: the only escape is a doubled quote. A path is written this way
            # (''C:\\Users\\...'' is invalid), so backslashes reach the value untouched.
            body = value[1:-1]
            out = []
            i = 0
            while i < len(body):
                if body[i] == "'":
                    if body[i + 1:i + 2] != "'":
                        raise DataFormatError("invalid quoted scalar")
                    out.append("'")
                    i += 2
                else:
                    out.append(body[i])
                    i += 1
            return "".join(out)
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise DataFormatError("invalid quoted scalar") from exc
    if re.fullmatch(r"[-+]?\d+", value) and not re.fullmatch(r"[-+]?0\d+", value):
        # A leading zero is an octal number to PyYAML (010 is 8), so it stays text here rather than read as ten.
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
        try:
            number = float(value)
        except ValueError:
            pass
        else:
            # A number is a float only when it prints back unchanged, so 3.10 and
            # 1.20 stay text (a version, not a quantity: converting would rename
            # the release). The rule is wider than versions on purpose: .5, +1.5,
            # 1., 1.50 and 1.5e+3 also stay text, where PyYAML reads all of them
            # (and 3.10) as floats. No shipped YAML holds an unquoted float.
            if str(number) == value:
                return number
    return value


#: Every chomping indicator is accepted; ``_block_scalar`` reads each as strip (see the module docstring).
_BLOCK_INDICATORS = {"|", ">", "|-", "|+", ">-", ">+"}
#: Any block scalar header, the unsupported ones with an indentation indicator (``|2``, ``>-1``) included.
_BLOCK_HEADER = re.compile(r"[|>][-+]?\d?[-+]?")


def _opens_block(content: str) -> bool:
    """True for a line whose value is a block scalar header: a mapping entry (``key: |``), or a list item's own line
    (``- >-``, ``- key: |``), so the lines under it pass through raw and the parser can name what it does not support."""
    if content.startswith("-"):
        content = content[1:].strip()
        if _BLOCK_HEADER.fullmatch(content):
            return True
    return ":" in content and bool(_BLOCK_HEADER.fullmatch(content.split(":", 1)[1].strip()))


def _scalar(value: str, lineno: int) -> Any:
    """``parse_scalar`` with the line the value came from in any error it raises."""
    try:
        return parse_scalar(value)
    except DataFormatError as exc:
        raise DataFormatError(f"{exc} (line {lineno})") from exc


def _normalise_lines(text: str) -> list[tuple[int, str, int]]:
    """Split text into (indent, content, line number), dropping comments and blank lines.

    The lines of a block scalar are the exception: inside one, a line that starts
    with ``#``, a `` #`` tail, and a blank line are all content, so they pass
    through raw and blank lines are kept as empty content one level deeper than
    the header.
    """
    lines: list[tuple[int, str, int]] = []
    block_indent: int | None = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        indent = len(raw) - len(raw.lstrip(" "))
        if block_indent is not None:
            if not raw.strip():
                lines.append((block_indent + 1, "", lineno))
                continue
            if indent > block_indent:
                if "\t" in raw[: len(raw) - len(raw.lstrip(" \t"))]:
                    raise DataFormatError(f"tabs are not supported for indentation at line {lineno}")
                lines.append((indent, raw[indent:], lineno))
                continue
            block_indent = None
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if stripped in {"---", "..."}:
            if stripped == "---" and lines:
                raise DataFormatError(f"a second document starts at line {lineno}; one document per file")
            continue
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise DataFormatError(f"tabs are not supported for indentation at line {lineno}")
        content = _strip_comment(raw[indent:])
        lines.append((indent, content, lineno))
        if _opens_block(content):
            block_indent = indent
    return lines


def _block_scalar(pieces: list[str], folded: bool) -> str:
    """Join a block scalar's lines: literal keeps line breaks, folded joins with a space.

    A blank line inside a folded scalar is a paragraph break, so it becomes a
    newline in place of the space rather than a second space.
    """
    if not folded:
        return "\n".join(pieces).rstrip()
    text, blanks = "", 0
    for piece in pieces:
        if not piece:
            blanks += 1
            continue
        if text:
            text += "\n" * blanks if blanks else " "
        text += piece
        blanks = 0
    return text.rstrip()


def _parse_block(lines: list[tuple[int, str, int]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines) or lines[index][0] < indent:
        return {}, index
    is_list = lines[index][0] == indent and lines[index][1].startswith("-")
    result: Any = [] if is_list else {}
    while index < len(lines):
        current_indent, content, lineno = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise DataFormatError(f"unexpected indentation at line {lineno}")
        if is_list:
            if not content.startswith("-"):
                break
            item = content[1:].strip()
            index += 1
            if _BLOCK_HEADER.fullmatch(item) or (":" in item and _BLOCK_HEADER.fullmatch(item.split(":", 1)[1].strip())):
                raise DataFormatError(
                    f"a block scalar on a list item's own line ({content!r}) at line {lineno} is not supported by the "
                    "catalog's YAML subset; write the item as one quoted string, or put its key on the next line under "
                    "the dash")
            if not item:
                if index < len(lines) and lines[index][0] > indent:
                    value, index = _parse_block(lines, index, lines[index][0])
                else:
                    value = None
            elif (
                ":" in item
                and not item.startswith(("http:", "https:"))
                and not (len(item) >= 2 and item[0] in {"'", '"'} and item[-1] == item[0])
            ):
                key, raw_value = item.split(":", 1)
                mapping_key = str(_scalar(key.strip(), lineno))
                mapping: dict[str, Any] = {mapping_key: _scalar(raw_value, lineno)} if raw_value.strip() else {mapping_key: None}
                if index < len(lines) and lines[index][0] > indent:
                    child, index = _parse_block(lines, index, lines[index][0])
                    if isinstance(child, dict):
                        duplicate = set(mapping) & set(child)
                        if duplicate:
                            raise DataFormatError(f"duplicate mapping key: {sorted(duplicate)[0]!r}")
                        mapping.update(child)
                    elif mapping[mapping_key] is None:
                        mapping[mapping_key] = child
                value = mapping
            else:
                value = _scalar(item, lineno)
                if index < len(lines) and lines[index][0] > indent:
                    raise DataFormatError(f"list scalar cannot have nested content at line {lines[index][2]}")
            result.append(value)
            continue

        if content == "?" or content.startswith("? "):
            raise DataFormatError(f"a complex mapping key ('? ') at line {lineno} is not supported by the catalog's YAML "
                                  "subset; write the key as a plain or quoted scalar before the ':'")
        if content.startswith("-") or ":" not in content:
            raise DataFormatError(f"expected mapping entry at line {lineno}")
        key, raw_value = content.split(":", 1)
        key = str(_scalar(key.strip(), lineno))
        if not key:
            raise DataFormatError(f"empty mapping key at line {lineno}")
        if key in result:
            raise DataFormatError(f"duplicate mapping key: {key!r} at line {lineno}")
        raw_value = raw_value.strip()
        index += 1
        if raw_value in _BLOCK_INDICATORS:
            pieces: list[str] = []
            base: int | None = None
            while index < len(lines) and lines[index][0] > indent:
                child_indent, child_content, _ = lines[index]
                if child_content:
                    base = child_indent if base is None else base
                    pieces.append(" " * max(child_indent - base, 0) + child_content)
                else:
                    pieces.append("")
                index += 1
            result[key] = _block_scalar(pieces, folded=raw_value.startswith(">"))
        elif _BLOCK_HEADER.fullmatch(raw_value):
            raise DataFormatError(f"block scalar indentation indicator {raw_value!r} at line {lineno} is not supported by "
                                  f"the catalog's YAML subset; drop the digit ({raw_value[0]} with an optional - or +) "
                                  "and indent the block's lines evenly")
        elif raw_value:
            result[key] = _scalar(raw_value, lineno)
            if index < len(lines) and lines[index][0] > indent:
                raise DataFormatError(f"scalar mapping value has nested content at line {lines[index][2]}: a value that "
                                      "continues on the next line is not supported; quote it on one line or use a block "
                                      "scalar (| or >)")
        elif index < len(lines) and lines[index][0] > indent:
            result[key], index = _parse_block(lines, index, lines[index][0])
        else:
            result[key] = None
    return result, index


def parse_yaml(text: str) -> Any:
    """Parse the catalog's supported YAML subset without third-party packages."""
    try:
        return json.loads(text, object_pairs_hook=_mapping_without_duplicates)
    except json.JSONDecodeError:
        pass
    # JSON is valid YAML, and a JSON document may legitimately carry YAML
    # full-line comments or document markers. Strip those and retry before
    # falling back to the block-YAML subset, so a commented copy of a JSON
    # spec is not an engine error.
    body_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#") and line.strip() not in {"---", "..."}]
    body = "\n".join(body_lines).strip()
    if body and body[0] in "{[" and body != text.strip():
        try:
            return json.loads(body, object_pairs_hook=_mapping_without_duplicates)
        except json.JSONDecodeError:
            pass
    stripped = text.strip()
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        return parse_scalar(stripped)
    lines = _normalise_lines(text)
    if not lines:
        return {}
    value, index = _parse_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise DataFormatError(f"unparsed YAML content at line {lines[index][2]}")
    return value


def load_data(path: Path) -> Any:
    """Load JSON or the supported YAML subset from ``path``."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise DataFormatError(f"cannot read {path}: {exc}") from exc
    try:
        return parse_yaml(text)
    except DataFormatError:
        raise
    except (ValueError, RecursionError) as exc:
        raise DataFormatError(f"cannot parse {path}: {exc}") from exc


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Return YAML frontmatter from a Markdown document, or an empty mapping."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        return {}
    value = parse_yaml(match.group(1))
    if not isinstance(value, dict):
        raise DataFormatError("frontmatter must be a mapping")
    return value


# --- Line-ending-agnostic content hashing ------------------------------------

#: Bytes inspected for a NUL to decide whether a file is text.
_TEXT_PROBE = 8192


def normalize_line_endings(data: bytes) -> bytes:
    """Return ``data`` with CRLF folded to LF when it is text; binary is untouched.

    A file is treated as text when its first 8 KiB carries no NUL byte. Every
    sha256 the catalog records or verifies - ``artifact_hashes``, probe, scan and
    render ``inputs``, tech-stack overlay digests, save evidence registrations -
    goes through this fold, so a checkout that converts line endings
    (core.autocrlf, editor settings, a zip round-trip) never turns a valid hash
    into ``input hash drift``. Binary artifacts (captures, archives) hash
    byte-for-byte because a CRLF pair inside them is data, not a line ending.
    """
    if b"\x00" in data[:_TEXT_PROBE]:
        return data
    return data.replace(b"\r\n", b"\n")


def content_sha256(path: Path | str) -> str:
    """sha256 of a file's line-ending-normalised content (see ``normalize_line_endings``)."""
    return hashlib.sha256(normalize_line_endings(Path(path).read_bytes())).hexdigest()
