---
name: guard
description: >-
  Combines careful and freeze into one posture: every destructive or externally
  visible step is confirmed with its owner, and the declared boundary is held until
  that owner lifts it. Use when the user asks to guard this work, turn on the safety
  guard, or wants both halves at once — confirm before acting *and* keep changes
  inside limits. Only one half: confirming intent alone is
  `careful`, locking a path alone is `freeze`, and
  lifting a lock is `unfreeze`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Guard

## Purpose

An intent check with no boundary asks permission and then trusts the answer; a boundary with no intent check stops the wrong write but never asks whether the right one should happen at all. Guard runs both against the same declared limits, so the record it leaves answers two questions at once — what this request is allowed to do, and what the enforcement layer will actually refuse regardless of what anyone intended. Where those two answers disagree, the disagreement is the finding.

## Use This Skill When

Use this skill when risky work needs **both** an intent check and a write boundary at once:

- "guard this work" / "turn on the safety guard" — apply intent confirmation and path locking together
- "confirm before acting and keep changes inside limits" — both halves as one posture
- "combine careful and freeze" — run both guardrails as one controlled posture

Route elsewhere for just an intent check (`careful`), just a path lock (`freeze`), or to lift the boundary (`unfreeze`).

## Inputs

- Guarded boundary definition with blocked paths, the exact owner-override conditions, and any operations meant to remain allowed. Allowed-operation nuance is advisory at this layer only: the deterministic layer denies the **whole glob** recorded in `frozen_globs` or `blocked_globs` — it has no per-operation allowance inside a guarded path — and `read_only` is the one key that carries an `allow` list the hook honours. A boundary that must stay partly writable is therefore recorded as a narrower glob, or as a `read-only` record whose `--allow` names the writable paths, not as a broad glob plus a prose exception.
- Current request or action to validate against the guard's write limits.
- Environmental context such as hook availability, the live boundary reported by `python skills/harness/hooks/guard_state.py status`, and filesystem permission constraints.

## Outputs

- Guard record with permitted actions, blocked actions, and the evidence enforcing each boundary.
- Guard-state records written through `../harness/hooks/guard_state.py` — `frozen_globs`, `blocked_globs`, `read_only`, and any `allow_dangerous` grant — for deterministic enforcement.
- Escalation path and remaining restrictions so the caller knows what is safe to proceed with.

## Workflow

1. Define the guarded boundary and the exact owner override conditions before any work proceeds, choosing the glob so that what must stay writable falls outside it — the enforcement layer denies a guarded glob entirely, so "allowed operations inside the boundary" is advisory unless it is expressed as a narrower glob or a `read-only` record's `--allow` list.
2. Check that the current request stays inside those write limits; if not, turn the mismatch into a guard violation instead of silently proceeding.
3. Record the guard state through `python skills/harness/hooks/guard_state.py` (`block`, `freeze`, or `read-only`) rather than by editing `.harness-state/guard-state.json`, and capture the permitted actions, blocked actions, and the evidence used to enforce the boundary alongside it.
4. Return a guard record with the escalation path, remaining restrictions, and the next safe action available to the caller.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Deterministic Enforcement (Action Realization layer)

This guard is the advisory expression of the Action Realization layer. When the host supports compatible runtime hooks, the guarded boundary can also be **deterministically enforced** by a pre-tool-use hook that blocks writes into guarded paths before they execute. The record it reads, `.harness-state/guard-state.json`, carries four keys:

- `frozen_globs` — owned records for paths the freeze layer locks against writes.
- `blocked_globs` — owned records for paths the guard forbids outright; the hook merges these with `frozen_globs` into one boundary.
- `read_only` — records (`run_id`, `owner`, `scope`, `allow` globs, `created_at`, `released_at`) that confine a run to its own save path, enforced by the hook's Rule D.
- `allow_dangerous` — an owned grant (`owner`, `reason`, `scope`, `created_at`, `expires_at`, 30 minutes by default) that lifts destructive-pattern blocking.

Four rules are load-bearing:

- **The guard-state record has a single writer.** `.harness-state/guard-state.json` is written only by `../harness/hooks/guard_state.py`, and `pre_tool_use.py` denies direct edit-tool writes and mutating shell commands against that path, exactly as core run records are routed through `save_run.py`. The reason is structural: before the writer existed the guard could lift itself, because one write to that file cleared any freeze — or set `allow_dangerous`, globally disabling destructive-pattern blocking — with no owner check and no `released_at` trail.
- **`allow_dangerous` requires explicit owner confirmation** before the grant is recorded — named approval, a recorded scope and reason, an expiry sized to the operation, and a revoke (`guard_state.py revoke-dangerous --requester <owner>`) the moment the dangerous operation completes. It is a **global kill-switch for every destructive-pattern block**, not an exception scoped to the one operation it was requested for, so it is never the default and never enabled silently. An expired or malformed grant leaves the block in force: a guard that cannot read its own grant stays closed rather than open. Exactly one shape lifts the block with no end to it — the legacy bare `true` — and `guard_state.py` never writes it, so a record carrying it was hand-edited and the lift has no owner, scope, or expiry behind it. `references/enforcement.md` names the four `allow_dangerous` shapes and which of them lift the block; read it before granting or trusting one.
- **Size the expiry to the whole operation plus margin.** The hook re-reads the grant on every tool call, so expiry mid-operation re-arms the block part-way through and the *next* step of a destructive sequence is denied — leaving the work half-done, which is frequently worse than either finishing or never starting. Estimate the operation's duration, add margin for a retry, and set `--minutes` from that; the default is 30. When a grant does lapse mid-flight, do not reflexively re-grant: record where the sequence stopped, establish whether the partial state is safe, and have the owner authorize the remainder explicitly. The expiry is a backstop, not the protocol — the revoke on completion is.
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
| An `allow_dangerous` grant is requested without explicit owner confirmation | Refuse to record the grant; require the owner to provide a named, scoped approval with a stated reason and an expiry before it is written. The grant lifts destructive-pattern blocking for every command in the session, not just the requested one, so an unconfirmed grant is a session-wide hole. |
| The `guard-state.json` file is corrupted, missing, or unreadable when enforcement is expected | Surface the fault loudly as a guard-state error. The deterministic hook *fails open* on a corrupt state (see `references/enforcement.md`), so do not rely on it — at the advisory layer, treat the destructive-command block as still in force and refuse dangerous operations until the owner inspects and repairs or recreates the file. `guard_state.py` refuses to read or overwrite a corrupt record, so the repair is an owner action taken outside the agent's tool loop — the hook denies an agent write to that path — followed by re-recording the boundary through the writer. |
| Another guard already exists with conflicting limits | Surface the conflict and require one authoritative boundary instead of stacking ambiguous restrictions. |
| An `allow_dangerous` grant expires part-way through the destructive operation it was granted for | Stop at the denial rather than working around it. Record exactly which step completed and which was refused, establish whether the partial state is safe to leave, and have the owner issue a fresh grant sized to the remainder with an explicit acknowledgement of the half-finished state. Sizing the original expiry to the operation plus retry margin is what prevents this. |
| The boundary is recorded as a broad glob with prose carve-outs for operations that must stay allowed | Re-record it. The hook denies the whole glob, so the carve-outs exist only in the narrative: narrow the glob, or use `guard_state.py read-only --run-id <run> --owner <owner> --allow "<writable glob>"`, the one key whose `allow` list the enforcement layer honours. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.
- `references/enforcement.md` for the `guard-state.json` schema, hook activation, the `allow_dangerous` override protocol, and fail-open semantics.
- `../harness-doctrine.md` (§1 Action Realization, §3 fail-open) and `../harness/hooks/pre_tool_use.py` / `../harness/hooks/README.md` for the deterministic enforcement hook itself.
- `../harness/hooks/guard_state.py` for the sanctioned writer of the boundary record and its subcommands, and `../save-ownership.yaml` (`harness-guards`) for the ownership rule that names it.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, and `references/enforcement.md` together. The deterministic hook ships with the harness (`harness/hooks/`), not inside this skill. Keep generated reports and archives outside the skill directory.
