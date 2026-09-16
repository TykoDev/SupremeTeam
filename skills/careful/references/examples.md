# Example Invocations

Each example opens with the step 0 boundary read, because a verdict on a
destructive action that does not quote the live guard state is a verdict issued
without knowing whether anything still stands behind it.

## Contents

1. Example 1 — schema migration: no-go pending rollback proof
2. Example 2 — deploy: canary go, full rollout blocked
3. Example 3 — cleanup while a stray `allow_dangerous` grant is live
4. Example 4 — the boundary cannot be read


## Example 1

**User request:** be careful with this schema migration

**Boundary read:**

```bash
python skills/harness/hooks/guard_state.py status
```

```text
record: D:\proj\.harness-state\guard-state.json (exists: True)
frozen:  ['db/migrations/**']
blocked: -
read-only runs: -
allow_dangerous: False
```

**Output:**
- Risky boundary: production billing tables and the migration that rewrites invoice status values.
- Guard state: `allow_dangerous` is `false`, so the destructive-pattern block is in force; `db/migrations/**` is frozen, so the hook's Rule B already denies every edit to the migration files themselves.
- Decision: no-go. Two things are missing — a rollback path with a verified backup timestamp, and a release of the migration freeze by its owner.
- Next safe action: collect the rollback proof, then route the freeze release to `unfreeze`; re-run the careful check on the result before touching production data.

## Example 2

**User request:** add a safety guard before this deploy

**Boundary read:** `guard_state.py status` reports no frozen or blocked globs covering the deployment path, no read-only run, and `allow_dangerous: False`.

**Output:**
- Risky boundary: container rollout for the public API during business hours.
- Guard state: nothing in the record covers this path, so the careful verdict is the only control in place — recorded as such rather than implied.
- Decision: go for a canary rollout only, because health checks exist and the blast radius is one replica; the full rollout stays blocked until the error-budget owner signs off.
- Record: release conditions are written directly into the careful note, so the deploy cannot be misread as fully approved.

## Example 3

**User request:** protect the risky action while I clean up stale files

**Boundary read:**

```bash
python skills/harness/hooks/guard_state.py status
```

```text
record: D:\proj\.harness-state\guard-state.json (exists: True)
frozen:  -
blocked: ['**/secrets/**']
read-only runs: -
allow_dangerous: {'owner': 'ops-lead', 'reason': 'reformat the scratch volume before the rebuild', 'scope': 'scratch-volume rebuild', 'created_at': '2026-09-16T09:20:11Z', 'expires_at': '2026-09-16T09:50:11Z'}
```

**Output:**
- Risky boundary: a cleanup command that deletes files across shared build output and cached release artifacts.
- Guard state: a live `allow_dangerous` grant is in force until `09:50:11Z`, scoped to a scratch-volume rebuild. That grant is session-wide, not scoped to its stated operation, so while it stands the recursive-delete block is off for this cleanup too.
- Decision: no-go on two independent grounds — the target path and retention window are still ambiguous, and the deterministic block that would have caught an over-broad delete is currently lifted for an unrelated operation.
- Next safe action: have `ops-lead` run `python skills/harness/hooks/guard_state.py revoke-dangerous --requester ops-lead` (only the grant's owner may revoke it), scope the delete to one directory, attach the retention rule, then re-run the careful check.

## Example 4 — the boundary cannot be read

**User request:** go ahead and wipe the worktree, just be careful

**Boundary read:**

```bash
python skills/harness/hooks/guard_state.py status
```

```text
refused: D:\proj\.harness-state\guard-state.json is not valid JSON (Expecting value: line 1 column 1 (char 0)). ...
```

(exit 1)

**Output:**
- Risky boundary: a recursive delete across the working tree.
- Guard state: unreadable. Every boundary in the record is unusable, and the hook falls back to its built-in destructive-pattern guard alone — which itself fails open on a malformed record.
- Decision: no-go. An unreadable boundary tightens the verdict rather than excusing it; a corrupt record is never evidence that nothing was protected.
- Next safe action: the record's owner repairs or removes the file directly — `guard_state.py` refuses to overwrite corrupt bytes and the hook denies an agent write to that path, so the repair happens outside the tool loop — then re-records the boundary through the writer and the check re-runs.
