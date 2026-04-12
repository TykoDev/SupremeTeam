# Azure Provisioner — Workflow Protocol

## Pipeline Ownership Rule

In pipeline mode, azure-provisioner is the only skill that submits Azure
deliverables to `gatekeeper-azure` and the only skill that advances or rewinds
the Azure state machine.

Specialists return deliverables to azure-provisioner. They do not self-submit
to gatekeeper-azure.

---

## State Machine

```text
INTAKE -> PLANNING_ACTIVE -> PLANNING_REVIEW -> ARCHITECTURE_ACTIVE ->
ARCHITECTURE_REVIEW -> CONFIGURATION_ACTIVE -> CONFIGURATION_REVIEW ->
DEPLOYMENT_ACTIVE -> DEPLOYMENT_REVIEW -> VERIFICATION_ACTIVE ->
VERIFICATION_REVIEW -> CONSOLIDATION -> DELIVERED
```

### State Transitions

| From State | Event | To State | Action | Save Action |
|-----------|-------|----------|--------|-------------|
| INTAKE | User confirms scope + Azure mode | PLANNING_ACTIVE | Delegate to azure-planner | Write `_phase-state.md` (ACTIVE), append `_audit-trail.md` |
| PLANNING_ACTIVE | Planner returns deliverable | PLANNING_REVIEW | Submit to gatekeeper-azure | Write `deliverable_deployment-runbook.md`; `_phase-state.md` (REVIEW) |
| PLANNING_REVIEW | Gatekeeper-azure APPROVED | ARCHITECTURE_ACTIVE | Record approval, delegate to azure-architect | Write `gatekeeper-verdict.md`; `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| PLANNING_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | PLANNING_ACTIVE | Route findings to planner | Write `gatekeeper-verdict.md`; increment revision count; append `_audit-trail.md` |
| PLANNING_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user | Update `_state.md`; append `_audit-trail.md` |
| ARCHITECTURE_ACTIVE | Architect returns deliverable | ARCHITECTURE_REVIEW | Submit to gatekeeper-azure | Write `deliverable_bicep-design.md`; `_phase-state.md` (REVIEW) |
| ARCHITECTURE_REVIEW | Gatekeeper-azure APPROVED | CONFIGURATION_ACTIVE | Record approval, delegate to azure-configurator | Write `gatekeeper-verdict.md`; `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| ARCHITECTURE_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | ARCHITECTURE_ACTIVE | Route findings to architect | Write `gatekeeper-verdict.md`; increment revision count; append `_audit-trail.md` |
| ARCHITECTURE_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user | Update `_state.md`; append `_audit-trail.md` |
| CONFIGURATION_ACTIVE | Configurator returns deliverable | CONFIGURATION_REVIEW | Submit to gatekeeper-azure | Write `deliverable_config-spec.md`; `_phase-state.md` (REVIEW) |
| CONFIGURATION_REVIEW | Gatekeeper-azure APPROVED | DEPLOYMENT_ACTIVE | Record approval, delegate to azure-deployer | Write `gatekeeper-verdict.md`; `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| CONFIGURATION_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | CONFIGURATION_ACTIVE | Route findings to configurator | Write `gatekeeper-verdict.md`; increment revision count; append `_audit-trail.md` |
| CONFIGURATION_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user | Update `_state.md`; append `_audit-trail.md` |
| DEPLOYMENT_ACTIVE | Deployer returns deliverable | DEPLOYMENT_REVIEW | Submit to gatekeeper-azure | Write `deliverable_deploy-report.md`; `_phase-state.md` (REVIEW) |
| DEPLOYMENT_REVIEW | Gatekeeper-azure APPROVED | VERIFICATION_ACTIVE | Record approval, delegate to azure-verifier | Write `gatekeeper-verdict.md`; `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| DEPLOYMENT_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | DEPLOYMENT_ACTIVE | Route findings to deployer | Write `gatekeeper-verdict.md`; increment revision count; append `_audit-trail.md` |
| DEPLOYMENT_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user | Update `_state.md`; append `_audit-trail.md` |
| VERIFICATION_ACTIVE | Verifier returns deliverable | VERIFICATION_REVIEW | Submit to gatekeeper-azure | Write `deliverable_verify-report.md`; `_phase-state.md` (REVIEW) |
| VERIFICATION_REVIEW | Gatekeeper-azure APPROVED | CONSOLIDATION | Assemble Azure Package | Write `gatekeeper-verdict.md`; `_phase-state.md` (APPROVED); update `_state.md`; append `_audit-trail.md` |
| VERIFICATION_REVIEW | Gatekeeper-azure REVISE targeting verifier | VERIFICATION_ACTIVE | Route findings to verifier | Write `gatekeeper-verdict.md`; increment revision count; append `_audit-trail.md` |
| VERIFICATION_REVIEW | Gatekeeper-azure REVISE targeting earlier phase | [Impacted phase]_ACTIVE | Rewind to earliest impacted phase and invalidate downstream approvals | Write `gatekeeper-verdict.md`; update `_state.md`; append `_audit-trail.md` |
| CONSOLIDATION | Consistency check passed | DELIVERED | Return Azure Package | Write `azure/azure-provisioner/azure-package.md`; write `azure/azure-provisioner/delegation-log.md`; write `azure/azure-provisioner/pipeline-record.md`; update `_state.md`; append `_audit-trail.md` |
| DEADLOCKED | User resolves or overrides | [Resolved phase ACTIVE] | Continue from resolved state | Update `_state.md`; append `_audit-trail.md` |

All save actions are relative to `skillset-saves/runs/{run-id}/azure/`.

---

## Partial Pipeline Handling

### Entry Phase Selection

| User Input | Entry Phase | Rationale |
|-----------|-------------|-----------|
| Full Azure deployment from scratch | PLANNING_ACTIVE | Start from strategy |
| Bicep templates already exist | CONFIGURATION_ACTIVE | Skip planning and architecture |
| Infrastructure deployed, needs verification | VERIFICATION_ACTIVE | Skip to validation |
| "Just plan the deployment" | PLANNING_ACTIVE | Exit after PLANNING_REVIEW |

### Exit Phase Selection

- For partial pipelines, exit at the review state following the last requested phase
- Gatekeeper-azure still validates the exit boundary
- For single-phase requests, the verdict is phase-readiness, not full-pipeline readiness

### Skipped Phase Handling

When phases are skipped:

1. Document why they were skipped
2. Mark skipped phases in the state tracker
3. Note assumptions about externally supplied artifacts
4. Record when skipped artifacts were not validated by gatekeeper-azure

---

## Context Propagation

Azure-provisioner passes all gatekeeper-approved upstream Azure deliverables
forward:

| Delegation | Artifacts Passed |
|-----------|-----------------|
| To azure-planner | User request, Azure constraints, Design/Build/Review Packages |
| To azure-architect | Approved Runbook, design topology, build container context |
| To azure-configurator | Approved Runbook and Bicep Design, env-var and secret catalogs |
| To azure-deployer | Approved Runbook, Bicep Design, Config Spec, deployment inputs |
| To azure-verifier | Approved Runbook, Bicep Design, Config Spec, Deploy Report |

During the final sweep, gatekeeper-azure may review the entire approved Azure
artifact set from phases 1-5.

---

## Error Handling

### Revision Cycle Management

Each impacted phase has a maximum of 3 revision attempts.

### Operational Retries vs. Quality Revisions

- **Operational retries**: transient deployment failures in Phase 4; do not
  count as gatekeeper revisions
- **Quality revisions**: any gatekeeper REVISE verdict; do count

### Final Sweep Rewinds

When the Phase 5 final adversarial sweep finds an earlier-phase issue:

1. identify the earliest responsible phase
2. rewind to that phase
3. re-run all downstream phases
4. block consolidation until the replayed phases are approved

### Escalation to User

When escalating, provide:

1. the blocked phase or rewind point
2. the gatekeeper's findings
3. the specialist's position
4. the operational impact of approval vs. revision
5. azure-provisioner's recommendation

---

## Traceability Record

Azure-provisioner maintains a running record:

```markdown
## Azure Pipeline Record

### Pipeline Mode
[Full / Partial — phases active]

### Phase 1: Planning
- Status: [...]
- Specialist: azure-planner
- Revision attempts: [0/3]
- Gatekeeper verdict: [...]

### Phase 2: Architecture
- Status: [...]
- Specialist: azure-architect
- Revision attempts: [0/3]
- Gatekeeper verdict: [...]

### Phase 3: Configuration
- Status: [...]
- Specialist: azure-configurator
- Revision attempts: [0/3]
- Gatekeeper verdict: [...]

### Phase 4: Deployment
- Status: [...]
- Specialist: azure-deployer
- Revision attempts: [0/3]
- Operational retries: [count]
- Gatekeeper verdict: [...]

### Phase 5: Verification
- Status: [...]
- Specialist: azure-verifier
- Revision attempts: [0/3]
- Gatekeeper verdict: [...]
- Final adversarial sweep: [PENDING / PASSED / FINDINGS]

### Accepted Risks
[List or "None"]

### User Overrides
[List or "None"]
```

---

## Resume State Loading

When resuming an Azure run:

1. read `_lock.md`, `_state.md`, and `_run-manifest.md`
2. verify the current session can own the active lease
3. load upstream approved Azure artifacts based on the saved state:
   - `PLANNING_ACTIVE` or `PLANNING_REVIEW`: no upstream Azure artifacts
   - `ARCHITECTURE_ACTIVE+`: Phase 1
   - `CONFIGURATION_ACTIVE+`: Phases 1-2
   - `DEPLOYMENT_ACTIVE+`: Phases 1-3
   - `VERIFICATION_ACTIVE+`: Phases 1-4
4. if a phase was mid-execution, re-delegate it from scratch
5. if a gate was in progress, re-submit to gatekeeper-azure
