# Bun 1.2+ and TypeScript

## Baseline
- Use Bun 1.2+ as the runtime, package manager, bundler, and built-in test runner for TypeScript services.
- Treat native TypeScript execution and ESM as the default; keep CommonJS only where a dependency requires it.
- Use a single event loop for I/O-bound work and move CPU-heavy work behind an explicit worker or separate service boundary.
- Choose Elysia for a typed full HTTP service, Hono for a portable edge service, or `Bun.serve()` for a deliberately small endpoint surface.

## Project shape
- Organize `src` by domain, with each domain keeping its endpoint, schema, service, and repository concerns close together.
- Keep shared middleware, errors, and utilities under `src/shared`; keep database schema and migration assets under `src/db`.
- Keep configuration in `src/config.ts`, the application entry in `src/index.ts`, and tests in `tests` or beside the code according to the repository convention.
- Treat `bunfig.toml`, `tsconfig.json`, `package.json`, and the lockfile as runtime and dependency contracts.

## Data and API boundaries
- Validate external input with Zod v4 or Elysia's TypeBox integration at the endpoint boundary, then derive internal types from the validated schema.
- Co-locate `*.schema.ts` files with their domain and keep request/response DTOs distinct from persistence records.
- Use Prisma or Drizzle for portable persistence, or Bun's SQLite driver only when embedded storage is an explicit product constraint.
- Validate required environment values at startup and inject production secrets through the host rather than committed `.env` files.

## Migration and versioning
- Keep Prisma Migrate or Drizzle Kit output versioned with the application and make connection-pool changes explicit in the migration notes.
- Audit native Node.js addons before switching a service to Bun; compatibility is not implied by npm package availability.
- Keep ESM and CommonJS interop at a narrow boundary, because changing module mode can affect imports, test discovery, and bundling.
- Recheck Bun's built-in SQLite behavior and ORM support when upgrading the runtime or changing database drivers.

## Deployment
- Produce a Bun-targeted bundle when bundling reduces startup or distribution cost, and keep the unbundled entry available for diagnostics when useful.
- Use a multi-stage image with a minimal Bun runtime and a non-root process for hosted services.
- Keep environment loading automatic only for local development; use a managed secret source in hosted environments.
- Preserve structured stdout logging and expose metrics or tracing through a Bun-compatible implementation.

## Testing defaults
- Use Bun's built-in test runner for unit tests and keep tests close to the domain behavior they prove.
- Exercise Elysia handlers through their in-process request method or Hono's test client rather than binding a real port for unit coverage.
- Use Playwright for browser-level flows and add persistence integration tests against the same database dialect used in production.
- Include a dependency audit and a compatibility check for native addons when the runtime version changes.

## Known uncertainty
- OpenTelemetry native compatibility is not guaranteed for every Bun dependency; verify the selected exporters and instrumentation in the target runtime.
- Elysia, Hono, and frameworkless serving have different middleware and typing surfaces, so the service boundary should record which one is chosen.
- Bun's lack of Deno-style permissions makes container isolation and dependency review part of the deployment assumption.
