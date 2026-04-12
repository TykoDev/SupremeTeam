# Challenge Protocol — Complete Adversarial Rubric

This reference provides the detailed rubric for each of the 5 challenge categories, including definitions, trigger conditions, example challenges, expected response formats, and resolution criteria.

---

## Challenge Category 1: Existence

### Definition
Verify that the evidence cited in a finding actually exists in the codebase. A finding without verifiable evidence is an unsubstantiated claim.

### Trigger Conditions
- A finding references a file path and line number
- A finding describes a function, variable, or code pattern
- A finding claims a specific behavior ("this function returns X when Y")
- A finding references an API, endpoint, or configuration

### Challenge Rate
- **Critical/Major findings:** 100% verification
- **Minor findings:** Sample 30% of Minor findings

### Challenge Procedure
1. Read the file at the cited path and line number
2. Verify the described code exists at that location
3. If a behavior is claimed, trace the code path to confirm the described execution
4. If a function is referenced, confirm it exists with the described signature
5. If a data flow is described, verify the flow path through the code

### Example Challenges

**Challenge 1: File reference incorrect**
```
The finding BUG-003 references `cache/store.go:112`, but the file only has 98 lines.
Please verify the correct location of the concurrent map access issue.
```

**Challenge 2: Behavior claim unverified**
```
SEC-005 claims that `processInput()` allows SQL injection at line 67. However,
line 67 uses a parameterized query via `db.Query($1, input)`. Please provide
the specific code path where unsanitized input reaches a query.
```

**Challenge 3: Function does not exist**
```
BUG-007 references `validateToken()` in `auth/middleware.py`, but no such function
exists in that file. The token validation appears to be in `auth/jwt.py:validateJWT()`.
Please verify the finding location.
```

### Resolution Criteria
- **Resolved (corrected):** Skill provides corrected file path/line number with matching evidence
- **Resolved (defended):** Skill explains the discrepancy (e.g., file was refactored between review and challenge)
- **Resolved (withdrawn):** Skill acknowledges the evidence does not exist and removes the finding

---

## Challenge Category 2: Accuracy

### Definition
Verify that the classification, severity, and description of a finding are correct. A finding with wrong CWE mapping, inflated severity, or inaccurate description erodes trust.

### Trigger Conditions
- A CWE ID is assigned to a finding
- A CVSS score is assigned
- A severity level (Critical/Major/Minor) is assigned
- A defect category (concurrency, input validation, etc.) is assigned
- The description claims a specific vulnerability type

### Challenge Rate
- **Critical findings:** 100% verification
- **Major findings:** 50% sampling
- **Minor findings:** Only if the classification looks suspicious

### Challenge Procedure
1. Read the CWE description and verify the code matches the weakness pattern
2. For CVSS scores, verify each component (attack vector, complexity, impact) against the actual exploit scenario
3. Compare the severity assignment against the skill's own severity rubric
4. Verify that the described vulnerability type matches the actual code behavior
5. Check for classification inflation (cosmetic issue classified as security) or deflation (real vulnerability classified as minor)

### Example Challenges

**Challenge 1: CWE mapping incorrect**
```
SEC-002 maps to CWE-79 (XSS), but the code at `api/render.go:45` outputs data
in an API JSON response, not in an HTML context. JSON API responses are not
vulnerable to XSS in the traditional sense. Should this be CWE-200 (Information
Exposure) instead, or is there an HTML rendering path not shown in the finding?
```

**Challenge 2: Severity inflation**
```
BUG-004 is classified as Critical, but the null dereference occurs in the
admin-only debug logging path, which is disabled in production configuration.
This appears to be Minor severity. Please justify the Critical classification
or reclassify.
```

**Challenge 3: Vulnerability type mismatch**
```
SEC-008 describes a "race condition in authentication" but the code uses a
database transaction with row-level locking. The described scenario (concurrent
login attempts) would be serialized by the database lock. Please explain how
the race condition manifests despite the transaction isolation.
```

### Resolution Criteria
- **Resolved (corrected):** Skill updates the classification with correct CWE/severity/type
- **Resolved (defended):** Skill provides evidence that the original classification is correct (e.g., the HTML rendering path exists elsewhere)
- **Resolved (withdrawn):** Skill acknowledges the classification was wrong and removes or reclassifies

---

## Challenge Category 3: Completeness

### Definition
Verify that the skill applied its full checklist and did not skip categories without justification. An incomplete review creates false confidence.

### Trigger Conditions
- The report's "Checklist Coverage" section shows fewer categories than the skill's documented checklist
- A code change touches areas that should trigger specific checklist categories (e.g., auth code change but no authentication checks reported)
- The report lacks a "Checklist Coverage" section entirely

### Challenge Procedure
1. Compare the report's coverage against the skill's complete checklist (in its `references/` directory)
2. Identify categories that were skipped
3. For each skipped category, determine whether it is plausibly not applicable or potentially overlooked
4. Consider the nature of the code change: does it touch areas where the skipped category is critical?

### Example Challenges

**Challenge 1: Missing checklist categories**
```
The bug-review report addressed 5 of 8 checklist categories but did not cover
"Concurrency Hazards," "Resource Management," or "Boundary Conditions." The
code change modifies a shared cache accessed from request handlers (concurrent
by nature). Please apply the concurrency and resource management checklists
or explain why they are not applicable.
```

**Challenge 2: AI threats not assessed**
```
The security-review report did not assess AI-specific threats, but the code
change modifies the prompt template in `ai/completion.py`. The "AI-Specific
Security Threats" checklist should be applied. Please evaluate for prompt
injection, excessive agency, and PII leakage.
```

**Challenge 3: No coverage declaration**
```
The code-review report does not include a "Checklist Coverage" section
documenting which of the 8 dimensions were assessed. Please add coverage
declarations for each dimension, noting any that were not applicable and why.
```

### Resolution Criteria
- **Resolved (applied):** Skill applies the missing checklist categories and reports findings (or confirms no issues)
- **Resolved (justified):** Skill provides specific justification for why the category is not applicable
- **Unresolved:** Skill does not address the gap — mark for escalation

---

## Challenge Category 4: Proportionality

### Definition
Verify that severity assignments are proportional to actual impact. Both inflation (creating noise) and deflation (hiding risk) degrade review quality.

### Trigger Conditions
- A finding's severity seems disproportionate to its described impact
- Multiple findings have the same severity despite clearly different impact levels
- Severity assignments do not match the skill's own rubric examples

### Challenge Procedure
1. Read the finding description and evidence
2. Assess the real-world impact: Who is affected? How likely is the scenario? What is the blast radius?
3. Compare against the skill's severity rubric:
   - Critical: data corruption, crash, security breach, all users affected
   - Major: incorrect output under reachable conditions, significant degradation
   - Minor: cosmetic, edge case with negligible impact
4. Check for systematic bias (all findings at the same severity level suggests rubber-stamping)

### Example Challenges

**Challenge 1: Inflation**
```
BUG-012 classifies a missing log context field as Major. The missing field
(`request_id`) in the debug log at `utils/logger.py:23` affects log
searchability but does not impact functionality or users. This appears to
be Minor severity. Please justify the Major classification or reclassify.
```

**Challenge 2: Deflation**
```
SEC-003 classifies a missing authorization check on `DELETE /api/users/{id}`
as Medium. Any authenticated user can delete any other user's account via
direct API call. This is a Critical severity finding per the security-review
rubric (security breach, all users affected). Please reclassify.
```

**Challenge 3: Uniform severity**
```
The quality-review report has 8 findings, all classified as Major. This
uniform distribution is suspicious — it suggests the severity rubric was not
applied individually. Please re-evaluate each finding against the rubric.
```

### Resolution Criteria
- **Resolved (reclassified):** Skill adjusts the severity with justification
- **Resolved (defended):** Skill provides evidence that the original severity is correct
- **Unresolved:** Severity dispute after 2 rounds — mark as Disputed with both positions

---

## Challenge Category 5: Consistency

### Definition
Verify coherence across multiple skill reports examining the same code change. Contradictions, unreconciled overlaps, and coverage gaps indicate review quality issues.

### Trigger Conditions
- Multiple skills flagged the same code area with different conclusions
- One skill found issues in an area that another skill declared clean
- Two skills assigned different severities to overlapping findings
- A skill found nothing in an area where another skill found significant issues

### Challenge Procedure
1. Build the cross-validation matrix (see `references/cross-validation.md`)
2. Identify all overlaps, gaps, and contradictions
3. For each inconsistency, determine which skill is more likely correct based on domain expertise alignment
4. Issue challenges to the skill whose finding appears less credible

### Example Challenges

**Challenge 1: Contradiction**
```
code-review approved the design of `OrderProcessor` (Dimension: Design — "No issues"),
but quality-review flagged the same class for architecture drift (QR-DRIFT-001, Major:
"OrderProcessor directly accesses the payment database, violating the service layer
boundary defined in ADR-015"). These findings are contradictory. One of the reviews
missed the boundary violation.

code-review: Please re-evaluate the Design dimension for OrderProcessor against ADR-015.
```

**Challenge 2: Severity inconsistency**
```
bug-review found an input validation issue in `api/handler.py:34` (BUG-005, Major:
"boundary condition — negative quantity not validated"). security-review found the
same issue (SEC-007, Critical: "missing input validation enables negative-quantity
injection affecting billing"). The underlying finding is the same, but severities
differ. Please reconcile to a single severity.
```

**Challenge 3: Coverage gap**
```
The code change modifies `auth/middleware.py`, `auth/jwt.py`, and `auth/rbac.py`.
security-review flagged issues in middleware.py and jwt.py but did not mention
rbac.py. bug-review found no issues in any auth files. Given that rbac.py handles
role-based access control, this appears to be a coverage gap.

security-review: Please confirm rbac.py was reviewed and report findings or explicit
"no issues found" with justification.
```

### Resolution Criteria
- **Resolved (reconciled):** Both skills align on the finding and severity
- **Resolved (explained):** The apparent inconsistency is justified (different perspectives, both valid)
- **Unresolved:** Skills disagree after challenge — mark as Disputed

---

## Challenge Prioritization

Not all challenges are equally important. Prioritize based on the cost of being wrong:

| Priority | Scenario | Cost of Being Wrong |
|----------|----------|-------------------|
| **P0** | False negative on Critical security finding | Vulnerability in production |
| **P1** | False positive on Critical finding | Unnecessary emergency rework |
| **P2** | Severity mismatch (Major ↔ Critical) | Misallocated remediation priority |
| **P3** | Completeness gap on High-risk code | Unreviewed attack surface |
| **P4** | Proportionality on Major findings | Moderate priority mismatch |
| **P5** | Minor classification issues | Negligible impact |

Focus challenge effort on P0–P3. P4–P5 challenges should only be issued if the gatekeeper has capacity after higher-priority work.

---

## Anti-Patterns in Challenging

**Challenge-for-challenge's-sake:** Issuing challenges to demonstrate rigor rather than improve accuracy. Symptom: challenging findings that have clear, verifiable evidence.

**Severity inflation by gatekeeper:** Systematically arguing that findings should be more severe. The gatekeeper's job is to verify accuracy, not to impose its own severity preferences.

**Ignoring strong evidence:** When a skill provides specific, verifiable evidence defending a finding, accept it. Engage evidence on its merits, not on rhetorical grounds.

**Scope creep:** The gatekeeper validates reports — it does not perform original code review. If the gatekeeper spots an issue not in any report, it should note it as a cross-validation gap and delegate to the appropriate skill, not file a finding directly.
