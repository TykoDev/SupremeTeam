# Where Everything Lives

## The repository

```text
SupremeTeam/
├── README.md                             # Start here
├── QUICK-START.md                        # Install and first run
├── Install.md                            # The full installation procedure
├── AGENTS.md                             # Flat skill index for tool discovery
├── scripts/
│   ├── install.ps1                       # Windows installer
│   ├── install.sh                        # macOS and Linux installer
│   └── install_hooks.py                  # Registers hooks, then verifies them
├── docs/
│   ├── architecture.md                   # Pipelines, tiers, execution modes
│   ├── skills.md                         # Every skill and what it owns
│   ├── gatekeepers.md                    # Boundaries, evidence, verdicts
│   ├── routing.md                        # How a request finds its skill
│   ├── harness.md                        # Hooks, readiness, gate validators
│   ├── persistent-saves.md               # Save layout, locks, resume
│   ├── direct-invocation.md              # Calling skills directly
│   ├── directory-structure.md            # This file
│   └── assets/                           # Diagrams used across the docs
└── skills/
    ├── gates.yaml                        # Gate spec: 9 boundaries
    ├── pipelines.yaml                    # Pipeline map: 8 pipelines
    ├── ownership.yaml                    # One writer per artifact
    ├── save-ownership.yaml               # One writer per save path class
    ├── team-manifest.yaml                # Roster
    ├── runtime-manifest.yaml             # Runtime floor, launchers, commands
    ├── package-manifest.yaml             # Packaging and delivery contract
    ├── execution-contract.md             # Preamble clauses and tiers
    ├── routing-doctrine.md               # Entry routing, Tier 0, session pin
    ├── grill-me-doctrine.md              # Intake interview
    ├── design-doctrine.md                # Design system and its gate evidence
    ├── harness-doctrine.md               # Lifecycle layers, taxonomy, rules
    ├── performance-doctrine.md           # Measured optimization
    ├── save-protocol.md                  # Save layout, lifecycle, resume
    ├── mcp-tools.md                      # MCP registry with a freshness TTL
    ├── contracts/                        # Six canonical cross-phase contracts
    ├── tech-stacks/                      # 14 stack overlays + registry.yaml
    ├── scripts/                          # Shared deterministic tooling
    │   ├── data_formats.py               # JSON and YAML with a stdlib fallback
    │   ├── output_paths.py               # Resolves every generated destination
    │   ├── check_runtime.py              # Runtime contract + stack detection
    │   ├── scan_record.py                # Typed scan evidence records
    │   ├── validate_manifests.py         # Manifest and cross-reference contracts
    │   └── package_check.py              # Packaging enumeration and residue check
    ├── validation/                       # Contract test suites
    ├── harness/
    │   ├── hooks/                        # 3 lifecycle hooks, save_run.py, diagnostics
    │   └── gatekeeper/                   # check.py (gate spec) + _gatecheck.py (shape)
    ├── admiral/                          # The front door
    │   ├── references/                   # workflow.md, examples.md
    │   └── agent/                        # agent-manifest.yaml, agent-protocol.md, adapters/
    ├── gatekeeper-admiral/               # Cross-stage validator
    ├── design/                           # commander, researcher, planner, architect,
    │                                     # engineer, gatekeeper-design
    ├── build/                            # build-management, bob-the-builder, test-builder,
    │                                     # security-builder, cross-check-build-confirm,
    │                                     # debugger, health-check, gatekeeper-build
    ├── review/                           # code-chief, bug-review, code-review,
    │                                     # quality-review, security-review, cso, mr-robot,
    │                                     # frontier, design-qa, devex-review, gatekeeper-code
    ├── investigate/                      # Investigation pipeline owner
    ├── skill-maker/                      # skill-creator, skill-reviewer
    ├── session-memory/                   # Run record and durable learnings
    ├── browser-automation/               # browse, open-browser, setup-browser-cookies, pair-agent
    ├── release-and-deployment/           # ship, land-and-deploy, setup-deploy, document-release
    ├── safety-guardrails/                # guard, careful, freeze, unfreeze
    └── testing-and-qa/                   # qa, qa-only, benchmark
```

## What never gets committed

| Path | What it holds | Status |
|---|---|---|
| `skillset-saves/` | Run state, locks, audit trails, evidence, gate packages | Ignored. Never commit |
| `.harness-state/` | Guard records and trajectory observations | Ignored. Never commit |
| `harness-test-work/` | Temporary harness regression workspace | Ignored. Never commit |
| `**/__pycache__/`, `*.pyc` | Interpreter caches | Ignored. Never publish |

Ignore rules are not the delivery control, though.
`python skills/scripts/package_check.py --root .` enumerates exactly what
`package-manifest.yaml` selects, rejects residue, and confirms the required assets
are there.

## The tree shape is load-bearing

The root contracts, doctrines, manifests, `scripts/`, `harness/`, and each skill's
`references/` and `scripts/` are resolved by relative path from inside skill
files. Flatten the tree, rename a directory, or extract a skill without its
dependencies and things break in ways that are annoying to diagnose.

Why things sit where they do:

- `admiral`, `gatekeeper-admiral`, `investigate`, `skill-maker`, and
  `session-memory` are directly under `skills/` because they are cross-cutting.
- Pipeline-stage skills nest under their category (`design/`, `build/`,
  `review/`).
- Standalone tools nest under their group.
- Contracts, doctrines, manifests, `scripts/`, `validation/`, `tech-stacks/`, and
  `harness/` live at the skill-set root so every skill can resolve them.
- `AGENTS.md` is the flat index, so nesting depth never matters for discovery.

## After installation

The target mirrors the `skills/` subtree.

| Target | macOS / Linux | Windows |
|---|---|---|
| Agent skills | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Codex mirror | `~/.codex/skills/` | `%USERPROFILE%\.codex\skills\` |
| Claude Code mirror | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |
| Cursor mirror | `~/.cursor/skills/` | `%USERPROFILE%\.cursor\skills\` |
| OpenCode mirror | `~/.config/opencode/skills/` | `%USERPROFILE%\.config\opencode\skills\` |

The common target is always installed. Existing mirrors get refreshed on upgrade
so a stale copy does not stay discoverable. Codex and Cursor are mirrored only
when their directory already holds Supreme Team files, or when you name that host
explicitly.

## What depends on what

| Component | Needs |
|---|---|
| Every skill | The root doctrines: `routing-doctrine.md`, `grill-me-doctrine.md`, `save-protocol.md`, and where relevant `design-doctrine.md`, `harness-doctrine.md`, `performance-doctrine.md`, `mcp-tools.md` |
| Every gate boundary | `gates.yaml` and `harness/gatekeeper/check.py` |
| Every `gatekeeper-*` skill | `harness/gatekeeper/_gatecheck.py`, found by walking up to the skill-set root |
| `admiral` at intake | `harness/hooks/verify_registration.py`, `check_readiness.py`, `save_run.py`, `mcp-tools.md` |
| `session-memory` | `harness/hooks/save_run.py` as the only writer of the run record |
| `commander` for the stack lock | `tech-stacks/registry.yaml`, `scripts/check_runtime.py` |
| `architect` for UI work | `design-doctrine.md` |
| Shared tooling | `scripts/data_formats.py` for every JSON and YAML read |
| Deterministic routing and guards | `harness/hooks/` registered with `-RegisterHooks` or `--register-hooks` |
