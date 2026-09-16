# Workflow Reference

Read this when writing or revising an `implementation-spec`: it carries the
document template, the field-by-field slice record, the endpoint fields a slice
must map, the ordering rules, and the checklist the spec is accepted against.

## Contents

1. Preconditions
2. Implementation-spec document template
3. Delivery-slice record, filled
4. Endpoint fields a slice must carry
5. Dependency and ordering rules
6. Proof-plan rules
7. Operational-constraint checklist
8. Acceptance checklist
9. Contract notes
10. Collaboration notes

## Preconditions

The spec is written only against approved upstream work. Confirm all four before
slicing; a missing one is a return to `design/commander`, not a gap to fill
locally.

| Precondition | Source | Why it blocks |
| --- | --- | --- |
| Component boundaries and data flow approved | `design/architect` (`architecture`) | Module ownership per slice is unassignable without them |
| Endpoint or interface contracts approved, where any surface is in scope | `design/architect` (`interface-contract`) | A contract test cannot be named against an unspecified contract |
| Milestones, rollout shape, and per-slice acceptance conditions approved | `design/planner` (`plan`) | Acceptance evidence has nothing to be judged against |
| Runtime, framework, and version choices locked | `design/commander` (`stack-lock`) | Migration order and rollback mechanism depend on the runtime |

## Implementation-Spec Document Template

```markdown
# Implementation Spec — {scope}

**Revision**: {n}   **Design package revision**: {n}   **Stack lock**: {slug}@{versions}

## Slice order

| # | Slice id | Depends on | Ships behind | Acceptance owner |
| - | -------- | ---------- | ------------ | ---------------- |

## Slices

{one delivery-slice record per slice, in the order above}

## Operational constraints

| Constraint | Slices affected | Owner | Removal criterion |
| ---------- | --------------- | ----- | ----------------- |

## Non-goals

- {what this spec deliberately does not cover, and which phase owns it instead}

## Blocking decisions

| Decision | Owner | Blocks slices | Latest safe decision point |
| -------- | ----- | ------------- | -------------------------- |
```

## Delivery-Slice Record, Filled

The eight fields from SKILL.md, shown with real content. Every slice in the spec
looks like this; a field with nothing to say records why, never nothing.

```markdown
### slice.tenancy.model

**Modules owned**: `src/db/schema/tenant.ts`, `src/auth/tenant-context.ts`
**Depends on**: none (root of the chain)
**Data / migration changes**: add `tenant_id` to `users`, `orders`, `audit_log`,
nullable in migration `0041`; backfill from `org_membership` in `0042`; the
NOT NULL constraint lands in `0043`, after every writer sets the column.
**Contract tests**: none — this slice exposes no endpoint. The invariant
"every row written carries a tenant id" is covered by the repository tests below.
**Proof plan**: failing test `tenant_context_test.py::test_write_without_tenant_rejects`
first; smallest green is the context object plus the repository guard; refactor
boundary is the repository layer only — no call-site changes in this slice.
**Rollback**: migrations `0041`–`0043` are additive and reversible; `0043` is
withdrawn by dropping the constraint, not by dropping the column.
**Acceptance evidence**: `pytest tests/tenancy -q` green and migration `0042`
dry-run reporting zero orphaned rows; accepted by the data owner named in the plan.
```

Field rules:

- **`id`** — `slice.<area>.<short-name>`. The area matches an architecture
  component so the slice traces back without a lookup table.
- **Modules owned** — exclusive. Two slices naming the same module is a merge or a
  split, never a shared claim, because parallel build work cannot resolve it.
- **Depends on** — every edge carries its reason. An unexplained edge is
  indistinguishable from a preference and gets reordered by someone downstream.
- **Data / migration changes** — ordered relative to the code that reads the data.
  Expand, migrate, contract: add nullable, backfill, then constrain.
- **Contract tests** — name the contract and the cases. "Add tests" is not a field
  value.
- **Proof plan** — failing test, smallest green target, refactor boundary. The
  refactor boundary is what keeps the slice from absorbing its neighbours.
- **Rollback** — the mechanism, not the intention. A slice whose only rollback is
  "revert the commit" says so, and that is a constraint on its ordering.
- **Acceptance evidence** — a command or an observation plus an accepting owner.
  A slice with no acceptor is a slice nobody can close.

## Endpoint Fields a Slice Must Carry

When a slice touches an API, webhook, event-ingest, or internal service endpoint,
these fields come across from the approved contract and appear in the slice. The
authoritative template is `../../architect/references/api-endpoint-design.md`
inside the full catalog; this subset is what makes a slice buildable on its own.

| Field | What the slice records |
| --- | --- |
| Method and path | The exact endpoint the slice implements or changes |
| Auth and authorization | Identity source, required roles or scopes, tenant boundary, anonymous behavior |
| Request shape | Path and query params, headers, body schema, validation rules |
| Response shape | Success status and body, empty-state response, error envelope, status codes |
| Idempotency and retry | Whether a repeat call is safe, and the key that makes it so |
| Versioning | Compatibility promise, and the deprecation behavior if the slice changes an existing contract |
| Contract tests | Positive, validation, auth/authorization, and compatibility cases |

A slice that changes any of these without a matching update to the approved
contract is architecture drift: route it to `design/architect` rather than
recording the new behavior in the spec.

## Dependency and Ordering Rules

- Prefer slice boundaries that can be built, tested, and rolled out independently;
  a slice that can only ship with its neighbour is one slice, not two.
- Order by hard prerequisite first, then migration risk, then rollout safety, then
  testability. A tie broken by convenience is recorded as a tie, so a later
  reorder does not look like drift.
- Expand-migrate-contract for every schema change: the contracting step is its own
  slice, ordered after every writer of the new shape has landed.
- Treat hidden migration or cutover work as a real blocker, not deferred
  housekeeping; work nobody sequenced is work nobody staffed.
- A slice behind a feature flag names the flag, its default, and the criterion for
  removing it. A flag with no removal criterion becomes permanent configuration.
- Escalate when the ordering the plan assumes contradicts the real dependency
  chain; the plan is `design/planner`'s artifact and the correction belongs there.

## Proof-Plan Rules

- Behavior changes get a failing test first. The test names the behavior, not the
  function, so the proof survives the refactor that follows it.
- The smallest green target is the least code that turns the test green. Anything
  beyond it belongs to the refactor step or to another slice.
- The refactor boundary names what may be restructured with the tests still
  passing, which is how the slice stays inside its owned modules.
- Name exactly one command per slice that becomes meaningful once the slice lands.
  Re-running an unchanged suite proves nothing and reads as evidence.
- Docs-only and static-content slices record why TDD does not apply; the field is
  answered, not skipped.

## Operational-Constraint Checklist

- Feature flags: name, default, owner, removal criterion.
- Migrations and backfills: order, dry-run expectation, and the slice that
  contracts the schema.
- Cutovers: the switch, who throws it, and what the fallback state is.
- Observability: the metric, log, or trace that shows the slice working in
  production, and which slice adds it.
- Support and operational tasks: runbook changes, on-call impact, manual steps.
- Removal criteria: for every temporary mechanism introduced.

## Acceptance Checklist

- Every slice fills all eight fields, and no field is blank without a stated reason.
- Slice order is explicit and every dependency edge carries a reason.
- Module ownership is exclusive across slices.
- Endpoint contracts in scope map to slices and to named contract tests.
- Every behavior-changing slice has a failing-test-first proof plan and one
  meaningful verification command.
- Migration order follows expand-migrate-contract, and every slice states its
  rollback mechanism.
- Operational constraints are attached to the slices they constrain.
- Remaining blockers are narrow, owned, and dated to a latest safe decision point.
- The spec names `design/commander` as its return target, not the build phase.

## Contract Notes

The contracts this workflow runs under are stated in `../SKILL.md` § Required Contracts.

## Collaboration Notes

The skills this workflow hands to and receives from are named in `../SKILL.md` § Collaboration Surface. What this workflow adds:

- `build/build-management` receives the spec through the approved design package after the gate, never directly from this skill.
