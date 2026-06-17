# Entry Routing Doctrine

Binding rule for how a fresh user request enters the SupremeTeam catalog. **`admiral`
is the primary entry orchestrator** — the single front door for the entire delivery
lifecycle. Every delivery-lifecycle request is initiated through `admiral` so that one
intake, one save-protocol run, and one cross-stage gatekeeper govern the whole pipeline.

This doctrine fixes the gap that descriptions alone cannot close: the catalog is
description-routed, so without a routing rule a request like "design this system" or
"investigate this bug" would land directly on a sub-orchestrator or utility, skipping
Admiral's intake, persistence, and gatekeeping.

## 1. Skill Tiers

| Tier | Skills | Entry behavior |
| --- | --- | --- |
| **Entry orchestrator** | `admiral` | The front door. All lifecycle work initiates here. |
| **In-scope (must defer)** | `design/commander`, `build/build-management`, `review/code-chief`, `skill-maker`, `investigate`, `session-memory`, `gatekeeper-admiral` | Components of the Admiral pipeline. When reached **without an active Admiral handoff**, they hand off to `admiral` first instead of running standalone. |
| **Internal specialists** | every skill under `design/`, `build/`, `review/` not listed above (e.g. `architect`, `planner`, `bob-the-builder`, `mr-robot`, `cso`, the stage gatekeepers) | Only ever reached via their owning sub-orchestrator; never a user entry point. |
| **Standalone tools** | `safety-guardrails/*` (`guard`, `freeze`, `unfreeze`, `careful`), `browser-automation/*`, `release-and-deployment/*`, `testing-and-qa/*`, `update-config` | Out of routing scope. May be invoked directly at any time. |

## 2. Routing Precedence

When a new user turn arrives, resolve the entry in this order:

1. **Active Admiral run.** If a run is active (`skillset-saves/` lock held / `session_pin: true`
   and not `DELIVERED`), the input belongs to that run. Route it to the active
   sub-orchestrator per Admiral's Session Routing contract. Do not fork a parallel skill.
2. **Explicit standalone tool.** A direct request for a Tier-4 standalone tool runs
   directly (no Admiral).
3. **Explicit slash command.** A `/<skill>` command is deterministic host routing; honor it.
   If it targets an in-scope skill, that skill's Entry Routing check (§3) still applies.
4. **Default → `admiral`.** Any other delivery-lifecycle request (design, build, review,
   ship, investigate, checkpoint/resume, gate validation, skill/team creation) initiates
   through `admiral`.

There is **no bypass keyword**. In-scope lifecycle work is not run standalone; standalone
tools remain reachable only because they are out of scope (Tier 4), not via an opt-out.

## 3. The Active-Handoff Check (loop guard)

Every in-scope skill performs this check before doing work. It is also the guard that keeps
Admiral's own delegations from bouncing back to Admiral.

An **active Admiral handoff** is present when **any** of these is true:

- the delegation prompt contains a `### Save Context` block, or
- an active run lock / `session_pin: true` exists under `skillset-saves/`, or
- the invocation explicitly frames this skill as the owning sub-orchestrator for a named
  boundary (Admiral's handoff template).

Resolution:

- **Handoff present** → proceed normally; you are running inside an Admiral run.
- **No handoff (cold/direct invocation for lifecycle work)** → do **not** run standalone.
  Start `admiral` first, let it run intake, persistence, and gatekeeping, then accept the
  delegation back. When Admiral delegates here it always includes the handoff signal, so a
  delegated call passes this check immediately and never re-bootstraps Admiral.

## 4. Deterministic Reinforcement (hook)

`harness/hooks/user_prompt_submit.py` is a prompt-submit hook that fires on every fresh
user prompt and injects a routing reminder pointing at `admiral` when no active run is
detected. It is advisory (it cannot own the host loop — see `harness-doctrine.md`), stdlib
only, and fail-open. It stays silent for explicit slash commands and reinforces the active
run's session pin when a run is in progress. Registration lives in the host-native hook
configuration or plugin layer and is installed only when explicitly requested (see
`harness/hooks/README.md`).

Because this deterministic layer only works once the hook is registered, Admiral verifies
registration at intake by running `harness/hooks/verify_registration.py` (its **Harness Hook
Registration** contract). When any of the three hooks is missing, the verifier emits a
`REGISTER_PROMPT` and Admiral asks the user whether to rerun the installer with
`-RegisterHooks` / `--register-hooks`. Until the prompt-submit hook is registered, entry
routing falls back to the advisory layer (this doctrine plus the skill descriptions and
per-skill Entry Routing checks).

## 5. Why This Matters

Initiating through Admiral guarantees every lifecycle run gets: the grill-me intake
interview, a persisted run under `skillset-saves/` with a lock and session pin, MCP registry
freshness checks, mode re-probing, and `gatekeeper-admiral` validation at every boundary.
A request that enters through a sub-orchestrator directly skips all of these, which is the
exact failure this doctrine prevents.
