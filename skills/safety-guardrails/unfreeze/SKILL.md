---
name: unfreeze
description: >-
  Clears an active protection boundary and records that the guarded area is open
  for changes again. Use when the user asks to unfreeze this area, remove the guard,
  lift the protection boundary, or allow changes again — even when they only say
  "we're done, open it back up". Lifts an existing boundary; defers creating a path
  lock to `safety-guardrails/freeze`, an intent check to `safety-guardrails/careful`,
  and the combined guard to `safety-guardrails/guard`.
version: 1.0.0
---


# Unfreeze

## Purpose

Clears an active protection boundary and records that the guarded area is open for changes again.

## Use This Skill When

Use this skill to **release an existing boundary** and record that the area is editable again:

- "unfreeze this area" / "lift the protection boundary" — clear the active freeze and its enforcement entry
- "remove the guard" — take down a combined guard posture
- "allow changes again" — record the release so later resume behavior stays unambiguous

Route elsewhere to create a lock rather than lift one (`safety-guardrails/freeze`), add an intent check (`safety-guardrails/careful`), or apply the combined guard (`safety-guardrails/guard`).

## Inputs

- Active freeze record identifying the locked boundary, the owning contributor, and the release conditions.
- Evidence that the release conditions have been met, such as resolved risks, completed deployments, or owner approval.
- Current `guard-state.json` entries and hook-enforcement status for the frozen boundary.

## Outputs

- Unfreeze record confirming the reopened boundary, cleared `frozen_globs` entries, and remaining neighboring protections.
- Residual-risk summary noting any follow-up checks needed after the protection is lifted.
- Escalation notes when release conditions cannot be verified and the boundary must remain frozen.

## Workflow

1. Confirm the active protection boundary, the owning contributor authority, and the exact guarded area to reopen before clearing any restrictions.
2. **Verify requester authority before proceeding**: only the original freeze owner or a named approver explicitly delegated in the freeze record may authorize an unfreeze. Matching authorization evidence — the freeze record naming the requester, or an explicit delegation from the freeze owner — is required. Do not lift the boundary on verbal request alone or based on role inference.
3. Compare the current state against the recorded release conditions so the guarded area opens for changes again only when the blocked risk is resolved or explicitly accepted.
4. **Remove the relevant `frozen_globs` entries from `guard-state.json`** once authorization and release conditions are both confirmed — clearing the enforcement entry is mandatory, not optional, so the hook no longer blocks the reopened paths.
5. Record the unfreeze decision with reopened scope, residual risks, and any follow-up checks that still need to happen after the protection boundary is lifted.
6. Return an unfreeze record that states what area is open for changes again, what neighboring boundaries remain protected, and the next safe action.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Verify every release condition against concrete evidence before lifting the freeze — never unfreeze based on intent alone.
- Surface unresolved risks and neighboring protections so the caller understands the residual exposure after the boundary opens.
- Shape the unfreeze record so the `freeze` and `guard` skills can reference it when auditing boundary history.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| There is no active freeze or guard record for the boundary being reopened | Stop and require the governing protection record before clearing anything. |
| Requester authority cannot be verified — the requester is not the freeze owner and no explicit delegation exists in the freeze record | Do not unfreeze; keep the boundary locked. Record the authorization gap and require the freeze owner or a documented delegate to authorize the lift. |
| The requester cannot prove authority to lift the boundary | Keep the protection in place and record the missing owner approval explicitly. |
| Release conditions remain unmet or only partially satisfied | Leave the boundary frozen, note the unmet condition, and name the remaining work needed for a safe unfreeze. |
| The unfreeze request only overlaps part of the protected area | Reopen only the verified subset and keep the rest protected with a clear partial-boundary note. |

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
