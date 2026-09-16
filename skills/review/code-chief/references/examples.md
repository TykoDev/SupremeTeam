# Example Invocations

Each example answers the five stage conditions `../../../pipelines.yaml`
attaches to the review pipeline, then shows which lenses that produced. The three
unconditional lenses — `review/bug-review`, `review/code-review`,
`review/quality-review` — run in all of them and are not re-argued per example.

## Contents

1. Payments API before merge
2. Admin dashboard release
3. Public CLI and SDK
4. Browserless host with a changed visible surface

## Example 1 — Payments API before merge

**User request:** run the full review flow for the payments API before merge

**Output:**
- Conditions: trust boundary changed — yes (auth and database writes); exploitable surface — yes (an unauthenticated retry endpoint); visible behavior changed — no; visible surface changed — no; developer-facing surface changed — no.
- Lenses run: the three unconditional lenses plus `review/security-review` and `review/mr-robot`.
- Lenses not run: `review/frontier`, `review/design-qa`, and `review/devex-review`, each recording the condition that was false rather than a generic skip note.
- `rendered_verification`: the sanctioned fallback `no visible surface changed - rendered verification not applicable`, carried as an applicability record with reason, scope, and decided_by.
- Security governance: none raised, because no accepted-risk, release-governance, or operating-model claim is in scope. A trust-boundary change schedules a lens; it is not by itself a governance judgment.
- Delivery: findings grouped into blocking defects, security follow-ups, and merge-readiness fixes, with `executed_probes` hashed and `revision_lineage` stated as `r1 <- build r1 <- design r1` before `review/gatekeeper-code` submission.

## Example 2 — Admin dashboard release

**User request:** review this codebase comprehensively for the admin dashboard release

**Output:**
- Conditions: trust boundary changed — yes (a new session scope); exploitable surface — no, so `review/mr-robot` does not run and the condition is recorded as false; visible behavior changed — yes; visible surface changed — yes (a design-token rollout); developer-facing surface changed — no.
- Lenses run: the three unconditional lenses plus `review/security-review`, `review/frontier`, and `review/design-qa`.
- `rendered_verification`: the `render` record `design-qa` returns, `result.status: pass`, hashed captures across the declared responsive tiers in both themes, inputs bound to the rendered source. Code-chief carries it unchanged; it authors none of it.
- Security governance: release security posture is in scope, so it escalates to `admiral` to open the `security` pipeline under `review/cso`, gated at `security-review`, and is recorded in the package as an open governance question rather than signed here.
- Consolidation rule: a disagreement between the code, security, and visual findings is preserved as a conflict for `review/gatekeeper-code` to judge, never averaged into one severity.

## Example 3 — Public CLI and SDK

**User request:** audit this change before merge for the public CLI and SDK

**Output:**
- Conditions: trust boundary changed — no; exploitable surface — no; visible behavior changed — no; visible surface changed — no; developer-facing surface changed — yes (setup docs, integration snippets, and a new SDK entry point).
- Lenses run: the three unconditional lenses plus `review/devex-review`. `review/security-review` and `review/mr-robot` do not run, and each records its false condition — an SDK release is not automatically a trust-boundary change.
- Gate intent: the execution manifest carries one line per unrun conditional lens naming the condition, and the submission includes the revision delta because this is a resubmission.
- Delivery: onboarding friction findings, merge blockers, `residual_risk` naming what stayed unproven and who carries it, and the exact items `review/gatekeeper-code` must validate.

## Example 4 — Browserless host with a changed visible surface

**User request:** pressure-test this project (a settings redesign, reviewed on a CI host with no browser)

**Output:**
- Conditions: visible surface changed — yes, so `review/design-qa` is scheduled; the host cannot render it.
- `rendered_verification`: the record `design-qa` returns with `result.status: inferred`, its limitation statement, and the label `INFERRED - no browser available` that `../../../gates.yaml` `evidence_type_rules.render` requires.
- What is not done: the no-visible-surface fallback is not used. It asserts that nothing visible changed, which is false here, and the gate treats the substitution as a judgment finding even when the mechanical pass succeeds.
- Carry-through: `review_verdict` states that rendering was not observed, and `residual_risk` names the missing capability plus the condition that closes it — a capture run on a host with a browser at the same revision.
