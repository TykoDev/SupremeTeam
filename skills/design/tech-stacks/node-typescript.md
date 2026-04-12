# TECH STACK OVERLAY: Node.js + TypeScript Backend

Applies to: Backend API services, microservices, full-stack server layers
Runtime: Node.js 22+ LTS | TypeScript 5.x

---

## Runtime and Execution Model

- **Language**: TypeScript 5.x with strict mode enabled
- **Runtime**: Node.js 22+ (LTS) with native ESM (`"type": "module"` in package.json)
- **Concurrency**: Single-threaded event loop with async/await; use Worker Threads for CPU-bound tasks
- **Module system**: ESM as default; use `module: "NodeNext"` in tsconfig with explicit `.js` extensions in imports

### TypeScript Configuration

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "target": "es2022",
    "module": "NodeNext",
    "resolveJsonModule": true,
    "outDir": "./dist",
    "rootDir": "./src"
  }
}
```

---

## Framework Choices

- **HTTP Framework (default)**: Fastify 5.x — 2× Express performance, built-in JSON Schema validation, TypeScript-first
- **HTTP Framework (legacy)**: Express 5.x — largest middleware ecosystem, suitable for brownfield projects
- **Lightweight/Edge**: Hono — multi-runtime, edge-native, minimal overhead
- **Routing strategy**: Domain-grouped route modules registered via plugin pattern (Fastify) or Router (Express)
- **Middleware**: Fastify hooks (`onRequest`, `preHandler`, `onSend`) or Express middleware chain

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
│   │   ├── users.router.ts
│   │   ├── users.schema.ts
│   │   ├── users.service.ts
│   │   └── users.repository.ts
│   ├── shared/
│   │   ├── middleware/
│   │   ├── errors/
│   │   └── utils/
│   ├── config.ts
│   ├── database.ts
│   └── server.ts
├── tests/
├── package.json
├── tsconfig.json
├── biome.json
├── Dockerfile
└── .env.example
```

---

## Data Contracts and Validation

- **Runtime validation**: Zod v4 — TypeScript-first, ~12KB, JIT compilation, 78+ integrations
- **Alternative (bundle-sensitive)**: Valibot — ~1KB for basic usage, 2× faster than Zod v3
- **Schema location**: Co-located `*.schema.ts` files within each domain module
- **Validation boundary**: Validate all external input at API boundary; trust data internally after validation
- **Type inference**: Use `z.infer<typeof schema>` to derive TypeScript types from Zod schemas

```typescript
// users/users.schema.ts
import { z } from 'zod';

export const createUserSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  role: z.enum(['admin', 'user', 'viewer']),
});

export type CreateUserInput = z.infer<typeof createUserSchema>;
```

---

## Persistence and Migrations

- **ORM (type-safe, rapid dev)**: Prisma — best DX, type-safe queries, visual migrations, schema-first
- **ORM (SQL-first, performance)**: Drizzle — lightweight, zero-overhead SQL generation, code-first schemas
- **Migration tool**: Prisma Migrate or Drizzle Kit depending on ORM choice
- **Connection pooling**: Use connection pool (Prisma default) or `pg` pool for raw queries
- **Query performance**: Use `select` projections, avoid N+1 with eager loading, use query analysis

### Prisma Schema Pattern

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String
  role      Role     @default(USER)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

enum Role {
  ADMIN
  USER
  VIEWER
}
```

---

## Configuration and Secrets

- **Local development**: `.env` file (gitignored) loaded via `dotenv` or Node 22+ built-in DotEnv
- **Production**: Inject via secrets manager (AWS Secrets Manager, Infisical, Doppler, HashiCorp Vault)
- **Validation**: Validate all environment variables at startup with Zod; fail fast on invalid config

```typescript
// config.ts
import { z } from 'zod';

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']),
  PORT: z.coerce.number().default(3000),
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export const env = envSchema.parse(process.env);
```

---

## Testing Strategy

- **Test runner**: Vitest — 4× faster cold starts than Jest, native ESM/TS support
- **Unit tests**: Co-located `*.test.ts` or in `/tests/unit/`
- **Integration tests**: Test API routes with `supertest` or Fastify's `inject()` method
- **E2E tests**: Playwright for full-stack scenarios
- **Contract tests**: Pact for microservice boundary contracts
- **Test DB**: Use Docker containers via Testcontainers or in-memory SQLite for fast tests

---

## Observability

- **Framework**: OpenTelemetry SDK for Node.js (`@opentelemetry/sdk-node`)
- **Auto-instrumentation**: `@opentelemetry/auto-instrumentations-node` for zero-code tracing
- **Logging**: Pino (structured JSON) with OpenTelemetry log correlation
- **Metrics**: Prometheus-format via `@opentelemetry/exporter-prometheus`
- **Tracing**: W3C TraceContext propagation; OTLP export to Grafana Tempo
- **Conventions**: Follow OpenTelemetry semantic conventions for attribute naming

---

## Build and Deployment

- **Package manager**: pnpm — strict dependency resolution, 70% disk savings, excellent monorepo support
- **Linter/formatter**: Biome 2.0 — single tool replacing ESLint + Prettier, 10-100× faster
- **Build**: `tsc` for type checking; `esbuild` or `tsup` for fast bundling
- **Container**: Multi-stage Docker build with `node:22-alpine` base
- **Release strategy**: Trunk-based development with feature flags (OpenFeature)
- **CI/CD**: GitHub Actions with SHA-pinned actions, OIDC cloud auth, least-privilege permissions

### Dockerfile Pattern

```dockerfile
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:22-alpine AS runtime
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./
USER appuser
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

---

## Security Essentials

- **Headers**: helmet middleware for Content-Security-Policy, HSTS, X-Frame-Options
- **Auth**: Passkeys primary + email/password fallback; access tokens in memory, refresh in httpOnly cookies
- **Input validation**: Zod at every API boundary; never trust client data
- **Dependencies**: Audit with `pnpm audit`; pin versions; SBOM generation with SPDX
- **Rate limiting**: Use `@fastify/rate-limit` or express-rate-limit
