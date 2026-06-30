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

> Repository hygiene: `skillset-saves/` is generated Admiral runtime state and
> is intentionally ignored by Git. Do not stage or commit saved runs, locks, audit
> trails, or local scratch directories.

## Entry Routing

`admiral` is the **primary entry orchestrator** — the single front door for the
entire delivery lifecycle (design, build, review, ship, investigate,
checkpoint/resume, gate validation, skill/team creation). Every in-scope request
initiates through `admiral` so that one intake, one persisted run, and one
cross-stage gatekeeper govern the whole pipeline. The binding contract is in
`skills/routing-doctrine.md` and is reinforced deterministically by the
`harness/hooks/user_prompt_submit.py` hook. Standalone Tier-4 tools
(`safety-guardrails/*`, `browser-automation/*`, `release-and-deployment/*`,
`testing-and-qa/*`) run directly, outside this routing.

| Tier | Skills |
|------|--------|
| **Entry orchestrator** | `admiral` |
| **In-scope (must defer to admiral when reached cold)** | `design/commander`, `build/build-management`, `review/code-chief`, `skill-maker`, `investigate`, `session-memory`, `gatekeeper-admiral` |
| **Internal specialists** | every skill under `design/`, `build/`, `review/` not listed above |
| **Standalone tools** | `safety-guardrails/*`, `browser-automation/*`, `release-and-deployment/*`, `testing-and-qa/*` (plus the host `update-config` skill) |

## Admiral Layer (2 skills)

| Skill | Path | Role |
|-------|------|------|
| **admiral** | `skills/admiral/SKILL.md` | Primary entry orchestrator — single front door for the full design→build→review delivery lifecycle, plus investigation, resume, and skill/team creation |
| **gatekeeper-admiral** | `skills/gatekeeper-admiral/SKILL.md` | Cross-stage adversarial validator — validates handoff packages at every major delivery boundary |

## Design Sub-Pipeline (6 skills)

| Skill | Path | Role |
|-------|------|------|
| **commander** | `skills/design/commander/SKILL.md` | Design pipeline orchestrator — delegates to specialists, owns gatekeeper-design cycles |
| **researcher** | `skills/design/researcher/SKILL.md` | Requirements gathering and domain analysis — grounds the design in evidence |
| **planner** | `skills/design/planner/SKILL.md` | Delivery planning with milestones, rollout strategy, decision gates, and risk handling |
| **architect** | `skills/design/architect/SKILL.md` | System architecture (interfaces, API contracts, component boundaries, data flow) **and** owner of the frontend/UI visual design system (shadcn/ui tokens, component template, UI/UX spec, design review) for user-facing surfaces |
| **engineer** | `skills/design/engineer/SKILL.md` | Implementation specification — delivery slices, dependency order, operational constraints |
| **gatekeeper-design** | `skills/design/gatekeeper-design/SKILL.md` | Adversarial quality gate for design deliverables (design→build boundary) |

> The frontend/UI design system that previously lived in a separate `designer`
> skill is now owned by **architect** per `skills/design-doctrine.md`. There is
> no separate `designer` skill and no `tech-stacks/` template library.

## Build Sub-Pipeline (8 skills)

| Skill | Path | Role |
|-------|------|------|
| **build-management** | `skills/build/build-management/SKILL.md` | Build pipeline orchestrator — delegates to specialists, owns gatekeeper-build cycles |
| **bob-the-builder** | `skills/build/bob-the-builder/SKILL.md` | Implements approved scope as production code without placeholders or unowned TODOs |
| **test-builder** | `skills/build/test-builder/SKILL.md` | Builds the automated test surface across intended scope and key failure paths |
| **security-builder** | `skills/build/security-builder/SKILL.md` | Hardens the implementation — unsafe dependencies, insecure patterns, missing controls |
| **cross-check-build-confirm** | `skills/build/cross-check-build-confirm/SKILL.md` | Internal completeness cross-check — verifies the build package is complete and consistent |
| **debugger** | `skills/build/debugger/SKILL.md` | Isolates root causes of a reproduced build-phase failure and returns a bounded fix path |
| **health-check** | `skills/build/health-check/SKILL.md` | Verifies runtime health, startup readiness, and environment dependencies |
| **gatekeeper-build** | `skills/build/gatekeeper-build/SKILL.md` | Adversarial validator of build outputs (build→review boundary) |

## Review Sub-Pipeline (11 skills)

| Skill | Path | Role |
|-------|------|------|
| **code-chief** | `skills/review/code-chief/SKILL.md` | Review pipeline orchestrator — delegates to specialists, owns gatekeeper-code cycles |
| **bug-review** | `skills/review/bug-review/SKILL.md` | Correctness defects, broken invariants, crash paths, data-corruption risks |
| **code-review** | `skills/review/code-review/SKILL.md` | Merge readiness, local code quality, change risk, and clarity for the change as submitted |
| **quality-review** | `skills/review/quality-review/SKILL.md` | Maintainability, architecture drift, standards compliance, tech-debt pressure |
| **security-review** | `skills/review/security-review/SKILL.md` | Defensive security posture, dependency exposure, access-control and data-handling risk |
| **cso** | `skills/review/cso/SKILL.md` | Security-leadership oversight — governance, accepted risk, release posture, control gaps |
| **mr-robot** | `skills/review/mr-robot/SKILL.md` | Adversarial penetration testing — exploit paths, abuse cases, chaining conditions |
| **frontier** | `skills/review/frontier/SKILL.md` | Frontend performance, accessibility, robustness, and component behavior |
| **design-qa** | `skills/review/design-qa/SKILL.md` | Visual quality assurance — hierarchy, token adherence, responsive behavior, interaction polish |
| **devex-review** | `skills/review/devex-review/SKILL.md` | Developer experience — onboarding, tool ergonomics, docs clarity, integration friction |
| **gatekeeper-code** | `skills/review/gatekeeper-code/SKILL.md` | Adversarial meta-reviewer — validates consolidated review packages (review→delivery boundary) |

## Investigation (1 skill)

| Skill | Path | Role |
|-------|------|------|
| **investigate** | `skills/investigate/SKILL.md` | Disciplined root-cause analysis across code, logs, runtime clues, and environmental evidence when the failure shape is still unclear (in-scope Admiral component) |

## Skill Maker (3 skills)

| Skill | Path | Role |
|-------|------|------|
| **skill-maker** | `skills/skill-maker/SKILL.md` | End-to-end orchestrator for creating, reviewing, improving, optimizing, and packaging Claude skills and coordinated skill teams |
| **skill-creator** | `skills/skill-maker/skill-creator/SKILL.md` | Drafts and improves skills — SKILL.md authoring, supporting files, evals, trigger tuning, `.skill` packaging |
| **skill-reviewer** | `skills/skill-maker/skill-reviewer/SKILL.md` | Adversarial quality gate for skills — scores 0–100 across a 10-dimension rubric and returns a prioritized fix list |

## Session Memory (1 skill)

| Skill | Path | Role |
|-------|------|------|
| **session-memory** | `skills/session-memory/SKILL.md` | Cross-session state and learnings manager — checkpoints for resume and durable learnings for accumulated project knowledge |

## Browser Automation (4 skills · standalone tools)

| Skill | Path | Role |
|-------|------|------|
| **browse** | `skills/browser-automation/browse/SKILL.md` | Drives an existing browser session via an evidence-first page-reading workflow |
| **open-browser** | `skills/browser-automation/open-browser/SKILL.md` | Launches a visible browser workspace, reusing an available browser before installing one |
| **setup-browser-cookies** | `skills/browser-automation/setup-browser-cookies/SKILL.md` | Imports/prepares authenticated browser session state for protected surfaces |
| **pair-agent** | `skills/browser-automation/pair-agent/SKILL.md` | Pairs a remote collaborator to a browser session with short-lived scoped access |

## Release & Deployment (4 skills · standalone tools)

| Skill | Path | Role |
|-------|------|------|
| **ship** | `skills/release-and-deployment/ship/SKILL.md` | End-to-end release orchestration — readiness, launch sequencing, verification, follow-up |
| **land-and-deploy** | `skills/release-and-deployment/land-and-deploy/SKILL.md` | Combined merge, rollout, verification, and post-release checks with rollback awareness |
| **setup-deploy** | `skills/release-and-deployment/setup-deploy/SKILL.md` | Defines durable deployment settings and environment conventions for reuse |
| **document-release** | `skills/release-and-deployment/document-release/SKILL.md` | Release notes, operational follow-up, and product documentation paper trail |

## Safety Guardrails (4 skills · standalone tools)

| Skill | Path | Role |
|-------|------|------|
| **guard** | `skills/safety-guardrails/guard/SKILL.md` | Combined intent checks + write boundaries — bundles careful and freeze |
| **careful** | `skills/safety-guardrails/careful/SKILL.md` | Intent/confirmation check before destructive or irreversible actions |
| **freeze** | `skills/safety-guardrails/freeze/SKILL.md` | Locks a declared path/boundary from edits until explicitly lifted |
| **unfreeze** | `skills/safety-guardrails/unfreeze/SKILL.md` | Clears an active protection boundary and records the area is open again |

> The guard/freeze boundary is enforced deterministically by
> `harness/hooks/pre_tool_use.py` via `.harness-state/guard-state.json`.

## Testing & QA (3 skills · standalone tools)

| Skill | Path | Role |
|-------|------|------|
| **qa** | `skills/testing-and-qa/qa/SKILL.md` | Systematic product testing that records evidence, applies scoped fixes, and reruns until stable |
| **qa-only** | `skills/testing-and-qa/qa-only/SKILL.md` | Read-only product testing — evidence-backed defect report without applying fixes |
| **benchmark** | `skills/testing-and-qa/benchmark/SKILL.md` | Comparative performance/workflow-speed measurement with repeatable evidence |

## Runtime Harness (infrastructure, not skills)

Located at `skills/harness/`. Deterministic enforcement of the lifecycle layers
defined in `skills/harness-doctrine.md`. See `skills/harness/hooks/README.md` and
`skills/harness/gatekeeper/README.md`.

| Component | Path | Purpose |
|-----------|------|---------|
| **pre_tool_use.py** | `skills/harness/hooks/pre_tool_use.py` | `PreToolUse` hook — blocks dangerous shell commands and writes into a frozen/guarded boundary (Layer 3 Action Realization) |
| **post_tool_use.py** | `skills/harness/hooks/post_tool_use.py` | `PostToolUse` hook — detects repeated failures, empty-output streaks, oscillation; injects a recovery hint (Layer 4 Trajectory Regulation) |
| **user_prompt_submit.py** | `skills/harness/hooks/user_prompt_submit.py` | `UserPromptSubmit` hook — advisory entry-routing reminder steering lifecycle requests through `admiral` |
| **verify_registration.py** | `skills/harness/hooks/verify_registration.py` | Diagnostic — confirms the three hooks are registered in host-native hook config (run by admiral at intake) |
| **check_readiness.py** | `skills/harness/hooks/check_readiness.py` | Diagnostic — reports Python version, hook registration, and active `skillset-saves` run status after Admiral startup |
| **\_gatecheck.py** | `skills/harness/gatekeeper/_gatecheck.py` | Shared stdlib gate engine behind every `gatekeeper-*` skill's `scripts/check.py` — deterministic, fail-loud package checks |

> Hook registration lives in host-native hook config and is installed only by
> explicit installer opt-in (`-RegisterHooks` / `--register-hooks`). Hooks are stdlib-only and fail open; the gate engine
> fails loud (a gate that cannot prove a package clean must never approve it).

## Doctrine & Protocol Files (skill set root)

| File | Path | Purpose |
|------|------|---------|
| **routing-doctrine.md** | `skills/routing-doctrine.md` | Entry-routing contract: admiral as the front door, skill tiers, active-handoff loop guard, hook reinforcement |
| **grill-me-doctrine.md** | `skills/grill-me-doctrine.md` | Binding intake interview protocol run before any delegation |
| **design-doctrine.md** | `skills/design-doctrine.md` | Frontend/UI design-system doctrine (shadcn/ui token system) owned by architect |
| **harness-doctrine.md** | `skills/harness-doctrine.md` | Runtime harness doctrine — four lifecycle layers, failure taxonomy, engineering non-negotiables |
| **mcp-tools.md** | `skills/mcp-tools.md` | Global MCP tool registry; admiral enforces its `discovery_ttl_hours` freshness rule (default 480h) at intake |
| **save-protocol.md** | `skills/save-protocol.md` | Persistent save system specification — directory structure, file formats, write probe, mode re-check, session pin, resume protocol |

## Directory Layout

```
skills/
├── admiral/                      # Primary entry orchestrator
│   ├── references/              # workflow.md, examples.md
│   └── agent/                   # agent-manifest.yaml, agent-protocol.md, adapters/{claude,codex,copilot}.md
├── gatekeeper-admiral/           # Cross-stage validator (+ scripts/check.py)
├── design/                       # Design sub-pipeline (6 skills)
│   ├── commander/
│   ├── researcher/
│   ├── planner/
│   ├── architect/               # also owns the frontend/UI design system
│   ├── engineer/
│   └── gatekeeper-design/       # + scripts/check.py
├── build/                        # Build sub-pipeline (8 skills)
│   ├── build-management/
│   ├── bob-the-builder/
│   ├── test-builder/
│   ├── security-builder/
│   ├── cross-check-build-confirm/
│   ├── debugger/
│   ├── health-check/
│   └── gatekeeper-build/        # + scripts/check.py
├── review/                       # Review sub-pipeline (11 skills)
│   ├── code-chief/
│   ├── bug-review/
│   ├── code-review/
│   ├── quality-review/
│   ├── security-review/
│   ├── cso/
│   ├── mr-robot/
│   ├── frontier/
│   ├── design-qa/
│   ├── devex-review/
│   └── gatekeeper-code/         # + scripts/check.py
├── investigate/                  # Root-cause analysis (in-scope component)
├── skill-maker/                  # Skill/team creation orchestrator
│   ├── skill-creator/
│   └── skill-reviewer/
├── session-memory/               # Cross-session state & learnings manager
├── browser-automation/           # Standalone tools (4)
│   ├── browse/
│   ├── open-browser/
│   ├── setup-browser-cookies/
│   └── pair-agent/
├── release-and-deployment/       # Standalone tools (4)
│   ├── ship/
│   ├── land-and-deploy/
│   ├── setup-deploy/
│   └── document-release/
├── safety-guardrails/            # Standalone tools (4)
│   ├── guard/
│   ├── careful/
│   ├── freeze/
│   └── unfreeze/
├── testing-and-qa/               # Standalone tools (3)
│   ├── qa/
│   ├── qa-only/
│   └── benchmark/
├── harness/                      # Runtime harness (infrastructure)
│   ├── hooks/                   # pre/post tool-use, user-prompt-submit, verify_registration
│   └── gatekeeper/              # _gatecheck.py deterministic gate engine
├── routing-doctrine.md
├── grill-me-doctrine.md
├── design-doctrine.md
├── harness-doctrine.md
├── mcp-tools.md
└── save-protocol.md
```

**Total: 47 skills** (Admiral 2 · Design 6 · Build 8 · Review 11 · Investigate 1 ·
Skill-Maker 3 · Session-Memory 1 · Browser-Automation 4 · Release-and-Deployment 4 ·
Safety-Guardrails 4 · Testing-and-QA 3), plus the runtime harness and six
doctrine/protocol files.

> **Note on folder depth:** `admiral`, `gatekeeper-admiral`, `investigate`,
> `skill-maker`, and `session-memory` sit directly under `skills/` (depth 2)
> because they are cross-cutting Admiral-pipeline components. Pipeline-stage
> skills nest under their category directory (`design/`, `build/`, `review/`),
> and standalone tools nest under their group directory. This manifest provides
> the authoritative flat index for tool discovery regardless of nesting depth.
