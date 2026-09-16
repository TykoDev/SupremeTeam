---
name: cross-check-build-confirm
description: >-
  Cross-checks the assembled build package for completeness and internal consistency,
  returning the `completeness-report`: a matrix binding every approved design decision
  to its changed artifact, test, and security evidence, each row proven or unproven.
  It answers what is still missing and decides nothing — whether the work advances is
  `build/gatekeeper-build`'s verdict, not this report. Internal build specialist
  reached through `build/build-management`, not directly, even when the request is
  only "did we finish everything?".
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Cross Check Build Confirm

## Purpose

The last read-only pass before the build package leaves the phase. It binds every approved decision to the artifact, test, and security evidence that carries it, marks each row proven or unproven against what is actually in the package, and hands every gap to `build/build-management`. It repairs nothing itself, and it decides nothing the gate decides.

## Use This Skill When

Use this skill to **prove the build package is whole** before it leaves the build phase:

- "confirm build completeness" / "verify the implementation is complete" — check every approved item is built and evidenced
- "cross-check the build package" — reconcile implementation, tests, runtime, and security evidence for internal consistency
- "prepare the build confirmation" — assemble the completeness matrix the gate will consume

Route elsewhere for the formal advance-or-revise decision (`build/gatekeeper-build`) or runtime, startup, and environment health (`build/health-check`).

## Entry Routing

Cross-check-build-confirm is an internal build specialist, not an entry point.
`../../routing-doctrine.md` places every `build/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. `../../pipelines.yaml` states the same thing from the other
side: `completeness-cross-check` is an unconditional stage of the `build`
pipeline owned by this skill. Run the active-handoff check before reading
anything, because the approved decision set, the package under review, and its
revision arrive with the handoff — and a completeness claim made against the
wrong revision is worse than no claim at all.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `build/build-management`
as the delegating owner for the build boundary.

- **Handoff present** → proceed; this is a delegated completeness pass.
- **Reached cold** → confirm nothing. Return to `build/build-management`, which
  owns package assembly and the approved scope this pass checks against, then
  accept the delegation back. Without the approved decision set there is no
  baseline, and a matrix with no baseline reports only that the package is
  consistent with itself.

## Inputs

- The assembled build package: implementation change set with hashes, test evidence, runtime evidence, security evidence, and package metadata.
- The approved design-phase artifacts the build claims to satisfy — decisions, delivery slices, and interface contracts — with the approved design revision.
- Prior completeness findings or gate outcomes when the package is being resubmitted, so unchanged rows are not re-litigated.

## Outputs

Everything below returns to `build/build-management`, the only skill
`../../gates.yaml` `boundaries.build-to-review` permits to submit that boundary.

- The `completeness-report` artifact `../../ownership.yaml` assigns to this skill, carrying its two evidence lines: promised scope versus delivered artifacts, and the unresolved gaps. Its core is the traceability matrix defined in `references/workflow.md`.
- That matrix is the input `build/build-management` authors its own `traceability` key from (`../../gates.yaml`, `evidence_owners.build-to-review`), which requires a design-decision-to-changed-artifact mapping with proven or unproven status stated per row.
- The gap list: every unproven row with its reason code, the evidence that would close it, and the specialist that owns producing it.

## Workflow

1. Establish the baseline before reading the package: the approved decision set, the approved design revision, and the delivery slices the build claims to satisfy. Without it the pass can only check the package against itself.
2. Build one matrix row per approved decision, binding each to its changed artifact, test evidence, and security evidence. The column schema, the status vocabulary, and the completeness threshold are in `references/workflow.md`.
3. Verify each binding against what is actually in the package — the path exists, its hash is registered, and its revision matches — rather than against the summary that claims it does.
4. Mark every row proven or unproven, attach a reason code to each unproven row, and record contradictions rather than reconciling them.
5. Return the completeness report and the gap list to `build/build-management`, routing each gap to the specialist that owns it. Nothing in the package is edited here.

## Required Contracts

Full normative text for each contract is in `references/contracts.md`; the lines
below are the operative rule, not a summary that softens it.

- **Read-only boundary**: This pass observes the package; it does not change it. `../../ownership.yaml` lists `implementation` under `does_not_write`, and the tool surface grants no edit capability. A gap discovered here is routed to `build/build-management`, which re-delegates it to the owning specialist. Repairing a gap in place would make the pass a reviewer of its own work, and the package would lose the one independent check it has before the gate.
- **Waived is present**: A cell holding a typed applicability record `{applicable: false, reason, scope, decided_by}` — whose `reason` carries the sanctioned wording from `../../gates.yaml` `fallback_values` — is evidence present. The row is proven by waiver, not blocked. The record is the waiver: a bare string carrying that same sanctioned wording is refused at schema 2, where `skills/harness/gatekeeper/check.py` fails the package with `bare fallback string not accepted at schema 2: <key> (use an applicability record)`. At `build-to-review` only `security_evidence` is waivable; the other five required keys carry no fallback, so nothing substitutes for them.
- **Binding, not claiming**: A row is proven only when the cited path exists in the package, its hash is registered, and its revision matches the package revision. A summary that asserts an artifact is attached is a claim about evidence, and the difference between the two is the entire value of this pass.
- **Contradictions stay visible**: When two artifacts disagree about a version, a scope, or an evidence lineage, record the disagreement and narrow the completeness statement. Choosing the more plausible of the two silently converts an open question into an unlogged decision.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically. Critical blocks; Major resolves before the gate or defers with an owner and a reopen trigger.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management` — delegating owner; supplies the baseline and the package, receives the completeness report and every gap, authors the `traceability` key from the matrix, and is the sole `build-to-review` submitter.
- `build/gatekeeper-build` — downstream gate; consumes the completeness report and owns the advance-or-revise decision this pass never makes.
- `build/bob-the-builder`, `build/test-builder`, `build/health-check`, `build/security-builder` — own the four evidence columns; each gap is routed to its owner through build-management rather than fixed here.

## Review Expectations

- Confirm completeness by cross-referencing the build artifacts against the design specification, not by summarizing intent.
- Call out every missing or inconsistent evidence element before the package reaches the build gate.
- Produce a traceability matrix the gatekeeper can audit without re-reading the full build output.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Invoked cold with no `### Save Context` block, no active run lock, and no named delegating owner | Confirm nothing. Return to `build/build-management` for the approved decision set, the package, and its revision, then accept the delegation back. A matrix built without a baseline reports only that the package agrees with itself. |
| `build/gatekeeper-build` returns a REVISE and the phase resubmits | Re-run the matrix, but re-judge only the rows whose bound artifacts changed; carry the prior status on unchanged rows, mirroring how the gate treats `changed_evidence` with `--prior` (`../../gates.yaml` `revise_policy.delta_review`). Mark each previously unproven row as closed or still open. `revise_policy.cycle_cap` is 2; a third cycle escalates to the build owner. |
| A hashing, diff, or manifest-reading tool needed to verify a binding is unavailable | Do not mark the row proven on the strength of the summary. Record which verification could not be performed and why, mark the row unproven with reason `unverifiable`, and return the tooling gap to `build/build-management`. An unchecked binding is not a checked one. |
| A required build artifact, test result, or security output is missing from the package | Mark the row unproven with reason `missing-artifact`, name the deliverable and its owner, and mark the package incomplete rather than inferring readiness. |
| An evidence cell holds a typed applicability record instead of an artifact | Treat the row as proven by waiver and record the waiver reference. Blocking a correctly waived package is a defect in this pass, not a strict reading. Verify the key is one `../../gates.yaml` actually sanctions as waivable at this boundary, and that the record's `reason` carries the sanctioned wording. |
| An evidence cell holds a bare fallback string rather than an applicability record | Mark the row `unproven` with reason `unsanctioned-waiver`, whatever the wording. At schema 2 `check.py` refuses the bare form outright, so the row is not waived and the package fails the machine as submitted. |
| Two build artifacts disagree about version, scope, or evidence lineage | Preserve the contradiction, mark the affected rows `unproven` with reason `contradicted`, and return a narrower completeness statement until the package is reconciled. |
| The build appears complete locally but lacks proof a downstream reviewer could consume | Treat the missing proof as a blocker and require explicit evidence for the gate-facing deliverable. |
| A gap could be closed here with a small edit to the package | Do not close it. Route it to `build/build-management` with the owning specialist named. The independence of this pass is the reason its verdict is worth anything, and one convenient edit ends it. |
| A remediation step would change the approved build scope rather than confirm it | Escalate the scope drift to the build owner instead of hiding it inside the completeness check. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Resolve every destination with `python skills/scripts/output_paths.py`, using the run id and
   phase from the Save Context block. Never compose a path by hand: the resolver refuses an
   unknown kind, a name that is absolute or traverses, and any path that escapes the
   project root, which is the containment check.
2. Write deliverables (reports, evidence bundles, review packets) to the destination it returns.
3. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
4. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the confirmation sequence, the traceability matrix schema, the status vocabulary, the completeness threshold, and resubmission handling.
- `references/contracts.md` for the full normative text of the read-only boundary, the waiver rule, and the binding rule.
- `references/examples.md` for worked completeness passes, including a rendered matrix and a correctly waived package.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
