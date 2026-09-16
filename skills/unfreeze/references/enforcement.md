# Unfreeze — Deterministic Enforcement Reference

Read this before lifting anything. It carries why a release is a recorded write
rather than a statement, who the writer will accept as authorized for each of the
four keys, what a release leaves behind, and why a boundary that still reads as
active is not proof that it was ever enforced.

## Contents

1. [Single writer](#single-writer)
2. [Authority, key by key](#authority-key-by-key)
3. [Release, never deletion](#release-never-deletion)
4. [Writer exit contract](#writer-exit-contract)
5. [Fail-open semantics](#fail-open-semantics)

## Single writer

`.harness-state/guard-state.json` is written only by
`../../harness/hooks/guard_state.py`, and `../../harness/hooks/pre_tool_use.py`
denies direct edit-tool writes and mutating shell commands against that path,
exactly as core run records are routed through `save_run.py`. The reason is
structural: before the writer existed, one write to that file lifted any freeze —
or set `allow_dangerous`, which globally disables destructive-pattern blocking —
with no owner check and no `released_at` trail. A hand-edited unfreeze is
therefore indistinguishable from an unfreeze performed without authority, which
is the exact failure this skill exists to prevent.

## Authority, key by key

The writer's authority check is `owner == requester`, or the requester appearing
in the record's `approvers` list. Which fields exist differs by key, and that
difference is load-bearing:

| Key | Lift command | Who the writer accepts |
| --- | --- | --- |
| `frozen_globs` | `release --glob <g> --requester <r> --reason "<why>"` | the record's `owner`, or any name in its `approvers` (recorded from `--approver` at freeze time) |
| `blocked_globs` | the same `release` call — it scans both keys for active records matching the glob | same as above, per matching record; **every** match must authorize the requester or the whole call is refused |
| `read_only` | `release-read-only --run-id <run> --requester <r>` | the record's `owner`, or a name in its `approvers`; the writer's `read-only` subcommand takes no `--approver`, so in practice this is the owner |
| `allow_dangerous` | `revoke-dangerous --requester <r>` | the grant's `owner` **only** — the writer records no `approvers` on a grant, so there is no delegate and no fallback |

Two legacy shapes defeat the check entirely and have to be re-recorded through
the writer before they can be lifted: a **bare glob string**, refused outright
because there is no field to check; and a record with an **absent `owner`**,
releasable only by a name in its `approvers` and by nobody when that list is
empty. `status` reports both under its unowned-entries warning.

## Release, never deletion

`release` and `release-read-only` set `released_at`, `released_by`, and
`release_reason` on the matching records and leave them in place. No boundary
entry is ever deleted, because the record is the audit trail: who locked what,
who lifted it, and on what grounds. The hook treats a record as effective until
`released_at` is set and never expires one by age, so the released record is both
the lift and the evidence of the lift.

`revoke-dangerous` is the exception in shape. It resets `allow_dangerous` to
`false` rather than annotating it, so the grant's owner, scope, reason, and expiry
do not survive the revoke — copy all four into the unfreeze record *before*
running it, or that history is gone.

## Writer exit contract

| Exit | Meaning | Response |
| --- | --- | --- |
| 0 | released; the JSON acknowledgement names the glob or run, the releaser, and how many records changed | attach it as the release evidence |
| 1 | refused — no active boundary matches, the requester is not authorized, the entry is an unowned legacy shape, or the record is corrupt; nothing changed | resolve the stated reason; a refusal is a contract violation, never something to route around |
| 2 | usage error — a missing or malformed flag | fix the command; nothing was written |
| other non-zero | the command never ran to completion — no interpreter on `PATH`, the harness not installed, or an unwritable state directory | the boundary is **still in force**; report the unfreeze as not performed |

## Fail-open semantics

Per `../../harness-doctrine.md` §3 the hook *fails open*: a malformed
`guard-state.json`, an unreadable path, or a host that does not run hooks lets the
action proceed silently. A boundary that still reads as active in `status` may
therefore already have been unenforced in practice, so an unreleased entry is
never evidence that the area was actually protected in the meantime. Report what
the record shows and what was verified, not what the hook is assumed to have
caught.
