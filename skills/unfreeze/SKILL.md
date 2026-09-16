---
name: unfreeze
description: >-
  Verifies requester authority, then releases an active protection boundary and
  records the area open again. Use when the user asks to unfreeze this
  area, remove the guard, lift the protection boundary, or allow changes again — even
  when they only say "we're done, open it back up". Lifts existing boundaries only: creating
  a path lock belongs to `freeze`, a verdict with no boundary to
  `careful`, the combined posture to `guard`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Unfreeze

## Purpose

Lifting a boundary is the single moment where a protection can be undone by the wrong person for the wrong reason, so it is treated as an authorized write rather than an announcement. Two things have to hold before anything reopens: the requester is the recorded owner or a delegate named at freeze time, and the conditions that justified the boundary are demonstrably resolved. The release then annotates the record instead of deleting it, so who locked what, who lifted it, and on what grounds all survive the lift.

## Use This Skill When

Use this skill to **release an existing boundary** and record that the area is editable again:

- "unfreeze this area" / "lift the protection boundary" — release the active freeze and its enforcement entry
- "remove the guard" — take down a combined guard posture across every key that holds the area closed
- "allow changes again" — record the release so later resume behavior stays unambiguous

Route elsewhere to create a lock rather than lift one (`freeze`), add an intent check (`careful`), or apply the combined guard (`guard`).

## Inputs

- Active freeze record identifying the locked boundary, the owning contributor, and the release conditions.
- Evidence that the release conditions have been met, such as resolved risks, completed deployments, or owner approval.
- Current boundary record — the `frozen_globs`, `blocked_globs`, `read_only`, and `allow_dangerous` keys as reported by `python skills/harness/hooks/guard_state.py status` — and the hook-enforcement status for the guarded area.

## Outputs

- Unfreeze record confirming the reopened boundary, the released entries — each carrying `released_at`, `released_by`, and `release_reason` rather than being deleted — and remaining neighboring protections.
- Residual-risk summary noting any follow-up checks needed after the protection is lifted.
- Escalation notes when release conditions cannot be verified and the boundary must remain frozen.

## Workflow

1. Confirm the active protection boundary, the owning contributor authority, and the exact guarded area to reopen before clearing any restrictions.
2. **Verify requester authority before proceeding**: only the original freeze owner or a named approver explicitly delegated in the freeze record may authorize an unfreeze. Matching authorization evidence — the freeze record naming the requester, or an explicit delegation from the freeze owner — is required. Do not lift the boundary on verbal request alone or based on role inference.
3. Compare the current state against the recorded release conditions so the guarded area opens for changes again only when the blocked risk is resolved or explicitly accepted.
4. **Release the governing entries through the sanctioned writer** once authorization and release conditions are both confirmed: `python skills/harness/hooks/guard_state.py release --glob <boundary> --requester <requester> --reason "<why it is safe to reopen>"`. One call covers both keys the hook merges into a single boundary, because the writer scans `frozen_globs` and `blocked_globs` for every active record matching the glob. Lifting the enforcement entry is mandatory, not optional, so the hook no longer blocks the reopened paths — but the lift is a release, never a deletion: the writer sets `released_at`, `released_by`, and `release_reason` and leaves the record in place, since deleting it would destroy the audit trail this skill exists to keep. The same command refuses a requester who is neither the recorded owner nor a named approver, which turns the authority check in step 2 from an instruction into an enforced one.
5. **Account for the other two live keys before calling the area open.** `read_only` and `allow_dangerous` hold work closed independently of any glob, so a request to remove the guard is complete only when all four keys are settled: release a read-only run with `guard_state.py release-read-only --run-id <run> --requester <requester>`, and revert a lifted `allow_dangerous` grant with `guard_state.py revoke-dangerous --requester <requester>`. **Authority narrows for the grant.** A frozen or blocked glob and a read-only record can each be released by their `owner` or by an approver recorded at freeze time, but the writer records no `approvers` on an `allow_dangerous` grant, so only the grant's own `owner` can revoke it — a delegate authorized for the glob is refused here, and the revoke has to be routed to the person named in the grant. Reverting `allow_dangerous` is mandatory and never deferred to a later cleanup, because that grant lifts destructive-pattern blocking for every command in the session rather than for the reopened path alone. Re-run `guard_state.py status` afterwards and attach its output as the evidence that the record matches what the unfreeze claims.
6. Record the unfreeze decision with reopened scope, residual risks, and any follow-up checks that still need to happen after the protection boundary is lifted.
7. Return an unfreeze record that states what area is open for changes again, what neighboring boundaries remain protected, and the next safe action.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Deterministic Enforcement (Action Realization layer)

Unfreeze lifts a boundary that `../harness/hooks/pre_tool_use.py` enforces deterministically (`../harness-doctrine.md` §1), so the release is a recorded write, not a statement of intent.

**The boundary record has a single writer.** `.harness-state/guard-state.json` is written only by `../harness/hooks/guard_state.py`, and `pre_tool_use.py` denies direct edit-tool writes and mutating shell commands against that path. A hand-edited unfreeze is indistinguishable from an unfreeze performed without authority, which is the exact failure this skill exists to prevent.

Four keys can hold an area closed, and an unfreeze accounts for all of them:

| Key | What it holds closed | How it is lifted |
| --- | --- | --- |
| `frozen_globs` | paths the freeze layer locks against writes | `guard_state.py release --glob <g> --requester <r> --reason "<why>"` |
| `blocked_globs` | paths the guard forbids outright; the hook merges these with `frozen_globs` into one boundary | the same `release` call, which scans both keys |
| `read_only` | a run confined to its own save path so an investigation cannot change the product surface (hook Rule D) | `guard_state.py release-read-only --run-id <run> --requester <r>` |
| `allow_dangerous` | the inverse of a lock: an owned grant that lifts destructive-pattern blocking globally until it expires | `guard_state.py revoke-dangerous --requester <r>`, where `<r>` must be the grant's own `owner` |

Both boundary releases — `release` and `release-read-only` — set `released_at`, `released_by`, and `release_reason` and leave the record in place; no boundary entry is ever deleted. The hook treats a record as effective until `released_at` is set and never expires one by age, so the released record is both the lift and the evidence of who lifted it. `revoke-dangerous` differs twice over: it resets `allow_dangerous` to `false` instead of annotating it, so the grant's owner, scope, reason, and expiry do not survive the revoke and belong in the unfreeze record before it is run — and it is the one lift with no delegate, because the writer records no `approvers` on a grant.

**The hook is advisory-grade, not a hard lock.** Per harness-doctrine §3 it *fails open*, so a boundary that still reads as active in `status` may already have been unenforced in practice: an unreleased entry is never evidence that the area was actually protected in the meantime. Report what the record shows and what was verified, not what the hook is assumed to have caught.

For the writer's authority check key by key, the two legacy shapes that defeat it, what a release leaves behind, and the writer's exit contract, see `references/enforcement.md`.

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
| The governing entry is a legacy one with no owner — a bare glob string, or a record whose `owner` is absent — written before the boundary record had a single writer | `status` lists both under the unowned entries it warns about. A bare glob string is refused outright by `guard_state.py release`, which has no field to check authority against; a record with an absent `owner` is still releasable by anyone listed in its `approvers`, and by nobody when that list is empty. Do not hand-edit the state file around a refusal: have the boundary owner re-record it through `guard_state.py freeze` or `block` with an explicit owner, then release it so the lift carries an attributable `released_by`. |
| The requester is a named approver on the frozen glob and asks to revoke the live `allow_dangerous` grant in the same pass | Release the glob, but route the revoke to the grant's own `owner`. `cmd_revoke_dangerous` authorizes against that owner alone and the writer records no `approvers` on a grant, so an approver's call is refused — leaving destructive-pattern blocking lifted session-wide if the unfreeze is reported as complete. Record the grant as still open until its owner reverts it. |
| `guard_state.py status` shows an `allow_dangerous` grant that has already expired | No revoke is required for enforcement — an expired grant leaves the block in force — but the key still reads as a grant. Record its owner, scope, and `expires_at` in the unfreeze record, and have its owner run `revoke-dangerous` so the record states `false` rather than a lapsed grant a later reader has to re-evaluate. |
| Release conditions remain unmet or only partially satisfied | Leave the boundary frozen, note the unmet condition, and name the remaining work needed for a safe unfreeze. |
| The unfreeze request only overlaps part of the protected area | Reopen only the verified subset and keep the rest protected with a clear partial-boundary note. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes, each showing the authority check and the `release` call that performed the lift.
- `references/enforcement.md` for the writer's authority check key by key, the legacy shapes that defeat it, release-not-deletion semantics, and the writer's exit contract.
- `../harness/hooks/guard_state.py` for the sanctioned writer and its `release`, `release-read-only`, and `revoke-dangerous` subcommands, and `../harness-doctrine.md` (§1 Action Realization, §3 fail-open) for the layer this lift sits in.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, and `references/enforcement.md` together. The deterministic hook and its writer ship with the harness (`harness/hooks/`), not inside this skill. Keep generated reports and archives outside the skill directory.
