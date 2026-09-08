# Quick Start

Five steps. The first one is the only one that is strictly required.

## 1. Install the skills

Pick one of the two setup options below.

### Option A — Let your coding agent do it

```text
Read Install.md and install Supreme Team for this assistant.
Use the default all-teams install unless a safer local target is obvious.
If Install.md came from a GitHub URL, download the repo archive and copy skills/.
```

That last line matters. If the agent is reading `Install.md` straight from a
GitHub URL, there is no checkout on disk yet, so it has to download the archive
first instead of trying to run scripts that are not there.

### Option B — Run the installer yourself

From a local checkout:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

```bash
bash ./scripts/install.sh
```

It installs to the common `~/.agents/skills` target and refreshes any host-native
mirror it finds. Codex and Cursor mirrors are only created when you ask for them
by name, or when one already exists.

### Installer options

| Goal | Windows | macOS / Linux |
|---|---|---|
| Pick teams | `-Team Design,Review` | `--team design --team review` |
| Pick hosts | `-Target Codex,Claude` | `--target codex --target claude` |
| Register hooks | `-RegisterHooks` | `--register-hooks` |
| Custom path | `-Destination "path"` | `--destination "path"` |

Teams: `Design`, `Build`, `Review`, `Browser`, `Release`, `Safety`, `Testing`,
`All`. Hosts: `auto`, `codex`, `claude`, `cursor`, `opencode`. Per-host
destination flags exist too (`-CodexDestination`, `--claude-destination`, and so
on); `-InstallClaude` and `--install-claude` are older aliases for the Claude
target.

You will know it worked when the installer prints its summary:

```text
Supreme Team installation complete.
Target: ...
Host targets: ...
Host mirrors: ...
Teams: ...
Hook registration: ...
```

## 2. Register the hooks (optional, recommended)

A normal install copies the hook files but does not wire them into your host.
That is deliberate: hooks change assistant runtime behavior, so turning them on
is an explicit choice.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks
```

```bash
bash ./scripts/install.sh --register-hooks
```

Then open `/hooks` or restart the host if it wants to review them first.

Without hooks everything still works, but entry routing and write guards become
advisory rather than enforced, and the run heartbeat only refreshes when a
checkpoint happens.

## 3. Restart your assistant

So it picks up the new skills and hook config.

## 4. Verify

```bash
python skills/harness/hooks/check_readiness.py --host auto
python skills/scripts/check_runtime.py
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
```

`check_readiness.py` gives you a capability map, not a pass or fail:
`python_runtime`, `hooks_configured`, `hooks_executable`, `hooks_observed`,
`saves_readable`, `active_run`, `deterministic_validators`. Missing hooks knock
out deterministic enforcement and leave everything else intact.

`hooks_observed` stays `unverified` until a hook actually fires. Reading config
proves a hook is registered, never that it ran, and the diagnostic will not
pretend otherwise.

If a hook is missing, look at the repair before you apply it:

```bash
python skills/harness/hooks/repair_registration.py --host claude --scope project
python skills/harness/hooks/repair_registration.py --host claude --scope project --apply
```

The preview is the default, and it never touches global host config unless you
ask for `--scope user`.

Then ask your assistant:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

It should come back with `admiral`, the design, build, and review pipelines, the
security, investigation, QA, skill-creation, and release pipelines, the
standalone tool groups, and the shared doctrine files.

## 5. Use it

Full pipeline:

```text
Use the admiral skill to design, build, and review this project:
[describe your project]
```

Or just say what you want. Entry routing sends these through `admiral` on its
own:

```text
Design [your idea].
Implement this approved design.
Review this codebase.
Find the root cause of this failure.
Audit this codebase for security issues.
Test this product and fix what's broken.
Use the skill-maker skill to create a skill that [behavior].
```

Standalone tools you can call directly, any time:

```text
Use the open-browser skill to launch a browser workspace.
Use the browse skill to click through the app and capture evidence.
Use the ship skill to coordinate this release.
Use the freeze skill to protect src/payments from edits.
Use the qa skill to test this product and fix what's broken.
```

### Small stuff stays small

A typo, a link, a narrow docs edit, a bug whose cause you already know: that runs
directly on the Tier 0 fast path. No interview, no saved run, no gate package.
You get the change, the checks that were actually run, and anything still
unresolved.

Security, deployment, and production changes never qualify, however small.

## If the scripts will not run

Manual copy of the common target. For upgrades, follow
[Install.md](Install.md) instead so existing host mirrors get refreshed too.

```bash
cd /path/to/SupremeTeam
mkdir -p "$HOME/.agents/skills"
cp -R skills/. "$HOME/.agents/skills/"
```

```powershell
cd C:\path\to\SupremeTeam
$destination = Join-Path $env:USERPROFILE ".agents\skills"
New-Item -ItemType Directory -Force -Path $destination | Out-Null
Copy-Item -Recurse -Force (Join-Path "skills" "*") -Destination $destination
```
