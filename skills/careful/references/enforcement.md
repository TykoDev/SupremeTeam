# Careful — Deterministic Enforcement Reference

Read this before issuing any verdict on a destructive action. It explains what
the deterministic half of the Action Realization layer blocks, how to read the
live boundary that step 0 of the careful check requires, and how a verdict must
change when that layer is lifted, faulted, or absent.

## Contents

1. [What sits behind a careful verdict](#what-sits-behind-a-careful-verdict)
2. [Step 0 — read the live boundary](#step-0--read-the-live-boundary)
3. [Reading the status output](#reading-the-status-output)
4. [When `allow_dangerous` actually lifts the block](#when-allow_dangerous-actually-lifts-the-block)
5. [Careful reads the record and never writes it](#careful-reads-the-record-and-never-writes-it)
6. [Fail-open semantics](#fail-open-semantics)
7. [Enforcement faults and the verdict they force](#enforcement-faults-and-the-verdict-they-force)

## What sits behind a careful verdict

Careful is the intent half of the Action Realization layer
(`../../harness-doctrine.md` §1). The deterministic half is
`../../harness/hooks/pre_tool_use.py`, which blocks a literally destructive
command — a recursive root or home delete, a drive format, a raw-device write, a
force-push to a protected branch — before the host executes it. A careful verdict
sits on top of that block, never in place of it, so a verdict is only as safe as
the block still standing behind it.

That block can be lifted. `allow_dangerous` in `.harness-state/guard-state.json`
is a global kill-switch: while an owned grant is live, every destructive pattern
passes for every command in the session, not only the operation the grant was
requested for. A go verdict issued while the kill-switch is lifted is wrong — it
reads as "this action is safe" when in fact nothing is left between the action
and execution.

## Step 0 — read the live boundary

```bash
python skills/harness/hooks/guard_state.py status
python skills/harness/hooks/guard_state.py status --json   # machine-readable form
```

Exit 0 prints the effective boundary. Exit 1 is a refusal — the record exists but
cannot be read (see [Enforcement faults](#enforcement-faults-and-the-verdict-they-force)).
Exit 2 is a usage error in the command itself.

## Reading the status output

The human-readable form prints one line per key:

```text
record: D:\proj\.harness-state\guard-state.json (exists: True)
frozen:  ['src/payments/**']
blocked: ['**/secrets/**']
read-only runs: ['2026-09-16-charge-bug']
allow_dangerous: {'owner': 'ops-lead', 'scope': 'scratch-volume rebuild', 'expires_at': '2026-09-16T09:50:11Z', ...}
WARNING unowned (not releasable by authority check): ['legacy/path/**']
```

Carry four facts into the careful record:

- whether `allow_dangerous` is `false` or a live grant, naming its owner, scope,
  and `expires_at`;
- which `frozen_globs` and `blocked_globs` entries cover the target — a write
  inside one is denied outright by the hook's Rule B, so an action planned there
  is blocked before intent is even considered;
- whether a `read_only` run is active, which confines every write to that run's
  own `allow` globs;
- any `unowned` warning, because such an entry cannot be released through the
  writer's authority check and has to be re-recorded before it can ever be lifted.

A live grant the requested action does not need is itself a finding. Require the
owner to revoke it and re-run the check before any go:

```bash
python skills/harness/hooks/guard_state.py revoke-dangerous --requester <owner>
```

Only the grant's owner may revoke it — the writer records no approvers on a
grant, so a delegate authorized for a frozen glob is still refused here.

## When `allow_dangerous` actually lifts the block

The hook's `_dangerous_lifted` check is deliberately narrow, and a careful record
that describes it loosely will read a closed guard as open or an open guard as
closed. Exactly four shapes matter:

| Recorded value | Destructive-pattern block |
| --- | --- |
| `false`, or the key absent | in force |
| bare `true` (legacy, never written by `guard_state.py`) | **lifted, with no end** |
| a grant whose `expires_at` is in the future | **lifted until that moment** |
| a grant with an expired, unparseable, or missing `expires_at` | in force |

A grant that carries no `expires_at` is malformed rather than permanent: the
writer always records one, and a guard that cannot read its own grant stays
closed rather than open. The only unbounded lift is the legacy bare `true`, which
the writer never produces — one more reason the record is not hand-edited.

## Careful reads the record and never writes it

`guard_state.py` is the record's single sanctioned writer, and `pre_tool_use.py`
denies direct edit-tool and mutating-shell writes to that path. Before that
routing existed, one hand edit lifted every freeze and disabled
destructive-pattern blocking outright. A careful check therefore reads `status`,
quotes it, and routes any change — recording a boundary, lifting one, revoking a
grant — to `guard`, `freeze`, or
`unfreeze`, which call the writer.

## Fail-open semantics

Per `../../harness-doctrine.md` §3 the hook *fails open*: malformed state, an
unreadable path, or a host that never runs hooks lets the action proceed
silently. A no-go therefore stands on its own evidence rather than on the hook,
and an absent, corrupt, or unreadable `guard-state.json` is a reason to tighten
the verdict — not to assume the command would have been caught anyway.

## Enforcement faults and the verdict they force

| Fault | Signal | Effect on the verdict |
| --- | --- | --- |
| `guard_state.py` cannot run — no interpreter on `PATH`, the harness is not installed, or the path does not resolve | the shell reports a missing command or file, and nothing is printed on stdout | Record that the boundary is unknown, not that it is clear. A destructive action gets no-go or escalate until the boundary can be read. |
| `status` exits 1 on a corrupt record | stderr begins `refused:` and names the record as invalid JSON or the wrong type | Treat every boundary in the file as unreadable and the hook as effectively absent. No-go on destructive work; the repair is an owner action outside the agent's tool loop, because the hook denies an agent write to that path. |
| The hook is never registered with the host | `status` reads cleanly but no tool call is ever denied; the host lists no `PreToolUse` hook | The deterministic layer does not exist for this session. Say so in the record rather than citing the boundary as protection, and treat the careful verdict as the only control in place. |
| A live `read_only` record covers the run | `read-only runs` is non-empty in `status` | Every write outside that run's `allow` globs is already denied. A go verdict on such a write is unreachable; escalate to the record's owner for a `release-read-only` instead. |
