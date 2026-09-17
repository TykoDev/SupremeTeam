#!/usr/bin/env python3
"""Small, dependency-free data readers shared by catalog validators.

The catalog uses YAML for human-authored manifests and frontmatter, but the
runtime must remain usable on a clean host.  This module intentionally supports
the subset used by the package: mappings, nested mappings, lists, inline lists,
quoted/unquoted scalars, and block strings.  JSON is accepted first because JSON
is also valid YAML and is useful for fixtures that need exact types.
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


def parse_scalar(value: str) -> Any:
    value = _strip_comment(value.strip())
    if not value:
        return ""
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
    if (value[0] == value[-1]) and value[0] in "'\"":
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise DataFormatError("invalid quoted scalar") from exc
    if re.fullmatch(r"[-+]?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def _normalise_lines(text: str) -> list[tuple[int, str, int]]:
    lines: list[tuple[int, str, int]] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        stripped = raw.strip()
        if stripped in {"---", "..."}:
            continue
        leading = raw[: len(raw) - len(raw.lstrip(" \t"))]
        if "\t" in leading:
            raise DataFormatError(f"tabs are not supported for indentation at line {lineno}")
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, _strip_comment(raw[indent:]), lineno))
    return lines


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
                mapping_key = str(parse_scalar(key.strip()))
                mapping: dict[str, Any] = {mapping_key: parse_scalar(raw_value)} if raw_value.strip() else {mapping_key: None}
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
                value = parse_scalar(item)
                if index < len(lines) and lines[index][0] > indent:
                    raise DataFormatError(f"list scalar cannot have nested content at line {lines[index][2]}")
            result.append(value)
            continue

        if content.startswith("-") or ":" not in content:
            raise DataFormatError(f"expected mapping entry at line {lineno}")
        key, raw_value = content.split(":", 1)
        key = str(parse_scalar(key.strip()))
        if not key:
            raise DataFormatError(f"empty mapping key at line {lineno}")
        if key in result:
            raise DataFormatError(f"duplicate mapping key: {key!r} at line {lineno}")
        raw_value = raw_value.strip()
        index += 1
        if raw_value in {"|", ">", "|-", "|+", ">-", ">+"}:
            pieces: list[str] = []
            while index < len(lines) and lines[index][0] > indent:
                child_indent, child_content, _ = lines[index]
                pieces.append(child_content if child_indent else "")
                index += 1
            result[key] = ("\n" if raw_value.startswith("|") else " ").join(pieces).rstrip()
        elif raw_value:
            result[key] = parse_scalar(raw_value)
            if index < len(lines) and lines[index][0] > indent:
                raise DataFormatError(f"scalar mapping value has nested content at line {lines[index][2]}")
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
        text = path.read_text(encoding="utf-8")
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
