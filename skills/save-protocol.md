# Skillset Saves — Persistent Save Protocol

## Overview

The `skillset-saves/` system provides persistent, tree-structured memory for the Supreme Team pipeline. It lives in the **active project's workspace root** (the directory being worked on, NOT inside Supreme_Team) and is used by all skills to save deliverables, track pipeline state, record gatekeeper verdicts, and enable cross-session resume.

> **Core principle**: Every pipeline artifact is saved to disk as it is produced. The conversation context window is no longer the single source of truth — `skillset-saves/` is the persistent backup that survives context compaction and session boundaries.

---

## Directory Structure

```
{workspace-root}/skillset-saves/
├── _index.md                               # Master registry of all pipeline runs
├── _latest.md                              # Pointer to the active/latest run
├── _save-protocol.md                       # This file (self-documenting copy)
│
└── runs/
    └── {run-id}/                            # One directory per pipeline execution
        ├── _run-manifest.md                 # User request, constraints, mode, stage status
    ├── _lock.md                         # Advisory session lock and crash-detection marker
        ├── _state.md                        # Current state machine snapshot (resume file)
        ├── _audit-trail.md                  # Chronological log of all state transitions
        │
        ├── admiral/
        │   ├── intake.md                    # Captured user request + constraints + mode
    │   ├── standalone-context.md        # Fallback input when upstream stages are absent or user-supplied
        │   ├── pipeline-record.md           # Admiral's running traceability record
        │   └── delivery-package.md          # Final unified delivery (when complete)
        │
        ├── design/
    │   ├── _skip-record.md              # Present only when Design was skipped or externally supplied
        │   ├── commander/
        │   │   ├── delegation-log.md        # Commander's delegation history
        │   │   ├── stack-lock-registry.md   # Accumulated stack locks
        │   │   └── design-package.md        # Consolidated design package
        │   │
        │   ├── phase-{N}_{skill-name}/      # One per design phase (1-5)
        │   │   ├── deliverable_{name}.md    # Skill deliverables (one per artifact)
        │   │   ├── review-packet.md         # Review packet for gatekeeper (design + azure pipelines only)
        │   │   ├── gatekeeper-verdict.md    # Gatekeeper-design verdict
        │   │   └── _phase-state.md          # Phase status tracker
        │   │
        │   └── gatekeeper-admiral_handoff-1.md
        │
        ├── build/
        │   ├── _skip-record.md              # Present only when Build was skipped or externally supplied
        │   ├── build-management/
        │   │   ├── delegation-log.md
        │   │   └── build-package.md
        │   │
        │   ├── phase-{N}_{skill-name}/      # One per build phase (1-4)
        │   │   ├── deliverable_{name}.md
        │   │   ├── gatekeeper-verdict.md
        │   │   └── _phase-state.md
        │   │
        │   └── gatekeeper-admiral_handoff-2.md
        │
        ├── review/
        │   ├── _skip-record.md              # Present only when Review was skipped or externally supplied
        │   ├── code-chief/
        │   │   ├── delegation-log.md
        │   │   └── review-package.md
        │   │
        │   ├── phase-{N}_{skill-name}/      # One per review phase (1-6)
        │   │   ├── deliverable_{name}.md
        │   │   └── _phase-state.md
        │   │
        │   ├── gatekeeper-code_verdict.md   # Consolidated verdict (not per-phase; see §Gatekeeper Verdict note)
        │   └── gatekeeper-admiral_handoff-3.md
        │
        └── azure/
            ├── _skip-record.md              # Present only when Azure was skipped or not targeted
            ├── azure-provisioner/
            │   ├── delegation-log.md
            │   ├── pipeline-record.md       # Azure provisioner's running traceability record
            │   └── azure-package.md         # Consolidated Azure package
            │
            ├── phase-{N}_{skill-name}/      # One per azure phase (1-5)
            │   ├── deliverable_{name}.md
            │   ├── review-packet.md         # Review packet for gatekeeper (design + azure pipelines only)
            │   ├── gatekeeper-verdict.md
            │   └── _phase-state.md
            │
            └── gatekeeper-admiral_handoff-4.md
```

### Phase Directory Names

| Pipeline | Phase | Directory Name |
|----------|-------|----------------|
| Design | 1 | `phase-1_researcher` |
| Design | 2 | `phase-2_planner` |
| Design | 3 | `phase-3_architect` |
| Design | 4 | `phase-4_designer` |
| Design | 5 | `phase-5_engineer` |
| Build | 1 | `phase-1_bob-the-builder` |
| Build | 2 | `phase-2_test-builder` |
| Build | 3 | `phase-3_security-builder` |
| Build | 4 | `phase-4_cross-check` |
| Review | 1 | `phase-1_bug-review` |
| Review | 2 | `phase-2_code-review` |
| Review | 3 | `phase-3_quality-review` |
| Review | 4 | `phase-4_security-review` |
| Review | 5 | `phase-5_mr-robot` |
| Review | 6 | `phase-6_frontier` |
| Azure | 1 | `phase-1_azure-planner` |
| Azure | 2 | `phase-2_azure-architect` |
| Azure | 3 | `phase-3_azure-configurator` |
| Azure | 4 | `phase-4_azure-deployer` |
| Azure | 5 | `phase-5_azure-verifier` |

---

## Run ID Format

```
run-{NNN}_{YYYY-MM-DD}_{slug}
```

- **NNN**: Zero-padded sequential number (001, 002, 003...)
- **YYYY-MM-DD**: Date the run was initiated
- **slug**: Short project name derived from the user request (max 30 chars, lowercase, hyphens only)

Examples:
- `run-001_2026-04-07_task-mgmt-api`
- `run-002_2026-04-10_ecommerce-platform`
- `run-003_2026-04-12_task-mgmt-api` (re-run of same project)

To generate the next run number: count existing directories in `runs/` and add 1.

---

## Session Management & Concurrency

Every active run has exactly one advisory lock file: `runs/{run-id}/_lock.md`.
The lock is used for collision avoidance, crash detection, and deterministic
resume behavior. It is advisory rather than fatal: stale or conflicting locks
must warn and be recorded, not silently overwrite prior session ownership.

### Session ID Format

```
sess-{YYYYMMDDTHHMMSSZ}-{random8}
```

- The timestamp is UTC and reflects the session start or resume time
- `random8` is an 8-character lowercase hexadecimal suffix
- Session IDs MUST be unique per run attempt; never reuse a prior session ID on resume

### Lock Lease Model

Locks use a renewable lease so an active session is not replaced while it is
still making progress.

- `lease_timeout_seconds` is recorded in `_lock.md`; default to `600` unless a
  pipeline-specific runtime documents a shorter safe interval
- An `ACTIVE` lock is considered live while `last_heartbeat` is within the
  lease window
- An `ACTIVE` lock owned by a different `session_id` becomes takeover-eligible
  only after the lease expires or the lock is explicitly released
- Long-running delegations or external waits must refresh `last_heartbeat` at
  least once every 300 seconds even when `_state.md` does not change
- Live-session conflicts are fail-closed: do NOT automatically replace a
  different session's `ACTIVE` lock while its heartbeat is still fresh

### Lock Acquisition Rules

1. On `RUN_INIT`, write `_lock.md` with the new `session_id`, `lock_status: ACTIVE`,
  `acquired_at`, `last_heartbeat`, `lease_timeout_seconds`, and `admiral_state`
2. On resume, read `_lock.md` before trusting `_state.md`
3. If `_lock.md` is `ACTIVE` for a different `session_id` and the heartbeat is
  still within the lease window, treat it as a live-session conflict:
  - warn the user that another session still owns the run
  - do NOT advance automatically or overwrite the lock
  - wait for the user to retry later or explicitly force takeover
4. If `_lock.md` is `ACTIVE` for a different `session_id`, the lease has
  expired, and the audit trail has no corresponding `SESSION_END`, treat the
  prior session as uncleanly terminated:
  - append `SESSION_CRASH_DETECTED` to `_audit-trail.md`
  - mark the prior lock as `STALE`
  - acquire the lock for the new session
5. If `_lock.md` is `RELEASED`, acquire it normally for the new session
6. If `_lock.md` is missing but `_state.md` exists, resume is still allowed;
  record a warning and recreate `_lock.md`
7. The active session refreshes `last_heartbeat` whenever `_state.md` is updated
  and at least once every 300 seconds while waiting on long-running delegated
  work

### Critical Write Ownership Check

Before writing any deliverable, verdict, `_state.md`, `_audit-trail.md`,
consolidated package, or delivery package:

1. Re-read `_lock.md`
2. Confirm `session_id` matches the current session and `lock_status` is `ACTIVE`
3. If a different session owns a fresh `ACTIVE` lease, stop writing and re-enter
   the conflict / resume flow instead of overwriting shared state

### Lock Release Rules

- On clean completion (`DELIVERED`) or explicit abort, set `_lock.md` to `RELEASED`
- On handoff to a standalone sub-orchestrator, the same `session_id` remains authoritative
- Never delete `_lock.md`; preserve it as a trace of the last owning session

---

## File Formats

Every file in `skillset-saves/` uses YAML frontmatter + markdown body.

### `_index.md` — Master Registry

```markdown
---
type: skillset-saves-index
version: 1.0.0
total_runs: {count}
active_run: {run-id or "none"}
last_updated: {ISO 8601 timestamp}
---

# Skillset Saves — Master Index

| Run ID | Project | Mode | Status | Started | Last Activity |
|--------|---------|------|--------|---------|---------------|
| {run-id} | {project name} | {pipeline mode} | {admiral state} | {date} | {timestamp} |
```

### `_latest.md` — Active Run Pointer

```markdown
---
type: latest-pointer
active_run_id: {run-id or "none"}
active_run_path: runs/{run-id}
pipeline_state: {admiral state}
last_completed_gate: {last gate passed}
last_updated: {ISO 8601 timestamp}
---
```

### `_run-manifest.md` — Run Metadata

```markdown
---
type: run-manifest
run_id: {run-id}
project_name: {human-readable project name}
pipeline_mode: {full|design-only|build-only|review-only|azure-only|design-build|build-review|review-azure|design-build-review-azure|...}
initiated: {ISO 8601 timestamp}
last_updated: {ISO 8601 timestamp}
admiral_state: {state}
design_state: {state or PENDING or SKIPPED}
build_state: {state or PENDING or SKIPPED}
review_state: {state or PENDING or SKIPPED}
azure_state: {state or PENDING or SKIPPED or NOT_APPLICABLE}
---

## User Request (Verbatim)
> {exact user request text}

## Constraints
{captured constraints as bullet list}

## Stage Status
| Stage | State | Gate Verdict | Revisions |
|-------|-------|-------------|-----------|
| Design | {state} | {verdict or PENDING} | {n}/{max} |
| Build | {state} | {verdict or PENDING} | {n}/{max} |
| Review | {state} | {verdict or PENDING} | {n}/{max} |
| Azure | {state} | {verdict or PENDING or N/A} | {n}/{max} |
```

### `_lock.md` — Advisory Session Lock

```markdown
---
type: run-lock
version: 1.0.0
run_id: {run-id}
session_id: {sess-YYYYMMDDTHHMMSSZ-random8}
lock_status: {ACTIVE|STALE|RELEASED}
acquired_at: {ISO 8601 timestamp}
last_heartbeat: {ISO 8601 timestamp}
lease_timeout_seconds: {integer, default 600}
admiral_state: {state}
previous_session_id: {session id displaced on resume or null}
---

## Lock Notes
- Reason acquired or replaced
- Any collision warning shown to the user
```

### `_state.md` — Compact Resume File

This is the critical file for cross-session resume. Keep it compact.

```markdown
---
type: state-snapshot
version: "1.2.0"
run_id: {run-id}
snapshot_time: {ISO 8601 timestamp}
session_id: {unique session identifier — format: sess-{YYYYMMDDTHHMMSSZ}-{random8}}
previous_session_id: {previous session id or null}
admiral_state: {state}
design_state: {state}
build_state: {state}
review_state: {state}
azure_state: {state or PENDING or SKIPPED or NOT_APPLICABLE}
current_phase_attempt: {attempt number}
# --- Failure & recovery tracking ---
gatekeeper_verdict_pending: {true/false}
last_gatekeeper_submission_id: {submission_id or null}
last_gatekeeper_handoff: {1/2/3/4 or null}
disputed_awaiting_user_decision: {true/false}
escalation_context: {legacy short description or null}
escalation_summary: {brief user-facing summary or null}
escalation_context_ref: {path to saved escalation record or null}
failure_state: {null or description of failure}
failure_reason: {null or error details}
last_successful_artifact: {path to last confirmed artifact or null}
skipped_stages: {[design|build|review|azure] or []}
standalone_fallback_ref: {path to admiral/standalone-context.md or null}
# --- Context management ---
context_tier: {1|2|3|4}
artifact_mode: {inline|reference|best-effort-inline}
artifact_integrity_status: {VERIFIED|UNVERIFIED|FAILED}
artifact_integrity_notes: {brief explanation or null}
---

## Resume Instructions
1. Load `_lock.md` and confirm this session owns the active lock before trusting `_state.md`
2. Load `_run-manifest.md` for user request, constraints, and skipped-stage status
3. Load `{last approved package path}` as input to the current stage, or `standalone_fallback_ref` when upstream stages were intentionally absent
4. Resume `{current orchestrator}` at `{current state}`
5. If `gatekeeper_verdict_pending` is true: check the corresponding handoff file for an existing verdict before resubmitting
6. If `disputed_awaiting_user_decision` is true: re-present `escalation_summary` and `escalation_context_ref` to the user — do NOT advance the pipeline
7. If `failure_state` is not null: present failure details and offer recovery options (retry / skip / abort)
8. If `artifact_integrity_status` is `UNVERIFIED` or `FAILED`: surface the limitation before advancing the pipeline
9. Check `context_tier` and `artifact_mode` and apply the corresponding artifact passing mode for resumed delegations
```

### `_audit-trail.md` — Chronological Log

```markdown
---
type: audit-trail
run_id: {run-id}
entries: {count}
---

# Audit Trail

| # | Timestamp | Pipeline | Skill | From → To | Event |
|---|-----------|----------|-------|-----------|-------|
| {n} | {HH:MM} | {pipeline} | {skill} | {from} → {to} | {event description} |
```

#### Session Boundary Events

The audit trail MUST include session boundary markers to enable crash detection and resume tracing:

| Event Type | When Recorded | Format |
|------------|---------------|--------|
| `SESSION_START` | Pipeline initialization or fresh start | `SESSION_START — session_id: {id}` |
| `SESSION_CRASH_DETECTED` | Resume detects prior session did not complete cleanly | `SESSION_CRASH_DETECTED — previous session: {id}, crashed at state: {state}` |
| `SESSION_RESUME` | Pipeline resumes from saved state | `SESSION_RESUME — session_id: {new-id}, resuming from: {state}, corrections: {list or "none"}` |
| `SESSION_END` | Pipeline reaches DELIVERED or user aborts | `SESSION_END — session_id: {id}, final state: {state}` |

The `session_id` is recorded in `_state.md`. If `_state.md` contains a `session_id` but the current session has a different id and no `SESSION_END` was logged, the prior session did not end cleanly — record `SESSION_CRASH_DETECTED` before `SESSION_RESUME`.

### `_phase-state.md` — Per-Phase Status

```markdown
---
type: phase-state
pipeline: {design|build|review|azure}
phase: {number}
skill: {skill-name}
state: {PENDING|ACTIVE|REVIEW|APPROVED|REVISING}
revision_attempts: {count}
max_revisions: {max}
started: {ISO 8601 timestamp or null}
completed: {ISO 8601 timestamp or null}
---

## Deliverables
{numbered list of deliverable filenames}

## Gatekeeper Verdict
{verdict summary or "PENDING"}
```

### `deliverable_{name}.md` — Deliverable Envelope

```markdown
---
type: deliverable
pipeline: {design|build|review|azure}
phase: {number}
skill: {skill-name}
name: {human-readable deliverable name}
version: {version number, starts at 1, increments on revision}
status: {draft|submitted|approved|revised}
created: {ISO 8601 timestamp}
---

{Full deliverable content as produced by the skill — verbatim, unmodified}
```

### `gatekeeper-verdict.md` — Verdict Record

```markdown
---
type: gatekeeper-verdict
pipeline: {design|build|review|azure}
phase: {number}
gatekeeper: {gatekeeper skill name}
verdict: {APPROVED|REVISE|ESCALATE}
attempt: {attempt number}
critical: {count}
major: {count}
minor: {count}
timestamp: {ISO 8601 timestamp}
---

{Full gatekeeper review content — verbatim}
```

> **Review pipeline naming note**: Design, Build, and Azure pipelines use per-phase `gatekeeper-verdict.md` files inside each phase directory. The Review pipeline uses a single consolidated `gatekeeper-code_verdict.md` at the pipeline level (`review/gatekeeper-code_verdict.md`) because gatekeeper-code validates all review specialist reports in a single pass rather than per-phase. The schema is identical; only the filename and location differ.

### `pipeline-record.md` — Traceability Record

A running log of orchestrator decisions, delegation outcomes, and traceability notes. Written by admiral and azure-provisioner. Created at RUN_INIT (or standalone init) with the initial entry, then appended after each state transition, delegation return, or gatekeeper verdict.

```markdown
---
type: pipeline-record
version: 1.0.0
run_id: {run-id}
owner: {admiral|azure-provisioner}
created_at: {ISO 8601 timestamp}
last_updated: {ISO 8601 timestamp}
entries: {count}
---

# Pipeline Traceability Record

| # | Timestamp | Event | Detail |
|---|-----------|-------|--------|
| {n} | {ISO 8601} | {DELEGATION_SENT|DELEGATION_RETURNED|GATE_SUBMITTED|GATE_VERDICT|STATE_CHANGE|DECISION|NOTE} | {brief description} |
```

### `review-packet.md` — Specialist Review Packet

A structured summary prepared by design and azure specialists alongside their deliverables, packaging the review context that the gatekeeper needs. Build and review specialists are exempt — their gatekeepers receive deliverables directly without a separate review packet.

```markdown
---
type: review-packet
version: 1.0.0
pipeline: {design|azure}
phase: {number}
skill: {skill-name}
run_id: {run-id}
created: {ISO 8601 timestamp}
deliverable_count: {number of deliverables in this phase}
---

## Deliverable Summary
{Brief summary of what was produced and key decisions made}

## Review Checklist
{Skill-specific checklist items the gatekeeper should validate}

## Cross-References
{References to upstream artifacts, stack locks, or constraints that informed this deliverable}
```

### `gatekeeper-admiral_handoff-{N}.md` — Cross-Pipeline Gate

```markdown
---
type: gatekeeper-admiral-verdict
handoff: {1|2|3|4}
from_pipeline: {design|build|review|azure}
to_pipeline: {build|review|azure|delivery}
submission_id: {unique submission id — format: {run-id}_handoff-{N}_attempt-{M}_{ISO-timestamp}}
submission_status: {PENDING|VERDICT_RECORDED}
verdict: {PENDING|APPROVED|REVISE|ESCALATE}
attempt: {attempt number}
timestamp: {ISO 8601 timestamp}
verdict_recorded_at: {ISO 8601 timestamp or null}
---

{Full gatekeeper-admiral validation report — verbatim, or "Awaiting verdict" if PENDING}
```

**Two-phase write protocol**: This file is written in two steps to support idempotent resume:
1. **Before gatekeeper invocation**: Write with `submission_status: PENDING`, `verdict: PENDING`, `verdict_recorded_at: null`
2. **After verdict returns**: Update with actual verdict, `submission_status: VERDICT_RECORDED`, and `verdict_recorded_at` timestamp

On resume, if this file exists with `submission_status: VERDICT_RECORDED`: the verdict was already captured — process it directly without resubmitting to gatekeeper-admiral. If `submission_status: PENDING`: the gatekeeper was invoked but crashed before returning — resubmit with the same `submission_id`.

### `standalone-context.md` — Upstream Replacement Context

Use this file when the pipeline intentionally begins after an upstream stage or
when a user provides external artifacts that replace earlier pipeline output.

```markdown
---
type: standalone-context
version: 1.0.0
run_id: {run-id}
entry_mode: {build-only|review-only|azure-only|standalone}
created_at: {ISO 8601 timestamp}
source_of_truth: {user request|user-supplied artifact|mixed}
trust_level: {USER_SUPPLIED|PARTIALLY_VERIFIED|GATEKEEPER_APPROVED}
replacement_for: {[design|build|review] or []}
---

## Context Summary
[Concise summary of the upstream information that downstream stages may rely on]

## Artifact Inventory
- [Artifact path or external reference] — [what it replaces]

## Resume Rules
- Which downstream stages may rely on this file
- Which consistency checks become `UNVERIFIED`
```

### `_skip-record.md` — Skipped or Replaced Stage Record

Write this file only when a stage is intentionally skipped, not required, or
replaced by external context.

```markdown
---
type: stage-skip-record
version: 1.0.0
run_id: {run-id}
pipeline: {design|build|review|azure}
status: {SKIPPED|USER_SUPPLIED|NOT_REQUIRED}
recorded_at: {ISO 8601 timestamp}
decision_source: {user|mode-selection|resume-correction}
replacement_context_ref: {path to standalone-context.md or null}
downstream_effect: {N/A|UNVERIFIED_UPSTREAM|LIMITED_TRACEABILITY|DELIVERY_ONLY}
---

## Reason
[Why the stage was skipped or replaced]

## Required Notices
- What downstream delegates must disclose
- Which checks become `N/A` or `UNVERIFIED`
```

---

## Save Triggers

| Trigger | Who Fires | What Gets Written |
|---------|-----------|-------------------|
| **RUN_INIT** | Admiral (or standalone orchestrator) | `_index.md`, `_latest.md`, `_run-manifest.md`, `_lock.md`, `_state.md`, `_audit-trail.md`, `admiral/intake.md`, `_save-protocol.md` (self-documenting copy at `skillset-saves/` root) |
| **RUN_LOCK_ACQUIRE** | Admiral (or standalone orchestrator) | `_lock.md` heartbeat/status update |
| **DELIVERABLE_COMPLETE** | Specialist skill | `deliverable_*.md` file(s) + `review-packet.md` (design and azure pipelines only; build and review specialists are exempt) |
| **GATE_VERDICT** | Orchestrator (captures gatekeeper result) | `gatekeeper-verdict.md` + `_phase-state.md` update |
| **SKIP_DECISION** | Admiral | `{pipeline}/_skip-record.md` + `_run-manifest.md` + `_state.md` + `_audit-trail.md` |
| **STATE_TRANSITION** | Orchestrator | `_state.md` update + `_audit-trail.md` append |
| **PACKAGE_CONSOLIDATION** | Sub-orchestrator | `design-package.md` / `build-package.md` / `review-package.md` + `delegation-log.md` |
| **CROSS_PIPELINE_GATE** | Admiral | `gatekeeper-admiral_handoff-{N}.md` + `_state.md` + `_latest.md` update |
| **AZURE_PACKAGE_CONSOLIDATION** | Azure-provisioner | `azure/azure-provisioner/azure-package.md` + `azure/azure-provisioner/pipeline-record.md` + `azure/azure-provisioner/delegation-log.md` |
| **RUN_COMPLETE** | Admiral | `delivery-package.md` + final `_index.md` / `_latest.md` updates |

---

## Write Responsibility

Clean separation of who writes what:

- **Orchestrators** (admiral, commander, build-management, code-chief, azure-provisioner) own:
  - State files: `_state.md`, `_audit-trail.md`, `_run-manifest.md`, `_latest.md`
  - Lock file: `_lock.md`
  - Phase tracking: `_phase-state.md` (created in each phase directory)
  - Gatekeeper captures: `gatekeeper-verdict.md` (written after receiving gatekeeper output)
  - Consolidated packages: `design-package.md`, `build-package.md`, `review-package.md`, `azure-package.md`
  - Delegation logs: `delegation-log.md`
  - Standalone fallback context: `admiral/standalone-context.md`
  - Skipped stage records: `{pipeline}/_skip-record.md`

- **Specialists** (researcher, planner, architect, azure-planner, azure-architect, etc.) own:
  - Deliverable files: `deliverable_{name}.md`
  - Review packets: `review-packet.md` (design and azure pipeline specialists only; build and review specialists are exempt — their gatekeepers receive deliverables directly)

- **Gatekeepers** do NOT write directly to `skillset-saves/`
  - Their output is captured by the invoking orchestrator
  - This matches the existing pattern where orchestrators own the gatekeeper cycle

> For the complete save ownership matrix and definitive component-to-file mappings, see `admiral/references/responsibility-matrix.md` §Layer 8: Save Ownership Matrix.

---

## Save Context (Delegation Integration)

Orchestrators include a `### Save Context` section in every delegation template to tell specialists where to save:

```markdown
### Save Context
- **Run ID**: {run-id}
- **Save path**: skillset-saves/runs/{run-id}/{pipeline}/phase-{N}_{skill}/
- **Persistence active**: {yes|no}
- **Context tier**: {1|2|3|4}
- **Artifact mode**: {inline|reference|best-effort-inline}
- **Standalone fallback ref**: {path or "none"}
- **Skipped upstream stages**: {none or list}
```

**Rules**:
- If `Save Context` is present with `Persistence active: yes`: specialist writes deliverables to the save path
- If `Save Context` is absent or `Persistence active: no`: specialist skips all save operations
- This ensures backward compatibility — skills work identically without saves

---

## Resume Protocol

### Detection (Admiral or standalone orchestrator on startup)

```
1. Check: does {workspace-root}/skillset-saves/ exist?
   ├── No  → Create it and start a new run (or skip saves entirely)
   └── Yes → Read _latest.md
              ├── No active run (active_run_id = "none") → Start new run
              └── Active run found → Read _state.md
                   ├── User request matches → Offer: "Resume from {state} or start fresh?"
                   └── Different project → Start new run
2. Before resuming or starting fresh on an existing run, acquire `_lock.md`
  ├── ACTIVE for same session_id → continue
  ├── ACTIVE for different session_id with fresh heartbeat → stop automatic resume, warn about live conflict, require user decision
  ├── ACTIVE for different session_id with expired heartbeat and no SESSION_END → record crash, stale prior lock, continue with warning
  ├── RELEASED → acquire for current session
  └── Missing → recreate lock and continue with warning
```

### Loading State on Resume

1. Read `_lock.md` and `_state.md` for the exact pipeline position and active-session ownership
2. If `_lock.md`, `_state.md`, or `_run-manifest.md` is present but unreadable, truncated, or missing required frontmatter fields: treat it as a control-file integrity failure, set `artifact_integrity_status: FAILED`, and stop automatic resume pending user direction
3. Read `_run-manifest.md` for user request, constraints, mode, and skipped-stage status
4. Read the last approved consolidated package for the completed stage (e.g., `design-package.md` if resuming at `BUILD_ACTIVE`)
5. If upstream packages were intentionally absent, read `standalone_fallback_ref` and any `{pipeline}/_skip-record.md` files instead of treating the absence as corruption
6. Read `_phase-state.md` for the current in-progress phase (if any)
7. If a phase was mid-execution (`ACTIVE` state): re-delegate to the specialist from scratch (deliverables from incomplete work are not trusted)
8. If a phase was at REVIEW (waiting for gatekeeper): re-read the deliverable and re-submit to gatekeeper
9. **Run state-artifact consistency validation** (see below)
10. Append to `_audit-trail.md`: `SESSION_RESUME — session_id: {new-id}, resuming from: {state}, corrections: {list or "none"}`

### State-Artifact Consistency Validation

Before executing any resume action, validate that `_state.md` and on-disk artifacts are consistent. This prevents duplicate work, duplicate gatekeeper submissions, and stale-state loops.

**Step 0 — Validate control files are readable**:
Before trusting `_lock.md`, `_state.md`, `_run-manifest.md`, or any authoritative
verdict file, confirm the YAML frontmatter and required fields can be read.
- If `_state.md` is unreadable or truncated: set `artifact_integrity_status: FAILED`, record a failure reason such as `CONTROL_FILE_CORRUPT`, and block automatic resume pending user direction
- If a verdict, package, or deliverable file is present but unreadable: treat it as an integrity failure for that artifact, not as authoritative evidence

**Step 1 — Check for orphaned verdicts (artifact ahead of state)**:
For each gate state (`{PHASE}_GATE_PENDING`), check if the corresponding `gatekeeper-admiral_handoff-{N}.md` file exists and contains `submission_status: VERDICT_RECORDED`:
- If found and `_state.md` still shows `*_GATE_PENDING`: the verdict was recorded but state was not updated. Adopt the verdict and advance `_state.md` to the correct post-verdict state.
- If found with `submission_status: PENDING`: the gatekeeper was invoked but did not return. Resubmit with the same `submission_id`.

**Step 2 — Check for orphaned packages (sub-orchestrator completed but state not updated)**:
For each ACTIVE state, check if the sub-orchestrator's consolidated package file exists (e.g., `design-package.md` for `DESIGN_ACTIVE`, `azure-package.md` for `AZURE_ACTIVE`):
- If the package exists but `_state.md` still shows `*_ACTIVE`: the sub-orchestrator completed but state was not advanced. Move to `*_GATE_PENDING`.

**Step 3 — Check for pending escalations**:
If `disputed_awaiting_user_decision` is `true` in `_state.md`: do NOT advance the pipeline. Re-present the stored `escalation_context` to the user and await their decision.

**Step 4 — Check for failure states**:
If `failure_state` is not null in `_state.md`: present the failure details and `failure_reason` to the user. Offer options: retry the stage, skip the stage (if non-mandatory), or abort the pipeline.

**Step 5 — Validate upstream artifacts exist**:
Before resuming any stage, confirm that required upstream artifacts are present on disk:
- `BUILD_ACTIVE` or `BUILD_GATE*` requires `design/commander/design-package.md`
- `REVIEW_ACTIVE` or `REVIEW_GATE*` requires both design and build packages
- `AZURE_ACTIVE` or `AZURE_GATE*` requires design, build, and review packages
- If a required artifact is missing but a matching `_skip-record.md` or `standalone-context.md` exists: continue with `artifact_integrity_status: UNVERIFIED` and surface the limitation
- If a required artifact is missing with no approved replacement context: warn the user and offer to re-run the upstream stage or fall back to user-provided context

**Step 5.5 — Validate artifact integrity**:
Before automatic advancement, validate the authoritative upstream artifacts:
- approved artifacts must still exist at the saved path
- the file must be readable as YAML frontmatter + markdown body; a present but unreadable file counts as `FAILED`, not `VERIFIED`
- the file frontmatter must still match the current `run_id`, `pipeline`, and approved `status`
- the artifact must not contradict its approving verdict or skip record
- if exact integrity cannot be proven, set `artifact_integrity_status: UNVERIFIED` and notify the user before advancing
- if artifacts contradict the recorded verdict, are externally mutated in a way that breaks traceability, or reference the wrong run, set `artifact_integrity_status: FAILED` and block automatic resume pending user direction

**Step 6 — Log all corrections**:
Append to `_audit-trail.md`: `SESSION_RESUME — corrections: {list of state adjustments or "none"}`

### Partial Pipeline Recovery (Standalone Mode)

When resuming a pipeline initiated in a partial mode (e.g., `build-only`, `review-only`) or invoked directly bypassing `admiral`:
1. **Context Check**: Identify the `pipeline_mode` and `admiral_state` from `_run-manifest.md`.
2. **Fallback Source of Truth**: If resuming a `review-only`, `build-only`, or `azure-only` run, do NOT fail simply because upstream pipeline deliverables are missing. Use `admiral/standalone-context.md` as the canonical replacement context.
3. **Skip Records are Required**: Any intentionally absent upstream stage must have a matching `{pipeline}/_skip-record.md` so downstream stages know whether the absence is `SKIPPED`, `USER_SUPPLIED`, or `NOT_REQUIRED`.
4. **User Notice Requirement**: Any downstream stage consuming `standalone-context.md` must surface that traceability is partially unverified and record that status in the final delivery package.
5. **Control Hand-off**: If `admiral_state` is `STANDALONE`, resume logic dictates control immediately passes to the executing sub-orchestrator (`commander`, `build-management`, `code-chief`, or `azure-provisioner`), completely bypassing `admiral`'s state machine.

### What Resume Preserves

- All completed deliverables (they are on disk)
- All gatekeeper verdicts (they are on disk)
- The exact pipeline position (from `_state.md`)
- The user's original request and constraints (from `_run-manifest.md`)
- The full audit trail of prior transitions (from `_audit-trail.md`)

### What Resume Does NOT Preserve

- In-context reasoning or discussion
- Partial deliverables from an interrupted specialist
- The gatekeeper's review-in-progress if interrupted mid-review

---

## Standalone Initialization Protocol

When a sub-orchestrator (commander, build-management, code-chief, or azure-provisioner) runs in standalone mode — invoked directly by the user, bypassing admiral — it MUST initialize the save system with the same minimum control files that admiral would create. The sub-orchestrator assumes the role of the top-level save owner for the duration of the run.

### Required Files on Standalone Init

The standalone orchestrator MUST write all of the following at startup:

1. `skillset-saves/_index.md` — Create or update the master registry
2. `skillset-saves/_latest.md` — Point to the new run
3. `skillset-saves/_save-protocol.md` — Self-documenting copy of this protocol
4. `skillset-saves/runs/{run-id}/_run-manifest.md` — With `pipeline_mode` reflecting the standalone scope (e.g., `design-only`, `build-only`, `review-only`, `azure-only`) and `admiral_state: STANDALONE`
5. `skillset-saves/runs/{run-id}/_lock.md` — Advisory lock with the new `session_id`, `lock_status: ACTIVE`, `admiral_state: STANDALONE`
6. `skillset-saves/runs/{run-id}/_state.md` — With `admiral_state: STANDALONE` and the relevant pipeline state set to its initial value (e.g., `design_state: DESIGN_ACTIVE`); all other pipeline states set to `SKIPPED` or `NOT_APPLICABLE`
7. `skillset-saves/runs/{run-id}/_audit-trail.md` — With `SESSION_START` entry
8. `skillset-saves/runs/{run-id}/{pipeline}/_skip-record.md` — One for each upstream pipeline that is intentionally absent (e.g., a standalone build run writes `design/_skip-record.md` with `status: SKIPPED` or `USER_SUPPLIED`)

### Optional Files

9. `skillset-saves/runs/{run-id}/admiral/standalone-context.md` — When the user provides external artifacts that replace upstream pipeline output; set `standalone_fallback_ref` in `_state.md` to this path
10. `skillset-saves/runs/{run-id}/admiral/intake.md` — Standalone orchestrators may replace this with their own intake context directly in their pipeline directory (e.g., `design/commander/delegation-log.md` initial entry) rather than writing to the `admiral/` directory

### Lock Lifecycle in Standalone Mode

Standalone orchestrators follow the same lock rules as admiral:
- **Acquisition**: Write `_lock.md` on init with `lock_status: ACTIVE` and a fresh `session_id`
- **Heartbeat**: Refresh `last_heartbeat` whenever `_state.md` is updated, and at least once every 300 seconds during long-running delegations
- **Conflict detection**: On resume, read `_lock.md` before trusting `_state.md`; follow the same live-session conflict and crash-detection rules as admiral (see §Session Management & Concurrency)
- **Release**: Set `_lock.md` to `RELEASED` on clean completion or explicit abort

### Resume in Standalone Mode

Standalone orchestrators MUST implement the full resume protocol, not a one-liner handwave:

1. Read `_lock.md` — handle conflict/crash/stale per §Session Management & Concurrency
2. Read `_state.md` — confirm `admiral_state: STANDALONE` and the relevant pipeline state
3. Run state-artifact consistency validation (§State-Artifact Consistency Validation) scoped to the active pipeline
4. Check for pending escalations (`disputed_awaiting_user_decision`) and failure states (`failure_state`)
5. Check `_skip-record.md` files and `standalone-context.md` for upstream context
6. Append `SESSION_RESUME` to `_audit-trail.md` with corrections list
7. Resume the sub-orchestrator's state machine at the recorded position

---

## Remediation Routing Save Behavior

### Build Phase 3→1 Security Remediation

When security-builder (Phase 3) produces remediation items that route back to bob-the-builder (Phase 1):

1. **Phase 3 deliverable is saved first**: `phase-3_security-builder/deliverable_security-audit.md` is written with the current version before any remediation routing
2. **Phase 1 re-entry updates the existing `_phase-state.md`**: The `phase-1_bob-the-builder/_phase-state.md` state reverts to `ACTIVE` (not `PENDING`) and the existing file is updated in-place — a new `_phase-state.md` is NOT created
3. **Deliverable version increments**: When bob-the-builder produces remediated code, the existing `deliverable_*.md` files in `phase-1_bob-the-builder/` are overwritten with `version` incremented by 1 in the YAML frontmatter
4. **A new gatekeeper-build verdict is written**: After re-validation, `phase-1_bob-the-builder/gatekeeper-verdict.md` is overwritten with the new attempt number
5. **Audit trail records the loop**: Build-management appends `REMEDIATION_LOOP — phase-3 → phase-1, reason: {remediation summary}` to `_audit-trail.md`

### Build Phase 4 Completeness Findings

When cross-check-build-confirm (Phase 4) produces FINDINGS (not CLEAN):

1. **Save on every scan cycle**: `phase-4_cross-check/deliverable_completeness-report.md` is written with `version` incremented on each scan, regardless of whether the result is FINDINGS or CLEAN
2. **FINDINGS route back to Phase 1**: Bob-the-builder fixes the issues and Phase 4 re-scans
3. **Final CLEAN is the last version**: The approved version has `status: approved` in the frontmatter; prior FINDINGS versions had `status: revised`

### Operational Retries (Azure Pipeline)

Azure-provisioner allows deployment execution failures (e.g., transient Azure API errors in Phase 4 azure-deployer) to be re-executed without counting as gatekeeper-azure revision cycles:

- **Deliverable version increments**: Each retry attempt writes a new version of the deliverable
- **`revision_attempts` does NOT increment**: Operational retries are distinct from gatekeeper revision cycles; `_phase-state.md` `revision_attempts` only increments when gatekeeper-azure issues a REVISE verdict
- **Audit trail records retries**: Append `OPERATIONAL_RETRY — phase-4, attempt: {N}, reason: {error}` to `_audit-trail.md`

---

## Graceful Degradation

### Standard Save Operations

Every save operation follows this pattern:

```
IF skillset-saves/ is available AND Save Context was provided:
    perform the save operation
    IF save fails (permissions, disk error, etc.):
        log a warning in-context: "⚠ Save failed for {file}: {reason}. Continuing without persistence."
        continue pipeline execution normally
ELSE:
    skip save operation silently (existing behavior preserved)
```

**Guarantees**:
- A save failure NEVER halts the pipeline
- Skills function identically without `skillset-saves/`
- Standalone-mode skills (user invokes directly, not via pipeline) skip saves unless they choose to initialize their own run
- The pipeline produces the same deliverables and follows the same state machine regardless of whether saves are active

### Durable Single-File Writes

Every individual file write in `skillset-saves/` uses the same single-file
durability protocol:

1. Run the Critical Write Ownership Check
2. Write the complete new contents to a temporary file in the same directory as the target
3. Flush buffers and fsync / sync the temporary file when the runtime allows
4. Atomically replace the target with the temporary file
5. Best-effort remove leftover temporary files if the replace fails

For append-oriented files such as `_audit-trail.md`, prefer a read-modify-rewrite
through the same durable replace flow unless the runtime can prove durable append
semantics.

### Critical State Transition Saves

Some save operations occur during critical state transitions (e.g., writing `_state.md` after a gatekeeper verdict). These use a stricter protocol:

```
1. Attempt the save operation
2. IF save fails:
   a. Log: "CRITICAL: State save failed for {file}: {reason}"
   b. Hold the state in-context memory — do NOT advance to the next pipeline action yet
   c. Retry the save once
   d. IF retry succeeds: continue normally
   e. IF retry fails:
      - Warn user: "Pipeline state could not be persisted. The pipeline will
        continue but cannot resume from this point if the session ends.
        Recommend completing the current stage without interruption."
      - Set context_tier to at least Tier 2 (save-degraded) in-context
      - Set `artifact_mode` to `inline` unless context pressure already requires Tier 4 handling
      - Continue pipeline execution
```

### Atomic Write Ordering

State transitions involve multiple file writes. To minimize desync risk on interruption, follow this strict ordering:

Each step below assumes the target file itself is written using the durable
single-file write protocol above and that the current session still owns the
`ACTIVE` lock immediately before the step executes.

1. **Artifact first**: Write the deliverable or verdict file (e.g., `gatekeeper-admiral_handoff-1.md`)
2. **State second**: Update `_state.md` with the new state and metadata
3. **Tracking third**: Append `_audit-trail.md`, update `_latest.md`, update `_run-manifest.md`

**Rationale**: If a crash occurs between steps 1 and 2, resume logic can detect the artifact exists but state was not updated, and recover by processing the artifact (see §State-Artifact Consistency Validation). If state were updated first, resume would skip the artifact-processing step and lose the verdict.

---

## Context-Aware Artifact Management

### The Problem

The conversation context window has a finite capacity. As pipeline artifacts accumulate (design packages, build packages, review reports, azure packages), the total volume can exceed what fits in context. The existing "pass all artifacts forward exactly as received" rule (workflow-protocol.md, Immutability Rule) must be reconciled with this physical constraint.

### Degradation Tiers

The pipeline operates in one of four degradation tiers. The current tier is tracked in `_state.md` (field: `context_tier`) and reported to the user.

| Tier | Condition | Artifact Handling | User Notice |
|------|-----------|------------------|-------------|
| **Tier 1: Normal** | Saves active, artifacts fit in context | All artifacts inline, saves active | None |
| **Tier 2: Save-Degraded** | Saves failed, artifacts fit in context | All artifacts inline, no persistence | "Warning: Pipeline persistence unavailable. Artifacts exist only in this session." |
| **Tier 3: Context-Pressured** | Saves active, artifacts too large for inline | Summaries inline + full artifacts referenced from saves | "Operating in reference mode. Full artifacts available at: {save-path}" |
| **Tier 4: Double-Degraded** | Saves failed AND artifacts too large | Best-effort summaries inline, no verified persistence | "CRITICAL: Both persistence and full-context are compromised. Artifact fidelity cannot be guaranteed. Recommend completing the current stage without interruption." |

### Context Pressure Detection

Orchestrators should monitor context pressure using these heuristics:

1. **Working-budget rule**: reserve at least 25% of the available context budget for delegation instructions, reasoning, and gatekeeper exchange. If inline artifacts would consume more than 75% of the working budget, switch to reference mode.
2. **Artifact count heuristic**: If more than 15 major artifacts (deliverables + packages + verdicts) have been produced in the current pipeline run, assume reference mode unless a smaller curated inline subset is clearly safe.
3. **Large-artifact heuristic**: If any single upstream artifact is too large to inspect accurately inline for schema-level, evidence-level, or traceability-level validation, it does NOT qualify for inline mode even if the total artifact count is low.
4. **Explicit signal**: If the system indicates context pressure (e.g., through truncation or compaction warnings), immediately switch to reference mode

These are heuristics, not hard thresholds, because the exact context capacity depends on the model and conversation history.

### Reference Mode Protocol

When operating in Tier 3 or Tier 4, artifacts are passed by reference rather than inline:

**Instead of:**
```markdown
### Approved Design Package
[FULL multi-thousand-line design package pasted inline]
```

**Use:**
```markdown
### Approved Design Package
**Mode**: Reference (full artifact on disk)
**Location**: skillset-saves/runs/{run-id}/design/commander/design-package.md
**Summary**: [3-5 sentence summary of the design package: key decisions, architecture style, stack locks, module count, critical constraints]
**Key artifacts for this delegation**:
- API Contracts: skillset-saves/runs/{run-id}/design/phase-3_architect/deliverable_api-contracts.md
- Stack Locks: skillset-saves/runs/{run-id}/design/commander/stack-lock-registry.md
- Implementation Spec: skillset-saves/runs/{run-id}/design/phase-5_engineer/deliverable_implementation-spec.md
```

**Rules for reference mode:**
1. The summary MUST capture enough context for the downstream consumer to operate without reading the full artifact
2. Key sub-artifacts that are directly needed by the downstream consumer SHOULD be listed with their save paths
3. The downstream consumer (sub-orchestrator or gatekeeper) may read referenced artifacts from disk as needed
4. Gatekeeper-admiral's existing save awareness (see `gatekeeper-admiral/references/cross-pipeline-criteria.md`) already supports this pattern
5. The summary is intentionally lossy. It is NOT authoritative for field-level schema review, exact evidence quoting, defect severity comparison, or final traceability verification.
6. Any downstream consumer needing exact text, exact counts, or exact contract structure MUST open the referenced artifact rather than rely on the inline summary.
7. If saves are unavailable, reference mode cannot guarantee fidelity; this escalates to Tier 4 and requires an immediate user notice.

### User Notice Rule

Whenever `context_tier` changes to Tier 2, Tier 3, or Tier 4, the active orchestrator MUST:

1. Surface the tier-specific notice to the user immediately
2. Record the same notice in `_audit-trail.md`
3. Carry the notice forward in the next delegation or delivery artifact that depends on the degraded context
4. State the operational limitation explicitly:
  - Tier 2: resume is no longer guaranteed beyond the current session
  - Tier 3: inline summaries are non-authoritative; full artifacts remain on disk
  - Tier 4: both resume and full artifact fidelity are unverified

### Tier Transitions

| From | To | Trigger | Action |
|------|----|---------|--------|
| Tier 1 | Tier 2 | Save operation fails | Log warning, continue inline, set `context_tier: 2` |
| Tier 1 | Tier 3 | Context pressure detected | Switch to reference mode, set `context_tier: 3`, set `artifact_mode: reference`, notify user |
| Tier 2 | Tier 4 | Context pressure detected while saves are failed | Set `context_tier: 4`, set `artifact_mode: best-effort-inline`, critical warning to user |
| Tier 3 | Tier 1 | Save confirmed working + context pressure relieved | Set `context_tier: 1` |
| Tier 3 | Tier 4 | Save operation fails | Set `context_tier: 4`, set `artifact_mode: best-effort-inline`, critical warning |
| Tier 4 | Tier 3 | Saves restored | Set `context_tier: 3`, keep `artifact_integrity_status: UNVERIFIED` until affected artifacts are regenerated or user-accepted |

### Tier 4 Operational Limits & Recovery

Tier 4 is not just "more degraded" Tier 3. It has stricter operational limits:

- Resume is not guaranteed past the current session
- Best-effort summaries may omit sections that would normally be recoverable from disk
- Cross-pipeline validations that depend on exact evidence MUST be marked `UNVERIFIED` unless the full artifact is later reconstructed
- Final delivery must carry a Tier 4 warning until all Tier 4-era artifacts are regenerated or explicitly accepted by the user

**Required user notice**:

> CRITICAL: Both persistence and full-context are compromised. Artifact fidelity cannot be guaranteed. Resume beyond this session is not reliable. Recommend completing the current stage without interruption and regenerating or manually exporting critical artifacts before continuing.

**Recovery path**:

1. If persistence is restored, transition Tier 4 → Tier 3 and recreate referenced artifacts where possible
2. Mark all Tier 4-era artifacts as `artifact_integrity_status: UNVERIFIED` until regenerated, re-approved, or explicitly accepted by the user
3. Only return to Tier 1 after saves are healthy and inline capacity is again sufficient

### Immutability Rule Clarification

The workflow-protocol.md Immutability Rule ("pass all artifacts forward exactly as received") is clarified as follows:

> Artifacts are passed forward either **inline** (full content in context) or **by reference** (summary + save path). Both forms are valid artifact passing. The artifact itself is never modified — in reference mode, the summary is generated from the unmodified artifact, and the on-disk copy IS the unmodified artifact.

Reference mode does NOT violate immutability because:
- The artifact on disk is the exact, unmodified output from the sub-orchestrator
- The summary is an addition for context management, not a modification
- Any consumer that needs the full artifact can read it from the save path
