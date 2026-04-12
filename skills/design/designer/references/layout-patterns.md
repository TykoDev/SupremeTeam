# Layout Patterns Reference

> **Purpose**: Authoritative reference for layout decisions within the designer
> skill. Covers Grid vs Flexbox selection, standard layout patterns, modern CSS
> capabilities, responsive strategy, and image handling. The designer SKILL.md
> instructs the agent to consult this file when defining the responsive and
> layout strategy.

---

## 1. CSS Grid vs Flexbox Decision Guide

| Requirement | Use | Why |
|-------------|-----|-----|
| **2D layout** (rows AND columns) | CSS Grid | Designed for 2D |
| **Equal-height columns** | CSS Grid | Equalizes automatically |
| **Page shells** (header, sidebar, main, footer) | CSS Grid | `grid-template-areas` |
| **Card grids** (masonry, bento) | CSS Grid | Spanning and auto-rows |
| **1D alignment** (single row or column) | Flexbox | Optimized for 1D |
| **Centering** | Flexbox | `flex items-center justify-center` |
| **Dynamic item sizing** | Flexbox | `flex-grow/shrink` |
| **Navigation bars** | Flexbox | Horizontal alignment + wrapping |
| **Form layout** (label + input side by side) | Flexbox | Simple horizontal alignment |

---

## 2. Standard Layout Patterns

### Container Layout (Foundation)

```css
.container {
  width: 100%;
  max-width: 1280px; /* 80rem */
  margin-inline: auto;
  padding-inline: 1rem;
}

@media (min-width: 640px)  { .container { padding-inline: 1.5rem; } }
@media (min-width: 1024px) { .container { padding-inline: 2rem; } }

/* Tailwind: max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 */
```

### Holy Grail Layout (Sidebar + Content)

```css
.holy-grail {
  display: grid;
  grid-template-areas:
    "header header"
    "sidebar main"
    "footer footer";
  grid-template-columns: 280px 1fr;
  grid-template-rows: auto 1fr auto;
  min-height: 100vh;
}

@media (max-width: 768px) {
  .holy-grail {
    grid-template-areas: "header" "main" "footer";
    grid-template-columns: 1fr;
  }
}
```

### Bento Grid (Trending 2025-2026)

```css
.bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-auto-rows: 180px;
  gap: 1rem;
}

.bento-grid .featured { grid-column: span 2; grid-row: span 2; }
.bento-grid .wide     { grid-column: span 2; }
.bento-grid .tall     { grid-row: span 2; }

@media (max-width: 768px) {
  .bento-grid { grid-template-columns: repeat(2, 1fr); grid-auto-rows: 150px; }
  .bento-grid .featured { grid-column: span 2; grid-row: span 1; }
}
```

### Dashboard Grid (Auto-Fill)

```css
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.5rem;
}
```

### Sidebar + Content (Collapsible)

```html
<div class="flex h-screen">
  <aside class="hidden lg:flex lg:w-64 lg:flex-col border-r">
    <!-- Sidebar (icons only when collapsed: 64px; expanded: 240-280px) -->
  </aside>
  <div class="flex flex-1 flex-col overflow-hidden">
    <header class="flex h-14 items-center border-b px-4">
      <!-- Top bar -->
    </header>
    <main class="flex-1 overflow-y-auto p-6">
      <!-- Content -->
    </main>
  </div>
</div>
```

### Centered Content (Marketing/Blog)

```html
<main class="min-h-screen">
  <div class="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
    <!-- Centered prose, max 65ch for readability -->
  </div>
</main>
```

### Full-Width Sections with Container

```html
<section class="bg-gradient-to-b from-brand-50 to-white py-20">
  <div class="mx-auto max-w-7xl px-4 text-center">
    <!-- Hero content (full-width bg, contained content) -->
  </div>
</section>
```

---

## 3. Modern CSS Capabilities

### Container Queries (2025 Standard)

Components respond to parent container size, not viewport. This makes
components truly reusable across different layout contexts:

```css
.card-container {
  container-type: inline-size;
  container-name: card;
}

@container card (min-width: 400px) {
  .card-content {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
}

@container card (max-width: 399px) {
  .card-content {
    display: flex;
    flex-direction: column;
  }
}
```

**When to use**: Component-level adaptations (card, widget, sidebar content).
**When NOT to use**: Page-level layout changes (use media queries instead).

In Tailwind v4: `@container` parent, `@sm:`, `@md:` on children.

### CSS Subgrid

Child elements align to parent grid tracks:

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
}

.card {
  display: grid;
  grid-template-rows: subgrid; /* Inherits parent row tracks */
  grid-row: span 3;           /* Participate in 3 parent rows */
}
```

Use case: Cards in a row with perfectly aligned headers, content, and footers
regardless of content length.

### Cascade Layers (@layer)

Define explicit CSS specificity hierarchy:

```css
@layer reset, framework, components, utilities;

@layer components {
  .btn { /* component styles */ }
}

@layer utilities {
  .text-center { /* utility overrides always win */ }
}
```

### The :has() Selector (Parent Selector)

Style a parent based on child state:

```css
/* Form group highlights when its input has focus */
.form-group:has(input:focus) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-ring);
}

/* Card shows footer only when it has one */
.card:has(.card-footer) {
  padding-bottom: 0;
}
```

### View Transitions API

Native browser animations between page states (prefer over JS libraries):

```css
::view-transition-old(root) {
  animation: fade-out 200ms ease-out;
}

::view-transition-new(root) {
  animation: fade-in 200ms ease-in;
}
```

---

## 4. Responsive Strategy

### 4.1 Mobile-First Methodology

Write base CSS for mobile (no media queries), then add complexity for larger
screens with `min-width` queries:

| Breakpoint | Min Width | Devices |
|-----------|-----------|---------|
| `sm` | 640px | Large phones (landscape) |
| `md` | 768px | Tablets (portrait) |
| `lg` | 1024px | Tablets (landscape), small laptops |
| `xl` | 1280px | Laptops, desktops |
| `2xl` | 1536px | Large desktops |

**Critical rule**: Design for viewport widths, not specific devices. Never use
device-specific breakpoints.

### 4.2 Responsive Element Behavior Matrix

| Element | Mobile (<768px) | Tablet (768–1024px) | Desktop (>1024px) |
|---------|----------------|--------------------|--------------------|
| **Navigation** | Bottom tabs / hamburger | Top navbar or sidebar | Navbar + sidebar |
| **Tables** | Card layout or stacked | Scrollable + sticky 1st col | Full table |
| **Modals** | Bottom sheet (full width) | Centered, max 90vw | Centered, max 600px |
| **Forms** | Single column, full width | 2-column for related fields | 2–3 columns |
| **Card grids** | 1 column | 2 columns | 3–4 columns |
| **Hero sections** | Stack: text then image | Side-by-side or stacked | Side-by-side |
| **Sidebars** | Hidden (drawer) | Collapsible overlay | Fixed visible |

---

## 5. Responsive Images

```html
<img
  src="image-800.webp"
  srcset="
    image-400.webp 400w,
    image-800.webp 800w,
    image-1200.webp 1200w
  "
  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
  alt="Description of the image"
  loading="lazy"
  decoding="async"
  width="800"
  height="600"
/>
```

**Rules**:
- Always `width` + `height` attributes (prevents CLS)
- `loading="lazy"` for below-the-fold images
- `decoding="async"` to prevent main thread blocking
- Prefer AVIF → WebP → JPEG/PNG fallback
- Use `<picture>` for art-directed images (different crops per viewport)

### Image Format Selection

| Format | Best For | Transparency | Compression |
|--------|---------|-------------|-------------|
| **AVIF** | Photos, complex images | Yes | Best (smallest) |
| **WebP** | Photos, complex images | Yes | Very Good |
| **SVG** | Icons, logos, illustrations | Yes | Excellent (vector) |
| **PNG** | Simple graphics, screenshots | Yes | Good (lossless) |
| **JPEG** | Fallback for older browsers | No | Good (lossy) |

**Default**: AVIF primary, WebP fallback. SVG for all icons/logos.

---

## 6. Interface Density Classification

Match spatial density to user needs and content type:

| Density | Applications | Spacing Strategy |
|---------|-------------|------------------|
| **High** | Trading platforms, analytics, ERP | Minimize whitespace, maximize data. Monospace/tabular numbers. |
| **Medium** | SaaS dashboards, CRM, standard apps | Default. Balance scannability with data. Moderate whitespace. |
| **Low** | Marketing, portfolios, editorial | Expansive negative space. Focus on narrative and aesthetics. |
