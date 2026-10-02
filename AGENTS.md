# Supreme Team Skill Manifest

The flat index of every skill in this repository, for tools and agents that are
pointed at a checkout. This file is a checkout-only index: the installers do not
copy it, and no host discovers skills from it. All paths are relative to the
repository root; in an installed copy `skills/` is the install root (see
[Install.md](Install.md#paths-and-the-python-command)).

**Install first.** Assistants find skills through their own skill directories, so
install the tree (the installers copy `skills/` into `~/.agents/skills/`, or
`%USERPROFILE%\.agents\skills\`, and mirror it into each host's directory) and keep
the grouped layout intact. A host that scans one level deep registers the 22
skills at the install root by name; the 31 nested specialists are reached by path
through the skill that delegates to them. See [Install.md](Install.md).

**Do not commit runtime state.** `skillset-saves/` and `.harness-state/` are
generated and Git-ignored. Saved runs, locks, audit trails, and guard records stay
out of version control.

## Entry routing

`admiral` is the single front door. Every in-scope request starts there so one
intake, one persisted run, and one gate govern the whole pipeline. The binding
contract is `skills/routing-doctrine.md`, reinforced by
`skills/harness/hooks/user_prompt_submit.py`.

Precedence: explicit slash command or standalone tool, then an active session pin,
then the Tier 0 fast path for minor reversible tasks, then `admiral`, then
ordinary conversation.

The classes are the ones in `skills/routing-doctrine.md` (Routing classes), which
is the table the tests compare with the roster; this table repeats it and the
doctrine wins where they differ.

| Routing class | Skills |
|---|---|
| Entry orchestrator | `admiral` |
| Pipeline owners (must defer) | `design/commander`, `build/build-management`, `review/code-chief`, `review/cso`, `investigate`, `design/redesign`, `skill-maker`, `taste` |
| Dual-mode entry | `qa`, `qa-only`, `ship` |
| Gatekeepers (must defer) | `gatekeeper-admiral`, `design/gatekeeper-design`, `build/gatekeeper-build`, `review/gatekeeper-code` |
| Session memory | `session-memory` |
| Internal specialists | every skill under `design/`, `build/`, `review/` not named above; `taste/taste-review`; `skill-maker/skill-creator`; `skill-maker/skill-reviewer` |
| Standalone tools | `audit-improve`, `careful`, `freeze`, `guard`, `unfreeze`, `browse`, `open-browser`, `setup-browser-cookies`, `pair-agent`, `benchmark`, `setup-deploy`, `land-and-deploy`, `document-release` |

"Must defer" and "dual-mode" are about how a skill is reached cold; the doctrine
defines both. Pipelines, owners and boundaries are in the next section.

## Pipelines and gate boundaries

Declared in `skills/pipelines.yaml`, gated by `skills/gates.yaml`.

| Pipeline | Owner | Closes at |
|---|---|---|
| `design` | `commander` | `design-to-build` |
| `redesign` | `redesign` | `redesign-review` |
| `build` | `build-management` | `build-to-review` |
| `review` | `code-chief` | `review-to-delivery` |
| `security` | `cso` | `security-review` |
| `investigation` | `investigate` | `investigation-review` |
| `qa` | `qa` | `qa-review` |
| `taste` | `taste` | `taste-review` |
| `skill-creation` | `skill-maker` | `skill-maker-to-delivery` |
| `release` | `ship` | `deploy-readiness` |

## The 53 skills

### Admiral layer (2)

| Skill | Path | Role |
|---|---|---|
| **admiral** | `skills/admiral/SKILL.md` | Entry orchestrator for the full lifecycle, plus investigation, security, QA, resume, and skill or team creation |
| **gatekeeper-admiral** | `skills/gatekeeper-admiral/SKILL.md` | Cross-stage adversarial validator at every delivery boundary |

### Design (9)

| Skill | Path | Role |
|---|---|---|
| **commander** | `skills/design/commander/SKILL.md` | Pipeline owner; delegates specialists, locks the stack, owns gatekeeper-design cycles |
| **researcher** | `skills/design/researcher/SKILL.md` | Requirements and domain analysis grounded in observed evidence |
| **planner** | `skills/design/planner/SKILL.md` | Milestones, rollout, decision gates, risk handling |
| **architect** | `skills/design/architect/SKILL.md` | System architecture, interface contracts, and the frontend design system |
| **engineer** | `skills/design/engineer/SKILL.md` | Implementation spec: delivery slices, dependency order, operational constraints |
| **gatekeeper-design** | `skills/design/gatekeeper-design/SKILL.md` | Design phase-exit validator; also gates `redesign-review` |
| **redesign** | `skills/design/redesign/SKILL.md` | Redesign pipeline owner: inventory, taste grilling, four design-system mocks, comparison, the user's decision, then one living prototype for the selected direction |
| **design-mapper** | `skills/design/design-mapper/SKILL.md` | Records the current design as a stable-id inventory with baseline captures; verifies variant parity |
| **prototyper** | `skills/design/prototyper/SKILL.md` | Builds one design-system variant: tokens, framework-free component library, living single-page prototype |

The UI design system belongs to **architect** per `skills/design-doctrine.md`.
There is no separate `designer` skill. `skills/tech-stacks/` is a resource library
of 14 overlays behind `stack_lock`, not a skill.

### Build (8)

| Skill | Path | Role |
|---|---|---|
| **build-management** | `skills/build/build-management/SKILL.md` | Pipeline owner; owns gatekeeper-build cycles |
| **bob-the-builder** | `skills/build/bob-the-builder/SKILL.md` | Implements approved scope without placeholders or unowned TODOs |
| **test-builder** | `skills/build/test-builder/SKILL.md` | Automated test surface across scope and key failure paths |
| **security-builder** | `skills/build/security-builder/SKILL.md` | Hardening; owns `security_seed` at design and `security_evidence` at build |
| **cross-check-build-confirm** | `skills/build/cross-check-build-confirm/SKILL.md` | Internal completeness cross-check of the build package |
| **debugger** | `skills/build/debugger/SKILL.md` | Root cause of a reproduced build failure; returns a bounded fix path |
| **health-check** | `skills/build/health-check/SKILL.md` | Runtime health and startup readiness; produces the `runtime` probe |
| **gatekeeper-build** | `skills/build/gatekeeper-build/SKILL.md` | Build phase-exit validator |

### Review (11)

| Skill | Path | Role |
|---|---|---|
| **code-chief** | `skills/review/code-chief/SKILL.md` | Pipeline owner; finding triage and the verdict recommendation |
| **bug-review** | `skills/review/bug-review/SKILL.md` | Correctness defects, broken invariants, crash paths, data corruption |
| **code-review** | `skills/review/code-review/SKILL.md` | Merge readiness, local quality, change risk, clarity |
| **quality-review** | `skills/review/quality-review/SKILL.md` | Maintainability, architecture drift, standards, tech-debt pressure |
| **security-review** | `skills/review/security-review/SKILL.md` | Defensive posture, dependency exposure, access control, data handling |
| **cso** | `skills/review/cso/SKILL.md` | Security leadership; owns the standalone security pipeline and threat model |
| **mr-robot** | `skills/review/mr-robot/SKILL.md` | Adversarial penetration testing; produces deny-path evidence |
| **frontier** | `skills/review/frontier/SKILL.md` | Frontend performance, accessibility, robustness, component behavior |
| **design-qa** | `skills/review/design-qa/SKILL.md` | Visual QA; produces the `rendered_verification` render record |
| **devex-review** | `skills/review/devex-review/SKILL.md` | Onboarding, tooling, docs clarity, integration friction |
| **gatekeeper-code** | `skills/review/gatekeeper-code/SKILL.md` | Review phase-exit validator |

### Cross-cutting (5)

| Skill | Path | Role |
|---|---|---|
| **investigate** | `skills/investigate/SKILL.md` | Root-cause analysis when the failure shape is unclear; returns a bounded fix path to the owning phase |
| **skill-maker** | `skills/skill-maker/SKILL.md` | Creating, reviewing, and packaging skills and coordinated teams |
| **skill-creator** | `skills/skill-maker/skill-creator/SKILL.md` | Drafts and improves skills: authoring, supporting files, evals, packaging |
| **skill-reviewer** | `skills/skill-maker/skill-reviewer/SKILL.md` | Adversarial quality gate; scores 0 to 100 across ten rubric dimensions |
| **session-memory** | `skills/session-memory/SKILL.md` | Owns the run record and durable learnings; writes only through `harness/hooks/save_run.py` |

### Taste (2)

| Skill | Path | Role |
|---|---|---|
| **taste** | `skills/taste/SKILL.md` | Preference lifecycle pipeline owner, canonical writer, consumer handoff owner, and Taste gate submitter |
| **taste-review** | `skills/taste/taste-review/SKILL.md` | Read-only reviewer for preference provenance, conflicts, redaction, confirmation, and persistence safety |

### Harness audit (1, standalone)

| Skill | Path | Role |
|---|---|---|
| **audit-improve** | `skills/audit-improve/SKILL.md` | Audits harness and saved-run failures, then routes supported improvements through Admiral and skill-maker |

### Browser automation (4, standalone)

| Skill | Path | Role |
|---|---|---|
| **browse** | `skills/browse/SKILL.md` | Drives an existing browser session, evidence first |
| **open-browser** | `skills/open-browser/SKILL.md` | Launches a visible browser workspace, reusing one if available |
| **setup-browser-cookies** | `skills/setup-browser-cookies/SKILL.md` | Prepares authenticated session state for protected surfaces |
| **pair-agent** | `skills/pair-agent/SKILL.md` | Pairs a remote collaborator to a browser session with scoped access |

### Release and deployment (4, standalone)

| Skill | Path | Role |
|---|---|---|
| **ship** | `skills/ship/SKILL.md` | Release orchestration; owns the `deploy-readiness` submission |
| **land-and-deploy** | `skills/land-and-deploy/SKILL.md` | Merge, rollout, verification, post-release checks, rollback awareness |
| **setup-deploy** | `skills/setup-deploy/SKILL.md` | Durable deployment settings, environment conventions, rollback plan |
| **document-release** | `skills/document-release/SKILL.md` | Release notes, operational follow-up, documentation trail |

### Safety guardrails (4, standalone)

| Skill | Path | Role |
|---|---|---|
| **guard** | `skills/guard/SKILL.md` | Combined intent check and write boundary |
| **careful** | `skills/careful/SKILL.md` | Intent confirmation before a destructive or irreversible action |
| **freeze** | `skills/freeze/SKILL.md` | Locks a declared path boundary until explicitly lifted |
| **unfreeze** | `skills/unfreeze/SKILL.md` | Clears an active protection boundary |

The guard and freeze boundary is enforced by `harness/hooks/pre_tool_use.py` via
`.harness-state/guard-state.json`.

### Testing and QA (3, standalone)

| Skill | Path | Role |
|---|---|---|
| **qa** | `skills/qa/SKILL.md` | Product testing that records evidence, applies scoped fixes, reruns until stable |
| **qa-only** | `skills/qa-only/SKILL.md` | Read-only product testing; evidence-backed defect report, no fixes |
| **benchmark** | `skills/benchmark/SKILL.md` | Comparative performance measurement with repeatable evidence |

## Orchestration contracts

Not skills. These are the files the skills are checked against.

| File | Purpose |
|---|---|
| `skills/gates.yaml` | Ten boundaries: required and artifact-backed evidence, sanctioned fallbacks, typed records, finding policy, submitters |
| `skills/pipelines.yaml` | Ten pipelines: ordered stages, owners, closing boundary, required scripts |
| `skills/ownership.yaml` | One writer per design and handoff artifact |
| `skills/save-ownership.yaml` | One writer per path class under `skillset-saves/` and `.harness-state/` |
| `skills/team-manifest.yaml` | The roster every owner and submitter is checked against |
| `skills/runtime-manifest.yaml` | Runtime floor, launchers, supported commands, CI matrix |
| `skills/package-manifest.yaml` | Include, exclude, delivery contract |
| `skills/execution-contract.md` | The six preamble clauses and the tier table |
| `skills/tech-stacks/registry.yaml` | 14 stack overlays with pinned versions and digests |

## Doctrine and protocol

| File | Purpose |
|---|---|
| `skills/routing-doctrine.md` | Entry routing, precedence, Tier 0 fast path, loop guard, session pin |
| `skills/grill-me-doctrine.md` | Intake interview; produces the hashed decisions artifact |
| `skills/design-doctrine.md` | Frontend design system, responsive tiers, accessibility, gate evidence |
| `skills/taste-doctrine.md` | Canonical semantics, provenance, lifecycle, scope, and deterministic resolution for user presentation and interaction preferences |
| `skills/harness-doctrine.md` | Lifecycle layers, failure taxonomy, engineering non-negotiables |
| `skills/performance-doctrine.md` | Measured optimization, baselines, regression budgets |
| `skills/save-protocol.md` | Save layout, startup, ownership, state and audit, resume and rewind |
| `skills/mcp-tools.md` | MCP tool registry; `discovery_ttl_hours` is the freshness window |

## Canonical contracts

| File | Purpose |
|---|---|
| `skills/contracts/evidence-standards.md` | What can support a claim: specificity, trust, input boundaries, retention, calibration |
| `skills/contracts/handoff-templates.md` | Save Context block, request and response fields, manifest schema 2 |
| `skills/contracts/workflow-protocol.md` | State machine, gate boundaries, revision lineage, rewind, resume, failure rules |
| `skills/contracts/responsibility-matrix.md` | One writer per lifecycle layer |
| `skills/contracts/universal-frameworks.md` | Cross-cutting invariants and where their practice is defined |
| `skills/contracts/delivery-template.md` | The final delivery record |

## Runtime harness

| Component | Path | Purpose |
|---|---|---|
| **pre_tool_use.py** | `skills/harness/hooks/pre_tool_use.py` | `PreToolUse`: the registered entry point; forwards to `guard_hook.py` and fails open, readably, on a fault |
| **guard_hook.py** | `skills/harness/hooks/guard_hook.py` | The guard engine: Rules A to G, one function per rule (destructive commands, frozen and blocked boundaries, read-only runs, single writers, the hook scripts and their registration files, a write the analysis cannot place) plus the coverage advisory |
| **_cmdscan.py** | `skills/harness/hooks/_cmdscan.py` | Shell command analyser behind the guard: quoting, wrappers, heredocs, `cd`, and the write targets of the usual verbs |
| **_paths.py** | `skills/harness/hooks/_paths.py` | Path and glob canonicaliser behind the guard: separators, `.` and `..`, `~`, drive letters, links and case |
| **guard_state.py** | `skills/harness/hooks/guard_state.py` | The only writer of the guard record (`.harness-state/guard-state.json`) that `guard`, `freeze` and `unfreeze` request |
| **post_tool_use.py** | `skills/harness/hooks/post_tool_use.py` | `PostToolUse`: records trajectory degeneration, refreshes the run heartbeat |
| **size_audit.py** | `skills/harness/hooks/size_audit.py` | Periodic bounded report of oversized runtime files and directories |
| **audit_improve.py** | `skills/harness/hooks/audit_improve.py` | Bounded read-only audit of saved failures and a skill-maker handoff |
| **user_prompt_submit.py** | `skills/harness/hooks/user_prompt_submit.py` | `UserPromptSubmit`: advisory entry-routing and session-pin reminder |
| **save_run.py** | `skills/harness/hooks/save_run.py` | The only writer of the run record |
| **_saves.py** | `skills/harness/hooks/_saves.py` | Shared reader that classifies saved state |
| **_state.py** | `skills/harness/hooks/_state.py` | Fail-open state helper: project root, hook input decoding, guard state, fault counting, trajectories |
| **run_heartbeat.py** | `skills/harness/hooks/run_heartbeat.py` | The heartbeat refresh every registered hook runs on a host event: throttled, fail-open, written only through `save_run.py` |
| **_fsutil.py** | `skills/harness/hooks/_fsutil.py` | The one atomic write and the one OS advisory lock the hook-directory writers share |
| **_bootstrap.py** | `skills/harness/hooks/_bootstrap.py` | Puts the hooks directory and `skills/scripts` on `sys.path` once, so modules import each other by name, and lists the files a registered hook runs to decide |
| **_testkit.py** | `skills/harness/hooks/_testkit.py` | Test support for the guard suites: an in-process `decide()` and a subprocess `run_hook()` |
| **verify_registration.py** | `skills/harness/hooks/verify_registration.py` | Inspects host hook config without mutating it |
| **repair_registration.py** | `skills/harness/hooks/repair_registration.py` | Previews a scoped registration repair; applies only with `--apply` |
| **check_readiness.py** | `skills/harness/hooks/check_readiness.py` | Python, hooks, and save state as an independent capability map |
| **gatekeeper/check.py** | `skills/harness/gatekeeper/check.py` | Boundary validator; loads `gates.yaml` |
| **gatekeeper/_gatecheck.py** | `skills/harness/gatekeeper/_gatecheck.py` | Package-shape engine behind each `gatekeeper-*/scripts/check.py` |

Shared tooling is in `skills/scripts/`. Its command-line tools are
`check_runtime.py`, `output_paths.py`, `scan_record.py`, `check_parity.py`,
`content_hash.py`, `validate_manifests.py` and `package_check.py`;
`data_formats.py` is the JSON and YAML reader every script shares, and the rest are
modules behind `check_runtime.py` and the save layout, listed in
[docs/directory-structure.md](docs/directory-structure.md). Contract suites are in
`skills/validation/`; the other suites sit beside the code they test: `test_*.py` in
`skills/harness/hooks/` (the guard, state, writers and registration), in
`skills/harness/gatekeeper/`, in `skills/scripts/`, in `skills/taste/` and in
`skills/skill-maker/skill-creator/scripts/`, and `scripts/test_install.py` for the
installers. The file-by-file list of the hooks directory is its
[README](skills/harness/hooks/README.md); the commands that run all seven suites
are in [CONTRIBUTING.md](CONTRIBUTING.md#run-the-suites).

Hook registration lives in host-native config and happens only on explicit opt-in
(`-RegisterHooks` / `--register-hooks`). Hooks are stdlib only and fail open. The
gate validators fail loud, because a gate that cannot prove a package clean must
never approve it.

## Layout

**53 skills**: Admiral 2, Design 9, Build 8, Review 11, Investigate 1,
Skill-Maker 3, Session-Memory 1, Taste 2, Harness Audit 1, Browser 4, Release 4,
Safety 4, Testing 3. Plus
the runtime harness, eight doctrine and protocol files, six canonical contracts,
and the machine-readable specs.

`admiral`, `gatekeeper-admiral`, `investigate`, `skill-maker`, `session-memory`,
`taste`, and `audit-improve` sit directly under `skills/` because they are cross-cutting.
Pipeline-stage skills nest under their category directory; standalone tools under
their group. This manifest is the authoritative flat index regardless of depth.

The checkout also carries files outside `skills/`, which the installers do not copy:
`README.md`, `QUICK-START.md`, `Install.md`, `BENCHMARK.md`,
`CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `ruff.toml`, `docs/`, the installers in `scripts/`
(`install.sh`, `install.ps1`, `install_hooks.py`, `install-items.txt`,
`test_install.py`) and the CI workflow `.github/workflows/ci.yml`.

Full tree in [docs/directory-structure.md](docs/directory-structure.md).
