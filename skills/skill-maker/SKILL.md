---
name: skill-maker
description: >
  End-to-end orchestrator for creating, reviewing, improving, optimizing, and packaging Claude
  skills and coordinated skill teams. Use when the user says "create a skill", "make a skill",
  "build me a skill", "write a skill", "run the skill pipeline", "review this skill", "harden
  this skill", "take this skill to 100", "ship this skill", "make it production-ready", "create
  and review a skill", "iterate this skill to perfection", or describes a desired skill behavior
  without naming skill-maker. Also use when `admiral` delegates skill or team creation. Routes
  all drafting, evals, fixes, rubric scoring, and packaging to specialists; do not use for
  general code review, architecture, or non-skill authoring tasks.
version: 1.0.0
---

# Skill Maker

Single entry point for the full skill creation, adversarial review, and iterative
improvement lifecycle. Delegates all substantive work to two specialists — never
modifies skill output directly. Skill-maker can be invoked standalone or as a
delegated sub-orchestrator inside admiral (the SupremeTeam pipeline orchestrator).

> "Orchestrate, delegate, gate. The orchestrator routes work and enforces the quality
> loop. It never writes skill content or scores rubric dimensions — that is the
> specialists' job."

## Entry Routing

Skill-maker is a component of the **Admiral** delivery pipeline; `admiral` (the SupremeTeam
pipeline orchestrator) is the primary entry orchestrator (see `../routing-doctrine.md` —
gates which orchestrator owns a given request and prevents double-routing). Before starting Stage 0, run the
**active-handoff check** — a handoff is present when the prompt carries a `### Save Context`
block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or `admiral`
explicitly delegates a skill/team-creation request (the `## Admiral Integration` contract
below).

- **Handoff present** → proceed with the pipeline; this is a delegated Admiral run.
- **No handoff (cold/direct invocation for a create/review/improve request)** → do not run
  standalone. Start `admiral` first (its Create-skill / Create-team mode), let it run intake
  and persistence, then accept the delegation back. This is the loop guard: Admiral delegates
  with the handoff signal, so a routed call proceeds immediately and never re-bootstraps
  Admiral.

## Pipeline overview

```
User Request
    │
    ▼
┌─────────────┐
│ Stage 0      │  Intake — classify mode, gather context
│ INTAKE       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Stage 1      │  Delegate to skill-creator (Create mode)
│ CREATE       │  → draft SKILL.md + supporting files
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Stage 2      │  Delegate to skill-reviewer
│ REVIEW       │  → scorecard + findings report
└──────┬──────┘
       │
       ▼
  score = 100? ──yes──→ Stage 4 (Optimize)
       │
      no
       │
       ▼
┌─────────────┐
│ Stage 3      │  Delegate to skill-creator (Improve mode)
│ IMPROVE      │  → apply reviewer findings
└──────┬──────┘
       │
       └──→ Loop back to Stage 2
              (max 5 cycles)

       ▼
┌─────────────┐
│ Stage 4      │  Delegate to skill-creator (Optimize mode)
│ OPTIMIZE     │  → description trigger accuracy
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Stage 5      │  Delegate to skill-creator (Package mode)
│ PACKAGE &    │  → .skill file + delivery report
│ DELIVER      │
└─────────────┘
```

---

## Stage 0 — Intake

Before classifying, run the `../grill-me-doctrine.md` intake interview — gates entry into
the pipeline by ensuring the skill's purpose, trigger language, and success criteria are
understood before any drafting begins — one question at a time, always recommending an
answer, and exploring existing skills and code instead of asking when the answer is
discoverable. If the doctrine file is absent (standalone install), run a brief inline
intake interview covering purpose, trigger language, and success criteria instead.

Classify the user's request into one of four entry modes:

| Mode | Entry condition | Starts at |
|------|----------------|-----------|
| **Full pipeline** | "Create a skill", "make a skill", "take this to 100" | Stage 1 |
| **Review-only** | "Review this skill", "score my skill", "audit this" | Stage 2 (skip 1) |
| **Improve-only** | "Fix these findings", "improve this skill" | Stage 3 (skip 1-2) |
| **Optimize-only** | "Optimize the description", "fix triggering" | Stage 4 (skip 1-3) |

For **full pipeline** and **improve-only**, confirm the user's intent and constraints
before proceeding. For **review-only**, just need the skill path. For
**optimize-only**, need the skill path and optionally existing eval queries.

If the user provides an existing skill path, verify the directory exists and contains
a SKILL.md before proceeding.

---

## Stage 1 — Create

Delegate to **skill-creator** in Create mode.

**Handoff includes:**
- User intent and constraints from intake
- Entry mode (new skill vs. harden existing)
- Path to existing skill (if hardening)
- Any example files or context the user provided

**Expected return:**
- Draft SKILL.md with frontmatter
- Supporting files (references/, scripts/, agents/, examples/ as needed)
- Behavioral eval results (if Track A evals were run)
- Skill directory path

**On return:** Verify the skill directory exists and SKILL.md is present. If
skill-creator reports blockers, surface them to the user and re-delegate with
clarifications. Proceed to Stage 2.

---

## Stage 2 — Review

Delegate to **skill-reviewer**.

**Handoff includes:**
- Skill directory path
- Iteration number (1 for first review, N+1 for subsequent)
- Previous scorecard (if iteration > 1, for delta tracking)
- Behavioral eval results (if available from Stage 1 or Stage 3)

**Expected return:**
- Scorecard (10 dimensions, each scored with evidence)
- Findings list (F-01, F-02, ... with severity, location, fix instructions)
- Verdict: SHIP (100/100) | ITERATE (< 100) | BLOCKED (critical findings)
- Iteration history (if iteration > 1)

**On return:**
- If **SHIP** → proceed to Stage 4 (Optimize)
- If **ITERATE** → proceed to Stage 3 (Improve)
- If **BLOCKED** → surface critical findings to user, get guidance, then either
  proceed to Stage 3 or abort

Present the scorecard and key findings to the user between stages. The user should
see progress at every iteration boundary.

---

## Stage 3 — Improve

Delegate to **skill-creator** in Improve mode.

**Handoff includes:**
- Skill directory path
- Full findings list from reviewer (prioritized: critical → major → minor)
- Current scorecard with scores per dimension
- Iteration number
- Any user guidance or overrides ("skip finding F-04", "prioritize security")

**Expected return:**
- Updated skill files
- Summary of changes made (which findings addressed, which deferred)
- Updated behavioral eval results (if re-run)

**On return:** Proceed to Stage 2 (Review) for the next scoring pass.

---

## Stage 4 — Optimize

Delegate to **skill-creator** in Optimize mode.

**Handoff includes:**
- Skill directory path
- Current description (confirmed at 100/100 by reviewer)
- Existing eval queries (if any from previous stages)

**Expected return:**
- Optimized description
- Trigger eval results (before/after accuracy)
- `best_description` selected by test-set score

**On return:** If the optimized description differs materially from the reviewed one,
optionally run a quick re-review (Stage 2) to confirm the score holds. Otherwise
proceed to Stage 5.

---

## Stage 5 — Package & Deliver

Delegate to **skill-creator** in Package mode.

**Handoff includes:**
- Skill directory path

**Expected return:**
- `.skill` file path
- Package contents summary

**Final delivery to user:**
Compile the delivery report using `references/delivery-template.md` and present it
with the packaged skill. Include the full iteration history, final scorecard, and
changes summary.

---

## Quality gate management

### Review-improve loop rules

| Rule | Value |
|------|-------|
| Max review-improve cycles | 5 |
| Plateau detection | If score unchanged for 2 consecutive iterations, escalate |
| Plateau escalation | Present findings to user with: "Score plateaued at X/100. The remaining findings may need your input. Options: (a) override and ship, (b) provide guidance on specific findings, (c) abort." |
| Critical finding policy | Any finding with severity "critical" blocks shipping. User can override with explicit acknowledgment. |
| Score threshold for optimization | 100/100 (description optimization only runs after perfect score) |

### What the orchestrator never does

- **Never modifies skill files directly** — route all changes through skill-creator.
- **Never scores rubric dimensions** — route all scoring through skill-reviewer.
- **Never overrides a reviewer verdict.** If the reviewer says ITERATE, the
  orchestrator iterates — unless the user explicitly overrides.
- **Never invents findings.** Passes reviewer output to creator verbatim.

### User visibility

Present to the user at every stage boundary:
- Current score and delta from previous iteration
- Key findings (critical and major only for brevity)
- What happens next and estimated remaining stages
- Option to override, skip stages, or abort

---

## Adaptive behavior

### Partial pipeline support

Users can enter at any stage and exit early:

- "Just create, don't review" → Run Stage 0-1, skip 2-5
- "Just review" → Run Stage 0 + 2, skip 1/3/4/5
- "Review and improve but don't package" → Run Stage 0 + 2-3 loop, skip 4-5
- "Skip description optimization" → Run Stage 0-3 loop + 5, skip 4

Honor explicit user requests to skip stages. If the user says "ship it" during the
review loop, present the current score and confirm before skipping remaining
iterations.

### Handling user feedback mid-loop

The user may provide feedback at any stage boundary:
- **Redirect:** "Actually, the skill should also handle X" → add to constraints,
  re-delegate to creator in Improve mode with the new requirement
- **Override:** "F-04 is not a real issue, skip it" → note the override, exclude from
  future improve handoffs, tell reviewer to not re-flag
- **Abort:** "Stop, this isn't working" → present current state, offer to save
  progress, clean exit

### Error recovery

| Error | Response |
|-------|----------|
| Specialist returns incomplete output | Re-delegate with explicit note about what is missing |
| Specialist cannot access skill files | Verify path, ask user to confirm location |
| Review score regresses (lower than previous) | Flag regression to user, include both scorecards, ask whether to continue or revert |
| Max iterations reached without 100/100 | Present final state, offer: (a) ship at current score, (b) continue manually, (c) start over |
| User provides conflicting instructions | Surface the conflict, ask for clarification, do not guess |

---

## Team Creation Protocol

When the request is to create a coordinated *team* of skills (e.g. "create a team of
skills", "build me a pipeline of skills") rather than a single skill:

1. Capture the team purpose, pipeline stages, specialist roles, and interaction patterns.
2. Generate the orchestrator skill first — it defines the delegation surface and stage model.
3. Generate each specialist skill with inputs/outputs shaped for the orchestrator's handoff contracts.
4. Generate the gatekeeper skill with verdict vocabulary and evidence standards matching the orchestrator's boundary rules.
5. Run each generated skill through the standard review-improve loop (Stages 2-3).
6. Package all skills as a coordinated team with a team manifest describing relationships.

---

## Admiral Integration

When invoked by Admiral (or another parent orchestrator) as a utility orchestrator:

- Admiral provides the skill intent or team description as input.
- Skill-maker runs its full pipeline autonomously and returns the delivery package.
- Verdict mapping for Admiral's handoff protocol: `SHIP` → `APPROVED`, `ITERATE` →
  `REVISE`, `BLOCKED` → `ESCALATE`.
- Admiral's `gatekeeper-admiral` validates the skill-maker output at the cross-pipeline
  boundary.
- Maximum revision cycles when called by Admiral: **2** (per Admiral's standard handoff
  rules), distinct from the internal max of 5 review-improve cycles.

---

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with
`Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path
   specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`,
   `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's
   responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and
deliver output inline as usual.

---

## Reference files

| File | Purpose | When to read |
|------|---------|-------------|
| `../grill-me-doctrine.md` | Binding intake interview protocol | At Stage 0, before classifying the request |
| `references/workflow-protocol.md` | State machine, transitions, resume protocol | Before starting any pipeline run |
| `references/handoff-templates.md` | Delegation templates for all 5 handoff types | Before each delegation |
| `references/delivery-template.md` | Final delivery report format | At Stage 5 |
| `references/skill-guide.md` | Canonical skill authoring guide (shared) | When user asks about skill structure |
| `intake-brief.yaml` | Trigger set, inputs, outputs, and acceptance contract | Confirming the pipeline's intake surface |
| `stub-contract.md` | Stage model, handoff rules, quality and delivery contract | Confirming stage boundaries and verdict vocabulary |
| `agent/agent-manifest.yaml` | Agent-mode delegation capabilities and fallback behavior | When invoked as a sub-orchestrator (e.g. by Admiral) |
| `skill-creator/SKILL.md` | Creation specialist capabilities and modes | Understanding what creator can do |
| `skill-reviewer/SKILL.md` | Review specialist capabilities and phases | Understanding what reviewer reports |

## Bundled Support Surface

The `skill-creator/` subtree is intentionally bundled with skill-maker because the
orchestrator delegates every substantive create, improve, optimize, eval, and package
operation there.

| Path | Purpose | Owner |
|------|---------|-------|
| `skill-creator/agents/grader.md` | Grades assertion results against skill outputs. | skill-creator eval mode |
| `skill-creator/agents/comparator.md` | Runs blind A/B comparisons for current vs. baseline outputs. | skill-creator eval mode |
| `skill-creator/agents/analyzer.md` | Explains why one output beat another and proposes improvement themes. | skill-creator improve mode |
| `skill-creator/assets/eval_review.html` | Static query-review template for trigger eval approval. | skill-creator optimize mode |
| `skill-creator/eval-viewer/` | Generates and serves reviewable eval-result reports. | skill-creator eval mode |
| `skill-creator/scripts/` | Validation, eval, benchmark aggregation, description optimization, reporting, and packaging utilities. | skill-creator modes |

Treat generated eval workspaces, packaged archives, benchmark outputs, and review
reports as run artifacts. Keep them outside this skill directory unless a script
explicitly writes a temporary file that is excluded from packaging.
