---
name: frontier
description: >-
  This skill should be used when the user asks to "review the frontend",
  "audit UI/UX", "check web performance", "test accessibility",
  "review Core Web Vitals", "why is this page slow?", "check keyboard
  navigation", "audit this design system", "review bundle size",
  "check frontend security", "audit CSS/HTML", "review component
  architecture", "check WCAG compliance", "run frontier", "assess
  frontend quality", "is this accessible?", "check lighthouse
  scores", or wants comprehensive frontend-specific code review
  covering performance, accessibility (WCAG 2.2), security, and UI/UX
  architecture. Produces a scored audit report across all four
  dimensions with evidence-backed findings.
  DO NOT USE for visual design correctness (use design-qa). DO NOT USE
  for backend code review (use code-review). DO NOT USE for penetration
  testing (use mr-robot).
version: 1.0.0
---

# Frontier — Frontend Analytics & UI/UX Audit Specialist

## Purpose

This skill performs comprehensive frontend-specific code review across five audit domains: performance, accessibility, frontend security, component architecture, and UI/UX quality. It goes significantly deeper on web frontend concerns than the generalist review skills can, applying current industry standards (Core Web Vitals 2025, WCAG 2.2, CSP Level 3) and frontend-specific testing methodologies.

Where `code-review` touches frontend concerns superficially across 8 dimensions, and `security-review` covers general web security patterns, frontier provides deep specialist analysis of how the frontend code affects real users — their performance experience, their ability to access the application, and their safety from client-side attacks.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.
Before auditing, confirm the frontend artifact is a complete build — not a partial
snapshot or stale bundle. If assets are missing or the build hash is unverifiable,
state the gap before proceeding.

## Differentiation

| Aspect | code-review | security-review | frontier |
|--------|-------------|----------------|----------|
| **Performance** | Flags obvious issues | N/A | Audit Core Web Vitals, bundle size, and performance budgets |
| **Accessibility** | Basic check | N/A | Audit full WCAG 2.2 Level AA compliance |
| **Frontend Security** | Style/formatting | XSS, CSRF (general) | Evaluate CSP, Trusted Types, DOM-based XSS, SRI, prototype pollution |
| **Component Quality** | Design dimension | N/A | Assess state management, render efficiency, error boundaries, component patterns |
| **UI/UX** | N/A | N/A | Verify responsive design, interaction patterns, loading/error/empty states |

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

Consult `references/performance-checklist.md` for the full coverage matrix by scope.

### Evidence Collection Baseline

Before assigning severity, collect the evidence type that matches the scope:

- Use measured evidence when available: Lighthouse/WebPageTest traces, DevTools data, axe output, keyboard traversal results, or CSP header output
- If runtime measurements are unavailable, mark conclusions as code-inferred instead of claiming concrete CWV numbers or WCAG pass/fail rates
- Separate first-party issues from third-party constraints so ownership stays clear
- For every Major or Critical finding, include at least one file reference, DOM snippet, or captured metric that proves the issue

Rationale: frontier reports lose credibility when they invent metrics, overclaim compliance, or blur ownership between application code and third-party embeds.

---

## Domain 1: Performance Audit

### Core Web Vitals Assessment

Evaluate code patterns against Google's Core Web Vitals thresholds:

**Largest Contentful Paint (LCP) — Target: ≤ 2.5s**

| Check | What to Look For |
|-------|-----------------|
| Image optimization | Hero images using `loading="lazy"`, responsive `srcset`, modern formats (WebP, AVIF)? |
| Font loading | Web fonts using `font-display: swap` or `optional`? Fonts preloaded? |
| Server-side rendering | For LCP-critical content, is SSR/SSG used? |
| Render-blocking resources | CSS/JS files blocking critical rendering path? |
| Critical CSS | Above-the-fold CSS inlined or prioritized? |
| Third-party scripts | Analytics, ads, or widgets deferring loading? |

**Interaction to Next Paint (INP) — Target: ≤ 200ms**

| Check | What to Look For |
|-------|-----------------|
| Long tasks | Event handlers with heavy computation on main thread (>50ms) |
| Debouncing/throttling | Input handlers (scroll, resize, keyup) not debounced |
| Expensive renders | Re-renders without memoization where beneficial |
| Main thread yielding | Long computations not using `requestIdleCallback` or `scheduler.yield()`? |
| Virtual scrolling | Large lists rendering all items instead of using virtualization |

**Cumulative Layout Shift (CLS) — Target: ≤ 0.1**

| Check | What to Look For |
|-------|-----------------|
| Image/video dimensions | Explicit `width`/`height` on `<img>` and `<video>`? |
| Dynamic content injection | Content injected above fold without reserved space? |
| Font loading shifts | Web fonts causing FOUT/FOIT? |
| Skeleton screens | Loading states using skeletons with correct dimensions? |

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

Consult `references/accessibility-checklist.md` for the complete WCAG 2.2 review checklist including framework-specific checks (React, Vue, Angular).

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

Consult `references/frontend-security.md` for the complete frontend security checklist including SRI, cookie security, and Trusted Types enforcement.

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

### State Management & Render Efficiency

Verify state colocation (state close to usage), normalized state shape, clean side-effect separation, and minimal global state scope. Check for unnecessary re-renders, missing memoization, unstable list keys, and render cascades. Verify error boundaries at route, feature, and critical component boundaries with meaningful fallback UI and recovery paths.

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
| **Loading** | Loading states clear and non-blocking? (Skeletons > spinners for known content) |
| **Error** | Are error states descriptive, recoverable, and visually distinct? |
| **Empty** | Are empty states helpful (guidance, illustrations, CTAs)? |
| **Success** | Success confirmations visible and non-disruptive? |
| **Hover/Focus** | Are hover and focus states visually distinct and consistent? |
| **Disabled** | Are disabled states visually clear with cursor and ARIA cues? |

### Animation Performance

Verify animations use GPU-composited properties (`transform`, `opacity`) instead of layout-triggering properties. Check `will-change` usage is minimal and `prefers-reduced-motion` is respected.

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

### Example Frontier Findings

#### Performance — Major
- **Evidence:** `src/components/Hero.tsx:12` renders a 2.1 MB JPEG hero image without `srcset`, making it the likely LCP candidate on mobile.
- **Remediation:** Convert the image to WebP or AVIF, add responsive sources, and preload only if it is above the fold.

#### Accessibility — Major
- **Evidence:** `src/components/FeedbackForm.tsx:45` renders `<button className="btn-submit" />` without text or an accessible name.
- **Remediation:** Provide visible button text or add `aria-label="Submit feedback form"`.

#### Frontend Security — Major
- **Evidence:** Security headers allow `script-src 'unsafe-inline'`, which weakens CSP protection for DOM injection paths.
- **Remediation:** Remove `'unsafe-inline'`, migrate inline logic to approved scripts, and adopt nonces or hashes for any remaining inline script needs.

**Worked LCP remediation:**

**Before (LCP = 4.2s — fails Core Web Vitals):**
```html
<!-- Hero image loaded via CSS background, invisible to preload scanner -->
<div class="hero" style="background-image: url('/images/hero-4k.jpg')">
  <h1>Welcome</h1>
</div>
```

**After (LCP = 1.8s — passes):**
```html
<!-- Explicit <img> with fetchpriority, responsive sources, proper dimensions -->
<div class="hero">
  <img src="/images/hero-800.webp"
       srcset="/images/hero-400.webp 400w, /images/hero-800.webp 800w, /images/hero-1200.webp 1200w"
       sizes="100vw"
       fetchpriority="high"
       width="1200" height="600"
       alt="Product dashboard showing real-time analytics" />
  <h1>Welcome</h1>
</div>
```

**Why:** CSS `background-image` is invisible to the browser's preload scanner, delaying discovery. An explicit `<img>` with `fetchpriority="high"` lets the browser start the fetch during HTML parsing. Responsive `srcset` avoids downloading a 4K image on mobile. Setting `width`/`height` prevents layout shift (CLS).

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

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No frontend code in the change set | Report "Not applicable — no frontend files in scope." Skip all 5 domains. |
| Server-side rendered application (SSR/SSG) | Adapt performance checks: focus on TTFB and server response times rather than client-side bundle analysis. Accessibility and security checks still apply fully. |
| Legacy frontend (jQuery, no component framework) | Adapt component architecture domain: evaluate code organization, separation of concerns, and DOM manipulation patterns instead of component patterns. All other domains apply. |
| Web Components / custom elements | Treat as a component framework. Check shadow DOM accessibility, style encapsulation, and custom element lifecycle management. |
| Mobile-only responsive design (no desktop) | Adjust responsive checks: verify the mobile viewport meta tag and test at 320px-428px range. Desktop checks become advisory rather than mandatory. |
| No runtime traces, Lighthouse data, or keyboard/assistive-technology evidence are available | Report performance and accessibility findings as code-inferred, not measured. Recommend the exact tool run needed to confirm severity before claiming CWV or WCAG failure rates. |
| Third-party widget/iframe heavy page | Check CSP and sandbox attributes for iframes. Note that third-party performance and accessibility are outside the project's control — report but classify as INFO. |
| Email template or embedded webview rendering | Restrict the audit to inline-CSS-safe patterns because email clients and webviews strip external stylesheets, ignore CSP, and limit JavaScript. Replace CSP and bundle checks with inline-style size, image-fallback, and dark-mode `prefers-color-scheme` media-query coverage. |

---

## Additional Resources

### Reference Files

- **`references/performance-checklist.md`** — Core Web Vitals audit checklist with framework-specific patterns
- **`references/accessibility-checklist.md`** — WCAG 2.2 Level AA review checklist
- **`references/frontend-security.md`** — CSP, Trusted Types, SRI, and DOM security guide

---
*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

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

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
