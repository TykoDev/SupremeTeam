# Workflow Protocol — Code-Chief State Management

## Phase State Machine

Every phase in the code-chief pipeline transitions through these states:

```
PENDING → IN_PROGRESS → SUBMITTED → GATEKEEPER_REVIEW → APPROVED / REVISE → COMPLETE
                                                              ↓
                                                         ESCALATE → USER_INPUT → resume
```

### State Definitions

| State | Description |
|-------|-------------|
| **PENDING** | Phase has not started. Waiting for prerequisite phase to complete. |
| **IN_PROGRESS** | Specialist skill is actively executing. |
| **SUBMITTED** | Specialist has returned its report to code-chief. |
| **GATEKEEPER_REVIEW** | Report is submitted to `gatekeeper-code` for adversarial validation. |
| **APPROVED** | Gatekeeper validated the report. Phase is complete. |
| **REVISE** | Gatekeeper found issues. Delegation request routed back to specialist. |
| **ESCALATE** | Blocking issue that code-chief cannot resolve autonomously. |
| **COMPLETE** | Phase finalized and locked. No further changes. |

### Transition Rules

1. A phase cannot enter `IN_PROGRESS` until all prerequisite phases are `COMPLETE`
2. `SUBMITTED` → `GATEKEEPER_REVIEW` happens only after all 6 phases are `SUBMITTED` (batch gatekeeper review), OR when code-chief determines incremental review is beneficial for complex reviews
3. `REVISE` → `IN_PROGRESS` routes the gatekeeper's delegation request to the originating skill
4. Maximum `REVISE` cycles per finding: **3** — after 3 rounds, unresolved findings are marked `DISPUTED` and escalated to the user
5. `ESCALATE` pauses the pipeline until user input is received

---

## Revision Cycle Tracking

Code-chief maintains a revision log for traceability:

```markdown
## Revision Log

| Phase | Skill | Finding ID | Round | Gatekeeper Challenge | Skill Response | Outcome |
|-------|-------|-----------|-------|---------------------|----------------|---------|
| 1 | bug-review | BUG-003 | 1 | Proportionality: Major → Minor? | Defended: shared state confirmed | Accepted |
| 4 | security-review | SEC-007 | 1 | Existence: line 42 mismatch | Corrected: updated to line 48 | Resolved |
| 4 | security-review | SEC-007 | 2 | Accuracy: CWE-79 → CWE-80? | Defended: reflected XSS confirmed | Accepted |
| 5 | mr-robot | MR-012 | 1 | Completeness: missing SSRF check | Corrected: added SSRF analysis | Resolved |
```

---

## Pipeline Execution Modes

### Full Pipeline Mode (Default)

All 6 phases execute sequentially. Gatekeeper review runs after all phases
complete with a consolidated package.

```
Phase 0 (Intake) → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
    → Consolidate → Gatekeeper Review → [Revision Loop] → Delivery
```

### Incremental Pipeline Mode

For very large codebases or complex reviews, code-chief may submit intermediate
gatekeeper reviews to catch issues early:

```
Phase 0 → Phase 1 → Phase 2 → [Intermediate Gate] →
Phase 3 → Phase 4 → [Intermediate Gate] →
Phase 5 → Phase 6 → [Final Gate] → Delivery
```

Intermediate gates are advisory — they flag early issues but do not block
subsequent phases from starting.

### Targeted Review Mode

When the user requests specific review types only:

```
Phase 0 (Intake) → [Selected Phases Only] → Gatekeeper Review → Delivery
```

Code-chief must still run gatekeeper-code even for single-phase reviews.

---

## Error Handling

### Specialist Skill Failure

If a specialist skill cannot complete its analysis:

1. Record the failure reason and partial output (if any)
2. Attempt once more with clarified scope
3. If still failing, mark the phase as `ESCALATE` with the failure details
4. Continue with remaining phases (do not block the entire pipeline)
5. Include the failed phase in the final report as `INCOMPLETE` with the reason

### Gatekeeper Deadlock

If the gatekeeper and a specialist cannot agree after 3 revision rounds:

1. Mark the finding as `DISPUTED`
2. Include both the gatekeeper's challenge and the specialist's defense in the final report
3. Flag the disputed item for user judgment
4. Do not block delivery of the rest of the validated package

### Scope Ambiguity

If code-chief cannot determine the review scope:

1. Attempt to infer from the file structure, project configuration, and language detection
2. If still ambiguous, ask the user one batch of clarifying questions
3. Document all assumptions made

---

## Phase Skip Documentation

When a phase is skipped, code-chief records:

```markdown
## Phase Skip Record

| Phase | Skill | Action | Justification |
|-------|-------|--------|---------------|
| 6 | frontier | SKIPPED | No frontend detected: no HTML/CSS/JS/JSX/TSX/Vue/Svelte files found |
| 5 | mr-robot | SIMPLIFIED | Low-risk change: documentation-only update; reconnaissance only |
```

This record is included in the final delivery package for audit trail purposes.

---

## Context Propagation

Code-chief passes accumulated context forward through the pipeline:

### Phase Context Object

```markdown
## Pipeline Context (Phase [N])

### Review Target
- Scope: [full codebase / PR / module / file]
- Files: [count and key paths]
- Technology: [detected languages, frameworks, runtimes]
- Risk Tier: [Low / Standard / High]

### Frontend Detection
- Has frontend: [yes / no]
- Frontend framework: [React / Vue / Angular / Svelte / vanilla / N/A]
- Frontend files: [count]

### Accumulated Findings (Prior Phases)
- Phase 1 (bug-review): [C/H/M/L counts]
- Phase 2 (code-review): [merge verdict]
- Phase 3 (quality-review): [quality score]
- ...

### Cross-References
[Files or functions flagged by multiple phases — potential overlap for gatekeeper attention]
```

Each subsequent phase receives the full context, enabling cross-referencing
and avoiding redundant analysis.

---

## Persistent Save Actions

Save actions are performed at each state transition when persistence is active. All paths are relative to `skillset-saves/runs/{run-id}/review/`.

### Per-Phase Saves

| Transition | Save Action |
|-----------|-------------|
| PENDING → IN_PROGRESS | Create phase directory (e.g., `phase-1_bug-review/`); write `_phase-state.md` (state: ACTIVE); append `_audit-trail.md` |
| IN_PROGRESS → SUBMITTED | Update `_phase-state.md` (state: SUBMITTED); append `_audit-trail.md` |
| SUBMITTED → GATEKEEPER_REVIEW | Update `_state.md`; append `_audit-trail.md` |
| GATEKEEPER_REVIEW → APPROVED | Write `gatekeeper-code_verdict.md`; update all `_phase-state.md` (COMPLETE); update `_state.md`; append `_audit-trail.md` |
| GATEKEEPER_REVIEW → REVISE | Write `gatekeeper-code_verdict.md` (REVISE); update affected `_phase-state.md`; append `_audit-trail.md` |
| REVISE → IN_PROGRESS | Update `_phase-state.md` (increment revision); append `_audit-trail.md` |
| All COMPLETE → CONSOLIDATION | Write `code-chief/review-package.md`, `code-chief/delegation-log.md`; update `_state.md` (DELIVERED); append `_audit-trail.md` |

### Specialist Deliverable Saves

When a specialist returns its report and `Save Context` was provided in the delegation, the specialist writes `deliverable_{report-name}.md` to its phase directory. Code-chief does NOT duplicate this write — the specialist owns its deliverable files.

If persistence is not active, all save actions are skipped silently.

**Lock heartbeat refresh**: The active session must refresh `_lock.md` `last_heartbeat` whenever `_state.md` is updated and at least every 300 seconds during long-running delegations, per `save-protocol.md` §Session Management & Concurrency.
