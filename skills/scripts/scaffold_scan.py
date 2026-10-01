"""Scan project text files for scaffold, placeholder and debug markers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_files import classify_path, is_sensitive, is_text_path, read_cached_text, relative_path
from redaction import redact


MARKER_PATTERN = re.compile(
    r"(?i)\b(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB|NOT\s+IMPLEMENTED|COMING\s+SOON|"
    r"TEMPORARY|TEMP|DUMMY|FAKE|SAMPLE|REMOVE\s+(?:THIS|ME|BEFORE)|CHANGE\s*ME)\b"
)
COMMENT_MARKER_PATTERN = re.compile(
    r"(?i)(?:^|\s)(?:#|//|/\*)\s*(TODO|FIXME|HACK|XXX|PLACEHOLDER|STUB|"
    r"NOT\s+IMPLEMENTED|COMING\s+SOON|TEMPORARY|TEMP|DUMMY|FAKE|SAMPLE|"
    r"REMOVE\s+(?:THIS|ME|BEFORE)|CHANGE\s*ME)\b"
)


def _language(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}:
        return "javascript"
    if suffix == ".go":
        return "go"
    if suffix == ".rs":
        return "rust"
    if suffix == ".cs":
        return "csharp"
    if suffix == ".java":
        return "java"
    if suffix == ".rb":
        return "ruby"
    if suffix in {".sh", ".bash", ".zsh"} or path.name.lower() == "makefile":
        return "shell"
    return None


def _canonical_marker(value: str) -> str:
    return " ".join(value.upper().split())


def _without_quoted_strings(line: str) -> str:
    return _without_quoted_strings_lines([line])[0]


def _without_quoted_strings_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    quote: str | None = None
    block_comment = False
    escaped = False
    for line in lines:
        clean_line: list[str] = []
        index = 0
        while index < len(line):
            if block_comment:
                close = line.find("*/", index)
                if close == -1:
                    clean_line.extend(line[index:])
                    index = len(line)
                    continue
                clean_line.extend(line[index:close + 2])
                index = close + 2
                block_comment = False
                continue
            if quote:
                if len(quote) == 3 and line.startswith(quote, index):
                    clean_line.extend(" " for _ in quote)
                    index += len(quote)
                    quote = None
                    escaped = False
                    continue
                char = line[index]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif len(quote) == 1 and char == quote:
                    quote = None
                clean_line.append(" ")
                index += 1
                continue
            if line[index] == "#" or line.startswith("//", index):
                clean_line.extend(line[index:])
                break
            if line.startswith("/*", index):
                clean_line.extend("/*")
                index += 2
                block_comment = True
                continue
            if line.startswith("'''", index) or line.startswith('"""', index):
                quote = line[index:index + 3]
                clean_line.extend(" " for _ in quote)
                index += 3
            elif line[index] in {"'", '"', "`"}:
                quote = line[index]
                clean_line.append(" ")
                index += 1
            else:
                clean_line.append(line[index])
                index += 1
        if quote in {"'", '"'}:
            # Only triple quotes and backticks span lines. A lone apostrophe (a Rust
            # lifetime, a regex literal) must not blank every line that follows it.
            quote = None
            escaped = False
        result.append("".join(clean_line))
    return result


def _line_matches(line: str, language: str | None, code_line: str | None = None) -> list[str]:
    markers: list[str] = []

    def add(value: str) -> None:
        marker = _canonical_marker(value)
        if marker not in markers:
            markers.append(marker)

    code_line = code_line if code_line is not None else _without_quoted_strings(line)
    comment_match = COMMENT_MARKER_PATTERN.search(code_line)
    if comment_match:
        add(comment_match.group(1))
    for match in MARKER_PATTERN.finditer(code_line):
        add(match.group(1))

    patterns: list[tuple[re.Pattern[str], str]] = []
    if language == "python":
        patterns = [
            (re.compile(r"\braise\s+NotImplementedError\b"), "NOT IMPLEMENTED"),
            (re.compile(r"\bdef\s+\w+\([^)]*\):\s*(?:pass|\.\.\.)\s*$"), "EMPTY FUNCTION"),
            (re.compile(r"\bexcept(?:\s+\w+)?\s*:\s*pass\s*$"), "EMPTY ERROR HANDLER"),
            (re.compile(r"(?<!\w)print\("), "DEBUG STATEMENT"),
        ]
    elif language == "javascript":
        patterns = [
            (re.compile(r"throw\s+new\s+Error\s*\(\s*[\"']not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\bfunction\s+\w+\([^)]*\)(?:\s*:\s*[^{}]+)?\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"=>\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"(?m)^\s*(?:(?:(?:public|private|protected|static|abstract|async|get|set|override)\s+)*"
                         r"(?!if\b|for\b|while\b|switch\b|catch\b)[A-Za-z_$][\w$]*\s*\([^)]*\)"
                         r"(?:\s*:\s*[^{}]+)?)\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), "EMPTY ERROR HANDLER"),
            (re.compile(r"console\.(?:log|debug|info|warn|error)\("), "DEBUG STATEMENT"),
        ]
    elif language == "go":
        patterns = [
            (re.compile(r"panic\s*\(\s*[\"']not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?\w+\([^)]*\)\s*(?:\([^)]*\)\s*)?\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"fmt\.Print(?:ln|f)?\("), "DEBUG STATEMENT"),
            (re.compile(r"^\s*(?:defer\s+)?recover\(\)\s*;?\s*$"), "EMPTY ERROR HANDLER"),
        ]
    elif language == "rust":
        patterns = [
            (re.compile(r"\b(?:todo|unimplemented)!\(\)"), "NOT IMPLEMENTED"),
            (re.compile(r"\bdbg!\("), "DEBUG STATEMENT"),
            (re.compile(r"\blet\s+_\s*=\s*"), "IGNORED RESULT"),
        ]
    elif language == "csharp":
        patterns = [
            (re.compile(r"\bthrow\s+new\s+NotImplementedException\b"), "NOT IMPLEMENTED"),
            (re.compile(r"\bthrow\s+new\s+NotSupportedException\([^)]*not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\b(?:public|private|protected|internal)\b[^{};]*\([^)]*\)\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"Console\.Write(?:Line)?\("), "DEBUG STATEMENT"),
        ]
    elif language == "java":
        patterns = [
            (re.compile(r"\bthrow\s+new\s+UnsupportedOperationException\([^)]*not\s+implemented", re.I), "NOT IMPLEMENTED"),
            (re.compile(r"\b(?:public|private|protected)\b[^{};]*\([^)]*\)\s*\{\s*\}"), "EMPTY FUNCTION"),
            (re.compile(r"System\.out\.print"), "DEBUG STATEMENT"),
        ]
    elif language == "ruby":
        patterns = [
            (re.compile(r"\braise\s+NotImplementedError\b"), "NOT IMPLEMENTED"),
            (re.compile(r"^\s*def\s+\w+[^;]*;\s*(?:nil|\.\.\.)\s*;\s*end\s*$"), "EMPTY FUNCTION"),
            (re.compile(r"\b(?:puts|p)\s+"), "DEBUG STATEMENT"),
        ]
    elif language == "shell":
        patterns = [
            (re.compile(r"\b(?:echo|printf)\b.*\b(?:TODO|PLACEHOLDER|STUB)\b", re.I), "UNFINISHED OUTPUT"),
        ]
    for pattern, marker in patterns:
        if pattern.search(code_line):
            add(marker)

    if re.search(r"(?i)lorem\s+ipsum|dolor\s+sit\s+amet", code_line):
        add("FILLER PROSE")
    if re.search(r"(?i)\b(?:example|test)\.(?:com|org|net)\b", code_line):
        add("PLACEHOLDER DOMAIN")
    if re.search(r"(?i)\b(?:password|secret)\s*[:=]\s*[\"']?(?:password|secret)", code_line):
        add("DEFAULT SECRET")
    if re.search(r"(?i)\b(?:key)\s*[:=]\s*[\"']?changeme\b", code_line):
        add("DEFAULT SECRET")
    if re.search(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0)\b", code_line):
        add("LOCALHOST ADDRESS")
    for pattern, marker in (
        (re.compile(r"\breturn\s*\[\s*\](?![\w.])"), "RETURN []"),
        (re.compile(r"\breturn\s*\{\s*\}(?![\w.])"), "RETURN {}"),
        (re.compile(r"\breturn\s+null\b", re.I), "RETURN NULL"),
        (re.compile(r"\breturn\s+None\b"), "RETURN NONE"),
        (re.compile(r"\breturn\s+0(?![\w.])"), "RETURN 0"),
    ):
        if pattern.search(code_line):
            add(marker)
    if language == "shell" and re.match(r"^\s*exit\s+0\b", code_line):
        add("EXIT 0")
    return markers


def _comment_only(line: str, language: str | None) -> bool:
    stripped = line.strip()
    if language == "python":
        return stripped.startswith("#")
    return stripped.startswith(("//", "/*", "*", "*/"))


def _block_matches(
    lines: list[str],
    index: int,
    language: str | None,
    code_lines: list[str] | None = None,
) -> list[tuple[str, str]]:
    detection_lines = code_lines if code_lines is not None else lines
    line = detection_lines[index]
    source_line = lines[index]

    if language == "python" and re.match(
        r"^\s*(?:async\s+)?def\s+\w+\([^)]*\)(?:\s*->\s*[^:\n]+)?\s*:\s*(?:pass|\.\.\.)(?:\s*#.*)?$",
        line,
    ):
        return [("EMPTY FUNCTION", source_line)]

    if language == "python" and re.match(
        r"^\s*(?:async\s+)?def\s+\w+\([^)]*\)(?:\s*->\s*[^:\n]+)?\s*:\s*(?:#.*)?$",
        line,
    ):
        header_indent = len(line) - len(line.lstrip())
        body_index = index + 1
        while body_index < len(detection_lines) and (
            not detection_lines[body_index].strip() or detection_lines[body_index].lstrip().startswith("#")
        ):
            body_index += 1
        if body_index < len(detection_lines):
            body_line = detection_lines[body_index]
            body_indent = len(body_line) - len(body_line.lstrip())
            if body_indent > header_indent and re.fullmatch(
                r"(?:pass|\.\.\.)(?:\s*#.*)?",
                body_line.strip(),
            ):
                next_index = body_index + 1
                has_more_body = False
                while next_index < len(detection_lines):
                    candidate = detection_lines[next_index]
                    if not candidate.strip() or _comment_only(candidate, language):
                        next_index += 1
                        continue
                    if len(candidate) - len(candidate.lstrip()) > header_indent:
                        has_more_body = True
                        break
                    if candidate.strip():
                        break
                    next_index += 1
                if not has_more_body:
                    return [("EMPTY FUNCTION", "\n".join(lines[index:body_index + 1]))]

    def empty_brace_block(header_pattern: str) -> tuple[str, str] | None:
        inline = re.match(
            r"^(?P<header>.*\{)\s*(?P<body>//.*|/\*.*\*/)?\s*\}\s*;?\s*$",
            line,
        )
        if inline and (inline.group("body") is None or _comment_only(inline.group("body"), language)):
            if re.match(header_pattern, inline.group("header")):
                return "EMPTY FUNCTION", source_line
        if not re.match(header_pattern, line):
            return None
        open_index = index
        if "{" not in line:
            open_index = next(
                (
                    candidate
                    for candidate in range(index + 1, min(len(detection_lines), index + 21))
                    if detection_lines[candidate].strip()
                ),
                -1,
            )
            if open_index == -1 or detection_lines[open_index].strip() != "{":
                return None
        close_index = next(
            (
                candidate
                for candidate in range(open_index + 1, min(len(detection_lines), open_index + 21))
                if detection_lines[candidate].strip() in {"}", "};"}
            ),
            None,
        )
        if close_index is None:
            return None
        if any(
            detection_lines[candidate].strip() and not _comment_only(detection_lines[candidate], language)
            for candidate in range(open_index + 1, close_index)
        ):
            return None
        return "EMPTY FUNCTION", "\n".join(lines[index:close_index + 1])

    if language == "javascript":
        block = empty_brace_block(
            r"^\s*(?:"
            r"(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+\w+\([^)]*\)(?:\s*:\s*[^{}]+)?|"
            r"(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)"
            r"(?:\s*:\s*[^{}]+)?\s*=>|"
            r"(?:(?:public|private|protected|static|abstract|async|get|set|override)\s+)*"
            r"(?!if\b|for\b|while\b|switch\b|catch\b)[A-Za-z_$][\w$]*\s*\([^)]*\)"
            r"(?:\s*:\s*[^{}]+)?"
            r")\s*(?:\{\s*)?$"
        )
        if block:
            return [block]

    if language == "go":
        block = empty_brace_block(
            r"^\s*func\s+(?:\([^)]*\)\s*)?\w+\([^)]*\)(?:\s*\([^)]*\))?(?:\s+[^{}]+)?\s*(?:\{\s*)?$"
        )
        if block:
            return [block]

    if language in {"csharp", "java"}:
        visibility = "public|private|protected|internal" if language == "csharp" else "public|private|protected"
        block = empty_brace_block(
            rf"^\s*(?:{visibility})\b[^{{}};]*\([^)]*\)\s*(?:\{{\s*)?$"
        )
        if block:
            return [block]

    if language == "ruby" and re.match(r"^\s*def\s+\w+", detection_lines[index]):
        end = next(
            (
                candidate
                for candidate in range(index + 1, min(len(detection_lines), index + 21))
                if detection_lines[candidate].strip() == "end"
            ),
            None,
        )
        if end is not None:
            body = [
                line.strip()
                for line in detection_lines[index + 1:end]
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if body in (["nil"], ["..."]):
                return [("EMPTY FUNCTION", "\n".join(lines[index:end + 1]))]

    if language == "shell" and re.match(
        r"^\s*(?:(?:function\s+)?[A-Za-z_][A-Za-z0-9_-]*\s*(?:\(\s*\))?)\s*\{\s*$",
        detection_lines[index],
    ):
        end = next(
            (
                candidate
                for candidate in range(index + 1, min(len(detection_lines), index + 21))
                if detection_lines[candidate].strip() == "}"
            ),
            None,
        )
        if end is not None:
            body = [
                line.strip()
                for line in detection_lines[index + 1:end]
                if line.strip() and not line.lstrip().startswith("#")
            ]
            if body and all(item in {":", "true"} for item in body):
                return [("EMPTY FUNCTION", "\n".join(lines[index:end + 1]))]
    if language == "shell":
        inline = re.match(
            r"^\s*(?:(?:function\s+)?[A-Za-z_][A-Za-z0-9_-]*\s*(?:\(\s*\))?)\s*"
            r"\{(?P<body>.*?)\}\s*$",
            line,
        )
        if inline:
            body = [item.strip() for item in inline.group("body").split(";") if item.strip()]
            if body and all(item in {":", "true"} for item in body):
                return [("EMPTY FUNCTION", source_line)]
    return []


def find_scaffold_markers(files: list[Path], root: Path, errors: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cache: dict[Path, str | None] = {}
    for path in files:
        if is_sensitive(path, root) or not is_text_path(path):
            continue
        relative = relative_path(path, root)
        text = read_cached_text(path, root, errors, cache, required=True)
        if text is None:
            continue
        path_class = classify_path(relative)
        language = _language(path)
        lines = text.splitlines()
        code_lines = _without_quoted_strings_lines(lines)
        for line_index, line in enumerate(lines):
            matches = [(marker, line) for marker in _line_matches(line, language, code_lines[line_index])]
            matches.extend(_block_matches(lines, line_index, language, code_lines))
            seen: set[str] = set()
            for marker, raw_context in matches:
                if marker in seen:
                    continue
                seen.add(marker)
                context = redact(raw_context.strip())
                findings.append(
                    {
                        "file": relative,
                        "line": line_index + 1,
                        "marker": marker,
                        "message": context,
                        "context": context,
                        "path_class": path_class,
                        "production_finding": path_class == "production",
                    }
                )
    findings.sort(key=lambda item: (item["file"], item["line"], item["marker"], item["message"]))
    return findings
