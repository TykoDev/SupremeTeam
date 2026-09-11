# Frontend Design Doctrine

Binding rules for every frontend design and review skill: `architect`,
`design-qa`, `frontier`, `commander`, and `gatekeeper-design`. A deliverable that
violates them is not gate-eligible. Reviewers cite this doctrine by section
number.

## 0. Decision provenance and effective Taste

Every design-system decision must trace to exactly one governing source:

1. an effective Taste entry from the immutable snapshot resolved for this design revision;
2. an explicit instruction from the current run;
3. an existing project convention observed in the current project; or
4. a documented designer/architect judgment, including its rationale.

Commander obtains the effective-profile snapshot from Admiral/Taste when project
or global Taste storage exists. The snapshot records its canonical digest,
project and global source revisions, resolved entries, shadowed entries,
unresolved conflicts, and applicability decision. Commander and Architect may
consume it but never edit either preference store. Design feedback not already in
the effective profile is a Taste candidate: record its source context, proposed
preference, rationale, and affected artifacts, then route it through Admiral to
the Taste pipeline for confirmation.

The design package contains a traceability table with, at minimum, `decision_id`,
`provenance_kind`, `effective_preference_id` (when applicable),
`taste_snapshot_digest`, `design_system_artifacts`, and
`rendered_verification_evidence`. Do not substitute mutable current Taste state
for the digest-bound snapshot during design or review.

Immediately before `design-to-build`, compare both recorded source revisions to
Taste. Any change invalidates the snapshot and requires re-resolution and replay
of affected decisions. A revision changed after design approval does not silently
invalidate the run: record it as a candidate for the next design revision unless
the user explicitly requests replay. Report a project preference that conflicts
with approved project design; do not apply it retroactively. Treat revocation of
a preference used by an active design as drift and ask the user whether to retain
the approved design or replay with a newly resolved snapshot.

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
