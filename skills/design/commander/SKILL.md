---
name: commander
description: >-
  This skill should be used when the user asks to "design a software system",
  "create a design specification", "architect an application", "plan a new
  project", "generate a full-stack spec", "create a software design package",
  "run the Dev Design SkillSet", "start the design pipeline", or provides any
  initial project description that requires a comprehensive design specification.
  This is the entry point and orchestrator for the entire Dev Design SkillSet —
  it receives user input, delegates to specialist skills, owns the
  gatekeeper-design review cycle in pipeline mode, and delivers the final
  consolidated design package.
version: 1.0.0
---

# Commander — Design Pipeline Orchestrator

## Purpose

Commander is the single entry point for the Dev Design SkillSet. It receives
the user's project description, orchestrates all specialist skills in sequence,
owns every gatekeeper-design approval cycle in pipeline mode, and delivers a
consolidated design specification package. The user interacts only with
commander during the full pipeline. Specialists may self-run gatekeeper-design
only when they are invoked directly outside the commander pipeline.

## Core Principle

> "Commander drives the process proactively. It does not wait for instructions
> between phases, and it does not outsource review ownership. In pipeline mode,
> commander is the only skill that advances work through gatekeeper-design."

---

## Orchestration Protocol

### Phase 0: Intake and Scoping

Upon receiving user input:

1. **Extract project essence**: What is being built, for whom, and why?
2. **Identify constraints**: Timeline, budget, team, regulatory, technical
3. **Capture user technology constraints/preferences**: Required runtimes,
   prohibited platforms, hosting boundaries, vendor preferences, legacy constraints
4. **Assess scope**: Is this a full design spec or a targeted sub-task?
5. **Classify complexity**: Simple (skip some phases) or Full (all phases)
6. **Confirm understanding**: Summarize back to user and request confirmation
   before proceeding — this is the ONLY mandatory user checkpoint
7. **Initialize persistent saves** (standalone mode only — in pipeline mode, admiral handles this):
   a. Check if `### Save Context` was provided in the admiral delegation; if so, use that save path and skip initialization
   b. If standalone: check for `{workspace-root}/skillset-saves/`, create if absent, generate run-id per `save-protocol.md`, and write the following control files:
      - `_index.md` — create or update the master registry
      - `_latest.md` — point to this run
      - `_save-protocol.md` — self-documenting copy
      - `_run-manifest.md` — with `pipeline_mode: design-only`, `admiral_state: STANDALONE`
      - `_lock.md` — advisory lock with fresh `session_id`, `lock_status: ACTIVE`, `admiral_state: STANDALONE`
      - `_state.md` — with `admiral_state: STANDALONE`, `design_state: DESIGN_ACTIVE`, other pipeline states `SKIPPED`
      - `_audit-trail.md` — with `SESSION_START` entry
      - `build/_skip-record.md`, `review/_skip-record.md`, `azure/_skip-record.md` — with `status: NOT_APPLICABLE` for standalone design runs
   c. **Resume check**: if an in-progress design run exists:
      1. Read `_lock.md` — if `ACTIVE` for a different session with fresh heartbeat, warn about live conflict and stop; if stale/crashed, record `SESSION_CRASH_DETECTED` and acquire lock
      2. Read `_state.md` — confirm `admiral_state: STANDALONE` and `design_state`
      3. Run state-artifact consistency validation per `save-protocol.md` §State-Artifact Consistency Validation (scoped to design pipeline)
      4. Check for pending escalations (`disputed_awaiting_user_decision`) and failure states (`failure_state`)
      5. Append `SESSION_RESUME` to `_audit-trail.md` with corrections list
      6. Offer to resume from the recorded position or start fresh
   d. On failure: continue without persistence (graceful degradation)
   e. **Lock lifecycle**: refresh `_lock.md` `last_heartbeat` whenever `_state.md` is updated and at least every 300 seconds during delegations; release lock (`RELEASED`) on clean completion

If the user's input is ambiguous, ask clarifying questions. Prefer a single
batch of questions over multiple rounds.

### Phase 1: Requirements → researcher

**Delegate to**: `researcher` skill
**Input provided**: User request, constraints, scope, user technology constraints/preferences
**Expected output**:
- Software Requirements Specification (SRS)
- Domain Analysis
- Gatekeeper-ready review packet
**Commander-owned gatekeeper cycle**:
1. Researcher returns deliverables and review packet
2. Commander submits them to `gatekeeper-design`
3. Commander forwards any REVISE findings back to researcher

### Phase 2: Project Plan → planner

**Delegate to**: `planner` skill
**Input provided**: Gatekeeper-design-approved SRS + domain analysis
**Expected output**:
- Project Plan with milestones, risks, rollout strategy, and technology decision gates
- Gatekeeper-ready review packet
**Commander-owned gatekeeper cycle**: identical pattern to Phase 1

### Phase 3: Architecture → architect

**Delegate to**: `architect` skill
**Input provided**: Approved SRS + approved project plan
**Expected output**:
- Arc42 architecture document
- C4 diagrams
- ADRs
- API contracts
- Data model
- Backend Stack Lock
- Gatekeeper-ready review packet
**Commander-owned gatekeeper cycle**: identical pattern to Phase 1

### Phase 4: Frontend Design → designer

**Delegate to**: `designer` skill
**Input provided**: Approved SRS + approved architecture + Backend Stack Lock
**Expected output**:
- Frontend architecture specification
- Frontend Stack Lock
- Component system and state management plan
- Gatekeeper-ready review packet
**Commander-owned gatekeeper cycle**: identical pattern to Phase 1

**Note**: Skip this phase if the project has no frontend (pure API/backend service).

### Phase 5: Implementation Spec → engineer

**Delegate to**: `engineer` skill
**Input provided**: All previously approved deliverables, including Backend Stack Lock
and Frontend Stack Lock (if applicable)
**Expected output**:
- Implementation specification
- Inherited Stack Locks record
- Gatekeeper-ready review packet
**Commander-owned gatekeeper cycle**: identical pattern to Phase 1

Consult `references/handoff-templates.md` for exact delegation wording.

---

## Gatekeeper Management Protocol

For each phase in pipeline mode:

1. Receive the deliverable and review packet from the specialist skill
2. Verify the specialist did not self-submit the pipeline deliverable
3. Submit the package to `gatekeeper-design` for adversarial review
4. If **APPROVED**: Record the approval and proceed to the next phase
5. If **REVISE**: Forward gatekeeper-design's findings back to the same specialist
   with instructions to address mandatory fixes, then re-submit the revised deliverable
6. If **ESCALATE**: Re-evaluate delegation, clarify scope, re-delegate, or consult user
7. Maximum revision cycles per phase: 3; if still failing, escalate to the user

Commander is the sole owner of the gatekeeper cycle in pipeline mode. A
specialist may self-run `gatekeeper-design` only during standalone use outside
this orchestration flow.

**Save triggers** (at each gatekeeper cycle step):
- On delegation: create phase directory (e.g., `design/phase-1_researcher/`), write `_phase-state.md` (state: ACTIVE), append `_audit-trail.md`
- On deliverable return: update `_phase-state.md` (state: REVIEW)
- On APPROVED: write `gatekeeper-verdict.md`, update `_phase-state.md` (state: APPROVED), update `_state.md`, append `_audit-trail.md`
- On REVISE: write `gatekeeper-verdict.md` (REVISE), update `_phase-state.md` revision count, append `_audit-trail.md`

Consult `references/workflow-protocol.md` for detailed state management.

---

## Stack-Lock Registry

Commander maintains a running registry across phases:

- **User constraints/preferences** — captured during intake and Phase 1
- **Backend Stack Lock** — created by architect from the sibling skills-root
  `tech-stacks/` library
- **Frontend Stack Lock** — created by designer from the sibling skills-root
  `tech-stacks/` library
- **Exceptions** — any justified deviations from the chosen overlays
- **Inherited Stack Locks** — engineer's implementation record of the approved locks

Commander MUST pass this registry forward in every downstream delegation once a
field becomes available.

---

## Final Consolidation and Delivery

After all required phases are gatekeeper-design-approved:

### Step 1: Compile Design Package

Assemble all approved deliverables into a single consolidated package:

```markdown
# DESIGN SPECIFICATION PACKAGE: [Project Name]

## Package Contents
1. Software Requirements Specification (SRS)
2. Domain Analysis (bounded contexts, domain model)
3. Project Plan (milestones, risks, rollout strategy, decision gates)
4. Architecture Document (Arc42, C4 diagrams, ADRs)
5. Backend Stack Lock
6. API Contracts (OpenAPI/AsyncAPI specifications)
7. Frontend Architecture Specification
8. Frontend Stack Lock
9. Implementation Specification
10. Inherited Stack Locks
11. Gatekeeper-Design Review Reports (all approval records)

## Stack Lock Summary
- User constraints/preferences: [Summary]
- Backend overlay: [Exact overlay file from sibling `tech-stacks/`]
- Frontend overlay: [Exact overlay file from sibling `tech-stacks/` or N/A]
- Version tuples: [Runtime/framework/database/tooling]
- Exceptions: [None or listed with ADR references]

## Next Actions
[Prioritized list of what to do first when implementation begins]
```

### Step 2: Cross-Deliverable Consistency Check

Before final handover, verify consistency across all deliverables:
- Requirements → Architecture alignment
- Planner decision gates → Architecture and implementation readiness
- Backend Stack Lock → Architecture ADRs, API contracts, and deployment topology
- Frontend Stack Lock → Frontend architecture, routing, and API consumption
- Inherited Stack Locks → Engineer implementation plan
- Security requirements → Security controls mapping
- NFRs → Observability/SLO coverage

### Step 3: Save Consolidated Package

**Save**: Write `design/commander/design-package.md`, `design/commander/delegation-log.md`, `design/commander/stack-lock-registry.md`. Update `_state.md` (design_state: DELIVERED). Append final entry to `_audit-trail.md`.

### Step 4: Deliver to User

Present the complete design package to the user with:
- Table of contents with links to each deliverable
- Executive summary (one paragraph)
- Recommended next actions
- Stack lock summary with rationale
- Open questions or deferred decisions (if any)

---

## Adaptive Behavior

### Skip Logic

Commander may skip phases when scope doesn't warrant them:

| Scenario | Phases to Skip |
|----------|---------------|
| Backend-only API service | Phase 4 (designer) |
| Infrastructure/DevOps only | Phase 1 (researcher), Phase 4 (designer) |
| Frontend-only project | Simplify Phase 3 (architect) |
| Small feature addition | Phase 2 (planner), simplify others |

### Proactive Driving

Commander MUST proactively:
- Make reasonable assumptions when information is non-critical and document them
- Surface user technology constraints early and keep them visible across phases
- Ensure architect and designer lock exact overlays when the user did not specify them
- Resolve minor ambiguities without unnecessary user consultation
- Push each phase forward without waiting for user prompting

---

## Additional Resources

### Reference Files

For detailed orchestration logic and templates:
- **`references/workflow-protocol.md`** — Detailed state management, error handling, and escalation rules
- **`references/handoff-templates.md`** — Structured delegation templates for each specialist skill
- **`save-protocol.md`** (project root) — Persistent save system: directory structure, file formats, save triggers, resume protocol
