# Frontend Design Doctrine

Binding rules for every frontend design and review skill: `architect`,
`design-qa`, `frontier`, `commander`, and `gatekeeper-design`. A deliverable that
violates them is not gate-eligible. Reviewers cite this doctrine by section
number.

This file is canonical for the visual and structural rules a user-facing
deliverable must satisfy, the six responsive tiers, the shadcn/ui component
foundation, the accessibility floor, the decision-provenance and Taste-snapshot
contract, and the redesign variant rules. It is not canonical for the meaning of
Taste itself ([taste-doctrine.md](taste-doctrine.md)), for gate boundaries and
their required evidence ([gates.yaml](gates.yaml)), or for routing
([routing-doctrine.md](routing-doctrine.md)).

**Which bound skills carry a pointer today.** `architect`, `design-qa`, and
`gatekeeper-design` link this doctrine from their own documents, so a run of any
of them loads it. `commander` and `frontier` do not: `commander` reaches these
rules through the `architect` package it assembles and the `gatekeeper-design`
verdict it receives, and `frontier` reaches them only through the reviewer
applying them. A doctrine no bound skill loads cannot bind that skill by
assertion, so the binding claim above is honest for three of the five and is a
standing gap for the other two.

User presentation and interaction preferences are governed by
[Taste Doctrine](taste-doctrine.md). Apply effective Taste where multiple valid
design choices remain, but this doctrine's mandatory accessibility and gate
requirements cannot be overridden. Surface conflicts instead of silently
normalizing either side.

## Contents

- [Enforcement status](#enforcement-status)
- [0. Decision provenance and the Taste snapshot](#0-decision-provenance-and-the-taste-snapshot)
- [1. Unified, quiet surface](#1-unified-quiet-surface)
- [2. Restraint and information density](#2-restraint-and-information-density)
- [3. Harmony and order](#3-harmony-and-order)
- [4. Responsive from mobile to ultrawide](#4-responsive-from-mobile-to-ultrawide)
- [5. shadcn/ui as the component foundation](#5-shadcnui-as-the-component-foundation)
- [6. Accessibility as correctness](#6-accessibility-as-correctness)
- [7. Gate behavior](#7-gate-behavior)
- [8. Gate evidence](#8-gate-evidence)
- [9. Redesign mocks, selection, and the living prototype](#9-redesign-mocks-selection-and-the-living-prototype)
- [Failure paths](#failure-paths)

## Enforcement status

Almost every rule in §1 through §7 is a judgement a reviewer makes by reading
the package. The mechanical layer is narrow and sits in §8 and §9: three
evidence keys at two boundaries, plus one parity script. Those keys verify that
a record of the right *shape* was submitted; none of them reads a design and
decides whether it is quiet, restrained, harmonious, or accessible.

| Statement | Status | What actually checks it |
| --- | --- | --- |
| `taste_snapshot`, `ui_evidence`, and `rendered_verification` are present and correctly shaped at their boundaries | machine-checked | `skills/harness/gatekeeper/check.py`, driven by [gates.yaml](gates.yaml) |
| A `rendered_verification` record is a typed `render` record with hashed captures, declared breakpoints and themes, and `inputs` bound to the rendered source by sha256 | machine-checked | `check.py`, `evidence_type_rules.render` in [gates.yaml](gates.yaml) |
| An artifact-backed evidence key references a correctly hashed artifact in the package | machine-checked | `check.py`, the `artifact_evidence` list per boundary |
| A fallback uses only the sanctioned applicability string for that key | machine-checked | `check.py`, `fallback_values` in [gates.yaml](gates.yaml) |
| `mock_rendering` has no fallback at `redesign-review` | machine-checked | `check.py`, `no_fallback` on that boundary |
| A `mock_set` carries exactly four mocks with unique ids and four correctly hashed files each, and `selected_variant` carries exactly one | machine-checked | `check.py`, `evidence_type_params.mock_set.required_count` and `.selected_variant.required_count` in [gates.yaml](gates.yaml) |
| When `selection.decision` is `variant`, the four selected-build keys carry evidence rather than a fallback string, and `selected_variant.variants[0].id` equals `selection.chosen` | machine-checked | `check.py`, the `redesign-review` selection consistency rule |
| Every inventory id the level scores appears as a parity marker on rendered markup (§9) | machine-checked | `skills/scripts/check_parity.py`, which passes only at full coverage of the lists its `--level` scores |
| The package carries no unfinished-work marker and no hollow-completion claim | machine-checked | `skills/harness/gatekeeper/_gatecheck.py`, the blocked-phrase check and its default phrase list |
| §7 bullets 1 to 6 — cards as a default primitive, a missing component template, a missing UI/UX handoff, missing behavior for all six tiers, off-scale spacing or ad-hoc color, accessibility treated as follow-up | **judgement** | nothing; a reviewer reads the package and cites the section |
| §7 bullets 7 and 8 | **part mechanical, part judgement** | the keys in §8 and §9 check presence, shape, hashes, the mock count, and the selected-variant count; the traceability content, the digest match, category divergence, and whether a draft stayed a mock are read by a reviewer |
| That the breakpoints a `render` record declares actually cover the six tiers §4 requires | judgement | the record's shape is checked; the coverage claim is read by a reviewer |
| That four directions genuinely differ in three or more Taste categories (§9) | judgement | `mock_set` counts mocks; it cannot measure divergence |
| WCAG 2.2 AA contrast, focus visibility, semantic HTML, reduced motion (§6) | judgement | `frontier` grades it; no automated contrast check is wired to a gate key |
| This document itself | **judgement** | nothing — no comparator opens this file. The mechanical rows above are properties of [gates.yaml](gates.yaml) with `check.py`, and of `check_parity.py`; they would keep passing if §1–§9 here were rewritten. `team-manifest.yaml` `design_system_doctrine` names this doctrine, and nothing resolves that name to a file (its own `authority.unchecked_keys` records the same gap). |

The distinction matters most at §7. Six of its eight bullets are reviewer
judgement, so a package can satisfy every mechanical check in the gate and still
be rejected — and a gate that returns `STRUCTURE_OK` has said nothing about
design quality.

## 0. Decision provenance and the Taste snapshot

Every design decision a later phase builds on records where it came from: the
grilling log (`intake/report_grilling.md`), an explicit run instruction, an
existing project convention, an effective Taste entry, or documented architect
judgment. A decision without provenance is not gate-eligible.

When a project or global Taste store exists, `commander` asks Admiral/Taste for
an effective-profile snapshot and treats it as immutable for the revision. The
snapshot is a shipped, hashed artifact (`design/artifacts/taste-snapshot.json`
or `.md`) carrying:

- `digest`: the canonical effective-profile sha256;
- `project_revision` and `global_revision`: the source store revisions it was
  resolved from;
- `resolved`: every effective entry with `preference_id`, `source_scope`,
  `category`, and `normalized_rule`;
- `shadowed` and `excluded`: the entries the merge in
  [Taste Doctrine §7](taste-doctrine.md) set aside, each with its reason;
- `unresolved_conflicts`: equal-precedence contradictions awaiting a user
  decision;
- `applicability`: the decision that the snapshot applies to this surface, its
  scope, and who decided.

Taste traceability is a table with one row per applied preference or non-Taste
provenance kind:

| Preference id or provenance kind | Snapshot digest | Design-system artifact(s) | Decision | Rendered-verification slot |
| --- | --- | --- | --- | --- |

Explicit run instructions, existing project conventions, and documented
architect judgment use the same table with their provenance kind in the first
column and no invented preference id. Reviewers evaluate against the digest
approved with the design, never against a later store revision; a changed
source revision before `design-to-build` invalidates the snapshot (§8).

## 1. Unified, quiet surface

- One coherent surface per screen. The page reads as a single composition, not a
  grid of competing tiles.
- No card containers as a default layout primitive. Do not wrap unrelated content
  in bordered, elevated, or tinted boxes to force grouping. Use spacing,
  typographic hierarchy, and dividers.
- Cards are permitted only when the content is a discrete, repeating, selectable
  entity (a product tile in a catalog grid, a media item in a gallery). Even
  then use the lightest treatment: no shadow stacks, no nested cards.
- No decorative chrome. No gradients, glows, or background patterns unless they
  carry a functional or brand meaning this doctrine cannot otherwise express.

## 2. Restraint and information density

- Every element earns its place. If removing it would not measurably hurt the
  user task, remove it.
- One strong primary action per view. Demote everything else.
- No duplicated navigation, no redundant labels, no helper text restating what a
  field already says.
- Long pages are acceptable; cluttered pages are not.

## 3. Harmony and order

- One spacing scale (4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px or the rem
  equivalent). No off-scale values.
- One typographic scale with at most six steps. One sans-serif family unless a
  second is justified by brand.
- A constrained palette: one neutral ramp, one accent, one semantic set
  (success / warning / danger / info). No ad-hoc colors, and no one-note palette
  dominated by a single hue family, so states stay distinguishable.
- One border radius, one shadow elevation, and one stroke weight used
  everywhere unless a specific component documents the exception.
- Align to a consistent grid. Optical alignment beats pixel-perfect when they
  conflict, but never both on the same surface.
- Letter spacing defaults to `0`; negative tracking requires a recorded brand
  exception and must not reduce readability.

## 4. Responsive from mobile to ultrawide

| Tier | Width | Required behavior |
| --- | --- | --- |
| Small mobile | 320-374 px | Single column, no horizontal scroll, tap targets at least 44 px, no truncation of primary content |
| Mobile | 375-639 px | Single column, comfortable measure, sticky primary action where relevant |
| Tablet | 640-1023 px | Optional two-column where it improves scanning, never forced |
| Desktop | 1024-1439 px | Multi-region layouts permitted; 72ch maximum measure for prose |
| Large desktop | 1440-1919 px | Centered max-width container; do not stretch text regions edge to edge |
| Ultrawide | 1920 px and above | Hard content-width cap (typically 1440-1600 px); use whitespace, not extra columns |

- Token-based typography that does not scale directly with viewport width.
  Fluid spacing is allowed where it improves rhythm; body copy stays readable.
- Container queries when the component, not the viewport, drives the shift.
- Fixed-format elements (boards, tables, toolbars, counters, tiles) need stable
  dimensions (`minmax`, aspect ratio, min/max bounds, or container-relative
  sizing) so hover states, labels, icons, and dynamic content do not shift the
  layout.
- Text must not overlap adjacent content or overflow its control. Wrap, shorten,
  or constrain before accepting truncation of primary content.
- Test every state (empty, loading, error, success, permission-denied) at each
  tier. Coverage at one breakpoint does not count.

## 5. shadcn/ui as the component foundation

- Every interface design includes a shadcn/ui component template. Mandatory
  output for any `architect` package with a user-facing surface.
- Every interface design includes a UI/UX handoff template: route inventory,
  screen states, API and data dependencies, validation behavior, and responsive
  evidence.
- Use shadcn/ui primitives as the default building blocks (`Button`, `Input`,
  `Label`, `Form`, `Dialog`, `Sheet`, `DropdownMenu`, `Tabs`, `Table`, `Toast`,
  `Tooltip`, `Separator`, `ScrollArea`). Do not hand-roll equivalents.
- Use the project's icon library, or `lucide-react` by default. Icon-only
  buttons need accessible names and tooltips when the meaning is not universal.
- Style via Tailwind utilities and shadcn CSS variable tokens (`--background`,
  `--foreground`, `--primary`, `--border`, `--radius`). No inline styles and no
  one-off CSS for what tokens already cover.
- Variants use the `cn()` helper and the `class-variance-authority` pattern.
- Dark mode works through the `.dark` class and standard token overrides.
- Custom components extend shadcn primitives in the same shape (Radix-based,
  token-driven, variant-typed); they do not replace them.

### Required component template

```markdown
## Component Template (shadcn/ui)

**Primitives used**: [e.g. Button, Input, Form, Dialog, Card-only-if-justified]
**New components introduced**: [name + one-line purpose, or "none"]
**Token overrides**: [--primary, --radius, etc., or "defaults"]
**Variant matrix**: [per new or customized component: variants x sizes x states]
**Composition example**: [short TSX snippet for the primary screen]
**Responsive behavior**: [reflow across the six tiers above]
**Dark mode**: [confirmed working, or token deltas required]
**Accessibility**: [keyboard map, ARIA, focus order, verified contrast ratios]
```

### Required UI/UX handoff

```markdown
## UI/UX Handoff

**Route / screen inventory**: [route, purpose, primary user, entry and exit points]
**Workflow and state matrix**: [loading, empty, error, success, permission-denied, disabled, optimistic per screen]
**API / data dependency map**: [screen -> endpoint -> cache key / state owner -> retry behavior]
**Forms and validation**: [client validation, server validation, error placement, success feedback]
**Responsive evidence**: [behavior at each of the six tiers]
**Interaction details**: [keyboard path, focus management, destructive confirmations, undo and retry]
**Text fit / overflow checks**: [long labels, narrow controls, localization-sensitive strings]
**Copy and empty-state rules**: [labels, error copy, empty-state action, permission-denied language]
```

Both sections are filled concretely, not with placeholder text. A design package
missing either one does not pass the design gate.

## 6. Accessibility as correctness

- WCAG 2.2 AA minimum for text contrast (4.5:1 body, 3:1 large and UI).
- Visible focus rings on every interactive element. Never `outline: none` without
  an equivalent custom indicator.
- Semantic HTML before ARIA. Use ARIA only to fill platform gaps.
- Honor `prefers-reduced-motion` for any non-essential motion.

An inaccessible flow is a broken flow, not a polish item.

## 7. Gate behavior

`gatekeeper-design`, `design-qa`, and `frontier` reject any package that:

- **(judgement)** Uses cards as a default grouping primitive without specific
  justification.
- **(judgement)** Lacks the component template section (§5). The `ui_evidence`
  key states that the section exists; no script opens the package and finds it.
- **(judgement)** Lacks the UI/UX handoff section with route inventory, state
  matrix, API and data dependency map, validation behavior, and responsive
  evidence (§5). Same key, same limit.
- **(judgement)** Lacks documented behavior for all six responsive tiers (§4).
  A `render` record declares which breakpoints it covered and that declaration
  is shape-checked, but nothing compares the declared breakpoints against the
  six tiers, and nothing reads the design for tier coverage.
- **(judgement)** Introduces off-scale spacing, ad-hoc colors, or a second
  typographic family without a recorded exception (§3).
- **(judgement)** Treats accessibility or responsive coverage as follow-up work
  (§6).
- **(part mechanical)** Lacks decision provenance or Taste traceability required
  by §0, or evaluates against a Taste digest other than the one approved with
  the design. `taste_snapshot` is a required, hashed, artifact-backed key at
  `design-to-build` (§8); that the traceability table is complete and that the
  digest is the approved one are judgements.
- **(part mechanical)** At `redesign-review`: fewer than four mocks, directions
  that differ in fewer than three Taste categories, a mock or a selected
  prototype below full parity coverage at its level, a living prototype built
  before a variant was selected, or a mock or prototype that needs a build step
  or the network (§9). The mock count, the selected-variant count, and the
  parity coverage are mechanical; category divergence, the no-build-step claim,
  and whether a draft stayed a mock are judgements.

Marking six of these eight as judgement is not a softening. A judgement
rejection is as binding as a mechanical one, and a reviewer who declines to make
it because no script demanded it has not done the review. The marking exists so
nobody reads a green gate report as a statement that these rules were checked.

## 8. Gate evidence

Three keys in [gates.yaml](gates.yaml) carry this doctrine mechanically. The key
names, boundaries, owners, and fallback strings below are quoted from that file
so a reader can check them against it directly; `gates.yaml` is canonical and
this section is derived from it.

- `taste_snapshot` at `design-to-build`, submitted by `commander` and owned by
  `taste` in `evidence_owners`. It appears in both `required_evidence` and
  `artifact_evidence`, so it must be present *and* reference a correctly hashed
  artifact in the package: a shipped snapshot artifact with the fields and
  traceability table from §0. When no saved Taste profile is available, it
  carries the typed applicability record for the sanctioned fallback string
  `no saved Taste profile available`, which is the only accepted fallback for
  this key.

- `ui_evidence` at `design-to-build`, submitted by `commander` and owned by
  `architect`. It is in `required_evidence` only, so it is a statement rather
  than a hashed artifact: it states that the design package contains the §5
  component template and UI/UX handoff, or carries the applicability record for
  the sanctioned fallback string
  `no user-facing surface - design system not engaged`.
- `rendered_verification` at `review-to-delivery`, submitted by `code-chief` and
  owned by `design-qa`. Its `evidence_types` entry is `render`, so `check.py`
  applies the typed `render` rule: hashed captures or artifacts, the breakpoints
  and themes covered, `inputs` bound to the rendered source by sha256, and a
  `result.status` of `pass` or `inferred`. A run with no visible change carries
  the applicability record for the sanctioned fallback string
  `no visible surface changed - rendered verification not applicable`. That
  fallback does not exist at `redesign-review`; there the key stands for the
  selected variant's captures and carries, when no variant was selected, one of
  that boundary's own sanctioned strings instead. The key listed under
  `no_fallback` at `redesign-review` is `mock_rendering`, which is always
  produced because the four mocks are always built.

A render record with `result.status: inferred` is accepted only with a stated
limitation and is labelled as inferred, never as observed.

What these three verify is record shape, hashes, and sanctioned fallback
strings. None of them verifies tier coverage, component-template content, or
design quality; those are the judgement clauses marked in §7.

## 9. Redesign mocks, selection, and the living prototype

The redesign pipeline (`design/redesign`) compares four design systems as
**mocks**, and implements one only after a mock has been selected. Four living
prototypes built before a choice is three implementations made to be thrown
away; that waste is the failure this section exists to prevent. These rules keep
the comparison honest and the implementation late.

- **Inventory first.** `design-mapper` records the current surface as a
  stable-id inventory (routes, states, components, interactions, flows,
  tokens, accessibility baseline) with baseline captures at the six tiers in
  both themes. The inventory is the parity contract; nothing is designed
  before it exists.
- **Four directions, genuinely different.** `architect` writes four
  directions that diverge in at least three Taste categories
  ([taste-doctrine.md](taste-doctrine.md) §3) and traces every decision to an
  effective preference, an explicit instruction, or documented judgment.
  Palette-only variation is one direction, not four.
- **Four mocks, not four implementations.** `prototyper` draws each direction as
  a static mock under `redesign/artifacts/mocks/<id>/`: `variant.md`,
  `tokens.css`, `components.css`, `components.html`, and `mock.html`.
  `mock.html` renders one screen per inventory route with `data-route="<id>"` on
  each screen's root, uses hard-coded sample content, carries every inventory
  component somewhere across `components.html` and `mock.html` marked
  `data-component="<id>"`, and offers light and dark through `tokens.css`. Its
  root element carries `data-mock="true"` so the parity checker and the
  reviewers can tell a mock from a living prototype.
- **What a mock must not contain.** No hash router with real navigation state,
  no in-memory data or state machine, no wired interactions or flows, no
  `components.js`. The only JavaScript a mock may carry is an optional theme
  toggle and an optional screen picker that shows and hides the static screens.
  `data-interaction` and `data-flow` markers are not required; route states may
  be drawn as extra static screens (`data-route-state`) but are not required
  either. A mock that wires an interaction is not a better mock, it is an
  implementation built before the decision that justifies it.
- **Mock parity, mechanically proven.** `scripts/check_parity.py --level mock`
  scores **routes and components only**, at `--min-coverage 1.0` for those two
  lists; interactions, flows, and states are reported as informational counts
  and never fail the mock level. The mapper writes one record per mock and one
  aggregated probe record over the set. Pixel similarity is never the criterion.
- **Selection before implementation.** The user picks one mock, asks for a
  merge, or defers, and the answer is recorded verbatim in
  `redesign/reports/selection.md` and in the typed `selection` record. Nothing
  is implemented before that decision exists.
- **One living prototype, for the chosen mock only.** When a variant was
  selected, `prototyper` builds `redesign/artifacts/variants/<id>/`:
  `variant.md`, `tokens.css`, `components.css`, `components.js`,
  `components.html`, and an `app.html` single-page prototype with hash routing
  over every inventory route, a switcher for every declared state, mocked data,
  working interactions and flows, dark mode, keyboard paths, and
  `prefers-reduced-motion`. It is derived from the selected mock's tokens and
  catalog. No build step, no network; the files open from disk. Every inventory
  id appears as a `data-route`, `data-state` (or `data-route-state`),
  `data-component`, `data-interaction`, or `data-flow` marker on rendered
  markup, and `check_parity.py --level full` passes only at full coverage of
  every list.
- **shadcn-shaped.** Component names, variant axes, and token names follow
  §5 so the chosen variant maps one-to-one onto the production design system
  the design pipeline then implements.
- **Evidence per stage.** `design-qa` captures every mock screen at the six
  tiers in both themes (§4), and captures the selected variant's routes and
  states the same way once it exists; `frontier` grades accessibility on the
  selected variant with the shared severities. A mock with a parity gap is
  repaired by its builder before it enters the comparison, and a Critical
  accessibility finding on the selected variant is repaired before the package
  gates.
- **Gate evidence.** At `redesign-review` ([gates.yaml](gates.yaml)) the
  fourteen required keys are `design_inventory`, `taste_grilling`,
  `taste_snapshot`, `design_directions`, `mock_set`, `mock_parity`,
  `mock_rendering`, `selection`, `selected_variant`, `parity_evidence`,
  `rendered_verification`, `accessibility_evidence`, `recommendation`, and
  `residual_risk`. Eleven of them are also `artifact_evidence` and so must
  reference correctly hashed artifacts: every key above except
  `accessibility_evidence`, `recommendation`, and `residual_risk`.
  `mock_rendering` is listed under `no_fallback` at this boundary, because the
  mocks are always built and therefore always renderable; `rendered_verification`
  is not, because a merge or a deferral legitimately leaves no living prototype
  to render. "Exactly four" is not prose:
  `evidence_type_params.mock_set.required_count` is `4`, and the typed record
  requires four mocks with unique ids whose `spec`, `tokens`, `components`, and
  `mock` files are each a correctly hashed artifact in the package, with `count`
  equal to the list length when present. A fifth mock fails the gate as
  mechanically as a third does. `selected_variant` is the mirror rule at
  `required_count` 1.
- **Handoff.** The chosen variant's `variant.md`, `tokens.css`, and
  `components.html` — from the selected living build, not from the mock — are
  the design-system input to the design pipeline; a merge choice is a brief for
  `architect`, not a fifth mock and not a second prototype.

## Failure paths

- **No saved Taste profile exists.** Do not ship an empty snapshot that claims a
  profile was resolved. Carry the typed applicability record for
  `no saved Taste profile available` (§8) and record in §0's traceability table
  that every decision rests on an explicit instruction, a project convention, or
  documented architect judgement.
- **The package has no user-facing surface.** Use the `ui_evidence`
  applicability record for `no user-facing surface - design system not engaged`.
  §5's template requirements do not apply to a package with no surface; they are
  not waived for a package that has one.
- **No browser or renderer is available.** A `render` record may carry
  `result.status: inferred`, but only with a stated limitation and labelled as
  inferred. At `redesign-review` there is no fallback on `mock_rendering`: the
  boundary does not close until a render record for the four mocks exists, even
  if it is an inferred one.
- **The Taste store revision changed between the snapshot and the gate.** The
  snapshot is invalid (§0). Re-resolve, re-snapshot, and re-run the affected
  design decisions against the new digest rather than approving against a digest
  the design was not written for.
- **A Taste preference collides with an accessibility, security, or gate
  requirement.** The requirement wins, the preference is not applied, and the
  collision is surfaced rather than normalized in either direction
  ([taste-doctrine.md](taste-doctrine.md) §1).
- **A responsive tier cannot be tested.** Record the tier as untested with the
  reason. An untested tier is a gap, never coverage, and §7's tier bullet is a
  judgement rejection precisely so a reviewer can weigh a stated gap against a
  silent one.
- **A shadcn/ui primitive does not exist for a required pattern.** Extend a
  primitive in the same shape (Radix-based, token-driven, variant-typed) and
  document the new component in the §5 variant matrix. Hand-rolling a
  replacement for a primitive that does exist is the case §5 forbids.
- **`check_parity.py` reports a coverage gap.** The builder repairs it before
  the mock enters the comparison, or before the selected variant gates (§9).
  Parity is pass-or-fail at full coverage of the lists the level scores; there is
  no partial credit and no reviewer override.
- **Two clauses of this doctrine conflict.** §6 and §0 outrank the rest: an
  accessibility requirement is never traded away for a §1 through §3 aesthetic
  rule, and a decision without provenance is not gate-eligible regardless of how
  well it satisfies everything else. Any remaining conflict is surfaced to the
  design owner rather than resolved silently in the deliverable.
