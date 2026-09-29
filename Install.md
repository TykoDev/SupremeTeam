# Installing Supreme Team

Installing means one thing: copy the `skills/` tree into the skill directory your
assistant reads from. **Do not flatten, rename, or cherry-pick skill folders** —
skills resolve shared doctrine and scripts by relative path, so a flattened tree
is a broken tree. The bundled installers handle target selection, host mirrors,
and upgrades for you, and only ever replace or remove what they installed.

## From a local checkout

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

```bash
bash ./scripts/install.sh
```

Installs the common `~/.agents/skills` target, refreshes any host mirror it finds,
and retires directories left by older layouts. Codex and Cursor mirrors are created
only when named or already present. Re-run the same command to upgrade, and add
`--dry-run` (`-DryRun`) first to see what it would do without writing anything.

The installer only replaces or removes what it installed. Each target gets a
`.supremeteam-manifest` listing the items it put there, and every directory it
creates carries a `.supremeteam-managed` marker. On an upgrade:

- Items it installed are replaced. Each new copy is staged first and swapped in,
  so an interrupted run never leaves a half-copied item and puts back anything it
  had moved aside, and items that are no longer shipped are removed. Edits inside
  an installed directory are replaced too, so keep your own skills in directories
  of their own.
- Anything else in the folder is left alone, including your own skills.
- If something of yours has the same name as an installed item (`review`, `qa`,
  `scripts`, ...), it is moved, never deleted, to
  `<target>.supremeteam-backup/<timestamp>/` beside the target, and the summary
  lists it. The first upgrade over an install made before these records existed
  moves that whole old install there once; delete the folder when you have checked
  that nothing in it is yours.
- `mcp-tools.md` is the tool registry your assistant fills in, so an existing copy
  is never replaced. Delete it and re-run to get the blank template back.
- `--destination` refuses the filesystem root, your home directory or one of its
  parents, and any folder that overlaps the checkout.

Common flags (full list in [QUICK-START.md](QUICK-START.md)):

| Goal | Windows | macOS / Linux |
|---|---|---|
| Pick teams | `-Team Design,Review` | `--team design --team review` |
| Pick hosts | `-Target Codex,Claude` | `--target codex --target claude` |
| Register hooks | `-RegisterHooks` | `--register-hooks` |
| Custom path | `-Destination "path"` | `--destination "path"` |
| Preview only | `-DryRun` | `--dry-run` |

## From a GitHub URL

When handed the `Install.md` URL with no checkout on disk, **do not run
`scripts/install.*`** — they are not there yet. Download the archive of a pinned
version, check it, then run the installer from inside it. Derive `<owner>` and
`<repo>` from the URL you were given.

**Pin the version.** `<ref>` is a release tag or a full 40-character commit SHA,
never a branch or a short SHA: a branch moves, and the installer runs with the
user's permissions and writes code that assistants load automatically. If the URL
names a branch, resolve it once with `git ls-remote https://github.com/<owner>/<repo> <branch>`,
show the user the commit it points to, and install that commit.

**Verify it.** The recipes below fail on an HTTP error, expect exactly one extracted
folder, require that its name ends in the ref you asked for (GitHub names it
`<repo>-<ref>`), and run the installer from that folder only. If the maintainers
publish a SHA-256 for the archive, compare it before extracting (`sha256sum`,
`shasum -a 256`, or `(Get-FileHash <file> -Algorithm SHA256).Hash`). GitHub does not
promise byte-identical generated archives, so the commit SHA is the durable pin and
a digest is an extra check.

```powershell
$repo = "<owner>/<repo>"
$ref = "<release tag or full commit SHA>"
$work = Join-Path $env:TEMP ("supremeteam-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $work | Out-Null
Invoke-WebRequest -UseBasicParsing -ErrorAction Stop -Uri "https://github.com/$repo/archive/$ref.zip" -OutFile (Join-Path $work "repo.zip")
Expand-Archive -LiteralPath (Join-Path $work "repo.zip") -DestinationPath $work
$roots = @(Get-ChildItem -LiteralPath $work -Directory)
if ($roots.Count -ne 1 -or -not (Test-Path (Join-Path $roots[0].FullName "scripts\install.ps1"))) { throw "No Supreme Team checkout in the archive." }
if (-not $roots[0].Name.EndsWith($ref.TrimStart("v"))) { throw "The archive folder does not match $ref." }
powershell -ExecutionPolicy Bypass -File (Join-Path $roots[0].FullName "scripts\install.ps1")
Remove-Item -Recurse -Force $work
```

```bash
repo="<owner>/<repo>"
ref="<release tag or full commit SHA>"
work="$(mktemp -d)"
curl --proto '=https' --tlsv1.2 -fsSL "https://github.com/$repo/archive/$ref.zip" -o "$work/repo.zip"
unzip -q "$work/repo.zip" -d "$work"
set -- "$work"/*/
[ "$#" -eq 1 ] && [ -f "${1}scripts/install.sh" ] || { echo "No Supreme Team checkout in the archive." >&2; exit 1; }
case "$1" in *"${ref#v}"/) ;; *) echo "The archive folder does not match $ref." >&2; exit 1 ;; esac
bash "${1}scripts/install.sh"
rm -rf "$work"
```

The archive is deleted at the end, and hook registration needs
`scripts/install_hooks.py` from it. Add `--register-hooks` (`-RegisterHooks`) to the
installer line to register hooks in the same run, or register later from the
installed tree with `harness/hooks/repair_registration.py` (preview first, see
[Runtime hooks](#runtime-hooks)).

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
by hand, then register the hooks. This skips host-mirror refresh, the ownership
records, and the removal of retired items, so prefer the installer for upgrades. A
hand copy also merges into any existing directory of the same name and overwrites
files in it, so move your own `review/`, `design/`, `scripts/` and similar folders
out of the way first; the installer treats a hand-copied tree as not its own and
moves it aside on its next run. Needs **Python 3.13 or newer** for the hook step.

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
| Download stops with an HTTP error | `<ref>` is not an existing release tag or full commit SHA | Use a real tag or the full 40-character SHA, not a branch or a short SHA |
| A skill of mine stopped working | Its folder shared a name with an installed item and was moved aside | It is unchanged in `<target>.supremeteam-backup/<timestamp>/`; move it back under a name the catalog does not use |
| `Refusing to install into ...` | `--destination` is the filesystem root, your home directory or a parent of it, or overlaps the checkout | Pass the skills folder itself |
| Python commands fail | Python missing or below the manifest floor | Install a supported Python, re-check |
| Gatekeepers can't find `_gatecheck.py` | `harness/` was skipped | Use the installer or copy every core component |
| Resume and saves broken | `save-protocol.md` was skipped | Copy the root doctrine files |
| Hooks not enforced | Never registered, trusted, or reloaded | Register explicitly, then reload the host |
