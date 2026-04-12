# Defect-Focused Reviewer Checklist

This checklist organizes bug detection into 8 categories derived from CWE Top 25 analysis, Google's reviewer guidance, and industry defect classification standards (IEEE 1044, IBM ODC). Apply each category to every changed function and data flow.

---

## 1. Input Validation and Parsing

**What to look for:**
- Missing validation on function parameters, API inputs, file contents, and deserialized data
- Insufficient length checks leading to buffer overflows or excessive memory allocation
- Missing format validation (dates, emails, URLs parsed without verification)
- Encoding mismatches (UTF-8 vs Latin-1 assumptions, BOM handling)
- Failure to handle malformed input gracefully (crash instead of error return)
- Implicit trust of data from "internal" sources that cross process boundaries

**Common patterns:**
- Function accepts `string` but assumes numeric content without parsing
- JSON/XML deserialization without schema validation
- Path concatenation without canonicalization (directory traversal as a correctness bug)
- Regex-based validation with catastrophic backtracking potential

**Language-specific gotchas:**
- Python: `int()` on user input without try/except; `json.loads()` without size limits
- JavaScript: Implicit type coercion (`"5" + 3` = `"53"`, not `8`); `parseInt` without radix
- Go: Ignoring error return from `strconv.Atoi()`; assuming `io.Reader` returns full buffer
- Rust: Unwrapping `Result`/`Option` without handling the error case
- Java: Not checking for negative indices; `Integer.parseInt` without bounds checking

**Example finding:**
> BUG-001 | Input Validation | Major | `api/handler.go:47` — `parseUserAge()` converts query parameter to integer using `strconv.Atoi()` but ignores the error return. Negative values and non-numeric strings cause downstream panic in `calculatePremium()`.

---

## 2. Error Handling and Fail-Closed Behavior

**What to look for:**
- Swallowed exceptions (empty catch blocks, ignored error returns)
- Incorrect error propagation (returning success when an error occurred)
- Missing cleanup in error paths (resources allocated before the error not freed)
- Error messages that expose internal state to callers
- Fallthrough to default/success paths when errors should abort
- Error handling that changes program state before determining success/failure

**Common patterns:**
- `try/catch` that catches `Exception` (too broad) and logs without re-throwing
- Go functions that return `(result, error)` but callers only check `result`
- Promise chains with missing `.catch()` handlers
- Database transactions not rolled back on partial failure

**Language-specific gotchas:**
- Python: Bare `except:` catching `SystemExit` and `KeyboardInterrupt`
- JavaScript: Unhandled promise rejections silently swallowed in Node.js
- Go: `defer file.Close()` ignoring the error return from `Close()`
- Java: Catching `Throwable` instead of specific exception types
- Rust: Using `unwrap()` in library code instead of propagating with `?`

**Example finding:**
> BUG-002 | Error Handling | Critical | `services/payment.py:89` — `charge_card()` wraps the payment API call in `try/except Exception` with only a log statement. The function returns `None` (interpreted as success by the caller) when the payment actually failed, leading to orders marked as paid without charging.

---

## 3. Concurrency Hazards and Unsafe Shared State

**What to look for:**
- Mutable state accessed from multiple threads/goroutines/async tasks without synchronization
- Data races: simultaneous read and write to the same memory location
- Deadlocks: lock acquisition ordering inconsistencies
- TOCTOU (Time-of-Check vs Time-of-Use): gap between checking a condition and acting on it
- Atomicity violations: multi-step operations that should be atomic but are not
- Lock scope issues: holding locks too long (blocking) or too briefly (not protecting the full critical section)

**Common patterns:**
- Shared map/dictionary modified concurrently without mutex
- Check-then-act patterns without atomic operations (`if not exists, then create`)
- Lazy initialization singletons without proper synchronization
- Callback or event handler modifying shared state without coordination
- File-based locking that does not account for NFS or network filesystem semantics

**Language-specific gotchas:**
- Go: Map access without sync.RWMutex; goroutine capturing loop variable by reference
- Python: GIL does NOT prevent data races on compound operations; `dict` operations not atomic
- JavaScript: Async/await race conditions between microtask queue operations
- Java: Non-volatile reads of shared fields; ConcurrentModificationException in iterators
- Rust: `unsafe` blocks bypassing the borrow checker; `Rc` used across threads (should be `Arc`)

**Example finding:**
> BUG-003 | Concurrency | Critical | `cache/store.go:112` — `globalCache` map is read by `GetItem()` and written by `SetItem()` across goroutines without synchronization. Under concurrent access, this causes a fatal `concurrent map writes` panic.

---

## 4. Resource Management

**What to look for:**
- File handles, sockets, database connections, or HTTP clients opened but never closed
- Resource leaks on error paths (resource acquired, error occurs, cleanup skipped)
- Connection pool exhaustion from unreturned connections
- Memory growth from accumulated caches without eviction
- Temporary files or directories not cleaned up
- Goroutine/thread leaks from spawned workers that never terminate

**Common patterns:**
- Opening a database connection per request without pooling
- Missing `defer close()` or `finally` blocks for cleanup
- Streaming responses without closing the body
- Timer/ticker not stopped, leaking goroutines
- Context cancellation not propagated to child operations

**Language-specific gotchas:**
- Go: `http.Response.Body` not closed; `time.After` in select loops leaking timers
- Python: File handles not using `with` statement; `requests.get()` response not closed
- JavaScript: EventListener references preventing garbage collection; readable streams not consumed
- Java: JDBC connections not returned to pool; `InputStream` not closed in finally
- Rust: Relying on `Drop` but not handling async cleanup correctly

**Example finding:**
> BUG-004 | Resource Management | Major | `db/queries.py:34` — `get_user_report()` opens a new database connection per invocation using `psycopg2.connect()` but never closes it. Under load, this exhausts the connection pool within minutes, causing `OperationalError: connection pool exhausted`.

---

## 5. Boundary Conditions and Integer Arithmetic

**What to look for:**
- Off-by-one errors in loop bounds, array indexing, string slicing
- Integer overflow/underflow in arithmetic operations
- Division by zero without guards
- Buffer size miscalculations (allocating n-1 or n+1 bytes)
- Unsigned integer underflow (subtracting from zero wrapping to MAX_VALUE)
- Floating-point comparison with equality (instead of epsilon range)
- Empty collection edge cases (first/last element access on empty lists)

**Common patterns:**
- Loop iterating `i <= length` instead of `i < length`
- Pagination calculating `totalPages = count / pageSize` without ceiling division
- Array index computed from user input without bounds checking
- Timestamp arithmetic crossing daylight saving time boundaries

**Language-specific gotchas:**
- C/C++: Signed integer overflow is undefined behavior; `size_t` underflow wraps to enormous value
- Go: Integer overflow wraps silently; `len()` on nil slice returns 0 (not panic)
- Python: Integers have arbitrary precision (no overflow) but list indexing can throw `IndexError`
- JavaScript: All numbers are IEEE 754 doubles; large integers lose precision above 2^53
- Rust: Debug builds panic on overflow; release builds wrap silently

**Example finding:**
> BUG-005 | Boundary Condition | Major | `utils/pagination.js:18` — `totalPages` calculated as `Math.floor(count / pageSize)` instead of `Math.ceil(count / pageSize)`. When items don't divide evenly, the last page of results is lost. For `count=11, pageSize=5`, returns 2 pages instead of 3.

---

## 6. Null/Optional Handling

**What to look for:**
- Null/nil/undefined dereferences on values returned from external APIs or database queries
- Optional chaining that silently produces undefined instead of surfacing errors
- Nullable types crossing API boundaries without null checks
- Default values that mask errors (defaulting to empty string or zero instead of handling absence)
- Null propagation through chains of method calls

**Common patterns:**
- Accessing properties of an API response without checking for null/404
- Database query returning null for missing records, caller assumes non-null
- Optional chaining (`?.`) hiding logic errors by producing undefined
- Destructuring assignments without defaults on nullable fields

**Language-specific gotchas:**
- JavaScript: `null` vs `undefined` confusion; `typeof null === 'object'`
- TypeScript: Non-null assertion operator (`!`) bypassing type safety
- Python: `None` comparisons using `==` instead of `is`; mutable default arguments
- Java: NPE from autoboxing (`Integer` to `int` on null); `Optional.get()` without `isPresent()`
- Go: Zero values for uninitialized pointers, slices, and maps; `nil` map panics on write
- Rust: Safe by design (`Option`/`Result`), but `unwrap()` turns safety into panics

**Example finding:**
> BUG-006 | Null Handling | Major | `components/UserProfile.tsx:67` — `user.address.street` accessed without null check. When the user has no address on file (returns `null` from API), this throws `TypeError: Cannot read properties of null`. Should use optional chaining or explicit null check.

---

## 7. Logging and Observability Correctness

**What to look for:**
- Error conditions logged without sufficient context (missing request IDs, user identifiers, input values)
- Log levels misassigned (errors logged at INFO, debug spam at WARN)
- Sensitive data in logs (passwords, tokens, PII, credit card numbers)
- Log injection vulnerabilities (user input embedded in log messages without sanitization)
- Missing logging at critical decision points (auth decisions, payment outcomes, data mutations)
- Structured logging not used where parsing is needed (free-text vs JSON)

**Common patterns:**
- `logger.error("Something went wrong")` without exception details or context
- Logging the full request body including authorization headers
- Interpolating user-supplied strings directly into log format strings
- Excessive debug logging left enabled in production paths

**Example finding:**
> BUG-007 | Logging | Minor | `middleware/auth.go:45` — Failed authentication attempts logged at DEBUG level instead of WARN. In production with DEBUG disabled, failed login attempts are invisible to monitoring, preventing brute-force detection.

---

## 8. Test Meaningfulness and Regression Coverage

**What to look for:**
- Tests that assert trivially true conditions (`assertTrue(true)`, `expect(1).toBe(1)`)
- Tests that do not exercise the changed code path
- Missing assertions (test runs code but never checks output)
- Tests that pass regardless of the code's behavior (mutation-surviving tests)
- Missing error path tests (only happy path covered)
- Missing boundary value tests (only typical values tested)
- Flaky tests (non-deterministic, time-dependent, order-dependent)
- Tests that mock so extensively they only test the mocking framework

**Common patterns:**
- Test creates a mock that returns the expected value, then asserts mock returned expected value
- Integration test that does not verify database state after operation
- Async test that does not await completion before asserting
- Test with no assertion failure message, making failures hard to diagnose

**Key principle:** A meaningful test would fail if the change it covers were reverted. If reverting the code change would not cause any test to fail, there is a regression coverage gap.

**Example finding:**
> BUG-008 | Test Quality | Major | `tests/test_calculator.py:23` — Test for `divide()` only checks `divide(10, 2) == 5`. Does not test division by zero, negative numbers, or floating-point edge cases. The `divide()` function has no zero-division guard, and this test would not catch its introduction or removal.
