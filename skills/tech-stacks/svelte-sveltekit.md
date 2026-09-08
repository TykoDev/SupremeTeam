# Svelte 5 and SvelteKit

## Baseline
- Use Svelte 5 runes, including `$state`, `$derived`, and `$effect`, for fine-grained component reactivity.
- Use SvelteKit for file-based page handling, server rendering by default, API endpoints, client hydration, and adapter-selected deployment.
- Use the Vite-based toolchain and keep static generation an explicit choice through the static adapter.
- Keep shared state, server data, and component state separate so hydration does not become an accidental persistence mechanism.

## Project shape
- Keep page and endpoint files in the SvelteKit application tree, shared components, stores, schemas, and utilities under `src/lib`, and the document shell in `src/app.html`.
- Keep static assets in `static`, and keep `svelte.config.js`, `vite.config.ts`, `package.json`, and `tsconfig.json` at the root.
- Use `+layout.svelte`, `+page.svelte`, `+page.server.ts`, and `+server.ts` according to whether data belongs to the browser or server.
- Keep shared stores under `src/lib/stores` and keep reusable validation schemas separate from page presentation.

## Data and API boundaries
- Validate form and endpoint input with Zod, and use Superforms with Zod integration when its form-state contract fits the project.
- Validate server load and action data in `+page.server.ts` before returning it to the browser.
- Use generated `$types` for page and server contracts, and keep database or external service access inside server-only modules.
- Use Svelte stores for intentionally shared state and keep `$state` local to the component or module that owns the behavior.

## Migration and versioning
- Move Svelte 4 reactive declarations toward Svelte 5 runes incrementally, testing derived values and effects for changed execution timing.
- Preserve the distinction between `+page.server.ts`, browser page code, and `+server.ts` when changing data loading or authentication behavior.
- Treat the selected adapter as part of the versioned deployment contract; SSR, static generation, and edge hosting do not have identical APIs.
- Recheck generated page types and form schemas after SvelteKit upgrades before changing page boundaries.

## Deployment
- Use pnpm and the Vite production build, then select the Node, Cloudflare, or static adapter that matches the hosting contract.
- Keep server-only environment values out of browser modules and inject hosted secrets through the platform environment.
- Preserve SSR cache behavior and hydration headers when using the Node or edge adapters; use immutable static assets for generated output.
- Keep ESLint with Svelte-aware rules and the selected adapter's build checks in release verification.

## Testing defaults
- Use Vitest for unit and component behavior, including rune transitions, derived state, and effect cleanup.
- Use Playwright for SSR, hydration, progressive enhancement, forms, endpoint errors, and responsive browser flows.
- Test server load and action validation with representative authenticated, invalid, empty, and partial data states.
- Include a static-build check when the static adapter is selected and an adapter-specific smoke check for SSR deployments.

## Known uncertainty
- Svelte 5 rune migration changes reactive execution semantics, so mechanically replacing syntax is not enough for effect-heavy components.
- SvelteKit adapters differ in filesystem, streaming, and environment support; an SSR result on Node.js does not prove edge parity.
- Superforms and generated `$types` add useful contracts but increase coupling to the selected SvelteKit version.
