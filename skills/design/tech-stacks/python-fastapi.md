# TECH STACK OVERLAY: Python + FastAPI Backend

Applies to: AI/ML APIs, data-heavy services, async microservices
Runtime: Python 3.12+ | FastAPI 0.115+

---

## Runtime and Execution Model

- **Language**: Python 3.12+ with full type hints
- **Runtime**: CPython 3.12+ with uvicorn ASGI server
- **Concurrency**: Async/await native with `asyncio`; use `ProcessPoolExecutor` for CPU-bound tasks
- **Package manager**: uv (by Astral) — 10-100× faster than pip, replaces pip + venv + pip-tools
- **Configuration**: `pyproject.toml` as single configuration hub

### pyproject.toml Configuration

```toml
[project]
name = "my-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
    "mypy>=1.13",
    "coverage>=7.0",
]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## Framework Choices

- **API Framework (default)**: FastAPI — async, auto-docs (OpenAPI), Pydantic integration, dependency injection
- **API Framework (enterprise)**: Django 5.x + DRF — batteries-included, admin panel, ORM
- **API Framework (lightweight)**: Flask 3.x — application factory pattern, minimal
- **ASGI server**: uvicorn (development) / gunicorn + uvicorn workers (production)
- **Middleware**: FastAPI middleware or Starlette `BaseHTTPMiddleware`

### Project Structure (Domain-First)

```
project-root/
├── src/
│   ├── auth/
│   │   ├── router.py
│   │   ├── schemas.py      # Pydantic models
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── service.py      # Business logic
│   │   ├── repository.py   # Data access
│   │   └── dependencies.py # FastAPI DI
│   ├── users/
│   ├── core/
│   │   ├── config.py       # pydantic-settings
│   │   ├── security.py
│   │   ├── middleware.py
│   │   └── exceptions.py
│   ├── db/
│   │   ├── database.py     # Engine/session factory
│   │   └── base.py         # Declarative base
│   └── main.py             # FastAPI app
├── alembic/
│   ├── versions/
│   └── env.py
├── tests/
│   ├── conftest.py
│   ├── test_auth/
│   └── test_users/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── Dockerfile
└── .env.example
```

---

## Data Contracts and Validation

- **Runtime validation**: Pydantic v2 — up to 50× faster than v1, Python type hint-based
- **API schemas**: Pydantic `BaseModel` for request/response schemas
- **Config validation**: `pydantic-settings` `BaseSettings` with `.env` support
- **Pattern**: Use `model_config = ConfigDict(from_attributes=True)` for ORM integration

```python
from pydantic import BaseModel, ConfigDict, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    role: str = "user"

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: EmailStr
    role: str
```

---

## Persistence and Migrations

- **ORM**: SQLAlchemy 2.0 with `Mapped` type annotations — async support, mature ecosystem
- **Migrations**: Alembic — version-controlled schema migrations
- **Alternative ORM**: SQLModel (by FastAPI creator) — combines SQLAlchemy + Pydantic
- **Connection pooling**: SQLAlchemy's built-in pool with `create_async_engine`
- **Query performance**: Use `Select` projections, avoid eager loading on large relations

### SQLAlchemy 2.0 Model Pattern

```python
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import String
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

---

## Configuration and Secrets

- **Local development**: `.env` file loaded via `python-dotenv` or `pydantic-settings`
- **Production**: Inject via secrets manager (AWS Secrets Manager, Vault, Infisical)
- **Validation**: `pydantic-settings` validates and types all env vars at startup

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    debug: bool = False
    log_level: str = "info"

    model_config = ConfigDict(env_file=".env")

settings = Settings()
```

---

## Testing Strategy

- **Test runner**: pytest 8.x with `pytest-asyncio`
- **HTTP client**: `httpx.AsyncClient` with FastAPI's `TestClient`
- **Fixtures**: `conftest.py` with database fixtures, test client factory
- **Coverage**: `coverage` or `pytest-cov`
- **Linting**: Ruff — single tool replacing Flake8 + isort + Black, 10-100× faster
- **Type checking**: mypy with strict mode

---

## Observability

- **Framework**: OpenTelemetry SDK for Python (`opentelemetry-sdk`)
- **Auto-instrumentation**: `opentelemetry-instrumentation-fastapi` + SQLAlchemy + httpx
- **Logging**: Structured JSON via `structlog` with OTel correlation
- **Metrics**: Prometheus export via OTel SDK
- **Tracing**: OTLP export to Grafana Tempo; W3C TraceContext

---

## Build and Deployment

- **Package manager**: uv for dependency management and virtual environments
- **Linter/formatter**: Ruff (single tool, 10-100× faster than flake8)
- **Type checker**: mypy with strict mode
- **Container**: Multi-stage Docker with `python:3.12-slim` base
- **Release strategy**: Trunk-based development with feature flags

### Dockerfile Pattern

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app appuser
COPY --from=builder /app/.venv ./.venv
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Security Essentials

- **Auth**: FastAPI security utilities (`OAuth2PasswordBearer`, JWT via `python-jose`)
- **Input validation**: Pydantic at every route boundary
- **CORS**: Configure `CORSMiddleware` explicitly with allowed origins
- **Rate limiting**: `slowapi` or custom middleware
- **Dependencies**: `uv audit` or `pip-audit`; generate SBOM
