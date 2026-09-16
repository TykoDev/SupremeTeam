# Code Chief Stub Contract

## Scope

Code chief owns the review pipeline from intake through consolidated gate submission and final review package delivery.

## Core Review Sequence

The stages `../../pipelines.yaml` declares without a condition. They run on every
review, though depth varies by scope.

1. `bug-review` — correctness
2. `code-review` — merge readiness
3. `quality-review` — maintainability
4. `code-chief` — finding triage, producing the `review-verdict`

## Conditional Review Sequence

Each stage below carries a condition in `../../pipelines.yaml` and runs only when
that condition holds. Security review and adversarial review are conditional, not
core: running them on a change with no trust boundary and no exploitable surface
adds noise rather than coverage.

- `security-review` — a trust boundary changed.
- `mr-robot` — an exploitable surface exists.
- `frontier` — visible behavior changed.
- `design-qa` — a visible surface changed; it produces `rendered_verification`.
- `devex-review` — a developer-facing surface changed: onboarding, CLI, SDK, or public integration.

Security leadership is not a conditional lens here. Accepted risk, release
security posture, operating-model controls, regulated commitments, and explicit
security-chief review language escalate to `admiral`, which opens the `security`
pipeline under `cso`, gated at `security-review`.

## Required Inputs

- Review target and scope statement
- Risk tier and detected technology stack
- Upstream design or build context when available

## Gate Contract

- Code chief owns the consolidated review submission at `review-to-delivery`.
- Core phases are always executed, though depth may vary by scope.
- Every conditional phase that did not run records the condition that was false in the execution manifest; every condition answered yes has its phase in the package.
- Required evidence: `review_verdict`, `findings`, `executed_probes`, `rendered_verification`, `residual_risk`, `revision_lineage`. Only `rendered_verification` is waivable, through `no visible surface changed - rendered verification not applicable` as the `reason` of an applicability record `{applicable: false, reason, scope, decided_by}`; at schema 2 the bare string is refused.
- Self-check before submitting: `python skills/harness/gatekeeper/check.py --boundary review-to-delivery --package review/manifest.json`, without `--verdict-out`.
- Maximum revisions per boundary: 2 (`gates.yaml` `revise_policy.cycle_cap`); a third cycle escalates to admiral instead of resubmitting.

## Package Shape

- Specialist reports for all executed phases
- Execution manifest with invoked phases and skip reasons
- Recorded escalation to `admiral` when security governance or accepted-risk claims are present, naming the `security` pipeline under `cso` as the owner of that judgment
- Consolidated risk summary and remediation priorities
- Final approval record from the review gate

## Downstream Expectations

- Delivery consumers can trace each major issue back to a named specialist report and evidence source.
