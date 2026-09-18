# Example Invocations

Each example shows the authority check against the record's own `owner` and
`approvers` fields, the writer call that performed the lift, and the `released_at`
trail it left. Approval asserted in conversation is not an authority check: the
writer refuses a requester it does not find in the record, which is what turns the
check from an instruction into an enforced one.

## Contents

1. Example 1 — approver authorized, one glob released
2. Example 2 — partial unfreeze, grant revoke refused for the requester
3. Example 3 — authority met, release conditions not
4. Example 4 — the governing entry has no owner


## Example 1

**User request:** unfreeze this area now that the hotfix is validated

**Read the governing record:**

```bash
python skills/harness/hooks/guard_state.py status --json
```

```json
{
  "allow_dangerous": false,
  "blocked_globs": [],
  "exists": true,
  "frozen_globs": [
    "services/payments/**",
    "release/manifests/**"
  ],
  "path": "D:\\proj\\.harness-state\\guard-state.json",
  "read_only_runs": [],
  "unowned_entries": []
}
```

Seven keys, key-sorted, exactly as `guard_state.py status --json` prints them —
`path` and `exists` name the record this reading came from, so a status block
pasted without them cannot be tied to a file.

The full record names `payments-lead` as `owner` of `services/payments/**` and
`release-owner` as an approver. The requester is `release-owner`, so the writer
will accept the release.

**Lift:**

```bash
python skills/harness/hooks/guard_state.py release --glob "services/payments/**" --requester release-owner --reason "charge-bug hotfix validated: rollback verified, canary green"
```

```json
{"ok": true, "action": "release", "glob": "services/payments/**", "released_by": "release-owner", "records": 1}
```

**Output:**
- Governing record: the payment hotfix freeze created during the incident window, owned by `payments-lead` with `release-owner` recorded as an approver at freeze time.
- Authority: the requester is a named approver on that record, which is why the writer accepted the call rather than refusing it.
- Release check: rollback verification and canary health checks are both attached, satisfying the recorded release conditions.
- Trail: the entry now carries `released_at`, `released_by: release-owner`, and the stated `release_reason`; it was annotated, not deleted, so the boundary history survives.
- Still protected: `release/manifests/**` remains frozen — the lift was scoped to one glob and the other boundary is named explicitly so the reopened scope cannot be over-read.

## Example 2

**User request:** remove the guard on the billing configs

**Read the governing record:** `config/billing/**` is blocked, `owner: billing-owner`,
`approvers: ["finance-eng-lead"]`. A live `allow_dangerous` grant is also present,
`owner: ops-lead`, scope "scratch-volume rebuild", expiring in 12 minutes. The
requester is `finance-eng-lead`.

**Lift the glob:**

```bash
python skills/harness/hooks/guard_state.py release --glob "config/billing/**" --requester finance-eng-lead --reason "checksum refresh complete for the local config set"
```

```json
{"ok": true, "action": "release", "glob": "config/billing/**", "released_by": "finance-eng-lead", "records": 1}
```

**Attempt the grant revoke with the same requester:**

```bash
python skills/harness/hooks/guard_state.py revoke-dangerous --requester finance-eng-lead
```

```text
refused: finance-eng-lead is not the owner (ops-lead) of the allow_dangerous grant.
```

(exit 1)

**Output:**
- Authority: the requester is a recorded approver on the blocked glob, so that release stands on the record rather than on the billing owner's say-so. Verbal approval alone would not have satisfied the writer, and does not satisfy this skill either.
- Partial unfreeze: local config edits are reopened; the production sync job was never in the guarded glob and its own boundary is unchanged, so it is named as still-restricted rather than assumed clear.
- Not complete: the `allow_dangerous` grant is still live and **cannot** be revoked by this requester — `revoke-dangerous` authorizes against the grant's `owner` alone and the writer records no approvers on a grant. The unfreeze record states the grant's owner, scope, reason, and `expires_at`, and the remaining action is `ops-lead` running the revoke. Until then destructive-pattern blocking is lifted session-wide, so the area is not reported as fully open.
- Evidence: `guard_state.py status` re-run after the release and attached, showing the released glob and the still-live grant.

## Example 3

**User request:** lift the protection boundary around the release pipeline

**Read the governing record:** `release/manifests/**` frozen, `owner: release-owner`,
`approvers: []`. The requester is `release-owner`, so authority is satisfied; the
release conditions are not.

**Output:**
- Governing record: the release manifest freeze from the stabilization window.
- Authority: satisfied — the requester is the recorded owner. Authority and release conditions are independent checks, and passing the first is not a reason to soften the second.
- Decision: no-go. The final artifact verification step recorded as a release condition is still missing, so no `release` call is made and the entry keeps its null `released_at`.
- Next safe action: finish artifact verification, attach the evidence, and re-run the unfreeze request. Nothing is hand-edited in the meantime — an unreleased record is the correct representation of a boundary that is still in force.

## Example 4 — the governing entry has no owner

**User request:** open up the legacy tooling directory, that freeze is ancient

**Read the governing record:**

```text
record: D:\proj\.harness-state\guard-state.json (exists: True)
frozen:  ['tools/legacy/**']
blocked: -
read-only runs: -
allow_dangerous: False
WARNING unowned (not releasable by authority check): ['tools/legacy/**']
```

**Attempted lift:**

```bash
python skills/harness/hooks/guard_state.py release --glob "tools/legacy/**" --requester tooling-lead --reason "legacy tools are back in scope"
```

```text
refused: tools/legacy/** was recorded as a bare glob with no owner, so authority cannot be verified. Re-record it through this writer (guard_state.py freeze --glob ... --owner ...) before releasing it.
```

(exit 1)

**Output:**
- Finding: the entry predates the single writer and is a bare glob string, so there is no `owner` and no `approvers` for the authority check to consult. The writer refuses rather than trusting the requester.
- Distinction worth recording: a bare string is refused outright, while a record with an absent `owner` but a populated `approvers` list can still be released by a listed approver. Both appear under the same `unowned` warning, so the record itself has to be read, not just the warning.
- Resolution: the boundary owner re-records it through `guard_state.py freeze --glob "tools/legacy/**" --owner <owner>`, then releases it, so the lift carries an attributable `released_by`.
- Not done: the state file is not hand-edited around the refusal — that would reproduce precisely the unattributable lift the writer exists to prevent, and the hook denies the write in any case.
