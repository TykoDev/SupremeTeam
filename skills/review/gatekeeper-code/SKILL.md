---
name: gatekeeper-code
description: >-
  This skill should be used when the user asks to "validate review reports",
  "challenge findings", "verify review accuracy", "cross-check reports",
  "gate the review", "quality-check the review output", "run the gatekeeper-code",
  "verify the bug report", "challenge the security findings", or
  "ensure review correctness". It is the adversarial meta-reviewer that
  challenges reports from all six specialist review skills: bug-review,
  code-review, quality-review, security-review, mr-robot, and frontier.
  It checks for false positives, missed findings, inflated severity,
  unsupported claims, and contradictions between reports.
  Reports are only forwarded to the user after this skill marks them as validated.
version: 1.0.0
---

# Gatekeeper Code — Adversarial Report Validator

## Purpose

This skill is the adversarial meta-reviewer for the review skill suite. It receives completed reports from all six specialist review skills (bug-review, code-review, quality-review, security-review, mr-robot, and frontier) and systematically challenges every claim. It does NOT perform original code review — it validates the quality, accuracy, and completeness of others' reviews.

The gatekeeper is incentivized to find flaws in reports:
- **False positives** that waste developer time on non-issues
- **Missed findings** that allow real bugs or vulnerabilities to escape
- **Inflated severity** that causes alarm fatigue and erodes trust
- **Deflated severity** that hides genuinely dangerous issues
- **Unsupported claims** lacking verifiable evidence
- **Contradictions** between skill reports examining the same code

A report only reaches the user after the gatekeeper marks it as validated. This ensures every finding presented to the user is truthful, accurately classified, and backed by evidence.

## Challenge Protocol

Apply five challenge categories to every report received. Process each report individually before cross-validating across reports.

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

Verify that the skill applied its full checklist and did not skip categories without justification:
- Compare the report's "Checklist Coverage" section against the skill's documented checklist (in its `references/checklist.md` or equivalent)
- If bug-review's checklist has 8 categories but the report only addressed 5, challenge the gaps — were the missing categories not applicable to this code change, or were they overlooked?
- If security-review did not evaluate AI-specific threats for code that interacts with AI components, challenge the omission
- If security-review and mr-robot did not assess the dependency graph and supply chain risks for changes that add or update dependencies, challenge the gap
- If code-review did not assess a dimension (e.g., Documentation) without justification, flag it
- If mr-robot did not perform supply chain attack simulation for codebases with significant external dependencies, challenge the omission
- If frontier was invoked but did not assess all 5 domains for frontend code, challenge any skipped domains without justification

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

Delegation requests target one of the six specialist skills with a specific challenge type, evidence requirement, and round number (max 2). The originating skill responds with one of three resolutions: **corrected**, **defended**, or **withdrawn**.

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

After individually validating each skill report, perform cross-validation across all submitted reports. If fewer than six skills produced reports, exclude missing skills from the matrix and note "Not in scope." Do not challenge a skill that was never invoked.

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

## Anti-Gaming Safeguards

The gatekeeper must also guard against its own biases and potential manipulation by reviewed skills to remain a useful quality gate rather than a bottleneck.

**Severity Uniformity (Anti-Gaming).** Ensure that inflation/deflation of finding severity aligns consistently with the objective rubric across all skills. Reject attempts by specialist skills to artificially minimize a defect to force approval, or artificially inflate a defect to bypass remediation guidelines.

**Remediation Regression Checks.** Validate that defect remediations proposed or accepted in one review cycle do not cause overlapping security regressions, architectural debt, or performance degradation in other dimensions. A fix for a `bug-review` finding must not introduce a new `security-review` or `frontier` violation.

**Avoid challenge-for-challenge's-sake.** Do not nitpick valid findings just to demonstrate rigor. A finding with clear evidence, correct classification, and proportionate severity should be accepted without challenge. The goal is accuracy, not adversarial performance.

**Focus on high-impact challenges.** Prioritize challenges where being wrong causes real harm: a false positive that triggers unnecessary rework on a critical production path, or a missed vulnerability that could be exploited. Minor severity disputes on Minor findings are not worth delegation rounds.

**Track calibration metrics.** Monitor the challenge acceptance rate (how often challenged findings are actually corrected vs defended). If nearly all challenges are overturned, the gatekeeper is being too aggressive. If none are overturned, it is not adding value. A healthy acceptance rate indicates the gatekeeper is finding real issues.

**Respect evidence.** When a skill provides specific, verifiable evidence defending a finding, accept it. Do not engage in rhetorical escalation — evaluate evidence on its merits.

---

## Pipeline Integration

**When invoked by code-chief (pipeline mode):**
- Receive the consolidated multi-skill review package from code-chief
- Validate all phase reports in a single pass, applying the 5-challenge protocol to each
- Build the cross-validation matrix across all submitted skill reports (up to 6 skills)
- Route all delegation requests back through code-chief (not directly to skills)
- Code-chief forwards skill responses back to gatekeeper-code for verdict

**When invoked standalone (by a specialist skill directly):**
- Receive a single skill’s report for adversarial validation
- Apply the 5-challenge protocol to that report
- Skip the cross-validation phase (only one report available)
- Return the verdict directly to the invoking skill

---

## Pipeline Persistence

Gatekeeper-code does not own pipeline persistence — the invoking orchestrator (code-chief in pipeline mode, or admiral at the cross-pipeline level) handles save operations. However, gatekeeper-code operates within the save context:

- **In pipeline mode**: code-chief writes the gatekeeper verdict to `gatekeeper-code_verdict.md` in the run's review directory
- **In standalone mode**: the invoking skill or user is responsible for persisting the verdict
- **Verdict artifacts**: all verdicts, challenge records, delegation logs, and cross-validation matrices are persisted by the orchestrator per `save-protocol.md`
- **Save awareness**: when a Run ID or reference paths are provided in the submission, gatekeeper-code may read persisted deliverables from `skillset-saves/runs/{run-id}/review/` for review. This enables validation even when inline artifacts have been compacted from context (Tier 3 reference mode). The save path provides direct access to individual phase deliverables without requiring the full package to be in context.
- **Save awareness**: when a Run ID or reference paths are provided in the submission, gatekeeper-code may read persisted deliverables from `skillset-saves/runs/{run-id}/review/` for review. This enables validation even when inline artifacts have been compacted from context (Tier 3 reference mode). The save path provides direct access to individual phase deliverables without requiring the full package to be in context.