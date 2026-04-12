# Supreme Team — Skill Manifest

> Authoritative index of all skills in this repository. Tools and agents use this
> file for skill discovery and routing. Paths are relative to the `skills/` directory.

> Installation note: keep the grouped `skills/` source tree intact and install it
> into your tool's configured skill path before invoking any skill. Recommended
> entrypoints are `scripts/install.ps1` on Windows and `scripts/install.sh` on
> macOS/Linux; see `Install.md` for the human and AI-agent installation
> procedure, options, manual fallback, and troubleshooting.

> Discovery prerequisite: assistants do not auto-discover skills from this
> repository checkout unless their configured skill path points here or you have
> copied the tree into `~/.agents/skills/` or `%USERPROFILE%\.agents\skills\`.

## Admiral Layer (2 skills)

| Skill | Path | Role |
|-------|------|------|
| **admiral** | `skills/admiral/SKILL.md` | Top-level pipeline orchestrator — single entry point for the full design-build-review-provision lifecycle |
| **gatekeeper-admiral** | `skills/gatekeeper-admiral/SKILL.md` | Cross-pipeline adversarial validator — validates handoffs between sub-pipelines |

## Design Sub-Pipeline (7 skills)

| Skill | Path | Role |
|-------|------|------|
| **commander** | `skills/design/commander/SKILL.md` | Design pipeline orchestrator — delegates to specialists, owns gatekeeper-design cycles |
| **researcher** | `skills/design/researcher/SKILL.md` | Requirements gathering and domain analysis (SRS, bounded contexts) |
| **planner** | `skills/design/planner/SKILL.md` | Project planning with milestones, risk register, and rollout strategy |
| **architect** | `skills/design/architect/SKILL.md` | System architecture design with C4 diagrams, ADRs, API contracts |
| **designer** | `skills/design/designer/SKILL.md` | UI/UX architecture — frontend strategy, design tokens, component system |
| **engineer** | `skills/design/engineer/SKILL.md` | Implementation specification — repo structure, DevOps, CI/CD, security controls |
| **gatekeeper-design** | `skills/design/gatekeeper-design/SKILL.md` | Adversarial quality gate for design deliverables |

### Tech-Stack Templates (14 files)

Located at `skills/design/tech-stacks/`. These are data files (not skills) providing
backend and frontend stack configurations consumed by architect and designer:

`angular.md` · `astro.md` · `bun-typescript.md` · `deno-typescript.md` ·
`dotnet-aspnet.md` · `go-gin.md` · `node-typescript.md` · `python-fastapi.md` ·
`react-nextjs.md` · `react-tanstack.md` · `rust-axum.md` · `svelte-sveltekit.md` ·
`vite-spa.md` · `vue-nuxt.md`

## Build Sub-Pipeline (6 skills)

| Skill | Path | Role |
|-------|------|------|
| **build-management** | `skills/build/build-management/SKILL.md` | Build pipeline orchestrator — delegates to specialists, owns gatekeeper-build cycles |
| **bob-the-builder** | `skills/build/bob-the-builder/SKILL.md` | Senior development engineer — translates design to production code |
| **test-builder** | `skills/build/test-builder/SKILL.md` | Test engineer — creates comprehensive unit, integration, and E2E test suites |
| **security-builder** | `skills/build/security-builder/SKILL.md` | Security auditor — maps findings to OWASP Top 10, CWE Top 25, NIST SSDF |
| **cross-check-build-confirm** | `skills/build/cross-check-build-confirm/SKILL.md` | Completeness scanner — verifies no scaffolding, TODOs, or placeholders remain |
| **gatekeeper-build** | `skills/build/gatekeeper-build/SKILL.md` | Adversarial validator of build outputs — challenges code, tests, security audits |

## Review Sub-Pipeline (8 skills)

| Skill | Path | Role |
|-------|------|------|
| **code-chief** | `skills/review/code-chief/SKILL.md` | Review pipeline orchestrator — delegates to specialists, owns gatekeeper-code cycles |
| **bug-review** | `skills/review/bug-review/SKILL.md` | Systematic bug detection using CWE-driven checklists and defect classification |
| **code-review** | `skills/review/code-review/SKILL.md` | Holistic 8-dimension code review (design, complexity, tests, naming, style) |
| **quality-review** | `skills/review/quality-review/SKILL.md` | Code health audits — maintainability, standards adherence, architecture drift |
| **security-review** | `skills/review/security-review/SKILL.md` | Vulnerability detection using NIST SSDF, OWASP ASVS, STRIDE threat modeling |
| **mr-robot** | `skills/review/mr-robot/SKILL.md` | Adversarial penetration testing with proof-of-concept exploit chains |
| **frontier** | `skills/review/frontier/SKILL.md` | Frontend performance, accessibility (WCAG 2.2), and security auditor |
| **gatekeeper-code** | `skills/review/gatekeeper-code/SKILL.md` | Adversarial meta-reviewer — validates all specialist review reports |

## Azure Provision Sub-Pipeline (7 skills)

| Skill | Path | Role |
|-------|------|------|
| **azure-provisioner** | `skills/azure/azure-provisioner/SKILL.md` | Azure pipeline orchestrator — delegates to specialists, owns gatekeeper-azure cycles |
| **azure-planner** | `skills/azure/azure-planner/SKILL.md` | Azure deployment strategy, stage sequencing, and runbook planning |
| **azure-architect** | `skills/azure/azure-architect/SKILL.md` | Azure infrastructure design — Bicep templates, resource topology, naming |
| **azure-configurator** | `skills/azure/azure-configurator/SKILL.md` | Azure resource configuration — RBAC, Key Vault, app settings, PostgreSQL auth |
| **azure-deployer** | `skills/azure/azure-deployer/SKILL.md` | Azure deployment execution — Docker builds, ACR push, container deployment |
| **azure-verifier** | `skills/azure/azure-verifier/SKILL.md` | Post-deployment verification — health checks, schema validation, smoke tests |
| **gatekeeper-azure** | `skills/azure/gatekeeper-azure/SKILL.md` | Unified adversarial quality gate for Azure provisioning deliverables |

## Shared Resources

| File | Path | Purpose |
|------|------|---------|
| **save-protocol.md** | `skills/save-protocol.md` | Persistent save system specification for pipeline state, resume, and audit trails |
| **responsibility-matrix.md** | `skills/admiral/references/responsibility-matrix.md` | Unified responsibility, trigger, input/output, escalation, and save ownership matrix for all pipeline components |
| **handoff-templates.md** (cross-pipeline) | `skills/admiral/references/handoff-templates.md` | Cross-pipeline handoff delegation templates used by admiral and gatekeeper-admiral |
| **handoff-templates.md** (universal) | `skills/references/handoff-templates.md` | Universal delegation handoff templates used by all sub-orchestrators for specialist delegations |

> Note: the table above lists the canonical shared handoff-template files.
> Orchestrator-local handoff-template files also exist under
> `skills/design/commander/references/`,
> `skills/build/build-management/references/`,
> `skills/review/code-chief/references/`, and
> `skills/azure/azure-provisioner/references/`.

## Directory Layout

```
skills/
├── admiral/                      # Top-level orchestrator
│   └── references/              # workflow-protocol, handoff-templates, delivery-template, responsibility-matrix
├── gatekeeper-admiral/           # Cross-pipeline validator
├── design/                       # Design sub-pipeline (7 skills + tech-stacks)
│   ├── commander/
│   ├── researcher/
│   ├── planner/
│   ├── architect/
│   ├── designer/
│   ├── engineer/
│   ├── gatekeeper-design/
│   └── tech-stacks/             # 14 stack templates
├── build/                        # Build sub-pipeline (6 skills)
│   ├── build-management/
│   ├── bob-the-builder/
│   ├── test-builder/
│   ├── security-builder/
│   ├── cross-check-build-confirm/
│   └── gatekeeper-build/
├── review/                       # Review sub-pipeline (8 skills)
│   ├── code-chief/
│   ├── bug-review/
│   ├── code-review/
│   ├── quality-review/
│   ├── security-review/
│   ├── mr-robot/
│   ├── frontier/
│   └── gatekeeper-code/
├── azure/                        # Azure provision sub-pipeline (7 skills)
│   ├── azure-provisioner/
│   ├── azure-planner/
│   ├── azure-architect/
│   ├── azure-configurator/
│   ├── azure-deployer/
│   ├── azure-verifier/
│   └── gatekeeper-azure/
├── references/                   # Shared universal handoff templates
└── save-protocol.md              # Persistent save system specification
```

**Total: 30 skills + 14 tech-stack templates**

> **Note on folder depth:** `admiral` and `gatekeeper-admiral` sit directly under
> `skills/` (depth 2) because they orchestrate across all sub-pipelines. All other
> skills are nested under their pipeline category directory (depth 3). This manifest
> provides the authoritative flat index for tool discovery regardless of nesting depth.
