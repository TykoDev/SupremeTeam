# Review Criteria Reference — Gatekeeper Azure

## Per-Phase Review Checklists

### Phase 1: azure-planner Output (Deployment Runbook)

#### Azure Alignment Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Service coverage | Every Azure service requested by the user appears in the runbook's resource list |
| 2 | Environment matching | The runbook targets the correct Azure environment |
| 3 | Region selection | The target region is specified and justified |
| 4 | Subscription targeting | The correct subscription and resource-group strategy are documented |

#### Infrastructure Correctness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | SKU validity | Proposed SKUs exist for the target resource types in the selected region |
| 2 | Tier matching | SKU tiers match the workload class |
| 3 | Service availability | Proposed services are available in the target region |
| 4 | Quota awareness | Relevant quota limits or capacity constraints are documented |

#### Cost Proportionality Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Estimate source | Cost estimates cite a reliable source or the omission is justified |
| 2 | Estimate scope | Major cost drivers are covered |
| 3 | Estimate assumptions | Region, SKU, quantity, and usage assumptions are explicit |
| 4 | No unreliable estimates | Unknown or unreliable pricing is omitted with explanation |

#### Documentation Quality Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Actionability | The runbook gives azure-architect enough detail to proceed without guessing |
| 2 | Decision record | Key Azure decisions include rationale |
| 3 | Dependency mapping | Resource and stage dependencies are documented |
| 4 | Risk documentation | Known risks and constraints are called out |

---

### Phase 2: azure-architect Output (Bicep Design)

#### Infrastructure Correctness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | API version currency | Bicep uses current, supported API versions |
| 2 | Resource provider validity | All resource types reference valid Azure providers |
| 3 | Property validity | Resource properties match the selected API versions |
| 4 | Module composition | Modules follow the repo's Bicep and naming references |
| 5 | Parameter typing | Parameters have correct types and safe defaults |
| 6 | Output completeness | Downstream phases get the outputs they need |

#### Naming & Conventions Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Naming compliance | Names follow Azure length, character, and uniqueness rules |
| 2 | Convention consistency | Naming matches the documented project convention |
| 3 | Prefix/suffix consistency | Environment and resource-type markers are applied consistently |

#### Downstream Feasibility Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Configurator sufficiency | Outputs include IDs, endpoints, and names needed by configuration |
| 2 | Deployer sufficiency | Module boundaries support deployment orchestration cleanly |
| 3 | Verifier sufficiency | Resource inventory is clear enough for verification targeting |

---

### Phase 3: azure-configurator Output (Configuration Spec)

#### Security & Compliance Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Least-privilege RBAC | No over-privileged role assignments |
| 2 | Managed identity usage | Managed identity is preferred over secret-based principals where feasible |
| 3 | Key Vault references | Secrets live in Key Vault or equivalent secure storage |
| 4 | Network security | Network rules are restrictive and intentional |
| 5 | Private access posture | Private endpoints or equivalent controls are used when warranted |
| 6 | TLS enforcement | Supported services enforce TLS 1.2+ |

#### Completeness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | App settings | All required settings are listed with values or secure references |
| 2 | Connection strings | Service-to-service connections are accounted for |
| 3 | Secrets catalog | Secrets are listed with storage location and ownership |
| 4 | Diagnostic settings | Observability configuration is included where supported |
| 5 | Tags | Tagging strategy is defined for ownership, environment, and cost |

#### Cost Proportionality Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | SKU confirmation | Final SKUs remain proportional to the workload |
| 2 | Savings options | Reserved capacity or savings opportunities are considered where relevant |
| 3 | No over-provisioning | Config choices do not materially overshoot requirements |

---

### Phase 4: azure-deployer Output (Deployment Report)

#### Operational Readiness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Idempotency | Re-running does not create duplicate resources or broken state |
| 2 | Health probes | Health endpoints are documented and responding |
| 3 | Diagnostic logging | Diagnostics are enabled and writing to the intended destination |
| 4 | Startup verification | Applications start successfully on the deployed infrastructure |
| 5 | Cleanup on failure | Failed or partial deployments do not leave dangerous or expensive residue |

#### Upstream Coherence Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Resource match | Deployed resources match the Bicep design |
| 2 | SKU match | Deployed SKUs match the approved architecture |
| 3 | Configuration match | Runtime settings align with the configuration spec |
| 4 | Failure documentation | Any failures include root cause and remediation |

---

### Phase 5: azure-verifier Output (Verification Report)

#### Accuracy Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Endpoint reachability | Endpoint URLs are reachable and return expected responses |
| 2 | Configuration verification | Spot-checks confirm runtime settings match the configuration spec |
| 3 | RBAC verification | Role assignments match the configuration spec |
| 4 | Network verification | Network controls match the intended design |
| 5 | Diagnostic verification | Diagnostics are active and capturing expected data |

#### Completeness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Full coverage | Every deployed resource has at least one verification check |
| 2 | Layer coverage | All verifier layers are addressed |
| 3 | Pass/fail clarity | Each check has a clear result |
| 4 | Evidence | Evidence is attached for each check |

#### Upstream Coherence Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Design alignment | Verified resources match the architect's design |
| 2 | Config alignment | Verified settings match the configurator's spec |
| 3 | Deploy alignment | Verified runtime matches the deployer's report |

#### Final Adversarial Sweep Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Audit-domain coverage | Architecture, configuration, deployment, verification fidelity, and overall security posture are challenged |
| 2 | Attack-surface coverage | Network, identity, secrets, containers, data, and deployment process are assessed |
| 3 | False-positive detection | Verification claims are challenged for blind spots and weak evidence |
| 4 | Cross-phase consistency | Earlier Azure phases remain coherent under adversarial review |
| 5 | Severity calibration | Security and operational findings are proportionate to exploitability and blast radius |
| 6 | No blind spots | No major deployed surface is left entirely unchallenged |
