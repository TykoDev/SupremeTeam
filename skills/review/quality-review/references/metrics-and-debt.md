# Quality Metrics and Technical Debt

This reference provides detailed metric definitions, framework descriptions, and technical debt measurement guidance for the quality review skill.

---

## DORA Metrics

The DevOps Research and Assessment (DORA) program defines software delivery performance metrics that predict organizational performance.

### The Four Key Metrics

**1. Deployment Frequency:** How often code is deployed to production.
- Elite: On-demand (multiple times per day)
- High: Between once per day and once per week
- Medium: Between once per week and once per month
- Low: Less than once per month

**2. Lead Time for Changes:** Time from code commit to production deployment.
- Elite: Less than one hour
- High: Between one day and one week
- Medium: Between one week and one month
- Low: More than one month

**3. Change Failure Rate:** Percentage of deployments causing a failure in production.
- Elite: 0–5%
- High: 5–10%
- Medium: 10–15%
- Low: More than 15%

**4. Mean Time to Recovery (MTTR):** Time to restore service after a production failure.
- Elite: Less than one hour
- High: Less than one day
- Medium: Between one day and one week
- Low: More than one week

### The 2025 DORA Report — Seven Archetypes

The 2025 DORA Report replaced the traditional low/medium/high/elite team categories with seven performance archetypes:

1. **Foundational Challenges** — Teams struggling with basic automation and delivery practices
2. **Emerging Practitioners** — Teams beginning to adopt CI/CD but with inconsistent execution
3. **Developing Capabilities** — Teams with solid foundations building advanced practices
4. **Balanced Performers** — Teams with consistent performance across all dimensions
5. **Efficiency Drivers** — Teams optimized for speed but potentially sacrificing quality
6. **Quality Focused** — Teams optimized for quality but potentially sacrificing speed
7. **Harmonious High-Achievers** — Teams excelling across all dimensions simultaneously

### The AI Productivity Paradox

The most striking finding from the 2025 DORA Report: AI tools boost individual output (21% more tasks, 98% more PRs merged per developer) while organizational delivery metrics remain flat.

**Key insight:** AI "magnifies the strengths of high-performing organizations and the dysfunctions of struggling ones." Organizations with strong engineering practices see AI accelerate their delivery. Organizations with weak practices see AI amplify their problems (more buggy code, more security vulnerabilities, faster accumulation of technical debt).

**Implication for quality review:** Measuring individual productivity (PRs merged, lines written) without measuring quality outcomes (change failure rate, defect escape rate) creates a misleading picture. Always pair productivity metrics with quality metrics.

---

## DX Core 4 Framework

The DX Core 4 Framework extends beyond DORA by combining four dimensions:

**1. Speed:** How fast can teams ship changes? (Aligns with DORA lead time and deploy frequency)

**2. Effectiveness:** Are teams productive? Measures include:
- Developer satisfaction and engagement
- Time spent on productive work vs overhead (meetings, context-switching, waiting)
- Self-reported ease of getting work done

**3. Quality:** Is the output reliable? Measures include:
- Change failure rate (DORA)
- Defect escape rate (bugs found in production)
- Technical debt trends
- Code quality gate pass rates

**4. Business Impact:** Are engineering outcomes driving business results? Measures include:
- Feature adoption rates
- Revenue impact of shipped features
- Customer satisfaction correlation with engineering changes

**Using DX Core 4 in quality review:** When assessing a code change's quality implications, consider all four dimensions. A change that ships fast (speed) but introduces debt (quality) and doesn't solve the user problem (business impact) is not a good change.

---

## IEEE 730-2026 — Software Quality Assurance Processes

Approved February 2026, IEEE 730-2026 provides the definitive international framework for Software Quality Assurance (SQA) processes. Harmonized with ISO/IEC/IEEE 12207:2017 (software lifecycle) and IEEE 2675-2021 (DevOps).

### Four Mandatory Phases

**1. Initiating:**
- Establish requirements, success criteria, and scope for SQA
- Define quality objectives for the project or sprint
- Identify applicable standards and compliance requirements

**2. Planning:**
- Detail automated strategies, testing methodologies, and quality gates
- Define which metrics will be tracked and what thresholds trigger action
- Plan review schedules and reviewer assignments

**3. Controlling:**
- Continuously monitor quality activities using real-time metrics
- Ensure engineering workflows align with defined architectural plans
- Trigger corrective actions when metrics fall below thresholds

**4. Executing:**
- Perform validation protocols, peer reviews, and automated testing
- Record quality findings and track remediation
- Generate quality reports and trend analyses

### Mapping IEEE 730-2026 to Code Review

| IEEE 730 Phase | Code Review Activity |
|----------------|---------------------|
| Initiating | Define review standards, checklist scope, reviewer qualifications |
| Planning | Configure CI quality gates, assign reviewers, set response SLAs |
| Controlling | Monitor review metrics (cycle time, defect yield, coverage), adjust process |
| Executing | Perform reviews, run automated checks, triage findings, apply fixes |

---

## Technical Debt Measurement

### Debt Indicators

Track these measurable signals to detect and quantify technical debt:

**Code Duplication (DRY Violations):**
- Metric: Percentage of duplicated code blocks across the codebase
- Tools: SonarQube (duplications metric), jscpd, CPD (PMD)
- Threshold: Flag when duplication exceeds 5% of total LOC
- Review check: Does the PR introduce new duplication that could be extracted?

**Cyclomatic Complexity:**
- Metric: Number of linearly independent paths through a function
- Tools: SonarQube, radon (Python), complexity-report (JS)
- Threshold: Flag functions with cyclomatic complexity > 10; require review for > 20
- Review check: Does the PR increase complexity of existing functions?

**Cognitive Complexity:**
- Metric: SonarQube's metric measuring how hard code is to understand (weighted by nesting, breaks in flow)
- More accurate than cyclomatic complexity for readability assessment
- Threshold: Flag functions with cognitive complexity > 15

**Dependency Staleness:**
- Metric: Age of dependencies relative to latest available versions
- Tools: npm outdated, pip-audit, Dependabot age reports
- Threshold: Flag dependencies more than 2 major versions behind
- Review check: Does the PR add new dependencies? Are they well-maintained?

**Test Coverage Gaps:**
- Metric: Line/branch coverage on changed files (not overall codebase)
- Tools: Istanbul/c8 (JS), coverage.py (Python), JaCoCo (Java), go test -cover
- Threshold: Changed files should maintain or improve coverage
- Review check: Does the PR reduce coverage on modified files?

**TODO/FIXME/HACK Density:**
- Metric: Count and age of TODO/FIXME/HACK comments
- Tools: grep/ripgrep with git blame for age, IDE task tracking
- Threshold: New TODOs require linked tracking issues
- Review check: Does the PR add TODOs without issue references?

### Debt Accumulation vs Reduction

For each quality review, assess whether the change increases or decreases technical debt:

**Debt Increased When:**
- New duplication introduced without extraction
- Complexity of existing functions increased without offsetting clarity improvements
- New dependencies added without justification
- Test coverage decreased on modified files
- New TODOs added without tracking issues
- Architecture drift score decreased

**Debt Reduced When:**
- Existing duplication extracted into shared utilities
- Complex functions broken into smaller, focused units
- Stale dependencies updated
- Test coverage improved on previously-uncovered code
- TODOs resolved and tracking issues closed
- Architecture drift corrected

**Debt Neutral When:**
- Change follows existing patterns without improving or degrading them
- New code meets quality standards but doesn't improve existing code
- Feature addition with appropriate tests and documentation

---

## Quality Gate Configuration

### SonarQube Quality Gates (Recommended Configuration)

Apply quality gates to **new code only** ("Clean as You Code" philosophy):

| Metric | Threshold | Blocking? |
|--------|-----------|-----------|
| New bugs | 0 | Yes |
| New vulnerabilities | 0 | Yes |
| New code smells (blocker/critical) | 0 | Yes |
| New code coverage | ≥ 80% | Yes |
| New duplicated lines | ≤ 3% | Yes |
| Reliability rating on new code | A | Yes |
| Security rating on new code | A | Yes |
| Maintainability rating on new code | A | No (warning) |

### Custom Quality Gate Checklist

For projects without SonarQube, enforce these manually during quality review:

- [ ] No new functions with cyclomatic complexity > 10
- [ ] No new code duplication (>10 lines identical)
- [ ] Test coverage on changed files ≥ existing coverage
- [ ] No new dependencies without documented justification
- [ ] No new TODOs without tracking issue references
- [ ] Architecture drift score maintained or improved
- [ ] Style guide compliance (linter passes)
- [ ] Type checking passes (if applicable)

---

## Review-Adjacent Metrics

### Flow/Throughput Metrics

Track these to ensure quality improvements don't destroy delivery performance:

**PR Cycle Time:** Time from PR open to merge. Target: under 24 hours for Medium risk, under 4 hours for first review response.

**Review Iteration Count:** Number of review cycles per PR. Target: ≤ 2 iterations for well-scoped PRs. High iteration counts indicate unclear requirements or insufficient self-review.

**PR Size Distribution:** Distribution of PR sizes across the team. Healthy: concentrated around 50–200 LOC. Unhealthy: bimodal (many tiny and many huge).

**Review Backlog Age:** How long PRs wait for their first review. Target: no PR waiting more than 1 business day.

### Outcome Metrics

**Defect Escape Rate:** Percentage of bugs found post-merge or post-release. Target: < 5% for Critical/Major.

**Change Failure Rate:** Percentage of deployments causing production issues. Target: < 5%.

**Time-to-Fix by Severity:** How quickly bugs are remediated after discovery. Critical: same day. Major: within sprint. Minor: within quarter.

**Rework Rate:** Percentage of PRs that require changes after initial approval. High rework rate may indicate insufficient first-pass review quality or unclear requirements.
