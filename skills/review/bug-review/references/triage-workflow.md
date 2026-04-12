# Bug Triage and Remediation Workflow

This reference provides the detailed process for classifying, triaging, and remediating bugs found during review. It aligns with IEEE 1044 for defect classification and IBM ODC for process feedback extraction.

---

## Triage Process

### Single Intake Queue

Establish a single intake queue for all CI and review findings, tagged by source. This prevents findings from falling through cracks between tools and reviewers.

**Source tags:**
- `review-comment` — Human reviewer finding during code review
- `sast` — Static analysis tool finding (SonarQube, Infer, CodeQL, Semgrep)
- `fuzzing` — Fuzzer crash or timeout (libFuzzer, OSS-Fuzz, ClusterFuzzLite)
- `sanitizer` — Runtime sanitizer detection (ASan, MSan, UBSan, TSan)
- `mutation` — Surviving mutant indicating test gap (PIT, Stryker, mutmut)
- `production` — Bug reported from production monitoring

### Triage Steps

1. **Assign owner:** Route to the developer most familiar with the affected code area. For shared code, route to the team lead.

2. **Reproduce:** Require a minimal reproduction artifact before classification:
   - For review findings: specific code path and input conditions that trigger the bug
   - For fuzzer crashes: minimized crash input file
   - For sanitizer findings: full sanitizer stack trace with source locations
   - For production bugs: deterministic reproduction steps or log evidence
   - If a finding cannot be reproduced, classify as "Unconfirmed" and schedule investigation

3. **Classify:** Apply IEEE 1044 classification (see below) and assign severity using the project's severity rubric.

4. **Prioritize:** Order the triage queue by severity, then by blast radius (how many users/systems affected), then by fix complexity (quick fixes first to reduce queue size).

---

## Defect Classification Standards

### IEEE 1044 Classification

IEEE 1044 provides a uniform approach to classifying software anomalies across lifecycle stages. It supports causal analysis and process improvement by categorizing defects along standardized dimensions.

**Classification dimensions:**
- **Phase found:** Requirements, design, code, test, deployment, production
- **Phase introduced:** Requirements, design, code, integration, deployment
- **Type:** Logic, computation, data handling, interface, timing, documentation
- **Severity:** Blocking, critical, major, minor, trivial, enhancement
- **Priority:** Immediate, high, normal, low, deferred

**Using IEEE 1044 for process improvement:**
- Track which phases introduce the most defects → invest in upstream prevention
- Track which types recur → create automated checks or lint rules
- Track severity distribution trends → measure whether quality is improving over time

### IBM Orthogonal Defect Classification (ODC)

ODC extracts process feedback signatures from defect data. It classifies defects with semantic information that enables in-process feedback rather than post-mortem analysis.

**"Opener" attributes (set when defect is filed):**
- **Activity:** Code inspection, function test, system test, field
- **Trigger:** What caused the defect to surface (coverage, sequence, interaction, workload, stress, recovery, exception, startup)
- **Impact:** Installability, integrity/security, performance, reliability, usability, capability, documentation, maintenance

**"Closer" attributes (set when defect is fixed):**
- **Target:** Design, code, build/package, information (docs), configuration
- **Defect type:** Assignment (value), checking (validation), algorithm, function, interface, timing/serialization
- **Age:** New (introduced in current cycle), base (pre-existing), rewrite (reintroduced)
- **Source:** Internal (own code), third-party (library), environment

**Using ODC for feedback loops:**
- High ratio of "assignment" defects → developers may need training on initialization and value handling
- High ratio of "checking" defects → insufficient input validation patterns; create shared validation utilities
- High ratio of "interface" defects → API contracts may be poorly defined; invest in contract testing
- High ratio of "timing" defects → concurrency model may need architectural review

---

## Severity Rubric

### General Defect Severity

| Severity | Definition | Response Time | Examples |
|----------|-----------|---------------|----------|
| **Critical** | System crash, data corruption, data loss, security breach. Affects all users or critical business functions. No workaround. | Fix immediately. Block merge. | Null deref in main request path; database write with wrong column; infinite loop on valid input |
| **Major** | Incorrect output under reachable conditions. Significant feature degradation. Workaround exists but is unacceptable for production. | Fix before merge. | Off-by-one excluding last page of results; resource leak under moderate load; race condition in cache |
| **Minor** | Cosmetic defect, edge case with negligible user impact, code quality issue. Workaround is trivial or impact is minimal. | Fix at author's discretion. | Dead code path; redundant null check; log message with wrong level; minor test improvement |

### Security-Adjacent Bug Severity (CVSS v4.0 Cross-Reference)

For bugs that have security implications (e.g., null dereference in authentication path, integer overflow in access control calculation), cross-reference with CVSS v4.0 scoring:

- **Attack Vector (AV):** Network (most severe), Adjacent, Local, Physical
- **Attack Complexity (AC):** Low (most severe), High
- **Privileges Required (PR):** None (most severe), Low, High
- **User Interaction (UI):** None (most severe), Required
- **Impact (CIA):** Confidentiality, Integrity, Availability — each rated None/Low/High

A security-adjacent bug with AV:Network/AC:Low/PR:None should be treated as Critical regardless of the general severity rubric.

---

## Remediation Workflow

### Fix-in-Small-PR Protocol

1. **Create a focused fix PR** containing only the bug fix and its regression test. Do not bundle unrelated changes.

2. **Write the regression test first (TDD):**
   - Write a test that reproduces the bug (the test must fail against the current code)
   - Verify the test fails
   - Apply the fix
   - Verify the test passes
   - This proves the fix addresses the actual bug and prevents regression

3. **Reviewer validates test-before-fix:**
   - During review, the reviewer confirms that the test would fail before the fix (either by inspection or by checking the test against the pre-fix code)
   - This is the "test-driven review" principle applied to remediation

4. **Submit for standard code review** with the bug ID referenced in the PR description.

### Post-Fix Classification

After the fix is merged, record defect classification attributes for process improvement:

1. **Record ODC attributes:**
   - Defect type (assignment, checking, algorithm, interface, timing)
   - Age (new, base, rewrite)
   - Source (internal, third-party, environment)
   - Trigger (what caused the bug to surface)

2. **Feed recurring patterns into prevention:**
   - If the same defect type recurs 3+ times, create a lint rule or Semgrep pattern to catch it automatically
   - If a defect cluster appears in a specific module, consider architectural review of that module
   - If a defect type correlates with a specific coding pattern, add it to the team's review checklist
   - If tests consistently miss a certain bug class, add property-based tests or fuzzing for that area

3. **Update the defect checklist:**
   - Add new patterns discovered during triage to the team's checklist
   - Remove patterns that automated tools now reliably catch
   - Review the checklist quarterly for relevance

---

## Metrics

Track these metrics to measure defect detection and remediation effectiveness:

### Defect Density
Number of defects per thousand lines of code (KLOC). Track by severity level and by module. Declining density over time indicates improving code quality.

### Escape Rate
Percentage of defects found in production vs found during review/testing. A high escape rate indicates gaps in the review and testing process. Target: less than 5% escape rate for Critical/Major defects.

### Time-to-Fix by Severity
Measure elapsed time from defect report to fix merge, segmented by severity:
- Critical: target same-day fix
- Major: target within 1 sprint
- Minor: target within 2 sprints or as capacity allows

### Review Defect Yield
Number of defects found per review hour. Track to calibrate review effort — if yield drops significantly, reviewers may need checklist updates or training.

### Defect Source Distribution
Percentage of defects found by each detection method (human review, SAST, fuzzing, sanitizer, production monitoring). If one source dominates, investigate why others are missing those defect classes.

---

## Integration with DORA Metrics

Defect metrics should be tracked alongside DORA delivery metrics to ensure quality improvements do not destroy delivery performance:

- **Deploy frequency** should not decrease as defect prevention improves
- **Lead time for changes** may temporarily increase as quality gates are added, but should stabilize
- **Change failure rate** should decrease as defect prevention improves
- **Mean time to recovery** should decrease as remediation workflows mature

The goal is to shift the quality curve left (find bugs earlier) without shifting the delivery curve right (deploy later). The 2025 DORA Report's AI Productivity Paradox confirms this balance matters: AI tools boost individual output but organizational delivery metrics remain flat without proper quality infrastructure.
