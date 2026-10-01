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
  parents, any folder that overlaps the checkout, and `.` unless the current
  directory already holds an install (a full path to it is always accepted).

### Installer options

| Goal | Windows | macOS / Linux |
|---|---|---|
| Pick teams | `-Team Design,Review` | `--team design --team review` |
| Pick hosts | `-Target Codex,Claude` | `--target codex --target claude` |
| Register hooks | `-RegisterHooks` | `--register-hooks` |
| Which hook config | `-HooksScope Project` | `--hooks-scope project` |
| Skip the hook question | `-HooksYes` | `--hooks-yes` |
| Custom path | `-Destination "path"` | `--destination "path"` |
| Preview only | `-DryRun` | `--dry-run` |

Teams: `Design`, `Build`, `Review`, `Browser`, `Release`, `Safety`, `Testing`,
`All`. Hosts: `auto`, `codex`, `claude`, `cursor`, `opencode`. Per-host
destination flags exist too (`-CodexDestination`, `--claude-destination`, and so
on); `-InstallClaude` and `--install-claude` are older aliases for the Claude
target. `--help` (`Get-Help .\scripts\install.ps1`) lists every option.

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
installer line to register hooks in the same run (it edits host config files; see
[Runtime hooks](#runtime-hooks) for which), or register later from the installed
tree with `harness/hooks/repair_registration.py` (a preview first).

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

GitHub Copilot has no skills directory here: only its hook configuration is
written, and only when you register hooks for it (see [Runtime hooks](#runtime-hooks)).

Claude Code and OpenCode mirror automatically when present. Codex and Cursor
mirror only when named explicitly or already holding an install. On upgrade,
every existing mirror is refreshed. Core components are never optional, even for a
single-team install: every skill resolves the root doctrine files, and every
`gatekeeper-*` depends on `harness/gatekeeper/`.

**What a host sees.** A host that scans its skill directory one level deep
registers the 22 skills that sit at the install root, by name. The 31 internal
specialists stay nested one level below, so no host lists them; they are reached by
path through the skill that delegates to them (`skills/routing-doctrine.md`,
"Host registration"). `AGENTS.md` is a checkout-only index: the installers do not
copy it, and nothing is discovered from it unless your tool is pointed at a
checkout.

## Python

The harness, hook verifier, and registration helper need **Python 3.13 or newer**
([`skills/runtime-manifest.yaml`](skills/runtime-manifest.yaml) is the authority).
Check with `python3 --version` (macOS and Linux) or `py -3 --version` (Windows);
`python3.13 --version` finds an interpreter installed under its versioned name. If
none is 3.13+, ask before installing one; the skill files still copy without it,
but hook verification and registration stay unavailable.

The shell installer looks for `python3`, then `python`. If your 3.13 exists only as
`python3.13`, make it answer to `python3` (a symlink earlier on `PATH`, or a
virtual environment), or skip the installer's registration step and run
`python3.13 scripts/install_hooks.py ...` yourself, as the examples below do.

### Paths and the Python command

Every command in this repository's documents is written for a checkout and starts
at its root, for example `python skills/scripts/check_runtime.py`. Two
substitutions give the form you need elsewhere:

| In the documents | macOS / Linux | Windows |
|---|---|---|
| leading `skills/` | the install root, `~/.agents/skills/` (or a host mirror such as `~/.claude/skills/`) | `%USERPROFILE%\.agents\skills\` |
| `python` | `python3` | `py -3` |

`python skills/harness/hooks/save_run.py status --run-id <id>` therefore reads
`python3 ~/.agents/skills/harness/hooks/save_run.py status --run-id <id>` in an
installed copy, run from your project: the run's files go to that project's
`skillset-saves/`, never into the install root. `skills/runtime-manifest.yaml`
(`launchers`) is the authority for the Python command per platform. Inside a skill,
paths are written relative to the skill (`../harness/hooks/...`) and mean the same
thing in both layouts.

Only a checkout holds `scripts/` (the installers, `install_hooks.py` and their
tests), `docs/`, `AGENTS.md`, `package_check.py`'s expected layout, and the test
suites; the commands that need one say so.

## Runtime hooks

Copying `skills/harness/` puts the three hooks (`pre_tool_use.py`,
`post_tool_use.py`, `user_prompt_submit.py`) in place but does **not** register
them — registration changes runtime behavior, so it is always explicit.

```bash
# Inspect current state (checks the hosts that have a config file or a host variable)
python3 ~/.agents/skills/harness/hooks/verify_registration.py --host auto
# From the checkout: preview what registration would change; writes nothing
python3 scripts/install_hooks.py --target codex --hook-root "$HOME/.agents/skills/harness/hooks" --dry-run
# From the checkout: register (or pass -RegisterHooks / --register-hooks to the installer)
python3 scripts/install_hooks.py --target codex --hook-root "$HOME/.agents/skills/harness/hooks"
```

`--host` / `--target` take `codex`, `claude`, or `copilot` for native JSON config;
`cursor` and `opencode` load a plugin package that is not machine-verifiable.
Registration edits these files, by default the global (`user`) ones:

| Host | `user` scope (default) | `project` / `local` scope |
|---|---|---|
| Claude Code | `~/.claude/settings.json` | `.claude/settings.json` / `.claude/settings.local.json` |
| Codex | `~/.codex/hooks.json` | `.codex/hooks.json` |
| GitHub Copilot | `~/.config/github-copilot/hooks.json` | `.github/hooks.json` |
| Cursor | `~/.cursor/plugins/local/supremeteam-hooks/` | not scoped |
| OpenCode | `~/.config/opencode/plugins/supremeteam-hooks.js` | not scoped |

`--scope project|local` (`--hooks-scope`, `-HooksScope` on the installers) means the
project around the directory you run it from. A `project` file is usually committed
and holds machine-absolute paths; for Claude Code `local` is the per-machine file.
Run from a terminal, the helper prints the diff of every file it would change and
asks before writing; `--yes` (`--hooks-yes`, `-HooksYes`) skips the question, and
with no terminal it writes straight away. It writes atomically, keeps a timestamped
`.bak-` copy with the original's permissions, refuses a file that is not UTF-8 JSON,
is idempotent, and leaves unrelated keys alone. It registers the Python that runs
it (`--python-command` names another), started with `-X utf8`, and records the
sha256 of the hook scripts in `.harness-state/hook-hashes.json` so a later edit to
one shows up in `verify_registration.py`. Afterward open `/hooks` or restart the
host. Without hooks, entry routing and tool guards are advisory only.

## Verify

Restart the assistant, then ask:

```text
Summarize the Supreme Team pipelines available from the installed skills.
```

A good install names `admiral` as the entry orchestrator, the design/build/review
pipelines, the investigation, session-memory, and skill-maker components, the
standalone browser/release/safety/testing groups, and the shared doctrine files.
To verify the installed copy itself (from any directory; see
[Paths and the Python command](#paths-and-the-python-command)):

```bash
python3 ~/.agents/skills/scripts/check_runtime.py
python3 ~/.agents/skills/scripts/validate_manifests.py
```

Once a run is active, one command covers Python, hooks, and saves:

```bash
python3 ~/.agents/skills/harness/hooks/check_readiness.py --host auto --require-active-run
```

`Ready` covers Python and, with that flag, the run. Hooks are optional, so missing
ones are listed beside it rather than failing it; add `--require-hooks` to make
working hooks part of ready.

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
py -3 scripts\install_hooks.py --target claude --hook-root "$destination\harness\hooks"
```

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/. "$HOME/.agents/skills/"
python3 scripts/install_hooks.py --target claude --hook-root "$HOME/.agents/skills/harness/hooks"
```

Swap `--target` for your host (`codex`, `claude`, `copilot`; `cursor`/`opencode`
write a plugin package). Skip the hook line to leave routing and guards advisory.

## Uninstall

There is no uninstall command. Undo what the installer did, hooks first so the host
stops calling scripts you are about to delete.

1. **Unregister the hooks**, if you registered them. In each file from the
   [Runtime hooks](#runtime-hooks) table that you registered, delete the three
   entries (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`) whose `command` runs
   `pre_tool_use.py`, `post_tool_use.py` and `user_prompt_submit.py`, or restore the
   newest `<file>.bak-<timestamp>` kept beside it if nothing else in the file has
   changed since. For Cursor and OpenCode delete the plugin package or file. Restart
   the host; `verify_registration.py --host auto` then reports `MISSING`.
2. **Remove the skills.** In each target from [Where it goes](#where-it-goes) that
   holds an install, delete every item named on an `item <name>` line of its
   `.supremeteam-manifest`, then the manifest. Leave everything else: `mcp-tools.md`
   is your tool registry, and `<target>.supremeteam-backup/` holds anything of yours
   the installer moved aside.
3. **Project leftovers**, if you want them gone: `.harness-state/` holds hook state
   and the hash record, and `skillset-saves/` holds your run history, so keep that
   one unless you are sure.

## When it goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Skills not discovered | Wrong target path, or a stale session | Check the path, restart the assistant |
| `admiral` missing | Tree flattened or copied from the wrong source | Copy `skills/` again, preserving directories |
| Remote install fails | Ran local scripts from a raw URL | Download and extract the archive first |
| Download stops with an HTTP error | `<ref>` is not an existing release tag or full commit SHA | Use a real tag or the full 40-character SHA, not a branch or a short SHA |
| A skill of mine stopped working | Its folder shared a name with an installed item and was moved aside | It is unchanged in `<target>.supremeteam-backup/<timestamp>/`; move it back under a name the catalog does not use |
| `Refusing to install into ...` | `--destination` is the filesystem root, your home directory or a parent of it, overlaps the checkout, or is `.` in a folder with no install | Pass the skills folder's full path |
| Python commands fail | Python missing or below the manifest floor | Install a supported Python, re-check |
| Gatekeepers can't find `_gatecheck.py` | `harness/` was skipped | Use the installer or copy every core component |
| Resume and saves broken | `save-protocol.md` was skipped | Copy the root doctrine files |
| Hooks not enforced | Never registered, trusted, or reloaded | Register explicitly, then reload the host |
| Registration says `declined` | You answered no at the preview | Re-run and answer `y`, or pass `--hooks-yes` |
| `verify_registration.py` warns about the interpreter | The registered Python is missing or older than the manifest floor | Edit the registered `command` to name a supported Python, or remove the three entries and register again (`--python-command`, or `repair_registration.py --python`) |
