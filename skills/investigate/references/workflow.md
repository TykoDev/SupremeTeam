# Workflow Reference

The stage-by-stage gate procedure for the `investigation` pipeline: what each
stage must produce, how it is hashed, what fills which evidence key, and what
blocks the `investigation-review` boundary. `SKILL.md` states the stage order and
the three decisions a caller needs; this file is the single full statement of the
boundary contract, the per-key backing, and the self-check, and neither `SKILL.md`
nor `stub-contract.md` repeats them.

## Contents

1. Boundary contract
2. Stage-by-stage gate procedure
3. Manifest assembly and self-check
4. REVISE handling
5. Decision rules
6. Acceptance checklist
7. Save instructions per stage, with the write triggers and the Save Context block
8. Collaboration notes

## Boundary Contract

`../../gates.yaml` `boundaries.investigation-review` guards the return from an
investigation to the owning phase (DESIGN, BUILD, or REVIEW). `investigate` is the
submitter and, per `evidence_owners.investigation-review`, the owner of all six
required keys. The boundary lists no `fallback_values`, so no key here is
waivable: a key without evidence is a missing key, not a waived one.

| Evidence key | Stage | Backing |
| --- | --- | --- |
| `scope` | scope-and-reproduction | Stated in the package: the symptom boundary, the affected surface, the owning phase, and what is excluded. |
| `reproduction` | scope-and-reproduction | Artifact-backed typed `probe` record: the executed log that reproduces the reported failure, with environment and inputs, hashed into `artifact_hashes`. |
| `evidence_chain` | evidence-chain | Artifact-backed typed `probe` record: the trace from symptom to mechanism, each link observed, hashed into `artifact_hashes`. |
| `mechanism` | mechanism | Stated in the package: the surviving explanation, the hypotheses it displaced, and the confidence level. |
| `fix_path` | bounded-fix-path | Stated in the package: the smallest change that addresses the mechanism, the phase that owns it, and the acceptance signal that would confirm it. |
| `residual_uncertainty` | bounded-fix-path | Stated in the package: what the conclusion does not cover, and the observation that would change it. |

Both artifact-backed keys are typed `probe` records under
`evidence_types`/`evidence_type_rules`: a record with hashed artifacts and
`result.status: pass`, where the executed log is the artifact. At this boundary
`reproduction` is the log that reproduces the reported failure and `evidence_chain`
is the trace from symptom to mechanism.

## Stage-By-Stage Gate Procedure

**1. scope-and-reproduction** (artifact `reproduction`; fills `scope`, `reproduction`).

Fix the symptom boundary, the timing, the impact, and the phase that owns the
affected code, and state what the investigation excludes — that statement is
`scope`. Then execute the failure. Resolve the destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase investigation --kind evidence --name reproduction.log`,
write the executed log there, and register its sha256 through a `session-memory`
checkpoint (`--evidence <path>`). The record names the environment and the inputs
that produced the failure. A described reproduction that was never run does not
satisfy this key; an unreproducible failure is reported through
`residual_uncertainty` and an `ESCALATE`, because the key accepts no fallback.

**2. evidence-chain** (artifact `evidence-chain`; fills `evidence_chain`).

Build the trace from symptom to mechanism, one link at a time, each link naming
its source, its timestamp, and the capture it came from. Inference is labelled as
inference and does not count as a link. Write the trace to the destination
`output_paths.py --kind evidence --name evidence-chain.log` resolves and register
its sha256 the same way. A chain with an unobserved link is the weak point a
caller is entitled to challenge, so the link stays visible rather than being
smoothed over.

**3. mechanism** (no artifact declared; fills `mechanism`).

Test the competing explanations against the chain until one survives or the
remaining ambiguity is explicit and bounded. State the surviving mechanism, the
hypotheses it displaced and why, and the confidence level. `../../pipelines.yaml`
declares no artifact for this stage, so the value lives in the package rather than
in a hashed file; it must still be specific enough that the owning phase can act
on it. A mechanism that only restates the symptom blocks the boundary in judgment
even when the mechanical pass succeeds.

**4. bounded-fix-path** (artifact `fix-path`; fills `fix_path`, `residual_uncertainty`).

Name the smallest change that addresses the mechanism, the phase that owns that
change, and the acceptance signal that would confirm it. In the same pass, state
what the conclusion does not cover and the observation that would change it —
that is `residual_uncertainty`, and it is required, not optional. Write the
package to the destination `output_paths.py --kind reports --name investigation-package.md`
resolves; it is the `investigation-package` artifact `../../ownership.yaml` assigns
to `investigate`, carrying scope and residual uncertainty alongside the
reproduction and evidence-chain paths.

**5. return-to-owning-phase** (owner `admiral`).

Submit, then hand off. `admiral` routes the approved package back to the phase
that owns the code, which schedules the fix through its own pipeline. Investigate
implements nothing at this stage: `../../ownership.yaml` records `implementation`
among the artifacts it never writes.

## Manifest Assembly And Self-Check

Resolve the manifest destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase investigation --kind manifest`,
never by composing the path by hand. The manifest is schema 2: it declares
`boundary: investigation-review`, `owner: investigate`, the `run_id` when inside a
run, one `revision` value, the `artifact_hashes` map, and the six evidence keys.
Artifact paths are manifest-relative and resolve inside the run directory, so
sibling phase evidence is admissible when the manifest's `run_id` matches the
directory and `_state.md`.

Self-check before submitting, per `../../gates.yaml` `revise_policy.self_check`:

```bash
python skills/harness/gatekeeper/check.py --boundary investigation-review --package <manifest.json>
```

Run it without `--verdict-out`. Every mechanical failure is fixed before
submission, so the gatekeeper spends judgment only on a package that already
passes the machine.

## REVISE Handling

A `REVISE` arrives as one packet carrying every mechanical failure and every
judgment finding from the pass, grouped by evidence key and owner in
`revise_packet.by_owner`. All six keys have the same owner here, so the whole
packet is resolved in a single pass rather than routed. Repair the failing keys,
re-hash any changed artifact, and resubmit once with `--prior <verdict.json>` so
`changed_evidence` names what to re-judge and the gatekeeper carries its prior
judgment on `unchanged_evidence`. `revise_policy.cycle_cap` is 2; a third cycle
escalates instead of resubmitting.

## Decision Rules

- Prefer the simplest theory that explains all surviving evidence, not the first theory that explains part of it.
- Keep mitigations distinct from confirmed mechanisms: a symptom that disappears is not a mechanism that was proven.
- Preserve contradictory evidence instead of smoothing it away; the contradiction is what bounds the conclusion.
- Escalate when a missing data source prevents a confident causal claim, and name the observation that would close the gap.
- Keep the fix path the smallest change that addresses the mechanism, and hand it to the phase that owns the code.

## Acceptance Checklist

- The symptom timeline, the affected surface, and the owning phase are explicit.
- The reproduction was executed and its log is hashed into the manifest.
- The evidence chain is hashed, and every link is observed or labelled as inference.
- Facts and hypotheses are separated, and the displaced hypotheses are named.
- The conclusion is proportional to the evidence, and residual uncertainty names what would change it.
- The fix path names one change and one owning phase.
- `check.py --boundary investigation-review` passes mechanically before submission.

## Save Instructions Per Stage

This is the single statement of the procedure; `../SKILL.md` carries only the
pointer and the two rules that decide path resolution.

When the delegating orchestrator sends a Save Context block with
`Persistence active: yes`, investigate is the phase lead for
`skillset-saves/runs/{run-id}/investigation/` and writes only the path classes
`../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`. Resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase investigation --kind <reports|artifacts|evidence|manifest> --name <file>`;
never compose a path or a filename by hand, and never create nested
per-specialist directories, because no declared class covers them. Phase state is
published only through `session-memory` (`save_run.py`), so investigate creates no
state file of its own. When persistence is inactive or read-only resume is in
effect, investigate keeps the same stage sequencing but returns artifacts inline.

| Trigger | What Investigate Writes |
|---------|-------------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` (`save_run.py checkpoint --run-id {run-id} --expect-revision <n> --owner investigate --set phase_state=INVESTIGATION_ACTIVE`; the active owner follows `--owner`, which `--set` refuses as a reserved field) before the first stage artifact |
| Reproduction | The executed log at the destination `output_paths.py --kind evidence` resolves, registered by sha256 through a `session-memory` checkpoint (`--evidence <path>`) |
| Evidence chain | The symptom-to-mechanism trace at the destination `output_paths.py --kind evidence` resolves, registered the same way |
| Package assembly | The report at the destination `output_paths.py --kind reports --name investigation-package.md` resolves |
| Gate submission | `investigation/manifest.json` (schema 2: `boundary: investigation-review`, `owner: investigate`) at the destination `output_paths.py --kind manifest` resolves, carrying the hashed reproduction and evidence chain plus the scope, mechanism, fix-path, and residual-uncertainty values |
| Gate verdict | Nothing: the gatekeeper writes `investigation/verdict_investigation-review.json` through `check.py --verdict-out`; investigate records the semantic verdict in its next checkpoint |

Save Context block carried on any delegation and echoed on return (the canonical
field set from `../../contracts/handoff-templates.md`; neither file may drop a field
the other carries):

```markdown
### Save Context
- Run ID: {run-id}
- Phase: investigation
- Save path: skillset-saves/runs/{run-id}/investigation/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Preamble tier: {0|1|2|3} + rationale
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: investigate
- Expected artifact: {reports/...|artifacts/...|evidence/...}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: investigation-review
```

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## Collaboration Notes

- `admiral` owns the `return-to-owning-phase` stage, normalizes the request on entry, and carries the approved package through `gatekeeper-admiral`.
- `session-memory` owns the run record; phase state and evidence hashes are published only through `save_run.py`, never by a file this skill writes.
- `build/build-management` delegates the build pipeline's `investigation` stage when the failure mechanism is unknown; `design/commander` and `review/code-chief` make the same request from their phases.
- `build/debugger` owns an already-reproduced build-phase failure with a known mechanism; work that arrives in that shape routes there instead.
