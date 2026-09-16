# Workflow Reference

The phase-by-phase procedure for the `build` pipeline: how the approved design boundary sets the baseline, the order phases run in, the acceptance checks each must pass, and what each phase saves. Read this on accepting a `design-to-build` verdict, and at any phase boundary whose save path is not already resolved.

## Contents

1. Build-pipeline sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Save instructions per phase
6. Collaboration notes

## Build-Pipeline Sequence

1. Establish the approved design boundary, active scope, and revision baseline the build pipeline must honor. The baseline is the revision named in the `design-to-build` verdict, which becomes `approved_design_revision`.
2. Delegate implementation, the test surface, the security checkpoint when a trust boundary is in scope, and runtime health on every build, in the order `../../../pipelines.yaml` declares, reopening only the affected phase path when a later finding invalidates earlier evidence.
3. Route a mid-build failure by what is known about it: a reproduced failure with a known mechanism to `build/debugger`, an unknown mechanism to `investigate`. Investigation is gated at `investigation-review` and returns a bounded fix path; it does not become a second build, and an investigation that returns no bounded path stops the phase instead of licensing a guess.
4. Confirm completeness through `build/cross-check-build-confirm`, then assemble the consolidated build package only when code, tests, runtime health, security disposition, and completeness certification all align on the same revision.
5. Send the package to `build/gatekeeper-build` with revision history, residual risk, and any bounded exceptions made explicit.

## Decision Rules

- Prefer replay of the affected phase chain over patching contradictory evidence into the final package.
- Treat stale evidence as a blocker even when the latest code looks correct locally.
- Keep phase ownership clear: build-management routes and assembles, specialists author, gatekeeper-build validates.
- Escalate when a required build fix changes the approved design or release contract.

## Acceptance Checklist

- Design input and active scope are explicit, and `approved_design_revision` names the revision the `design-to-build` verdict approved.
- Mandatory build phases have current outputs for the submitted revision, including the `runtime-health` smoke log, which no test result substitutes for.
- Non-first-party surfaces are identified against the mechanical detection rule and justified with source, version, owner, and scan note.
- `traceability` walks every approved design decision to the changed artifact that carries it, with unproven rows stating why.
- `python skills/harness/gatekeeper/check.py --boundary build-to-review --package build/manifest.json` passes mechanically before submission.
- The package is coherent enough for downstream review consumers to trust directly.

## Contract Notes

The two contracts that bind this phase are stated in `../SKILL.md` § Required Contracts, with their full normative text in `contracts.md`; the six canonical execution-contract clauses are stated verbatim in `../SKILL.md` § Execution Contract. This reference restates neither, because a second phrasing at a weaker strength is drift.

## Save Instructions Per Phase

This is the single statement of the procedure; `../SKILL.md` carries only the
pointer and the two rules that decide path resolution. When persistence is active
(Save Context received from admiral), build-management is the phase lead for
`skillset-saves/runs/{run-id}/build/` and writes only the classes
`../../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`.

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --run-id {run-id} --owner build-management --expect-revision <n> --set phase_state=BUILD_ACTIVE`; the active owner follows `--owner`, which `--set` refuses as a reserved field) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `reports/report_implementation.md` or `evidence/tests.log`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-build verdict**: the gatekeeper has written `build/verdict_build-to-review.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=BUILD_GATE_PENDING`, `BUILD_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `build/reports/build-package.md` and `build/manifest.json` (schema 2) summarizing all phase outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

### Save Context Block Template

Include this block in every specialist delegation, populating each field from the
current run state. It is the canonical field set from
`../../../contracts/handoff-templates.md`; neither file may drop a field the
other carries.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: build
- Save path: skillset-saves/runs/{run-id}/build/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Preamble tier: {0|1|2|3} + rationale
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {specialist}
- Expected artifact: {reports/...|artifacts/...|evidence/...}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: build-to-review
```

When Save Context is absent or `Persistence active: no`, skip all save operations
and return the deliverable inline.

### Write Triggers

| Trigger | What Build-Management Writes |
|---------|------------------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` before the first specialist delegation |
| Specialist delegation | The delegation block above, naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `build-to-review` as `Return boundary` |
| Specialist return | Nothing new: the returned artifact is verified at its destination and its sha256 registered through a checkpoint (`--evidence <path>`) |
| Gate submission | `build/manifest.json` (schema 2: `boundary: build-to-review`, `owner: build-management`), carrying `tests` and `runtime` as typed probe records whose hashed logs live under `build/evidence/`, and `security_evidence` as a findings record or its applicability record |
| Phase-gate verdict | Nothing: `build/gatekeeper-build` writes `build/verdict_build-to-review.json` through `check.py --verdict-out`; build-management records the semantic verdict in its next checkpoint |
| Package consolidation | `build/reports/build-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

## Collaboration Notes

The stage owners this workflow delegates to are listed in `../SKILL.md` § Delegation Surface. What this workflow adds:

- `session-memory` provides cross-session checkpoints when context pressure rises.
