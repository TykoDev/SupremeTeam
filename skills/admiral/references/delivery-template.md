# Unified Delivery Package Template

## Package Template

Use this template when compiling the final delivery package after all active
stages are gatekeeper-admiral-approved.

```markdown
# UNIFIED DELIVERY PACKAGE: [Project Name]

## Executive Summary
[One paragraph summarizing what was designed, built, and reviewed]

## Context Status
- **Degradation tier**: [Tier 1: Normal / Tier 2: Save-Degraded / Tier 3: Context-Pressured / Tier 4: Double-Degraded]
- **Artifact mode**: [All inline / Mixed (some referenced) / All referenced]
- **Save status**: [Active / Failed — {reason}]
- **Referenced artifacts**: [List of artifacts passed by reference during the pipeline, with save paths, or "None — all artifacts were inline"]
- **Skipped or external upstream stages**: [None or list of `{pipeline}/_skip-record.md` and `admiral/standalone-context.md` references]
- **Traceability status**: [Verified / Mixed / Unverified]

[If Tier 2+]: **Degradation Notice**: [Tier-appropriate warning from save-protocol.md §Degradation Tiers — e.g., "Pipeline persistence was unavailable during this run. Artifacts were carried in-context only." or "Some artifacts were passed by reference due to context pressure. Full artifacts are available at the save paths listed above."]
[If Tier 3+]: **Reference-Mode Notice**: [Inline summaries were non-authoritative. Exact schema, evidence, and traceability validation required opening the referenced artifacts.]
[If Tier 4 or any skipped/external stage]: **Reliability Notice**: [Some delivery claims remain `UNVERIFIED` because persistence, full artifact fidelity, or upstream gatekeeper validation was unavailable. These limitations are listed explicitly below.]

## Package Contents
1. Design Package (from commander)
   - SRS, Domain Analysis, Project Plan, Architecture (Arc42 + C4)
   - ADRs, API Contracts, Stack Locks, Implementation Spec
2. Build Package (from build-management)
   - Production Code, Test Suite, Security Audit, Completeness Cert
3. Review Package (from code-chief)
   - Bug, Code, Quality, Security, Adversarial, Frontend Reports
4. Azure Provisioning Package (from azure-provisioner, if Stage 4 executed)
   - Deployment Runbook, Bicep Design, Config Spec, Deploy Report
   - Verification Report, Adversary Audit, Pipeline Record, Cost Estimation
5. Gatekeeper-Admiral Validation Records
5. Cross-Pipeline Traceability Matrix
6. Admiral Pipeline Record (traceability audit trail)

## Cross-Pipeline Traceability
| Requirement | Architecture Decision | Implementation | Review Findings | Azure Resource |
|-------------|----------------------|----------------|-----------------|----------------|
| [FR-001]    | [ADR-001]           | [module/file]  | [finding refs]  | [resource type/name or N/A] |

## Stack Lock Summary
- Backend: [overlay file + version tuple]
- Frontend: [overlay file + version tuple or N/A]
- Exceptions: [None or listed with ADR references]

## Disputed Items
[Any items where gatekeepers and sub-orchestrators could not agree —
both positions documented with user decisions recorded, or "None"]

## Recommended Next Actions
[Prioritized list of deployment steps or remaining items]
```

---

## Cross-Pipeline Consistency Check

Before final handover, verify end-to-end consistency across all pipeline
outputs. Every check must be marked `PASS`, `N/A`, `UNVERIFIED`, or `BLOCKING`.

### Verification Status Meanings

- **PASS**: verified against authoritative artifacts
- **N/A**: intentionally not applicable because the stage was skipped or not required
- **UNVERIFIED**: the check could not be completed with full confidence because the upstream source was external, summarized, or degraded
- **BLOCKING**: a material inconsistency that prevents delivery until resolved

### Alignment Checks

| From | To | Verification | Status |
|------|----|-------------|--------|
| SRS functional requirements | Architecture data model | Same entities, same bounded contexts, no orphaned requirements | [PASS/N/A/UNVERIFIED/BLOCKING] |
| SRS API requirements | API contracts | Every required endpoint exists with complete schemas | [PASS/N/A/UNVERIFIED/BLOCKING] |
| API contracts | Implemented route handlers | Every contract endpoint has a matching route | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Architecture ERD | Database models / ORM | Every entity has a matching model with correct fields | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Architecture ADRs | Stack locks | ADR decisions consistent with selected stacks | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Stack locks | Dependency files (package.json, etc.) | Locked versions match actual dependency versions | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Frontend component specs | Implemented components | Key components exist with specified props and state | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Implementation spec repo structure | Actual directory layout | Directory structure follows the specification | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Security requirements (SRS) | Security controls (impl spec) | Every requirement has a corresponding control | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Security controls | Security review findings | Controls verified or gaps identified | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Review findings (critical/high) | Resolution status | All critical/high findings addressed or documented for user decision | [PASS/N/A/UNVERIFIED/BLOCKING] |

**Azure Alignment Checks (when Stage 4 executed):**

| From | To | Verification | Status |
|------|----|-------------|--------|
| Architecture deployment requirements | Azure runbook resource list | Every deployment-relevant architecture requirement has a corresponding Azure resource | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Build Package container images | Azure deployer target resources | Container images match App Service/Container Apps configuration | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Review security findings | Gatekeeper Azure final adversarial sweep | Security review findings traceable to Azure gatekeeper adversarial findings (or documented as not applicable to Azure) | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Design Package tech stack | Azure SKU selections | SKU tiers match the workload class defined in the design spec | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Implementation spec environment variables | Azure config spec app settings | Every required env var has a corresponding app setting or Key Vault reference | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Architecture data model | Azure storage configuration | Database/storage resources match the data model requirements | [PASS/N/A/UNVERIFIED/BLOCKING] |
| Cost estimation | Azure runbook scope | All major resources in the runbook are covered by the cost estimate (or omission is documented) | [PASS/N/A/UNVERIFIED/BLOCKING] |

### Traceability Checks

For at least 3 high-priority requirements, trace the full path:

```
FR-XXX (SRS) → ADR-XXX (Architecture) → [module/file] (Build) → [finding] (Review)
```

Confirm that:
- The requirement was not lost or diluted through the pipeline
- The architecture decision supports the requirement
- The implementation matches the architecture
- The review covered the implemented code
- If any upstream stage was skipped, user-supplied, or produced during Tier 4, mark the affected trace as `UNVERIFIED` rather than implying full continuity

### Gap Documentation

If any consistency check fails:
1. Document the gap with specific references to both sides
2. Classify as BLOCKING (prevents delivery), ADVISORY (documented risk), or UNVERIFIED (insufficient authoritative evidence)
3. For BLOCKING gaps: return to the relevant sub-orchestrator for remediation
4. For ADVISORY gaps: include in the Disputed Items section of the delivery package
5. For UNVERIFIED gaps: cite the precise degradation, skip record, or standalone fallback source that prevented full verification

---

## Persistent Save — Final Delivery

After the delivery package is compiled and presented to the user, persist the final state:

1. **Write** `admiral/delivery-package.md` — the complete Unified Delivery Package
2. **Update** `_state.md` — set `admiral_state` to `DELIVERED` and update `snapshot_time`
3. **Update** `_run-manifest.md` — set all active stage states to their final values (DELIVERED or SKIPPED)
4. **Update** `_index.md` — change the run's status to `DELIVERED` and update `last_activity` timestamp
5. **Update** `_latest.md` — set `active_run_id` to `"none"` and `pipeline_state` to `DELIVERED`
6. **Append** to `_audit-trail.md` — final entry: "Pipeline DELIVERED — Unified Delivery Package presented to user"

All paths are relative to `skillset-saves/runs/{run-id}/`. If persistence is not active, skip all save operations.
