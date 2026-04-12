# Cross-Validation — Matrix, Gap Detection, and Contradiction Resolution

This reference provides the cross-skill validation methodology used by the gatekeeper to ensure consistency and completeness across all four review skill reports.

---

## Cross-Validation Matrix

### Purpose

The cross-validation matrix maps every changed file and function against findings from all four skills. It reveals overlaps (same issue found by multiple skills), gaps (code areas with no coverage), and contradictions (conflicting conclusions about the same code).

### Matrix Template

```
| File/Function          | bug-review       | code-review        | quality-review     | security-review    | Status          |
|------------------------|------------------|--------------------|--------------------|--------------------|-----------------|
| auth/middleware.py:34  | —                | CR-Func (Nit)      | —                  | SEC-001 (Critical) | Review overlap  |
| auth/middleware.py:67  | BUG-003 (Major)  | —                  | —                  | SEC-003 (Critical) | Check severity  |
| auth/jwt.py            | —                | CR-Design (Approve)| QR-Drift (Major)   | —                  | Contradiction?  |
| cache/store.go:87      | BUG-005 (Critical)| CR-Complex (Nit)  | QR-Perf (Major)    | —                  | Overlap OK      |
| api/handler.py         | —                | —                  | —                  | —                  | Gap!            |
| utils/parse.py:12-45   | BUG-008 (Minor)  | —                  | QR-Style (Minor)   | SEC-005 (Major)    | Check overlap   |
| config/settings.yml    | —                | CR-Doc (Nit)       | —                  | —                  | Expected        |
| tests/test_auth.py     | BUG-010 (Major)  | CR-Test (Blocking) | —                  | —                  | Overlap OK      |
```

### Building the Matrix

1. **List all changed files** from the code change (PR diff, commit, or file list)
2. **Extract findings** from each skill's report, mapping them to specific files and line ranges
3. **Fill the matrix** with finding IDs and severities
4. **Identify patterns** in each row:
   - **Empty row** = Potential gap (no skill found anything in a changed file)
   - **Multiple entries** = Potential overlap (check consistency)
   - **Conflicting entries** = Potential contradiction (investigate)
   - **Single entry** = Normal (one skill domain is most relevant)

---

## Overlap Detection

### Definition
An overlap occurs when two or more skills flag findings in the same code area. Overlaps are expected — the skills examine code from different perspectives — but the findings should be consistent.

### Types of Overlap

**Complementary Overlap (Healthy):**
- bug-review finds a boundary condition bug in input parsing
- security-review finds the same input parsing allows injection
- Both are valid findings from different perspectives. Severity may differ based on domain.
- **Action:** Verify severities are compatible. The security finding may warrant higher severity.

**Redundant Overlap (Waste):**
- bug-review and code-review both flag the same missing null check
- The findings are identical in substance
- **Action:** Deduplicate. Keep the finding under the most relevant skill. Note the overlap.

**Conflicting Overlap (Problem):**
- bug-review says the function handles errors correctly
- security-review says the function leaks error details to users
- The findings contradict each other
- **Action:** Challenge both skills. One of them is wrong, or they're examining different aspects.

### Overlap Resolution Protocol

For each overlap:
1. Determine whether it is complementary, redundant, or conflicting
2. For **complementary overlaps:** Adopt the higher severity if the perspectives justify it. Keep both findings if they recommend different fixes.
3. For **redundant overlaps:** Merge into a single finding under the primary skill. Credit both skills.
4. For **conflicting overlaps:** Issue consistency challenges to both skills (see Challenge Category 5 in `challenge-protocol.md`).

### Severity Reconciliation

When multiple skills find the same issue with different severities:

| Scenario | Resolution |
|----------|------------|
| bug-review: Major, security-review: Critical | Adopt Critical if the exploit scenario justifies it |
| code-review: Nit, quality-review: Major | Investigate — different perspectives may both be valid |
| bug-review: Major, code-review: Major | Consistent — no action needed |
| Any skill: differs by 2+ levels from another | Mandatory challenge — large discrepancy requires investigation |

---

## Gap Detection

### Definition
A gap occurs when a changed code area has no findings from any skill, OR when a skill that should have reviewed a specific area did not.

### Types of Gaps

**File-Level Gap:**
A changed file appears in no skill's findings. This may indicate:
- The file is genuinely clean (most common for config files, test fixtures)
- All skills overlooked it (concerning for logic-heavy files)
- The file was not in scope for any skill's checklist (may need scope clarification)

**Skill-Level Gap:**
A skill that should have reviewed specific code did not. For example:
- security-review did not examine auth-related changes
- bug-review did not examine complex algorithmic code
- quality-review did not assess architecture for a structural change

**Checklist-Level Gap:**
A skill reviewed the code but skipped relevant checklist categories. This is caught by the Completeness challenge (Category 3) during individual report validation.

### Gap Analysis Methodology

1. **List all changed files and their nature:**
   ```
   auth/middleware.py    — Authentication logic (security-critical)
   cache/store.go        — In-memory cache (concurrency-relevant)
   api/handler.py        — API endpoint (input validation, error handling)
   config/settings.yml   — Configuration (low risk)
   tests/test_auth.py    — Test code (test quality relevant)
   ```

2. **Map expected coverage per file:**
   ```
   auth/middleware.py    — Must be covered by: security-review, bug-review
   cache/store.go        — Must be covered by: bug-review (concurrency), quality-review (performance)
   api/handler.py        — Must be covered by: all four skills
   config/settings.yml   — Coverage by: code-review (documentation dimension)
   tests/test_auth.py    — Coverage by: bug-review (test quality), code-review (test dimension)
   ```

3. **Compare expected coverage against actual matrix entries**

4. **For each gap:** Issue a completeness challenge to the skill that should have covered the area

### Gap Classification

| Gap Type | Severity | Action |
|----------|----------|--------|
| Security-critical file uncovered by security-review | P0 | Immediate challenge — potential false negative |
| Logic-heavy file uncovered by bug-review | P1 | Challenge — potential missed defects |
| Structural change uncovered by quality-review | P2 | Challenge — potential missed drift |
| Config file uncovered by any skill | Low | Acceptable — unlikely to have findings |
| Test file uncovered by code-review | Low | Acceptable if bug-review covers test quality |

---

## Contradiction Resolution

### Definition
A contradiction occurs when two or more skills reach conflicting conclusions about the same code area. Contradictions are the most serious cross-validation finding because at least one skill is wrong.

### Common Contradiction Patterns

**Pattern 1: Design Approval vs Drift Detection**
- code-review: Design dimension — "No issues"
- quality-review: Architecture drift — "Module violates boundary defined in ADR-015"
- **Resolution path:** Challenge code-review to re-evaluate Design dimension against the specific ADR. If the ADR exists and the violation is real, code-review missed it.

**Pattern 2: Clean Security vs Functional Bug**
- security-review: "No input validation issues"
- bug-review: "Boundary condition bug — negative values not validated"
- **Resolution path:** The same missing validation is both a functional bug AND a security issue. Challenge security-review for the gap.

**Pattern 3: Test Approval vs Quality Concern**
- code-review: Tests dimension — "Tests are adequate"
- bug-review: Test quality — "Tests would not fail on regression"
- **Resolution path:** bug-review's test-driven review methodology is more rigorous than code-review's tests dimension check. Challenge code-review to re-evaluate with the test-driven review criteria.

**Pattern 4: Conflicting Severity on Same Issue**
- bug-review: "Null dereference — Major"
- security-review: "Null dereference in auth path — Critical"
- **Resolution path:** Not a true contradiction — the security context elevates the severity. Adopt Critical.

### Contradiction Resolution Process

1. **Identify the contradiction** in the cross-validation matrix
2. **Determine which skill has domain authority:** Security findings → security-review authority. Correctness findings → bug-review authority. Architecture findings → quality-review authority. Holistic assessment → code-review authority.
3. **Issue consistency challenges** to both skills with the contradiction clearly stated
4. **Evaluate responses:** The skill with stronger evidence prevails
5. **If unresolved:** Mark as Disputed with both positions documented

---

## Coverage Scoring

### Formula

```
Coverage Score = (Files with ≥1 applicable skill finding) / (Total changed files requiring review) × 100%
```

**Exclude from denominator:**
- Auto-generated files (lock files, compiled assets)
- Trivially changed files (whitespace, formatting-only)
- Files with no logic (empty config templates)

### Scoring Guide

| Score | Assessment | Action |
|-------|-----------|--------|
| 95-100% | Excellent coverage | Proceed to finalization |
| 85-94% | Good coverage | Verify gaps are genuinely clean code |
| 70-84% | Moderate coverage | Challenge skills for uncovered areas |
| Below 70% | Insufficient coverage | Report Not-Ready — significant review gaps |

---

## Final Report Assembly

After all delegations are resolved and cross-validation is complete, assemble the final unified report.

### Assembly Steps

1. **Merge findings:** Combine all validated/amended findings from the four skills into a single list
2. **Deduplicate:** Remove redundant overlaps, keeping the most comprehensive version
3. **Order by severity:** Critical → Major → Minor
4. **Append cross-validation results:** Overlaps resolved, gaps investigated, contradictions reconciled or disputed
5. **Add gatekeeper metadata:** Challenge statistics, delegation outcomes, coverage score

### Unified Finding Format

```
#### [UNIFIED-001] [Original ID] [Category] — [Title]
- **Source Skill:** [bug-review | code-review | quality-review | security-review]
- **Severity:** [Critical | Major | Minor]
- **Location:** file:line
- **Description:** [from the validated/amended finding]
- **Evidence:** [verified evidence]
- **Remediation:** [recommended fix]
- **Validation Status:** [Validated | Validated-with-amendments | Disputed]
- **Cross-Validation:** [any related findings from other skills]
```

### Final Verdict Criteria

**Ready:**
- Coverage score ≥ 85%
- No unresolved Critical/Major findings without evidence
- No unresolved contradictions on Critical items
- All skills applied their checklists (or justified omissions)

**Not-Ready:**
- Coverage score < 70%
- Any Critical finding with unresolved existence or accuracy challenge
- Unresolved contradiction involving Critical severity items
- Skill refused to respond to delegation requests

**Ready-with-Disputes:**
- Meets "Ready" criteria except for disputed findings
- Disputed items are documented with both positions
- User must resolve disputes before acting on the report
