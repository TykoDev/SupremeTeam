# Skill Inventory

Supreme Team contains **35 skills** and **14 tech-stack templates**.

## Admiral Layer (2 skills)

| Skill | Role |
|-------|------|
| **admiral** | Top-level pipeline orchestrator — single entry point for the full lifecycle |
| **gatekeeper-admiral** | Cross-pipeline adversarial validator — validates handoffs between sub-pipelines |

## Design Sub-Pipeline (7 skills + tech-stacks)

| Skill | Role | Key Standards |
|-------|------|---------------|
| **commander** | Design pipeline orchestrator | Phased delegation protocol |
| **researcher** | Requirements and domain analysis | ISO 29148, ISO 25010, DDD |
| **planner** | Project strategy and risk management | 12-Factor, CI/CD rollout |
| **architect** | System architecture and API contracts | C4/Arc42, Clean Architecture |
| **designer** | Frontend strategy and UI/UX | WCAG, Core Web Vitals |
| **engineer** | Implementation specification and DevOps | OWASP, OpenTelemetry, SLSA |
| **gatekeeper-design** | Adversarial design validator | 7-dimension review matrix |

The **tech-stacks** library provides 14 backend and frontend stack templates:

`angular.md` · `astro.md` · `bun-typescript.md` · `deno-typescript.md` ·
`dotnet-aspnet.md` · `go-gin.md` · `node-typescript.md` · `python-fastapi.md` ·
`react-nextjs.md` · `react-tanstack.md` · `rust-axum.md` · `svelte-sveltekit.md` ·
`vite-spa.md` · `vue-nuxt.md`

## Build Sub-Pipeline (8 skills)

| Skill | Role | Key Standards |
|-------|------|---------------|
| **build-management** | Build pipeline orchestrator | State machine protocol |
| **bob-the-builder** | Senior development engineer | IEEE 730, ISO/IEC 25010 |
| **test-builder** | Test engineering specialist | ISO/IEC 29119, ISTQB |
| **security-builder** | Code security auditor | OWASP Top 10, CWE Top 25, NIST SSDF |
| **cross-check-build-confirm** | Implementation completeness scanner | Exhaustive pattern catalog |
| **debugger** | Systematic root-cause debugging | Iron-law debugging, 5-phase methodology |
| **health-check** | Code quality dashboard | Composite scoring (type safety, lint, tests, dead code) |
| **gatekeeper-build** | Adversarial implementation validator | 5-type challenge protocol |

## Review Sub-Pipeline (10 skills)

| Skill | Role | Key Standards |
|-------|------|---------------|
| **code-chief** | Review pipeline orchestrator | State machine protocol |
| **bug-review** | Correctness defect detection | CWE Top 25, IEEE 1044, IBM ODC |
| **code-review** | Holistic 8-dimension PR review | Google's code review framework |
| **quality-review** | Maintainability and tech debt | Clean Code, C4, DORA, IEEE 730 |
| **security-review** | Vulnerability detection and compliance | NIST SSDF, OWASP ASVS, STRIDE |
| **mr-robot** | Adversarial penetration testing | OWASP Testing Guide, PTES, CVSS 4.0 |
| **frontier** | Frontend performance and accessibility | Core Web Vitals, WCAG 2.2, CSP |
| **design-qa** | Frontend visual quality assurance | Design tokens, visual hierarchy, CSS audits |
| **devex-review** | Developer experience auditor | TTHW measurement, 8-dimension DX scoring |
| **gatekeeper-code** | Adversarial meta-reviewer | 5-type challenge protocol |

## Azure Provision Sub-Pipeline (7 skills)

| Skill | Role | Key Standards |
|-------|------|---------------|
| **azure-provisioner** | Azure pipeline orchestrator | State machine protocol |
| **azure-planner** | Deployment strategy and runbook planning | Stage sequencing, env-var catalog |
| **azure-architect** | Infrastructure design (Bicep IaC) | Azure naming rules, SKU selection |
| **azure-configurator** | Resource configuration specialist | RBAC, Key Vault, PostgreSQL auth |
| **azure-deployer** | Deployment execution engineer | Docker, ACR, container pipelines |
| **azure-verifier** | Post-deployment verification | Health checks, schema validation |
| **gatekeeper-azure** | Unified Azure deliverable validator | 5-type challenge protocol + final adversarial sweep |

## Session Memory (1 skill)

| Skill | Role | Key Standards |
|-------|------|---------------|
| **session-memory** | Cross-session state and learnings manager | Checkpoints (save/resume), JSONL learnings |
