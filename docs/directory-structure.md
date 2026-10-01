# Where Everything Lives

## The repository

```text
SupremeTeam/
├── README.md                             # Start here
├── QUICK-START.md                        # Install and first run
├── Install.md                            # The full installation procedure
├── AGENTS.md                             # Flat skill index for a checkout (not installed)
├── BENCHMARK.md                          # Scores, routing accuracy, how each was measured
├── CHANGELOG.md                          # What changed
├── CONTRIBUTING.md                       # Running the suites, fail-open and fail-loud, commits
├── LICENSE                               # MIT
├── .github/workflows/ci.yml              # Runs the suites and validators on three OSes
├── scripts/                              # Checkout-only: not part of an installed copy
│   ├── install.ps1                       # Windows installer
│   ├── install.sh                        # macOS and Linux installer
│   ├── install-items.txt                 # What the installers copy
│   ├── install_hooks.py                  # Registers hooks, then verifies them
│   └── test_install.py                   # Installer suite
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
    ├── gates.yaml                        # Gate spec: 10 boundaries
    ├── pipelines.yaml                    # Pipeline map: 10 pipelines
    ├── ownership.yaml                    # One writer per artifact
    ├── save-ownership.yaml               # One writer per save path class
    ├── team-manifest.yaml                # Roster
    ├── runtime-manifest.yaml             # Runtime floor, launchers, commands
    ├── package-manifest.yaml             # Packaging and delivery contract
    ├── execution-contract.md             # Preamble clauses and tiers
    ├── routing-doctrine.md               # Entry routing, Tier 0, session pin
    ├── grill-me-doctrine.md              # Intake interview
    ├── design-doctrine.md                # Design system and its gate evidence
    ├── taste-doctrine.md                 # Preference semantics, provenance, lifecycle
    ├── harness-doctrine.md               # Lifecycle layers, taxonomy, rules
    ├── performance-doctrine.md           # Measured optimization
    ├── save-protocol.md                  # Save layout, lifecycle, resume
    ├── mcp-tools.md                      # MCP registry with a freshness TTL
    ├── contracts/                        # Six canonical cross-phase contracts
    ├── tech-stacks/                      # 14 stack overlays + registry.yaml
    ├── scripts/                          # Shared deterministic tooling; its test_*.py suite sits in the same folder
    │   ├── data_formats.py               # JSON and YAML with a stdlib fallback
    │   ├── output_paths.py               # Resolves every generated destination
    │   ├── check_runtime.py              # Runtime contract check and the command line
    │   ├── project_inspection.py         # Read-only inspection behind --detect-project and friends
    │   ├── stack_detection.py            # Registry match and project classification
    │   ├── language_entrypoints.py       # Python, Go and Rust entrypoints and start commands
    │   ├── script_commands.py            # Package-script and Makefile command reading
    │   ├── project_files.py              # Bounded read-only walk, text reads, path classes
    │   ├── scaffold_scan.py              # Scaffold and placeholder marker scan
    │   ├── redaction.py                  # Secret redaction for every check_runtime report
    │   ├── scan_record.py                # Typed scan evidence records
    │   ├── check_parity.py               # Redesign mock and prototype parity against the inventory
    │   ├── content_hash.py               # The catalog's sha256 (text folded to LF) for evidence files
    │   ├── save_taxonomy.py              # The save-path constants the writer, reader and resolver share
    │   ├── validate_manifests.py         # Manifest and cross-reference contracts
    │   └── package_check.py              # Packaging enumeration and residue check
    ├── validation/                       # Contract test suites, run_eval.py and trigger_eval.py
    ├── harness/
    │   ├── hooks/                        # lifecycle hooks, guard and maintenance audits, save_run.py
    │   └── gatekeeper/                   # check.py (gate spec) + _gatecheck.py (shape)
    ├── admiral/                          # The front door
    │   ├── references/                   # workflow, routing, contracts, failure-modes, examples
    │   ├── intake-brief.yaml, stub-contract.md
    │   └── agent/                        # agent-manifest.yaml, agent-protocol.md, adapters/
    ├── gatekeeper-admiral/               # Cross-stage validator
    ├── design/                           # commander, researcher, planner, architect,
    │                                     # engineer, gatekeeper-design, redesign,
    │                                     # design-mapper, prototyper
    ├── build/                            # build-management, bob-the-builder, test-builder,
    │                                     # security-builder, cross-check-build-confirm,
    │                                     # debugger, health-check, gatekeeper-build
    ├── review/                           # code-chief, bug-review, code-review,
    │                                     # quality-review, security-review, cso, mr-robot,
    │                                     # frontier, design-qa, devex-review, gatekeeper-code
    ├── investigate/                      # Investigation pipeline owner
    ├── skill-maker/                      # skill-creator, skill-reviewer
    ├── audit-improve/                    # read-only harness audit and skill-maker handoff
    ├── session-memory/                   # Run record and durable learnings
    ├── taste/                            # Preference lifecycle owner and atomic writer
    ├── browse/, open-browser/, setup-browser-cookies/, pair-agent/
    ├── ship/, land-and-deploy/, setup-deploy/, document-release/
    ├── guard/, careful/, freeze/, unfreeze/
    └── qa/, qa-only/, benchmark/
```

## What never gets committed

| Path | What it holds | Status |
|---|---|---|
| `skillset-saves/` | Run state, locks, audit trails, evidence, gate packages | Ignored. Never commit |
| `.harness-state/` | Guard records and trajectory observations | Ignored. Never commit |
| `.harness-state/test-work/`, `eval-reports/`, `eval-workspaces/`, `packages/` | Test scratch, skill-creator reports and workspaces, packages built outside a run | Ignored. Never commit |
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

- `admiral`, `gatekeeper-admiral`, `investigate`, `skill-maker`,
  `session-memory`, `taste`, and `audit-improve` are directly under `skills/`
  because they are cross-cutting.
- Pipeline-stage skills nest under their category (`design/`, `build/`,
  `review/`).
- Standalone tools sit directly under `skills/` so a host that scans one level
  deep registers them by name. Depth does matter to that loader: the 22 root-level
  skills register, and the 31 nested specialists are reached by path through the
  skill that delegates to them (`routing-doctrine.md`, "Host registration").
- Contracts, doctrines, manifests, `scripts/`, `validation/`, `tech-stacks/`, and
  `harness/` live at the skill-set root so every skill can resolve them.
- `AGENTS.md` is a flat index of a checkout. The installers do not copy it and no
  host discovers skills from it.

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
| Every skill | The root doctrines: `routing-doctrine.md`, `grill-me-doctrine.md`, `save-protocol.md`, and where relevant `design-doctrine.md`, `taste-doctrine.md`, `harness-doctrine.md`, `mcp-tools.md`. `performance-doctrine.md` is reached through `contracts/universal-frameworks.md`; no `SKILL.md` links it |
| Every gate boundary | `gates.yaml` and `harness/gatekeeper/check.py` |
| Every `gatekeeper-*` skill | `harness/gatekeeper/_gatecheck.py`, found by walking up to the skill-set root |
| `admiral` at intake | `harness/hooks/verify_registration.py`, `check_readiness.py`, `save_run.py`, `mcp-tools.md` |
| `session-memory` | `harness/hooks/save_run.py` as the only writer of the run record |
| `commander` for the stack lock | `tech-stacks/registry.yaml`, `scripts/check_runtime.py` |
| `architect` for UI work | `design-doctrine.md` |
| Shared tooling | `scripts/data_formats.py` for every JSON and YAML read |
| Deterministic routing and guards | `harness/hooks/` registered with `-RegisterHooks` or `--register-hooks` |
