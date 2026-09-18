---
name: code-review
description: >-
  Judges one change for merge: the merge blockers in this diff, change risk, test
  signal, and reviewer load. Use when the user asks to check merge readiness, audit
  this diff, or find the merge blockers in this diff — even when they just drop a
  diff and ask "is this good to merge?". Exhaustive correctness hunting goes to
  `review/bug-review`, security to `review/security-review`, long-horizon
  maintainability to `review/quality-review`; an unscoped review request with no
  diff named yet, and the full multi-lens flow, go to `review/code-chief`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Code Review

## Purpose

Answers whether this change is safe to merge now. The unit of judgment is the submitted diff and the context it touches — not the module it lives in, and not the rewrite it could have been — so an observation earns a place in the packet only when it changes the merge decision or a reviewer's ability to make that decision confidently.

## Entry Routing

Code-review is an internal review lens, not an entry point. `../../routing-doctrine.md` places every `review/` skill it does not name separately in the internal-specialist row, reached only through the owning sub-orchestrator — `review/code-chief`, which owns lens selection, scope, and packet assembly for the `review` pipeline. Run the active-handoff check before judging anything: the diff boundary, the merge target, and the approved revision this lens rules on arrive with the handoff and nowhere else.

A handoff is present when the delegation prompt carries a `### Save Context` block, an active run lock with `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names `review/code-chief` as the delegating owner for the review boundary.

- **Handoff present** → proceed; this is a delegated lens assignment.
- **Reached cold** → return to `review/code-chief`, let it run lens selection and scoping, then accept the delegation back. A merge recommendation made without the run's scope, baseline, and revision is an opinion the gate cannot act on.

## Use This Skill When

Use this lens to judge **a specific change for merge** — readability, change risk, test signal, and reviewer load on the diff under judgment:

- "check merge readiness" — weigh blockers against the merge decision
- "audit this diff" — bound the review to the actual diff and touched interfaces
- "find the merge blockers in this diff" — separate what stops the merge from what can follow it
- "is this good to merge?" — the bare verdict, on a diff someone has just dropped
- "what's the change risk in this diff" — size the blast radius and the test signal standing behind it

Route elsewhere when the real need is exhaustive correctness or crash analysis (`review/bug-review`), defensive-security review (`review/security-review`), whole-surface architecture drift rather than this diff (`review/quality-review`), or the full multi-lens flow (`review/code-chief`). An unscoped review request that names no diff belongs to `review/code-chief` as well: it owns the bare phrase, bounds the surface, and schedules this lens among the others. This lens claims a request only once a specific change is named.

## Inputs

- Change diff, commit history, and the merge target branch or release context.
- Local quality signals such as linting results, style violations, and naming conventions.
- Change-risk indicators including affected module scope, breaking-change potential, and reviewer notes.
- Merge-decision guidance such as release urgency, style-policy exclusions, or areas already approved by earlier review.
- Verification story for the change: tests run, manual checks, build/lint output, and any intentionally skipped validation.
- On a REVISE round, the `changed_evidence` key list from the gate packet and the prior packet's finding ids.

## Outputs

- Merge-readiness assessment with a clear go/no-go recommendation and supporting evidence.
- Finding list covering merge blockers, change risk, and clarity issues prioritized by merge impact.
- Merge-readiness lens packet for `review/code-chief` with go/no-go rationale, blocking issues, optional cleanup, and excluded diff regions.

### Where the packet lands at `review-to-delivery`

This lens owns no evidence key. `../../gates.yaml` `evidence_owners` assigns every `review-to-delivery` key to `code-chief` or `design-qa`; the consolidated `review_verdict` belongs to `code-chief`, and a recommendation from this lens is an input to it, never a substitute for it. The packet reaches the gate two ways:

| Path | What must be true |
| --- | --- |
| Graded items merge into `findings` | Every item carries an id, one of the four severities, and a status, so `code-chief` can merge the packet without re-diffing the change (`../../gates.yaml` `evidence_types.findings`). |
| The saved packet fills the `lens_code` slot | `review/gatekeeper-code`'s `scripts/check.py` matches `lens_code` on `*code-review*.md`, `*code*.md`, or `deliverable_*code*.md`, so the packet is saved as `deliverable_code-review.md`. The previously sanctioned `review-packet.md` matches no lens pattern and leaves the slot empty. |

The `merge-readiness-report` artifact `../../ownership.yaml` assigns to this lens is that same packet, due before finding triage.

## Workflow

1. Bound the review to the actual diff, touched interfaces, and merge context before commenting on readiness.
2. Review the test evidence first, then inspect correctness signals, readability/simplicity, architecture fit, security exposure, and performance risk in that order. Security exposure here is *flag, do not review*: name what looks exposed and route it to `review/security-review`, which owns the assessment. A merge-readiness packet that adjudicates a security finding has done another lens's job without its evidence.
3. Apply YAGNI and dependency discipline: flag speculative abstractions, pass-through wrappers, future-proofing with no current use, unnecessary new dependencies, and refactors that relocate complexity instead of reducing it.
4. Separate merge blockers from optional cleanup, then explain how each major issue affects safety, maintainability, reviewer comprehension, or verification confidence.
5. Deliver a merge-readiness packet to `review/code-chief` with blockers, optional cleanups, rejected nits, and any follow-up lenses that should inspect the same surface.

## Packet Shape

Every pass returns the same fields in this order, so `review/code-chief` merges lenses instead of reformatting them (`../../execution-contract.md`, clause 6; this lens owns no gate, so it returns no verdict):

```text
Outcome:     code-review, <revision reviewed>, merge recommendation: <go | no-go>, <n> findings: <c> Critical, <m> Major, <k> Minor, <i> Info
Evidence:    <diff range judged, tests and lint output read, regions excluded as generated or vendored>
Findings:    <id> | Critical|Major|Minor|Info | <file:line> | <merge impact> | <fix direction>
Open risks:  <readiness questions left unanswered, and the artifact that would answer each>
Next action: <single next step with its owner>
Revision:    <revision this packet judges>
```

Grade findings `Critical | Major | Minor | Info` and nothing else (`../../execution-contract.md`, clause 3). "Blocker" and "nit" describe consequence, not severity: a blocker is a Critical, or a Major whose status says it blocks the merge; a nit is a Minor, and an observation with no merge consequence is Info.

### Clean pass

A pass that finds nothing returns the same fields with an empty finding set — never silence, never an absent packet, because clause 5 requires empty results to be stated explicitly:

```text
Outcome:     code-review clean — go, 0 findings across <diff range>
Evidence:    <files and hunks judged, test and lint results relied on>
Findings:    (none)
Open risks:  <verification the diff did not carry>, or "none"
Next action: none from this lens
Revision:    <revision reviewed>
```

A clean pass asserts the diff was judged and is merge-ready. When there is no code diff at all, the Skip Rule below applies instead and produces a skip record; `review/code-chief` carries a clean result and a skip differently into the package.

## REVISE Rounds

`check.py` groups a REVISE packet by evidence key and routes each group to that key's owner in `../../gates.yaml` `evidence_owners`. At `review-to-delivery` every key belongs to `code-chief` or `design-qa`, so no group is addressed to this lens directly: `code-chief` receives the group and sub-delegates the part this lens owns, under a `cycle_cap` of 2. `revise_policy.parallel_fix` is what lets that sub-delegation run alongside the other lenses rather than in sequence. A REVISE round is a delta pass, not a fresh review:

1. Re-review only the hunks and keys named in `changed_evidence` for this group, plus any interface or test whose readiness judgment depended on them. Unchanged evidence keeps its prior judgment, mirroring how the gatekeeper re-judges under `delta_review`.
2. Carry prior finding ids forward. A resolved blocker returns with status `verified` and the evidence that verifies it; an unresolved one returns under its original id and severity, never renumbered.
3. State the round in the `Revision` line as a delta, for example `r2 <- r1`, and restate the merge recommendation for the revised diff rather than leaving the prior one standing.
4. Report an issue that falls outside the round as a new item marked out-of-delta rather than widening the round silently — either outside `changed_evidence` entirely, or inside it by path but unrelated to the findings this round was opened for. Both are the same call: the round answers the questions it was opened with, and anything else is named and handed on rather than folded in. `review/code-chief` decides whether it enters this cycle or the next.

At the cycle cap, an unresolved Critical or Major returns unchanged with its blocking status intact, and the recommendation stays no-go; the cap never converts an unfixed blocker into an accepted one.

## Required Contracts

- **Read-only over the reviewed surface**: This lens reports and never edits the diff, tests, configuration, or documentation it judges. `allowed-tools` withholds `Edit` so the posture is enforced rather than promised, and `Write` covers the packet and its evidence under the save path only. A cleanup this lens can see is written into the finding as a fix direction and routed through `review/code-chief` to the owning build skill; editing the diff under review would change the artifact the merge decision rests on and invalidate the evidence already gathered against it.
- **Before/After Evidence**: This lens intervenes in nothing, so the contract is a baseline rule: the "before" is the submitted diff and the test output read at step 2, recorded so a later claim that the revision improved something can be checked instead of believed. `references/workflow.md` states where in the sequence it is taken.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Base every merge recommendation on observable code evidence — diffs, test results, linting output — not on intent.
- Flag change-risk concerns and breaking-change potential before the consolidated review reaches the gate.
- Use required vs optional language deliberately: correctness, security, contract, and verification gaps block; preference-only simplifications are optional unless the change actively worsens structure.
- Watch change size and file size: ask for a split when one logical review cannot be done confidently, and treat generated/vendor/mechanical churn as excluded evidence unless it changes first-party behavior.
- Deliver findings that `review/code-chief` can merge without re-diffing the change set.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no code diff to review (purely visual assets or documentation with no code paths affected). A skip is recorded as a `_skip-record.md` carrying `pipeline`, `skipped_at`, `reason`, and `approved_by`, which `review/gatekeeper-code` validates; that is a different result from the clean pass above, which asserts the diff was judged.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The diff arrives without a baseline, caller context, or the tests needed to judge merge impact | Record the missing review inputs, narrow the claim to what is visible, and request the smallest artifact set needed for a reliable merge decision. |
| Generated, vendored, or mechanical formatting changes obscure the first-party logic that actually needs review | Isolate the human-authored changes, document what was excluded, and keep style churn from hiding functional blockers. |
| A public interface changes but the affected callers, tests, or migration steps are outside the provided scope | Flag the interface risk explicitly and require the missing usage evidence before calling the change merge-ready. |
| Style or cleanup comments start to crowd out the real merge blockers | Re-rank the report so safety, correctness, and reviewer comprehension issues remain separate from optional cleanup. |
| The diff is judged merge-ready with nothing to report | Return the clean-pass packet above. A go recommendation without the evidence it rests on is indistinguishable from a lens that never ran. |
| A REVISE round arrives without `changed_evidence` | Request the key list from `review/code-chief` before re-reviewing. Re-diffing the whole change inside a capped cycle spends the round on hunks nobody touched. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Name the lens packet `deliverable_code-review.md`, the filename `review/gatekeeper-code` matches for the `lens_code` slot. A packet under any other name leaves that slot empty and fails the mechanical pass for a lens that ran.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
