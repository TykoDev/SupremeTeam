---
name: designer
description: >-
  This skill should be used when the user asks to "design the frontend",
  "define the design system", "select a styling framework", "create
  component architecture", "define design tokens", "choose a rendering
  pattern", "define the visual design language", "set up the UI
   framework", "spec the UI", "plan the app shell", "pick a component
   library", or "what should the frontend look like?". Defines the
   complete frontend strategy — rendering pattern, design tokens,
   component architecture, styling stack, layout templates, responsive
   strategy, accessibility targets, and performance budgets — so the
   implementation team can build the frontend without guessing.
  DO NOT USE for backend architecture (use architect). DO NOT USE
  for implementation code (use bob-the-builder). DO NOT USE for
  visual QA of existing implementations (use design-qa).
version: 1.0.0
---

# Designer — Frontend Architecture & Design Specialist

## Purpose

Receive upstream context (requirements from `researcher`, plan from `planner`,
system architecture from `architect`) and produce a complete **Frontend Design
Specification** that the `engineer` skill will implement without guessing.

Do not produce code. Lock the frontend strategy, token model, layout system,
interaction rules, accessibility requirements, and performance constraints
needed to build a reviewable frontend implementation.

Cover the full frontend specification, from rendering pattern and stack lock
through tokens, layouts, components, accessibility, performance targets, and
the final handoff to `gatekeeper-design`.

---

## Design Philosophy

Use `references/design-philosophy.md` to choose and defend the visual
direction. The non-negotiables are simple: commit to a distinctive aesthetic,
enforce WCAG 2.2 AA and Core Web Vitals as hard constraints, and keep all
visual decisions token-first instead of falling back to generic defaults.

Apply the adversarial anti-gaming framework from `../../references/universal-frameworks.md`
to frontend decisions. Reject generic filler choices, placeholder layouts, and
scope cuts disguised as minimalism when they are really unresolved design work.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

---

## Workflow

Execute these steps in order. For each step, consult the referenced file for
detailed guidance. Every step produces a discrete section of the final deliverable.

Before beginning Step 1, validate upstream deliverables: confirm the researcher
SRS contains functional requirements, NFRs, and technology constraints; confirm
the architect's system architecture includes the backend stack lock and API
contracts. If any required input is missing or contradictory, stop and escalate
to commander because unvalidated upstream gaps propagate as silent design drift.

---

### Step 1 — Select Frontend Architecture Pattern

**Reference**: `references/frontend-patterns.md`

Evaluate the project requirements and select the rendering strategy:

| Factor | Consider |
|--------|---------|
| SEO requirements | Public-facing → SSR/SSG; authenticated → SPA |
| Interactivity | High → SPA/hybrid; low → SSG/Islands |
| Data freshness | Real-time → SSR; periodic → ISR; static → SSG |
| Team size | Single → monolith; multiple → micro-frontends |
| Content vs app | Content → Astro/SSG; application → SPA/SSR |

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

Mini example of the expected hierarchy:
- primitive: `--color-sage-500`
- semantic: `--color-primary`
- component: `--button-primary-bg`

**Worked example — token resolution for a primary button:**
A designer receives a project with brand color Sage and needs to specify the
primary button’s background. The resolution chain:
1. Define primitive: `--color-sage-500: oklch(0.55 0.15 155)` in the global scale
2. Map semantic: `--color-primary: var(--color-sage-500)` (light), `--color-primary: var(--color-sage-400)` (dark)
3. Bind component: `--button-primary-bg: var(--color-primary)` in the Button spec
4. Hover state: `--button-primary-bg-hover: var(--color-sage-600)` (one stop darker)
5. Engineer implements `<Button variant="primary">` resolving `bg-[var(--button-primary-bg)]`

If the brand later changes from Sage to Indigo, only Tier 1 primitives
update — semantic and component tokens resolve automatically.

**Produce**: Complete CSS custom properties for Tiers 1 and 2, plus dark mode
overrides.

---

### Step 5 — Define Visual Design Language

**Reference**: `references/visual-design-guide.md`

Define the project's visual identity using the reference framework:

1. Choose the aesthetic direction and typography system — align with the
   brand brief or, for greenfield projects, with the target audience's
   expectations (enterprise → restrained, consumer → expressive)
2. Lock color, spacing, depth, and dark-mode strategy — every value MUST
   resolve to a Tier 1 primitive token from Step 4 because unlinked values
   bypass the token system and break theme switching
3. Define composition rules, contrast, and negative-space behavior — set
   minimum contrast ratios that satisfy the WCAG targets from Step 12

**Produce**: A short aesthetic direction statement plus the final typography,
color, and composition choices.

---

### Step 6 — Select Page Templates

**Reference**: `references/page-templates/00-selection-guide.md`

Treat `references/page-templates/` as a numbered template library. Always
start with `00-selection-guide.md`, then read the exact numbered template files listed in
the Reference Files section for every route you select. Do not invent a new
template structure when an existing library template already matches the page
intent, because the selection guide is the authoritative entry point for
matching route intent to the existing template library and reusing the library
preserves consistency across layouts, responsive behavior, and interaction
patterns.

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

Design the component inventory using the reference format:

1. List the required components and classify them by Atomic Design level and category
2. Specify props, defaults, and composition rules for the highest-value components
3. Define the full 10-state model for every interactive component
4. Keep component APIs composable, token-first, and variant-driven

**Produce**: A component inventory table plus detailed specs for 5–10 key components.

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
2. **Breakpoints**: Confirm or customize the standard set (sm/md/lg/xl/2xl)
3. **Element behavior matrix**: For each major UI element, specify behavior at mobile, tablet, and desktop
4. **Image strategy**: Format selection (AVIF/WebP), srcset/sizes, lazy loading, dimensions
5. **Touch targets**: Minimum 44×44px for all interactive elements

Use the Responsive Element Behavior Matrix from `references/ui-ux-standards.md` §9 and `references/layout-patterns.md` §4.

**Produce**: Breakpoint table + element behavior matrix + image strategy.

---

### Step 11 — Define Motion & Animation Strategy

**Reference**: `references/visual-design-guide.md` §6

1. Allocate animation focus to high-impact moments (page load, route transitions, scroll reveals, hover states)
2. Define purpose, duration, and easing for each animation category (entry, exit, state change, feedback, loading, shared element) using motion tokens from Step 4
3. Select technology: CSS transitions for simple effects, View Transitions API for route changes, Motion library for complex orchestration
4. Enforce `prefers-reduced-motion: reduce` to disable all non-essential animation — this is non-negotiable for WCAG compliance

**Produce**: Motion budget allocation + timing tokens + technology selection
+ reduced motion strategy.

---

### Step 12 — Specify Accessibility Requirements

**Reference**: `references/design-system-template.md` §5,
`references/ui-ux-standards.md` §3–4

Specify WCAG 2.2 Level AA compliance across four principles:

1. **Perceivable**: Alt text, captions, semantic structure, contrast ratios (4.5:1 / 3:1), color not sole indicator
2. **Operable**: Full keyboard access, no traps, skip links, visible focus, min target 24×24px, drag alternatives
3. **Understandable**: Language declaration, visible labels, descriptive errors, consistent help, accessible auth
4. **Robust**: Valid HTML, correct ARIA, status announcements without focus

Consult `references/ui-ux-standards.md` §3.4 for keyboard interaction standards and §4 for accessible form markup.

**Produce**: Compliance target statement + project-specific accessibility
requirements + WCAG 2.2 checklist reference.

---

### Step 13 — Set Performance Targets

Define measurable performance goals:

| Metric | Target | Measurement |
|--------|--------|------------|
| **Largest Contentful Paint (LCP)** | < 2.5s | 75th percentile |
| **Interaction to Next Paint (INP)** | < 200ms | 75th percentile |
| **Cumulative Layout Shift (CLS)** | < 0.1 | 75th percentile |
| **First Contentful Paint (FCP)** | < 1.8s | 75th percentile |
| **Time to Interactive (TTI)** | < 3.8s | 75th percentile |
| **Total Bundle Size (JS)** | < 200KB gzipped | Initial load |

**Performance rules**:
- Route-level code splitting (every route is lazy-loaded)
- Images: `loading="lazy"`, `width`/`height` set, AVIF/WebP preferred
- Fonts: `font-display: swap`, preload critical fonts, max 2 families
- No layout shift: Skeleton loaders match content dimensions
- Third-party scripts: Load async, defer, or behind interaction

Validate the visual system against these budgets before handoff. Do not approve
heavy motion, oversized type scales, or token choices that clearly violate the
stated performance targets.

**Produce**: Performance budget table + enforcement rules.

---

### Step 14 — Prepare Review Handoff

Compile Steps 1–13 into the structured deliverable below. Gatekeeper-design will review against its adversarial checklist.

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

Confirm the deliverable satisfies Nielsen's heuristics, complete 10-state
coverage for interactive elements, appropriate confirmation levels for
destructive actions, modern form and empty-state patterns, responsive data
display fallbacks, sensible navigation hierarchy, and clear feedback behavior.
Document any deliberate exceptions with rationale.

---

## Review Packet for Gatekeeper

When operating within the commander pipeline, include this review packet
alongside the deliverable:

```markdown

---

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

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No existing design system or brand guidelines | Create the design system from scratch using the 3-tier token system. Document all aesthetic decisions and their rationale. This is the expected path for greenfield projects. |
| Backend-only project (no frontend) | Skip the designer phase entirely. Return "Not applicable — no frontend in scope" to commander. |
| Existing design system that conflicts with best practices | Respect the existing system as a constraint. Document each concrete conflict, explain whether it is retained or normalized, recommend incremental improvements, and identify which legacy patterns are frozen versus which can be migrated safely. Do not override established design tokens without an explicit approved exception. |
| Upstream stack lock conflicts with the preferred frontend choice | Treat the approved stack lock as binding. Document the conflict, explain the design tradeoff, and propose any change as an explicit exception for commander and architect review instead of silently switching frameworks. |
| Accessibility requirements exceed WCAG AA | Elevate the target to the specified level (e.g., AAA). Adjust color contrast ratios, font sizes, and interactive targets accordingly. Document the elevated requirements. |
| Mobile-first vs. desktop-first ambiguity | Default to mobile-first (progressive enhancement). If the user specifies desktop-first, document the choice and adjust breakpoint strategy. |
| Animation/motion requirements conflict with accessibility | Respect `prefers-reduced-motion`. All animations must have a reduced-motion fallback. This is non-negotiable for WCAG compliance. |
| Existing frontend needs refactoring rather than net-new design | Extract the current token system, component patterns, and routing model first. Preserve stable user-facing conventions, then document which parts are retained, replaced, or normalized in the new specification. |
| Brand guidelines specify contrast ratios below WCAG AA | WCAG AA is non-negotiable. Document the conflict, propose the closest brand-compliant colors that meet AA contrast (4.5:1 for text, 3:1 for large text), and escalate the trade-off to the user for explicit approval. Never ship below AA. |

---

## Reference Files

| File | Purpose |
|------|---------|
| `references/frontend-patterns.md` | Rendering pattern decision tree |
| `references/design-system-template.md` | Token template and component spec format |
| `references/design-philosophy.md` | Visual principles and prohibited defaults |
| `references/visual-design-guide.md` | Typography, color, spacing, composition |
| `references/ui-ux-standards.md` | Heuristics, forms, feedback, data display |
| `references/styling-decision-matrix.md` | Styling stack and component library choices |
| `references/layout-patterns.md` | Layout, responsive, and image rules |
| `references/page-templates/00-selection-guide.md` | Template selection and page mapping |
| `references/page-templates/01-marketing-landing.md` | Hero-led landing page template for marketing and product launches |
| `references/page-templates/02-saas-product.md` | Authenticated SaaS product shell with workspace navigation |
| `references/page-templates/03-documentation.md` | Documentation and knowledge-base template |
| `references/page-templates/04-admin-dashboard.md` | Admin dashboard layout and dense management workflows |
| `references/page-templates/05-analytics.md` | Analytics-heavy reporting and insights template |
| `references/page-templates/06-ecommerce-product.md` | Product detail and conversion-focused commerce template |
| `references/page-templates/07-blog.md` | Editorial and blog-oriented reading template |
| `references/page-templates/08-portfolio.md` | Portfolio and showcase template |
| `references/page-templates/09-pricing.md` | Pricing comparison and plan-selection template |
| `references/page-templates/10-authentication.md` | Sign-in, sign-up, and recovery-flow template |
| `references/page-templates/11-settings.md` | Settings and account-management template |
| `references/page-templates/12-data-table.md` | Data-table-heavy operational workspace template |
| `references/page-templates/13-chat.md` | Chat and conversational workspace template |
| `references/page-templates/14-file-manager.md` | File manager and content-browser template |
| `references/page-templates/15-calendar.md` | Calendar and scheduling template |
| `references/page-templates/16-multi-step-wizard.md` | Multi-step workflow and onboarding wizard template |
| `references/page-templates/17-error-pages.md` | Empty, error, and fallback-state templates |
| `references/page-templates/18-email-template.md` | Product email and notification template |
| `../../references/universal-frameworks.md` | Shared cross-cutting frameworks for adversarial anti-gaming, debugging, build quality, and deployment assumptions |

---

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

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
