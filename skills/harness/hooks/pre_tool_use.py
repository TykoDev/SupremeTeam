#!/usr/bin/env python3
"""
Action Realization hook (LIFE-HARNESS Layer 3) for SupremeTeam.

Runs as a Claude Code ``PreToolUse`` hook. It validates a generated action
*before* the host executes it and BLOCKS the ones that would deterministically
fail or violate an active guard/freeze boundary. This is the deterministic
expression of the otherwise-advisory ``safety-guardrails`` skills.

Doctrine (../../harness-doctrine.md):
  - section 3: local & minimal, evidence-triggered, fail open.
  - section 0: inert on a competent action. Every rule below fires only on a
    mechanically certain signal (a literal dangerous pattern or a path inside a
    recorded frozen boundary) — never on ambiguous intent — so a strong backbone
    is unaffected.

Block contract: prints the Claude Code PreToolUse deny envelope to stdout and
exits 0. On any internal error it exits 0 silently (fail open), letting the
action proceed.
"""

import fnmatch
import re
import sys

import _state

# Literal, unambiguous destructive shell patterns. Conservative on purpose:
# only catch commands that are almost never a legitimate agent action.
_DANGEROUS = [
    (r"\brm\s+-rf\s+(/|~|\$HOME|\*)(\s|$)", "recursive force-delete of a root/home/glob target"),
    (r"\brm\s+-rf\s+--no-preserve-root", "recursive delete with --no-preserve-root"),
    (r":\(\)\s*\{\s*:\|:&\s*\}\s*;:", "shell fork bomb"),
    (r"\bmkfs(\.\w+)?\s+/dev/", "filesystem format of a device"),
    (r"\bdd\b.*\bof=/dev/(sd|nvme|hd)", "raw disk overwrite via dd"),
    (r">\s*/dev/(sd|nvme|hd)\w*", "redirect over a raw block device"),
    (r"\bchmod\s+-R\s+0?00\s+/(\s|$)", "recursive chmod 000 on root"),
    # Force-push to a protected branch. Order-independent: two forward lookaheads
    # from `git push` assert (a) a force flag and (b) a protected-branch ref token
    # appear anywhere in the remainder, so `git push --force origin main` and
    # `git push origin main --force` are both caught. The branch token must be a
    # standalone ref (bounded by space/`:`/`/`) so `main-thing` does not trip it.
    (r"\bgit\s+push\b"
     r"(?=.*(?:--force\b|--force-with-lease\b|(?:^|\s)-f(?=\s|$)))"
     r"(?=.*(?:^|[\s:/])(?:main|master)(?:[\s:]|$))",
     "force-push to a protected branch (main/master)"),
]

# Tools whose input names a filesystem path we can match against a boundary.
_PATH_KEYS = ("file_path", "path", "notebook_path")


def _deny(reason: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(__import__("json").dumps(out))
    sys.exit(0)


def _command_text(tool_input: dict) -> str:
    # Bash uses "command"; PowerShell skills may use "command" too.
    return str(tool_input.get("command", "") or "")


def _written_paths(tool_input: dict) -> list:
    paths = []
    for k in _PATH_KEYS:
        v = tool_input.get(k)
        if isinstance(v, str) and v:
            paths.append(v.replace("\\", "/"))
    return paths


# A shell command counts as a *write* into a boundary only if it contains a
# mechanically detectable mutation: output redirection, a known file-mutating
# coreutil, an in-place editor, a mutating git subcommand, or a mutating
# PowerShell cmdlet/alias. A read-only command (cat/grep/ls/Get-Content) that
# merely *references* a frozen path is NOT a write and must pass — blocking it
# would violate harness-doctrine §0 (inert on a competent action). When mutation
# cannot be determined, treat the command as non-mutating and let it proceed
# (fail open / §0), rather than guessing.
_SHELL_MUTATION = re.compile(
    r">>?|>\|"                                                      # output redirection
    r"|(?<![\w.-])(?:rm|mv|cp|ln|dd|tee|truncate|shred|install|"    # mutating coreutils
    r"mkdir|rmdir|touch|chmod|chown|unlink|rename)(?![\w-])"
    r"|\bsed\s+-[a-z]*i|\bperl\s+-[a-z]*i\b"                        # in-place stream edit
    r"|\bgit\s+(?:add|commit|checkout|restore|reset|rm|mv|apply|stash|clean|push)\b"
    r"|(?<![\w.-])(?:Set-Content|Add-Content|Clear-Content|Out-File|"  # PS cmdlets
    r"Remove-Item|Move-Item|Copy-Item|New-Item|Rename-Item)(?![\w-])"
    r"|(?<![\w.-])(?:ni|ri|rni|mi|ci|sc|ac|clc)(?![\w-])",          # PS aliases
    re.IGNORECASE,
)


def _command_mutates(cmd: str) -> bool:
    return bool(_SHELL_MUTATION.search(cmd))


def _path_token_present(cmd_norm: str, token: str) -> bool:
    """True when `token` (a frozen-glob prefix like ``src/payments``) appears in
    the normalized command as a path token — preceded by start, whitespace,
    quote, equals, open paren, colon, or slash;
    and followed by ``/``, whitespace, quote, or end — so it matches
    ``src/payments`` and ``src/payments/old`` but not ``src/payments-archive``.
    """
    pat = r"(?:^|[\s\"'=(:/])" + re.escape(token) + r"(?:$|[\s\"'/):])"
    return bool(re.search(pat, cmd_norm))


def _glob_path_tokens(glob: str) -> list:
    """Return conservative literal path tokens for a guard glob.

    Prefix globs such as ``src/payments/**`` use the stable prefix first. Leading
    wildcard globs such as ``**/secrets/**`` have no prefix, so fall back to
    literal path segments (``secrets``). If a glob has no literal segment, return
    no tokens and fail open.
    """
    g = str(glob).replace("\\", "/")
    prefix = g.split("*")[0].rstrip("/")
    if prefix:
        return [prefix]
    tokens = []
    for part in g.split("/"):
        if part and not re.search(r"[*?\[\]]", part):
            tokens.append(part)
    return tokens


def main() -> None:
    data = _state.read_hook_input()
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        return

    guard = _state.load_guard_state()

    # --- Rule A: dangerous shell patterns (action would deterministically harm)
    if tool_name in ("Bash", "PowerShell") and not guard.get("allow_dangerous"):
        cmd = _command_text(tool_input)
        for pattern, label in _DANGEROUS:
            if re.search(pattern, cmd, re.IGNORECASE):
                _deny(
                    f"Blocked by harness Action Realization layer: {label}. "
                    f"If this is genuinely intended, the owner must lift the guard "
                    f"(set allow_dangerous in .harness-state/guard-state.json) or use a narrower command."
                )

    # --- Rule B: write into a frozen/blocked boundary (guard & freeze skills)
    frozen = list(guard.get("frozen_globs", []) or []) + list(guard.get("blocked_globs", []) or [])
    if frozen:
        # Path-naming tools (Edit/Write/NotebookEdit): match the declared target
        # path directly against the boundary — these are always writes.
        if tool_name in ("Edit", "Write", "NotebookEdit"):
            candidates = _written_paths(tool_input)
            for glob in frozen:
                g = str(glob).replace("\\", "/")
                if any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p, g.rstrip("/") + "/**") for p in candidates):
                    _deny(
                        f"Blocked by harness Action Realization layer: target is inside a frozen "
                        f"boundary ({glob}). Lift the freeze via the unfreeze skill before editing here."
                    )

        # Shell tools (Bash/PowerShell): only block when the command both mutates
        # AND names a frozen path. Read-only references (cat/grep/ls) pass — see
        # _command_mutates. The token match is a conservative prefix (it covers
        # the whole frozen subtree), which is acceptable for a block boundary.
        elif tool_name in ("Bash", "PowerShell"):
            cmd = _command_text(tool_input)
            if cmd and _command_mutates(cmd):
                cmd_norm = cmd.replace("\\", "/")
                for glob in frozen:
                    if any(_path_token_present(cmd_norm, token) for token in _glob_path_tokens(glob)):
                        _deny(
                            f"Blocked by harness Action Realization layer: a mutating command targets a "
                            f"frozen boundary ({glob}). Lift the freeze via the unfreeze skill before proceeding."
                        )

    # No rule fired — stay silent and let the action proceed.


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail open: never let a harness fault block the host loop.
        sys.exit(0)
