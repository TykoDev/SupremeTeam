# Example Invocations

Three delegations and the actual plan text returned — the milestone path with its
acceptance rows, a Decision Register, and a migration/deprecation plan. The
templates behind them are in `workflow.md`.

## Contents

1. Example 1 — "plan this project"
2. Example 2 — "create the rollout plan" with two open choices
3. Example 3 — "sequence the implementation work" where a legacy API is replaced

## Example 1 — "plan this project"

A tenant-scoped order workflow, architecture approved for the whole scope.
Verbatim from the plan:

```markdown
## Milestone path

| # | Milestone | Delivery slices | Depends on | Decision gate before it | Target |
| - | --------- | --------------- | ---------- | ----------------------- | ------ |
| M1 | Scope validated | tenancy model | — | — | week 1 |
| M2 | Core API and auth | orders API, auth scoping | M1 (schema) | — | week 4 |
| M3 | Admin workflow | admin UI, reassignment | M2 (endpoint contract) | permission matrix approved | week 7 |
| M4 | Reporting and rollout hardening | event taxonomy, reports, backfill | M3 | event model approved | week 10 |

**Critical gate**: reporting does not start until the event model and permission
matrix are approved. Both are `design/architect` decisions; the plan names them as
gates rather than assuming an outcome.

## Acceptance criteria

| Slice | Observable condition | Check that proves it | Acceptor |
| ----- | -------------------- | -------------------- | -------- |
| tenancy model | No row in `orders`, `users`, or `audit_log` exists without a tenant id | `SELECT count(*) … WHERE tenant_id IS NULL` returns 0 on staging after backfill | data owner |
| orders API | A token scoped to tenant A cannot read tenant B's orders | Contract test `test_cross_tenant_read_is_404` green against staging | API owner |
| admin UI | A dispatcher reassigns a job in two interactions from the queue | Scripted walkthrough at 1024 and 1440 px, both themes, recorded | product owner |
| reporting | Every report figure reconciles to the event log for the same window | Reconciliation job reports zero variance across a 7-day sample | finance reviewer |

## Rollout and rollback shape

| Stage | Audience | Mechanism | Rollback | Trigger to advance |
| ----- | -------- | --------- | -------- | ------------------ |
| Internal alpha | operations users, 1 tenant | flag `orders_v2` per tenant | flag off; v1 handler still live | zero Critical findings for 5 working days |
| Tenant-limited beta | 5 tenants | flag per tenant | flag off per tenant | migration rehearsal passed, reconciliation variance zero |
| GA | all tenants | flag default on | flag off globally; v1 retained 30 days | beta stable 2 weeks |

## Risk handling

| Risk | Kind | Consequence if it lands | Mitigation | Owner |
| ---- | ---- | ----------------------- | ---------- | ----- |
| Backfill exceeds the maintenance window | technical dependency | M2 slips a week; beta date moves | rehearse on a production-sized copy before M2 closes | data owner |
| Only one engineer knows the event pipeline | staffing | M4 cannot start if they are unavailable | pair on the taxonomy slice during M3 | eng lead |
| Rollback is not instantaneous after backfill | rollout | A bad beta cannot be fully reverted, only flagged off | keep migrations additive until GA; contract step is post-GA | data owner |
```

**Returned to** `design/commander`. `design/engineer` consumes it at the next
stage and owns the spec that slices against it.

## Example 2 — "create the rollout plan" with two open choices

The plan is credible only if two decisions are made in order. The Decision
Register, verbatim:

```markdown
## Decision Register

| Decision | Status | Chosen | Source | Rejected options (why) | Owner | Reopen trigger / latest safe point |
| -------- | ------ | ------ | ------ | ---------------------- | ----- | ---------------------------------- |
| Rollout mechanism | resolved | Feature-flagged per tenant | user (intake 2026-09-04) | Tenant-by-tenant migration — rollback needs a restore, not a toggle, and beta rollback must be instant | product owner | Locked once the flag is read by two services; before M2 closes |
| Migration rehearsal before beta | resolved | Required | prior-artifact (`architecture` §invariants) | Skip it — rejected; the backfill is the only irreversible step in M2 | data owner | Not reversible |
| Historical backfill scope | deferred | — | — | Full history now — rejected for M1–M4; window exceeds the maintenance slot | data owner | Reopen when GA is stable; latest safe point is before the schema contract step |
| Per-tenant queues vs shared queue | deferred | Shared queue as the reversible default | delegated-default | Per-tenant queues — deferred, not rejected; sizing evidence does not exist yet | platform lead | Reopen at 200 tenants or p95 queue latency > 2s; before M4 sizes the fleet |
| Reporting UI framework | yagni-deferred | — | delegated-default | Building a chart library now — the first release has four fixed reports | product owner | Reopen when a user-defined report is requested |

**Sequencing consequence**: the rollout mechanism had to resolve before the
rehearsal decision, because a tenant-by-tenant migration would have made the
rehearsal mandatory for every stage rather than once before beta.
```

## Example 3 — "sequence the implementation work" where a legacy API is replaced

The plan removes a v1 endpoint, so it carries a migration/deprecation section.

```markdown
## Migration / deprecation — `GET /v1/orders`

**Replacement readiness**: `/v2/orders` must reach feature parity (filtering,
pagination, the `include=customer` expansion), match v1 p95 latency within 10%, and
ship a request-translation snippet in the integration docs. Until all three hold,
v1 is not discouraged.
**Consumer discovery**: 90 days of gateway access logs grouped by API key, plus the
internal dependency graph. Coverage: every authenticated caller. Misses: any
consumer that called v1 less than once per quarter, and any unauthenticated
health-check path.
**Consumers found**: 14 keys. Four matter — the partner integration (external,
partner success owns the contact), the mobile client below version 3.2 (mobile
lead), the finance export job (finance eng), and one internal admin script (ops).
**Posture**: advisory from GA + 2 weeks → compulsory at GA + 6 months. The
compulsory date is set by the partner's own release cadence, not by the team's.
**Migration path**: v2 is additive; a consumer changes the path and one field name.
The docs carry a side-by-side diff and a 20-line translation shim for the partner's
stack.
**Removal criteria**: zero v1 requests for 30 consecutive days AND all four named
consumers confirmed migrated. Either alone is insufficient — a quiet month does not
prove the quarterly caller is gone.
**Fallback**: at the compulsory date, v1 returns 410 with a `Link` header to the
migration guide; it is not silently removed.

**Sequencing consequence**: the removal slice is not in this plan's milestone path.
It is a named non-goal of this revision with a reopen trigger at GA + 6 months,
because sequencing work whose criteria cannot be met inside the window would make
the schedule non-credible.
```
