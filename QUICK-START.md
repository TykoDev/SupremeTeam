# Supreme Team — Quick Start

## Step 1: Install The Skills

Start with the automatic installation option: add [`Install.md`](Install.md) to
your coding agent's context and ask it to install Supreme Team. If you reference
`Install.md` directly from a GitHub URL, tell the agent to use the Remote URL
Install flow: download the repository archive to a temp directory, extract it,
copy `skills/.` directly into the skill target, verify, then delete the temp
files. It should not try to run local install scripts until a checkout/archive
exists on disk.

If you prefer to install manually from a local checkout, use the helper scripts
in [`scripts/`](scripts/).
They install the common `.agents/skills` target and can also add locally
confirmed host-native mirrors. During upgrades, existing host-native mirrors
such as `.codex/skills` and `.claude/skills` are refreshed instead of being left
behind. Cursor is refreshed in auto mode only when `~/.cursor/skills` already
contains a Supreme Team install; explicit Cursor targeting creates or updates
that global mirror.

### Automatic Agent Install

```text
Read Install.md and install Supreme Team for this assistant.
Use the default all-teams install unless a safer local target is obvious.
If Install.md came from a GitHub URL, download the repo archive and copy skills/.
```

### Manual Windows Install

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

### Manual macOS / Linux Install

```bash
bash ./scripts/install.sh
```

### Manual Script Options

| Goal | Windows | macOS / Linux |
|------|---------|---------------|
| Install specific teams | `-Team Design,Review` | `--team design --team review` |
| Explicit host target | `-Target Codex,Claude` | `--target codex --target claude` |
| Register runtime hooks | `-RegisterHooks` | `--register-hooks` |
| Custom common path | `-Destination "path"` | `--destination "path"` |
| Custom Codex path | `-CodexDestination "path"` | `--codex-destination "path"` |
| Custom Claude path | `-ClaudeDestination "path"` | `--claude-destination "path"` |
| Custom Cursor path | `-CursorDestination "path"` | `--cursor-destination "path"` |
| Custom OpenCode path | `-OpenCodeDestination "path"` | `--opencode-destination "path"` |

`-InstallClaude` and `--install-claude` still work as compatibility aliases for
selecting the Claude target.

Available teams: `Design`, `Build`, `Review`, `Browser`, `Release`, `Safety`,
`Testing`, or `All`.

Host targets: `auto`, `codex`, `claude`, `cursor`, `opencode`.

`auto` always updates the common `.agents/skills` target. It also updates
detected host-native mirrors; Codex and Cursor are mirrored only when an
existing Supreme Team install is found in their host-native skill directory.
Explicit `-Target Codex` / `--target codex` or `-Target Cursor` /
`--target cursor` creates or updates that host-native mirror.

### Successful Output

The install succeeded when you see:

```text
Supreme Team installation complete.
Target: ...
Host targets: ...
Host mirrors: ...
Teams: ...
Hook registration: ...
```

## Step 2: Optional Hook Registration

Runtime hooks are not registered during a normal install. To enable deterministic
entry routing and tool guards, opt in explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks
```

```bash
bash ./scripts/install.sh --register-hooks
```

Then open `/hooks` or restart the host if it requires hook review or reload.

Manual verification:

```bash
python skills/harness/hooks/verify_registration.py --host auto
```

## Step 3: Restart Your Assistant

Restart any running assistant session so it reloads installed skills and any new
hook configuration.

## Step 4: Verify Skill Discovery

Ask your assistant:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

It should identify `admiral`, the design/build/review sub-pipelines, standalone
tool groups, and shared doctrine/protocol files.

## Step 5: Start Using Supreme Team

### Full Pipeline

```text
Use the admiral skill to design, build, and review this project:
[describe your project]
```

### Design / Build / Review

```text
Design [your idea].
Implement this approved design.
Review this codebase.
```

These initiate through `admiral` automatically when entry routing is active.

### Investigate

```text
Find the root cause of this failure.
```

### Create Skills Or Teams

```text
Use the skill-maker skill to create a skill that [behavior].
```

### Standalone Tools

```text
Use the open-browser skill to launch a browser workspace.
Use the browse skill to click through the app and capture evidence.
Use the ship skill to coordinate this release.
Use the freeze skill to protect src/payments from edits.
Use the qa skill to test this product and fix what's broken.
```

## Manual Install Fallback

Use this only when the scripts cannot run. For upgrades, follow
[`Install.md`](Install.md)'s managed multi-target direct-copy steps so existing
`.codex/skills`, `.claude/skills`, and eligible host-native mirrors are
refreshed. The short commands below install only the common target.

### macOS / Linux

```bash
cd /path/to/SupremeTeam
mkdir -p "$HOME/.agents/skills"
cp -R skills/. "$HOME/.agents/skills/"
```

### Windows

```powershell
cd C:\path\to\SupremeTeam
$destination = Join-Path $env:USERPROFILE ".agents\skills"
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Recurse -Force (Join-Path "skills" "*") -Destination $destination
```

See [Install.md](Install.md) for the full installation procedure and host-specific
hook details.
