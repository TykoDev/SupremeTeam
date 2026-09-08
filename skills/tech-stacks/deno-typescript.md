# Deno 2 and TypeScript

## Baseline
- Use Deno 2.x with native TypeScript, ESM imports, and secure-by-default permissions.
- Keep runtime, imports, tasks, compiler settings, and permission declarations in `deno.json`; use npm compatibility only at explicit dependency boundaries.
- Use Fresh for a full-stack island application, Oak for a middleware-oriented service, or Hono for a portable edge API.
- Document the minimum network, file, and environment access for each execution context rather than granting broad access by default.

## Project shape
- For an API service, organize `src` by domain with schemas, handlers, services, repositories, shared middleware, configuration, and a single application entry.
- For Fresh, keep `components`, `islands`, page handlers, and `static` in the framework's expected root shape, with client behavior isolated under `islands`.
- Keep `deno.json`, `deno.lock`, and `.env.example` as explicit runtime and dependency records.
- Avoid `index.ts` filenames when following the source convention; use descriptive entry names and JSDoc for exported APIs.

## Data and API boundaries
- Validate request and response data with Zod v4 at HTTP boundaries and co-locate `*.schema.ts` files with the domain that owns them.
- Keep Fresh page data, Oak/Hono handler input, and persistence models separate so permission decisions do not leak into view data.
- Use Deno KV for key-value workloads or an external PostgreSQL service for relational workloads; keep the chosen persistence contract explicit.
- Load local configuration through the environment-file support or `Deno.env.get`, and validate all required values before serving traffic.

## Migration and versioning
- Version `deno.json` import mappings and `deno.lock` together; review URL, `jsr:`, and `npm:` imports when changing dependencies.
- Keep Prisma, Drizzle, or Deno KV migration behavior documented beside the persistence boundary, especially when moving from local KV to hosted storage.
- Treat permission changes as compatibility changes: update the environment matrix and denial tests whenever a service gains file, network, or environment access.
- Preserve ESM-only assumptions during upgrades and verify that package compatibility does not add an implicit Node.js module expectation.

## Deployment
- Use Deno Deploy for edge-oriented services when its supported APIs match the service, or produce a compiled binary or minimal container for controlled hosting.
- Inject hosted environment values through platform secrets and retain the smallest permission set needed by the deployed entry point.
- Keep linting and formatting in the release verification path, using Deno's built-in tools where possible.
- Expose structured logs and OpenTelemetry signals only through integrations verified against the selected Deno runtime.

## Testing defaults
- Use Deno's permission-aware test runner and grant only the permissions required by each test group.
- Test Oak or Hono handlers with their in-process client, and test Fresh page behavior with the framework's supported utilities.
- Cover schema failures, permission denial, environment validation, and Deno KV or external database behavior separately.
- Keep lint and format checks deterministic and include import-lock integrity in dependency verification.

## Known uncertainty
- Fresh, Oak, and Hono have different rendering and middleware boundaries; the selected framework changes how much of the application can remain server-only.
- Deno Deploy, containers, and local Deno can expose different APIs and permission behavior, so deployment parity needs a target-specific probe.
- npm compatibility and URL import caching reduce migration friction but do not remove the need to audit import provenance.
