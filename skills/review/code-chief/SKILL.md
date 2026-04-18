---
name: code-chief
description: >-
  This skill should be used when the user asks to "do a full code
  review", "review this codebase comprehensively", "run all review
   skills", "start the review pipeline", "do a complete audit",
   "audit this PR", "check this change before merge", "review
   everything", "pressure-test this codebase", or "run code-chief".
   Entry point and orchestrator for the Code-Check SkillSet —
   always delegates to the core review specialists (bug-review,
   code-review, quality-review, security-review, mr-robot) and
   conditionally invokes frontier, design-qa, and devex-review when
   frontend or developer-experience surfaces are in scope. Manages
   gatekeeper-code cycles and delivers a consolidated review package
   with readiness verdicts and prioritized remediation.
   DO NOT USE for running an individual specialist review directly.
   DO NOT USE for build pipeline tasks (use build-management).
   DO NOT USE for design tasks (use commander).
version: 1.0.0
 
---

# Code-Chief — Review Pipeline Orchestrator

## Purpose

Act as the single entry point for the Code-Check SkillSet. Receive the user's
review request (codebase, changeset, PR, module), orchestrate all applicable
specialist review skills in sequence, manage gatekeeper-code approval cycles,
and deliver a consolidated, validated review package. Keep the user interacting
with code-chief only during the full pipeline — all other skills are invoked
autonomously.

Treat inputs per the trust levels defined in
`../../references/evidence-standards.md` §Input Trust Boundaries.

The canonical workflow is strict and fail-closed. It always runs the core
five review specialists, then adds optional specialist phases when the target
surface warrants them:

`code-chief → bug-review → code-review → quality-review → security-review → mr-robot → [frontier] → [design-qa] → [devex-review] → gatekeeper-code → delivery`

No mandatory phase may be skipped in the canonical pipeline without documented
justification, and a phase is not accepted until `gatekeeper-code` validates it
through code-chief.

## Core Principle

> "Code-chief drives the review pipeline proactively. It does not wait for
> instructions between phases — it pushes forward, resolves ambiguity where
> possible, and only returns to the user when it cannot proceed without their
> input."

---

## Orchestration Protocol

### Phase 0: Intake and Scoping

When invoked, execute the intake sequence:

1. **Identify the review target**: What is being reviewed — a full codebase, a PR/changeset, a specific module, or a targeted audit?
2. **Assess scope**: Full pipeline (all applicable phases) or targeted review (specific skills)?
3. **Detect technology stack**: Identify languages, frameworks, and runtime environments to configure phase-specific checklists
4. **Determine frontend presence**: Does the codebase include a user-facing frontend? (Determines whether Phases 6 and 7 run)
5. **Determine developer-experience surface**: Does the target expose onboarding docs, CLI commands, SDKs, public APIs, or setup flows worth auditing? (Determines whether Phase 8 runs)
6. **Classify risk tier**: Low-risk (docs, config, styling, test-only), Standard (feature code, business logic), High-risk (auth, crypto, payments, data handling, infrastructure)
7. **Confirm understanding**: Summarize the review scope back to the user and request confirmation before proceeding — this is the ONLY mandatory user checkpoint
8. **Initialize persistent saves** (standalone mode only — in pipeline mode, admiral handles this):
   a. Check if `### Save Context` was provided in the admiral delegation; if so, use that save path and skip initialization
   b. If standalone: check for `{workspace-root}/skillset-saves/`, create if absent, generate run-id per `save-protocol.md`, and write the following control files:
      - `_index.md` — create or update the master registry
      - `_latest.md` — point to this run
      - `_save-protocol.md` — self-documenting copy
      - `_run-manifest.md` — with `pipeline_mode: review-only`, `admiral_state: STANDALONE`
      - `_lock.md` — advisory lock with fresh `session_id`, `lock_status: ACTIVE`, `admiral_state: STANDALONE`
      - `_state.md` — with `admiral_state: STANDALONE`, `review_state: REVIEW_ACTIVE`, other pipeline states `SKIPPED`
      - `_audit-trail.md` — with `SESSION_START` entry
      - `design/_skip-record.md`, `build/_skip-record.md` — with `status: USER_SUPPLIED` or `SKIPPED` depending on whether the user provided upstream artifacts
      - `azure/_skip-record.md` — with `status: NOT_APPLICABLE`
   c. **Resume check**: if an in-progress review run exists, follow the resume protocol in `save-protocol.md` §State-Artifact Consistency Validation (scoped to review pipeline). Check `_lock.md` for live conflicts, validate `_state.md`, check for pending escalations, append `SESSION_RESUME` to `_audit-trail.md`, and offer to resume or start fresh
   d. On failure: continue without persistence (graceful degradation)
   e. **Lock lifecycle**: refresh `_lock.md` `last_heartbeat` whenever `_state.md` is updated and at least every 300 seconds during delegations; release lock (`RELEASED`) on clean completion

If the review target is ambiguous, ask clarifying questions. Prefer a single
batch of questions over multiple rounds.

### Phase 1: Correctness Defects → bug-review

**Delegate to**: `bug-review` skill
**Input provided**: Review target scope, identified files and modules, technology stack
**Expected output**: Structured defect report with findings classified by severity (Critical/Major/Minor), 8-category checklist coverage, and risk assessment
**Why first**: Correctness defects are the most immediately dangerous — a crashing or data-corrupting bug outweighs style or maintainability concerns

Consult `../../references/handoff-templates.md` for the unified delegation template format (metadata header, save context, phase instruction, return contract).

### Phase 2: Merge-Readiness Assessment → code-review

**Delegate to**: `code-review` skill
**Input provided**: Review target + Phase 1 findings (for context, not re-evaluation)
**Expected output**: 8-dimension assessment with scores per dimension, PR assessment (size, risk tier, Ship/Show/Ask), and merge recommendation (Approve/Approve with Nits/Request Changes)
**Why second**: Holistic merge-readiness builds on the correctness foundation and provides the broadest assessment before deep-diving into specific concerns

### Phase 3: Maintainability & Standards → quality-review

**Delegate to**: `quality-review` skill
**Input provided**: Review target + Phase 1–2 context
**Expected output**: Quality score (Pass/Conditional/Fail), standards enforcement report (3-layer stack), architecture drift assessment, efficiency findings, and technical debt measurement
**Why third**: Long-term sustainability is evaluated after immediate correctness and merge-readiness, catching patterns that will degrade the codebase over time

### Phase 4: Security Analysis → security-review

**Delegate to**: `security-review` skill
**Input provided**: Review target + Phase 1–3 context
**Expected output**: Security findings mapped to NIST SSDF, OWASP ASVS/Top 10, CWE Top 25 with risk tier, threat model updates, and compliance assessment
**Why fourth**: Defensive security review establishes the compliance baseline before adversarial testing deepens the analysis

### Phase 5: Adversarial Penetration Testing → mr-robot

**Delegate to**: `mr-robot` skill
**Input provided**: Review target + Phase 4 security findings (critical input for targeted exploitation)
**Expected output**: Adversarial analysis report with exploit chain constructions, supply chain attack surface assessment, API abuse scenarios, and CVSS 4.0-scored findings with proof-of-concept descriptions
**Why fifth**: Offensive testing validates that the defensive security controls identified in Phase 4 actually hold under attack conditions

### Phase 6: Frontend Analytics & UI/UX Audit → frontier

**Delegate to**: `frontier` skill
**Input provided**: Review target (frontend components only) + Phase 1–5 context
**Expected output**: 5-domain audit report covering performance (Core Web Vitals), accessibility (WCAG 2.2), frontend security (CSP, Trusted Types), component architecture, and UI/UX quality
**Condition**: Skip this phase if the codebase has no user-facing frontend (pure backend/API/CLI). Document the skip justification.

### Phase 7: Visual Design Quality Audit → design-qa

**Delegate to**: `design-qa` skill
**Input provided**: Review target (rendered frontend, component styles, tokens, screenshots if available) + Phase 1–6 context
**Expected output**: Visual QA report covering token adherence, hierarchy, spacing, color, interactive states, responsive quality, AI-slop detection, and any direct mechanical CSS fixes applied
**Condition**: Run this phase only when the target includes a user-facing frontend with meaningful rendered UI, CSS, or component styling. Skip for pure backend/API/CLI work, or when no visual surface is available for review. Document the skip justification.
**Why seventh**: Visual QA should build on frontier's structural, accessibility, and security analysis so the final UI recommendations are specific and non-contradictory.

### Phase 8: Developer Experience Audit → devex-review

**Delegate to**: `devex-review` skill
**Input provided**: Review target + docs, onboarding flows, CLI/API/SDK surfaces, and Phase 1–7 context
**Expected output**: Evidence-based DX audit report with TTHW, onboarding friction, docs quality, error-message quality, upgrade path assessment, and prioritized DX improvements
**Condition**: Run this phase when the project exposes developer-facing surfaces such as a README onboarding flow, CLI, SDK, API docs, integration docs, or contributor workflow. Skip for purely internal code changes that do not affect developer-facing surfaces. Document the skip justification.
**Why eighth**: DX review is most useful after correctness, security, frontend, and visual findings are known so onboarding and documentation recommendations reflect the actual product state.

Consult `../../references/handoff-templates.md` for exact delegation wording for each phase.

---

## Gatekeeper Management Protocol

After all applicable phases complete, code-chief consolidates all phase reports
and submits the combined package to `gatekeeper-code` for adversarial validation.

For the consolidated submission:

1. Compile all phase reports into a single review package plus a review execution manifest listing invoked skills, skipped skills, skip justifications, frontend presence, and developer-experience surface status
2. Validate each incoming specialist report against `../../references/evidence-standards.md` before consolidation: reject phantom findings, flag severity inflation or deflation, require explicit justification for `N/A` checklist areas, and record any confidence gaps in the execution manifest
3. Submit the package to `gatekeeper-code` for adversarial validation
4. If **APPROVED**: Record the approval and proceed to final consolidation
5. If **REVISE**: Forward gatekeeper-code's findings back to the originating specialist skill(s) with instructions to address mandatory fixes, then re-submit the revised package
6. If **ESCALATE**: Surface the blocking issue and consult the user
7. Maximum revision cycles: **3** per finding because unbounded revision loops waste context and delay delivery; if still unresolved after 3, escalate to user with both positions documented

Code-chief is the sole owner of the gatekeeper cycle in pipeline mode. A
specialist skill may self-run `gatekeeper-code` only during standalone use
outside this orchestration flow.

**Save triggers** (at each pipeline step):
- On delegation: create phase directory (e.g., `review/phase-1_bug-review/`), write `_phase-state.md` (state: ACTIVE), append `_audit-trail.md`
- On report return: update `_phase-state.md` (state: SUBMITTED)
- On gatekeeper-code APPROVED: write `gatekeeper-code_verdict.md`, update all `_phase-state.md` to COMPLETE, update `_state.md`, append `_audit-trail.md`
- On REVISE: write `gatekeeper-code_verdict.md` (REVISE), update affected `_phase-state.md`, append `_audit-trail.md`

### Delegation Requests Through Code-Chief

When `gatekeeper-code` issues a delegation request, code-chief routes it to the
target skill and collects the response:

1. Receive delegation request from `gatekeeper-code`
2. Forward to the target skill (e.g., `bug-review`, `mr-robot`)
3. Receive the skill's response (corrected, defended, or withdrawn)
4. Forward the response back to `gatekeeper-code`
5. Repeat until `gatekeeper-code` issues a verdict

Consult `references/workflow-protocol.md` for detailed state management.

### Specialist Report Intake Heuristics

Before accepting any specialist report into the consolidated package:

1. Confirm cited evidence meets the minimum specificity bar in `../../references/evidence-standards.md`
2. Reject findings whose file, line, screenshot, command output, or reproduction evidence cannot be traced back to the actual target
3. Flag severity inflation or deflation when the reported impact does not match the skill's own rubric
4. Require any skipped checklist area or optional phase omission to be documented in the execution manifest
5. Preserve unresolved confidence gaps for `gatekeeper-code` instead of silently normalizing them away

---

## Skip Logic

Code-chief may skip or simplify phases when the review scope does not warrant
full execution. All skips MUST be documented with justification because
undocumented skips cause gatekeeper rejection and audit-trail gaps.

| Scenario | Phase(s) Affected |
|----------|-------------------|
| Backend-only / API / CLI project | Phase 6 (frontier) — SKIP; Phase 7 (design-qa) — SKIP |
| Low-risk change (docs, config, styling) | Phase 5 (mr-robot) — SIMPLIFY to reconnaissance only; Phase 8 (devex-review) — RUN if docs or onboarding changed |
| Test-only changes | Phase 5 (mr-robot) — SKIP, Phase 6 (frontier) — SKIP, Phase 7 (design-qa) — SKIP |
| No external dependencies changed | Phase 5 (mr-robot) — Skip supply chain analysis |
| Single-file hotfix | Phases 3, 6, and 7 — SIMPLIFY |
| Security-focused audit request | Phases 1–3 — SIMPLIFY, Phases 4–5 — FULL |
| Frontend-only change | Phase 5 (mr-robot) — SIMPLIFY to frontend attack vectors only; Phases 6–7 — FULL |
| Library / SDK / platform onboarding change | Phase 8 (devex-review) — FULL |
| No developer-facing surface in scope | Phase 8 (devex-review) — SKIP |

Phases 1 (bug-review), 2 (code-review), and 4 (security-review) are NEVER
fully skipped in the canonical pipeline because correctness, merge-readiness,
and security are baseline guarantees every review must provide. They may be
simplified for trivial changes but must always execute. Phase 7 runs whenever
a user-facing frontend
surface exists. Phase 8 runs whenever onboarding, CLI, SDK, API docs, or other
developer-facing surfaces are in scope.

---

## Worked Routing Example

**Worked routing example:**

1. Code-chief receives delegation from admiral with review target scope
2. Code-chief delegates Phase 1 to bug-review: "Review `src/` for correctness defects"
3. Bug-review returns report with 2 Critical, 1 Major findings
4. Code-chief delegates Phase 2 to code-review: same scope + bug-review context
5. Code-review returns report with 3 Major, 2 Minor findings
6. (Phases 3–6 continue with remaining specialists)
7. Code-chief consolidates all specialist reports into a review package
8. Code-chief submits the consolidated package to gatekeeper-code
9. Gatekeeper-code challenges: "Bug-review SEC-002 and code-review CR-005 both flag `auth.ts:42` — are these the same finding or distinct issues?"
10. Code-chief resolves: "Distinct. SEC-002 is a missing null check (correctness). CR-005 is the same function having cyclomatic complexity 18 (maintainability). Both require fixes but for different reasons."
11. Gatekeeper-code issues APPROVED with the clarification recorded

---

## Edge Cases & Failure Modes

| Scenario | How to Handle |
|----------|---------------|
| Monorepo contains frontend code but the change touches backend-only services | Run Phase 6 and Phase 7 only if the backend change affects frontend contracts, rendering paths, or shared UI packages. Otherwise, record both phases as out of scope in the execution manifest. |
| Docs-only or onboarding-only change with no production code change | Keep Phases 1, 2, and 4 lightweight, then run Phase 8 in full because developer-facing friction is the primary review target. |
| User-facing frontend exists but no rendered screenshots or running surface is available | Run `frontier` on the code and component structure, then either run `design-qa` against source styling artifacts or document a justified skip if no meaningful visual surface can be inspected. |
| Code-chief receives a partial upstream package with missing phase reports | Stop before gatekeeper submission, record the missing artifacts in the execution manifest, and request the missing specialist output rather than inferring coverage. |
| Frontier and design-qa disagree on a frontend issue | Preserve both findings, note the contradiction in the execution manifest, and send both into `gatekeeper-code` for reconciliation instead of resolving the conflict locally. |
| Diff is too large for exhaustive deep review in one pass | Prioritize entry points, security boundaries, data mutation paths, and user-visible workflows first, then record any scoped sampling limits explicitly in the final package. |
| A specialist skill is unavailable or returns an error mid-pipeline | Record the failure in the execution manifest, attempt one retry, then proceed with remaining specialists and flag the gap for gatekeeper-code rather than blocking the entire pipeline. |
| Two specialists produce findings that require contradictory fixes | Do not resolve the contradiction locally. Document both findings with full evidence, flag the conflict in the execution manifest, and escalate to gatekeeper-code for adjudication. |

---

## Final Consolidation and Delivery

After the gatekeeper-code has approved the consolidated review package:

### Step 1: Compile Review Package

Assemble bug-review, code-review, quality-review, security-review, mr-robot,
frontier (or its skip record), design-qa (or its skip record), devex-review
(or its skip record), the review execution manifest, and gatekeeper-code
outputs into the package template defined in `references/delivery-protocol.md`.

### Step 2: Cross-Deliverable Consistency Check

Before final handover, verify consistency across all reports:
- Bug findings do not contradict security findings on the same code paths
- Quality architectural concerns align with code-review design assessment
- Security findings and mr-robot findings agree on severity for overlapping issues
- Frontend security findings from frontier align with security-review's web security assessment

### Step 3: Save Consolidated Package

**Save**: Write `review/code-chief/review-package.md` and `review/code-chief/delegation-log.md`. Update `_state.md` (review_state: DELIVERED). Append final entry to `_audit-trail.md`.

### Step 4: Deliver to User

Present the complete review package with:
- Table of contents linking to each report
- Executive summary (one paragraph)
- Risk summary table
- Prioritized remediation list
- Disputed items requiring user judgment

---

## Canonical Workflow Guarantees

### Mandatory Phase Enforcement

In the canonical pipeline, the following phases are mandatory for every review
(subject to skip logic for scope-irrelevant phases):

- Phase 1: `bug-review` — ALWAYS
- Phase 2: `code-review` — ALWAYS
- Phase 3: `quality-review` — ALWAYS (may simplify for hotfixes)
- Phase 4: `security-review` — ALWAYS
- Phase 5: `mr-robot` — ALWAYS for Standard/High risk; simplifiable for Low risk
- Phase 6: `frontier` — ALWAYS if frontend present; SKIP if no frontend
- Phase 7: `design-qa` — ALWAYS if a rendered frontend or styling surface is present; SKIP if no frontend/UI surface exists
- Phase 8: `devex-review` — ALWAYS if docs, CLI, SDK, API docs, onboarding, or contributor workflow are in scope; SKIP only when no developer-facing surface exists

If a specialist phase or `gatekeeper-code` review cannot run, code-chief MUST
escalate and stop rather than skipping the phase or self-approving the output
because self-approval bypasses the adversarial validation that gatekeepers exist
to provide.

### Proactive Driving

Code-chief MUST proactively drive the pipeline because returning to the user at
every step defeats the pipeline's speed advantage:
- Detect the technology stack and configure review checklists without asking the user
- Determine frontend presence automatically by examining file extensions and project structure
- Resolve minor ambiguities without user consultation (document assumptions)
- Push each phase forward without waiting for user prompting
- Track all phase outputs and revision cycles for traceability
- Aggregate cross-skill findings to eliminate duplicate reports on the same issue

---

## Additional Resources

### Reference Files

For detailed orchestration logic and templates:
- **`references/workflow-protocol.md`** — Detailed state management, transition rules, revision cycle tracking, error handling, and escalation procedures
- **`references/delivery-protocol.md`** — Final review-package template, risk summary layout, and delivery checklist
- **`../../references/handoff-templates.md`** — Structured delegation templates for each specialist skill, gatekeeper submission format, and final delivery template
- **`save-protocol.md`** (project root) — Persistent save system: directory structure, file formats, save triggers, resume protocol

If any save operation fails, follow the Persistence-Failure Decision Tree
in `save-protocol.md` §Persistence-Failure Decision Tree.

---

*Cross-cutting frameworks (Build & Implementation, Iron-Law Debugging, Azure Deployment, Adversarial Anti-Gaming) apply to all skills. See `../../references/universal-frameworks.md` for complete definitions.*
