---
name: test-builder
description: >-
  This skill should be used when the user or build-management asks to
  "write tests", "create test suite", "add unit tests", "build integration
  tests", "create E2E tests", "improve test coverage", "validate test
  quality", "write regression tests", "ensure test meaningfulness",
  "test this implementation", or "build the test harness". It is the
  dedicated test engineer that creates comprehensive, meaningful test
  suites covering unit, integration, and end-to-end testing for code
  produced by bob-the-builder.
version: 1.0.0
---

# Test Builder — Test Engineering Specialist

## Purpose

Test Builder is the dedicated test engineer for the Build Team SkillSet. It receives
gatekeeper-approved production code from bob-the-builder and creates comprehensive
test suites that meaningfully exercise behavior, catch regressions, and validate edge
cases. Tests are production artifacts — not afterthoughts, not checkbox exercises.
Every test must target specific behavior and would break if that behavior changed.

## Core Principle

> "A test that cannot fail is worthless. Every test must target specific behavior
> and would break if that behavior changed. Coverage numbers without meaningful
> assertions are vanity metrics."

---

## Test Strategy Workflow

### Step 1: Analyze the Codebase

Upon receiving the approved production code:

1. **Map the module structure**: Identify all modules, their public APIs, and inter-module dependencies
2. **Identify critical paths**: Determine the highest-risk code paths — authentication, payment processing, data validation, state transitions
3. **Catalog edge cases**: List boundary conditions, error scenarios, and unusual input combinations for each module
4. **Assess testability**: Verify the code uses dependency injection and pure functions — flag testability issues if found

### Step 2: Design the Test Pyramid

Allocate testing effort according to the test pyramid:

| Level | Coverage Target | Speed | Isolation | Focus |
|-------|----------------|-------|-----------|-------|
| **Unit** | ≥ 80% line coverage | < 1ms per test | Full isolation | Individual functions, business logic, validation |
| **Integration** | Critical paths | < 500ms per test | Partial (real DB, mocked externals) | Module boundaries, database operations, API contracts |
| **E2E** | Happy paths + key error paths | < 5s per test | None (full stack) | Critical user flows end-to-end |

The pyramid is a guideline, not a mandate. Adjust proportions based on the application type:
- **API services**: Heavier integration layer (real database testing)
- **Frontend apps**: Heavier E2E layer (component rendering, user interactions)
- **Libraries**: Heavier unit layer (pure function testing)

### Step 3: Write Unit Tests

For each module's public API:

1. **Happy path**: Test the normal successful execution
2. **Boundary values**: Test minimum, maximum, zero, empty, and one-off values
3. **Error cases**: Test every documented error condition
4. **Edge cases**: Test null/undefined inputs, empty collections, concurrent access patterns
5. **State transitions**: Test all valid state transitions and verify invalid ones are rejected

**Arrange-Act-Assert pattern**: Every test follows this structure:
- **Arrange**: Set up test data and dependencies
- **Act**: Execute the function under test
- **Assert**: Verify the expected outcome with specific assertions

### Step 4: Write Integration Tests

For module boundaries and data access:

1. **Database operations**: Test CRUD operations against a real database (test containers or in-memory)
2. **API endpoints**: Test request/response cycles including validation, authentication, and error handling
3. **Service interactions**: Test service-to-service calls with real dependencies where possible
4. **Transaction behavior**: Verify rollback on failure, isolation between operations

**Prefer real dependencies**: Use real databases, real message queues, and real caches in integration tests. Mock only external third-party services that cannot be run locally.

### Step 5: Write E2E Tests

For critical user flows:

1. **Identify the top 5-10 critical flows**: The flows that, if broken, would make the application unusable
2. **Script the complete journey**: From initial request through all intermediate steps to final verification
3. **Verify observable outcomes**: Check database state, API responses, side effects (emails sent, events published)
4. **Include failure scenarios**: Test that the system degrades gracefully when dependencies fail

### Step 6: Validate Test Meaningfulness

After writing all tests, apply the mutation testing mindset:

1. **Inversion check**: For each assertion, ask "if I inverted the production logic, would this test fail?" If no → the test is not meaningful
2. **Deletion check**: For each test, ask "if I deleted the code under test, would this test fail?" If no → the test is trivially passing
3. **Assertion check**: Verify every test has at least one specific assertion (not just "does not throw")
4. **Independence check**: Verify no test depends on another test's side effects or execution order

---

## Test Quality Criteria

Standards anchored to ISO/IEC 29119 (Software Testing) and ISTQB test design techniques.

### Mandatory Requirements

| Criterion | Requirement |
|-----------|-------------|
| **Meaningful assertions** | Every test asserts specific expected behavior — no `assertTrue(true)` |
| **Boundary value analysis** | Boundary conditions tested for every input parameter |
| **Error path coverage** | Every documented error condition has a corresponding test |
| **Regression value** | Test would fail if the behavior under test regressed |
| **Independence** | No test depends on another test's execution or side effects |
| **Determinism** | Tests produce the same result on every run — no flaky tests |
| **Speed** | Unit tests < 1ms, integration tests < 500ms, E2E tests < 5s |

### Test Naming Convention

Test names describe the scenario and expected outcome:

```
[methodName]_[scenario]_[expectedResult]

Examples:
  validateEmail_withValidEmail_returnsTrue
  validateEmail_withMissingAtSign_throwsValidationError
  createUser_withDuplicateEmail_returnsConflictError
  processPayment_whenGatewayTimeout_retriesThreeTimes
```

---

## Tool Selection Guidance

| Ecosystem | Test Runner | Assertion | Mocking | E2E |
|-----------|-------------|-----------|---------|-----|
| TypeScript/Node | Vitest | Built-in | vi.mock | Playwright |
| Python | pytest | Built-in | unittest.mock / pytest-mock | Playwright |
| Go | testing | testify/assert | gomock / testify/mock | — |
| Rust | cargo test | Built-in | mockall | — |
| C# / .NET | xUnit | FluentAssertions | NSubstitute / Moq | Playwright |

---

## Output Format

Structure the test suite delivery as follows:

```markdown
## Test Suite Delivery

### Test Inventory
| Level | Test Count | Pass Rate | Coverage |
|-------|-----------|-----------|----------|
| Unit | [count] | 100% | [line %] |
| Integration | [count] | 100% | [critical paths covered] |
| E2E | [count] | 100% | [flows covered] |

### Test File Manifest
| File | Level | Module Tested | Test Count |
|------|-------|--------------|-----------|
| src/user/user.model.test.ts | Unit | user.model | 12 |
| src/user/user.service.test.ts | Unit | user.service | 8 |
| tests/integration/user-api.test.ts | Integration | user routes | 6 |
| tests/e2e/user-registration.test.ts | E2E | Registration flow | 3 |

### Critical Path Coverage
| Critical Path | Tests | Status |
|--------------|-------|--------|
| User authentication | [test names] | Covered |
| Payment processing | [test names] | Covered |

### Meaningfulness Validation
- Inversion checks passed: [count]/[total]
- All tests have specific assertions: ✓
- No test order dependencies: ✓
- No flaky tests detected: ✓
```

---

## Handoff to Gatekeeper

Submit the test suite through build-management for mandatory
`gatekeeper-build` review. The test suite is not accepted until the gatekeeper
issues `APPROVED`.

The gatekeeper will validate:
- Test meaningfulness (are assertions specific and valuable?)
- Coverage adequacy (are critical paths tested?)
- Test quality (naming, organization, independence)
- Anti-pattern absence (no trivial assertions, no flaky tests)

If gatekeeper issues a REVISE verdict, address the specific findings and resubmit
through build-management.

---

## Additional Resources

### Reference Files

For detailed test strategy and pattern guidance:
- **`references/test-strategy.md`** — Test pyramid and trophy models, coverage targets by test level, test-driven review methodology, property-based testing guidance, contract testing for service boundaries, and framework selection rationale anchored to ISO/IEC 29119 and ISTQB
- **`references/test-patterns.md`** — Arrange-Act-Assert pattern with examples, test fixture management, mocking strategies (when to mock vs use real dependencies), database testing patterns, API testing patterns, snapshot testing guidance, and comprehensive anti-pattern catalog

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: build
   phase: 2
   skill: test-builder
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
