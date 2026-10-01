"""Read package scripts and Makefile recipes as command lines, without running them."""

from __future__ import annotations

import re
import shlex


COMMAND_OPTIONS_WITH_VALUES = frozenset(
    {
        "--cache",
        "--cache-folder",
        "--config",
        "--config-dir",
        "--cwd",
        "--dir",
        "--filter",
        "--package",
        "--prefix",
        "--registry",
        "--script-shell",
        "--userconfig",
        "--workspace",
        "--workspace-root",
        "-w",
        "-c",
        "-f",
    }
)
PACKAGE_MANAGER_OPTIONS_WITH_VALUES = {
    "bun": frozenset({"--config", "--cwd", "--filter", "--package"}),
    "npm": frozenset(
        {"--cache", "--cache-folder", "--globalconfig", "--package", "--prefix", "--registry", "--userconfig", "--workspace", "--workspace-root", "-w"}
    ),
    "pnpm": frozenset({"--dir", "--filter", "--package", "--workspace-concurrency", "--workspace-root", "-c", "-f"}),
    "yarn": frozenset({"--cache-folder", "--cwd", "--modules-folder", "--mutex", "--package", "--registry", "-c"}),
}
ENV_OPTIONS_WITH_VALUES = frozenset({"--chdir", "--split-string", "--unset", "-S", "-c", "-u"})
EXEC_OPTIONS_WITH_VALUES = frozenset({"--argv0", "-a"})
COMMAND_LOOKUP_OPTIONS = frozenset({"--help", "--version", "-V", "-v", "-h"})


def _script_token_name(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in {"'", '"'}:
        token = token[1:-1]
    name = re.split(r"[/\\]", token)[-1].lower()
    return re.sub(r"\.(?:cmd|exe|bat)$", "", name)


def _shell_tokens(value: str) -> list[str]:
    quoted_operators = {
        ";": "__SUPREMETEAM_QUOTED_SEMICOLON__",
        "&": "__SUPREMETEAM_QUOTED_AMPERSAND__",
        "|": "__SUPREMETEAM_QUOTED_PIPE__",
    }
    masked: list[str] = []
    quote: str | None = None
    escaped = False
    for char in value:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            masked.append(quoted_operators.get(char, char))
        elif char in {"'", '"'}:
            quote = char
            masked.append(char)
        elif char in "\r\n":
            masked.append(";")
        else:
            masked.append(char)
    lexer = shlex.shlex("".join(masked), posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    return list(lexer)


def _expand_env_split(tokens: list[str]) -> list[str]:
    if not tokens or _script_token_name(tokens[0]) != "env":
        return tokens
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--" or not token.startswith("-"):
            break
        option = token.split("=", 1)[0].lower()
        if option in {"-s", "--split-string"}:
            if "=" in token:
                command = token.split("=", 1)[1]
                end = index + 1
            elif index + 1 < len(tokens):
                command = tokens[index + 1]
                end = index + 2
            else:
                return tokens
            return tokens[:index] + _shell_tokens(command) + tokens[end:]
        index += 1
    return tokens


def _script_segments(scripts: dict[str, str]) -> list[list[str]]:
    segments: list[list[str]] = []
    for value in scripts.values():
        try:
            tokens = _expand_env_split(_shell_tokens(value))
        except ValueError:
            continue
        segment: list[str] = []
        for token in [*tokens, ";"]:
            if token in {";", "&", "&&", "||", "|"}:
                if segment:
                    segments.append(segment)
                segment = []
            else:
                segment.append(token)
    return segments


def _skip_command_options(
    tokens: list[str],
    index: int,
    options_with_values: frozenset[str] = COMMAND_OPTIONS_WITH_VALUES,
) -> int:
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return index + 1
        if not token.startswith("-"):
            break
        option = token.split("=", 1)[0].lower()
        index += 1
        if "=" not in token and option in options_with_values and index < len(tokens):
            index += 1
    return index


def _has_lookup_option(
    tokens: list[str],
    index: int,
    options_with_values: frozenset[str] = COMMAND_OPTIONS_WITH_VALUES,
) -> bool:
    while index < len(tokens):
        token = tokens[index]
        if token == "--" or not token.startswith("-"):
            return False
        option = token.split("=", 1)[0].lower()
        if option in COMMAND_LOOKUP_OPTIONS:
            return True
        index += 1
        if "=" not in token and option in options_with_values and index < len(tokens):
            index += 1
    return False


def _script_command_index(tokens: list[str], index: int = 0, depth: int = 0) -> int:
    if depth > 8:
        return len(tokens)
    while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
        index += 1
    if index >= len(tokens):
        return index

    name = _script_token_name(tokens[index])
    if name == "env":
        index = _skip_command_options(tokens, index + 1, ENV_OPTIONS_WITH_VALUES)
        while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
            index += 1
        return _script_command_index(tokens, index, depth + 1)
    if name == "command":
        if _has_lookup_option(tokens, index + 1):
            return len(tokens)
        index = _skip_command_options(tokens, index + 1)
        return _script_command_index(tokens, index, depth + 1)
    if name == "exec":
        index = _skip_command_options(tokens, index + 1, EXEC_OPTIONS_WITH_VALUES)
        return _script_command_index(tokens, index, depth + 1)
    if name in {"npx", "bunx"}:
        if _has_lookup_option(tokens, index + 1):
            return len(tokens)
        index = _skip_command_options(tokens, index + 1)
        return _script_command_index(tokens, index, depth + 1)
    if name in {"bun", "npm", "pnpm", "yarn"}:
        options_with_values = PACKAGE_MANAGER_OPTIONS_WITH_VALUES[name]
        if _has_lookup_option(tokens, index + 1, options_with_values):
            return len(tokens)
        subcommand_index = _skip_command_options(tokens, index + 1, options_with_values)
        if subcommand_index >= len(tokens) or _script_token_name(tokens[subcommand_index]) not in {"exec", "dlx", "run"}:
            return len(tokens)
        if _has_lookup_option(tokens, subcommand_index + 1, options_with_values):
            return len(tokens)
        index = _skip_command_options(tokens, subcommand_index + 1, options_with_values)
        return _script_command_index(tokens, index, depth + 1)
    return index


def script_uses_command(scripts: dict[str, str], command: str) -> bool:
    return any(
        index < len(tokens) and _script_token_name(tokens[index]) == command
        for tokens in _script_segments(scripts)
        for index in [_script_command_index(tokens)]
    )


def script_uses_python_module(scripts: dict[str, str], module: str) -> bool:
    for tokens in _script_segments(scripts):
        index = _script_command_index(tokens)
        if index >= len(tokens) or _script_token_name(tokens[index]) not in {"python", "python3", "py"}:
            continue
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if token == "-m" and index + 1 < len(tokens):
                name = _script_token_name(tokens[index + 1])
                if name == module or name.startswith(module + "."):
                    return True
                break
            if not token.startswith("-"):
                break
            index += 1
    return False


def script_uses_subcommand(scripts: dict[str, str], command: str, subcommand: str) -> bool:
    for tokens in _script_segments(scripts):
        raw_index = 0
        while raw_index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[raw_index]):
            raw_index += 1
        raw_name = _script_token_name(tokens[raw_index]) if raw_index < len(tokens) else ""
        options_with_values = PACKAGE_MANAGER_OPTIONS_WITH_VALUES.get(raw_name, COMMAND_OPTIONS_WITH_VALUES)
        lookup_only = raw_name in PACKAGE_MANAGER_OPTIONS_WITH_VALUES and _has_lookup_option(
            tokens, raw_index + 1, options_with_values
        )
        if raw_name == command and not lookup_only:
            raw_subcommand_index = _skip_command_options(tokens, raw_index + 1, options_with_values)
            if (
                raw_subcommand_index < len(tokens)
                and _script_token_name(tokens[raw_subcommand_index]) == subcommand
            ):
                if _has_lookup_option(tokens, raw_subcommand_index + 1, options_with_values):
                    continue
                return True
        index = _script_command_index(tokens)
        if index < len(tokens) and _script_token_name(tokens[index]) == command:
            if index + 1 < len(tokens) and _script_token_name(tokens[index + 1]) == subcommand:
                return True
    return False


def script_uses_node_server(scripts: dict[str, str]) -> bool:
    node_options_with_values = frozenset(
        {"--eval", "--import", "--input-type", "--loader", "--print", "--require", "-e", "-p", "-r"}
    )
    for tokens in _script_segments(scripts):
        index = _script_command_index(tokens)
        if index >= len(tokens) or _script_token_name(tokens[index]) != "node":
            continue
        index += 1
        while index < len(tokens):
            token = tokens[index]
            if token == "--":
                index += 1
                break
            if not token.startswith("-"):
                name = _script_token_name(token)
                return bool(re.search(r"(?i)(?:^|[/_.-])(server|api)(?:$|[/_.-])", name))
            option = token.split("=", 1)[0].lower()
            index += 1
            if "=" not in token and option in node_options_with_values:
                index += 1
    return False


def _makefile_runtime_recipe(recipe: str) -> bool:
    scripts = {"makefile": recipe}
    return (
        any(
            script_uses_command(scripts, command)
            for command in (
                "bun", "cargo", "deno", "dotnet", "flask", "go", "gradle", "gunicorn",
                "java", "mvn", "node", "parcel", "pnpm", "python", "ruby", "uvicorn",
                "astro", "next", "nuxt", "svelte", "vite", "webpack", "yarn",
            )
        )
        or any(
            script_uses_subcommand(scripts, manager, subcommand)
            for manager in ("bun", "npm", "pnpm", "yarn")
            for subcommand in ("dlx", "exec", "run")
        )
    )


def makefile_recipe(lines: list[str], target: str, seen: set[str] | None = None) -> str | None:
    seen = set() if seen is None else seen
    if target in seen:
        return None
    seen.add(target)
    target_pattern = re.compile(rf"^\s*{re.escape(target)}\s*:(?P<inline>.*)$")
    for index, line in enumerate(lines):
        match = target_pattern.match(line)
        if not match:
            continue
        inline = match.group("inline").strip()
        if ";" in inline:
            recipe = inline.split(";", 1)[1].strip()
            if recipe:
                return re.sub(r"^[@+-]+\s*", "", recipe)
            prerequisites = inline.split(";", 1)[0].strip().split()
        else:
            prerequisites = inline.split()
        recipes: list[str] = []
        for candidate in lines[index + 1:]:
            if not candidate.strip():
                continue
            if not candidate[:1].isspace():
                break
            if candidate.lstrip().startswith("#"):
                continue
            recipe = re.sub(r"^[@+-]+\s*", "", candidate.strip())
            if recipe:
                recipes.append(recipe)
        for recipe in recipes:
            if _makefile_runtime_recipe(recipe):
                return recipe
        for prerequisite in prerequisites:
            recipe = makefile_recipe(lines, prerequisite, seen)
            if recipe:
                return recipe
    return None


def makefile_runtime_signals(text: str) -> tuple[bool, bool]:
    frontend = False
    backend = False
    lines = text.splitlines()
    for target in ("dev", "run", "serve"):
        recipe = makefile_recipe(lines, target)
        if not recipe:
            continue
        scripts = {"makefile": recipe}
        frontend = frontend or any(script_uses_command(scripts, tool) for tool in ("vite", "next", "astro", "nuxt", "svelte", "webpack", "parcel"))
        backend = backend or any(script_uses_command(scripts, tool) for tool in ("uvicorn", "gunicorn", "flask", "django", "fastapi"))
        backend = backend or any(
            script_uses_python_module(scripts, module)
            for module in ("uvicorn", "gunicorn", "flask", "django", "fastapi")
        )
        backend = backend or script_uses_node_server(scripts)
    return frontend, backend
