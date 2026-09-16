# Workflow Reference

## Contents

1. Unfreeze sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Unfreeze Sequence

1. Retrieve the active protection record — `python skills/harness/hooks/guard_state.py status` — and confirm who is allowed to lift it.
2. Compare the current state with the recorded release conditions and unresolved risks.
3. Reopen only the boundary that is proven safe to resume, through the record's single writer: `guard_state.py release` for a frozen or blocked glob, `release-read-only` for a read-only run, `revoke-dangerous` for a lifted `allow_dangerous` grant.
4. Write the unfreeze record with any remaining follow-up checks or adjacent protections.

## Decision Rules

- Never unfreeze a boundary without the governing record that created it.
- Release conditions must be satisfied or explicitly waived by the owner.
- A boundary lift is a release, never a deletion: the writer sets `released_at`, `released_by`, and `release_reason` and leaves the entry in place so the boundary history stays auditable. `revoke-dangerous` is the exception in shape — it resets `allow_dangerous` to `false` — so the grant's owner, scope, and reason are copied into the unfreeze record before it is revoked.
- An unfreeze is complete only when all four keys are settled — `frozen_globs`, `blocked_globs`, `read_only`, and any `allow_dangerous` grant, which is reverted rather than left to expire because it lifts destructive-pattern blocking session-wide. When the requester cannot revoke the grant, the unfreeze is incomplete and says so; it does not report an area as open while a session-wide lift stands.
- Partial unfreezes should stay explicit so the reopened scope cannot be misunderstood.
- Residual risks belong in the unfreeze record, not in unstated assumptions.

## Acceptance Checklist

- Governing protection record is identified.
- Owner authority is explicit, and matches the `owner` or `approvers` the writer checks against — with the exception of an `allow_dangerous` grant, which carries no approvers and is revocable only by its own owner.
- Release conditions are checked against current evidence.
- Every lift shows `released_at` and `released_by` on the surviving record; nothing was deleted.
- Reopened and still-protected boundaries are both named clearly, across all four keys.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
