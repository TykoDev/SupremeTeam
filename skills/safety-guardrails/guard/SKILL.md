---
name: guard
description: >-
  Combines intent checks and write boundaries so risky work stays inside explicit
  limits until the owner decides otherwise. Use when the user asks to guard this
  work, turn on the safety guard, protect this area, or combine careful and freeze
  — even when they only ask to "lock things down while we work". Bundles both
  layers; use `safety-guardrails/careful` for an intent check alone,
  `safety-guardrails/freeze` for a path lock alone, and `safety-guardrails/unfreeze`
  to lift the boundary.
version: 1.0.0
---


# Guard

## Purpose

Combines intent checks and write boundaries so risky work stays inside explicit limits until the owner decides otherwise.

## Use This Skill When

Use this skill when risky work needs **both** an intent check and a write boundary at once:

- "guard this work" / "turn on the safety guard" — apply intent confirmation and path locking together
- "protect this area" — keep changes inside explicit limits until the owner lifts them
- "combine careful and freeze" — run both guardrails as one controlled posture

Route elsewhere for just an intent check (`safety-guardrails/careful`), just a path lock (`safety-guardrails/freeze`), or to lift the boundary (`safety-guardrails/unfreeze`).

## Inputs

- Guarded boundary definition with allowed operations, blocked paths, and the exact owner-override conditions.
- Current request or action to validate against the guard's write limits.
- Environmental context such as hook availability, `guard-state.json` state, and filesystem permission constraints.

## Outputs

- Guard record with permitted actions, blocked actions, and the evidence enforcing each boundary.
- Guard-state update with `frozen_globs`, `blocked_globs`, and `allow_dangerous` entries for deterministic enforcement.
- Escalation path and remaining restrictions so the caller knows what is safe to proceed with.

## Workflow

1. Define the guarded boundary, the allowed operations inside it, and the exact owner override conditions before any work proceeds.
2. Check that the current request stays inside those write limits; if not, turn the mismatch into a guard violation instead of silently proceeding.
3. Record the guard state with permitted actions, blocked actions, and the evidence used to enforce the boundary.
4. Return a guard record with the escalation path, remaining restrictions, and the next safe action available to the caller.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Deterministic Enforcement (Action Realization layer)

This guard is the advisory expression of the Action Realization layer. When the host supports Claude Code hooks, the guarded boundary can also be **deterministically enforced** by a pre-tool-use hook that blocks writes into guarded paths before they execute. Two rules are load-bearing:

- **`allow_dangerous: true` requires explicit owner confirmation** before the guard-state file is written — named approval, recorded scope and reason, and reverted to `false` the moment the dangerous operation completes. Never the default; never enabled silently.
- **The hook is advisory-grade, not a hard security control.** Per harness-doctrine §3 it *fails open*: any internal error — malformed state, an unreadable path, or a host that never runs the hook — lets the action proceed. Never treat `blocked_globs` as the sole protection for secrets or production paths; for real isolation use OS/filesystem permissions or a sandbox.

For the `guard-state.json` schema, hook activation, the `allow_dangerous` override protocol, and fail-open semantics in full, see `references/enforcement.md`.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Confirm every guarded boundary has an explicit owner, permitted actions, and evidence of the risk that justified the restriction.
- Surface enforcement gaps — such as missing hooks, absent `guard-state.json`, or fail-open conditions — so the caller knows the guard is advisory-only.
- Shape the guard record so downstream workflows can check boundary compliance without re-reading the guard policy.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The guarded boundary is too broad to tell what work remains allowed | Shrink the guard to a specific path, service, or operation before enforcing it. |
| The request mixes guarded and unguarded surfaces in one step | Split the work and block only the guarded portion so the record stays precise. |
| The owner override is required but not actually present or verifiable | Keep the boundary locked and record the missing override evidence explicitly. |
| `allow_dangerous: true` is requested without explicit owner confirmation | Refuse to write the override; require the owner to provide a named, scoped approval before enabling it. |
| The `guard-state.json` file is corrupted, missing, or unreadable when enforcement is expected | Surface the fault loudly as a guard-state error. The deterministic hook *fails open* on a corrupt state (see `references/enforcement.md`), so do not rely on it — at the advisory layer, treat the destructive-command block as still in force and refuse dangerous operations until the owner inspects and repairs or recreates the file. |
| Another guard already exists with conflicting limits | Surface the conflict and require one authoritative boundary instead of stacking ambiguous restrictions. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.
- `references/enforcement.md` for the `guard-state.json` schema, hook activation, the `allow_dangerous` override protocol, and fail-open semantics.
- `../../harness-doctrine.md` (§1 Action Realization, §3 fail-open) and `../../harness/hooks/pre_tool_use.py` / `../../harness/hooks/README.md` for the deterministic enforcement hook itself.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, and `references/enforcement.md` together. The deterministic hook ships with the harness (`harness/hooks/`), not inside this skill. Keep generated reports and archives outside the skill directory.
