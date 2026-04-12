# TECH STACK OVERLAY: Deno + TypeScript Backend

Applies to: Secure APIs, edge services, full-stack apps with Fresh
Runtime: Deno 2.x | TypeScript (native)

---

## Runtime and Execution Model

- **Language**: TypeScript (natively executed; zero config)
- **Runtime**: Deno 2.x — secure-by-default, built-in tooling, full npm compatibility
- **Concurrency**: Async/await with Tokio-based event loop; Web Worker support
- **Module system**: ESM only; URL imports with global cache (no `node_modules` by default); npm compatibility via `npm:` specifier
- **Security model**: Permission-based — explicit `--allow-net`, `--allow-read`, `--allow-env` flags
- **Configuration**: `deno.json` for imports, tasks, permissions, and compiler options

### Deno Configuration

```json
{
  "compilerOptions": {
    "strict": true,
    "lib": ["deno.window"]
  },
  "imports": {
    "@std/": "jsr:@std/",
    "hono": "npm:hono@^4"
  },
  "tasks": {
    "dev": "deno run --watch --allow-net --allow-env --allow-read src/main.ts",
    "test": "deno test --allow-net --allow-env",
    "lint": "deno lint",
    "fmt": "deno fmt"
  }
}
```

---

## Framework Choices

- **Full-stack SSR**: Fresh — islands architecture with Preact, zero JS by default, `islands/` directory for client components
- **API middleware**: Oak — middleware framework working across Deno, Node.js, Bun, and Cloudflare Workers
- **Lightweight**: Hono — multi-runtime, edge-native
- **Routing strategy**: File-based routing (Fresh) or middleware chain (Oak/Hono)

### Project Structure (Domain-First)

```
project-root/
├── src/
│   ├── auth/
│   │   ├── auth.router.ts
│   │   ├── auth.schema.ts
│   │   ├── auth.service.ts
│   │   └── auth.repository.ts
│   ├── users/
│   ├── shared/
│   │   ├── middleware/
│   │   └── utils/
│   ├── config.ts
│   ├── database.ts
│   └── main.ts
├── tests/
├── deno.json
├── deno.lock
├── Dockerfile
└── .env.example
```

### Fresh Project Structure

```
project-root/
├── components/
├── islands/          # Client-side interactive components
├── routes/           # File-based routing + API routes
│   ├── index.tsx
│   ├── api/
│   │   └── users.ts
│   └── _app.tsx
├── static/
├── fresh.config.ts
├── deno.json
└── .env
```

---

## Data Contracts and Validation

- **Runtime validation**: Zod v4 (via `npm:zod`) — works identically across all TS runtimes
- **Schema location**: Co-located `*.schema.ts` within domain modules
- **Deno style**: Prohibit `index.ts` filenames; require explicit JSDoc for all exports

---

## Persistence and Migrations

- **ORM (portable)**: Prisma — explicitly supports Deno runtime
- **ORM (SQL-first)**: Drizzle — Deno-compatible
- **Built-in**: Deno KV for key-value storage (serverless-friendly)
- **Migration tool**: Prisma Migrate or Drizzle Kit
- **Deno Deploy**: Use Deno KV or connect to external PostgreSQL via connection string

---

## Configuration and Secrets

- **Local development**: `.env` loaded via `--env-file` flag or `Deno.env.get()`
- **Production**: Inject via platform environment variables or secrets manager
- **Validation**: Zod schema validation at startup
- **Permissions**: Document required Deno permissions explicitly for each environment

---

## Testing Strategy

- **Test runner**: `deno test` — built-in, permission-aware, supports BDD
- **Unit tests**: Co-located `*_test.ts` files (Deno convention) or `*.test.ts`
- **Integration tests**: Use Oak/Hono test client or Fresh's test utilities
- **Linting**: `deno lint` — built-in, opinionated
- **Formatting**: `deno fmt` — built-in, consistent

---

## Observability

- **Framework**: OpenTelemetry — built-in support in Deno 2.4+ (stable)
- **Logging**: Structured JSON via `@std/log` or custom logger
- **Metrics**: Prometheus-compatible export via OTel SDK
- **Tracing**: Native OTLP export; W3C TraceContext propagation

---

## Build and Deployment

- **Package manager**: Deno's built-in dependency management (no `node_modules` by default)
- **Linter/formatter**: Built-in `deno lint` + `deno fmt`
- **Build**: `deno compile` for single binary output
- **Container**: Multi-stage Docker with `denoland/deno:alpine`
- **Edge deployment**: Deno Deploy for serverless edge
- **Release strategy**: Trunk-based with feature flags

### Dockerfile Pattern

```dockerfile
FROM denoland/deno:alpine AS builder
WORKDIR /app
COPY deno.json deno.lock ./
RUN deno cache src/main.ts
COPY . .

FROM denoland/deno:alpine AS runtime
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app ./
USER appuser
EXPOSE 3000
CMD ["deno", "run", "--allow-net", "--allow-env", "--allow-read", "src/main.ts"]
```

---

## Security Essentials

- **Permission model**: Deno's built-in permissions prevent unauthorized file/network/env access
- **Supply chain**: URL imports with lock file (`deno.lock`) integrity checking
- **Headers**: Standard security headers via middleware
- **Auth**: Same patterns as Node.js overlay
- **Audit**: Review import URLs; prefer `jsr:` (JSR registry) over raw URLs
