# Guard — Deterministic Enforcement Reference

How the advisory guard is backed by a deterministic host-compatible hook: the
single writer of the boundary record, the `guard-state.json` schema, activation
steps, the `allow_dangerous` override protocol, and the fail-open semantics.
Read this when activating hook-level enforcement or diagnosing why a guarded
write was or was not blocked.

## Contents

1. [Action Realization layer](#action-realization-layer)
2. [Single writer](#single-writer)
3. [guard-state.json](#guard-statejson)
4. [allow_dangerous override protocol](#allow_dangerous-override-protocol)
5. [Sizing the expiry](#sizing-the-expiry)
6. [Fail-open semantics](#fail-open-semantics-advisory-grade-not-a-hard-control)

## Action Realization layer

The guard is the advisory expression of the Action Realization layer
(`../../harness-doctrine.md` §1). When the host supports compatible runtime hooks, the
guarded boundary is also deterministically enforced by
`../../harness/hooks/pre_tool_use.py`, which blocks writes into the guarded paths
before they execute — so the guard is no longer advice the model can ignore. When
the state file is absent no boundary is enforced and the guard remains advisory
only; the destructive-command rule and the single-writer rule need no record and
still run. See `../../harness/hooks/README.md`.

## Single writer

`.harness-state/guard-state.json` is written only by
`../../harness/hooks/guard_state.py`, and `pre_tool_use.py` denies direct
edit-tool writes and mutating shell commands against that path — the same
routing that sends core run records through `save_run.py`. The reason is
structural: before that writer existed the guard could lift itself, because one
write to the record cleared any freeze, or set `allow_dangerous` and disabled
destructive-pattern blocking globally, with no owner check and no `released_at`
trail. Hand-editing the record is neither necessary nor permitted; every change
below is a writer subcommand.

```bash
python skills/harness/hooks/guard_state.py block   --glob "**/secrets/**"  --owner <contributor> --scope "<why>" [--approver <delegate>]
python skills/harness/hooks/guard_state.py freeze  --glob "src/payments/**" --owner <contributor> --scope "<why>" [--run-id <run>]
python skills/harness/hooks/guard_state.py release --glob "src/payments/**" --requester <owner> --reason "<why it reopens>"
python skills/harness/hooks/guard_state.py read-only --run-id <run> --owner <contributor> --allow "skillset-saves/runs/<run>/**"
python skills/harness/hooks/guard_state.py release-read-only --run-id <run> --requester <owner>
python skills/harness/hooks/guard_state.py allow-dangerous --owner <contributor> --reason "<why>" --scope "<operation>" [--minutes 30]
python skills/harness/hooks/guard_state.py revoke-dangerous --requester <owner>
python skills/harness/hooks/guard_state.py status [--json]
```

Exit 0 is ok; exit 1 is refused — an authority, validation, or corrupt-record
refusal that changes nothing and prints its reason to stderr; exit 2 is a usage
error. A refusal is a contract violation to resolve, never something to work
around by editing the record.

The writer records a glob in one spelling (`./src/**`, `src//**`, `src\**` and the
absolute form of a project path are all `src/**`), refuses one that can never match
(empty, `.`, climbing out of the project with `..`, a leading `!`, a drive or file-system root, or a
leading-slash path under a directory this machine does not have, which `/src/**` is), and keeps one record per
glob in each key. Every command except `status` holds one lock
(`.harness-state/guard-state.json.lock`) from reading the record to replacing it, so
two sessions cannot lose each other's change; one that cannot take it within
`--lock-timeout` seconds (a flag before the subcommand, default 5) exits 1 and
changes nothing, and a crashed holder never wedges it.

## guard-state.json

Enforcement reads `.harness-state/guard-state.json`. The state directory
resolves under `SUPREMETEAM_PROJECT_DIR` first, then a known host workspace
variable (`CLAUDE_PROJECT_DIR`, `CODEX_WORKSPACE_DIR`, `GITHUB_WORKSPACE`), then
the nearest ancestor of the working directory that holds `skillset-saves/`,
`.harness-state/`, or `.git`, then the working directory itself, then an
isolated per-project directory under the OS temp root. The ancestor walk is what
keeps a command issued from a subdirectory recording into the project's own
boundary file instead of starting a second one beside it.

```json
{
  "frozen_globs": [
    {
      "glob": "src/payments/**",
      "owner": "payments-lead",
      "scope": "charge-bug hotfix window",
      "created_at": "2026-09-16T09:12:04Z",
      "run_id": "2026-09-16-charge-bug",
      "approvers": ["release-owner"],
      "released_at": null
    }
  ],
  "blocked_globs": [
    {
      "glob": "**/secrets/**",
      "owner": "security-lead",
      "scope": "secrets stay out of agent writes",
      "created_at": "2026-09-16T09:12:40Z",
      "run_id": null,
      "approvers": [],
      "released_at": null
    }
  ],
  "read_only": [
    {
      "run_id": "2026-09-16-charge-bug",
      "owner": "incident-lead",
      "scope": "incident investigation",
      "allow": ["skillset-saves/runs/2026-09-16-charge-bug/**"],
      "created_at": "2026-09-16T09:13:02Z",
      "released_at": null
    }
  ],
  "allow_dangerous": false
}
```

- `frozen_globs` — owned records for paths the freeze layer locks against
  writes.
- `blocked_globs` — owned records for paths the guard forbids outright. The hook
  merges these with `frozen_globs` into one boundary, so one
  `release --glob <g>` call covers both keys. Both are *write* boundaries: a read
  of a blocked path is never denied, so a blocked glob keeps an agent from
  changing a secret, not from reading it.
- `read_only` — owned records confining a run to its own save path, enforced by
  the hook's Rule D: while an unreleased record exists, every write target of an
  edit tool or of the analysed shell command must lie inside that record's
  `allow` globs or the harness state directory (`.harness-state/**`). Naming one
  allowed path in a command that also writes somewhere else does not satisfy it,
  and a git command that changes the repository without naming a path
  (`git add -A`, `git push`, `git merge`, `git restore --staged .`) is denied, as is a
  package manager installing, removing or updating (`npm install`, `pip install`,
  `apt-get install`: a table of the usual ones, not every tool). So is a write with
  no target in the command, because a target the hook cannot place cannot be shown
  to lie inside: a mutating verb whose operands arrive on standard input
  (`cat list | xargs rm -rf`, `xargs rm < list`, `Get-ChildItem | Remove-Item`), and an
  inline `awk`, `sed`, `perl`, `python`, `node` or `ruby` program that redirects or
  opens a file for writing (`awk '{print > "out"}'`, `sed -n 'w out'`,
  `python3 -c "open('x', 'w')"`). Name each target in the shell command itself, as an
  operand or a redirect (`awk '{print}' f > <allowed path>`), and it is judged like any
  other. This applies to `read_only` only: a freeze or a block judges the targets a
  command names. Reads pass untouched, including `awk '$1 > 5'` and `xargs grep`.
- `allow_dangerous` — `false`, or an owned grant that lifts the built-in
  destructive-command block (see the next section).

**The run can still checkpoint itself.** A script's arguments are data, not write
targets, so `python skills/harness/hooks/save_run.py checkpoint ...` is not stopped
by Rule D, and Rule C (the single-writer rule) does not treat a path passed to the
script as a write either. That is a property of how the command is analysed, not a list of
exempt names: a redirect from the same command into a core run file, or any other
command that writes there, is still denied. A command the analyser cannot tokenise
(an unbalanced quote) falls back to textual rules, which carry no such exception: a
`save_run.py` command with a stray quote is denied while a run is read-only, and when
it names a core run file, until it is issued again with balanced quoting.

A boundary record stays effective until its owner records `released_at`; age
alone never expires a protection, and a release never deletes the record, so who
locked what and who lifted it stays readable in the file itself. `status`
reports the effective boundary and warns about any legacy entry with no owner —
the authority check cannot release one, so it has to be re-recorded through the
writer first.

## allow_dangerous override protocol

`allow_dangerous` is a **global kill-switch for destructive-pattern blocking**,
not an exception scoped to one operation: while it is lifted, every pattern the
hook knows — recursive root deletes, drive formats, raw-device writes, force
pushes to a protected branch — passes for every command in the session, not only
for the operation the grant was requested for.

Recording it requires explicit owner confirmation first: a named approval, the
scope it is for, and the reason a narrower command will not do. The writer
records all three plus an expiry.

**That confirmation is a convention, not a mechanism.** `cmd_allow_dangerous`
writes whatever `--owner`, `--reason`, and `--scope` it is given; there is no
confirmation step in the code, and the owner name is self-asserted like every
other `--requester`/`--owner` string in this writer. So the fields prove that
someone *recorded* an approval, never that one was *obtained*. The control that
does bite is the expiry, which the hook re-reads on every call. Treat a grant
whose reason reads thin the way you would treat an unsigned change: ask the named
owner, rather than inferring approval from the record's existence.

```bash
python skills/harness/hooks/guard_state.py allow-dangerous --owner <contributor> --reason "<why a narrower command will not do>" --scope "<the operation>" --minutes 15
```

```json
{
  "allow_dangerous": {
    "owner": "ops-lead",
    "reason": "reformat the scratch volume before the rebuild",
    "scope": "scratch-volume rebuild",
    "created_at": "2026-09-16T09:20:11Z",
    "expires_at": "2026-09-16T09:50:11Z"
  }
}
```

## Sizing the expiry

The expiry defaults to 30 minutes, is never more than 8 hours (the writer refuses a
longer `--minutes`, and the hook reads a grant with more than 8 hours left as
malformed, so a hand-written far-future expiry is not a standing kill-switch), and is
set as short as the operation needs — but not shorter than the operation itself. The hook re-evaluates the grant on
every tool call, so a grant that lapses mid-sequence re-arms the destructive
pattern block between two steps of the same operation: the earlier steps have
already run, the next one is denied, and the work is left half-done. That is
frequently a worse state than either completing or never starting.

Size `--minutes` from the operation's expected duration plus margin for one
retry, and prefer a single grant covering the whole sequence over a short grant
that has to be renewed under time pressure. When a grant does lapse mid-flight,
the response is not a reflexive re-grant: record which step completed and which
was refused, establish whether the partial state is safe to leave, and have the
owner issue a fresh grant for the remainder with the half-finished state
acknowledged explicitly. A grant renewed without that check hides exactly the
condition it interrupted.

Expiry is a backstop, not the protocol: revert the grant the moment the
dangerous operation completes with
`guard_state.py revoke-dangerous --requester <owner>`, which sets the key back
to `false`. Only the grant's owner may revoke it — the writer records no
approvers on a grant, so this one has no delegate. It must never be the default
value and must never be enabled silently.

An expired grant, one whose `expires_at` cannot be parsed, one carrying no
`expires_at`, and the legacy bare `true` all leave the block **in force**. The
writer always records an owned grant with an expiry; an ownerless or unbounded
value cannot lift the block.

## Fail-open semantics (advisory-grade, not a hard control)

Per harness-doctrine §3 the hook *fails open*: an internal error, an unreadable
path, or a host that does not run the hook at all lets the action proceed. A guard
fault therefore means a write into `blocked_globs` is *allowed*, not denied. Each
fault is counted by type in `.harness-state/observations/PreToolUse.json`. A
`guard-state.json` that cannot be read does not switch every rule off: the hook
applies no boundary from it, but the destructive-command rule still runs, and a
list in the wrong shape is skipped without stopping the rest of the record.

The hook is also a text guard, not a hard lock. It analyses the command a tool is
about to run and the path an edit tool names, and runs nothing, so a program that
builds its path at run time, a script file, a tool it has no entry for, or a link
made in the same command can write past it, and interpreter inline code
(`python -c`, `node -e`) is searched for protected paths rather than understood
(a read-only run reads it further, for the shapes above).
`../../harness/hooks/README.md` § What the guard cannot see lists these limits in
full. Treat the boundary as a discipline aid that catches honest mistakes — do not
rely on it to stop a determined or adversarial actor, and never use `blocked_globs`
as the sole protection for secrets or production paths. For real isolation, use
OS/filesystem permissions or a sandbox in addition to the guard.

While a run is pinned or any boundary is recorded, Rule F also denies edits to the
hook scripts and to the host files that register them, so the guard cannot be
switched off from inside a session; a maintainer who must edit them starts the host
with `SUPREMETEAM_HARNESS_DEV=1`, which only the person launching the host can set.
