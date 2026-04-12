# Output Protocol Reference

## Structured Change Manifest

Every implementation delivery from bob-the-builder MUST include a structured change manifest that enables gatekeeper-build to systematically validate the output.

### Manifest Format

```markdown
# IMPLEMENTATION MANIFEST

## Metadata
- **Source**: bob-the-builder
- **Phase**: [1 — Initial Implementation | Remediation Cycle N]
- **Design Spec Reference**: [document name or link]
- **Tech Stack**: [language, framework, key dependencies]
- **Date**: [YYYY-MM-DD]

## File Inventory

### Created Files
| # | File Path | Purpose | Lines | Dependencies |
|---|-----------|---------|-------|-------------|
| 1 | src/config/env.ts | Environment variable parsing | 45 | zod |
| 2 | src/user/user.model.ts | User domain model | 62 | zod |
| 3 | src/user/user.service.ts | User business logic | 85 | user.model, user.repository |

### Modified Files
| # | File Path | Change Description | Lines Changed |
|---|-----------|-------------------|---------------|
| 1 | package.json | Added dependencies | +5 |
| 2 | tsconfig.json | Enabled strict mode | +3 -1 |

### Deleted Files
| # | File Path | Reason |
|---|-----------|--------|
| 1 | src/legacy/old-handler.ts | Replaced by new user routes |

## Requirements Traceability

| Requirement ID | Description | Implementation Location | Status |
|---------------|-------------|------------------------|--------|
| FR-001 | User registration | src/user/user.routes.ts:register() | Complete |
| FR-002 | Email validation | src/user/user.model.ts:emailSchema | Complete |
| FR-003 | Password hashing | src/user/user.service.ts:hashPassword() | Complete |
| NFR-001 | Response time < 200ms | Connection pooling in src/config/database.ts | Complete |

## Architecture Compliance

### Layer Verification
| Layer | Files | Dependency Direction |
|-------|-------|---------------------|
| Domain | src/*/[name].model.ts | No external imports ✓ |
| Application | src/*/[name].service.ts | Imports domain only ✓ |
| Infrastructure | src/*/[name].repository.ts | Imports domain interfaces ✓ |
| Presentation | src/*/[name].routes.ts | Imports application layer ✓ |

### Pattern Compliance
- [ ] Domain-first file organization
- [ ] Repository pattern for data access
- [ ] Schema-based validation at boundaries
- [ ] Dependency injection via constructor/function params
- [ ] Structured error types

## Self-Review Checklist
- [ ] Every requirement has a corresponding implementation
- [ ] No TODO, FIXME, HACK, or placeholder comments
- [ ] No hardcoded credentials or secrets
- [ ] No console.log or print debugging statements
- [ ] No empty catch blocks or swallowed exceptions
- [ ] No unused imports or dead code
- [ ] All functions have error handling
- [ ] All public APIs have documentation

## Assumptions Made
| # | Assumption | Rationale | Impact if Wrong |
|---|-----------|-----------|----------------|
| 1 | [assumption] | [why assumed] | [what breaks] |

## Known Limitations
| # | Limitation | Reason | Mitigation |
|---|-----------|--------|------------|
| 1 | [limitation] | [why it exists] | [workaround or future plan] |
```

---

## File-by-File Implementation Tracking

For large implementations, maintain a running tracker:

```markdown
## Implementation Progress

| Module | File | Status | Notes |
|--------|------|--------|-------|
| config | src/config/env.ts | ✓ Complete | |
| config | src/config/database.ts | ✓ Complete | |
| user | src/user/user.model.ts | ✓ Complete | |
| user | src/user/user.service.ts | ✓ Complete | |
| user | src/user/user.repository.ts | ✓ Complete | |
| user | src/user/user.routes.ts | ✓ Complete | |
| order | src/order/order.model.ts | ◉ In progress | |
| order | src/order/order.service.ts | ○ Pending | Depends on order.model |
```

---

## Incremental Delivery Protocol

For large implementations that span multiple rounds:

### Round Structure

1. **Round 1**: Foundation modules (config, shared utilities, database setup)
2. **Round 2**: Core domain modules (models, services, repositories)
3. **Round 3**: Presentation layer (API routes, controllers, middleware)
4. **Round 4**: Integration and wiring (app bootstrap, dependency composition)

### Round Delivery Format

Each round includes:
- Updated file inventory (cumulative)
- Requirements covered in this round
- Dependencies on previous rounds
- Self-review checklist for this round's code

---

## Remediation Response Format

When addressing findings from gatekeeper-build, security-builder, or cross-check-build-confirm:

```markdown
# REMEDIATION RESPONSE

## Source Findings
- **From**: [gatekeeper-build | security-builder | cross-check-build-confirm]
- **Finding Count**: [N] Critical, [N] Major, [N] Minor

## Remediation Actions

### [Finding ID]: [Finding Title]
- **Severity**: [Critical | Major | Minor]
- **Original Issue**: [Description from the finding]
- **Fix Applied**: [What was changed and why]
- **Files Modified**: [list]
- **Verification**: [How to verify the fix resolves the issue]

### [Finding ID]: [Finding Title]
...

## Regression Check
- [ ] Existing functionality unaffected by fixes
- [ ] No new anti-patterns introduced
- [ ] Fix addresses root cause, not symptom

## Updated Manifest
[Include updated file inventory reflecting all changes]
```

---

## Submission Checklist

Before submitting any delivery to build-management:

1. **Manifest complete**: All created, modified, and deleted files listed
2. **Traceability verified**: Every requirement maps to implementation
3. **Self-review passed**: All checklist items checked
4. **Anti-patterns scanned**: No TODOs, no placeholders, no debug statements
5. **Architecture compliant**: Dependency direction verified
6. **Assumptions documented**: All assumptions listed with rationale
7. **Limitations acknowledged**: Genuine limitations noted (not excuses for incomplete work)

---

## Save Path Integration

When persistence is active (save path provided in `### Save Context`), the implementation manifest and all deliverables are additionally written to the save path as `deliverable_implementation-manifest.md`. This complements the in-context delivery — the on-disk copy serves as persistent backup that survives context compaction.
