# Run-Record Operations Reference

Read this before issuing any `save_run.py` operation, and again when a result is
not `ok`. `../SKILL.md` states the write-ownership boundary and the failure
branches; this file is the operation-level detail behind them. The canonical
contract is `../../save-protocol.md`; nothing here overrides it.

## Contents

1. Operations
2. Results and exit codes
3. Revision lineage and `--expect-revision`
4. Lock, heartbeat, and reclaim
5. Interrupted publish and rollback
6. Reading state without writing

## Operations

`python skills/harness/hooks/save_run.py <operation> --run-id <run-id> [options]`

| Operation | What it does | When session-memory issues it |
| --- | --- | --- |
| `create` | Probes the save root, acquires an exclusive pinned lock, publishes revision 1, writes the pointer | Once, at the start of a run, after intake normalizes the request |
| `checkpoint` | Publishes revision n+1 atomically after snapshotting revision n into `_history/`, and registers evidence hashes | Before every delegation and at every return or boundary |
| `heartbeat` | Refreshes the lock heartbeat without changing the revision | Between checkpoints on a long stage; the harness hooks also call it on real host activity |
| `complete` | Terminal transition to status `complete`, releasing the pin | At run completion |
| `block` | Terminal transition to status `blocked`, releasing the pin | When the run stops on a blocker no later stage can clear |
| `release` | Releases lock and pin without a terminal status | On a paused hand-back the run may resume from |
| `recover` | Reclaims a stale lock, or with `--rollback` restores the last coherent revision | Only after `status` proves the lock stale or the publish interrupted |
| `status` | Read-only classification of the saved state | Before any write on a run this session did not create |

Useful flags: `--evidence <path>` is repeatable and binds a project-relative
evidence file by sha256; `--set key=value` is repeatable and records a
non-reserved state field; `--next-action` records the resume instruction;
`--reopen` deliberately reopens a `complete` or `blocked` run as a new revision;
`--reason` states why a stale lock is being reclaimed. Run
`python skills/harness/hooks/save_run.py --help` for the full option set.

## Results and exit codes

Every operation emits one JSON result on stdout. Read `result` before reporting
anything; the exit code carries the same verdict for a shell caller.

| `result` | Exit | Meaning | Response |
| --- | --- | --- | --- |
| `ok` | 0 | The revision published and the pointer was written | Report the revision, the registered evidence hashes, and the next action |
| `refused` | 1 | Contract violation: competing owner, wrong revision, unsafe path, stale lock, terminal run without `--reopen` | Resolve the contract and reissue. Never hand-edit a core run file to get past it |
| `degraded` | 2 | The write failed; nothing coherent was published and the previous revision is intact | Warn once, report persistence as degraded, keep readable evidence, and use transient mode only when resume cannot be proven |
| *(engine error)* | 3 | Bad input or an internal failure in the writer itself | Treat as degraded for persistence purposes and surface the raw message; do not retry blindly |

A `degraded` result is not a smaller `refused`. `refused` means the run said no
and the fix is upstream of the write; `degraded` means the medium said no and the
run's own state is still exactly what it was.

## Revision lineage and `--expect-revision`

`--expect-revision <n>` is the optimistic-concurrency guard: the operation
publishes n+1 only if n is the revision currently on disk. A mismatch is
`refused`, and it means another writer advanced the run between the read and the
write.

The repair is always the same three steps: re-read with `status`, reconcile what
the other writer changed, then checkpoint against the revision actually
published. Re-issuing with the stale number — or dropping the flag to make the
refusal go away — publishes a lineage in which the other writer's revision never
existed, which is the one failure `_history/` cannot reconstruct afterwards.

## Lock, heartbeat, and reclaim

Active state requires a pinned, held lock; terminal state requires an unpinned,
released one. The lock carries an ISO-8601 `heartbeat`, refreshed on every
checkpoint or `heartbeat` operation and, between operations, by the harness hooks
on real host activity. A lock is stale when its heartbeat is older than 30
minutes.

A checkpoint or heartbeat on a stale lock is refused. Reclaim it with
`recover --reason "<why>"`, which records the stale lock's path, heartbeat,
owner, and sha256 in the audit trail before granting a fresh one, and which
refuses outright against a fresh lock or a competing active run. The reclaim
leaves evidence precisely so a contested run cannot be quietly taken over.

## Interrupted publish and rollback

`_journal.json` is written before the first `os.replace` of a publish and removed
after the last, so an interrupted publish is visible: `status` reports
`interrupted`. While the journal is present, `checkpoint`, `heartbeat`,
`complete`, `block`, `release`, and a non-rollback `recover` are all refused.

The only forward path is `recover --rollback`, and it resolves to one of three
outcomes depending on how far the interrupted publish got. The writer decides;
the caller does not choose between them, and the `operation` field of the result
names which one ran.

| Outcome | Condition | What the writer does |
| --- | --- | --- |
| `rollforward` | The state file and the lock both already carry the journal's revision — the core publish completed and only the pointer/journal step was lost | Completes the revision instead of undoing it: writes the pointer at the journal revision, removes the journal, and returns `operation: rollforward` at that same revision. `_history/` is not read. |
| `rollback` from a history snapshot | `_history/rev-<n-1>.state.json` and `_history/rev-<n-1>.lock.json` both exist | Restores both from the snapshot, records `source: history snapshot` in the audit trail, and returns `operation: rollback` at revision n-1. |
| `rollback` with the lock rebuilt | No history snapshot, but the state file is already at revision n-1 — only the lock or the pointer was left mid-publish | Keeps that state file and rebuilds the lock from it, records `source: state file (lock rebuilt)`, and returns `operation: rollback` at revision n-1. `_history/` is never touched. |

Two conditions are refusals rather than outcomes: a journal naming no prior
revision (`target < 1`), and a target with neither a snapshot nor a matching state
file. Both escalate to the owner rather than guessing a revision.

Deleting the journal by hand clears the symptom and leaves the run mid-publish,
which is why the class is single-writer in the first place.

## Reading state without writing

A lookup, a resume probe, and any pre-write check are read-only:

```bash
python skills/harness/hooks/save_run.py status --run-id <run-id>
```

`status` classifies the state as active, inactive, complete, stale, orphaned,
conflicting, corrupt, interrupted, missing, or unreadable. Only a coherent fresh
active or orphaned record reinforces the session pin. `corrupt` and `unreadable`
are terminal for the resume path until an owner decides: the canonical bytes stay
untouched, because they are the only record of what the run was when it broke.
