# Test Patterns Reference

## 1. Arrange-Act-Assert (AAA) Pattern

### Structure

Every test follows this three-phase structure:

```
test "createUser with valid input creates and returns user":
    // ARRANGE — Set up test data and dependencies
    const userInput = { name: "Alice", email: "alice@example.com" }
    const mockRepo = createMockUserRepository()

    // ACT — Execute the function under test
    const result = await createUser(mockRepo, userInput)

    // ASSERT — Verify the expected outcome
    expect(result.name).toBe("Alice")
    expect(result.email).toBe("alice@example.com")
    expect(result.id).toBeDefined()
    expect(mockRepo.create).toHaveBeenCalledWith(userInput)
```

### Rules

- **One ACT per test**: Each test exercises one behavior. Multiple acts indicate the test should be split.
- **Specific assertions**: Assert on concrete values, not just truthiness. `expect(result.email).toBe("alice@example.com")` not `expect(result).toBeTruthy()`.
- **Minimal arrange**: Set up only what is needed for this specific test. Shared setup belongs in `beforeEach` only if truly shared by all tests in the suite.

---

## 2. Test Fixture Management

### Factory Functions

Create test data with factory functions that provide sensible defaults:

```
function createTestUser(overrides = {}):
    return {
        id: generateId(),
        name: "Test User",
        email: "test@example.com",
        role: "user",
        createdAt: new Date("2026-01-01"),
        ...overrides
    }

// Usage
const admin = createTestUser({ role: "admin" })
const alice = createTestUser({ name: "Alice", email: "alice@example.com" })
```

### Builder Pattern (Complex Objects)

For deeply nested or complex test data:

```
const order = OrderBuilder.new()
    .withCustomer(alice)
    .withItem({ product: "Widget", quantity: 3 })
    .withItem({ product: "Gadget", quantity: 1 })
    .withShipping("express")
    .build()
```

### Setup and Teardown

| Scope | Use | Caution |
|-------|-----|---------|
| `beforeAll` / `afterAll` | Expensive setup shared across suite (DB connection, containers) | Never for mutable state |
| `beforeEach` / `afterEach` | Reset mutable state between tests (truncate tables, reset mocks) | Keep minimal |
| Inline arrangement | Test-specific data | Preferred for clarity |

---

## 3. Mocking Strategies

### When to Mock

| Scenario | Mock? | Reason |
|----------|-------|--------|
| External HTTP APIs (Stripe, SendGrid) | **Yes** | Cannot control, slow, costs money |
| System clock / Date | **Yes** | Non-deterministic |
| File system (in unit tests) | **Yes** | Side effects, slow |
| Database (in unit tests) | **Yes** | Isolation, speed |
| Database (in integration tests) | **No** | Test real behavior |
| Internal service classes | **Rarely** | Mocking internals couples tests to implementation |
| Pure functions | **Never** | No side effects to isolate |

### Mock Types

| Type | Purpose | Example |
|------|---------|---------|
| **Stub** | Return predetermined values | `mockRepo.findById = () => testUser` |
| **Spy** | Record calls for verification | `expect(emailService.send).toHaveBeenCalledWith(...)` |
| **Fake** | Simplified working implementation | In-memory repository instead of database |
| **Mock** | Stub + spy with expectations | Full mock object with configured returns and call verification |

### Anti-Pattern: Over-Mocking

When a test requires more than 3 mocks, the code under test likely has too many dependencies. Refactor the production code rather than adding more mocks.

---

## 4. Database Testing Patterns

### Transaction Rollback Pattern

Wrap each test in a transaction that rolls back after the test:

```
beforeEach:
    transaction = db.beginTransaction()

afterEach:
    transaction.rollback()
```

**Advantage**: Fast cleanup, perfect isolation.
**Limitation**: Cannot test transaction behavior itself.

### Truncate Pattern

Truncate all tables between tests:

```
afterEach:
    for table in ALL_TABLES:
        db.truncate(table, cascade: true)
```

**Advantage**: Tests real commit behavior.
**Limitation**: Slower than rollback.

### Test Container Pattern

Spin up a fresh database container for each test suite:

```
beforeAll:
    container = startPostgresContainer()
    db = connect(container.connectionString)
    runMigrations(db)

afterAll:
    container.stop()
```

**Advantage**: Complete isolation, real database engine.
**Limitation**: Slower startup (mitigate with container reuse).

---

## 5. API Testing Patterns

### Request/Response Testing

Test the full HTTP cycle including middleware, validation, and error handling:

```
test "POST /api/users with valid body returns 201":
    const response = await request(app)
        .post("/api/users")
        .send({ name: "Alice", email: "alice@example.com" })
        .expect(201)

    expect(response.body.data.name).toBe("Alice")
    expect(response.body.data.id).toBeDefined()
```

### Error Response Testing

Verify all documented error codes and response formats:

```
test "POST /api/users with duplicate email returns 409":
    // Arrange: create existing user
    await createTestUser({ email: "alice@example.com" })

    // Act
    const response = await request(app)
        .post("/api/users")
        .send({ name: "Alice 2", email: "alice@example.com" })
        .expect(409)

    // Assert: RFC 7807 error format
    expect(response.body.type).toBe("conflict")
    expect(response.body.detail).toContain("email")
```

### Authentication Testing

Test both authenticated and unauthenticated access:

```
test "GET /api/admin without token returns 401":
    await request(app).get("/api/admin").expect(401)

test "GET /api/admin with valid admin token returns 200":
    const token = generateTestToken({ role: "admin" })
    await request(app)
        .get("/api/admin")
        .set("Authorization", `Bearer ${token}`)
        .expect(200)

test "GET /api/admin with user token returns 403":
    const token = generateTestToken({ role: "user" })
    await request(app)
        .get("/api/admin")
        .set("Authorization", `Bearer ${token}`)
        .expect(403)
```

---

## 6. Snapshot Testing

### When Appropriate

- Serialized output (JSON responses, HTML rendering, error messages)
- Configuration file generation
- Code generation output

### When to Avoid

- Frequently changing output (timestamps, random IDs)
- Large complex objects (snapshots become unreadable)
- As a substitute for specific assertions

### Best Practices

- Review every snapshot update — do not blindly accept
- Use inline snapshots for small outputs
- Use file snapshots for large outputs
- Include only stable fields (strip timestamps, IDs)

---

## 7. Comprehensive Anti-Pattern Catalog

### Anti-Pattern: Testing Implementation Details

```
// BAD: Tests internal method calls
test "createUser calls hashPassword":
    const spy = spyOn(crypto, "hashPassword")
    await createUser(input)
    expect(spy).toHaveBeenCalled()

// GOOD: Tests observable behavior
test "createUser stores hashed password":
    const user = await createUser(input)
    const stored = await db.findUser(user.id)
    expect(stored.password).not.toBe(input.password)
    expect(isValidHash(stored.password)).toBe(true)
```

### Anti-Pattern: Flaky Tests

Common causes and fixes:

| Cause | Fix |
|-------|-----|
| Time dependency | Inject clock, use fixed timestamps |
| Random data | Use seeded random or fixed test data |
| Shared mutable state | Isolate state per test |
| Network calls | Mock external services |
| Race conditions | Use proper async/await, never `sleep()` |
| Port conflicts | Use random available ports |

### Anti-Pattern: Trivial Tests

```
// BAD: Tests the language, not the application
test "1 + 1 equals 2":
    expect(1 + 1).toBe(2)

// BAD: Tests getter, not behavior
test "user has name":
    const user = new User("Alice")
    expect(user.name).toBe("Alice")
```

### Anti-Pattern: God Tests

A single test that exercises multiple behaviors:

```
// BAD: Tests create, read, update, and delete in one test
test "user CRUD":
    const user = await createUser(input)     // Create
    const found = await findUser(user.id)    // Read
    await updateUser(user.id, { name: "Bob" }) // Update
    await deleteUser(user.id)                // Delete
    // What exactly failed?

// GOOD: One behavior per test
test "createUser with valid input returns user with id": ...
test "findUser with existing id returns user": ...
test "updateUser changes specified fields": ...
test "deleteUser removes user from database": ...
```

### Anti-Pattern: Test Without Assertions

```
// BAD: Only checks that code doesn't throw
test "processOrder handles large orders":
    await processOrder(largeOrder)
    // No assertions — what was actually verified?

// GOOD: Specific assertion
test "processOrder with large order applies bulk discount":
    const result = await processOrder(largeOrder)
    expect(result.discount).toBe(0.15)
    expect(result.total).toBe(expectedTotal)
```

### Anti-Pattern: Conditional Logic in Tests

```
// BAD: Test contains if/else
test "validate handles all types":
    for type in ["email", "phone", "url"]:
        result = validate(type, testData[type])
        if type == "email":
            expect(result.format).toBe("RFC 5322")
        else if type == "phone":
            expect(result.format).toBe("E.164")

// GOOD: Parameterized tests
test.each([
    ["email", "RFC 5322"],
    ["phone", "E.164"],
    ["url", "RFC 3986"],
])("validate %s returns %s format", (type, format) => {
    expect(validate(type, testData[type]).format).toBe(format)
})
```
