# Rust 2024 and Axum 0.8+

## Baseline
- Use Rust 2024 Edition with Axum 0.8+ and Tokio for asynchronous services.
- Use Tokio's multi-threaded scheduler for concurrent work, preserve ownership and borrowing guarantees, and keep error intent explicit with `thiserror` for libraries and `anyhow` for applications.
- Use Axum extractors, method handlers, and Tower middleware as the HTTP boundary.
- Treat Cargo workspaces and reproducible lockfile resolution as the dependency and build baseline.

## Project shape
- Keep a service under `services/api` with pure domain models and errors, application use cases, infrastructure adapters, and API extractors and responses.
- Keep configuration and the executable entry under the service, and place reusable code in `shared_crates` only when the dependency direction is clear.
- Keep workspace members and shared dependency versions in the root `Cargo.toml`; keep migrations and environment documentation near the persistence adapter.
- Keep endpoint groups thin and pass domain ports into them rather than allowing handlers to own database or external service policy.

## Data and API boundaries
- Use serde and serde_json for wire serialization, `validator` for field constraints, and newtypes or enums for domain invariants.
- Keep request extractors, response types, and domain models distinct so wire naming does not dictate business representation.
- Use SQLx compile-time checked queries or a typed ORM behind an infrastructure port; keep database errors translated before they reach the public response.
- Make authentication, CORS, compression, and tracing Tower layers explicit at the HTTP assembly boundary.

## Migration and versioning
- Version SQLx or Diesel migrations with the service and verify SQLx queries against the supported database schema during the build process.
- Keep workspace dependency updates coordinated for Axum, Tokio, Tower, serde, and database drivers because their trait bounds can change together.
- Preserve error enums and public response mappings during refactors so clients do not depend on internal anyhow text.
- Recheck async cancellation and shutdown behavior whenever a synchronous adapter becomes a Tokio task.

## Deployment
- Build an optimized release binary with LTO and place it in a scratch or similarly small image when the service has no dynamic runtime dependency.
- Make certificates, environment values, and required filesystem paths explicit in a minimal image; do not assume shell-based diagnostics at runtime.
- Keep tracing, JSON logs, and OpenTelemetry export configured through the host environment and verify the exporter in the target runtime.
- Enforce Cargo formatting and Clippy checks as part of the release evidence.

## Testing defaults
- Use `#[cfg(test)]` modules and Cargo's test runner for domain and application behavior.
- Use in-process HTTP tests with an Axum `Router` and `tower::ServiceExt::oneshot` against a constructed request; use `reqwest` only when a bound server is specifically required.
- Use property tests for parsers, validators, and invariants where examples do not cover the input space.
- Test migration compatibility and graceful task shutdown separately from pure domain logic.

## Known uncertainty
- SQLx compile-time checking depends on database schema visibility and configuration, so a clean local compile does not alone prove production migration compatibility.
- Axum 0.8, Tower layers, and database driver versions interact through traits; adapter upgrades need compile and integration evidence together.
- Minimal images reduce operational surface but make certificates and diagnostics explicit deployment responsibilities.
