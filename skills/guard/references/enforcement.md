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
the state file is absent the hook is inert and the guard remains advisory only.
See `../../harness/hooks/README.md`.

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
  `release --glob <g>` call covers both keys.
- `read_only` — owned records confining a run to its own save path, enforced by
  the hook's Rule D: while an unreleased record exists, the only writable
  locations are that record's `allow` globs and the harness state directory, and
  any other edit-tool write or mutating shell command is denied. A command that
  invokes `save_run.py` is exempt, so the run can still checkpoint its own
  record, and read-only commands pass untouched.
- `allow_dangerous` — `false`, or an owned grant that lifts the built-in
  destructive-command block (see the next section).

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

The expiry defaults to 30 minutes and is set as short as the operation needs —
but not shorter than the operation itself. The hook re-evaluates the grant on
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

An expired grant, one whose `expires_at` cannot be parsed, and one carrying no
`expires_at` at all all leave the block **in force**: a guard that cannot read
its own grant stays closed rather than open. The writer always records an expiry,
so a grant without one is malformed rather than permanent. Exactly one shape
lifts the block without an end — the legacy bare `true` — and the writer never
produces it, which is one more reason the record is not hand-edited.

## Fail-open semantics (advisory-grade, not a hard control)

Per harness-doctrine §3 the hook *fails open*: any internal error — a malformed
`guard-state.json`, an unreadable path, or a host that does not run the hook at
all — exits silently and lets the action proceed. A guard fault therefore means a
write into `blocked_globs` is *allowed*, not denied. Treat the boundary as a
discipline aid that catches honest mistakes — do not rely on it to stop a
determined or adversarial actor, and never use `blocked_globs` as the sole
protection for secrets or production paths. For real isolation, use OS/filesystem
permissions or a sandbox in addition to the guard.
