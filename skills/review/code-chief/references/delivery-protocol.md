# Delivery Protocol

Use this template when `code-chief` assembles the final review package after
`gatekeeper-code` approval.

```markdown
# CODE REVIEW PACKAGE: [Project/PR Name]

## Executive Summary
[One paragraph summarizing overall code health, critical findings, and risk assessment]

## Package Contents
1. Bug Review Report (Phase 1) — [finding count by severity]
2. Code Review Assessment (Phase 2) — [merge recommendation]
3. Quality Review Report (Phase 3) — [quality score]
4. Security Review Report (Phase 4) — [risk tier + finding count]
5. Adversarial Analysis Report (Phase 5) — [exploit chain count + severity]
6. Frontend Audit Report (Phase 6) — [domain scores] / SKIPPED: [justification]
7. Gatekeeper-Code Validation Record (all approval/dispute records)

## Cross-Skill Risk Summary

| Risk Dimension | Status | Critical | High | Medium | Low |
|----------------|--------|----------|------|--------|-----|
| Correctness    | [tier] | [n]      | [n]  | [n]    | [n] |
| Merge-Ready    | [verdict] | — | — | — | — |
| Sustainability | [score] | [n]     | [n]  | [n]    | [n] |
| Security       | [tier] | [n]      | [n]  | [n]    | [n] |
| Adversarial    | [tier] | [n]      | [n]  | [n]    | [n] |
| Frontend       | [tier] | [n]      | [n]  | [n]    | [n] |

## Disputed Items
[Any findings where the gatekeeper and a skill could not agree — user decides]

## Recommended Actions
[Prioritized list of remediation steps, blocking items first]
```

## Delivery Checklist

Before returning the package:

1. Confirm every included specialist report is the gatekeeper-approved revision.
2. Mark skipped phases explicitly with justification rather than omitting them.
3. Ensure the risk summary does not contradict the underlying specialist reports.
4. Put blocking remediation items first in `Recommended Actions`.