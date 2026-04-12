# Handoff Templates — Code-Chief Delegations

> **Placeholder notation**: Square-bracket tokens in this file are template
> placeholders to be replaced during delegation construction. The authoritative
> persisted-path format in `save-protocol.md` uses brace variables such as
> `{run-id}`.

## Phase Delegation Templates

### Phase 1: bug-review Delegation

```markdown
## CODE-CHIEF DELEGATION: Phase 1 — Correctness Defects

### Review Target
[Scope description: full codebase, PR #N, module X, files Y]

### Technology Stack
[Detected languages, frameworks, runtimes, build tools]

### Risk Tier
[Low / Standard / High — with justification]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/phase-1_bug-review/
- **Persistence active**: [yes/no]

### Instruction
Execute the bug-review skill workflow. Apply the full 8-category defect
checklist against the review target. Produce a structured report with:
- Findings classified by severity (Critical / Major / Minor)
- Evidence for each finding (file path, line number, reproducible conditions)
- 8-category checklist coverage percentage
- Overall risk assessment (High / Medium / Low)
- Structured summary block for pipeline consumption

Submit the completed report to code-chief for pipeline continuation.
You are operating in pipeline mode — do NOT submit directly to gatekeeper-code.
```

---

### Phase 2: code-review Delegation

```markdown
## CODE-CHIEF DELEGATION: Phase 2 — Merge-Readiness Assessment

### Review Target
[Scope description]

### Phase 1 Context
[Summary of bug-review findings: severity counts, key issues, risk assessment]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/phase-2_code-review/
- **Persistence active**: [yes/no]

### Instruction
Execute the code-review skill workflow. Evaluate the review target across all
8 dimensions (Design, Functionality, Complexity, Tests, Naming, Comments,
Style, Documentation). Produce a structured report with:
- Score per dimension
- PR assessment (size check, risk tier, Ship/Show/Ask classification)
- Merge recommendation (Approve / Approve with Nits / Request Changes)
- Feedback items with severity prefixes (Blocking / Nit / Optional / Question)
- Structured summary block for pipeline consumption

Submit the completed report to code-chief for pipeline continuation.
You are operating in pipeline mode — do NOT submit directly to gatekeeper-code.
```

---

### Phase 3: quality-review Delegation

```markdown
## CODE-CHIEF DELEGATION: Phase 3 — Maintainability & Standards

### Review Target
[Scope description]

### Phase 1–2 Context
[Summary of bug-review and code-review findings]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/phase-3_quality-review/
- **Persistence active**: [yes/no]

### Instruction
Execute the quality-review skill workflow. Produce a structured report with:
- Standards enforcement assessment (3-layer stack: baseline hygiene, semantic analysis, AI-assisted review)
- Architecture drift detection (C4 boundary violations, coupling creep)
- Efficiency assessment (algorithmic complexity, resource utilization, database queries)
- Technical debt measurement (duplication, complexity, dependency staleness, TODO density)
- Quality score (Pass / Conditional / Fail)
- Structured summary block for pipeline consumption

Submit the completed report to code-chief for pipeline continuation.
You are operating in pipeline mode — do NOT submit directly to gatekeeper-code.
```

---

### Phase 4: security-review Delegation

```markdown
## CODE-CHIEF DELEGATION: Phase 4 — Security Analysis

### Review Target
[Scope description]

### Phase 1–3 Context
[Summary of prior phase findings, especially any correctness defects affecting
security-relevant code paths]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/phase-4_security-review/
- **Persistence active**: [yes/no]

### Instruction
Execute the security-review skill workflow. Produce a structured report with:
- Findings mapped to NIST SSDF, OWASP ASVS/Top 10, CWE Top 25
- Risk tier assessment per finding
- Threat model updates (new data flows, trust boundary changes, auth modifications)
- Supply chain assessment (dependency vulnerabilities, SBOM gaps, SCA results)
- STRIDE classification for identified threats
- Structured summary block for pipeline consumption

Submit the completed report to code-chief for pipeline continuation.
You are operating in pipeline mode — do NOT submit directly to gatekeeper-code.
```

---

### Phase 5: mr-robot Delegation

```markdown
## CODE-CHIEF DELEGATION: Phase 5 — Adversarial Penetration Testing

### Review Target
[Scope description]

### Phase 4 Security Context
[Security-review findings — critical input for targeted exploitation]

### Risk Tier
[Standard / High — Low-risk targets use simplified reconnaissance only]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/phase-5_mr-robot/
- **Persistence active**: [yes/no]

### Instruction
Execute the mr-robot skill workflow. Using the security-review findings as
input, perform offensive analysis to validate whether identified (and
unidentified) vulnerabilities are exploitable. Produce a structured report with:
- Attack surface map (entry points, trust boundaries, data flows)
- Exploit chain constructions with preconditions and impact analysis
- Supply chain attack surface assessment
- API abuse scenarios (if applicable)
- CVSS 4.0-scored findings with proof-of-concept descriptions
- Structured summary block for pipeline consumption

Submit the completed report to code-chief for pipeline continuation.
You are operating in pipeline mode — do NOT submit directly to gatekeeper-code.
```

---

### Phase 6: frontier Delegation

```markdown
## CODE-CHIEF DELEGATION: Phase 6 — Frontend Analytics & UI/UX Audit

### Review Target
[Frontend components and files only]

### Frontend Framework
[Detected: React / Vue / Angular / Svelte / vanilla JS / other]

### Phase 1–5 Context
[Summary of prior findings relevant to frontend code]

### Save Context
- **Run ID**: [run-id]
- **Save path**: skillset-saves/runs/[run-id]/review/phase-6_frontier/
- **Persistence active**: [yes/no]

### Instruction
Execute the frontier skill workflow. Produce a structured report with:
- Performance audit (Core Web Vitals: LCP, INP, CLS against thresholds)
- Accessibility audit (WCAG 2.2 Level AA compliance)
- Frontend security audit (CSP, Trusted Types, XSS prevention, SRI)
- Component architecture assessment (design quality, state management, error boundaries)
- UI/UX quality review (responsive design, interaction patterns, loading/error/empty states)
- Structured summary block for pipeline consumption

Submit the completed report to code-chief for pipeline continuation.
You are operating in pipeline mode — do NOT submit directly to gatekeeper-code.
```

---

## Gatekeeper Submission Template

```markdown
## CODE-CHIEF → GATEKEEPER-CODE: Consolidated Review Package

### Review Target
[Full scope description]

### Pipeline Execution Summary
| Phase | Skill | Status | Duration | Finding Count (C/H/M/L) |
|-------|-------|--------|----------|-------------------------|
| 1 | bug-review | COMPLETE | — | [n/n/n/n] |
| 2 | code-review | COMPLETE | — | [verdict] |
| 3 | quality-review | COMPLETE | — | [score] |
| 4 | security-review | COMPLETE | — | [n/n/n/n] |
| 5 | mr-robot | COMPLETE | — | [n/n/n/n] |
| 6 | frontier | COMPLETE / SKIPPED | — | [n/n/n/n] / [reason] |

### Phase Skip Records
[Any phase skip justifications]

### Phase Reports
[Full report from each phase, in order]

### Cross-Reference Flags
[Files or functions with findings from multiple phases — priority for
consistency challenge]

### Instruction
Execute the gatekeeper-code adversarial validation protocol against this
consolidated review package. Apply all 5 challenge types. Build the
cross-validation matrix across all submitted skill reports. Route delegation
requests back through code-chief.
```

---

## Structured Summary Block

Every specialist skill report must end with this machine-readable block for
code-chief pipeline consumption:

```markdown
---
## Pipeline Summary (Machine-Readable)

phase_id: [1-6]
skill: [skill-name]
status: COMPLETE
risk_assessment: [High / Medium / Low]
finding_count:
  critical: [n]
  high: [n] / major: [n]
  medium: [n] / minor: [n]
  low: [n]
checklist_coverage: [percentage]
verdict: [skill-specific verdict]
key_concerns: [top 3 findings by severity, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```

---

## Final Delivery Template

```markdown
# CODE REVIEW PACKAGE: [Project/PR Name]

## Executive Summary
[One paragraph: overall health, critical findings, risk level, recommendation]

## Package Contents
1. Bug Review Report (Phase 1) — [C/H/M/L counts]
2. Code Review Assessment (Phase 2) — [merge verdict]
3. Quality Review Report (Phase 3) — [quality score]
4. Security Review Report (Phase 4) — [risk tier + counts]
5. Adversarial Analysis Report (Phase 5) — [exploit chains + counts]
6. Frontend Audit Report (Phase 6) — [domain scores] / SKIPPED: [reason]
7. Gatekeeper-Code Validation Record

## Cross-Skill Risk Summary

| Risk Dimension | Status | Critical | High | Medium | Low |
|----------------|--------|----------|------|--------|-----|
| Correctness (bug-review) | [tier] | [n] | [n] | [n] | [n] |
| Merge-Ready (code-review) | [verdict] | — | — | — | — |
| Sustainability (quality-review) | [score] | [n] | [n] | [n] | [n] |
| Security (security-review) | [tier] | [n] | [n] | [n] | [n] |
| Adversarial (mr-robot) | [tier] | [n] | [n] | [n] | [n] |
| Frontend (frontier) | [tier] | [n] | [n] | [n] | [n] |

## Disputed Items
[Findings where gatekeeper-code and a specialist could not agree — user decides]

## Recommended Actions
[Prioritized remediation list: blocking items first, then high, medium, low]

## Phase Reports
[Individual reports from each phase, in order]

## Gatekeeper Validation Record
[Challenge log, delegation requests, resolutions]

## Pipeline Metadata
- Phases executed: [list]
- Phases skipped: [list with justifications]
- Revision cycles: [count]
- Total findings: [count by severity across all phases]
```
