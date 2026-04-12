# Risk-Tiered PR Workflow

This reference describes the complete pull request lifecycle from pre-commit through post-merge, including risk tiering, Ship/Show/Ask classification, stacked PR strategies, and merge queue patterns.

---

## The Risk-Tiered PR Lifecycle

### Pre-Commit (Developer Local)

Before opening a PR, enforce baseline checks locally:
1. **Format and lint:** Run formatters (Prettier, Black, gofmt) and linters (ESLint, Ruff, clippy) — catches style issues before they enter the review queue
2. **Unit tests:** Run fast unit tests locally to catch obvious regressions
3. **Secret scan:** Run pre-commit secret detection (Gitleaks, git-secrets) to prevent credential leaks before push
4. **Self-review:** Read the diff as if reviewing someone else's code. Catch obvious issues before consuming reviewer time.

### PR Open

When opening the PR:
1. **PR template:** Use a standardized template capturing: what changed, why, testing performed, risks, dependencies, documentation updates
2. **Size check:** PR should be under 400 lines of code. If larger, consider splitting.
3. **Risk label:** Auto-label or manually assign Low/Medium/High risk tier
4. **Reviewer routing:** Auto-assign reviewers via CODEOWNERS. For High-risk areas, add domain specialist.

### CI Security and Quality Gates

Automated gates run on every PR:
1. **Build verification:** Code compiles/transpiles without errors
2. **Test execution:** Unit and integration tests pass
3. **SAST scan:** Static analysis (CodeQL, Semgrep) — no new critical findings
4. **SCA scan:** Dependency scanning — no new critical vulnerabilities in dependencies
5. **Secrets detection:** No secrets detected in the diff
6. **Type checking:** Type checker passes (mypy, Pyright, TypeScript strict)
7. **Coverage check:** Test coverage does not decrease on changed files

### Merge Gates

Requirements before merge:
- **Low risk:** 1 approval + all CI checks passing
- **Medium risk:** 1 approval + all CI checks + reviewer validates business logic
- **High risk:** 2 approvals (including domain expert) + all CI checks + security review sign-off + threat model validation (if applicable)

### Post-Merge

After merge:
1. **Monitoring:** Watch for regressions in error rates, latency, and user-reported issues
2. **SBOM generation:** Generate updated SBOM for the release artifact
3. **Defect triage SLAs:** Any escaped defects enter triage within defined SLAs
4. **Metrics feedback:** Update PR cycle time, review throughput, and defect escape rate metrics

---

## Risk Tier Definitions

### Low Risk
- Configuration file changes (non-security)
- Documentation updates
- Test-only changes (adding or modifying tests without changing production code)
- UI cosmetic changes (colors, spacing, text)
- Dependency version bumps (patch versions with no breaking changes)

### Medium Risk
- New features in existing modules
- Business logic modifications
- Database query changes
- API endpoint additions or modifications (non-auth)
- Internal tooling changes
- Dependency version bumps (minor or major versions)

### High Risk
- Authentication or authorization code
- Payment, billing, or financial logic
- Cryptographic operations or key management
- Deserialization of untrusted data
- CI/CD pipeline configuration changes
- Infrastructure as Code (Terraform, CloudFormation)
- New external dependencies (especially from unknown publishers)
- AI/ML model integration or prompt engineering
- Data migration scripts affecting production data
- Security middleware or firewall rules

---

## Ship/Show/Ask Model

Categorize changes by review need to optimize reviewer bandwidth. Published on MartinFowler.com, this model decouples code review from pull requests for mature teams.

### Ship (No Blocking Review)
Merge directly without waiting for review. Use for:
- Typo fixes in documentation or comments
- Auto-formatted code (formatter-only changes)
- Dependency lock file updates (automated by bots)
- Feature flag cleanup (removing dead code behind disabled flags)

**Prerequisite:** CI gates must pass. The developer has high confidence and the change is trivially reversible.

### Show (Non-Blocking Review)
Open a PR for visibility but merge without waiting for approval. Reviewers provide feedback asynchronously, and the author addresses comments in follow-up PRs. Use for:
- Minor refactors with comprehensive test coverage
- Non-critical bug fixes with clear regression tests
- Internal tooling improvements
- Test additions with no production code changes

**Prerequisite:** CI gates must pass. The change has good test coverage and low risk of user-facing impact.

### Ask (Blocking Review)
Standard PR workflow — requires approval before merge. Use for:
- New features affecting users
- Architecture changes
- Security-sensitive modifications
- Changes to shared libraries consumed by multiple services
- Performance-critical code changes
- Any High-risk tier change

---

## Stacked PRs

For large features, break the work into a stack of small, dependent PRs that can be reviewed independently.

**Benefits:**
- Each PR is small enough for thorough review (50–200 lines)
- Shopify reported 33% more PRs per developer using stacked PRs
- Asana reported saving 7 hours per developer per week
- Reviewers maintain focus and catch more issues

**Implementation:**
- Use tools like Graphite, ghstack, or git-town to manage PR dependencies
- Each PR in the stack should be independently correct (compiles, tests pass)
- Bottom of the stack merges first; higher PRs rebase automatically
- Review can happen in parallel across the stack

**Splitting strategies:**
- **By layer:** Database schema → repository layer → service layer → API handler → UI
- **By feature slice:** Core functionality → error handling → edge cases → documentation
- **By refactor-then-feature:** Refactoring PR → feature PR that builds on the refactoring

---

## Merge Queues

Merge queues automate rebasing, ordering, and conflict resolution at scale. Essential for repositories with high PR throughput.

### Graphite
Developer-focused merge queue that manages stacked PRs. Provides automatic rebasing, trunk-based development workflow, and review analytics.

### Aviator
Enterprise merge queue with priority ordering, batch merging, and automatic conflict resolution. Integrates with GitHub and GitLab.

### GitHub Native Merge Queue
Built-in GitHub feature. Creates temporary merge commits to test PRs against the latest base branch before actually merging. Prevents "merge skew" where CI passes on an outdated base.

**When to adopt merge queues:**
- Repository has >10 PRs merging per day
- Main branch breaks frequently due to merge conflicts
- CI time is long enough that PRs become stale during review
- Team uses trunk-based development with continuous deployment

---

## PR Size Guidelines

Research consistently shows that PR size is the single most impactful variable in code review effectiveness.

| PR Size (LOC) | Review Time | Defect Detection | Recommendation |
|---------------|-------------|------------------|----------------|
| 1–50 | Minutes | Highest | Ideal for critical code |
| 50–200 | 30–60 min | High | Sweet spot for most changes |
| 200–400 | 60–90 min | Moderate | Acceptable, but consider splitting |
| 400–1000 | Hours | Low | Should be split |
| 1000+ | Days | Very low | Must be split |

Teams with PRs averaging 50 lines ship 40% more code than teams exceeding 200 lines. The industry consensus target is 200–400 LOC per PR.

**Oversized PR protocol:**
1. If a PR exceeds 400 LOC, the reviewer should first assess whether it can be split
2. If splitting is feasible, request the author to split before reviewing
3. If splitting is infeasible (e.g., large-scale automated refactoring), review in focused sessions with breaks
4. Never review more than 400 LOC in a single sitting — effectiveness drops sharply

---

## Reviewer Assignment and Routing

### CODEOWNERS
Define code ownership at the directory or file level. Platform auto-requests reviews from owners when their code is modified. Ensures domain experts review domain-specific changes.

### Preventing Self-Approval
Configure branch protections to prevent authors from approving their own PRs. Required for compliance in regulated environments.

### Expertise Routing
For High-risk changes, route to specialists:
- Security-sensitive code → security champion or security team
- Database changes → DBA or database-experienced reviewer
- Infrastructure changes → platform/SRE team
- Performance-critical code → performance-experienced reviewer
- New external dependencies → supply chain security reviewer

### Review Load Balancing
Distribute review load evenly across the team. Monitor per-reviewer review counts to prevent burnout. Rotate "primary reviewer" responsibility weekly or per-sprint.
