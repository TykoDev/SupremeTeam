# Runtime Harness Hooks

Deterministic enforcement for the **Action Realization** (Layer 3) and **Trajectory
Regulation** (Layer 4) lifecycle layers defined in `../../harness-doctrine.md`. These are the
*only* place SupremeTeam can intercept a tool call deterministically, because skills are
instructions running inside the Claude Code host loop and do not own that loop.

| Hook | Event | Layer | Behavior |
| --- | --- | --- | --- |
| `pre_tool_use.py` | `PreToolUse` | 3 — Action Realization | Blocks dangerous shell commands and writes into a frozen/guarded boundary, *before* execution. |
| `post_tool_use.py` | `PostToolUse` | 4 — Trajectory Regulation | Detects repeated failing commands, empty-output streaks, and oscillation; injects a recovery hint. |
| `user_prompt_submit.py` | `UserPromptSubmit` | — Entry Routing | Injects an advisory reminder steering delivery-lifecycle requests through `admiral` (the primary entry orchestrator) when no Admiral run is active; reinforces the session pin when one is. Stays silent on slash commands. See `../../routing-doctrine.md`. |
| `verify_registration.py` | — (diagnostic) | — | Confirms the three hooks above are registered in a host `settings.json`. Run by `admiral` at intake; emits a `REGISTER_PROMPT` + ready-to-paste block when any are missing. Exit 0 = registered, 1 = missing, 2 = unknown. |
| `_state.py` | — | — | Shared, fail-open state helper (stdlib only). |

## Design guarantees

- **Stdlib only.** Runs on any host Python 3.8+; no `pip install`.
- **Fail open (doctrine §3).** Any internal error exits 0 and lets the action proceed. A
  harness fault can never block or crash the host loop.
- **Inert on the strong case (doctrine §0).** Every rule fires only on a mechanically certain
  signal — a literal destructive pattern, a path inside a recorded boundary, or an identical
  action repeating/oscillating. Ambiguous intent triggers nothing.

## Installation

Hook registration lives in the host's `settings.json`, which is **project/host-specific** and
is owned by the **`update-config`** skill — do not commit a `settings.json` into the skills
tree. Ask `update-config` to register the two hooks, or add this block manually:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|Edit|Write|NotebookEdit",
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/SupremeTeam/harness/hooks/pre_tool_use.py\"" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash|PowerShell",
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/SupremeTeam/harness/hooks/post_tool_use.py\"" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "python \"$CLAUDE_PROJECT_DIR/SupremeTeam/harness/hooks/user_prompt_submit.py\"" }
        ]
      }
    ]
  }
}
```

On Windows, replace `python` with `py -3` (or the host's interpreter) as appropriate. Adjust the
path if `SupremeTeam/` is not directly under `$CLAUDE_PROJECT_DIR`.

**`UserPromptSubmit` has no matcher** — it is a prompt-lifecycle event, not a tool event, so it
runs once per user turn regardless of which tools follow. It only ever *adds context*
(`additionalContext`); it never blocks a prompt, and it fails open like the other two hooks.

**Matcher scope (by design).** `PreToolUse` matches the write-capable tools
(`Bash|PowerShell|Edit|Write|NotebookEdit`) because Layer 3 must be able to block an edit or a
write before it lands. `PostToolUse` matches **only** `Bash|PowerShell`: Layer 4 trajectory
regulation watches *command* actions (the loops, retries, and empty-output streaks that degrade a
run), not file edits, so `Edit`/`Write` are intentionally excluded from the post matcher. The
`_signature()` helper in `post_tool_use.py` still folds in `file_path` so the same helper keeps
working unchanged if a host ever adds `Edit`/`Write` to the post matcher — it is forward-compat
scaffolding, not an indication that edits are tracked today.

## Guard / freeze integration

`pre_tool_use.py` enforces the boundary recorded by the `guard` and `freeze` skills at
`.harness-state/guard-state.json` (under `$CLAUDE_PROJECT_DIR`, else the OS temp dir):

```json
{
  "frozen_globs":  ["src/payments/**", "infra/*.tf"],
  "blocked_globs": ["**/secrets/**"],
  "allow_dangerous": false
}
```

When the file is absent or empty (the default), the boundary rules are inert and only the
built-in destructive-pattern guard applies. The `unfreeze` skill clears `frozen_globs`.

## Manual smoke test

```bash
# Action Realization — expect a deny envelope:
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python pre_tool_use.py

# Trajectory Regulation — repeat 3x with a failing response, expect a hint on the 3rd:
echo '{"session_id":"t","tool_name":"Bash","tool_input":{"command":"ls /nope"},"tool_response":{"stderr":"No such file"}}' | python post_tool_use.py

# Entry Routing — natural-language prompt with no active run, expect an admiral routing reminder:
echo '{"prompt":"design this system"}' | python user_prompt_submit.py
# Slash command, expect silence (deterministic host routing):
echo '{"prompt":"/freeze src/payments"}' | python user_prompt_submit.py

# Registration check — prints a per-hook status table; exit 0 registered / 1 missing / 2 unknown:
python verify_registration.py; echo "exit=$?"
```

## Automated regression tests

Run the stdlib regression suite after any hook change:

```bash
python -m unittest discover -s SupremeTeam/harness/hooks -p "test_*.py"
```

Coverage includes dangerous-command allow/deny behavior, frozen-boundary read-vs-write behavior, leading-wildcard blocked globs such as `**/secrets/**`, malformed JSON fail-open behavior, repeated failing commands, empty-output streaks, non-progressing A,B,A,B oscillation, and entry-routing behavior (route reminder on natural language, silence on slash commands, session-pin reinforcement on an active run, and not-active classification of a delivered run).
