# Freeze — Deterministic Enforcement Reference

Read this when activating hook-level enforcement for a freeze, or when diagnosing
why a recorded freeze was or was not honoured. It carries the record shape the
enforcing hook reads, where that record is resolved on disk, the authority fields
`unfreeze` checks, and the writer's exit contract.

## Contents

1. [Single writer](#single-writer)
2. [Recording a freeze](#recording-a-freeze)
3. [The frozen_globs record](#the-frozen_globs-record)
4. [Authority fields](#authority-fields)
5. [Where the record lives](#where-the-record-lives)
6. [Writer exit contract](#writer-exit-contract)
7. [Release, not deletion](#release-not-deletion)
8. [Fail-open semantics](#fail-open-semantics)

## Single writer

`.harness-state/guard-state.json` is written only by
`../../harness/hooks/guard_state.py`, and `../../harness/hooks/pre_tool_use.py`
denies direct edit-tool writes and mutating shell commands against that path,
exactly as core run records are routed through `save_run.py`. The reason is
structural: before the writer existed the boundary was self-liftable, because one
write clearing `frozen_globs` — or setting `allow_dangerous`, which disables
destructive-pattern blocking globally — lifted the protection before any rule ever
ran. Recording through the writer keeps every entry owned, every release
attributable, and the audit trail intact.

## Recording a freeze

```bash
python skills/harness/hooks/guard_state.py freeze --glob "src/payments/**" --owner payments-lead --scope "charge-bug hotfix window" --run-id 2026-09-16-charge-bug --approver release-owner
python skills/harness/hooks/guard_state.py status
```

`--glob` and `--owner` are required; `--scope`, `--run-id`, and `--approver`
(repeatable) are optional. Each successful run appends exactly one owned record to
`frozen_globs` and prints a JSON acknowledgement naming the glob, the owner, and
the record path.

## The frozen_globs record

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
  ]
}
```

The hook merges `frozen_globs` with `blocked_globs` into one boundary, so a glob
frozen here is enforced by the same Rule B that enforces a guard block, and one
`release --glob <g>` call covers both keys.

## Authority fields

`owner` and `approvers` are the two fields `unfreeze` checks a requester against:
a release is authorized when the requester equals the record's `owner` **or**
appears in its `approvers` list. Two legacy shapes behave differently and both
have to be re-recorded through the writer before they can be lifted:

- A **bare glob string** (no record object at all) is refused outright by
  `guard_state.py release`, because there is no owner and no approver list to
  check against.
- A **record with no `owner`** is releasable only by a requester named in its
  `approvers`; with an empty `approvers` list nothing can release it. The writer
  requires `--owner`, so it never produces this shape.

`status` lists both under its `unowned_entries` warning.

## Where the record lives

The state directory resolves in this order, and the first hit wins:

1. `SUPREMETEAM_PROJECT_DIR`
2. a known host workspace variable — `CLAUDE_PROJECT_DIR`, `CODEX_WORKSPACE_DIR`,
   `GITHUB_WORKSPACE`
3. the nearest ancestor of the working directory holding `skillset-saves/`,
   `.harness-state/`, or `.git`
4. the working directory itself
5. an isolated per-project directory under the OS temp root

The ancestor walk in step 3 is what keeps a command issued from a subdirectory
recording into the project's own boundary file instead of starting a second one
beside it. When a freeze appears not to take effect, compare the `record:` path in
`status` against the project root before assuming the hook is at fault.

## Writer exit contract

| Exit | Meaning | Response |
| --- | --- | --- |
| 0 | recorded; the JSON acknowledgement names the glob and owner | quote it as the freeze evidence |
| 1 | refused — the glob is already recorded and unreleased, the record on disk is corrupt, or an authority check failed; nothing changed | resolve the stated reason; never hand-edit the record around a refusal |
| 2 | usage error — a missing or malformed flag | fix the command; nothing was written |
| other non-zero | the command never completed — no interpreter on `PATH`, the harness not installed, or the state directory cannot be created or written | treat the freeze as **not recorded**, say so explicitly, and hold the boundary socially until the writer can run |

The duplicate check compares the glob **exactly, as a string** — no path
normalisation of any kind runs first. Two consequences, and both produce stacked
records rather than a refusal:

- A *narrower* glob under an already-frozen path is a second boundary: `src/payments/**` and `src/payments/api/**` coexist.
- So is the *same* boundary spelled differently. `./src/payments/**` and `src/payments/**` are different strings, so the second call is accepted and the path now carries two independent records, each needing its own release before the area is actually open.

Keep one glob per boundary, and spell it the way `status` prints it. A boundary
reported as released while a differently-spelled duplicate is still active is the
failure this note exists to prevent — `status` is what shows it, so read it after
every release rather than trusting the release call's own output.

## Release, not deletion

`unfreeze` lifts the restriction with `guard_state.py release --glob <g>
--requester <r> --reason "<why>"`, which sets `released_at`, `released_by`, and
`release_reason` and never deletes the record, so the freeze stays auditable after
it is lifted. A record stays effective until its owner records `released_at`; age
alone never expires a protection.

## Fail-open semantics

Per `../../harness-doctrine.md` §3 the hook *fails open*: any internal error —
a malformed `guard-state.json`, an unreadable path, or a host that does not run
hooks — exits silently and lets the edit proceed. A hook fault therefore means a
write into a frozen path is *allowed*, not blocked. Treat freeze as a discipline
aid that catches honest mistakes; for a boundary that must not change under any
circumstances, back it with version-control protections or filesystem permissions
in addition to the freeze. See `../../harness/hooks/README.md`.
