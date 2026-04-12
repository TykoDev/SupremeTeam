# Coding Standards Reference

## Framework Alignment

These standards are anchored to:
- **IEEE 730-2026** — Software Quality Assurance Processes
- **ISO/IEC 25010** — Software Quality Model (functional suitability, performance efficiency, compatibility, usability, reliability, security, maintainability, portability)
- **Clean Code** — Robert C. Martin's principles adapted for AI-generated code

---

## 1. Naming Conventions

### General Rules

- Names reveal intent: a reader should understand the purpose without reading the implementation
- Length proportional to scope: loop variables may be short (`i`), module-level constants must be descriptive (`MAX_RETRY_ATTEMPTS`)
- Consistent vocabulary: choose one term per concept and use it everywhere (`user` not sometimes `user`, sometimes `account`, sometimes `member`)
- Avoid encodings: no Hungarian notation, no type prefixes (`strName`, `iCount`)

### Specific Patterns

| Element | Convention | Example |
|---------|-----------|---------|
| Variables | camelCase (JS/TS), snake_case (Python/Rust/Go) | `userEmail`, `user_email` |
| Constants | SCREAMING_SNAKE_CASE | `MAX_RETRY_ATTEMPTS` |
| Functions | Verb-first, describes action | `validateEmail()`, `create_user()` |
| Boolean variables | Question-form prefix | `isActive`, `has_permission` |
| Classes/Types | PascalCase | `UserRepository`, `PaymentService` |
| Files | kebab-case or snake_case (match ecosystem) | `user-service.ts`, `user_service.py` |
| Database tables | snake_case, plural | `user_accounts`, `order_items` |
| API endpoints | kebab-case, plural nouns | `/api/v1/user-accounts` |

### Anti-Patterns

- Generic names: `data`, `info`, `item`, `temp`, `result` — always qualify with domain context
- Abbreviations: `usr`, `mgr`, `cfg` — spell out unless universally understood (`id`, `url`, `api`)
- Numbered variables: `user1`, `user2` — use descriptive qualifiers (`sourceUser`, `targetUser`)

---

## 2. Function Design

### Single Responsibility

Each function does exactly one thing. Test: can the function be described in a single sentence without "and" or "or"?

### Size Guidelines

| Metric | Target | Hard Limit |
|--------|--------|------------|
| Lines of code | 5-15 | 30 |
| Parameters | 1-3 | 5 (use options object beyond 3) |
| Cyclomatic complexity | 1-4 | 10 |
| Nesting depth | 1-2 | 3 |

### Early Returns

Prefer guard clauses over nested conditionals:

```
# PREFER: Guard clauses
function processOrder(order):
    if order is null: return error("Order required")
    if order.items is empty: return error("No items")
    if order.payment is invalid: return error("Invalid payment")
    # Happy path at base indentation
    return executeOrder(order)

# AVOID: Nested conditionals
function processOrder(order):
    if order is not null:
        if order.items is not empty:
            if order.payment is valid:
                return executeOrder(order)
```

### Pure Functions

Prefer pure functions (same input → same output, no side effects) wherever possible. Isolate side effects to explicit boundary functions (repository methods, API calls, file I/O).

---

## 3. Error Handling

### Principles

1. **Fail fast**: Detect errors at the earliest possible point
2. **Fail loud**: Never swallow exceptions silently
3. **Structured errors**: Use typed error objects, not string messages
4. **Context preservation**: Each error handler adds context about what was being attempted

### Patterns

**Boundary validation**: Validate all inputs at system boundaries (API handlers, CLI parsers, message consumers). Internal functions may trust validated data.

```
# BOUNDARY: validate inputs
function handleCreateUser(request):
    validatedInput = validateSchema(request.body, CreateUserSchema)
    if validatedInput.error: return 400 response with validation details
    # Internal functions trust validated data
    user = userService.create(validatedInput.data)
```

**Structured error types**: Define error categories with codes and metadata:

```
ApplicationError
├── ValidationError (code: VALIDATION_FAILED, fields: [...])
├── NotFoundError (code: NOT_FOUND, resource: string, id: string)
├── AuthorizationError (code: FORBIDDEN, requiredPermission: string)
├── ConflictError (code: CONFLICT, existingResource: string)
└── InternalError (code: INTERNAL, cause: Error)
```

**Error propagation**: Let errors bubble up with added context. Do not catch and re-throw without adding information.

### Anti-Patterns

- Empty catch blocks: `catch (e) { }` — always handle or rethrow
- Catch-all handlers: `catch (e) { return "Error" }` — preserve error type information
- Logging and rethrowing: `catch (e) { log(e); throw e }` — log at the final handler only
- Return codes for errors: Use exceptions/Result types, not `return -1`

---

## 4. Documentation Standards

### Inline Comments

- Comment the **"why"**, never the **"what"**
- Delete comments that restate the code
- Keep comments adjacent to the code they explain
- Update comments when code changes — stale comments are worse than no comments

**Acceptable:**
```
// Circuit breaker: retry with exponential backoff because the payment
// gateway rate-limits at 100 req/s and returns 429 without retry-after
```

**Unacceptable:**
```
// Get the user
const user = getUser(id);
// Check if user exists
if (!user) { ... }
```

### Public API Documentation

Every exported function, class, and type requires documentation:

| Language | Format | Required Fields |
|----------|--------|----------------|
| TypeScript/JavaScript | JSDoc | `@param`, `@returns`, `@throws`, `@example` |
| Python | Docstrings (Google/NumPy style) | Args, Returns, Raises, Examples |
| Go | Godoc comments | Parameter descriptions, return descriptions |
| Rust | `///` doc comments | Parameters, panics, examples |

### Module-Level Documentation

Each module (directory containing related files) should have a brief description in its index/barrel file explaining the module's responsibility and public API.

---

## 5. Code Organization

### Single Responsibility at Module Level

Each module owns one domain concept. A `user` module contains everything about users — model, validation, repository, service. It does not contain payment logic even if users make payments.

### Dependency Direction

Dependencies point inward toward the domain:

```
Presentation → Application → Domain ← Infrastructure
(controllers)  (services)   (models)  (repositories)
```

The domain layer has ZERO external dependencies. Infrastructure adapts to domain interfaces, not the other way around.

### Layer Separation

| Layer | Contains | Imports From |
|-------|----------|-------------|
| Domain | Models, validation, business rules | Nothing external |
| Application | Services, use cases, orchestration | Domain |
| Infrastructure | Repositories, external APIs, ORM | Domain, Application |
| Presentation | API routes, controllers, middleware | Application |

### File Organization

Prefer domain-first (by feature) over layer-first (by type):

```
# PREFER: Domain-first
src/
├── user/
│   ├── user.model.ts
│   ├── user.service.ts
│   ├── user.repository.ts
│   └── user.routes.ts
├── order/
│   ├── order.model.ts
│   ├── order.service.ts
│   └── order.routes.ts

# AVOID: Layer-first
src/
├── models/
│   ├── user.model.ts
│   └── order.model.ts
├── services/
│   ├── user.service.ts
│   └── order.service.ts
```

---

## 6. Security Standards

### Input Validation

- Validate ALL external inputs using schema-based validation (Zod, Pydantic, or equivalent)
- Reject unknown fields (strict mode) — do not silently ignore extra data
- Validate types, ranges, lengths, and formats at the boundary

### Output Encoding

- Encode all user-supplied data before rendering in HTML, SQL, shell, or log contexts
- Use parameterized queries exclusively — never string concatenation for SQL
- Sanitize data before logging (strip credentials, tokens, PII)

### Secrets Management

- **NEVER** hardcode credentials, API keys, or tokens in source code
- Use environment variables loaded from `.env` files (excluded from version control)
- Provide `.env.example` with placeholder values documenting required variables
- Use secret management services in production (Vault, AWS Secrets Manager, etc.)

### Dependency Security

- Pin dependency versions (lockfiles committed to version control)
- Audit dependencies for known vulnerabilities before adding
- Prefer well-maintained packages with active security response teams

---

## 7. Performance Standards

### Algorithmic Efficiency

- Choose appropriate data structures: hash maps for lookups, arrays for iteration
- Avoid O(n²) algorithms when O(n log n) or O(n) alternatives exist
- Profile before optimizing — measure, do not guess

### Resource Management

- Close all resources explicitly: database connections, file handles, network sockets
- Use connection pooling for database connections
- Implement timeouts on all external calls (HTTP, database, message queues)
- Paginate list endpoints — never return unbounded result sets

### Caching

- Cache expensive computations with appropriate TTL
- Invalidate caches explicitly when underlying data changes
- Document cache invalidation strategy alongside cache implementation

---

## 8. Testing Standards (For Production Code)

Production code MUST be written to be testable:

- **Dependency injection**: Accept dependencies as parameters, do not instantiate internally
- **Pure functions**: Business logic in pure functions, side effects at boundaries
- **Deterministic behavior**: Avoid implicit dependencies on time, random, or global state
- **Seams**: Provide interfaces/abstractions at boundaries for test doubles when integration tests are impractical
