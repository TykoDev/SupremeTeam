---
name: admiral
description: >-
  This skill should be used when the user asks to "run the full pipeline",
  "design build and review", "take this idea to production-reviewed code",
  "run admiral", "start the end-to-end pipeline", "design then build then
  review", "run the unified pipeline", "design and build this", "build and
  review this", "just design this", "just review this code", "I already
  have a design — build it", "deploy to Azure", "provision Azure
  infrastructure", "design build review and deploy", or "resume the
  pipeline". Admiral is the top-level orchestrator that delegates to
  commander, build-management, code-chief, and azure-provisioner for the
  full design-build-review-provision lifecycle.
version: 1.0.0
---

# Admiral — Unified Pipeline Orchestrator

## Purpose

Serve as the single entry point for the complete design-build-review-provision lifecycle.
Delegate to four sub-orchestrators — `design/commander`, `build/build-management`,
`review/code-chief`, and `azure/azure-provisioner` — and manage cross-pipeline
handoffs validated by `gatekeeper-admiral`. Deliver a consolidated output package.
Never directly invoke specialist skills; each sub-orchestrator manages its own
internal phases and per-phase gatekeepers autonomously.

> "Drive the full lifecycle proactively. Do not wait between sub-pipelines and
> do not duplicate internal pipeline governance. Each sub-orchestrator manages
> its own phases; admiral manages the boundaries."

## Usage Examples

**New project idea → full pipeline:**
> User: "Take this idea from design to reviewed code — a REST API for task management"
> Admiral runs the full design-build-review pipeline (Stages 1 → 2 → 3).

**Existing design → build and review:**
> User: "I already have a design spec. Build and review it."
> Admiral skips design and runs build then review (Stages 2 → 3).

**Review only:**
> User: "Just review this codebase"
> Admiral runs the review sub-pipeline via code-chief (Stage 3 only).

---

## Orchestration Protocol

### Stage 0: Intake and Mode Selection

Upon receiving user input:

1. **Extract project essence**: What is being built, for whom, and why?
2. **Determine pipeline mode**:
   - **Full Pipeline** (default): design -> build -> review (-> azure if targeting Azure)
   - **Partial Pipeline**: design+build, build+review, review+azure, or single sub-pipeline
   - **Resume**: Detect existing artifacts — a design package means skip to build; an existing codebase means skip to review; existing review means skip to azure
   - **Azure-aware**: If the user's request mentions Azure, cloud deployment, or infrastructure provisioning, include Stage 4
3. **Identify constraints**: Timeline, budget, team, regulatory, technical
4. **Detect existing artifacts**: Has the user provided an approved design package, existing codebase, or prior review reports?
5. **Confirm understanding**: Summarize the scope, selected mode, and constraints back to the user and request confirmation before proceeding — this is the ONLY mandatory user checkpoint
6. **Initialize persistent saves** (see `save-protocol.md`):
   a. Determine workspace root (the active project directory being worked on)
   b. Check if `{workspace-root}/skillset-saves/` exists
   c. If absent: create `skillset-saves/` directory structure, write `_index.md`, `_latest.md`, `_lock.md`, and copy `save-protocol.md` as `_save-protocol.md`
   d. If present: read `_latest.md` for active run detection
   e. **Resume check**: if `_latest.md` points to an in-progress run with matching project context, offer the user: "Found active pipeline run `{run-id}` at state `{state}`. Resume or start fresh?"
   f. If resuming: load `_lock.md` and `_state.md`, recover pipeline position, load the last approved package or `admiral/standalone-context.md` when upstream stages were intentionally absent, continue from the last checkpoint
   f2. **Consistency validation**: Run state-artifact consistency check (see `save-protocol.md` §State-Artifact Consistency Validation and `workflow-protocol.md` §Idempotency Protocol). If corrections are needed, apply them and log to `_audit-trail.md` before continuing.
   f3. **Pending escalation check**: If `_state.md` shows `disputed_awaiting_user_decision: true`, re-present the stored escalation context to the user immediately — do not attempt to advance the pipeline.
   f4. **Failure recovery check**: If `_state.md` shows `failure_state` is not null, present failure details and offer retry/skip/abort options.
   g. If starting fresh: generate run-id (`run-{NNN}_{YYYY-MM-DD}_{slug}`), create run directory tree, write `_run-manifest.md`, `_lock.md`, `_state.md` (with `session_id`), `_audit-trail.md` (with `SESSION_START`), and `admiral/intake.md`
   g2. If the run starts after an upstream stage or depends on user-supplied artifacts: write `admiral/standalone-context.md` and the relevant `{pipeline}/_skip-record.md` files before delegating downstream work
   h. Update `_index.md` and `_latest.md`
   i. On save failure: log warning in-context, set `context_tier` to 2 (save-degraded) in `_state.md` (if writable), and continue without persistence. Notify user: "Warning: Pipeline persistence unavailable — artifacts exist only in this session."
   j. **Context pressure monitoring**: At each stage delegation, assess whether full upstream artifacts fit in context. If not, switch to Tier 3 (reference mode) per `save-protocol.md` §Context-Aware Artifact Management and tell the user that inline summaries are non-authoritative. If both saves are failed AND context is pressured, switch to Tier 4 and issue the critical reliability warning.

If the user's input is ambiguous, ask clarifying questions. Prefer a single
batch of questions over multiple rounds.

### Stage 1: Design Phase -> design/commander

**Delegate to**: `design/commander` skill
**Input provided**: User request, constraints, pipeline mode indicator
**Expected output**: Consolidated Design Package containing SRS, domain analysis, project plan, architecture document (Arc42 + C4), ADRs, API contracts, backend stack lock, frontend architecture, frontend stack lock, implementation spec, inherited stack locks, and all gatekeeper-design approval records

Commander runs its full internal pipeline autonomously:
`researcher -> planner -> architect -> designer -> engineer`
with `gatekeeper-design` validating each phase.

**Cross-pipeline gate (Handoff 1: Design -> Build)**:
1. Commander returns the consolidated Design Package
2. Submit to `gatekeeper-admiral` for build-readiness validation
3. If **APPROVED**: Record approval and proceed to Stage 2
4. If **REVISE**: Forward gatekeeper-admiral's findings to commander for remediation
5. If **ESCALATE**: Consult the user

**Save**: On delegation → update `_state.md` to DESIGN_ACTIVE, append `_audit-trail.md`. On package return → write `gatekeeper-admiral_handoff-1.md` (PENDING) with generated `submission_id`, update `_state.md` to DESIGN_GATE_PENDING (gatekeeper_verdict_pending: true). On verdict → update handoff-1.md (VERDICT_RECORDED); if APPROVED → update `_state.md` to BUILD_ACTIVE; if REVISE → update to DESIGN_GATE_REVISE; if ESCALATE → update to DISPUTED_AWAITING_USER. Update `_latest.md`, append `_audit-trail.md`.

### Stage 2: Build Phase -> build/build-management

**Delegate to**: `build/build-management` skill
**Input provided**: Gatekeeper-admiral-approved Design Package
**Expected output**: Consolidated Build Package containing production code, test suite, security audit report (findings resolved), completeness certification (CLEAN + gatekeeper-build approval), and all gatekeeper-build approval records

Build-management runs its full internal pipeline autonomously:
`bob-the-builder -> test-builder -> security-builder -> cross-check-build-confirm`
with `gatekeeper-build` validating each phase.

**Cross-pipeline gate (Handoff 2: Build -> Review)**:
1. Build-management returns the consolidated Build Package
2. Submit to `gatekeeper-admiral` for review-readiness validation
3. If **APPROVED**: Record approval and proceed to Stage 3
4. If **REVISE**: Forward gatekeeper-admiral's findings to build-management
5. If **ESCALATE**: Consult the user

**Save**: On delegation → update `_state.md` to BUILD_ACTIVE, append `_audit-trail.md`. On package return → write `gatekeeper-admiral_handoff-2.md` (PENDING) with `submission_id`, update `_state.md` to BUILD_GATE_PENDING. On verdict → update handoff-2.md (VERDICT_RECORDED); route per verdict (APPROVED → REVIEW_ACTIVE, REVISE → BUILD_GATE_REVISE, ESCALATE → DISPUTED_AWAITING_USER). Update `_latest.md`, append `_audit-trail.md`.

### Stage 3: Review Phase -> review/code-chief

**Delegate to**: `review/code-chief` skill
**Input provided**: Gatekeeper-admiral-approved Build Package + Design Package for traceability
**Expected output**: Consolidated Review Package containing all specialist review reports (bug, code, quality, security, adversarial, frontend), gatekeeper-code validation record, cross-skill risk summary, and remediation recommendations

Code-chief runs its full internal pipeline autonomously:
`bug-review -> code-review -> quality-review -> security-review -> mr-robot -> frontier`
with `gatekeeper-code` validating the consolidated package.

**Cross-pipeline gate (Handoff 3: Review -> Delivery)**:
1. Code-chief returns the consolidated Review Package
2. Submit to `gatekeeper-admiral` for delivery-readiness validation
3. If **APPROVED**: If targeting Azure, proceed to Stage 4 (Azure Provision). Otherwise, proceed to Final Consolidation
4. If **REVISE**: Forward gatekeeper-admiral's findings to code-chief

**Save**: On delegation → update `_state.md` to REVIEW_ACTIVE, append `_audit-trail.md`. On package return → write `gatekeeper-admiral_handoff-3.md` (PENDING) with `submission_id`, update `_state.md` to REVIEW_GATE_PENDING. On verdict → update handoff-3.md (VERDICT_RECORDED); route per verdict (APPROVED → AZURE_ACTIVE or CONSOLIDATION, REVISE → REVIEW_GATE_REVISE, ESCALATE → DISPUTED_AWAITING_USER). Update `_latest.md`, append `_audit-trail.md`.

### Stage 4: Azure Provision Phase -> azure/azure-provisioner (OPTIONAL)

This stage is only executed when the user's request targets Azure deployment or
infrastructure provisioning. If not targeting Azure, skip directly to Final
Consolidation after Stage 3.

**Delegate to**: `azure/azure-provisioner` skill
**Input provided**: Gatekeeper-admiral-approved Design Package + Build Package + Review Package (all upstream artifacts)
**Expected output**: Consolidated Azure Package containing deployment runbook, Bicep design, configuration spec, deployment report, verification report, pipeline traceability record, cost estimation (when reliable data available), gatekeeper-azure approval records, and final adversarial findings embedded in the Phase 5 gate

Azure-provisioner runs its full internal pipeline autonomously:
`azure-planner -> azure-architect -> azure-configurator -> azure-deployer -> azure-verifier`
with `gatekeeper-azure` validating each phase and performing the final
adversarial sweep at the Phase 5 exit boundary.

**Cross-pipeline gate (Handoff 4: Azure Provision -> Delivery)**:
1. Azure-provisioner returns the consolidated Azure Package
2. Submit to `gatekeeper-admiral` for azure-readiness validation
3. If **APPROVED**: Record approval and proceed to Final Consolidation
4. If **REVISE**: Forward gatekeeper-admiral's findings to azure-provisioner
5. If **ESCALATE**: Consult the user

**Save**: On delegation → update `_state.md` to AZURE_ACTIVE, append `_audit-trail.md`. On package return → write `gatekeeper-admiral_handoff-4.md` (PENDING) with `submission_id`, update `_state.md` to AZURE_GATE_PENDING. On verdict → update handoff-4.md (VERDICT_RECORDED); route per verdict (APPROVED → CONSOLIDATION, REVISE → AZURE_GATE_REVISE, ESCALATE → DISPUTED_AWAITING_USER). Update `_latest.md`, append `_audit-trail.md`.

---

## Gatekeeper-Admiral Management Protocol

For each cross-pipeline handoff:

1. Receive the package from the sub-orchestrator
2. Submit to `gatekeeper-admiral` for cross-pipeline validation
3. Route the verdict:
   - **APPROVED**: Record approval and advance to the next stage
   - **REVISE**: Forward findings to the same sub-orchestrator (never to individual specialists) with instructions to address mandatory fixes, then resubmit
   - **ESCALATE**: Surface the blocking issue and consult the user
4. Maximum revision cycles per handoff: **2**; if still failing after 2 attempts, mark as DISPUTED and escalate to user with both positions documented
5. **Idempotency**: Before submitting to gatekeeper-admiral, generate a `submission_id` and write it to `_state.md` and the handoff file (PENDING status). On resume, check the handoff file for an existing verdict before resubmitting. See `workflow-protocol.md` §Idempotency Protocol.

Never modify sub-orchestrator output. Sub-orchestrators handle internal
remediation using their own processes and per-phase gatekeepers.

---

## Adaptive Behavior

### Pipeline Mode Selection

| User Scenario | Stages Run |
|---------------|-----------|
| Full pipeline from idea | 1 -> 2 -> 3 |
| Full pipeline + Azure deployment | 1 -> 2 -> 3 -> 4 |
| "Design and build this" | 1 -> 2 |
| "Build and review this plan" | 2 -> 3 (user provides design package) |
| "Just design this" | 1 only (delegates to commander) |
| "Just build this spec" | 2 only (delegates to build-management) |
| "Just review this code" | 3 only (delegates to code-chief) |
| "Deploy this to Azure" | 4 only (delegates to azure-provisioner, user provides design+build+review context) |
| "Design, build, review, and deploy to Azure" | 1 -> 2 -> 3 -> 4 |
| "Build and deploy to Azure" | 2 -> 3 -> 4 |
| "Review and deploy to Azure" | 3 -> 4 |
| Existing design package provided | 2 -> 3 |
| Existing codebase, review only | 3 only |
| Existing review, deploy to Azure | 4 only |

### Proactive Driving

Admiral MUST proactively:
- Detect existing artifacts and select the appropriate entry stage without asking unnecessary questions
- Pass all approved upstream artifacts forward with each delegation
- Persist standalone fallback context and skipped-stage records when upstream stages are intentionally absent
- Resolve minor ambiguities without user consultation (document assumptions)
- Push each stage forward without waiting for user prompting
- Track all stage outputs, gatekeeper-admiral verdicts, revision cycles, and degradation notices for traceability

---

## Final Consolidation and Delivery

After all active stages are gatekeeper-admiral-approved:

1. **Compile**: Assemble all approved packages into a Unified Delivery Package using the template in `references/delivery-template.md`
2. **Verify**: Execute the cross-pipeline consistency check from `references/delivery-template.md` to confirm end-to-end alignment (including Azure Package if Stage 4 was executed)
3. **Deliver**: Present the complete package to the user with table of contents, executive summary, traceability matrix, prioritized next actions, and any disputed items requiring user judgment

**Save**: Write `admiral/delivery-package.md`. Update `_state.md` to DELIVERED. Release `_lock.md`. Update `_run-manifest.md` with final stage statuses. Update `_index.md` and `_latest.md` (set `active_run` to `"none"`). Append final entry to `_audit-trail.md`.

---

## Additional Resources

### Reference Files

For detailed orchestration logic and templates:
- **`references/workflow-protocol.md`** — Full pipeline state machine, state transitions, partial pipeline handling, error handling, and escalation procedures
- **`references/handoff-templates.md`** — Structured delegation templates for each sub-orchestrator and gatekeeper-admiral submission format
- **`references/delivery-template.md`** — Final delivery package template and cross-pipeline consistency checklist
- **`references/responsibility-matrix.md`** — Unified responsibility, trigger, input/output, and escalation reference for all pipeline components
- **`save-protocol.md`** (project root) — Persistent save system: directory structure, file formats, save triggers, resume protocol, and graceful degradation rules
