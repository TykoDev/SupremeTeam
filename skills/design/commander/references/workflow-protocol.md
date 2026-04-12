# Commander Workflow Protocol

## Pipeline Ownership Rule

In pipeline mode, commander is the only skill that submits deliverables to
`gatekeeper-design` and the only skill that advances work from one phase to the
next. Specialist skills return gatekeeper-ready deliverables plus review
metadata; they do not self-run the approval loop while delegated by commander.

Standalone direct use is different: a specialist may self-run `gatekeeper-design`
only when it was invoked directly by a user outside this workflow.

---

## State Machine

The commander operates as a state machine with the following states:

```
INTAKE → PHASE_1_ACTIVE → PHASE_1_REVIEW → PHASE_2_ACTIVE → PHASE_2_REVIEW →
PHASE_3_ACTIVE → PHASE_3_REVIEW → PHASE_4_ACTIVE → PHASE_4_REVIEW →
PHASE_5_ACTIVE → PHASE_5_REVIEW → CONSOLIDATION → DELIVERED
```

### State Transitions

| From State | Event | To State | Action | Save Action |
|-----------|-------|----------|--------|-------------|
| INTAKE | User confirms scope | PHASE_1_ACTIVE | Delegate to researcher | Create `phase-1_researcher/`, write `_phase-state.md` (ACTIVE); update `_state.md`; append `_audit-trail.md` |
| PHASE_N_ACTIVE | Specialist returns deliverable + review packet | PHASE_N_REVIEW | Commander submits to gatekeeper-design | Update `_phase-state.md` (REVIEW); append `_audit-trail.md` |
| PHASE_N_REVIEW | Gatekeeper-design APPROVED | PHASE_N+1_ACTIVE | Record approval and delegate to next skill | Write `gatekeeper-verdict.md`; update `_phase-state.md` (APPROVED); create next phase dir; update `_state.md`; append `_audit-trail.md` |
| PHASE_N_REVIEW | Gatekeeper-design REVISE | PHASE_N_ACTIVE | Return findings to the same specialist | Write `gatekeeper-verdict.md` (REVISE); update `_phase-state.md` (increment revision_attempts); append `_audit-trail.md` |
| PHASE_N_REVIEW | Gatekeeper-design ESCALATE | INTAKE | Re-scope with user | Update `_state.md`; append `_audit-trail.md` |
| PHASE_N_REVIEW | 3 revisions failed | ESCALATE_TO_USER | Show findings and request guidance | Update `_state.md`; append `_audit-trail.md` |
| PHASE_5_REVIEW | Gatekeeper-design APPROVED | CONSOLIDATION | Compile final package | Write `gatekeeper-verdict.md`; update `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| CONSOLIDATION | Consistency check passed | DELIVERED | Deliver to user | Write `commander/design-package.md`, `commander/delegation-log.md`, `commander/stack-lock-registry.md`; update `_state.md` (DELIVERED); append `_audit-trail.md` |

All save paths are relative to `skillset-saves/runs/{run-id}/design/`. If persistence is not active, save actions are skipped silently.

**Lock heartbeat refresh**: The active session must refresh `_lock.md` `last_heartbeat` whenever `_state.md` is updated and at least every 300 seconds during long-running delegations, per `save-protocol.md` §Session Management & Concurrency.

---

## Error Handling

### Revision Cycle Management

Each phase has a maximum of 3 revision attempts:

```
Attempt 1:
  Specialist produces deliverable + review packet
  → Commander submits to gatekeeper-design
  → If REVISE: proceed to attempt 2

Attempt 2:
  Specialist addresses MANDATORY FIXES from gatekeeper-design
  → Commander re-submits the revised deliverable
  → If REVISE: proceed to attempt 3

Attempt 3:
  Specialist addresses remaining fixes
  → Commander re-submits the revised deliverable
  → If REVISE: ESCALATE to commander → commander escalates to user
```

### Escalation to User

When escalating to the user, provide:
1. Which phase failed gatekeeper-design review
2. Summary of gatekeeper-design's findings across all attempts
3. What the gatekeeper-design requires for approval
4. Commander's recommendation for resolution
5. Specific questions for the user to resolve

### Phase Skip Handling

When a phase is skipped:
1. Document why the phase was skipped with rationale
2. Mark the phase as SKIPPED in the state tracker
3. Ensure downstream phases are aware of the gap
4. Note any assumptions that would change if the skipped phase were added later

---

## Context Handoff Rules

When delegating to a specialist skill, commander MUST provide:

1. **Original user request** — verbatim, unmodified
2. **Phase context** — which phase this is and what came before
3. **Upstream deliverables** — all gatekeeper-design-approved documents from prior phases
4. **Constraints** — any business, regulatory, team, or technical constraints discovered during intake
5. **Stack-lock registry** — user preferences, Backend Stack Lock, Frontend Stack Lock, and exceptions as available
6. **Specific instructions** — any phase-specific guidance based on commander's understanding
7. **Execution mode** — explicit instruction that the specialist is operating in pipeline mode

When receiving output from a specialist skill:
1. Require the deliverable plus a review packet
2. Do NOT modify the specialist's deliverable before review
3. Submit to gatekeeper-design exactly as received
4. Forward gatekeeper-design findings exactly as received back to the specialist
5. Only add commander context when forwarding rejection findings or clarifying scope

---

## Quality Assurance Rules

### Commander's Self-Check Before Delivery

Before presenting the final package to the user, verify:

1. **All required phases completed** (or explicitly skipped with rationale)
2. **All gatekeeper-design approvals recorded** (one per completed phase)
3. **Cross-deliverable consistency**:
   - Requirements entities match architecture data model
   - Planner decision gates align with architecture and implementation readiness
   - Architecture API contracts match implementation routes
   - Frontend state management aligns with API design
   - Security requirements have implementation controls
   - NFR thresholds have observability coverage
4. **Stack-lock lineage is intact**:
   - User constraints/preferences are reflected in stack selection
   - Backend Stack Lock matches architecture decisions and deployment topology
   - Frontend Stack Lock matches frontend architecture and API usage
   - Engineer's Inherited Stack Locks match the approved upstream locks
5. **No orphaned references** — every document cross-reference is valid
6. **Tech stack consistency** — same versions and tools across all deliverables unless explicitly approved as exceptions

### Conflict Resolution

If cross-deliverable consistency check reveals conflicts:
1. Identify which deliverable is likely correct
2. Document the conflict
3. Recommend resolution
4. If critical: re-submit the affected deliverable to gatekeeper-design after revision
5. If minor: note it in the final package for implementation team awareness
