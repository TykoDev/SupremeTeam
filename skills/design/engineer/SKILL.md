---
name: engineer
description: >-
  This skill should be used when the user or commander asks to "create the
  implementation spec", "define the code structure", "design the testing
  strategy", "configure CI/CD", "set up Docker", "define the .env contract",
  "plan the observability setup", "configure code quality tools", "design the
  repository structure", "create the DevOps configuration", or "specify
  security controls". It produces implementation-ready specifications covering
  repository structure, testing strategy, CI/CD pipeline, containerization,
  environment configuration, security controls, and observability setup.
version: 1.0.0
---

# Engineer — Implementation Specification & DevOps

## Purpose

This skill performs Phase 5 (final technical phase) of the Dev Design SkillSet
pipeline. It takes all previously approved deliverables (requirements, project
plan, architecture, frontend spec) and produces the implementation-ready
specification: repository structure, code patterns, testing strategy, CI/CD
pipeline, Docker configuration, environment contracts, security controls,
observability setup, and an explicit record of the inherited stack locks it is
implementing.

## When to Activate

Activate when commander delegates Phase 5 (Implementation Specification)
after all prior phases have been approved by gatekeeper-design, or when a user
directly requests an implementation specification, repository layout, CI/CD
plan, or DevOps configuration for an already defined design.

---

## Execution Modes

### Pipeline Mode (Commander-Delegated)

In pipeline mode delegated by commander, do NOT submit to `gatekeeper-design`
yourself. Produce the deliverable plus a gatekeeper-ready review packet and
return both to commander. Commander owns the review cycle.

### Standalone Mode (Direct User Activation)

When activated directly by a user, this skill owns the final review loop for
its own deliverable. Produce the implementation specification, submit it to
`gatekeeper-design`, address any REVISE findings, and return the approved
result plus the final review report.

---

## Workflow

### Step 1: Record Inherited Stack Locks

Start by copying forward the approved stack locks exactly as received:
- **Backend Stack Lock** from architect
- **Frontend Stack Lock** from designer (if applicable)

Document an **Inherited Stack Locks** section containing:
- The exact overlay filenames selected upstream
- The runtime/framework/database/tooling version tuples being implemented
- Any approved exceptions already recorded upstream

Do not silently substitute stacks, frameworks, or major tooling. Any deviation
from the inherited locks MUST reference a new or updated ADR and be called out
as an exception for gatekeeper review.

### Step 2: Define Repository Structure

Based on the architecture document and inherited stack locks, produce the
complete repository layout using domain-first organization:

```
project-root/
├── src/                    # Application source code
│   ├── [domain-a]/         # Feature/domain modules
│   │   ├── router.*        # Route definitions
│   │   ├── schema.*        # Validation schemas
│   │   ├── service.*       # Business logic
│   │   ├── repository.*    # Data access
│   │   └── models.*        # Domain types
│   ├── [domain-b]/
│   ├── shared/             # Cross-cutting concerns
│   │   ├── middleware/
│   │   ├── errors/
│   │   └── utils/
│   ├── config.*            # Environment config + validation
│   ├── database.*          # DB connection factory
│   └── main.*              # Application entry point
├── tests/                  # Test files
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/                   # Project documentation
│   ├── architecture/
│   ├── decisions/          # ADRs
│   └── api/                # OpenAPI/AsyncAPI specs
├── scripts/                # Build/deployment scripts
├── .github/                # CI/CD workflows
│   └── workflows/
├── docker/                 # Docker configurations
├── [config files]          # package.json, pyproject.toml, Cargo.toml, etc.
├── Dockerfile
├── docker-compose.yml      # Local development
├── .env.example
├── .gitignore
└── README.md
```

Reference the inherited overlay files from the sibling skills-root
`../tech-stacks/` library for stack-specific structure details.

### Step 3: Define Environment Variable Contract

Produce the complete `.env` specification:

```markdown
## Environment Variable Contract

### Required Variables
| Variable | Type | Example | Description |
|----------|------|---------|-------------|
| NODE_ENV | enum | production | Runtime environment |
| PORT | number | 3000 | Server listen port |
| DATABASE_URL | url | postgresql://... | Database connection string |
| JWT_SECRET | string(32+) | [generated] | JWT signing secret |
| LOG_LEVEL | enum | info | Logging verbosity |

### Optional Variables
| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| CORS_ORIGINS | csv | * | Allowed CORS origins |
| RATE_LIMIT_MAX | number | 100 | Max requests per window |
| CACHE_TTL | number | 3600 | Cache TTL in seconds |

### Secrets (Never in .env files in production)
| Secret | Injection Method | Rotation Policy |
|--------|-----------------|----------------|
| DATABASE_URL | Secrets Manager | 90 days |
| JWT_SECRET | Secrets Manager | On security incident |
| API_KEYS | Secrets Manager | 180 days |
```

Validate all variables at startup with schema validation (Zod/Pydantic).
Fail fast on invalid or missing configuration.

### Step 4: Design Testing Strategy

Select and specify the testing approach:

| Test Level | Tools | Scope | Coverage Target |
|-----------|-------|-------|----------------|
| **Unit** | [Vitest/pytest/cargo test] | Individual functions, services | ≥ 80% |
| **Integration** | [Supertest/httpx/reqwest] | API routes with DB | Critical paths |
| **Contract** | [Pact] | Service boundaries | All service interfaces |
| **E2E** | [Playwright] | Full user flows | Happy paths + critical errors |

Consult `references/implementation-patterns.md` for detailed testing patterns.

### Step 5: Design CI/CD Pipeline

Produce the CI/CD pipeline specification:

```yaml
# Pipeline Stages
1. Lint & Typecheck:
   - Run linter (Biome/Ruff/clippy/golangci-lint)
   - Run type checker (tsc/mypy/cargo check)
   
2. Test:
   - Run unit tests with coverage
   - Run integration tests
   - Run contract tests
   
3. Security:
   - Dependency vulnerability scan
   - SAST scan
   - License compliance check
   
4. Build:
   - Build application artifacts
   - Build Docker image
   - Generate SBOM
   
5. Deploy (staging):
   - Deploy to staging environment
   - Run smoke tests
   
6. Deploy (production):
   - Progressive rollout via feature flags
   - Health check gates
   - Automated rollback on failure
```

Consult `references/devops-patterns.md` for pipeline templates.

### Step 6: Configure Containerization

Produce Docker and docker-compose configurations:

**Dockerfile requirements**:
- Multi-stage build (separate build and runtime stages)
- Non-root user (`USER appuser`)
- Copy dependency files before source code (layer caching)
- Slim base image (alpine, slim, scratch, distroless)
- Health check endpoint

**docker-compose.yml for local development**:
- Application service
- Database service with volume persistence
- Cache service (Redis) if needed
- Message broker if needed
- Port mapping and environment variables

### Step 7: Specify Security Controls

Map OWASP Top 10:2025 mitigations to implementation:

| OWASP Risk | Implementation Control |
|-----------|----------------------|
| A01: Broken Access Control | RBAC/ABAC middleware; deny-by-default; verify on every request |
| A02: Cryptographic Failures | TLS 1.3 in transit; AES-256 at rest; PBKDF2/bcrypt for passwords |
| A03: Injection | Parameterized queries (ORM); Zod/Pydantic input validation |
| A04: Insecure Design | Threat model review; rate limiting; business logic abuse prevention |
| A05: Security Misconfiguration | Security headers (CSP, HSTS, X-Frame-Options); disable debug in prod |
| A06: Vulnerable Components | Lockfile pinning; `audit` in CI; SBOM generation; Sigstore signing |
| A07: Authentication Failures | Credential storage; session management; brute-force protection; MFA |
| A08: Data Integrity Failures | Deserialization safety; CI/CD pipeline integrity; update mechanisms |
| A09: Logging Failures | Structured error handling; audit trails; no sensitive data in logs |
| A10: SSRF | Server-side request forgery prevention in URL-fetching, webhook, or redirect logic |

### Step 8: Configure Observability

Specify the OpenTelemetry setup:

```markdown
## Observability Configuration

### Logging
- Format: Structured JSON to stdout
- Fields: timestamp, level, message, traceId, spanId, service, [domain-specific]
- Levels: error, warn, info, debug (configurable via LOG_LEVEL)
- Correlation: Inject traceId into all log entries

### Tracing
- Protocol: OTLP (OpenTelemetry Protocol)
- Propagation: W3C TraceContext
- Auto-instrumentation: HTTP, database, external API calls
- Sampling: 100% of errors, 10% of healthy traffic (tail-based)

### Metrics
- Export: Prometheus format
- Built-in: Request count, latency (p50/p95/p99), error rate, active connections
- Custom: [Domain-specific metrics per SLO]

### Dashboards
- Service health (request rate, error rate, latency)
- Infrastructure (CPU, memory, disk, network)
- Business metrics (per SLO definition from requirements)

### Alerting
- Error rate > 1% for 5 min → Page on-call
- p95 latency > SLO threshold → Warn
- Health check failing → Page immediately
```

### Step 9: Specify Code Quality Tooling

Define the code quality configuration:

| Tool | Purpose | Configuration |
|------|---------|--------------|
| **Biome/Ruff/clippy** | Lint + format | Config in biome.json/pyproject.toml/clippy.toml |
| **TypeScript strict** | Type safety | tsconfig.json with strict: true |
| **Conventional Commits** | Commit format | Commitlint + Husky git hooks |
| **semantic-release** | Versioning | Automated from commit messages |
| **Changesets** | Monorepo versioning | @changesets/cli |

### Step 10: Prepare Review Handoff

Package the complete implementation specification with a review packet containing:
- Source skill: `engineer`
- Deliverable produced
- Approved upstream context used
- Inherited Stack Locks summary with exact overlay file names and version tuples
- Any ADR-backed deviations or unresolved exceptions

If operating in pipeline mode, return the deliverable and review packet to
commander for gatekeeper submission.

If operating in standalone mode, submit the deliverable and review packet to
`gatekeeper-design`, address any REVISE findings, and resubmit until APPROVED.

---

## Output Format

The engineer produces one consolidated deliverable:

**Implementation Specification** containing:
1. Inherited Stack Locks with exact overlay filenames, version tuples, and
   any ADR-backed deviations
2. Repository structure with complete directory layout
3. Environment variable contract (.env specification)
4. Testing strategy with tools and coverage targets
5. CI/CD pipeline specification
6. Docker/containerization configuration
7. Security controls (OWASP mapping)
8. Observability configuration (OpenTelemetry)
9. Code quality tooling configuration

In pipeline mode, return the deliverable with a gatekeeper-ready review packet.

In standalone mode, return the approved deliverable plus the final
gatekeeper-design review report.

---

## Additional Resources

### Reference Files

For detailed patterns and templates:
- **`references/implementation-patterns.md`** — Repository structure patterns, ORM selection, validation patterns, error handling
- **`references/devops-patterns.md`** — CI/CD pipeline templates, Docker patterns, IaC patterns, secrets management

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: design
   phase: 5
   skill: engineer
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. Write the review packet as `review-packet.md` in the same save path directory

3. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
