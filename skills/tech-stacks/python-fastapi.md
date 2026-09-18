# Python 3.12+ and FastAPI 0.115+

## Baseline
- Use Python 3.12+ with full type hints, FastAPI 0.115+, and an ASGI server such as Uvicorn.
- Use async/await for I/O-bound work and isolate CPU-heavy work behind a process pool or separate worker boundary.
- Use uv for dependency and environment management, with `pyproject.toml` as the configuration hub.
- Keep FastAPI's OpenAPI generation and dependency injection aligned with explicit application boundaries rather than hiding behavior in global state.

## Project shape
- Organize `src` by domain, keeping each domain's endpoint handler, Pydantic schemas, models, service, repository, and dependency providers together.
- Keep cross-cutting configuration, security, middleware, and exceptions under `src/core`; keep engine and session setup under `src/db`.
- Keep Alembic versions and environment configuration under `alembic`, tests under `tests`, and dependency metadata in `pyproject.toml` and `uv.lock`.
- Keep `src.main` as the small application assembly point and keep business logic out of framework startup code.

## Data and API boundaries
- Use Pydantic v2 `BaseModel` types for request and response schemas, and validate every external payload before it reaches a service.
- Use `pydantic-settings` for typed configuration and keep ORM response models explicit with `from_attributes` where needed.
- Use SQLAlchemy 2.0 `Mapped` annotations and async engines for relational persistence; keep repositories responsible for session and query boundaries.
- Configure CORS and authentication explicitly at the FastAPI boundary, and return stable validation errors rather than leaking internal exceptions.

## Migration and versioning
- Use Alembic as the version-controlled schema migration system and review generated operations against the supported database.
- Keep SQLAlchemy model changes, Pydantic response changes, and migration files coordinated so reads and writes remain compatible during rollout.
- Pin Python, FastAPI, Pydantic, and Uvicorn compatibility in the project metadata; recheck async driver support on every major upgrade.
- Keep CPU-bound work out of the event loop when migrating synchronous code to async endpoints.

## Deployment
- Resolve dependencies from the locked project metadata and serve the application with a production ASGI process model suited to the host.
- Use a multi-stage Python 3.12 image, copy the application and locked environment, and run as a non-root process.
- Inject database URLs, signing material, and log settings through a managed secret source or environment; do not commit local environment files.
- Keep structured logs, OpenTelemetry instrumentation, and health behavior compatible with the selected worker count.

## Testing defaults
- Use pytest 8.x with pytest-asyncio for unit and asynchronous service tests.
- Use httpx AsyncClient or FastAPI TestClient for HTTP behavior, with database fixtures and a test-client factory under `conftest.py`.
- Test Pydantic rejection, dependency overrides, transaction boundaries, and Alembic migrations separately.
- Run Ruff and strict mypy checks with the test suite, and use coverage to identify unexercised domain and error paths.
- Send coverage output to the run, never the project root: resolve the destination with `scripts/output_paths.py --kind coverage` and set `COVERAGE_FILE=<dest>/.coverage` (or `--data-file`), with `--cov-report=<fmt>:<dest>/<name>` for every requested report format. Never use `-p`, `--parallel-mode`, or `parallel = True` unless the same command ends with `coverage combine` into that destination; per-process mode with nothing combining it leaves one `.coverage.<host>.<pid>.<rand>` file per worker at the root.

## Known uncertainty
- The source offers Uvicorn for development and a multi-worker ASGI arrangement for production; worker count and shared state need host-specific decisions.
- SQLAlchemy async behavior and external database drivers can expose different transaction semantics than local fixtures.
- FastAPI, Pydantic, and Python minor versions move together in the source baseline; pin and verify them as one compatibility set.
