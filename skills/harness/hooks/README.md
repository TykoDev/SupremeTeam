# Runtime Harness Hooks

Deterministic enforcement for the **Action Realization** and **Trajectory
Regulation** lifecycle layers defined in `../../harness-doctrine.md`.

| Hook | Event | Layer | Behavior |
|------|-------|-------|----------|
| `pre_tool_use.py` | `PreToolUse` / pre-tool | 3 | Blocks dangerous shell commands and writes into a frozen/guarded boundary before execution. |
| `post_tool_use.py` | `PostToolUse` / post-tool | 4 | Detects repeated failing commands, empty-output streaks, and oscillation; injects or logs a recovery hint where the host supports it. |
| `user_prompt_submit.py` | `UserPromptSubmit` / prompt-submit | Entry routing | Adds an advisory reminder steering lifecycle requests through `admiral`; reinforces the session pin when one is active. |
| `verify_registration.py` | diagnostic | - | Checks host-native hook config and rejects stale/unrelated same-name hook scripts. |
| `_state.py` | helper | - | Shared fail-open state helper. |

## Design Guarantees

- Stdlib only; no `pip install`.
- Fail open; a harness fault cannot block or crash the host loop.
- Inert on the strong case; rules fire only on mechanically certain signals.

## Installation

Normal skill installation does not register hooks. Register hooks only when the
user explicitly opts in:

```bash
bash ./scripts/install.sh --register-hooks
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks
```

The installer writes host-native configuration:

| Host | Config |
|------|--------|
| Codex | `~/.codex/hooks.json` |
| Claude Code | `~/.claude/settings.json` |
| Cursor | `~/.cursor/plugins/local/supremeteam-hooks/` |
| OpenCode | `~/.config/opencode/plugins/supremeteam-hooks.js` |

After registration, open `/hooks` or restart the host if it requires hook review
or reload.

Manual helper:

```bash
python scripts/install_hooks.py --hook-root "$HOME/.agents/skills/harness/hooks" --target codex
```

Verification:

```bash
python skills/harness/hooks/verify_registration.py --host auto
python skills/harness/hooks/verify_registration.py --host all
```

## Matcher Scope

`PreToolUse` matches write-capable tools and shell tools because Layer 3 must be
able to block an edit or command before it lands. `PostToolUse` watches command
actions and other supported tool names where the host exposes a post-tool event.
`UserPromptSubmit` has no matcher in hosts that model it as a prompt-lifecycle
event.

## Guard / Freeze Integration

`pre_tool_use.py` enforces boundaries recorded by `guard` and `freeze` at:

```text
.harness-state/guard-state.json
```

The state helper resolves that under `SUPREMETEAM_PROJECT_DIR` first, then known
host workspace variables, then the current working directory, then the OS temp
fallback.

Example state:

```json
{
  "frozen_globs": ["src/payments/**", "infra/*.tf"],
  "blocked_globs": ["**/secrets/**"],
  "allow_dangerous": false
}
```

When the file is absent or empty, boundary rules are inert and only the built-in
destructive-pattern guard applies.

## Manual Smoke Test

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python pre_tool_use.py
echo '{"prompt":"design this system"}' | python user_prompt_submit.py
python verify_registration.py --host auto
```

## Automated Regression Tests

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
```
