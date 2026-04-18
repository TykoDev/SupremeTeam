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
│   ├── gatekeepers.md                    # Gatekeeper pattern explanation
│   ├── persistent-saves.md              # Save system documentation
│   ├── direct-invocation.md             # Standalone skill usage
│   └── directory-structure.md           # This file
└── skills/
    ├── admiral/                          # Top-level orchestrator
    │   ├── SKILL.md
    │   └── references/
    ├── gatekeeper-admiral/               # Cross-pipeline validator
    │   ├── SKILL.md
    │   └── references/
    ├── design/                           # Design sub-pipeline (7 skills + tech-stacks)
    │   ├── commander/
    │   ├── researcher/
    │   ├── planner/
    │   ├── architect/
    │   ├── designer/
    │   ├── engineer/
    │   ├── gatekeeper-design/
    │   └── tech-stacks/                  # 14 stack templates
    ├── build/                            # Build sub-pipeline (8 skills)
    │   ├── build-management/
    │   ├── bob-the-builder/
    │   ├── test-builder/
    │   ├── security-builder/
    │   ├── cross-check-build-confirm/
    │   ├── debugger/
    │   ├── health-check/
    │   └── gatekeeper-build/
    ├── review/                           # Review sub-pipeline (10 skills)
    │   ├── code-chief/
    │   ├── bug-review/
    │   ├── code-review/
    │   ├── quality-review/
    │   ├── security-review/
    │   ├── mr-robot/
    │   ├── frontier/
    │   ├── design-qa/
    │   ├── devex-review/
    │   └── gatekeeper-code/
    ├── azure/                            # Azure provision sub-pipeline (7 skills)
    │   ├── azure-provisioner/
    │   ├── azure-planner/
    │   ├── azure-architect/
    │   ├── azure-configurator/
    │   ├── azure-deployer/
    │   ├── azure-verifier/
    │   └── gatekeeper-azure/
    ├── session-memory/                   # Cross-session state & learnings manager
    ├── references/                       # Shared universal references
    └── save-protocol.md                  # Persistent save system specification
```

## Skills Directory

The grouped `skills/` hierarchy is load-bearing. Shared references, persistence
files, and design tech-stack overlays are consumed by relative paths inside the
skill files.

**Do not flatten, rename, or partially extract individual skill folders without
their dependencies.**

### Nesting Convention

- `admiral` and `gatekeeper-admiral` sit directly under `skills/` (depth 2)
  because they orchestrate across all sub-pipelines
- `session-memory` also sits at depth 2 as a cross-cutting utility skill
- All other skills are nested under their pipeline category directory (depth 3)
- `AGENTS.md` provides the authoritative flat index for tool discovery
  regardless of nesting depth

## Installed Layout

After running the installer, the target directory mirrors the `skills/`
subtree:

| Target | Linux / macOS | Windows |
|--------|---------------|---------|
| Agent skills | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Claude Code mirror | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |

## Critical Dependencies

| Component | Depends On |
|-----------|-----------|
| `design/architect/`, `design/designer/`, `design/engineer/` | `design/tech-stacks/` |
| `review/code-chief/` | `references/` |
| `admiral`, `commander`, `build-management`, `code-chief`, `azure-provisioner` | `save-protocol.md` |
