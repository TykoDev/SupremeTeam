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
6. The audit trail
7. Reading state without writing

## Operations

`python skills/harness/hooks/save_run.py <operation> --run-id <run-id> [options]`

| Operation | What it does | When session-memory issues it |
| --- | --- | --- |
| `create` | Probes the save root, acquires an exclusive pinned lock, publishes revision 1, writes the pointer; needs at least one `--evidence` path and a run id of 1 to 128 letters, digits, `.`, `_` or `-` that starts with a letter, digit or `_` (every other operation accepts any single path segment, so a run made under a looser id stays closable) | Once, at the start of a run, after intake normalizes the request and writes its report |
| `checkpoint` | Publishes revision n+1 atomically after snapshotting revision n into `_history/`, and registers evidence hashes; `--drop-evidence` removes a registered path | Before every delegation and at every return or boundary |
| `heartbeat` | Refreshes the lock heartbeat without changing the revision | Between checkpoints on a long stage; the harness hooks also call it on real host activity |
| `complete` | Terminal transition to status `complete`, releasing the pin; refused on a run already complete or blocked | At run completion |
| `block` | Terminal transition to status `blocked`, releasing the pin; refused on a run already complete or blocked | When the run stops on a blocker no later stage can clear |
| `release` | Releases lock and pin without a terminal status | On a paused hand-back the run may resume from |
| `recover` | Reclaims a stale lock (`--reason`), or with `--rollback` settles an interrupted publish | Only after `status` proves the lock stale or the publish interrupted |
| `status` | Read-only classification of the saved state, and of the run you name | Before any write on a run this session did not create |

Useful flags: `--evidence <path>` is repeatable and binds a project-relative
evidence file by sha256, and a path is registered under one normalised spelling
(`./x` and `x` are the same file); `--drop-evidence <path>` is repeatable, stops
registering a path (one that was moved or pruned), and needs `--reason`; a run
keeps at least one evidence path, so the last one is dropped only together with
its replacement in `--evidence`;
`--set key=value` is repeatable and records a non-reserved state field, on
`create` as well as `checkpoint`; `--next-action` records the resume instruction;
`--reopen` deliberately reopens a `complete` or `blocked` run as a new revision;
`--reason` states why a stale lock is reclaimed or why evidence is dropped, and a
blank one is refused; `--lock-timeout` is how many seconds a writer waits for
another writer (default 10). Run
`python skills/harness/hooks/save_run.py --help` for the full option set.

## Results and exit codes

Every operation emits one JSON result, on stdout except for an engine error,
which writes its JSON to stderr. Read `result` before reporting anything; the exit
code carries the same verdict for a shell caller.

| `result` | Exit | Meaning | Response |
| --- | --- | --- | --- |
| `ok` | 0 | The revision published and the pointer was written | Report the revision, the registered evidence hashes, and the next action |
| `refused` | 1 | Contract violation: competing owner, wrong revision, unsafe path, stale lock, `create` with no evidence, terminal run without `--reopen`. Also a busy write lock, which says so | Resolve the contract and reissue; for a busy lock just reissue. Never hand-edit a core run file to get past it |
| `degraded` | 2 | The write failed; nothing coherent was published and the previous revision is intact | Warn once, report persistence as degraded, keep readable evidence, and use transient mode only when resume cannot be proven |
| *(engine error)* | 3 | Bad input or an internal failure in the writer itself | Treat as degraded for persistence purposes and surface the raw message; do not retry blindly |

Read `result` as well as the code: a mistyped option is argparse's own exit 2,
which looks like `degraded`, but it prints nothing to stdout and the usage message
goes to stderr.

A `degraded` result is not a smaller `refused`. `refused` means the run said no
and the fix is upstream of the write; `degraded` means the medium said no and the
run's own state is still exactly what it was. Both are written to the run's audit
trail as `refused` and `degraded` events (operation, owner, reason), when the run
directory exists, so the harness audit sees them.

A `degraded` reason can say the revision *was* published: when the state and lock
are written and only the audit line failed, the journal stays and `status`
reports `interrupted`, so `recover --rollback` rolls that revision forward.

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

A heartbeat dated more than five minutes ahead of the clock is treated as stale
too: it can never age, so it would otherwise pin the run for ever.

A checkpoint or heartbeat on a stale lock is refused. Reclaim it with
`recover --reason "<why>"`, which records the stale lock's path (relative to the
project), heartbeat, owner, and sha256 in the audit trail before granting a fresh
one, and which refuses outright against a fresh lock, a competing active run, or
a blank reason. The reclaim leaves evidence precisely so a contested run cannot
be quietly taken over.

The lock record above is separate from the writer mutex, `skillset-saves/_write.lock`.
Every operation that writes holds the mutex from reading the run to its last
write, and reads the revision again inside it, so two writers at once take turns:
the second finds what the first published, and a stale `--expect-revision` is
refused instead of overwritten. It is an operating-system lock, gone when its
holder exits, so a killed writer never leaves it held; never delete the file. A
writer that must succeed waits `--lock-timeout` seconds and then refuses with a
message to retry. The hook heartbeat waits a quarter of a second and skips.

## Interrupted publish and rollback

`_journal.json` is written before the first `os.replace` of a publish and removed
after the last, so an interrupted publish is visible: `status` reports
`interrupted`. While the journal is present, `checkpoint`, `heartbeat`,
`complete`, `block`, `release`, and a non-rollback `recover` are all refused.

The only forward path is `recover --rollback`, and it resolves to one of four
outcomes depending on how far the interrupted publish got. The writer decides;
the caller does not choose between them, and the `operation` field of the result
names which one ran. `--rollback` with no journal present is refused: it is not a
way to reclaim a lock, which takes `--reason`.

| Outcome | Condition | What the writer does |
| --- | --- | --- |
| `rollforward` | The state file and the lock both already carry the journal's revision — the core publish completed and only the pointer/journal step was lost | Completes the revision instead of undoing it: refreshes the lock heartbeat, writes the pointer at the journal revision, removes the journal, and returns `operation: rollforward` at that same revision. `_history/` is not read. |
| `rollback` from a history snapshot | `_history/rev-<n-1>.state.json` and `_history/rev-<n-1>.lock.json` both exist, parse, and are this run's revision n-1 | Restores both from the snapshot, records `source: history snapshot` in the audit trail, and returns `operation: rollback` at revision n-1. |
| `rollback` with the lock rebuilt | No usable history snapshot, but the state file is already at revision n-1 — only the lock or the pointer was left mid-publish | Keeps that state file and rebuilds the lock from it, records `source: state file (lock rebuilt)`, and returns `operation: rollback` at revision n-1. `_history/` is never touched. |
| `rollback` of an unpublished first revision | The journal names revision 1: a `create` died before it finished, so there is no earlier revision | Moves whatever it wrote into `_history/` as `rev-1.<kind>.unpublished-<time>.json`, records the digests, and returns `operation: rollback` at revision 0. The run directory reads `uninitialized` and the run id is free for `create`. |

Whichever outcome runs, the lock leaves it with a fresh heartbeat, so a run that
was interrupted overnight is not stale the moment it is repaired and the next
`checkpoint` is not refused.

Two conditions are refusals rather than outcomes: a journal that is unreadable or
names no revision, and a target with neither a usable snapshot nor a matching
state file. A snapshot that does not parse or is not this run's record is never
restored, so a damaged one can no longer publish an empty record as the run. Both
refusals leave every file untouched and escalate to the owner rather than
guessing a revision.

Deleting the journal by hand clears the symptom and leaves the run mid-publish,
which is why the class is single-writer in the first place.

## The audit trail

`_audit-trail.md` is append-only, one JSON object per line, and its events are
`create`, `checkpoint`, `reopen`, `resume`, `complete`, `blocked`, `released`,
`recover`, `rollforward`, `rollback`, `pointer-degraded`, and, for an operation
that did not happen, `refused` and `degraded`. An event is appended once its
revision's files are published, before the journal is cleared, so a publish that
fails leaves no event for a revision that never existed. There is no operation
that appends a line by name: facts such as a probe result, the hook-registration
check, the MCP registry check, or why a pin was released are state, carried as
`--set key=value` on `create` or the next `checkpoint`.

## Reading state without writing

A lookup, a resume probe, and any pre-write check are read-only:

```bash
python skills/harness/hooks/save_run.py status --run-id <run-id>
```

`status` classifies the state as active, inactive, complete, stale, orphaned,
conflicting, corrupt, interrupted, missing, uninitialized, or unreadable, and
names the `next_step` for it. `complete` is a finished run the pointer names;
`inactive` is a released or blocked one, and `run_status` says which, so a
resumable `released` run is not mistaken for a `complete` one that needs
`--reopen`. `uninitialized` is a run directory holding intake's report and no
record, which is not a fault: run `create`. `status` also classifies the run named
by `--run-id` on its own as `requested_run`, so the answer for that run does not
depend on what else the save root holds. Only a coherent fresh active or orphaned
record reinforces the session pin. `corrupt` and `unreadable` are terminal for the
resume path until an owner decides: the canonical bytes stay untouched, because
they are the only record of what the run was when it broke. A record that is not
valid UTF-8, or is nested deeply enough to overflow the parser, is `corrupt`, not
an error. A closed run whose evidence was pruned is not `corrupt`; its
`evidence_missing` lists the paths. Evidence under a directory this account may not
search is listed as `evidence_unverifiable` instead, and the run keeps the
classification its own records give. A record this account is refused (records are
owner-only, so a second account sharing the directory cannot read the first one's)
is `corrupt` too, with `access_denied` naming the file and the reason `permission
denied`: it may be a held run and `create` refuses beside it. Its owner completing
or releasing the run does not change that, because the records of a closed run stay
owner-only: they have to be made readable to this account, or removed by an account
that may delete them.
