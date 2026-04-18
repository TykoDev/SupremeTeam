# Debug Methodology — Extended Investigation Techniques

## Bisection Strategy

When the root cause is in a regression (something that used to work):

### Git Bisect Protocol

1. Identify the last known good commit and the first known bad commit
2. Use binary search across the commit range to isolate the introducing commit
3. For each bisect step, run the minimal reproduction to classify as good/bad
4. The introducing commit reveals the exact change that caused the regression

**Automated bisection:**
```
git bisect start <bad-commit> <good-commit>
git bisect run <test-script>
```

**Manual bisection checklist:**
- [ ] Good commit confirmed (bug absent)
- [ ] Bad commit confirmed (bug present)
- [ ] Reproduction is deterministic enough for bisection
- [ ] Bisection result: commit `{hash}` introduced the regression

### Time-Based Bisection

When git bisect is impractical (e.g., database state changes, configuration drift):

1. Identify the approximate time window when the bug appeared
2. Check deployment logs, configuration changes, and infrastructure events in that window
3. Correlate timestamps with the first user report or monitoring alert
4. The causal event is usually the most recent change before the first report

---

## Distributed System Debugging

### Cross-Service Trace Analysis

1. **Correlation ID tracking:** Follow the request through all services using the correlation/trace ID
2. **Timeline reconstruction:** Build a timeline of events across services for the failing request
3. **Boundary inspection:** Check serialization/deserialization at service boundaries — type mismatches, missing fields, version skew
4. **Retry amplification:** Check if retry logic is amplifying the failure (retry storms, cascading timeouts)

### Database Investigation

1. **Query plan analysis:** Check if the failing operation has a degraded query plan (missing index, table scan, lock contention)
2. **Transaction isolation:** Check if concurrent transactions are interfering (phantom reads, dirty reads, deadlocks)
3. **Migration state:** Verify the database schema matches the code's expectations (pending migrations, partial rollbacks)
4. **Connection pool exhaustion:** Check if connections are being leaked or the pool is saturated

### Infrastructure Correlation

1. **Resource exhaustion:** Check CPU, memory, disk, network metrics at the time of failure
2. **Dependency health:** Check the health of all upstream and downstream dependencies
3. **DNS/certificate expiry:** Check for DNS resolution failures or expired TLS certificates
4. **Rate limiting:** Check if external APIs are throttling requests

---

## Advanced Tracing Methods

### Structured Logging Analysis

1. **Log level upgrade:** Temporarily increase log verbosity in the affected area
2. **Correlation filtering:** Filter logs by request ID, user ID, or session ID to isolate the failing flow
3. **Diff analysis:** Compare log output of a successful request with the failing request — the divergence point reveals the root cause
4. **Timing analysis:** Add timestamps to trace where time is spent — latency spikes indicate the bottleneck

### Memory and Resource Debugging

1. **Heap snapshot comparison:** Take heap snapshots before and after the operation — growing object counts indicate leaks
2. **Event loop blocking:** Check for synchronous operations blocking the event loop (Node.js: `--prof`, `--trace-warnings`)
3. **File descriptor tracking:** Check for unclosed files, sockets, or database connections
4. **GC pressure:** Check garbage collection frequency and duration — excessive GC indicates memory pressure

### Concurrency Debugging

1. **Thread dump analysis:** Capture thread dumps during the failure — deadlocks show as threads waiting on each other
2. **Lock ordering verification:** Check if locks are acquired in consistent order across code paths
3. **Atomic operation audit:** Verify that read-modify-write sequences are atomic (check for TOCTOU races)
4. **Channel/queue inspection:** Check if message queues or channels are full, empty, or mismatched in consumer/producer rates

---

## Investigation Anti-Patterns

### What NOT to do

| Anti-Pattern | Why It Fails | What to Do Instead |
|-------------|-------------|-------------------|
| **Shotgun debugging** (change random things) | Creates new bugs, obscures the real cause | Follow the 5-phase workflow systematically |
| **Fix-and-pray** (apply a fix without understanding why) | The fix may mask the symptom while the root cause persists | Prove the root cause before writing any fix |
| **Stack Overflow copy-paste** (apply a fix from a similar-looking error) | The error may be similar but the cause different | Verify the fix applies to YOUR specific code path |
| **Blame the framework** (assume the bug is in a library) | 99% of bugs are in application code | Prove the bug is in the library with a minimal reproduction |
| **Scope creep** (refactor while debugging) | Creates a large, unreviewed diff that may introduce new bugs | Use scope lock. Fix the bug only. Refactor later. |
| **Parallel hypothesis testing** (try multiple fixes at once) | Cannot determine which fix resolved the issue | Test one hypothesis at a time. Verify. Then move on. |

---

## Escalation Criteria

### When to STOP and escalate

1. **3 failed hypotheses:** The mental model is wrong. Fresh perspective needed.
2. **Intermittent reproduction:** Cannot trigger reliably. Need monitoring/instrumentation.
3. **Cross-team boundary:** The root cause is in code owned by another team. Provide evidence and hand off.
4. **Data-dependent:** The bug only occurs with specific data that cannot be reproduced locally. Need access to the affected data.
5. **Security-sensitive:** The bug involves sensitive data or security controls. Need security team involvement.
6. **Infrastructure-dependent:** The bug is in infrastructure (DNS, load balancer, CDN) not in application code. Need ops involvement.

---

## Environment-Specific Debugging

When a bug manifests in one environment but not another (the classic "works on my machine"):

### Systematic Environment Comparison

1. **Enumerate differences:** Create a two-column comparison of the working and broken environments:
   - Runtime version (exact patch level)
   - OS and architecture
   - Environment variables (diff, redacting secrets)
   - Network topology (proxies, firewalls, DNS resolvers)
   - Dependency versions (lock file diff)
   - Resource limits (memory, CPU, file descriptors)
   - Configuration files (diff all non-secret config)

2. **Binary search the differences:** If there are many differences, systematically align them one at a time until the bug appears or disappears. The last aligned variable is the cause.

3. **Container reproduction:** If the failing environment is containerized, pull the exact image and run it locally with the same env vars and volume mounts. If the bug reproduces, you have eliminated infrastructure as a variable.

4. **Network-layer isolation:** Use `curl -v` or equivalent to test each external dependency from the failing environment. Check for DNS resolution differences, TLS certificate issues, proxy interference, and firewall rules.

### Profiling Techniques by Runtime

| Runtime | CPU Profiling | Memory Profiling | I/O Profiling |
|---------|--------------|-----------------|---------------|
| **Node.js** | `--prof`, `--inspect` + DevTools | `--inspect` heap snapshot | `--trace-warnings`, async_hooks |
| **Python** | `cProfile`, `py-spy` | `tracemalloc`, `objgraph` | `strace`, `asyncio.debug` |
| **.NET** | `dotnet-trace`, `PerfView` | `dotnet-dump`, `dotnet-gcdump` | `dotnet-counters` |
| **Go** | `pprof` (CPU) | `pprof` (heap) | `trace` tool |
| **Java** | `async-profiler`, JFR | `jmap`, `MAT` | `jstack`, JFR I/O events |
| **Rust** | `perf`, `flamegraph` | `valgrind`, `heaptrack` | `strace`, `tokio-console` |
