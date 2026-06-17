# Runtime Harness

The runtime harness adapts the **interface** between the model and its
environment — not the model itself. It is Supreme Team's adaptation of
*LIFE-HARNESS: Adapting the Interface, Not the Model*, and is specified in
`skills/harness-doctrine.md`. It gives skill authors and gatekeepers a shared
vocabulary, a failure taxonomy, and a deterministic enforcement layer where the
host supports it.

## Model-Agnostic Principle

Supreme Team runs across whatever backbone the host provides. Every harness
intervention must **rescue a weak backbone without degrading a strong one**. An
intervention that helps a small/local model but interferes with a competent
model's correct action is a defect, not a feature. When in doubt, the
intervention does nothing.

## The Four Lifecycle Layers

| # | Layer | When it acts | What it does |
|---|-------|--------------|--------------|
| 1 | **Environment Contract** | before interaction | Make stable tool, policy, and format constraints explicit (design-doctrine, grill-me intake, MCP registry, intake briefs). |
| 2 | **Procedural Skill** | task conditioning | Retrieve a compact, reusable procedure for the current task and surface it before work starts (the skill library itself, session-memory learnings). |
| 3 | **Action Realization** | before execution | Validate, canonicalize, or **block** a generated action before it touches the environment (`safety-guardrails`, save-protocol write probe, **`pre_tool_use.py`**). |
| 4 | **Trajectory Regulation** | after execution | Detect degenerate patterns (loops, stagnation, empty-output streaks, budget exhaustion) and inject recovery (gatekeepers, session-memory, admiral rewind, **`post_tool_use.py`**). |

Skills are instructions running *inside* the host loop and do not own that loop.
The only place Supreme Team can deterministically intercept a tool call is a
host hook or plugin lifecycle, so Layers 3 and 4 have both an advisory expression
(skill prose) and, where the host supports compatible hooks, a deterministic one
(`harness/hooks/`).

## Hooks

Located at `skills/harness/hooks/`. Stdlib-only (Python 3.8+), **fail open** (any
internal error exits 0 and lets the action proceed), and inert on the strong case
(each rule fires only on a mechanically certain signal).

| Hook | Event | Layer | Behavior |
|------|-------|-------|----------|
| `pre_tool_use.py` | `PreToolUse` | 3 | Blocks dangerous shell commands and writes into a frozen/guarded boundary, *before* execution. |
| `post_tool_use.py` | `PostToolUse` | 4 | Detects repeated failing commands, empty-output streaks, and A,B,A,B oscillation; injects a recovery hint. |
| `user_prompt_submit.py` | `UserPromptSubmit` | — | Advisory entry-routing reminder steering lifecycle requests through admiral when no run is active; reinforces the session pin when one is. Silent on slash commands. |
| `verify_registration.py` | diagnostic | — | Confirms host-native hook config points at Supreme Team's three hooks (exit 0 registered / 1 missing / 2 unknown). Run by admiral at intake; emits a `REGISTER_PROMPT` when any are missing. |

### Registration

Hook registration is explicit opt-in in the installers:
`-RegisterHooks` on Windows and `--register-hooks` on macOS/Linux. The installer
writes host-native config: Codex `~/.codex/hooks.json`, Claude Code
`~/.claude/settings.json`, Cursor a local `supremeteam-hooks` plugin, and
OpenCode a local plugin script. See `skills/harness/hooks/README.md`. Admiral
never blocks a run on a failed registration check — it warns and continues, and
flags that entry routing is advisory-only until the prompt hook is registered.

### Guard / freeze integration

`pre_tool_use.py` enforces the boundary recorded by the `guard` and `freeze`
skills at `.harness-state/guard-state.json` under `SUPREMETEAM_PROJECT_DIR`, a
known host workspace variable, the current working directory, or the OS temp
fallback: `frozen_globs`, `blocked_globs`, and `allow_dangerous`. When the file
is absent or empty (the default), only the built-in destructive-pattern guard
applies. `unfreeze` clears `frozen_globs`.

## Deterministic Gate Engine

Located at `skills/harness/gatekeeper/`. The gate-side companion to the hooks:
a shared, stdlib-only engine (`_gatecheck.py`) behind every `gatekeeper-*` skill's
`scripts/check.py`. Each gate ships a thin wrapper that declares only its
boundary's required-artifact manifest and calls the engine, which locates itself
by walking up to the skill-set root — so the skills package independently of
their directory depth.

The engine reports **facts** (`PASS` / `FAIL` / `UNCHECKED`), never a verdict.
Unlike the hooks (which fail open), the gate engine **fails loud**: a gate that
cannot prove a package clean must never silently approve it (internal error →
exit `2`, blocking failure → non-zero exit). See [gatekeepers.md](gatekeepers.md)
and `skills/harness/gatekeeper/README.md`.

## Failure Taxonomy

When a recurring failure is observed, it is classified by the **earliest**
matching category so a downstream symptom never masks the root interface failure:

1. **Action-realization failure** — reasonable intent not submitted in executable
   form (plain-text "tool call", invalid args). → Layer 3.
2. **Environment-contract mismatch** — executable but violates tool bounds,
   ordering, or argument semantics. → Layer 1.
3. **Trajectory degeneration** — valid actions, but the episode loops, stagnates,
   or exhausts budget without progress. → Layer 4.
4. **Residual reasoning failure** — protocol followed but the logic is wrong.
   **Out of scope for the harness** — interface tricks must not paper over
   reasoning errors.

Categories 1–3 are harness-addressable; routing a category-4 reasoning failure to
a harness intervention is itself a doctrine violation.

## Engineering Non-Negotiables

Every harness intervention — a doctrine clause, a hook rule, a guard boundary —
must be **local and minimal**, **evidence-triggered**, **never override ambiguous
reasoning**, use **no oracle / hidden labels**, ship with a **mandatory
regression check**, and **fail open**. Hook changes must run the stdlib suite at
`harness/hooks/test_hooks.py` (or add an equivalent case); gate-engine changes run
`harness/gatekeeper/test_gatecheck.py`.

## Testing

```bash
# Hooks
python -m unittest discover -s skills/harness/hooks -p "test_*.py"

# Gate engine
python -m unittest discover -s SupremeTeam/harness/gatekeeper -p "test_*.py"
```
