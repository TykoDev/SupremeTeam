---
name: bug-review
description: >-
  Finds correctness defects, broken invariants, crash paths, and data-corruption
  risk in the scoped code surface. Use when the user asks to find the bugs, review
  correctness, check failure paths, or look for broken assumptions — even when they
  only say "something is wrong here" and point at code. Deterministic correctness
  only: exploit chaining goes to `review/mr-robot`, defensive posture to
  `review/security-review`, tech debt to `review/quality-review`, merge-readiness to
  `review/code-review`, and the whole multi-lens flow to `review/code-chief`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Bug Review

## Purpose

Answers one question about the scoped surface: does it do the wrong thing on a path a user can reach. A defect counts here only when a trigger, an observable failure, and a code anchor can all be named; anything short of that is carried as an open question rather than promoted to a finding.

## Entry Routing

Bug-review is an internal review lens, not an entry point. `../../routing-doctrine.md` places every `review/` skill it does not name separately in the internal-specialist row, reached only through the owning sub-orchestrator — `review/code-chief`, which owns lens selection, scope, and packet assembly for the `review` pipeline. Run the active-handoff check before tracing anything: the bounded surface, the approved revision, and the invariants this lens judges arrive with the handoff and nowhere else.

A handoff is present when the delegation prompt carries a `### Save Context` block, an active run lock with `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names `review/code-chief` as the delegating owner for the review boundary.

- **Handoff present** → proceed; this is a delegated lens assignment.
- **Reached cold** → return to `review/code-chief`, let it run lens selection and scoping, then accept the delegation back. A cold invocation carries no bounded surface and no revision to anchor a defect to, so its report cannot enter the consolidated package.

## Use This Skill When

Use this lens for **deterministic correctness** — defects that yield wrong output, crashes, or corrupted state on a reachable path:

- "find the bugs" / "review correctness" — trace the logic for broken invariants
- "check failure paths" — exercise error, retry, and recovery branches
- "look for broken assumptions" — surface unstated preconditions callers can violate
- "something is wrong here" — pointed at code, with no reproduction or mechanism supplied yet

Route elsewhere when the real concern is attacker-driven chaining (`review/mr-robot`), defensive-security exposure (`review/security-review`), maintainability or architecture drift (`review/quality-review`), or merge-readiness of a specific diff (`review/code-review`). An unreproduced failure whose mechanism is unknown belongs to `investigate`, not to this lens.

## Inputs

- Code surface under review, including changed files, modules, and the implementation diff.
- Test results, crash logs, and any prior defect reports that narrow the suspect surface.
- Interface contracts and invariants the code is expected to preserve.
- Bug-priority guidance, known flaky areas, excluded modules, or pipeline-specific invariants that constrain the defect hunt.
- On a REVISE round, the `changed_evidence` key list from the gate packet and the prior packet's finding ids.

## Outputs

- Correctness defect report with each bug tied to a specific file, line, or observable behavior.
- Severity-ranked finding list distinguishing crash paths and data-corruption risks from minor logic errors.
- Bug-review lens packet for `review/code-chief` with defect ids, affected invariants, reproduction evidence, and any scoped exclusions.

### Where the packet lands at `review-to-delivery`

This lens owns no evidence key. `../../gates.yaml` `evidence_owners` assigns every `review-to-delivery` key to `code-chief` or `design-qa`; `findings` and `review_verdict` belong to `code-chief` and are never authored here. The packet feeds them, and reaches the gate two ways:

| Path | What must be true |
| --- | --- |
| Graded items merge into `findings` | Every item carries an id, one of the four severities, and a status, so `code-chief` can merge without re-reading the implementation (`../../gates.yaml` `evidence_types.findings`). |
| The saved packet fills the `lens_bug` slot | `review/gatekeeper-code`'s `scripts/check.py` matches `lens_bug` on `*bug*.md` or `deliverable_*bug*.md`, so the packet is saved as `deliverable_bug-review.md`. Any other name leaves the slot empty and fails the mechanical pass for a lens that actually ran. |

The `bug-findings` artifact `../../ownership.yaml` assigns to this lens is that same packet, due before finding triage.

## Workflow

1. Trace the scoped code paths, mutable state, and invariants before naming any correctness defect.
2. Trace crash paths, stale-state updates, ordering mistakes, retry hazards, and persistence corruption risks by reading the code and the evidence the handoff supplies — probing here means following a path through the source, never executing it (Required Contracts below) — and anchor each suspected bug to visible evidence.
3. Separate deterministic correctness failures from speculative concerns, then document trigger condition, user impact, and smallest credible fix path for every major finding.
4. Deliver a correctness packet to `review/code-chief` with repro notes, blocking defects, and any handoffs required for security, UX, or performance follow-up.

## Packet Shape

Every pass returns the same fields in this order, so `review/code-chief` merges lenses instead of reformatting them (`../../execution-contract.md`, clause 6; this lens owns no gate, so it returns no verdict):

```text
Outcome:     bug-review, <revision reviewed>, <n> findings: <c> Critical, <m> Major, <k> Minor, <i> Info
Evidence:    <files and ranges traced, tests and logs read, what was excluded>
Findings:    <id> | Critical|Major|Minor|Info | <file:line> | <broken invariant and trigger> | <fix direction>
Open risks:  <suspected defects left unverified, and the log or repro that would settle each>
Next action: <single next step with its owner>
Revision:    <revision this packet judges>
```

Grade findings `Critical | Major | Minor | Info` and nothing else (`../../execution-contract.md`, clause 3). "Blocking", "high", and "nit" are not severities: a blocker is a Critical, or a Major whose status says it blocks; a nit is a Minor.

### Clean pass

A pass that finds nothing returns the same fields with an empty finding set — never silence, never an absent packet, because clause 5 requires empty results to be stated explicitly:

```text
Outcome:     bug-review clean — 0 findings across <surface traced>
Evidence:    <paths and branches actually walked, so the emptiness is attributable>
Findings:    (none)
Open risks:  <coverage this pass could not reach>, or "none"
Next action: none from this lens
Revision:    <revision reviewed>
```

A clean pass asserts the surface was examined and held. When the surface itself is absent, the Skip Rule below applies instead and produces a skip record; `review/code-chief` carries a clean result and a skip differently into the package.

## REVISE Rounds

`check.py` groups a REVISE packet by evidence key and routes each group to that key's owner in `../../gates.yaml` `evidence_owners`. At `review-to-delivery` every key belongs to `code-chief` or `design-qa`, so no group is addressed to this lens directly: `code-chief` receives the group and sub-delegates the part this lens owns, under a `cycle_cap` of 2. `revise_policy.parallel_fix` is what lets that sub-delegation run alongside the other lenses rather than in sequence. A REVISE round is a delta pass, not a fresh review:

1. Re-review only the files and keys named in `changed_evidence` for this group, plus any path whose correctness depends on them. Unchanged evidence keeps its prior judgment, mirroring how the gatekeeper re-judges under `delta_review`.
2. Carry prior finding ids forward. A resolved defect returns with status `verified` and the evidence that verifies it; an unresolved one returns under its original id and severity, never renumbered.
3. State the round in the `Revision` line as a delta, for example `r2 <- r1`.
4. Report a defect found outside `changed_evidence` as a new item marked out-of-delta rather than widening the round silently. `review/code-chief` decides whether it enters this cycle or the next.

At the cycle cap, an unresolved Critical or Major returns unchanged with its blocking status intact; the cap never justifies a downgrade.

## Required Contracts

- **Read-only over the reviewed surface**: This lens reports and never edits the code, tests, configuration, or documentation it reviews. `allowed-tools` withholds `Edit` so the posture is enforced rather than promised, and `Write` covers the packet and its evidence under the save path only. A fix this lens can see is written into the finding as a fix direction and routed through `review/code-chief` to the owning build skill; applying it here would insert an unreviewed change into the surface the gate is judging and destroy the baseline the next round compares against.
- **Execution posture — read and trace, never run the reviewed surface**: `allowed-tools` grants `Bash`, and that grant is bounded: it is for reading the surface and the run's own evidence — `git` history and diffs, `grep` and file inspection, the test, CI, and crash logs the handoff supplies, and the save-path writes this lens owns. It is never for running the reviewed program, its test suite, its build, or any script the reviewed tree ships. The reason is that this lens has no disposable environment to run them in. `review/devex-review` is the one lens in this pipeline that executes, and it takes on a throwaway container, a per-command owner approval, and a recorded read-only boundary to do it; bug-review has none of those, so executing here would take that risk on the host bare, and a defect reproduced on a machine the reviewed code just wrote to is no longer attributable to the revision under review. A defect that only execution can settle is not promoted on suspicion: it goes in Open risks naming the run that would settle it, and `review/code-chief` routes it to a lens or phase that can execute safely. A trigger, an observable failure, and a code anchor are all nameable from reading; where they are not, the item is an open question by construction.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Anchor every defect to a concrete code path, test failure, or invariant violation — not to a category label.
- Distinguish confirmed bugs from suspicious patterns that need further investigation.
- Shape the defect report so `review/code-chief` can merge it into the consolidated review without re-reading the implementation.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no behavioral or logical surface to exercise (pure formatting, comment-only, or asset-only changes). A skip is recorded as a `_skip-record.md` carrying `pipeline`, `skipped_at`, `reason`, and `approved_by`, which `review/gatekeeper-code` validates; that is a different result from the clean pass above, which asserts the surface was examined.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The supplied artifacts do not expose enough runtime behavior to reproduce a suspected crash or invariant break | Mark the issue as unverified, name the missing logs, test case, or repro steps, and request the minimum evidence needed to confirm the defect. |
| The suspected bug crosses async, distributed, or persistence boundaries outside the provided scope | Trace the visible boundary, describe the missing dependency chain, and stop short of inventing behavior that is not in evidence. |
| Multiple symptoms appear to stem from the same broken invariant | Merge them under one root-cause finding so the remediation path stays coherent instead of fragmented. |
| A discovered issue belongs primarily to security, UX, or performance rather than correctness | Record the correctness impact if any, then hand the item to the appropriate specialist instead of diluting the bug report. |
| The pass ends with no defect found | Return the clean-pass packet above. Silence is indistinguishable from a lens that never ran, and an empty result is evidence only when the traced surface is stated with it. |
| A REVISE round arrives without `changed_evidence` | Request the key list from `review/code-chief` before re-reviewing. Re-reading the whole surface inside a capped cycle spends the round on unchanged code and loses the delta the gatekeeper expects. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Name the lens packet `deliverable_bug-review.md`, the filename `review/gatekeeper-code` matches for the `lens_bug` slot. A packet under any other name leaves that slot empty and fails the mechanical pass for a lens that ran.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
