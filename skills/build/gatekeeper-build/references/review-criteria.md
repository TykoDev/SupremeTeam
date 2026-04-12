# Review Criteria Reference

## Per-Phase Review Checklists

### Phase 1: bob-the-builder Output (Production Code)

#### Spec Alignment Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Requirements traceability | Every requirement in the design spec has a corresponding entry in the implementation manifest |
| 2 | API contract compliance | Every endpoint matches the OpenAPI/AsyncAPI spec (method, path, request/response schemas) |
| 3 | Data model compliance | Database entities match the data model from the design specification |
| 4 | Feature completeness | Every user story or feature has corresponding implemented code paths |
| 5 | Constraint adherence | Performance, security, and compatibility constraints from the spec are addressed |

#### Code Quality Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Logical correctness | Functions produce correct output for expected inputs |
| 2 | Error handling | All foreseeable failure modes have explicit handling — no empty catch blocks |
| 3 | Type safety | No type escape hatches (`any`, `as unknown`, `# type: ignore`) without justification |
| 4 | Naming clarity | Variables, functions, and files follow consistent naming conventions |
| 5 | Function design | Functions have single responsibility, ≤ 30 lines, ≤ 5 parameters |
| 6 | Dependency direction | Domain layer has zero external dependencies; imports flow inward |
| 7 | Code organization | Domain-first file organization; modules are self-contained |
| 8 | No dead code | No unused imports, unreachable code, or commented-out code blocks |

#### Security Checklist (For Code)

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Input validation | All external inputs validated at system boundaries |
| 2 | Output encoding | User data encoded before rendering in HTML, SQL, shell, or log contexts |
| 3 | No hardcoded secrets | Zero credentials, API keys, or tokens in source code |
| 4 | Authentication | All protected endpoints have authentication middleware |
| 5 | Authorization | Resource access includes ownership verification |

#### Anti-Pattern Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | No TODO/FIXME/HACK markers | Zero instances in production code |
| 2 | No placeholder data | Zero instances of lorem ipsum, example.com, hardcoded test data |
| 3 | No mock implementations | Zero stub functions or hardcoded returns in production paths |
| 4 | No debug statements | Zero console.log/print debugging |
| 5 | No empty blocks | Zero empty function bodies, catch blocks, or conditional branches |

---

### Phase 2: test-builder Output (Test Suite)

#### Test Meaningfulness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Specific assertions | Every test has at least one specific assertion (not just "does not throw") |
| 2 | Behavior testing | Tests verify observable behavior, not implementation details |
| 3 | Inversion resilience | Tests would fail if the production logic were inverted |
| 4 | Edge case coverage | Boundary values, null inputs, empty collections tested for each function |
| 5 | Error path coverage | Every documented error condition has a corresponding test |

#### Test Quality Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Naming convention | Test names describe scenario and expected result |
| 2 | AAA structure | Tests follow Arrange-Act-Assert pattern |
| 3 | Independence | No test depends on another test's execution or side effects |
| 4 | Determinism | Tests produce the same result on every run |
| 5 | No conditional logic | Tests do not contain if/else or loops (use parameterized tests) |
| 6 | Appropriate mocking | Mocks used only for external services; real dependencies preferred |

#### Test Coverage Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Critical paths | All critical user flows have test coverage |
| 2 | API endpoints | All endpoints tested for success AND error responses |
| 3 | Validation rules | All input validation schemas tested with valid and invalid inputs |
| 4 | Authentication | Both authenticated and unauthenticated access tested |
| 5 | Authorization | Horizontal and vertical access control tested |

---

### Phase 3: security-builder Output (Security Audit)

#### Finding Accuracy Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Evidence present | Every finding includes file:line reference with code snippet |
| 2 | CWE mapping correct | The cited CWE ID matches the actual vulnerability pattern |
| 3 | CVSS scoring valid | Score components (vector, complexity, impact) match the exploit scenario |
| 4 | Exploitability verified | The described attack is actually possible given the code structure |
| 5 | Impact assessment accurate | The stated impact reflects the real consequence of exploitation |

#### Audit Completeness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | OWASP coverage | All 10 OWASP Top 10 categories assessed or justified as N/A |
| 2 | Input trace | All external input entry points identified and traced |
| 3 | Auth verification | All protected endpoints verified for auth enforcement |
| 4 | Dependency scan | All dependencies checked against vulnerability databases |
| 5 | Secrets scan | Full codebase scanned for hardcoded credentials |

#### Remediation Quality Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Actionable fixes | Every finding includes a specific, implementable fix |
| 2 | Root cause targeting | Fixes address root cause, not symptoms |
| 3 | Priority clear | Findings ranked by severity with clear priority |
| 4 | Verification defined | Each finding specifies how to verify the fix |

---

### Phase 4: cross-check-build-confirm Output (Completeness Scan)

#### Static Scan Completeness Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | All 7 scan steps executed | Scan report includes results for all categories: Static Pattern, Structural, Behavioral, Data, Configuration, Documentation, Runtime Startup |
| 2 | Scan scope covers full codebase | Total files scanned is reasonable for project size; no directories excluded without justification |
| 3 | Design spec referenced | Scan references the original design specification for structural and feature completeness |
| 4 | Severity classifications correct | BLOCKERs are genuinely production-breaking; WARNINGs are genuinely ambiguous |
| 5 | Feature completeness matrix present | All features from design spec listed with implementation status |

#### Runtime Startup Verification Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | Project type correctly identified | Classification matches actual project structure and dependencies |
| 2 | Start commands correctly identified | Commands match project's package.json scripts, Makefile targets, or framework conventions |
| 3 | Backend startup tested (if applicable) | Startup log provided showing successful boot; health check response documented |
| 4 | Frontend startup tested (if applicable) | Dev server startup confirmed; content served and verified |
| 5 | Simultaneous operation tested (if full-stack) | Both servers confirmed running concurrently without conflict |
| 6 | Startup stability verified | Servers remained running for at least 10 seconds without crash |
| 7 | Process cleanup confirmed | All started processes properly terminated after verification |
| 8 | Exemption justified (if no server) | Clear documentation of why runtime verification does not apply, with alternative verification |
| 9 | Failure logs captured (if failures) | Full startup error output included for any BLOCKER findings |
| 10 | Findings correctly classified | Runtime failures classified as BLOCKER (not WARNING or INFO) |

#### Verdict Validation Checklist

| # | Check | Pass Criteria |
|---|-------|--------------|
| 1 | CLEAN verdict justified | Zero BLOCKERs, zero WARNINGs across ALL 7 steps including runtime |
| 2 | FINDINGS verdict complete | All findings packaged with correct severity, file location, and required action |
| 3 | Runtime verification not skipped | Step 7 results present in the scan report, or exemption documented |
| 4 | Remediation loop tracked | If re-scan, previous findings verified as resolved |
| 5 | Escalation criteria met (if applicable) | If 2 cycles completed with persistent BLOCKERs, escalation report provided |

---

## Cross-Phase Consistency Matrix

After reviewing individual phases, verify consistency across all approved deliverables:

```markdown
## Cross-Phase Consistency Check

| Code Module | Implementation (Phase 1) | Tests (Phase 2) | Security (Phase 3) | Completeness (Phase 4) | Status |
|------------|------------------------|-----------------|-------------------|----------------------|--------|
| user/auth | Implemented ✓ | Tests cover login, registration ✓ | Auth audit passed ✓ | Complete, server starts ✓ | Consistent |
| order/payment | Implemented ✓ | Tests cover CRUD but not payment edge cases | No specific payment security review | Complete ✓ | GAP (tests + security) |
| config | Implemented ✓ | No tests | No security review of config loading | Env vars documented ✓ | GAP (tests + security) |
```

### Consistency Checks

| Check | What to Verify |
|-------|---------------|
| Code ↔ Tests | Every implemented module has corresponding tests |
| Code ↔ Security | Every security-sensitive module was audited |
| Tests ↔ Security | Security findings have corresponding test coverage |
| Code ↔ Spec | Implementation matches design specification |
| Security fixes ↔ Code | All remediation items are reflected in the final code |
| Code ↔ Runtime | All server components identified in code have corresponding startup verification |
| Spec ↔ Runtime | Design spec's deployment architecture matches tested server components |
| Runtime ↔ Config | Environment variables needed for startup are all documented in .env.example |

### Gap Resolution

When gaps are found:
1. Determine which phase should address the gap
2. Issue a specific challenge to the responsible skill
3. Track resolution in the challenge ledger
4. Do not approve until gaps are resolved or explicitly justified
