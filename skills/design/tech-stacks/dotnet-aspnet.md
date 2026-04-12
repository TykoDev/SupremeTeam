# TECH STACK OVERLAY: C# / .NET 9 Backend

Applies to: Enterprise APIs, compliance-heavy systems (HIPAA/SOC2), Azure-integrated services
Runtime: .NET 9 | ASP.NET Core | Entity Framework Core 9

---

## Runtime and Execution Model

- **Language**: C# 13 with nullable reference types enabled
- **Runtime**: .NET 9 — cross-platform, high-performance, enterprise-grade
- **Concurrency**: async/await with Task-based patterns; built-in `Channel<T>` for producer/consumer
- **Build system**: MSBuild with `Directory.Build.props` for shared settings
- **DI**: Built-in dependency injection (`AddScoped`, `AddSingleton`, `AddTransient`)

---

## Framework Choices

- **API Framework (default)**: ASP.NET Core Minimal APIs — recommended for new projects per Microsoft
- **API Framework (enterprise)**: Controller-based APIs — more structure, attribute routing
- **Routing**: Minimal API `MapGet/MapPost` or `[Route]` attribute routing
- **Middleware**: ASP.NET Core middleware pipeline (`UseAuthentication`, `UseAuthorization`, etc.)

### Project Structure (Clean Architecture)

```
solution-root/
├── src/
│   ├── MyApp.Domain/              # Entities, value objects, interfaces (ZERO dependencies)
│   │   ├── Entities/
│   │   ├── ValueObjects/
│   │   ├── Interfaces/
│   │   └── MyApp.Domain.csproj
│   ├── MyApp.Application/         # Use cases, DTOs (depends: Domain)
│   │   ├── UseCases/
│   │   ├── DTOs/
│   │   ├── Interfaces/
│   │   └── MyApp.Application.csproj
│   ├── MyApp.Infrastructure/      # EF Core, external APIs (depends: Application)
│   │   ├── Data/
│   │   │   ├── AppDbContext.cs
│   │   │   └── Configurations/
│   │   ├── Repositories/
│   │   ├── Services/
│   │   └── MyApp.Infrastructure.csproj
│   └── MyApp.Web/                 # Controllers/endpoints, DI setup (depends: Application, Infrastructure)
│       ├── Endpoints/
│       ├── Middleware/
│       ├── Program.cs
│       └── MyApp.Web.csproj
├── tests/
│   ├── MyApp.UnitTests/
│   └── MyApp.IntegrationTests/
├── Directory.Build.props
├── MyApp.sln
├── Dockerfile
└── .env.example
```

---

## Data Contracts and Validation

- **Validation**: Data Annotations (`[Required]`, `[MaxLength]`) or FluentValidation for complex rules
- **DTOs**: Records for immutable request/response types
- **Serialization**: `System.Text.Json` (default) with source generators for AOT
- **Pattern**: Separate domain entities from API DTOs; map with AutoMapper or manual mapping

```csharp
public record CreateUserRequest(
    [Required][MaxLength(100)] string Name,
    [Required][EmailAddress] string Email,
    [Required] string Role
);

public record UserResponse(string Id, string Name, string Email, string Role);
```

---

## Persistence and Migrations

- **ORM**: Entity Framework Core 9 — type-safe, LINQ queries, migrations
- **Best practices**: Use `AddDbContextPool<T>()` for connection pooling, `AsNoTracking()` for reads, `Select()` projections
- **Configuration**: Fluent API via `IEntityTypeConfiguration<T>` over data annotations
- **Migrations**: EF Core migrations (`dotnet ef migrations add`, `dotnet ef database update`)
- **Alternative**: Dapper for raw SQL performance-critical queries

### EF Core Configuration Pattern

```csharp
public class UserConfiguration : IEntityTypeConfiguration<User>
{
    public void Configure(EntityTypeBuilder<User> builder)
    {
        builder.HasKey(u => u.Id);
        builder.Property(u => u.Email).HasMaxLength(255).IsRequired();
        builder.HasIndex(u => u.Email).IsUnique();
    }
}
```

---

## Configuration and Secrets

- **Local development**: `appsettings.Development.json` + User Secrets (`dotnet user-secrets`)
- **Production**: Azure Key Vault, AWS Secrets Manager, or environment variables
- **Pattern**: Options pattern with `IOptions<T>` for strongly-typed configuration
- **Validation**: `DataAnnotation` validation on options classes at startup

---

## Testing Strategy

- **Test framework**: xUnit (default) or NUnit
- **Unit tests**: Test use cases and domain logic in isolation
- **Integration tests**: `WebApplicationFactory<T>` for in-memory API testing
- **Mocking**: Moq or NSubstitute for interface mocking
- **Test DB**: Testcontainers or EF Core in-memory provider

---

## Observability

- **Framework**: OpenTelemetry .NET SDK (`OpenTelemetry.Extensions.Hosting`)
- **Auto-instrumentation**: ASP.NET Core, EF Core, HttpClient instrumentation packages
- **Logging**: `ILogger<T>` with structured logging; Serilog for sinks
- **Metrics**: Prometheus via OTel SDK or `dotnet-counters`
- **Health checks**: Built-in `AddHealthChecks()` with custom health check endpoints

---

## Build and Deployment

- **Build**: `dotnet build` / `dotnet publish`
- **Linting**: Roslyn analyzers + `.editorconfig` for code style enforcement
- **Container**: Multi-stage Docker with `mcr.microsoft.com/dotnet/aspnet:9.0-alpine` base
- **Output mode**: `output: standalone` for self-contained deployment
- **Release strategy**: Trunk-based with feature flags (LaunchDarkly, Unleash)

### Dockerfile Pattern

```dockerfile
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS builder
WORKDIR /app
COPY *.sln ./
COPY src/**/*.csproj ./src/
RUN dotnet restore
COPY . .
RUN dotnet publish src/MyApp.Web -c Release -o /publish

FROM mcr.microsoft.com/dotnet/aspnet:9.0-alpine AS runtime
WORKDIR /app
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
COPY --from=builder /publish ./
USER appuser
EXPOSE 8080
ENTRYPOINT ["dotnet", "MyApp.Web.dll"]
```

---

## Security Essentials

- **Auth**: ASP.NET Core Identity + JWT Bearer authentication
- **Authorization**: Policy-based authorization with `[Authorize]` attributes
- **CORS**: `AddCors()` with explicit policy configuration
- **Headers**: Built-in HSTS, X-Content-Type-Options via `UseHsts()`
- **Vulnerability scanning**: `dotnet list package --vulnerable`; NuGet auditing
