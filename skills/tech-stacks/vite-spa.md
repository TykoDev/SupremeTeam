# Vite 8 single-page application

## Baseline
- Use Vite 8 with Rolldown for a client-rendered single-page application and treat SSR as outside this baseline.
- Use React 19 or Vue 3.5 according to the product's component model, with Vite's native ESM development server and fast refresh support.
- Keep the browser bundle responsible for UI state and API calls, while preserving a clear boundary for any server-backed data.
- Use Vite plugins only for capabilities the selected UI library and verification tools actually require.

## Project shape
- Keep `index.html` as the Vite entry document and application code under `src` with an explicit `main.tsx` or equivalent entry.
- Organize reusable UI under `src/components`, screens under `src/pages`, hooks or composables near their consumers, and API clients, schemas, and utilities under `src/lib`.
- Keep state containers under `src/stores` and global or variable styles under `src/styles`; keep unprocessed assets in `public`.
- Treat `vite.config.ts`, `package.json`, `tsconfig.json`, and `biome.json` as the build contract.

## Data and API boundaries
- Expose browser configuration only through `VITE_`-prefixed values and never place secrets in the client bundle.
- Validate environment and API response data with Zod at application initialization or the API client boundary.
- Keep API client functions separate from screen components and translate transport errors into stable UI states.
- Use TanStack Query or VueQuery for server state and Zustand, Pinia, or an equally narrow store for client UI state.

## Migration and versioning
- Keep the React or Vue plugin aligned with Vite 8 and Rolldown, and review plugin compatibility before changing the bundler path.
- Preserve alias and proxy behavior in `vite.config.ts` when reorganizing source directories or API environments.
- Treat manual chunks and bundle analysis as measured optimizations; remove them when they no longer reflect actual dependency cost.
- If the product requires SSR, treat that as a new rendering baseline rather than silently extending the SPA assumptions.

## Deployment
- Use pnpm and produce the Vite `dist` output for a CDN or static host such as Cloudflare Pages, Netlify, or an object-storage front end.
- Keep preview behavior separate from production caching and provide the API origin through environment-specific client configuration.
- Preserve source maps and browser error reporting according to the hosting policy without exposing secret configuration.
- Use the Vite checker and selected UI-library linting in the same verification path as the production bundle.

## Testing defaults
- Test API client parsing, environment validation, store transitions, and loading, empty, partial, and error UI states independently.
- Use the selected React or Vue component runner for unit behavior and browser tests for client-only navigation and interaction.
- Test the production bundle through a static preview host, including API proxy or origin configuration.
- Use bundle analysis when dependency changes affect initial load, and compare the result with the product's performance budget.

## Known uncertainty
- React and Vue share the Vite baseline but differ in state, plugin, and component testing conventions; the chosen library must own those details.
- Rolldown and plugin support can change across Vite releases, so a successful development server does not prove production-bundle parity.
- A client-only app cannot protect secrets or perform server-only validation; those needs require an explicit backend contract.
