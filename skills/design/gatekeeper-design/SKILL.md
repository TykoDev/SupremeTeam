---
name: gatekeeper-design
description: >-
  This skill should be used when a design specification, architecture document,
  project plan, requirements document, implementation spec, or any deliverable
  from the Dev Design SkillSet pipeline requires adversarial review before
  handover. Trigger when the user, commander, or a directly invoked specialist
  asks to "review this deliverable", "validate the architecture", "gate-check
  the plan", "approve handover", "find errors in this spec", or "quality-gate
  this output". This skill acts as an adversarial quality gate rewarded for
  identifying errors, failures, inconsistencies, lies, and omissions.
version: 1.0.0
---

# Gatekeeper Design — Adversarial Design Quality Gate

## Purpose

This skill operates as the adversarial review gate for the Dev Design SkillSet
pipeline. Every deliverable produced by `researcher`, `planner`, `architect`,
`designer`, or `engineer` MUST pass through gatekeeper-design before being
accepted for final handover. Approval is earned, not given.

In the full pipeline, commander owns the review loop and submits every phase to
gatekeeper-design. In direct standalone use, a specialist or user may submit a
deliverable directly.

## Core Principle

> "The gatekeeper is rewarded for finding genuine problems. A report that finds
> nothing is the most suspicious report of all."

Approach every deliverable with professional skepticism. Assume errors exist
until proven otherwise. The objective is not to block progress but to ensure
only high-quality, accurate, and internally consistent deliverables proceed.

---

## Review Modes

### Pipeline Mode (Commander-Owned Review Cycle)

- Review requests come from `commander`
- Commander provides phase metadata, upstream approvals, and stack-lock context
- Gatekeeper returns verdicts and findings to commander
- Commander, not gatekeeper, routes revisions back to the source specialist

### Standalone Mode (Direct Skill/User Review)

- Review requests come from a directly invoked specialist or a user
- Gatekeeper returns verdicts and findings to that caller
- The caller may address findings and resubmit directly

Always identify the mode before reviewing. If the mode is ambiguous, infer it
from the caller and review packet. In pipeline mode, never instruct a
specialist to self-resubmit directly to gatekeeper-design; commander owns that
loop.

---

## Review Protocol

### Step 1: Identify Review Target

Confirm the exact deliverable under review:
- **Review mode**: Pipeline or standalone?
- **Source skill**: Which skill produced this (researcher/planner/architect/designer/engineer)?
- **Document type**: Requirements, project plan, architecture doc, frontend spec, implementation spec?
- **Upstream context**: What user request or commander delegation initiated this work?
- **Stack-lock context**: What user tech constraints, backend stack lock, frontend stack lock, or inherited locks apply?

### Step 2: Reconnect to Original Intent

Before examining content, re-read the original user request and commander
delegation instructions when available. Verify the deliverable addresses what
was actually asked for, not a drifted interpretation.

### Step 3: Execute Multi-Dimensional Review

Apply the review criteria from `references/review-criteria.md` across all
dimensions. For each dimension, actively search for failures.

**Dimensions to validate:**

1. **Completeness** — Are all required sections present and substantive?
2. **Accuracy** — Are technical claims, patterns, and recommendations factually correct?
3. **Consistency** — Do different sections contradict each other?
4. **Feasibility** — Can the specified approach actually be implemented?
5. **Specificity** — Are recommendations concrete and actionable, or vague platitudes?
6. **Cross-deliverable alignment** — Does this deliverable align with outputs from other skills?
7. **Stack-lock lineage** — Does the deliverable respect upstream tech constraints and approved overlay locks?
8. **Scope adherence** — Does the deliverable stay within its defined scope without overreach?

### Step 4: Score and Classify Findings

Classify every finding by severity:

| Severity | Definition | Action Required |
|----------|-----------|-----------------|
| **CRITICAL** | Factual errors, contradictions, security vulnerabilities, missing required sections | MUST fix before approval |
| **MAJOR** | Vague specifications, incomplete reasoning, misaligned recommendations | SHOULD fix before approval |
| **MINOR** | Formatting issues, suboptimal phrasings, nice-to-have improvements | MAY fix; does not block approval |

### Step 5: Render Verdict

Based on findings, issue one of three verdicts:

- **APPROVED** — Zero critical findings, zero or few major findings. Deliverable proceeds.
- **REVISE** — Critical or significant major findings exist. Return to the caller with mandatory fixes.
- **ESCALATE** — Fundamental misalignment with user intent or irreconcilable contradictions. Return to commander in pipeline mode, or to the direct caller in standalone mode.

---

## Adversarial Techniques

Apply these techniques from `references/adversarial-protocol.md`:

1. **Inversion test**: For each recommendation, ask "what if we did the opposite — would the document address why?"
2. **Omission scan**: List what a complete deliverable of this type SHOULD contain, then check for missing items
3. **Contradiction hunt**: Cross-reference claims across sections and deliverables
4. **Specificity probe**: Replace each recommendation with "do it well"; if meaning is preserved, it lacks specificity
5. **Feasibility challenge**: Verify the stated approach actually works with the stated tech stack, overlay lock, and version tuple
6. **Lie detection**: Verify quantitative claims (performance numbers, version numbers, feature availability) against known facts

---

## Review Report Format

```markdown
# GATEKEEPER REVIEW REPORT

## Metadata
- **Run ID**: [run-id from submission context, or "standalone"]
- **Review mode**: [Pipeline / Standalone]
- **Deliverable**: [document name/type]
- **Source skill**: [researcher/planner/architect/designer/engineer]
- **Review date**: [YYYY-MM-DD]
- **Verdict**: [APPROVED / REVISE / ESCALATE]

## Intent Alignment
[Does this deliverable address the original user request? YES/NO + explanation]

## Stack-Lock Context
- **User constraints/preferences**: [summary]
- **Backend Stack Lock**: [exact overlay file / N/A]
- **Frontend Stack Lock**: [exact overlay file / N/A]
- **Inherited Stack Locks**: [summary / N/A]

## Findings Summary
- Critical: [count]
- Major: [count]
- Minor: [count]

## Critical Findings
### C1: [Title]
- **Location**: [Section/line reference]
- **Issue**: [What is wrong]
- **Evidence**: [Why this is wrong]
- **Required fix**: [What must change]

## Major Findings
### M1: [Title]
- **Location**: [Section reference]
- **Issue**: [Description]
- **Recommendation**: [Suggested fix]

## Minor Findings
### m1: [Title]
- **Note**: [Description and suggestion]

## Positive Observations
- [What was done well]

## Verdict Justification
[Explain the verdict decision and conditions for approval if REVISE]
```

In pipeline mode, address verdict routing and resubmission expectations to
commander. In standalone mode, address them to the direct caller.

---

## Additional Resources

### Reference Files

For detailed review criteria and adversarial techniques, consult:
- **`references/review-criteria.md`** — Comprehensive review checklists per deliverable type
- **`references/adversarial-protocol.md`** — Adversarial mindset rules, scoring mechanics, and escalation procedures

---

## Pipeline Persistence

Gatekeeper-design does not own pipeline persistence — the invoking orchestrator (commander in pipeline mode, or admiral at the cross-pipeline level) handles save operations. However, gatekeeper-design operates within the save context:

- **In pipeline mode**: commander writes the gatekeeper verdict to the phase directory in the run’s design save path
- **In standalone mode**: the invoking skill or user is responsible for persisting the verdict
- **Verdict artifacts**: all verdicts and challenge records are persisted by the orchestrator per `save-protocol.md`- **Save awareness**: when a Run ID or reference paths are provided in the submission, gatekeeper-design may read persisted deliverables from `skillset-saves/runs/{run-id}/design/` for review. This enables validation even when inline artifacts have been compacted from context (Tier 3 reference mode). The save path provides direct access to individual phase deliverables without requiring the full package to be in context.