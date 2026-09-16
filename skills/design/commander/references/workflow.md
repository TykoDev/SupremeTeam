# Workflow Reference

The phase-by-phase procedure for the `design` pipeline: the order phases run in, the decision rules that move between them, the acceptance checks each must pass, and what each phase saves. Read this before delegating the first phase, and at any phase boundary where the next owner is in question.

## Contents

1. Design-pipeline sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Save instructions per phase
6. Collaboration notes

## Design-Pipeline Sequence

1. Establish the design entry conditions from the request, constraints, upstream approvals, and any saved stack-lock context.
   The stage order is research, architecture, interface and design-system work, the security seed when a trust boundary exists, the delivery plan, the implementation spec, and the stack lock.
2. Delegate only the earliest incomplete design phase, then wait for the corresponding gatekeeper-design verdict before advancing.
3. Reopen only the affected phase path when a verdict or drift invalidates downstream design work.
4. Assemble the consolidated design package only after all required phase outputs and approval records align on the same revision.

## Decision Rules

- Prefer replay from the earliest invalid boundary over patching contradictions inside the final package.
- Treat missing approval lineage as a structural blocker even when the content itself looks complete.
- Keep phase ownership clear: commander routes and assembles, specialists author, gatekeeper-design validates.
- Escalate user-facing scope decisions instead of silently skipping required phases.

## Acceptance Checklist

- Entry conditions and active constraints are explicit.
- Phase order matches `../../../pipelines.yaml` — architecture before the plan — and any justified skips are recorded.
- API endpoint contracts are present or explicitly skipped when endpoint surfaces are in scope.
- Frontend/UI Component Template and UI/UX Handoff evidence are present or explicitly skipped when user-facing surfaces are in scope.
- Every included artifact has matching approval lineage.
- The final package is coherent enough for build consumers to reuse directly.

## Contract Notes

The five contracts that bind this phase are stated in `../SKILL.md` § Required Contracts, with their full normative text in `contracts.md`; the six execution-contract clauses are stated verbatim in `../SKILL.md` § Execution Contract. This reference adds phase detail and restates neither in weaker words.

## Save Instructions Per Phase

This is the single statement of the procedure; `../SKILL.md` carries only the
pointer and the two rules that decide path resolution. When persistence is active
(Save Context received from admiral), commander is the phase lead for
`skillset-saves/runs/{run-id}/design/` and writes only the classes
`../../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`.

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --run-id {run-id} --owner commander --expect-revision <n> --set phase_state=DESIGN_ACTIVE`; the active owner follows `--owner`, which `--set` may not override) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `reports/report_research.md` or `artifacts/taste-snapshot.json`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-design verdict**: the gatekeeper has written `design/verdict_design-to-build.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=DESIGN_GATE_PENDING`, `DESIGN_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `design/reports/design-package.md` and `design/manifest.json` (schema 2) summarizing all phase outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

### Save Context Block Template

Include this block in every specialist delegation, populating each field from the
current run state. It is the canonical field set from
`../../../contracts/handoff-templates.md`; neither file may drop a field the
other carries.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: design
- Save path: skillset-saves/runs/{run-id}/design/
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
- Return boundary: design-to-build
```

When Save Context is absent or `Persistence active: no`, skip all save operations
and return the deliverable inline.

### Write Triggers

| Trigger | What Commander Writes |
|---------|----------------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` before the first specialist delegation |
| Specialist delegation | The delegation block above, naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `design-to-build` as `Return boundary` |
| Specialist return | Nothing new: the returned artifact is verified at its destination and its sha256 registered through a checkpoint (`--evidence <path>`) |
| Gate submission | `design/manifest.json` (schema 2: `boundary: design-to-build`, `owner: commander`), referencing the run's intake grilling log manifest-relative (`../intake/report_grilling.md` from the design phase directory) as `decisions`, the hashed architecture and plan reports, and the hashed `taste_snapshot` artifact or its applicability record |
| Phase-gate verdict | Nothing: `design/gatekeeper-design` writes `design/verdict_design-to-build.json` through `check.py --verdict-out`; commander records the semantic verdict in its next checkpoint |
| Package consolidation | `design/reports/design-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

## Collaboration Notes

Stage owners, in the order `../../../pipelines.yaml` declares for the design pipeline, are listed in `../SKILL.md` § Delegation Surface. What this workflow adds:

- `session-memory` provides cross-session checkpoints when context pressure rises.
