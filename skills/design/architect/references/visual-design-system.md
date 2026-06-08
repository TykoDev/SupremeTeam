# Visual Design System — Frontend/UI Pipeline

The architect owns the visual design system for any user-facing surface. This
reference is the full pipeline: from "we need a UI" to a production-ready token
set, shadcn/ui component template, UI/UX specification, and an adversarial design
review that proves the result before the design gate.

This work is bound by `design-doctrine.md` (the quiet-surface rules, the shadcn
foundation, the six responsive tiers, and the accessibility floor). Read it first
— a deliverable that violates the doctrine is not gate-eligible. Run the intake
interview per `grill-me-doctrine.md` before generating anything.

Skip the entire pipeline only for genuinely backend-only systems, and record the
skip with a one-line justification in the architecture package.

---

## Phase 0 — Mode Selection

Decide the starting mode before touching any file.

- **New** — blank-slate surface. Run the design interview (Phase 2A), then
  generate tokens, template, and preview from scratch.
- **Existing** — there is a frontend already. Analyse it first (Phase 2B), then
  present a proposed redesign for approval before generating anything.

Default to **Existing** when the user supplies a project path, screenshots, a
`components.json`, or mentions an existing codebase. Default to **New** for "from
scratch", "blank project", or "new app".

---

## Phase 1 — Detect Framework & Tailwind Version

The token format is **version-specific and not interchangeable** — get this wrong
and every themed class silently falls back to its default (looks identical to "my
theme isn't loading"). Detect before writing a single token.

Read `package.json` (or ask if unavailable) and determine:

- **Package manager** — `npm` / `pnpm` / `bun` / `yarn`. Use one runner
  consistently; mixing runners corrupts the lockfile.
- **Framework** — `next` / `vite` / `astro` / `react-router` / `laravel` /
  `tanstack`.
- **Tailwind major version** — v4 if `tailwindcss` is `^4` and the CSS uses
  `@import "tailwindcss"`; v3 if `^3` with a `tailwind.config.{js,ts}` and
  `@tailwind base/components/utilities`.
- **shadcn already initialised?** — presence of `components.json`.

| Situation | Action |
|---|---|
| Fresh project, shadcn not initialised | `npx shadcn@latest init` (substitute the project's runner) |
| `components.json` already present | Do **not** re-init. Run `npx shadcn@latest info --json` to list installed components and the configured registry |
| shadcn CLI unreachable / network blocked | Stop. Do not hand-roll components from memory (the registry drifts faster than training data). Ask the user to enable network, point to a mirror via `--registry`, or clone from <https://ui.shadcn.com/docs/components> |

After init, confirm: `components.json` exists, CSS variables are injected into the
global stylesheet, and the Tailwind entry (`tailwind.config` for v3, or
`@import "tailwindcss"` + `@theme inline` for v4) is present.

---

## Phase 2A — Design Interview (New mode)

Run as a structured conversation per `grill-me-doctrine.md`: one design/configuration
decision at a time, using the host-native planning prompt when available. Each
question carries a recommended answer and a one-line rationale. Confirm each
decision before moving on. Do not bundle multiple decisions into a topic group and
do not dump a wall of questions.

1. **Purpose & brand** — app type, industry, target users, three personality
   keywords (e.g. "calm, precise, trustworthy").
2. **Layout** — app shell (sidebar / topnav / minimal), responsive priorities.
3. **Color palette** — primary, secondary, accent; dark-mode requirement (yes/no).
4. **Typography** — font pairing, scale tightness (tight / balanced / loose),
   weight range.
5. **Radius & density** — border-radius scale, spacing density (compact / default
   / spacious).
6. **Icons** — library (`lucide-react` default, `heroicons`, `radix-icons`).
7. **Motion** — none / subtle / expressive; transition speed.
8. **Component inventory** — which shadcn components are needed (forms, tables,
   charts, dialogs, sidebars, …).
9. **Behavior patterns** — loading, error, empty states, toasts.

Resolve every ambiguity before generating the preview. Record the resolved
decisions as a **Decision Register** — Phase 7 checks the implementation against it
1:1. For each decision, record source (`user`, `codebase`, `prior-artifact`, or
`delegated-default`), selected option, rejected material alternatives, and any
safe deferral.

---

## Phase 2B — Existing Frontend Analysis (Existing mode)

Collect source material in priority order:

1. Read `components.json` (style, base color, CSS-variable mode, aliases).
2. `npx shadcn@latest info --json` for the installed component list.
3. Read `globals.css` / `app.css` for the current tokens.
4. Scan `components/` and `app/` for layout and composition patterns.
5. Accept screenshots or a verbal description when file access is unavailable.

Extract and document: existing color tokens, typography (families/sizes/weights),
radius values, which components exist and how they compose, and **inconsistencies**
(hardcoded hex, mixed spacing units, duplicate components, off-scale values).

Present a structured analysis. Confirm **what to preserve vs replace** with the
user. Only proceed to Phase 3 with explicit confirmation.

---

## Phase 3 — Token System

Write the complete CSS-variable block. The format depends on the Tailwind version
detected in Phase 1. **Never mix formats.**

### Required token set (light + dark)

`background`, `foreground`, `card`, `card-foreground`, `popover`,
`popover-foreground`, `primary`, `primary-foreground`, `secondary`,
`secondary-foreground`, `muted`, `muted-foreground`, `accent`,
`accent-foreground`, `destructive`, `destructive-foreground`, `border`, `input`,
`ring`, plus `--radius`. Add `chart-1..5` and the `sidebar-*` set when those
components are in the inventory. Every light token must have a `.dark` override.

### Tailwind v4 — OKLCH function form

In-CSS `@theme inline` block, no `tailwind.config.ts`:

```css
:root {
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --primary: oklch(0.205 0 0);
  --primary-foreground: oklch(0.985 0 0);
  --radius: 0.625rem;
  /* …all tokens */
}
.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  /* …dark overrides */
}
@theme inline {
  --color-background: var(--background);
  --color-primary: var(--primary);
  /* …map every token to a --color-* utility */
}
```

### Tailwind v3 — HSL channel form

HSL **channels only** (no `hsl(...)` wrapper), inside `@layer base`, plus a
`tailwind.config.ts` that extends `theme.colors` to read the variables:

```css
@layer base {
  :root {
    --background: 0 0% 100%;     /* H S% L% */
    --foreground: 0 0% 9%;
    --primary: 0 0% 13%;
    --radius: 0.625rem;
  }
  .dark {
    --background: 0 0% 9%;
    --foreground: 0 0% 98%;
  }
}
```

```ts
// tailwind.config.ts (v3 only)
colors: {
  background: "hsl(var(--background))",
  primary: {
    DEFAULT: "hsl(var(--primary))",
    foreground: "hsl(var(--primary-foreground))",
  },
}
```

Detect the version from `package.json` before writing. OKLCH in a v3 project, or
HSL channels in v4, both fail silently.

---

## Phase 4 — shadcn Component Template + Install

Install every component in the approved inventory in one command where possible:
`npx shadcn@latest add button input label form dialog …`. For a custom registry use
`npx shadcn@latest add @<registry>/<name>` and verify import paths match the
project's UI alias afterward.

Produce the mandatory **Component Template** section (per `design-doctrine.md`
§5), filled concretely:

```markdown
## Component Template (shadcn/ui)

**Primitives used**: [Button, Input, Form, Dialog, …]
**New components introduced**: [name + one-line purpose, or "none"]
**Token overrides**: [--primary, --radius deltas, or "defaults"]
**Variant matrix**: [per component: variants × sizes × states]
**Composition example**: [short TSX showing the primary screen composed]
**Responsive behavior**: [how it reflows across the six tiers]
**Dark mode**: [confirmed working / token deltas]
**Accessibility**: [keyboard map, ARIA, focus order, contrast verified]
```

Custom components extend shadcn primitives (Radix-based, token-driven,
variant-typed via `cva`, composed with `cn()`); they never replace them. Use
semantic token classes only (`bg-primary`, `text-muted-foreground`) — no inline
styles, no hardcoded hex.

---

## Phase 5 — Preview

Generate a single self-contained component (a design-system reference page, like
`https://ui.shadcn.com/create`) that renders:

- **Color swatches** — every token with its label (and foreground pair).
- **Typography scale** — H1–H4, body, small, muted, code with live samples.
- **Component gallery** — Button (all variants), Badge, Input, Select, Card,
  Alert, Dialog trigger, Tabs, Switch using the real shadcn imports.
- **Layout specimen** — a mini page frame showing the chosen app shell.
- **Dark-mode toggle** — all of the above in both modes.

Present it as an artifact. Ask: "Does this match the vision? Any adjustments before
I generate the full system?" Iterate as many times as needed. **Do not** generate
the final spec until the user approves with an explicit phrase ("looks good",
"approved", "generate it"). Keep a running list of confirmed deltas.

---

## Phase 6 — UI/UX Specification (`design-system.md`)

Write `design-system.md` in the project root covering:

- **Design principles** — the personality keywords and how each translates to a
  visual decision.
- **Route / screen inventory** — every route or primary screen, purpose, primary
  user, entry points, exit points, and owning component.
- **Workflow and state matrix** — loading, empty, error, success,
  permission-denied, disabled, pending mutation, optimistic update, and retry
  states per screen.
- **API / data dependency map** — screen -> endpoint/query/mutation -> cache key
  or state owner -> retry/cache/invalidations. If no API exists, state "no API
  dependency" and name the local/static data source.
- **Forms and validation** — field-level client validation, server validation,
  error placement, destructive confirmation, success feedback, and reset/undo
  behavior.
- **Color system** — every token, its semantic meaning, and its measured contrast
  ratio (real numbers, not placeholders).
- **Typography** — families, a scale table (size / weight / line-height per level),
  usage rules.
- **Spacing & layout** — density setting, grid, common gap/padding values from the
  doctrine spacing scale.
- **Component catalog** — every installed component with allowed variants,
  composition rules, and do/don't examples.
- **Motion** — easing functions, duration scale, which interactions animate;
  `prefers-reduced-motion` behavior.
- **Accessibility** — contrast table, keyboard navigation, focus-visible spec,
  minimum tap target.
- **Dark mode** — toggle mechanism and any manual overrides.
- **Responsive evidence** — expected layout behavior and state coverage at small
  mobile, mobile, tablet, desktop, large desktop, and ultrawide tiers.
- **Text fit and stable layout** — long labels, narrow controls,
  localization-sensitive strings, empty/error copy, fixed-format components, and
  any min/max/aspect-ratio constraints that prevent layout shift.
- **Handoff notes** — how to install, add a component, update tokens, add a
  route, and connect a screen to its API contract.

---

## Phase 7 — Adversarial Design Review

After Phases 3–6 the work is *generated* but not *audited*. Run a hostile review
pass before declaring done. Score **eight dimensions 0–10**:

1. **Token integrity** — every token used in components is declared in `:root`; no
   hardcoded hex/hsl/rgb leaked into generated `.tsx`.
2. **Dark-mode parity** — every light token has a `.dark` override; contrast holds
   in both modes.
3. **WCAG contrast** — `foreground/background`, `primary-foreground/primary`,
   `muted-foreground/muted`, `destructive-foreground/destructive` all meet AA
   (4.5:1 body, 3:1 large/UI). Compute with the formula below — never eyeball.
4. **Component coverage** — every inventory component is actually installed
   (`info --json` lists it); every previewed component imports from the project's
   UI alias.
5. **Framework alignment** — token format matches the Tailwind major version (v4 →
   OKLCH + `@theme inline`; v3 → HSL channels + matching `tailwind.config.ts`).
6. **Spec completeness** — `design-system.md` has a catalog entry per installed
   component, route/screen inventory, workflow/state matrix, API/data dependency
   map, form validation behavior, responsive evidence for all six tiers, real
   contrast numbers, text-fit/stable-layout checks, and token values matching
   `globals.css` exactly.
7. **Accessibility scaffolding** — `prefers-reduced-motion` present; `ring`/focus
   tokens defined; minimum tap target documented; icon-only buttons paired with
   `aria-label` in examples.
8. **Decision traceability** — the Phase 2 decision record maps 1:1 onto the
   implemented tokens, fonts, and components. No silent overrides.

### Run order

1. Walk all eight dimensions, scoring each with evidence (severity + location + fix).
2. **Auto-fix every critical/major finding** — never hand the user a broken system:
   - hardcoded hex in a component → replace with the matching semantic class;
   - missing `.dark` override → add it from shadcn's standard dark palette, then
     flag for tuning;
   - failing contrast → adjust the L channel of the offending token by ±0.05 (OKLCH)
     or ±the equivalent L% (HSL) and re-check until ≥ AA.
3. Re-run until **all eight dimensions ≥ 9** and zero critical findings remain.
4. Present the final scorecard with the generated files. Be honest about any 8/10
   or 9/10 findings the user may want to polish — a 9/10 with one tracked finding is
   more honest than a padded 10/10.

### When to stop

- All dimensions 10/10, **or**
- All ≥ 9 and the user accepts the remaining minor findings, **or**
- A score plateaus for two iterations with the same finding — surface the blocker
  (usually ambiguous intent or a hex the user insists on keeping) and ask whether to
  ship as-is or revise upstream.

### WCAG contrast formula

For each channel `c` in {R, G, B} as an 8-bit value, let `s = c / 255`, then:

```
linear(s) = s / 12.92                         if s ≤ 0.03928
linear(s) = ((s + 0.055) / 1.055) ^ 2.4       otherwise

L = 0.2126·linear(R) + 0.7152·linear(G) + 0.0722·linear(B)

contrast = (L_lighter + 0.05) / (L_darker + 0.05)
```

Convert OKLCH/HSL tokens to sRGB first, then apply the formula. AA requires
contrast ≥ 4.5 for body text and ≥ 3.0 for large text (≥ 24px, or ≥ 18.66px bold)
and UI component boundaries.

---

## Edge cases & failure modes

| Scenario | Response |
|---|---|
| Framework not detected | Ask explicitly; never guess. A wrong runner corrupts `package.json`. |
| `components.json` already exists | Skip `init`; run `info --json`. Offer to merge approved tokens rather than overwrite. |
| Dark-mode tokens unspecified | Default to shadcn's standard dark palette; note in the spec that manual tuning may be needed. |
| Existing project with hardcoded colors | Flag every `text-gray-*`, `bg-white`, `border-black` as a migration candidate; present the list and confirm before touching files. |
| User approves then changes mind mid-generation | Stop at the next file boundary, present what exists, re-enter Phase 5 with confirmed deltas. |
| User contradicts an earlier interview answer | Call out the contradiction explicitly and update the decision record before proceeding. Never silently overwrite a recorded decision. |
| Contrast fails in Phase 7 | Do not lower the requirement. Adjust the L channel in ±0.05 steps, re-check, and surface the change with a one-line rationale. If three steps miss AA, ask whether to revise the palette or accept AAA-only-on-large-text. |
| Custom / private registry | Use `npx shadcn@latest add @<registry>/<name>`; verify import paths match the UI alias after install. |
