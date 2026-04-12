# Challenge Protocol Reference — Gatekeeper Azure

## Challenge Framework

Gatekeeper-azure applies five challenge categories across ten review
dimensions. For Phase 5, these challenges cover both the verifier's report and
the final adversarial sweep across all approved Azure deliverables.

---

## Challenge Category 1: Existence

### Definition

Verify that claimed resources, configurations, checks, and references actually
exist in the deliverable set.

### Trigger Conditions

- The runbook lists resources that should appear in Bicep
- The configuration spec references settings or secrets that should exist
- The deployment report claims resources were provisioned
- The verification report claims checks were executed
- The final adversarial sweep cites attack surfaces or weaknesses that must map
  to real resources or configuration paths

### Application by Phase

**Phase 1 (azure-planner — runbook):**

| Dimension | Existence Check |
|-----------|----------------|
| Azure Alignment | Verify each requested service appears in the runbook |
| Completeness | Verify supporting resources are included where needed |
| Documentation Quality | Verify the runbook names concrete resource types and SKUs |

**Phase 2 (azure-architect — Bicep design):**

| Dimension | Existence Check |
|-----------|----------------|
| Infrastructure Correctness | Verify each module targets a valid provider and API version |
| Naming | Verify each resource name is structurally valid |
| Downstream Feasibility | Verify outputs expose downstream-needed values |

**Phase 3 (azure-configurator — config spec):**

| Dimension | Existence Check |
|-----------|----------------|
| Security & Compliance | Verify role definitions and identities actually exist |
| Completeness | Verify required settings, secrets, and connection strings are present |
| Cost Proportionality | Verify SKU selections are explicit when they affect configuration |

**Phase 4 (azure-deployer — deploy report):**

| Dimension | Existence Check |
|-----------|----------------|
| Operational Readiness | Verify probes, diagnostics, and resource inventory are documented |
| Upstream Coherence | Verify deployed resources map back to the architecture |

**Phase 5 (azure-verifier + final adversarial sweep):**

| Dimension | Existence Check |
|-----------|----------------|
| Accuracy | Verify each verification check references a specific deployed resource |
| Completeness | Verify all deployed resources have verification coverage |
| Security & Compliance | Verify the adversarial sweep maps findings to real Azure surfaces |
| Completeness | Verify all audit domains and attack surfaces were challenged |

### Example Challenge (Phase 2)

```text
CHALLENGE: Existence
Target: azure-architect — Phase 2 Bicep Design
Finding: The design claims to include Application Insights, but no resource
         or module defines Microsoft.Insights/components.
Question: Where is the Application Insights resource defined?
Evidence Required: The module or inline resource that creates it.
```

### Example Challenge (Phase 5)

```text
CHALLENGE: Existence
Target: azure-verifier — Phase 5 Verification + Final Adversarial Sweep
Finding: The gate claims the deployment process attack surface was reviewed,
         but no state-file, migration, or deployment-script evidence appears
         in the verifier package.
Question: What evidence shows the deployment-process surface was actually
          challenged?
Evidence Required: The artifacts or notes that demonstrate review of state,
                   migration, or deployment automation risk.
```

---

## Challenge Category 2: Accuracy

### Definition

Verify that SKUs, API versions, RBAC assignments, security claims, and verdicts
are technically correct.

### Application by Phase

**Phase 1 (azure-planner):**

| Dimension | Accuracy Check |
|-----------|---------------|
| Infrastructure Correctness | Verify proposed SKUs exist in the selected region |
| Cost Proportionality | Verify estimates cite reliable pricing sources |

**Phase 2 (azure-architect):**

| Dimension | Accuracy Check |
|-----------|---------------|
| Infrastructure Correctness | Verify API versions are current and properties are valid |
| Naming | Verify names comply with Azure constraints |

**Phase 3 (azure-configurator):**

| Dimension | Accuracy Check |
|-----------|---------------|
| Security & Compliance | Verify RBAC grants least privilege |
| Security & Compliance | Verify secret-handling choices are appropriate |

**Phase 4 (azure-deployer):**

| Dimension | Accuracy Check |
|-----------|---------------|
| Operational Readiness | Verify idempotent execution and credible rollback claims |
| Upstream Coherence | Verify deployed SKUs and settings match approved specs |

**Phase 5 (azure-verifier + final adversarial sweep):**

| Dimension | Accuracy Check |
|-----------|---------------|
| Accuracy | Verify endpoints, checks, and evidence are trustworthy |
| Upstream Coherence | Verify runtime matches design intent |
| Security & Compliance | Verify adversarial findings map to real Azure risks, not generic theory |
| Proportionality | Verify severity reflects actual exploitability and blast radius |

### Example Challenge (Phase 3)

```text
CHALLENGE: Accuracy
Target: azure-configurator — Phase 3 Configuration Spec
Finding: The spec assigns Owner to the application's managed identity.
Question: What concrete operation requires Owner instead of Contributor or
          a narrower custom role?
Evidence Required: A least-privilege justification or a corrected assignment.
```

---

## Challenge Category 3: Completeness

### Definition

Verify that the deliverable covers the full Azure scope without hidden gaps.

### Application by Phase

- **Phase 1**: Are all requested services and support resources included?
- **Phase 2**: Does Bicep include every planned resource and enough outputs?
- **Phase 3**: Are all settings, secrets, tags, and RBAC assignments covered?
- **Phase 4**: Does the deployment report cover all resources and failures?
- **Phase 5**: Are all deployed resources verified, and does the final sweep
  challenge every major attack surface?

### Example Challenge (Phase 1)

```text
CHALLENGE: Completeness
Target: azure-planner — Phase 1 Deployment Runbook
Finding: The runbook includes App Service and PostgreSQL but omits
         diagnostic settings and log routing.
Question: How will operators observe runtime failures or audit access?
Evidence Required: Added observability resources or explicit justification
                   for omission.
```

---

## Challenge Category 4: Proportionality

### Definition

Verify that resource choices, permission scopes, and severity ratings are
calibrated to the real workload and risk.

### Application Across Phases

| Phase | Proportionality Check |
|-------|----------------------|
| 1 | SKU selection matches workload tier |
| 2 | Availability and redundancy match SLA requirements |
| 3 | RBAC and network controls are not broader than necessary |
| 4 | Deployment approach matches the complexity and blast radius |
| 5 | Verification depth and adversarial severity match criticality and exposure |

### Example Challenge (Phase 5)

```text
CHALLENGE: Proportionality
Target: azure-verifier — Phase 5 Verification + Final Adversarial Sweep
Finding: A public blob container serving only public marketing assets is
         flagged as Critical without evidence of sensitive data exposure.
Question: Does the actual blast radius justify Critical severity?
Evidence Required: Proof of sensitive content or a corrected severity rating.
```

---

## Challenge Category 5: Consistency

### Definition

Verify coherence within each deliverable and across the approved Azure package.

### Cross-Phase Consistency Checks

| Upstream Phase | Downstream Phase | Consistency Check |
|---------------|-----------------|-------------------|
| Planning | Architecture | Every runbook resource has a corresponding design artifact |
| Architecture | Configuration | Every required Bicep output is available to configuration |
| Configuration | Deployment | Deployed identities, secrets, and settings match the spec |
| Deployment | Verification | Every deployed resource has verification coverage |
| Verification | Final sweep | Final adversarial findings reference the real approved package |

### Intra-Deliverable Consistency

- Parameter types match their Bicep usage
- RBAC assignments reference real identities
- Cost estimates align with architecture decisions
- Verification status aligns with the evidence provided
- Final adversarial findings do not contradict verified facts without evidence

### Example Challenge (Cross-Phase)

```text
CHALLENGE: Consistency
Target: azure-configurator — Phase 3 Configuration Spec
Finding: The config spec references a user-assigned identity for Key Vault,
         but the Bicep design uses only a system-assigned App Service identity.
Question: Which identity actually accesses Key Vault?
Evidence Required: Reconciled config or amended architecture output.
```
