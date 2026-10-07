# The Skills

53 of them. Ten pipelines (design, build and review are the delivery lifecycle),
five cross-cutting components, two Taste skills, and sixteen standalone tools.

The roster is [`skills/team-manifest.yaml`](../skills/team-manifest.yaml); the
flat index with paths is [AGENTS.md](../AGENTS.md).

## Admiral layer (2)

| Skill | What it does |
|---|---|
| **admiral** | The front door: intake, run state, delegation, gate routing, delivery assembly |
| **gatekeeper-admiral** | Cross-stage gate at every boundary |

## Design (9)

| Skill | What it does |
|---|---|
| **commander** | Owns the design pipeline, locks the stack, owns the gatekeeper-design cycle |
| **researcher** | Requirements and domain analysis grounded in the repository |
| **planner** | Milestones, rollout, decision gates, risk handling |
| **architect** | System architecture, API contracts, the frontend design system |
| **engineer** | Implementation spec: delivery slices, dependency order, operational constraints |
| **gatekeeper-design** | Design phase-exit gate; also gates `redesign-review` |
| **redesign** | Owns the redesign pipeline: inventory, taste grilling, four mocks, the user's decision, one living prototype |
| **design-mapper** | Stable-id inventory of the current design with baseline captures; verifies parity |
| **prototyper** | Builds one variant: tokens, framework-free component library, living single-page prototype |

The design system belongs to **architect** ([`design-doctrine.md`](../skills/design-doctrine.md)).

## Build (8)

| Skill | What it does |
|---|---|
| **build-management** | Owns the build pipeline and the gatekeeper-build cycle |
| **bob-the-builder** | Implements the approved scope; no placeholders, no unowned TODOs |
| **test-builder** | Test surface across the scope and the failure paths that matter |
| **security-builder** | Hardening; owns `security_seed` at design and `security_evidence` at build |
| **cross-check-build-confirm** | Completeness cross-check of the build package |
| **debugger** | Root cause of a reproduced build failure; returns a bounded fix |
| **health-check** | Runtime health and startup readiness; produces the `runtime` probe |
| **gatekeeper-build** | Build phase-exit gate |

## Review (11)

| Skill | What it does |
|---|---|
| **code-chief** | Owns the review pipeline, triages findings, recommends the verdict |
| **bug-review** | Correctness defects, broken invariants, crash paths, data corruption |
| **code-review** | Merge readiness, local quality, change risk, clarity |
| **quality-review** | Maintainability, architecture drift, standards, tech-debt pressure |
| **security-review** | Defensive posture, dependency exposure, access control, data handling |
| **cso** | Security leadership; owns the standalone security pipeline and threat model |
| **mr-robot** | Adversarial penetration testing; produces deny-path evidence |
| **frontier** | Frontend performance, accessibility, robustness, component behavior |
| **design-qa** | Visual QA; produces the `rendered_verification` render record |
| **devex-review** | Onboarding, tooling, docs clarity, integration friction |
| **gatekeeper-code** | Review phase-exit gate |

## Cross-cutting (5)

| Skill | What it does |
|---|---|
| **investigate** | Root-cause analysis when the failure shape is unclear; owns the investigation pipeline and returns a bounded fix path to the owning phase |
| **skill-maker** | Creation, review, improvement and packaging of skills and teams |
| **skill-creator** | Drafts and improves skills: authoring, supporting files, evals, packaging |
| **skill-reviewer** | Adversarial quality gate; scores 0 to 100 across ten dimensions |
| **session-memory** | Run record and durable learnings; writes only through `save_run.py` |

## Taste (2)

| Skill | What it does |
|---|---|
| **taste** | Preference intake, canonical writes, effective-profile resolution, the Taste gate submission |
| **taste-review** | Read-only review of provenance, conflicts, redaction, confirmation, persistence safety |

## Standalone tools (16)

Directly callable at any time. `qa`, `qa-only` and `ship` also own a gated
pipeline when `admiral` delegates to them ([routing.md](routing.md)).

### Harness audit (1)

| Skill | What it does |
|---|---|
| **audit-improve** | Audits harness and run state, then routes supported improvements through Admiral and skill-maker |

### Browser automation (4)

| Skill | What it does |
|---|---|
| **browse** | Drives an existing browser session, evidence first |
| **open-browser** | Launches a visible browser workspace, reusing one if available |
| **setup-browser-cookies** | Prepares authenticated session state for protected surfaces |
| **pair-agent** | Pairs a remote collaborator to a browser session with scoped access |

### Release and deployment (4)

| Skill | What it does |
|---|---|
| **ship** | Release orchestration; owns the `deploy-readiness` submission |
| **land-and-deploy** | Merge, rollout, verification, post-release checks, rollback awareness |
| **setup-deploy** | Durable deployment settings, environment conventions, rollback plan |
| **document-release** | Release notes, operational follow-up, documentation trail |

### Safety guardrails (4)

| Skill | What it does |
|---|---|
| **guard** | Intent check and write boundary together |
| **careful** | Confirmation before a destructive or irreversible action |
| **freeze** | Locks a declared path until lifted |
| **unfreeze** | Clears an active protection boundary |

### Testing and QA (3)

| Skill | What it does |
|---|---|
| **qa** | Product testing with evidence, scoped fixes, reruns until stable |
| **qa-only** | Read-only product testing; evidence-backed defect report, no fixes |
| **benchmark** | Comparative performance measurement with repeatable evidence |

## Not skills, but load-bearing

| File | Purpose |
|---|---|
| `gates.yaml` | Ten boundaries: required and artifact-backed evidence, fallbacks, typed records, finding and revise policy, submitters |
| `pipelines.yaml` | Ten pipelines: stages, owners, dependency graphs, scheduling, closing boundary |
| `ownership.yaml`, `save-ownership.yaml` | One writer per artifact; one writer per save path class |
| `team-manifest.yaml` | The roster everything is checked against |
| `runtime-manifest.yaml`, `package-manifest.yaml` | Runtime floor and commands; packaging and delivery contract |
| `tech-stacks/registry.yaml` | 14 stack overlays with pinned versions and digests |
| `execution-contract.md` | The six preamble clauses and the tier table |
| `routing-doctrine.md`, `grill-me-doctrine.md` | Entry routing and session pin; intake interview and ceremony scaling |
| `design-doctrine.md`, `taste-doctrine.md`, `performance-doctrine.md` | Design system; preferences; measured optimization |
| `harness-doctrine.md`, `save-protocol.md`, `mcp-tools.md` | Lifecycle layers; save lifecycle; MCP registry |
| `contracts/` | Evidence standards, handoff templates, workflow protocol, responsibility matrix, universal frameworks, delivery template |
| `harness/hooks/`, `harness/gatekeeper/` | The three hooks and their writers; the two gate validators |
| `scripts/`, `validation/` | Shared tooling; contract test suites |

See [architecture.md](architecture.md), [gatekeepers.md](gatekeepers.md), [harness.md](harness.md).
