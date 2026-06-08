---
name: careful
description: >-
  Adds a protective decision layer before risky operations so destructive or
  irreversible actions require explicit evidence and intent. Use when the user asks
  to be careful with this, add a safety guard, protect the risky action, or pause
  before destructive work — even when they only say "don't break anything". Adds an
  intent/confirmation check on actions; defers locking a path from edits to
  `safety-guardrails/freeze`, the combined intent-plus-boundary guard to
  `safety-guardrails/guard`, and lifting a boundary to `safety-guardrails/unfreeze`.
version: 1.0.0
---


# Careful

## Purpose

Adds a protective decision layer before risky operations so destructive or irreversible actions require explicit evidence and intent.

## Use This Skill When

Use this skill to **add a confirmation checkpoint** before a destructive or irreversible action runs:

- "be careful with this" / "pause before destructive work" — require explicit intent before the action proceeds
- "add a safety guard" — insert an evidence-and-intent check ahead of the risky step
- "protect the risky action" — make the consequences explicit before committing

Route elsewhere to lock a path from any edits (`safety-guardrails/freeze`), combine intent checks with a write boundary (`safety-guardrails/guard`), or lift an existing boundary (`safety-guardrails/unfreeze`).

## Inputs

- Description of the risky or destructive action, the affected boundary, and the current environment state.
- Evidence required to authorize the action, such as backup confirmation, rollback availability, or owner approval.
- Known constraints including protected environments, irreversibility thresholds, and side-effect blast radius.

## Outputs

- Safety guard decision record with go, no-go, or escalate verdict and the exact evidence used.
- Blocked-action list identifying what cannot proceed and what proof would unlock it.
- Escalation notes when the requested action exceeds the available evidence or authority.

## Workflow

1. Identify the risky action, affected boundary, and the evidence required before any destructive, irreversible, or hard-to-undo step is allowed.
2. Check that the current environment, target surface, and requested intent all match; if any one is ambiguous, stop before execution.
3. Record a go, no-go, or escalate decision with the exact evidence used, the remaining uncertainty, and the safest next action available.
4. Return a careful record that states what can proceed now, what stays blocked, and what proof would unlock the next step safely.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Base every safety verdict on explicit evidence — backup confirmation, rollback test, or owner approval — not on assumed safety.
- Surface missing prerequisites and irreversibility risks before the action reaches execution.
- Shape the guard record so the requesting workflow knows exactly what is safe to proceed with and what remains blocked.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The risky action is described too broadly to tell what would actually be affected | Narrow the boundary first and refuse to bless a vague request that could hide destructive scope. |
| Intent, evidence, and environment point at different targets | Freeze the decision, name the mismatch, and require one coherent target before any action proceeds. |
| The requested step depends on a prerequisite that has not been verified | Keep the action blocked and state the minimum evidence needed to prove the precondition. |
| Another contributor could misread the outcome as unconditional approval | Write the residual risk and release conditions directly into the careful record so the next step is bounded. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
