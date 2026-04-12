# Azure Provisioner — Handoff Templates

> **Placeholder notation**: Square-bracket tokens are template placeholders.

## Phase 1 Delegation: azure-planner

```markdown
## AZURE-PROVISIONER DELEGATION: Phase 1 — Deployment Planning

### Execution Mode
Pipeline mode delegated by azure-provisioner. Azure-planner operates
autonomously and returns the deployment runbook to azure-provisioner for
gatekeeper-azure review. Do NOT self-submit to gatekeeper-azure.

### Original User Request
[Paste user's deployment description verbatim]

### Azure Constraints
- **Subscription ID**: [Specified or TBD]
- **Tenant ID**: [Specified or TBD]
- **Region(s)**: [Specified or not yet selected]
- **Compliance requirements**: [GDPR/HIPAA/SOC2/ISO 27001/None]
- **Budget constraints**: [Specified or not specified]
- **Existing resources**: [List or greenfield deployment]
- **Azure quota status**: [Verified / needs check / unknown]

### Approved Upstream Packages
- **Design Package**: [Reference]
- **Build Package**: [Reference]
- **Review Package**: [Reference]

### Expected Deliverable
Deployment Runbook containing:
1. stage design
2. state management schema
3. environment-variable classification
4. secret detection and catalog
5. RBAC planning
6. migration strategy
7. rollout strategies
8. cost estimation when reliable data is available

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/azure/phase-1_azure-planner/
- **Persistence active**: [yes/no]
```

---

## Phase 2 Delegation: azure-architect

```markdown
## AZURE-PROVISIONER DELEGATION: Phase 2 — Infrastructure Architecture

### Execution Mode
Pipeline mode delegated by azure-provisioner. Azure-architect returns the
Bicep IaC design to azure-provisioner for gatekeeper-azure review.

### Approved Upstream Deliverables
- **Deployment Runbook**: [Reference to approved Phase 1 output]

### Expected Deliverable
Bicep IaC Design Package containing:
1. resource topology
2. naming convention
3. module decomposition
4. parameter strategy
5. output contract
6. security baseline

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/azure/phase-2_azure-architect/
- **Persistence active**: [yes/no]
```

---

## Phase 3 Delegation: azure-configurator

```markdown
## AZURE-PROVISIONER DELEGATION: Phase 3 — Resource Configuration

### Execution Mode
Pipeline mode delegated by azure-provisioner. Azure-configurator returns the
configuration specification to azure-provisioner for gatekeeper-azure review.

### Approved Upstream Deliverables
- **Deployment Runbook**: [Reference to Phase 1]
- **Bicep IaC Design Package**: [Reference to Phase 2]

### Expected Deliverable
Configuration Specification containing:
1. RBAC role assignments
2. Key Vault secret management
3. App Service configuration
4. PostgreSQL configuration
5. Storage and diagnostic configuration

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/azure/phase-3_azure-configurator/
- **Persistence active**: [yes/no]
```

---

## Phase 4 Delegation: azure-deployer

```markdown
## AZURE-PROVISIONER DELEGATION: Phase 4 — Deployment Execution

### Execution Mode
Pipeline mode delegated by azure-provisioner. Azure-deployer executes the
deployment and returns a deployment report to azure-provisioner for
gatekeeper-azure review.

### Approved Upstream Deliverables
- **Deployment Runbook**: [Reference to Phase 1]
- **Bicep IaC Design Package**: [Reference to Phase 2]
- **Configuration Specification**: [Reference to Phase 3]

### Expected Deliverable
Deployment Execution Report containing:
1. Bicep deployment results
2. image build/push results
3. runtime configuration and health checks
4. deployment state
5. rollback notes

### Operational Retry Note
Transient Azure or Docker failures may be retried operationally without
consuming a gatekeeper revision attempt.

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/azure/phase-4_azure-deployer/
- **Persistence active**: [yes/no]
```

---

## Phase 5 Delegation: azure-verifier

```markdown
## AZURE-PROVISIONER DELEGATION: Phase 5 — Deployment Verification

### Execution Mode
Pipeline mode delegated by azure-provisioner. Azure-verifier performs the
verification pass and returns the verification report to azure-provisioner for
gatekeeper-azure review.

### Approved Upstream Deliverables
- **Deployment Runbook**: [Reference to Phase 1]
- **Bicep IaC Design Package**: [Reference to Phase 2]
- **Configuration Specification**: [Reference to Phase 3]
- **Deployment Execution Report**: [Reference to Phase 4]

### Expected Deliverable
Verification Report containing:
1. infrastructure verification
2. RBAC verification
3. secrets verification
4. database verification
5. app-service verification
6. health-check results
7. smoke-test results
8. storage verification
9. overall PASS/FAIL status

### Gate Note
Gatekeeper-azure will use this Phase 5 submission for both:
- standard verification-report review
- the final adversarial sweep across the approved Azure package

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/azure/phase-5_azure-verifier/
- **Persistence active**: [yes/no]
```

---

## Gatekeeper-Azure Submission Template

```markdown
## AZURE-PROVISIONER -> GATEKEEPER-AZURE: Phase Review Request

### Run ID
[run-id or "standalone"]

### Phase
[1-Planning / 2-Architecture / 3-Configuration / 4-Deployment / 5-Verification]

### Source Skill
[azure-planner / azure-architect / azure-configurator / azure-deployer / azure-verifier]

### Revision Attempt
[1 / 2 / 3]

### Deliverable Summary
[Brief description of what the deliverable contains]

### Upstream Approved Deliverables
[List of prior approved deliverables, or "None — first phase"]

### Known Concerns
[Any issues already noted, or "None identified"]

### Instruction
Execute the gatekeeper review for the specified phase. Apply all review
dimensions and challenge categories from the gatekeeper-azure references.
If Phase 5, also execute the final adversarial sweep across the approved Azure
package before issuing the verdict.
```

---

## Gatekeeper-Azure Findings Routing Template

```markdown
## AZURE-PROVISIONER REVISION REQUEST: [Target Specialist]

### Context
Gatekeeper-azure reviewed the [deliverable name] and issued a REVISE verdict.

### Effective Rewind Point
[Phase N — which phase must be corrected]

### Revision Attempt
[1 / 2 / 3] of 3 maximum

### Mandatory Fixes
[Paste critical and major findings verbatim]

### Advisory Notes
[Paste minor findings]

### Instruction
Address all mandatory fixes and return the revised deliverable to
azure-provisioner for gatekeeper-azure re-review. If this rewind affects
downstream phases, azure-provisioner will replay them after your fix is
approved.
```
