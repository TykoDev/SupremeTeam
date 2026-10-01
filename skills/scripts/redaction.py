"""Secret redaction for the runtime report: free text, URLs, command lines and structured values."""

from __future__ import annotations

import json
import math
import re
from typing import Any
from urllib.parse import unquote


SECRET_KEYS = r"(?:password|passwd|passphrase|secret(?:[_-]?key)?|webhook[_-]?secret|token|auth[_-]?(?:key|token)?|api[_-]?key|authorization|private[_-]?key|client[_-]?secret|database[_-]?(?:password|url)|access[_-]?token|access[_-]?key(?:[_-]?id)?|shared[_-]?access[_-]?(?:key|signature)|sig|refresh[_-]?token|session(?:s|[_-]?(?:id|token))?|cookie(?:s)?|set[_-]?cookie|bearer|credential(?:s)?|csrf(?:[_-]?token)?|jwt|signature|signed[_-]?url|connection[_-]?string|signing[_-]?key|encryption[_-]?key|secret[_-]?access[_-]?key|storage[_-]?account[_-]?key|service[_-]?account[_-]?key|secret[_-]?key[_-]?base64|azure[_-]?storage[_-]?account[_-]?key|cloud[_-]?(?:access|secret)(?:[_-]?access)?[_-]?key|aws[_-]?(?:access[_-]?key(?:[_-]?id)?|secret[_-]?access[_-]?key|session[_-]?token)|github[_-]?token|npm[_-]?token|redis[_-]?url|mongo(?:db)?[_-]?(?:url|uri))"
SECRET_VALUE = r"(?:(?:bearer|basic|token)\s+[^\s,;&|\"'}]+|\\?[\"](?:\\.|[^\"\\])*\\?[\"]|\\?['\"](?:\\.|[^'\"\\])*\\?['\"]|[^\s,;&|\"'}]+)"
SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?i)(\\?[\"']?{SECRET_KEYS}\\?[\"']?)"
    r"(\s*[:=]\s*)"
    rf"(?P<secret_value>{SECRET_VALUE})"
)
SECRET_FLAG_RE = re.compile(
    rf"(?i)(--?{SECRET_KEYS})"
    r"(?=\s|=)(?:\s*=\s*|\s+)"
    rf"{SECRET_VALUE}"
)
AUTH_SCHEME_RE = re.compile(r"(?i)\b(?:bearer|basic|token|digest)\b(?=\s+)")
REDACTION_DEPTH_LIMIT = 100
STRUCTURED_SECRET_KEYS = frozenset(
    {
        "password", "passwd", "passphrase", "secret", "secretkey", "webhooksecret",
        "token", "apikey", "authorization", "privatekey", "clientsecret",
        "databasepassword", "databaseurl", "dbpassword", "dburl", "accesstoken", "accesskey",
        "accesskeyid", "sastoken", "sharedaccesskey", "sharedaccesssignature",
        "refreshtoken", "session", "sessions", "sessionid", "sessiontoken",
        "cookie", "cookies", "setcookie", "bearer", "auth", "authkey", "authtoken",
        "credential", "credentials", "csrftoken", "jwt", "signature", "sig", "signedurl",
        "connectionstring", "signingkey", "encryptionkey", "secretaccesskey",
        "storageaccountkey", "serviceaccountkey", "secretkeybase64",
        "azurestorageaccountkey", "cloudaccesskey", "cloudsecretaccesskey",
        "awsaccesskey", "awsaccesskeyid", "awssecretaccesskey", "awssessiontoken",
        "githubtoken", "npmtoken", "redisurl", "mongourl", "mongouri",
        "xamzsignature", "xamzsecuritytoken",
        "xapikey", "xauthtoken", "xaccesstoken",
    }
)
URL_SECRET_QUERY_KEYS = frozenset(
    {
        "sig", "signature", "signedurl", "accesskey", "accesskeyid", "sharedaccesskey", "sharedaccesssignature", "secretaccesskey",
        "awsaccesskeyid", "xamzcredential", "xamzsignature", "token", "apikey",
        "authorization",
    }
)
URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+")
URL_QUERY_RE = re.compile(r"(?i)([?&])([^=&#\s]+)=([^&#\s\"']*)")


def _auth_value_end(value: str, start: int) -> int:
    index = start
    while index < len(value) and value[index].isspace():
        index += 1
    if index == len(value):
        return start
    if value.startswith((r'\"', r"\'"), index):
        quote = value[index + 1]
        closing = value.find("\\" + quote, index + 2)
        return len(value) if closing == -1 else closing + 2
    if value[index] in {"'", '"'}:
        quote = value[index]
        index += 1
        escaped = False
        while index < len(value):
            char = value[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return index + 1
            index += 1
        return len(value)

    body_start = index
    while index < len(value):
        char = value[index]
        if char in ",;|&\"'}\r\n":
            break
        if char.isspace():
            if char in "\r\n":
                break
            lookahead = index
            while lookahead < len(value) and value[lookahead] in " \t":
                lookahead += 1
            if lookahead < len(value):
                remainder = value[lookahead:]
                if re.match(
                    r"(?i)(?:--?[A-Za-z_][A-Za-z0-9_-]*|(?:Bearer|Basic|Token|Digest)\b|"
                    r"[A-Za-z_][A-Za-z0-9_-]*\s*[:=])",
                    remainder,
                ):
                    break
        index += 1
    return index if index > body_start else start


def _redact_auth_schemes(value: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in AUTH_SCHEME_RE.finditer(value):
        if match.start() < cursor:
            continue
        pieces.append(value[cursor:match.end()])
        remainder = value[match.end():]
        if (
            match.group(0).strip().lower() == "token"
            and re.match(
                r"(?i)\s+(?:must|is|was|were|should|cannot|can\s+not|can't|isn't|is\s+not)\b",
                remainder,
            )
        ) or re.match(
            r"(?i)\s+(?:authentication|authorization|auth|credentials?|field|header|scheme|token|value)\s+"
            r"(?:is|are|required|was|were|must|should|cannot|can\s+not|can't)\b",
            remainder,
        ):
            cursor = match.end()
            continue
        end = _auth_value_end(value, match.end())
        if end > match.end():
            pieces.append(" <redacted>")
        cursor = end
    pieces.append(value[cursor:])
    return "".join(pieces)


def _redact_url(match: re.Match[str]) -> str:
    value = re.sub(r"(?i)(://)[^/?#\s@]+@", r"\1<redacted>@", match.group(0), count=1)

    def redact_query(query_match: re.Match[str]) -> str:
        key = query_match.group(2)
        query_value = query_match.group(3)
        normalized = re.sub(r"[^a-z0-9]", "", unquote(key).lower())
        if normalized in URL_SECRET_QUERY_KEYS and query_value != "<redacted>":
            return f"{query_match.group(1)}{key}=<redacted>"
        return query_match.group(0)

    return URL_QUERY_RE.sub(redact_query, value)


def _redact_urls(value: str) -> str:
    return URL_RE.sub(_redact_url, value)


def _redact_assignment(match: re.Match[str], value: str) -> str:
    diagnostic_value = match.group("secret_value").strip().strip("'\"").lower()
    if diagnostic_value in {"field", "value", "authentication", "authorization", "credentials", "header", "scheme"} and re.match(
        r"(?i)\s+(?:is|required|was|were|must|should|cannot|can\s+not|can't|isn't|is\s+not|missing|invalid)\b",
        value[match.end():],
    ):
        return match.group(0)
    return f"{match.group(1)}{match.group(2)}<redacted>"


def _redact_sequence(value: list[Any], depth: int) -> list[Any]:
    result: list[Any] = []
    redact_next = False
    for item in value:
        if redact_next:
            result.append("<redacted>")
            redact_next = False
            continue
        if isinstance(item, str):
            token = item.strip().strip("'\"")
            normalized = re.sub(r"[^a-z0-9]", "", token.lstrip("-").lower())
            if token.lower() in {"bearer", "basic", "token", "digest"} or (
                token.startswith("-") and normalized in STRUCTURED_SECRET_KEYS
            ):
                redact_next = True
            result.append(redact(item, parse_structured=False))
        else:
            result.append(redact_value(item, depth + 1))
    return result


def redact(value: str, *, parse_structured: bool = True) -> str:
    if parse_structured:
        try:
            parsed = json.loads(value)
        except (ValueError, RecursionError):
            parsed = None
        if isinstance(parsed, (dict, list)):
            try:
                return json.dumps(redact_value(parsed), ensure_ascii=False, sort_keys=True)
            except (ValueError, RecursionError):
                pass
    value = _redact_urls(value)
    value = _redact_auth_schemes(value)
    value = SECRET_FLAG_RE.sub(r"\1=<redacted>", value)
    value = SECRET_ASSIGNMENT_RE.sub(lambda match: _redact_assignment(match, value), value)
    return value


def redact_value(value: Any, depth: int = 0) -> Any:
    if isinstance(value, str):
        return redact(value, parse_structured=False)
    if isinstance(value, list):
        if depth >= REDACTION_DEPTH_LIMIT:
            return "<nested value omitted>"
        return _redact_sequence(value, depth)
    if isinstance(value, dict):
        if depth >= REDACTION_DEPTH_LIMIT:
            return "<nested value omitted>"
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in STRUCTURED_SECRET_KEYS:
                result[str(key)] = "<redacted>"
            else:
                result[str(key)] = redact_value(item, depth + 1)
        return result
    if isinstance(value, float) and not math.isfinite(value):
        return "<non-finite>"
    return value


def add_error(errors: list[str], message: str) -> None:
    message = redact(message)
    if message not in errors:
        errors.append(message)


def add_warning(warnings: list[str], message: str) -> None:
    add_error(warnings, message)
