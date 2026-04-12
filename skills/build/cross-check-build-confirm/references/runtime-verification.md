# Runtime Verification Reference

## Project Type Detection Matrix

### Detection Priority Order

Detect project type by examining files in this priority order:

| Priority | File / Pattern | Detection Logic | Project Classification |
|---|---|---|---|
| 1 | `docker-compose.yml` | Contains `services:` with port mappings | Docker-orchestrated (may be full-stack) |
| 2 | `package.json` (root) | Check `scripts` and `dependencies` | Node.js (classify further below) |
| 3 | `manage.py` | Django management script | Python Django backend |
| 4 | `main.py` or `app.py` with `uvicorn`/`flask` import | FastAPI or Flask entry point | Python API backend |
| 5 | `go.mod` + `main.go` | Go module with entry point | Go backend |
| 6 | `Cargo.toml` with `[[bin]]` or `src/main.rs` | Rust binary project | Rust backend |
| 7 | `pom.xml` or `build.gradle` | Java build file | Java backend |
| 8 | `Makefile` with `run` or `serve` target | Makefile-driven project | Classify by Makefile contents |

### Node.js Sub-Classification

| Signal | Classification |
|---|---|
| Dependencies include `express`, `fastify`, `koa`, `hapi`, `@nestjs/core` | Backend API |
| Dependencies include `react`, `vue`, `angular`, `svelte`, `solid-js` | Frontend SPA |
| Dependencies include `next`, `nuxt`, `remix`, `@sveltejs/kit`, `astro` | Full-stack SSR |
| Dependencies include `vite`, `webpack`, `parcel` (without backend framework) | Frontend build tool |
| Separate `client/` and `server/` directories each with `package.json` | Monorepo full-stack |
| `workspaces` in package.json with multiple packages | Monorepo (classify each workspace) |

### Start Command Resolution

For each project type, resolve the start command in this priority:

1. Explicit `scripts.dev` in `package.json` (preferred for development)
2. Explicit `scripts.start` in `package.json`
3. `Makefile` target: `dev`, `run`, `serve` (in that order)
4. `docker-compose.yml` with `docker compose up`
5. Language-specific default (e.g., `go run .`, `cargo run`, `python manage.py runserver`)

---

## Startup Verification Protocol

### Phase 1: Pre-Flight Checks

Before attempting to start any server, verify prerequisites.

#### Dependency Check

| Runtime | Check | Command | Failure Action |
|---|---|---|---|
| Node.js | `node_modules/` exists | `ls node_modules/` | Run `npm install` or report BLOCKER |
| Python | Virtual env or dependencies installed | `pip list` or check `.venv/` | Run `pip install -r requirements.txt` or report BLOCKER |
| Go | Module dependencies resolved | `go mod verify` | Run `go mod download` or report BLOCKER |
| Rust | Build dependencies resolved | Check `target/` or run `cargo check` | Run `cargo build` or report BLOCKER |
| Java | Build artifacts present | Check `target/` or `build/` | Run `mvn compile` or `gradle build` or report BLOCKER |
| Docker | Docker daemon running | `docker info` | Report BLOCKER with instruction to start Docker |

#### Environment Check

| Check | Method | Failure Action |
|---|---|---|
| `.env` file exists (if `.env.example` exists) | File search | Copy `.env.example` to `.env` or report BLOCKER |
| Required env vars have values | Parse `.env` for empty values; cross-reference code references | Report BLOCKER for each missing required variable |
| Database URL points to reachable host | Parse DATABASE_URL; attempt TCP connect to host:port | Report WARNING (may need external service) |
| No port conflicts | Check if target port is already bound | Report BLOCKER with port conflict details |

### Phase 2: Backend Startup

#### Startup Procedure

1. **Record environment state**: Note current port bindings, running processes
2. **Execute start command**: Run the identified start command in background
3. **Monitor stdout/stderr**: Capture all output during the startup window
4. **Detect startup completion**: Look for one of these indicators in stdout:
   - `listening on port` / `listening at` / `server started on`
   - `ready in` / `started server on`
   - `Application startup complete`
   - `Listening and serving HTTP on`
   - `Rocket has launched from`
   - Custom pattern from framework documentation
5. **Timeout**: If no startup indicator within 30 seconds, check if process is still running
   - If still running: Attempt health check anyway (some servers don't log startup)
   - If exited: Capture exit code and last 50 lines of output — report as BLOCKER

#### Health Check Procedure

Try endpoints in this order until one responds:

| Priority | Endpoint | Expected Response |
|---|---|---|
| 1 | `GET /health` | 200 with body |
| 2 | `GET /api/health` | 200 with body |
| 3 | `GET /healthz` | 200 |
| 4 | `GET /api/v1/health` | 200 |
| 5 | `GET /` | Any 2xx or 3xx |
| 6 | `GET /api` | Any 2xx or 3xx |

Health check timeout: 5 seconds per attempt. Maximum 3 retries with 2-second intervals.

#### Stability Window

After successful health check:
- Keep process running for 10 additional seconds
- Monitor for crashes (unexpected process exit)
- Monitor stdout/stderr for error-level log entries
- If stable: Record "PASS" with startup time and health check response

### Phase 3: Frontend Startup

#### Startup Procedure

1. **Execute start command**: Run frontend dev server in background
2. **Monitor stdout/stderr**: Capture output during startup window
3. **Detect compilation completion**: Look for:
   - `compiled successfully` / `compiled with warnings`
   - `ready in` / `ready on` / `ready -`
   - `Local:   http://localhost:`
   - `Compiled successfully` (Create React App)
   - `VITE` + `Local:` (Vite)
   - `event compiled client and server successfully` (Next.js)
4. **Timeout**: 60 seconds (frontend builds can be slower)

#### Content Verification

After detecting startup:

| Check | Method | Pass Criteria |
|---|---|---|
| HTTP response | GET to dev server URL | Response status 200 |
| Content type | Check Content-Type header | Contains `text/html` |
| Body content | Check response body | Contains `<html` or `<!DOCTYPE` |
| Root element | Check for app mount point | Contains `<div id="root">` or `<div id="app">` or `<div id="__next">` or similar |
| No error state | Check body for error markers | Does not contain "Cannot GET", "Module not found", "Compilation error" |

### Phase 4: Simultaneous Operation (Full-Stack)

1. Start backend (Phase 2 procedure) — verify healthy
2. Start frontend (Phase 3 procedure) — verify healthy
3. Confirm both processes are still running
4. Both health checks still pass
5. Hold for 10-second stability window
6. Shut down frontend first, then backend

### Phase 5: Process Cleanup

Mandatory after all verification:

1. Send SIGTERM to all started processes
2. Wait 5 seconds for graceful shutdown
3. If processes still running, send SIGKILL
4. Verify ports are released
5. Document any cleanup issues

---

## Common Failure Catalog

### Node.js Failures

| Error Pattern | Root Cause | Severity | Resolution |
|---|---|---|---|
| `Error: Cannot find module 'X'` | Missing dependency | BLOCKER | Run `npm install` |
| `EADDRINUSE :::3000` | Port 3000 already in use | BLOCKER | Kill conflicting process or change port |
| `SyntaxError: Unexpected token` | Syntax error in source | BLOCKER | Fix source code (bob-the-builder) |
| `TypeError: X is not a function` | Runtime type error | BLOCKER | Fix source code (bob-the-builder) |
| `Error: connect ECONNREFUSED 127.0.0.1:5432` | Database not running | WARNING | Document external dependency requirement |
| `TS2304: Cannot find name` | TypeScript compilation error | BLOCKER | Fix type errors (bob-the-builder) |

### Python Failures

| Error Pattern | Root Cause | Severity | Resolution |
|---|---|---|---|
| `ModuleNotFoundError: No module named 'X'` | Missing package | BLOCKER | Run `pip install -r requirements.txt` |
| `django.db.utils.OperationalError` | Database not available | WARNING | Document database requirement |
| `ImportError: cannot import name` | Circular import or missing export | BLOCKER | Fix imports (bob-the-builder) |
| `SyntaxError: invalid syntax` | Python syntax error | BLOCKER | Fix source code (bob-the-builder) |

### Go Failures

| Error Pattern | Root Cause | Severity | Resolution |
|---|---|---|---|
| `cannot find package` | Missing module dependency | BLOCKER | Run `go mod tidy` |
| `undefined: X` | Undefined reference | BLOCKER | Fix source code (bob-the-builder) |
| `bind: address already in use` | Port conflict | BLOCKER | Change port or kill process |

### Rust Failures

| Error Pattern | Root Cause | Severity | Resolution |
|---|---|---|---|
| `error[E0433]: failed to resolve` | Missing crate | BLOCKER | Add dependency to Cargo.toml |
| `error[E0382]: borrow of moved value` | Ownership error | BLOCKER | Fix source code (bob-the-builder) |

### Docker Failures

| Error Pattern | Root Cause | Severity | Resolution |
|---|---|---|---|
| `Cannot connect to the Docker daemon` | Docker not running | BLOCKER | Start Docker daemon |
| `port is already allocated` | Port conflict | BLOCKER | Free port or change mapping |
| `no such image` | Image not built/pulled | BLOCKER | Run `docker compose build` first |
| Container exits immediately | Application error inside container | BLOCKER | Check container logs |

---

## Edge Case Handling

### Libraries and CLI Tools

Projects without HTTP servers are exempt from runtime startup verification. To qualify for exemption:

| Requirement | Verification |
|---|---|
| No HTTP server dependency | `package.json` / `requirements.txt` / `go.mod` does not include web framework |
| No `serve`/`dev`/`start` script that launches a server | Verify scripts in package.json or Makefile |
| Project README describes it as a library or CLI | Documentation confirms non-server nature |

Alternative verification for exempt projects:
- **Libraries**: Verify the package can be imported/required without errors
- **CLI tools**: Verify `--help` or `--version` flag executes without error
- **Build tools**: Verify the tool runs its default command without error

### Monorepo Projects

For monorepos with multiple services:
1. Identify all packages/services with their own server entry points
2. Test each service independently
3. If a root-level command starts all services, test that as well
4. Report results per-service

### Projects Requiring External Services

When a project requires databases, message queues, or other external services:

| Approach | When to Use |
|---|---|
| Use docker-compose.yml | If project provides docker-compose with service dependencies |
| Skip external service checks | If no docker-compose and services are external (cloud-hosted) |
| Report as WARNING | If project needs external service but provides no way to start it locally |

Document which external services are required and how to provision them.

---

## Finding ID Convention

Runtime verification findings use the `CCC-1xx` range (100-199):

| Range | Category |
|---|---|
| CCC-100 to CCC-109 | Pre-flight check failures (dependencies, env vars) |
| CCC-110 to CCC-119 | Backend startup failures |
| CCC-120 to CCC-129 | Frontend startup failures |
| CCC-130 to CCC-139 | Simultaneous operation failures |
| CCC-140 to CCC-149 | Process cleanup failures |
| CCC-150 to CCC-159 | Edge case / exemption documentation |
