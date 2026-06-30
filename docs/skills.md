# Skill Inventory

Supreme Team contains **47 skills** plus a runtime harness and six
doctrine/protocol files. Skills are grouped into the three-stage delivery
pipeline (design, build, review), the cross-cutting Admiral-pipeline components
(investigation, skill-maker, session-memory), and four standalone tool groups
(browser automation, release & deployment, safety guardrails, testing & QA).

## Admiral Layer (2 skills)

| Skill | Role |
|-------|------|
| **admiral** | Primary entry orchestrator — single front door for the full delivery lifecycle |
| **gatekeeper-admiral** | Cross-stage adversarial validator — validates handoff packages at every major delivery boundary |

## Design Sub-Pipeline (6 skills)

| Skill | Role |
|-------|------|
| **commander** | Design pipeline orchestrator — phased delegation, owns gatekeeper-design cycles |
| **researcher** | Requirements gathering and domain analysis — grounds the design in evidence |
| **planner** | Delivery plan — milestones, rollout strategy, decision gates, risk handling |
| **architect** | System architecture and API contracts **and** owner of the frontend/UI visual design system (shadcn/ui tokens, component template, UI/UX spec, design review) |
| **engineer** | Implementation specification — delivery slices, dependency order, operational constraints |
| **gatekeeper-design** | Adversarial design validator (design→build boundary) |

> The frontend/UI design system, previously a separate `designer` skill, is now
> owned by **architect** per `skills/design-doctrine.md`. There is no separate
> `designer` skill and no `tech-stacks/` template library.

## Build Sub-Pipeline (8 skills)

| Skill | Role |
|-------|------|
| **build-management** | Build pipeline orchestrator — owns gatekeeper-build cycles |
| **bob-the-builder** | Implements approved scope as production code without placeholders or unowned TODOs |
| **test-builder** | Builds the automated test surface across intended scope and key failure paths |
| **security-builder** | Hardens the build — unsafe dependencies, insecure patterns, missing controls |
| **cross-check-build-confirm** | Internal completeness cross-check of the build package |
| **debugger** | Isolates the root cause of a reproduced build-phase failure; returns a bounded fix path |
| **health-check** | Runtime health, startup readiness, and environment dependencies |
| **gatekeeper-build** | Adversarial implementation validator (build→review boundary) |

## Review Sub-Pipeline (11 skills)

| Skill | Role |
|-------|------|
| **code-chief** | Review pipeline orchestrator — owns gatekeeper-code cycles |
| **bug-review** | Correctness defects, broken invariants, crash paths, data-corruption risks |
| **code-review** | Merge readiness, local code quality, change risk, and clarity for the change as submitted |
| **quality-review** | Maintainability, architecture drift, standards compliance, tech-debt pressure |
| **security-review** | Defensive security posture, dependency exposure, access-control and data-handling risk |
| **cso** | Security-leadership oversight — governance, accepted risk, release posture, control gaps |
| **mr-robot** | Adversarial penetration testing — exploit paths, abuse cases, chaining conditions |
| **frontier** | Frontend performance, accessibility, robustness, and component behavior |
| **design-qa** | Visual quality assurance — hierarchy, token adherence, responsive behavior, polish |
| **devex-review** | Developer experience — onboarding, tool ergonomics, docs clarity, integration friction |
| **gatekeeper-code** | Adversarial meta-reviewer — validates consolidated review packages (review→delivery boundary) |

## Investigation (1 skill)

| Skill | Role |
|-------|------|
| **investigate** | Disciplined root-cause analysis across code, logs, runtime clues, and environmental evidence when the failure shape is still unclear |

## Skill Maker (3 skills)

| Skill | Role |
|-------|------|
| **skill-maker** | End-to-end orchestrator for creating, reviewing, improving, optimizing, and packaging Claude skills and skill teams |
| **skill-creator** | Drafts and improves skills — SKILL.md authoring, supporting files, evals, trigger tuning, `.skill` packaging |
| **skill-reviewer** | Adversarial quality gate — scores a skill 0–100 across a 10-dimension rubric, returns a prioritized fix list |

## Session Memory (1 skill)

| Skill | Role |
|-------|------|
| **session-memory** | Cross-session state and learnings manager — checkpoints (save/resume) and durable learnings |

## Browser Automation (4 skills · standalone tools)

| Skill | Role |
|-------|------|
| **browse** | Drives an existing browser session via an evidence-first page-reading workflow |
| **open-browser** | Launches a visible browser workspace, reusing an available browser before installing one |
| **setup-browser-cookies** | Imports/prepares authenticated browser session state for protected surfaces |
| **pair-agent** | Pairs a remote collaborator to a browser session with short-lived scoped access |

## Release & Deployment (4 skills · standalone tools)

| Skill | Role |
|-------|------|
| **ship** | End-to-end release orchestration — readiness, launch sequencing, verification, follow-up |
| **land-and-deploy** | Combined merge, rollout, verification, and post-release checks with rollback awareness |
| **setup-deploy** | Durable deployment settings and environment conventions for reuse |
| **document-release** | Release notes, operational follow-up, and product documentation paper trail |

## Safety Guardrails (4 skills · standalone tools)

| Skill | Role |
|-------|------|
| **guard** | Combined intent checks + write boundaries (bundles careful and freeze) |
| **careful** | Intent/confirmation check before destructive or irreversible actions |
| **freeze** | Locks a declared path/boundary from edits until explicitly lifted |
| **unfreeze** | Clears an active protection boundary and records the area is open again |

## Testing & QA (3 skills · standalone tools)

| Skill | Role |
|-------|------|
| **qa** | Systematic product testing that records evidence, applies scoped fixes, and reruns until stable |
| **qa-only** | Read-only product testing — evidence-backed defect report without fixes |
| **benchmark** | Comparative performance/workflow-speed measurement with repeatable evidence |

## Runtime Harness & Doctrine (infrastructure)

Not skills, but load-bearing for the catalog. See [harness.md](harness.md) and
[routing.md](routing.md).

| Component | Purpose |
|-----------|---------|
| `harness/hooks/` | Deterministic `PreToolUse`, `PostToolUse`, and `UserPromptSubmit` enforcement + registration and runtime readiness diagnostics |
| `harness/gatekeeper/` | Shared stdlib gate engine behind every `gatekeeper-*` skill's `scripts/check.py` |
| `routing-doctrine.md` | Entry-routing contract and skill tiers |
| `grill-me-doctrine.md` | Binding intake interview protocol |
| `design-doctrine.md` | Frontend/UI design-system doctrine (owned by architect) |
| `harness-doctrine.md` | Runtime harness doctrine — lifecycle layers, failure taxonomy, non-negotiables |
| `mcp-tools.md` | Global MCP tool registry with a freshness TTL |
| `save-protocol.md` | Persistent save system specification |
