# Persistent Saves

Supreme Team includes a persistent save system that writes pipeline state,
deliverables, gatekeeper verdicts, and audit trails to disk as the pipeline
runs. This removes dependency on the context window and enables cross-session
resume.

## How It Works

When admiral (or any sub-orchestrator in standalone mode) starts a pipeline run,
it creates a `skillset-saves/` directory in the **active project's workspace
root**:

```

## Repository Hygiene

`skillset-saves/` is local runtime state. It contains run locks, audit trails,
handoff packages, and resumable deliverables for the current workspace. The
directory is intentionally listed in `.gitignore` and must not be committed to
the Supreme Team source repository.

Keep `skillset-saves/` when you want Admiral to resume or audit a local run.
Delete it only when you intentionally want to discard local run history.
your-project/
├── skillset-saves/
│   ├── _index.md          # Registry of all pipeline runs
│   ├── _latest.md         # Pointer to active run
│   ├── _save-protocol.md  # Self-documenting copy of save specification
│   └── runs/
│       └── run-001_2026-04-07_my-project/
│           ├── _state.md          # State machine snapshot (resume file)
│           ├── _lock.md           # Advisory session lock (lease-based)
│           ├── _audit-trail.md    # Every state transition logged
│           ├── design/            # Design phase deliverables + verdicts
│           ├── build/             # Build phase deliverables + verdicts
│           └── review/            # Review phase reports + verdicts
├── src/
└── ...
```

## Key Features

- **Cross-session resume**: Start a pipeline, close the conversation, come back
  later — admiral detects the active run and offers to resume from exactly where
  you left off
- **Failure state recovery**: Crash-resilient state machine with
  `{PHASE}_GATE_PENDING`, `{PHASE}_GATE_REVISE`, `{PHASE}_FAILED`, and
  `DISPUTED_AWAITING_USER` states — session crashes never cause duplicate
  submissions or lost verdicts
- **Lease-based session locking**: `_lock.md` with heartbeat refresh prevents
  concurrent session corruption and enables stale-session detection on resume
- **Sub-orchestrator support**: Each sub-orchestrator (commander,
  build-management, code-chief) participates in the save tree with full lock
  lifecycle, skip-records, and resume protocol. Per the entry-routing doctrine,
  delivery-lifecycle work initiates through admiral, so a sub-orchestrator
  reached cold hands off to admiral first rather than starting an independent run
- **Idempotent gatekeeper submissions**: Every handoff carries a unique
  `submission_id`; on resume, existing verdicts are detected before resubmission
- **State-artifact consistency validation**: On every resume, a 6-step check
  detects and corrects orphaned verdicts, orphaned packages, pending
  escalations, and state/artifact desync
- **Session boundary tracking**: `SESSION_START`, `SESSION_CRASH_DETECTED`,
  `SESSION_RESUME`, and `SESSION_END` events with session IDs for crash
  detection
- **Context degradation tiers**: Four-tier system (Normal -> Save-Degraded ->
  Context-Pressured -> Double-Degraded) with automatic detection and user
  notification when artifacts are passed by reference instead of inline
- **Deliverable backup**: Every SRS, architecture doc, test report, and security
  audit is saved to disk as it's produced
- **Audit trail**: Complete chronological log of every state transition,
  gatekeeper verdict, session boundary, and revision cycle
- **Graceful degradation**: If saves fail or are unavailable, the pipeline
  continues with in-context artifacts; critical state transitions retry once
  before warning the user about persistence gaps
- **Self-documenting**: A copy of `skills/save-protocol.md` is placed in
  `skillset-saves/` so the directory structure is understandable on its own

The save check runs at admiral startup: it classifies the latest run as
active/inactive/orphaned/missing/unreadable, resumes an active or recoverable
run before starting a new one, and rebuilds a missing or stale `_latest.md`
pointer by scanning `runs/`. A lost pointer is never treated as a lost run.

See `skills/save-protocol.md` for the complete specification — directory
structure, file formats, the write-capability probe, mode re-check, session pin,
save triggers, and the resume protocol.
