# Vue 3 and Nuxt 3

## Baseline
- Use Vue 3.5 with the Composition API and `<script setup lang="ts">` as the component standard.
- Use Nuxt 3.14+ for server rendering, file-based pages, auto-imports, server endpoints, and Nitro deployment targets.
- Let the selected Nuxt release own the Vite version: Nuxt 3.14 resolves Vite 5.4.10, so do not independently force Vite 8; keep SSR, hydration, and static generation as explicit output choices.
- Use Pinia for shared client state and reserve composables for independently scoped behavior.

## Project shape
- Keep the Nuxt 3 application directories top-level: `components`, `composables`, `layouts`, `pages`, `middleware`, and `plugins`; keep `app.vue` at the project root.
- Keep server endpoints, middleware, and utilities under `server`; keep shared validators under `shared` for use by Vue and Nitro.
- Keep Pinia stores under `stores`, public assets under `public`, and the Nuxt/Vite configuration at the root.
- Follow Nuxt auto-import conventions while keeping high-risk dependencies explicit when auto-import would hide a boundary.

## Data and API boundaries
- Validate forms with VeeValidate and Zod, and place full-stack schemas in `shared/utils/validators.ts` when both browser and server consume them.
- Use `useFetch` or `useAsyncData` for Nuxt-managed server data, and use TanStack Query Vue when its cache and mutation contract is required.
- Keep Nitro endpoint input and output contracts separate from Vue component props and Pinia state.
- Use setup stores for intentional cross-component state and keep composables independent per consumer.

## Migration and versioning
- Treat Nuxt 3 as the legacy baseline: Nuxt 3 reaches end of life on 31 July 2026; keep Vue 3.5, Nuxt 3.14+, its lockfile-selected Vite version, and the Nitro version aligned.
- Move older component patterns toward Composition API and `<script setup>` in slices that preserve page and hydration behavior.
- Review auto-import additions, shared schema changes, and server endpoint serialization together when moving files across Nuxt directories.
- Treat SSR, static generation, and adapter changes as different deployment contracts even when page source stays the same.

## Deployment
- Use pnpm and Nuxt's production build for Nitro hosting, or the static generation output when the product has no request-time data.
- Verify the target Nitro adapter for Node.js, Deno, Cloudflare, Vercel, Netlify, or AWS Lambda before selecting it as the release target.
- Keep server-only environment values out of browser-exposed configuration and inject secrets through the hosting platform.
- Use Biome or Nuxt-aware ESLint consistently with the repository's existing formatting and linting contract.

## Testing defaults
- Use Vitest for composables, Pinia stores, schemas, and component behavior, and use Playwright for page and browser flows.
- Test SSR and hydration with representative server data, client-only interactions, and endpoint failures.
- Test `useFetch` or `useAsyncData` caching separately from Pinia state and form validation so each data contract has an observable boundary.
- Include a Nitro-adapter smoke check and a static-generation check when either output mode is part of the release.

## Known uncertainty
- Nuxt auto-imports improve ergonomics but can hide dependency movement and name collisions; inspect generated behavior after structural changes.
- Nitro adapter parity differs across Node.js, Deno, edge, and function hosts, especially for filesystem and streaming behavior.
- The source offers both built-in Nuxt data tools and TanStack Query Vue; choose one primary server-state contract per feature.
