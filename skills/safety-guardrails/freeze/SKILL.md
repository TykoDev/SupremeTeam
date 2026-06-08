---
name: freeze
description: >-
  Prevents changes inside a declared boundary until the owning contributor
  explicitly lifts the restriction. Use when the user asks to freeze this area,
  protect this path from edits, lock the boundary, or stop changes here — even when
  they only say "don't touch the payments code". Locks a path from edits; defers
  lifting that lock to `safety-guardrails/unfreeze`, a pure intent check to
  `safety-guardrails/careful`, and the combined intent-plus-boundary guard to
  `safety-guardrails/guard`.
version: 1.0.0
---


# Freeze

## Purpose

Prevents changes inside a declared boundary until the owning contributor explicitly lifts the restriction.

## Use This Skill When

Use this skill to **lock a declared path or boundary** from edits until it is explicitly lifted:

- "freeze this area" / "lock the boundary" — declare the path, service, or environment off-limits
- "protect this path from edits" — record the lock and (where hooks run) enforce it deterministically
- "stop changes here" — hold the boundary until the owner releases it

Route elsewhere to lift the lock (`safety-guardrails/unfreeze`), add only an intent check (`safety-guardrails/careful`), or apply both intent checks and the boundary together (`safety-guardrails/guard`).

## Inputs

- Path, service, or environment boundary to freeze and the owning contributor who can lift the restriction.
- Current mutable operations against the boundary, pending changes, and deployment state at freeze time.
- Release conditions that define when and how the boundary can be unfrozen.

## Outputs

- Freeze record identifying the locked boundary, blocked operations, permitted exceptions, and the owner who can unfreeze.
- Guard-state update with `frozen_globs` entries for deterministic enforcement when hooks are available.
- Release-condition summary so the `unfreeze` skill knows exactly what must be verified before lifting the restriction.

## Workflow

1. Identify the declared path, service, or environment boundary to freeze and the owning contributor who can later lift the restriction.
2. Verify owner intent and current mutable operations, then mark the guarded area as frozen before additional edits, deploys, or destructive steps occur.
3. Record the freeze state with blocked changes, permitted exceptions, and the evidence showing why the restriction must stay in place.
4. Return a freeze record with release conditions, owner handoff notes, and the next safe work that can continue outside the frozen boundary.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Deterministic Enforcement (Action Realization layer)

Freeze is the advisory expression of the Action Realization layer (`../../harness-doctrine.md` §1). When the host supports Claude Code hooks, the frozen boundary is also **deterministically enforced** by `../../harness/hooks/pre_tool_use.py`, which blocks any edit or command that touches a frozen path before it executes.

To activate enforcement, add the frozen paths to `frozen_globs` in `.harness-state/guard-state.json` (under `$CLAUDE_PROJECT_DIR`, else the OS temp dir):

```json
{ "frozen_globs": ["infra/*.tf", "src/payments/**"] }
```

The `unfreeze` skill clears these entries to lift the restriction. When the file is absent the freeze remains advisory. See `../../harness/hooks/README.md`.

**This hook is advisory-grade, not a hard lock.** Per harness-doctrine §3 the hook *fails open*: any internal error (malformed `guard-state.json`, an unreadable path, or a host that does not run hooks) exits silently and lets the edit proceed. A hook fault therefore means a write into a frozen path is *allowed*, not blocked. Treat freeze as a discipline aid that catches honest mistakes — for a boundary that must not change under any circumstances, back it with version-control protections or filesystem permissions in addition to the freeze.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Confirm every frozen boundary is backed by an explicit owner, release conditions, and evidence of the risk that justified the freeze.
- Surface enforcement gaps — such as missing hooks or absent `guard-state.json` — so the caller knows the freeze is advisory-only.
- Shape the freeze record so the `unfreeze` skill can verify release conditions without re-investigating the original risk.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The freeze request does not identify one coherent boundary to lock | Refuse the freeze until the path, service, or environment is explicit enough to enforce. |
| Active remediation is already in progress inside the boundary | Record the overlap and decide whether the work must stop immediately or complete one bounded step before the freeze takes effect. |
| A requested exception would silently undermine the freeze | Treat the exception as a separate override decision and keep the freeze intact until it is approved explicitly. |
| A stale freeze record already exists for the same area | Reconcile the existing state before writing a second freeze record so later resume behavior stays unambiguous. |

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
