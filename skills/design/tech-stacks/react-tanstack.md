# TECH STACK OVERLAY: React + TanStack Start

Applies to: Type-safe full-stack apps, composable architectures, vendor-agnostic deployment
Runtime: Vite 8 | TanStack Start | TanStack Router

---

## Runtime and Execution Model

- **Meta-framework**: TanStack Start — built on TanStack Router + Vite, end-to-end type safety
- **UI Library**: React 19 with Hooks and Server Components support
- **Build tool**: Vite 8 with Rolldown (Rust-based bundler, 10-30× faster)
- **Deployment**: Any runtime — no vendor lock-in (Vercel, Cloudflare, Node, Deno, Bun)

---

## Framework Conventions

### File-Based Routing (TanStack Router)

```
routes/
├── __root.tsx              # Root layout
├── index.tsx               # Home page
├── about.tsx               # /about
├── dashboard/
│   ├── index.tsx           # /dashboard
│   └── settings.tsx        # /dashboard/settings
├── users/
│   ├── index.tsx           # /users
│   └── $userId.tsx         # /users/:userId (dynamic)
└── _auth/                  # Layout route group (underscore prefix)
    ├── login.tsx
    └── register.tsx
```

### Project Structure

```
project-root/
├── app/
│   ├── routes/             # File-based route tree
│   ├── components/
│   │   ├── ui/
│   │   └── features/
│   ├── lib/
│   │   ├── schemas/
│   │   ├── api/
│   │   └── utils/
│   ├── styles/
│   ├── client.tsx
│   ├── router.tsx
│   └── ssr.tsx
├── public/
├── app.config.ts
├── package.json
├── tsconfig.json
└── biome.json
```

---

## Key TanStack Ecosystem

| Package | Purpose |
|---------|---------|
| **TanStack Router** | Type-safe file-based routing, auto-generated route trees, code splitting via `.lazy.tsx` |
| **TanStack Query** | Server state management — caching, deduplication, optimistic mutations, SSR hydration |
| **TanStack Table v8** | Headless data grid — sorting, filtering, pagination; pair with `@tanstack/react-virtual` |
| **TanStack Form v1** | Form management with Standard Schema — Zod/Valibot schemas work natively |

---

## State Management

- **Server state**: TanStack Query with query key factories
- **Client UI state**: Zustand or React Context
- **URL state**: TanStack Router's type-safe search params
- **Form state**: TanStack Form with Zod validators

---

## Data Contracts and Validation

- **Runtime validation**: Zod v4 or Valibot (Standard Schema compatible)
- **TanStack Form**: Pass schemas directly to validators — no adapters needed
- **Server functions**: Type-safe RPC-style server functions with full inference
- **Search params**: Typed search parameters validated via Zod schemas

---

## Data Fetching

- **Route loaders**: Data loaders with full type inference from route definition
- **SSR hydration**: `dehydrate` / `HydrationBoundary` for server-to-client state transfer
- **Stale time**: Configure per-query; use query key factories for consistent cache management
- **Optimistic updates**: `useMutation` with `onMutate` for instant UI feedback

---

## Performance

- **Code splitting**: Automatic per-route; `.lazy.tsx` suffix for deferred route components
- **Build**: Vite 8 + Rolldown — 10-30× faster builds than Webpack
- **Virtualization**: `@tanstack/react-virtual` for rendering large datasets efficiently
- **Bundle analysis**: `rollup-plugin-visualizer`

---

## Build and Deployment

- **Package manager**: pnpm
- **Build tool**: Vite 8
- **Linter/formatter**: Biome 2.0
- **Deployment**: Works with Node.js, Deno, Bun, Cloudflare Workers, Vercel, Netlify
- **Environment variables**: `VITE_` prefix for client-exposed vars

---

## Why TanStack Start Over Next.js

- End-to-end compile-time type safety (no manual validation gaps)
- No vendor lock-in — deploy anywhere
- Composable middleware (not framework-imposed)
- Transparent — no hidden runtime "magic"
- Strict TypeScript inference across routing, data, and forms
