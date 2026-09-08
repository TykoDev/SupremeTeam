# React 19 and TanStack Start

## Baseline
- Use React 19 with TanStack Start and Vite 8 with Rolldown for a type-safe full-stack application.
- Treat end-to-end TypeScript inference across URL definitions, data loaders, forms, and server functions as the primary framework benefit.
- Preserve server rendering and client hydration boundaries explicitly while keeping the deployment target portable.
- Keep vendor-neutral runtime support as an assumption to verify, not as permission to ignore adapter-specific behavior.

## Project shape
- Keep the file-based URL tree under `app`, shared UI under `app/components`, and schemas, API clients, and utilities under `app/lib`.
- Keep `client.tsx` and `ssr.tsx` as the application assembly boundaries; keep navigation setup close to them and keep styles and public assets separate.
- Use the root page and layout conventions expected by TanStack Start, and keep generated URL-tree artifacts out of hand-edited domain code.
- Treat `app.config.ts`, `package.json`, `tsconfig.json`, and `biome.json` as the build and runtime contract.

## Data and API boundaries
- Use TanStack Query with query-key factories for server state, and use TanStack Start search-parameter schemas for typed URL state.
- Use TanStack Form with Zod or Valibot validators for form input, and keep server functions behind typed request and response contracts.
- Use loader data and SSR dehydration deliberately, then hydrate only the state needed by the client.
- Keep Zustand or React Context limited to client UI state and keep persistence or external service calls behind `app/lib/api` boundaries.

## Migration and versioning
- Keep Vite 8, Rolldown, TanStack Start, and React versions aligned because their generated types and SSR adapters interact.
- Review generated URL-tree changes as source changes; update lazy components and search-parameter schemas together with their consuming screens.
- Preserve query-key factories and stale-time policy during data-library upgrades so cache identity does not drift silently.
- Recheck server-function serialization and hydration behavior when changing the target runtime from Node.js to Deno, Bun, or an edge host.

## Deployment
- Use pnpm and Biome with the repository's lockfile, and keep the Vite build target explicit for the selected runtime.
- Verify the same application against Node.js, Deno, Bun, Cloudflare Workers, or a managed host only when the selected adapter supports the required server features.
- Keep `VITE_` values limited to browser-visible configuration and provide server-only values through the host environment.
- Preserve source maps, structured logs, and request trace context in the chosen deployment adapter.

## Testing defaults
- Use Vitest for component and data-layer tests, with tests for query identity, stale data, optimistic updates, and schema rejection.
- Test URL search parameters and loader data through TanStack Start's typed interfaces rather than stringly typed fixtures.
- Test SSR dehydration and client hydration with representative authenticated and unauthenticated states.
- Use Playwright for browser flows and run a build against the production adapter before treating portability as proven.

## Known uncertainty
- TanStack Start and Vite 8 are fast-moving; generated URL types, server functions, and adapter behavior need version-pinned verification.
- Runtime portability does not guarantee identical streaming, environment, or edge API behavior across Node.js, Deno, Bun, and Cloudflare.
- TanStack Query, Form, Table, and Virtual each add different cache or rendering contracts; include only the packages the product actually exercises.
