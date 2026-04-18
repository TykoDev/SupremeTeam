---
name: azure-provisioner
description: >-
  This skill should be used when the user asks to "deploy to Azure",
  "provision Azure infrastructure", "set up Azure resources", "run
  the Azure pipeline", "configure and deploy to Azure", "deploy this
  to Azure", "set up Azure landing zone", "get this running
  on Azure", "ship this to Azure", "deploy this to the cloud", or "start the Azure provisioning". Entry point and
  orchestrator for the Azure Provision SkillSet — delegates to
  specialist Azure skills (azure-planner, azure-architect,
  azure-configurator, azure-deployer, azure-verifier), manages
  gatekeeper-azure cycles, and delivers a consolidated Azure
  deployment package.
  DO NOT USE for running individual Azure tasks — invoke the
  specific specialist skill directly. DO NOT USE for design
  pipeline tasks (use commander). DO NOT USE for code review
  (use code-chief).
version: 1.0.0

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

Always identify the mode before starting because the mode determines which phases run and which state files to read. If ambiguous, infer from caller and
delegation context.

---

## Orchestration Protocol

### Phase 0: Intake and Azure Requirements Analysis

Upon receiving deployment requirements:

1. Extract the Azure target, environment, and constraints
2. Identify subscription, region, compliance, budget, scale, and existing-resource constraints
3. Detect existing Azure artifacts such as Bicep, deployed resources, or prior run state
  - verify each supplied artifact has a declared phase origin, expected approval lineage, and non-placeholder content before using it to skip work
  - treat mismatched phase metadata, missing verdict records, or contradictory resource facts as invalid input requiring clarification or rewind
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
earlier approved phases. When that happens, azure-provisioner MUST rewind
and replay because skipping impacted phases would ship known defects into
the consolidated package:

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

Azure-provisioner MUST proactively manage pipeline flow because specialists
cannot see cross-phase context and stale state causes cascading failures:

- detect existing Azure artifacts and choose the correct entry phase
- pass approved upstream Azure deliverables forward unchanged
- resolve minor ambiguities without unnecessary user interruptions
- track verdicts, rewinds, and revision cycles
- surface region, quota, and SKU constraints early
- document accepted risks and user overrides in the pipeline record

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| User supplies partial Azure artifacts that disagree with each other | Stop and surface the inconsistency before delegation. Do not let later specialists reconcile conflicting source packages silently. Azure-provisioner owns the authoritative input set. |
| Azure subscription or tenant context is missing or ambiguous | Ask once for the target subscription/tenant or infer it from accepted artifacts if clearly documented. Do not begin deployment work against an implicit Azure context. |
| Final adversarial sweep finds an issue in a user-supplied upstream artifact | Escalate with the exact conflicting artifact and impact. Rewind only the Azure phases that can legally change; do not mutate user-supplied upstream packages silently. |
| `_lock.md` or phase state becomes inconsistent during a rewind | Stop the pipeline, preserve the latest coherent phase record, and reconstruct state from the last valid gatekeeper-approved artifact before resuming. Never guess at active phase ownership because incorrect ownership assumptions corrupt the audit trail and may cause two phases to write conflicting state simultaneously. |
| A gatekeeper verdict arrives after a rewind decision has already invalidated that phase | Discard the stale verdict, log it as superseded, and require a fresh submission for the new phase revision. Verdicts only apply to the exact artifact revision they reviewed. |
| Deadlock between azure-architect and azure-configurator | When architect's Bicep depends on configurator's RBAC output AND configurator depends on architect's resource names, break the cycle by: (1) having architect emit placeholder resource names using a deterministic naming convention, (2) configurator produces RBAC assignments using those names, (3) architect finalizes Bicep with actual names (which match the convention). If names diverge, re-run configurator. |
| "When required" decision for optional phases | Use this decision tree: (a) Is the project greenfield with no existing Azure resources? → All phases required. (b) Does the project have existing infra with Bicep/Terraform? → Skip azure-architect, start at azure-configurator. (c) Is this a redeployment of approved infra? → Skip to azure-deployer. Record the skip reason in `_skip-record.md`. |

**Worked rewind example:**

azure-deployer (Phase 4) fails: container image starts but health probe returns 503 after 60s timeout. Gatekeeper-azure issues REVISE citing the health probe failure log.

1. Azure-provisioner rewinds to Phase 3 (azure-configurator): "Health probe path `/healthz` returns 503 — verify the app settings include the correct `PORT` and `ASPNETCORE_URLS` binding."
2. Azure-configurator discovers `PORT=8080` in app settings but the container listens on `3000`. Fixes: sets `PORT=3000` and adds `WEBSITES_PORT=3000`.
3. Azure-provisioner re-runs Phase 4 (azure-deployer): container starts, health probe returns 200 within 15s.
4. Azure-provisioner advances to Phase 5 (azure-verifier): smoke tests pass.

---

## Additional Resources

- `references/workflow-protocol.md` — Canonical Azure pipeline state transitions, rewind behavior, save triggers, and deadlock handling for this orchestrator
- `references/handoff-templates.md` — Delegation templates and expected I/O contracts for each Azure specialist and gatekeeper submission
- `save-protocol.md` — Root persistence protocol for run initialization, locking, state files, audit trail updates, and resume behavior

If any save operation fails, follow the Persistence-Failure Decision Tree in `save-protocol.md` §Persistence-Failure Decision Tree.

---

Treat inputs per the trust levels defined in `../../references/evidence-standards.md` §Input Trust Boundaries.

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*
