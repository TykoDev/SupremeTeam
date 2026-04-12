# Implementation Patterns Reference

## 1. Domain-First File Organization

### Principle

Organize code by business domain, not by technical layer. Each domain module is a self-contained unit with its own model, service, repository, and API layer.

### Standard Structure

```
src/
├── config/                    # Application configuration
│   ├── env.ts                 # Environment variable parsing and validation
│   ├── database.ts            # Database connection configuration
│   └── server.ts              # Server configuration
│
├── shared/                    # Cross-cutting concerns
│   ├── errors/                # Structured error types
│   ├── middleware/             # HTTP middleware (auth, logging, error handling)
│   ├── types/                 # Shared type definitions
│   └── utils/                 # Pure utility functions
│
├── [domain-module]/           # One directory per domain concept
│   ├── [domain].model.ts      # Domain model, types, validation schemas
│   ├── [domain].service.ts    # Business logic and orchestration
│   ├── [domain].repository.ts # Data access layer
│   ├── [domain].routes.ts     # API endpoint definitions
│   └── [domain].test.ts       # Tests co-located with source
│
├── app.ts                     # Application bootstrap and middleware registration
└── server.ts                  # Entry point
```

### Module Boundary Rules

- Each module exports a public API through an index/barrel file
- Modules communicate through their public APIs, never by importing internal files
- Circular dependencies between modules indicate a design problem — resolve by extracting shared logic to `shared/`

---

## 2. Repository Pattern

### Purpose

Decouple domain logic from data storage. The domain layer defines repository interfaces; the infrastructure layer implements them.

### Interface Definition

```
interface UserRepository:
    findById(id: string): User | null
    findByEmail(email: string): User | null
    create(data: CreateUserInput): User
    update(id: string, data: UpdateUserInput): User
    delete(id: string): void
    list(filter: UserFilter, pagination: Pagination): PaginatedResult<User>
```

### Implementation Guidelines

| Guideline | Rationale |
|-----------|-----------|
| One repository per aggregate root | Prevents data access sprawl |
| Return domain models, not ORM entities | Keeps domain layer clean |
| Handle transactions at the service layer | Services orchestrate, repositories execute |
| Use query builders for complex queries | Avoid raw SQL concatenation |
| Paginate all list operations | Prevent unbounded result sets |

### ORM Selection Guidance

| Language | Recommended | Notes |
|----------|------------|-------|
| TypeScript | Drizzle ORM | Type-safe, SQL-first, thin abstraction |
| Python | SQLAlchemy 2.0 | Mature, flexible, supports both ORM and Core |
| Go | sqlc or GORM | sqlc for type-safe SQL; GORM for rapid development |
| Rust | sqlx or Diesel | sqlx for async; Diesel for compile-time safety |
| C# | Entity Framework Core | First-party, migrations, LINQ |

---

## 3. Validation Patterns

### Boundary Validation

Validate at system boundaries — where external data enters the application:

1. **API endpoints**: Validate request body, query params, path params, headers
2. **Message consumers**: Validate message payload before processing
3. **File uploads**: Validate file type, size, and content before processing
4. **Configuration**: Validate environment variables at startup — fail fast if invalid

### Schema-Based Validation

Use schema libraries that provide both runtime validation and static type inference:

| Language | Library | Key Feature |
|----------|---------|-------------|
| TypeScript | Zod | Schema → TypeScript type inference |
| Python | Pydantic v2 | Schema → dataclass with validation |
| Go | go-playground/validator | Struct tag validation |
| Rust | serde + validator | Derive macros for deserialization + validation |

### Validation Rules

- **Strict mode**: Reject unexpected fields — do not silently strip them
- **Coercion**: Perform type coercion explicitly (string → number) where appropriate
- **Nested validation**: Validate nested objects and arrays recursively
- **Custom validators**: Use custom validation functions for business rules (email format, phone number, date ranges)
- **Error messages**: Return field-specific errors with human-readable messages

---

## 4. Dependency Injection

### Purpose

Decouple component creation from component usage. Components declare dependencies as constructor or function parameters rather than instantiating them internally.

### Patterns by Language

**Constructor injection (classes):**
```
class UserService:
    constructor(
        private userRepo: UserRepository,
        private emailService: EmailService,
        private logger: Logger
    )
```

**Function injection (functional):**
```
function createUserHandler(deps: { userRepo, emailService, logger }):
    return async (request) => ...
```

**Composition root:** Wire all dependencies at application startup in a single composition root file:
```
# composition-root.ts
const db = createDatabase(config)
const userRepo = new PostgresUserRepository(db)
const emailService = new SmtpEmailService(config.smtp)
const userService = new UserService(userRepo, emailService, logger)
const userRoutes = createUserRoutes(userService)
```

### Avoid

- Service locator pattern (hides dependencies, complicates testing)
- Global singletons (implicit shared state)
- Auto-wiring DI containers in simple applications (unnecessary complexity)

---

## 5. Configuration Management

### Environment Variables

- Parse and validate ALL environment variables at application startup
- Fail fast with descriptive error messages for missing or invalid values
- Provide an `.env.example` file documenting every required variable with placeholder values
- Group variables by concern (database, auth, external services, feature flags)

### Configuration Structure

```
config/
├── env.ts          # Parse and validate environment variables
├── database.ts     # Database-specific configuration
├── auth.ts         # Authentication configuration
└── index.ts        # Export unified config object
```

### Configuration Hierarchy

```
Default values → .env file → Environment variables → CLI arguments
(lowest priority)                              (highest priority)
```

---

## 6. Database Migration Patterns

### Migration Rules

1. **Forward-only**: Every migration has an up function. Down functions are optional but recommended for development
2. **Atomic**: Each migration is a single transaction. If any statement fails, the entire migration rolls back
3. **Idempotent**: Migrations check current state before applying changes
4. **Numbered sequentially**: Use timestamps or sequential numbers for ordering
5. **Descriptive names**: `20260405_create_user_accounts_table`, not `migration_001`

### Migration Structure

```
migrations/
├── 20260405_001_create_user_accounts.sql
├── 20260405_002_create_order_items.sql
├── 20260406_001_add_user_email_index.sql
└── 20260406_002_add_order_status_enum.sql
```

### Safety Rules

- **Never modify a deployed migration**: Create a new migration instead
- **Test migrations against production-like data**: Empty-database testing misses constraint violations
- **Include rollback testing**: Verify down migrations actually reverse the change
- **Add NOT NULL with defaults**: Never add a NOT NULL column without a DEFAULT to a table with existing data

---

## 7. API Implementation Patterns

### REST API Conventions

| Aspect | Convention |
|--------|-----------|
| URL structure | `/api/v[N]/[resource-plural]/[id]` |
| Methods | GET (read), POST (create), PUT (full update), PATCH (partial update), DELETE (remove) |
| Status codes | 200 OK, 201 Created, 204 No Content, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 409 Conflict, 422 Unprocessable Entity, 500 Internal Server Error |
| Error format | RFC 7807 Problem Details: `{ type, title, status, detail, instance }` |
| Pagination | Cursor-based preferred; offset-based acceptable. Include `total`, `next`, `previous` |
| Filtering | Query parameters: `?status=active&sort=-createdAt&limit=20` |
| Versioning | URL path versioning (`/api/v1/`) for simplicity |

### Request/Response Pattern

```
# Request validation → Service call → Response formatting

async function handleCreateUser(request):
    # 1. Validate input
    input = validate(request.body, CreateUserSchema)

    # 2. Execute business logic
    user = await userService.create(input)

    # 3. Format response
    return response(201, { data: formatUser(user) })
```

### Middleware Stack

Apply middleware in consistent order:

```
Request → CORS → Rate Limit → Auth → Validation → Handler → Error Handler → Response
```

---

## 8. Cross-Cutting Concerns

### Logging

- Use structured logging (JSON format) in production
- Include correlation IDs for request tracing
- Log at appropriate levels: ERROR (failures), WARN (degraded), INFO (business events), DEBUG (development only)
- Never log sensitive data (passwords, tokens, PII)

### Health Checks

Implement health check endpoints for orchestration:

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /health` | Liveness check | 200 if process is running |
| `GET /health/ready` | Readiness check | 200 if dependencies are connected |

### Graceful Shutdown

Handle process signals (SIGTERM, SIGINT) to:
1. Stop accepting new connections
2. Complete in-flight requests (with timeout)
3. Close database connections and external clients
4. Exit with code 0
