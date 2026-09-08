# Installing Supreme Team

Installing means one thing: copy the `skills/` tree into the skill directory your
assistant reads from. **Do not flatten, rename, or cherry-pick skill folders** —
skills resolve shared doctrine and scripts by relative path, so a flattened tree
is a broken tree. The bundled installers handle target selection, host mirrors,
and stale-file cleanup for you.

## From a local checkout

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

```bash
bash ./scripts/install.sh
```

Installs the common `~/.agents/skills` target, refreshes any host mirror it finds,
and clears files from older layouts. Codex and Cursor mirrors are created only
when named or already present. Re-run the same command to upgrade — it overwrites
current files and removes stale ones while leaving unrelated sibling skills alone.

Common flags (full list in [QUICK-START.md](QUICK-START.md)):

| Goal | Windows | macOS / Linux |
|---|---|---|
| Pick teams | `-Team Design,Review` | `--team design --team review` |
| Pick hosts | `-Target Codex,Claude` | `--target codex --target claude` |
| Register hooks | `-RegisterHooks` | `--register-hooks` |
| Custom path | `-Destination "path"` | `--destination "path"` |

## From a GitHub URL

When handed the `Install.md` URL with no checkout on disk, **do not run
`scripts/install.*`** — they are not there yet. Download the archive, then run the
installer from inside it. Derive `<owner>`, `<repo>`, `<branch>` from the URL you
were given, trying the branch in the URL before asking.

```powershell
$archiveUrl = "https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip"
$work = Join-Path $env:TEMP ("supremeteam-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $work | Out-Null
Invoke-WebRequest -Uri $archiveUrl -OutFile (Join-Path $work "repo.zip")
Expand-Archive -LiteralPath (Join-Path $work "repo.zip") -DestinationPath $work
$repoRoot = Get-ChildItem $work -Directory -Recurse |
  Where-Object { Test-Path (Join-Path $_.FullName "scripts\install.ps1") } |
  Select-Object -First 1
if (-not $repoRoot) { throw "No Supreme Team checkout in the archive." }
powershell -ExecutionPolicy Bypass -File (Join-Path $repoRoot.FullName "scripts\install.ps1")
Remove-Item -Recurse -Force $work
```

```bash
archive_url="https://github.com/<owner>/<repo>/archive/refs/heads/<branch>.zip"
work="$(mktemp -d)"
curl -L "$archive_url" -o "$work/repo.zip"
unzip -q "$work/repo.zip" -d "$work"
script="$(find "$work" -path '*/scripts/install.sh' -print -quit)"
test -n "$script" || { echo "No Supreme Team checkout in the archive." >&2; exit 1; }
bash "$script"
rm -rf "$work"
```

## Where it goes

The common `.agents/skills` target is always installed. Host-native mirrors are
added when there is local evidence of the host.

| Target | macOS / Linux | Windows |
|---|---|---|
| Common | `~/.agents/skills/` | `%USERPROFILE%\.agents\skills\` |
| Claude Code | `~/.claude/skills/` | `%USERPROFILE%\.claude\skills\` |
| OpenCode | `~/.config/opencode/skills/` | `%USERPROFILE%\.config\opencode\skills\` |
| Codex | `~/.codex/skills/` | `%USERPROFILE%\.codex\skills\` |
| Cursor | `~/.cursor/skills/` | `%USERPROFILE%\.cursor\skills\` |

Claude Code and OpenCode mirror automatically when present. Codex and Cursor
mirror only when named explicitly or already holding an install. On upgrade,
every existing mirror is refreshed. Core components are never optional, even for a
single-team install: every skill resolves the root doctrine files, and every
`gatekeeper-*` depends on `harness/gatekeeper/`.

## Python

The harness, hook verifier, and registration helper need **Python 3.13 or newer**
([`skills/runtime-manifest.yaml`](skills/runtime-manifest.yaml) is the authority).
Check with `python --version`, `py -3 --version`, or `python3 --version`. If none
is 3.13+, ask before installing one; the skill files still copy without it, but
hook verification and registration stay unavailable.

## Runtime hooks

Copying `skills/harness/` puts the three hooks (`pre_tool_use.py`,
`post_tool_use.py`, `user_prompt_submit.py`) in place but does **not** register
them — registration changes runtime behavior, so it is always explicit.

```bash
# Inspect current state
python skills/harness/hooks/verify_registration.py --host auto
# Register (or pass -RegisterHooks / --register-hooks to the installer)
python scripts/install_hooks.py --target codex --hook-root "$HOME/.agents/skills/harness/hooks"
```

`--host` / `--target` take `codex`, `claude`, or `copilot` for native JSON config;
`cursor` and `opencode` load a plugin package that is not machine-verifiable. The
helper writes atomically, keeps a timestamped `.bak-` copy, is idempotent, and
leaves unrelated keys alone. Afterward open `/hooks` or restart the host. Without
hooks, entry routing and tool guards are advisory only.

## Verify

Restart the assistant, then ask:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

A good install names `admiral` as the entry orchestrator, the design/build/review
pipelines, the investigation, session-memory, and skill-maker components, the
standalone browser/release/safety/testing groups, and the shared doctrine files.
Once a run is active, one command covers Python, hooks, and saves:

```bash
python skills/harness/hooks/check_readiness.py --host auto --require-active-run
```

## Manual install (fallback)

If the scripts will not run, copy the skills folder content into the common target
by hand, then register the hooks. This skips host-mirror refresh and stale-file
cleanup, so prefer the installer for upgrades. Needs **Python 3.13 or newer** for
the hook step.

```powershell
$destination = Join-Path $env:USERPROFILE ".agents\skills"
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Recurse -Force (Join-Path "skills" "*") -Destination $destination
python scripts\install_hooks.py --target claude --hook-root "$destination\harness\hooks"
```

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/. "$HOME/.agents/skills/"
python scripts/install_hooks.py --target claude --hook-root "$HOME/.agents/skills/harness/hooks"
```

Swap `--target` for your host (`codex`, `claude`, `copilot`; `cursor`/`opencode`
write a plugin package). Skip the hook line to leave routing and guards advisory.

## When it goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Skills not discovered | Wrong target path, or a stale session | Check the path, restart the assistant |
| `admiral` missing | Tree flattened or copied from the wrong source | Copy `skills/` again, preserving directories |
| Remote install fails | Ran local scripts from a raw URL | Download and extract the archive first |
| Python commands fail | Python missing or below the manifest floor | Install a supported Python, re-check |
| Gatekeepers can't find `_gatecheck.py` | `harness/` was skipped | Use the installer or copy every core component |
| Resume and saves broken | `save-protocol.md` was skipped | Copy the root doctrine files |
| Hooks not enforced | Never registered, trusted, or reloaded | Register explicitly, then reload the host |
