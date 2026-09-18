# Persistent Saves

Everything the pipeline produces goes to disk while it runs: run state,
deliverables, evidence, verdicts. So the next session resumes from evidence rather
than from memory, which is the only kind of resume that survives a crash.

Full contract in [`skills/save-protocol.md`](../skills/save-protocol.md).

![Crash recovery and state validation](assets/10_recovery.jpg)

## Layout

Saves live in `skillset-saves/` inside the project you are working on, never in
the Supreme Team source tree.

```text
skillset-saves/
  _latest.md                       # pointer: run_id, revision, updated_at
  runs/{run-id}/
    _state.md                      # run state
    _lock.md                       # lock with heartbeat
    _audit-trail.md                # append-only events
    _journal.json                  # exists only mid-publish
    _history/                      # rev-<n>.state.json / rev-<n>.lock.json
    intake/report_grilling.md      # the hashed decisions artifact
    design/                        # one directory per phase
      manifest.json                #   the gate submission
      reports/                     #   reports, plans, summaries
      artifacts/                   #   tokens, components, snapshots
      evidence/                    #   command logs, scans, captures
        coverage/                  #     coverage data files and reports
      packages/                    #   exported archives
      verdict_design-to-build.json #   the phase gatekeeper's durable verdict
      verdict_design-to-build.cross-stage.json  # gatekeeper-admiral's, beside it
    build/  review/  security/  investigation/  qa/  taste/  redesign/  skill-creation/  release/
    delivery/reports/              # admiral's handoff_<boundary>.md and delivery-package.md
```

Your application source keeps its own layout. Evidence that depends on it binds by
`path` plus `sha256`, so a changed source file fails the gate as `input hash
drift` instead of silently going stale. Hashes fold CRLF to LF for text and leave
binary untouched, so the same value verifies on either line-ending convention;
`python skills/scripts/content_hash.py <path>` prints it.

## One writer per path

This is the rule that keeps concurrent phases from stepping on each other.

`session-memory` owns the run record and writes it only through
`skills/harness/hooks/save_run.py`. Each phase lead owns its phase directory. A
specialist writes only the artifact its delegation named. Gatekeepers write
verdicts and never touch a submission.

[`save-ownership.yaml`](../skills/save-ownership.yaml) is the path-level policy;
[`ownership.yaml`](../skills/ownership.yaml) is the artifact-level owner map.
`skills/validation/test_save_contracts.py` checks the two agree, and
`pre_tool_use.py` denies edit-tool writes to core run files outright.

## Lifecycle

```bash
python skills/harness/hooks/save_run.py create     --run-id <run> --evidence <path>
python skills/harness/hooks/save_run.py checkpoint --run-id <run> --expect-revision <n> --evidence <path>
python skills/harness/hooks/save_run.py status     --run-id <run>
python skills/harness/hooks/save_run.py complete   --run-id <run>
python skills/harness/hooks/save_run.py recover    --run-id <run> --reason "<why>" [--rollback]
```

`create` runs a write, read, and delete probe before claiming anything, and
refuses while another run holds the session pin. Persistence is active only once
it returns `ok`.

Checkpoint before every delegation and at every returned boundary. Each checkpoint
snapshots the previous revision into `_history/`, registers evidence hashes,
refreshes the heartbeat, and publishes state, lock, and pointer atomically behind
`_journal.json`.

An interrupted publish shows up as `interrupted` and is repaired with
`recover --rollback`. While the journal exists, every other operation is refused
rather than layering a second partial write on top of the first.

Exit codes matter here. 0 is `ok`. 1 is `refused`, which is a contract violation to
resolve, never something to work around by hand-editing save files. 2 is
`degraded`, meaning the write failed and nothing coherent was published.

## Locks and staleness

A lock records owner, status, session pin, revision, and an ISO-8601 heartbeat.
Active state needs a pinned, held lock. Terminal state needs an unpinned, released
one. A lock goes stale when its heartbeat is more than 30 minutes old.

With hooks registered, `post_tool_use.py` refreshes the heartbeat from real host
activity, throttled to once every five minutes, so an attended run does not go
stale mid-phase. It will not revive a lock that is already stale.

Reclaiming a stale lock requires `recover --reason`, which writes the stale lock's
path, heartbeat, owner, and sha256 into the audit trail before taking it. Nothing
disappears quietly.

## What startup sees

`save_run.py status` (or the readiness diagnostic) classifies saved state as
active, inactive, complete, stale, orphaned, conflicting, corrupt, interrupted,
missing, or unreadable. Only a coherent fresh active or orphaned record reinforces
the session pin.

`_latest.md` is a pointer, not the truth. When it is missing, stale, or disagrees
with a reclaimable run, scan `runs/` before concluding there is nothing to resume.

A lost pointer is not a lost run.

## Resume and rewind

On resume, verify the pointer, lock, owner, revision, referenced artifacts,
hashes, and evidence before picking a state. Then continue from the next
incomplete boundary.

When upstream evidence changes, rewind to the earliest affected boundary and
invalidate only the verdicts that actually depend on it. A verdict survives only
when `check.py --prior` reports `prior_reusable: true`.

## Repository hygiene

`skillset-saves/` is local runtime state: locks, audit trails, gate packages, and
resumable deliverables for the current workspace. It is in `.gitignore` and should
stay there.

Keep it to resume or audit a run. Delete it when you actually mean to throw that
history away.

Coverage output is part of that runtime state, not part of your repository.
Anything named `.coverage`, `.coverage.*`, `.coverage/`, `htmlcov/`, or
`.nyc_output/` at the project root is residue a test step left behind; the data
belongs in the run at `evidence/coverage/`, resolved with
`skills/scripts/output_paths.py --kind coverage`. Point `COVERAGE_FILE`,
`--data-file`, `--cov-report`, `--coverage.reportsDirectory`, or `--report-dir`
plus `--temp-dir` there before the runner starts, and never use parallel or
per-process mode without a `coverage combine` into that destination — one
observed run wrote a `.coverage` tree of over three thousand files in under two
minutes that way. After a command action `post_tool_use.py` moves whatever is
left into the run's `evidence/coverage/` (or, with no active run, into
`.harness-state/test-work/coverage-residue/<timestamp>/`), combining the
fragments where it can and deleting nothing. Those names are in `.gitignore` and
should stay there.
