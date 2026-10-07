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
├── ruff.toml                             # Lint rules CI enforces
├── .gitattributes                        # LF text in the repository, binary file types
├── .gitignore                            # Run state, local environments, interpreter and coverage residue
├── .github/workflows/ci.yml              # Runs the suites and validators on three OSes
├── scripts/                              # Checkout-only: not part of an installed copy
│   ├── install.ps1                       # Windows installer
│   ├── install.sh                        # macOS and Linux installer
│   ├── install-items.txt                 # What the installers copy
│   ├── install_hooks.py                  # Registers hooks, then verifies them
│   ├── superseded/                       # Registry texts earlier releases shipped; an unedited copy is replaced on upgrade
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
    ├── LICENSE                           # Byte copy of the root licence, so an install carries it
    ├── execution-contract.md             # Preamble clauses and tiers
    ├── routing-doctrine.md               # Entry routing, Tier 0, session pin
    ├── grill-me-doctrine.md              # Intake interview
    ├── design-doctrine.md                # Design system and its gate evidence
    ├── taste-doctrine.md                 # Preference semantics, provenance, lifecycle
    ├── harness-doctrine.md               # Lifecycle layers, taxonomy, rules
    ├── performance-doctrine.md           # Measured optimization
    ├── save-protocol.md                  # Save layout, lifecycle, resume
    ├── mcp-tools.md                      # Blank MCP template; project cache uses the configured TTL
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
    │   ├── save_taxonomy.py              # Shared save constants and phase-to-protocol state mapping
    │   ├── contract_floor.py             # Independent safety floor for the shipped gate spec
    │   ├── mcp_registry.py               # Read-only project MCP freshness/identity diagnostic
    │   ├── validate_manifests.py         # Manifest and cross-reference contracts
    │   └── package_check.py              # Packaging enumeration and residue check
    ├── validation/                       # Contract test suites and the two paid evals
    │   ├── __init__.py                   # Package marker
    │   ├── _catalog.py                   # Reads the catalog with the production parser, for the suite
    │   ├── run_eval.py                   # Run-level eval: which skills a real session registers
    │   ├── trigger_eval.py               # Trigger eval: does the right skill win
    │   └── test_*.py                     # The validation suite, listed under The test suites
    ├── harness/
    │   ├── hooks/                        # Lifecycle hooks, the guard, the record writers, diagnostics
    │   │   ├── pre_tool_use.py           # PreToolUse entry point; forwards to guard_hook.py
    │   │   ├── guard_hook.py             # The guard engine: Rules A to G, one function per rule
    │   │   ├── _cmdscan.py               # Shell command analyser: wrappers, redirects, write targets
    │   │   ├── _paths.py                 # Path and glob canonicaliser
    │   │   ├── _program_paths.py         # Bounded literal Python I/O targets; never evaluates code
    │   │   ├── guard_state.py            # Sole guard writer; legacy adoption preserves protection
    │   │   ├── post_tool_use.py          # PostToolUse: trajectory, heartbeat, coverage sweep
    │   │   ├── user_prompt_submit.py     # UserPromptSubmit: routing and session-pin reminder
    │   │   ├── save_run.py               # The only writer of the run record
    │   │   ├── _saves.py                 # Reader that classifies saved state
    │   │   ├── _state.py                 # Project root, hook input, guard state, fault counting
    │   │   ├── run_heartbeat.py          # The heartbeat refresh every hook runs on a host event
    │   │   ├── _fsutil.py                # The shared atomic write and OS advisory lock
    │   │   ├── _bootstrap.py             # sys.path setup, done once; lists the files a hook runs to decide
    │   │   ├── size_audit.py             # Bounded report of oversized runtime files
    │   │   ├── audit_improve.py          # Read-only audit of saved failures
    │   │   ├── verify_registration.py    # Inspects host hook config without changing it
    │   │   ├── repair_registration.py    # Previews or applies a registration repair
    │   │   ├── check_readiness.py        # Python, hooks and saves as a capability map
    │   │   ├── _testkit.py               # Test support for the guard suites
    │   │   ├── README.md                 # Rules, limits, fault trace, and a manifest of every file here
    │   │   ├── .gitignore                # Runtime observations and bytecode caches
    │   │   └── test_*.py                 # The hooks suite, listed under The test suites
    │   └── gatekeeper/                   # check.py (gate spec), _gatecheck.py (shape), README.md, test_*.py
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
    ├── skill-maker/                      # skill-creator (scripts/ with its test_*.py, eval-viewer/), skill-reviewer
    ├── audit-improve/                    # read-only harness audit and skill-maker handoff
    ├── session-memory/                   # Run record and durable learnings
    ├── taste/                            # Preference lifecycle owner; taste_prefs.py is the atomic writer, taste-review/ the reviewer
    ├── browse/, open-browser/, setup-browser-cookies/, pair-agent/
    ├── ship/, land-and-deploy/, setup-deploy/, document-release/
    ├── guard/, careful/, freeze/, unfreeze/
    └── qa/, qa-only/, benchmark/
```

## The test suites

Seven suites, standard library only, each beside the code it tests; the commands
are in [CONTRIBUTING.md](../CONTRIBUTING.md#run-the-suites).

- **Hooks**, `skills/harness/hooks/`:
  - the guard: `test_guard_rules.py`, `test_guard_cmdscan.py`, `test_guard_paths.py`,
    `test_guard_harness_files.py`, `test_guard_state.py`, `test_pre_tool_entry.py`,
    `test_hooks_robustness.py`, `test_quality_audit.py`, `test_program_paths.py`
  - the hooks and their state: `test_hooks.py`, `test_hooks_hardening.py`,
    `test_hooks_observed.py`, `test_state_hardening.py`, `test_fsutil.py`,
    `test_hooks_maintenance.py`
  - the run record and its reader: `test_hooks_lifecycle.py`, `test_run_state.py`,
    `test_saves_reader.py`, `test_quality_state.py`
  - registration and readiness: `test_registration_contract.py`,
    `test_registration_hardening.py`, `test_installer_hooks.py`, `test_documented_flags.py`
  - maintenance audits: `test_size_audit.py`, `test_audit_improve.py`,
    `test_audit_improve_parts.py`
- **Gates**, `skills/harness/gatekeeper/`: `test_gatecheck.py`, `test_gate_engine.py`,
  `test_gate_manifests.py`, `test_gate_run_layout.py`, `test_gate_revise.py`,
  `test_gate_wrappers.py`, `test_quality_audit.py`
- **Validation**, `skills/validation/`: `test_catalog_contracts.py`, `test_orchestration.py`,
  `test_pipeline_contracts.py`, `test_pipeline_workflows.py`, `test_save_contracts.py`,
  `test_save_prose.py`, `test_save_taxonomy.py`, `test_trigger_routing.py`,
  `test_eval_tools.py`, `test_repository_hygiene.py`, `test_docs_inventory.py`,
  `test_lint_config.py`, `test_stdlib_only.py`, `test_contract_mirrors.py`
- **Scripts**, `skills/scripts/`: `test_check_runtime_contract.py`,
  `test_check_runtime_detection.py`, `test_check_runtime_layout.py`,
  `test_check_runtime_redaction.py`, `test_check_runtime_scaffold.py`,
  `test_check_parity.py`, `test_data_formats.py`, `test_package_check.py`,
  `test_runtime_utilities.py`, `test_scan_record.py`, `test_validate_manifests.py`,
  `test_contract_floor.py`, `test_mcp_registry.py`, `test_quality_examples.py`
- **Taste**, `skills/taste/`: `test_taste_prefs.py`, `test_taste_store.py`
- **Installers**, `scripts/`: `test_install.py`
- **Skill-creator**, `skills/skill-maker/skill-creator/scripts/`: `test_aggregate_benchmark.py`,
  `test_documentation.py`, `test_encoding.py`, `test_entry_points.py`, `test_generate_review.py`,
  `test_improve_description.py`, `test_older_interpreters.py`, `test_package_skill.py`,
  `test_quick_validate.py`, `test_regressions.py`, `test_run_eval.py`, `test_run_loop.py`,
  `test_utils.py`

## The `.yaml` specs

`gates.yaml`, `pipelines.yaml` and `runtime-manifest.yaml` are JSON documents with
a `.yaml` extension; the rest are block YAML. `skills/scripts/data_formats.py`
reads both without PyYAML. Load a spec with `data_formats.load_data` and keep each
in the format it is in.

## What never gets committed

| Path | What it holds | Status |
|---|---|---|
| `skillset-saves/` | Run state, locks, audit trails, evidence, gate packages | Ignored. Never commit |
| `.harness-state/` | Guard records and trajectory observations | Ignored. Never commit |
| `.harness-state/test-work/`, `eval-reports/`, `eval-workspaces/`, `packages/` | Test scratch, skill-creator reports and workspaces, packages built outside a run | Ignored. Never commit |
| `**/__pycache__/`, `*.pyc` | Interpreter caches | Ignored. Never publish |

`python skills/scripts/package_check.py --root .` enumerates what
`package-manifest.yaml` selects, rejects residue and confirms the required assets.

## The tree shape is load-bearing

Root contracts, doctrines, manifests, `scripts/`, `harness/` and each skill's
`references/` and `scripts/` are resolved by relative path from inside skill
files; a flattened or renamed tree breaks them.

- `admiral`, `gatekeeper-admiral`, `investigate`, `skill-maker`,
  `session-memory`, `taste`, and `audit-improve` are directly under `skills/`
  because they are cross-cutting.
- Pipeline-stage skills nest under their category (`design/`, `build/`,
  `review/`).
- Standalone tools sit directly under `skills/` so a host that scans one level
  deep registers them by name: the 22 root-level skills register, the 31 nested
  specialists are reached by path through the skill that delegates to them.
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

The common target is always installed; existing mirrors are refreshed on
upgrade. Codex and Cursor are mirrored only when their directory already holds
Supreme Team files or you name the host.

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
