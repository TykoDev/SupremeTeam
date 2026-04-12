# TECH STACK OVERLAY: Bun + TypeScript Backend

Applies to: High-performance APIs, serverless functions, edge services
Runtime: Bun 1.2+ | TypeScript (native, no transpilation)

---

## Runtime and Execution Model

- **Language**: TypeScript (natively executed — no `ts-node` or transpilation required)
- **Runtime**: Bun 1.2+ — all-in-one runtime, package manager, bundler, test runner
- **Concurrency**: Single-threaded event loop; 3–4× faster startup than Node.js; cold starts ~8ms
- **Module system**: ESM default; CommonJS also supported; no `"type": "module"` needed
- **Configuration**: `bunfig.toml` for runtime settings; `tsconfig.json` for TypeScript

### Key Bun Advantages

- Native TypeScript execution without configuration
- Built-in SQLite driver
- Built-in test runner (`bun test`)
- Built-in package manager (`bun install` — faster than pnpm)
- Automatic `.env` file loading (no `dotenv` needed)

---

## Framework Choices

- **HTTP Framework (default)**: Elysia — full-featured, Express-like syntax, end-to-end type safety, Swagger/OpenAPI integration
- **HTTP Framework (lightweight)**: Hono — multi-runtime, edge-native, minimal overhead
- **Frameworkless**: `Bun.serve()` — maximum throughput for simple APIs
- **Routing strategy**: Elysia plugin-based route groups or Hono route modules
- **Middleware**: Elysia lifecycle hooks or Hono middleware chain

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
│   │   ├── errors/
│   │   └── utils/
│   ├── db/
│   │   ├── schema.ts
│   │   └── migrations/
│   ├── lib/
│   ├── config.ts
│   └── index.ts
├── tests/
├── package.json
├── tsconfig.json
├── bunfig.toml
├── Dockerfile
└── .env.example
```

---

## Data Contracts and Validation

- **Runtime validation**: Zod v4 — same patterns as Node.js overlay
- **Elysia integration**: Elysia has built-in validation via `t` (TypeBox) — use for route-level validation; Zod for shared schemas
- **Schema location**: Co-located `*.schema.ts` within domain modules
- **Type inference**: Derive types from schemas; share between client and server

---

## Persistence and Migrations

- **ORM (portable)**: Prisma — explicitly supports Bun runtime
- **ORM (SQL-first)**: Drizzle — excellent Bun compatibility, zero overhead
- **Built-in**: Bun SQLite driver for embedded database use cases
- **Migration tool**: Prisma Migrate or Drizzle Kit
- **Connection pooling**: Use Prisma's built-in pool or `postgres` package for raw pool

---

## Configuration and Secrets

- **Local development**: `.env` loaded automatically by Bun (no dotenv required)
- **Production**: Inject via secrets manager; never commit `.env` files
- **Validation**: Validate with Zod at startup; fail fast on missing/invalid variables
- **Documentation**: Maintain `.env.example` with all required variables and types

---

## Testing Strategy

- **Test runner**: `bun test` — built-in, Jest-compatible API, fastest option
- **Unit tests**: Co-located `*.test.ts` files
- **Integration tests**: Use Elysia's `handle()` or Hono's test client
- **E2E tests**: Playwright for browser-level scenarios
- **Performance**: Bun test runner starts in milliseconds — ideal for TDD workflow

---

## Observability

- **Framework**: OpenTelemetry SDK (verify Bun compatibility; some native addons may not work)
- **Logging**: Structured JSON logging to stdout
- **Metrics**: Prometheus-compatible export
- **Tracing**: W3C TraceContext; OTLP export
- **Fallback**: If OTel SDK has Bun issues, use Pino + custom metrics endpoint

---

## Build and Deployment

- **Package manager**: `bun install` — fastest available, compatible with npm registry
- **Linter/formatter**: Biome 2.0
- **Build**: `bun build` for bundling; no separate TypeScript compilation needed
- **Container**: Multi-stage Docker build with `oven/bun:alpine` base
- **Release strategy**: Trunk-based development with feature flags
- **Migration gotcha**: Native C++ Node.js addons may not work in Bun — audit dependencies

### Dockerfile Pattern

```dockerfile
FROM oven/bun:1-alpine AS builder
WORKDIR /app
COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile
COPY . .
RUN bun build ./src/index.ts --outdir ./dist --target bun

FROM oven/bun:1-alpine AS runtime
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
USER appuser
EXPOSE 3000
CMD ["bun", "run", "dist/index.js"]
```

---

## Security Essentials

- **Headers**: Use Elysia/Hono security middleware for standard headers
- **Auth**: Same patterns as Node.js — passkeys primary, tokens in httpOnly cookies
- **Input validation**: Zod or Elysia's built-in TypeBox at API boundaries
- **Dependencies**: `bun audit` (or `npm audit` fallback); pin versions
- **Permissions**: Bun does not have Deno-style permissions — rely on container isolation
