---
name: quality-review
description: >-
  This skill should be used when the user asks to "review code quality",
  "check coding standards", "assess maintainability", "check for technical
  debt", "evaluate efficiency", "review best practices", "check architecture
  drift", "evaluate code health", "how clean is this code?", "run a
  maintainability audit", "audit the code", or "rate this codebase". Evaluates
  maintainability, standards adherence,
  efficiency, and architectural alignment using Clean Code principles,
  architecture drift detection, and industry-standard metrics. Produces
  a scored quality report with prioritized improvement recommendations.
  DO NOT USE for bug detection (use bug-review). DO NOT USE for
  security vulnerabilities (use security-review). DO NOT USE for
  frontend visual issues (use design-qa).
version: 1.0.0
---

# Code Quality, Efficiency & Best Practices Specialist

## Purpose

This skill evaluates long-term code health: maintainability, readability, standards compliance, architectural alignment, and computational efficiency. It is distinct from code-review (which applies a holistic 8-dimension assessment for merge readiness) because this skill goes deep on quality metrics, tooling recommendations, architecture drift detection, and technical debt measurement. The objective is to ensure the codebase remains sustainable, performant, and structurally sound over time — not just correct today.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

---

## Workflow

### Step 1: Validate Review Inputs

Validate the review inputs themselves before scoring. If the supplied diff,
file list, or architecture context is incomplete, say so explicitly instead of
pretending the quality signal is complete.

1. Confirm the review target is defined (specific files, a PR diff, or the full codebase)
2. Identify the primary language(s) and framework(s) in scope
3. Check whether architecture documentation exists (ADRs, C4 models, conventions docs)
4. Check whether automated tooling is already configured (linters, formatters, type checkers)
5. Record any gaps as open constraints — do not silently assume completeness

### Step 2: Enforce Standards Compliance

Apply the three-layer automation stack to evaluate code hygiene systematically.

1. **Layer 1 — Baseline Hygiene**: Check formatter, linter, and type-checker compliance for the project's language(s). If tooling is not configured, report as a Critical finding and recommend the minimum viable stack.
2. **Layer 2 — Semantic Analysis**: Check for deep quality signals — SonarQube gate status, static-analysis findings, or equivalent tooling output. If unavailable, state the gap.
3. **Layer 3 — AI-Assisted Review**: Evaluate change-risk, intent alignment, and cross-file dependency impacts.
4. **Language-Specific Standards**: Verify adherence to the authoritative style guide for each language (Airbnb for JS/TS, PEP 8 for Python, Rust Style Guide for Rust, .editorconfig for C#/.NET).

Consult `references/standards-enforcement.md` for detailed tool configurations, language-specific rule sets, and the Rust rewrite wave tooling comparisons.

### Step 3: Assess Architecture Alignment

Evaluate whether the code change respects the intended architecture.

1. **C4 Model Validation**: If C4 documentation exists, validate the change against all four levels (System Context → Containers → Components → Code). If no documentation exists, skip to drift detection and note the gap as a Major finding.
2. **ADR Compliance**: Verify the change aligns with documented Architecture Decision Records. If a change contradicts an existing ADR without referencing a superseding ADR, flag as drift.
3. **Drift Detection**: Check module boundary respect, coupling between independent components, interface bypass, and layering violations. Compute an informal drift score when documentation exists.

Consult `references/architecture-review.md` for C4 evaluation procedures, ADR format templates, and drift scoring methodology.

### Step 4: Evaluate Efficiency

Assess computational efficiency and resource utilization for production-impacting code. Prioritize based on execution context: hot paths get full algorithmic analysis; startup code gets lighter treatment.

1. **Algorithmic Complexity**: Flag unnecessary O(n²) operations where O(n) or O(n log n) alternatives exist. Check for nested loops over large collections and repeated linear searches.
2. **Resource Utilization**: Examine memory allocation in hot paths, connection pooling, and caching strategy.
3. **Database Query Optimization**: Identify N+1 query patterns, missing indices, unnecessary joins, full table scans, and transaction scope issues.
4. **Unnecessary Computation**: Flag redundant API calls, repeated parsing, missed memoization, and loop-hoistable work.

Flag efficiency findings only when the impact is measurable or the pattern is clearly suboptimal — avoid premature optimization suggestions.

### Step 5: Measure Technical Debt

Report on quality indicators that predict long-term maintainability.

1. **Technical Debt Indicators**: Measure code duplication (DRY violations), cyclomatic and cognitive complexity (threshold: ≤15 per function, ≤25 for complex rules), dependency staleness, test coverage gaps on critical paths, and TODO/FIXME/HACK density.
2. **Quantification**: Where tooling is available, report CodeClimate maintainability rating (A–F), SonarQube technical debt ratio (A ≤5%, B ≤10%, C ≤20%, D ≤50%, E >50%), or cognitive complexity per function.
3. **Standards Mapping**: Map findings to ISO/IEC 5055:2021 (Reliability, Security, Performance Efficiency, Maintainability) and IEEE 730-2026 SQA phases because industry-standard mapping enables cross-team comparability and audit trail.

Consult `references/metrics-and-debt.md` for detailed metric definitions, DORA/DX Core 4 framework operationalization, and IEEE 730-2026 process mapping.

### Step 6: Compile Quality Report

Structure the report per the Output Format section below. Every finding must cite a specific file:line, code excerpt, and the standard or metric it violates. Append the machine-readable Pipeline Summary block.

### Step 7: Submit for Review

If operating in pipeline mode (delegated by code-chief):
- Return the completed report to code-chief with the structured pipeline summary block
- Code-chief owns the gatekeeper-code validation cycle

If operating in standalone mode:
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` is available, self-validate by verifying that architectural drift claims reference specific documented constraints and efficiency findings cite measurable impact
- Address any REVISE findings and resubmit until APPROVED

---

## Output Format

```markdown
# QUALITY REVIEW REPORT

## Quality Verdict: [Pass / Conditional / Fail]

## Standards Compliance
| Layer | Status | Tool / Method | Key Findings |
|-------|--------|---------------|--------------|
| 1 — Baseline Hygiene | [Pass/Fail/Gap] | [tool] | [summary] |
| 2 — Semantic Analysis | [Pass/Fail/Gap] | [tool] | [summary] |
| 3 — AI-Assisted Review | [Pass/Fail/Gap] | [tool] | [summary] |

## Architecture Alignment
- Drift Score: [None / Low / Medium / High]
- ADR Compliance: [compliant / N violations / no ADRs]
- Key Findings: [list]

## Efficiency Findings
[Findings by severity with file:line evidence]

## Technical Debt Summary
| Metric | Value | Rating |
|--------|-------|--------|
| Cyclomatic complexity (max) | [n] | [OK/Warning/Critical] |
| Code duplication | [%] | [OK/Warning/Critical] |
| Test coverage (critical paths) | [%] | [OK/Warning/Critical] |
| TODO/FIXME density | [n per kLOC] | [OK/Warning/Critical] |

## Prioritized Recommendations
1. [highest-impact recommendation with file:line]
2. …
```

Append this machine-readable block at the end of every report:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 3
skill: quality-review
status: COMPLETE
risk_assessment: [High / Medium / Low]
quality_verdict: [Pass / Conditional / Fail]
drift_score: [None / Low / Medium / High]
finding_count:
  critical: [n]
  major: [n]
  minor: [n]
key_concerns: [top 3 findings by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

### Worked Quality Finding

**Finding QR-002: Architecture Drift — Service bypasses repository layer**

- **File:** `src/controllers/OrderController.ts:47`
- **Code:** `const orders = await db.query('SELECT * FROM orders WHERE user_id = ?', [userId]);`
- **Standard violated:** ADR-002 mandates all data access through the repository layer (`src/repositories/`). Direct database queries in controllers bypass the abstraction boundary.
- **Severity:** Major — creates coupling between controller and database schema, prevents repository-level caching or query optimization, and makes the data access pattern invisible to integration tests that mock the repository.
- **Recommendation:** Move the query to `OrderRepository.findByUserId(userId)` and call it from the controller. Verify no other controllers contain direct `db.query()` calls.

---

| Scenario | How to Handle |
|----------|---------------|
| No architecture docs (no ADRs, no C4 models) | Skip drift detection. Note the absence as a Major finding: architecture decisions are undocumented. Infer conventions from the code structure and report against those. |
| Greenfield project (no history, no metrics) | Baseline metrics cannot be computed. Focus on standards enforcement and initial architecture assessment. Flag any patterns that will create future debt. |
| Polyglot codebase (multiple languages) | Apply language-specific standards per file type. Note where cross-language boundaries create additional complexity. Prioritize the dominant language. |
| No automated tooling configured | Report as a Critical finding. Recommend the minimum viable automation stack for the detected language. Do not substitute manual analysis for tool output — state what tools *should* report rather than guessing. |
| Conflicting standards (team style vs language convention) | Prefer documented team standards when they exist and are enforced. If team standards conflict with language conventions without documented rationale, flag as a finding. |
| Code is generated or vendored | Skip quality review on generated/vendored code. State the exclusion explicitly. If generated code is modified, review only the modifications. |
| Massive codebase (>100k LOC) | Focus review scope on changed files and their immediate dependencies. Do not attempt full-codebase metrics without tooling. State scope limitations. |
| Monorepo with mixed standards across modules | Apply per-module standards based on each module's language and documented conventions. Do not merge metrics across modules with different quality baselines. Report each module separately. |
| Automated tools disagree with manual review findings | Trust the tool output for quantitative metrics (coverage, complexity, duplication). For architectural or semantic findings, document both the tool result and the manual assessment with evidence. Escalate ambiguous cases to the user rather than silently choosing one. |

---

## Additional Resources

### Reference Files

For detailed standards, architecture procedures, and metrics guidance, consult:

- **`references/standards-enforcement.md`** — Language-specific style guides and tool configurations for JavaScript/TypeScript, Python, C#/.NET, Rust, and Go, including the three-layer automation stack implementation details and Rust rewrite wave tooling comparisons
- **`references/architecture-review.md`** — C4 model evaluation procedures at all four levels, ADR format and lifecycle, architecture drift detection methodology with scoring, decision authority mapping, and common drift patterns (boundary violations, coupling creep, interface bypass)
- **`references/metrics-and-debt.md`** — DORA metrics definitions and the 7 archetypes, DX Core 4 Framework, AI Productivity Paradox analysis, IEEE 730-2026 SQA process integration, technical debt measurement, quality gate configuration, and code complexity metrics

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

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
