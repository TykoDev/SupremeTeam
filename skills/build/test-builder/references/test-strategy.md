# Test Strategy Reference

## Framework Alignment

These strategies are anchored to:
- **ISO/IEC 29119** — Software Testing (test process, test design techniques, test documentation)
- **ISTQB** — International Software Testing Qualifications Board (test design, test management)
- **Google Testing Blog** — Practical testing best practices from industry scale

---

## 1. Test Pyramid and Trophy Models

### The Test Pyramid

The classic test pyramid prioritizes fast, isolated tests at the base:

```
        /  E2E  \           Few, slow, high-confidence
       /----------\
      / Integration \       Moderate count, moderate speed
     /----------------\
    /    Unit Tests     \   Many, fast, highly isolated
   /--------------------\
```

**When to use**: API services, libraries, business logic-heavy applications.

### The Test Trophy

The testing trophy emphasizes integration tests in the middle:

```
        /  E2E  \           Few, highest confidence
       /----------\
      / Integration \       Most tests here — test real behavior
     /================\
    /  Unit Tests      \    Fewer, focused on pure logic
   /--------------------\
    Static Analysis         Type checking, linting
```

**When to use**: Frontend applications, applications with many external integrations, microservices.

### Selection Guidance

| Application Type | Recommended Model | Emphasis |
|-----------------|-------------------|----------|
| Backend API service | Pyramid | Heavy unit + integration |
| Frontend SPA | Trophy | Heavy integration + E2E |
| Library/SDK | Pyramid | Heavy unit tests |
| Microservice | Trophy | Heavy integration (contract tests) |
| Data pipeline | Custom | Property-based + integration |

---

## 2. Coverage Targets by Test Level

### Unit Test Coverage

| Metric | Target | Hard Minimum |
|--------|--------|-------------|
| Line coverage | ≥ 80% | 60% |
| Branch coverage | ≥ 70% | 50% |
| Function coverage | ≥ 90% | 75% |

**Coverage exclusions** (do not count against targets):
- Generated code (ORM models, protobuf stubs)
- Configuration files
- Entry points (main, bootstrap)
- Third-party adapter thin wrappers

### Integration Test Coverage

Measure by critical path coverage rather than line coverage:

| Metric | Target |
|--------|--------|
| Critical user paths covered | 100% |
| API endpoints tested | 100% |
| Database operations tested | All CRUD for each entity |
| Error responses tested | All documented error codes |

### E2E Test Coverage

| Metric | Target |
|--------|--------|
| Critical user flows | Top 5-10 flows |
| Happy paths | All primary workflows |
| Key error scenarios | Authentication failure, authorization denial, validation errors |

---

## 3. Test-Driven Review Methodology

When reviewing existing tests for quality:

### Meaningfulness Assessment

For each test, apply these checks:

| Check | Method | Pass Criteria |
|-------|--------|--------------|
| **Inversion** | Invert the production logic | Test fails |
| **Deletion** | Delete the code under test | Test fails |
| **Mutation** | Change a boundary value | Test fails |
| **Assertion specificity** | Check assertion type | Not just "does not throw" |
| **Independence** | Run test in isolation | Same result as in suite |

### Red Flags

- Test always passes regardless of production code
- Test only checks that no exception was thrown
- Test asserts implementation details (internal state, call counts) instead of behavior
- Test has no assertions
- Test depends on execution order
- Test uses `sleep()` or `setTimeout()` for synchronization

---

## 4. Property-Based Testing

### When to Use

- Functions with mathematical properties (sorting, encoding, compression)
- Serialization/deserialization roundtrips
- State machines with known invariants
- Functions where edge cases are hard to enumerate manually

### Key Properties

| Property | Description | Example |
|----------|-------------|---------|
| **Roundtrip** | encode(decode(x)) == x | JSON parse/stringify |
| **Idempotence** | f(f(x)) == f(x) | Normalization, formatting |
| **Commutativity** | f(a, b) == f(b, a) | Set operations, merging |
| **Invariant** | Property holds for all inputs | Sort preserves length |
| **Oracle** | Compare against known-good implementation | Optimized vs naive algorithm |

### Libraries

| Language | Library | Notes |
|----------|---------|-------|
| TypeScript | fast-check | Comprehensive, integrates with Vitest |
| Python | Hypothesis | Mature, excellent shrinking |
| Rust | proptest | Derive macros for custom types |
| Go | rapid | Simple API, good shrinking |

---

## 5. Contract Testing

### Purpose

Verify that services agree on their shared interfaces without requiring both services to be running simultaneously.

### When to Use

- Microservice architectures with HTTP or message-based communication
- Frontend-backend API contracts
- Third-party API integrations (consumer-driven contracts)

### Approach

1. **Consumer writes contract**: The service that calls the API defines expected request/response shapes
2. **Provider verifies contract**: The service that serves the API runs the consumer's contracts as tests
3. **Contract broker**: Store contracts in a shared location (Pact Broker, schema registry)

### Tools

| Ecosystem | Tool |
|-----------|------|
| Language-agnostic | Pact |
| OpenAPI-based | Schemathesis, Dredd |
| gRPC | buf, grpcurl |
| GraphQL | Apollo contract testing |

---

## 6. Database Testing Patterns

### Test Database Strategies

| Strategy | Speed | Fidelity | Setup Complexity |
|----------|-------|----------|-----------------|
| **Test containers** | Medium | High | Medium (Docker required) |
| **In-memory DB** | Fast | Medium (behavior differences) | Low |
| **Shared test DB** | Medium | High | Low (but isolation issues) |
| **SQLite for dev, Postgres for CI** | Fast local | Medium | Low |

**Recommendation**: Test containers for integration tests (real database engine), in-memory for unit tests where DB behavior is not the focus.

### Data Setup Patterns

- **Factory pattern**: Create test data using factory functions with sensible defaults
- **Builder pattern**: Fluent API for constructing complex test objects
- **Fixtures**: Predefined data sets loaded before test suites
- **Seeded databases**: Migration + seed scripts for reproducible state

### Isolation Rules

- Each test starts with a clean state (transaction rollback or truncate)
- Tests NEVER share mutable state
- Parallel test suites use separate database schemas or containers

---

## 7. Performance and Load Testing

### When to Include

- Endpoints with performance SLAs
- Data processing pipelines with throughput requirements
- Real-time features with latency requirements

### Approach

1. **Baseline measurement**: Establish current performance under normal load
2. **Load targets**: Define requests/second, concurrent users, data volume targets
3. **Stress boundaries**: Identify the breaking point (when does latency spike? when do errors start?)
4. **Regression detection**: Compare against baseline on every build

### Tools

| Type | Tool | Use Case |
|------|------|----------|
| HTTP load | k6, Artillery | API endpoint performance |
| Browser | Lighthouse CI | Frontend Core Web Vitals |
| Database | pgbench | Database query performance |
| Custom | Custom scripts | Domain-specific benchmarks |

---

## 8. Test Organization

### Directory Structure

```
project/
├── src/
│   └── user/
│       ├── user.model.ts
│       ├── user.model.test.ts          # Co-located unit tests
│       ├── user.service.ts
│       └── user.service.test.ts
├── tests/
│   ├── integration/
│   │   ├── user-api.test.ts            # Integration tests
│   │   └── setup.ts                    # Shared setup (DB, containers)
│   ├── e2e/
│   │   ├── user-registration.test.ts   # E2E tests
│   │   └── setup.ts                    # E2E setup (browser, server)
│   └── fixtures/
│       └── users.ts                    # Test data factories
```

### Naming Conventions

- Unit test files: `[module].test.ts` (co-located with source)
- Integration test files: `tests/integration/[feature].test.ts`
- E2E test files: `tests/e2e/[flow].test.ts`
- Test utilities: `tests/fixtures/`, `tests/helpers/`
