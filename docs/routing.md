# Entry Routing

Supreme Team's catalog is description-routed: a host assistant picks a skill by
matching the request against skill descriptions. Without a routing rule, a
request like "design this system" or "investigate this bug" would land directly
on a sub-orchestrator and skip admiral's intake, persistence, and gatekeeping.
The **entry-routing doctrine** (`skills/routing-doctrine.md`) closes that gap by
making **admiral the primary entry orchestrator** — the single front door for
the entire delivery lifecycle.

## Skill Tiers

| Tier | Skills | Entry behavior |
|------|--------|----------------|
| **Entry orchestrator** | `admiral` | The front door. All lifecycle work initiates here. |
| **In-scope (must defer)** | `design/commander`, `build/build-management`, `review/code-chief`, `skill-maker`, `investigate`, `session-memory`, `gatekeeper-admiral` | Components of the Admiral pipeline. When reached **without an active Admiral handoff**, they hand off to `admiral` first. |
| **Internal specialists** | every skill under `design/`, `build/`, `review/` not listed above (e.g. `architect`, `bob-the-builder`, `mr-robot`, `cso`, the stage gatekeepers) | Only ever reached via their owning sub-orchestrator; never a user entry point. |
| **Standalone tools** | `safety-guardrails/*`, `browser-automation/*`, `release-and-deployment/*`, `testing-and-qa/*` (plus the host `update-config` skill) | Out of routing scope. May be invoked directly at any time. |

## Routing Precedence

When a new user turn arrives, the entry is resolved in this order:

1. **Active Admiral run.** If a run is active (`skillset-saves/` lock held /
   `session_pin: true` and not `DELIVERED`), the input belongs to that run and is
   routed to the active sub-orchestrator. No parallel skill is forked.
2. **Explicit standalone tool.** A direct request for a Tier-4 tool runs directly.
3. **Explicit slash command.** A `/<skill>` command is deterministic host
   routing; it is honored. If it targets an in-scope skill, that skill's
   active-handoff check still applies.
4. **Default → admiral.** Any other delivery-lifecycle request initiates through
   admiral.

There is **no bypass keyword**. Standalone tools remain reachable only because
they are out of scope (Tier 4), not via an opt-out.

## The Active-Handoff Check (loop guard)

Every in-scope skill performs this check before doing work. It is also the guard
that keeps admiral's own delegations from bouncing back to admiral. An **active
Admiral handoff** is present when any of these is true:

- the delegation prompt contains a `### Save Context` block, or
- an active run lock / `session_pin: true` exists under `skillset-saves/`, or
- the invocation explicitly frames the skill as the owning sub-orchestrator for a
  named boundary (admiral's handoff template).

If a handoff is present, the skill proceeds normally. If not (a cold/direct
invocation for lifecycle work), it starts admiral first, lets it run intake,
persistence, and gatekeeping, then accepts the delegation back. Because admiral's
delegations always carry the handoff signal, a delegated call passes the check
immediately and never re-bootstraps admiral.

## Session Pinning

Once a run is in any `*_ACTIVE`, `*_GATE_PENDING`, or `*_GATE_REVISE` state with
`_lock.md` held, admiral sets `session_pin: true`. Every subsequent user input in
the same session is treated as input to the active run — even when the user does
not say "admiral" — and is routed to the active sub-orchestrator. The pin clears
only on `RUN_COMPLETE` (`DELIVERED`), the command `release admiral` /
`/exit-admiral`, or lock staleness.

## Deterministic Reinforcement (hook)

`harness/hooks/user_prompt_submit.py` is a `UserPromptSubmit` hook that fires on
every fresh user prompt and injects an advisory reminder pointing at admiral when
no active run is detected, and reinforces the session pin when a run is in
progress. It stays silent for explicit slash commands, is stdlib-only, and fails
open. Registration lives in the host `settings.json` and is owned by the
`update-config` skill.

Because this deterministic layer only works once the hook is registered, admiral
verifies registration at intake via `harness/hooks/verify_registration.py`. Until
the `user_prompt_submit.py` hook is registered, entry routing falls back to the
advisory layer (this doctrine plus the skill descriptions and per-skill
active-handoff checks). See [harness.md](harness.md).

## Why It Matters

Initiating through admiral guarantees every lifecycle run gets the grill-me
intake interview, a persisted run under `skillset-saves/` with a lock and session
pin, MCP registry freshness checks, execution-mode re-probing, and
gatekeeper-admiral validation at every boundary. A request that enters through a
sub-orchestrator directly skips all of these — the exact failure this doctrine
prevents.
