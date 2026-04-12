---
name: quality-review
description: >-
  This skill should be used when the user asks to "review code quality",
  "check coding standards", "assess maintainability", "check for technical
  debt", "evaluate efficiency", "review best practices", "check architecture
  drift", or "evaluate code health". It evaluates maintainability, standards
  adherence, efficiency, and architectural alignment using Clean Code
  principles, architecture drift detection, and industry-standard metrics.
version: 1.0.0
---

# Code Quality, Efficiency & Best Practices Specialist

## Purpose

This skill evaluates long-term code health: maintainability, readability, standards compliance, architectural alignment, and computational efficiency. It is distinct from code-review (which applies a holistic 8-dimension assessment for merge readiness) because this skill goes deep on quality metrics, tooling recommendations, architecture drift detection, and technical debt measurement. The objective is to ensure the codebase remains sustainable, performant, and structurally sound over time — not just correct today.

## Clean Code in the AI Era

Code quality matters exponentially more when AI generates substantial portions of the codebase. AI models depend on the existing repository's abstractions, naming conventions, and architectural patterns to generate new code. If the codebase is messy, inconsistent, or poorly architected, AI systems absorb, mimic, and amplify that mess at massive scale. Software does not run on semantic meaning or intent — it runs on formal, precise, executable instructions. Code is the definitive formal anchor that ties business intent to deterministic behavior.

The "Clean as You Code" philosophy (pioneered by SonarQube) addresses this pragmatically: apply quality gates only to new and changed code, not the entire legacy codebase. This prevents technical debt accumulation in new work without requiring a massive retroactive cleanup. Quality gates on new code achieve false positive rates as low as 1% on mature codebases.

Clean, maintainable code enables AI agents to reason clearly, manage token limits effectively, and produce reliable outputs. Dirty code produces dirty AI outputs at scale — creating a compounding degradation loop.

## Standards Enforcement Framework

Apply a three-layer automation stack to enforce quality systematically.

**Layer 1 — Baseline Hygiene.** Formatters, linters, and type checkers provide the foundation. Every PR must pass these before human review begins:
- **Formatters:** Prettier (JS/TS), Black (Python), rustfmt (Rust), gofmt (Go) — eliminate all style debates
- **Linters:** Ruff (Python, 10–100x faster than Flake8/Pylint, replaces multiple tools), ESLint v10 (JS/TS, now multi-threaded with CSS/HTML/JSON support), Oxlint (Rust-powered JS linter, 50–100x faster), golangci-lint (Go)
- **Type Checkers:** mypy (Python, 58% adoption), Pyright (3–5x faster, powers VS Code Pylance), ty (Astral, 80x faster than Pyright on incremental checks), TypeScript strict mode (gold standard for JS/TS)

**Layer 2 — Semantic Analysis.** Deep analysis engines that understand code meaning beyond syntax:
- SonarQube quality gates with pass/fail enforcement on new code
- Meta's Infer for inter-procedural bug detection using separation logic
- CodeQL for semantic pattern matching across 30+ languages
- Semgrep with reachability analysis reducing false positives by up to 98%

**Layer 3 — AI-Assisted Review.** Contextual analysis of design, intent, and cross-file dependencies:
- AI reviewers for change risk assessment and design evaluation
- Intent analysis comparing the change against its stated purpose
- Cross-file dependency tracing for impact assessment

**Language-Specific Standards.** Enforce the authoritative style guide for each language:
- JavaScript/TypeScript: Airbnb Style Guide (const over let, no var, strict ESLint enforcement)
- C#/.NET: .editorconfig rules (IDE0017 object initializers, IDE0018 inline variables, IDE0016 throw expressions)
- Rust: Rust Style Guide with rustfmt + clippy (watch for non-idiomatic AI-generated Rust)
- Python: PEP 8 via Ruff, PEP 484 type hints enforced by type checker

Consult `references/standards-enforcement.md` for detailed tool configurations and language-specific rule sets.

## Architecture Review Protocol

Evaluate whether the code change respects the intended architecture using the C4 model as the documentation standard.

**C4 Model Validation.** The C4 model maps architecture across four levels of abstraction:
1. **System Context (Level 1):** How the system fits into the broader environment — actors, users, external integrations
2. **Containers (Level 2):** Separately deployable building blocks — web apps, APIs, databases, message brokers
3. **Components (Level 3):** Internal logical groupings within a container — domain services, handlers, clients
4. **Code (Level 4):** Implementation-level classes and interfaces — generally auto-generated from the codebase

**Architecture Decision Records (ADRs).** Verify that the change aligns with documented ADRs. If the change contradicts an existing ADR, it must either reference a new ADR that supersedes the old one or be flagged as architectural drift. ADRs capture context, alternatives considered, and consequences — not just the decision.

**Drift Detection.** Compare the live code against the documented architecture:
- Does the change respect defined module boundaries?
- Does it introduce new coupling between components that should be independent?
- Does it bypass established interfaces or create "shortcut" dependencies?
- Does it violate the layering defined in the C4 model (e.g., presentation layer directly accessing data layer)?

If architecture documentation exists, compute an informal drift score. Significant drift should block the merge or trigger an architecture review discussion.

Consult `references/architecture-review.md` for C4 evaluation procedures, ADR format templates, and drift scoring methodology.

## Efficiency Assessment

Evaluate computational efficiency and resource utilization for production-impacting code.

**Algorithmic Complexity.** Flag unnecessary O(n^2) operations where O(n) or O(n log n) alternatives exist. Check for nested loops over large collections, repeated linear searches that should use hash maps, and sorting operations inside loops.

**Resource Utilization.** Examine memory allocation patterns (large allocations in hot paths, unnecessary copies), connection pooling (database connections, HTTP clients), and caching strategy (missing caches for expensive computations, stale cache invalidation).

**Database Query Optimization.** Identify N+1 query patterns, missing indices on frequently queried columns, unnecessary joins, full table scans in production paths, and transaction scope issues (holding locks longer than necessary).

**Unnecessary Computation.** Flag redundant API calls, repeated parsing of the same data, missed memoization opportunities, and work performed inside loops that could be hoisted outside.

**Prioritization.** Focus efficiency review effort based on the code's execution context. For hot paths (request handlers, real-time processing, tight loops), algorithmic complexity and resource utilization are the highest priority. For batch jobs and background workers, database query optimization and connection management matter most. For startup and initialization code, efficiency concerns are typically lower priority unless they impact deployment speed. Flag efficiency findings only when the impact is measurable or the pattern is clearly suboptimal — avoid premature optimization suggestions on code that runs infrequently.

## Quality Metrics and Technical Debt

Measure and report on quality indicators that predict long-term maintainability.

**DORA Metrics Integration.** The 2025 DORA Report identifies seven performance archetypes. Track four key metrics: deployment frequency, lead time for changes, change failure rate, and mean time to recovery. Note the AI Productivity Paradox: AI tools boost individual output (21% more tasks, 98% more PRs merged per developer) while organizational delivery metrics remain flat.

**DX Core 4 Framework.** Extend beyond DORA by combining speed, effectiveness, quality, and business impact dimensions for a more complete picture.

**Technical Debt Indicators.** Report on measurable debt signals:
- Code duplication (DRY violations across modules)
- Cyclomatic and cognitive complexity (functions exceeding thresholds)
- Dependency staleness (outdated packages with known issues)
- Test coverage gaps on critical paths
- TODO/FIXME/HACK density and age

**Technical Debt Quantification.** Where possible, provide concrete measurements:
- CodeClimate maintainability rating (A through F, based on 10-point technical debt assessment)
- SonarQube technical debt ratio (remediation cost / development cost, with thresholds: A ≤5%, B ≤10%, C ≤20%, D ≤50%, E >50%)
- Cognitive complexity per function (threshold: ≤15 for most functions, ≤25 for complex business rules)

**ISO/IEC 5055:2021 Reference.** The first international standard for automated source code quality measurement. Defines four quality characteristics measurable from source code:
- **Reliability:** Defect patterns that cause failures (null pointers, resource leaks, unchecked returns)
- **Security:** Weakness patterns mapped to CWE (injection, broken access control, crypto failures)
- **Performance Efficiency:** Patterns causing excessive resource consumption (N+1 queries, memory bloat)
- **Maintainability:** Patterns reducing changeability (high coupling, deep nesting, complex conditionals)
When ISO 5055 compliance is relevant to the project, map quality findings to these four characteristics.

**IEEE 730-2026 Alignment.** For organizations requiring formal SQA processes, map findings to the four mandatory phases: Initiating (scope/criteria), Planning (strategies/gates), Controlling (metrics monitoring), Executing (validation/review).

Consult `references/metrics-and-debt.md` for detailed metric definitions, dashboard configurations, and IEEE 730-2026 process mapping.

## Output Format

Structure the quality review report as follows:

```
## Quality Review Report
### Summary
- **Quality Score:** Pass | Conditional | Fail
- **Architecture Drift:** None | Minor | Significant
- **Technical Debt Impact:** Reduced | Neutral | Increased
- **Findings:** [count by category]

### Standards Compliance
- [Formatting/linting results]
- [Type checking results]
- [Style guide adherence findings]

### Architecture Assessment
- [C4 alignment status]
- [ADR compliance findings]
- [Drift indicators]

### Efficiency Findings
- [Algorithmic concerns]
- [Resource utilization issues]
- [Database query issues]

### Technical Debt Assessment
- [New debt introduced]
- [Existing debt addressed]
- [Metrics impact]

### Tooling Recommendations
- [Missing or recommended automated checks]
```

Append the following structured summary block at the end of every report for
pipeline consumption:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 3
skill: quality-review
status: COMPLETE
risk_assessment: [High / Medium / Low]
finding_count:
  critical: [n]
  major: [n]
  minor: [n]
checklist_coverage: [percentage]
verdict: [Pass / Conditional / Fail]
quality_score: [Pass / Conditional / Fail]
architecture_drift: [None / Minor / Significant]
tech_debt_impact: [Reduced / Neutral / Increased]
key_concerns: [top 3 findings by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation with review target scope, Phase 1–2 context, and technology stack
- Execute the full quality review workflow (standards, architecture, efficiency, tech debt)
- Submit the completed report to code-chief (not directly to gatekeeper-code)
- Include the structured pipeline summary block at the end of the report
- Code-chief owns the gatekeeper-code validation cycle in pipeline mode

**When invoked standalone:**
- Execute the full quality review workflow independently
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` skill is available, self-validate by verifying that architectural drift claims reference specific documented constraints (ADRs, C4 models, or established conventions) and that efficiency findings cite measurable impact

In both modes, the gatekeeper-code will challenge whether quality claims are substantiated, whether architectural assessments are backed by evidence, and whether tooling recommendations are appropriate for the project's context. For security-specific or performance-testing concerns discovered during quality review, defer to the security-review or dedicated performance testing skills respectively.

## Additional Resources

### Reference Files

For detailed standards, architecture procedures, and metrics guidance, consult:

- **`references/standards-enforcement.md`** — Language-specific style guides and tool configurations for JavaScript/TypeScript, Python, C#/.NET, Rust, and Go, including the three-layer automation stack implementation details and Rust rewrite wave tooling comparisons
- **`references/architecture-review.md`** — C4 model evaluation procedures at all four levels, ADR format and lifecycle, architecture drift detection methodology with scoring, decision authority mapping, and common drift patterns (boundary violations, coupling creep, interface bypass)
- **`references/metrics-and-debt.md`** — DORA metrics definitions and the 7 archetypes, DX Core 4 Framework, AI Productivity Paradox analysis, IEEE 730-2026 SQA process integration, technical debt measurement, quality gate configuration, and code complexity metrics

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the review report, write it to the designated save path as `deliverable_{report-name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 3
   skill: quality-review
   name: Quality Report
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
