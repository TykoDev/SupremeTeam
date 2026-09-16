# Workflow Reference

## Contents

1. Design-pipeline sequence
2. Decision rules
3. Acceptance checklist
4. Collaboration notes

## Design-Pipeline Sequence

1. Establish the design entry conditions from the request, constraints, upstream approvals, and any saved stack-lock context.
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
- Phase order and any justified skips are recorded.
- API endpoint contracts are present or explicitly skipped when endpoint surfaces are in scope.
- Frontend/UI Component Template and UI/UX Handoff evidence are present or explicitly skipped when user-facing surfaces are in scope.
- Every included artifact has matching approval lineage.
- The final package is coherent enough for build consumers to reuse directly.

## Contract Notes

- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.

## Save Instructions Per Phase

When persistence is active (Save Context received from admiral), the phase lead
writes only the classes `../../../save-ownership.yaml` grants it under
`skillset-saves/runs/{run-id}/design/`:

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=commander --set phase_state=DESIGN_ACTIVE`) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `reports/report_research.md` or `artifacts/taste-snapshot.json`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-design verdict**: the gatekeeper has written `design/verdict_design-to-build.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=DESIGN_GATE_PENDING`, `DESIGN_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `design/reports/design-package.md` and `design/manifest.json` (schema 2) summarizing all phase outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

## Collaboration Notes

- `design/researcher` owns requirements and domain grounding.
- `design/planner` owns milestone and rollout sequencing.
- `design/architect` owns system boundaries, interface contracts, and the frontend/UI visual design system (shadcn/ui tokens, components, preview, and spec) where applicable.
- `design/engineer` owns implementation slicing and delivery constraints.
- `design/gatekeeper-design` owns design-phase validation and resubmission verdicts.
- `session-memory` provides cross-session checkpoints when context pressure rises.
