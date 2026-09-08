# Astro 5 content and islands

## Baseline
- Use Astro 5 for content-driven sites, documentation, marketing pages, blogs, and other surfaces where static HTML is the primary output; this Astro 5 baseline is a historical, unmaintained snapshot rather than the current Astro release.
- Treat zero JavaScript as the default. Add interactive islands only where a visible interaction requires client execution.
- Use the Content Layer API with Zod-validated content schemas, and use the Vite-based build system as the default toolchain.
- Choose among React, Vue, Svelte, Solid, or Preact components per island only when the interaction benefits from that library.

## Project shape
- Keep file-based pages under `src/pages`, reusable wrappers under `src/layouts`, and static or interactive pieces under `src/components`.
- Keep content entries under `src/content`; define Astro 5 Content Layer collections and schemas in `src/content.config.ts`; keep styles in `src/styles` and unprocessed assets in `public`.
- Use a small root configuration with `astro.config.mjs`, `package.json`, and `tsconfig.json`; keep page-specific content out of global configuration.
- Make each interactive island explicit in the component tree so the static shell remains easy to inspect.

## Data and API boundaries
- Validate frontmatter and content records with Zod before rendering a page or generating a feed.
- Use local file collections or remote loaders behind the Content Layer API, and keep loader-specific data mapping outside presentation components.
- Use `client:load`, `client:idle`, `client:visible`, `client:media`, or `client:only` only when the interaction's latency and rendering needs justify that choice.
- Keep personalized data behind a server island or a server endpoint so CDN-cached page content does not accidentally contain request-specific data.

## Migration and versioning
- Treat the Astro 5 Content Layer schema as a versioned content contract; update validators and representative fixtures together.
- Review every hydration directive when converting a static component into an island, because the directive changes JavaScript timing and browser ownership.
- Keep framework integrations version-aligned with Astro and verify that a component still renders correctly in both the static shell and its hydrated state.
- Decide explicitly whether an adapter change moves the project from static output to server rendering; do not infer that change from a component import.

## Deployment
- Publish static output to a CDN or static host when pages do not need request-time rendering.
- Use the Node, Deno, or Cloudflare adapter when server rendering or server islands are required, and keep the adapter choice in release configuration.
- Use pnpm and keep content, image processing, and integration dependencies pinned to the repository's lockfile.
- Preserve cache headers for static content while isolating request-specific responses from the CDN cache.

## Testing defaults
- Test content schemas with representative valid, missing-field, and malformed records before testing page output.
- Test the static HTML shell without JavaScript, then test each interactive island at its selected hydration condition.
- Test server islands and remote loaders with deterministic fixtures that cover unavailable or partial content.
- Use Playwright for navigation, responsive interaction, and Core Web Vitals-sensitive pages; use the selected component library's unit runner for island logic.

## Known uncertainty
- The source describes both static and SSR deployments, so cache behavior and request-time data need a project-specific decision.
- Remote Content Layer loaders and multi-framework islands can introduce different failure and hydration behavior than local Markdown content.
- Adapter support changes faster than the static output path; verify the target host and adapter together for every release.
