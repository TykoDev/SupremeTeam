# Supreme Team — Installation Guide

Supreme Team ships with installer scripts in the `scripts/` directory:

- `scripts/install.ps1` for Windows
- `scripts/install.sh` for macOS and Linux

For human users, Markdown does not execute automatically. Opening or running
`Install.md` in an editor does not install anything by itself; you must run one
of the installer scripts.

For AI agents, this file is the procedural installation entry point. Use it to
identify the operating system, ask the user what to install, and then execute
the correct installer script with the matching flags.

Supreme Team ships as a grouped `skills/` source tree. This layout is
load-bearing — do not flatten, rename, or partially extract individual skill
folders without their dependencies.

## AI agent entry point

If you are an AI agent installing Supreme Team, follow this flow before running
anything:

### 1. Detect the operating system

| OS | Script | Base command |
|----|--------|--------------|
| Windows | `scripts/install.ps1` | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1` |
| macOS / Linux | `scripts/install.sh` | `bash ./scripts/install.sh` |

### 2. Ask the user what they want installed

Ask these questions in order:

1. Install all teams or only a subset?
2. If subset, which teams: `Design`, `Build`, `Review`, `Browser`, `Release`,
   `Safety`, `Testing`?
3. Install to the default agent skill path only, also mirror to Claude Code, or
   install only to the Claude Code path?
4. Do they want to override either default destination path?

### 3. Map the user's answers to the installer flags

| User intent | Windows | macOS / Linux | Notes |
|-------------|---------|---------------|-------|
| Install all teams | no extra flags | no extra flags | This is the default behavior |
| Install a subset | `-Team Design,Review` | `--team design --team review` | Windows accepts a comma-separated list; macOS/Linux repeats `--team` |
| Also mirror to Claude Code | `-InstallClaude` | `--install-claude` | Adds a Claude Code mirror in addition to the primary install |
| Install only to Claude Code path | `-Destination "$HOME\.claude\skills"` | `--destination "$HOME/.claude/skills"` | Use this when Claude Code should be the only target |
| Override the primary install path | `-Destination "D:\SupremeTeam\skills"` | `--destination "/custom/skills/path"` | Replaces the default agent skill path |
| Override the Claude Code mirror path | `-InstallClaude -ClaudeDestination "D:\Claude\skills"` | `--install-claude --claude-destination "/custom/claude/path"` | Use only when a Claude mirror is also requested |

Team flag values: `Design`, `Build`, `Review`, `Browser`, `Release`, `Safety`,
`Testing`, or `All`. On macOS/Linux these are lowercase
(`design build review browser release safety testing all`).

> **Note:** All script paths above are relative to the repository root. The base
> commands in Step 1 already include the `scripts/` prefix.

### 4. Execute the matching script

Use the base command for the detected operating system and append only the flags
that match the user's answers.

Representative examples:

| Intent | Windows | macOS / Linux |
|--------|---------|---------------|
| Install all teams to the default agent path | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1` | `bash ./scripts/install.sh` |
| Install Design + Review and also mirror to Claude Code | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Team Design,Review -InstallClaude` | `bash ./scripts/install.sh --team design --team review --install-claude` |
| Install only to the Claude Code path | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Destination "$HOME\.claude\skills"` | `bash ./scripts/install.sh --destination "$HOME/.claude/skills"` |

The scripts resolve the repository root from their own location, so they still
work when launched by full path from another directory.

### 5. Verify success from installer output

Treat the install as successful when the script prints these summary lines
without an error:

- `Supreme Team installation complete.`
- `Target: ...`
- `Teams: ...`
- `Claude mirror: ...`

### 6. Recommend registering the runtime harness hooks

After a successful install, recommend registering the three runtime harness hooks
(`pre_tool_use.py`, `post_tool_use.py`, `user_prompt_submit.py`) in the host
`settings.json` to enable deterministic entry routing and action guards. The
`update-config` skill owns this registration, or the block can be applied
manually from `skills/harness/hooks/README.md`. Without registration these layers
fall back to advisory doctrine. Admiral also checks registration at intake via
`harness/hooks/verify_registration.py`.

### 7. Boundary note for Claude requests

This repository defines two built-in install targets only:

- the default agent skills path
- an optional Claude Code mirror path

There is no separate built-in `Claude Coder` target or agent-type switch in the
current scripts. If the user says `Claude Coder`, clarify whether they mean
Claude Code or another custom destination. If they mean another destination, use
`-Destination` or `--destination` with the exact path they want.

## What the installers do

- Resolve the repository root from the script location, so they work even when launched from another directory
- Install all teams by default
- Support partial installs while always including the shared core components
- Optionally mirror the same install into Claude Code's skill path
- Replace the Supreme Team-managed paths in the target directory on each run, leaving unrelated entries alone
- Validate the copied tree before reporting success

## Default targets

| Target | Linux / macOS | Windows |
|--------|----------------|---------|
| Agent skills | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Claude Code mirror | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |

## Quick install

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

If script execution is already allowed in your shell, this works too:

```powershell
.\scripts\install.ps1
```

### macOS / Linux

```bash
bash ./scripts/install.sh
```

By default, both installers copy the full Supreme Team bundle into the default
agent skill path and verify the result before finishing.

## Partial install rules

These core components are always installed, even when you choose only one team:

| Directory / File | Purpose |
|------------------|---------|
| `admiral/` | Primary entry orchestrator |
| `gatekeeper-admiral/` | Cross-stage adversarial validator |
| `session-memory/` | Cross-session state and learnings manager |
| `investigate/` | Root-cause analysis component |
| `skill-maker/` | Skill/team creation orchestrator |
| `harness/` | Runtime harness (hooks + deterministic gate engine) |
| `routing-doctrine.md` | Entry-routing contract |
| `grill-me-doctrine.md` | Intake interview protocol |
| `design-doctrine.md` | Frontend/UI design-system doctrine |
| `harness-doctrine.md` | Runtime harness doctrine |
| `mcp-tools.md` | Global MCP tool registry |
| `save-protocol.md` | Persistent save system specification |

Selectable teams:

| Team | Directory | Skills | Notes |
|------|-----------|--------|-------|
| **Design** | `design/` | 6 skills | `architect` owns the frontend/UI design system |
| **Build** | `build/` | 8 skills | |
| **Review** | `review/` | 11 skills | |
| **Browser** | `browser-automation/` | 4 tools | Standalone (out of pipeline routing) |
| **Release** | `release-and-deployment/` | 4 tools | Standalone |
| **Safety** | `safety-guardrails/` | 4 tools | Enforced by `harness/hooks/pre_tool_use.py` |
| **Testing** | `testing-and-qa/` | 3 tools | Standalone |

Critical dependencies:

- All skills resolve the root doctrine/protocol files
  (`routing-doctrine.md`, `grill-me-doctrine.md`, `save-protocol.md`, and the
  relevant `design-doctrine.md` / `harness-doctrine.md` / `mcp-tools.md`)
- Every `gatekeeper-*` skill depends on `harness/gatekeeper/_gatecheck.py`
- `design/architect` UI work depends on `design-doctrine.md`
- `admiral` intake depends on `harness/hooks/verify_registration.py`, `mcp-tools.md`, and `save-protocol.md`

## Common installer options

| Goal | Windows | macOS / Linux |
|------|---------|---------------|
| Install all teams | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1` | `bash ./scripts/install.sh` |
| Install only Design + Review | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Team Design,Review` | `bash ./scripts/install.sh --team design --team review` |
| Install only the standalone tools | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Team Browser,Release,Safety,Testing` | `bash ./scripts/install.sh --team browser --team release --team safety --team testing` |
| Install and mirror to Claude Code | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -InstallClaude` | `bash ./scripts/install.sh --install-claude` |
| Install only to the Claude Code path | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Destination "$HOME\.claude\skills"` | `bash ./scripts/install.sh --destination "$HOME/.claude/skills"` |
| Install into a custom agent path | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Destination "D:\SupremeTeam\skills"` | `bash ./scripts/install.sh --destination "$HOME/.agents/skills"` |
| Install into a custom Claude path | `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -InstallClaude -ClaudeDestination "D:\Claude\skills"` | `bash ./scripts/install.sh --install-claude --claude-destination "$HOME/.claude/skills"` |

If you launch either script by full path, it still resolves the repository root
automatically. The current working directory does not need to be the repository
root.

## Updating an existing install

Re-run the installer script. Each run replaces the Supreme Team-managed paths in
the target directory:

- `admiral/`
- `gatekeeper-admiral/`
- `session-memory/`
- `investigate/`
- `skill-maker/`
- `harness/`
- `routing-doctrine.md`, `grill-me-doctrine.md`, `design-doctrine.md`,
  `harness-doctrine.md`, `mcp-tools.md`, `save-protocol.md`
- `design/`
- `build/`
- `review/`
- `browser-automation/`
- `release-and-deployment/`
- `safety-guardrails/`
- `testing-and-qa/`

Unrelated entries in the same target directory are left alone.

## Verification

After installation:

1. Confirm the target contains the core components plus the teams you selected.
2. Start a new assistant session if your current one was already running.
3. Ask your assistant:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

If skill discovery is configured correctly, the assistant should identify the
admiral orchestrator, the installed team sub-pipelines, the standalone tool
groups, and the shared resources.

## Manual fallback

Use these commands only if you cannot run the installer scripts. They assume you
are already in the repository root. The scripts above are safer because they
validate the result and do not depend on the current working directory.

### macOS / Linux

```bash
repo_root="$(pwd)"
destination="$HOME/.agents/skills"

mkdir -p "$destination"
cp -R "$repo_root/skills/." "$destination/"
```

### Windows (PowerShell)

```powershell
$repoRoot = (Get-Location).Path
$source = Join-Path $repoRoot "skills"
$destination = Join-Path $env:USERPROFILE ".agents\skills"

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Recurse -Force (Join-Path $source "*") -Destination $destination -ErrorAction Stop
```

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| PowerShell blocks `install.ps1` | Script execution policy is restricting local scripts | Run `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1` |
| Installer says the `skills/` source tree is missing | The script is not being run from a valid Supreme Team checkout | Re-run the installer from this repository or point to the correct clone |
| `Unknown team` error | A team name was misspelled | Use `Design`, `Build`, `Review`, `Browser`, `Release`, `Safety`, `Testing`, or `All` |
| Design skills cannot resolve the design-system doctrine | `design-doctrine.md` was not copied | Re-run the installer so the core components are restored |
| Gatekeepers' `check.py` cannot find the engine | `harness/` was not copied | Re-run the installer so the core components are restored |
| Resume or save artifacts do not work | `save-protocol.md` is missing | Re-run the installer so the core components are restored |
| Entry routing / action guards are not enforced | The harness hooks are not registered in `settings.json` | Register them via the `update-config` skill (see `skills/harness/hooks/README.md`) |
| Skills are not discovered after install | Wrong target path, stale assistant session, or your tool is not configured to scan that path | Verify the install target, restart the assistant session, and confirm your tool discovers skills from `~/.agents/skills/` or `%USERPROFILE%\.agents\skills\` |
