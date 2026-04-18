# Review Suite Checklist Reference

This file defines the canonical completeness matrix for `gatekeeper-code`.
Use it during the Completeness Challenge to verify that each submitted report
covered the expected domains for the skills that were actually invoked.

## Suite-Level Requirements

Every consolidated package submitted by `code-chief` must include:

- a review execution manifest listing invoked skills
- explicit skip records for every skill omitted from the review suite
- the review target scope and risk tier
- enough evidence to trace each finding back to the code or rendered surface

If any of these are missing, `gatekeeper-code` should return `REVISE` before
scoring completeness.

## Per-Skill Coverage Expectations

| Skill | Minimum expected coverage |
|------|----------------------------|
| `bug-review` | All 8 defect categories: input validation, error handling, concurrency, resource management, boundary conditions, null/optional handling, logging/observability correctness, and test meaningfulness |
| `code-review` | All 8 code-review dimensions plus merge recommendation and PR risk framing |
| `quality-review` | Standards enforcement, maintainability, architecture drift, efficiency, and technical-debt assessment |
| `security-review` | NIST SSDF / OWASP / CWE mapping, threat-model reasoning, dependency and supply-chain review when relevant, and severity calibration |
| `mr-robot` | Exploit-chain thinking, adversarial attack paths, abuse scenarios, and supply-chain attack simulation when the dependency surface changed |
| `frontier` | Performance, accessibility, frontend security, component architecture, and UI/UX quality |
| `design-qa` | Visual hierarchy, typography, spacing, color, interactive states, responsive quality, and AI-slop detection |
| `devex-review` | Getting started, API/CLI/SDK ergonomics, error messages, documentation, upgrade path, dev environment, community, and DX measurement |

## Decision Rules

- If an invoked skill omits one of its mandatory domains without justification, raise a Completeness Challenge.
- If a report marks a domain `N/A`, require the report to explain why that domain did not apply to the target.
- If an optional skill was not invoked, the execution manifest must say why it was out of scope.
- If a report is intentionally partial because the review was narrowly scoped, the package must state that limitation and map it back to the original user request.

## Optional-Phase Guidance

`frontier` and `design-qa` are expected only when a user-facing frontend,
rendered UI, or styling surface is in scope. `devex-review` is expected only
when onboarding docs, CLI commands, SDKs, API docs, or similar
developer-facing surfaces are in scope.

Absence of an optional skill is acceptable only when the execution manifest
documents the skip reason clearly.