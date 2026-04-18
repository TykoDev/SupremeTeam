# Cross-Pipeline Validation Criteria

> **Save awareness**: When a Run ID is provided in the submission, gatekeeper-admiral may reference persisted deliverables in `skillset-saves/runs/{run-id}/` for cross-pipeline verification. The save path provides direct access to individual phase deliverables and gatekeeper verdicts without requiring the full package to be in context.

## Handoff 1: Design Package -> Build Pipeline

### Required Deliverable Inventory

Check every item. A missing or placeholder deliverable is a CRITICAL finding.

| # | Deliverable | Required | Validation |
|---|------------|----------|------------|
| 1 | Software Requirements Specification (SRS) | Always | Contains functional requirements (FR-XXX) with acceptance criteria, non-functional requirements with measurable thresholds, stakeholder analysis |
| 2 | Domain Analysis | Always | Contains bounded contexts, domain model with entities and relationships, aggregate boundaries |
| 3 | Project Plan | Always | Contains phase breakdown, milestone map with dates/criteria, risk register (RISK-XXX), rollout strategy |
| 4 | Architecture Document (Arc42) | Always | Contains all 12 Arc42 sections, C4 diagrams (Levels 1-3), deployment topology |
| 5 | ADR Collection | Always | At minimum ADR-001 (architecture style selection), MADR v4.0 format, status/context/decision/consequences |
| 6 | API Contracts | Always | OpenAPI 3.1 for REST or AsyncAPI 3.0 for events — complete schemas, not placeholder stubs |
| 7 | Data Model | Always | ERD with entity definitions, field types, relationships, migration strategy |
| 8 | Backend Stack Lock | Always | Exact overlay file from tech-stacks/, version tuple, decision drivers, exceptions with ADR refs |
| 9 | Frontend Architecture Spec | If frontend | Rendering pattern, component system, design tokens, routing, responsive strategy |
| 10 | Frontend Stack Lock | If frontend | Exact overlay file from tech-stacks/, version tuple, rationale |
| 11 | Implementation Specification | Always | Repo structure, .env contract, testing strategy, CI/CD pipeline, Docker config, security controls, observability |
| 12 | Inherited Stack Locks | Always | Record of backend + frontend locks as received by engineer |
| 13 | Gatekeeper-Design Approval Records | Always | One approval per completed phase |

### Implementability Checks

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| API schemas are complete | Every endpoint has request/response schemas with field types, not `object` or `any` | CRITICAL |
| Data model has field definitions | Every entity has named fields with types, constraints, and relationships | CRITICAL |
| Component specs have props | Frontend components define prop interfaces with types | MAJOR |
| Acceptance criteria are testable | FR acceptance criteria use GIVEN/WHEN/THEN or equivalent testable format | MAJOR |
| NFRs have measurable thresholds | Performance, availability, security NFRs include numeric targets | MAJOR |

### Stack Lock Integrity Checks

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| Backend overlay specified | References an exact file from tech-stacks/ (not "to be decided") | CRITICAL |
| Version tuple present | Runtime, framework, database versions are pinned | CRITICAL |
| Frontend overlay specified (if applicable) | References an exact file from tech-stacks/ | CRITICAL |
| Exceptions documented | Any deviations from the overlay have ADR references | MAJOR |

### Internal Consistency Matrix

| Source A | Source B | Check | Severity |
|----------|----------|-------|----------|
| SRS functional requirements | Architecture data model | Same entities, same bounded contexts | CRITICAL |
| SRS API requirements | API contracts | Every required API endpoint exists in contracts | CRITICAL |
| Architecture ADRs | Stack locks | ADR decisions consistent with selected stacks | MAJOR |
| Project plan decision gates | Architecture + implementation readiness | Decision gates reflect actual stack/architecture choices | MAJOR |
| NFR performance targets | Architecture deployment topology | Infrastructure supports stated performance targets | MAJOR |
| Security requirements (SRS) | Implementation spec security controls | Every security requirement has a corresponding control | MAJOR |

---

## Handoff 2: Build Package -> Review Pipeline

### Required Deliverable Inventory

| # | Deliverable | Required | Validation |
|---|------------|----------|------------|
| 1 | Production Code | Always | All modules from the implementation spec are present; no empty files or stub modules |
| 2 | Test Suite | Always | Unit, integration, and E2E tests as specified in implementation spec; tests execute (not just present) |
| 3 | Security Audit Report | Always | Gatekeeper-build-approved; all findings either resolved in code or documented as accepted risk |
| 4 | Completeness Certification | Always | CLEAN verdict from cross-check-build-confirm + gatekeeper-build Phase 4 approval |
| 5 | Gatekeeper-Build Approval Records | Always | One approval per completed phase (Phases 1-4) |

### Design Alignment Checks

| Design Artifact | Implementation Artifact | Check | Severity |
|----------------|------------------------|-------|----------|
| API Contracts (OpenAPI) | Route definitions | Every contract endpoint has a corresponding route handler | CRITICAL |
| Data Model (ERD) | Database schema/ORM models | Every entity in the ERD exists as a model with matching fields | CRITICAL |
| Frontend Component Specs | Component implementations | Key components exist with specified props and state | MAJOR |
| Repo Structure (impl spec) | Actual directory layout | Directory structure follows the implementation specification | MAJOR |
| .env Contract (impl spec) | .env.example file | All required environment variables documented | MAJOR |
| CI/CD Pipeline (impl spec) | CI/CD configuration files | Pipeline stages match the specification | MINOR |
| Backend Stack Lock | package.json / requirements.txt / go.mod | Dependency versions match locked version tuple | CRITICAL |
| Frontend Stack Lock | package.json (frontend) | Frontend dependency versions match locked version tuple | CRITICAL (if frontend) |

### Test Quality Checks

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| Tests are meaningful | Tests assert behavior, not just that code runs without error | MAJOR |
| Critical paths covered | Auth, payment, data mutation paths have dedicated tests | MAJOR |
| No placeholder tests | No `test("todo")`, `it.skip()`, or empty test bodies | MAJOR |
| Test count proportional | Test count is reasonable for the codebase size | MINOR |

### Security Resolution Checks

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| All CRITICAL findings resolved | Security audit CRITICAL items have corresponding code fixes | CRITICAL |
| All MAJOR findings resolved | Security audit MAJOR items have corresponding code fixes or documented acceptance | MAJOR |
| No regressions from remediation | Code changes for security fixes did not introduce new issues | MAJOR |
| Accepted risks documented | Any unresolved findings have explicit risk acceptance with justification | MAJOR |

---

## Handoff 3: Review Package -> Final Delivery

### Required Deliverable Inventory

| # | Deliverable | Required | Validation |
|---|------------|----------|------------|
| 1 | Bug Review Report | Always | Structured defect report with severity classifications |
| 2 | Code Review Assessment | Always | 8-dimension assessment with merge recommendation |
| 3 | Quality Review Report | Always | Quality score, standards enforcement, architecture drift assessment |
| 4 | Security Review Report | Always | Findings mapped to NIST SSDF, OWASP, CWE |
| 5 | Adversarial Analysis Report | Always (standard/high risk) | Exploit chains, CVSS scores, supply chain assessment |
| 6 | Frontend Audit Report | If frontend | Core Web Vitals, WCAG, CSP, component architecture |
| 7 | Gatekeeper-Code Validation Record | Always | Validation of all specialist reports |
| 8 | Cross-Skill Risk Summary | Always | Aggregated risk table across all dimensions |

### Traceability Checks

| Check | How to Verify | Severity |
|-------|--------------|----------|
| Critical requirements reviewed | High-priority SRS requirements trace to code that was reviewed | MAJOR |
| Architecture decisions validated | ADR-driven design choices are covered in code-review or quality-review | MAJOR |
| Security controls verified | Security requirements from SRS have corresponding security-review findings or confirmations | MAJOR |
| No blind spots | All significant modules appear in at least one review report | MAJOR |

### Finding Resolution Checks

| Check | How to Verify | Severity |
|-------|--------------|----------|
| All CRITICAL findings addressed | Every CRITICAL finding has a resolution (fixed, documented, or user-decision-needed) | CRITICAL |
| All HIGH findings addressed | Every HIGH finding has a resolution or explicit deferral with justification | MAJOR |
| Cross-specialist agreement | Overlapping findings from different skills agree on severity | MAJOR |
| No contradictions | Bug-review and security-review do not contradict on the same code path | MAJOR |

### Delivery Completeness Checks

| Check | How to Verify | Severity |
|-------|--------------|----------|
| All three pipeline outputs present | Design Package + Build Package + Review Package all included | CRITICAL |
| All gatekeeper approvals recorded | gatekeeper-design, gatekeeper-build, gatekeeper-code, and gatekeeper-admiral records present | CRITICAL |
| Disputed items documented | Any DISPUTED items from any gatekeeper have both positions and user decisions | MAJOR |
| Executive summary accurate | Summary reflects actual findings, not boilerplate | MINOR |

---

## Handoff 4: Review Package -> Azure Provisioning (When Stage 4 Active)

Validate the approved delivery package is provision-ready.

| # | Check | How to Verify | Severity if Failed |
|---|-------|--------------|-------------------|
| 1 | Infrastructure Alignment | Deployment topology matches architecture spec — container counts, service types, database engine, networking | CRITICAL |
| 2 | Configuration Completeness | Env vars, connection strings, Key Vault refs, RBAC assignments sufficient for azure-provisioner without guessing | MAJOR |
| 3 | Security Posture Continuity | Security findings resolved during review remain resolved in deployment config — no hardcoded secrets, TLS enforced, managed identity used | CRITICAL |
| 4 | Artifact Readiness | Build artifacts (Docker images, compiled output, static assets) referenced by deployment config exist and are accessible | CRITICAL |
| 5 | Rollback Specification | Rollback strategy documented — what to do if health checks fail, which prior version to restore | MAJOR |

---

## Handoff 4: Azure Package -> Final Delivery (when Stage 4 executed)

This handoff validates the Azure Provisioning Package when admiral has executed
Stage 4 (Azure Provision). It is only applicable when the user's request targets
Azure deployment.

### Required Deliverable Inventory

| # | Deliverable | Required | Validation |
|---|------------|----------|------------|
| 1 | Deployment Runbook | Always | Contains resource list, SKU selections, dependencies, deployment order, cost estimation (when reliable data available) or documented omission |
| 2 | Bicep Design | Always | Contains modules, parameters, outputs, naming conventions — valid Azure resource types with current API versions |
| 3 | Configuration Specification | Always | Contains RBAC assignments (least-privilege), secrets catalog, app settings, diagnostic settings |
| 4 | Deployment Report | Always | Contains execution log, deployed resource inventory, health verification results |
| 5 | Verification Report | Always | Contains 8-layer check results for all deployed resources — no unverified resources |
| 6 | Adversary Audit Report | Always | Contains 5 audit domains covering 6 attack surface categories with severity-tiered findings |
| 7 | Pipeline Traceability Record | Always | Contains phase status, revision history, accepted risks, user overrides |
| 8 | Cost Estimation Report | When reliable data available | Source-attributed estimates (Microsoft Learn, Azure Pricing Calculator, Azure MCP) or documented reason for omission |
| 9 | Azure Resource Summary | Always | Contains Resource Group, Subscription, Region, SKU selections, endpoint URLs |
| 10 | Deployment Checklist & Next Actions | Always | Contains post-deployment steps, monitoring setup, DNS/SSL config, backup/DR validation |
| 11 | Gatekeeper-Azure Approval Records | Always | One approval per completed phase (Phases 1-6) |

### Infrastructure Alignment Checks

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| Design architecture matches Azure topology | Architecture deployment topology from Arc42 maps to Azure resources in runbook | CRITICAL |
| Build container images match Azure targets | Container images from Build Package correspond to App Service/Container Apps configuration | CRITICAL |
| Implementation spec env vars match config spec | Every .env variable from implementation spec has a corresponding Azure app setting or Key Vault reference | MAJOR |
| Data model matches Azure storage configuration | ERD entities map to Azure database/storage resources (SQL, Cosmos, Storage) | CRITICAL |
| API contracts match Azure networking | API endpoints are accessible through the configured Azure networking (App Gateway, Front Door, or direct) | MAJOR |
| Stack lock runtimes match Azure SKU capabilities | Selected Azure SKUs support the runtime versions specified in stack locks | CRITICAL |

### Cost & Quota Validation

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| Cost estimate covers major resources | Compute, storage, and networking are included in the estimate | MAJOR |
| Cost estimate has source attribution | Estimates reference Microsoft Learn, Azure Pricing Calculator, or Azure MCP | MAJOR |
| Cost omission is justified | If no estimate for a resource, the reason is documented | MINOR |
| SKU selections are proportional | Dev/test SKUs for dev environments; production SKUs for production | MAJOR |
| Known quota limits documented | vCPU limits, storage account limits, and other quotas are identified | MINOR |

### Deployment Model Compatibility

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| Bicep modules are idempotent | Re-deployment does not create duplicate resources | CRITICAL |
| Deployment order respects dependencies | Resources with dependencies are deployed after their dependents | CRITICAL |
| Health probes configured | All App Service / Container Apps have health probe endpoints | MAJOR |
| Diagnostic settings configured | All supported resources have diagnostic settings writing to a Log Analytics workspace | MAJOR |
| Deployment failure handling documented | Failed deployments have cleanup procedures documented | MAJOR |

### Security & Compliance Coherence

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| RBAC assignments are least-privilege | No Owner assignments where Contributor or custom role suffices | CRITICAL |
| Managed identity preferred | Managed identity used instead of service principals with client secrets | MAJOR |
| Key Vault used for secrets | No secrets in app settings that should be in Key Vault | CRITICAL |
| Network security is restrictive | NSG rules are deny-by-default with explicit allow rules | CRITICAL |
| Security review findings traceable to Azure | Security findings from Review Package have corresponding Azure security controls or documented gaps | MAJOR |
| Final Azure adversarial sweep covers all attack surfaces | Gatekeeper-azure's Phase 5 exit gate assesses all 5 audit domains and 6 Azure attack surface categories | MAJOR |

### Review-to-Azure Coherence

| Check | How to Verify | Severity if Failed |
|-------|--------------|-------------------|
| Security review findings addressed in Azure config | CRITICAL/HIGH security review findings have corresponding Azure security controls | CRITICAL |
| Adversarial findings from review trace to Gatekeeper Azure | Exploit scenarios from code review are covered in the gatekeeper-azure final adversarial sweep | MAJOR |
| Frontend audit findings reflected in Azure CDN/WAF config | If frontier found CSP or performance issues, Azure CDN/WAF config addresses them | MINOR |
| Quality review architecture drift checked | Quality review's architecture drift assessment is consistent with Azure architecture | MAJOR |
