# Example Invocations

Four delegations and the actual artifact text returned — one per owned artifact:
`architecture`, `interface-contract`, `design-system`, and `design-directions`.
The templates behind them are in `workflow.md`, `api-endpoint-design.md`, and
`visual-design-system.md`.

## Contents

1. Example 1 — "design the architecture"
2. Example 2 — "define system boundaries"
3. Example 3 — "set up shadcn/ui tokens and produce the UI/UX spec"
4. Example 4 — "propose four design directions" (redesign pipeline)

## Example 1 — "design the architecture"

A workflow product with asynchronous events. Returned: the component table, the
invariants, and the open decision. Verbatim from the package:

```markdown
## Components

| Component | Owns | Depends on | Failure behavior | Paged owner |
| --------- | ---- | ---------- | ---------------- | ----------- |
| public-api | request validation, authn session | identity-svc | 503 with `Retry-After`; no partial writes | platform |
| workflow-engine | workflow instance state | event-bus | resumes from last committed step on restart | workflow |
| notification-worker | delivery attempts, retry state | event-bus, email vendor | at-least-once; duplicate sends suppressed by `event_id` | ops |
| audit-store | append-only audit records | — | write failure blocks the originating mutation | compliance |
| identity-svc | users, roles, tenants | — | external; hard dependency for every authenticated path | platform |

## Invariants

| Invariant | Enforced by | Broken when | Detected by |
| --------- | ----------- | ----------- | ----------- |
| Every state transition is audited | audit-store write inside the engine's transaction | audit-store unavailable and the mutation proceeds | `audit_gap_total` counter, alert at > 0 |
| A workflow advances at most once per event | `event_id` idempotency key on the engine's step table | a replayed event lands before the key is written | duplicate-step assertion in the engine's contract tests |

## Technology rationale

| Choice | Alternatives rejected | Why | Reversible? |
| ------ | --------------------- | --- | ----------- |
| Event bus between engine and worker | direct synchronous call | decouples notification latency from workflow commit; the worker can be down without stalling the engine | yes — the worker can be called directly behind the same interface |
| At-least-once delivery, idempotent consumers | exactly-once | exactly-once across two stores is a distributed transaction the stack does not support | no — consumers are written against it |

## Open decisions

| Decision | Owner | Blocks | Latest safe decision point |
| -------- | ----- | ------ | -------------------------- |
| per-tenant queues vs one shared queue | platform lead | worker fleet sizing | before the plan sizes milestone 3 |
```

**Returned to** `design/commander`. The package goes next to `design/planner`, the
stage `../../../pipelines.yaml` places after architecture; `design/engineer`
consumes it one stage later, through the plan.

## Example 2 — "define system boundaries"

The proposed design let both billing and the core app mutate subscription state.
The finding, as it appears in the package:

```markdown
### Rejected boundary — split-brain on subscription state

**Test applied**: single writer (`workflow.md` §Boundary decision method).
**Observed**: `billing` writes `subscription.status` on payment events; `core-app`
writes the same field on plan changes. Both are authoritative; neither reads the
other first.
**Consequence**: a failed payment concurrent with a plan change produces a status
that depends on arrival order, and neither service can be held to an invariant.
**Resolution**: `core-app` becomes the single writer of `subscription.status`.
`billing` emits `payment.failed` and `payment.recovered`; `core-app` applies them.
`analytics` consumes events only and writes nothing.
**Severity**: Critical — the architecture is not build-ready until this is applied.
**Rejected alternative**: an advisory lock shared by both services. It makes the
race rarer without making the invariant enforceable, and it hides the boundary
error behind an operational mechanism.
```

## Example 3 — "set up shadcn/ui tokens and produce the UI/UX spec"

Tailwind v4 detected (OKLCH function form), dark mode required. Excerpts from
`design-system.md`:

```css
:root {
  --background: oklch(0.99 0.002 250);
  --foreground: oklch(0.21 0.01 250);      /* 15.8:1 on --background */
  --primary: oklch(0.52 0.16 250);
  --primary-foreground: oklch(0.99 0.002 250); /* 5.1:1 on --primary */
  --muted-foreground: oklch(0.47 0.01 250);    /* 4.8:1 on --background */
  --destructive: oklch(0.51 0.19 27);
  --border: oklch(0.90 0.004 250);
  --ring: oklch(0.52 0.16 250);
  --radius: 0.5rem;
}
```

```markdown
## Component Template (shadcn/ui)

**Primitives used**: Button, Input, Label, Form, Dialog, Table, Tabs, Toast, Tooltip, Separator
**New components introduced**: `StatusBadge` — workflow state with its colour mapping
**Token overrides**: `--radius: 0.5rem`; chart set added for the reporting route
**Variant matrix**: StatusBadge — variants (pending, active, failed, archived) x sizes (sm, md) x states (default, interactive)
**Composition example**: `<Form>` + `<Input>` + `<Button variant="default" size="sm">` on the workflow-create dialog
**Responsive behavior**: table collapses to stacked cards below 640; sidebar becomes a Sheet below 1024
**Dark mode**: confirmed; `--muted-foreground` lifted to oklch(0.72 0.01 250) for 4.7:1
**Accessibility**: Tab order follows visual order; dialog traps focus and restores on close; StatusBadge carries a text label, never colour alone; measured ratios above

## UI/UX Handoff — workflow list route (excerpt)

| Route | Endpoint | Load | Empty | Error | Mutation feedback |
| ----- | -------- | ---- | ----- | ----- | ----------------- |
| /workflows | GET /v1/workflows | skeleton rows, 6 | "No workflows yet" + Create action | inline alert + Retry, list preserved | Toast on create; row updates optimistically, reverts on 4xx |
```

**Adversarial review**: eight dimensions, lowest score 9 (information density,
after the table's default row height dropped from 56 to 44px). Contrast verified
to WCAG 2.2 AA in both themes.

## Example 4 — "propose four design directions" (redesign pipeline)

Delegated by `design/redesign` with the hashed inventory and the taste grilling
log. The divergence matrix and one direction, verbatim:

```markdown
## Divergence matrix

| Category | A — Quiet Editorial | B — Dense Operational | C — Soft Console | D — Structured Utility |
| -------- | ------------------- | --------------------- | ---------------- | ---------------------- |
| density | generous, 8px unit | compact, 4px unit | compact, 4px unit | medium, 6px unit |
| visual-style | flat, hairline rules | flat, filled headers | soft depth, tinted panels | flat, boxed regions |
| typography | serif headings, 16px base | 13px base, tabular figures | 14px base, single family | 15px base, weight-led hierarchy |
| motion | none beyond focus | 120ms state changes only | 200ms with easing | none beyond focus |
| layout | single column, wide gutters | full-bleed tables | sidebar + panel | fixed 12-column grid |

Five categories differ across all four columns; the gate requires three.

## Direction B — Dense Operational

**Concept**: a queue to work through, not a page to read. Everything visible at once,
nothing decorative competing with the data.
**Token strategy**: 13px base with a 13/15/17/20/26 scale, tabular figures; 4px
spacing unit; 0.25rem radius everywhere; one elevation; 120ms transitions on state
change only.
**Component approach**: Table and Badge carry the identity — filled headers,
row density switching, inline status. Button, Input, and Dialog stay plain shadcn.
**Differentiators**: row-density switcher; keyboard-first queue traversal
(`j`/`k`/`Enter`); every list state reachable without leaving the route.
**Taste traceability**:

| Decision | Preference id | Strength | Snapshot digest |
| -------- | ------------- | -------- | --------------- |
| 13px base, 4px unit | taste:density/compact-operational-tables | hard | sha256:4c7e… |
| one elevation, no tint | taste:visual-style/plain-surfaces | strong | sha256:4c7e… |

**Inventory fit**: resolves the `component.button` / `component.primary-button`
duplicate by keeping one Button; fixes `a11y.contrast.muted` (3.9:1) by moving
`--muted-foreground` to 4.8:1.
```

**Returned**: `design-directions.md` with its sha256, to `design/redesign` for the
four parallel variant builds by `design/prototyper`.
