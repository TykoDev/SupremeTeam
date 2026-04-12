# TECH STACK OVERLAY: Go Backend

Applies to: Cloud-native microservices, CLI tools, high-concurrency APIs
Runtime: Go 1.23+ | Gin or Chi

---

## Runtime and Execution Model

- **Language**: Go 1.23+ with generics support
- **Runtime**: Single static binary — sub-millisecond startup, minimal memory footprint
- **Concurrency**: Goroutines + channels — lightweight green threads, built-in concurrency primitives
- **Module system**: Go Modules (`go.mod`) — standard dependency management
- **Error handling**: Explicit error returns with `errors.Is()`, `fmt.Errorf("context: %w", err)` for wrapping

---

## Framework Choices

- **HTTP Framework (popular)**: Gin — 48% adoption, middleware-rich, fast, ideal for beginners
- **HTTP Framework (idiomatic)**: Chi — `net/http` compatible, composable, preferred for clean architecture
- **HTTP Framework (performance)**: Echo — balanced structure and performance
- **Routing strategy**: Route groups by domain; Chi's `r.Route("/users", usersRouter)` pattern
- **Middleware**: Chi/Gin middleware chain (logging, recovery, CORS, auth)

### Project Structure (Standard Go Layout)

```
project-root/
├── cmd/
│   └── api/
│       └── main.go           # Application entry point
├── internal/
│   ├── auth/
│   │   ├── handler.go        # HTTP handlers
│   │   ├── service.go        # Business logic
│   │   ├── repository.go     # Data access
│   │   └── models.go         # Domain types
│   ├── users/
│   │   ├── handler.go
│   │   ├── service.go
│   │   ├── repository.go
│   │   └── models.go
│   ├── middleware/
│   ├── config/
│   │   └── config.go
│   └── database/
│       └── postgres.go
├── pkg/                       # Public reusable packages
│   └── validator/
├── api/
│   └── openapi.yaml
├── migrations/
├── go.mod
├── go.sum
├── Makefile
├── Dockerfile
└── .env.example
```

**Note**: The `internal/` directory is enforced by the Go compiler — external modules cannot import from it.

---

## Data Contracts and Validation

- **Struct tags**: Use `json`, `validate`, and `binding` struct tags
- **Validation**: `go-playground/validator` for struct validation
- **Serialization**: `encoding/json` (standard library) or `json-iterator` for performance
- **Pattern**: Define request/response DTOs separate from domain models

```go
type CreateUserRequest struct {
    Name  string `json:"name" validate:"required,min=1,max=100"`
    Email string `json:"email" validate:"required,email"`
    Role  string `json:"role" validate:"required,oneof=admin user viewer"`
}

type UserResponse struct {
    ID    string `json:"id"`
    Name  string `json:"name"`
    Email string `json:"email"`
    Role  string `json:"role"`
}
```

---

## Persistence and Migrations

- **ORM (rapid dev)**: GORM — developer-friendly, full-featured, ActiveRecord-style
- **SQL-first (performance)**: sqlc — SQL-first codegen, type-safe, best performance
- **SQL-first (flexible)**: sqlx — adds scanning/binding on top of `database/sql`
- **Complex schemas**: Ent — compile-time safety, code generation, graph traversal
- **Migrations**: `golang-migrate/migrate` CLI or GORM AutoMigrate (dev only)
- **Connection pooling**: `database/sql` built-in pool (`SetMaxOpenConns`, `SetMaxIdleConns`)

### Table-Driven Tests (Go Convention)

```go
func TestCreateUser(t *testing.T) {
    tests := []struct {
        name    string
        input   CreateUserRequest
        wantErr bool
    }{
        {"valid user", CreateUserRequest{Name: "Alice", Email: "a@b.com", Role: "user"}, false},
        {"missing name", CreateUserRequest{Email: "a@b.com", Role: "user"}, true},
        {"invalid role", CreateUserRequest{Name: "Alice", Email: "a@b.com", Role: "superadmin"}, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := validate.Struct(tt.input)
            if (err != nil) != tt.wantErr {
                t.Errorf("got error %v, wantErr %v", err, tt.wantErr)
            }
        })
    }
}
```

---

## Configuration and Secrets

- **Local development**: `.env` loaded via `godotenv` or `viper`
- **Production**: Environment variables injected by orchestrator
- **Validation**: Parse config at startup with strong types; use `viper` for multi-source config
- **Pattern**: Config struct populated from env vars, validated at startup

---

## Testing Strategy

- **Test framework**: Built-in `testing` package + `go test ./...`
- **Convention**: Table-driven tests with `t.Run()` subtests
- **HTTP testing**: `httptest.NewServer` + `http.Client` for handler tests
- **Mocking**: Interface-based mocking with `gomock` or `testify/mock`
- **Coverage**: `go test -cover -coverprofile=coverage.out`
- **Linting**: `golangci-lint` — aggregates 100+ linters

---

## Observability

- **Framework**: OpenTelemetry Go SDK (`go.opentelemetry.io/otel`)
- **Logging**: `slog` (standard library, Go 1.21+) — structured logging
- **Metrics**: Prometheus via OTel SDK
- **Tracing**: OTLP export; `otelgin` or `otelchi` middleware for automatic span creation

---

## Build and Deployment

- **Build**: `go build -ldflags="-s -w"` for stripped binaries
- **Linting**: `golangci-lint run`
- **Formatting**: `gofmt` / `goimports` (enforced)
- **Container**: Multi-stage Docker targeting `scratch` or `distroless` for minimal images
- **Binary**: Single static binary — ideal for minimal containers
- **Release strategy**: Trunk-based with feature flags

### Dockerfile Pattern

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /api cmd/api/main.go

FROM scratch
COPY --from=builder /api /api
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 3000
ENTRYPOINT ["/api"]
```

---

## Security Essentials

- **Input validation**: Validate all structs at handler boundary before passing to service layer
- **Auth**: JWT via `golang-jwt/jwt`; middleware-based authentication
- **CORS**: `rs/cors` middleware
- **Dependencies**: `govulncheck` for vulnerability scanning
- **Static analysis**: `gosec` for security-focused linting
