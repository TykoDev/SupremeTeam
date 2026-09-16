# Workflow Reference

The procedure for running a review pass: how intake triages a change into lenses, the rules that schedule them, how their findings consolidate into one verdict, and what each lens saves. Read this before scheduling the first lens, and again before consolidating.

## Contents

1. Intake triage
2. Lens scheduling rules
3. Consolidation checklist
4. Contract notes
5. Save instructions per lens, with the Save Context block template
6. Collaboration notes

## Intake Triage

1. Inventory the approved upstream artifacts, active diff or package revision, and the exact review boundary.
2. Mark the three unconditional lenses, which run on every review: `review/bug-review`, `review/code-review`, and `review/quality-review`. `../../../pipelines.yaml` attaches no condition to their stages.
3. Answer each stage condition the same file declares, and add the lens only where the answer is yes:
   - `review/security-review` — a trust boundary changed.
   - `review/mr-robot` — an exploitable surface exists.
   - `review/frontier` — visible behavior changed.
   - `review/design-qa` — a visible surface changed. `design-qa` is the producer of `rendered_verification`, so the trigger is the changed surface, never the presence of rendered evidence that only `design-qa` can create.
   - `review/devex-review` — a developer-facing surface changed: onboarding, CLI, SDK, integration, or public tooling.
   Record each no with its reason. A conditional lens run without its surface dilutes the package; a conditional lens skipped while its surface changed is a coverage gap the gate treats as a missing lens.
4. Escalate to `admiral` when the surface includes security governance, accepted-risk decisions, release security posture, operating-model controls, regulated-data commitments, or explicit security-chief review language. `../../../pipelines.yaml` puts those under the `security` pipeline owned by `cso` and gated at `security-review`; the review pipeline has no cso stage to add. This is separate from step 3: a trust-boundary change schedules `review/security-review` as a lens, while a governance judgment escalates and is never signed here.
5. Run `finding-triage` last: merge the lens reports into `review_verdict`, `findings`, and `residual_risk`, and state `revision_lineage` back to the approved upstream revisions.

## Lens Scheduling Rules

- Keep optional phases out of the run unless the supporting surface is actually in scope.
- Pass each specialist the same bounded scope, risk tier, and upstream artifact set so findings remain comparable.
- Require every specialist packet to preserve concrete evidence, blocking issues, and unresolved questions instead of flattening them into one summary.
- If two lenses disagree, preserve the conflict in the consolidated package and let `review/gatekeeper-code` decide whether the disagreement blocks advancement.

## Consolidation Checklist

- Every executed lens has a named report or a traceable packet.
- Every conditional lens that was not run records the condition that was false, and every condition answered yes has its lens in the package.
- An escalation to `admiral` is recorded when the package touches security leadership signoff, accepted risk, release posture, or operating-model controls, naming the `security` pipeline under `cso` as the owner of that judgment.
- Consolidated findings preserve contradictory evidence instead of averaging it away.
- Remediation guidance is grouped by blocking, major, and optional work.
- Gate submission includes the revision delta when the package is being resubmitted.

## Contract Notes

- Execution contract: the six canonical clauses are stated verbatim in `../SKILL.md` under "Execution Contract"; this reference restates none of them, because a second phrasing at a weaker strength is drift.
- Cross-model synthesis: Compare signals from multiple review lenses and merge them into one decision record without flattening meaningful disagreements.

## Save Instructions Per Lens

When persistence is active (Save Context received from admiral), the phase lead
writes only the classes `../../../save-ownership.yaml` grants it under
`skillset-saves/runs/{run-id}/review/`:

1. **Before delegating** a specialist: checkpoint through `session-memory` (`save_run.py checkpoint --run-id {run-id} --expect-revision <n> --owner code-chief --set phase_state=REVIEW_ACTIVE`; the active owner follows `--owner`, which `--set` refuses as a reserved field) and include the canonical `### Save Context` block naming the specialist as `Owner` and its `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`. Do not create per-specialist directories or phase-state files.
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
- Return boundary: review-to-delivery
```

When Save Context is absent or `Persistence active: no`, skip all save operations and return the deliverable inline.

## Collaboration Notes

- `review/bug-review` owns deterministic correctness defects and invariant failures.
- `review/code-review` owns merge readiness, local code quality, and reviewability.
- `review/quality-review` owns maintainability pressure, architecture drift, and technical debt.
- `review/security-review` owns defensive security posture, dependency exposure, and unsafe data handling, in the `security-review` stage conditioned on a changed trust boundary.
- `review/mr-robot` owns adversarial abuse cases and exploit chaining, in the `penetration-review` stage conditioned on an exploitable surface.
- `cso` owns security leadership posture, accepted-risk candidates, compensating controls, and governance gaps through the `security` pipeline, reached by escalating to `admiral` rather than by delegation from code-chief.
- `review/frontier` owns frontend behavior, accessibility, and performance.
- `review/design-qa` owns visual hierarchy, token fidelity, responsive polish, and the `rendered_verification` record code-chief carries to the gate.
- `review/devex-review` owns onboarding, tooling ergonomics, and integration friction.
- `review/gatekeeper-code` owns the final review-gate verdict.
- `session-memory` provides cross-session checkpoints when context pressure rises.
