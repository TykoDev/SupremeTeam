---
name: freeze
description: >-
  Records an owned write boundary over a declared glob so nothing changes inside it
  until the owner lifts it. Use when the user asks to freeze this area, protect this
  path from edits, lock the boundary, or stop changes here — even when they only say
  "don't touch the payments code". Creates the lock only: lifting it belongs to
  `unfreeze`, a verdict with no boundary to `careful`,
  the combined posture to `guard`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Freeze

## Purpose

An informal "don't touch that" survives exactly as long as everyone remembers it. This skill turns it into a durable record with a name on it: one glob, one accountable owner, the release conditions written down at the moment the risk is understood rather than reconstructed later, and — where the host runs hooks — a deterministic block that stops the edit instead of regretting it. What the record buys is a boundary that outlives the conversation that created it and can be lifted only by someone entitled to lift it.

## Use This Skill When

Use this skill to **lock a declared path or boundary** from edits until it is explicitly lifted:

- "freeze this area" / "lock the boundary" — declare the path, service, or environment off-limits
- "protect this path from edits" — record the lock and (where hooks run) enforce it deterministically
- "stop changes here" — hold the boundary until the owner releases it

Route elsewhere to lift the lock (`unfreeze`), add only an intent check (`careful`), or apply both intent checks and the boundary together (`guard`).

## Inputs

- Path, service, or environment boundary to freeze and the owning contributor who can lift the restriction.
- Current mutable operations against the boundary, pending changes, and deployment state at freeze time.
- Release conditions that define when and how the boundary can be unfrozen.

## Outputs

- Freeze record identifying the locked boundary, blocked operations, permitted exceptions, and the owner who can unfreeze.
- Guard-state record appended to `frozen_globs` through `../harness/hooks/guard_state.py` — glob, owner, scope, created_at, run_id, approvers, and a null `released_at` — for deterministic enforcement when hooks are available.
- Release-condition summary so the `unfreeze` skill knows exactly what must be verified before lifting the restriction.

## Workflow

1. Identify the declared path, service, or environment boundary to freeze and the owning contributor who can later lift the restriction.
2. Verify owner intent and current mutable operations, then mark the guarded area as frozen before additional edits, deploys, or destructive steps occur.
3. Record the freeze by running `python skills/harness/hooks/guard_state.py freeze --glob <boundary> --owner <contributor>` — never by editing `.harness-state/guard-state.json` — and capture the blocked changes, permitted exceptions, and the evidence showing why the restriction must stay in place alongside it.
4. Return a freeze record with release conditions, owner handoff notes, and the next safe work that can continue outside the frozen boundary.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Deterministic Enforcement (Action Realization layer)

Freeze is the advisory expression of the Action Realization layer (`../harness-doctrine.md` §1). When the host supports compatible runtime hooks, the frozen boundary is also **deterministically enforced** by `../harness/hooks/pre_tool_use.py`, which blocks any edit or command that touches a frozen path before it executes.

**The boundary record has a single writer.** `.harness-state/guard-state.json` is written only by `../harness/hooks/guard_state.py`, and `pre_tool_use.py` denies direct edit-tool writes and mutating shell commands against that path, exactly as core run records are routed through `save_run.py`. The reason is structural: before the writer existed the boundary was self-liftable, because one write clearing `frozen_globs` — or setting `allow_dangerous`, which disables destructive-pattern blocking globally — lifted the protection before any rule below ever ran. Recording through the writer keeps every entry owned, every release attributable, and the audit trail intact.

To activate enforcement, record the frozen path through the writer rather than by editing the file:

```bash
python skills/harness/hooks/guard_state.py freeze --glob "src/payments/**" --owner <contributor> --scope "<why the boundary exists>" [--run-id <run>] [--approver <delegate>]
python skills/harness/hooks/guard_state.py status
```

Each run appends one owned record to `frozen_globs`. Two fields decide who can ever lift it: `owner`, and the `approvers` the writer records from `--approver`. A release is authorized by either, so a boundary whose owner may go off-shift is recorded with a named delegate at freeze time rather than negotiated later. A record stays effective until its owner records `released_at`; age alone never expires a protection.

The writer exits 1 and changes nothing when the glob is already recorded and unreleased or the record on disk is corrupt, so a duplicate or damaged freeze surfaces instead of being silently overwritten. Any other non-zero exit means the freeze was **not recorded** at all — check the command actually ran before reporting a boundary that does not exist.

**This hook is advisory-grade, not a hard lock.** Per harness-doctrine §3 it *fails open*: a malformed `guard-state.json`, an unreadable path, or a host that does not run hooks exits silently and lets the edit proceed, so a hook fault means a write into a frozen path is *allowed*. Back a boundary that must not change under any circumstances with version-control protections or filesystem permissions as well.

For the `frozen_globs` record shape, the state-directory resolution order, the authority fields and the two legacy shapes that defeat them, and the writer's full exit contract, see `references/enforcement.md`.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Confirm every frozen boundary is backed by an explicit owner, release conditions, and evidence of the risk that justified the freeze.
- Surface enforcement gaps — such as missing hooks or absent `guard-state.json` — so the caller knows the freeze is advisory-only.
- Shape the freeze record so the `unfreeze` skill can verify release conditions without re-investigating the original risk.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The freeze request does not identify one coherent boundary to lock | Refuse the freeze until the path, service, or environment is explicit enough to enforce. |
| Active remediation is already in progress inside the boundary | Record the overlap and decide whether the work must stop immediately or complete one bounded step before the freeze takes effect. |
| A requested exception would silently undermine the freeze | Treat the exception as a separate override decision and keep the freeze intact until it is approved explicitly. |
| A stale freeze record already exists for the same area | Reconcile the existing state before recording a second freeze so later resume behavior stays unambiguous. `guard_state.py freeze` refuses a glob that is already recorded and unreleased, so the reconciliation is release-then-record through the writer, never a hand edit of the state file. |
| The writer exits non-zero for a reason other than a duplicate or a corrupt record — no interpreter on `PATH`, the harness not installed, an unwritable or uncreatable state directory, or a usage error (exit 2) | Report the freeze as not recorded and name the exact failure. Do not describe the boundary as enforced: nothing was written, so the hook will not block anything. Hold the area socially, fix the environment or the command, and re-run the writer before claiming the freeze. |
| The requested boundary is described in prose rather than as a glob ("the migration scripts and the schema history directory") | Convert it to one or more explicit globs before recording, because `--glob` is what the hook matches against; a prose boundary recorded verbatim enforces nothing. Record one glob per boundary and name each in the freeze record. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes, each recorded through the writer with an explicit owner.
- `references/enforcement.md` for the `frozen_globs` record shape, state-directory resolution, the `owner`/`approvers` authority fields, and the writer's exit contract.
- `../harness/hooks/guard_state.py` for the sanctioned writer and its subcommands, and `../harness-doctrine.md` (§1 Action Realization, §3 fail-open) for the layer this boundary sits in.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, and `references/enforcement.md` together. The deterministic hook and its writer ship with the harness (`harness/hooks/`), not inside this skill. Keep generated reports and archives outside the skill directory.
