# Styling & Component Library Decision Matrix

> **Purpose**: Authoritative reference for the designer skill's styling stack
> selection. Covers the decision tree for choosing styling frameworks,
> component libraries, variant management tools, and CSS architecture. The
> designer SKILL.md instructs the agent to consult this file when selecting the
> project's styling stack and component library strategy.

---

## 1. Styling Framework Decision Tree

```
START: What is the project's primary framework?
│
├── React / Next.js
│   ├── Need maximum control + excellent DX?
│   │   └── YES → shadcn/ui + Tailwind CSS v4
│   ├── Need enterprise-grade i18n and complex components?
│   │   └── YES → React Aria + Tailwind CSS v4
│   ├── Building a custom design system from scratch?
│   │   └── YES → Radix Primitives + Tailwind CSS v4
│   ├── Need type-safe styling with zero runtime?
│   │   └── YES → Panda CSS + Ark UI
│   └── Simple project, want fast setup?
│       └── YES → Headless UI + Tailwind CSS v4
│
├── Vue / Nuxt
│   ├── Using Tailwind?
│   │   └── YES → Headless UI (Vue) + Tailwind CSS v4
│   └── Need more components?
│       └── YES → Ark UI (Vue) + Tailwind CSS v4
│
├── Svelte / SvelteKit
│   └── Tailwind CSS v4 + Skeleton UI / shadcn-svelte
│
├── Astro / Static Sites
│   └── Tailwind CSS v4 (no JS component library needed)
│
├── HTML-only / Vanilla JS
│   └── Tailwind CSS v4 (CDN or build)
│
└── Multi-framework / Framework-agnostic
    └── Ark UI + Tailwind CSS v4
```

---

## 2. Styling Approach Comparison

| Approach | Runtime Cost | Type Safety | Framework Lock | Customization | Learning Curve |
|----------|-------------|-------------|----------------|---------------|---------------|
| **Tailwind CSS v4** | Zero | Low (IDE plugin) | None | Unlimited | Low |
| **Panda CSS** | Zero | Excellent (native) | Low | High | Medium-High |
| **Vanilla Extract** | Zero | Excellent (native) | Low | High | Medium-High |
| **CSS Modules** | Zero | Low | Framework-dependent | High | Low |
| **Styled Components** | ~13KB runtime | Medium | React | High | Medium |
| **Emotion** | ~12KB runtime | Medium | React | High | Medium |
| **UnoCSS** | Zero | Low (preset) | None | High | Medium |

**Default**: Tailwind CSS v4 for all projects unless compile-time type safety
for styles is a hard requirement (→ Panda CSS).

---

## 3. Component Library Comparison

| Library | Framework | A11y | Bundle | Customization | Best For |
|---------|-----------|------|--------|---------------|---------|
| **shadcn/ui** | React/Next.js | Excellent (Radix) | N/A (copy-paste) | Full control | Design systems, startups, SaaS |
| **Radix Primitives** | React | Excellent | Small (per-component) | Unlimited (unstyled) | Custom design systems |
| **React Aria** | React | Excellent (Adobe) | Medium (larger) | High (hooks) | Enterprise, i18n, complex forms |
| **Headless UI** | React/Vue | Good | Tiny | High (unstyled) | Tailwind teams, simple apps |
| **Ark UI** | React/Vue/Solid | Good | Small | High (unstyled) | Multi-framework projects |
| **Ariakit** | React | Excellent | Tiny | Unlimited (unstyled) | Accessibility-first projects |

### Selection Guide

| When you need... | Choose | Reason |
|------------------|--------|--------|
| Maximum control + best DX (React/Next.js) | **shadcn/ui** | Copy-paste ownership, Radix accessibility, Tailwind styling |
| Enterprise i18n + RTL + complex date/number | **React Aria** | Adobe-backed, comprehensive i18n |
| Cross-framework consistency | **Ark UI** | Same API across React, Vue, Solid |
| Smallest possible bundle | **Ariakit** | Tiny, granular, a11y-first primitives |
| Simplest API + Tailwind | **Headless UI** | Small focused set, easiest to learn |
| Building from raw primitives | **Radix Primitives** | Battle-tested unstyled building blocks |

---

## 4. shadcn/ui Deep Dive

### Architecture

shadcn/ui is **not** a traditional component library. Components are copied
into your codebase, giving full ownership and control:

- **Copy, don't install**: Lives in your code, not node_modules
- **Built on Radix**: Uses Radix UI primitives for accessibility
- **Styled with Tailwind**: All styling via utility classes
- **CSS Variables**: CSS custom properties for all theming
- **Composable**: Compound patterns (Card.Header, Card.Body)
- **Accessible by default**: Full keyboard nav, ARIA, screen reader support

### Component Categories

| Category | Components |
|----------|-----------|
| **Form** | Input, Textarea, Select, Checkbox, Radio, Switch, Label, Form |
| **Data Display** | Table, Card, Badge, Avatar, Calendar, Separator |
| **Feedback** | Alert, Alert Dialog, Toast, Progress |
| **Navigation** | Tabs, Breadcrumb, Menubar, Navigation Menu, Pagination |
| **Overlay** | Dialog, Sheet, Popover, Dropdown Menu, Command Palette |
| **Layout** | Aspect Ratio, Scroll Area |

### Theming

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --primary: 222.2 47.4% 11.2%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --destructive: 0 84.2% 60.2%;
    --border: 214.3 31.8% 91.4%;
    --ring: 222.2 84% 4.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    /* ... full dark overrides ... */
  }
}
```

### Best Practices

1. Keep form logic outside UI components (use React Hook Form/Zod for state)
2. Extend with CVA for variants — don't override styles
3. Keep custom styles minimal — let layout handle spacing
4. Update via CLI and merge customizations manually
5. Leverage shadcn block libraries (Magic UI, shadcn-blocks) for pre-built sections

---

## 5. Class Variance Authority (CVA)

CVA is the standard for managing component variants with Tailwind:

```typescript
import { cva, type VariantProps } from "class-variance-authority";

const buttonVariants = cva(
  // Base styles (always applied)
  "inline-flex items-center justify-center rounded-md text-sm font-medium
   transition-colors focus-visible:outline-none focus-visible:ring-2
   disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

### twMerge Utility

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
// Usage: cn("px-4 py-2", "px-6") → "py-2 px-6"
```

---

## 6. Tailwind CSS v4 Key Features

### CSS-First Configuration

All customization via `@theme` in CSS (no JavaScript config file):

```css
@import "tailwindcss";

@theme {
  --color-primary: oklch(0.55 0.2 250);
  --color-primary-hover: oklch(0.48 0.18 250);
  --font-sans: "Inter", system-ui, sans-serif;
  --radius-md: 0.375rem;
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
}
```

### Built-in Container Queries

```html
<div class="@container">
  <div class="grid grid-cols-1 @sm:grid-cols-2 @md:grid-cols-3">
    <!-- Responds to container size, not viewport -->
  </div>
</div>
```

### Class Organization Order

Layout → Sizing → Spacing → Typography → Visual → Interaction → Overrides

---

## 7. CSS Architecture Standards

### Z-Index Token System

```css
:root {
  --z-base: 0;
  --z-above: 10;
  --z-dropdown: 100;
  --z-sticky: 200;
  --z-overlay: 300;
  --z-modal: 400;
  --z-popover: 500;
  --z-toast: 600;
  --z-tooltip: 700;
}
```

**Rules**: Never exceed 1000. Never `!important` with z-index. Use
`isolation: isolate` to create stack contexts within components.

### CSS Methodology Selection

| Methodology | Best For | When to Use |
|------------|---------|-------------|
| **Utility-First (Tailwind)** | Component-based frameworks | Default choice |
| **CSS Modules** | Scoped styles in Next.js/Nuxt | When team prefers traditional CSS |
| **BEM** | Large traditional CSS projects | Legacy or non-JS projects |
| **Tailwind + CVA** | Component variant management | Any Tailwind project with variants |

---

## 8. Recommended Stacks by Project Type

| Project Type | Styling | Components | Rationale |
|-------------|---------|------------|-----------|
| **SaaS App (React/Next.js)** | Tailwind v4 | shadcn/ui | Full control, a11y, DX |
| **Marketing Site (Next.js/Astro)** | Tailwind v4 | Custom | Max performance, SEO |
| **Admin Dashboard (React)** | Tailwind v4 | shadcn/ui + blocks | Pre-built dashboard sections |
| **E-commerce (Next.js)** | Tailwind v4 | shadcn/ui | Accessible forms, cards |
| **Documentation** | Tailwind v4 | N/A (framework docs) | Starlight/Docusaurus built-in |
| **Design System Library** | Panda CSS | Ark UI / Radix | Type-safe, framework-agnostic |
| **Vue/Nuxt App** | Tailwind v4 | Headless UI (Vue) | Best Vue support |
| **SvelteKit App** | Tailwind v4 | shadcn-svelte | Svelte-adapted shadcn |
| **Enterprise (React, i18n)** | Tailwind v4 | React Aria | Comprehensive i18n, a11y |
| **Rapid Prototype** | Tailwind v4 + DaisyUI | DaisyUI | Fastest setup, 70+ components |
