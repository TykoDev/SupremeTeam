# Performance Checklist — Core Web Vitals & Bundle Analysis

## Largest Contentful Paint (LCP) — Target: ≤ 2.5s

### Image Optimization

- [ ] Hero/banner images use responsive `srcset` with appropriate breakpoints
- [ ] Images use modern formats (WebP, AVIF) with fallbacks
- [ ] Above-the-fold images use `loading="eager"` or `fetchpriority="high"`
- [ ] Below-the-fold images use `loading="lazy"`
- [ ] Images have explicit `width` and `height` attributes
- [ ] Image CDN with automatic resizing is configured (if applicable)
- [ ] `<picture>` element used for art direction across breakpoints

### Font Loading

- [ ] Web fonts use `font-display: swap` or `font-display: optional`
- [ ] Critical fonts are preloaded: `<link rel="preload" as="font" crossorigin>`
- [ ] Font files use WOFF2 format (best compression)
- [ ] Font subset is limited to required character ranges
- [ ] System font fallbacks closely match web font metrics (minimizes CLS)

### Server-Side Rendering

- [ ] LCP content rendered by server (not hydrated after client JS executes)
- [ ] Streaming SSR used for long-loading pages (React 18+, Nuxt 3, SvelteKit)
- [ ] Static pages use SSG or ISR where content doesn't change per-request
- [ ] Edge rendering considered for latency-sensitive content

### Render-Blocking Resources

- [ ] Critical CSS is inlined in `<head>` or served via separate critical stylesheet
- [ ] Non-critical CSS uses `media` attribute or dynamic loading
- [ ] Scripts use `defer` or `async` attributes (not render-blocking)
- [ ] Third-party scripts loaded asynchronously or deferred
- [ ] No synchronous XHR calls blocking paint

---

## Interaction to Next Paint (INP) — Target: ≤ 200ms

### Event Handler Efficiency

- [ ] Click/tap handlers execute in < 50ms (no heavy computation)
- [ ] Form submission handlers are non-blocking (optimistic UI or async processing)
- [ ] Search/filter handlers use debouncing (300ms recommended)
- [ ] Scroll handlers use `passive: true` option and throttling
- [ ] Resize handlers are debounced or use `ResizeObserver`

### Main Thread Management

- [ ] Long tasks (> 50ms) are broken into smaller chunks using `scheduler.yield()` or `requestIdleCallback`
- [ ] Web Workers used for heavy computation (parsing, sorting, filtering large datasets)
- [ ] `requestAnimationFrame` used for visual updates (not `setTimeout(0)`)
- [ ] No synchronous `localStorage` reads/writes in hot code paths

### React-Specific

- [ ] `useMemo` used for expensive computations derived from props/state
- [ ] `useCallback` used for event handlers passed as props to memoized children
- [ ] `React.memo` wraps components that re-render unnecessarily
- [ ] `useTransition` used for non-urgent state updates (React 18+)
- [ ] `useDeferredValue` used for derived values in low-priority renders

### Vue-Specific

- [ ] `computed` used instead of methods for derived state
- [ ] `v-once` used for truly static content
- [ ] `shallowRef` / `shallowReactive` used when deep reactivity is unnecessary
- [ ] Component `key` forces re-mount only when necessary

### Large List Rendering

- [ ] Lists > 100 items use virtualization (react-virtuoso, TanStack Virtual, vue-virtual-scroller)
- [ ] Pagination used for data sets > 500 items
- [ ] Infinite scroll implements proper cleanup and memory management

---

## Cumulative Layout Shift (CLS) — Target: ≤ 0.1

### Explicit Dimensions

- [ ] All `<img>` elements have `width` and `height` attributes (or CSS `aspect-ratio`)
- [ ] All `<video>` elements have explicit dimensions
- [ ] All `<iframe>` elements have explicit dimensions
- [ ] Ad slots and embedded content have reserved space

### Dynamic Content

- [ ] Content injected above the fold reserves space with min-height or skeleton
- [ ] Banners, cookie notices, and alerts do not push content down (use overlay or reserved slot)
- [ ] Lazy-loaded content below the fold does not shift visible content
- [ ] Search results / filter results update in-place without layout reflow

### Font Loading

- [ ] `font-display: optional` used to prevent all text reflow (strictest)
- [ ] Or `font-display: swap` with `size-adjust` and `ascent-override` on fallback fonts
- [ ] Font loading tracked and optimized (preconnect to font origins)

---

## Bundle Analysis Checklist

### Code Splitting

- [ ] Route-based code splitting with dynamic `import()` for each route
- [ ] Component-based lazy loading for large components not visible on initial load
- [ ] Vendor bundle separated from application code
- [ ] Shared chunks extracted for common dependencies

### Tree Shaking

- [ ] Named imports used instead of default/namespace imports: `import { map } from 'lodash-es'`
- [ ] Side-effect-free marking in `package.json`: `"sideEffects": false` (or explicit list)
- [ ] ESM-native libraries preferred over CJS
- [ ] No barrel file re-exports that defeat tree shaking

### Dependency Audit

- [ ] Bundle visualized with webpack-bundle-analyzer or vite-bundle-analyzer
- [ ] Largest dependencies identified and alternatives evaluated
- [ ] Duplicate package versions resolved (single version in lock file)
- [ ] Unused dependencies removed

### Performance Budgets (CI Enforcement)

| Metric | Default Budget | Notes |
|--------|---------------|-------|
| Main JS bundle (gzipped) | ≤ 200KB | All application JavaScript for initial route |
| Total JS (gzipped) | ≤ 500KB | All JavaScript including async chunks |
| Total CSS (gzipped) | ≤ 50KB | All stylesheets |
| Total page weight (gzipped) | ≤ 1.5MB | All resources combined |
| Number of HTTP requests | ≤ 50 | Initial page load |
| Lighthouse Performance score | ≥ 90 | CI gate threshold |

---

## Tool Integration

### Lighthouse CI Configuration

```yaml
# lighthouserc.yml
ci:
  collect:
    url:
      - http://localhost:3000/
      - http://localhost:3000/dashboard
  assert:
    assertions:
      categories:performance:
        - error
        - minScore: 0.9
      largest-contentful-paint:
        - warn
        - maxNumericValue: 2500
      interactive:
        - warn
        - maxNumericValue: 3500
      cumulative-layout-shift:
        - error
        - maxNumericValue: 0.1
```

### Bundle Size CI Check

```bash
# Example: size-limit configuration
# .size-limit.json
[
  { "path": "dist/index.js", "limit": "200 KB" },
  { "path": "dist/vendor.js", "limit": "150 KB" }
]
```
