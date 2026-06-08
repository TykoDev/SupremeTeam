# Pipeline Architecture

Supreme Team orchestrates a three-stage delivery pipeline through a single entry
point (**admiral**), with adversarial validation at every phase boundary and a
cross-stage gate at every handoff. Cross-cutting standalone tools (browser
automation, release & deployment, safety guardrails, testing & QA) run outside
the pipeline, and a runtime harness deterministically enforces the parts of the
contract that can be checked mechanically.

## Pipeline Flow

```
 USER REQUEST / EXISTING ARTIFACTS
       |
       v
    +-----------+    intake interview (grill-me) · persisted run · mode probe
    |  ADMIRAL  |    MCP registry freshness · harness hook registration check
    +-----------+
       |
       v
 +---------------------------+     +---------------------+
 | design/commander          | --> | GATEKEEPER-ADMIRAL  |  Handoff 1:
 | researcher -> planner ->  |     | Design -> Build     |  Build-ready?
 | architect -> engineer     |     +---------------------+
 +---------------------------+
       |
       v
 +---------------------------+     +---------------------+
 | build/build-management    | --> | GATEKEEPER-ADMIRAL  |  Handoff 2:
 | bob-the-builder ->        |     | Build -> Review     |  Review-ready?
 | test-builder ->           |     +---------------------+
 | security-builder ->       |
 | cross-check-build-confirm |
 | [debugger] [health-check] |
 +---------------------------+
       |
       v
 +---------------------------+     +---------------------+
 | review/code-chief         | --> | GATEKEEPER-ADMIRAL  |  Handoff 3:
 | bug-review -> code-review |     | Review -> Delivery  |  Delivery-ready?
 | -> quality-review ->      |     +---------------------+
 | security-review -> cso -> |
 | mr-robot -> frontier ->   |
 | design-qa -> devex-review |
 +---------------------------+
       |
       v
  +------------------------+
  | FINAL DELIVERY PACKAGE |
  +------------------------+
```

There is no built-in cloud-provisioning stage. Production rollout is handled by
the standalone **release-and-deployment** tools (`ship`, `land-and-deploy`,
`setup-deploy`, `document-release`), which are invoked directly rather than as a
pipeline stage.

## Admiral

Admiral is the **primary entry orchestrator** — the single front door for the
entire delivery lifecycle, as fixed by `skills/routing-doctrine.md`. Every
delivery-lifecycle request initiates through admiral so that one intake, one
persisted run, and one cross-stage gatekeeper govern the whole pipeline. It:

1. Runs the startup save check, classifies any existing `skillset-saves/` run,
   and resumes an active or orphaned run before starting a new one.
2. Runs the **grill-me intake interview** (`skills/grill-me-doctrine.md`) to reach
   a shared understanding before any delegation.
3. Probes the **execution mode** (sub-agent delegation, file I/O, command
   execution), verifies **harness hook registration**
   (`harness/hooks/verify_registration.py`), and checks **MCP registry freshness**
   (`skills/mcp-tools.md`, default 480h TTL).
4. Classifies the request mode (full, partial, resume, create-skill, create-team),
   then delegates to the owning sub-orchestrator for the earliest incomplete
   boundary.
5. Routes every returned package through **gatekeeper-admiral**, rewinding
   downstream work when upstream approvals drift.
6. Assembles only approved packages into a unified delivery package.

Immediately after scope is confirmed at intake — and before the first
sub-orchestrator delegation — admiral engages **session-memory** to checkpoint
the normalized intake. Every run therefore engages at least two catalog skills
(session-memory plus the first stage owner).

### Trigger Phrases

```
"Run the full pipeline on this idea"
"Design, build, and review this project"
"Take this from idea to reviewed code"
"Run admiral"
"Resume the pipeline"
"Investigate this bug / find the root cause"
"Create a skill / build me a team of skills"
```

## Pipeline Modes

| Mode | Entry condition | Path |
|------|-----------------|------|
| **Full pipeline** | "run the full pipeline", "ship this end to end" | Design → Build → Review → Delivery |
| **Partial pipeline** | "just design", "just review this code" | Only the explicitly requested approved subset |
| **Resume** | Active latest run or existing approved artifacts detected | Start from the earliest incomplete boundary after lock and lineage validation |
| **Create-skill** | "create a skill", "build me a skill" | Intake → skill-maker → Delivery |
| **Create-team** | "create a team", "build me a pipeline" | Intake → skill-maker team mode → Delivery |

Admiral auto-detects existing artifacts. If a design package is provided, it
skips to build. If an existing codebase is provided, it skips to review. A skip
is honored only when the upstream artifact is fully approved, structurally
complete, and valid for the next boundary.

## Execution Modes

Admiral operates in two execution modes depending on the host platform:

- **Agent mode** uses `skills/admiral/agent/agent-manifest.yaml`,
  `agent-protocol.md`, and the adapter docs under `agent/adapters/`
  (`claude.md`, `codex.md`, `copilot.md`) to manage state programmatically,
  delegate sub-agents, and validate boundaries with live tool access.
- **Skill mode** keeps the same stage sequencing, gatekeeper routing, and rewind
  rules but expresses them as instructions the host agent carries out manually.

The detected mode is recorded in the run state and re-probed before every
boundary delegation and on every resume, so resumes never mix autonomous and
instruction-only behavior.

## Design Sub-Pipeline

Primary entry skill: **`commander`** (`skills/design/commander/SKILL.md`)

```
commander -> researcher -> gatekeeper-design -> planner -> gatekeeper-design ->
architect -> gatekeeper-design -> engineer -> gatekeeper-design -> Design Package
```

`architect` also owns the frontend/UI visual design system (design interview,
shadcn/ui token system, component template, UI/UX spec, and adversarial design
review) for user-facing surfaces, per `skills/design-doctrine.md`. There is no
separate `designer` skill and no `tech-stacks/` template library.

Output: Approved Design Package (requirements, plan, architecture, interface
contracts, design system, implementation spec).

## Build Sub-Pipeline

Primary entry skill: **`build-management`** (`skills/build/build-management/SKILL.md`)

```
build-management -> bob-the-builder -> gatekeeper-build ->
test-builder -> gatekeeper-build -> security-builder -> gatekeeper-build ->
cross-check-build-confirm -> gatekeeper-build -> Build Package
```

Utility skills **debugger** and **health-check** are available on demand within
the build sub-pipeline for root-cause repair and runtime/startup health.

Output: Production-ready code, tests, security hardening evidence, completeness
confirmation.

## Review Sub-Pipeline

Primary entry skill: **`code-chief`** (`skills/review/code-chief/SKILL.md`)

```
code-chief -> bug-review -> code-review -> quality-review -> security-review ->
cso* -> mr-robot -> frontier* -> design-qa* -> devex-review* ->
gatekeeper-code -> Review Package

* cso engaged when scope includes security governance / release posture
* frontier / design-qa skipped for backend-only projects with no frontend
* devex-review engaged when targeting developer-facing surfaces
```

Output: Adversarially validated review reports with a merge recommendation.

## Cross-Cutting Subsystems

| Subsystem | Purpose | Reference |
|-----------|---------|-----------|
| **Entry routing** | Makes admiral the enforced front door; defines skill tiers and the active-handoff loop guard | [routing.md](routing.md) · `skills/routing-doctrine.md` |
| **Runtime harness** | Deterministic hooks (action realization, trajectory regulation, entry routing) + the gatekeeper gate engine | [harness.md](harness.md) · `skills/harness-doctrine.md` |
| **Persistent saves** | Cross-session resume, crash recovery, audit trail | [persistent-saves.md](persistent-saves.md) · `skills/save-protocol.md` |
| **MCP registry** | Global inventory of available MCP tools with a freshness TTL checked at intake | `skills/mcp-tools.md` |
| **Standalone tools** | Browser automation, release & deployment, safety guardrails, testing & QA — invoked directly | [direct-invocation.md](direct-invocation.md) |
