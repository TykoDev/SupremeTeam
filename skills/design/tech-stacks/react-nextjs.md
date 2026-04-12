# TECH STACK OVERLAY: React 19 + Next.js 15 Frontend

Applies to: Full-stack web apps, server-rendered applications, content-heavy platforms
Runtime: Node.js 22+ | Next.js 15 App Router | React 19

---

## Runtime and Execution Model

- **Framework**: Next.js 15 with App Router (server-first)
- **UI Library**: React 19.2 — Server Components, Actions, React Compiler
- **Rendering**: Server Components by default; Client Components opt-in with `'use client'`
- **Build tool**: Turbopack (dev) / Webpack (production)
- **Deployment**: Vercel (managed) or self-hosted with `output: 'standalone'`

---

## Framework Conventions

### File-Based Routing (App Router)

```
app/
├── layout.tsx              # Root layout
├── page.tsx                # Home page
├── loading.tsx             # Loading UI
├── error.tsx               # Error boundary
├── not-found.tsx           # 404 page
├── (auth)/                 # Route group (no URL segment)
│   ├── login/page.tsx
│   └── register/page.tsx
├── dashboard/
│   ├── layout.tsx
│   ├── page.tsx
│   └── settings/page.tsx
└── api/
    └── users/route.ts      # API route handler
```

### Project Structure

```
project-root/
├── app/                    # App Router pages and layouts
├── components/
│   ├── ui/                 # Reusable UI primitives
│   └── features/           # Feature-specific components
├── lib/
│   ├── actions/            # Server Actions
│   ├── schemas/            # Zod validation schemas
│   ├── db/                 # Database client
│   └── utils/
├── public/
├── styles/
├── next.config.ts
├── package.json
├── tsconfig.json
└── biome.json
```

---

## State Management

- **Server state**: TanStack Query v5 — caching, deduplication, background refetch
- **Client UI state**: Zustand (~1KB) — minimal, no boilerplate
- **Simple prop drilling**: React Context (built-in)
- **Rule**: Never use Redux for server state; never mix server/client state stores

---

## Data Contracts and Validation

- **Runtime validation**: Zod v4 for shared schemas (client + server)
- **Server Actions**: Always validate with Zod, check auth, verify authorization
- **Form handling**: `useActionState` + `useOptimistic` for instant feedback

### Server Action + Zod Pattern

```typescript
// lib/schemas/contact.ts (shared)
import { z } from 'zod';

export const contactSchema = z.object({
  name: z.string().min(1).max(100),
  email: z.string().email(),
  message: z.string().min(10),
});

// lib/actions/contact.ts
'use server'
import { contactSchema } from '@/lib/schemas/contact';

export async function submitContact(prev: ActionResult, formData: FormData) {
  const result = contactSchema.safeParse(Object.fromEntries(formData));
  if (!result.success) return { success: false, errors: result.error.flatten().fieldErrors };
  // ... process validated data
}
```

---

## Data Fetching Model

- **Static (default)**: Pages are static by default; cached at build time
- **ISR**: `revalidate` option for time-based revalidation
- **Dynamic**: `cache: 'no-store'` for real-time data
- **Server Components**: Fetch data directly in async Server Components
- **Client Components**: TanStack Query for client-side data fetching

---

## Performance Requirements

- **Core Web Vitals targets**: LCP < 2.5s | INP < 200ms | CLS < 0.1
- **React Compiler**: Eliminates manual `useMemo`/`useCallback`/`memo`
- **Code splitting**: Automatic per-route; use `@next/dynamic` for component-level splitting
- **Images**: `next/image` for automatic optimization, lazy loading, responsive sizing

---

## Accessibility (WCAG 2.2)

- Minimum 24×24px touch targets
- Focus visibility requirements
- Accessible authentication (passkeys and password managers)
- Semantic HTML with proper heading hierarchy
- Single `<h1>` per page

---

## Build and Deployment

- **Package manager**: pnpm
- **Linter/formatter**: Biome 2.0
- **Type checking**: TypeScript strict mode
- **Container**: `output: 'standalone'` for Docker deployment
- **Cost note**: Vercel ~$3,500/month at 2M pageviews vs self-hosted ~$150/month

---

## Observability

- **Vercel Analytics**: Built-in Web Vitals and speed insights
- **OpenTelemetry**: `@vercel/otel` or manual OTel SDK setup
- **Error tracking**: Sentry Next.js SDK for client + server errors
