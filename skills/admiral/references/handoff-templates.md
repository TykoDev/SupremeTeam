# Admiral Handoff Templates

> **Scope**: Admiral-specific delegation templates for cross-pipeline handoffs
> (Stages 1–4) and gatekeeper-admiral submissions. For universal delegation
> templates used by all sub-orchestrators, see `../../references/handoff-templates.md`.

> **Placeholder notation**: Square-bracket tokens in this file are template
> placeholders to be replaced during delegation construction. The authoritative
> persisted-path format in `save-protocol.md` uses brace variables such as
> `{run-id}`.

## Global Delegation Rules

### Context Mode Rules

1. Read `context_tier` and `artifact_mode` from `_state.md` before constructing any delegation
2. If `artifact_mode` is `inline`, include the full upstream artifact inline
3. If `artifact_mode` is `reference`, include a concise summary plus authoritative save paths
4. If `artifact_mode` is `best-effort-inline`, explicitly state that fidelity is unverified and that the downstream consumer must treat exact traceability as `UNVERIFIED`

### Reliability Notice Rules

For any delegation that depends on prior-stage artifacts, include an
`### Upstream Reliability Status` section when any of the following are true:

- `context_tier` is 2, 3, or 4
- any upstream stage was skipped, user-supplied, or marked `NOT_REQUIRED`
- `standalone-context.md` is the upstream source of truth
- `artifact_integrity_status` is `UNVERIFIED` or `FAILED`

The block must state:

- the current degradation tier
- whether inline summaries are authoritative or not
- whether resume is reliable beyond the current session
- which skip records or fallback context files govern the upstream assumption set

## Stage 1 Delegation: design/commander

```markdown
## ADMIRAL DELEGATION: Stage 1 — Design Pipeline

### Execution Mode
Pipeline mode delegated by admiral. Commander operates its full internal
pipeline autonomously (researcher -> planner -> architect -> designer ->
engineer, with gatekeeper-design at each phase). Return the consolidated
Design Package to admiral when all internal phases are gatekeeper-design-
approved.

### Original User Request
[Paste user's project description verbatim]

### Identified Constraints
- **Timeline**: [Specified or "Not specified"]
- **Team size**: [Specified or "Not specified"]
- **Budget**: [Specified or "Not specified"]
- **Regulatory**: [Specified or "None identified"]
- **Technical constraints/preferences**: [Specified or "None identified"]
- **Existing systems**: [Specified or "Greenfield project"]

### Pipeline Mode
[Full Pipeline / Design+Build / Design Only]

### Admiral Notes
[Any additional context, clarifications from intake, or assumptions made]

### Expected Deliverable
Consolidated Design Package containing:
1. Software Requirements Specification (SRS)
2. Domain Analysis (bounded contexts, domain model)
3. Project Plan (milestones, risks, rollout strategy)
4. Architecture Document (Arc42 with C4 diagrams)
5. ADR Collection
6. API Contracts (OpenAPI/AsyncAPI specifications)
7. Backend Stack Lock (exact overlay + version tuple)
8. Frontend Architecture Specification (if applicable)
9. Frontend Stack Lock (if applicable)
10. Implementation Specification
11. Inherited Stack Locks record
12. All gatekeeper-design approval records

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/design/
- **Persistence active**: [yes/no]
- **Context tier**: [1/2/3/4]
- **Artifact mode**: [inline/reference/best-effort-inline]
- **Standalone fallback ref**: [none or path]
- **Skipped upstream stages**: [none or list]

### Return Contract
Return the complete Design Package to admiral for gatekeeper-admiral
cross-pipeline validation. Do NOT submit to gatekeeper-admiral yourself.
Admiral owns cross-pipeline gate submission, revision routing, and escalation.
```

---

## Stage 2 Delegation: build/build-management

```markdown
## ADMIRAL DELEGATION: Stage 2 — Build Pipeline

### Execution Mode
Pipeline mode delegated by admiral. Build-management operates its full
internal pipeline autonomously (bob-the-builder -> test-builder ->
security-builder -> cross-check-build-confirm, with gatekeeper-build at
each phase). Return the consolidated Build Package to admiral when all
internal phases are gatekeeper-build-approved.

### Approved Design Package
[CONTEXT MODE DECISION — select based on current degradation tier:

**If Tier 1/2 (inline mode):**
Paste the full gatekeeper-admiral-approved Design Package inline below.

**If Tier 3/4 (reference mode):**
- **Mode**: Reference (full artifact persisted to disk)
- **Location**: skillset-saves/runs/[run-id]/design/commander/design-package.md
- **Summary**: [3-5 sentences: project scope, architecture style, key stack locks, module count, critical constraints, API endpoint count]
- **Key artifacts for build**:
  - API Contracts: skillset-saves/runs/[run-id]/design/phase-3_architect/deliverable_api-contracts.md
  - Data Model: skillset-saves/runs/[run-id]/design/phase-3_architect/deliverable_data-model.md
  - Implementation Spec: skillset-saves/runs/[run-id]/design/phase-5_engineer/deliverable_implementation-spec.md
  - Stack Locks: skillset-saves/runs/[run-id]/design/commander/stack-lock-registry.md

See save-protocol.md §Context-Aware Artifact Management for the full reference mode protocol.

### Design Package Summary
- Total functional requirements: [count]
- Architecture style: [selected]
- Backend stack: [overlay + version tuple]
- Frontend stack: [overlay + version tuple or N/A]
- Modules to implement: [ordered list from implementation spec]
- API contracts: [count of endpoints/events]

### Upstream Reliability Status
- **Degradation tier**: [Tier 1 / Tier 2 / Tier 3 / Tier 4]
- **Artifact mode**: [inline / reference / best-effort-inline]
- **Resume reliability**: [Normal / Not guaranteed beyond current session]
- **Traceability status**: [Verified / Unverified due to skipped or external upstream context]
- **Supporting records**: [None or paths to `_skip-record.md` / `admiral/standalone-context.md`]
- **Required handling**: [Read referenced artifacts for exact schema/contract detail when summaries are non-authoritative]

### Admiral Notes
[Any observations from the design gate, constraints, or user preferences
relevant to implementation]

### Expected Deliverable
Consolidated Build Package containing:
1. Production code (all modules, gatekeeper-build-approved)
2. Test suite (unit, integration, E2E — gatekeeper-build-approved)
3. Security audit report (gatekeeper-build-approved; all findings resolved)
4. Completeness certification (CLEAN verdict + final gatekeeper-build approval)
5. All gatekeeper-build approval records

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/build/
- **Persistence active**: [yes/no]
- **Context tier**: [1/2/3/4]
- **Artifact mode**: [inline/reference/best-effort-inline]
- **Standalone fallback ref**: [none or path]
- **Skipped upstream stages**: [none or list]

### Return Contract
Return the complete Build Package to admiral for gatekeeper-admiral
cross-pipeline validation. Do NOT submit to gatekeeper-admiral yourself.
Admiral owns cross-pipeline gate submission, revision routing, and escalation.
```

---

## Stage 3 Delegation: review/code-chief

```markdown
## ADMIRAL DELEGATION: Stage 3 — Review Pipeline

### Execution Mode
Pipeline mode delegated by admiral. Code-chief operates its full internal
pipeline autonomously (bug-review -> code-review -> quality-review ->
security-review -> mr-robot -> frontier, with gatekeeper-code validating
the consolidated package). Return the consolidated Review Package to
admiral when gatekeeper-code has validated the review suite.

### Review Target
[CONTEXT MODE DECISION — select based on current degradation tier:

**If Tier 1/2 (inline mode):**
Paste the full gatekeeper-admiral-approved Build Package inline below.

**If Tier 3/4 (reference mode):**
- **Mode**: Reference (full artifact persisted to disk)
- **Location**: skillset-saves/runs/[run-id]/build/build-management/build-package.md
- **Summary**: [3-5 sentences: modules implemented, test coverage, security findings status, completeness verdict]
- **Key artifacts for review**:
  - Source code: [list of module directories]
  - Test suite: [location]
  - Security audit: skillset-saves/runs/[run-id]/build/phase-3_security-builder/deliverable_security-audit.md

### Design Context
[CONTEXT MODE DECISION:

**If Tier 1/2 (inline mode):**
Paste the approved Design Package for traceability between requirements, architecture decisions, and review findings.

**If Tier 3/4 (reference mode):**
- **Mode**: Reference
- **Location**: skillset-saves/runs/[run-id]/design/commander/design-package.md
- **Summary**: [2-3 sentences: key requirements, architecture decisions relevant to review]
- **Key artifacts for traceability**: SRS, ADRs, API Contracts (save paths)]

### Build Package Summary
- Modules implemented: [count]
- Test coverage: [percentage if known]
- Security findings resolved: [count]
- Completeness scan: CLEAN
- Frontend present: [Yes/No — determines whether frontier runs]

### Upstream Reliability Status
- **Degradation tier**: [Tier 1 / Tier 2 / Tier 3 / Tier 4]
- **Artifact mode**: [inline / reference / best-effort-inline]
- **Resume reliability**: [Normal / Not guaranteed beyond current session]
- **Traceability status**: [Verified / Unverified due to skipped or external upstream context]
- **Supporting records**: [None or paths to `_skip-record.md` / `admiral/standalone-context.md`]
- **Required handling**: [Read referenced artifacts for exact evidence, counts, and contract detail when summaries are non-authoritative]

### Admiral Notes
[Any observations from the build gate, areas of concern, or user
priorities for the review]

### Expected Deliverable
Consolidated Review Package containing:
1. Bug Review Report (correctness defects)
2. Code Review Assessment (merge-readiness, 8-dimension scores)
3. Quality Review Report (maintainability, standards, tech debt)
4. Security Review Report (NIST SSDF, OWASP, CWE mapping)
5. Adversarial Analysis Report (exploit chains, CVSS scores)
6. Frontend Audit Report (if applicable — Core Web Vitals, WCAG, CSP)
7. Gatekeeper-code validation record
8. Cross-skill risk summary table
9. Remediation recommendations (prioritized)

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/
- **Persistence active**: [yes/no]
- **Context tier**: [1/2/3/4]
- **Artifact mode**: [inline/reference/best-effort-inline]
- **Standalone fallback ref**: [none or path]
- **Skipped upstream stages**: [none or list]

### Return Contract
Return the complete Review Package to admiral for gatekeeper-admiral
delivery validation. Do NOT submit to gatekeeper-admiral yourself.
Admiral owns cross-pipeline gate submission, revision routing, and escalation.
```

---

## Stage 4 Delegation: azure/azure-provisioner

```markdown
## ADMIRAL DELEGATION: Stage 4 — Azure Provision Pipeline

### Execution Mode
Pipeline mode delegated by admiral. Azure-provisioner operates its full
internal pipeline autonomously (azure-planner -> azure-architect ->
azure-configurator -> azure-deployer -> azure-verifier, with
gatekeeper-azure at each phase and the final adversarial sweep embedded in
the Phase 5 gate). Return the consolidated Azure Package to admiral when
all internal phases are gatekeeper-azure-approved.

### Approved Design Package
[CONTEXT MODE DECISION — if Tier 1/2: include full package inline.
If Tier 3/4: reference mode with summary + save path.
Location: skillset-saves/runs/[run-id]/design/commander/design-package.md
Key artifacts for Azure: Architecture doc, stack locks, API contracts.]

### Approved Build Package
[CONTEXT MODE DECISION — if Tier 1/2: include full package inline.
If Tier 3/4: reference mode with summary + save path.
Location: skillset-saves/runs/[run-id]/build/build-management/build-package.md
Key artifacts for Azure: Container image details, deployment-ready code.]

### Approved Review Package
[CONTEXT MODE DECISION — if Tier 1/2: include full package inline.
If Tier 3/4: reference mode with summary + save path.
Location: skillset-saves/runs/[run-id]/review/code-chief/review-package.md
Key artifacts for Azure: Security findings, review verdict.]

### Upstream Package Summary
- Architecture style: [from Design Package]
- Backend stack: [from Design Package]
- Frontend stack: [from Design Package or N/A]
- Container images: [from Build Package — count and registry]
- Security findings: [from Review Package — count of resolved items]
- Review verdict: [PASS / CONDITIONAL PASS]

### Upstream Reliability Status
- **Degradation tier**: [Tier 1 / Tier 2 / Tier 3 / Tier 4]
- **Artifact mode**: [inline / reference / best-effort-inline]
- **Resume reliability**: [Normal / Not guaranteed beyond current session]
- **Traceability status**: [Verified / Unverified due to skipped or external upstream context]
- **Supporting records**: [None or paths to `_skip-record.md` / `admiral/standalone-context.md`]
- **Required handling**: [Read referenced artifacts for exact deployment/security detail when summaries are non-authoritative]

### Azure-Specific Constraints
- **Target subscription**: [specified or "To be determined by planner"]
- **Target region**: [specified or "To be determined by planner"]
- **Azure environment**: [Public / Government / Sovereign]
- **Budget constraints**: [specified or "Not specified"]
- **Compliance requirements**: [specified or "None identified"]

### Admiral Notes
[Any observations from the review gate, areas of concern for Azure
deployment, user priorities for the provision pipeline, or cost
constraints]

### Expected Deliverable
Consolidated Azure Package containing:
1. Deployment Runbook (strategy, resources, dependencies, cost estimation when reliable data available)
2. Bicep Design (modules, parameters, outputs, naming conventions)
3. Configuration Specification (RBAC, secrets, app settings, diagnostic settings)
4. Deployment Report (execution log, resource inventory, health verification)
5. Verification Report (8-layer check results for all deployed resources)
6. Pipeline Traceability Record (phase status, revision history, accepted risks)
7. Cost Estimation Report (when reliable data available; source-attributed; or documented omission)
8. Azure Resource Summary (Resource Group, Subscription, Region, SKU selections, endpoint URLs)
9. Deployment Checklist & Next Actions (post-deployment steps, monitoring, DNS/SSL, backup/DR)
10. All gatekeeper-azure approval records, including the Phase 5 final adversarial sweep findings

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/azure/
- **Persistence active**: [yes/no]
- **Context tier**: [1/2/3/4]
- **Artifact mode**: [inline/reference/best-effort-inline]
- **Standalone fallback ref**: [none or path]
- **Skipped upstream stages**: [none or list]

### Return Contract
Return the complete Azure Package to admiral for gatekeeper-admiral
cross-pipeline validation. Do NOT submit to gatekeeper-admiral yourself.
Admiral owns cross-pipeline gate submission, revision routing, and escalation.
```

---

## Gatekeeper-Admiral Submission Template

```markdown
## ADMIRAL -> GATEKEEPER-ADMIRAL: Cross-Pipeline Validation Request

### Run ID
[run-id or "standalone"]

### Submission ID
[{run-id}_handoff-{N}_attempt-{M}_{ISO-timestamp} — unique per submission for idempotency tracking]

### Handoff Point
[Design->Build / Build->Review / Review->Azure / Review->Delivery / Azure->Delivery]

### Source Pipeline
[commander / build-management / code-chief / azure-provisioner]

### Downstream Target
[build-management / code-chief / azure-provisioner / user delivery]

### Revision Attempt
[1 / 2]

### Package Summary
[Brief description of what the package contains — deliverable count,
key artifacts, scope]

### Upstream Internal Approvals
[List of internal gatekeeper approvals from the source pipeline,
e.g., "gatekeeper-design approved Phases 1-5" or "gatekeeper-build
approved Phases 1-4"]

### Known Concerns
[Any issues noted during the pipeline that may affect the handoff,
or "None identified"]

### Context Reliability Status
- **Degradation tier**: [Tier 1 / Tier 2 / Tier 3 / Tier 4]
- **Artifact mode**: [inline / reference / best-effort-inline]
- **Resume reliability**: [Normal / Not guaranteed beyond current session]
- **Skipped or external upstream context**: [None or referenced records]
- **Verification impact**: [None / Some checks must be treated as `UNVERIFIED` or `N/A`]

### Instruction
Execute cross-pipeline validation protocol for Handoff [1/2/3/4].
Verify completeness, alignment, consistency, and feasibility per
`gatekeeper-admiral/references/cross-pipeline-criteria.md`. Issue verdict: APPROVED,
REVISE, or ESCALATE.
```

---

## Gatekeeper-Admiral Findings Routing Template

When gatekeeper-admiral issues a REVISE verdict, route findings back to the
source sub-orchestrator using this template:

```markdown
## ADMIRAL REVISION REQUEST: [Source Sub-Orchestrator]

### Context
Gatekeeper-admiral reviewed the [Design/Build/Review/Azure] Package at Handoff
[1/2/3/4] and issued a REVISE verdict.

### Revision Attempt
[1 / 2] of 2 maximum

### Mandatory Fixes
[Paste gatekeeper-admiral's critical and major findings verbatim]

### Advisory Notes
[Paste gatekeeper-admiral's minor findings — recommended but not blocking]

### Instruction
Address all mandatory fixes using your internal pipeline processes.
Resubmit the revised package to admiral for gatekeeper-admiral re-review.

### Escalation Warning
[If attempt 2]: This is the final revision attempt. If gatekeeper-admiral
issues another REVISE verdict, the issue will be escalated to the user
as DISPUTED.

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/[pipeline]/
- **Persistence active**: [yes/no]
- **Context tier**: [1|2|3|4]
- **Artifact mode**: [inline|reference|best-effort-inline]
- **Standalone fallback ref**: [path or "none"]
- **Skipped upstream stages**: [none or list]
```
