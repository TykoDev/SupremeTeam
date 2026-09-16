---
name: design-qa
description: >-
  Assesses visual hierarchy, token adherence, spacing and typographic rhythm, and
  static visual fidelity in an interface's rendered captures. Use when the user asks
  to review the visual quality, audit the design implementation, check the interface
  polish, or validate the visual system — even when they only say a screen "looks
  off". Judges what a still capture shows; anything that must be resized, exercised,
  or measured goes to `review/frontier`, ergonomics to `review/devex-review`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Design QA

## Purpose

Answers whether the captured interface matches the design that was approved. The approved snapshot and its digest are the baseline, so a deviation is measured against that frozen record rather than against current preference state or the reviewer's eye — and the captures themselves become the evidence a later reader can re-check.

## Entry Routing

Design-QA is an internal review lens, not an entry point. `../../routing-doctrine.md` places every `review/` skill it does not name separately in the internal-specialist row, reached only through the owning sub-orchestrator — `review/code-chief` in the `review` pipeline, and `design/redesign` in the redesign pipeline. Run the active-handoff check before comparing anything: the approved design package, the snapshot digest that fixes the baseline, and the screens in scope arrive with the handoff and nowhere else.

A handoff is present when the delegation prompt carries a `### Save Context` block, an active run lock with `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names `review/code-chief` (or `design/redesign` at `redesign-review`) as the delegating owner for the boundary.

- **Handoff present** → proceed; this is a delegated lens assignment.
- **Reached cold** → return to the owning orchestrator and accept the delegation back. Without the approved package there is no digest to bind the review to, and a fidelity judgment against an unpinned baseline is taste, not verification.

## Use This Skill When

Use this lens for **static visual fidelity** — whether the rendered captures match the design system and read cleanly:

- "review the visual quality" / "check the interface polish" — judge hierarchy, spacing, typography, and finish in what was captured
- "audit the design implementation" — verify token adherence against the approved spec
- "validate the visual system" — confirm the implemented UI honors the design system it was signed off against

Route elsewhere when the concern is responsive behavior, accessibility, or runtime performance (`review/frontier`) or developer-facing onboarding and tooling (`review/devex-review`).

## Inputs

- Rendered interface screenshots or live surface plus the design-token system the implementation should follow.
- Visual hierarchy spec, layout targets per tier, and finish expectations from the design package.
- Prior design-qa findings or design-review scorecards when the surface is being re-evaluated.
- Design-review priorities such as target breakpoints, brand-token exceptions, finish expectations, or excluded screens.
- The immutable `taste_snapshot` artifact approved at `design-to-build`, its canonical digest, and preference-to-artifact traceability rows.
- For the redesign pipeline: each variant's `app.html` and `tokens.css` plus the baseline captures from `design/design-mapper`, to render every route and declared state at the six tiers in both themes per variant as the `rendered_verification` record at `redesign-review` (`../../design-doctrine.md` §9), bound by sha256 to the prototype files.
- On a REVISE round, the `changed_evidence` key list from the gate packet and the prior packet's finding ids.

## Outputs

- Visual-quality assessment covering hierarchy adherence, token compliance, layout fidelity at each captured tier, and finish.
- Finding list with each design issue tied to a specific component, capture, or token violation.
- Design-QA lens packet for `review/code-chief` with capture anchors, token/tier evidence, and any skipped surfaces.

### Gate evidence owned at `review-to-delivery` and `redesign-review`

`../../gates.yaml` `evidence_owners` assigns `rendered_verification` to design-qa at both boundaries, and it is the only `review-to-delivery` key this lens owns. `code-chief` submits the review boundary and `redesign` the redesign boundary; design-qa authors this key and hands it over unchanged.

| Key | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- |
| `rendered_verification` at `review-to-delivery` | The `rendered-verification` artifact `../../ownership.yaml` assigns to design-qa: captures across the declared breakpoints and themes for the changed surface, with the inputs bound to the rendered source | Yes. `artifact_evidence` at this boundary names this key, so its value references paths recorded in the manifest `artifact_hashes` map | `render`: hashed captures with `breakpoints`, `themes`, `inputs` bound to the rendered source, and `result.status` pass — or `inferred`, which requires a limitation statement and the label `INFERRED - no browser available`. Breakpoints cover the responsive tiers `../../design-doctrine.md` §4 requires for the changed surface | `no visible surface changed - rendered verification not applicable`, used only when no visible surface changed — never to paper over a visual-qa stage that was skipped while one did. At `schema_version: 2` that wording is never the key's value: `check.py` refuses a bare fallback string and accepts only the applicability record `{applicable: false, reason, scope, decided_by}`, with the sanctioned wording carried as `reason` |
| `rendered_verification` at `redesign-review` | The same record, per variant: every route and declared state rendered at all six tiers in both themes, bound by sha256 to that variant's `app.html` and `tokens.css` | Yes, on the same rule | Same `render` record, produced once per variant | None. `../../gates.yaml` lists this key under `no_fallback` at this boundary, so neither the fallback string nor an applicability record is accepted |

The packet itself is saved as `deliverable_design-qa.md` beside the captures; the captures are the hashed evidence, and the packet is the reading of them.

## Workflow

1. Verify the supplied snapshot digest matches the digest recorded in the approved design package, then compare the rendered screens against the intended visual hierarchy, token usage, spacing rhythm, typography, layout composition, and finish. Never resolve against mutable current project or global Taste state.
2. Inspect alignment, contrast, component composition, and per-tier layout using screenshots, recordings, or rendered UI evidence.
3. Separate fidelity breaks from intentional product tradeoffs, then explain which screen, state, or tier is affected and why the deviation weakens the design system.
4. Deliver a visual QA packet to `review/code-chief` with evidence anchors, affected states, and any runtime-behavior handoff needed from `review/frontier`.

## Packet Shape

Every pass returns the same fields in this order, so `review/code-chief` merges lenses instead of reformatting them (`../../execution-contract.md`, clause 6; this lens owns no gate, so it returns no verdict):

```text
Outcome:     design-qa, <revision reviewed>, digest <snapshot digest>, <n> findings: <c> Critical, <m> Major, <k> Minor, <i> Info
Evidence:    <capture paths, tiers and themes covered, screens or states not captured>
Findings:    <id> | Critical|Major|Minor|Info | <screen / state / tier> | <design-system rule broken> | <correction>
Open risks:  <deviations suspected where no capture exists, and the capture that would settle each>
Next action: <single next step with its owner>
Revision:    <revision this packet judges>
```

Grade findings `Critical | Major | Minor | Info` and nothing else (`../../execution-contract.md`, clause 3). "Visual regression" and "polish" describe the kind of deviation, not its severity; each still takes one of the four grades.

### Clean pass

A pass that finds nothing returns the same fields with an empty finding set — never silence, never an absent packet, because clause 5 requires empty results to be stated explicitly:

```text
Outcome:     design-qa clean — 0 findings across <screens> at <tiers> in <themes>
Evidence:    <capture paths and the digest they were judged against>
Findings:    (none)
Open risks:  <states or tiers not captured>, or "none"
Next action: none from this lens
Revision:    <revision reviewed>
```

A clean pass still produces the `rendered_verification` record: the captures are owed to the gate whether or not they reveal a deviation. When no visible surface changed at all, the Skip Rule below applies and the sanctioned fallback value carries the key instead.

## REVISE Rounds

`../../gates.yaml` `revise_policy.parallel_fix` delegates the design-qa group of a REVISE packet straight to this lens, in parallel with the other owners, under a `cycle_cap` of 2. A REVISE round is a delta pass, not a fresh review:

1. Re-capture and re-judge only the screens, states, and tiers named in `changed_evidence` for this group, plus any view whose layout depends on them. Unchanged captures keep their prior judgment, mirroring how the gatekeeper re-judges under `delta_review`.
2. Re-hash every capture that was re-taken and update the `rendered_verification` record accordingly, because a stale hash fails the artifact-backing check even when the image looks right.
3. Carry prior finding ids forward. A corrected deviation returns with status `verified` and the new capture that verifies it; an uncorrected one returns under its original id and severity, never renumbered.
4. State the round in the `Revision` line as a delta, for example `r2 <- r1`, and keep the baseline digest from round one: a REVISE round re-checks the implementation, never the approved design.

At the cycle cap, an unresolved Critical or Major returns unchanged with its blocking status intact; the cap never justifies accepting a fidelity break.

## Required Contracts

- **Read-only over the reviewed surface**: This lens reports and never edits the components, stylesheets, tokens, or templates it reviews. `allowed-tools` withholds `Edit` so the posture is enforced rather than promised, and `Write` covers the packet, the captures, and the `rendered_verification` record under the save path only. A spacing or token correction this lens can see is written into the finding and routed through `review/code-chief` to the owning build or design skill; changing the surface here would invalidate the very captures the gate hashes as proof of what was reviewed.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.
- **Digest-bound Taste conformance**: Fill the design traceability rows with rendered-verification evidence for each applicable effective preference id and judge conformance only against the exact design-time snapshot digest. Later Taste changes are drift/candidates, not silent review criteria.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code
- review/frontier
- `design/redesign`, which owns the `redesign` pipeline, delegates the `visual-qa` stage once per variant, and submits the package at `redesign-review`

## Review Expectations

- Anchor every visual finding to a capture, token value, or rendered measurement — not to subjective impression.
- Separate design-system violations from finish issues so remediation routes accurately.
- Hand anything that requires exercising the interface — reflow while resizing, focus order, motion under interaction — to `review/frontier`; this lens judges what a still capture can show.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-rendering the surface.

## Skip Rule

Skip only when the surface required by the review lens does not exist — for this visual lens that means a rendered interface, screenshots, or equivalent visual evidence must be absent for the skip to apply. A skip is recorded as a `_skip-record.md` carrying `pipeline`, `skipped_at`, `reason`, and `approved_by`, which `review/gatekeeper-code` validates, and at `review-to-delivery` the key `rendered_verification` carries its sanctioned fallback value alongside it. At `redesign-review` no fallback exists, so a missing capture set is a gate failure rather than a skip.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The design system, token set, or reference mocks have not been shared | Halt the fidelity assessment, name the missing design source, and request the relevant design system docs or mock exports before continuing. |
| The package lacks design mocks, token references, or rendered screenshots for the claimed surface | Limit the review to the visible evidence, state the missing design source, and avoid inventing the intended visual target. |
| The captures do not cover the tier or state where the deviation is suspected | Mark the finding as partial, name the missing tier or state, and request the additional capture before broadening the claim. |
| No browser or renderer is available to produce captures | Record `result.status` as `inferred`, label the record `INFERRED - no browser available`, and state the limitation on the record itself. An inferred record is a declared gap, never a substitute for a capture. |
| A deviation may be intentional product direction rather than a design-system miss | Ask for the governing design decision or note the ambiguity instead of treating every difference as a defect. |
| Current Taste state differs from the approved snapshot | Preserve the design-time digest as the review baseline and report the difference as drift; replay only on explicit user request. A revoked used preference requires a user decision. |
| Every captured screen matches the approved design | Return the clean-pass packet above with the `rendered_verification` record attached. The captures are owed to the gate whether or not they show a deviation. |
| A REVISE round arrives without `changed_evidence` | Request the key list from the delegating orchestrator before re-capturing. Re-rendering every screen inside a capped cycle spends the round on views nobody changed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block. Captures and the `rendered_verification` record are evidence, so they land under the phase's `evidence/` directory and are hashed into the manifest.
2. Name the lens packet `deliverable_design-qa.md`. This lens fills no lens slot in `review/gatekeeper-code`'s `scripts/check.py` — its gate evidence is the hashed capture set, not a filename match — so the packet name exists for the reader, and the captures carry the gate.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
