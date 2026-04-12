# Commander Handoff Templates

> **Placeholder notation**: Square-bracket tokens in this file are template
> placeholders to be replaced during delegation construction. The authoritative
> persisted-path format in `save-protocol.md` uses brace variables such as
> `{run-id}`.

## Phase 1 Delegation: researcher

```markdown
## COMMANDER DELEGATION: Phase 1 — Requirements & Domain Analysis

### Execution Mode
Pipeline mode delegated by commander. Do NOT submit to `gatekeeper-design`
yourself. Return deliverables plus a review packet to commander.

### Original User Request
[Paste user's project description verbatim]

### Identified Constraints
- **Timeline**: [Specified or "Not specified"]
- **Team size**: [Specified or "Not specified"]
- **Budget**: [Specified or "Not specified"]
- **Regulatory**: [Specified or "None identified"]
- **Technical constraints/preferences**: [Specified or "None identified"]
- **Existing systems**: [Specified or "Greenfield project"]

### Scope Classification
[Full system design / Feature design / Component design]

### Commander Notes
[Any additional context, clarifications from user intake, or assumptions made]

### Expected Deliverables
1. Software Requirements Specification (SRS) following `references/requirements-template.md`
2. Domain Analysis with bounded contexts and domain model

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/design/phase-1_researcher/
- **Persistence active**: [yes/no]

### Return Contract
Return the completed deliverables plus a review packet containing:
- Source skill: `researcher`
- Deliverables list
- Hard user technology constraints/preferences captured in the SRS
- Open questions and assumptions
```

---

## Phase 2 Delegation: planner

```markdown
## COMMANDER DELEGATION: Phase 2 — Project Planning & Delivery Strategy

### Execution Mode
Pipeline mode delegated by commander. Do NOT submit to `gatekeeper-design`
yourself. Return deliverables plus a review packet to commander.

### Original User Request
[Paste user's project description verbatim]

### Approved Upstream Deliverables
- ✅ SRS (from researcher, gatekeeper-design-approved)
- ✅ Domain Analysis (from researcher, gatekeeper-design-approved)

### Key Requirements Summary
- Total functional requirements: [count]
- MUST-priority items: [count]
- Key NFRs: [list critical ones]
- Bounded contexts: [count]
- User technology constraints/preferences: [summary]

### Commander Notes
[Any timeline pressure, phasing preferences, or risk areas to prioritize]

### Expected Deliverables
1. Project Plan with phase breakdown and milestones
2. Risk register with mitigations
3. Rollout strategy with feature flag lifecycle
4. Technology decision timeline and rollout prerequisites

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/design/phase-2_planner/
- **Persistence active**: [yes/no]

### Return Contract
Return the completed deliverable plus a review packet containing:
- Source skill: `planner`
- Deliverables list
- Explicit technology constraints/preferences carried forward
- Technology decision gates and rollout prerequisites
```

---

## Phase 3 Delegation: architect

```markdown
## COMMANDER DELEGATION: Phase 3 — System Architecture

### Execution Mode
Pipeline mode delegated by commander. Do NOT submit to `gatekeeper-design`
yourself. Return deliverables plus a review packet to commander.

### Original User Request
[Paste user's project description verbatim]

### Approved Upstream Deliverables
- ✅ SRS (from researcher)
- ✅ Domain Analysis (from researcher)
- ✅ Project Plan (from planner)

### Key Architecture Drivers
- Primary quality attributes: [from SRS NFRs]
- Domain complexity: [number of bounded contexts]
- Scale requirements: [from NFRs]
- Integration points: [from SRS external interfaces]
- Team constraints: [from planner]
- User technology constraints/preferences: [summary]

### Backend Overlay Library
Select exactly one backend/runtime overlay from the sibling skills-root
`tech-stacks/` folder. The architect should load the matching overlay file from
its own skill context.
- `node-typescript.md`
- `bun-typescript.md`
- `deno-typescript.md`
- `python-fastapi.md`
- `rust-axum.md`
- `go-gin.md`
- `dotnet-aspnet.md`

### Expected Deliverables
1. Arc42 Architecture Document with C4 diagrams (Mermaid)
2. Architecture Decision Records (ADRs) for significant decisions
3. API Contracts (OpenAPI/AsyncAPI specifications)
4. Data Model (ERD with entity definitions)
5. Backend Stack Lock with exact overlay file, version tuple, and justified deviations

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/design/phase-3_architect/
- **Persistence active**: [yes/no]

### Return Contract
Return the completed deliverables plus a review packet containing:
- Source skill: `architect`
- Deliverables list
- Backend Stack Lock summary
- Exceptions or ADR-backed deviations
```

---

## Phase 4 Delegation: designer

```markdown
## COMMANDER DELEGATION: Phase 4 — Frontend Architecture & UI/UX

### Execution Mode
Pipeline mode delegated by commander. Do NOT submit to `gatekeeper-design`
yourself. Return deliverables plus a review packet to commander.

### Original User Request
[Paste user's project description verbatim]

### Approved Upstream Deliverables
- ✅ SRS (from researcher)
- ✅ Architecture Document (from architect)
- ✅ API Contracts (from architect)
- ✅ Backend Stack Lock (from architect)

### Frontend Requirements
- SEO requirements: [Critical / Not important]
- Target devices: [Desktop / Mobile / Both]
- Accessibility level: [WCAG 2.2 AA / custom]
- Performance targets: [from SRS NFRs]
- Framework preference: [if user specified]

### Frontend Overlay Library
Select exactly one frontend overlay from the sibling skills-root `tech-stacks/`
folder. The designer should load the matching overlay file from its own skill
context.
- `react-nextjs.md`
- `react-tanstack.md`
- `vue-nuxt.md`
- `angular.md`
- `astro.md`
- `vite-spa.md`
- `svelte-sveltekit.md`

### Architecture Context
- Rendering approach recommended by architect: [SSR/SPA/SSG/Islands]
- Backend API protocol: [REST/GraphQL/tRPC/gRPC]
- Auth flow: [from architecture document]
- Backend Stack Lock: [exact overlay file and version tuple]

### Expected Deliverables
1. Frontend Architecture Specification
2. Frontend Stack Lock with exact overlay file, version tuple, and justified deviations
3. Component hierarchy and design system spec
4. State management strategy
5. Accessibility requirements
6. Performance targets

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/design/phase-4_designer/
- **Persistence active**: [yes/no]

### Return Contract
Return the completed deliverable plus a review packet containing:
- Source skill: `designer`
- Deliverables list
- Frontend Stack Lock summary
- Alignment notes for backend stack lock and API contracts
- Exceptions or justified deviations
```

---

## Phase 5 Delegation: engineer

```markdown
## COMMANDER DELEGATION: Phase 5 — Implementation Specification

### Execution Mode
Pipeline mode delegated by commander. Do NOT submit to `gatekeeper-design`
yourself. Return deliverables plus a review packet to commander.

### Original User Request
[Paste user's project description verbatim]

### Approved Upstream Deliverables
- ✅ SRS (from researcher)
- ✅ Project Plan (from planner)
- ✅ Architecture Document (from architect)
- ✅ API Contracts (from architect)
- ✅ ADRs (from architect)
- ✅ Backend Stack Lock (from architect)
- ✅ Frontend Spec (from designer) [if applicable]
- ✅ Frontend Stack Lock (from designer) [if applicable]

### Architecture Decisions Summary
- Architecture style: [from ADR-001]
- Runtime: [from Backend Stack Lock]
- Framework: [from stack lock]
- Database: [from ADR / Backend Stack Lock]
- ORM: [from ADR]

### Locked Overlays
- Backend: [exact overlay file from architect]
- Frontend: [exact overlay file from designer or N/A]
- Exceptions: [list or "None"]

### Expected Deliverables
1. Inherited Stack Locks record with exact overlay filenames, version tuples, and deviations
2. Repository structure (complete directory layout)
3. Environment variable contract (.env specification)
4. Testing strategy (tools, levels, coverage targets)
5. CI/CD pipeline specification
6. Docker/containerization configuration
7. Security controls (OWASP mapping)
8. Observability configuration (OpenTelemetry)
9. Code quality tooling

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/design/phase-5_engineer/
- **Persistence active**: [yes/no]

### Return Contract
Return the completed deliverable plus a review packet containing:
- Source skill: `engineer`
- Deliverables list
- Inherited Stack Locks summary
- Any ADR-backed deviations or unresolved exceptions
```

---

## Gatekeeper-Design Submission Template

```markdown
## GATEKEEPER-DESIGN REVIEW REQUEST

### Review Mode
Pipeline mode — commander-owned review cycle

### Phase
[Phase number and name]

### Source Skill
[researcher / planner / architect / designer / engineer]

### Deliverable(s)
[List all documents being submitted]

### Upstream Context
[What approved deliverables informed this work]

### Stack-Lock Registry
- User technology constraints/preferences: [summary]
- Backend Stack Lock: [exact overlay file / N/A]
- Frontend Stack Lock: [exact overlay file / N/A]
- Exceptions: [None or listed]

### Review Request
Execute full adversarial review per gatekeeper-design protocol.
Validate against `review-criteria.md` for this deliverable type.
Cross-check against upstream approved deliverables for consistency and stack-lock lineage.
```

---

## Final Delivery Template

```markdown
# DESIGN SPECIFICATION PACKAGE
## [Project Name]

**Prepared by**: Dev Design SkillSet Pipeline
**Date**: [YYYY-MM-DD]
**Status**: Complete — All required phases gatekeeper-design-approved

---

## Executive Summary
[One paragraph: what was designed, key decisions, recommended approach]

## Package Contents

| # | Deliverable | Source | Gatekeeper-Design Status |
|---|------------|--------|-------------------|
| 1 | Software Requirements Specification | researcher | ✅ APPROVED |
| 2 | Domain Analysis | researcher | ✅ APPROVED |
| 3 | Project Plan | planner | ✅ APPROVED |
| 4 | Architecture Document (Arc42) | architect | ✅ APPROVED |
| 5 | Backend Stack Lock | architect | ✅ APPROVED |
| 6 | API Contracts | architect | ✅ APPROVED |
| 7 | ADR Collection | architect | ✅ APPROVED |
| 8 | Frontend Architecture Spec | designer | ✅ APPROVED |
| 9 | Frontend Stack Lock | designer | ✅ APPROVED |
| 10 | Implementation Specification | engineer | ✅ APPROVED |
| 11 | Inherited Stack Locks | engineer | ✅ APPROVED |

## Stack Lock Summary

| Layer | Locked Overlay | Version Tuple | Notes |
|-------|----------------|---------------|-------|
| Backend | [e.g. `node-typescript.md`] | [e.g. Node.js 22 + Fastify 5 + PostgreSQL 16 + Zod 4] | [Brief rationale / exceptions] |
| Frontend | [e.g. `react-nextjs.md`] | [e.g. Node.js 22 + Next.js 15 + React 19 + TanStack Query 5] | [Brief rationale / exceptions] |

## Recommended Next Actions

1. [First action to take when beginning implementation]
2. [Second action]
3. [Third action]

## Open Questions / Deferred Decisions
[Any items that require further discussion or were deferred]
```
