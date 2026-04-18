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

Available teams: `Design`, `Build`, `Review`, `Azure` (or `All`).

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
| `admiral/` | Top-level pipeline orchestrator |
| `gatekeeper-admiral/` | Cross-pipeline adversarial validator |
| `session-memory/` | Cross-session state and learnings manager |
| `references/` | Shared handoff templates |
| `save-protocol.md` | Persistent save system specification |

Plus whichever team directories you selected (`design/`, `build/`, `review/`,
`azure/`).

---

## Step 2: Restart Your Assistant Session

If your AI assistant was already running, restart it so it picks up the new
skills.

## Step 3: Verify Skill Discovery

Ask your assistant:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

If configured correctly, it should identify admiral, the sub-pipelines, and
shared resources.

## Step 4: Start Using Supreme Team

### Full Pipeline (Idea to Reviewed Code)

```text
Use the admiral skill to design, build, and review this project:
[describe your project]
```

### Design Only

```text
Use the commander skill to design [your idea].
```

### Build from a Plan

```text
Use the build-management skill to implement this approved design.
```

### Review Existing Code

```text
Use the code-chief skill to do a full code review of this codebase.
```

### Deploy to Azure

```text
Use the azure-provisioner skill to deploy this application to Azure.
```

### Individual Skills

```text
Use the bug-review skill on src/auth/ to find correctness defects.
Use the security-review skill to audit this module for vulnerabilities.
Use the mr-robot skill to adversarially test this API.
Use the frontier skill to audit the frontend for accessibility.
Use the design-qa skill to check visual consistency of the UI.
Use the devex-review skill to test the developer onboarding experience.
Use the test-builder skill to create a test suite for this module.
Use the debugger skill to investigate this failing test.
Use the health-check skill to run a code quality dashboard.
Use the session-memory skill to checkpoint progress.
```

If your tool supports slash-style skill commands, you can use that syntax
as shorthand.

## Updating

Re-run the installer script. Each run replaces the Supreme Team-managed paths
in the target directory while leaving unrelated entries alone.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| PowerShell blocks `install.ps1` | Use `powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1` |
| Installer says `skills/` source is missing | Run the installer from the Supreme Team repository root |
| Skills are not discovered | Check the install target path, restart the assistant session |
| Design skills can't find stack templates | Re-run installer with Design or All |
| Review can't find shared templates | Re-run installer to restore core components |

See [Install.md](Install.md) for the full installation procedure and
[docs/directory-structure.md](docs/directory-structure.md) for the expected
layout.
