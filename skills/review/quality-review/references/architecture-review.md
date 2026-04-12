# Architecture Review — C4 Model, ADRs, and Drift Detection

This reference provides detailed procedures for evaluating architectural alignment, maintaining Architecture Decision Records, and detecting architecture drift.

---

## The C4 Model

The C4 model is the industry standard for hierarchical architecture documentation. It uses a cartographic "zoom" approach to map architecture across four levels of abstraction, from the highest-level system view down to code-level detail.

### Level 1: System Context

**What it shows:** How the software system fits into the broader environment. Actors (users, external systems), the system under development, and the relationships between them. No technology details.

**During review, verify:**
- New external integrations are documented at the context level
- New actor types (user roles, service accounts) are reflected
- Removed integrations are cleaned up from the diagram
- Data flow directions between systems are accurate

**Red flags:**
- PR adds an external API call, but no context diagram update
- New user-facing feature with no actor relationship documented
- Undocumented "shadow" integrations (system calls an API not shown in context)

### Level 2: Containers

**What it shows:** The separately deployable building blocks: web applications, API services, databases, message brokers, file storage, serverless functions. Technology choices are shown at this level.

**During review, verify:**
- New services or databases are documented as containers
- Communication protocols between containers are accurate (REST, gRPC, WebSocket, message queue)
- Data storage technology choices align with documented decisions
- Container responsibilities are clearly bounded (no container doing everything)

**Red flags:**
- New microservice added without updating container diagram
- Database schema changes implying a new data store not documented
- Container coupling: two containers sharing a database directly (should use APIs)

### Level 3: Components

**What it shows:** Internal logical groupings within a single container: domain services, HTTP handlers, repository layers, external API clients. Shows separation of concerns within a container.

**During review, verify:**
- New components respect the container's documented internal architecture
- Dependencies between components follow the intended direction (e.g., handlers → services → repositories)
- No circular dependencies introduced
- Component responsibilities are cohesive (each component has one clear purpose)

**Red flags:**
- Handler directly accessing database, bypassing the repository layer
- Business logic leaking into presentation components
- Shared mutable state between components that should be independent

### Level 4: Code

**What it shows:** Implementation-level details — classes, interfaces, functions. Generally auto-generated from the codebase rather than manually maintained.

**During review, verify:**
- Class/interface structure aligns with the component design
- Public APIs match the documented interfaces
- Implementation patterns are consistent within the component

---

## Architecture Decision Records (ADRs)

ADRs are formal markdown documents that capture the context, decision, alternatives considered, and consequences of key architectural choices. They serve as the decision audit trail for the architecture.

### ADR Format

```markdown
# ADR-XXX: [Title]

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-YYY]

## Context
[What is the issue? What forces are at play? What constraints exist?]

## Decision
[What is the change that we're proposing or have agreed to implement?]

## Alternatives Considered
[What other approaches were evaluated? Why were they rejected?]

## Consequences
[What becomes easier or harder? What are the trade-offs?]

## Date
[YYYY-MM-DD]
```

### ADR Lifecycle During Review

**When reviewing a PR, check:**

1. **Does this change align with existing ADRs?** If the codebase has ADRs, verify the change respects them.

2. **Does this change warrant a new ADR?** Create a new ADR when:
   - Introducing a new technology (database, framework, language)
   - Changing a communication pattern (REST to gRPC, synchronous to async)
   - Altering data flow architecture
   - Changing deployment topology
   - Making a decision that is expensive to reverse

3. **Does this change contradict an existing ADR?** If so:
   - The PR must include a new ADR that supersedes the old one
   - The old ADR's status must be updated to "Superseded by ADR-YYY"
   - Rationale for the change must be documented

4. **Is the ADR discoverable?** ADRs should live in a known location (`docs/adr/`, `architecture/decisions/`) and be indexed (numbered sequentially or by date).

---

## Architecture Drift Detection

Architecture drift occurs when the actual code diverges from the intended/documented architecture. In the AI era, drift accelerates because AI coding assistants generate code that may not respect architectural boundaries.

### Drift Indicators

**Boundary violations:**
- Direct imports across module boundaries that should communicate via defined interfaces
- Presentation layer importing directly from data layer (bypassing service layer)
- Business logic embedded in infrastructure code (database queries containing business rules)

**Coupling creep:**
- Increasing number of cross-module imports over time
- Shared data structures modified by multiple independent modules
- Circular dependency chains forming between packages

**Interface bypass:**
- Code calling internal methods of another module instead of the public API
- Database queries from modules that should access data through a service
- Direct file system access from business logic (should use an abstraction)

**Convention erosion:**
- New code using a different pattern than established convention (e.g., callbacks where the codebase uses async/await)
- Configuration approaches diverging (some modules use env vars, others use config files)
- Error handling patterns inconsistent across modules

### Drift Scoring Methodology

Compute an informal drift score by evaluating:

| Dimension | Weight | Score (0-10) | Description |
|-----------|--------|-------------|-------------|
| Boundary compliance | 30% | | Do modules respect defined boundaries? |
| Dependency direction | 25% | | Do dependencies flow in the intended direction? |
| Interface adherence | 20% | | Are public APIs used instead of internals? |
| Convention consistency | 15% | | Does new code follow established patterns? |
| ADR alignment | 10% | | Are documented decisions respected? |

**Scoring guide:**
- 9-10: Exemplary alignment, no drift detected
- 7-8: Minor drift, non-blocking but worth noting
- 5-6: Moderate drift, should be addressed before it compounds
- 3-4: Significant drift, recommend architectural review discussion
- 1-2: Severe drift, likely indicates the architecture needs updating or the code needs refactoring

**Threshold recommendation:** Flag for discussion when score drops below 7. Consider blocking merge when score drops below 5.

### Decision Authority Mapping

Map architectural decision authority to C4 abstraction levels:

| C4 Level | Decision Authority | Example Decisions |
|----------|-------------------|-------------------|
| System Context (L1) | Enterprise Architect / CTO | New external integrations, system boundaries |
| Containers (L2) | Solution Architect / Tech Lead | New services, databases, communication patterns |
| Components (L3) | Tech Lead / Senior Developer | Internal module structure, dependency patterns |
| Code (L4) | Developer / Reviewer | Class design, function structure, naming |

Changes at higher levels require higher-authority sign-off. A developer can restructure code within a component (L4), but adding a new container (L2) requires solution architect review.

### Automated Drift Detection Tools

**Archyl:** AI-powered discovery engine that scans Git repositories, analyzes code structures and dependency graphs, and generates live C4 models. Compares live model against documented baseline to produce an Architecture Drift Score.

**ArchUnit (Java/.NET):** Define architectural rules as unit tests. Tests fail when code violates defined boundaries.

**Dependency-cruiser (JavaScript):** Validates and visualizes module dependencies against defined rules. Catches circular dependencies, forbidden imports, and layer violations.

**go-arch-lint (Go):** Validates Go project architecture by enforcing import rules between packages.

---

## Common Drift Patterns to Watch

### Pattern 1: The Shortcut Dependency
**Symptom:** Module A directly imports Module C, bypassing Module B (the defined intermediary).
**Cause:** Developer takes the shortest path instead of following the architecture.
**Fix:** Route through the defined interface. If the interface is too cumbersome, improve it.

### Pattern 2: The Leaky Abstraction
**Symptom:** Internal implementation details of Module A are used by Module B.
**Cause:** Convenient access to internals instead of going through the public API.
**Fix:** Make internals truly internal (unexported in Go, package-private in Java). Expose needed functionality through the public API.

### Pattern 3: The Distributed Monolith
**Symptom:** Microservices that must be deployed together and share databases.
**Cause:** Service boundaries drawn incorrectly, or boundaries eroded over time.
**Fix:** Evaluate whether services should be merged or truly decoupled with proper API boundaries.

### Pattern 4: The God Module
**Symptom:** One module that everything depends on, with hundreds of exports.
**Cause:** Convenience — dumping shared code into `utils`, `common`, or `helpers`.
**Fix:** Extract cohesive domains from the god module into purpose-specific modules.

### Pattern 5: Convention Erosion
**Symptom:** Three different error handling patterns in the same codebase.
**Cause:** No enforcement mechanism; new developers introduce patterns from previous jobs.
**Fix:** Document the canonical pattern, add lint rules to enforce it, update existing code incrementally.
