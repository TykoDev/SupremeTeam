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

When persistence is active (Save Context received from admiral), the phase lead
writes only the classes `../../../save-ownership.yaml` grants it under
`skillset-saves/runs/{run-id}/review/`:

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --expect-revision <n> --set active_owner=code-chief --set phase_state=REVIEW_ACTIVE`) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
2. **After specialist returns**: verify the named artifact exists at its destination (for example `reports/report_bug-review.md` or `evidence/capture-1280-dark.png`), then checkpoint with `--evidence <path>` so its sha256 is registered.
3. **After gatekeeper-code verdict**: the gatekeeper has written `review/verdict_review-to-delivery.json`; record the semantic verdict and next action in the next checkpoint (`--set phase_state=REVIEW_GATE_PENDING`, `REVIEW_GATE_REVISE`, or the next active state). Never edit the verdict record.
4. **On package consolidation**: write `review/reports/review-package.md` and `review/manifest.json` (schema 2) summarizing all phase outcomes with hashes; admiral submits that manifest to `gatekeeper-admiral`.

### Save Context Block Template

Include the following block verbatim in every specialist delegation, populating each field from the current run state. It is the canonical field set from `../../../contracts/handoff-templates.md`; neither file may drop a field the other carries.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: review
- Save path: skillset-saves/runs/{run-id}/review/
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
- Return boundary: review-to-delivery
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
