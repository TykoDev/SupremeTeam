---
name: researcher
description: >-
  This skill should be used when the user or commander asks to "gather
  requirements", "analyze the domain", "create an SRS", "identify stakeholders",
  "define non-functional requirements", "map bounded contexts", "conduct
  requirements engineering", or "research the problem space". It performs
  comprehensive requirements gathering, domain analysis, and produces a
  structured Software Requirements Specification aligned with ISO/IEC/IEEE 29148.
version: 1.0.0
---

# Researcher — Requirements & Domain Analysis

## Purpose

This skill performs the first phase of the Dev Design SkillSet pipeline.
It transforms raw user input into structured, testable requirements and a
domain model. The output is a Software Requirements Specification (SRS)
and Domain Analysis document that becomes the foundation for all downstream
skills (planner, architect, designer, engineer). It captures hard user
technology constraints and preferences in the requirements set, but it does
not select a tech-stack overlay.

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

### Step 2: Identify Stakeholders

Map every stakeholder role that interacts with or is affected by the system:

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
Every requirement MUST have at least one testable acceptance criterion.
Acceptance criteria MUST use GIVEN/WHEN/THEN format for unambiguous testing.

### Step 4: Define Non-Functional Requirements

Map NFRs to ISO/IEC 25010 quality characteristics. Every NFR MUST have a
measurable threshold — never use subjective terms like "fast" or "reliable".

Consult `references/requirements-template.md` for the complete quality
attributes framework.

**Example NFRs**:
- **Performance**: API response time MUST be < 200ms at p95 under 1000 concurrent users
- **Availability**: System uptime MUST be ≥ 99.9% measured monthly
- **Security**: All PII MUST be encrypted at rest (AES-256) and in transit (TLS 1.3)
- **Scalability**: System MUST handle 10x current load without architecture changes
- **Accessibility**: UI MUST meet WCAG 2.2 Level AA compliance

### Step 5: Domain Analysis

Apply Domain-Driven Design techniques to identify the problem space structure:

1. **Event Storming**: Identify domain events (orange), commands (blue), 
   aggregates (yellow), policies (purple)
2. **Bounded Context Mapping**: Define context boundaries and their relationships
   (Shared Kernel, Customer/Supplier, Conformist, Anti-Corruption Layer)
3. **Core Domain Identification**: Which bounded contexts are the core domain
   (competitive advantage), supporting, or generic?

Consult `references/domain-analysis.md` for detailed methodology.

### Step 6: Produce SRS Document

Compile all findings into the SRS format from `references/requirements-template.md`.
The document MUST include:

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

## Additional Resources

### Reference Files

For detailed templates and methodology:
- **`references/requirements-template.md`** — Full SRS template with all sections and quality attributes framework
- **`references/domain-analysis.md`** — Event Storming methodology, bounded context mapping, and domain model documentation format

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

See `save-protocol.md` (project root) for complete format specifications.
