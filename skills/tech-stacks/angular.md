# Angular 19+ standalone and signals

## Baseline
- Use Angular 19+ with standalone components as the default composition unit.
- Use signals for local and derived state, including `signal`, `computed`, `effect`, `input`, `output`, and `model` where their semantics fit.
- Treat strict TypeScript as the baseline. Client-side rendering is the default; add server-side rendering and hydration only when the product needs them.
- Prefer Angular's new control-flow syntax and `@defer` for explicit conditional, collection, and deferred work.

## Project shape
- Keep application code under `src/app` with `core` for singletons and cross-cutting services, `shared` for reusable UI pieces, and `features` for independently owned product areas.
- Keep feature models, services, and URL definitions close to their feature, with lazy loading at feature boundaries.
- Keep `app.component.ts` and `app.config.ts` as the small application shell; keep URL definitions with their feature code and environments, assets, and styles outside feature code.
- Treat `angular.json`, `package.json`, and `tsconfig.json` as the build and compiler contract.

## Data and API boundaries
- Use typed Reactive Forms with explicit `FormGroup` and `FormControl` shapes for user input.
- Type `HttpClient` request and response bodies, and use functional interceptors for authentication headers and consistent error translation.
- Keep API DTOs separate from view models; validate untrusted data at the HTTP boundary before storing it in signals.
- Use a signal store for shared feature state when local component signals are not sufficient, while keeping derived values read-only.

## Migration and versioning
- Preserve standalone component boundaries when upgrading and move legacy module declarations toward explicit imports incrementally.
- Replace decorator-based inputs and outputs with signal-based APIs only when the surrounding component contract can be updated together.
- Treat SSR and hydration as a paired compatibility surface; verify browser-only dependencies before enabling hydration.
- Recheck Angular CLI esbuild and legacy Webpack settings after a major upgrade rather than assuming their output is equivalent.

## Deployment
- Use the Angular CLI build output on a static host for client-rendered applications.
- Use a Node.js server and an SSR-capable adapter when server rendering or hydration is part of the product contract.
- Keep environment-specific values outside committed source and make the selected build configuration observable in release evidence.
- Keep ESLint with Angular-aware rules in the verification path; use npm or pnpm according to the existing lockfile.

## Testing defaults
- Use Karma/Jasmine or Jest for component and service tests, matching the repository's existing runner.
- Test signal transitions, typed form validation, HTTP serialization, and interceptor failure behavior at their owning boundary.
- Use Playwright for browser scenarios that cross standalone components, lazy feature loading, or hydration.
- Include a server-rendered and hydrated check when SSR is enabled; otherwise keep the browser suite client-only.

## Known uncertainty
- The source supports both client-only and SSR deployments, so the correct rendering mode remains a product decision rather than a framework default to copy blindly.
- NgRx SignalStore is useful for larger shared state, but its dependency and API version must be checked against the selected Angular release.
- The source lists both esbuild and legacy Webpack paths; build output and plugin compatibility need a repository-specific check after upgrades.
