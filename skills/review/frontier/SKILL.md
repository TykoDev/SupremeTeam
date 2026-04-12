---
name: frontier
description: >-
  This skill should be used when the user asks to "review the frontend",
  "audit UI/UX", "check web performance", "test accessibility",
  "review Core Web Vitals", "check frontend security", "audit CSS/HTML",
  "review component architecture", "check WCAG compliance",
  "run frontier", "assess frontend quality", or wants comprehensive
  frontend-specific code review covering performance, accessibility,
  security, and UI/UX best practices.
version: 1.0.0
---

# Frontier — Frontend Analytics & UI/UX Audit Specialist

## Purpose

This skill performs comprehensive frontend-specific code review across five audit domains: performance, accessibility, frontend security, component architecture, and UI/UX quality. It goes significantly deeper on web frontend concerns than the generalist review skills can, applying current industry standards (Core Web Vitals 2025, WCAG 2.2, CSP Level 3) and frontend-specific testing methodologies.

Where `code-review` touches frontend concerns superficially across 8 dimensions, and `security-review` covers general web security patterns, frontier provides deep specialist analysis of how the frontend code affects real users — their performance experience, their ability to access the application, and their safety from client-side attacks.

## Differentiation

| Aspect | code-review | security-review | frontier |
|--------|-------------|----------------|----------|
| **Performance** | Flags obvious issues | N/A | Core Web Vitals audit, bundle analysis, performance budgets |
| **Accessibility** | Basic check | N/A | Full WCAG 2.2 Level AA compliance audit |
| **Frontend Security** | Style/formatting | XSS, CSRF (general) | CSP evaluation, Trusted Types, DOM-based XSS, SRI, prototype pollution |
| **Component Quality** | Design dimension | N/A | State management, render efficiency, error boundaries, component patterns |
| **UI/UX** | N/A | N/A | Responsive design, interaction patterns, loading/error/empty states |

---

## Frontend Audit Workflow

### Step 1: Technology Detection

Before auditing, identify the frontend stack:

- **Framework**: React, Vue, Angular, Svelte, SolidJS, Astro, vanilla JS, or multi-framework
- **Build tool**: Webpack, Vite, Rollup, Rolldown, Rspack, esbuild, Parcel, Turbopack
- **CSS approach**: Vanilla CSS, Tailwind, CSS Modules, CSS-in-JS, SCSS/SASS, Styled Components
- **State management**: Redux, Zustand, Pinia, MobX, Jotai, Context API, signals, none
- **Testing stack**: Vitest, Jest, Playwright, Cypress, React Testing Library, Storybook
- **Rendering strategy**: CSR, SSR, SSG, ISR, streaming SSR, hybrid

This detection determines which audit checks are applicable and which framework-specific patterns to evaluate.

### Step 2: Scope Assessment

Classify the review scope:

| Scope | Audit Depth |
|-------|-------------|
| **Full application** | All 5 domains, complete audit |
| **Component library** | Domains 3-5 primary, Domain 1-2 for individual components |
| **Single PR/changeset** | Focused audit on changed code within applicable domains |
| **Performance-specific** | Domain 1 deep dive |
| **Accessibility-specific** | Domain 2 deep dive |

---

## Domain 1: Performance Audit

### Core Web Vitals Assessment

Evaluate code patterns against Google's Core Web Vitals thresholds:

**Largest Contentful Paint (LCP) — Target: ≤ 2.5s**

| Check | What to Look For |
|-------|-----------------|
| Image optimization | Are hero images using `loading="lazy"`, responsive `srcset`, modern formats (WebP, AVIF)? |
| Font loading | Are web fonts using `font-display: swap` or `optional`? Are fonts preloaded? |
| Server-side rendering | For LCP-critical content, is SSR or SSG used to reduce time-to-first-paint? |
| Render-blocking resources | Are CSS/JS files blocking the critical rendering path? |
| Critical CSS | Is above-the-fold CSS inlined or prioritized? |
| Third-party scripts | Are analytics, ads, or widgets deferring loading? |

**Interaction to Next Paint (INP) — Target: ≤ 200ms**

| Check | What to Look For |
|-------|-----------------|
| Long tasks | Event handlers executing heavy computation on the main thread (>50ms) |
| Debouncing/throttling | Input handlers (scroll, resize, keyup) not debounced or throttled |
| Expensive renders | React re-renders without `useMemo`, `useCallback`, `React.memo` where beneficial |
| Main thread yielding | Are long computations using `requestIdleCallback` or `scheduler.yield()`? |
| Virtual scrolling | Large lists rendering all items vs. using virtualization (react-virtuoso, TanStack Virtual) |

**Cumulative Layout Shift (CLS) — Target: ≤ 0.1**

| Check | What to Look For |
|-------|-----------------|
| Image/video dimensions | Are explicit `width` and `height` attributes set on `<img>` and `<video>` elements? |
| Dynamic content injection | Content injected above the fold without reserved space (ads, banners, lazy content) |
| Font loading shifts | Web fonts causing text reflow (FOUT/FOIT) |
| Skeleton screens | Are loading states using skeletons or placeholders with correct dimensions? |

### Bundle Analysis

| Check | What to Look For |
|-------|-----------------|
| Code splitting | Is the application using dynamic `import()` for route-based or component-based splitting? |
| Tree shaking | Are imports specific (`import { map } from 'lodash-es'`) vs whole-library (`import _ from 'lodash'`)? |
| Duplicate dependencies | Are multiple versions of the same library in the bundle? |
| Bundle size budget | Does the main bundle exceed reasonable limits (200KB gzipped for initial load)? |
| Dead code | Are there imported modules that are never used? |

### Performance Budgets

| Metric | Budget Threshold |
|--------|-----------------|
| Main bundle (gzipped) | ≤ 200KB |
| Total page weight | ≤ 1.5MB |
| JavaScript execution time | ≤ 3s on mid-tier mobile |
| First-party JS | ≤ 150KB gzipped |
| Third-party JS | ≤ 100KB gzipped |

Consult `references/performance-checklist.md` for the complete checklist with framework-specific patterns.

---

## Domain 2: Accessibility (A11y) Audit

### WCAG 2.2 Level AA Compliance

Apply the four WCAG principles with emphasis on code-level verification:

**Perceivable:**
- All images have meaningful `alt` text (decorative images use `alt=""` or `role="presentation"`)
- Video/audio content has captions and/or transcripts
- Content is presented in a logical reading order
- Color is not the sole means of conveying information
- Text color contrast meets 4.5:1 for normal text, 3:1 for large text
- Non-text UI components meet 3:1 contrast against adjacent colors

**Operable:**
- All interactive elements are keyboard accessible (`tabIndex`, focus management)
- No keyboard traps (user can Tab in and out of all components)
- Focus order follows the visual layout
- Skip navigation links are present
- Touch targets meet minimum 24×24px (WCAG 2.2 new requirement)
- Dragging movements have alternative inputs (WCAG 2.2 new requirement)
- Focus appearance is visible and meets minimum area requirements (WCAG 2.2)

**Understandable:**
- Form inputs have programmatically associated labels (`<label for>`, `aria-labelledby`)
- Error messages are descriptive and associated with the erroring field
- Form validation provides specific guidance (not just "invalid input")
- Language is set on the `<html>` element
- Consistent navigation patterns across pages

**Robust:**
- Semantic HTML is used appropriately (`<nav>`, `<main>`, `<article>`, `<button>` vs `<div>`)
- ARIA attributes are used correctly (not conflicting with semantic HTML)
- Custom components expose correct roles, states, and properties
- Dynamic content updates are announced to screen readers (live regions)

### Framework-Specific A11y Checks

| Framework | Key Checks |
|-----------|-----------|
| **React** | `aria-*` props, `htmlFor` vs `for`, Fragment key accessibility, Portal focus management |
| **Vue** | `v-bind:aria-*` usage, transition group announcements, teleport accessibility |
| **Angular** | `ngAria` module usage, CDK a11y module, template-driven form accessibility |

Consult `references/accessibility-checklist.md` for the complete WCAG 2.2 review checklist.

---

## Domain 3: Frontend Security Audit

### Content Security Policy (CSP) Evaluation

| Check | Severity if Failing |
|-------|--------------------|
| CSP header present | Major — no CSP means no XSS mitigation layer |
| `unsafe-inline` for scripts | Major — defeats most XSS protection |
| `unsafe-eval` for scripts | Major — enables eval-based attacks |
| `default-src 'none'` as base | Minor — best practice for restrictive default |
| Nonce-based or hash-based script policy | Major if missing — inline scripts should use nonces |
| `frame-ancestors` set | Medium — prevents clickjacking equivalent of X-Frame-Options |
| Report-URI or report-to configured | Minor — enables CSP violation monitoring |

### Trusted Types Enforcement

| Check | What to Look For |
|-------|-----------------|
| Trusted Types policy | Is `require-trusted-types-for 'script'` set in CSP? |
| DOM sink usage | Are `innerHTML`, `outerHTML`, `document.write()` used? |
| Sanitization | Is DOMPurify or equivalent used before DOM insertion? |
| Policy creation | Are Trusted Types policies created with named policies? |

### XSS Prevention (Frontend-Specific)

| Check | What to Look For |
|-------|-----------------|
| Template auto-escaping | Is the framework's auto-escaping enabled and not bypassed? |
| `dangerouslySetInnerHTML` | Is user-controlled data passed through this React API? |
| `v-html` directive | Is user-controlled data rendered with Vue's raw HTML directive? |
| `bypassSecurityTrust*` | Is Angular's sanitizer bypassed for user-controlled data? |
| `eval()` / `new Function()` | Is dynamic code execution used with user-influenced input? |
| `postMessage` handlers | Do `message` event handlers validate origin? |
| URL scheme validation | Are `javascript:` URLs blocked in `href` attributes? |

### Subresource Integrity (SRI)

| Check | What to Look For |
|-------|-----------------|
| CDN resources | Do `<script>` and `<link>` tags for CDN resources include `integrity` attributes? |
| Hash algorithm | Are hashes using SHA-384 or SHA-512 (not SHA-256 alone)? |
| Build integration | Is SRI hash generation integrated into the build pipeline? |

### Cookie Security

| Check | What to Look For |
|-------|-----------------|
| `HttpOnly` flag | Are session cookies marked HttpOnly (inaccessible to JavaScript)? |
| `Secure` flag | Are cookies marked Secure (HTTPS only)? |
| `SameSite` attribute | Are cookies using `SameSite=Strict` or `SameSite=Lax`? |
| Cookie scope | Are cookies scoped to the narrowest path and domain? |

Consult `references/frontend-security.md` for the complete frontend security checklist.

---

## Domain 4: Component Architecture Assessment

### Component Design Quality

| Check | What to Evaluate |
|-------|-----------------|
| Single responsibility | Does each component have one clear purpose? |
| Prop interface clarity | Are props well-typed, documented, and not excessively numerous (>7 is a smell)? |
| Prop drilling depth | Is data passed through >3 component levels? (Consider context/state management) |
| Component size | Is any component >300 lines? (Candidate for decomposition) |
| Reusability | Are common patterns extracted into shared components? |

### State Management Patterns

| Check | What to Evaluate |
|-------|-----------------|
| State colocation | Is state kept as close to where it's used as possible? |
| Derived state | Is derived data computed from state (not stored redundantly)? |
| State shape | Is state normalized (avoiding deeply nested or duplicated data)? |
| Side effect management | Are side effects (API calls, subscriptions) cleanly separated? |
| Global state scope | Is global state limited to truly global concerns? |

### Render Efficiency

| Check | What to Evaluate |
|-------|-----------------|
| Unnecessary re-renders | Are components re-rendering when their inputs haven't changed? |
| Memoization | Are expensive computations memoized (`useMemo`, `computed`, `memo`)? |
| Key stability | Are list keys stable and unique (not array indices for dynamic lists)? |
| Render cascades | Does a state change in a parent cause deep re-render trees? |

### Error Boundary Coverage

| Check | What to Evaluate |
|-------|-----------------|
| Strategic placement | Are error boundaries at route level, feature level, and critical component boundaries? |
| Fallback UI | Do error boundaries render meaningful fallback UI (not blank screens)? |
| Error reporting | Are caught errors reported to monitoring (Sentry, Datadog)? |
| Recovery mechanism | Can users recover from error states without full page refresh? |

---

## Domain 5: UI/UX Quality Review

### Responsive Design

| Check | What to Evaluate |
|-------|-----------------|
| Breakpoint coverage | Are mobile (320px), tablet (768px), and desktop (1024px+) viewports handled? |
| Fluid typography | Are font sizes responsive (clamp(), viewport units, or media queries)? |
| Touch targets | Are interactive elements at least 44×44px on touch devices? |
| Content overflow | Is horizontal scrolling prevented on mobile viewports? |

### Interaction States

| State | What to Verify |
|-------|---------------|
| **Loading** | Are loading states clear and non-blocking? (Skeletons > spinners for known content) |
| **Error** | Are error states descriptive, recoverable, and visually distinct? |
| **Empty** | Are empty states helpful (guidance, illustrations, CTAs)? |
| **Success** | Are success confirmations visible and non-disruptive? |
| **Hover/Focus** | Are hover and focus states visually distinct and consistent? |
| **Disabled** | Are disabled states visually clear with cursor and ARIA cues? |

### Animation Performance

| Check | What to Evaluate |
|-------|-----------------|
| Compositor properties | Are animations using `transform` and `opacity` (GPU-composited) vs. `left`, `top`, `width` (layout-triggering)? |
| `will-change` usage | Is `will-change` applied sparingly and removed after animation? |
| `prefers-reduced-motion` | Are animations reduced/removed for users with motion sensitivity? |
| Frame budget | Do animations target 60fps (16.67ms per frame)? |

---

## Severity Model

| Severity | Criteria | Examples |
|----------|---------|---------|
| **Critical** | Performance regression causing CWV failure; accessibility barrier blocking user groups; exploitable frontend security flaw | LCP > 4s, no keyboard access to primary navigation, CSP allows unsafe-inline with user input |
| **Major** | Sub-optimal CWV metrics; WCAG A violations; weak CSP configuration; architectural anti-patterns | LCP 2.5–4s, missing alt text on informational images, no error boundaries, excessive re-renders |
| **Minor** | Polish items; WCAG AAA suggestions; best-practice deviations; style inconsistencies | Missing `prefers-reduced-motion`, non-ideal key usage, inconsistent loading states |

---

## Output Format

```markdown
# FRONTEND AUDIT REPORT

## Technology Stack
- Framework: [detected]
- Build tool: [detected]
- CSS approach: [detected]
- State management: [detected]
- Rendering strategy: [detected]

## Domain Scores

| Domain | Score | Critical | Major | Minor |
|--------|-------|----------|-------|-------|
| Performance | [Pass/Conditional/Fail] | [n] | [n] | [n] |
| Accessibility | [Pass/Conditional/Fail] | [n] | [n] | [n] |
| Frontend Security | [Pass/Conditional/Fail] | [n] | [n] | [n] |
| Component Architecture | [Pass/Conditional/Fail] | [n] | [n] | [n] |
| UI/UX Quality | [Pass/Conditional/Fail] | [n] | [n] | [n] |

## Findings by Domain
[Structured findings per domain with evidence and remediation]

## Tool Recommendations
[Specific tools to run for automated validation]
```

Append the following structured summary block at the end of every report for
pipeline consumption:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 6
skill: frontier
status: COMPLETE
risk_assessment: [High / Medium / Low]
domain_scores:
  performance: [Pass / Conditional / Fail]
  accessibility: [Pass / Conditional / Fail]
  frontend_security: [Pass / Conditional / Fail]
  component_architecture: [Pass / Conditional / Fail]
  ui_ux_quality: [Pass / Conditional / Fail]
finding_count:
  critical: [n]
  major: [n]
  minor: [n]
verdict: [Pass / Conditional / Fail]
key_concerns: [top 3 findings by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

---

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation with prior phase context
- Execute the 5-domain audit on frontend components only
- Submit completed report to code-chief (not directly to gatekeeper-code)
- Include the structured pipeline summary block at report end

**When invoked standalone:**
- Execute the full 5-domain audit independently
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` skill is available, self-validate by confirming each domain was assessed with evidence and framework compliance mapping

---

## Tool Recommendations

| Purpose | Tools |
|---------|-------|
| **Performance** | Lighthouse CI, WebPageTest, Chrome DevTools, webpack-bundle-analyzer, vite-bundle-analyzer |
| **Accessibility** | axe-core, Pa11y, Lighthouse a11y audit, WAVE, NVDA (screen reader) |
| **Frontend Security** | CSP Evaluator (Google), SecurityHeaders.com, Lighthouse security audit |
| **Linting** | Biome, Oxlint, ESLint (eslint-plugin-jsx-a11y), Stylelint |
| **Visual Regression** | Chromatic, Percy, Applitools, Playwright screenshots |
| **Testing** | Vitest, Playwright, React Testing Library, Storybook |

---

## Additional Resources

### Reference Files

- **`references/performance-checklist.md`** — Core Web Vitals audit checklist with framework-specific patterns
- **`references/accessibility-checklist.md`** — WCAG 2.2 Level AA review checklist
- **`references/frontend-security.md`** — CSP, Trusted Types, SRI, and DOM security guide

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the review report, write it to the designated save path as `deliverable_{report-name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 6
   skill: frontier
   name: Frontend Audit Report
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
