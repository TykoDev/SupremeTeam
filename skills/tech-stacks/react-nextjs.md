# React 19 and Next.js 15

## Baseline
- Use React 19 with the Next.js 15 App model and Node.js 22+ for a server-rendered or full-stack web application.
- Treat Server Components as the default and mark Client Components explicitly when browser state, event handlers, or browser APIs are required.
- Distinguish static generation, time-based revalidation, and request-time rendering; do not let a data-fetching change silently alter cache behavior.
- Use Turbopack for development and preserve the production bundler configuration actually exercised by the repository.

## Project shape
- Keep layouts and pages under `app`, reusable primitives under `components/ui`, and product-specific components under `components/features`.
- Keep Server Actions, shared schemas, database access, and utilities under `lib`; keep public assets and global styles at the application edge.
- Use loading, error, and not-found files where the user needs an explicit state boundary; keep API endpoint handlers close to their public surface.
- Treat `next.config.ts`, `package.json`, `tsconfig.json`, and `biome.json` as the framework and compiler contract.

## Data and API boundaries
- Share Zod v4 schemas between client and server, and validate Server Action input before authentication, authorization, or persistence work.
- Use TanStack Query for server state, Zustand for small client UI state, and React Context only when prop passing is the simpler contract.
- Fetch stable data in async Server Components and use explicit revalidation or no-store semantics for changing data.
- Keep server-only modules out of Client Components and make API DTOs distinct from database records and rendered props.

## Migration and versioning
- Move older page surfaces to the Next.js App model incrementally, preserving loading, error, not-found, and metadata behavior at each slice.
- Review every `use client` boundary during a React or Next.js upgrade; a wider client boundary changes bundle size, data access, and test seams.
- Treat React Compiler behavior as a versioned optimization assumption and avoid relying on manual memoization as a default performance policy.
- Recheck cache and revalidation semantics after Next.js upgrades, especially for Server Actions and dynamic data.

## Deployment
- Use pnpm, strict TypeScript, and Biome according to the existing lockfile and repository configuration.
- Deploy to a managed Next.js host or self-host with standalone output when the application needs a controlled Node.js image.
- Keep image optimization, OpenTelemetry, and error tracking compatible with both server and browser execution contexts.
- Track Core Web Vitals targets of LCP below 2.5 seconds, INP below 200 milliseconds, and CLS below 0.1 as performance evidence.

## Testing defaults
- Test Server Components and Client Components at their separate boundaries, including serialization and client-state hydration.
- Test Server Actions with invalid input, unauthenticated input, unauthorized input, and successful persistence using real schema validation.
- Use Playwright for loading, error, not-found, responsive, and browser interaction states across the application shell.
- Include an accessibility check for semantic headings, focus visibility, and touch target constraints on user-facing pages.

## Known uncertainty
- Next.js caching defaults and React Server Component behavior depend on the exact minor versions and deployment adapter; verify them against the repository's version pins.
- Managed hosting and standalone self-hosting have different telemetry, image, and cost characteristics, so deployment evidence cannot be copied between them.
- The source names several state tools; the smallest tool that preserves a clear server/client state boundary is the safer project choice.
