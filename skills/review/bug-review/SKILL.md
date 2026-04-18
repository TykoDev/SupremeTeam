---
name: bug-review
description: >-
  This skill should be used when the user asks to "find bugs in this code",
  "review for defects", "check for edge cases", "analyze error handling",
  "look for concurrency issues", "validate test quality", "check for null
  handling", "review boundary conditions", "check for race conditions",
  "assess error paths", "hunt for bugs", "what could go wrong here?",
  "sanity check this change", "what might break?", "check for bugs", or
  "is there a bug here?".
  Performs systematic bug detection across code changes using CWE-driven
  checklists, defect classification (logic/data/interface/concurrency/
  resource), and test-driven review methodology with severity and
  confidence levels per finding.
  DO NOT USE for security vulnerability analysis (use security-review).
  DO NOT USE for code quality assessment (use quality-review). DO NOT
  USE for general code review (use code-review).
version: 1.0.0
---

# Bug Finding Specialist

## Purpose

Perform systematic bug detection focused exclusively on correctness defects, logic errors, and reliability issues. This skill is distinct from security review (which focuses on exploitability and compliance) and code review (which applies a holistic 8-dimension assessment). The sole objective is to identify code that will produce incorrect results, crash, leak resources, corrupt data, or behave unpredictably under realistic conditions.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

## Core Methodology

The bug-finding methodology rests on three pillars derived from industry research and practice.

**CWE Top 25 as a Defect Checklist Driver.** Use the Common Weakness Enumeration Top 25 (2025 edition) to prioritize which bug classes to hunt for. Many CWE entries — buffer overflows, null pointer dereferences, integer overflows, improper input validation — are correctness bugs as much as security issues. Focus first on weaknesses that cause data corruption, crashes, and incorrect outputs.

**Google's Reviewer Focus Areas.** Google's publicly shared code review guidance directs reviewers to evaluate design correctness, functional behavior, edge cases, concurrency hazards, and test adequacy. Adopt this prioritization: architectural misfit first (highest impact), then logic errors, then edge cases and race conditions, then test gaps.

**Test-Driven Review.** Validate that tests are meaningful and would actually fail on regressions — not merely that tests exist. A test that asserts `true == true` provides zero defect detection value. Examine whether assertions target the behavior being changed, whether error paths are exercised, and whether boundary values are tested. Research (OOPSLA 2025) confirms that thinking in terms of properties helps developers write fundamentally better tests.

## Bug Detection Workflow

Follow these steps in order when reviewing code for bugs.

**Step 1: Identify Change Boundaries.** Map which functions, modules, and data flows are touched by the change. Identify entry points where external or upstream data enters the modified code. Determine which callers and downstream consumers are affected.

**Step 2: Apply the Defect Checklist.** For each changed function, systematically evaluate against the 8 bug class categories defined in `references/checklist.md`:
- Input validation and parsing edge cases
- Error handling and fail-closed behavior
- Concurrency hazards and unsafe shared state
- Resource management (handles, sockets, memory, connections)
- Boundary conditions and integer arithmetic
- Null/optional handling across API boundaries
- Logging and observability correctness
- Test meaningfulness and regression coverage

**Step 3: Trace Error Paths.** Follow every error return, exception throw, and failure mode through the call chain. Verify that errors propagate correctly, resources are cleaned up on failure, and callers handle error returns rather than ignoring them. Check that partial state mutations are rolled back or handled atomically.

**Step 4: Evaluate Concurrency and Shared State.** Identify all mutable state accessible from multiple threads, goroutines, or async tasks. Check for data races, deadlocks, and Time-of-Check vs Time-of-Use (TOCTOU) vulnerabilities. Verify that synchronization primitives (locks, atomics, channels) are used correctly and consistently. Flag any shared state modifications without synchronization.

**Step 5: Assess Test Quality.** Apply the test-driven review principle. For each changed behavior, verify:
- A test exists that exercises the changed code path
- Assertions validate the actual behavior, not trivial conditions
- Error paths and boundary values are tested
- Tests would fail if the change were reverted (regression value)
- Concurrent scenarios are tested where applicable
- Mutation-surviving test patterns are avoided (tests that pass regardless of code changes)

Treat a test as placeholder or low-value if it lacks a specific assertion,
only checks that code executes, or would still pass if the changed logic were
inverted.

**Step 6: Classify Findings by Severity.** Assign each finding a severity level using the classification rubric below, and record the evidence (specific code locations, execution conditions, expected vs actual behavior).

## Severity Classification

Assign findings using this three-tier rubric:

**Critical** — Data corruption, crash under normal operation, security-adjacent defect (null dereference in authentication path), infinite loop or deadlock reachable from production input, silent data loss. Requires immediate fix before merge.

**Major** — Incorrect output under non-trivial but reachable conditions, resource leaks in long-running services, race conditions that manifest under moderate concurrency, missing error handling that causes silent failures, test gaps on critical paths. Should be fixed before merge.

**Minor** — Cosmetic logic issues with negligible impact, unreachable dead code, redundant defensive checks, minor test improvements, logging enhancements. Fix at author's discretion; do not block merge.

For security-adjacent bugs, cross-reference with CVSS v4.0 scoring. For general defect classification and post-mortem analysis, apply IEEE 1044 or IBM Orthogonal Defect Classification (ODC) categories as described in `references/triage-workflow.md`.

**Worked bug trace:**

**Entry point:** `POST /api/orders` → `OrderController.create()`
**Logic error at:** `src/services/orderService.ts:67`
```typescript
// BUG: off-by-one in quantity validation
if (item.quantity > inventory.available) {  // should be >=
  throw new InsufficientStockError();
}
// When quantity === available, the order succeeds but inventory goes to -1
```
**Downstream impact:** Negative inventory allows overselling; warehouse ships orders it cannot fulfill.
**Catching test:**
```typescript
test('rejects order when quantity equals exact remaining inventory', () => {
  const inventory = { available: 5 };
  const order = { items: [{ productId: 'A', quantity: 5 }] };
  // This test fails on the buggy code (no exception thrown)
  expect(() => orderService.create(order, inventory))
    .toThrow(InsufficientStockError);
});
```
**Classification:** CWE-193 (Off-by-one Error), Severity: Major

## Detection Technique Recommendations

Beyond manual review, recommend specific detection techniques based on the code characteristics. Select the technique that best matches the bug class and language involved.

**Static Analysis** — For codebases with complex inter-procedural data flows, recommend Meta's Infer (uses separation logic to trace bugs across function and module boundaries). For general quality gates, recommend SonarQube with "Clean as You Code" configuration targeting new code only. Recommend static analysis when the code change introduces new call chains, cross-module data flows, or error propagation paths that are difficult to trace manually.

**Dynamic Analysis and Sanitizers** — For C, C++, and other memory-unsafe languages, require sanitizer-enabled CI runs: AddressSanitizer (buffer overflows, use-after-free), MemorySanitizer (uninitialized reads), UndefinedBehaviorSanitizer, ThreadSanitizer (data races). Recommend sanitizers when the change modifies memory management, pointer arithmetic, or concurrent data access in unsafe code. For Go, always recommend the `-race` flag for test runs.

**Fuzzing** — For parsers, protocol handlers, serialization/deserialization, and any input-heavy code, recommend coverage-guided fuzzing via libFuzzer (in-process, evolutionary) or ClusterFuzzLite (CI-integrated, targets PRs before merge). Google's OSS-Fuzz has found over 10,000 vulnerabilities and 36,000 bugs across 1,000+ projects. Recommend fuzzing when the change adds or modifies code that processes external or untrusted input formats.

**Mutation Testing** — To validate test suite strength beyond line coverage, recommend PIT (Java), Stryker (JavaScript/TypeScript/C#), or mutmut (Python). Focus mutation analysis on PR-scoped changes to manage execution cost. The mutation score (killed mutants / total non-equivalent mutants) provides a stronger signal than branch coverage alone. Research consistently shows mutation score correlates more strongly with real defect detection than statement or branch coverage. Recommend mutation testing when the change includes complex business logic with new test coverage that needs validation.

**Property-Based Testing** — For algorithmic or mathematical code, recommend Hypothesis (Python) or fast-check (JavaScript). Property-based tests find diverse bugs with few false alarms by exploring input spaces systematically rather than relying on hand-picked examples. Recommend property-based testing when the change involves data transformations, serialization round-trips, or mathematical operations where invariants can be expressed as properties.

**SARIF Output.** When recommending static analysis tools, prefer tools that output SARIF (Static Analysis Results Interchange Format) for standardized finding interchange. SARIF enables automated ingestion by CI/CD pipelines, code-chief cross-skill correlation, and gatekeeper-code validation. Tools supporting SARIF: CodeQL, Semgrep, ESLint (via sarif formatter), SonarQube (via export), Meta Infer (via sarif output).

**Formal Verification** — For cryptographic implementations, consensus protocols, and safety-critical control systems, recommend Dafny (with Z3 SMT solver) or TLA+ (for concurrent/distributed systems). Formal verification provides mathematical proof of correctness — recommend it when the cost of an undetected bug exceeds the cost of verification. See `references/detection-techniques.md` for DafnyPro results and integration guidance.

Consult `references/detection-techniques.md` for detailed guidance on each technique, including tool setup and integration patterns.

## Output Format

Structure the bug review report as follows:

```

---

## Bug Review Report
### Summary
- Total findings: [count] (Critical: [n], Major: [n], Minor: [n])
- Files reviewed: [list]
- Risk assessment: [High/Medium/Low]

### Findings
#### [BUG-001] [Category] — [Brief Title]
- **Severity:** Critical | Major | Minor
- **Location:** file:line
- **Description:** [What the bug is and under what conditions it manifests]
- **Evidence:** [Specific code path, input conditions, expected vs actual behavior]
- **Suggested Fix:** [Concrete fix or approach]
- **Test Recommendation:** [What test to add to prevent regression]

### Detection Gaps
- [Areas where automated detection tools would add value]

### Checklist Coverage
- [Which checklist categories were applied and which were not applicable, with justification]
```

Append the following structured summary block at the end of every report for
pipeline consumption:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 1
skill: bug-review
status: COMPLETE
risk_assessment: [High / Medium / Low]
finding_count:
  critical: [n]
  major: [n]
  minor: [n]
checklist_coverage: [percentage]
verdict: [High Risk / Medium Risk / Low Risk / Clean]
key_concerns: [top 3 findings by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation with review target scope, technology stack, and risk tier
- Execute the full defect detection workflow
- Submit the completed report to code-chief (not directly to gatekeeper-code)
- Include the structured pipeline summary block at the end of the report
- Code-chief owns the gatekeeper-code validation cycle in pipeline mode

**When invoked standalone:**
- Execute the full defect detection workflow independently
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` skill is available, perform a self-review pass applying the existence and proportionality checks described in the gatekeeper-code's challenge protocol

In both modes, prepare to defend each finding with specific evidence: code paths, reproducible conditions, and concrete expected-vs-actual behavior. The gatekeeper-code will challenge whether findings are real, whether severities are accurately calibrated, and whether important bug classes were missed given the nature of the code change.

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No test suite exists | Report as a Major finding (untestable code). Recommend specific detection techniques from `references/detection-techniques.md` as compensating controls. Manual review depth increases. |
| Change is configuration-only (no logic) | Focus on state corruption patterns: are defaults safe? Are types validated? Are migrations idempotent? Skip algorithm/logic bug classes. |
| Concurrency code without clear threading model | Do not assume single-threaded. Check for shared mutable state, async patterns, and event loop behavior. If the threading model is unclear, flag as a finding. |
| Third-party library code included in diff | Skip review of vendored/generated code. Review only the integration points and call sites. |
| Bug report provided but not reproducible | Document the attempted reproduction steps. Classify as Possible (not Proven). Flag for monitoring rather than immediate fix. |
| Massive diff (>1000 lines changed) | Focus on high-risk areas: entry points, data mutation, error paths, security boundaries. State the scope limitation. |
| AI-generated code in the diff | Increase scrutiny on boundary conditions, off-by-one errors, and hallucinated API calls because AI-generated code frequently compiles but silently mishandles edge cases. Verify every assertion in AI-written tests actually exercises the stated behavior. |
| Change spans multiple services with shared data contracts | Trace data flow across service boundaries. Check for schema version mismatches, backward-incompatibility in serialization, and missing validation at the receiving service. A bug in the contract affects all consumers. |

---

## Additional Resources

### Reference Files

For detailed checklists, detection techniques, and triage workflows, consult:

- **`references/checklist.md`** — Complete defect-focused reviewer checklist organized by 8 bug classes, with patterns, language-specific gotchas, and example findings for each category
- **`references/detection-techniques.md`** — Deep dive on static analysis (Infer, SonarQube), sanitizers (ASan, MSan, UBSan, TSan), fuzzing (libFuzzer, OSS-Fuzz, ClusterFuzzLite, LibAFL), mutation testing (PIT, Stryker, mutmut), and property-based testing (Hypothesis, fast-check)
- **`references/triage-workflow.md`** — Detailed triage process using IEEE 1044 and IBM ODC classification, severity rubrics, remediation workflow with repro artifact requirements, and defect metrics (density, escape rate, time-to-fix)

---
*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the review report, write it to the designated save path as `deliverable_{report-name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 1
   skill: bug-review
   name: Defect Report
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
