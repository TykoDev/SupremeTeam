# Frontend Architecture Patterns Reference

> **Purpose**: Comprehensive reference for selecting frontend rendering
> strategies and architectural patterns. The designer SKILL.md instructs the
> agent to consult this file when deciding the project's rendering pattern.

---

## Architecture Selection Decision Tree

```
START: What does the project need?
│
├── Public-facing, SEO-critical content?
│   ├── Content changes rarely? → Static Site Generation (SSG)
│   ├── Content changes often but not real-time? → Incremental Static Regen (ISR)
│   └── Content is personalized per user? → Server-Side Rendering (SSR)
│
├── Behind authentication? (dashboard, admin, tool)
│   ├── Single team, moderate complexity? → SPA (CSR)
│   └── Multiple teams, large platform? → Micro-Frontends
│
├── Content site with pockets of interactivity?
│   └── Islands Architecture (Astro)
│
└── Complex app with both public + authenticated?
    └── SSR + Hybrid (Next.js App Router / Nuxt)
        Server Components for data + Client Components for interactivity
```

---

## Single-Page Application (SPA / CSR)

### Description

Entire application loads once; subsequent navigation handled client-side
via JavaScript. The server serves a single HTML file; routing, rendering,
and data fetching happen in the browser.

### Advantages
- Smooth, app-like transitions between views
- Rich interactivity without page reloads
- Decoupled from backend (API-first)
- Simple deployment (static files)

### Disadvantages
- Poor SEO without additional configuration (hydration, pre-rendering)
- Slower initial load (full JS bundle)
- Accessibility challenges with client-side routing
- Memory management responsibility on the client

### Best For
Internal dashboards, admin panels, real-time collaboration tools,
applications behind authentication.

---

## Server-Side Rendering (SSR)

### Description

Pages are rendered on the server for each request. The browser receives
fully-formed HTML, then "hydrates" it with JavaScript for interactivity.

### Advantages
- Excellent SEO (crawlers see full HTML)
- Faster First Contentful Paint (HTML arrives ready)
- Better for users with slow connections or devices
- Access control enforced server-side

### Disadvantages
- Server required (not just static files)
- Increased server costs
- Hydration mismatch bugs
- Higher framework complexity

### Best For
Content-heavy sites, e-commerce, SEO-critical applications,
applications with public and authenticated sections.

---

## Static Site Generation (SSG)

### Description

All pages are pre-built at compile time. The output is static HTML, CSS,
and JavaScript files deployed to a CDN.

### Advantages
- Maximum performance (pre-built, CDN-served)
- Lowest hosting cost (static files)
- Excellent SEO
- Simple deployment and caching

### Disadvantages
- Content changes require rebuild
- Not suitable for dynamic/personalized content
- Build times grow with page count

### Best For
Documentation sites, blogs, marketing pages, portfolios.

---

## Incremental Static Regeneration (ISR)

### Description

Combines SSG with background revalidation. Pages are pre-built but can
be regenerated in the background after a specified interval or on-demand.

### Advantages
- SSG performance with dynamic-like freshness
- No rebuild for content updates
- CDN-cacheable with stale-while-revalidate

### Disadvantages
- Framework-specific (primarily Next.js)
- Stale content during revalidation window

### Best For
Large catalogs, directories, CMS-driven content that updates frequently
but does not require real-time accuracy.

---

## Islands Architecture (Astro)

### Description

Pages are rendered as static HTML by default. Only specific "islands"
of interactivity are hydrated with JavaScript. The rest remains static.

### Advantages
- Zero JavaScript by default — excellent performance
- Selective hydration reduces bundle size
- Multi-framework support (React + Vue + Svelte on one page)
- Perfect Core Web Vitals scores

### Disadvantages
- Limited to content-driven sites
- Complex interactive applications are awkward
- Hydration boundaries require careful planning
- Smaller ecosystem than SPA frameworks

### Best For
Content sites with selective interactivity, documentation with
interactive code examples, marketing sites with animated widgets.

---

## Server Components (React / Next.js App Router)

### Description

Components that render exclusively on the server. They can access
databases, file systems, and backend services directly. The rendered
output (not the component code) is sent to the client.

### Key Rules

1. Server Components are the **default** in Next.js App Router
2. Client Components must be marked with `'use client'`
3. Server Components CAN import Client Components (not vice versa)
4. Server Components CANNOT use hooks (`useState`, `useEffect`)
5. Server Components CAN be async — await data directly

### Mental Model

```
Server Components → Fetch data, render HTML → Send to client
Client Components → Interactive UI, event handlers, browser APIs
```

### Page Layout Strategy

A typical page combines both:

```
page.tsx (Server Component)
 ├── Header.tsx (Server — static nav)
 ├── DataSection.tsx (Server — fetches data)
 │   └── InteractiveChart.tsx (Client — 'use client')
 ├── Form.tsx (Client — 'use client' — event handlers)
 └── Footer.tsx (Server — static)
```

**Rule**: Keep as much as possible as Server Components. Only add
`'use client'` when the component needs: event handlers, useState,
useEffect, browser APIs, or third-party client-only libraries.

---

## Micro-Frontends

### Description

Split the frontend into independently deployable units, each owned by a
different team. Units integrate at runtime via Module Federation,
Web Components, or iframe composition.

### Integration Approaches

| Approach | Isolation | Performance | Complexity |
|----------|-----------|-------------|-----------|
| **Module Federation** | Medium | Good | Medium |
| **Web Components** | High | Medium | Low |
| **iframe** | Complete | Poor | Low |
| **Server-side composition** | Medium | Good | High |

### Anti-Pattern Warning

Do NOT use micro-frontends with a single team. The overhead is only
justified when multiple teams need independent deployment.

### Best For
Large enterprises with multiple autonomous teams, platforms with distinct
product areas, gradually migrating legacy frontends.

---

## Signals-Based Reactivity (2025-2026 Trend)

Signals provide fine-grained, synchronous reactivity without virtual DOM
diffing. A signal holds a value; when changed, only the exact DOM nodes
that depend on it update.

### Framework Adoption

| Framework | Signal API | Status (2026) |
|-----------|-----------|---------------|
| **Angular** | `signal()`, `computed()`, `effect()` | Production (v17+) |
| **Vue** | `ref()`, `computed()`, `watch()` | Production (Vue 3+) |
| **Svelte** | `$state`, `$derived`, `$effect` | Production (Svelte 5) |
| **Solid.js** | `createSignal()`, `createMemo()` | Production |
| **React** | React Compiler (auto-memoizes) | Production (React 19+) |
| **Preact** | `@preact/signals` | Production |

---

## Modern CSS Capabilities Summary

These browser-native features reduce JavaScript requirements:

| Feature | What It Does | Replaces |
|---------|-------------|----------|
| **Container Queries** | Style based on parent container size | JS resize observers |
| **CSS Subgrid** | Child aligns to parent grid tracks | Manual grid math |
| **Cascade Layers** | Explicit specificity hierarchy | BEM naming, !important fights |
| **:has() Selector** | Style parent based on child state | JS class toggling |
| **View Transitions API** | Native page/route transitions | JS animation libraries |
| **Scroll-Driven Animations** | Animate on scroll position | JS scroll listeners |
| **CSS Nesting** | Native rule nesting | Sass/Less preprocessors |

See `references/layout-patterns.md` for implementation details and code
examples for each.
