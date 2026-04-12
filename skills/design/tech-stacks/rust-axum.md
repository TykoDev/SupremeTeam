# TECH STACK OVERLAY: Rust + Axum Backend

Applies to: Performance-critical APIs, safety-critical systems, high-throughput services
Runtime: Rust 2024 Edition | Axum 0.8+ | Tokio

---

## Runtime and Execution Model

- **Language**: Rust (2024 edition) — memory-safe without garbage collection
- **Runtime**: Tokio async runtime (multi-threaded work-stealing scheduler)
- **Concurrency**: Async/await with Tokio tasks; zero-cost abstractions; fearless concurrency
- **Build system**: Cargo with workspace support
- **Error handling**: `thiserror` for libraries, `anyhow` for applications

### Cargo Workspace Configuration

```toml
[workspace]
resolver = "3"
members = ["services/*", "shared_crates/*"]

[workspace.dependencies]
axum = { version = "0.8", features = ["macros"] }
tokio = { version = "1.45", features = ["full"] }
sqlx = { version = "0.8", features = ["runtime-tokio-rustls", "postgres"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "2.0"
anyhow = "1"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }
tower = "0.5"
tower-http = { version = "0.6", features = ["cors", "trace", "compression-gzip"] }
```

---

## Framework Choices

- **HTTP Framework**: Axum 0.8 — Tokio/Tower/Hyper native, type-safe extractors, Tower middleware ecosystem
- **Alternative**: Actix-web — slightly faster raw throughput, different concurrency model
- **Routing**: Axum's `Router` with method routers and nested route groups
- **Middleware**: Tower middleware stack (logging, CORS, compression, auth)

### Project Structure (Hexagonal Architecture)

```
project-root/
├── services/
│   └── api/
│       ├── src/
│       │   ├── domain/           # Pure business logic
│       │   │   ├── models.rs
│       │   │   ├── errors.rs
│       │   │   └── ports.rs      # Trait definitions (interfaces)
│       │   ├── application/      # Use cases / orchestration
│       │   │   ├── commands.rs
│       │   │   └── queries.rs
│       │   ├── infrastructure/   # Adapters (DB, external APIs)
│       │   │   ├── database.rs
│       │   │   └── repositories.rs
│       │   ├── api/              # Axum routers, extractors
│       │   │   ├── routes/
│       │   │   ├── extractors.rs
│       │   │   └── responses.rs
│       │   ├── config.rs
│       │   └── main.rs
│       └── Cargo.toml
├── shared_crates/
│   └── common/
│       └── src/lib.rs
├── Cargo.toml (workspace)
├── Dockerfile
└── .env.example
```

---

## Data Contracts and Validation

- **Serialization**: serde + serde_json for JSON handling
- **Validation**: `validator` crate for field-level validation rules
- **Type safety**: Rust's type system makes illegal states unrepresentable at compile time
- **API contracts**: Use newtypes and enums to enforce domain invariants

```rust
use serde::{Deserialize, Serialize};
use validator::Validate;

#[derive(Debug, Deserialize, Validate)]
pub struct CreateUser {
    #[validate(length(min = 1, max = 100))]
    pub name: String,
    #[validate(email)]
    pub email: String,
    pub role: UserRole,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum UserRole {
    Admin,
    User,
    Viewer,
}
```

---

## Persistence and Migrations

- **SQL-first (compile-time checked)**: SQLx — async, compile-time query verification against live DB
- **ORM (type-safe)**: Diesel — maximum type safety, synchronous
- **ORM (rapid dev)**: SeaORM — ActiveRecord patterns, async, code generation
- **Migrations**: SQLx migrations (`sqlx migrate run`) or Diesel CLI
- **Connection pooling**: SQLx built-in pool or `deadpool-postgres`

### SQLx Pattern

```rust
use sqlx::PgPool;

pub async fn find_user_by_id(pool: &PgPool, id: &str) -> Result<User, sqlx::Error> {
    sqlx::query_as!(User, "SELECT id, name, email, role FROM users WHERE id = $1", id)
        .fetch_one(pool)
        .await
}
```

---

## Configuration and Secrets

- **Local development**: `.env` loaded via `dotenvy` crate
- **Production**: Environment variables injected by orchestrator
- **Validation**: Parse and validate config at startup with strong types; fail fast on errors
- **Pattern**: Config struct with `envy` or manual `std::env` parsing

---

## Testing Strategy

- **Test framework**: Built-in `#[cfg(test)]` modules + `cargo test`
- **Integration tests**: `tests/` directory with `axum::test::TestClient`
- **HTTP testing**: `reqwest` for API-level tests
- **Mocking**: `mockall` crate for trait-based mocking
- **Property testing**: `proptest` for generative testing
- **CI**: `cargo clippy` for linting + `cargo fmt` for formatting

---

## Observability

- **Framework**: `tracing` crate (structured, span-based logging) + OpenTelemetry integration
- **Subscriber**: `tracing-subscriber` with JSON formatting for production
- **OTel export**: `opentelemetry-otlp` for trace/metric export
- **Tower integration**: `tower-http::trace::TraceLayer` for automatic request tracing

---

## Build and Deployment

- **Build**: `cargo build --release` with LTO for optimized binaries
- **Linting**: `cargo clippy` — Rust's official lint collection
- **Formatting**: `cargo fmt` — enforced style
- **Container**: Multi-stage Docker with `scratch` or `distroless` for minimal images
- **Binary size**: Single static binary — no runtime dependencies
- **Release strategy**: Trunk-based with feature flags

### Dockerfile Pattern

```dockerfile
FROM rust:1.83-slim AS builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY services/ ./services/
COPY shared_crates/ ./shared_crates/
RUN cargo build --release --bin api

FROM gcr.io/distroless/cc-debian12 AS runtime
COPY --from=builder /app/target/release/api /
EXPOSE 3000
CMD ["/api"]
```

---

## Security Essentials

- **Memory safety**: Guaranteed by Rust's ownership system — no buffer overflows, use-after-free
- **Dependencies**: `cargo audit` for vulnerability scanning; `cargo deny` for license compliance
- **Auth**: `axum-extra` for typed headers; JWT via `jsonwebtoken` crate
- **Headers**: `tower-http` for CORS, HSTS, content-type enforcement
- **Supply chain**: `cargo-vet` for dependency auditing
