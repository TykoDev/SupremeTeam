---
name: code-review
description: >-
  This skill should be used when the user asks to "review this code",
  "do a code review", "review this pull request", "check this PR",
  "evaluate code changes", "review for design and complexity",
  "assess code readiness for merge", "review this diff", "give
  feedback on this code", "look at my changes", "what would you
  comment on here?", "is this code okay?", or "is this ready to merge?". Performs
  comprehensive code review covering design,
  functionality, complexity, tests, naming, comments, style, and
  documentation using Google's 8-dimension framework with risk-tiered
  PR assessment (Low/Medium/High/Critical).
  DO NOT USE for bug hunting (use bug-review). DO NOT USE for
  security-specific review (use security-review). DO NOT USE for
  frontend visual audit (use design-qa or frontier).
version: 1.0.0
---

# Code Reviewing Specialist

## Purpose

This skill performs comprehensive, general-purpose code review across the broadest possible scope. It applies Google's 8-dimension framework — design, functionality, complexity, tests, naming, comments, style, and documentation — holistically to every code change. It is distinct from the specialized skills (bug-review targets correctness defects, security-review targets exploitability, quality-review targets long-term maintainability) because it evaluates all dimensions together and provides a unified merge recommendation.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

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
Use `references/pr-workflow.md` for the structural review flow and
`references/feedback-guide.md` for phrasing and severity conventions so the
review stays evidence-based and consistent from intake through final comments.

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

**Step 1: Validate Inputs.** Before reviewing, confirm the PR diff is complete and untruncated. If the diff is partial, file list is missing, or commit history is squashed beyond reconstruction, state the gap explicitly — do not review what you cannot see. Treat inputs per the trust levels in `../../references/evidence-standards.md` §Input Trust Boundaries.

**Step 2: Read the PR Description.** Understand the intent before reading code. Review the linked issue or requirement. Verify the PR description explains what changed and why.

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

**Focus Human Attention.** In practice, only a small share of review comments surface real defects when teams spend human time on style and formatting. Reserve human review comments for logic, security, architecture, and design. Automated tools should handle style, formatting, and known vulnerability patterns.

**Handling Disagreements.** If the author and reviewer disagree on a non-blocking issue, the author's judgment prevails. For blocking issues, escalate to a third reviewer or team lead rather than engaging in prolonged debate.

Consult `references/feedback-guide.md` for detailed examples, comment transformations (bad to good), and time-boxing guidance.

## The Improvement Principle

Google's guiding principle for code review: "A CL that improves the overall code health of the system should not be delayed for days because it isn't perfect." Balance thoroughness with velocity. Approve with minor nits rather than blocking on cosmetics. Provide the first review response within one business day to prevent systemic throughput collapse. Time-box individual review sessions to 60–90 minutes maximum — reviewer effectiveness degrades sharply after that point. This skill is language-agnostic and applies to any programming language, framework, or technology stack.

**Worked review finding:**

**Dimension:** Complexity (Dimension 3)
**Location:** `src/utils/permissions.ts:12-45`
**Finding:** Function `canAccess()` uses a 34-line nested if/else chain to check 6 permission levels. Cyclomatic complexity is 12.
**Why it matters:** Each new permission level requires modifying the chain, increasing regression risk. The nested structure makes it easy to miss a branch during future changes.
**Recommendation:** Replace with a strategy map:
```typescript
const permissionChecks: Record<Role, (resource: Resource) => boolean> = {
  admin: () => true,
  editor: (r) => r.ownerId === user.id || r.isPublic,
  viewer: (r) => r.isPublic || r.sharedWith.includes(user.id),
  // ...
};
return permissionChecks[user.role]?.(resource) ?? false;
```
**Severity:** Major (maintainability, not correctness — the current code works but resists change)

## Output Format

Structure the code review report as follows:

```

---

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

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No PR context (reviewing files directly) | Skip PR assessment protocol (size check, risk tier). Apply the 8-dimension review to the files as-is. Note the absence of PR context. |
| AI-generated code detected | Apply extra scrutiny to all 8 dimensions. AI code often passes superficial review but fails on edge cases, error handling, and security. Check for hallucinated APIs or impossible patterns. |
| Very large PR (>1000 lines) | Recommend splitting before reviewing. If splitting is not possible, focus on Design and Functionality first — these catch the highest-impact issues. Document what was not reviewed. |
| Review of generated/scaffolded code | Skip cosmetic dimensions (Style, Naming). Focus on Design and Functionality for the customized portions. |
| Reviewer lacks domain expertise | State the limitation. Focus on general code quality dimensions (Complexity, Tests, Style). Flag domain-specific logic for specialist review. |
| Conflicting feedback from multiple reviewers | Apply the hierarchy: Blocking > Nit > Optional. For conflicting blocking items, escalate to the code owner. |
| PR consists primarily of file deletions | Verify that no other code depends on the deleted files (imports, configuration references, test fixtures). Check for orphaned tests that tested the deleted code. Deletion PRs are high-risk for silent breakage because compilers may not catch all dynamic references. |
| Code contains obfuscated or intentionally obscured logic | Flag as a Blocking finding. Obfuscated code cannot be meaningfully reviewed for correctness or security. Require the author to explain the logic in comments or refactor to readable form before the review can proceed. |

---

## Additional Resources

### Reference Files

For detailed review guidance, PR workflows, and feedback conventions, consult:

- **`references/review-dimensions.md`** — Detailed guidance for each of Google's 8 review dimensions, with questions to ask, common mistakes, and example review comments per dimension
- **`references/pr-workflow.md`** — Complete risk-tiered PR lifecycle from pre-commit through post-merge, Ship/Show/Ask model with examples, stacked PR strategies, merge queues (Graphite, Aviator, GitHub native), and reviewer assignment patterns
- **`references/feedback-guide.md`** — Constructive feedback conventions with before/after examples, severity prefix usage, handling disagreements, sandwich method for juniors, and time-boxing guidance

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

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
