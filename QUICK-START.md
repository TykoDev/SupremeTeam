# Quick Start

You need **Python 3.13 or newer**. One optional extra: `skill-maker`'s
description-optimization stage runs the `claude` CLI, which must be on your `PATH`
and signed in, and each run makes paid model calls. Everything else works without it.

## 1. Install

From a checkout of this repository, install the skills and register the runtime hooks:

```bash
bash ./scripts/install.sh --register-hooks
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1 -RegisterHooks
```

The skills go to `~/.agents/skills`, and Claude Code and OpenCode get a copy when
present; name Codex or Cursor with `--target` ([details](Install.md#where-it-goes)).
The hooks enforce the rules; registering them edits your assistant's config, and on a
terminal the installer shows each change and asks first. It only replaces what it installed; anything else
with a clashing name is moved to `<target>.supremeteam-backup/`, never deleted. Add
`--dry-run` (`-DryRun`) to preview without writing anything.

Or let your assistant do it:

```text
Read Install.md and install Supreme Team for this assistant, registering the runtime
hooks. If Install.md came from a GitHub URL, download the archive of a pinned release
tag or commit and run the installer from inside it.
```

It worked when the installer ends with:

```text
Supreme Team installation complete.
Target: ...
Host targets: ...
Host mirrors: ...
Teams: ...
Installed items: ...
Moved aside: ...
Hook registration: completed
```

## 2. Restart and check

Restart your assistant so it loads the skills and hooks, then run:

```bash
python3 ~/.agents/skills/harness/hooks/check_readiness.py --host auto --require-hooks
```

```powershell
py -3 "$env:USERPROFILE\.agents\skills\harness\hooks\check_readiness.py" --host auto --require-hooks
```

The last line should read `Ready: yes`. Anything missing is listed above it, with
the command that repairs it.

## 3. Use it

Say what you want. Lifecycle work goes through `admiral`, which interviews you,
writes the scope down and gates every phase:

```text
Design [your idea].
Review this codebase.
Find the root cause of this failure.
Test this product and fix what's broken.
```

A typo, a link or a bug whose cause you already know runs directly, with no
interview and no saved run (never security, deployment or production changes).
Standalone tools work any time:

```text
Use the freeze skill to protect src/payments from edits.
```

### What a run costs

A governed run first reads `admiral/SKILL.md` and seven root contracts, about
220 KB together, so budget the context for it. Small reversible work skips all of it.

Options, hosts, teams, manual install, uninstalling and troubleshooting are in
[Install.md](Install.md).
