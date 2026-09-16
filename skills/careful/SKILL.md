---
name: careful
description: >-
  Gates a destructive or irreversible action the moment before it runs, behind
  explicit evidence, reading the live guard state first. Use when the user is about to
  do something they cannot undo — delete, overwrite, force-push, drop, deploy — and
  wants intent confirmed first, even when they only say "don't break anything". Judges
  an action, not a document: issues a go, no-go, or escalate verdict and nothing else.
  Locking a path belongs to `freeze`, both halves together to `guard`, lifting a lock
  to `unfreeze`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Careful

## Purpose

A destructive step is cheap to run and expensive to undo, and the moment before it runs is the only moment where the cost is still zero. This skill spends that moment: it names what the action would actually touch, tests whether the evidence on hand proves target, environment, and intent are the same thing, and converts an implied approval into a written verdict that carries its own residual risk — so nothing downstream can read it as blanket clearance.

## Use This Skill When

Use this skill to **add a confirmation checkpoint** before a destructive or irreversible action runs:

- "be careful with this" / "confirm intent first" — require explicit intent before the action proceeds
- "don't break anything" — insert an evidence-and-intent check ahead of the irreversible step
- "about to delete or overwrite something" — make the consequences explicit before it runs

Route elsewhere to lock a path from any edits (`freeze`), combine intent checks with a write boundary (`guard`), or lift an existing boundary (`unfreeze`).

## Inputs

- Description of the risky or destructive action, the affected boundary, and the current environment state, including the live guard state reported by `python skills/harness/hooks/guard_state.py status`.
- Evidence required to authorize the action, such as backup confirmation, rollback availability, or owner approval.
- Known constraints including protected environments, irreversibility thresholds, and side-effect blast radius.

## Outputs

- Safety guard decision record with go, no-go, or escalate verdict and the exact evidence used.
- Blocked-action list identifying what cannot proceed and what proof would unlock it.
- Escalation notes when the requested action exceeds the available evidence or authority.

## Workflow

1. Read the live boundary with `python skills/harness/hooks/guard_state.py status` (step 0 of Deterministic Enforcement below), then identify the risky action, affected boundary, and the evidence required before any destructive, irreversible, or hard-to-undo step is allowed.
2. Check that the current environment, target surface, and requested intent all match; if any one is ambiguous, stop before execution.
3. Record a go, no-go, or escalate decision with the exact evidence used — including the guard state read in step 1 and any live `allow_dangerous` grant — the remaining uncertainty, and the safest next action available.
4. Return a careful record that states what can proceed now, what stays blocked, and what proof would unlock the next step safely.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Deterministic Enforcement (Action Realization layer)

Careful is the intent half of the Action Realization layer (`../harness-doctrine.md` §1). The deterministic half is `../harness/hooks/pre_tool_use.py`, which blocks a literally destructive command before the host executes it. A careful verdict sits on top of that block, never in place of it, so a verdict is only as safe as the block still standing behind it — and that block can be lifted session-wide by an `allow_dangerous` grant.

**Step 0 of every careful check on a destructive action is therefore to read the live boundary:**

```bash
python skills/harness/hooks/guard_state.py status
```

Quote that state in the careful record — the `allow_dangerous` value with its owner, scope, and `expires_at`; the `frozen_globs`, `blocked_globs`, and `read_only` records covering the target — and treat a live grant the requested action does not need as a finding rather than as context. Careful reads this record and never writes it; changing a boundary routes to `guard`, `freeze`, or `unfreeze`, which call the single sanctioned writer.

The hook *fails open* (harness-doctrine §3), so an absent, corrupt, or unreadable `guard-state.json` tightens a verdict rather than excusing one. Read `references/enforcement.md` before the first destructive verdict: it carries how to read the `status` output, exactly which `allow_dangerous` shapes lift the block and which leave it in force, and the verdict each enforcement fault forces.

## Collaboration Surface

- None required beyond the active task surface.

## Review Expectations

- Base every safety verdict on explicit evidence — backup confirmation, rollback test, or owner approval — not on assumed safety.
- Surface missing prerequisites and irreversibility risks before the action reaches execution.
- Shape the guard record so the requesting workflow knows exactly what is safe to proceed with and what remains blocked.

## Skip Rule

Skip only when the requested surface, tool, or environment does not exist and a safe fallback is unavailable.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The risky action is described too broadly to tell what would actually be affected | Narrow the boundary first and refuse to bless a vague request that could hide destructive scope. |
| Intent, evidence, and environment point at different targets | Freeze the decision, name the mismatch, and require one coherent target before any action proceeds. |
| The requested step depends on a prerequisite that has not been verified | Keep the action blocked and state the minimum evidence needed to prove the precondition. |
| Another contributor could misread the outcome as unconditional approval | Write the residual risk and release conditions directly into the careful record so the next step is bounded. |
| `guard_state.py` cannot run — no interpreter on `PATH`, the harness is not installed, or the path does not resolve | Record the boundary as unknown rather than clear, and hold a destructive action at no-go or escalate until step 0 can actually be performed. |
| `guard_state.py status` exits 1 because the record is corrupt or not a JSON object | Treat every boundary in the file as unreadable and the deterministic layer as absent. Refuse destructive work and route the repair to the record's owner — the hook denies an agent write to that path, so it is fixed outside the tool loop. |
| The hook is never registered with the host, so no tool call is ever denied | Name the gap in the record and treat the careful verdict as the only control in place; do not cite the boundary as protection that is not running. |
| A live `allow_dangerous` grant is present that the requested action does not need | Withhold the go, record the grant's owner, scope, and `expires_at`, and require `guard_state.py revoke-dangerous --requester <owner>` — only the grant's owner may revoke it — before re-running the check. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes, each showing the step 0 boundary read that produced the verdict.
- `references/enforcement.md` for reading the `status` output, the four `allow_dangerous` shapes and which of them lift the block, and the verdict each enforcement fault forces.
- `../harness/hooks/guard_state.py` for the `status` read in step 0 and the `revoke-dangerous` subcommand, and `../harness-doctrine.md` (§1 Action Realization, §3 fail-open) for the layer this check sits on.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, and `references/enforcement.md` together. The deterministic hook and its writer ship with the harness (`harness/hooks/`), not inside this skill. Keep generated reports and archives outside the skill directory.
