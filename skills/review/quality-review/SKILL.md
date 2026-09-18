---
name: quality-review
description: >-
  Assesses long-horizon maintainability, architecture drift, standards compliance,
  and technical-debt pressure across the scoped surface. Use when the user asks to
  review code quality, check maintainability, measure technical debt, or look for
  architecture drift — even when they only ask "is this codebase getting harder to
  work in?". Takes the multi-change health view; gating one diff for merge goes to
  `review/code-review`, concrete defects to `review/bug-review`, and security
  exposure to `review/security-review`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Quality Review

## Purpose

Answers what this surface will cost to change six months from now. Judgment runs against the architecture the system actually committed to, not a greenfield the reviewer would have preferred, so every finding names the boundary that drifted and the future work it taxes.

## Entry Routing

Quality-review is an internal review lens, not an entry point. `../../routing-doctrine.md` places every `review/` skill it does not name separately in the internal-specialist row, reached only through the owning sub-orchestrator — `review/code-chief`, which owns lens selection, scope, and packet assembly for the `review` pipeline. Run the active-handoff check before assessing anything: the module boundaries in scope, the accepted legacy exclusions, and the approved revision arrive with the handoff and nowhere else.

A handoff is present when the delegation prompt carries a `### Save Context` block, an active run lock with `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names `review/code-chief` as the delegating owner for the review boundary.

- **Handoff present** → proceed; this is a delegated lens assignment.
- **Reached cold** → return to `review/code-chief`, let it run lens selection and scoping, then accept the delegation back. Without the run's accepted-debt exclusions, a cold pass re-reports debt the team already decided to carry.

## Use This Skill When

Use this lens for **long-horizon health** — how maintainable the surface stays as it grows, independent of any single merge:

- "review code quality" / "check maintainability" — assess structure, naming, and coupling
- "measure technical debt" — name the debt and the pressure it puts on future change
- "look for architecture drift" — flag where the implementation diverges from intended boundaries
- "is this codebase getting harder to work in?" — the complaint form, with no single diff in view

Route elsewhere when the concern is gating one diff for merge (`review/code-review`), a concrete crash or wrong-output defect (`review/bug-review`), or a security weakness (`review/security-review`).

## Inputs

- Code surface under review with its module boundaries, dependency graph, and architecture constraints.
- Standards baseline such as naming conventions, layering rules, and technical-debt indicators.
- Prior quality findings or architecture-drift notes from earlier review rounds.
- Maintainability priorities such as architecture layers to inspect, standards exceptions, legacy areas accepted as-is, or debt categories to ignore.
- Deprecation, migration, or simplification context: known legacy systems, replacement plans, unused abstractions, and areas where behavior must be preserved exactly.
- On a REVISE round, the `changed_evidence` key list from the gate packet and the prior packet's finding ids.

## Outputs

- Maintainability assessment covering architecture drift, standards compliance, and technical-debt pressure.
- Finding list with each quality issue tied to a specific module, pattern, or dependency boundary.
- Quality lens packet for `review/code-chief` with module/coupling evidence, standards impact, refactor urgency, and excluded legacy debt.

### Where the packet lands at `review-to-delivery`

This lens owns no evidence key. `../../gates.yaml` `evidence_owners` assigns every `review-to-delivery` key to `code-chief` or `design-qa`. The packet reaches the gate two ways:

| Path | What must be true |
| --- | --- |
| Graded items merge into `findings` | Every item carries an id, one of the four severities, and a status; a deferred Major also carries the owner and reopen trigger that make it tracked debt (`../../gates.yaml` `evidence_types.findings`, `finding_policy.major_deferral`). |
| The saved packet fills the `lens_quality` slot | `review/gatekeeper-code`'s `scripts/check.py` matches `lens_quality` on `*quality*.md` or `deliverable_*quality*.md`, so the packet is saved as `deliverable_quality-review.md`. Any other name leaves the slot empty and fails the mechanical pass for a lens that actually ran. |

The `maintainability-report` artifact `../../ownership.yaml` assigns to this lens is that same packet, due before finding triage.

## Workflow

1. Map the module boundaries, ownership seams, and architectural commitments touched by the scoped surface before naming maintainability issues.
2. Apply Chesterton's Fence before recommending removal or simplification: identify what calls the code, what behavior/tests protect it, and why the structure may exist.
3. Examine duplication, abstraction pressure, dependency direction, configuration sprawl, migration/deprecation residue, and long-term change cost against the current architecture rather than an idealized rewrite.
4. Separate local cleanup from structural drift, then explain how each major issue increases future delivery cost, fragility, or cognitive load.
5. Deliver a maintainability packet to `review/code-chief` with architecture drift, simplification candidates, debt hotspots, migration cleanup, and a pragmatic remediation order.

## Blocking and Tracked Debt Inside the Four Tiers

The four shared severities are the whole vocabulary (`../../execution-contract.md`, clause 3). "Blocker" and "debt" name what happens to a graded finding, not a second scale, and `../../gates.yaml` `finding_policy` fixes the mapping:

| Grade | When a maintainability finding earns it | What the gate then does |
| --- | --- | --- |
| Critical | The structure makes shipping code wrong, unsafe, or unmaintainable now — a half-applied migration across live paths, an ownership seam with no writer at all | Blocks until verified fixed, or recorded not-applicable with a reason |
| Major | Change-cost on the critical path is raised now, though the system ships correctly | Blocks unless verified, not-applicable with a reason, or deferred with a named owner and a reopen trigger — that deferral is exactly what tracked debt is |
| Minor | Real friction away from the critical path; the next change in the area pays a small tax | Recorded and carried; becomes owned debt when someone claims it |
| Info | Context the next reviewer needs — a boundary worth watching, a convention that has begun to slip | Preserved as context, never gating |

Debt is a deferred Major or a recorded Minor, never a fifth label. When the grade is genuinely uncertain, take the lower one and state the reason: a Major that turns out to be Minor erodes trust in the lens faster than a Minor that later has to be escalated.

## Packet Shape

Every pass returns the same fields in this order, so `review/code-chief` merges lenses instead of reformatting them (`../../execution-contract.md`, clause 6; this lens owns no gate, so it returns no verdict):

```text
Outcome:     quality-review, <revision reviewed>, <n> findings: <c> Critical, <m> Major, <k> Minor, <i> Info
Evidence:    <modules and boundaries inspected, dependency evidence read, legacy areas excluded by scope>
Findings:    <id> | Critical|Major|Minor|Info | <module or boundary> | <future cost it imposes> | <remediation direction> | <owner + reopen trigger when deferred>
Open risks:  <drift suspected beyond the visible slice, and the modules that would confirm it>
Next action: <single next step with its owner>
Revision:    <revision this packet judges>
```

### Clean pass

A pass that finds nothing returns the same fields with an empty finding set — never silence, never an absent packet, because clause 5 requires empty results to be stated explicitly:

```text
Outcome:     quality-review clean — 0 findings across <modules assessed>
Evidence:    <boundaries walked and the dependency evidence relied on, so the emptiness is attributable>
Findings:    (none)
Open risks:  <structure this pass could not see>, or "none"
Next action: none from this lens
Revision:    <revision reviewed>
```

A clean pass asserts the boundaries were assessed and hold. When there is no structural surface at all, the Skip Rule below applies instead and produces a skip record; `review/code-chief` carries a clean result and a skip differently into the package.

## REVISE Rounds

`check.py` groups a REVISE packet by evidence key and routes each group to that key's owner in `../../gates.yaml` `evidence_owners`. At `review-to-delivery` every key belongs to `code-chief` or `design-qa`, so no group is addressed to this lens directly: `code-chief` receives the group and sub-delegates the part this lens owns, under a `cycle_cap` of 2. `revise_policy.parallel_fix` is what lets that sub-delegation run alongside the other lenses rather than in sequence. A REVISE round is a delta pass, not a fresh assessment:

1. Re-assess only the modules and keys named in `changed_evidence` for this group, plus any boundary whose drift judgment depended on them. Unchanged evidence keeps its prior judgment, mirroring how the gatekeeper re-judges under `delta_review`.
2. Carry prior finding ids forward. A resolved item returns with status `verified` and the structural evidence that verifies it; an unresolved one returns under its original id and severity, never renumbered, and a Major that has since acquired an owner and reopen trigger returns as deferred rather than as resolved.
3. State the round in the `Revision` line as a delta, for example `r2 <- r1`.
4. Report drift that falls outside the round as a new item marked out-of-delta rather than widening the round silently — either outside `changed_evidence` entirely, or inside it by path but unrelated to the findings this round was opened for. Both are the same call: the round answers the questions it was opened with. `review/code-chief` decides whether it enters this cycle or the next.

At the cycle cap, an unresolved Critical or Major returns unchanged with its blocking status intact; the cap is never a reason to re-grade a finding downward.

## Required Contracts

- **Read-only over the reviewed surface**: This lens reports and never edits the modules, configuration, or documentation it assesses. `allowed-tools` withholds `Edit` so the posture is enforced rather than promised, and `Write` covers the packet and its evidence under the save path only. A refactor this lens can see is written into the finding as a remediation direction and routed through `review/code-chief` to the owning build skill; a structural change applied here would be the largest unreviewed edit in the run, made by the one lens with no one checking it.
- **Before/After Evidence**: This lens intervenes in nothing, so the contract is a baseline rule: the "before" is the boundary map built at step 1, which is what a later claim of reduced coupling is measured against. `references/workflow.md` states where in the sequence it is taken.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code

## Review Expectations

- Ground every quality finding in a concrete module, coupling pattern, or standards violation — not in subjective preference.
- Distinguish systemic architecture drift from isolated code-quality issues so remediation routes correctly.
- Prefer behavior-preserving simplification over aesthetic refactors: removing speculative abstractions, duplicate branches, or unused migration scaffolding is valuable only when the current behavior and rollback story are understood.
- Treat zombie code as a decision, not background noise: either assign ownership and tests, or require a deprecation/migration plan with usage evidence.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-analyzing the module graph.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no structural or maintainability surface to assess — a copy-only, comment-only, or single-constant change with no logic, dependency, abstraction, or design impact. A skip is recorded as a `_skip-record.md` carrying `pipeline`, `skipped_at`, `reason`, and `approved_by`, which `review/gatekeeper-code` validates; that is a different result from the clean pass above, which asserts the boundaries were assessed.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Architecture documentation is missing, incomplete, or clearly stale | Do not halt. Infer the current architecture from the code, module boundaries, and dependency graph, state each inference explicitly in the findings so a reader can challenge it, and record the documentation gap itself as a Minor — or a deferred Major with an owner when the missing document is what makes the drift unreviewable. |
| The scope only exposes a local slice of a broader dependency or ownership problem | State the visible architectural pressure, identify the hidden boundary, and avoid overstating a system-wide conclusion without the missing modules. |
| A cleanup suggestion conflicts with established platform conventions or shared abstractions | Flag the tension explicitly and recommend the narrowest change that improves maintainability without inventing a new platform direction. |
| A suspected debt hotspot is real but the package lacks evidence that it affects current delivery cost | Keep it as a Minor with the confidence gap stated, rather than inflating it to a Major the gate must then block on. |
| Multiple symptoms point to the same abstraction or layering flaw | Collapse them into one structural finding so the remediation plan targets the root cause rather than the surface manifestations. |
| The surface is assessed and nothing is found | Return the clean-pass packet above. An absent maintainability packet is indistinguishable from a lens that was never run. |
| A REVISE round arrives without `changed_evidence` | Request the key list from `review/code-chief` before re-assessing. Re-walking the whole module graph inside a capped cycle spends the round on boundaries nobody touched. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Name the lens packet `deliverable_quality-review.md`, the filename `review/gatekeeper-code` matches for the `lens_quality` slot. A packet under any other name leaves that slot empty and fails the mechanical pass for a lens that ran.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
