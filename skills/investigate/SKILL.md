---
name: investigate
description: >-
  Admiral-pipeline investigation sub-orchestrator for a failure whose mechanism
  is unknown: scopes and reproduces the symptom, builds an observed evidence
  chain, settles the mechanism, and returns one bounded fix path through
  `investigation-review` to the phase that owns the code. Use to investigate this
  issue, find the root cause, explain why this broke, trace the failure, or narrow
  a messy incident to one credible explanation — even when Admiral is never named.
  An already-reproduced failure with a known mechanism belongs to
  `build/debugger`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Investigate

## Purpose

Investigate explains; it does not fix. `../ownership.yaml` records
`implementation` among the artifacts it never writes, and that boundary is the
point of the pipeline: an investigation that starts editing loses the
independence that made its conclusion worth trusting, and hands the owning phase
a change nobody gated.

Two things are most often got wrong. Confidence outruns evidence, because an
inferred link is quietly counted as an observed one — the chain then reads as
complete while resting on a step nobody watched happen. And an unreproducible
failure is papered over: `reproduction` accepts no fallback at
`investigation-review`, so the honest output is `ESCALATE` with the gap stated in
`residual_uncertainty`, never a package with the key left out.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly frames this skill as the owning component for an Admiral boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- investigate this issue
- find the root cause
- explain why this broke
- trace the failure
- narrow a messy incident to one credible explanation

A reproduced build-phase failure with a known mechanism belongs to
`build/debugger`; this pipeline runs when the mechanism itself is unknown —
`unknown failure mechanism`, the exact wording `../pipelines.yaml` attaches to
the build pipeline's `investigation` stage, which is skipped whenever the
mechanism is already known. `build/debugger` no longer advertises "find the root
cause": an unexplained failure is scoped and reproduced here first.

## Inputs

- The incident, defect, or unexplained behavior in scope, the expected healthy behavior, and the phase that owns the affected code.
- Relevant logs, runtime observations, screenshots, traces, or configuration snapshots, plus the access needed to execute a reproduction.
- Known constraints such as protected environments, missing access, or evidence-retention limits.
- Active investigation save context, prior verdicts, and revision lineage when resuming.

## Outputs

- `investigation-package` at `investigation/reports/investigation-package.md`: scope, the reproduction, the evidence chain, the surviving mechanism with the hypotheses it displaced, the bounded fix path with its owning phase, and the residual uncertainty.
- `investigation/manifest.json` (schema 2, `boundary: investigation-review`, `owner: investigate`) carrying every evidence key `../gates.yaml` requires at `investigation-review`.
- Investigation escalation packet naming the missing evidence source, the access boundary, the owner, and what observation would change the conclusion.

## Execution Contract

Canonical source: `../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under
   the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier
   0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3
   for destructive, security-sensitive, production, or irreversible work. Record the tier and
   rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline
   ceremony and full security audits, but retains focused verification and applicable
   guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request
   uses different words; decline adjacent work and route end-to-end or specialist ownership
   explicitly. Offer a next safe action only after the current step, scope, and approval
   lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a
   gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate
   verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations
   inside the workspace, use read-only or dry-run probes first, and require explicit owner
   intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty
   results, and unavailable checks explicitly: preserve evidence, do not fabricate, return
   REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns
   a gate. A concise result without evidence is incomplete.

## Workflow

The stage list, owners, and artifacts below are the `investigation` pipeline as
`../pipelines.yaml` declares it. The prose elaborates those stages and never
contradicts them.

1. **scope-and-reproduction** (owner `investigate`, artifact `reproduction`). Fix the symptom boundary, the timing, and the known impact, then execute the failure rather than describing it. The artifact is the log that reproduces the reported failure together with its environment and inputs. Produces the `scope` and `reproduction` evidence keys. Checkpoint through `session-memory` before any further stage writes.
2. **evidence-chain** (owner `investigate`, artifact `evidence-chain`). Build the trace from symptom to mechanism, one observed link at a time, keeping raw observations separate from inference so a caller can challenge any weak link. An inferred link is labelled as inference and is not counted as a link. Produces the `evidence_chain` evidence key.
3. **mechanism** (owner `investigate`). Test competing explanations until one survives the evidence or the remaining ambiguity is explicit and bounded. `../pipelines.yaml` declares no artifact for this stage; the mechanism statement, the displaced hypotheses, and the confidence level are stated in the package. Produces the `mechanism` evidence key.
4. **bounded-fix-path** (owner `investigate`, artifact `fix-path`). Name the smallest change that addresses the mechanism and the phase that owns that change, with the acceptance signal that would confirm it. State what the conclusion still does not cover in the same pass. Produces the `fix_path` and `residual_uncertainty` evidence keys, and closes the `investigation-package` that carries scope and residual uncertainty per `../ownership.yaml`.
5. **return-to-owning-phase** (owner `admiral`). Investigate writes `investigation/manifest.json`, runs the self-check below, and submits at the `investigation-review` boundary; admiral routes the approved package back to the owning phase (DESIGN, BUILD, or REVIEW), which schedules the fix through its own pipeline. Investigate implements nothing here.

## Required Contracts

- **Observed over inferred**: Every link in the chain is an observation with its source, timestamp, and capture path. Inference is labelled and kept out of the link count, so the conclusion stays proportional to the evidence.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Bounded conclusion**: A surviving mechanism or an explicit suspect set, never a narrative that spans the gap. Missing access is reported as a boundary, not absorbed into confidence.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, persist every stage artifact to the save path through the classes below and checkpoint through `session-memory` at every stage boundary. Saving is mandatory, not optional.

Severity grading and proactive triggering are execution-contract clauses 3 and 2
above, stated there verbatim. They are not restated here, because a second
phrasing at a weaker strength is the drift the contract exists to prevent.

## Collaboration Surface

Investigate owns four of the five stages itself, so the surface is thin but real;
it is not empty. `references/workflow.md` — "Collaboration notes" — states what
each party owns.

- `admiral` owns the `return-to-owning-phase` stage: it normalizes the request on the way in and routes the approved bounded fix path back to the phase that owns the code on the way out.
- `session-memory` owns the run record; investigate never writes it directly.
- `gatekeeper-admiral`, reached through `admiral`, returns the verdict at `investigation-review`.
- The requesting phase lead — `build/build-management`, `design/commander`, or `review/code-chief` — receives the fix path for the change it owns.
- `build/debugger` is the adjacent owner: work that arrives with the mechanism already known routes there instead.

## Gate Submission

Investigate is the only submitter at the `investigation-review` boundary, which
guards the return from an investigation to the owning phase, and it owns all six
evidence keys itself. No other skill supplies any of them, so a gap here has no
other owner to route to and no REVISE packet to fan out.

Three decisions live here; `references/workflow.md` — "Boundary contract" and
"Stage-by-stage gate procedure" — carries the per-key table, what fills each key,
and the self-check command.

- **Which keys are hashed files**: `reproduction` and `evidence_chain` only. Each must reference a path present in the manifest's `artifact_hashes` map, so the evidence is a shipped, executed log rather than a bare claim. `scope`, `mechanism`, `fix_path`, and `residual_uncertainty` are stated in the package.
- **Which keys may be waived**: none. `../gates.yaml` lists no `fallback_values` at this boundary, and only a key listed there is waivable, so no applicability record substitutes for any of the six. An unreproducible failure is reported through `residual_uncertainty` and an `ESCALATE`, never by omitting `reproduction`.
- **What the submission is**: `investigation/manifest.json` at schema 2, declaring `boundary: investigation-review`, `owner: investigate`, the `run_id` when inside a run, and one `revision` value — self-checked with `check.py` before submission, so the gatekeeper spends judgment only on a package that already passes the machine.

## Boundary Rules

- Record the boundary before requesting a verdict, and name the revision the package carries.
- Reuse a prior verdict only when the boundary, submission, revision, package fingerprint, and gate spec digest are all unchanged.
- Treat a `REVISE` as one packet: address every failure in `revise_packet.by_owner` in one pass, then resubmit once with `--prior` so the gate re-judges only `changed_evidence`. `revise_policy.cycle_cap` is 2; a third cycle escalates instead of resubmitting.

## Skip Rule

Never skip the reproduction or the evidence chain: they are the two artifact-backed
keys, and a package without them cannot pass the boundary mechanically. Skip only
when the requested surface, tool, or environment does not exist and a safe fallback
is unavailable; record the decision and its decider rather than omitting the stage
silently.

## Failure Modes

These five change what Investigate does next. The competing-hypothesis,
provisional-mitigation, and fix-path-scope failures whose handling is procedural
rather than routing are in `references/failure-modes.md`, which repeats none of
these rows.

| Scenario | Response |
| --- | --- |
| The incident cannot be reproduced and key logs or traces have already aged out | Bound the uncertainty explicitly in `residual_uncertainty`, preserve the evidence that still exists, and request the next capture opportunity. `reproduction` accepts no fallback, so an unreproducible failure returns `ESCALATE` rather than a package missing its artifact. |
| Access limitations hide one critical evidence source, such as production logs or a managed-service metric stream | Escalate the missing evidence boundary, scope the conclusion to what can actually be observed, and name the observation that would close the gap. |
| The gate returns `REVISE` a second time, exhausting `../gates.yaml` `revise_policy.cycle_cap` of 2 | Stop resubmitting and escalate to the delegating orchestrator with both revise packets, both verdicts, and the unclosed keys named. There is no second owner to route to here, so a second failure on the same keys means the evidence does not reach the standard the boundary sets — which is a finding about the investigation, not a formatting defect to retry. |
| The request arrives without a symptom boundary, an expected healthy behavior, or the phase that owns the affected code; or a resume package carries an unparsable manifest or an evidence chain spanning two revisions | Execute no reproduction yet. Without the expected behavior there is no failure to define, and without an owning phase the fix path has no destination, so name the missing field and resolve it before the first stage writes. A resume whose manifest does not parse or whose links span revisions is rebuilt from the earliest provable observation rather than reused. |
| A required capability is unavailable: no command execution to run the reproduction, no access to the failing environment, or no Python for the gate self-check | Report the capability by name and scope the conclusion to what can actually be observed. A reproduction that could not be executed is not a `reproduction`: the key accepts no fallback, so the outcome is `ESCALATE` with the gap in `residual_uncertainty` and the observation that would close it. Without Python the self-check did not run, so the package is submitted as unverified rather than described as passing. |

## Save Protocol

See `references/workflow.md` — "Save instructions per stage" — for the full
write-trigger table, the path classes a phase lead may create, and the
`### Save Context` block carried on any delegation and echoed on return. Two
rules decide the rest: resolve every destination and filename with
`python skills/scripts/output_paths.py --run-id {run-id} --phase investigation --kind <reports|artifacts|evidence|manifest> --name <file>`
rather than composing a path, because nested per-specialist directories belong to
no class `../save-ownership.yaml` declares and phase state is published only
through `session-memory`; and when persistence is inactive or read-only resume is
in effect, keep the same stage sequencing and deliver artifacts inline.

## References

- `../pipelines.yaml` for the authoritative `investigation` stage list, stage owners, and artifacts.
- `../gates.yaml` for the `investigation-review` required evidence, artifact-backed keys, evidence owners, and the REVISE policy. It is the single source of truth; this skill's documents elaborate it and never restate a key list against it.
- `../ownership.yaml` for the artifact writers behind `reproduction`, `evidence-chain`, `fix-path`, and `investigation-package`.
- `../execution-contract.md` for the canonical clause source and the tier table.
- `references/failure-modes.md` for the competing-hypothesis, provisional-mitigation, fix-path-scope, and first-REVISE cases the SKILL.md table does not carry.
- `references/workflow.md` for the stage-by-stage gate procedure, the full boundary contract and per-key backing, the manifest self-check, and the save instructions with the `### Save Context` block.
- `references/examples.md` for concrete investigation examples.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the stage order, package shape, and the return into the owning phase.
- `agent/agent-manifest.yaml` for agent-mode capabilities and fallback behavior.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/failure-modes.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports, reproduction logs, and evidence under the run's `investigation/` directory, never inside the skill directory.
