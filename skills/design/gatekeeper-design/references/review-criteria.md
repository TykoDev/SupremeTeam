# Gatekeeper Review Criteria — Per Deliverable Type

## Requirements Document (from researcher)

### Required Sections Checklist
- [ ] Problem statement with clear scope boundaries
- [ ] Stakeholder identification with roles
- [ ] Functional requirements with testable acceptance criteria
- [ ] Non-functional requirements with measurable thresholds
- [ ] Quality attributes mapped to ISO 25010 characteristics
- [ ] Domain model or bounded context identification
- [ ] Constraints and assumptions explicitly stated
- [ ] Out-of-scope items explicitly listed
- [ ] Technology constraints and preferences captured without prematurely locking a stack

### Accuracy Checks
- Verify acceptance criteria are truly testable
- Verify NFRs have numeric thresholds
- Check for conflicting requirements
- Verify stakeholder roles match responsibilities described
- Confirm domain terms are defined consistently throughout
- Confirm tech constraints/preferences are recorded faithfully rather than invented

### Completeness Checks
- Every functional requirement has at least one acceptance criterion
- Error scenarios and edge cases are addressed
- Data retention and privacy requirements are specified
- Integration points with external systems are identified
- Regulatory/compliance requirements are listed if applicable

---

## Project Plan (from planner)

### Required Sections Checklist
- [ ] Milestones with dates or relative sequencing
- [ ] Deliverable list per milestone
- [ ] Risk register with probability, impact, and mitigation
- [ ] Dependency map (what blocks what)
- [ ] Rollout strategy (phased, big-bang, canary)
- [ ] Feature flag strategy for progressive rollout
- [ ] Resource assumptions or constraints
- [ ] Technology decision timeline
- [ ] Explicit rollout prerequisites tied to approved requirements and constraints

### Accuracy Checks
- Verify milestone dependencies are logically ordered
- Check risk mitigations are actionable
- Verify rollout strategy is compatible with the current delivery model and known constraints
- Confirm estimates are grounded in complexity, not arbitrary dates
- Check for missing dependencies between deliverables

### Consistency Checks
- Milestones align with requirements scope
- Risks identified in the plan match risks that should influence the architecture document
- Rollout prerequisites reflect explicit tech constraints/preferences from research
- The plan does not claim a finalized backend or frontend overlay before later phases lock them

---

## Architecture Document (from architect)

### Required Sections Checklist
- [ ] C4 System Context diagram
- [ ] C4 Container diagram
- [ ] C4 Component diagram (for complex domains)
- [ ] Architecture Decision Records (ADRs) for significant choices
- [ ] API contracts (OpenAPI for REST, AsyncAPI for events)
- [ ] Data model with entity relationships
- [ ] Security architecture (auth flows, trust boundaries)
- [ ] Deployment topology (environments, regions)
- [ ] Cross-cutting concerns (logging, caching, config, i18n)
- [ ] Alternatives considered with trade-off analysis
- [ ] Backend Stack Lock with exact `../tech-stacks/*.md` overlay reference and version tuple

### Accuracy Checks
- Verify C4 diagrams are internally consistent
- Check ADR decisions are justified with concrete reasoning
- Verify API contracts match the data models
- Check that the stated architecture pattern is reflected in the structure
- Verify backend stack versions exist and are compatible with each other
- Confirm performance claims are realistic for the chosen architecture

### Feasibility Checks
- Can the deployment topology actually handle the stated NFRs?
- Are the chosen technologies compatible?
- Is the complexity appropriate for the team size and timeline?
- Are there single points of failure in the architecture?
- Does every stated exception or deviation from the backend overlay have justification and ADR traceability?

---

## Frontend Specification (from designer)

### Required Sections Checklist
- [ ] Frontend architecture pattern decision (SPA, SSR, SSG, Islands)
- [ ] Frontend Stack Lock with exact `../tech-stacks/*.md` overlay reference and version tuple
- [ ] Component hierarchy and design system
- [ ] State management strategy
- [ ] Routing strategy
- [ ] Accessibility requirements (WCAG 2.2 compliance level)
- [ ] Performance targets (Core Web Vitals)
- [ ] Responsive design breakpoints
- [ ] Browser/device support matrix

### Accuracy Checks
- Verify chosen frontend framework matches the project requirements
- Check state management choice is appropriate
- Verify accessibility claims meet WCAG 2.2 Level AA requirements
- Confirm Core Web Vitals targets are realistic for the chosen architecture
- Check component naming follows stated conventions consistently
- Confirm the frontend overlay exists and the version tuple is coherent

### Consistency Checks
- Frontend Stack Lock aligns with architect's container diagram and Backend Stack Lock
- API consumption patterns match the API contracts in the architecture doc
- State management approach aligns with data flow patterns in architecture
- Every stated frontend exception is explicit and justified

---

## Implementation Specification (from engineer)

### Required Sections Checklist
- [ ] Inherited Stack Locks with exact upstream overlay filenames and version tuples
- [ ] Repository structure with directory layout
- [ ] Code organization pattern (domain-first)
- [ ] Testing strategy with tool choices and coverage targets
- [ ] CI/CD pipeline design
- [ ] Docker/containerization configuration
- [ ] Environment variable contract (.env specification)
- [ ] Security implementation details (OWASP controls)
- [ ] Observability setup (OpenTelemetry configuration)
- [ ] Code quality tooling configuration
- [ ] Migration and data seeding strategy

### Accuracy Checks
- Verify dependency versions are current and compatible
- Check CI/CD pipeline stages are logically ordered
- Verify Docker configurations follow multi-stage build best practices
- Confirm testing strategy covers the testing model appropriately
- Check ORM configurations match the database stated in architecture
- Verify security controls address OWASP Top 10 items relevant to the application

### Consistency Checks
- Inherited Stack Locks match the approved Backend Stack Lock and Frontend Stack Lock
- Repository structure matches the architecture's domain model
- CI/CD pipeline produces artifacts needed by the deployment topology
- Environment variables defined here match what the architecture expects
- Testing tools are compatible with the chosen framework and runtime
- Observability setup aligns with the reliability requirements (SLOs)
- No silent stack substitutions appear without explicit ADR-backed exceptions

---

## Cross-Deliverable Consistency Matrix

When reviewing any deliverable, cross-check against previously approved deliverables:

| Check | Source A | Source B | What to Verify |
|-------|----------|----------|----------------|
| Domain alignment | Requirements | Architecture | Same bounded contexts, same entities |
| Planner readiness | Requirements | Project Plan | Decision gates and rollout prerequisites match actual constraints |
| Backend stack lock lineage | Requirements / Plan | Architecture | Chosen overlay respects user constraints and project realities |
| Frontend stack lock lineage | Architecture | Frontend Spec | Frontend overlay aligns with backend/API decisions |
| Implementation stack lineage | Architecture / Frontend | Implementation | Inherited locks match approved upstream locks |
| API match | Architecture | Implementation | OpenAPI contracts match route definitions |
| NFR coverage | Requirements | Architecture / Implementation | Performance targets addressed with specific mechanisms |
| Security coverage | Requirements | Implementation | All security requirements have implementation controls |
| Scope containment | Requirements | All | No deliverable exceeds the defined scope |
