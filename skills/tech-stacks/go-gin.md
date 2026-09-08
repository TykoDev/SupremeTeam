# Go 1.23+ and Gin

## Baseline
- Use Go 1.23+ with Go Modules, explicit error returns, and goroutines or channels only where concurrency ownership is clear.
- Use Gin as the default HTTP framework for this overlay; consider Chi or Echo only when their different middleware and composition model is an explicit decision.
- Keep handlers thin, keep business logic in services, and wrap errors with context while preserving `errors.Is` behavior.
- Treat the compiled static binary and the standard library concurrency model as the runtime baseline.

## Project shape
- Keep the application entry under `cmd/api`, domain packages under `internal`, and reusable public packages under `pkg` only when external reuse is intentional.
- Keep domain handlers, services, repositories, and models together under each internal feature; keep shared middleware, configuration, and database adapters separate.
- Keep OpenAPI descriptions under `api`, schema changes under `migrations`, and module metadata in `go.mod` and `go.sum`.
- Use the compiler-enforced `internal` boundary to prevent external packages from depending on private application details.

## Data and API boundaries
- Validate Gin request binding at the handler boundary using `json`, `validate`, and `binding` struct tags plus `go-playground/validator`.
- Keep request and response DTOs separate from domain models and serialize through `encoding/json` unless a measured need justifies another encoder.
- Group endpoints by domain and keep authentication, recovery, logging, and CORS middleware outside business services.
- Return wrapped errors with stable public error categories so callers do not depend on database or driver text.

## Migration and versioning
- Version SQL changes with `golang-migrate` or the repository's chosen migration library; treat GORM AutoMigrate as development-only convenience.
- Keep connection-pool limits explicit and review them with database capacity rather than inheriting driver defaults.
- Update `go.mod`, `go.sum`, and generated API artifacts together when changing a dependency or contract.
- Re-run static analysis after changing goroutine ownership, because a compile-clean concurrency change can still leak work or shutdown ordering.

## Deployment
- Build a stripped static binary and place it in a minimal scratch or similarly small image when the service has no dynamic runtime dependency.
- Provide CA certificates and required configuration explicitly in minimal images; do not assume a shell or package manager exists at runtime.
- Inject environment values through the host and keep structured logs, metrics, and trace context on stdout or the configured telemetry path.
- Keep `gofmt`, `goimports`, and `golangci-lint` aligned with the version selected in the module.

## Testing defaults
- Use the built-in testing package with table-driven cases and subtests for validation and domain behavior.
- Use `httptest` and an HTTP client for handler behavior, then use interface-based mocks only at external seams.
- Exercise database migrations and repository queries against the production dialect when practical, and record coverage with the repository's chosen tool.
- Run `govulncheck` and `gosec` alongside ordinary tests for dependency and source-level findings.

## Known uncertainty
- Gin is the baseline here, but the source also presents Chi and Echo; middleware behavior and composition cannot be assumed interchangeable.
- Scratch images reduce surface area but make certificates, time data, and diagnostics explicit deployment concerns.
- SQL generation, connection pools, and goroutine lifetimes need workload-specific checks beyond the static source conventions.
