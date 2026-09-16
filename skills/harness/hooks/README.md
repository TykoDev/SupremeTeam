# Runtime Harness Hooks

Deterministic enforcement for the Action Realization and Trajectory Regulation
layers defined in [`../../harness-doctrine.md`](../../harness-doctrine.md), plus
the save lifecycle writer and the registration diagnostics.

| File | Event | Layer | Behavior |
|------|-------|-------|----------|
| `pre_tool_use.py` | `PreToolUse` | 3 | Blocks dangerous shell commands, writes into a frozen or guarded boundary, and direct edit-tool writes to core run files. |
| `post_tool_use.py` | `PostToolUse` | 4 | Records trajectory observations (repeated failures, empty-output streaks, oscillation) and refreshes the pinned run's heartbeat from real host activity. |
| `user_prompt_submit.py` | `UserPromptSubmit` | entry routing | Advises routing lifecycle work through `admiral`; reinforces the session pin when a run is active. |
| `save_run.py` | CLI | persistence | The only writer of `_state.md`, `_lock.md`, `_audit-trail.md`, `_journal.json`, and `_history/`. |
| `_saves.py` | helper | persistence | Shared reader that classifies saved state; used by readiness, the prompt hook, and the gate checker. |
| `_state.py` | helper | 3 and 4 | Fail-open state helper: project-root resolution, guard state, trajectory records, heartbeat refresh. |
| `verify_registration.py` | diagnostic | - | Inspects host-native hook config without mutating it; rejects stale same-name scripts. |
| `repair_registration.py` | diagnostic | - | Previews a scoped registration repair; applies only with `--apply`. |
| `check_readiness.py` | diagnostic | - | Reports Python, hooks, and save state as an independent capability map. |

## Design guarantees

- Stdlib only. No `pip install`.
- Fail open: a harness fault cannot block or crash the host loop.
- Inert on the strong case: rules fire only on mechanically certain signals.
- Config inspection never claims the host actually fired a hook. The readiness
  capability map reports `hooks_observed: unverified` until a hook runs.

## Save lifecycle

`save_run.py` is the single writer of the run record
([`../../save-protocol.md`](../../save-protocol.md) §3):

```bash
python skills/harness/hooks/save_run.py create     --run-id <run> --evidence <path>
python skills/harness/hooks/save_run.py checkpoint --run-id <run> --expect-revision <n> --evidence <path>
python skills/harness/hooks/save_run.py heartbeat  --run-id <run>
python skills/harness/hooks/save_run.py complete   --run-id <run>
python skills/harness/hooks/save_run.py block      --run-id <run> --reason "<why>"
python skills/harness/hooks/save_run.py release    --run-id <run>
python skills/harness/hooks/save_run.py recover    --run-id <run> --reason "<why>" [--rollback]
python skills/harness/hooks/save_run.py status     --run-id <run>
```

`create` runs the write/read/delete probe and refuses while another run holds the
pin. Each checkpoint snapshots the previous revision, registers evidence hashes,
and publishes state, lock, and pointer atomically behind `_journal.json`. An
interrupted publish is visible as `interrupted` and repaired with
`recover --rollback`. Exit 0 is `ok`, exit 1 is `refused` (a contract violation
to resolve, never to work around by hand-editing files), exit 2 is `degraded`
(the write failed and nothing coherent was published).

## Registration

Normal skill installation does not register hooks. Register only on explicit
opt-in:

```bash
bash ./scripts/install.sh --register-hooks
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks
```

The installer writes host-native configuration:

| Host | Config | Verifiable |
|------|--------|-----------|
| Codex | `~/.codex/hooks.json` | yes |
| Claude Code | `~/.claude/settings.json` | yes |
| Copilot | `~/.config/github-copilot/hooks.json` | yes |
| Cursor | `~/.cursor/plugins/local/supremeteam-hooks/` | no |
| OpenCode | `~/.config/opencode/plugins/supremeteam-hooks.js` | no |

Codex, Claude Code, and Copilot write native JSON hook configuration that
`verify_registration.py` can inspect. Cursor and OpenCode load a plugin package,
so they are written but not machine-verifiable, and they are not `--host` values
for the verifier. `--scope user|project|local` selects which file to write;
`--dry-run` prints a diff and writes nothing.

After registration, open `/hooks` or restart the host if it requires hook review
or reload.

Manual helper. It does not define the hook set: the required hooks, matchers,
command format, and config paths all come from `verify_registration.py` and
`repair_registration.py` under `--hook-root`, so a first-time install and a later
repair cannot write different registrations for the same host. After writing, it
re-reads the file and asks the verifier whether each command is executable.

```bash
python scripts/install_hooks.py --hook-root "$HOME/.agents/skills/harness/hooks" --target codex
python scripts/install_hooks.py --hook-root "$HOME/.agents/skills/harness/hooks" --target claude --scope project --dry-run
```

Verification and repair:

```bash
python skills/harness/hooks/verify_registration.py --host auto
python skills/harness/hooks/check_readiness.py --host auto
python skills/harness/hooks/check_readiness.py --host auto --require-active-run
python skills/harness/hooks/repair_registration.py --host claude --scope project          # preview
python skills/harness/hooks/repair_registration.py --host claude --scope project --apply  # with owner approval
```

`--require-active-run` is for a resume. A fresh intake has no run yet, so
requiring one there always reports not ready.

## Matcher scope

`PreToolUse` matches write-capable and shell tools, because Layer 3 must block an
edit or command before it lands. `PostToolUse` watches command actions and other
supported tool names where the host exposes a post-tool event.
`UserPromptSubmit` has no matcher in hosts that model it as a prompt-lifecycle
event.

## Guard and freeze integration

`pre_tool_use.py` enforces boundaries recorded by `guard` and `freeze` at
`.harness-state/guard-state.json`. The state helper resolves that under
`SUPREMETEAM_PROJECT_DIR` first, then known host workspace variables, then the
nearest ancestor of the working directory that holds `skillset-saves/`,
`.harness-state/`, or `.git`, then the working directory itself, then an
isolated OS temp fallback. `save_run.py`, `check_readiness.py`, and
`verify_registration.py` default their project root the same way, so a script
run from `skills/` never scatters state into a subdirectory.

```json
{
  "frozen_globs": ["src/payments/**", "infra/*.tf"],
  "blocked_globs": ["**/secrets/**"],
  "allow_dangerous": false
}
```

When the file is absent or empty, boundary rules are inert and only the built-in
destructive-pattern guard applies.

## Heartbeat refresh

With the hooks registered, `post_tool_use.py` refreshes the pinned run's
heartbeat from real host activity: only for a payload carrying a host session id,
only on a held, pinned, coherent, non-interrupted, still-fresh lock, throttled to
once per five minutes, and always written through `save_run.py heartbeat` as the
lock owner. It never revives a stale lock. Without hooks, a run goes stale after
30 minutes without an explicit checkpoint.

## Manual smoke test

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | python pre_tool_use.py
echo '{"prompt":"design this system"}' | python user_prompt_submit.py
python verify_registration.py --host auto
```

## Regression tests

```bash
python -m unittest discover -s skills/harness/hooks -p "test_*.py"
```

`test_hooks.py` covers the three lifecycle hooks, registration verification, and
readiness. `test_hooks_hardening.py` covers path and payload hardening,
`test_hooks_lifecycle.py` the save lifecycle writer, and
`test_hooks_observed.py` the observed-versus-configured distinction.
