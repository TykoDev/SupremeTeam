# TECH STACK OVERLAY: Astro 5 (Content Sites + Islands)

Applies to: Content-driven websites, documentation, marketing pages, blogs
Runtime: Astro 5 | Islands Architecture | Zero JS by default

---

## Runtime and Execution Model

- **Framework**: Astro 5 — ships zero JavaScript by default, static HTML output
- **Architecture**: Islands — interactive components hydrated selectively
- **Multi-framework**: Supports React, Vue, Svelte, Solid, Preact on the same page
- **Build tool**: Vite-based
- **Content**: Content Layer API with Zod-validated schemas

---

## Framework Conventions

### Project Structure

```
project-root/
├── src/
│   ├── pages/              # File-based routing
│   │   ├── index.astro
│   │   ├── about.astro
│   │   └── blog/
│   │       ├── index.astro
│   │       └── [slug].astro
│   ├── layouts/            # Reusable page wrappers
│   │   └── BaseLayout.astro
│   ├── components/         # Astro + framework components (islands)
│   │   ├── Header.astro
│   │   ├── Footer.astro
│   │   └── InteractiveWidget.tsx  # React island
│   ├── content/            # Content collections
│   │   ├── config.ts
│   │   └── blog/
│   │       ├── post-1.md
│   │       └── post-2.mdx
│   └── styles/
├── public/
├── astro.config.mjs
├── package.json
└── tsconfig.json
```

---

## Islands Architecture

- **Default**: All components render to static HTML — zero JS shipped
- **Selective hydration**: Use `client:*` directives only where interactivity is needed

```astro
---
import StaticHeader from '../components/Header.astro';
import ReactChart from '../components/Chart.tsx';
import VueForm from '../components/ContactForm.vue';
---

<StaticHeader />                              <!-- Static, no JS -->
<ReactChart client:visible />                 <!-- Hydrates when visible in viewport -->
<VueForm client:idle />                       <!-- Hydrates when browser is idle -->
```

### Hydration Directives

| Directive | When Hydrated |
|-----------|---------------|
| `client:load` | Immediately on page load |
| `client:idle` | When browser is idle |
| `client:visible` | When component enters viewport |
| `client:media="(max-width: 768px)"` | When media query matches |
| `client:only="react"` | Client-only (no SSR) |

---

## Content Layer API (Astro 5)

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    date: z.date(),
    author: z.string(),
    tags: z.array(z.string()),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
```

- Content builds are **5× faster** for Markdown with 25-50% less memory
- Supports local files (`glob()`) and remote APIs via custom loaders
- All content validated with Zod schemas at build time

---

## Server Islands (`server:defer`)

Combine CDN-cached static pages with personalized dynamic content:

```astro
---
import UserGreeting from '../components/UserGreeting.astro';
---

<h1>Welcome to our site</h1>        <!-- Static, CDN-cached -->
<UserGreeting server:defer />        <!-- Dynamic, server-rendered per request -->
```

---

## Performance

- **Zero JS default**: Perfect Lighthouse scores out of the box
- **Selective hydration**: Only interactive islands add JavaScript
- **Core Web Vitals**: Inherently optimized — minimal CLS, fast LCP
- **Image optimization**: `astro:assets` for automatic image processing

---

## Build and Deployment

- **Package manager**: pnpm
- **Build**: `astro build` for static output or `astro build --adapter=node` for SSR
- **Hosting**: Any CDN for static; Node/Deno/Cloudflare adapter for SSR
- **Integrations**: `@astrojs/react`, `@astrojs/vue`, `@astrojs/svelte` as needed
