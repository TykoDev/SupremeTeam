# Unified Responsibility & Trigger Matrix

> Single authoritative reference for component responsibilities, triggers, inputs,
> outputs, and escalation paths across the entire Admiral pipeline. All other files
> remain the source of truth for their detailed protocols; this matrix provides the
> consolidated cross-reference.

## How to Use This Matrix

- Use this file to answer **who owns** a trigger, decision, notice, save artifact,
  or escalation path
- Use `workflow-protocol.md` for **state-transition behavior**
- Use `save-protocol.md` for **file formats, resume semantics, locks, and degradation tiers**
- Use `handoff-templates.md` for **delegation payload shape**

If another document appears to redefine ownership or trigger authority, this
matrix wins and the other document should be brought back into alignment.

---

## Layer 1: Orchestration

### Admiral — Unified Pipeline Orchestrator

| Field | Value |
|-------|-------|
| **Trigger** | User asks to "run the full pipeline", "design build and review", etc.; or resume of existing run |
| **Input** | User project description + constraints; or existing artifacts for partial pipeline |
| **Output** | Unified Delivery Package (design + build + review + optional azure + traceability) |
| **Internal phases** | Delegates to commander, build-management, code-chief, azure-provisioner |
| **Gatekeeper** | gatekeeper-admiral (at 3-4 cross-pipeline handoff points) |
| **Escalation path** | gatekeeper-admiral ESCALATE or 2x REVISE → DISPUTED_AWAITING_USER → user decides |
| **Max revision cycles** | 2 per handoff point |
| **Save ownership** | `_index.md`, `_latest.md`, `_run-manifest.md`, `_lock.md`, `_state.md`, `_audit-trail.md`, `admiral/intake.md`, `admiral/standalone-context.md`, `admiral/pipeline-record.md`, `admiral/delivery-package.md`, `{pipeline}/_skip-record.md`, `gatekeeper-admiral_handoff-{1,2,3,4}.md` |
| **User communication** | Intake confirmation (mandatory), escalation presentations, degradation tier notices, skipped-stage notices, delivery package |
| **Context tier ownership** | Admiral owns tier decisions at cross-pipeline boundaries; sub-orchestrators inherit and may escalate |

### Commander — Design Pipeline Orchestrator

| Field | Value |
|-------|-------|
| **Trigger** | Admiral delegates Stage 1; or user directly invokes for standalone design |
| **Input** | User request + constraints + pipeline mode (from admiral) or direct user input |
| **Output** | Consolidated Design Package (SRS, domain analysis, project plan, architecture, ADRs, API contracts, stack locks, implementation spec) |
| **Internal phases** | researcher → planner → architect → designer → engineer |
| **Gatekeeper** | gatekeeper-design (at each of 5 phases) |
| **Escalation path** | gatekeeper-design ESCALATE or 3x REVISE → escalate to user |
| **Max revision cycles** | 3 per phase |
| **Save ownership** | `design/commander/design-package.md`, `design/commander/delegation-log.md`, `design/commander/stack-lock-registry.md`, `design/phase-{N}_*/` directories + `_phase-state.md`, `gatekeeper-verdict.md` captures |

### Build-Management — Build Pipeline Orchestrator

| Field | Value |
|-------|-------|
| **Trigger** | Admiral delegates Stage 2; or user directly invokes for standalone build |
| **Input** | Gatekeeper-admiral-approved Design Package (from admiral) or user-provided design spec |
| **Output** | Consolidated Build Package (production code, test suite, security audit, completeness cert) |
| **Internal phases** | bob-the-builder → test-builder → security-builder → cross-check-build-confirm |
| **Gatekeeper** | gatekeeper-build (at each of 4 phases) |
| **Escalation path** | gatekeeper-build ESCALATE or 3x REVISE → escalate to user (Phase 4: 2 scan cycles then escalate) |
| **Max revision cycles** | 3 per phase (Phase 4 completeness: 2 scan cycles) |
| **Save ownership** | `build/build-management/build-package.md`, `build/build-management/delegation-log.md`, `build/phase-{N}_*/` directories + `_phase-state.md`, `gatekeeper-verdict.md` captures |

### Code-Chief — Review Pipeline Orchestrator

| Field | Value |
|-------|-------|
| **Trigger** | Admiral delegates Stage 3; or user directly invokes for standalone review |
| **Input** | Gatekeeper-admiral-approved Build Package + Design Package (from admiral) or user-provided codebase |
| **Output** | Consolidated Review Package (6 specialist reports, gatekeeper-code validation, risk summary) |
| **Internal phases** | bug-review → code-review → quality-review → security-review → mr-robot → frontier |
| **Gatekeeper** | gatekeeper-code (1 consolidated gate after all phases) |
| **Escalation path** | gatekeeper-code ESCALATE or 3x REVISE per finding → DISPUTED → user decides |
| **Max revision cycles** | 3 per finding |
| **Save ownership** | `review/code-chief/review-package.md`, `review/code-chief/delegation-log.md`, `review/phase-{N}_*/` directories + `_phase-state.md`, `gatekeeper-code_verdict.md` capture |

### Azure-Provisioner — Azure Pipeline Orchestrator

| Field | Value |
|-------|-------|
| **Trigger** | Admiral delegates Stage 4 (when targeting Azure); or user directly invokes for standalone deployment |
| **Input** | Gatekeeper-admiral-approved Design + Build + Review Packages (from admiral) or user-provided context |
| **Output** | Consolidated Azure Package (runbook, Bicep design, config spec, deploy report, verification, gatekeeper adversarial findings) |
| **Internal phases** | azure-planner → azure-architect → azure-configurator → azure-deployer → azure-verifier |
| **Gatekeeper** | gatekeeper-azure (at each of 5 phases, with final adversarial sweep in Phase 5) |
| **Escalation path** | gatekeeper-azure ESCALATE or 3x REVISE → escalate to user |
| **Max revision cycles** | 3 per phase |
| **Save ownership** | `azure/azure-provisioner/azure-package.md`, `azure/azure-provisioner/delegation-log.md`, `azure/azure-provisioner/pipeline-record.md`, `azure/phase-{N}_*/` directories + `_phase-state.md`, `gatekeeper-verdict.md` captures |

---

## Layer 2: Cross-Pipeline Validation

### Gatekeeper-Admiral — Cross-Pipeline Adversarial Validator

| Field | Value |
|-------|-------|
| **Trigger** | Admiral submits a package at one of 4 handoff points |
| **Activation pattern** | Per-handoff (Design→Build, Build→Review, Review→Azure or Delivery, Azure→Delivery) |
| **Input** | Consolidated package from the source sub-orchestrator + submission metadata + submission_id |
| **Output** | Validation report with verdict (APPROVED/REVISE/ESCALATE), finding counts, evidence |
| **Challenge types** | 4: Completeness, Alignment, Consistency, Feasibility |
| **Verdict rules** | 0 CRITICAL + 0-2 MAJOR = APPROVED; 1+ CRITICAL or 3+ MAJOR = REVISE; fundamental misalignment = ESCALATE |
| **Save ownership** | None — output captured by admiral into `gatekeeper-admiral_handoff-{N}.md` |
| **Escalation path** | Returns ESCALATE verdict to admiral; admiral presents to user |
| **Save awareness** | May reference persisted deliverables in `skillset-saves/runs/{run-id}/` when Run ID is provided |

---

## Layer 3: Internal Design Validation

### Gatekeeper-Design — Per-Phase Design Validator

| Field | Value |
|-------|-------|
| **Trigger** | Commander submits a phase deliverable (5 submission points) |
| **Activation pattern** | Per-phase (5 gates: one after each of researcher, planner, architect, designer, engineer) |
| **Input** | Phase deliverable + review packet + upstream approved deliverables + stack-lock context |
| **Output** | Verdict (APPROVED/REVISE/ESCALATE) with findings |
| **Save ownership** | None — output captured by commander into per-phase `gatekeeper-verdict.md` |
| **Escalation path** | Returns ESCALATE to commander; commander may escalate to user |

---

## Layer 4: Internal Build Validation

### Gatekeeper-Build — Per-Phase Build Validator

| Field | Value |
|-------|-------|
| **Trigger** | Build-management submits a phase deliverable (4 submission points) |
| **Activation pattern** | Per-phase (4 gates: one after each of bob-the-builder, test-builder, security-builder, cross-check) |
| **Input** | Phase deliverable + design spec reference + change manifest |
| **Output** | Verdict (APPROVED/REVISE/ESCALATE) with findings |
| **Save ownership** | None — output captured by build-management into per-phase `gatekeeper-verdict.md` |
| **Escalation path** | Returns ESCALATE to build-management; build-management escalates to user |

---

## Layer 5: Internal Review Validation

### Gatekeeper-Code — Consolidated Review Validator

| Field | Value |
|-------|-------|
| **Trigger** | Code-chief submits the consolidated review package (1 submission point) |
| **Activation pattern** | **Consolidated-only** (NOT per-phase); all 6 specialist reports are submitted together for cross-validation |
| **Input** | Consolidated review package with all specialist reports |
| **Output** | Validation record with cross-validation matrix, delegation requests, verdict |
| **Save ownership** | None — output captured by code-chief into `gatekeeper-code_verdict.md` |
| **Escalation path** | Returns ESCALATE to code-chief; code-chief escalates to user |

> **Pattern asymmetry note**: Design and Build use per-phase gatekeeping (incremental approval). Review uses a single consolidated gate (batch approval after all specialists). This is intentional — review findings have cross-cutting dependencies that are best validated together.

---

## Layer 6: Internal Azure Validation

### Gatekeeper-Azure — Per-Phase Azure Validator

| Field | Value |
|-------|-------|
| **Trigger** | Azure-provisioner submits a phase deliverable (5 submission points) |
| **Activation pattern** | Per-phase (5 gates: one after each of azure-planner, azure-architect, azure-configurator, azure-deployer, azure-verifier) |
| **Input** | Phase deliverable + upstream approved deliverables + Azure-specific context |
| **Output** | Verdict (APPROVED/REVISE/ESCALATE) with findings |
| **Save ownership** | None — output captured by azure-provisioner into per-phase `gatekeeper-verdict.md` |
| **Escalation path** | Returns ESCALATE to azure-provisioner; azure-provisioner escalates to user |

---

## Layer 7: Specialist Skills

| Specialist | Pipeline | Invoked By | Produces | Validated By |
|------------|----------|------------|----------|--------------|
| researcher | Design | commander | SRS + Domain Analysis | gatekeeper-design (Phase 1) |
| planner | Design | commander | Project Plan + Risk Register | gatekeeper-design (Phase 2) |
| architect | Design | commander | Arc42 + C4 + ADRs + API Contracts + Backend Stack Lock | gatekeeper-design (Phase 3) |
| designer | Design | commander | Frontend Architecture + Frontend Stack Lock | gatekeeper-design (Phase 4) |
| engineer | Design | commander | Implementation Spec + Inherited Stack Locks | gatekeeper-design (Phase 5) |
| bob-the-builder | Build | build-management | Production code (all modules) | gatekeeper-build (Phase 1) |
| test-builder | Build | build-management | Test suite (unit, integration, E2E) | gatekeeper-build (Phase 2) |
| security-builder | Build | build-management | Security audit report + remediation items | gatekeeper-build (Phase 3) |
| cross-check-build-confirm | Build | build-management | Completeness scan (CLEAN/FINDINGS) | gatekeeper-build (Phase 4) |
| bug-review | Review | code-chief | Correctness defect report | gatekeeper-code (consolidated) |
| code-review | Review | code-chief | 8-dimension merge-readiness assessment | gatekeeper-code (consolidated) |
| quality-review | Review | code-chief | Quality score + standards + tech debt | gatekeeper-code (consolidated) |
| security-review | Review | code-chief | Security findings (NIST/OWASP/CWE mapping) | gatekeeper-code (consolidated) |
| mr-robot | Review | code-chief | Adversarial analysis + exploit chains | gatekeeper-code (consolidated) |
| frontier | Review | code-chief | Frontend audit (Web Vitals, WCAG, CSP) | gatekeeper-code (consolidated) |
| azure-planner | Azure | azure-provisioner | Deployment runbook + resource catalog | gatekeeper-azure (Phase 1) |
| azure-architect | Azure | azure-provisioner | Bicep design + resource topology | gatekeeper-azure (Phase 2) |
| azure-configurator | Azure | azure-provisioner | Configuration spec (RBAC, Key Vault, app settings) | gatekeeper-azure (Phase 3) |
| azure-deployer | Azure | azure-provisioner | Deployment execution report | gatekeeper-azure (Phase 4) |
| azure-verifier | Azure | azure-provisioner | Verification report + final gatekeeper adversarial sweep input | gatekeeper-azure (Phase 5) |

**Specialist save ownership**: Specialists write `deliverable_{name}.md` and `review-packet.md` to their phase directory when Save Context is provided. They do NOT write state files, gatekeeper verdicts, or consolidated packages.

---

## Layer 8: Save Ownership Matrix

| File | Written By | Updated By | When |
|------|-----------|------------|------|
| `_index.md` | Admiral (or standalone orchestrator) | Admiral | RUN_INIT, RUN_COMPLETE |
| `_latest.md` | Admiral | Admiral | RUN_INIT, each CROSS_PIPELINE_GATE, RUN_COMPLETE |
| `_run-manifest.md` | Admiral | Admiral | RUN_INIT, each stage transition |
| `_lock.md` | Admiral (or standalone orchestrator) | Same | RUN_INIT, RUN_LOCK_ACQUIRE, heartbeat refresh during long-running waits, RUN_COMPLETE/ABORT |
| `_state.md` | Admiral | Admiral, sub-orchestrators (their own sub-state) | Every STATE_TRANSITION |
| `_audit-trail.md` | Admiral | All orchestrators | Every state transition, session boundaries |
| `admiral/intake.md` | Admiral | Never (immutable) | RUN_INIT |
| `admiral/standalone-context.md` | Admiral | Admiral | RUN_INIT for standalone/partial entry, SKIP_DECISION |
| `admiral/pipeline-record.md` | Admiral | Admiral | Each stage transition |
| `admiral/delivery-package.md` | Admiral | Never | RUN_COMPLETE |
| `{pipeline}/commander\|build-management\|code-chief\|azure-provisioner/*.md` | Respective sub-orchestrator | Same | PACKAGE_CONSOLIDATION |
| `{pipeline}/_skip-record.md` | Admiral | Admiral | SKIP_DECISION |
| `{pipeline}/phase-{N}_*/_phase-state.md` | Respective orchestrator | Same | Phase transitions |
| `{pipeline}/phase-{N}_*/deliverable_*.md` | Specialist skill | Never (immutable once approved) | DELIVERABLE_COMPLETE |
| `{pipeline}/phase-{N}_*/gatekeeper-verdict.md` | Orchestrator (capturing gatekeeper output) | Same (on revision) | GATE_VERDICT |
| `{pipeline}/gatekeeper-admiral_handoff-{N}.md` | Admiral | Admiral (PENDING → VERDICT_RECORDED) | CROSS_PIPELINE_GATE |
| `review/gatekeeper-code_verdict.md` | Code-chief (capturing gatekeeper-code output) | Code-chief | GATE_VERDICT |
| `_save-protocol.md` (at `skillset-saves/` root) | Admiral (or standalone orchestrator) | Never (immutable copy) | RUN_INIT |
| `{pipeline}/phase-{N}_*/review-packet.md` | Design and Azure specialists only | Never (immutable once submitted) | DELIVERABLE_COMPLETE |

---

## Layer 9: Escalation Path Summary

| Component | Escalation Trigger | Escalation Target | What User Receives |
|-----------|-------------------|-------------------|-------------------|
| gatekeeper-admiral | Fundamental misalignment between pipelines | Admiral → User | Both positions + evidence + options + recommendation |
| Admiral (2x REVISE) | 2 failed revision cycles at any handoff | User | Sub-orchestrator position vs. gatekeeper-admiral position + recommendation |
| Admiral (failure) | Sub-orchestrator crashes or produces unrecoverable output | User | Failure details + retry/skip/abort options |
| gatekeeper-design | Design deliverable has unresolvable issues | Commander → User (via Admiral if in pipeline) | Phase failure details + gatekeeper requirements + resolution options |
| Commander (3x REVISE) | 3 failed revision cycles at any design phase | User | Revision history + remaining findings + recommended action |
| gatekeeper-build | Build deliverable has unresolvable issues | Build-management → User (via Admiral if in pipeline) | Phase failure details + resolution options |
| Build-management (3x REVISE) | 3 failed revision cycles at any build phase | User | Revision history + remaining findings + recommended action |
| gatekeeper-code | Review findings have unresolvable disputes | Code-chief → User (via Admiral if in pipeline) | Both positions with evidence |
| Code-chief (3x REVISE per finding) | 3 failed revision rounds for a finding | User | Challenge-response log + disputed finding |
| gatekeeper-azure | Azure deliverable has unresolvable issues | Azure-provisioner → User (via Admiral if in pipeline) | Phase failure details + resolution options |
| Azure-provisioner (3x REVISE) | 3 failed revision cycles at any azure phase | User | Revision history + remaining findings + recommended action |
| Sub-orchestrator unavailability | Specialist crashes, timeout, malformed output | Orchestrator → User | Failure details + retry/skip/abort options |
| Gatekeeper unavailability | Gatekeeper cannot run | Orchestrator → User | Pipeline stopped, no self-approval permitted |

---

## Gatekeeper Activation Pattern Clarification

| Gatekeeper | Pattern | Gate Count | Notes |
|------------|---------|------------|-------|
| gatekeeper-design | Per-phase | 5 gates | One after each design specialist |
| gatekeeper-build | Per-phase | 4 gates | One after each build specialist |
| gatekeeper-code | **Consolidated-only** | 1 gate | All 6 reports submitted together; NOT per-phase |
| gatekeeper-azure | Per-phase | 5 gates | One after each azure specialist, with final adversarial sweep in the Phase 5 gate |
| gatekeeper-admiral | Per-handoff | 3-4 gates | At each cross-pipeline boundary (4 when Azure is active) |

---

## Context Tier Responsibilities

| Component | Context Tier Role |
|-----------|------------------|
| **Admiral** | Owns tier decisions at cross-pipeline boundaries. Tracks `context_tier` in `_state.md`. Selects inline vs. reference mode for each delegation. |
| **Sub-orchestrators** | Inherit tier from `_state.md` / delegation context. May escalate tier within their pipeline if internal artifacts grow unexpectedly large, and must preserve the inherited notice in downstream work products. |
| **Specialists** | Unaware of tiers. Produce deliverables normally. Orchestrators handle artifact passing mode. |
| **Gatekeepers** | May read referenced artifacts from `skillset-saves/` paths. Gatekeeper-admiral already supports this (see cross-pipeline-criteria.md). |

## Layer 10: Resume & Degradation Control Ownership

| Concern | Primary Owner | Trigger | Required Artifact or Action |
|---------|---------------|---------|-----------------------------|
| Session lock acquisition | Admiral or standalone orchestrator | RUN_INIT, SESSION_RESUME | `_lock.md` |
| Live lock conflict handling | Admiral or standalone orchestrator | Resume sees different `ACTIVE` `session_id` with fresh `last_heartbeat` | Warn user, do not steal lock, wait or force takeover |
| Crash detection | Admiral or standalone orchestrator | Resume sees different `ACTIVE` `session_id` with expired lease and no `SESSION_END` | `_audit-trail.md` `SESSION_CRASH_DETECTED`, `_lock.md` marked `STALE` |
| Heartbeat refresh | Active orchestrator | Long-running delegated work or external waits | `_lock.md` `last_heartbeat` updated at least every 300 seconds |
| Critical write ownership check | Any writer performing critical save | Before deliverable, verdict, state, or package write | Re-read `_lock.md` and confirm current session still owns the `ACTIVE` lease |
| Durable single-file write protocol | Any component writing `skillset-saves/` artifacts | Every save operation | temp file in same directory + flush/sync + atomic replace + best-effort cleanup |
| Control-file integrity failure | Admiral or standalone orchestrator | `_lock.md`, `_state.md`, `_run-manifest.md`, or authoritative verdict is unreadable | Mark integrity `FAILED`, surface to user, block automatic resume |
| Skipped-stage disclosure | Admiral | User skips non-mandatory stage or partial mode omits a stage | `{pipeline}/_skip-record.md`, `_run-manifest.md`, `_state.md` |
| Standalone fallback context | Admiral | Upstream package intentionally absent or user-supplied | `admiral/standalone-context.md` |
| Artifact-integrity gating | Admiral on resume; sub-orchestrator within standalone mode | Resume or downstream continuation depends on saved artifacts | `_state.md` integrity fields + user notice when `UNVERIFIED` or `FAILED` |
| Tier 2/3/4 user notice | Active orchestrator; admiral owns cross-pipeline carry-forward | `context_tier` changes to degraded state | Immediate user notice + `_audit-trail.md` + next delegation/delivery note |
| Reference-mode fidelity warning | Active orchestrator | Artifact mode switches to `reference` | Explicit statement that inline summary is non-authoritative |
| Tier 4 critical warning | Active orchestrator; admiral owns final delivery carry-forward | Save failure while context-pressured or vice versa | Critical user notice + final delivery warning until resolved |

See `save-protocol.md` §Context-Aware Artifact Management for the full degradation tier protocol.

---

## Design Patterns

### Nested Orchestration
```
Admiral (top-level orchestrator)
├── Commander (design sub-orchestrator)
│   ├── Researcher → Planner → Architect → Designer → Engineer
│   └── Gatekeeper-Design (per-phase)
├── Build-Management (build sub-orchestrator)
│   ├── Bob-the-Builder → Test-Builder → Security-Builder → Cross-Check
│   └── Gatekeeper-Build (per-phase)
├── Code-Chief (review sub-orchestrator)
│   ├── Bug-Review, Code-Review, Quality-Review, Security-Review, Mr-Robot, Frontier
│   └── Gatekeeper-Code (consolidated, not per-phase)
└── Azure-Provisioner (azure sub-orchestrator, optional)
    ├── Azure-Planner → Azure-Architect → Azure-Configurator → Azure-Deployer → Azure-Verifier
    └── Gatekeeper-Azure (per-phase, with final adversarial sweep in Phase 5)
```

### Immutability Contract
- Admiral NEVER modifies sub-orchestrator output
- Sub-orchestrators NEVER modify specialist output (handled by internal gatekeepers)
- Packages flow forward unchanged; gatekeeper verdicts are added as separate files, never embedded in the package
- In reference mode (Tier 3/4), the on-disk artifact IS the unmodified original; summaries are additive
