# Supreme Team — Quick Start

## Step 1: Choose Your Install Method

Supreme Team's `skills/` folder needs to be copied into your AI tool's skill
discovery path. You can do this with the installer scripts or manually.

### Default Install Targets

| Target | Linux / macOS | Windows |
|--------|---------------|---------|
| Agent skills | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Claude Code skills | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |

---

## Option A: Install with Scripts (Recommended)

### Windows (PowerShell)

Install all teams to the default agent skill path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Install all teams and also mirror to Claude Code:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -InstallClaude
```

Install only specific teams:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Team Design,Review
```

Install only to the Claude Code path (skip the default agent path):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -Destination "$HOME\.claude\skills"
```

### macOS / Linux

Install all teams to the default agent skill path:

```bash
bash ./scripts/install.sh
```

Install all teams and also mirror to Claude Code:

```bash
bash ./scripts/install.sh --install-claude
```

Install only specific teams:

```bash
bash ./scripts/install.sh --team design --team review
```

Install only to the Claude Code path:

```bash
bash ./scripts/install.sh --destination "$HOME/.claude/skills"
```

### Script Options Reference

| Goal | Windows Flag | macOS/Linux Flag |
|------|-------------|-----------------|
| Install specific teams | `-Team Design,Review` | `--team design --team review` |
| Mirror to Claude Code | `-InstallClaude` | `--install-claude` |
| Custom agent path | `-Destination "path"` | `--destination "path"` |
| Custom Claude path | `-ClaudeDestination "path"` | `--claude-destination "path"` |

Available teams (or `All`):

| Team flag | Installs |
|-----------|----------|
| `Design` | `design/` (6 skills) |
| `Build` | `build/` (8 skills) |
| `Review` | `review/` (11 skills) |
| `Browser` | `browser-automation/` (4 tools) |
| `Release` | `release-and-deployment/` (4 tools) |
| `Safety` | `safety-guardrails/` (4 tools) |
| `Testing` | `testing-and-qa/` (3 tools) |

The core components (see below) are always installed regardless of team
selection.

### Verify Script Success

The install succeeded when you see these lines without errors:

```
Supreme Team installation complete.
Target: ...
Teams: ...
Claude mirror: ...
```

---

## Option B: Manual Install

Use these steps if you cannot run the installer scripts.

### macOS / Linux

```bash
# 1. Open a terminal and navigate to the Supreme Team repository
cd /path/to/SupremeTeam

# 2. Create the target directory
mkdir -p "$HOME/.agents/skills"

# 3. Copy the entire skills tree
cp -R skills/. "$HOME/.agents/skills/"

# 4. (Optional) Also copy to Claude Code
mkdir -p "$HOME/.claude/skills"
cp -R skills/. "$HOME/.claude/skills/"

# 5. Verify the copy
ls "$HOME/.agents/skills/admiral"
```

### Windows (PowerShell)

```powershell
# 1. Open PowerShell and navigate to the Supreme Team repository
cd C:\path\to\SupremeTeam

# 2. Create the target directory
$destination = Join-Path $env:USERPROFILE ".agents\skills"
New-Item -ItemType Directory -Force -Path $destination | Out-Null

# 3. Copy the entire skills tree
Copy-Item -Recurse -Force (Join-Path "skills" "*") -Destination $destination

# 4. (Optional) Also copy to Claude Code
$claudeDest = Join-Path $env:USERPROFILE ".claude\skills"
New-Item -ItemType Directory -Force -Path $claudeDest | Out-Null
Copy-Item -Recurse -Force (Join-Path "skills" "*") -Destination $claudeDest

# 5. Verify the copy
Test-Path (Join-Path $destination "admiral")
```

### What Must Be Present After Install

These core components are always required, even for partial installs:

| Item | Purpose |
|------|---------|
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

Plus whichever team directories you selected (`design/`, `build/`, `review/`,
`browser-automation/`, `release-and-deployment/`, `safety-guardrails/`,
`testing-and-qa/`).

---

## Step 2: Restart Your Assistant Session

If your AI assistant was already running, restart it so it picks up the new
skills.

## Step 3: (Recommended) Register the Runtime Harness Hooks

To enable deterministic entry routing and action guards, register the three
harness hooks in your host `settings.json`. The simplest path is to ask the
`update-config` skill to register them, or apply the block in
`skills/harness/hooks/README.md` manually. Without registration, entry routing
and guard enforcement fall back to advisory doctrine. A newly created settings
file needs `/hooks` or a restart to load.

## Step 4: Verify Skill Discovery

Ask your assistant:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

If configured correctly, it should identify admiral, the sub-pipelines, the
standalone tool groups, and the shared resources.

## Step 5: Start Using Supreme Team

### Full Pipeline (Idea to Reviewed Code)

```text
Use the admiral skill to design, build, and review this project:
[describe your project]
```

### Design Only / Build / Review

```text
Design [your idea].
Implement this approved design.
Review this codebase.
```

These initiate through admiral automatically (the entry-routing doctrine) — you
do not need to name a sub-orchestrator.

### Investigate a Bug

```text
Find the root cause of this failure.
```

### Create a Skill or Team

```text
Use the skill-maker skill to create a skill that [behavior].
```

### Standalone Tools (invoke directly)

```text
Use the open-browser skill to launch a browser workspace.
Use the browse skill to click through the app and capture evidence.
Use the ship skill to coordinate this release.
Use the land-and-deploy skill to get this branch live.
Use the freeze skill to protect src/payments from edits.
Use the guard skill to lock things down while we work.
Use the qa skill to test this product and fix what's broken.
Use the benchmark skill to compare performance.
Use the session-memory skill to checkpoint progress.
```

If your tool supports slash-style skill commands, you can use that syntax as
shorthand.

## Updating

Re-run the installer script. Each run replaces the Supreme Team-managed paths in
the target directory while leaving unrelated entries alone.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| PowerShell blocks `install.ps1` | Use `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1` |
| Installer says `skills/` source is missing | Run the installer from the Supreme Team repository root |
| Skills are not discovered | Check the install target path, restart the assistant session |
| Entry routing / guards not enforced | Register the harness hooks via `update-config` (see Step 3) |
| Design skills can't resolve the design-system doctrine | Re-run the installer so core components (`design-doctrine.md`) are restored |

See [Install.md](Install.md) for the full installation procedure and
[docs/directory-structure.md](docs/directory-structure.md) for the expected
layout.
