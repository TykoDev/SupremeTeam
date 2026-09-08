# Workflow Protocol — Skill Maker Pipeline

State machine, transition rules, track management, and resume protocol for the
skill-maker orchestrator.

## Contents

1. State machine
2. State definitions
3. Transition rules
4. Track management
5. Iteration tracking
6. Resume protocol
7. Partial pipeline handling

---

## State machine

```
INTAKE
  │
  ├─ full pipeline ──→ CREATE_ACTIVE
  ├─ review-only ────→ REVIEW_ACTIVE
  ├─ improve-only ───→ IMPROVE_ACTIVE
  └─ optimize-only ──→ OPTIMIZE_ACTIVE

CREATE_ACTIVE ──→ CREATE_COMPLETE ──→ REVIEW_ACTIVE

REVIEW_ACTIVE ──→ REVIEW_COMPLETE
                    │
                    ├─ verdict: SHIP ──→ OPTIMIZE_ACTIVE
                    ├─ verdict: ITERATE ──→ IMPROVE_ACTIVE
                    └─ verdict: BLOCKED ──→ USER_DECISION
                                             ├─ continue ──→ IMPROVE_ACTIVE
                                             └─ abort ──→ ABORTED

IMPROVE_ACTIVE ──→ IMPROVE_COMPLETE ──→ REVIEW_ACTIVE
                                        (iteration N+1)

OPTIMIZE_ACTIVE ──→ OPTIMIZE_COMPLETE
                       ├─ files changed ──→ REVIEW_ACTIVE ──SHIP──→ PACKAGE_ACTIVE
                       └─ unchanged, matching review ──→ PACKAGE_ACTIVE

PACKAGE_ACTIVE ──→ DELIVERED

USER_DECISION: orchestrator pauses, presents state, waits for user input.
ABORTED: clean exit, present current state summary.
```

---

## State definitions

| State | Owner | Description |
|-------|-------|-------------|
| `INTAKE` | orchestrator | Classifying mode, gathering context |
| `CREATE_ACTIVE` | skill-creator | Drafting skill from intent |
| `CREATE_COMPLETE` | orchestrator | Draft received, preparing review handoff |
| `REVIEW_ACTIVE` | skill-reviewer | Scoring and auditing skill |
| `REVIEW_COMPLETE` | orchestrator | Scorecard received, deciding next step |
| `IMPROVE_ACTIVE` | skill-creator | Applying reviewer findings |
| `IMPROVE_COMPLETE` | orchestrator | Improved skill received, preparing re-review |
| `OPTIMIZE_ACTIVE` | skill-creator | Running description optimization |
| `OPTIMIZE_COMPLETE` | orchestrator | Optimized description applied |
| `PACKAGE_ACTIVE` | skill-creator | Building .skill package |
| `DELIVERED` | orchestrator | Pipeline complete, delivery report presented |
| `USER_DECISION` | user | Waiting for user input on blocked/plateaued state |
| `ABORTED` | orchestrator | Pipeline terminated by user |

---

## Transition rules

### CREATE_COMPLETE → REVIEW_ACTIVE

**Required artifacts:**
- SKILL.md exists at the skill path with valid frontmatter
- At least the SKILL.md body is non-empty
- Supporting files referenced in SKILL.md exist

**Orchestrator action:** Bundle skill path + iteration number (1) + any eval results
into the review handoff template. Transition to REVIEW_ACTIVE.

### REVIEW_COMPLETE → next state

**Decision logic:**

```
if score == 100 and no critical findings:
    → PACKAGE_ACTIVE if optimization already completed, otherwise OPTIMIZE_ACTIVE
elif iteration_count >= max_iterations (5):
    → USER_DECISION (max iterations reached)
elif score == previous_score for 2 consecutive iterations:
    → USER_DECISION (plateau detected)
elif critical findings exist:
    → USER_DECISION (blocked) or IMPROVE_ACTIVE (user's call)
else:
    → IMPROVE_ACTIVE
```

### IMPROVE_COMPLETE → REVIEW_ACTIVE

**Required artifacts:**
- Updated skill files
- Changes summary from creator

**Orchestrator action:** Increment iteration counter. Bundle skill path +
iteration number + previous scorecard + eval results. Transition to REVIEW_ACTIVE.

### OPTIMIZE_COMPLETE → PACKAGE_ACTIVE

**Required artifacts:**
- `best_description` from optimizer
- Trigger eval scores (before/after)

**Required re-review:** Any changed description invalidates the review of the
previous files. Return to Stage 2 for the revised files; after SHIP, proceed to
packaging without repeating optimization. Resolve review findings through the
normal improve/review loop. If no files changed, retain the matching review.

### PACKAGE_ACTIVE → DELIVERED

**Required artifacts:**
- `.skill` file created
- Package contents verified

---

## Track management

Two evaluation tracks run at different points in the pipeline:

| Track | Owner | When | Purpose |
|-------|-------|------|---------|
| **Track A** (behavioral evals) | skill-creator | During CREATE and IMPROVE | Real test cases via subagents — catches functional problems |
| **Track B** (rubric scoring) | skill-reviewer | During REVIEW | 10-dimension adversarial scoring — catches structural problems |

The orchestrator does not manage track execution — each specialist runs their own
track. The orchestrator ensures both tracks are consulted:

- After CREATE: reviewer receives creator's eval results (if any)
- After REVIEW: creator receives reviewer's findings
- Eval results accumulate across iterations — later reviews have richer context

---

## Iteration tracking

The orchestrator maintains an iteration log:

```markdown
| Iter | State transition | Score | Delta | Key event |
|------|-----------------|-------|-------|-----------|
| 1 | CREATE → REVIEW | 62/100 | — | Initial draft |
| 2 | IMPROVE → REVIEW | 78/100 | +16 | Fixed description, edges |
| 3 | IMPROVE → REVIEW | 91/100 | +13 | Extracted refs, voice |
| 4 | IMPROVE → REVIEW | 100/100 | +9 | Fixed orphans, security |
| 5 | OPTIMIZE | 100/100 | 0 | Description optimized |
| 6 | PACKAGE | — | — | Delivered |
```

This log feeds the delivery template and gives the user a progress narrative.

---

## Resume protocol

If the conversation is interrupted mid-pipeline:

1. **Identify last completed state** — check which files exist, what the last
   scorecard shows, what iteration the log reflects.
2. **Validate lineage before resuming** — verify that the artifacts still match
   the reviewed revision and saved gate verdict. Re-run the earliest affected
   stage when files changed or evidence is missing; file existence alone does not
   prove completion. Otherwise resume from the next incomplete state.
3. **Re-read the skill** — always re-read SKILL.md and key reference files on resume
   to avoid stale context.

Resume entry points:

| Evidence found | Resume at |
|----------------|-----------|
| SKILL.md exists, no scorecard | REVIEW_ACTIVE (iteration 1) |
| Scorecard exists, score < 100 | IMPROVE_ACTIVE (iteration N+1) |
| Scorecard at 100, no `.skill` file | OPTIMIZE_ACTIVE |
| `.skill` file exists | Verify package contents, revision lineage, and the required Admiral boundary verdict; resume the earliest incomplete stage if any check fails. Only matching approved evidence permits delivery. |

---

## Partial pipeline handling

When the user requests a subset of stages:

| User intent | States executed | Skipped |
|-------------|----------------|---------|
| "Just create" | INTAKE → CREATE_ACTIVE → CREATE_COMPLETE | All review/improve |
| "Just review" | INTAKE → REVIEW_ACTIVE → REVIEW_COMPLETE | Create/improve/optimize/package |
| "Review and improve" | INTAKE → REVIEW → IMPROVE loop | Create/optimize/package |
| "Skip optimization" | Full pipeline minus OPTIMIZE | OPTIMIZE_ACTIVE/COMPLETE |
| "Create and review, stop there" | INTAKE → CREATE → REVIEW | Improve/optimize/package |

The orchestrator records which stages were skipped so the delivery report accurately
reflects what was done.
