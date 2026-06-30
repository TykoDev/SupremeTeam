# Supreme Team — Agent Installation Guide

This guide is written for coding agents that can read and write the local file
system. Install Supreme Team by copying the grouped `skills/` source tree into
the skill discovery paths used by the active assistant host.

Do not flatten, rename, or cherry-pick individual skill folders. The tree shape
is load-bearing because skills resolve shared doctrine, gatekeeper scripts, and
handoff references by relative path.

For a human-operated fallback from a local checkout, use the helper scripts in
[`scripts/`](scripts/). If this file was opened directly from a GitHub URL and
there is no local checkout yet, use the **Remote URL Install** flow below rather
than trying to run repository scripts that are not present on disk.

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
| Codex skills | `~/.codex/skills/` | `%USERPROFILE%\.codex\skills\` |
| Claude Code skills | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |
| Cursor skills | `~/.cursor/skills/` | `%USERPROFILE%\.cursor\skills\` |
| OpenCode skills | `~/.config/opencode/skills/` | `%USERPROFILE%\.config\opencode\skills\` |

The common `.agents/skills` target is always installed. Some hosts also read
host-native skill directories. During upgrades, refresh every existing
host-native Supreme Team target so old copies do not remain discoverable.
Codex is mirrored automatically only when `~/.codex/skills/` already exists; an
explicit Codex target creates or updates that mirror.

Use local evidence before adding host-native mirrors:

| Host | Evidence | Install target |
|------|----------|----------------|
| Codex | `codex` on PATH or `~/.codex/` exists | common `.agents/skills`; also existing `.codex/skills`, or create it when Codex is explicitly targeted |
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

## Managed Upgrade Boundary

Installs and upgrades own only the Supreme Team paths listed below. Before
copying fresh files into an existing target, remove these paths if they are
present, then copy the new `skills/` contents. This overwrites current Supreme
Team files and removes stale Supreme Team files from older layouts while
preserving unrelated sibling skills in the same host directory.

Managed current paths:

- `admiral/`
- `gatekeeper-admiral/`
- `session-memory/`
- `investigate/`
- `skill-maker/`
- `harness/`
- `design/`
- `build/`
- `review/`
- `browser-automation/`
- `release-and-deployment/`
- `safety-guardrails/`
- `testing-and-qa/`
- `design-doctrine.md`
- `grill-me-doctrine.md`
- `harness-doctrine.md`
- `mcp-tools.md`
- `routing-doctrine.md`
- `save-protocol.md`

Known legacy paths from older Supreme Team layouts:

- `azure/`
- `references/`
- `design/tech-stacks/`

Do not delete the entire host skill directory unless the user explicitly
confirms that it contains no unrelated skills.

## Remote URL Install

Use this path when the user references `Install.md` from a repository URL and no
local Supreme Team checkout is available. Keep it simple:

1. Download the repository archive to a temporary directory.
2. Extract the archive.
3. Find the extracted directory that contains `skills/admiral/SKILL.md`.
4. Build the target list: the common `.agents/skills` target plus every existing
   host-native skills target from **Default Targets**. Include `.codex/skills`
   when it already exists, and include it when the user explicitly asks for
   Codex.
5. Remove the managed current paths and known legacy paths from each selected
   skill target if they are present.
6. Copy `skills/.` directly into each selected skill target, preserving structure.
7. Verify every selected target contains `admiral/SKILL.md`,
   `harness/hooks/verify_registration.py`, `harness/hooks/check_readiness.py`,
   and the root doctrine files.
8. Delete the temporary download/extract directory.
9. Ask the user before registering hooks or installing Python.

Do not use `scripts/install.ps1` or `scripts/install.sh` for this path unless the
user explicitly asks for the script wrapper after the archive has been extracted.
Those scripts are local-checkout helpers; a raw `Install.md` URL by itself does
not provide the script files or the `skills/` tree.

### GitHub Archive Pattern

For a GitHub repository URL, download the branch archive:

```text
https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip
```

If the `Install.md` URL is a raw GitHub URL, derive `<owner>`, `<repo>`, and
`<branch>` from the raw path, then use the archive URL above. If the branch is
unknown, try the branch in the raw URL first, then ask the user before guessing a
different default branch.

### Windows Remote Copy

```powershell
$archiveUrl = "https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip"
$work = Join-Path $env:TEMP ("supremeteam-" + [guid]::NewGuid().ToString("N"))
$zip = Join-Path $work "repo.zip"
$destinations = @(
  (Join-Path $env:USERPROFILE ".agents\skills")
)

foreach ($candidate in @(
  (Join-Path $env:USERPROFILE ".codex\skills"),
  (Join-Path $env:USERPROFILE ".claude\skills"),
  (Join-Path $env:USERPROFILE ".cursor\skills"),
  (Join-Path $env:USERPROFILE ".config\opencode\skills")
)) {
  if (Test-Path -LiteralPath $candidate) {
    $destinations += $candidate
  }
}

New-Item -ItemType Directory -Force -Path $work | Out-Null
Invoke-WebRequest -Uri $archiveUrl -OutFile $zip
Expand-Archive -LiteralPath $zip -DestinationPath $work
$repoRoot = Get-ChildItem -Path $work -Directory -Recurse |
  Where-Object { Test-Path (Join-Path $_.FullName "skills\admiral\SKILL.md") } |
  Select-Object -First 1

if (-not $repoRoot) { throw "Could not find Supreme Team skills directory in archive." }

$managed = @(
  "admiral",
  "gatekeeper-admiral",
  "session-memory",
  "investigate",
  "skill-maker",
  "harness",
  "design",
  "build",
  "review",
  "browser-automation",
  "release-and-deployment",
  "safety-guardrails",
  "testing-and-qa",
  "design-doctrine.md",
  "grill-me-doctrine.md",
  "harness-doctrine.md",
  "mcp-tools.md",
  "routing-doctrine.md",
  "save-protocol.md",
  "azure",
  "references",
  "design\tech-stacks"
)

foreach ($destination in $destinations) {
  New-Item -ItemType Directory -Force -Path $destination | Out-Null

  foreach ($item in $managed) {
    $path = Join-Path $destination $item
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Recurse -Force
    }
  }

  Copy-Item -Recurse -Force (Join-Path $repoRoot.FullName "skills\*") -Destination $destination
  foreach ($required in @(
    "admiral\SKILL.md",
    "harness\hooks\verify_registration.py",
    "harness\hooks\check_readiness.py",
    "save-protocol.md"
  )) {
    if (-not (Test-Path -LiteralPath (Join-Path $destination $required))) {
      throw "Missing required installed file '$required' in '$destination'."
    }
  }
}

Remove-Item -Recurse -Force $work
```

### macOS / Linux Remote Copy

```bash
archive_url="https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip"
work="$(mktemp -d)"
destinations=("$HOME/.agents/skills")

for candidate in \
  "$HOME/.codex/skills" \
  "$HOME/.claude/skills" \
  "$HOME/.cursor/skills" \
  "$HOME/.config/opencode/skills"
do
  if [ -d "$candidate" ]; then
    destinations+=("$candidate")
  fi
done

curl -L "$archive_url" -o "$work/repo.zip"
unzip -q "$work/repo.zip" -d "$work"
repo_root="$(find "$work" -path "*/skills/admiral/SKILL.md" -print -quit)"
repo_root="${repo_root%/skills/admiral/SKILL.md}"

test -n "$repo_root" || { echo "Could not find Supreme Team skills directory in archive." >&2; exit 1; }

for destination in "${destinations[@]}"; do
  mkdir -p "$destination"
  for item in \
    admiral \
    gatekeeper-admiral \
    session-memory \
    investigate \
    skill-maker \
    harness \
    design \
    build \
    review \
    browser-automation \
    release-and-deployment \
    safety-guardrails \
    testing-and-qa \
    design-doctrine.md \
    grill-me-doctrine.md \
    harness-doctrine.md \
    mcp-tools.md \
    routing-doctrine.md \
    save-protocol.md \
    azure \
    references \
    design/tech-stacks
  do
    rm -rf "$destination/$item"
  done

  cp -R "$repo_root/skills/." "$destination/"
  for required in \
    admiral/SKILL.md \
    harness/hooks/verify_registration.py \
    harness/hooks/check_readiness.py \
    save-protocol.md
  do
    test -f "$destination/$required"
  done
done

rm -rf "$work"
```

## Direct Local Install Steps

1. Resolve the repository root that contains this `Install.md`.
2. Verify Python 3.13+ is installed; if missing or outdated, ask the user before
   installing it.
3. Select target directories from the table above. Include the common target and
   every existing host-native mirror; include `.codex/skills` when it already
   exists, or when Codex is explicitly requested.
4. Create each selected target directory if missing.
5. Remove managed current paths and known legacy paths from each target if they
   are present. Preserve unrelated sibling skills.
6. Copy `skills/` contents into each target, preserving directory structure.
7. Verify every target contains `admiral/SKILL.md`,
   `harness/hooks/verify_registration.py`, `harness/hooks/check_readiness.py`,
   and the shared doctrine files.
8. Restart or reload the assistant so it refreshes skill discovery.

### Windows Direct Copy

Run from the Supreme Team repository root, or adapt `$repoRoot` to the checkout
path:

```powershell
$repoRoot = (Get-Location).Path
$source = Join-Path $repoRoot "skills"
$destinations = @(
  (Join-Path $env:USERPROFILE ".agents\skills")
)

foreach ($candidate in @(
  (Join-Path $env:USERPROFILE ".codex\skills"),
  (Join-Path $env:USERPROFILE ".claude\skills"),
  (Join-Path $env:USERPROFILE ".cursor\skills"),
  (Join-Path $env:USERPROFILE ".config\opencode\skills")
)) {
  if (Test-Path -LiteralPath $candidate) {
    $destinations += $candidate
  }
}

$managed = @(
  "admiral",
  "gatekeeper-admiral",
  "session-memory",
  "investigate",
  "skill-maker",
  "harness",
  "design",
  "build",
  "review",
  "browser-automation",
  "release-and-deployment",
  "safety-guardrails",
  "testing-and-qa",
  "design-doctrine.md",
  "grill-me-doctrine.md",
  "harness-doctrine.md",
  "mcp-tools.md",
  "routing-doctrine.md",
  "save-protocol.md",
  "azure",
  "references",
  "design\tech-stacks"
)

foreach ($destination in $destinations) {
  New-Item -ItemType Directory -Force -Path $destination | Out-Null

  foreach ($item in $managed) {
    $path = Join-Path $destination $item
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Recurse -Force
    }
  }

  Copy-Item -Recurse -Force (Join-Path $source "*") -Destination $destination -ErrorAction Stop
  foreach ($required in @(
    "admiral\SKILL.md",
    "harness\hooks\verify_registration.py",
    "harness\hooks\check_readiness.py",
    "save-protocol.md"
  )) {
    if (-not (Test-Path -LiteralPath (Join-Path $destination $required))) {
      throw "Missing required installed file '$required' in '$destination'."
    }
  }
}
```

### macOS / Linux Direct Copy

Run from the Supreme Team repository root, or adapt `repo_root` to the checkout
path:

```bash
repo_root="$(pwd)"
source="$repo_root/skills"
destinations=("$HOME/.agents/skills")

for candidate in \
  "$HOME/.codex/skills" \
  "$HOME/.claude/skills" \
  "$HOME/.cursor/skills" \
  "$HOME/.config/opencode/skills"
do
  if [ -d "$candidate" ]; then
    destinations+=("$candidate")
  fi
done

for destination in "${destinations[@]}"; do
  mkdir -p "$destination"
  for item in \
    admiral \
    gatekeeper-admiral \
    session-memory \
    investigate \
    skill-maker \
    harness \
    design \
    build \
    review \
    browser-automation \
    release-and-deployment \
    safety-guardrails \
    testing-and-qa \
    design-doctrine.md \
    grill-me-doctrine.md \
    harness-doctrine.md \
    mcp-tools.md \
    routing-doctrine.md \
    save-protocol.md \
    azure \
    references \
    design/tech-stacks
  do
    rm -rf "$destination/$item"
  done

  cp -R "$source/." "$destination/"
  for required in \
    admiral/SKILL.md \
    harness/hooks/verify_registration.py \
    harness/hooks/check_readiness.py \
    save-protocol.md
  do
    test -f "$destination/$required"
  done
done
```

## Host-Native Mirrors

When local evidence confirms a host, repeat the managed-clean copy into that
host's native skill directory as well as the common `.agents/skills` target. For
upgrades, every existing host-native Supreme Team directory must be refreshed
and verified; do not stop after the common target succeeds.

Codex mirror rule: auto mode updates `.codex/skills` only when that directory
already exists. If the user explicitly selects Codex, create or update
`.codex/skills`.

Examples:

| Host | Windows destination | macOS / Linux destination |
|------|---------------------|---------------------------|
| Codex | `%USERPROFILE%\.codex\skills` | `~/.codex/skills` |
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
intake, or use the helper script directly from a local checkout:

```bash
python scripts/install_hooks.py --target codex --hook-root "$HOME/.agents/skills/harness/hooks"
```

Use `--target claude`, `--target cursor`, or `--target opencode` for other
hosts. Repeat `--target` to register more than one host.

After registration, open `/hooks` or restart the host if it requires hook review
or reload. Codex and Claude may require explicit trust before newly registered
hooks execute.

Without registered hooks, Supreme Team still works through skills and doctrine,
but deterministic entry routing and pre/post tool enforcement are advisory only.

After Admiral has activated or resumed a run, the combined runtime diagnostic can
confirm Python, hooks, and active saves together:

```bash
python skills/harness/hooks/check_readiness.py --host auto --require-active-run
```

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

Use the same managed-clean flow as a fresh install:

1. Resolve all existing Supreme Team skill targets: the common `.agents/skills`
   target plus any host-native mirrors such as `.codex/skills`,
   `.claude/skills`, `.cursor/skills`, and `.config/opencode/skills`.
2. Remove only the managed current paths and known legacy paths listed in
   **Managed Upgrade Boundary** from each target.
3. Copy the new `skills/` contents into every target.
4. Verify required files and hook readiness in every target. At minimum verify
   `admiral/SKILL.md`, `harness/hooks/verify_registration.py`,
   `harness/hooks/check_readiness.py`, and the root doctrine/protocol files.
5. Restart or reload the assistant so skill discovery refreshes.

This is the default upgrade path. It overwrites current Supreme Team files,
removes stale Supreme Team files from older installs in every selected target,
and preserves unrelated sibling skills. Do not use overlay-only copy for
upgrades unless the user explicitly accepts the risk of stale removed skills
remaining discoverable.

## Manual Script Fallback

Use the helper scripts only when a human wants a wrapper around the direct copy
and validation flow. The scripts run the same managed-clean refresh described
above. In auto mode they refresh existing host-native mirrors; explicit
`-Target Codex` / `--target codex` creates or updates the Codex mirror.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

```bash
bash ./scripts/install.sh
```

Script options remain available for team selection, explicit host targets,
custom destinations, host-native mirror destinations, and hook registration. See the script help or
[`scripts/`](scripts/) for details.

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| Skills are not discovered | Wrong target path or stale assistant session | Verify the target path and restart the assistant session |
| `admiral` is missing | The tree was flattened or copied from the wrong source | Copy the contents of `skills/` again, preserving directories |
| Remote URL install fails | The agent tried to run local scripts from a raw `Install.md` URL | Use the Remote URL Install flow: download archive, extract, copy `skills/.`, verify |
| Python verifier commands fail | Python is missing or older than 3.13 | Ask the user for approval to install Python 3.13+, install from a trusted source, then re-run the version check |
| Gatekeepers cannot find `_gatecheck.py` | `harness/` was omitted | Copy the required core components |
| Resume or save artifacts do not work | `save-protocol.md` was omitted | Copy the required root doctrine/protocol files |
| Hooks are not enforced | Hook registration was not requested, trusted, or loaded | Register hooks explicitly, then reload or restart the host |
| Verifier reports missing hooks even though old hook names exist | Host config points at another package or stale path | Re-register hooks so config points at this Supreme Team checkout |
