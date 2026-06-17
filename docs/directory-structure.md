# Directory Structure

## Repository Layout

```
SupremeTeam/
├── README.md                             # Project overview and value proposition
├── QUICK-START.md                        # Installation and first-use guide
├── Install.md                            # Detailed AI-agent installation procedure
├── AGENTS.md                             # Authoritative skill manifest for discovery
├── scripts/
│   ├── install.ps1                       # Windows installer
│   └── install.sh                        # macOS / Linux installer
├── docs/
│   ├── architecture.md                   # Pipeline architecture and modes
│   ├── skills.md                         # Complete skill inventory
│   ├── gatekeepers.md                    # Gatekeeper pattern + deterministic gate engine
│   ├── routing.md                        # Entry-routing doctrine and skill tiers
│   ├── harness.md                        # Runtime harness (hooks + gate engine)
│   ├── persistent-saves.md               # Save system documentation
│   ├── direct-invocation.md              # Standalone skill usage
│   └── directory-structure.md            # This file
└── skills/
    ├── admiral/                          # Primary entry orchestrator
    │   ├── SKILL.md
    │   ├── references/                   # workflow.md, examples.md
    │   └── agent/                        # agent-manifest.yaml, agent-protocol.md, adapters/
    ├── gatekeeper-admiral/               # Cross-stage validator (+ scripts/check.py)
    ├── design/                           # Design sub-pipeline (6 skills)
    │   ├── commander/
    │   ├── researcher/
    │   ├── planner/
    │   ├── architect/                    # also owns the frontend/UI design system
    │   ├── engineer/
    │   └── gatekeeper-design/
    ├── build/                            # Build sub-pipeline (8 skills)
    │   ├── build-management/
    │   ├── bob-the-builder/
    │   ├── test-builder/
    │   ├── security-builder/
    │   ├── cross-check-build-confirm/
    │   ├── debugger/
    │   ├── health-check/
    │   └── gatekeeper-build/
    ├── review/                           # Review sub-pipeline (11 skills)
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
    │   └── gatekeeper-code/
    ├── investigate/                      # Root-cause analysis (in-scope component)
    ├── skill-maker/                      # Skill/team creation orchestrator
    │   ├── skill-creator/
    │   └── skill-reviewer/
    ├── session-memory/                   # Cross-session state & learnings manager
    ├── browser-automation/               # Standalone tools (4)
    │   ├── browse/
    │   ├── open-browser/
    │   ├── setup-browser-cookies/
    │   └── pair-agent/
    ├── release-and-deployment/           # Standalone tools (4)
    │   ├── ship/
    │   ├── land-and-deploy/
    │   ├── setup-deploy/
    │   └── document-release/
    ├── safety-guardrails/                # Standalone tools (4)
    │   ├── guard/
    │   ├── careful/
    │   ├── freeze/
    │   └── unfreeze/
    ├── testing-and-qa/                   # Standalone tools (3)
    │   ├── qa/
    │   ├── qa-only/
    │   └── benchmark/
    ├── harness/                          # Runtime harness (infrastructure)
    │   ├── hooks/                        # pre/post tool-use, user-prompt-submit, verify_registration
    │   └── gatekeeper/                   # _gatecheck.py deterministic gate engine
    ├── routing-doctrine.md
    ├── grill-me-doctrine.md
    ├── design-doctrine.md
    ├── harness-doctrine.md
    ├── mcp-tools.md
    └── save-protocol.md
```

## Skills Directory

The grouped `skills/` hierarchy is load-bearing. The root doctrine and protocol
files, the runtime harness, and each skill's `references/` and `scripts/`
subdirectories are consumed by relative paths inside the skill files.

**Do not flatten, rename, or partially extract individual skill folders without
their dependencies.**

### Nesting Convention

- `admiral`, `gatekeeper-admiral`, `investigate`, `skill-maker`, and
  `session-memory` sit directly under `skills/` (depth 2) because they are
  cross-cutting Admiral-pipeline components
- Pipeline-stage skills nest under their category directory (`design/`,
  `build/`, `review/`) at depth 3
- Standalone tools nest under their group directory (`browser-automation/`,
  `release-and-deployment/`, `safety-guardrails/`, `testing-and-qa/`)
- The six doctrine/protocol files and the `harness/` tree live at the skill-set
  root so every skill can resolve them by relative path
- `AGENTS.md` provides the authoritative flat index for tool discovery
  regardless of nesting depth

## Installed Layout

After running the installer, the target directory mirrors the `skills/` subtree.
Core components are always installed; selected team directories are added
alongside them.

| Target | Linux / macOS | Windows |
|--------|---------------|---------|
| Agent skills | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Claude Code mirror | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |

## Critical Dependencies

| Component | Depends On |
|-----------|-----------|
| All skills | The root doctrine/protocol files: `routing-doctrine.md`, `grill-me-doctrine.md`, `save-protocol.md` (and, for relevant skills, `design-doctrine.md`, `harness-doctrine.md`, `mcp-tools.md`) |
| `admiral` (intake) | `harness/hooks/verify_registration.py`, `mcp-tools.md`, `save-protocol.md` |
| Every `gatekeeper-*` skill | `harness/gatekeeper/_gatecheck.py` (located by walking up to the skill-set root) |
| `design/architect` (UI work) | `design-doctrine.md` (frontend/UI design-system doctrine) |
| Deterministic entry routing / guard enforcement | `harness/hooks/` registered in host-native hook config with `-RegisterHooks` / `--register-hooks` |
