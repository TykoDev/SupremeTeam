# Quick Start

Five steps. The first one is the only one that is strictly required. Supreme Team
needs **Python 3.13 or newer** for the runtime harness, hook verification, and
readiness checks.

Creating a skill with `skill-maker` needs nothing more, with one exception: its
optional description-optimization stage runs the `claude` CLI, which must be on
your `PATH` and signed in, and every run is a paid model call (about 20 queries
x 3 runs per iteration). Skip that stage if you do not want it; the rest of
skill creation, including packaging, works without the CLI.

## 1. Install the skills

Pick one of the two setup options below.

### Option A — Let your coding agent do it

```text
Read Install.md and install Supreme Team for this assistant.
Use the default all-teams install unless a safer local target is obvious.
Register the runtime hooks as part of the install.
If Install.md came from a GitHub URL, download the archive of a pinned release tag
or full commit SHA and run the installer from inside it.
```

That last line matters. If the agent is reading `Install.md` straight from a
GitHub URL, there is no checkout on disk yet, so it has to download the archive
first instead of trying to run scripts that are not there. The archive must be a
tag or commit, not a branch, so what runs is what you reviewed.

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

The installer only replaces or removes what it installed. Anything of yours that
shares a name with an installed item (`review`, `qa`, `scripts`, ...) is moved,
never deleted, to `<target>.supremeteam-backup/<timestamp>/` and listed in the
summary. Run it with `--dry-run` (`-DryRun` on Windows) first to see what it would
do without writing anything. [Install.md](Install.md) has the details.

Teams, hosts, the hook-scope and no-prompt flags, a custom destination and
`--dry-run` are in [Install.md](Install.md#installer-options).

You will know it worked when the installer prints its summary:

```text
Supreme Team installation complete.
Target: ...
Host targets: ...
Host mirrors: ...
Teams: ...
Installed items: ...
Moved aside: ...
Hook registration: ...
```

`Moved aside` names any of your items that shared a name with an installed one and
where they are now (the first upgrade over an older install lists that whole install,
because nothing recorded it as the installer's). `Hook registration` reads `not
requested`, `skipped (no host detected)`, `declined (nothing was written)`, `failed
(exit status N; see the messages above)` or `completed`; only `completed` means
registration ran. When it failed the first line reads `Supreme Team skills are
installed, but hook registration failed.`, the skills are in place, and the installer
exits with the registration's status after telling you how to try again.

## 2. Register the hooks (the enforcement layer)

A normal install copies the hook files but does not wire them into your host.
That is deliberate: hooks change assistant runtime behavior, so turning them on
is an explicit choice. Make it, unless you have a reason not to: without the
hooks every rule in this catalog is advice. The pre-tool hook is what refuses a
write into a guarded, frozen or single-writer path; the prompt hook is what sends
a lifecycle request through `admiral` instead of straight to a specialist; the
post-tool hook is what keeps a run's heartbeat fresh between checkpoints. An
install that skips registration ends with a banner saying exactly that, and
`check_readiness.py --require-hooks` reports it as not ready.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks
```

```bash
bash ./scripts/install.sh --register-hooks
```

Registration edits host config files, and by default the global ones in your home
directory: `~/.claude/settings.json`, `~/.codex/hooks.json`, or a plugin package
for Cursor and OpenCode. Run from a terminal, the installer prints exactly what it
would change in each file and asks before it writes; `--hooks-yes` (`-HooksYes`)
skips the question, and with no terminal it writes straight away. Every file keeps
a `.bak-<timestamp>` backup and its permissions. `--hooks-scope project` (or
`local`, for Claude Code's per-machine file) writes the project around the
directory you run the installer from instead; a `project` file is usually
committed and holds machine-absolute paths. [Install.md](Install.md#runtime-hooks)
lists the file for every host and scope, and [how to undo it](Install.md#uninstall).

To see the change before running the installer for real, install first without
`--register-hooks`, then:

```bash
python3 scripts/install_hooks.py --target claude --hook-root "$HOME/.agents/skills/harness/hooks" --dry-run
```

Copilot has hook support but no skills directory. The installers take it as a hooks-only
target (`--target copilot`, `-Target Copilot`); `auto` never picks it, so name it. To register
only its hooks, run
`python3 scripts/install_hooks.py --target copilot --hook-root "$HOME/.agents/skills/harness/hooks"`.

Then open `/hooks` or restart the host if it wants to review them first.

Without hooks the skills still run, but entry routing and write guards are
advisory rather than enforced, the run heartbeat only refreshes when a checkpoint
happens, and `admiral` says so at the top of every intake.

## 3. Restart your assistant

So it picks up the new skills and hook config.

## 4. Verify

Verify the installed copy from any directory (Python 3.13 or newer; `py -3` and
`%USERPROFILE%\.agents\skills\` on Windows, and
[Install.md](Install.md#paths-and-the-python-command) for the rule behind the
paths):

```bash
python3 ~/.agents/skills/harness/hooks/check_readiness.py --host auto
python3 ~/.agents/skills/scripts/check_runtime.py
python3 ~/.agents/skills/scripts/validate_manifests.py
```

In a checkout, the same commands start at its root (`python3 skills/...`), and
`python3 skills/scripts/package_check.py --root .` is available too.

`check_readiness.py` gives you a capability map: `python_runtime`,
`hooks_configured`, `hooks_executable`, `hooks_coverage`, `hooks_interpreter`,
`hooks_observed`, `hooks_faults`, `saves_readable`, `active_run`,
`deterministic_validators`. The `Ready` line covers Python, and a run when you
pass `--require-active-run`. Hooks are optional: missing hooks are listed next to
it, knock out deterministic enforcement and leave everything else intact. Add
`--require-hooks` to make working hooks part of ready. `--host auto` checks the
hosts that have a config file or a host environment variable and says which, so a
host you do not use is not reported as unregistered.

`hooks_observed` stays `unverified` until a hook actually fires. Reading config
proves a hook is registered, never that it ran, and the diagnostic will not
pretend otherwise.

If a hook is missing, look at the repair before you apply it:

```bash
python3 ~/.agents/skills/harness/hooks/repair_registration.py --host claude --scope project
python3 ~/.agents/skills/harness/hooks/repair_registration.py --host claude --scope project --apply
```

The preview is the default, and it never touches global host config unless you
ask for `--scope user`. It registers the Python that runs it (an absolute path,
started with `-X utf8`); `--python "py -3.13"` names another.

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

Security, deployment, and production changes never qualify, however small. The
test is not file count: a change qualifies when it is local, understood and
reversible and its acceptance check is obvious. A one-line change to an
authentication check does not qualify.

### What a run costs

A governed run starts from `admiral/SKILL.md` (about 28 KB) and the root contracts
it points at: `routing-doctrine.md`, `grill-me-doctrine.md`, `save-protocol.md`,
`harness-doctrine.md`, `execution-contract.md`, `gates.yaml` and `pipelines.yaml`
(about 155 KB between them). That is the price of one interview, one persisted run
and a gate at every boundary, so budget the context for it. The sizes drift as the
files change; this measures them now:

```bash
wc -c skills/admiral/SKILL.md skills/{routing-doctrine,grill-me-doctrine,save-protocol,harness-doctrine,execution-contract}.md skills/{gates,pipelines}.yaml
```

The Tier 0 fast path above needs none of it (no interview, no saved run, no gate
package), which is why small work is better left off the full route.

## Manual install

If the installer will not run, copy the skills folder by hand and register the
hooks yourself: [Install.md](Install.md#manual-install-fallback) has the commands
and what a hand copy skips.
