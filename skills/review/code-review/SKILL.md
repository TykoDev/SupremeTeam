---
name: code-review
description: >-
  This skill should be used when the user asks to "review this code",
  "do a code review", "review this pull request", "check this PR",
  "evaluate code changes", "review for design and complexity",
  "assess code readiness for merge", "review this diff", or
  "give feedback on this code". It performs comprehensive code review
  covering design, functionality, complexity, tests, naming, comments,
  style, and documentation using Google's 8-dimension framework with
  risk-tiered PR assessment.
version: 1.0.0
---

# Code Reviewing Specialist

## Purpose

This skill performs comprehensive, general-purpose code review across the broadest possible scope. It applies Google's 8-dimension framework — design, functionality, complexity, tests, naming, comments, style, and documentation — holistically to every code change. It is distinct from the specialized skills (bug-review targets correctness defects, security-review targets exploitability, quality-review targets long-term maintainability) because it evaluates all dimensions together and provides a unified merge recommendation.

## The 8 Review Dimensions

Evaluate every code change against these eight dimensions, adapted from Google's publicly shared engineering practices.

**Design.** Assess whether the change belongs in this location within the codebase. Evaluate the overall approach: is the architecture sound? Are the right abstractions used? Does the change respect separation of concerns and existing module boundaries? Design is the highest-impact dimension — a wrong design decision affects everything downstream.

**Functionality.** Verify that the code does what the developer intended for all inputs, not just the happy path. Consider edge cases the author may not have anticipated: empty collections, null inputs, concurrent access, network failures, malformed data. Think about how end users will actually interact with the change.

**Complexity.** Determine whether the code can be understood quickly by future readers. "Too complex" means a reader cannot grasp the logic in a single pass. Flag over-engineering (premature abstractions, unnecessary generics, speculative configurability), clever tricks that sacrifice readability, and functions doing too many things.

**Tests.** Evaluate test design, not just test existence. Tests must be correct (testing the right behavior), well-designed (clear arrange/act/assert structure), meaningful (assertions that validate actual behavior and would fail on regression), and appropriately scoped (unit vs integration vs end-to-end). Tests do not test themselves — examine whether they actually exercise the changed code paths.

**Naming.** Verify that names are clear, descriptive, and consistent with the project's conventions. Name length should be proportional to scope: short names for tight scopes, descriptive names for broader scopes. Avoid abbreviations that require domain knowledge to decode. Functions should use verb-noun patterns; variables should use noun patterns.

**Comments.** Assess whether comments explain "why" rather than "what." Good comments capture intent, constraints, trade-offs, and non-obvious decisions. Bad comments restate the code, become stale quickly, or apologize for complexity instead of simplifying it. Flag TODOs without tracking information.

**Style.** Defer to the project's style guide as the absolute authority on style questions. Do not debate personal preferences during review — if the style guide permits it, accept it. If the project lacks a formal style guide, apply the dominant convention already established in the codebase. Style disagreements are the least productive use of reviewer time.

**Documentation.** Check whether READMEs, API docs, inline documentation, changelog entries, and migration guides are updated to reflect the change. If the change alters public APIs or user-facing behavior, documentation updates are mandatory, not optional.

Consult `references/review-dimensions.md` for detailed guidance, common mistakes, and example review comments for each dimension.

## PR Assessment Protocol

Before beginning line-by-line review, assess the PR at the structural level.

**Size Check.** Target 200–400 lines of code per PR. PRs under 100 lines review fastest and most thoroughly. PRs exceeding 400 lines should trigger a size warning. PRs exceeding 1,000 lines MUST be split — recommend logical splitting strategies (by layer, by feature, by refactor-then-feature). Teams with PRs averaging 50 lines ship 40% more code than teams exceeding 200 lines. For large features, recommend stacked PRs. Record the size classification in the report (Small <100, Medium 100-400, Large 400-1000, Oversized >1000).

**Risk Tier Assignment.** Classify the change as Low, Medium, or High risk:
- **Low:** Configuration changes, documentation, cosmetic fixes, test-only changes
- **Medium:** Business logic modifications, new features in existing modules, dependency updates
- **High:** Authentication/authorization changes, payment/financial logic, cryptographic operations, CI/CD pipeline modifications, infrastructure changes, new external dependencies

**Ship/Show/Ask Classification.** Determine the review need:
- **Ship** — Trivial changes (typo fixes, formatting) that can merge without review
- **Show** — Changes that benefit from awareness but should not block on review feedback
- **Ask** — Complex changes requiring blocking review and explicit approval

**Reviewer Routing.** Determine whether the change touches CODEOWNERS-protected areas requiring specialized sign-off. For High-risk changes, require an additional reviewer with domain expertise (security specialist for auth code, database expert for schema changes).

Consult `references/pr-workflow.md` for the complete risk-tiered PR lifecycle, merge queue strategies, and stacked PR patterns.

## Review Execution Workflow

Follow these steps in order for each code review.

**Step 1: Read the PR Description.** Understand the intent before reading code. Review the linked issue or requirement. Verify the PR description explains what changed and why.

**Step 2: AI-Generated Code Detection.** Assess whether the code appears to be AI-generated. Indicators include: uniform variable naming patterns, overly verbose comments restating the code, missing edge case handling, generic error messages, and suspiciously complete but shallow implementations. If AI generation is suspected, apply heightened scrutiny to: edge case handling, error path completeness, business logic correctness, and whether the code truly fits the project's patterns rather than being generic boilerplate. Document AI-generation suspicion in the report.

**Step 3: Assess Design at the Architectural Level.** Start with the highest-impact dimension. Evaluate whether the approach is fundamentally sound before examining implementation details. If the design is wrong, file-level feedback is wasted effort.

**Step 4: Walk Through the Code File by File.** Read the diff systematically. For large PRs, start with the files most central to the change (usually identified in the PR description), then move to supporting files.

**Step 5: Apply the 8 Dimensions Checklist.** For each significant code section, evaluate against all 8 dimensions. Record findings as they arise — do not rely on memory for a second pass.

**Step 6: Check CI Gate Results.** Review lint, test, SAST, and SCA results from the CI pipeline. Do not duplicate work that automation has already performed. If CI gates passed, focus human attention on design, logic, and architecture — not formatting.

**Step 7: Formulate Feedback.** Organize findings by severity and dimension. Apply the feedback conventions described below.

## Feedback Conventions

Effective review feedback is constructive, prioritized, and actionable.

**Framing.** Use "we" instead of "you" to frame suggestions collaboratively. "We might want to handle the null case here" is more constructive than "You forgot to handle null." For new developers, apply the sandwich method: suggestion between two genuine compliments.

**Severity Prefixes.** Mark each comment with its blocking level:
- **Blocking:** Must be addressed before merge. Use sparingly — only for correctness, security, or design issues.
- **Nit:** Non-blocking polish suggestion. The author may address or ignore without discussion.
- **Optional:** Improvement that the author should consider but is explicitly not required.
- **Question:** Seeking understanding, not requesting a change. Indicates the reviewer needs clarification.

**Focus Human Attention.** Research shows only ~15% of code review comments address real defects — the bulk target style and formatting issues that automated linters should handle. Reserve human review comments for logic, security, architecture, and design. Automated tools should handle style, formatting, and known vulnerability patterns.

**Handling Disagreements.** If the author and reviewer disagree on a non-blocking issue, the author's judgment prevails. For blocking issues, escalate to a third reviewer or team lead rather than engaging in prolonged debate.

Consult `references/feedback-guide.md` for detailed examples, comment transformations (bad to good), and time-boxing guidance.

## The Improvement Principle

Google's guiding principle for code review: "A CL that improves the overall code health of the system should not be delayed for days because it isn't perfect." Balance thoroughness with velocity. Approve with minor nits rather than blocking on cosmetics. Provide the first review response within one business day to prevent systemic throughput collapse. Time-box individual review sessions to 60–90 minutes maximum — reviewer effectiveness degrades sharply after that point. This skill is language-agnostic and applies to any programming language, framework, or technology stack.

## Output Format

Structure the code review report as follows:

```
## Code Review Report
### Summary
- **Verdict:** Approve | Approve with Nits | Request Changes
- **Risk Tier:** Low | Medium | High
- **PR Size:** [LOC changed] across [file count] files
- **Blocking Items:** [count]
- **Non-Blocking Items:** [count]

### Findings by Dimension
#### Design
- [findings or "No issues identified"]
#### Functionality
- [findings]
#### Complexity
- [findings]
#### Tests
- [findings]
#### Naming
- [findings]
#### Comments
- [findings]
#### Style
- [findings]
#### Documentation
- [findings]

### Verdict Rationale
[Brief explanation of the overall assessment and any conditions for approval]
```

Append the following structured summary block at the end of every report for
pipeline consumption:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 2
skill: code-review
status: COMPLETE
risk_assessment: [High / Medium / Low]
finding_count:
  blocking: [n]
  nit: [n]
  optional: [n]
  question: [n]
checklist_coverage: [8/8 dimensions assessed]
verdict: [Approve / Approve with Nits / Request Changes]
key_concerns: [top 3 blocking items, one line each]
cross_references: [file:line pairs flagged for cross-skill attention]
---
```


## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive delegation with review target scope, Phase 1 context, and technology stack
- Execute the full 8-dimension review workflow
- Submit the completed report to code-chief (not directly to gatekeeper-code)
- Include the structured pipeline summary block at the end of the report
- Code-chief owns the gatekeeper-code validation cycle in pipeline mode

**When invoked standalone:**
- Execute the full 8-dimension review workflow independently
- Submit the completed report to `gatekeeper-code` for adversarial validation
- If no `gatekeeper-code` skill is available, self-validate by confirming each of the 8 dimensions was assessed and the risk tier assignment is justified by the actual change scope

In both modes, the gatekeeper-code will challenge whether all dimensions were thoroughly assessed, whether the risk tier matches the actual change scope, and whether blocking items were correctly identified or missed.

## Additional Resources

### Reference Files

For detailed review guidance, PR workflows, and feedback conventions, consult:

- **`references/review-dimensions.md`** — Detailed guidance for each of Google's 8 review dimensions, with questions to ask, common mistakes, and example review comments per dimension
- **`references/pr-workflow.md`** — Complete risk-tiered PR lifecycle from pre-commit through post-merge, Ship/Show/Ask model with examples, stacked PR strategies, merge queues (Graphite, Aviator, GitHub native), and reviewer assignment patterns
- **`references/feedback-guide.md`** — Constructive feedback conventions with before/after examples, severity prefix usage, handling disagreements, sandwich method for juniors, and time-boxing guidance

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the review report, write it to the designated save path as `deliverable_{report-name}.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 2
   skill: code-review
   name: Code Review Assessment
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations — the skill operates identically to its pre-persistence behavior

See `save-protocol.md` (project root) for complete format specifications.
