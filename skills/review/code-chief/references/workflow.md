# Workflow Reference

## Contents

1. Intake triage
2. Lens scheduling rules
3. Consolidation checklist
4. Collaboration notes

## Intake Triage

1. Inventory the approved upstream artifacts, active diff or package revision, and the exact review boundary.
2. Mark the mandatory review lenses: `review/bug-review`, `review/code-review`, `review/quality-review`, `review/security-review`, and `review/mr-robot`.
3. Add `review/cso` when the surface includes security governance, accepted-risk decisions, release security posture, operating-model controls, regulated-data commitments, or explicit security-chief review language.
4. Add `review/frontier` and `review/design-qa` only when rendered UI, screenshots, or interaction evidence are present.
5. Add `review/devex-review` only when the surface includes onboarding, CLI, SDK, integration, or public tooling concerns.

## Lens Scheduling Rules

- Keep optional phases out of the run unless the supporting surface is actually in scope.
- Pass each specialist the same bounded scope, risk tier, and upstream artifact set so findings remain comparable.
- Require every specialist packet to preserve concrete evidence, blocking issues, and unresolved questions instead of flattening them into one summary.
- If two lenses disagree, preserve the conflict in the consolidated package and let `review/gatekeeper-code` decide whether the disagreement blocks advancement.

## Consolidation Checklist

- Every executed lens has a named report or a traceable packet.
- Every skipped optional lens has a written justification.
- `review/cso` is present or explicitly skipped when the package discusses security leadership signoff, accepted risk, release posture, or operating-model controls.
- Consolidated findings preserve contradictory evidence instead of averaging it away.
- Remediation guidance is grouped by blocking, major, and optional work.
- Gate submission includes the revision delta when the package is being resubmitted.

## Contract Notes

- Cross-model synthesis: Compare signals from multiple review lenses and merge them into one decision record without flattening meaningful disagreements.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Proactive triggers: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.

## Save Instructions Per Lens

When persistence is active (Save Context received from admiral):

1. **Before delegating** a specialist lens: create `lens-{N}_{skill}/_phase-state.md` with `state: ACTIVE`. Include a `### Save Context` block in the delegation prompt pointing to `skillset-saves/runs/{run-id}/review/lens-{N}_{skill}/`.
2. **After specialist returns**: verify the specialist wrote `report_{name}.md` to the save path.
3. **After gatekeeper-code verdict**: write `lens-{N}_{skill}/gatekeeper-verdict.md` with the full verdict. Update `_phase-state.md` to APPROVED, REVISING, or ESCALATED.
4. **On package consolidation**: write `review/review-package.md` and `review/delegation-log.md` summarizing all lens outcomes.

### Save Context Block Template

Include the following block verbatim in every specialist delegation, populating each field from the current run state:

```markdown
### Save Context
- **Run ID**: {run-id}
- **Save path**: skillset-saves/runs/{run-id}/review/lens-{N}_{skill}/
- **Persistence active**: {yes|no — copied from current run state}
- **Persistence probe result**: {ok|failed|skipped}
- **Context tier**: {1|2|3|4}
- **Artifact mode**: {inline|reference|best-effort-inline}
- **Standalone fallback ref**: {path or "none"}
- **Skipped upstream stages**: {none or list}
- **Session pin**: {true|false}
- **Execution mode**: {agent|skill}
```

When Save Context is absent or `Persistence active: no`, skip all save operations and return the deliverable inline.

## Collaboration Notes

- `review/bug-review` owns deterministic correctness defects and invariant failures.
- `review/code-review` owns merge readiness, local code quality, and reviewability.
- `review/quality-review` owns maintainability pressure, architecture drift, and technical debt.
- `review/security-review` owns defensive security posture, dependency exposure, and unsafe data handling.
- `review/mr-robot` owns adversarial abuse cases and exploit chaining.
- `review/cso` owns security leadership posture, accepted-risk candidates, compensating controls, and governance gaps.
- `review/frontier` owns frontend behavior, accessibility, and performance.
- `review/design-qa` owns visual hierarchy, token fidelity, and responsive polish.
- `review/devex-review` owns onboarding, tooling ergonomics, and integration friction.
- `review/gatekeeper-code` owns the final review-gate verdict.
- `session-memory` provides cross-session checkpoints when context pressure rises.
