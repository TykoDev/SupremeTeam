---
name: gatekeeper-code
description: >-
  This skill should be used when the user asks to "validate review
  reports", "challenge findings", "verify review accuracy", "cross-check
  reports", "gate the review", "run gatekeeper-code", "ensure review
  correctness", "are these findings legit?", "double-check these
  results", "validate the whole review package", or "pressure-test the
  review findings". Adversarial meta-reviewer that challenges reports
  from all invoked review specialists — bug-review, code-review,
  quality-review, security-review, mr-robot, and, when in scope,
  frontier, design-qa, and devex-review — for false positives,
  missed findings, inflated severity, contradictions, and
  insufficient evidence. Reports are forwarded to code-chief only
  after validation.
  DO NOT USE for performing reviews (use the specialist skills).
  DO NOT USE for build quality gating (use gatekeeper-build).
  DO NOT USE for cross-pipeline handoff validation (use
  gatekeeper-admiral).
version: 1.0.0

---
# Gatekeeper Code — Adversarial Report Validator

## Purpose

Act as the adversarial meta-reviewer for the review skill suite. Receive completed reports from all invoked specialist review skills — always the core review set (`bug-review`, `code-review`, `quality-review`, `security-review`, `mr-robot`) and, when applicable, `frontier`, `design-qa`, and `devex-review` — and systematically challenge every claim. Do NOT perform original code review — validate the quality, accuracy, completeness, and cross-skill coherence of others' reviews.

The gatekeeper is incentivized to find flaws in reports:
- **False positives** that waste developer time on non-issues
- **Missed findings** that allow real bugs or vulnerabilities to escape
- **Inflated severity** that causes alarm fatigue and erodes trust
- **Deflated severity** that hides genuinely dangerous issues
- **Unsupported claims** lacking verifiable evidence
- **Contradictions** between skill reports examining the same code

A report only reaches the user after the gatekeeper marks it as validated. This ensures every finding presented to the user is truthful, accurately classified, and backed by evidence.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

## Intake Contract

Before challenging reports, read the review execution manifest supplied by
`code-chief`. The manifest must identify:

- every specialist report that was submitted
- every specialist that was intentionally skipped and why
- whether a user-facing frontend was in scope
- whether developer-experience surfaces were in scope
- whether each submitted report already meets the minimum evidence bar from `../../references/evidence-standards.md`

If the manifest is missing or ambiguous, return **REVISE** before validating
the report suite. The gatekeeper cannot score completeness against an unknown
expected skill set.

Validate specialist reports as partially-trusted input (Trust Level 3 per
evidence-standards.md): confirm each report contains the required sections
(findings list, evidence citations, severity classifications), reject reports
with missing or malformed structure before challenge evaluation.

## Challenge Protocol

Apply five challenge categories to every report received. Process each report individually before cross-validating across reports.

**Challenge category quick reference:**

| # | Category | Trigger | Example challenge |
|---|----------|---------|-------------------|
| 1 | Evidence Insufficiency | Finding lacks file:line or code excerpt | "CR-003 says 'auth is weak' — which file, which line, what code?" |
| 2 | Severity Inflation | Severity exceeds demonstrated impact | "This is rated Critical but requires admin access to exploit — justify the rating" |
| 3 | Scope Gap | Review missed files or dimensions | "The PR changes 8 files but bug-review only examined 5 — which 3 were skipped?" |
| 4 | Contradictory Findings | Two specialists disagree on the same code | "Bug-review says this null check is missing; code-review says it's unnecessary — resolve" |
| 5 | Phantom Resolution | Fix claims don't match actual changes | "The diff shows only a comment change but the response claims 'logic corrected'" |

### 1. Existence Challenge

Verify that cited evidence actually exists. For every finding:
- Confirm the referenced file path and line number contain the described code
- Verify the described code path actually executes (is it reachable from production entry points?)
- Check that function names, variable names, and API calls mentioned in the finding match the actual code
- For claims about behavior ("this function returns null when..."), verify the stated conditions produce the stated result

**Challenge rate:** Verify 100% of Critical/Major findings. Sample 30% of Minor findings.

### 2. Accuracy Challenge

Verify that classifications are correct. For each finding:
- If a bug is labeled "concurrency hazard," confirm shared mutable state is actually accessed from multiple execution contexts
- If a security finding maps to a CWE ID (e.g., CWE-79 XSS), confirm the code actually matches the weakness pattern described by that CWE
- If a CVSS score is assigned, verify the score components (attack vector, complexity, impact) match the actual exploit scenario
- If a quality finding claims "architecture drift," verify the architectural constraint being violated is documented (in an ADR, C4 model, or codebase convention)

**Challenge rate:** Verify 100% of Critical findings. Sample 50% of Major findings.

### 3. Completeness Challenge

Verify that each skill applied its full checklist without skipping categories:
- Compare the report's coverage against the skill's documented checklist (in its `references/checklist.md` or equivalent)
- If a skill addressed fewer categories than its checklist defines, challenge the gaps — were missing categories not applicable or overlooked?
- If security-review/mr-robot did not assess dependency graph and supply chain risks for changes adding/updating dependencies, challenge the gap
- If optional skills (frontier, design-qa, devex-review) were invoked, verify they covered all their documented domains; challenge any skipped domain without justification

Use `references/checklist.md` as the canonical completeness matrix for the
review suite.

### 4. Proportionality Challenge

Verify that severity assignments match actual impact:
- A missing null check in a logging utility is Minor, not Major
- A SQL injection in a user-facing endpoint is Critical, not Medium
- A style inconsistency is not a bug — flag reports that inflate cosmetic issues
- A race condition in a single-threaded application is not a concurrency hazard
- Cross-reference severity against the skill's own rubric definition

Flag both **inflation** (finding classified higher than warranted, creating noise) and **deflation** (finding classified lower than warranted, hiding risk).

### 5. Consistency Challenge

Verify coherence across multiple skill reports (applied during cross-validation phase):
- If code-review approved the design but quality-review flagged architecture drift in the same module, one of them is wrong — or the findings need reconciliation
- If security-review found no input validation issues but bug-review flagged boundary condition bugs on the same inputs, there may be a gap
- If two skills found the same issue, verify they assigned consistent severity

Consult `references/challenge-protocol.md` for the complete rubric with examples, resolution criteria, and edge case guidance for each challenge type.

## Delegation Mechanism

When a challenge identifies an issue, construct a delegation request and send it back to the originating skill for resolution.

Delegation requests target one of the invoked specialist skills with a specific challenge type, evidence requirement, and round number (max 2). Valid targets are `bug-review`, `code-review`, `quality-review`, `security-review`, `mr-robot`, `frontier`, `design-qa`, and `devex-review` when they were in scope. The originating skill responds with one of three resolutions: **corrected**, **defended**, or **withdrawn**.

- **Maximum 2 delegation rounds per finding.** Round 1 is the initial challenge. Round 2 is a follow-up if Round 1's response is unconvincing. After Round 2, unresolved findings are marked **"Disputed"** with both positions documented.
- **Batch delegation:** Group related challenges targeting the same skill into a single request to reduce round-trip overhead.

Consult `references/delegation-workflow.md` for the complete request/response formats, worked examples, batch strategies, escalation procedures, and resolution tracking ledger.

---

## Readiness Verdicts

The gatekeeper issues one of three verdicts after completing all challenges and cross-validation:

### Report Suite Marked "Ready" When:

- All challenged findings are resolved (corrected, defended with evidence, or withdrawn)
- No remaining Critical or Major issues are unaddressed
- Cross-validation shows no unresolved contradictions between skill reports
- Checklist coverage meets minimum thresholds for each invoked skill

### Report Suite Marked "Ready-with-Disputes" When:

- All "Ready" criteria are met except for findings in Disputed status
- Disputed items are fully documented with both skill and gatekeeper positions
- The user must resolve disputes before acting on the report
- No more than 2 Critical findings are in Disputed status (otherwise, verdict is "Not-Ready")

### Report Suite Marked "Not-Ready" When:

- Mandatory challenges remain unresolved after 2 delegation rounds
- More than 2 Critical findings are in Disputed status
- Cross-validation reveals unresolved contradictions that affect Critical/Major findings
- A skill's checklist coverage is below the minimum threshold without justification

---

## Cross-Validation Protocol

After individually validating each skill report, perform cross-validation across all submitted reports. Use the review execution manifest to determine which skills were expected. If fewer than two specialist reports were submitted, skip the matrix and note the reduced coverage. If an optional skill was out of scope and explicitly skipped, mark it "Not in scope." Do not challenge a skill that was never invoked.

**Build the Cross-Validation Matrix.** Map every changed file and function against findings from all invoked skills. For each cell, record the finding ID and severity, or "—" if no finding.

**Detect Overlaps.** When multiple skills flag the same code area, verify severity consistency. An input validation issue found by both bug-review (boundary condition) and security-review (injection) may warrant the higher severity — but both should agree on the core finding.

**Detect Gaps.** Changed code areas with no findings from any skill may be genuinely clean or may represent review blind spots. Challenge the skill most relevant to that code area.

**Detect Contradictions.** When findings from different skills conflict, escalate the contradiction. The gatekeeper must determine which position is correct or document both positions as Disputed for user resolution.

Consult `references/cross-validation.md` for the full cross-validation protocol and report template.

---

## Output Format

Structure the validation report with the following sections:

1. **Run ID** and **Overall Verdict** (Ready | Ready-with-Disputes | Not-Ready)
2. **Per-Skill Validation** — for each invoked skill: status (Validated / Validated-with-amendments / Requires-rework), challenge counts by type, amendments applied
3. **Cross-Validation Findings** — overlaps with severity reconciliation, gaps with justification or challenge, contradictions with resolution or dispute status
4. **Disputed Items** — finding ID, skill position vs gatekeeper position, user judgment required
5. **Confidence Assessment** — review coverage percentage, challenge acceptance rate (calibration indicator)

Consult `references/cross-validation.md` for the full report template.

---

## Adversarial Verification Protocol

Before issuing ANY verdict, execute the following mandatory self-checks.
Skipping any step invalidates the review because partial adversarial
verification creates a false sense of validation quality.

### Anti-Rubber-Stamp Rule

A Ready verdict requires ALL of the following:

1. **Minimum 3 specific code references** — cite exact files and lines from
   the codebase that were inspected to verify findings
2. **At least 1 cross-validation finding** — document at least one overlap,
   gap, or contradiction found during cross-validation (or explicitly state
   why none exist)
3. **Explicit confidence statement** — classify each challenged finding as
   Proven (verified by reading code), Likely (strong indicators), or
   Possible (circumstantial). Only Proven findings may be CRITICAL.

### Gaming Detection

Watch for these manipulation patterns in review reports:

- **Phantom findings:** Findings that cite file paths or line numbers that
  do not exist or do not contain the described issue. Always verify.
- **Severity inflation:** Classifying cosmetic issues as MAJOR to pad the
  finding count and appear thorough. Check against the severity rubric.
- **Severity deflation:** Classifying genuine vulnerabilities as MINOR to
  avoid remediation effort. Cross-reference with CVSS/CWE standards.
- **Checklist gaming:** Marking checklist items as "N/A" without
  justification to avoid reviewing them. Challenge every N/A.
- **Contradiction hiding:** Two skills finding the same issue at different
  severities without reconciliation. Force reconciliation.

### Pre-Verdict Self-Check

1. Re-read all critical findings across all skill reports
2. For each finding marked as resolved, confirm the resolution evidence
   exists in the actual code (not just in the skill's narrative)
3. Ask: "If this code has a vulnerability that escapes review, would my
   cross-validation have caught it?" If uncertain, add more scrutiny
4. Verify the cross-validation matrix has no unexplained gaps in coverage

---

## Anti-Gaming Safeguards

Guard against own biases and potential manipulation by reviewed skills:

- **Severity Uniformity:** Reject inflation/deflation that bypasses the objective rubric
- **Remediation Regression:** Verify fixes do not introduce new findings elsewhere
- **Calibration:** Track challenge acceptance rate — too high = too aggressive; too low = not adding value
- **Proportionality:** Prioritize high-impact challenges over Minor disputes

---

## Gatekeeper Self-Correction

When a gatekeeper challenge is overturned by evidence from the specialist:

1. **Acknowledge the error explicitly** — state what was wrong in the challenge
2. **Withdraw the challenge** — remove it from the blocking findings list
3. **Adjust calibration** — if the same type of challenge keeps getting overturned, recalibrate the threshold for that challenge type
4. **Document the pattern** — note the overturned challenge and reason in the verdict report under "Calibration Notes" so future runs benefit

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| Only 1-2 specialist reports submitted (not the full 6) | Validate available reports normally. Skip cross-validation (insufficient for meaningful matrix). Note reduced coverage in verdict as a limitation — do not inflate confidence. |
| Code-chief omits an optional skill without a skip reason | Return **REVISE**. Require the execution manifest to state whether the skill was out of scope, unavailable, or intentionally deferred. |
| Specialist report references files that no longer exist | Treat cited evidence as unverifiable. Downgrade the finding confidence to "Possible" and request re-verification from the specialist via delegation. |
| Two specialists flag the same issue at contradictory severities | Force reconciliation: cite both severity assessments, apply the objective rubric, and declare the correct severity. If genuinely ambiguous, mark as Disputed and escalate. |
| Specialist provides no evidence for a Critical finding | Reject the finding. Critical findings require Proven evidence (file:line references verified in the codebase). Return to the specialist for substantiation. |
| All reports are clean — no findings at all | Do not rubber-stamp. Verify that the review scope was correct (were all changed files covered?). If scope was incomplete, challenge. If genuinely clean, issue Ready with a note confirming scope verification. |
| Gatekeeper receives a report from a skill not in the expected set | Accept and validate it if it covers code in scope. Note the unexpected skill in the verdict report. Do not reject work simply because the routing was unconventional. |
| Specialist findings reference a codebase version that has changed since the review started | Treat findings as stale. Flag the version mismatch, identify which findings are likely still valid (logic issues) versus potentially invalidated (line-number-dependent fixes), and request targeted re-verification for invalidated findings. |
| Gatekeeper challenge is well-reasoned but specialist provides convincing counter-evidence | Accept the specialist's defense, withdraw the challenge, and log the overturned challenge in Calibration Notes. If the same challenge type is overturned repeatedly, adjust the challenge threshold for that type. |
| All specialist reports are clean (zero findings) and suspiciously uniform | Do not rubber-stamp. Verify scope coverage was complete (all changed files examined). Sample-challenge at least 2 reports for checklist completeness. If scope was correct and reviews are genuinely clean, issue Ready with explicit scope verification note. |

### Worked Challenge Cycle

**Context:** code-chief submits a 6-skill review package for a Node.js REST API.

1. **Existence challenge on security-review:** Report lists 8 findings but only cites file:line for 5. Gatekeeper returns REVISE: "Findings SEC-003, SEC-006, SEC-008 lack file:line evidence. Substantiate or withdraw."
2. **Security-review responds:** Provides file:line for SEC-003 and SEC-006. Withdraws SEC-008 (was a false positive from an outdated dependency list).
3. **Cross-validation:** quality-review rates the codebase "B" on maintainability. code-review flags 3 "High complexity" functions. Bug-review finds 0 issues in those same functions. Gatekeeper notes the discrepancy: high complexity but no bugs found — either bug-review missed edge cases or complexity is well-tested.
4. **Proportionality challenge on bug-review:** "Functions `calculateDiscount()`, `applyTaxRules()`, and `resolveShipping()` have cyclomatic complexity >20 per quality-review. Bug-review reports 0 findings. Confirm these functions were exercised with boundary inputs."
5. **Bug-review responds:** Provides evidence that all 3 functions were tested with boundary inputs. 0 bugs confirmed. Gatekeeper accepts — complexity does not guarantee bugs.
6. **Verdict:** APPROVED with 2 resolved findings, 1 withdrawn, and a calibration note that high complexity without bugs should still carry an advisory for future refactoring.

---

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive the consolidated multi-skill review package from code-chief
- Validate all phase reports in a single pass, applying the 5-challenge protocol to each
- Build the cross-validation matrix across all submitted skill reports (up to 8 skills)
- Route all delegation requests back through code-chief (not directly to skills)
- Code-chief forwards skill responses back to gatekeeper-code for verdict

**When invoked standalone (by a specialist skill directly):**
- Receive a single skill’s report for adversarial validation
- Apply the 5-challenge protocol to that report
- Skip the cross-validation phase (only one report available)
- Return the verdict directly to the invoking skill

---

## Reference Files

| File | Purpose |
|------|---------|
| `references/checklist.md` | Canonical completeness matrix for the review suite, including optional design-qa and devex-review coverage expectations |
| `references/challenge-protocol.md` | Detailed existence, accuracy, completeness, proportionality, and consistency challenge rules |
| `references/cross-validation.md` | Cross-validation matrix process, overlap resolution, contradiction handling, and report template |
| `references/delegation-workflow.md` | Delegation request and response formats, batch strategy, dispute handling, and escalation rules |
| `../../references/evidence-standards.md` | Shared evidence specificity, severity alignment, and calibration thresholds used before accepting any finding as validated |

---

## Pipeline Persistence

Gatekeeper-code does not own pipeline persistence — the invoking orchestrator (code-chief in pipeline mode, or admiral at the cross-pipeline level) handles save operations.

- **In pipeline mode**: code-chief writes the gatekeeper verdict to `gatekeeper-code_verdict.md` in the run's review directory
- **In standalone mode**: the invoking skill or user is responsible for persisting the verdict
- **Save awareness**: when a Run ID or reference paths are provided, gatekeeper-code may read persisted deliverables from `skillset-saves/runs/{run-id}/review/` for validation
- **Evidence standards**: require every verdict to meet the minimum evidence bar in `../../references/evidence-standards.md`

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

---

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*
