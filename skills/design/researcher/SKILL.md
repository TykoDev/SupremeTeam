---
name: researcher
description: >-
  This skill should be used when the user or commander asks to "gather
  requirements", "analyze the domain", "create an SRS", "identify stakeholders",
  "define non-functional requirements", "map bounded contexts", "conduct
  requirements engineering", "research the problem space", "what do we
   need to build?", "define the scope", "what are the requirements?", or directly asks for requirements
   gathering or domain modeling for a new software project. Performs comprehensive
  requirements gathering, domain analysis, and produces a structured
  Software Requirements Specification aligned with ISO/IEC/IEEE 29148.
  DO NOT USE for project planning (use planner). DO NOT USE for
  architecture decisions (use architect). DO NOT USE for user
  experience design (use designer).
version: 1.0.0
---

# Researcher — Requirements & Domain Analysis

## Purpose

Perform the first phase of the Dev Design SkillSet pipeline by transforming
raw user input into structured, testable requirements and a domain model.
Produce a Software Requirements Specification (SRS) and Domain Analysis
document that becomes the foundation for all downstream skills (planner,
architect, designer, engineer). Capture hard user technology constraints
and preferences in the requirements set, but do not select a tech-stack
overlay.

## When to Activate

Activate when commander delegates Phase 1 (Requirements & Domain Analysis)
or when a user directly requests requirements gathering, domain modeling,
or stakeholder analysis for a new software project.

---

## Execution Modes

### Pipeline Mode (Commander-Delegated)

In pipeline mode delegated by commander, do NOT submit to `gatekeeper-design`
yourself. Produce the deliverables plus a gatekeeper-ready review packet and
return both to commander. Commander owns the review cycle.

### Standalone Mode (Direct User Activation)

When activated directly by a user, this skill owns the final review loop for
its own deliverables. Produce the deliverables, submit them to
`gatekeeper-design`, address any REVISE findings, and return the approved
result plus the final review report.

---

## Workflow

### Step 1: Extract Project Context

From the commander's delegation (or direct user input), extract:
- **Project vision**: What is being built and why?
- **Target users**: Who will use this system?
- **Business context**: What problem does this solve? What value does it create?
- **Constraints**: Budget, timeline, regulatory, technical, team limits
- **Existing systems**: What integrations or migrations are involved?
- **Hard tech constraints/preferences**: User-mandated runtimes, cloud providers,
  languages, frameworks, hosting limits, or forbidden technologies

If critical information is missing, note it as an open question rather than
inventing assumptions. Prefer explicit gaps over implicit guesses.

Apply the adversarial anti-gaming framework from `../../references/universal-frameworks.md`
while gathering requirements. Do not smuggle assumptions, stakeholder wishes,
or tool preferences into the SRS as if they were confirmed facts.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

### Step 2: Identify Stakeholders

Map every stakeholder role that interacts with or is affected by the system:

Use this discovery order so no stakeholder class is skipped:
1. Walk the primary user journeys end to end
2. Identify who owns each touchpoint, approval, integration, and support burden
3. Add downstream operators, compliance reviewers, and analytics consumers affected by the system
4. Record any external team or vendor whose delay could block delivery

| Role | Responsibility | Key Concerns |
|------|---------------|--------------|
| Business Owner | Budget, priority, success metrics | ROI, time-to-market |
| End User(s) | Daily system interaction | Usability, reliability |
| Architect | System design, tech decisions | Scalability, maintainability |
| Security/Compliance | Risk, regulatory adherence | Data protection, audit |
| SRE/Operations | Runtime stability, observability | Uptime, incident response |
| Data/Analytics | Reporting, insights | Data quality, access |

### Step 3: Define Functional Requirements

For each feature or capability, produce a structured requirement:

```markdown
### FR-001: [Requirement Title]
**Priority**: MUST | SHOULD | MAY (RFC 2119)
**Description**: [What the system does]
**Acceptance Criteria**:
  - GIVEN [precondition] WHEN [action] THEN [outcome]
  - GIVEN [precondition] WHEN [action] THEN [outcome]
**Error Scenarios**:
  - WHEN [error condition] THEN [system behavior]
```

Use RFC 2119 keywords (MUST, SHOULD, MAY) for priority classification.
Every requirement MUST have at least one testable acceptance criterion because
untestable requirements become unverifiable promises during build and review.
Acceptance criteria MUST use GIVEN/WHEN/THEN format because that structure
eliminates ambiguity and maps directly to executable tests.

**Complete example:**

```markdown
### FR-007: User Password Reset
**Priority**: MUST
**Description**: The system allows authenticated users to reset their password
via a time-limited email link.
**Acceptance Criteria**:
  - GIVEN a registered user WHEN they request a password reset THEN the system
    sends an email with a unique reset link valid for 30 minutes
  - GIVEN a valid reset link WHEN the user submits a new password meeting
    complexity rules THEN the password is updated and all existing sessions
    are invalidated
  - GIVEN an expired reset link WHEN the user clicks it THEN the system
    displays "Link expired" and offers to resend
**Error Scenarios**:
  - WHEN the email address is not registered THEN the system responds
    identically to a valid request (prevents user enumeration)
  - WHEN the reset link has already been used THEN the system displays
    "Link already used" and offers to resend
```

### Step 4: Define Non-Functional Requirements

Map NFRs to ISO/IEC 25010 quality characteristics. Every NFR MUST have a
measurable threshold because unmeasurable requirements cannot be verified
during testing or review — never use subjective terms like "fast" or
"reliable" because subjective terms create ambiguity that leads to
build/review disputes.

Before finalizing the NFR set, validate that security, privacy, and compliance
requirements do not contradict each other or the stated technical constraints.
When high-risk requirements appear, cross-check them against the applicable
standard family (for example GDPR, HIPAA, SOC 2, OWASP, or project-specific
security policy) and record the governing reference directly in the SRS.
If a requirement is incompatible with the stated technical constraints, stop
and surface the contradiction explicitly rather than carrying an infeasible NFR
set downstream.

Consult `references/requirements-template.md` for the complete quality
attributes framework.

**Example NFRs**:
- **Performance**: API response time MUST be < 200ms at p95 under 1000 concurrent users
- **Availability**: System uptime MUST be ≥ 99.9% measured monthly
- **Security**: All PII MUST be encrypted at rest (AES-256) and in transit (TLS 1.3)
- **Scalability**: System MUST handle 10x current load without architecture changes
- **Accessibility**: UI MUST meet WCAG 2.2 Level AA compliance

### Step 5: Domain Analysis

Apply Domain-Driven Design techniques to identify the problem space structure.
Follow this procedure:

1. **Event Discovery**: Walk every user journey and system interaction from
   end to end. For each action, ask "what happened?" and record it as a past-tense
   domain event (e.g., "OrderPlaced", "PaymentProcessed", "InventoryReserved").
2. **Command Identification**: For each event, identify the command that triggers
   it (e.g., "PlaceOrder") and the actor who issues it (user, system, scheduler).
3. **Aggregate Grouping**: Cluster commands and events around the data they
   modify. Each cluster is a candidate aggregate (e.g., Order, Payment, Inventory).
4. **Policy Detection**: Identify reactive rules — "when X happens, automatically
   do Y" — as policies (e.g., "when PaymentProcessed, trigger InventoryReserved").
   Policies often signal bounded context boundaries.
5. **Bounded Context Mapping**: Group aggregates into bounded contexts by
   linguistic consistency (same term means the same thing within a context).
   Where the same word means different things (e.g., "Account" in billing vs.
   identity), draw a context boundary. Map relationships between contexts
   using DDD patterns: Shared Kernel, Customer/Supplier, Conformist,
   Anti-Corruption Layer, or Published Language.
6. **Core Domain Classification**: Label each bounded context as Core Domain
   (competitive advantage — build custom), Supporting (necessary but not
   differentiating — build or buy), or Generic (commodity — buy or use SaaS).
7. **Validate with Stakeholders**: Present the context map back to the user or
   domain expert. Ask: "Does this grouping match how your organization thinks
   about these concepts?" Revise boundaries based on feedback.

Consult `references/domain-analysis.md` for detailed methodology, notation
conventions, and domain model documentation format.

### Step 6: Produce SRS Document

Compile all findings into the SRS format from `references/requirements-template.md`.
The document MUST include the following because downstream skills depend on a complete SRS to produce accurate architecture and implementation specs:

1. Document metadata (title, authors, version, status)
2. Project overview and background
3. Stakeholder registry
4. Functional requirements (all FR-XXX items)
5. Non-functional requirements (mapped to ISO 25010)
6. Domain model (bounded contexts, entities, key relationships)
7. External interface requirements (integrations, APIs, data imports)
8. Constraints and assumptions
9. Out-of-scope items
10. Open questions and ambiguities

Add a dedicated subsection for **Technology Constraints and Preferences** that
records only user-specified requirements, prohibitions, or preferences. Do not
choose backend or frontend overlays in this phase.

### Step 7: Prepare Review Handoff

Package the completed SRS and domain analysis documents with a review packet
containing:
- Source skill: `researcher`
- Deliverables produced
- Original user request or commander delegation summary
- Hard technology constraints/preferences captured from the user
- Open questions and assumptions

If operating in pipeline mode, return the deliverables and review packet to
commander for gatekeeper submission.

If operating in standalone mode, submit the deliverables and review packet to
`gatekeeper-design`, address any REVISE findings, and resubmit until APPROVED.

---

## Output Format

The researcher produces two deliverables:

1. **Software Requirements Specification (SRS)** — Complete requirements document
2. **Domain Analysis** — Bounded context map, domain events, aggregate boundaries

Both follow the templates in the references directory.

In pipeline mode, return both deliverables with a gatekeeper-ready review packet.

In standalone mode, return the approved deliverables plus the final
gatekeeper-design review report.

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| User request is vague or underspecified | Ask ONE batch of clarifying questions covering: target users, core problem, key constraints, and success criteria. Do not proceed with assumptions on ambiguous core requirements. |
| Conflicting stakeholder needs | Document both positions with their rationale. Mark the requirement as "Disputed — requires user resolution" and present the trade-offs. Do not silently pick one side. |
| Requirements contradict technical constraints | Flag the contradiction explicitly. Propose feasible alternatives that satisfy the intent. Let the user decide which constraint yields. |
| Domain is unfamiliar (no prior domain knowledge) | Invest more time in domain analysis. Use event storming to surface domain concepts. Ask the user to validate the domain model before proceeding to functional requirements. |
| Existing system being replaced or extended | Capture legacy constraints: data migration needs, backward compatibility requirements, feature parity expectations, and integration points that must be preserved. |
| Regulatory or compliance requirements detected | Document them as non-negotiable constraints with specific standard references (GDPR, HIPAA, SOC 2, etc.). These constrain all downstream phases. |

---

## Additional Resources

### Reference Files

For detailed templates and methodology:
- **`references/requirements-template.md`** — Full SRS template with all sections and quality attributes framework
- **`references/domain-analysis.md`** — Event Storming methodology, bounded context mapping, and domain model documentation format

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
   phase: 1
   skill: researcher
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
