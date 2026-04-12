# Admiral Workflow Protocol

## Pipeline Ownership Rule

In pipeline mode, admiral is the only skill that submits packages to
`gatekeeper-admiral` and the only skill that advances work from one
sub-pipeline to the next. Sub-orchestrators (commander, build-management,
code-chief, azure-provisioner) return consolidated packages to admiral;
they do not self-submit to gatekeeper-admiral while delegated by admiral.

Sub-orchestrators retain full ownership of their internal phase sequences
and per-phase gatekeepers. Admiral does not intervene in internal pipeline
governance.

Standalone mode is distinct from partial-pipeline mode:

- **Pipeline mode**: admiral is always the entry point, even when one or more
  stages are intentionally skipped
- **Standalone mode**: a sub-orchestrator is invoked directly by the user and
  admiral is not in the loop

Responsibility and trigger ownership live in `responsibility-matrix.md`; this
file defines the state machine and allowed transitions.

---

## State Machine

The admiral operates as a state machine with the following states:

```
Happy path:
INTAKE → DESIGN_ACTIVE → DESIGN_GATE_PENDING → BUILD_ACTIVE → BUILD_GATE_PENDING →
REVIEW_ACTIVE → REVIEW_GATE_PENDING → AZURE_ACTIVE → AZURE_GATE_PENDING →
CONSOLIDATION → DELIVERED

Error/hold states (reachable from multiple points):
  {PHASE}_GATE_PENDING     — package submitted to gatekeeper-admiral, awaiting verdict
  {PHASE}_GATE_REVISE      — gatekeeper returned REVISE, awaiting remediation delegation
  {PHASE}_FAILED           — sub-orchestrator crashed or produced unrecoverable output
  DISPUTED_AWAITING_USER   — escalation presented, user decision pending
```

Note: AZURE_ACTIVE → AZURE_GATE_PENDING is optional. If the user's request does not
target Azure deployment, the state machine transitions directly from
REVIEW_GATE_PENDING (APPROVED) → CONSOLIDATION.

**Backward compatibility**: The `{PHASE}_GATE` states from schema v1.0 map to `{PHASE}_GATE_PENDING` in v1.1. Resume logic should treat `DESIGN_GATE` as equivalent to `DESIGN_GATE_PENDING` when loading v1.0 state files.

## Revision Limit Summary

| Boundary | Owner | Max Revision Cycles |
|----------|-------|---------------------|
| Internal design/build/azure phase gates | Respective sub-orchestrator | 3 |
| Review consolidated findings | code-chief / gatekeeper-code | 3 per finding |
| Cross-pipeline handoffs | admiral / gatekeeper-admiral | 2 |

Use these limits consistently when interpreting retry, revise, and dispute
states. The matrix is authoritative for ownership; this file is authoritative
for state transitions.

### State Transitions — Happy Path

| From State | Event | To State | Action | Save Action |
|-----------|-------|----------|--------|-------------|
| INTAKE | User confirms scope + mode | First active stage | Delegate to first sub-orchestrator | Write `_lock.md`, `_state.md` (with SESSION_START), `_run-manifest.md`, `admiral/intake.md`; append `_audit-trail.md` |
| DESIGN_ACTIVE | Commander returns Design Package | DESIGN_GATE_PENDING | Generate submission_id, write handoff file (PENDING), submit to gatekeeper-admiral | Write `design/commander/design-package.md`; write `design/gatekeeper-admiral_handoff-1.md` (PENDING); update `_state.md` (gatekeeper_verdict_pending: true); append `_audit-trail.md` |
| DESIGN_GATE_PENDING | Gatekeeper-admiral APPROVED | BUILD_ACTIVE | Record approval, delegate to build-management | Update `design/gatekeeper-admiral_handoff-1.md` (VERDICT_RECORDED); update `_state.md` (verdict_pending: false), `_latest.md`, `_run-manifest.md`; append `_audit-trail.md` |
| BUILD_ACTIVE | Build-management returns Build Package | BUILD_GATE_PENDING | Generate submission_id, write handoff file (PENDING), submit to gatekeeper-admiral | Write `build/build-management/build-package.md`; write `build/gatekeeper-admiral_handoff-2.md` (PENDING); update `_state.md`; append `_audit-trail.md` |
| BUILD_GATE_PENDING | Gatekeeper-admiral APPROVED | REVIEW_ACTIVE | Record approval, delegate to code-chief | Update `build/gatekeeper-admiral_handoff-2.md` (VERDICT_RECORDED); update `_state.md`, `_latest.md`, `_run-manifest.md`; append `_audit-trail.md` |
| REVIEW_ACTIVE | Code-chief returns Review Package | REVIEW_GATE_PENDING | Generate submission_id, write handoff file (PENDING), submit to gatekeeper-admiral | Write `review/code-chief/review-package.md`; write `review/gatekeeper-admiral_handoff-3.md` (PENDING); update `_state.md`; append `_audit-trail.md` |
| REVIEW_GATE_PENDING | Gatekeeper-admiral APPROVED | CONSOLIDATION or AZURE_ACTIVE | If targeting Azure: delegate to azure-provisioner; else: compile final package | Update `review/gatekeeper-admiral_handoff-3.md` (VERDICT_RECORDED); update `_state.md`, `_latest.md`, `_run-manifest.md`; append `_audit-trail.md` |
| AZURE_ACTIVE | Azure-provisioner returns Azure Package | AZURE_GATE_PENDING | Generate submission_id, write handoff file (PENDING), submit to gatekeeper-admiral | Write `azure/azure-provisioner/azure-package.md`; write `azure/gatekeeper-admiral_handoff-4.md` (PENDING); update `_state.md`; append `_audit-trail.md` |
| AZURE_GATE_PENDING | Gatekeeper-admiral APPROVED | CONSOLIDATION | Record approval, compile final package | Update `azure/gatekeeper-admiral_handoff-4.md` (VERDICT_RECORDED); update `_state.md`, `_latest.md`, `_run-manifest.md`; append `_audit-trail.md` |
| CONSOLIDATION | Consistency check passed | DELIVERED | Deliver to user | Write `admiral/delivery-package.md`; update `_state.md` to DELIVERED (SESSION_END); release `_lock.md`; update `_index.md` (status), `_latest.md` (active_run = "none"); append `_audit-trail.md` |

### State Transitions — Revision & Escalation

| From State | Event | To State | Action | Save Action |
|-----------|-------|----------|--------|-------------|
| DESIGN_GATE_PENDING | Gatekeeper-admiral REVISE (attempt < 2) | DESIGN_GATE_REVISE | Record REVISE verdict | Update handoff-1.md (VERDICT_RECORDED, REVISE); update `_state.md` (verdict_pending: false); append `_audit-trail.md` |
| DESIGN_GATE_REVISE | Remediation delegated to commander | DESIGN_ACTIVE | Forward findings to commander | Update `_state.md`; append `_audit-trail.md` |
| DESIGN_GATE_PENDING | Gatekeeper-admiral REVISE (attempt = 2) | DISPUTED_AWAITING_USER | Present both positions | Update handoff-1.md; update `_state.md` (disputed_awaiting_user_decision: true, escalation_context); append `_audit-trail.md` |
| DESIGN_GATE_PENDING | Gatekeeper-admiral ESCALATE | DISPUTED_AWAITING_USER | Surface issue to user | Update handoff-1.md; update `_state.md` (disputed_awaiting_user_decision: true, escalation_context); append `_audit-trail.md` |
| BUILD_GATE_PENDING | Gatekeeper-admiral REVISE (attempt < 2) | BUILD_GATE_REVISE | Record REVISE verdict | Update handoff-2.md (VERDICT_RECORDED, REVISE); update `_state.md`; append `_audit-trail.md` |
| BUILD_GATE_REVISE | Remediation delegated to build-management | BUILD_ACTIVE | Forward findings to build-management | Update `_state.md`; append `_audit-trail.md` |
| BUILD_GATE_PENDING | Gatekeeper-admiral REVISE (attempt = 2) | DISPUTED_AWAITING_USER | Present both positions | Update `_state.md` (disputed: true); append `_audit-trail.md` |
| BUILD_GATE_PENDING | Gatekeeper-admiral ESCALATE | DISPUTED_AWAITING_USER | Surface issue to user | Update `_state.md` (disputed: true); append `_audit-trail.md` |
| REVIEW_GATE_PENDING | Gatekeeper-admiral REVISE (attempt < 2) | REVIEW_GATE_REVISE | Record REVISE verdict | Update handoff-3.md; update `_state.md`; append `_audit-trail.md` |
| REVIEW_GATE_REVISE | Remediation delegated to code-chief | REVIEW_ACTIVE | Forward findings to code-chief | Update `_state.md`; append `_audit-trail.md` |
| REVIEW_GATE_PENDING | Gatekeeper-admiral REVISE (attempt = 2) | DISPUTED_AWAITING_USER | Present both positions | Update `_state.md` (disputed: true); append `_audit-trail.md` |
| REVIEW_GATE_PENDING | Gatekeeper-admiral ESCALATE | DISPUTED_AWAITING_USER | Surface issue to user | Update `_state.md` (disputed: true); append `_audit-trail.md` |
| AZURE_GATE_PENDING | Gatekeeper-admiral REVISE (attempt < 2) | AZURE_GATE_REVISE | Record REVISE verdict | Update handoff-4.md; update `_state.md`; append `_audit-trail.md` |
| AZURE_GATE_REVISE | Remediation delegated to azure-provisioner | AZURE_ACTIVE | Forward findings to azure-provisioner | Update `_state.md`; append `_audit-trail.md` |
| AZURE_GATE_PENDING | Gatekeeper-admiral REVISE (attempt = 2) | DISPUTED_AWAITING_USER | Present both positions | Update `_state.md` (disputed: true); append `_audit-trail.md` |
| AZURE_GATE_PENDING | Gatekeeper-admiral ESCALATE | DISPUTED_AWAITING_USER | Surface issue to user | Update `_state.md` (disputed: true); append `_audit-trail.md` |
| DISPUTED_AWAITING_USER | User provides decision | (depends on decision) | Record decision, resume or abort | Update `_state.md` (disputed: false, record decision); append `_audit-trail.md` |

### State Transitions — Failure & Recovery

| From State | Event | To State | Action | Save Action |
|-----------|-------|----------|--------|-------------|
| DESIGN_ACTIVE | Commander fails/crashes | DESIGN_FAILED | Record failure | Update `_state.md` (failure_state, failure_reason); append `_audit-trail.md` |
| BUILD_ACTIVE | Build-management fails/crashes | BUILD_FAILED | Record failure | Update `_state.md` (failure_state, failure_reason); append `_audit-trail.md` |
| REVIEW_ACTIVE | Code-chief fails/crashes | REVIEW_FAILED | Record failure | Update `_state.md` (failure_state, failure_reason); append `_audit-trail.md` |
| AZURE_ACTIVE | Azure-provisioner fails/crashes | AZURE_FAILED | Record failure | Update `_state.md` (failure_state, failure_reason); append `_audit-trail.md` |
| {PHASE}_FAILED | User chooses retry | {PHASE}_ACTIVE | Re-delegate to sub-orchestrator | Clear failure fields in `_state.md`; append `_audit-trail.md` |
| {PHASE}_FAILED | User chooses skip (if non-mandatory and user-approved) | Next active stage or CONSOLIDATION | Record skip decision, write `{pipeline}/_skip-record.md`, update standalone fallback if needed, advance with explicit downstream warning | Update `_state.md`, `_run-manifest.md`; append `_audit-trail.md` |
| {PHASE}_FAILED | User chooses abort | DELIVERED | Mark pipeline incomplete | Update `_state.md` to DELIVERED (incomplete); release `_lock.md`; append `_audit-trail.md` (SESSION_END) |

All save actions reference paths relative to `skillset-saves/runs/{run-id}/`. If persistence is not active, save actions are skipped silently. All writes follow the durable single-file write and atomic write ordering defined in `save-protocol.md` under `Durable Single-File Writes` and `Atomic Write Ordering`. Before each critical save, admiral must re-read `_lock.md` and confirm that the current session still owns the `ACTIVE` lease.

---

## Partial Pipeline Handling

When the user requests only a subset of stages, admiral adjusts the state
machine accordingly:

### Entry State Selection

| User Input | Entry State | Rationale |
|-----------|-------------|-----------|
| Project idea, no prior artifacts | DESIGN_ACTIVE | Start from scratch |
| Approved design package provided | BUILD_ACTIVE | Skip design, start build |
| Existing codebase for review | REVIEW_ACTIVE | Skip design and build |
| "Design and build" request | DESIGN_ACTIVE | Exit after BUILD_GATE |
| "Build and review" with design | BUILD_ACTIVE | Exit after REVIEW_GATE |
| "Just design this" | DESIGN_ACTIVE | Exit after DESIGN_GATE |
| "Just review this" | REVIEW_ACTIVE | Exit after REVIEW_GATE |
| "Deploy to Azure" with existing review | AZURE_ACTIVE | Skip design, build, review |
| "Review and deploy to Azure" | REVIEW_ACTIVE | Exit after AZURE_GATE |
| "Build, review, and deploy to Azure" | BUILD_ACTIVE | Exit after AZURE_GATE |

Partial-pipeline mode still belongs to admiral. The selected entry state changes,
but admiral remains responsible for cross-pipeline validation, degradation
notices, skipped-stage records, and final delivery packaging.

### Exit State Selection

- For partial pipelines, the exit state is the GATE state following the last
  requested stage
- Gatekeeper-admiral still validates at the exit boundary — even for
  single-stage requests, the output is gate-checked before delivery
- For single-stage requests, gatekeeper-admiral validates the output as a
  delivery-readiness check rather than a handoff-readiness check

### Skipped Stage Handling

When stages are skipped:
1. Write `{pipeline}/_skip-record.md` with `status`, `decision_source`, `reason`, and `downstream_effect`
2. Mark skipped stages in `_run-manifest.md` and `_state.md`
3. If user-provided artifacts replace a skipped stage, persist the replacement summary in `admiral/standalone-context.md`
4. Note any assumptions about the skipped stage's output quality
5. Never silently treat a skipped stage as equivalent to a gatekeeper-approved upstream package
6. Mark downstream checks as `UNVERIFIED` or `N/A` rather than implying full traceability
7. Surface the same limitation in the next delegation and the final delivery package if it remains unresolved

---

## Context Propagation

### Forward Propagation Rule

Admiral passes all approved artifacts forward with each delegation:

| Delegation | Artifacts Passed |
|-----------|-----------------|
| To commander | User request, constraints, pipeline mode |
| To build-management | Gatekeeper-admiral-approved Design Package |
| To code-chief | Gatekeeper-admiral-approved Build Package + Design Package |
| To azure-provisioner | Gatekeeper-admiral-approved Design Package + Build Package + Review Package |

### Immutability Rule

Admiral MUST NOT modify sub-orchestrator output. The packages are passed
exactly as received from each sub-orchestrator and exactly as approved by
gatekeeper-admiral. Any modifications would invalidate the gatekeeper
approval.

**Reference Mode Exception**: When operating in Tier 3 or Tier 4 (context-pressured), artifacts may be passed by reference (summary + save path) instead of inline. This is not a modification — the on-disk artifact remains the unmodified original, and the summary is an accompaniment, not a replacement. See `save-protocol.md` §Context-Aware Artifact Management for the full reference mode protocol.

### Context Mode Selection

At each delegation, admiral selects the artifact passing mode based on the current degradation tier:

| Condition | Mode | Action |
|-----------|------|--------|
| Tier 1 or 2 AND artifact fits in context | Inline | Pass full artifact in delegation template |
| Tier 3 or 4 AND saves active | Reference | Pass summary + save paths in delegation template |
| Tier 4 AND saves failed | Best-effort inline | Pass as much as fits; warn user about potential truncation |

The `context_tier` is tracked in `_state.md` and evaluated at each cross-pipeline boundary. Sub-orchestrators inherit the tier from the delegation context and can escalate it further within their pipelines (e.g., if internal phases produce unexpectedly large artifacts).

### Degradation Notice Propagation

When `context_tier` changes to Tier 2, Tier 3, or Tier 4, admiral MUST:

1. Surface the tier-specific notice to the user immediately
2. Append the same notice to `_audit-trail.md`
3. Include the limitation in the next delegation template that depends on degraded artifacts
4. Carry the limitation into the final delivery package until it is no longer relevant

Tier-specific operational language must remain consistent with `save-protocol.md`:

- Tier 2: resume beyond the current session is not guaranteed
- Tier 3: inline summaries are non-authoritative; full artifacts remain on disk
- Tier 4: both resume and artifact fidelity are unverified

---

## Error Handling

### Revision Cycle Management

Each cross-pipeline handoff has a maximum of 2 revision attempts:

```
Attempt 1:
  Sub-orchestrator returns package
  → Admiral submits to gatekeeper-admiral
  → If REVISE: proceed to attempt 2

Attempt 2:
  Sub-orchestrator addresses mandatory fixes from gatekeeper-admiral
  → Admiral re-submits the revised package
  → If REVISE: ESCALATE to user with both positions
```

### Escalation to User

When escalating to the user, provide:
1. Which cross-pipeline handoff failed gatekeeper-admiral review
2. Summary of gatekeeper-admiral's findings across all attempts
3. What gatekeeper-admiral requires for approval
4. The sub-orchestrator's position on the findings
5. Admiral's recommendation for resolution
6. Specific questions for the user to resolve

### Sub-Orchestrator Failure

If a sub-orchestrator fails internally (internal gatekeeper escalation,
unresolvable error, or timeout):
1. Record the failure state and any partial output
2. Present the failure to the user with the sub-orchestrator's error details
3. Offer options: retry the stage, skip the stage (if non-mandatory), or
   abort the pipeline

### Disputed Items

Items where gatekeeper-admiral and a sub-orchestrator cannot agree after
2 revision cycles:
1. Mark the item as DISPUTED
2. Document both positions with evidence
3. Present to the user for final judgment
4. Record the user's decision and proceed

---

## Idempotency Protocol

### Gatekeeper Submission Idempotency

Each gatekeeper-admiral submission is assigned a unique `submission_id` before the package is sent:

```
submission_id format: {run-id}_handoff-{N}_attempt-{M}_{ISO-timestamp}
```

The submission_id is:
1. Written to `_state.md` BEFORE the gatekeeper is invoked
2. Included in the gatekeeper submission template
3. Written into the handoff file header (with `submission_status: PENDING`)

**On resume**, before resubmitting to gatekeeper-admiral:
1. Read `_state.md` — check `last_gatekeeper_submission_id`
2. Read the corresponding `gatekeeper-admiral_handoff-{N}.md` file
3. If the file exists AND contains `submission_status: VERDICT_RECORDED`: the verdict was already captured — do NOT resubmit; instead, process the existing verdict
4. If the file exists with `submission_status: PENDING`: the submission was made but crashed before the verdict returned — resubmit with the SAME submission_id
5. If the file does not exist: the submission was never made — proceed normally

### Delegation Idempotency

Each sub-orchestrator delegation is tracked similarly:
1. Write `_state.md` with the target ACTIVE state BEFORE delegation
2. On resume, check if the sub-orchestrator package file exists (e.g., `design-package.md`)
3. If package exists: sub-orchestrator completed — do not re-delegate; advance to GATE_PENDING
4. If package does not exist: re-delegate from scratch (sub-orchestrators handle their own internal resume)

### Resume Correction Rules for Skipped or Replaced Stages

1. If a stage is marked `SKIPPED` and the matching `{pipeline}/_skip-record.md` exists, do NOT recreate the skipped stage on resume
2. If the downstream stage is active and the upstream package is absent but a `_skip-record.md` or `admiral/standalone-context.md` exists, continue only with explicit `UNVERIFIED` status
3. If a stage is marked skipped but the skip record is missing, pause automatic recovery and consult the user instead of silently advancing

### Resume Artifact Integrity

Before automatically advancing from any resumed state, admiral must confirm that:

1. the expected approved package or skip record exists
2. the artifact identity does not contradict the current run or state
3. the next transition is still justified by the saved evidence

If these checks fail, do not silently continue. Surface the inconsistency to the
user or move into `DISPUTED_AWAITING_USER` as appropriate.

### User Escalation Idempotency

When an escalation is pending:
1. `_state.md` records `disputed_awaiting_user_decision: true` with `escalation_context`
2. On resume, if this flag is true: re-present the escalation to the user (do NOT re-submit to gatekeeper or re-delegate)
3. After user decision: clear the flag and record the decision BEFORE advancing state

---

## Traceability Record

Admiral maintains a running traceability record throughout the pipeline:

```markdown
## Admiral Pipeline Record

### Pipeline Mode
[Full / Partial — stages active]

### Stage 1: Design
- Status: [PENDING / ACTIVE / GATE / APPROVED / SKIPPED]
- Sub-orchestrator: commander
- Revision attempts: [0/2]
- Gatekeeper-admiral verdict: [PENDING / APPROVED / REVISE / ESCALATE]

### Stage 2: Build
- Status: [PENDING / ACTIVE / GATE / APPROVED / SKIPPED]
- Sub-orchestrator: build-management
- Revision attempts: [0/2]
- Gatekeeper-admiral verdict: [PENDING / APPROVED / REVISE / ESCALATE]

### Stage 3: Review
- Status: [PENDING / ACTIVE / GATE / APPROVED / SKIPPED]
- Sub-orchestrator: code-chief
- Revision attempts: [0/2]
- Gatekeeper-admiral verdict: [PENDING / APPROVED / REVISE / ESCALATE]

### Stage 4: Azure Provision (optional)
- Status: [PENDING / ACTIVE / GATE / APPROVED / SKIPPED / NOT_APPLICABLE]
- Sub-orchestrator: azure-provisioner
- Revision attempts: [0/2]
- Gatekeeper-admiral verdict: [PENDING / APPROVED / REVISE / ESCALATE]

### Disputed Items
[List or "None"]

### User Decisions
[Any escalation decisions recorded]
```

This record is included in the final Unified Delivery Package for full
audit trail.

**Save**: Write `admiral/pipeline-record.md` to `skillset-saves/` at each stage transition to keep the persistent copy in sync. This file is updated alongside `_state.md`.

---

## Persistent Save Protocol — Resume State Loading

When admiral detects an existing `skillset-saves/` directory with an active in-progress run (see `save-protocol.md` §Resume Protocol):

### Step 1: Detect and Offer Resume

1. Read `_latest.md` — check if `active_run_id` is not `"none"` and `pipeline_state` is not `DELIVERED`
2. If an active run exists, read `_lock.md` before trusting `_state.md`
3. If `_lock.md` is `ACTIVE` for a different session and `last_heartbeat` is still within the lease window: surface a live-session conflict and do NOT auto-resume or steal the lock
4. If `_lock.md` is `ACTIVE` for a different session, the lease has expired, and no `SESSION_END` exists: record crash handling and continue with stale-lock takeover per `save-protocol.md`
5. Read `_run-manifest.md` — compare the stored user request against the current context
6. If the project matches: offer "Found active pipeline run `{run-id}` at state `{state}`. Resume or start fresh?"
7. If the project does not match: start a new run

### Step 2: Load State on Resume

1. Read `_lock.md` and confirm this session can acquire or resume the `ACTIVE` lease
2. If `_lock.md`, `_state.md`, or `_run-manifest.md` is unreadable, truncated, or missing required frontmatter fields: treat it as a control-file integrity failure and stop automatic resume pending user direction
3. Read `_state.md` for the exact state machine position (`admiral_state`, `design_state`, `build_state`, `review_state`, `azure_state`)
4. Read `_run-manifest.md` for the original user request, constraints, and pipeline mode
5. **Run state-artifact consistency validation** (see `save-protocol.md` §State-Artifact Consistency Validation) — this may correct the state before proceeding
6. Based on corrected `admiral_state`, load the required inputs:
   - **DESIGN_ACTIVE, DESIGN_FAILED, or DESIGN_GATE_***: No upstream packages needed
   - **BUILD_ACTIVE, BUILD_FAILED, or BUILD_GATE_***: Load `design/commander/design-package.md` as input
   - **REVIEW_ACTIVE, REVIEW_FAILED, or REVIEW_GATE_***: Load both design and build packages
   - **AZURE_ACTIVE, AZURE_FAILED, or AZURE_GATE_***: Load all three consolidated packages (design, build, review)
   - **CONSOLIDATION**: Load all consolidated packages (including Azure Package if Stage 4 was executed)
   - **DISPUTED_AWAITING_USER**: Re-present escalation context from `_state.md`; do NOT load or advance
  - **Skipped upstream stage with replacement context**: Load `admiral/standalone-context.md` and the matching `{pipeline}/_skip-record.md`, then mark downstream traceability as `UNVERIFIED`
7. Apply idempotency checks (see §Idempotency Protocol):
   - If `gatekeeper_verdict_pending` is true: check handoff file for existing verdict before resubmitting
   - If `disputed_awaiting_user_decision` is true: re-present escalation to user
   - If `failure_state` is not null: present failure and recovery options to user
  - If a required upstream package is absent with no approved replacement context: stop automatic resume and consult the user
8. Check `context_tier` in `_state.md` and apply the appropriate artifact passing mode (see `save-protocol.md` §Context-Aware Artifact Management)

### Step 3: Resume Execution

1. Generate new `session_id` only after the live-lock conflict check passes
2. If `_state.md` contains a different `session_id`, the prior lease was expired, and no `SESSION_END` was logged: record `SESSION_CRASH_DETECTED` in `_audit-trail.md`
3. Record `SESSION_RESUME` in `_audit-trail.md` with corrections list
4. Update `_lock.md` with the new `session_id`, refreshed `last_heartbeat`, `lease_timeout_seconds`, and `lock_status: ACTIVE`
5. Update `_state.md` with new `session_id` and `snapshot_time`
6. Continue the state machine from the loaded (and possibly corrected) state

---

## Reference

For the definitive mapping of all component responsibilities, triggers, inputs, outputs, gatekeeper assignments, escalation paths, and save ownership across the entire pipeline, see **`responsibility-matrix.md`** in this directory.
