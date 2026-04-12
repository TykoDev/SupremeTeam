# Build Pipeline Workflow Protocol

## State Machine Definition

Build-management operates as a deterministic state machine. Each state has defined entry conditions, actions, and exit transitions. In the canonical workflow, no mandatory phase may be skipped.

### State Diagram

```
INTAKE ──► PHASE_1_BUILD ──► PHASE_1_GATE ──┐
                                              │
           ┌──────────────────────────────────┘
           │
           ├─[APPROVED: initial implementation]──► PHASE_2_TEST ──► PHASE_2_GATE ──┐
           │                                                                          │
           ├─[APPROVED: security remediation re-validation]──► PHASE_4_COMPLETENESS │
           │                                                                          │
           └─[REVISE]───► PHASE_1_BUILD (retry / security remediation)               │
                                              ┌──────────────┘
                                              │
           ┌──────────────────────────────────┘
           │
           ├─[APPROVED]──► PHASE_3_SECURITY ──► PHASE_3_GATE ──┐
           │                                                     │
           └─[REVISE]───► PHASE_2_TEST (retry)                  │
                                              ┌──────────────────┘
                                              │
           ┌──────────────────────────────────┘
           │
           ├─[APPROVED]──► PHASE_4_COMPLETENESS ──► PHASE_4_GATE ──┐
           │                                                         │
           ├─[APPROVED, has remediation]──► PHASE_1_BUILD (security remediation)    │
           │                                                                          │
           └─[REVISE]───► PHASE_3_SECURITY (retry)                                    │
                                              ┌──────────────────────┘
                                              │
           ┌──────────────────────────────────┘
           │
           ├─[CLEAN]────► PHASE_4_GATE ──► [APPROVED] ──► CONSOLIDATION ──► DELIVERED
           │                                  │
           │                                  └─[REVISE]──► PHASE_4_COMPLETENESS (re-scan / amend report)
           │
           └─[FINDINGS]─► PHASE_1_BUILD (completeness remediation) ──► PHASE_4_COMPLETENESS
```

### State Transition Table

| Current State | Event | Next State | Action | Save Action |
|---------------|-------|------------|--------|-------------|
| INTAKE | Spec validated, user confirmed | PHASE_1_BUILD | Delegate to bob-the-builder | Create `phase-1_bob-the-builder/`; write `_phase-state.md` (ACTIVE); update `_state.md`; append `_audit-trail.md` |
| PHASE_1_BUILD | Code complete (initial implementation) | PHASE_1_GATE | Submit to gatekeeper-build | Update `_phase-state.md` (REVIEW); append `_audit-trail.md` |
| PHASE_1_BUILD | Code complete (security remediation) | PHASE_1_GATE | Submit updated code for remediation re-validation | Update `_phase-state.md`; append `_audit-trail.md` |
| PHASE_1_BUILD | Code complete (completeness remediation) | PHASE_4_COMPLETENESS | Re-run cross-check-build-confirm | Update `_phase-state.md`; append `_audit-trail.md` |
| PHASE_1_GATE | APPROVED (initial implementation) | PHASE_2_TEST | Delegate to test-builder | Write `gatekeeper-verdict.md`; update `_phase-state.md` (APPROVED); create `phase-2_test-builder/`; update `_state.md`; append `_audit-trail.md` |
| PHASE_1_GATE | APPROVED (security remediation) | PHASE_4_COMPLETENESS | Resume after validated security fixes | Write `gatekeeper-verdict.md`; update `_state.md`; append `_audit-trail.md` |
| PHASE_1_GATE | REVISE (attempt < 3) | PHASE_1_BUILD | Return findings to bob-the-builder | Write `gatekeeper-verdict.md` (REVISE); update `_phase-state.md` (increment revision); append `_audit-trail.md` |
| PHASE_1_GATE | REVISE (attempt = 3) | ESCALATE | Present findings to user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_1_GATE | ESCALATE | INTAKE | Re-scope with user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_2_TEST | Tests complete | PHASE_2_GATE | Submit to gatekeeper-build | Update `_phase-state.md` (REVIEW); append `_audit-trail.md` |
| PHASE_2_GATE | APPROVED | PHASE_3_SECURITY | Delegate to security-builder | Write `gatekeeper-verdict.md`; update `_phase-state.md` (APPROVED); create `phase-3_security-builder/`; update `_state.md`; append `_audit-trail.md` |
| PHASE_2_GATE | REVISE (attempt < 3) | PHASE_2_TEST | Return findings to test-builder | Write `gatekeeper-verdict.md` (REVISE); update `_phase-state.md`; append `_audit-trail.md` |
| PHASE_2_GATE | REVISE (attempt = 3) | ESCALATE | Present findings to user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_3_SECURITY | Audit complete | PHASE_3_GATE | Submit to gatekeeper-build | Update `_phase-state.md` (REVIEW); append `_audit-trail.md` |
| PHASE_3_GATE | APPROVED, no remediation | PHASE_4_COMPLETENESS | Delegate to cross-check | Write `gatekeeper-verdict.md`; update `_phase-state.md` (APPROVED); create `phase-4_cross-check/`; update `_state.md`; append `_audit-trail.md` |
| PHASE_3_GATE | APPROVED, has remediation | PHASE_1_BUILD | Route remediation to bob-the-builder | Write `gatekeeper-verdict.md`; update `_state.md`; append `_audit-trail.md` |
| PHASE_3_GATE | REVISE (attempt < 3) | PHASE_3_SECURITY | Return findings to security-builder | Write `gatekeeper-verdict.md` (REVISE); update `_phase-state.md`; append `_audit-trail.md` |
| PHASE_3_GATE | REVISE (attempt = 3) | ESCALATE | Present findings to user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_4_COMPLETENESS | CLEAN | PHASE_4_GATE | Submit completeness report to gatekeeper-build | Update `_phase-state.md` (REVIEW); append `_audit-trail.md` |
| PHASE_4_COMPLETENESS | FINDINGS (cycle < 2) | PHASE_1_BUILD | Delegate to bob-the-builder | Update `_phase-state.md`; append `_audit-trail.md` |
| PHASE_4_COMPLETENESS | FINDINGS (cycle = 2) | ESCALATE | Present findings to user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_4_GATE | APPROVED | CONSOLIDATION | Compile delivery package | Write `gatekeeper-verdict.md`; update `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| PHASE_4_GATE | REVISE (cycle < 2) | PHASE_4_COMPLETENESS | Return findings to cross-check | Write `gatekeeper-verdict.md` (REVISE); update `_phase-state.md`; append `_audit-trail.md` |
| PHASE_4_GATE | REVISE (cycle = 2) | ESCALATE | Present findings to user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_4_GATE | ESCALATE | ESCALATE | Present findings to user | Update `_state.md`; append `_audit-trail.md` |
| CONSOLIDATION | Package assembled | DELIVERED | Deliver to user | Write `build-management/build-package.md`, `build-management/delegation-log.md`; update `_state.md` (DELIVERED); append `_audit-trail.md` |

All save paths are relative to `skillset-saves/runs/{run-id}/build/`. If persistence is not active, save actions are skipped silently.

**Lock heartbeat refresh**: The active session must refresh `_lock.md` `last_heartbeat` whenever `_state.md` is updated and at least every 300 seconds during long-running delegations, per `save-protocol.md` §Session Management & Concurrency.

---

## Revision Cycle Management

### Per-Phase Revision Tracking

Maintain a revision counter for each phase:

```
Phase 1 (bob-the-builder):          attempt 0/3
Phase 2 (test-builder):             attempt 0/3
Phase 3 (security-builder):         attempt 0/3
Phase 4 (cross-check-build-confirm + gatekeeper-build): cycle 0/2
```

### Revision Rules

1. **Increment on REVISE**: Each REVISE verdict increments the phase counter
2. **Reset on phase change**: Counters reset only when moving to a NEW phase (not when looping)
3. **Escalation threshold**: Counter reaches maximum → escalate to user with full findings history
4. **User override**: User may authorize additional revision cycles beyond the maximum

### Escalation Format

When escalating to the user:

```markdown
## ESCALATION: Phase [N] — [Phase Name]

### Summary
[Phase] has failed gatekeeper-build review [N] times.

### Revision History
| Attempt | Key Findings | Resolution Attempted | Outcome |
|---------|-------------|---------------------|---------|
| 1 | [summary] | [what was changed] | REVISE |
| 2 | [summary] | [what was changed] | REVISE |
| 3 | [summary] | [what was changed] | REVISE |

### Remaining Unresolved Findings
[List of findings that persist across all attempts]

### Recommended Action
[Suggest re-scoping, clarifying requirements, or alternative approach]
```

---

## Mandatory Phase Enforcement

The canonical workflow is fail-closed:

- Phase 1 implementation is mandatory
- Phase 2 testing is mandatory
- Phase 3 security audit is mandatory
- Phase 4 completeness scanning is mandatory
- Every phase output must be reviewed by `gatekeeper-build`

If any mandatory phase or gatekeeper review cannot run, build-management must
escalate to the user and stop the pipeline.

---

## Context Handoff Rules

### What to Pass to Each Specialist

Each specialist receives only what it needs — not the entire accumulated history.

| Specialist | Required Context | Optional Context |
|------------|-----------------|------------------|
| **bob-the-builder** | Design spec, tech stack, module scope, constraints | Prior gatekeeper findings (for remediation) |
| **test-builder** | Approved code, design spec (for requirements), tech stack | Architecture decisions relevant to test design |
| **security-builder** | Complete codebase (code + tests), tech stack, deployment model | Threat model from design phase |
| **cross-check-build-confirm** | Complete codebase, original design spec (for completeness comparison) | Build manifest listing all expected modules |

### Context Filtering

Build-management MUST prevent context bloat by:
- Passing only approved deliverables (not revision history) to downstream skills
- Summarizing gatekeeper reports rather than forwarding full text when only key findings are relevant
- Forwarding gatekeeper findings exactly as-is when delegating remediation (no modification)

---

## Quality Assurance Rules

### Pre-Delivery Self-Check

Before marking DELIVERED, build-management must verify:

1. **Phase completion**: All four phases reached APPROVED status
2. **Remediation closure**: All security remediation items are addressed and re-validated
3. **Completeness certification**: cross-check-build-confirm issued a CLEAN verdict and `gatekeeper-build` approved Phase 4
4. **Consistency**: No contradictions between phase outputs (e.g., security findings that were not actually fixed)
5. **Traceability**: Every requirement from the design spec maps to implemented code

### Audit Trail

Maintain a running log of all phase transitions:

```markdown
## Build Audit Trail

| Timestamp | State | Action | Outcome |
|-----------|-------|--------|---------|
| [time] | INTAKE | Validated design spec | Confirmed with user |
| [time] | PHASE_1_BUILD | Delegated to bob-the-builder | Code delivered |
| [time] | PHASE_1_GATE | Submitted to gatekeeper-build | APPROVED |
| [time] | PHASE_2_TEST | Delegated to test-builder | Tests delivered |
| [time] | PHASE_4_GATE | Submitted completeness report to gatekeeper-build | APPROVED |
```

---

## Error Recovery

### Specialist Failure

If a specialist skill fails to produce output (timeout, error, or incomplete delivery):

1. **Retry once**: Re-delegate with clarified instructions
2. **If retry fails**: Escalate to user with the failure details
3. **Never skip a failed phase**: A failed phase cannot be treated as skipped

### Gatekeeper Unavailability

If gatekeeper-build is unavailable:

1. Stop the pipeline immediately
2. Escalate to the user that the canonical workflow cannot continue without `gatekeeper-build`
3. Do not self-approve or self-gate any phase output

### Conflict Between Phases

When a later phase's findings require changes that invalidate an earlier phase's approval:

1. Route the changes to bob-the-builder for implementation
2. Re-submit the affected code to gatekeeper-build for re-validation
3. Do NOT re-run phases that were not affected by the change
