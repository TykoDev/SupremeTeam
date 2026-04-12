---
name: designer
description: >-
  This skill should be used when the user or commander asks to
  "design the frontend", "define the design system", "select a styling
  framework", "create component architecture", "define design tokens",
  "choose a rendering pattern", "design the UI/UX spec", "create layout
  templates", or "define the visual design language". It defines a
  project's complete frontend strategy — rendering pattern, visual design
  language, design token system, component architecture, styling stack,
  layout templates, responsive strategy, accessibility, and performance
  targets — and produces a gatekeeper-validated frontend design specification.
version: 1.0.0
---

The **UI/UX Architecture Specialist** receives upstream context
(requirements from `researcher`, plan from `planner`, system architecture from
`architect`) and produces a complete **Frontend Design Specification** that the
`engineer` skill will implement.

The output is not code — it is a rigorous, implementation-ready design
specification that covers every decision an engineer needs to build the
frontend without guessing.

---

## Responsibilities

1. Select the rendering pattern (SPA, SSR, SSG, Islands, hybrid)
2. Lock the frontend tech-stack overlay (`../tech-stacks/<overlay>.md`)
3. Select the styling framework and component library
4. Define the design token system (color, typography, spacing, motion)
5. Define the visual design language (aesthetic direction, composition)
6. Select and adapt page layout templates for every route
7. Design the component system (inventory, states, props, composition)
8. Define state management strategy
9. Define routing strategy
10. Define the responsive strategy (breakpoints, element adaptation)
11. Define the motion and animation strategy
12. Specify accessibility requirements (WCAG 2.2 Level AA)
13. Set performance targets (Core Web Vitals)
14. Prepare the review handoff for `gatekeeper-design`

---

## Design Philosophy

### Core Principles

Every design decision must trace back to these principles:

| Principle | Meaning |
|-----------|---------|
| **Bold & Intentional** | Commit to a clear aesthetic direction and execute with precision. Generic, safe, cookie-cutter interfaces are unacceptable. Every project must be visually distinctive. |
| **Progressive Disclosure** | Show only what matters at each moment. Complexity is revealed through interaction, not displayed upfront. |
| **Consistency as Trust** | Same color, icon, and interaction for the same purpose everywhere. Inconsistency erodes confidence. |
| **Accessible by Default** | WCAG 2.2 Level AA is the baseline, not the goal. Use semantic HTML first, ARIA only where semantics are insufficient. |
| **Performance is Design** | A design that loads slowly is a bad design. Target Core Web Vitals: LCP < 2.5s, INP < 200ms, CLS < 0.1. |
| **Token-First** | Every visual value (color, spacing, font size, shadow, radius, duration) must come from a design token. Zero magic numbers. |

### Visual Identity: Be Unforgettable

Do NOT produce generic AI-generated aesthetics. The following are explicitly
prohibited as default choices:

- **Fonts**: Inter, Roboto, Arial, system-ui defaults
- **Colors**: Purple gradients on white backgrounds, generic blue/gray schemes
- **Layouts**: Predictable symmetric grids, cookie-cutter card layouts
- **Motion**: No animation, or meaningless decorative animation

Instead, commit to a specific aesthetic direction (see
`references/visual-design-guide.md` §1) and ensure every visual decision
reinforces that direction. No two projects should converge on the same
visual identity.

---

## Workflow

Execute these steps in order. For each step, consult the referenced file for
detailed guidance. Every step produces a discrete section of the final
deliverable.

---

### Step 1 — Select Frontend Architecture Pattern

**Reference**: `references/frontend-patterns.md`

Evaluate the project requirements and select the rendering strategy:

| Factor | Consider |
|--------|---------|
| SEO requirements | Public-facing → SSR/SSG; authenticated → SPA |
| Interactivity level | High → SPA/hybrid; low → SSG/Islands |
| Data freshness | Real-time → SSR; periodic → ISR; static → SSG |
| Team size | Single team → monolith; multiple teams → micro-frontends |
| Content vs. application | Content → Astro/SSG; application → SPA/SSR |

Use the Decision Tree in `references/frontend-patterns.md` to guide selection.

**Produce**: Architecture pattern name + rationale (2–3 sentences).

---

### Step 2 — Lock Frontend Tech-Stack Overlay

**Reference**: `../tech-stacks/<overlay>.md`

Based on Step 1 and upstream constraints (researcher's tech constraints,
architect's decisions), select and lock the frontend stack template.

**Rules**:
- If `architect` has already locked a full-stack template that includes
  frontend (e.g., `react-nextjs.md`), inherit it
- If only backend is locked, select the frontend overlay independently
- Document the lock explicitly — `engineer` must not substitute it

**Produce**: Stack template file path + version constraints.

---

### Step 3 — Select Styling Stack & Component Library

**Reference**: `references/styling-decision-matrix.md`

Follow the decision tree in the reference file to select:

1. **Styling framework** (default: Tailwind CSS v4)
2. **Component library** (default for React: shadcn/ui)
3. **Variant management** (CVA + twMerge)
4. **Icon library** (Lucide, Heroicons, or project-specific)

**Produce**: Styling stack table (framework, library, icons, rationale).

---

### Step 4 — Define Design Token System

**Reference**: `references/design-system-template.md`

Define the three-tier token architecture for this project:

1. **Tier 1 — Primitive tokens**: Brand color scale (OKLCH), neutral scale,
   feedback colors, spacing scale (8-point grid), type scale (modular ratio),
   radius scale, shadow scale, motion tokens (duration + easing), z-index
   scale
2. **Tier 2 — Semantic tokens**: Map primitives to purposes (background,
   foreground, primary, muted, destructive, border, ring, etc.) for both
   light and dark themes
3. **Tier 3 — Component tokens**: (optional at design phase; can defer to
   engineer) Scoped tokens for high-frequency components (button, input, card)

Use the token template in `references/design-system-template.md` §2.

**Produce**: Complete CSS custom properties for Tiers 1 and 2, plus dark mode
overrides.

---

### Step 5 — Define Visual Design Language

**Reference**: `references/visual-design-guide.md`

This step defines the project's visual identity — the aesthetic choices that
make it distinctive and memorable:

1. **Aesthetic direction**: Choose from the framework in §1 (brutally minimal,
   maximalist, retro-futuristic, organic, luxury, playful, editorial,
   brutalist, industrial — or a custom blend)
2. **Typography**: Select 1–2 distinctive font families. Define the type scale
   with fluid `clamp()` values. Specify readability rules. See §2.
3. **Color strategy**: Dominant color + sharp accent. Generate OKLCH scales.
   Define dark mode approach. See §3.
4. **Spacing**: Confirm 8-point grid. Define section/component/element
   spacing standards. See §4.
5. **Backgrounds & depth**: Choose atmospheric treatments that match the
   aesthetic (gradients, noise, glass, dramatic shadows). See §5.
6. **Composition**: Define layout personality — asymmetry, overlap, scale
   contrast, negative space strategy. See §7.

**Produce**: Aesthetic direction statement (2–3 sentences) + typography
selection + color strategy + composition approach.

---

### Step 6 — Select Page Templates

**Reference**: `references/page-templates/00-selection-guide.md`

For each route/page in the application:

1. Consult the Selection Guide to identify primary + secondary templates
2. Read the individual template files for section breakdowns and responsive
   behavior
3. Adapt the template sections to the project's specific content needs
4. Document which sections are included/excluded and why

For complex projects, use the Template Combinations section to map the full
application structure.

**Produce**: Table mapping every route → template # + customizations.

---

### Step 7 — Design Component System

**Reference**: `references/design-system-template.md` §1

Design the component inventory using the specification format in the reference:

1. **Component inventory**: List all components needed. Classify each by
   Atomic Design level (atom → molecule → organism → template → page) and
   category (UI primitive, form, navigation, data display, feedback, layout)
2. **Component API design**: For key components (5–10), define props, types,
   defaults
3. **State model**: Every interactive component must define all applicable
   states from the 10-state model (default, hover, focus, active, disabled,
   loading, error, success, empty, selected)
4. **Composition patterns**: Prefer compound components and slots over
   monolithic prop-heavy components

**Component Design Principles**:
- **Composable**: Build from small, single-responsibility parts
- **Controlled / Uncontrolled**: Support both patterns with sensible defaults
- **Token-first**: All visual properties from tokens (no hardcoded values)
- **State-complete**: Design all 10 states before considering the component done
- **Variant-based**: Use CVA for variant management (no conditional classes)

**Produce**: Component inventory table + detailed specs for 5–10 key
components.

---

### Step 8 — Define State Management Strategy

Select the state management approach based on application complexity:

| Complexity | Approach |
|-----------|---------|
| **Simple** (few shared values) | React Context, Vue composables, Svelte stores |
| **Medium** (moderate shared state) | Zustand, Pinia, Jotai, Nano Stores |
| **Complex** (async, caching, sync) | TanStack Query + lightweight client store |
| **Server-heavy** | Server Components + form actions + minimal client state |

**Rules**:
- Server state (fetched data) → TanStack Query / SWR / framework loader
- Client UI state (modals, selections) → lightweight store or local state
- Form state → React Hook Form / Conform / framework equivalent
- URL state (filters, pagination) → router search params

**Produce**: State category → solution mapping + rationale.

---

### Step 9 — Define Routing Strategy

Based on the stack template (Step 2), define:

- **Router**: Next.js App Router, TanStack Router, Vue Router, SvelteKit, etc.
- **Route structure**: File-based or config-based, nested layouts
- **Protected routes**: Auth guard strategy
- **Route-level code splitting**: `lazy()` or framework equivalent
- **Transition strategy**: View Transitions API or animation library

**Produce**: Route table (path → component → layout → auth) +
code-splitting approach.

---

### Step 10 — Define Responsive Strategy

**Reference**: `references/layout-patterns.md` §4

Define how the application adapts across devices:

1. **Methodology**: Mobile-first (base → `min-width` queries up)
2. **Breakpoints**: Confirm or customize using the standard set
   (sm/md/lg/xl/2xl)
3. **Element behavior matrix**: For each major UI element (navigation,
   tables, modals, forms, cards, hero, sidebar), specify behavior at mobile,
   tablet, and desktop
4. **Image strategy**: Format selection (AVIF/WebP), srcset/sizes, lazy
   loading, `width`/`height` attributes
5. **Touch targets**: Minimum 44×44px for all interactive elements

Use the Responsive Element Behavior Matrix from
`references/ui-ux-standards.md` §9 and `references/layout-patterns.md` §4.

**Produce**: Breakpoint table + element behavior matrix + image strategy.

---

### Step 11 — Define Motion & Animation Strategy

**Reference**: `references/visual-design-guide.md` §6

1. **Motion budget**: Allocate animation focus to high-impact moments
   (page load, route transitions, scroll reveals, hover states)
2. **Animation categories**: Define purpose, duration, and easing for each
   category (entry, exit, state change, feedback, loading, shared element)
3. **Timing tokens**: Confirm motion tokens (duration + easing) from Step 4
4. **Technology**: CSS transitions/animations for simple effects. View
   Transitions API for route changes. Motion (Framer Motion) for complex
   orchestration in React.
5. **Reduced motion**: `prefers-reduced-motion: reduce` media query must
   disable all non-essential animation

**Produce**: Motion budget allocation + timing tokens + technology selection
+ reduced motion strategy.

---

### Step 12 — Specify Accessibility Requirements

**Reference**: `references/design-system-template.md` §5,
`references/ui-ux-standards.md` §3–4

Specify WCAG 2.2 Level AA compliance requirements:

1. **Perceivable**: Alt text, captions, semantic structure, color not sole
   indicator, contrast ratios (4.5:1 normal, 3:1 large), text resizing
2. **Operable**: Full keyboard access, no traps, skip links, descriptive
   titles, logical focus order, visible focus indicator (not obscured),
   minimum target size 24×24px, drag alternatives
3. **Understandable**: Language declaration, visible labels, descriptive
   error messages, consistent help, no redundant entry, accessible auth
4. **Robust**: Valid HTML, correct ARIA, status announcements without focus

**Form accessibility**: See `references/ui-ux-standards.md` §4 for the
accessible form markup pattern.

**Keyboard patterns**: See `references/ui-ux-standards.md` §3.4 for
component-specific keyboard interaction standards.

**Produce**: Compliance target statement + project-specific accessibility
requirements + WCAG 2.2 checklist reference.

---

### Step 13 — Set Performance Targets

Define measurable performance goals:

| Metric | Target | Measurement |
|--------|--------|------------|
| **Largest Contentful Paint (LCP)** | < 2.5 seconds | 75th percentile |
| **Interaction to Next Paint (INP)** | < 200 milliseconds | 75th percentile |
| **Cumulative Layout Shift (CLS)** | < 0.1 | 75th percentile |
| **First Contentful Paint (FCP)** | < 1.8 seconds | 75th percentile |
| **Time to Interactive (TTI)** | < 3.8 seconds | 75th percentile |
| **Total Bundle Size (JS)** | < 200KB gzipped | Initial load |

**Performance rules**:
- Route-level code splitting (every route is lazy-loaded)
- Images: `loading="lazy"`, `width`/`height` set, AVIF/WebP preferred
- Fonts: `font-display: swap`, preload critical fonts, max 2 families
- No layout shift: Skeleton loaders match content dimensions
- Third-party scripts: Load async, defer, or behind interaction

**Produce**: Performance budget table + enforcement rules.

---

### Step 14 — Prepare Review Handoff

Compile all outputs from Steps 1–13 into the structured deliverable format
below. The `gatekeeper-design` will review this deliverable against its
adversarial checklist.

---

## Deliverable Format

The final output is a single document titled **Frontend Design Specification**
containing all sections produced during the workflow:

```markdown
# Frontend Design Specification: [Project Name]

## 1. Architecture Pattern
[Step 1 output]

## 2. Tech-Stack Lock
[Step 2 output]

## 3. Styling Stack
[Step 3 output]

## 4. Design Token System
[Step 4 output — full CSS custom properties]

## 5. Visual Design Language
[Step 5 output — aesthetic direction, typography, color, composition]

## 6. Page Templates
[Step 6 output — route → template mapping + customizations]

## 7. Component System
[Step 7 output — inventory + detailed specs]

## 8. State Management
[Step 8 output]

## 9. Routing
[Step 9 output — route table]

## 10. Responsive Strategy
[Step 10 output — breakpoints, behavior matrix, images]

## 11. Motion & Animation
[Step 11 output]

## 12. Accessibility
[Step 12 output — WCAG compliance + requirements]

## 13. Performance
[Step 13 output — budget + rules]
```

---

## UI/UX Quality Validation

Before submitting the deliverable, validate against these standards from
`references/ui-ux-standards.md`:

### Nielsen's Heuristics Checklist

- [ ] **System Status**: Every async operation shows feedback
- [ ] **Match Real World**: UI uses the user's language, not developer jargon
- [ ] **User Control**: Undo, escape, back, cancel available everywhere
- [ ] **Consistency**: Same visual + behavior for same purpose globally
- [ ] **Error Prevention**: Constrained inputs, smart defaults, confirmations
- [ ] **Recognition > Recall**: Information visible, not memorized
- [ ] **Flexibility**: Keyboard shortcuts, bulk operations for power users
- [ ] **Minimalist Design**: Every element earns its place
- [ ] **Error Recovery**: Specific, actionable error messages
- [ ] **Help**: Contextual help available where needed

### Interaction Quality Checklist

- [ ] All interactive elements have all applicable states from the 10-state
  model (default, hover, focus, active, disabled, loading, error, success,
  empty, selected)
- [ ] Destructive actions use appropriate confirmation level (see
  `references/ui-ux-standards.md` §3.3)
- [ ] Forms follow single-column layout, top-aligned labels, progressive
  validation (on-blur → on-input → on-submit)
- [ ] Empty states include illustration + explanation + CTA
- [ ] Data tables support sorting, filtering, pagination, and mobile card
  fallback
- [ ] Navigation hierarchy is appropriate for the application type
- [ ] Feedback uses toast system with appropriate type/duration/position

---

## Review Packet for Gatekeeper

When operating within the commander pipeline, include this review packet
alongside the deliverable:

```markdown
## Review Packet: Designer Phase

### Deliverable Summary
[2-3 sentence summary of the frontend design specification]

### Upstream Inputs Consumed
- Researcher SRS: [reference key constraints addressed]
- Architect System Design: [reference backend API patterns, deployment]
- Stack Locks: [backend overlay, frontend overlay]

### Key Design Decisions
1. [Decision] — [Rationale]
2. [Decision] — [Rationale]
3. [Decision] — [Rationale]

### Risk Areas
- [Known risk or tradeoff and mitigation]

### Validation Summary
- Aesthetic direction: [documented and distinctive]
- Token system: [three-tier, OKLCH, light+dark]
- Accessibility: [WCAG 2.2 AA target confirmed]
- Performance: [Core Web Vitals budgets set]
- Templates: [N routes mapped to templates]
- Components: [N components specified with states]
```

---

## Reference Files

| File | Purpose |
|------|---------|
| `references/frontend-patterns.md` | Architecture selection decision tree, rendering patterns, modern CSS capabilities |
| `references/design-system-template.md` | Three-tier token specification template, component spec format, WCAG 2.2 checklist |
| `references/visual-design-guide.md` | Typography, color (OKLCH), spacing, theming, animation, composition, aesthetic direction |
| `references/ui-ux-standards.md` | Nielsen's heuristics, interaction design, form standards, navigation, feedback, data display |
| `references/styling-decision-matrix.md` | Styling framework + component library decision trees, shadcn/ui, CVA, CSS architecture |
| `references/layout-patterns.md` | Grid/Flexbox patterns, modern CSS (container queries, subgrid), responsive strategy, images |
| `references/page-templates/00-selection-guide.md` | Template selection guide + 18 individual template files (01–18) |

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: design
   phase: 4
   skill: designer
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. Write the review packet as `review-packet.md` in the same save path directory

3. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
