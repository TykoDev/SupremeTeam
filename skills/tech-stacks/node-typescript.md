# Node.js 22+ and TypeScript

## Baseline
- Use Node.js 22+ LTS with TypeScript 5.x in strict mode and native ESM as the default module model.
- Use `module: NodeNext` semantics with explicit `.js` import extensions in emitted-module source, and use Worker Threads only for measured CPU-bound work.
- Prefer Fastify 5 for a typed service, Express 5 for an established middleware ecosystem, or Hono for a portable edge service.
- Keep the event loop responsible for I/O and make backpressure, cancellation, and shutdown behavior explicit for long-lived work.

## Project shape
- Organize `src` by domain, keeping each domain's endpoint definitions, schemas, services, and repositories together.
- Keep shared middleware, errors, and utilities under `src/shared`; keep configuration and database access at the application edge.
- Keep tests in `tests` or beside source according to the existing convention, and keep `package.json`, `tsconfig.json`, and `biome.json` as the toolchain contract.
- Use a single `server.ts` or equivalent entry that assembles the application after configuration validation.

## Data and API boundaries
- Validate all external input with Zod v4 or Valibot at the HTTP boundary, then derive internal types from the validated schema.
- Co-locate `*.schema.ts` files with domain modules and keep request/response DTOs separate from database records.
- Prefer Prisma or Drizzle behind a repository seam, use projections to avoid unnecessary columns, and make connection-pool ownership explicit.
- Validate environment variables at startup and keep client-visible and server-only configuration in separate contracts.

## Migration and versioning
- Version Prisma Migrate or Drizzle Kit output with the service and review generated schema changes before releasing them.
- Keep ESM migration work incremental: update package metadata, TypeScript module resolution, import extensions, and test tooling as one compatibility set.
- Recheck Fastify plugins, Express middleware, and Hono adapters after a major runtime upgrade because package support is not uniform.
- Treat Node's built-in environment-file support as an optional local convenience, not a production secret-management policy.

## Deployment
- Use pnpm or the repository's existing lockfile, type-check with TypeScript, and bundle with esbuild or tsup only when the deployment target benefits from it.
- Use a multi-stage Node 22 image, copy only the release artifact and required dependencies, and run the process without root privileges.
- Inject production secrets through a managed source and retain structured Pino logging with trace context.
- Keep CI actions pinned and cloud identity permissions narrow when the repository owns its deployment workflow.

## Testing defaults
- Use Vitest for unit tests when the project has no established runner, with integration tests through Fastify's in-process client or `supertest`.
- Test schema rejection, configuration failure, graceful shutdown, and database transaction behavior at the public service seams.
- Use Playwright for full-stack browser flows and Pact when an independently deployed service needs a consumer contract.
- Use Testcontainers or an in-memory SQLite database only when its behavior matches the production persistence contract being proved.

## Known uncertainty
- Native ESM, package export maps, and test transforms can disagree across dependencies; verify the actual dependency graph before a module migration.
- Fastify, Express, and Hono differ in middleware order and error handling, so an adapter swap is not behavior-neutral.
- The source gives both hosted secret-provider and self-hosted deployment choices; the selected platform determines the final process and telemetry contract.
