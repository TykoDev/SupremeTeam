---
name: skill-reviewer
description: >
  Adversarial quality gate for Claude skills. Scores a skill 0-100 across 10 rubric
  dimensions, runs a structural and specification audit, and produces a findings report
  with a prioritized fix list. Use when the skill-maker orchestrator delegates a review
  task. Also usable standalone to audit any SKILL.md — invoke when the user says
  "review my skill", "score this skill", "audit my skill", "is this skill
  production-ready", "rate my SKILL.md", or "check skill quality". Even trigger on
  "how does this look" after working on a SKILL.md. Does NOT apply fixes — returns
  findings to the orchestrator (or user) for the creator to act on.
version: 1.0.0
---

# Skill Reviewer

Score a Claude skill against the 10-dimension rubric, run structural and specification
audits, and produce a findings report with actionable fix instructions. Approval is
earned through evidence — not granted by default.

> "Professional skepticism. A skill ships at 100/100 because every dimension is
> demonstrably covered, not because it *looks* okay."

**Source of truth:** `references/scoring-rubric.md` — the 10-dimension × 10-point
rubric. All scores, deductions, and evidence requirements come from that document.
Read it in full before scoring.

**Worked examples:** `references/examples.md` — a sample finding in the F-[NN]
format and an abridged scorecard, for output-shape calibration.

---

## Phase 1 — Benchmark

Locate the skill, ingest it, measure raw metrics, score every dimension, and produce
the scorecard.

### 1.1 Locate and ingest

1. Get the skill path — from the orchestrator handoff, user message, or conversation
   context. **Before reading anything else**, validate the path: confirm it resolves to
   a real directory that is within the working area (no path traversal outside the
   project root), and that a readable `SKILL.md` exists inside it. If the path escapes
   the working area, does not exist, or `SKILL.md` is absent, stop immediately and ask
   the user to confirm the correct location — do not read arbitrary paths or proceed on
   a guess.
2. Read SKILL.md in full. If SKILL.md exists but is **empty or has malformed / absent
   YAML frontmatter** (missing opening `---`, missing `name` or `description` fields,
   or unparseable YAML), record this as a blocking documentation finding (D10 = low)
   before continuing. Score every dimension that can be assessed from the body alone;
   set D1 and D10 to their rubric floor and note that frontmatter issues must be fixed
   before the skill can ship.
3. Read every file in `references/`, `scripts/`, `agents/`, `examples/`, `assets/`,
   `eval-viewer/`. Build a mental model of the complete package before scoring anything.
4. If files are missing or unreadable, note this — it will affect multiple dimensions.

### 1.2 Measure raw metrics

Collect these numbers before scoring:

| Metric | How to measure |
|--------|---------------|
| SKILL.md body word count (excl. frontmatter) | Count words after the closing `---` |
| `name` character count | Length of `name` field |
| `description` character count | Length of `description` field |
| Total reference file word count | Sum of all files outside SKILL.md |
| File tree depth and count | Max folder depth, total file count |
| Broken internal references | Body mentions a file that does not exist |
| Orphaned files | Files that exist but nothing points to them |
| Second-person pronoun count | Occurrences of "you", "your", "you're" in body |
| Voice violations | Lines using passive or second-person instead of imperative |

### 1.3 Score all 10 dimensions

Read `references/scoring-rubric.md` and score each dimension independently:

1. **Trigger description** (10 pts) — Does the description reliably trigger on relevant
   user requests and correctly avoid adjacent domains?
2. **Scope & intent alignment** (10 pts) — Does the body deliver exactly what the
   description promises?
3. **Content depth** (10 pts) — Is the content substantive and actionable, with
   appropriate detail for the domain?
4. **Writing style** (10 pts) — Imperative voice, concise, no second-person drift,
   no filler?
5. **Progressive disclosure** (10 pts) — SKILL.md is a workflow/TOC; heavy content
   lives in references?
6. **Examples & references** (10 pts) — Real-world examples, well-structured supporting
   files, no orphans?
7. **Edge-case coverage** (10 pts) — Failure modes, unexpected inputs, boundary
   conditions addressed?
8. **Security & robustness** (10 pts) — No dangerous patterns, safe defaults, input
   validation where needed?
9. **Structure & readability** (10 pts) — Scannable headers, consistent formatting,
   logical flow?
10. **Documentation & metadata** (10 pts) — Frontmatter valid, all constraints met,
    install/usage clear?

For each dimension:
- Start at 10/10.
- Apply deductions per the rubric's deduction ladder. Each deduction must cite
  specific evidence (line number, file name, quote).
- Record the final score and the list of deductions with evidence.

### 1.4 Produce scorecard

```markdown
## Scorecard — [skill-name] — Iteration [N]

| # | Dimension | Score | Deductions |
|---|-----------|-------|------------|
| 1 | Trigger description | X/10 | ... |
| 2 | Scope & intent alignment | X/10 | ... |
| 3 | Content depth | X/10 | ... |
| 4 | Writing style | X/10 | ... |
| 5 | Progressive disclosure | X/10 | ... |
| 6 | Examples & references | X/10 | ... |
| 7 | Edge-case coverage | X/10 | ... |
| 8 | Security & robustness | X/10 | ... |
| 9 | Structure & readability | X/10 | ... |
| 10 | Documentation & metadata | X/10 | ... |
| | **Total** | **XX/100** | |

Raw metrics: body words: X | desc chars: X | name chars: X | ref words: X |
files: X | depth: X | broken refs: X | orphans: X | voice violations: X
```

---

## Phase 2 — Audit

Two parallel lenses. Every finding uses the standard finding format.

### 2.1 Skill-architecture lens

Audit from the perspective of "is this a well-constructed skill?":

- **Trigger audit** — Would this description reliably fire for the right prompts?
  Test mentally against 5 realistic queries and 3 near-miss queries that should NOT
  trigger. Flag trigger phrases that are too generic (would match unrelated skills) or
  too narrow (misses obvious phrasings).
- **Content audit** — Does the body contain actionable instructions, or is it a wall of
  context Claude already knows? Flag paragraphs that teach Claude things it can already
  do. Flag missing instructions for things the description claims.
- **Progressive disclosure audit** — Is SKILL.md under 500 lines? Are reference files
  used properly? Flag reference material inlined in the body (>100 words of tables,
  API specs, pattern catalogues). Flag references over 100 lines without a TOC.
- **Supporting files audit** — Are all referenced files present? Are there orphaned
  files? Do scripts have docstrings and error handling? Is execution vs. read intent
  clear?

### 2.2 Specification-review lens

Audit from the perspective of "does this skill specification produce correct behavior?":

- **Scope audit** — Could the instructions produce output outside the declared scope?
  Flag instructions that are ambiguous enough to cause scope creep.
- **Correctness audit** — Are factual claims accurate? Are code patterns correct? Flag
  anything that would produce wrong output if followed literally.
- **Security audit** — Any command injection vectors? Unsafe file operations? Secrets
  in prompts? Dangerous defaults? Flag using the rubric's security dimension criteria.
- **Testability audit** — Could someone write a deterministic test for the core
  workflow? Flag vague output expectations that prevent verification.

### 2.3 Finding format

Every finding follows this structure:

```markdown
### F-[NN]: [Short title]

- **Dimension:** [1-10 name from rubric]
- **Severity:** critical | major | minor
- **Location:** [file path, line number or section]
- **Issue:** [What is wrong — specific, evidence-based]
- **Fix:** [Concrete instruction — what to change, where, how]
- **Impact:** [Which rubric score improves and by how much]
```

Severity rules:
- **Critical** — Security vulnerability, skill fundamentally broken, description never
  triggers, or body contradicts description. Must fix before shipping.
- **Major** — Significant quality gap: missing edge cases, orphaned files, poor
  progressive disclosure, voice violations in >10% of lines. Should fix.
- **Minor** — Polish issues: inconsistent formatting, slightly verbose section, one
  missing trigger phrase. Nice to fix.

---

## Phase 3 — Present

Compile the final review report with everything the orchestrator (or user) needs to
decide whether to ship or iterate.

### Report structure

```markdown
# Review Report — [skill-name] — Iteration [N]

## Scorecard
[Full scorecard from Phase 1]

## Summary
- **Total score:** XX/100
- **Verdict:** SHIP (100/100) | ITERATE (< 100) | BLOCKED (critical findings)
- **Critical findings:** [count]
- **Major findings:** [count]
- **Minor findings:** [count]

## Findings (prioritized)
[All findings from Phase 2, ordered: critical → major → minor]

## Behavioral eval status
[If eval results were provided as input, summarize pass/fail. If not provided, note
"No behavioral eval results available for this iteration."]

## Recommendations
[For ITERATE verdict: top 3 highest-impact fixes that would move the score most.
For BLOCKED verdict: the critical issues that must be resolved first.]
```

### Iteration history (when reviewing after improvements)

If this is not the first review, prepend an iteration history:

```markdown
## Iteration history

| Iter | Score | Delta | Key changes |
|------|-------|-------|-------------|
| 1 | 62/100 | — | Initial draft |
| 2 | 78/100 | +16 | Fixed description, added edge cases |
| 3 | 91/100 | +13 | Extracted references, fixed voice |
| 4 | 100/100 | +9 | Fixed orphans, added security section |
```

### Calibration warnings

Guard against these scoring errors (detailed in `references/scoring-rubric.md`):

- **Halo effect** — good description doesn't mean good content. Score independently.
- **Severity inflation** — don't score minor polish issues as major deductions.
- **Context bleed** — score what's written, not what the author intended but didn't write.
- **Anchoring** — don't let a strong first dimension bias later scores upward.
- **Perfectionism** — don't deduct for absence of things the rubric doesn't require.
- **Leniency** — don't round up because the skill is "pretty close". Evidence required.

---

## Environment-specific notes

### Claude Code / Cowork

- Use `Read`, `Grep`, `Glob` to explore skill files systematically
- Measure metrics programmatically where possible (word counts, file existence checks)
- Write the review report to a file and tell the user the path

### Claude.ai

- Ask the user to paste the skill content or provide the file
- Present the review report inline
- Be explicit about which files are needed — the user may need to paste them
  one at a time

---

## What this skill does NOT do

- **Does not apply fixes.** Returns findings and recommendations. The orchestrator
  delegates improvement to skill-creator.
- **Does not run behavioral evals.** That is skill-creator's Phase 3. If eval results
  are provided as input, the reviewer incorporates them into the report.
- **Does not write skills.** Reads, scores, audits. Never modifies the skill under
  review.
