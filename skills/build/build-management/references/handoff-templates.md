# Build Pipeline Handoff Templates

> **Placeholder notation**: Square-bracket tokens in this file are template
> placeholders to be replaced during delegation construction. The authoritative
> persisted-path format in `save-protocol.md` uses brace variables such as
> `{run-id}`.

## Phase 1: Delegation to bob-the-builder

Use this template when delegating the initial implementation to bob-the-builder.

```markdown
## BUILD-MANAGEMENT DELEGATION: Phase 1 — Implementation

### Original Design Specification
[Paste the approved design spec verbatim or reference the deliverable location]

### Tech Stack Selection
- Language/Runtime: [e.g., TypeScript 5.x / Node.js 22]
- Backend Framework: [e.g., Fastify 5.x]
- Frontend Framework: [e.g., Next.js 15 / React 19]
- Database: [e.g., PostgreSQL 16 with Drizzle ORM]
- Infrastructure: [e.g., Docker, Fly.io]

### Implementation Scope
[Ordered list of modules with dependency relationships]

1. [Module A] — Foundation (no dependencies)
2. [Module B] — Depends on Module A
3. [Module C] — Depends on Module A, Module B
...

### Constraints
- Performance: [targets, SLAs]
- Compatibility: [browser support, API versioning]
- Security: [compliance requirements, data sensitivity]
- Timeline: [if applicable]

### Architecture Decisions
[Key ADRs or design decisions that constrain implementation]

### API Contracts
[OpenAPI/AsyncAPI references or inline contract definitions]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/build/phase-1_bob-the-builder/
- **Persistence active**: [yes/no]

### Instruction
Execute the bob-the-builder skill workflow. Produce complete, production-ready
code for all specified modules. Implement in dependency order. No placeholders,
no TODO stubs, no mock implementations. Submit to build-management for
gatekeeper-build review when complete.
```

---

## Phase 2: Delegation to test-builder

Use this template after Phase 1 code is gatekeeper-build-approved.

```markdown
## BUILD-MANAGEMENT DELEGATION: Phase 2 — Test Suite Creation

### Approved Codebase
[Reference to gatekeeper-approved code from Phase 1]

### Design Specification
[Reference to original design spec for requirements-based testing]

### Tech Stack
- Test Runner: [e.g., Vitest, pytest, Go testing]
- Assertion Library: [e.g., built-in, Chai, assertpy]
- Mocking: [e.g., vitest mocks, unittest.mock, gomock]
- E2E: [e.g., Playwright, Cypress]

### Critical Paths
[List the most critical user flows and code paths that must be tested first]

1. [Critical path 1 — e.g., user authentication flow]
2. [Critical path 2 — e.g., payment processing]
3. [Critical path 3 — e.g., data validation pipeline]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/build/phase-2_test-builder/
- **Persistence active**: [yes/no]

### Instruction
Execute the test-builder skill workflow. Create a comprehensive test suite
covering unit, integration, and E2E tests. Prioritize critical paths. Every
test must be meaningful — no trivial assertions. Submit to build-management
for gatekeeper-build review when complete.
```

---

## Phase 3: Delegation to security-builder

Use this template after Phase 2 tests are gatekeeper-build-approved.

```markdown
## BUILD-MANAGEMENT DELEGATION: Phase 3 — Security Audit

### Approved Codebase
[Reference to gatekeeper-approved code and tests]

### Tech Stack
[Language, framework, dependencies — relevant to vulnerability patterns]

### Deployment Model
- Hosting: [e.g., cloud, on-premise, serverless]
- Network exposure: [e.g., public API, internal service, hybrid]
- Data sensitivity: [e.g., PII, financial, healthcare, public]

### Trust Boundaries
[Describe where external input enters the system and where sensitive data exits]

### Compliance Requirements
[Any regulatory frameworks: GDPR, HIPAA, PCI-DSS, SOC 2]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/build/phase-3_security-builder/
- **Persistence active**: [yes/no]

### Instruction
Execute the security-builder skill workflow. Perform a systematic security
audit of the entire codebase. Map findings to OWASP Top 10, CWE Top 25,
and NIST SSDF. Package remediation items separately for routing to
bob-the-builder. Submit the audit report and any remediation package to
build-management for gatekeeper-build review when complete.
```

---

## Phase 4: Delegation to cross-check-build-confirm

Use this template after Phase 3 security audit is gatekeeper-build-approved and all remediation is complete.

```markdown
## BUILD-MANAGEMENT DELEGATION: Phase 4 — Completeness Scan

### Approved Codebase
[Reference to security-cleared, fully remediated codebase]

### Original Design Specification
[Reference to the original design spec for completeness comparison]

### Expected Modules
[Complete list of modules, features, and components that should exist]

| Module | Expected Location | Status |
|--------|------------------|--------|
| [Module A] | src/domain/module-a/ | Verify |
| [Module B] | src/api/module-b/ | Verify |
...

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/build/phase-4_cross-check/
- **Persistence active**: [yes/no]

### Instruction
Execute the cross-check-build-confirm skill workflow. Perform a complete
scan for scaffold code, TODOs, placeholders, mockups, fake data, and
temporary implementations. Compare implemented modules against the design
specification. Issue a CLEAN or FINDINGS verdict. If the verdict is CLEAN,
submit the report to build-management for final gatekeeper-build review. If the
verdict is FINDINGS, submit the findings package to build-management for
remediation routing.
```

---

## Gatekeeper Submission Template

Use this template when submitting any phase output to gatekeeper-build.

```markdown
## GATEKEEPER SUBMISSION

### Phase: [1 — Implementation | 2 — Testing | 3 — Security Audit | 4 — Completeness Scan]
### Source Skill: [bob-the-builder | test-builder | security-builder | cross-check-build-confirm]
### Revision Attempt / Cycle: [1 | 2 | 3]

### Deliverable Summary
[Brief description of what is being submitted for review]

### Design Specification Reference
[Link or reference to the original design spec for intent verification]

### Change Manifest
[File-by-file listing of all created or modified files]

### Self-Assessment
[The source skill's self-review notes, if applicable]

### Previous Gatekeeper Findings (if revision)
[Reference to prior gatekeeper findings and how they were addressed]

### Request
Review this deliverable against the design specification. Validate correctness,
completeness, code quality, security, documentation, and runtime verification
when applicable. Issue a verdict:
APPROVED, REVISE, or ESCALATE.
```

---

## Remediation Routing Template

Use this template when routing security or completeness findings to bob-the-builder.

```markdown
## REMEDIATION REQUEST

### Source: [security-builder | cross-check-build-confirm]
### Priority: [Critical — fix immediately | Major — fix before delivery | Minor — fix if time permits]

### Findings to Address
| ID | Severity | File | Line | Description | Required Fix |
|----|----------|------|------|-------------|-------------|
| [SEC-001] | Critical | src/auth.ts | 42 | SQL injection | Parameterize query |
| [CCC-003] | Blocker | src/api.ts | 15 | TODO placeholder | Implement handler |

### Context
[Any additional context needed for the fixes]

### Instruction
Address all Critical and Major findings. Submit updated code through
build-management for re-validation. Apply the same production-quality
standards as original implementation.
```

---

## Final Delivery Template

Use this template when delivering the completed build package to the user.

```markdown
## FINAL BUILD DELIVERY: [Project Name]

### Executive Summary
[One paragraph describing what was built, key decisions made, and overall quality]

### Build Statistics
- Modules implemented: [count]
- Total files created/modified: [count]
- Test suite: [count] tests ([unit], [integration], [E2E])
- Test coverage: [percentage]
- Security findings: [count] found, [count] resolved, [count] accepted risk
- Completeness scan: CLEAN
- Final completeness gate: APPROVED
- Gatekeeper reviews: [count] phases × [avg attempts] average attempts

### Package Contents
1. **Production Code** — [location reference]
2. **Test Suite** — [location reference]
3. **Security Audit Report** — [inline or reference]
4. **Completeness Certification** — CLEAN + final gatekeeper approval
5. **Build Audit Trail** — [inline log]

### Deployment Checklist
- [ ] Configure environment variables (see .env.example)
- [ ] Run database migrations
- [ ] Execute test suite: [command]
- [ ] Deploy to staging first
- [ ] Verify health checks
- [ ] Promote to production

### Open Items
[Any deferred decisions, known limitations, or manual steps remaining]
```
