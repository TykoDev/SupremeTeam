# Detection Techniques Deep Dive

This reference provides detailed guidance on automated bug detection techniques beyond manual code review. Each technique targets different bug classes and complements human review.

---

## Static Analysis

### Meta's Infer

Infer is the gold standard for inter-procedural static analysis, using separation logic to trace bugs across function and module boundaries. This distinguishes it from intra-procedural tools that analyze functions in isolation.

**Key capabilities:**
- Detects null pointer dereferences, resource leaks, and data races across call chains
- Analyzes entire call graphs, not just individual functions
- Used in production at Meta for all Android and iOS applications
- Supports Java, C, C++, Objective-C

**When to recommend:** Codebases with complex data flows across module boundaries. Especially valuable for mobile applications and systems code where bugs manifest only through multi-function interactions.

**Integration pattern:** Run as part of CI on changed files and their transitive callers. Focus on new findings (diff analysis) to avoid noise from existing issues.

### SonarQube

SonarQube serves over 7 million developers across 400,000+ organizations. Version 26.2.0 combines SAST with LLM-based post-processing, reducing false positives by 91% compared to standalone scanning.

**Key capabilities:**
- "Clean as You Code" philosophy: quality gates applied only to new code
- Achieved false positive rates as low as 1% on mature codebases
- Pass/fail quality gates that block merges when critical issues detected
- Supports 30+ languages with unified dashboard

**When to recommend:** All projects as a baseline quality gate. Particularly effective for teams adopting quality practices incrementally — applying standards to new code without retroactive cleanup.

### Language-Specific Linters

- **Ruff (Python):** Rust-based, 10–100x faster than Flake8/Pylint. Replaces Flake8, Black, isort, pydocstyle in a single binary. Adopted by FastAPI and Pandas.
- **ESLint v10 (JS/TS):** Added multithreading and expanded beyond JavaScript to CSS, HTML, JSON, Markdown.
- **Oxlint (JS/TS):** Rust-powered alternative, 50–100x faster than ESLint. Use for extremely large codebases where ESLint performance is a concern.
- **golangci-lint (Go):** Meta-linter aggregating multiple Go linters with unified configuration.
- **clippy (Rust):** Catches non-idiomatic Rust patterns, especially important for AI-generated Rust code.

---

## Dynamic Analysis and Sanitizers

Sanitizers instrument compiled code to detect errors at runtime. They are particularly effective for memory-unsafe languages (C, C++, and partially Go and Rust unsafe blocks).

### AddressSanitizer (ASan)

Detects buffer overflows (stack, heap, global), use-after-free, use-after-return, and double-free. Typical slowdown: 2x. Memory overhead: 2–3x.

**Integration:** Compile with `-fsanitize=address`. Run full test suite with ASan enabled as a CI gate for memory-unsafe code.

### MemorySanitizer (MSan)

Detects reads of uninitialized memory. Catches subtle bugs where code depends on arbitrary memory contents. Requires all dependencies to be MSan-instrumented.

**Integration:** Compile with `-fsanitize=memory`. Most effective in controlled environments where all libraries can be recompiled.

### UndefinedBehaviorSanitizer (UBSan)

Detects undefined behavior: signed integer overflow, null pointer dereference, type punning violations, shift operations exceeding bit width.

**Integration:** Compile with `-fsanitize=undefined`. Low overhead — suitable for always-on in CI test runs.

### ThreadSanitizer (TSan)

Detects data races: unsynchronized concurrent access to shared memory. Reports the two conflicting accesses with full stack traces.

**Integration:** Compile with `-fsanitize=thread`. Memory overhead: 5–10x. Run concurrency-focused tests with TSan enabled. Particularly valuable for Go (`go test -race`) and C++ codebases.

**When to recommend sanitizers:** Any project in C, C++, or Rust (unsafe blocks). For Go, always recommend `-race` flag for test runs. Gate PR merges on sanitizer-clean test runs for memory-safety-critical code.

---

## Fuzzing

Coverage-guided fuzzing automatically generates inputs to maximize code coverage and trigger bugs. It is the industry standard for high-risk parsers, protocol handlers, and input-driven components.

### libFuzzer

LLVM's in-process, coverage-guided, evolutionary fuzzing engine. Linked directly with the code under test via the `LLVMFuzzerTestOneInput` harness format (the de facto standard).

**Key characteristics:**
- In-process: very fast iteration (millions of inputs per second)
- Coverage-guided: mutates inputs to explore new code paths
- Supports corpus management, minimization, and merge operations

**When to use:** Parsers (JSON, XML, protobuf, custom formats), compression/decompression, image processing, cryptographic operations, any code processing untrusted input.

### OSS-Fuzz

Google's continuous fuzzing service for open-source projects. Has found over 10,000 vulnerabilities and 36,000 bugs across 1,000+ projects. Uses ClusterFuzz as distributed execution environment.

**Key characteristics:**
- Continuous: runs 24/7, not just during CI
- Multi-engine: supports libFuzzer, AFL++, Honggfuzz
- Auto-reports bugs, auto-closes when fixed
- Free for open-source projects

### ClusterFuzzLite

Brings continuous fuzzing into CI workflows, explicitly targeting PRs to catch bugs before commit/merge. Lighter-weight than full OSS-Fuzz.

**When to use:** PR-scoped fuzzing for projects that cannot commit to full continuous fuzzing. Runs for a bounded time (e.g., 10 minutes) per PR to catch regressions.

### LibAFL

Rust library spin-off from AFL++. Achieved the highest median score on FuzzBench. Provides building blocks for custom fuzzers with pluggable mutation strategies, schedulers, and feedback mechanisms.

**When to use:** Custom fuzzing needs beyond standard harness-based fuzzing — protocol fuzzing, stateful fuzzing, or domain-specific mutation strategies.

### AFL++

Community-maintained fork of AFL with enhanced features: custom mutators, QEMU mode for binary-only fuzzing, persistent mode for faster iteration.

**Integration pattern for fuzzing:**
1. Write a harness function that takes fuzzer-generated bytes and feeds them to the code under test
2. Create a seed corpus of valid inputs as starting points
3. Run locally during development, then add to CI via ClusterFuzzLite
4. For critical parsers, enroll in OSS-Fuzz for continuous coverage
5. Triage crashes: minimize, deduplicate, classify (security vs correctness)

---

## Mutation Testing

Mutation testing measures test suite effectiveness by systematically introducing small code changes (mutants) and verifying that tests detect them. The mutation score (killed mutants / total non-equivalent mutants) provides a stronger signal than line or branch coverage.

### PIT (Java/JVM)

The gold standard for JVM mutation testing. Mutates bytecode, runs incrementally on changed code.

**Key capabilities:**
- Bytecode-level mutation (no source modification needed)
- Incremental analysis: only re-runs affected tests
- Multiple mutation operators: negate conditionals, remove void calls, change return values, boundary mutations

### Stryker (JavaScript/TypeScript/C#/Scala)

Multi-language mutation testing framework branded as "test your tests."

**Key capabilities:**
- AST-level mutation for JavaScript/TypeScript
- Dashboard for visualizing mutation results
- Incremental mode for PR-scoped analysis

### mutmut (Python)

Python-native mutation testing with AST-based mutation.

**Practical integration:**
- Run mutation analysis only on PR-changed files and their immediate dependencies
- Focus on critical modules where test confidence matters most
- 80–90% of mutation testing time is spent running tests — limit scope to manage cost
- A mutation score below 60% on changed code indicates weak test coverage
- Surviving mutants (mutations tests did not catch) reveal specific test gaps

**When to recommend:** Teams that need stronger assurance than line coverage for safety-critical, financial, or high-reliability code. Not recommended for test suites with slow execution times unless scoped to changed files only.

---

## Property-Based Testing

Property-based testing generates diverse inputs automatically, checking that properties (invariants) hold across all generated cases. More effective than example-based testing for algorithmic and mathematical code.

### Hypothesis (Python)

The most mature property-based testing framework. OOPSLA 2025 study analyzed 426 Python projects using Hypothesis with 7,125 property-based tests.

**Key findings from research:**
- Most mutations caught by a property-based test were found with a single input
- Thinking in terms of properties helps developers write fundamentally better tests
- Properties find bugs that example-based tests miss because they explore input spaces systematically

### fast-check (JavaScript/TypeScript)

JavaScript/TypeScript property-based testing framework with shrinking (automatic minimization of failing inputs).

### When to recommend property-based testing:
- Algorithmic code (sorting, searching, graph operations)
- Serialization/deserialization round-trip correctness
- Mathematical operations (commutativity, associativity, idempotency)
- State machine modeling (protocol implementations)
- Data transformation pipelines (input → transform → output preserves invariants)

**Integration pattern:**
1. Identify invariants that should hold for all valid inputs
2. Write property tests using `@given` decorators (Hypothesis) or `fc.property` (fast-check)
3. Let the framework generate edge cases automatically
4. Use shrinking to get minimal failing examples

---

## Formal Verification

Formal verification mathematically proves that code satisfies its specification. Historically limited to specialists, but LLM integration is making it more accessible.

### Dafny (with Z3 SMT Solver)

Dafny is a verification-aware programming language. DafnyPro (POPL 2026) achieved 86% correct proofs on DafnyBench using Claude Sonnet 3.5 — a 16 percentage point improvement over prior state-of-the-art. Amazon uses Dafny to verify cryptographic implementations in AWS.

### TLA+ (Leslie Lamport)

Standard for specifying concurrent and distributed systems. Used at Amazon and Microsoft for specifying and verifying distributed protocols.

**When to recommend formal verification:**
- Cryptographic implementations
- Consensus protocols and distributed systems
- Safety-critical control systems
- Code where testing cannot adequately cover the state space

Formal verification is the most rigorous technique but has the highest adoption barrier. Recommend only for code where the cost of a bug exceeds the cost of verification.
