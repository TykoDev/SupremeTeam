# Debug Pattern Library — Common Bug Patterns by Category

## Race Conditions

### Signature
- Intermittent failures
- Timing-dependent behavior
- "Works on my machine" but fails under load
- Different results on each run

### Patterns

| Pattern | Language/Framework | Code Smell |
|---------|-------------------|-----------|
| **TOCTOU** (Time-of-check-to-time-of-use) | All | Checking a condition then acting on it without atomicity |
| **Lost update** | Database | Two transactions reading same row, both writing — last one wins |
| **Stale closure** | JavaScript/React | Closure captures a variable that changes after capture |
| **Double-checked locking** | Java/C# | Incorrect implementation of lazy initialization |
| **Concurrent map access** | Go | Reading/writing maps without sync.Mutex |
| **Shared mutable state** | All | Multiple coroutines/threads modifying the same data structure |

### Investigation Steps
1. Identify all shared mutable state in the affected code path
2. Check if access is synchronized (locks, transactions, atomic operations)
3. Add timing delays to amplify the race window and reproduce reliably
4. Check if the issue disappears under a debugger (Heisenbug indicator)

---

## Null/Nil/Undefined Propagation

### Signature
- NullPointerException, TypeError, NoMethodError
- "Cannot read property X of undefined"
- Crashes in seemingly unrelated code

### Patterns

| Pattern | Language | Code Smell |
|---------|---------|-----------|
| **Optional chaining gap** | TypeScript/JS | Missing `?.` on a chain where one link can be null |
| **Unguarded API response** | All | Assuming API always returns expected shape |
| **Partial initialization** | All | Object used before all fields are set |
| **Empty collection assumption** | All | Calling `.first()` or `[0]` without checking length |
| **Type narrowing failure** | TypeScript | Using `as` cast instead of type guard |

### Investigation Steps
1. Trace the null value backward from the crash site to its origin
2. Check every function boundary where the value is passed or returned
3. Identify the first point where null becomes possible (API call, database query, optional parameter)
4. Add null guards at the origin, not at the crash site

---

## State Corruption

### Signature
- Inconsistent data across related tables/objects
- Partial updates visible to users
- "Impossible" state combinations

### Patterns

| Pattern | Context | Code Smell |
|---------|---------|-----------|
| **Non-atomic multi-write** | Database | Multiple INSERT/UPDATE without a transaction |
| **Optimistic locking failure** | ORM | Version check missing on concurrent updates |
| **Event handler side effects** | UI frameworks | State mutation inside render/computed/effect |
| **Stale cache + write-through** | Caching | Cache invalidation race with database write |
| **Partial rollback** | Transactions | Error handling that rolls back some writes but not others |

### Investigation Steps
1. Identify all writes to the affected data in a single operation
2. Check if writes are wrapped in a transaction/atomic block
3. Check for callbacks, hooks, or triggers that fire during the operation
4. Reproduce with concurrent requests to verify consistency

---

## Integration Failures

### Signature
- Timeouts, connection refused, unexpected response format
- Works locally but fails against real services
- Intermittent 500 errors from external APIs

### Patterns

| Pattern | Context | Code Smell |
|---------|---------|-----------|
| **Schema drift** | API integration | Consumer expects field X, producer renamed it to Y |
| **Timeout cascade** | Microservices | Service A times out waiting for B, which times out waiting for C |
| **Retry amplification** | HTTP clients | Automatic retries creating N^depth requests |
| **SSL/TLS mismatch** | HTTPS | Certificate expired, wrong CA bundle, TLS version mismatch |
| **Rate limit exhaustion** | External APIs | Hitting API limits without backoff |
| **Serialization mismatch** | Cross-language | Different JSON serialization of dates, enums, or null values |

### Investigation Steps
1. Capture the exact request and response (headers + body)
2. Compare against the API documentation or contract
3. Check for recent changes to the external service (changelogs, status pages)
4. Test with a minimal standalone request to isolate from application logic

---

## Configuration Drift

### Signature
- "Works on my machine" / "Works locally, fails in CI"
- Behavior changes after deployment without code changes
- Feature flags in unexpected state

### Patterns

| Pattern | Context | Code Smell |
|---------|---------|-----------|
| **Missing env var** | Deployment | Code reads `process.env.X` without fallback or validation |
| **Default override** | Config files | Local config overrides production value, not caught in review |
| **Secret rotation** | Credentials | API key rotated but not updated in deployment config |
| **Feature flag staleness** | Feature management | Flag evaluated but never cleaned up, accumulating tech debt |
| **Database version skew** | Migrations | Code expects schema version N but database is at N-1 |

### Investigation Steps
1. Compare the environment (env vars, config files, secrets) between working and broken environments
2. Check if a deployment, migration, or infrastructure change occurred in the failure window
3. Verify all external dependencies are accessible from the failing environment
4. Check if the failure correlates with a specific environment (staging vs production vs local)

---

## Frontend-Specific Patterns

### Signature
- Visual glitches, broken layouts, unresponsive interactions
- "Works in Chrome, broken in Safari"
- Memory leaks in single-page applications

### Patterns

| Pattern | Framework | Code Smell |
|---------|----------|-----------|
| **Infinite re-render** | React | State update inside useEffect without dependency array |
| **Memory leak via listener** | All | addEventListener without corresponding removeEventListener |
| **Hydration mismatch** | Next.js/SSR | Server-rendered HTML differs from client render |
| **Z-index warfare** | CSS | Competing z-index values across components |
| **Event bubbling** | DOM | Click handler fires on parent instead of target |
| **Stale props** | React/Vue | Component receives old props due to parent memoization |

### Investigation Steps
1. Open browser DevTools, check Console for errors and Warnings
2. Use Performance tab to identify expensive renders or long tasks
3. Use Memory tab to check for growing heap (leak indicator)
4. Use Network tab to verify API requests match expectations
5. Test across browsers if the issue is visual or behavioral

---

## Performance Degradation

### Signature
- Gradually increasing response times
- High CPU or memory under normal load
- Specific endpoints or operations disproportionately slow
- Throughput drops under concurrent load

### Patterns

| Pattern | Context | Code Smell |
|---------|---------|-----------|
| **N+1 query** | ORM/Database | Loop executing one query per item instead of batch |
| **Missing index** | Database | Full table scans on frequently queried columns |
| **Unbatched I/O** | All | Sequential async calls that could be parallel |
| **Hot loop allocation** | All | Creating objects inside tight loops (GC pressure) |
| **Synchronous blocking** | Node.js/Python async | Blocking call inside async context starving the event loop |
| **Excessive serialization** | APIs | Serializing large object graphs when only a subset is needed |
| **Connection churn** | Database/HTTP | Opening new connections per request instead of pooling |

### Investigation Steps
1. Profile first — do not guess. Use flame graphs (CPU), allocation profilers (memory), or query analyzers (database)
2. Identify the single hottest path — optimize only that path
3. Measure before and after — quantify the improvement with the same workload
4. Check for load-dependent behavior — profile under realistic concurrency, not single-request

---

## Deployment & Infrastructure Mismatch

### Signature
- Works perfectly locally, fails on deploy
- Container starts but health checks fail
- Intermittent failures correlated with deploys or scaling events

### Patterns

| Pattern | Context | Code Smell |
|---------|---------|-----------|
| **Stale image tag** | Docker/K8s | Deploying `latest` tag that was not rebuilt |
| **Missing build arg** | CI/CD | Build-time variable absent in pipeline but present locally |
| **Port binding conflict** | Containers | App listens on 3000, Dockerfile EXPOSE is 8080 |
| **Filesystem assumption** | Containers | Code assumes writable `/tmp` or persistent local storage |
| **Startup order dependency** | Docker Compose/K8s | App starts before database is ready, no retry logic |
| **Resource limit OOM** | K8s | Container killed by OOM because memory limit is too low |

### Investigation Steps
1. Compare local run environment to deployment environment exhaustively (env vars, volumes, network, resources)
2. Check container logs from the orchestrator (not just app logs)
3. Verify health check endpoint matches what the load balancer or orchestrator expects
4. Test with the exact same image/artifact locally (not a fresh build)
