# Example Invocations

Three delegations and the actual text engineer returns. Example 1 is a slice as it
appears in the spec, example 2 a reorder returned against a plan, example 3 the
refusal when no approved design package exists. The field rules behind them are in
`workflow.md`.

## Contents

1. Example 1 — "prepare the implementation spec"
2. Example 2 — "translate design into delivery slices"
3. Example 3 — "write the engineering plan" with nothing approved upstream

## Example 1 — "prepare the implementation spec"

Delegated by `design/commander` with an approved architecture, endpoint contracts,
and plan for a multi-tenant order workflow. Returned: slice order, then one record
per slice. The first two slices, verbatim:

```markdown
## Slice order

| # | Slice id | Depends on | Ships behind | Acceptance owner |
| - | -------- | ---------- | ------------ | ---------------- |
| 1 | slice.tenancy.model | — | no flag (additive) | data owner |
| 2 | slice.orders.api | slice.tenancy.model (schema) | flag `orders_v2` | API owner |
| 3 | slice.admin.ui | slice.orders.api (contract) | flag `orders_v2` | product owner |
| 4 | slice.notify.worker | slice.orders.api (events) | flag `notify_v2` | ops owner |
| 5 | slice.tenancy.constrain | 1–4 (all writers) | no flag (migration) | data owner |

### slice.orders.api

**Modules owned**: `src/api/orders/*`, `src/services/order.ts`
**Depends on**: `slice.tenancy.model` — every order row must carry `tenant_id`
before the endpoint can scope a query to a tenant.
**Data / migration changes**: none of its own; reads the columns migration `0042`
backfilled.
**Contract tests**: `POST /v1/orders` and `GET /v1/orders` against the approved
contract — positive, validation (missing `sku`, negative `qty`), auth (no token,
wrong tenant), and compatibility (v1 response shape unchanged for existing
consumers). `POST` is idempotent on `Idempotency-Key`; the retry case is a
contract test, not a unit test.
**Proof plan**: failing `tests/api/test_orders_contract.py::test_cross_tenant_read_is_404`
first; smallest green is the tenant-scoped repository query; refactor boundary is
`src/services/order.ts` only — the handler signature stays fixed so slice 3 can
start against it.
**Rollback**: flag `orders_v2` off routes traffic back to the v1 handler, which
stays in place until slice 5 accepts.
**Acceptance evidence**: `pytest tests/api/test_orders_contract.py -q` green and
the contract-test suite running against the staging deployment with the flag on;
accepted by the API owner.
```

**Operational constraints returned with it**: `orders_v2` removed once the v1
handler has zero traffic for seven days; migration `0042` requires a dry-run
backfill reporting zero orphaned rows before the flag opens; the `order_created`
metric ships inside slice 4, not after it.

**Blocking decision returned**: data-retention window for `audit_log` — owner is
the product owner, blocks `slice.tenancy.constrain`, latest safe decision point is
before migration `0043` is written.

## Example 2 — "translate design into delivery slices"

Same package, but the plan sequences the worker queue second. The dependency chain
does not support it, so the spec returns a reorder rather than the plan's order.

```markdown
## Slice order (revised — see conflict note)

| # | Slice id | Depends on | Reason for the edge |
| - | -------- | ---------- | ------------------- |
| 1 | slice.queue.shell | — | transport only; no retry semantics |
| 2 | slice.orders.api | slice.queue.shell | emits `order_created` |
| 3 | slice.queue.retry | slice.orders.api | idempotency key comes from the endpoint contract |
```

**Conflict note to `design/planner`**: the plan places the worker in milestone 2
as one unit. The retry and idempotency rules are defined by the `POST /v1/orders`
contract, so a single worker slice cannot be built before the endpoint lands.
Split as above: the shell is transport-only and can start immediately; the retry
policy follows the endpoint. Severity: Major — the plan's milestone 2 date assumes
the unsplit slice.

**Recommendation**: accept the split, or re-scope milestone 2 to the shell alone.
The spec does not renumber the plan's milestones; that is `design/planner`'s
artifact.

## Example 3 — "write the engineering plan" with nothing approved upstream

Delegated with a product brief and a stack preference, but no `architecture`
artifact in the package. No slices are written.

```markdown
## Blocked — missing upstream artifact

**Missing**: `architecture` (owner `design/architect`), and with it the
`interface-contract` for the two endpoints the brief names.
**Present**: intake brief, stack preference `node-22`, no approved plan.
**Why this blocks**: module ownership per slice is assigned from component
boundaries, and a contract test cannot be named against an unspecified contract.
Slicing from the brief alone would invent both, and the invented boundaries would
reach build with no owner having approved them.
**Returned to**: `design/commander`, to replay the design pipeline from the
`architecture` stage. The `plan` stage is also unstarted and follows it.
**Severity**: Critical — no part of the spec can be written.
**What would unblock it**: an approved architecture covering both endpoints, the
endpoint contracts, and the plan's per-slice acceptance conditions.
```

No skip is recorded here: the artifact is not out of scope, it is not yet
available. A Skip Rule entry would tell the gate the spec was deliberately
omitted, which is a different and false claim.
