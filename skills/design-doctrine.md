# Frontend Design Doctrine

Binding rules for every frontend design and review skill in the catalog (`architect`, `design-qa`, `frontier`, and `commander`). These constraints are non-negotiable. A deliverable that violates them is not gate-eligible.

## 1. Unified, Quiet Surface

- One coherent surface per screen. The page reads as a single composition, not a grid of competing tiles.
- **No card containers as a default layout primitive.** Do not wrap unrelated content in bordered, elevated, or background-tinted boxes to force visual grouping. Use spacing, typographic hierarchy, and dividers instead.
- Cards are permitted **only** when the content is genuinely a discrete, repeating, selectable entity (e.g. a product tile in a catalog grid, a media item in a gallery). Even then, prefer the lightest possible treatment — no shadow stacks, no nested cards, no card-inside-card.
- No decorative chrome. No gradients, glows, or background patterns unless they carry a specific functional or brand meaning that the doctrine cannot otherwise express.

## 2. Restraint and Information Density

- Every element must earn its place. If removing it would not measurably hurt the user task, remove it.
- Prefer one strong primary action per view. Demote everything else.
- No duplicated navigation, no redundant labels, no helper text restating what a field already says.
- Long pages are acceptable; cluttered pages are not. A scannable, sparse layout beats a packed one.

## 3. Harmony and Order

- Use a single spacing scale (4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 px or equivalent rem). No off-scale values.
- Use a single typographic scale with at most six steps. One sans-serif family unless a second is justified by brand.
- Use a constrained palette: one neutral ramp, one accent, one semantic set (success / warning / danger / info). No ad-hoc colors.
- Avoid one-note palettes dominated by one hue family; vary neutrals, accent, and semantic colors enough that states remain distinguishable.
- Align to a consistent grid. Optical alignment beats pixel-perfect when they conflict, but never both at once on the same surface.
- Border radius, shadow elevation, and stroke weight each have **one** chosen value used everywhere unless a specific component documents an exception.
- Letter spacing defaults to `0`; negative tracking requires a recorded brand exception and must not reduce readability.

## 4. Responsive From Mobile to Ultrawide

Every design and every implementation must work and look correct across the full range:

| Tier | Width range | Required behavior |
| --- | --- | --- |
| Small mobile | 320–374 px | Single column, no horizontal scroll, tap targets ≥ 44 px, no truncation of primary content. |
| Mobile | 375–639 px | Single column, comfortable reading measure, sticky primary action where relevant. |
| Tablet | 640–1023 px | Optional two-column where it improves scanning, never forced. |
| Desktop | 1024–1439 px | Multi-region layouts permitted; max content measure 72ch for prose. |
| Large desktop | 1440–1919 px | Centered max-width container; do not stretch text-heavy regions edge-to-edge. |
| Ultrawide | ≥ 1920 px | Hard cap on content width (typically 1440–1600 px); use surrounding whitespace, not extra columns. |

- Use token-based typography that does not scale directly with viewport width. Fluid spacing is allowed where it improves layout rhythm; body copy must remain readable and stable.
- Use container queries when the component, not the viewport, drives the layout shift.
- Fixed-format elements such as boards, tables, toolbars, counters, and tiles need stable dimensions (`minmax`, aspect ratio, min/max bounds, or container-relative sizing) so hover states, labels, icons, loading text, and dynamic content do not shift the layout.
- Text must not overlap adjacent content or overflow its control. Move text to another line, shorten copy, or use safe dynamic constraints before accepting truncation of primary content.
- Test every state (empty, loading, error, success, permission-denied) at each tier. State coverage at one breakpoint does not count.

## 5. shadcn/ui as the Component Foundation

- **Every interface design must include a shadcn/ui component template.** This is mandatory output for any `architect` package that includes a user-facing surface.
- **Every interface design must include a UI/UX handoff template.** Route inventory, screen states, API/data dependencies, validation behavior, and responsive evidence are mandatory output for any user-facing surface.
- Use shadcn/ui components as the default building blocks: `Button`, `Input`, `Label`, `Form`, `Dialog`, `Sheet`, `DropdownMenu`, `Tabs`, `Table`, `Toast`, `Tooltip`, `Separator`, `ScrollArea`, etc. Do not hand-roll equivalents.
- Use the project's existing icon library, or `lucide-react` by default, for familiar icon actions. Icon-only buttons need accessible names and tooltips when the meaning is not universal.
- Style via Tailwind utility classes and shadcn's CSS variable tokens (`--background`, `--foreground`, `--primary`, `--border`, `--radius`, etc.). No inline styles, no one-off CSS files for things tokens already cover.
- Theming uses shadcn's `cn()` helper and the `class-variance-authority` (`cva`) pattern for variants.
- Dark mode must work out of the box via the `.dark` class and the standard token overrides.
- Custom components extend shadcn primitives; they do not replace them. If a primitive does not exist, build a new one in the same shape (Radix-based, token-driven, variant-typed).

### Required Component Design Template

Every design deliverable includes this section, filled out concretely (not as placeholder text):

```markdown
## Component Template (shadcn/ui)

**Primitives used**: [list, e.g. Button, Input, Form, Dialog, Card-only-if-justified]
**New components introduced**: [name + one-line purpose, or "none"]
**Token overrides**: [list any --primary, --radius, etc. changes, or "defaults"]
**Variant matrix**: [for each new/customized component: variants × sizes × states]
**Composition example**: [short JSX/TSX snippet showing the component composed for the primary screen]
**Responsive behavior**: [how the component reflows across the six tiers above]
**Dark mode**: [confirmed working / token deltas required]
**Accessibility**: [keyboard map, ARIA, focus order, contrast ratios verified]
```

A design package missing this section is incomplete and must not pass the design gate.

### Required UI/UX Handoff Template

Every user-facing design deliverable also includes this section, filled out concretely:

```markdown
## UI/UX Handoff

**Route / screen inventory**: [route, purpose, primary user, entry points, exit points]
**Workflow and state matrix**: [loading, empty, error, success, permission-denied, disabled, optimistic/pending mutation states per screen]
**API / data dependency map**: [screen -> endpoint/query/mutation -> cache key/state owner -> retry behavior]
**Forms and validation**: [field-level client validation, server validation, error placement, success feedback]
**Responsive evidence**: [behavior at small mobile, mobile, tablet, desktop, large desktop, ultrawide]
**Interaction details**: [keyboard path, focus management, destructive confirmations, undo/retry affordances]
**Text fit / overflow checks**: [long labels, narrow controls, localization-sensitive strings, empty/error copy]
**Copy and empty-state rules**: [labels, error copy, empty-state action, permission-denied language]
```

A design package missing this section is incomplete and must not pass the design gate.

## 6. Accessibility as a First-Class Constraint

- WCAG 2.2 AA minimum for text contrast (4.5:1 body, 3:1 large/UI).
- Visible focus rings on every interactive element. Never `outline: none` without an equivalent custom indicator.
- Semantic HTML before ARIA. Use ARIA only to fill gaps the platform does not cover.
- Honor `prefers-reduced-motion` for any non-essential motion.

## 7. Gate Behavior

The frontend gate (`gatekeeper-design`) and review skills (`design-qa`, `frontier`) must reject any package that:

- Uses cards as a default grouping primitive without specific justification.
- Lacks the shadcn Component Template section.
- Lacks the UI/UX Handoff section with route inventory, state matrix, API/data dependency map, validation behavior, and responsive evidence.
- Lacks documented behavior for all six responsive tiers.
- Introduces off-scale spacing, ad-hoc colors, or a second typographic family without a recorded exception.
- Treats accessibility or responsive coverage as a follow-up.

Reviewers cite this doctrine by section number when issuing findings.
