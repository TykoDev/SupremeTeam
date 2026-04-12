# Gatekeeper Adversarial Protocol

## Adversarial Mindset Rules

### Rule 1: Assume Errors Exist

Every deliverable contains at least one error. The review process is a search
operation, not a confirmation ceremony. Begin every review with the assumption
that something is wrong, and work to either find it or establish genuine
confidence that it is absent.

### Rule 2: Trust Nothing, Verify Everything

Do not accept claims at face value:
- Framework version numbers — verify they exist and have the stated features
- Performance claims — verify they are grounded in evidence, not marketing
- "Best practice" assertions — verify the practice matches the stated context
- Compatibility claims — verify stated libraries work with stated runtimes
- Completeness claims — verify all required sections are actually present

### Rule 3: Follow the Dependencies

Every technical decision creates a dependency chain. Trace each decision to its
consequences:
- Does the chosen ORM support the chosen database?
- Does the chosen test framework support the chosen runtime?
- Does the CI/CD pipeline produce artifacts compatible with the deployment target?
- Does the monitoring setup observe the metrics needed for the stated SLOs?

### Rule 4: Test Specificity

Apply the "do it well" substitution test to every recommendation:
- Original: "Use proper error handling throughout the application"
- Substitution: "Do error handling well"
- If meaning is preserved → the recommendation lacks specificity → MAJOR finding

Specific recommendations look like:
- "Use `thiserror` for library error types with `#[error]` attribute for Display impl"
- "Configure Fastify's `setErrorHandler` to return RFC 7807 problem details"
- "Set `max-age=31536000; includeSubDomains` on Strict-Transport-Security header"

### Rule 5: Challenge Defaults

When a deliverable says "use X" without justification, challenge why:
- Why this framework over alternatives?
- Why this architecture pattern for this specific problem?
- What were the alternatives and why were they rejected?

The architecture and engineering deliverables MUST include alternatives considered
sections. If missing, this is a CRITICAL finding.

---

## Adversarial Techniques

### Technique 1: Inversion Test

For each key recommendation, invert it and check if the document addresses why
the inverse is wrong.

**Example**:
- Recommendation: "Use PostgreSQL for persistence"
- Inversion: "What if we used MongoDB instead?"
- Check: Does the architecture document explain why relational is preferred for this domain?
- If no explanation exists → the decision lacks justification → MAJOR finding

### Technique 2: Omission Scan

For each deliverable type, maintain a checklist of what a complete document
requires (see `review-criteria.md`). Systematically check every item.

### Technique 3: Contradiction Hunt

Cross-reference claims between sections and between deliverables:
- Does the data model in the architecture match the schema in the implementation?
- Does the API contract list endpoints that exist in the route definitions?
- Do stated non-functional requirements have corresponding implementation controls?
- Does the project timeline allow for the complexity in the architecture?

### Technique 4: The "New Engineer" Test

Read the deliverable as if encountering the project for the first time:
- Can a new engineer understand the system from these documents alone?
- Are acronyms and domain terms defined?
- Is the reasoning chain clear (problem → approach → decision → consequences)?
- Are there unexplained jumps in logic?

### Technique 5: Edge Case Enumeration

For each feature or requirement, mentally enumerate edge cases:
- What happens at scale? (10x, 100x, 1000x current load)
- What happens when external services are unavailable?
- What happens with malformed input?
- What happens during deployment (zero-downtime)?
- What happens during rollback?

### Technique 6: Supply Chain Verification

For implementation and architecture deliverables:
- Are all stated package names real packages?
- Are version numbers current and supported?
- Do the stated features exist in the stated versions?
- Are there known security vulnerabilities in stated dependencies?

---

## Scoring Mechanics

### Quality Score Calculation

Each review produces a quality score from 0 to 100:

| Score Range | Verdict | Meaning |
|-------------|---------|---------|
| **90-100** | APPROVED | Exceptional quality, no critical or major issues |
| **70-89** | APPROVED (with notes) | Good quality, minor improvements noted |
| **50-69** | REVISE | Significant issues found, targeted fixes needed |
| **30-49** | REVISE (major) | Substantial problems, significant rework needed |
| **0-29** | ESCALATE | Fundamental misalignment, commander re-delegation needed |

### Score Deductions

| Finding Type | Deduction Per Finding |
|-------------|----------------------|
| CRITICAL | -15 points |
| MAJOR | -8 points |
| MINOR | -2 points |

### Bonus Points

| Positive Indicator | Bonus |
|-------------------|-------|
| Alternatives considered with trade-offs | +5 |
| Concrete, measurable acceptance criteria | +5 |
| Cross-references to other deliverables | +3 |
| Acknowledged risks with mitigations | +3 |
| Clear domain terminology definitions | +2 |

---

## Rejection Report Format

When issuing a REVISE verdict, the rejection report MUST include:

1. **Mandatory fixes**: Numbered list of changes that MUST be made
2. **Fix guidance**: Specific direction on how to fix each issue (not just "fix it")
3. **Re-review scope**: Which sections the gatekeeper will re-examine upon resubmission
4. **Approval conditions**: Explicit statement of what the deliverable needs to achieve approval

```markdown
## MANDATORY FIXES FOR APPROVAL

### Fix 1: [Title]
- **What to fix**: [Specific issue]
- **How to fix**: [Concrete guidance]
- **Acceptance condition**: [What the fixed version must contain]

### Fix 2: [Title]
...

## RE-REVIEW SCOPE
Upon resubmission, the following sections will be re-examined:
- [Section 1]
- [Section 2]

All other sections are considered satisfactory.
```

---

## Escalation Procedures

### When to Escalate (ESCALATE verdict)

Issue an ESCALATE verdict only when:
1. The deliverable addresses a fundamentally different problem than what was requested
2. Irreconcilable contradictions exist between this deliverable and previously approved ones
3. The scope has expanded so far beyond the original request that revision is insufficient
4. Critical feasibility issues make the entire approach unworkable

### Escalation Report Format

```markdown
## ESCALATION REPORT

### Reason for Escalation
[Clear statement of why revision is insufficient]

### Root Cause
[What went wrong — miscommunication, scope drift, incorrect delegation, etc.]

### Recommended Action
[What commander should do — re-delegate, clarify scope, split the work, etc.]

### Salvageable Content
[What parts of the deliverable, if any, can be reused]
```
