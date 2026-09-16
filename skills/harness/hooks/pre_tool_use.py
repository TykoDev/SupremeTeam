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
    mechanically certain signal (a literal dangerous pattern or a path inside a
    recorded frozen boundary) — never on ambiguous intent — so a strong backbone
    is unaffected.

Block contract: prints the PreToolUse deny envelope to stdout and
exits 0. On any internal error it exits 0 silently (fail open), letting the
action proceed.
"""

import fnmatch
import re
import sys
from datetime import datetime, timezone

import _state

# Literal, unambiguous destructive shell patterns. Conservative on purpose:
# only catch commands that are almost never a legitimate agent action.
_DANGEROUS = [
    (r"\brm\s+(?:-\S+\s+)*--no-preserve-root", "recursive delete with --no-preserve-root"),
    # PowerShell / cmd equivalents of a recursive drive, root, or home wipe. The
    # target must be a *bare* root (C:\, /, ~, $HOME); a path underneath it does
    # not match, so `Remove-Item -Recurse -Force .\build` stays allowed.
    (r"\b(?:Remove-Item|ri|rd|rmdir|del|erase)\b(?=[^\n;|&]*\s-(?:Recurse|r)\b)[^\n;|&]*?\s['\"]?"
     r"(?:[A-Za-z]:[\\/]?|/|~|\$HOME|\$env:USERPROFILE)['\"]?(?:\s|$|;)",
     "recursive delete of a drive, root, or home target"),
    (r"\brd\s+/s\b[^\n;|&]*\s[A-Za-z]:\\?(?:\s|$)", "recursive removal of a drive root"),
    (r"\bformat(?:\.com)?\s+[A-Za-z]:(?:\s|$)", "format of a drive"),
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


# Tools whose input names a filesystem path we can match against a boundary.
_PATH_KEYS = ("file_path", "path", "notebook_path")

# Core save-protocol files with a single sanctioned writer (save_run.py).
_CORE_SAVE_FILE = re.compile(
    r"(?:^|/)skillset-saves/(?:_latest\.md|runs/[^/]+/(?:_state\.md|_lock\.md|_audit-trail\.md|_journal\.json|_history/[^/]+))$"
)
# The same files named anywhere inside a shell command (redirect, tee, cp, mv...).
_CORE_SAVE_TOKEN = re.compile(
    r"skillset-saves/(?:_latest\.md|runs/[^\s\"'/]+/(?:_state\.md|_lock\.md|_audit-trail\.md|_journal\.json|_history/))"
)
_CORE_SAVE_REASON = (
    "Blocked by harness Action Realization layer: core save files are written only by "
    "skills/harness/hooks/save_run.py (create/checkpoint/heartbeat/complete/release/recover) "
    "so revision lineage, history snapshots, and the audit trail stay coherent."
)

# Durable project Taste state has one sanctioned writer. This rule is limited
# to path-addressed edit tools: reads remain available and shell behavior is not
# guessed from ambiguous command text.
_TASTE_SAVE_PATH = re.compile(r"(?:^|/)skillset-saves/preferences/(?:taste\.(?:json|md)|taste\.journal\.jsonl|taste\.lock|_history(?:/.*)?)$")
_TASTE_SAVE_REASON = (
    "Blocked by harness Action Realization layer: durable project Taste records, views, "
    "history, journals, and locks are written only by skills/taste/taste_prefs.py. "
    "Use that command's mutation subcommands instead of an edit tool."
)

# The guard/freeze boundary record itself. Without this rule the boundary is
# self-liftable: a single write clearing frozen_globs, or setting
# allow_dangerous, disables the rules below before they ever run. One sanctioned
# writer (guard_state.py) keeps a release attributable and reversible.
_GUARD_STATE_PATH = re.compile(r"(?:^|/)\.harness-state/guard-state\.json$")
_GUARD_STATE_TOKEN = re.compile(r"\.harness-state/guard-state\.json")
_GUARD_STATE_REASON = (
    "Blocked by harness Action Realization layer: the guard/freeze boundary record is "
    "written only by skills/harness/hooks/guard_state.py "
    "(freeze/block/release/allow-dangerous/revoke-dangerous/read-only). Editing it directly "
    "would lift an owned boundary with no owner check and no released_at trail."
)


def _dangerous_lifted(guard: dict) -> bool:
    """True while destructive-pattern blocking is deliberately lifted.

    Accepts the legacy bare ``true`` (a permanent global kill-switch) and the
    owned grant guard_state.py writes, which carries an expiry so the lift is
    bounded. An expired or malformed grant leaves the block in force: a guard
    that cannot read its own grant must stay closed, not open.
    """
    grant = guard.get("allow_dangerous")
    if grant is True:
        return True
    if not isinstance(grant, dict):
        return False
    expires = grant.get("expires_at")
    if not expires:
        # guard_state.py always records an expiry, so a grant without one is
        # malformed. Fail closed: an unbounded lift is the state this rule exists
        # to prevent.
        return False
    try:
        deadline = datetime.strptime(str(expires), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) < deadline


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
# would violate the doctrine's Principles (inert on a competent action). When mutation
# cannot be determined, treat the command as non-mutating and let it proceed
# (fail open per Principles), rather than guessing.
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


def _glob_variants(glob: str) -> list:
    """Expand a guard glob into the fnmatch patterns a target path is checked
    against.

    Host tools report absolute target paths (``D:/proj/src/payments/x.py``,
    ``/home/u/proj/src/payments/x.py``) while guard globs are usually written
    relative to the project root (``src/payments/**``). ``fnmatch`` requires a
    full-string match, so a relative glob — one that does not start with a
    drive letter, ``/``, or ``**`` — is additionally matched with a leading
    ``*/`` prefix. The prefix anchors the glob's first literal segment at a
    path-separator boundary, so the absolute form of a frozen path is caught
    without loosening the boundary (``mysrc/payments/x.py`` still does not
    match ``*/src/payments/**``). Backslashes are normalized to forward
    slashes before matching.
    """
    g = str(glob).replace("\\", "/")
    base = g.rstrip("/")
    variants = [g, base + "/**"]
    is_relative = not (g.startswith("/") or g.startswith("**") or re.match(r"^[A-Za-z]:", g))
    if is_relative:
        variants += ["*/" + g, "*/" + base + "/**"]
    return variants


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
    _state.record_observation("PreToolUse", data)
    _state.refresh_run_heartbeat(data, "PreToolUse")
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    if not isinstance(tool_input, dict):
        return

    guard = _state.load_guard_state()

    # --- Rule A: dangerous shell patterns (action would deterministically harm)
    if tool_name in ("Bash", "PowerShell") and not _dangerous_lifted(guard):
        cmd = _command_text(tool_input)
        for pattern, label in _DANGEROUS:
            if re.search(pattern, cmd, re.IGNORECASE):
                _deny(
                    f"Blocked by harness Action Realization layer: {label}. "
                    f"If this is genuinely intended, the owner must lift the guard with "
                    f"'python skills/harness/hooks/guard_state.py allow-dangerous --owner <owner> "
                    f"--reason <why> --scope <operation>' (bounded by an expiry), or use a narrower command."
                )
        if _rm_wipes_root(cmd):
            _deny(
                "Blocked by harness Action Realization layer: recursive delete of a root/home/glob target. "
                "If this is genuinely intended, the owner must lift the guard with "
                "'python skills/harness/hooks/guard_state.py allow-dangerous --owner <owner> "
                "--reason <why> --scope <operation>' (bounded by an expiry), or use a narrower command."
            )

    # --- Rule B: write into a frozen/blocked boundary (guard & freeze boundary)
    frozen = list(guard.get("frozen_globs", []) or []) + list(guard.get("blocked_globs", []) or [])
    if frozen:
        # Path-naming tools (Edit/Write/NotebookEdit): match the declared target
        # path directly against the boundary — these are always writes.
        if tool_name in ("Edit", "Write", "NotebookEdit"):
            candidates = _written_paths(tool_input)
            for glob in frozen:
                variants = _glob_variants(glob)
                if any(fnmatch.fnmatch(p, v) for p in candidates for v in variants):
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

    # --- Rule D: read-only run. While an unreleased read_only record exists
    # (recorded by the `guard` skill through guard_state.py read-only, for an
    # investigation or audit that must not change the product surface), the only
    # writable locations are the record's allow globs (the run's own save path)
    # and the harness state directory; save_run.py keeps writing the run records
    # and Rule C still protects guard-state.json itself. An edit-tool write
    # elsewhere, or a mutating shell command that names no allowed path, is
    # denied. Read-only commands pass untouched.
    read_only = guard.get("read_only") or []
    if read_only:
        allow = [".harness-state/**"]
        for record in read_only:
            allow += [str(g) for g in (record.get("allow") or []) if g]
        run_ids = ", ".join(str(r.get("run_id", "?")) for r in read_only)
        reason = (
            f"Blocked by harness Action Realization layer: run {run_ids} is recorded read-only. "
            "Only the run's own save path may change; record the decision, then release the boundary with "
            "'python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <owner>' "
            "before changing anything else."
        )
        if tool_name in ("Edit", "Write", "NotebookEdit"):
            for target in _written_paths(tool_input):
                if not any(fnmatch.fnmatch(target, v) for g in allow for v in _glob_variants(g)):
                    _deny(reason)
        elif tool_name in ("Bash", "PowerShell"):
            cmd = _command_text(tool_input)
            if cmd and "save_run.py" not in cmd and _command_mutates(cmd):
                cmd_norm = cmd.replace("\\", "/")
                tokens = [t for g in allow for t in _glob_path_tokens(g)]
                if not any(_path_token_present(cmd_norm, token) for token in tokens):
                    _deny(reason)

    # --- Rule C: core save files have one writer (save_run.py). A direct edit
    # tool call on _state.md/_lock.md/_audit-trail.md/_latest.md/_journal.json
    # under skillset-saves would bypass revision lineage, the history snapshot,
    # and the append-only audit trail. A *mutating* shell command that names one
    # of those files (redirect, tee, cp, mv, Set-Content...) is denied the same
    # way unless it invokes save_run.py itself; read-only references pass. The
    # save reader still classifies an incoherent result as corrupt, so this is
    # a discipline aid, not the only line of defence.
    if tool_name in ("Edit", "Write", "NotebookEdit"):
        for target in _written_paths(tool_input):
            if _CORE_SAVE_FILE.search(target):
                _deny(_CORE_SAVE_REASON)
            if _TASTE_SAVE_PATH.search(target):
                _deny(_TASTE_SAVE_REASON)
            if _GUARD_STATE_PATH.search(target):
                _deny(_GUARD_STATE_REASON)
    elif tool_name in ("Bash", "PowerShell"):
        cmd = _command_text(tool_input)
        cmd_norm = cmd.replace("\\", "/") if cmd else ""
        if cmd and "save_run.py" not in cmd and _command_mutates(cmd) and _CORE_SAVE_TOKEN.search(cmd_norm):
            _deny(_CORE_SAVE_REASON)
        if cmd and "guard_state.py" not in cmd and _command_mutates(cmd) and _GUARD_STATE_TOKEN.search(cmd_norm):
            _deny(_GUARD_STATE_REASON)

    # No rule fired — stay silent and let the action proceed.


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail open: never let a harness fault block the host loop.
        sys.exit(0)
