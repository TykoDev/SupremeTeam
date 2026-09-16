# Rollback Plan Reference

Read this when writing the `rollback-plan` artifact, and again when checking whether it
satisfies `rollback_plan` at the `deploy-readiness` boundary. SKILL.md names the three parts;
this file states what each must contain and what makes it fail.

## Contents

1. Why the rollback plan is its own artifact
2. Rollback trigger
3. Rollback procedure
4. Data considerations
5. Gate checks
6. Minimum viable shape

## 1. Why the Rollback Plan Is Its Own Artifact

`../../ownership.yaml` requires two kinds of evidence in `rollback-plan`: the rollback trigger
and procedure, and the data considerations. A rollback command folded into the settings bundle
satisfies neither, because the command answers how to redeploy and says nothing about when to do
it or what the redeploy cannot undo. Those are the two questions an on-call responder actually
faces, at the worst possible moment to be deriving them, which is why the plan is a separate
hashed file rather than a field.

## 2. Rollback Trigger

The observable condition that starts a rollback, stated as a threshold a responder can evaluate
under pressure rather than a judgment call:

- **Which signal** — the exact metric, alert, or check, named as it appears in the dashboard the
  responder will be looking at.
- **Which value, over which window, held for how long** — "error rate above 2% over a 5-minute
  window, sustained for 10 minutes", not "if errors spike".
- **Who calls it** — the owner authorized to call the rollback, and the owner to escalate to
  when that person is unreachable. An unnamed caller means nobody calls it.
- **The decision deadline** — the point after which no rollback happens and the release is
  repaired forward instead. Without it, a rollback stays notionally available long past the point
  where it is more dangerous than the defect.

## 3. Rollback Procedure

The ordered steps that return the environment to its previous state, each paired with the check
that confirms the step worked:

- The previous artifact id or version, named explicitly rather than as "the last good build".
- The exact command or console path for each step.
- The secret and certificate versions restored alongside it — a rolled-back build with a
  rotated-forward secret is a second outage.
- The routing, DNS, and feature-flag state to revert, with propagation times where they apply.
- The expected duration of each step, so a stalled rollback is recognisable as stalled.
- The smoke checks that confirm the environment is healthy again, not merely that the deploy
  command exited zero.

Mark any step that cannot be rehearsed as unrehearsed, so its risk is visible before the release
rather than discovered during it.

## 4. Data Considerations

What the rollback cannot undo. This is where a clean-looking rollback leaves damage, and it is
the part a responder cannot reconstruct mid-incident. Cover, at minimum:

| Surface | The question it answers |
| --- | --- |
| Schema migrations already applied | Does the previous build still run against this schema? |
| Rows written, backfilled, or deleted under the new code | What data exists that the old code cannot read, or has lost? |
| Messages consumed from a queue or topic | What was acknowledged and will not be redelivered? |
| Emitted webhooks and third-party side effects | What has already left the system — charges, emails, partner notifications? |
| Cache, index, and CDN state | What survives the deploy and keeps serving the new behavior? |

For each one state three things: whether it is forward-only, the compensating action and its
owner, and the data loss or inconsistency a rollback would leave. A plan that does not state its
data boundary is incomplete, and the unstated boundary is the release blocker.

## 5. Gate Checks

`rollback_plan` is artifact-backed at `deploy-readiness` with no sanctioned fallback value in
`../../gates.yaml`, so it is a hashed file or the gate does not close. Three failures make an
otherwise well-written plan unsatisfied:

1. **A trigger with no signal behind it** — a threshold on a metric the configuration does not
   actually emit is not evaluable.
2. **A procedure that restores an artifact the configuration no longer retains** — check the
   retention policy of the artifact store against the decision deadline, not against intent.
3. **An empty data-considerations section** — including one that says "none", unless each
   surface in the table above is individually accounted for.

## 6. Minimum Viable Shape

```markdown
# Rollback Plan - <service> <config revision>

## Trigger
Signal: checkout 5xx rate (dashboard "Checkout Health", panel 2)
Threshold: above 2% over a 5-minute window, sustained 10 minutes
Called by: on-call release owner; escalation: platform lead
Decision deadline: 60 minutes after rollout start; after that, repair forward

## Procedure
1. Redeploy artifact `web-2026.04.12` - `deploy web --version 2026.04.12` (~4 min)
   Check: /healthz returns 200 and reports build 2026.04.12
2. Restore secret bundle version 7 and certificate `star-example-2026-03`
   Check: TLS chain valid, no auth errors in the 2 minutes after restart
3. Revert feature flag `checkout_v2` to off (propagation ~60s)
   Check: flag read path returns off from two regions
4. Smoke: guest checkout, saved-card checkout, refund path
   [unrehearsed] Step 2 has never been exercised in production.

## Data considerations
- `orders.currency` migration: forward-only. Old build reads the column as NULL.
  Compensating action: backfill script `scripts/currency_backfill.py`, owned by payments.
  Rollback leaves orders created after the migration without a readable currency.
- Payment webhooks already emitted: cannot be recalled. Partner reconciliation job
  owned by payments handles duplicates.
- Order-summary cache: survives the rollback. Flush required, `cache flush order-summary`.
```
