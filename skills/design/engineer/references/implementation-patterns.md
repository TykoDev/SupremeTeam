# Implementation Patterns Reference

## Domain-First Repository Organization

The 2025-2026 consensus: organize by domain/feature, not by file type.
No top-level `controllers/`, `models/`, `services/` directories.

### Anti-Pattern (Layer-First — AVOID)

```
src/
├── controllers/     # All controllers lumped together
│   ├── auth.ts
│   └── users.ts
├── models/          # All models together
│   ├── auth.ts
│   └── users.ts
├── services/        # All services together
│   ├── auth.ts
│   └── users.ts
└── middleware/
```

### Correct Pattern (Domain-First)

```
src/
├── auth/            # Authentication domain
│   ├── router.ts        # Route definitions
│   ├── schemas.ts       # Validation schemas
│   ├── service.ts       # Business logic
│   ├── repository.ts    # Data access
│   └── models.ts        # Domain types
├── users/           # Users domain
│   ├── router.ts
│   ├── schemas.ts
│   ├── service.ts
│   ├── repository.ts
│   └── models.ts
├── orders/          # Orders domain
└── shared/          # Cross-cutting concerns
    ├── middleware/
    ├── errors/
    └── utils/
```

### Benefits
- Feature ownership is clear (one team owns one domain folder)
- Adding/removing features doesn't scatter changes across folders
- Each domain is self-contained and independently testable
- Maps directly to bounded contexts from DDD

---

## ORM Selection Guide

### TypeScript ORMs

| ORM | Approach | Best For | Key Feature |
|-----|---------|---------|-------------|
| **Prisma** | Schema-first | Rapid development, type-safe queries | Auto-generated types from schema |
| **Drizzle** | Code-first | Performance, serverless, SQL control | Zero-overhead SQL generation |
| **Kysely** | Query builder | Complex queries, type safety | Type-safe raw SQL |

### Python ORMs

| ORM | Approach | Best For | Key Feature |
|-----|---------|---------|-------------|
| **SQLAlchemy 2.0** | Declarative/imperative | Complex domains, mature ecosystem | `Mapped` type annotations |
| **SQLModel** | Pydantic + SQLAlchemy | FastAPI projects, rapid dev | Combines validation + ORM |
| **Django ORM** | Active Record | Django projects | Built-in admin, migrations |

### Rust Data Access

| Library | Approach | Best For | Key Feature |
|---------|---------|---------|-------------|
| **SQLx** | SQL-first | Performance, compile-time safety | Query verification at build time |
| **Diesel** | ORM | Maximum type safety | Type-safe query builder |
| **SeaORM** | ActiveRecord | Rapid development | Code generation, async |

### Go Data Access

| Library | Approach | Best For | Key Feature |
|---------|---------|---------|-------------|
| **sqlc** | SQL-first codegen | Performance | Type-safe code from SQL |
| **GORM** | ORM | Prototyping, rapid dev | Full-featured ActiveRecord |
| **Ent** | Code-first | Complex schemas | Compile-time graph traversal |

---

## Validation Patterns

### Principle: Validate at the Boundary, Trust Internally

```
External Input → [VALIDATE] → Internal Processing → [FORMAT] → External Output
                    ↑                                    ↑
               Zod/Pydantic                        Response DTO
```

### TypeScript (Zod)

```typescript
// Define schema once
const createUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  role: z.enum(['admin', 'user']),
});

// Derive type (never duplicate)
type CreateUserInput = z.infer<typeof createUserSchema>;

// Validate at boundary
app.post('/users', (req, res) => {
  const result = createUserSchema.safeParse(req.body);
  if (!result.success) {
    return res.status(400).json({ errors: result.error.flatten() });
  }
  // result.data is fully typed and validated
  const user = await userService.create(result.data);
});
```

### Python (Pydantic)

```python
from pydantic import BaseModel, EmailStr

class CreateUser(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    role: Literal["admin", "user"] = "user"

@app.post("/users")
async def create_user(payload: CreateUser):
    # payload is already validated by FastAPI+Pydantic
    user = await user_service.create(payload)
    return UserResponse.model_validate(user)
```

### Rules

1. Define schemas once at module level — never inside hot loops
2. Use `safeParse` (Zod) for graceful error handling at API boundaries
3. Derive TypeScript types from schemas — never manually duplicate
4. Validate arrays atomically to get index-mapped errors
5. Share schemas between client and server for full-stack validation

---

## Error Handling Patterns

### HTTP Error Response Format (RFC 7807)

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Validation Error",
  "status": 400,
  "detail": "The request body contains invalid fields",
  "instance": "/users",
  "errors": {
    "email": ["Invalid email format"],
    "name": ["Must be at least 1 character"]
  }
}
```

### Error Classification

| HTTP Status | Category | When to Use |
|------------|----------|-------------|
| 400 | Client error | Invalid input, validation failure |
| 401 | Authentication | Missing or invalid credentials |
| 403 | Authorization | Valid credentials, insufficient permissions |
| 404 | Not found | Resource does not exist |
| 409 | Conflict | State conflict (duplicate, concurrent modification) |
| 422 | Unprocessable | Syntactically valid but semantically wrong |
| 429 | Rate limit | Too many requests |
| 500 | Server error | Unexpected internal failure |

### Rules

1. Never expose stack traces or internal details in production error responses
2. Log full error details server-side; return sanitized messages to clients
3. Use error codes (not just messages) for machine-readable error handling
4. Include correlation IDs (traceId) in error responses for debugging
