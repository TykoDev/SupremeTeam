# Delivery Template — Skill Maker Pipeline

Use this template to compile the final delivery report at Stage 5 (Package & Deliver).
Fill in all sections; omit sections only if the corresponding stage was skipped.

## Contents

1. Executive summary
2. Iteration history
3. Final scorecard
4. Behavioral eval status
5. Description optimization
6. Changes summary
7. Files in package
8. Stages executed
9. Recommendations

---

```markdown
# Skill Delivery Report — [skill-name]

## Executive summary

**Skill:** [name]
**Pipeline mode:** [full | review-only | improve-only | optimize-only]
**Final score:** [XX/100]
**Iterations:** [N]
**Verdict:** [SHIPPED | SHIPPED_WITH_OVERRIDES | PARTIAL]

[1-2 sentence summary: what the skill does and the outcome of the pipeline run.]

---

## Iteration history

| Iter | Stage | Score | Delta | Key changes |
|------|-------|-------|-------|-------------|
| 1 | Create → Review | XX/100 | — | Initial draft |
| 2 | Improve → Review | XX/100 | +N | [brief changes] |
| ... | ... | ... | ... | ... |
| N | Optimize | XX/100 | 0 | Description optimized |
| N+1 | Package | — | — | .skill file created |

---

## Final scorecard

| # | Dimension | Score | Notes |
|---|-----------|-------|-------|
| 1 | Trigger description | X/10 | |
| 2 | Scope & intent alignment | X/10 | |
| 3 | Content depth | X/10 | |
| 4 | Writing style | X/10 | |
| 5 | Progressive disclosure | X/10 | |
| 6 | Examples & references | X/10 | |
| 7 | Edge-case coverage | X/10 | |
| 8 | Security & robustness | X/10 | |
| 9 | Structure & readability | X/10 | |
| 10 | Documentation & metadata | X/10 | |
| | **Total** | **XX/100** | |

---

## Behavioral eval status

[If Track A evals were run:]

| Test case | Result | Notes |
|-----------|--------|-------|
| [query 1] | pass/fail | [brief note] |
| [query 2] | pass/fail | [brief note] |
| ... | ... | ... |

[If no evals were run: "Behavioral evals were not run during this pipeline execution."]

---

## Description optimization

**Before:** [original description]
**After:** [optimized description]
**Trigger accuracy:** [before]% → [after]%

[If optimization was skipped: "Description optimization was skipped."]

---

## Changes summary

### By dimension

[Group all changes made across iterations by the rubric dimension they addressed:]

**Trigger description:**
- [change 1]
- [change 2]

**Content depth:**
- [change 1]

[...etc. for each dimension that had changes]

### User overrides

[List any reviewer findings the user chose to skip or override:]

| Finding | Reason |
|---------|--------|
| F-XX: [title] | User override: "[reason]" |

[If none: "No user overrides."]

---

## Files in package

| File | Purpose |
|------|---------|
| SKILL.md | Main skill definition |
| references/[name].md | [purpose] |
| scripts/[name].py | [purpose] |
| ... | ... |

**Package path:** [path to .skill file]

---

## Stages executed

- [x] Intake
- [x/skip] Create
- [x/skip] Review ([N] iterations)
- [x/skip] Improve ([N] cycles)
- [x/skip] Optimize
- [x/skip] Package

---

## Recommendations

[If the skill shipped at 100/100 with no caveats, this section can be brief:]

"Skill is production-ready. No outstanding issues."

[If shipped with overrides or at < 100:]

1. [Recommendation 1 — highest impact remaining improvement]
2. [Recommendation 2]
3. [Recommendation 3]
```
