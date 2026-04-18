---
name: devex-review
description: >-
  This skill should be used when the user asks to "test the developer
  experience", "DX audit", "try the onboarding", "test the getting
  started flow", "review the docs", "run devex-review", "developer
  experience test", "check the SDK ergonomics", "review error
  messages", "test the CLI", "how easy is this to use?", "audit
  the onboarding", "walk the first-run experience", "is this developer-friendly?", or wants a
  live, evidence-based audit of the
  developer experience across 8 dimensions (getting started,
  API/CLI/SDK, error messages, docs, upgrade path, dev environment,
  community, DX measurement). Measures TTHW (Time To Hello World)
  and scores each dimension 0-10 with cited evidence.
  DO NOT USE for code quality review (use code-review or
  quality-review). DO NOT USE for fixing code issues (use
  bob-the-builder). DO NOT USE for security testing (use
  security-review).
version: 1.0.0
---

# DevEx-Review — Developer Experience Auditor

## Purpose

This skill performs a live, evidence-based audit of the developer experience by testing the actual product — navigating documentation, running CLI commands, evaluating error messages, and measuring time-to-hello-world. Every score is backed by evidence (screenshots, command output, file references). Guesses are not evidence.

Where code-review and quality-review evaluate code internals, devex-review evaluates the experience from the developer's perspective: can a new developer get started quickly, find what they need, understand errors, and integrate effectively?

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.
Before auditing, confirm the project includes a README, setup instructions, and
a runnable entrypoint. If any are missing, flag them as findings rather than
attempting to infer the developer experience from incomplete artifacts.

---

## DX Audit Workflow

### Step 1: Target Discovery

1. Read project documentation for URLs, CLI commands, and getting started instructions
2. Identify the product surfaces to test:
   - Documentation site (if web-accessible)
   - CLI tool (if available)
   - API endpoints (if documented)
   - SDK packages (if applicable)
3. If insufficient information exists, ask the user for the documentation URL or primary developer surface

### Step 2: Getting Started Audit

Test the onboarding flow step by step. For each step, record:

Start the TTHW timer at the first documented prerequisite the developer must
act on, not at the first successful command. Hidden prerequisites are part of
the onboarding experience and must count against the score.

| Step | Action | Estimated Time | Friction | Evidence |
|------|--------|---------------|----------|----------|
| 1 | {what the developer does} | {time} | {Low/Med/High} | {screenshot/output} |
| 2 | {next action} | {time} | {Low/Med/High} | {screenshot/output} |

**Score 0-10.** Calibration anchors:
- 10: Hello world in <2 minutes, single command, no prerequisites
- 7: Hello world in <5 minutes, clear instructions, minor friction
- 4: Hello world in <15 minutes, multiple unclear steps
- 0: Cannot complete hello world without external help

**TTHW (Time To Hello World):** Record the total measured time.
If TTHW cannot be measured live, mark it `INFERRED`, explain why, and cap the
Getting Started score at 6/10 until a live run confirms a higher score.

### Step 3: API/CLI/SDK Ergonomics Audit

Test what is accessible:

**CLI (if available):**
- Run `--help` and evaluate output quality
- Check flag naming consistency and discoverability
- Test common workflows for friction

**API (if documented):**
- Navigate API reference or playground
- Evaluate endpoint naming consistency
- Check request/response examples for completeness

**SDK (if applicable):**
- Evaluate type definitions and autocomplete quality
- Check method naming consistency
- Evaluate initialization flow

**Score 0-10.** Calibration anchors:
- 10: Stripe-quality API — consistent naming, discoverable, self-documenting
- 7: Good naming, minor inconsistencies, usable without docs
- 4: Inconsistent naming, requires frequent doc lookups
- 0: Undiscoverable, inconsistent, undocumented

### Step 4: Error Message Audit

Trigger common error scenarios and evaluate the messages:

- Run with missing arguments, invalid flags, bad input
- Navigate to 404 pages, submit invalid forms
- Try unauthenticated access to protected resources

**Score against the three-tier model:**

| Tier | Quality | Example |
|------|---------|---------|
| Excellent | Says what went wrong, why, and how to fix | "File 'config.yaml' not found. Create one with `app init` or specify a path with --config." |
| Adequate | Says what went wrong | "File not found: config.yaml" |
| Poor | Generic or unhelpful | "Error: ENOENT" or "Something went wrong" |

**Score 0-10.** Calibration anchors:
- 10: All errors are Tier 1 (Elm/Rust quality)
- 7: Most errors are Tier 1-2, no Tier 3
- 4: Mix of tiers, some errors are unhelpful
- 0: Mostly Tier 3, stack traces exposed to users

### Step 5: Documentation Audit

Evaluate the documentation structure and quality:

- **Search:** Test 3 common queries — can you find what you need?
- **Code examples:** Are they copy-paste-complete? Do they run?
- **Information architecture:** Can you find what you need in <2 minutes?
- **Freshness:** Do docs match the current API/CLI version?

**Score 0-10.** Calibration anchors:
- 10: Stripe/Twilio quality — searchable, complete examples, versioned
- 7: Good docs, mostly complete, minor gaps
- 4: Docs exist but are incomplete or outdated
- 0: No docs or docs are misleading

### Step 6: Upgrade Path Audit

Evaluate via file inspection:

- CHANGELOG quality (clear, user-facing, migration notes?)
- Migration guides (exist? step-by-step? automated?)
- Deprecation warnings in code (grep for deprecated/obsolete)
- Semantic versioning adherence

**Score 0-10.** Evidence: INFERRED from files.

### Step 7: Developer Environment Audit

Evaluate via file inspection:

- README setup instructions (steps, prerequisites, platform coverage)
- CI/CD configuration (exists, documented)
- Type definitions (TypeScript, Python type hints)
- Test utilities and fixtures
- Development scripts (dev server, build, test, lint)

**Score 0-10.** Evidence: INFERRED from files.

### Step 8: Community & Ecosystem Audit

Evaluate community touchpoints:

- GitHub issues (templates, response time, labels)
- Contributing guide (exists, clear, actionable)
- Community channels (Discord, Discussions, Stack Overflow)
- Changelog/release notes accessibility

**Score 0-10.** Evidence: TESTED where web-accessible, INFERRED otherwise.

---

## DX Scorecard

Present the composite scorecard with evidence sources:

```
DX AUDIT SCORECARD
═══════════════════
Project:  {project name}
Date:     {today}
Auditor:  devex-review

Dimension            Score   Evidence         Method
──────────────────   ─────   ──────────────   ────────
Getting Started      __/10   [screenshots]    TESTED
API/CLI/SDK          __/10   [output refs]    TESTED
Error Messages       __/10   [screenshots]    TESTED
Documentation        __/10   [screenshots]    TESTED
Upgrade Path         __/10   [file refs]      INFERRED
Dev Environment      __/10   [file refs]      INFERRED
Community            __/10   [links]          PARTIAL
DX Measurement       __/10   [file refs]      INFERRED

TTHW (measured):     __ minutes
Overall DX Score:    __/10

Evidence Method Legend:
  TESTED   = Directly tested via tools, screenshots captured
  PARTIAL  = Some aspects tested, some inferred
  INFERRED = Evaluated from file inspection, not live testing
```

**Worked DX audit — React SaaS starter kit:**

| TTHW Step | Time | Friction | Score |
|-----------|------|----------|-------|
| Clone repo | 0:00–0:15 | None — `git clone` works | 10/10 |
| Install deps | 0:15–1:30 | `npm install` warns about 3 deprecated packages, no errors | 8/10 |
| Start dev server | 1:30–2:00 | `npm run dev` starts on first try, hot reload works | 10/10 |
| Find first file to edit | 2:00–4:00 | README says "see docs/" but docs/ has 12 files with no index. Developer reads 3 files before finding the right one | 5/10 |
| Make first change | 4:00–5:30 | Edit a component, see it reflect in the browser | 9/10 |
| Run tests | 5:30–8:00 | `npm test` fails: missing env variable `DATABASE_URL`. README doesn't mention test env setup. Developer spends 2.5 min finding `.env.example` | 3/10 |
| **Total TTHW** | **8:00** | **Overall: 6/10** | Blocked by missing test env docs |

**Top recommendation:** Add a "Quick Start" section to README with exact commands including test environment setup. Target TTHW under 5 minutes.

---

## Severity Model

| Severity | Criteria | Examples |
|----------|---------|---------| 
| **Critical** | Blocks developer adoption entirely | Cannot complete getting started, no docs, cryptic errors with no guidance |
| **Major** | Significant friction in core workflows | TTHW >15 minutes, inconsistent API naming, misleading docs |
| **Minor** | Polish items, nice-to-haves | Missing search in docs, generic error in edge case, incomplete CHANGELOG |

---

## Output Format

```markdown
# DEVELOPER EXPERIENCE AUDIT REPORT

## Executive Summary
- Overall DX Score: [n/10]
- TTHW: [n minutes]
- Top 3 Issues: [list]

## Scorecard
[Full scorecard table above]

## Findings by Dimension
[Structured findings with evidence and recommendations]

## Recommendations (prioritized)
1. [Highest impact improvement]
2. [Second highest]
3. [Third highest]
```

Append the structured pipeline summary:

```
---
## Pipeline Summary (Machine-Readable)

phase_id: 8
skill: devex-review
status: COMPLETE
risk_assessment: [High / Medium / Low]
overall_dx_score: [n/10]
tthw_minutes: [n]
dimensions_tested: [n]
dimensions_inferred: [n]
finding_count:
  critical: [n]
  major: [n]
  minor: [n]
verdict: [Pass / Conditional / Fail]
---
```

---

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Execute the full 8-dimension audit
- Submit completed report to code-chief
- Include the structured pipeline summary block

**When invoked standalone:**
- Execute the full audit independently
- Present the report and recommendations directly to the user

---

## Proactive Triggers

Suggest devex-review after shipping a developer-facing feature, API, CLI tool,
or SDK, or when onboarding friction is suspected.

---

## Important Rules

1. **Evidence or nothing.** Every score must cite its evidence source. No guesswork.
2. **TESTED > INFERRED.** Prefer live testing over file inspection whenever possible.
3. **Measure, do not estimate.** TTHW is measured by walking through the steps, not guessed.
4. **Developer perspective.** Evaluate as a new developer encountering this for the first time.
5. **Actionable recommendations.** Every finding must include a specific, implementable fix.
6. **Read-only.** Audit and report. Do not modify code unless explicitly asked to fix issues.
7. **Tool requirements are explicit.** If a dimension requires tool access that is unavailable (e.g., documentation URL not provided, CLI not installed, API playground offline), state the limitation, mark the dimension as `BLOCKED`, and score it as INFERRED from available file evidence. A BLOCKED dimension is never scored as 0 — it is scored from file evidence with a penalty noted.
8. **TTHW environment conditions.** TTHW measurement assumes a clean development environment with standard tooling (Node.js, Python, etc.) pre-installed. Record any additional prerequisites required (Docker, specific SDK versions, database servers). If prerequisites are unclear, that is itself a Getting Started finding.
9. **Sensitive data in error testing.** When triggering error scenarios (Step 4), avoid submitting real credentials, PII, or injection payloads that could cause damage. Use obviously fake test data (e.g., `test@example.com`, `invalid-key-12345`). If error messages expose sensitive data (stack traces with connection strings, internal paths), classify as a security-relevant finding.

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| No documentation exists | Score "Documentation" as 0/10 with evidence: "No documentation found." This is a Critical finding. Proceed with other dimensions normally — absence of docs is itself a finding, not a blocker. |
| Internal-only tool (not web-accessible) | Skip web-based testing. Evaluate from file inspection: README, code comments, error messages in source. Mark evidence method as INFERRED for web-dependent dimensions. |
| No CLI or API (library-only package) | Skip CLI/API ergonomics. Evaluate SDK: type definitions, README examples, test fixtures as usage examples. Redistribute scoring weight to applicable dimensions. |
| Product is pre-release / alpha | Note the maturity stage. Evaluate against the expected standard for that stage (e.g., getting started flow matters; changelog history does not). Adjust findings severity downward for polish items but not for core onboarding friction. |
| Non-English documentation | Evaluate structure and completeness regardless of language. Note the language. If you cannot read the language, mark as INFERRED and state the limitation. |
| Multiple entry points (CLI + SDK + API) | Audit each surface separately. Present per-surface scores in the scorecard. Use the lowest score as the headline to avoid masking weak surfaces. |
| Test infrastructure not available | State that TTHW could not be measured live. Estimate from documented steps, mark as INFERRED, and cap the Getting Started dimension at 6/10 pending live confirmation because inferred measurements are systematically less reliable than live observations. |
| Project uses auto-generated docs only (no hand-written guides) | Evaluate the generated docs against the same criteria. Auto-generated API references satisfy reference completeness but rarely satisfy onboarding, tutorials, or conceptual explanations. Score accordingly and recommend supplemental guides for gaps. |

---

## Additional Resources

### Reference Files

- **`references/dx-scorecard.md`** — Calibration anchors for each dimension, evidence collection methods, scoring examples, and comparative DX benchmarks used to keep scores consistent across audits
- **`references/error-message-guide.md`** — Error-message audit criteria, severity model, and remediation patterns for developer-facing failures so message-quality findings are concrete rather than taste-based

---

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*

---

## Persistent Save Protocol

When `### Save Context` is present in the delegation with `Persistence active: yes`:

1. After producing the audit report, write it to the designated save path as `deliverable_devex-review-report.md` using the standard frontmatter envelope:
   ```yaml
   ---
   type: deliverable
   pipeline: review
   phase: 8
   skill: devex-review
   name: Developer Experience Audit Report
   version: 1
   status: draft
   created: {ISO 8601 timestamp}
   ---
   ```
   Followed by the full report content verbatim.

2. If `### Save Context` is absent or `Persistence active: no`, skip all save operations.

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

See `save-protocol.md` (project root) for complete format specifications.
