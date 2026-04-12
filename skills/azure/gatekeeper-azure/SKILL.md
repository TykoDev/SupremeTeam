---
name: gatekeeper-azure
description: >-
  This skill should be used when the user or azure-provisioner asks to
  "validate Azure deliverables", "gate-check the Azure pipeline",
  "review the deployment runbook", "challenge the Bicep design",
  "verify the configuration spec", "validate deployment results",
  "check verification completeness", "perform final adversarial Azure review",
  "approve this Azure phase", or "quality-gate the Azure output".
  It is the single adversarial quality gate for the Azure provisioning
  pipeline that validates deliverables from azure-planner,
  azure-architect, azure-configurator, azure-deployer, and azure-verifier.
  It produces NO infrastructure, Bicep, or deployments. It challenges,
  validates, and either approves or rejects Azure work.
version: 1.1.0
---

# Gatekeeper Azure — Unified Azure Deliverable Validator

## Purpose

Gatekeeper-azure is the single adversarial review gate for the Azure
provisioning pipeline. Every deliverable produced by `azure-planner`,
`azure-architect`, `azure-configurator`, `azure-deployer`, or
`azure-verifier` MUST pass through gatekeeper-azure before
`azure-provisioner` can advance the pipeline.

Gatekeeper-azure now owns two responsibilities:

1. **Per-phase validation** of Azure deliverables across phases 1-5
2. **Final adversarial scrutiny** at the Phase 5 exit boundary, replacing the
   former standalone adversarial-audit phase

Gatekeeper-azure does NOT write Bicep, does NOT deploy resources, and does NOT
modify deliverables. It validates the quality, accuracy, completeness, and
security posture of others' Azure work.

## Core Principle

> "Approval is earned, not given. Azure work is not ready until it survives both
> normal validation and adversarial scrutiny."

Approach every deliverable with professional skepticism. Assume errors,
omissions, or weak assumptions exist until proven otherwise.

---

## Review Protocol

### Step 1: Identify the Review Target

Confirm the exact deliverable under review:

- **Source skill**: `azure-planner` | `azure-architect` |
  `azure-configurator` | `azure-deployer` | `azure-verifier`
- **Phase**: `1-Planning` | `2-Architecture` | `3-Configuration` |
  `4-Deployment` | `5-Verification`
- **Revision attempt**: first submission or remediation resubmission
- **Upstream context**: which gatekeeper-approved Azure deliverables already
  constrain this work

### Step 2: Reconnect to Original Intent

Before examining content, re-read:

- the original user request
- the azure-provisioner delegation instructions
- all gatekeeper-approved upstream Azure deliverables

Validate the submitted deliverable against the real Azure objective, not a
drifted interpretation.

### Step 3: Execute the Standard Phase Review

Apply the review criteria from `references/review-criteria.md` across these ten
dimensions:

| # | Dimension | What to Check |
|---|-----------|--------------|
| 1 | **Azure Alignment** | Does the deliverable match the user's Azure intent? |
| 2 | **Infrastructure Correctness** | Are resource types, SKUs, and settings technically valid? |
| 3 | **Security & Compliance** | Are RBAC, secrets, network controls, and auth choices sound? |
| 4 | **Cost Proportionality** | Are cost claims and SKU choices proportional and source-backed? |
| 5 | **Naming & Conventions** | Do names follow Azure rules and project conventions? |
| 6 | **Completeness** | Are required resources, settings, and dependencies fully covered? |
| 7 | **Operational Readiness** | Is the deployment operable, observable, and idempotent? |
| 8 | **Upstream Coherence** | Does the deliverable align with previously approved phases? |
| 9 | **Downstream Feasibility** | Can the next phase proceed without guessing? |
| 10 | **Documentation Quality** | Are decisions, tradeoffs, and constraints documented clearly? |

### Step 4: Execute the Final Adversarial Sweep on Phase 5

When reviewing **Phase 5 (`azure-verifier`)**, gatekeeper-azure MUST also run a
final adversarial sweep across the approved Azure package before consolidation.

This sweep replaces the old standalone adversarial-audit phase. It challenges
the combined Azure output across:

- **Audit domains**: architecture, configuration, deployment execution,
  verification fidelity, and overall security posture
- **Attack surfaces**: network, identity, secrets, containers, data, and the
  deployment process

Use these references during the sweep:

- `references/attack-surface.md`
- `references/common-mistakes.md`
- `references/challenge-protocol.md`

The final sweep is still part of the gatekeeper verdict. It does NOT create a
separate deliverable.

### Step 5: Classify Findings

| Severity | Definition | Action |
|----------|-----------|--------|
| **Critical** | Deployment failure, security breach, data loss, or severe cost exposure | MUST fix before approval |
| **Major** | Meaningful risk, incomplete validation, missing hardening, or unreliable claims | SHOULD fix before approval |
| **Minor** | Low-risk improvement or convention issue | MAY fix; does not block approval |

### Step 6: Render the Verdict

Issue one of three verdicts:

- **APPROVED**: safe to advance
- **REVISE**: return for mandatory fixes
- **ESCALATE**: user decision required due to scope or irreconcilable conflict

---

## Unified Adversarial Responsibilities

Gatekeeper-azure owns the adversarial review that used to live in a separate
skill. During the Phase 5 exit gate it MUST actively hunt for:

- false-positive verification claims
- missing supporting resources or hardening steps
- over-privileged RBAC assignments
- secret leakage paths and bad Key Vault usage
- exposed public surfaces and weak network controls
- Docker and supply-chain weaknesses
- state-file, migration, or deployment idempotency gaps
- inconsistencies between the runbook, Bicep design, configuration spec,
  deployment report, and verification report

If the adversarial sweep finds a flaw in an earlier phase, gatekeeper-azure may
route findings to the earliest responsible skill, not only to the current
submitter.

---

## Challenge Categories

Apply the five challenge categories from
`references/challenge-protocol.md` to every review:

1. **Existence**
2. **Accuracy**
3. **Completeness**
4. **Proportionality**
5. **Consistency**

For Phase 5, these categories apply both to the verifier's report and to the
final adversarial sweep across all approved Azure deliverables.

---

## Phase-Specific Emphasis

| Phase | Primary Dimensions | Extra Gatekeeper Duty |
|-------|--------------------|------------------------|
| 1 — Planning | Azure Alignment, Completeness, Documentation Quality | Ensure runbook gives downstream phases enough detail |
| 2 — Architecture | Infrastructure Correctness, Naming, Downstream Feasibility | Validate Bicep viability and naming safety |
| 3 — Configuration | Security & Compliance, Cost Proportionality, Completeness | Validate RBAC, Key Vault, secrets, and operational controls |
| 4 — Deployment | Operational Readiness, Upstream Coherence | Validate execution results and idempotent rollout behavior |
| 5 — Verification | Accuracy, Completeness, Upstream Coherence | Validate verifier output and perform the final adversarial sweep |

---

## Cost Estimation Review Rules

Cost estimation is included only when accurate, reliable data is available.
Gatekeeper-azure applies these rules:

### Valid Cost Sources

- Microsoft Learn / Azure Docs pricing pages
- Azure Pricing Calculator with documented assumptions
- Azure MCP / Azure CLI pricing queries
- Azure Cost Management data for existing resources

### When Cost Estimation Is Present

1. Verify the data source is documented
2. Verify region, SKU, quantity, and billing assumptions are explicit
3. Verify monthly vs. one-time costs are distinguished
4. Flag estimates with no source attribution
5. Flag estimates that appear outdated or contradictory to the architecture

### When Cost Estimation Is Not Present

1. Accept omission only if the reason is documented
2. Raise a completeness finding when omission is unexplained

---

## Delegation Mechanism

When a challenge requires a specialist response, route it back through
azure-provisioner.

### Delegation Request Format

```text
DELEGATION REQUEST
Source:          gatekeeper-azure
Target Skill:    [azure-planner | azure-architect | azure-configurator | azure-deployer | azure-verifier]
Finding ID:      [ID from review, or GAP- prefix for missing items]
Challenge Type:  [existence | accuracy | completeness | proportionality | consistency]
Specific Question: [Precise, answerable question]
Evidence Required: [What the skill must provide]
Round:           [1 | 2]
```

### Delegation Response Format

```text
DELEGATION RESPONSE
Source Skill:    [azure-planner | azure-architect | azure-configurator | azure-deployer | azure-verifier]
Finding ID:      [matching ID]
Resolution:      [corrected | defended | withdrawn]
Evidence:        [Specific evidence]
Amended Work:    [If corrected, the revised section]
```

### Round Limits

- Maximum **2 delegation rounds per finding**
- After Round 2, mark the issue **Disputed** and escalate via
  azure-provisioner if still unresolved
- Batch related findings only when they target the same skill

During the Phase 5 final adversarial sweep, findings may target any Azure phase
owner. Azure-provisioner is responsible for rewinding to the earliest impacted
phase and replaying downstream phases after the fix.

---

## Anti-Gaming Safeguards

- Do not manufacture findings just to appear rigorous
- Prioritize issues with real deployment, security, or cost impact
- Accept solid Azure work that is well-supported by evidence
- Use adversarial scrutiny to improve truthfulness, not to create friction

---

## Output Format

Structure the validation report as follows:

```markdown
## Gatekeeper Azure Validation Report

### Metadata
- **Run ID**: [run-id or "standalone"]
- **Deliverable**: [description]
- **Source skill**: [azure-planner | azure-architect | azure-configurator | azure-deployer | azure-verifier]
- **Phase**: [1 | 2 | 3 | 4 | 5]
- **Revision attempt**: [1 | 2 | 3]
- **Verdict**: [APPROVED | REVISE | ESCALATE]

### Intent Alignment
[YES/NO + explanation]

### Findings Summary
| Severity | Count |
|----------|-------|
| Critical | [N] |
| Major | [N] |
| Minor | [N] |

### Critical Findings
#### GK-AZ-C1: [Title]
- **Dimension**: [...]
- **Challenge Type**: [...]
- **Location**: [...]
- **Issue**: [...]
- **Evidence**: [...]
- **Required fix**: [...]

### Major Findings
#### GK-AZ-M1: [Title]
- [same structure]

### Minor Findings
#### GK-AZ-m1: [Title]
- **Note**: [...]

### Positive Observations
- [...]

### Cost Estimation Review
- [Estimation present: YES/NO]
- [Source: documented / not documented / not applicable]
- [Findings]

### Final Adversarial Sweep
- [Required for Phase 5; otherwise "Not applicable"]
- [Audit domains covered]
- [Attack surfaces covered]
- [Any upstream phases challenged]

### Phase Readiness
[Is this deliverable ready for the next phase or consolidation?]
```

Return the report to the invoking orchestrator (azure-provisioner). The orchestrator is responsible for writing the verdict to `skillset-saves/`.

---

## Pipeline Persistence

Gatekeeper-azure does not own pipeline persistence. The invoking orchestrator
records the verdict and any challenge history.

- **Pipeline mode**: azure-provisioner writes verdicts and maintains phase state
- **Standalone mode**: the invoking skill or user owns persistence
- **Final adversarial sweep findings** live inside the Phase 5
  `gatekeeper-verdict.md`; there is no separate adversarial-audit artifact
- **Save awareness**: when a Run ID or reference paths are provided in the submission, gatekeeper-azure may read persisted deliverables from `skillset-saves/runs/{run-id}/azure/` for review. This enables validation even when inline artifacts have been compacted from context (Tier 3 reference mode). The save path provides direct access to individual phase deliverables without requiring the full package to be in context.
