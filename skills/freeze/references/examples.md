# Example Invocations

Every example records the boundary through `guard_state.py freeze` with an
explicit `--owner`, because a freeze with no owner is a freeze nobody is entitled
to lift, and the boundary the hook matches is the `--glob` — not the prose that
described it.

## Contents

1. Example 1 — payment hotfix, owner plus delegate
2. Example 2 — prose boundary converted to two globs
3. Example 3 — release candidates, single-owner lock
4. Example 4 — the writer refuses a duplicate


## Example 1

**User request:** freeze this area around the payment hotfix

**Command:**

```bash
python skills/harness/hooks/guard_state.py freeze \
  --glob "services/payments/**" \
  --owner payments-lead \
  --scope "charge-bug hotfix window" \
  --run-id 2026-09-16-charge-bug \
  --approver release-owner
```

```json
{"ok": true, "action": "frozen_globs", "glob": "services/payments/**", "owner": "payments-lead", "path": "D:\\proj\\.harness-state\\guard-state.json"}
```

**Output:**
- Boundary: `services/payments/**`. The deploy pipeline that promotes payment changes is named in the freeze record as a social hold, because a pipeline is not a path the hook can match.
- Owner and delegate: `payments-lead` owns the boundary; `release-owner` is recorded as an approver so the hotfix can close out of hours without a hand edit.
- Freeze state: no edits inside that glob until the incident owner releases it; the hook denies both edit-tool writes and mutating shell commands that name the path.
- Release condition: the hotfix ships and its canary is green, then `unfreeze` releases the glob.
- Safe work: log analysis and test work outside the frozen payment surface, which read-only commands can still reach — the hook blocks mutations, not reads.

## Example 2

**User request:** protect this path from edits during the migration

The stated boundary — the migration scripts and the schema history directory — is
prose, so it is converted to globs before anything is recorded. Two boundaries
means two calls, one glob each.

**Commands:**

```bash
python skills/harness/hooks/guard_state.py freeze --glob "db/migrations/**" --owner data-platform-lead --scope "migration window: no new migration files"
python skills/harness/hooks/guard_state.py freeze --glob "db/schema_history/**" --owner data-platform-lead --scope "migration window: history is append-only and written by the migrator"
```

**Output:**
- Boundary: `db/migrations/**` and `db/schema_history/**`, recorded as two separate owned entries so either can be released independently.
- Exception handling: the in-flight rollback verification is read-only and unaffected. Any write it still needs is a separate override decision, not an implicit carve-out — the hook has no per-operation allowance inside a frozen glob, so a genuinely required write means releasing the glob, performing the step, and re-recording it.
- Release condition: rollback verification completes and its checksum evidence is attached, then each glob is released by name.

## Example 3

**User request:** lock the boundary while we stabilize release candidates

**Commands:**

```bash
python skills/harness/hooks/guard_state.py freeze --glob "release/manifests/**" --owner release-owner --scope "RC stabilization"
python skills/harness/hooks/guard_state.py freeze --glob ".github/workflows/publish.yml" --owner release-owner --scope "RC stabilization"
python skills/harness/hooks/guard_state.py status
```

```text
record: D:\proj\.harness-state\guard-state.json (exists: True)
frozen:  ['release/manifests/**', '.github/workflows/publish.yml']
blocked: -
read-only runs: -
allow_dangerous: False
```

**Output:**
- Boundary: the release manifests and the publish workflow, both owned by `release-owner` with no delegate — during stabilization the lift is deliberately a single-person decision.
- Freeze record: direct edits are blocked; any exception must cite release-owner approval and is handled as a release-then-re-record, not as a side agreement.
- Evidence: the `status` output above is attached to the freeze record so the next contributor can see the boundary as the hook sees it.
- Next safe action: changelog drafting and artifact verification outside the locked paths.

## Example 4 — the writer refuses

**User request:** freeze the payments service again, I don't think the first one took

**Command and result:**

```bash
python skills/harness/hooks/guard_state.py freeze --glob "services/payments/**" --owner payments-lead
```

```text
refused: services/payments/** is already inside an active boundary in frozen_globs. Release it first, or record a different glob.
```

(exit 1)

**Output:**
- Finding: the boundary was already recorded and unreleased. The refusal is the evidence that the first freeze took effect, not a failure to apply a second one.
- Correction: the apparent gap is elsewhere — either the hook is not registered with the host, or the state directory `status` reports is not the one the host resolves. Compare the `record:` path in `status` against the project root before re-recording anything.
- Not done: the state file is never hand-edited around the refusal. Reconciliation is release-then-record through the writer, so the history shows both the original boundary and its replacement.
