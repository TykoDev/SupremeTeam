# Example Invocations

## Contents

1. Example 1 — release branch, path glob vs social boundary
2. Example 2 — billing configs, advisory rule as a release precondition
3. Example 3 — incident scope, advisory layer catches an out-of-scope edit
4. Example 4 — guard around the patch, not across it
5. Example 5 — investigation as a read-only run


## Example 1

**User request:** guard this work on the release branch

**Command:**

```bash
python skills/harness/hooks/guard_state.py block --glob "release/manifests/**" --owner release-owner --scope "release branch is frozen for the RC"
```

**Output:**
- Boundary: `release/manifests/**`, owned by `release-owner`. The release branch itself is a social boundary named in the guard record — the hook matches paths, not branches, so branch protection belongs in version control.
- Allowed actions: reads anywhere, and patches proposed against files outside the guarded glob. Read-only commands that merely name a guarded path still pass; the hook blocks mutations, not references.
- Blocked actions: every edit-tool write and every mutating shell command targeting the manifests, until the owner releases the glob through `unfreeze`.

## Example 2

**User request:** turn on the safety guard for the billing configs

**Command:**

```bash
python skills/harness/hooks/guard_state.py block --glob "config/billing/**" --owner billing-owner --scope "no config change without a checksum" --approver finance-eng-lead
```

**Output:**
- Boundary: `config/billing/**`, with `finance-eng-lead` recorded as an approver so the lift does not depend on one person's availability.
- Guard rule (advisory): a change is acceptable only with the billing owner's approval and the current config checksum attached. The enforcement layer cannot express that condition — it denies the glob outright — so the rule is a release precondition, checked before `unfreeze`, not a carve-out inside the boundary.
- Next safe action: continue analysis work outside the guarded config path; the sync job's own code is not in the glob and stays editable.

## Example 3

**User request:** protect this area while we investigate the incident

**Command:**

```bash
python skills/harness/hooks/guard_state.py block --glob "services/queue-worker/**" --owner incident-lead --scope "queue incident: no changes while the failure is being characterized"
```

**Output:**
- Boundary: `services/queue-worker/**`, covering the failing worker config and its code.
- Violation detected: the requested change would also rewrite `config/shared/retry.yaml`, outside the stated incident scope and outside the guarded glob — so the hook would have allowed it silently. The advisory layer is what catches this one.
- Resolution: split the change set, keep the guarded incident boundary intact, and record the shared-config edit as a separate decision with its own owner.
- Note: had the investigation needed to touch nothing at all, a `read-only` record (Example 5) would have been the stronger posture.

## Example 4

**User request:** lock down src/payments and turn on hard enforcement while we patch the charge bug

The request contains a contradiction worth naming before anything is recorded:
freezing `src/payments/**` and then patching inside it are mutually exclusive.
Under the hook's Rule B every edit-tool write and every mutating shell command
targeting a frozen glob is denied, with no per-operation allowance. So the guard
is recorded around the patch, not across it.

**Commands:**

```bash
python skills/harness/hooks/guard_state.py block --glob "**/secrets/**" --owner security-lead --scope "secrets stay out of agent writes"
python skills/harness/hooks/guard_state.py freeze --glob "src/payments/ledger/**" --owner payments-lead --scope "charge-bug window: ledger math is out of scope for this patch" --run-id 2026-09-16-charge-bug
python skills/harness/hooks/guard_state.py status
```

**Output:**
- Boundary: `**/secrets/**` blocked outright; `src/payments/ledger/**` frozen. The charge-bug fix lives in `src/payments/checkout/`, which is deliberately left outside both globs — the guarded boundary is drawn around the blast radius the patch must not touch, not around the file the patch must edit.
- Enforcement: recorded through `guard_state.py block` and `guard_state.py freeze` — the record's only writer — into `.harness-state/guard-state.json`, so the pre-tool-use hook blocks stray writes, with the caveat that the hook fails open, so it is a discipline aid, not isolation (see `enforcement.md`).
- Rejected alternative: freezing `src/payments/**` wholesale with a prose exception for the charge-bug files. The exception would exist only in the narrative; the hook would deny the patch. If the patch genuinely had to touch a frozen path, the sequence is release-patch-re-record through `unfreeze` and `freeze`, never a carve-out.
- `allow_dangerous`: left `false`. The owner also asked to run a destructive migration; the grant is held pending the owner's named, scoped approval, and because it lifts destructive-pattern blocking for the whole session rather than for the migration alone, it gets an expiry sized to that operation plus retry margin and a `revoke-dangerous` the moment it completes.
- Next safe action: patch the charge bug in `src/payments/checkout/`; the ledger, secrets, and unrelated configs stay blocked.

## Example 5

**User request:** guard this incident investigation so nobody changes the product while we look

**Command:**

```bash
python skills/harness/hooks/guard_state.py read-only \
  --run-id 2026-09-16-queue-incident \
  --owner incident-lead \
  --allow "skillset-saves/runs/2026-09-16-queue-incident/**" \
  --scope "incident investigation"
```

**Output:**
- Boundary: the whole workspace is read-only for this run except the run's own save path, enforced by the hook's Rule D. This is the one key whose `allow` list the enforcement layer honours, which is why an investigation is recorded as a `read-only` run rather than as a freeze over everything else.
- Allowed: reads anywhere; writes under `skillset-saves/runs/2026-09-16-queue-incident/**` and the harness state directory; `save_run.py` invocations, which are exempt so the run can still checkpoint itself.
- Blocked: every other edit-tool write and every mutating shell command that names no allowed path — including the "one quick fix" an investigation is most likely to reach for.
- Release: findings are recorded first, then `guard_state.py release-read-only --run-id 2026-09-16-queue-incident --requester incident-lead` reopens the workspace. Only the record's owner may release it.
