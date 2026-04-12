---
name: azure-provisioner
description: >-
  This skill should be used when the user or admiral asks to "deploy to Azure",
  "provision Azure infrastructure", "set up Azure resources", "run the Azure
  pipeline", "configure and deploy to Azure", "provision cloud infrastructure",
  "run the Azure cyber team", "deploy this to Azure", or "set up Azure landing
  zone". It is the entry point and orchestrator for the Azure Provision
  SkillSet — it receives deployment requirements (or approved upstream packages
  from admiral), delegates to specialist Azure skills (azure-planner,
  azure-architect, azure-configurator, azure-deployer, azure-verifier),
  manages gatekeeper-azure approval cycles, and delivers a consolidated Azure
  Package.
version: 1.1.0
---

# Azure Provisioner — Azure Pipeline Orchestrator

## Purpose

Serve as the entry point for the complete Azure Provision SkillSet. Orchestrate
5 sequential specialist skills — `azure-planner`, `azure-architect`,
`azure-configurator`, `azure-deployer`, and `azure-verifier` — and manage
gatekeeper-azure approval cycles for each phase.

Gatekeeper-azure now owns the former adversarial-audit responsibility. The
pipeline therefore ends with a **Phase 5 verification gate plus final
adversarial sweep**, not a separate sixth specialist phase.

> "Drive the Azure pipeline proactively. Specialists own their domain work;
> azure-provisioner owns phase boundaries, rewinds, and gatekeeper flow."

---

## Execution Modes

### Pipeline Mode (Admiral-Delegated)

- Admiral provides approved Design, Build, and Review Packages plus Azure
  constraints and save context
- Azure-provisioner runs all Azure phases autonomously
- Returns the consolidated Azure Package to admiral for handoff validation

### Standalone Mode (Direct User Invocation)

- User provides Azure requirements, code/artifacts, and subscription context
- Azure-provisioner initializes its own `skillset-saves/` structure when needed
- Returns the Azure Package directly to the user

Always identify the mode before starting. If ambiguous, infer from caller and
delegation context.

---

## Orchestration Protocol

### Phase 0: Intake and Azure Requirements Analysis

Upon receiving deployment requirements:

1. Extract the Azure target, environment, and constraints
2. Identify subscription, region, compliance, budget, scale, and existing-resource constraints
3. Detect existing Azure artifacts such as Bicep, deployed resources, or prior run state
4. Determine pipeline mode:
   - **Full Azure Pipeline** (default): all 5 phases
   - **Partial Pipeline**: skip phases backed by accepted artifacts
   - **Resume**: continue an in-progress Azure run
5. Confirm understanding back to the user when required
6. **Initialize persistent saves** (standalone mode only — in pipeline mode, admiral handles this):
   a. Check if `### Save Context` was provided in the admiral delegation; if so, use that save path and skip initialization
   b. If standalone: check for `{workspace-root}/skillset-saves/`, create if absent, generate run-id per `save-protocol.md`, and write the following control files:
      - `_index.md` — create or update the master registry
      - `_latest.md` — point to this run
      - `_save-protocol.md` — self-documenting copy
      - `_run-manifest.md` — with `pipeline_mode: azure-only`, `admiral_state: STANDALONE`
      - `_lock.md` — advisory lock with fresh `session_id`, `lock_status: ACTIVE`, `admiral_state: STANDALONE`
      - `_state.md` — with `admiral_state: STANDALONE`, `azure_state: AZURE_ACTIVE`, other pipeline states `SKIPPED` or `USER_SUPPLIED`
      - `_audit-trail.md` — with `SESSION_START` entry
      - `design/_skip-record.md`, `build/_skip-record.md`, `review/_skip-record.md` — with `status: USER_SUPPLIED` or `SKIPPED` depending on whether the user provided upstream artifacts
   c. **Resume check**: if an in-progress azure run exists:
      1. Read `_lock.md` — if `ACTIVE` for a different session with fresh heartbeat, warn about live conflict and stop; if stale/crashed, record `SESSION_CRASH_DETECTED` and acquire lock
      2. Read `_state.md` — confirm `admiral_state: STANDALONE` and `azure_state`
      3. Run state-artifact consistency validation per `save-protocol.md` §State-Artifact Consistency Validation (scoped to azure pipeline)
      4. Check for pending escalations (`disputed_awaiting_user_decision`) and failure states (`failure_state`)
      5. Append `SESSION_RESUME` to `_audit-trail.md` with corrections list
      6. Offer to resume from the recorded position or start fresh
   d. On failure: continue without persistence (graceful degradation)
   e. **Lock lifecycle**: refresh `_lock.md` `last_heartbeat` whenever `_state.md` is updated and at least every 300 seconds during delegations; release lock (`RELEASED`) on clean completion

### Phase 1: Deployment Planning -> azure-planner

**Expected output**: Deployment Runbook with stage design, environment and
secret cataloging, RBAC planning, migration strategy, rollout options, and
cost estimation when reliable pricing data is available.

**Gatekeeper cycle**: Submit to gatekeeper-azure. If APPROVED, proceed. If
REVISE, route findings to planner. If ESCALATE, consult the user.

**Save**: `phase-1_azure-planner/`

### Phase 2: Infrastructure Architecture -> azure-architect

**Expected output**: Bicep IaC Design Package with resource topology, naming
strategy, module decomposition, parameters, outputs, and security baseline.

**Gatekeeper cycle**: same pattern as Phase 1.

**Save**: `phase-2_azure-architect/`

### Phase 3: Resource Configuration -> azure-configurator

**Expected output**: Configuration Specification with RBAC, Key Vault, app
settings, PostgreSQL hardening, storage config, and diagnostic settings.

**Gatekeeper cycle**: same pattern as Phase 1.

**Save**: `phase-3_azure-configurator/`

### Phase 4: Deployment Execution -> azure-deployer

**Expected output**: Deployment Execution Report with Bicep deployment results,
image build/push results, runtime configuration, health checks, deployment
state, and rollback notes.

**Gatekeeper cycle**: same pattern as Phase 1.

**Special remediation loop**: operational retries for transient deployment
failures do not count as gatekeeper revision cycles.

**Save**: `phase-4_azure-deployer/`

### Phase 5: Verification -> azure-verifier

**Expected output**: Verification Report with infrastructure, RBAC, secrets,
database, app service, health, smoke-test, and storage verification evidence.

**Gatekeeper cycle**:

- gatekeeper-azure reviews the verification report
- gatekeeper-azure performs the **final adversarial sweep** across the approved
  Azure package
- if APPROVED: proceed directly to consolidation
- if REVISE: route findings to the responsible skill

**Final adversarial sweep behavior**:

- findings may target **any Azure phase owner** from phases 1-5
- azure-provisioner rewinds to the **earliest impacted phase**
- all downstream phases from that point are replayed and re-gated before
  consolidation

**Save**: `phase-5_azure-verifier/`

---

## Gatekeeper-Azure Management Protocol

Azure-provisioner owns the gatekeeper cycle for all 5 phases:

1. Receive a specialist deliverable
2. Submit it to gatekeeper-azure
3. If **APPROVED**: record approval and proceed
4. If **REVISE**: route findings to the responsible specialist
5. If **ESCALATE**: consult the user

### Final Sweep Rewind Rule

During the Phase 5 exit gate, gatekeeper-azure may issue findings against
earlier approved phases. When that happens, azure-provisioner MUST:

1. Identify the earliest impacted phase
2. Rewind the state machine to that phase's ACTIVE state
3. Route the finding to that phase owner
4. Invalidate downstream approvals from that point onward
5. Replay downstream phases through gatekeeper-azure before consolidation

After 3 revision cycles without approval, mark the phase DEADLOCKED and surface
options to the user.

---

## Cost Estimation Protocol

Azure-provisioner integrates cost estimation into Phase 1 under these rules:

### Estimate Only When

1. Reliable pricing data is accessible
2. SKU selections are stable enough to be meaningful
3. Region is specified
4. The estimate can be source-attributed

### Do Not Estimate When

- pricing data is unavailable or unreliable
- SKUs are placeholders
- region is unknown
- the resource is too usage-driven to produce an honest estimate

Gatekeeper-azure validates any cost estimate that appears in the runbook.

---

## Consolidated Azure Package

When all 5 phases are gatekeeper-approved, azure-provisioner assembles the
Azure Package:

**Save**: Write `azure/azure-provisioner/azure-package.md`, `azure/azure-provisioner/delegation-log.md`, and `azure/azure-provisioner/pipeline-record.md`. Update `_state.md` (azure_state: DELIVERED). Append final entry to `_audit-trail.md`. Release `_lock.md` if running in standalone mode.

**Pipeline-record.md write timing**: `pipeline-record.md` is created at init with the first entry, then appended after each state transition, delegation return, and gatekeeper verdict throughout the pipeline — not only at consolidation.

```markdown
# AZURE PROVISION PACKAGE: [Project Name]

## Executive Summary
[What Azure infrastructure was planned, configured, deployed, verified, and
adversarially gated]

## Package Contents
1. Deployment Runbook (from azure-planner)
2. Bicep IaC Design Package (from azure-architect)
3. Configuration Specification (from azure-configurator)
4. Deployment Execution Report (from azure-deployer)
5. Verification Report (from azure-verifier)
6. Pipeline Traceability Record
7. Cost Estimation Report (when reliable data is available, or documented omission)
8. Azure Resource Summary
9. Deployment Checklist & Next Actions
10. All gatekeeper-azure approval records (5 phase approvals, with final
    adversarial findings embedded in the Phase 5 verdict)
```

There is **no standalone adversarial-audit deliverable**. Final adversarial
findings live inside gatekeeper-azure reporting.

---

## State Machine

```text
INTAKE -> PLANNING_ACTIVE -> PLANNING_REVIEW -> ARCHITECTURE_ACTIVE ->
ARCHITECTURE_REVIEW -> CONFIGURATION_ACTIVE -> CONFIGURATION_REVIEW ->
DEPLOYMENT_ACTIVE -> DEPLOYMENT_REVIEW -> VERIFICATION_ACTIVE ->
VERIFICATION_REVIEW -> CONSOLIDATION -> DELIVERED
```

### State Transitions

| From State | Event | To State | Action |
|-----------|-------|----------|--------|
| INTAKE | User confirms scope + Azure mode | PLANNING_ACTIVE | Delegate to azure-planner |
| PLANNING_ACTIVE | Planner returns deliverable | PLANNING_REVIEW | Submit to gatekeeper-azure |
| PLANNING_REVIEW | Gatekeeper-azure APPROVED | ARCHITECTURE_ACTIVE | Delegate to azure-architect |
| PLANNING_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | PLANNING_ACTIVE | Route findings to planner |
| PLANNING_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user |
| ARCHITECTURE_ACTIVE | Architect returns deliverable | ARCHITECTURE_REVIEW | Submit to gatekeeper-azure |
| ARCHITECTURE_REVIEW | Gatekeeper-azure APPROVED | CONFIGURATION_ACTIVE | Delegate to azure-configurator |
| ARCHITECTURE_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | ARCHITECTURE_ACTIVE | Route findings to architect |
| ARCHITECTURE_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user |
| CONFIGURATION_ACTIVE | Configurator returns deliverable | CONFIGURATION_REVIEW | Submit to gatekeeper-azure |
| CONFIGURATION_REVIEW | Gatekeeper-azure APPROVED | DEPLOYMENT_ACTIVE | Delegate to azure-deployer |
| CONFIGURATION_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | CONFIGURATION_ACTIVE | Route findings to configurator |
| CONFIGURATION_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user |
| DEPLOYMENT_ACTIVE | Deployer returns deliverable | DEPLOYMENT_REVIEW | Submit to gatekeeper-azure |
| DEPLOYMENT_REVIEW | Gatekeeper-azure APPROVED | VERIFICATION_ACTIVE | Delegate to azure-verifier |
| DEPLOYMENT_REVIEW | Gatekeeper-azure REVISE (attempt < 3) | DEPLOYMENT_ACTIVE | Route findings to deployer |
| DEPLOYMENT_REVIEW | Gatekeeper-azure REVISE (attempt = 3) | DEADLOCKED | Escalate to user |
| VERIFICATION_ACTIVE | Verifier returns deliverable | VERIFICATION_REVIEW | Submit to gatekeeper-azure for verification review + final adversarial sweep |
| VERIFICATION_REVIEW | Gatekeeper-azure APPROVED | CONSOLIDATION | Assemble Azure Package |
| VERIFICATION_REVIEW | Gatekeeper-azure REVISE against Phase 5 | VERIFICATION_ACTIVE | Route findings to verifier |
| VERIFICATION_REVIEW | Gatekeeper-azure REVISE against earlier phase | [Earliest impacted phase]_ACTIVE | Rewind and replay downstream phases |
| VERIFICATION_REVIEW | Gatekeeper-azure REVISE (attempt = 3 for impacted phase) | DEADLOCKED | Escalate to user |
| CONSOLIDATION | Cross-deliverable consistency check passed | DELIVERED | Return Azure Package |
| DEADLOCKED | User resolves or overrides | [Resolved phase ACTIVE] | Continue from resolved state |

All transitions trigger the appropriate save behavior from `save-protocol.md`.

---

## Proactive Driving

Azure-provisioner MUST proactively:

- detect existing Azure artifacts and choose the correct entry phase
- pass approved upstream Azure deliverables forward unchanged
- resolve minor ambiguities without unnecessary user interruptions
- track verdicts, rewinds, and revision cycles
- surface region, quota, and SKU constraints early
- document accepted risks and user overrides in the pipeline record

---

## Additional Resources

- `references/workflow-protocol.md`
- `references/handoff-templates.md`
- `save-protocol.md`
