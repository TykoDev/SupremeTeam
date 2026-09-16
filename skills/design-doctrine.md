# Frontend Design Doctrine

Binding rules for every frontend design and review skill: `architect`,
`design-qa`, `frontier`, `commander`, and `gatekeeper-design`. A deliverable that
violates them is not gate-eligible. Reviewers cite this doctrine by section
number.

User presentation and interaction preferences are governed by
[Taste Doctrine](taste-doctrine.md). Apply effective Taste where multiple valid
design choices remain, but this doctrine's mandatory accessibility and gate
requirements cannot be overridden. Surface conflicts instead of silently
normalizing either side.

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

- Uses cards as a default grouping primitive without specific justification.
- Lacks the component template section (§5).
- Lacks the UI/UX handoff section with route inventory, state matrix, API and
  data dependency map, validation behavior, and responsive evidence (§5).
- Lacks documented behavior for all six responsive tiers (§4).
- Introduces off-scale spacing, ad-hoc colors, or a second typographic family
  without a recorded exception (§3).
- Treats accessibility or responsive coverage as follow-up work (§6).
- Lacks decision provenance or Taste traceability required by §0, or evaluates against a Taste digest other than the one approved with the design.
- At `redesign-review`: fewer than four variants, directions that differ in fewer than three Taste categories, a prototype below full parity coverage, or a prototype that needs a build step or the network (§9).

## 8. Gate evidence

Three keys in [gates.yaml](gates.yaml) carry this doctrine mechanically:

- `taste_snapshot` at `design-to-build`, submitted by `commander`. It is a
  shipped, hashed snapshot artifact with the fields and traceability table from
  §0. When no saved Taste profile is available, it carries the typed
  applicability record for the sanctioned fallback
  `no saved Taste profile available`.

- `ui_evidence` at `design-to-build`, submitted by `commander`. It states that
  the design package contains the §5 component template and UI/UX handoff, or
  carries the applicability record for the sanctioned fallback
  `no user-facing surface - design system not engaged`.
- `rendered_verification` at `review-to-delivery`, submitted by `code-chief` and
  produced by `design-qa`. It is a typed `render` record: hashed captures, the
  breakpoints and themes covered, and `inputs` bound to the rendered source by
  sha256. A run with no visible change carries the applicability record for
  `no visible surface changed - rendered verification not applicable`.

A render record with `result.status: inferred` is accepted only with a stated
limitation and is labelled as inferred, never as observed.

## 9. Redesign variants and living prototypes

The redesign pipeline (`design/redesign`) compares four design systems before
one is built for real. These rules keep the comparison honest.

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
- **Living prototypes.** `prototyper` builds each variant as plain HTML, CSS,
  and JavaScript: `tokens.css`, `components.css`, `components.js`, a
  `components.html` catalog showing every primitive in every variant, size,
  and state, and an `app.html` single-page prototype with hash routing over
  every inventory route, a switcher for every declared state, mocked data,
  working interactions and flows, dark mode, keyboard paths, and
  `prefers-reduced-motion`. No build step, no network; the files open from disk.
- **shadcn-shaped.** Component names, variant axes, and token names follow
  §5 so the chosen variant maps one-to-one onto the production design system
  the design pipeline then implements.
- **Functional parity, mechanically proven.** Every inventory id appears as a
  `data-route`, `data-state` (or `data-route-state`), `data-component`,
  `data-interaction`, or `data-flow` marker on rendered markup.
  `scripts/check_parity.py` writes a typed probe record per variant bound by
  sha256 to the inventory and prototype files; it passes only at full
  coverage. Pixel similarity is never the criterion.
- **Evidence per variant.** `design-qa` renders every route and state at the
  six tiers in both themes (§4); `frontier` grades accessibility with the
  shared severities. A variant with an open Critical accessibility finding or
  a parity gap is repaired by its builder before it enters the comparison.
- **Gate evidence.** At `redesign-review` ([gates.yaml](gates.yaml)):
  `design_inventory`, `taste_grilling`, `taste_snapshot`, `design_directions`,
  `variant_set` (exactly four, every file hashed), `parity_evidence`,
  `rendered_verification` (no fallback at this boundary),
  `accessibility_evidence`, `recommendation`, and `residual_risk`.
- **Handoff.** The chosen variant's `variant.md`, `tokens.css`, and
  `components.html` are the design-system input to the design pipeline; a
  merge choice is a brief for `architect`, not a fifth prototype.
