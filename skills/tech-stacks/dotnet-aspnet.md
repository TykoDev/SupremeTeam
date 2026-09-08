# .NET 9 and ASP.NET Core

## Baseline
- Use .NET 9 with C# 13, nullable reference types enabled, and ASP.NET Core as the HTTP host.
- Prefer Minimal APIs for a small new service and controller-based APIs when the application needs the additional structure of attributes and controllers.
- Use async/await with Task-based APIs and the built-in dependency injection container; use `Channel<T>` when producer and consumer work must be coordinated.
- Keep shared MSBuild settings in `Directory.Build.props` and treat the solution file as the application boundary.

## Project shape
- Keep domain entities, value objects, and interfaces in a dependency-light domain project.
- Keep use cases and DTOs in an application project, EF Core and external adapters in infrastructure, and endpoints, middleware, and DI setup in the web project.
- Separate unit and integration projects under `tests`; keep the solution and project files at the repository root.
- Make dependency direction visible in project references: domain first, application next, infrastructure and web at the edge.

## Data and API boundaries
- Use records for immutable request and response DTOs and separate them from domain entities.
- Use Data Annotations for simple constraints and FluentValidation for rules that span fields or depend on application state.
- Serialize through `System.Text.Json`, using source generation when AOT or startup constraints require it.
- Validate authentication, authorization, and input at the ASP.NET boundary before invoking application use cases; keep response mapping explicit.

## Migration and versioning
- Use EF Core 9 migrations as the versioned persistence contract and prefer Fluent API configuration for schema details.
- Keep migration review separate from application code review, and verify generated SQL against the supported database before release.
- Use Dapper only behind a narrow data access seam for measured SQL-sensitive paths; do not let it create a second persistence model accidentally.
- Recheck nullable warnings, options validation, and JSON source-generation output when moving between .NET major versions.

## Deployment
- Build and publish a release artifact with MSBuild, then use a multi-stage image with the .NET 9 ASP.NET runtime for hosted services.
- Run the service as a non-root process, expose the configured HTTP port, and inject production configuration through a managed secret source or environment.
- Keep health checks, structured `ILogger<T>` output, and OpenTelemetry instrumentation aligned with the hosting environment.
- Use Roslyn analyzers and `.editorconfig` as part of the same verification contract as the release build.

## Testing defaults
- Use xUnit or NUnit for unit tests and keep domain and use-case tests independent of the web host.
- Use `WebApplicationFactory<T>` for HTTP integration tests and Testcontainers or a deliberately scoped EF Core provider for persistence behavior.
- Test DTO validation, authorization policy outcomes, serialization, and health checks at their public boundaries.
- Keep mocking limited to interfaces whose external behavior is not practical to run in the test; prefer real in-memory or container-backed adapters for integration proof.

## Known uncertainty
- Minimal APIs and controllers offer different discoverability and filter surfaces; the choice should follow the existing application shape rather than a blanket preference.
- AOT, JSON source generation, and third-party middleware can impose constraints not visible in a normal development build.
- The source lists several secret providers and deployment modes; the selected hosting and identity contract must be verified separately.
