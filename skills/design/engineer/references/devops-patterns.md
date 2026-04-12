# DevOps Patterns Reference

## CI/CD Pipeline Template (GitHub Actions)

### Standard Pipeline

```yaml
name: CI/CD Pipeline
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }

permissions: { contents: read }

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint-and-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-sha>
      - uses: actions/setup-node@<full-sha>
        with: { node-version: '22', cache: 'pnpm' }
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint && pnpm typecheck

  test:
    needs: lint-and-typecheck
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: testdb
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@<full-sha>
      - uses: actions/setup-node@<full-sha>
        with: { node-version: '22', cache: 'pnpm' }
      - run: pnpm install --frozen-lockfile
      - run: pnpm test -- --coverage
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/testdb
      - uses: actions/upload-artifact@<full-sha>
        with:
          name: coverage
          path: coverage/

  security:
    needs: lint-and-typecheck
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-sha>
      - run: pnpm audit --audit-level=high
      - run: pnpm dlx @cyclonedx/cyclonedx-npm --output-file sbom.json

  build:
    needs: [test, security]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<full-sha>
      - run: pnpm install --frozen-lockfile && pnpm build
      - uses: docker/build-push-action@<full-sha>
        with:
          push: ${{ github.ref == 'refs/heads/main' }}
          tags: registry/app:${{ github.sha }}

  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/main'
    environment: staging
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: echo "Deploy to staging environment"
      - name: Run smoke tests
        run: echo "Run smoke tests against staging"

  deploy-production:
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    environment: production
    runs-on: ubuntu-latest
    steps:
      - name: Progressive rollout
        run: echo "Enable feature flags for canary deployment"
```

### Security Best Practices for CI/CD

1. **Pin all actions to full SHA** — never use tags (e.g., `@v4`)
2. **Use OIDC for cloud auth** — no static credentials in secrets
3. **Least-privilege permissions** — `permissions:` at job level
4. **Audit third-party actions** — use `actionlint` and `zizmor`
5. **Immutable artifacts** — sign Docker images with Sigstore
6. **Secret scanning** — enable GitHub secret scanning

---

## Docker Multi-Stage Build Patterns

### Pattern: Node.js Application

```dockerfile
# Stage 1: Install dependencies
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile --prod

# Stage 2: Build application
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

# Stage 3: Production runtime
FROM node:22-alpine AS runtime
WORKDIR /app

# Security: non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# Layer caching: production deps only
COPY --from=deps /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

USER appuser
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "dist/server.js"]
```

### Docker Compose for Local Development

```yaml
version: '3.8'

services:
  app:
    build: .
    ports: ['3000:3000']
    environment:
      - NODE_ENV=development
      - DATABASE_URL=postgresql://dev:dev@db:5432/devdb
      - REDIS_URL=redis://cache:6379
    volumes:
      - ./src:/app/src           # Hot reload
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_started

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: devdb
    ports: ['5432:5432']
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U dev']
      interval: 5s
      timeout: 3s
      retries: 5

  cache:
    image: redis:7-alpine
    ports: ['6379:6379']

volumes:
  pgdata:
```

---

## Infrastructure as Code Patterns

### Decision: OpenTofu vs Pulumi

| Criteria | OpenTofu | Pulumi |
|----------|----------|--------|
| **Language** | HCL (declarative) | TypeScript, Python, Go, C# |
| **Ecosystem** | Largest (Terraform-compatible) | Growing |
| **Learning curve** | HCL syntax to learn | Use existing language skills |
| **State management** | Remote state with locking | Pulumi Cloud or self-managed |
| **Best for** | Infra-focused teams | Dev-heavy teams wanting same language |
| **License** | MPL 2.0 (open source) | Apache 2.0 (open source) |

### IaC Best Practices

1. **Modular structure**: Separate directories per environment
2. **Remote state**: Store state in cloud backend with locking
3. **Secrets**: Never in code — use secrets manager references
4. **Drift detection**: Scheduled `plan` runs to detect manual changes
5. **Policy-as-code**: OPA or Checkov for compliance enforcement
6. **Version pinning**: Pin provider versions in lock files

---

## Secrets Management Strategies

### Development → Production Flow

| Environment | Strategy | Tools |
|------------|----------|-------|
| **Local dev** | `.env` file (gitignored) | dotenv, python-dotenv |
| **CI/CD** | Pipeline secrets | GitHub Actions secrets, OIDC |
| **Staging** | Secrets manager | AWS Secrets Manager, Vault |
| **Production** | Secrets manager + rotation | AWS Secrets Manager, Vault, Infisical |

### Rules

1. **Never** commit secrets to version control
2. **Always** have a `.env.example` with placeholder values
3. **Rotate** secrets on a defined schedule (90-180 days)
4. **Audit** secret access logs
5. **Validate** all secrets exist at application startup
6. **Scope** secrets to minimum required permissions
