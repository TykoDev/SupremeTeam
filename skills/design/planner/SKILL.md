---
name: planner
description: >-
  This skill should be used when the user or commander asks to "create a project
  plan", "define milestones", "assess risks", "plan the delivery", "create a
  rollout strategy", "estimate effort", "define feature flags strategy",
  "create a risk register", "what's the timeline?", "plan the rollout", or "how should we
  phase this?". Produces a structured project plan with milestones, risk
  register, delivery strategy, and progressive rollout plan based on
  approved requirements.
  DO NOT USE for gathering requirements (use researcher). DO NOT USE
  for system architecture (use architect). DO NOT USE for build
  execution (use build-management).
version: 1.0.0
---

# Planner — Project Planning & Delivery Strategy

## Purpose

Perform Phase 2 of the Dev Design SkillSet pipeline by taking
gatekeeper-design-approved requirements (from researcher) and transforming them
into a structured project plan with milestones, risk register, delivery
strategy, and progressive rollout approach. Drive downstream phases by
establishing scope, sequencing, risk boundaries, and technology decision gates
without prematurely finalizing backend or frontend stack overlays. Do not make
technology stack selections — those belong to architect and designer.

## When to Activate

Activate when commander delegates Phase 2 (Project Planning) after the
researcher's requirements document has been approved by gatekeeper-design, or
when a user directly requests a delivery plan, milestones, rollout strategy,
or risk register for an already understood scope.

Apply the adversarial anti-gaming framework from `../../references/universal-frameworks.md`
to planning outputs. Do not hide uncertainty inside optimistic dates, convert
must-have scope into later phases without approval, or bury external
dependencies inside generic contingency language.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

---

## Execution Modes

### Pipeline Mode (Commander-Delegated)

In pipeline mode delegated by commander, do NOT submit to `gatekeeper-design`
yourself. Produce the deliverable plus a gatekeeper-ready review packet and
return both to commander. Commander owns the review cycle.

### Standalone Mode (Direct User Activation)

When activated directly by a user, this skill owns the final review loop for
its own deliverable. Produce the project plan, submit it to
`gatekeeper-design`, address any REVISE findings, and return the approved
result plus the final review report.

---

## Workflow

### Step 1: Ingest Approved Requirements

Read the gatekeeper-design-approved SRS and domain analysis. Extract:
- Total scope (functional requirements count and complexity)
- Non-functional requirements (performance, security, compliance constraints)
- Domain complexity (number of bounded contexts, integration points)
- Stated constraints (timeline, budget, team size, regulatory deadlines)
- Explicit technology constraints/preferences captured by researcher

### Step 2: Define Project Phases

Break the project into logical delivery phases using this decomposition procedure:

1. **Identify the architectural spine**: Which features require foundational infrastructure (auth, data layer, CI/CD)? These form Phase 1.
2. **Group by value delivery**: Cluster remaining requirements into the smallest groups that each deliver independently deployable user value.
3. **Order by risk × value**: Deliver the most valuable, highest-risk items first because early validation of value and architecture lowers schedule risk.
4. **Apply the dependency graph**: Reorder groups so that each phase's prerequisites are satisfied by prior phases. If circular dependencies exist, break them with feature flags or interface contracts.
5. **Validate independent deployability**: Each phase MUST be independently deployable and valuable because coupled phases negate the schedule and risk benefits of phased delivery. If a phase cannot ship without the next phase, merge them.
6. **Cap phase count**: Prefer 3–6 phases. Fewer than 3 indicates insufficient decomposition; more than 6 indicates over-slicing that adds coordination overhead.

Each phase MUST use this structure because consistent structure enables automated parsing by downstream pipeline skills:

```markdown

---

## Phase [N]: [Phase Name]
**Duration**: [Estimated weeks/sprints]
**Goal**: [What this phase achieves]
**Deliverables**:
  - [Deliverable 1]
  - [Deliverable 2]
**Requirements covered**: [FR-001, FR-002, ...]
**Dependencies**: [Phase N-1 must be complete / External: API ready]
**Exit criteria**: [What must be true to consider this phase done]
```

### Step 3: Create Milestone Map

Define milestones with concrete deliverables and acceptance criteria:

| Milestone | Target Date | Deliverables | Acceptance Criteria |
|-----------|-------------|-------------|---------------------|
| M1: Foundation | Week N | Project scaffolding, CI/CD, DB schema | Pipeline green, schema migrated |
| M2: Core MVP | Week N+X | Core features functional | All MUST requirements passing |
| M3: Integration | Week N+Y | External integrations | Contract tests passing |
| M4: Hardening | Week N+Z | Security, performance, accessibility | NFRs verified |
| M5: Launch | Week N+W | Production deployment | SLOs met for 48 hours |

### Step 4: Build Risk Register

For every identified risk, produce a structured entry scored using the
Probability × Impact matrix below.

**Risk Scoring Matrix:**

| | Impact: Low (1) | Impact: Medium (2) | Impact: High (3) |
|---|---|---|---|
| **Probability: High (3)** | 3 — Medium | 6 — High | 9 — Critical |
| **Probability: Medium (2)** | 2 — Low | 4 — Medium | 6 — High |
| **Probability: Low (1)** | 1 — Low | 2 — Low | 3 — Medium |

**Calibration examples:**
- **Score 9 (Critical)**: Third-party payment API has no sandbox environment, team has never integrated it, and it's on the critical path → Probability High (no prior experience + no test env) × Impact High (blocks launch) = 9.
- **Score 4 (Medium)**: Database migration might take longer than estimated due to data volume uncertainty → Probability Medium (uncertain but bounded) × Impact Medium (delays one phase, not the project) = 4.
- **Score 1 (Low)**: A non-critical UI library might release a breaking update → Probability Low (pinned version) × Impact Low (cosmetic feature, easy to swap) = 1.

Each risk entry MUST use this structure because consistent risk entries enable severity-based prioritization and cross-referencing with the mitigation plan:

```markdown
### RISK-001: [Risk Title]
**Category**: Technical | Schedule | Resource | External | Security
**Probability**: High (3) | Medium (2) | Low (1)
**Impact**: High (3) | Medium (2) | Low (1)
**Risk Score**: [Probability × Impact] — [Critical | High | Medium | Low]
**Description**: [What could go wrong]
**Mitigation**: [Specific, actionable steps to reduce probability or impact]
**Contingency**: [What to do if the risk materializes]
**Owner**: [Who is responsible for monitoring]
**Review cadence**: [How often to reassess]
```

Consult `references/risk-assessment-guide.md` for extended risk scoring guidance,
mitigation patterns, and contingency design.

### Step 5: Define Rollout Strategy

Specify the progressive deployment approach. Consult
`references/project-plan-template.md` for rollout strategy patterns and templates:

1. **Deployment model**: Blue/green, canary, rolling, or feature-flag-based
2. **Feature flag lifecycle**: Deploy OFF → internal team → 5% canary → 
   monitor metrics → 25% → 50% → 100% → remove flag and dead code
3. **Rollback plan**: Conditions that trigger rollback, rollback procedure,
   maximum rollback time
4. **Monitoring gates**: Which metrics must be healthy to proceed at each stage
5. **Communication plan**: Who is notified at each rollout stage

Define rollout prerequisites in terms of approved requirements, architecture
readiness, and known technical constraints. Do not assume a finalized backend
or frontend stack if it has not yet been locked by later phases because the
planner defines deadlines and rollout prerequisites, not downstream technology
choices.

### Step 6: Define Technology Decision Timeline

Map when technology decisions must be finalized:

| Decision | Deadline | Impact if Delayed | Decision Owner |
|----------|----------|-------------------|----------------|
| Runtime selection | Phase 1 start | Blocks all development | Architect |
| Database selection | Phase 1 start | Blocks schema design | Architect |
| Frontend framework | Phase 1 | Blocks UI development | Designer |
| CI/CD platform | Phase 1 | Blocks pipeline setup | Engineer |
| Hosting/deployment | Phase 2 | Blocks staging environment | Engineer |

Make the distinction explicit:
- The planner defines decision deadlines, rollout prerequisites, and risk impact
- The planner does NOT finalize backend/runtime or frontend overlay selection

If a required technology decision is still open when its deadline arrives,
escalate it as a planning risk immediately. Document the blocked milestone,
the downstream impact, the owner, and the contingency plan rather than hiding
the delay inside a later phase.

### Step 7: Prepare Review Handoff

Package the complete project plan with a review packet containing:
- Source skill: `planner`
- Deliverable produced
- Approved upstream context used
- Explicit tech constraints/preferences carried forward from research
- Decision gates and rollout prerequisites called out in the plan

If operating in pipeline mode, return the deliverable and review packet to
commander for gatekeeper submission.

If operating in standalone mode, submit the deliverable and review packet to
`gatekeeper-design`, address any REVISE findings, and resubmit until APPROVED.

---

## Output Format

The planner produces one consolidated deliverable:

**Project Plan** containing:
1. Phase breakdown with scope mapping
2. Milestone map with dates and acceptance criteria
3. Risk register with mitigations
4. Dependency graph
5. Rollout strategy with feature flag lifecycle
6. Technology decision timeline
7. Resource assumptions
8. Explicit technology constraints and rollout prerequisites

In pipeline mode, return the deliverable with a gatekeeper-ready review packet.

In standalone mode, return the approved deliverable plus the final
gatekeeper-design review report.

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| Requirements are still evolving during planning | Plan in phases with explicit decision gates. Mark volatile requirements as "subject to change" and build flexibility into the milestone map. Avoid hard commitments on uncertain features. |
| Technology decisions have not been finalized | Plan around the decision timeline. Identify which milestones depend on specific technology choices and when those decisions must be made. Do not assume a stack. |
| Team capacity is unknown | Document resource assumptions explicitly. Plan milestones with time ranges rather than fixed dates. Flag capacity as a High risk in the risk register. |
| Dependencies on external teams or services | Track as explicit risks with mitigation plans. Identify the critical path and which external dependencies are on it. Build buffer time for external dependencies. |
| External dependency misses a committed milestone | Re-score the risk immediately, update the milestone plan with the new critical-path impact, and surface the revised contingency instead of silently absorbing the slip. |
| Prior estimates proved wildly inaccurate | Use relative sizing (story points, T-shirt sizes) rather than absolute time estimates. Build in explicit contingency (15-25% buffer). Track estimation accuracy as a project metric. |
| Scope creep detected during planning | Compare current scope against the SRS. Any feature not in the requirements is scope creep. Document it, get explicit user approval, and adjust the timeline. |
| Milestone slip discovered during phase execution | Re-score affected risks, recalculate the critical path, and surface the revised timeline to commander with options (reduce scope, extend deadline, add resources). Do not silently absorb the slip because hidden delays compound downstream. |

---

## Additional Resources

### Reference Files

For detailed templates and risk patterns:
- **`references/project-plan-template.md`** — Full project plan template, rollout strategy patterns, and estimation guidance
- **`references/risk-assessment-guide.md`** — Risk categories, scoring matrix, mitigation patterns, and contingency guidance

---

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: design
   phase: 2
   skill: planner
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. Write the review packet as `review-packet.md` in the same save path directory

3. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
