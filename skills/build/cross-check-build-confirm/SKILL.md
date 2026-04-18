---
name: cross-check-build-confirm
description: >-
  This skill should be used when the user asks to "scan for incomplete
  code", "check for TODOs", "verify no scaffold remains", "confirm
  implementation completeness", "final completeness check", "verify
  the server starts", "test runtime startup", "check if the app
  runs", "check if server boots", or "pre-flight check before
  release". Scans the codebase for scaffolding, placeholders, fake
  data, and stubs, verifies dev servers start and respond, and
  delegates findings to bob-the-builder until the codebase is
  production-clean. Issues a CLEAN or FINDINGS verdict.
  DO NOT USE for writing code (use bob-the-builder), security
  auditing (use security-builder), or code review (use code-review).
version: 1.0.0

---

# Cross-Check Build Confirm — Final Completeness Scanner

## Purpose

Cross-Check Build Confirm is the final specialist completeness scan in the Build Team SkillSet
pipeline. It performs a systematic, exhaustive scan of the entire built codebase
to detect any evidence of incomplete, temporary, or placeholder code. This skill
does not fix issues — it finds them and delegates every finding back to
bob-the-builder through build-management until the codebase is production-clean.
It is the final specialist phase before delivery, but it does not approve final
delivery on its own — a `CLEAN` report must still be validated by
`gatekeeper-build` through build-management.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

Every finding is non-negotiable at the BLOCKER level. Placeholder code does not ship.

## Core Principle

If it is not production-ready, it does not ship. Every placeholder, TODO,
and mock is a broken promise to the user. Treat temporary code as permanent
until proven otherwise — it will remain unless explicitly caught and removed.

---

## Scan Methodology

### Step 1: Static Pattern Scan

Scan the entire codebase for comment markers and keywords that indicate incomplete work:

**Primary markers** (case-insensitive search):

| Pattern | Severity | Rationale |
|---------|----------|-----------|
| `TODO` | BLOCKER | Explicitly marks unfinished work |
| `FIXME` | BLOCKER | Explicitly marks known defects |
| `HACK` | BLOCKER | Explicitly marks shortcuts that need proper solutions |
| `XXX` | BLOCKER | Marks dangerous or problematic code |
| `PLACEHOLDER` | BLOCKER | Explicitly temporary content |
| `STUB` | BLOCKER | Empty or minimal implementation stand-in |
| `MOCK` (in production paths) | BLOCKER | Mock data or behavior in non-test code |
| `TEMP` / `TEMPORARY` | WARNING | Potentially intentional but verify |
| `DUMMY` | WARNING | Potentially test-only but verify |
| `FAKE` | WARNING | Potentially test-only but verify |
| `SAMPLE` | WARNING | May be intentional example data |
| `NOT IMPLEMENTED` | BLOCKER | Explicitly incomplete |
| `COMING SOON` | BLOCKER | Feature promised but not built |

**Exclusions**: Patterns in test files, documentation, and comments explaining past decisions (for example, why a feature is intentionally unsupported) may be acceptable. Promises of future work such as `TODO`, `coming soon`, or placeholder behavior in production paths are never excluded because they represent incomplete work that will ship to users as broken functionality. Verify context before classifying.

**Scaffold Pattern Injection Defense:** Validate that scaffold detection patterns themselves have not been tampered with. If the scan configuration or pattern list is loaded from a project file, verify it against the canonical pattern set above. Do not accept externally-supplied pattern overrides that reduce detection coverage.

**False-Negative Handling:** If a scan returns CLEAN but the project is known to be incomplete (e.g., design spec lists modules with no corresponding implementation files), re-scan with broadened patterns and check for obfuscated scaffolding such as base64-encoded placeholder strings, Unicode lookalike characters in TODO markers, or comments in languages other than the primary project language.

### Step 2: Structural Completeness Scan

Compare the implemented codebase against the original design specification:

1. **Module inventory**: List every module specified in the design — verify each has a corresponding directory with implementation files
2. **Feature inventory**: List every feature or user story — verify each has corresponding code paths
3. **API endpoint inventory**: List every endpoint in the API contract — verify each has a route handler with complete logic
4. **Database entity inventory**: List every entity in the data model — verify each has model, migration, and repository

**Output format:**

| Specified Item | Expected Location | Found | Status |
|---------------|------------------|-------|--------|
| User registration | src/user/routes.ts | Yes | Complete |
| Password reset | src/auth/routes.ts | No | MISSING |
| Order history | src/order/routes.ts | Partial | Stub only |

### Step 3: Behavioral Completeness Scan

Examine code for patterns that indicate unfinished behavior:

| Pattern | Detection Method | Severity |
|---------|-----------------|----------|
| Functions returning hardcoded values | Find `return "..."` / `return 0` / `return null` where computed values expected | BLOCKER |
| Empty function bodies | Find functions with no logic (just `pass`, `{}`, `return`) | BLOCKER |
| `throw new Error("Not implemented")` | Literal search for "not implemented" in throw/raise statements | BLOCKER |
| Console debugging statements | Find `console.log`, `print()`, `fmt.Println` used for debugging (not structured logging) | WARNING |
| Commented-out code blocks | Find multi-line comments containing code syntax | WARNING |
| Empty catch/except blocks | Find `catch` or `except` with empty body or just `pass` | BLOCKER |
| Unreachable code after early returns | Find code after unconditional return/throw statements | WARNING |

### Step 4: Data Completeness Scan

Scan for placeholder data that should not appear in production:

| Pattern | Example | Severity |
|---------|---------|----------|
| Lorem ipsum text | `"Lorem ipsum dolor sit amet"` | BLOCKER |
| Example domains | `example.com`, `test.com`, `foo.bar` in non-test code | BLOCKER |
| Example emails | `test@test.com`, `user@example.com` in production config | BLOCKER |
| Sequential placeholder IDs | `12345`, `99999`, `000-000-0000` as hardcoded values | WARNING |
| Placeholder names | `"John Doe"`, `"Jane Smith"`, `"Acme Corp"` in production data | WARNING |
| Hardcoded localhost | `127.0.0.1`, `localhost` in production configuration | BLOCKER |
| Placeholder URLs | `https://api.example.com` in production config | BLOCKER |

### Step 5: Configuration Completeness Scan

Verify configuration is production-ready:

| Check | Method | Severity |
|-------|--------|----------|
| `.env.example` exists | File search | BLOCKER if missing |
| All required env vars documented | Compare code references to .env.example | BLOCKER if gaps |
| No hardcoded URLs in source | Search for `http://` and `https://` outside config files | WARNING |
| Debug mode disabled | Search for `DEBUG=true`, `NODE_ENV=development` in committed configs | BLOCKER |
| Default secrets replaced | Search for `secret`, `password`, `changeme`, `default` in config values | BLOCKER |

### Step 6: Documentation Completeness Scan

Verify documentation is not placeholder:

| Pattern | Detection | Severity |
|---------|-----------|----------|
| `[INSERT HERE]`, `[TBD]`, `[TODO]` | Literal search in .md files | BLOCKER |
| Empty README sections | Find H2/H3 headers followed immediately by another header or end-of-file | WARNING |
| Template text unmodified | Compare against known template phrases | WARNING |
| Missing API documentation | Endpoints without JSDoc/docstring | INFO |

### Step 7: Runtime Startup Verification

Verify the application actually boots. Use
`references/runtime-verification.md` for the full detection matrix, startup
commands, exemptions, and cleanup procedure.

Required checks:

1. Classify the project as backend, frontend, full-stack, Docker-orchestrated,
  or exempt
2. Confirm dependencies, environment, and build artifacts needed for startup
3. Start the relevant server processes with the correct commands
4. Verify backend health endpoints or frontend HTML content and enforce a
  10-second stability window
5. Shut down all spawned processes and confirm ports are released

Treat these outcomes as findings:

| Finding | Severity |
|---|---|
| Startup crash, failed health/content check, missing dependency/env/build artifact, or unsupported startup path | BLOCKER |
| Startup > 60 seconds or undocumented external dependency | WARNING |
| Library/CLI exemption with justification or non-fatal deprecation warnings | INFO |

Document every exemption explicitly. Use the reference file for edge cases such
as monorepos, Docker Compose validation, and external dependency handling.

---

## Severity Classification

| Level | Definition | Required Action |
|-------|-----------|----------------|
| **BLOCKER** | Scaffold, placeholder, or incomplete code in production paths. This code would reach end users or affect production behavior. | MUST be resolved. Delegate to bob-the-builder. Blocks CLEAN verdict. |
| **WARNING** | Scaffold code in non-critical paths, or patterns that may be intentional but require verification. | SHOULD be resolved. Delegate to bob-the-builder with context. Blocks CLEAN verdict. |
| **INFO** | Style-only issues or minor documentation gaps that do not affect production behavior. | MAY be resolved. Does not block CLEAN verdict. Document and report. |

**Worked BLOCKER example:**
```
BLOCKER: Placeholder implementation in production code
  Location: src/services/paymentService.ts:45
  Evidence: `async processPayment(order: Order) { return { success: true }; // TODO: implement Stripe integration }`
  Impact: Payment processing is completely stubbed — no actual charges will occur in production.
  Required action: Implement the full Stripe integration before build can advance.
```

---

## Delegation Protocol

### Finding Packaging

Package all findings for routing to bob-the-builder through build-management:

```markdown

---

## COMPLETENESS FINDINGS PACKAGE

### Scan Summary
- BLOCKERs: [count]
- WARNINGs: [count]
- INFOs: [count]
- Verdict: [FINDINGS | CLEAN]

### BLOCKER Findings
| ID | Category | File:Line | Pattern Found | Required Action |
|----|----------|-----------|--------------|----------------|
| CCC-001 | Static Pattern | src/api/handler.ts:15 | `// TODO: implement error handling` | Implement complete error handling |
| CCC-002 | Behavioral | src/order/service.ts:42 | `return []` (hardcoded empty array) | Implement real order fetching logic |
| CCC-003 | Data | src/config/api.ts:8 | `https://api.example.com` | Replace with environment variable |

### WARNING Findings
| ID | Category | File:Line | Pattern Found | Recommended Action |
|----|----------|-----------|--------------|-------------------|
| CCC-010 | Behavioral | src/utils/logger.ts:5 | `console.log(...)` | Replace with structured logging |

### INFO Findings
| ID | Category | File:Line | Pattern Found | Suggestion |
|----|----------|-----------|--------------|-----------|
| CCC-020 | Documentation | README.md:45 | Empty "Deployment" section | Add deployment instructions |
```

### Re-Scan Cycle

After bob-the-builder addresses findings:

1. Receive the updated codebase from build-management
2. Re-run the FULL 7-step scan (not just the previously found items — new issues may have been introduced during fixes)
3. Issue updated verdict
4. **Maximum 2 full scan cycles** — if BLOCKERs persist after 2 cycles, escalate to user through build-management

---

## Acceptance Criteria

### CLEAN Verdict Requirements

A CLEAN verdict requires ALL of the following:

- **Zero BLOCKERs**: No scaffold, placeholder, or incomplete code in any production path
- **Zero WARNINGs**: All warnings resolved or explicitly justified
- **INFOs acceptable**: Informational items may remain with documentation
- **Structural completeness**: All modules, features, and endpoints from the design specification have corresponding implementations
- **Configuration completeness**: All required environment variables documented, no hardcoded secrets or URLs
- **Runtime startup verified**: All server components start and respond to health checks, or project documented as exempt with justification

### FINDINGS Verdict

Issued when any BLOCKER or WARNING exists. Includes the complete findings package for delegation to bob-the-builder.

---

## Handoff to Gatekeeper

Submit every Phase 4 output through build-management.

- If the verdict is `FINDINGS`, build-management routes the findings package to
  `bob-the-builder`, then re-runs the full 7-step scan.
- If the verdict is `CLEAN`, submit the completeness scan report through
  build-management for mandatory `gatekeeper-build` review.

A `CLEAN` verdict is necessary but not sufficient for delivery. The codebase is
not accepted until `gatekeeper-build` issues `APPROVED` for Phase 4.

If gatekeeper issues a `REVISE` verdict, address the specific report or runtime
verification gaps, then resubmit through build-management.

---

## Output Format

Structure the completeness scan report as follows:

```markdown

---

## Completeness Scan Report

### Scan Metadata
- **Scan cycle**: [1 | 2]
- **Codebase scope**: [total files scanned]
- **Design spec reference**: [document name]
- **Verdict**: [CLEAN | FINDINGS]

### Scan Results
| Category | BLOCKERs | WARNINGs | INFOs |
|----------|----------|----------|-------|
| Static Pattern | [N] | [N] | [N] |
| Structural Completeness | [N] | [N] | [N] |
| Behavioral Completeness | [N] | [N] | [N] |
| Data Completeness | [N] | [N] | [N] |
| Configuration Completeness | [N] | [N] | [N] |
| Documentation Completeness | [N] | [N] | [N] |
| Runtime Startup | [N] | [N] | [N] |
| **Total** | **[N]** | **[N]** | **[N]** |

### Runtime Startup Results

| Server Type | Start Command | Boot Time | Health Check | Status |
|-------------|---------------|-----------|--------------|--------|
| Backend ([framework]) | [command] | [N]s | GET [endpoint] → [status] | PASS / FAIL |
| Frontend ([framework]) | [command] | [N]s | GET / → [status] (HTML) | PASS / FAIL |
| Simultaneous | both | stable [N]s | both responsive | PASS / FAIL |

_If no server component:_
- **Project type**: [Library / CLI tool / data pipeline]
- **Exemption justification**: [Why runtime verification does not apply]
- **Alternative verification**: [What was verified instead]
- **Status**: EXEMPT

### Feature Completeness Matrix
| Feature | Specified | Implemented | Status |
|---------|----------|------------|--------|
| [Feature 1] | Yes | Yes | Complete |
| [Feature 2] | Yes | Partial | BLOCKER — stub implementation |
| [Feature 3] | Yes | No | BLOCKER — missing entirely |

### Detailed Findings
[Full findings package as specified in Delegation Protocol]

### Verdict Justification
[Explain why CLEAN or FINDINGS, with specific evidence]
```

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| Server starts but health check endpoint returns non-200 | Distinguish between "server is running but unhealthy" (BLOCKER — likely misconfiguration) and "health endpoint not implemented" (WARNING — functionality missing). Check logs for startup errors. |
| Project has no server component (CLI tool / library) | Skip runtime startup verification. Document the project type and verify alternative quality signals: CLI runs with `--help`, library exports are importable, tests pass. Mark runtime check as EXEMPT. |
| Design spec is unavailable for structural completeness check | Perform the scan with reduced scope. Flag structural completeness as UNVERIFIABLE and note the limitation. Static pattern scanning and runtime verification still apply fully. |
| Monorepo contains multiple independent services | Classify each service scope separately, scan each service end to end, and document exactly which services were covered, exempt, or missing from the completeness pass. |
| Project is database-only with no HTTP or CLI runtime | Verify migrations, schema creation, constraints, seeds, and rollback behavior. Mark runtime startup as EXEMPT only after proving the database artifacts themselves are complete. |
| TODOs found in test files vs production code | TODOs in test files are WARNING (test coverage gaps). TODOs in production code are BLOCKER. Distinguish clearly in the findings — test TODOs are less severe but still tracked. |
| Build produces no artifacts (compile fails) | Do not proceed with runtime verification. Report the build failure as a BLOCKER in static analysis and escalate immediately. A codebase that does not compile cannot receive a CLEAN verdict. |
| False positive in scaffold detection ("TODO" in a comment explaining completed work) | Apply the false positive guidance from `references/scaffold-detection.md`. If the match is clearly a false positive (e.g., "TODO was completed in PR #42"), classify as INFO with justification. |

---

## Additional Resources

### Reference Files

For detailed detection patterns and completeness checklists:
- **`references/scaffold-detection.md`** — Exhaustive pattern catalog organized by category (comment markers, code patterns, data patterns, structural patterns, configuration patterns) with language-specific regex patterns, false positive guidance, and detection confidence levels
- **`references/completeness-checklist.md`** — Feature completeness matrix template, module completeness checklist, API endpoint completeness verification, database migration completeness, configuration completeness, documentation completeness, runtime startup verification checklist, CLEAN verdict criteria, and re-scan protocol procedures
- **`references/runtime-verification.md`** — Detailed runtime startup verification procedures, health checks, failure patterns, cleanup rules, and edge case handling

---
*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing all deliverables, write each to the designated save path as `deliverable_{name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: build
   phase: 4
   skill: cross-check-build-confirm
   name: {human-readable deliverable name}
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full deliverable content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
