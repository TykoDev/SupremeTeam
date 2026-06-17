# Supreme Team — Agent Installation Guide

This guide is written for coding agents that can read and write the local file
system. Install Supreme Team by copying the grouped `skills/` source tree into
the skill discovery paths used by the active assistant host.

Do not flatten, rename, or cherry-pick individual skill folders. The tree shape
is load-bearing because skills resolve shared doctrine, gatekeeper scripts, and
handoff references by relative path.

For a human-operated fallback, use the helper scripts in [`scripts/`](scripts/).

## Agent Install Contract

Before installing, confirm these repository paths exist:

- `skills/admiral/SKILL.md`
- `skills/gatekeeper-admiral/SKILL.md`
- `skills/harness/hooks/verify_registration.py`
- `skills/routing-doctrine.md`
- `skills/grill-me-doctrine.md`
- `skills/save-protocol.md`

Then copy the selected Supreme Team directories and root doctrine files into one
or more host skill paths.

Default install scope is **all teams**. Partial installs are allowed, but the
core components are always required.

## Python Prerequisite

Supreme Team's runtime harness, hook verifier, and hook registration helpers use
Python. Before installation, verify that Python **3.13 or newer** is available.

Check local commands in this order and use the first one that reports version
`3.13.x` or newer:

### Windows

```powershell
py -3.13 --version
python --version
python3 --version
```

### macOS / Linux

```bash
python3 --version
python --version
```

If no Python command exists, or the newest detected version is older than 3.13,
do not install Python silently. Prompt the user for approval first:

```text
Supreme Team needs Python 3.13+ for hook verification and runtime harness
helpers. I found no compatible Python installation. Do you want me to install
Python 3.13 or newer for this system?
```

Only after approval, install Python 3.13+ using a trusted system package source
appropriate for the host, such as `winget` on Windows, Homebrew on macOS, or the
distribution package manager on Linux. Re-run the version check after
installation. If the user declines, continue with the skill file copy, but warn
that hook verification and hook registration cannot run until Python 3.13+ is
available.

## Default Targets

| Target | Linux / macOS | Windows |
|--------|---------------|---------|
| Common Agent Skills | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Claude Code skills | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |
| Cursor skills | `~/.cursor/skills/` | `%USERPROFILE%\.cursor\skills\` |
| OpenCode skills | `~/.config/opencode/skills/` | `%USERPROFILE%\.config\opencode\skills\` |

Codex uses the common `.agents/skills` path and does not require a separate
mirror.

Use local evidence before adding host-native mirrors:

| Host | Evidence | Install target |
|------|----------|----------------|
| Codex | `codex` on PATH or `~/.codex/` exists | common `.agents/skills` |
| Claude Code | `claude` on PATH or `~/.claude/` exists | `.claude/skills` |
| Cursor | `cursor` on PATH, `~/.cursor/`, or app config exists | `.cursor/skills` |
| OpenCode | `opencode` on PATH or `~/.config/opencode/` exists | `.config/opencode/skills` |

## What To Copy

Always copy these core components:

| Source under `skills/` | Purpose |
|------------------------|---------|
| `admiral/` | Primary entry orchestrator |
| `gatekeeper-admiral/` | Cross-stage adversarial validator |
| `session-memory/` | Cross-session checkpoints and durable learnings |
| `investigate/` | Root-cause analysis component |
| `skill-maker/` | Skill and coordinated team creation |
| `harness/` | Runtime hooks and deterministic gate engine |
| `routing-doctrine.md` | Entry-routing contract |
| `grill-me-doctrine.md` | Intake interview protocol |
| `design-doctrine.md` | Frontend/UI design-system doctrine |
| `harness-doctrine.md` | Runtime harness doctrine |
| `mcp-tools.md` | Global MCP tool registry |
| `save-protocol.md` | Persistent save system specification |

Selectable teams:

| Team | Source directory | Skills |
|------|------------------|--------|
| Design | `design/` | 6 skills |
| Build | `build/` | 8 skills |
| Review | `review/` | 11 skills |
| Browser | `browser-automation/` | 4 standalone tools |
| Release | `release-and-deployment/` | 4 standalone tools |
| Safety | `safety-guardrails/` | 4 standalone tools |
| Testing | `testing-and-qa/` | 3 standalone tools |

For the default all-teams install, copy the full contents of `skills/` into each
selected target.

## Direct Install Steps

1. Resolve the repository root that contains this `Install.md`.
2. Verify Python 3.13+ is installed; if missing or outdated, ask the user before
   installing it.
3. Select target directories from the table above.
4. Create each target directory if missing.
5. Copy `skills/` contents into each target, preserving directory structure.
6. Remove stale Supreme Team legacy paths from the target if present:
   `azure/`, `references/`, and `design/tech-stacks/`.
7. Verify each target contains `admiral/SKILL.md` and the shared doctrine files.
8. Restart or reload the assistant so it refreshes skill discovery.

### Windows Direct Copy

Run from the Supreme Team repository root, or adapt `$repoRoot` to the checkout
path:

```powershell
$repoRoot = (Get-Location).Path
$source = Join-Path $repoRoot "skills"
$destination = Join-Path $env:USERPROFILE ".agents\skills"

New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Recurse -Force (Join-Path $source "*") -Destination $destination -ErrorAction Stop

foreach ($stale in @("azure", "references", "design\tech-stacks")) {
  $path = Join-Path $destination $stale
  if (Test-Path $path) {
    Remove-Item -Recurse -Force $path
  }
}

Test-Path (Join-Path $destination "admiral\SKILL.md")
```

### macOS / Linux Direct Copy

Run from the Supreme Team repository root, or adapt `repo_root` to the checkout
path:

```bash
repo_root="$(pwd)"
source="$repo_root/skills"
destination="$HOME/.agents/skills"

mkdir -p "$destination"
cp -R "$source/." "$destination/"

rm -rf "$destination/azure" "$destination/references" "$destination/design/tech-stacks"

test -f "$destination/admiral/SKILL.md"
```

## Host-Native Mirrors

When local evidence confirms a host, repeat the direct copy into that host's
native skill directory as well as the common `.agents/skills` target.

Examples:

| Host | Windows destination | macOS / Linux destination |
|------|---------------------|---------------------------|
| Claude Code | `%USERPROFILE%\.claude\skills` | `~/.claude/skills` |
| Cursor | `%USERPROFILE%\.cursor\skills` | `~/.cursor/skills` |
| OpenCode | `%USERPROFILE%\.config\opencode\skills` | `~/.config/opencode/skills` |

If a user asks for a custom destination, copy into that path instead and verify
the same required files.

## Partial Installs

For a partial install, copy all core components plus only the requested team
directories. Do not omit core files even when the user asks for a single team;
the orchestrators, gatekeepers, save protocol, and doctrine files are shared.

Critical dependencies:

- All skills resolve the root doctrine and protocol files.
- Every `gatekeeper-*` skill depends on `harness/gatekeeper/_gatecheck.py`.
- `design/architect` UI work depends on `design-doctrine.md`.
- `admiral` intake depends on `harness/hooks/verify_registration.py`,
  `mcp-tools.md`, and `save-protocol.md`.

## Runtime Harness Hooks

The runtime harness includes three stdlib Python hooks:

- `pre_tool_use.py`
- `post_tool_use.py`
- `user_prompt_submit.py`

Copying `skills/harness/` installs the hook files, but it does not register them
in host configuration. Hook registration is explicit opt-in because it changes
assistant runtime behavior.

Do not run the verifier or registration helper until Python 3.13+ has been
confirmed. If Python is missing or outdated, ask for approval to install Python
3.13+ first, then retry the verifier.

After installation, verify hook status from the repository root or an installed
target:

```bash
python skills/harness/hooks/verify_registration.py --host auto
```

Use `--host codex`, `--host claude`, `--host cursor`, `--host opencode`, or
`--host all` for a specific check.

If hooks are missing, let `admiral` surface the generated registration prompt at
intake, or use the helper script directly:

```bash
python scripts/install_hooks.py --host auto --repo-root .
```

After registration, open `/hooks` or restart the host if it requires hook review
or reload. Codex and Claude may require explicit trust before newly registered
hooks execute.

Without registered hooks, Supreme Team still works through skills and doctrine,
but deterministic entry routing and pre/post tool enforcement are advisory only.

## Verify Skill Discovery

Restart the assistant session, then ask:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

A successful install should identify:

- `admiral` as the entry orchestrator
- design, build, and review sub-pipelines
- investigation, session memory, and skill-maker components
- standalone browser, release, safety, and testing tool groups
- shared doctrine and protocol files, including the save protocol and harness

## Updating An Existing Install

Repeat the direct copy into the same target directories. This refreshes Supreme
Team-managed files while preserving unrelated files in the skill target.

If you need a fully clean Supreme Team refresh, remove only the Supreme
Team-managed paths listed in this guide, then copy again. Do not delete an entire
host skill directory unless the user explicitly confirms that it contains no
unrelated skills.

## Manual Script Fallback

Use the helper scripts only when a human wants a wrapper around the direct copy
and validation flow:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

```bash
bash ./scripts/install.sh
```

Script options remain available for team selection, explicit host targets,
custom destinations, and hook registration. See the script help or
[`scripts/`](scripts/) for details.

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| Skills are not discovered | Wrong target path or stale assistant session | Verify the target path and restart the assistant session |
| `admiral` is missing | The tree was flattened or copied from the wrong source | Copy the contents of `skills/` again, preserving directories |
| Python verifier commands fail | Python is missing or older than 3.13 | Ask the user for approval to install Python 3.13+, install from a trusted source, then re-run the version check |
| Gatekeepers cannot find `_gatecheck.py` | `harness/` was omitted | Copy the required core components |
| Resume or save artifacts do not work | `save-protocol.md` was omitted | Copy the required root doctrine/protocol files |
| Hooks are not enforced | Hook registration was not requested, trusted, or loaded | Register hooks explicitly, then reload or restart the host |
| Verifier reports missing hooks even though old hook names exist | Host config points at another package or stale path | Re-register hooks so config points at this Supreme Team checkout |
