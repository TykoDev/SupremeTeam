---
name: build-management
description: >-
  Build sub-orchestrator that runs the pipeline from approved design inputs to
  a production-ready build package with implementation, tests, security
  posture, and completeness evidence. Use when asked to implement a design,
  start the build pipeline, build a project, or turn a specification into
  code. Delegates implementation to `build/bob-the-builder`, tests to
  `build/test-builder`, hardening to `build/security-builder`, completeness
  to `build/cross-check-build-confirm`, and gate validation to
  `build/gatekeeper-build`.
version: 1.0.0
---

# Build Management

## Purpose

Run the build pipeline from approved design inputs to a production-ready build package with implementation, tests, security posture, and completeness evidence.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the build boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- implement this design
- start the build pipeline
- build this project
- turn the specification into code

## Inputs

- Gate-approved design package with implementation specification, delivery slices, interface contracts, and acceptance evidence expectations.
- Active build save context, prior build-phase verdicts, and revision lineage when resuming an interrupted build run.
- Upstream decisions, design-gate conditions, or review findings that constrain implementation, testing, hardening, or completeness scope.

## Outputs

- Build package combining implemented slices, diff summary, test evidence, security hardening, health/completeness certification, and dependency notes.
- `build/gatekeeper-build` submission record with implementation revision, evidence timestamps, phase lineage, and unresolved blockers.
- Build escalation packet naming missing design input, environment blocker, vendored-surface decision, or validation gap.

## Workflow

1. Validate the implementation scope and identify any design gaps before code work starts.
2. Run implementation, testing, security hardening, and completeness confirmation as separate controlled phases.
3. Route findings back to the owning build specialist and re-run affected phases before the build package advances.
4. Publish one build package with enough evidence for review work to trust the code, tests, and remediation history.

## Required Contracts

- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every phase state transition, gatekeeper capture, and consolidated package to the save path. Include a `### Save Context` block in every specialist delegation. Saving is mandatory, not optional.

## Delegation Surface

- `build/bob-the-builder`
- `build/test-builder`
- `build/security-builder`
- `build/cross-check-build-confirm`
- `build/gatekeeper-build`

## Boundary Rules

- Record each boundary before requesting a verdict.
- Reuse prior verdicts only when the package revision is unchanged.
- Push remediation back to the owning sub-surface instead of editing its package locally.

## Skip Rule

Skip only when an upstream artifact is fully approved, structurally complete, and valid for the next boundary.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Implementation, test, security, or completeness artifacts point to different revisions of the build package | Treat the package as incoherent, require a single revision-aligned evidence set, and stop the handoff until the lineage is repaired. |
| A security remediation or late implementation fix changes the code surface after tests have already passed | Reopen the affected phases, rerun the necessary validation, and prevent the build packet from advancing on stale evidence. |
| Schedule pressure or a local workaround attempts to skip a mandatory build phase such as testing, security review, or completeness confirmation | Reject the shortcut and force the missing phase back into the pipeline before the package can claim readiness. |
| Generated, vendored, or third-party content appears in the build package without explicit ownership, scan notes, or change rationale | Isolate the non-first-party surface, require explicit treatment, and keep the package out of the review boundary until it is explained. |

## Save Protocol

When admiral delegates with `Persistence active: yes`, build-management is the phase lead
for `skillset-saves/runs/{run-id}/build/` and writes only the path classes
`../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`. Resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase build --kind <reports|artifacts|evidence|manifest> --name <file>`;
never compose a path by hand, and never create nested per-specialist directories
or phase-state files, because no declared class covers them and phase state lives
in the run record. When persistence is inactive or read-only resume is in effect,
build-management keeps the same phase sequencing but returns artifacts inline and
propagates `Persistence active: no` to specialists.

| Trigger | What Build-Management Writes |
|---------|----------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=build-management --set phase_state=BUILD_ACTIVE`) before the first specialist delegation |
| Specialist delegation | The canonical `### Save Context` block (below) naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `build-to-review` as `Return boundary` |
| Specialist return | Verify the named artifact exists at its destination, then register its sha256 through a `session-memory` checkpoint (`--evidence <path>`) |
| Gate submission | `build/manifest.json` (schema 2: `boundary: build-to-review`, `owner: build-management`), carrying `tests` and `runtime` as typed probe records whose hashed logs live under `build/evidence/`, and `security_evidence` as a findings record or its applicability record |
| Phase-gate verdict | Nothing: `build/gatekeeper-build` writes `build/verdict_build-to-review.json` through `check.py --verdict-out`; build-management records the semantic verdict in its next checkpoint |
| Package consolidation | `build/reports/build-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

Save Context block for specialist delegations (the canonical field set from
`../../contracts/handoff-templates.md`; neither file may drop a field the other
carries):

```markdown
### Save Context
- Run ID: {run-id}
- Phase: build
- Save path: skillset-saves/runs/{run-id}/build/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
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

When Save Context is absent or `Persistence active: no`, skip all save operations and return the deliverable inline.

## References

- `references/workflow.md` for the detailed phase-order, revision-loop, and package-assembly rules.
- `references/examples.md` for concrete build-pipeline outputs and handoff examples.
- `intake-brief.yaml` for the trigger set, input and output contract, and packaging expectations.
- `stub-contract.md` for the mandatory phase order, package shape, and downstream review expectations.
- `agent/agent-manifest.yaml` for agent-mode delegation capabilities and fallback behavior.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `intake-brief.yaml`, `stub-contract.md`, and `agent/agent-manifest.yaml` together. Keep generated reports and archives outside the skill directory.
