---
name: skill-creator
description: >
  Drafts and improves Claude skills for the skill-maker pipeline. Use when skill-maker
  delegates create, improve, eval, optimize, or package work, or when the user asks to
  write a skill, fix reviewer findings, run behavioral evals, optimize the description,
  or package a skill directory — even if they only say "make this a skill" or "fix these
  findings". Handles SKILL.md authoring, supporting files, real evals, trigger tuning,
  and `.skill` packaging; leaves rubric scoring to skill-reviewer.
---

# Skill Creator

Draft new Claude skills, apply improvement fixes, run behavioral evals, optimize
descriptions, and package the result. Operates in five modes — the skill-maker
orchestrator selects the appropriate mode, or invoke standalone for any individual
phase.

> "Capture the user's intent, turn it into a production-quality skill, and keep
> iterating until it works on real tasks. Leave structural scoring to the reviewer —
> focus on making the skill *do the right thing*."

## Modes

| Mode | When invoked | Input | Output |
|------|-------------|-------|--------|
| **Create** | New skill from scratch | User intent + constraints | Draft skill package (SKILL.md + supporting files) |
| **Improve** | Reviewer returned findings | Skill path + findings list | Improved skill package |
| **Eval** | Run behavioral tests | Skill path + eval queries | Eval results + user feedback |
| **Optimize** | Tune description triggering | Skill path + eval queries | Optimized description |
| **Package** | Ship the final skill | Skill path | `.skill` file |

---

## Phase 1 — Capture Intent (Create mode)

Extract as much as possible from conversation history before asking questions.
Ask, roughly in this order:

1. What should this skill enable Claude to do?
2. When should it trigger? (user phrasings, contexts)
3. What is the expected output format?
4. Are real test cases needed? Skills with objectively verifiable outputs benefit
   from them. Skills with subjective outputs (writing style, art) often do not.
   Suggest a default and let the user decide.
5. Is this a new skill or are we hardening an existing one? If existing, get the path.

Probe edge cases, input/output formats, example files, success criteria, and
dependencies proactively. Research in parallel via subagents when available — check
for similar skills, consult docs, look up best practices — so the interview starts
with context rather than cold.

---

## Phase 2 — Draft (Create mode)

Write the skill following the authoring guide in `../references/skill-guide.md`.
Key constraints:

**Frontmatter:**

| Field | Constraint |
|-------|-----------|
| `name` | ≤ 64 chars, `[a-z0-9-]` only, matches directory name, no reserved words |
| `description` | ≤ 1024 chars, third-person declarative, states what AND when, lean pushy |

**Body:** Under 500 lines, imperative voice, forward slashes only.

**Progressive disclosure:** SKILL.md is the table of contents — workflow and decisions.
Move deep reference material (>100 words of tables, API specs, pattern catalogues) to
`references/`. Reusable scripts to `scripts/`. Examples over 20 lines to `examples/`.
Reference files over 100 lines need a TOC. All references one level deep — no nesting.

**Description craft — the pushy pattern:**

> Weak: "Build dashboards from internal data."
>
> Strong: "Build dashboards from internal data. Use this skill whenever the user
> mentions dashboards, data visualization, internal metrics, or wants to display any
> kind of company data — even if they don't explicitly say 'dashboard'."

**Safety:** No malware, exploit code, or content that compromises security. Skill
behavior must not surprise the user given its description.

For detailed patterns — section order, degrees of freedom, workflow patterns, common
mistakes, pre-ship checklist — read `references/authoring-patterns.md`.

---

## Phase 3 — Behavioral Eval (Eval mode)

Run real test cases to catch behavioral problems the rubric cannot see ("the output
chart is ugly", "it missed the deadline column"). Full workflow details in
`references/real-evals.md`.

### Essentials

1. Write 2–3 realistic test prompts that a real user would say. Save to
   `evals/evals.json` (schema in `references/schemas.md`).
2. For each test, spawn two subagents in the same turn: one *with* the skill, one
   baseline (no skill for new skills; old snapshot for hardening existing ones).
3. While runs happen, draft assertions and explain them to the user.
4. Capture timing data from task notifications as they arrive.
5. Grade via subagent or inline, aggregate with `scripts/aggregate_benchmark.py`, and
   launch the eval-viewer so the user can review outputs and leave feedback.
6. Read `feedback.json` when the user says they are done.

### Metrics to capture

- SKILL.md body word count (excluding frontmatter)
- Total reference word count
- File tree depth and count
- Broken internal references (body mentions a file that does not exist)
- Orphaned files (exist but nothing references them)

These metrics feed the reviewer's rubric dimensions and surface problems invisible
when reading prose alone.

---

## Phase 4 — Apply Fixes (Improve mode)

Receive findings from the reviewer (or user feedback) and apply them in priority
order: **critical → major → minor**. Any security issue is automatically critical.

### Fix categories

| Category | Typical fixes |
|----------|---------------|
| Description | Add missing trigger phrasings, lean pushier, fix person/voice, trim bloat |
| Body content | Replace vague instructions with concrete ones, add *why*, remove duplication |
| Progressive disclosure | Move >100-word reference material to `references/`, add TOCs, extract long examples and reusable scripts |
| Supporting files | Delete orphans, create missing referenced files, add error handling to scripts |
| Security | Add input validation, safe defaults, document failure modes |
| Edge cases | Add sections for unexpected inputs where findings identified gaps |

### How to think about improvements

**Generalize from feedback.** Skills run thousands of times across prompts never seen.
Iterating on 2–3 examples is fast, but if the skill works *only* for those examples it
is useless. Try different patterns rather than overfit-y MUSTs patching a specific case.

**Keep the prompt lean.** Remove things not pulling their weight. Read subagent
transcripts — if the skill makes the model waste time on unproductive steps, cut them.

**Explain the why.** Today's LLMs have good theory of mind. If feedback is terse,
work to understand the actual desire and transmit that understanding as reasoning.
All-caps MUST/NEVER is a yellow flag — reframe and explain.

**Look for repeated work.** If all subagents independently wrote similar helper scripts,
that is a signal the skill should bundle the script in `scripts/`.

**Return the improved skill to the orchestrator** — do not self-score. The reviewer
handles the next benchmark pass.

---

## Phase 5 — Description Optimization (Optimize mode)

After the main improvement loop settles, optimize the description for trigger
accuracy. Full guidance in `references/description-opt.md`.

Three-step summary:

1. **Generate ~20 trigger eval queries** — mix of should-trigger and should-not-trigger.
   Near-miss negatives are most valuable. Save as JSON array of
   `{query, should_trigger}` objects.
2. **Review with the user** — render `assets/eval_review.html` with placeholders, open
   it, let the user edit and export `eval_set.json`.
3. **Run the optimization loop:**
   ```bash
   python -m scripts.run_loop \
     --eval-set <path-to-trigger-eval.json> \
     --skill-path <path-to-skill> \
     --model <model-id> \
     --max-iterations 5 \
     --verbose
   ```
   The script splits 60/40 train/test, evaluates (3 runs per query), proposes
   improvements, re-evaluates, loops up to 5 times. Selects `best_description` by
   *test* score to avoid overfitting.

Apply `best_description` to SKILL.md frontmatter. Show before/after and report scores.

### Triggering caveat

Claude only consults skills for tasks it cannot easily handle on its own — simple
one-step queries may not trigger even with a perfect description. Eval queries should
be substantive enough that Claude would actually benefit from consulting a skill.

---

## Phase 6 — Package (Package mode)

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

This creates a `.skill` ZIP file excluding `evals/`, `__pycache__`, `.pyc`,
`.DS_Store`. Point the user to the resulting file path.

When updating an existing skill:
- Preserve the original name — use the same directory name and `name` frontmatter
- Copy to a writeable location before editing if the installed path is read-only
- Stage in `/tmp/` first if packaging manually, then copy to output directory

## Script and Path Safety

Before running bundled scripts, validate that every user-supplied path resolves inside
the intended skill directory, eval workspace, or explicit output directory. Refuse paths
that escape through `..`, symlinks, absolute paths outside the working boundary, or
ambiguous drive roots. Pass arguments as structured argv values; do not compose shell
commands from user text. Keep secrets, API keys, auth cookies, and private eval outputs
out of packaged `.skill` archives and generated reports.

---

## Environment-specific guidance

The core workflow is identical everywhere. What differs is tool availability.

### Claude Code (richest environment)

- **Subagents available** — Phase 3 evals work fully in parallel
- Use `Read`, `Grep`, `Glob` to explore; `Write` / `Edit` to apply fixes
- Eval-viewer runs as local server (browser opens automatically)
- Description optimizer (`run_loop.py` via `claude -p`) works natively
- Blind comparison available (`agents/comparator.md`, `agents/analyzer.md`)

### Cowork

- **Subagents available** — Phase 3 works in parallel; fall back to serial on timeouts
- No browser — use `--static <output_path>` for eval viewer to write standalone HTML
- Generate eval viewer with `eval-viewer/generate_review.py` *before* self-evaluating —
  get examples in front of the human ASAP
- Feedback arrives as downloaded `feedback.json`
- Description optimizer works fine (uses `claude -p` subprocess)

### Claude.ai

- **No subagents** — for each test case, read the skill yourself and follow its
  instructions. One at a time. Less rigorous, but human review compensates. Skip
  baseline runs
- **No browser** — present results inline (prompt + output). Save files and tell the
  user the path for download. Invite feedback on the output before proceeding.
- **Skip quantitative benchmarking** — relies on baselines unavailable without subagents
- **Skip description optimizer** — requires `claude -p` CLI
- **Packaging still works** — `package_skill.py` only needs Python and filesystem

---

## Reference files

- **`../references/skill-guide.md`** — canonical authoring guide: hard constraints,
  anatomy, progressive disclosure, frontmatter rules, body writing, bundled resources.
  Read when drafting a new skill or diagnosing structural issues.
- **`references/authoring-patterns.md`** — workflow patterns (checklist, feedback-loop,
  template, conditional), common mistakes, pre-ship validation checklist. Read when
  applying fixes or auditing draft structure.
- **`references/real-evals.md`** — Track A workflow: writing test cases, workspace layout,
  spawning runs, assertions, grading, viewer launch, iteration mechanics. Read before
  running evals.
- **`references/description-opt.md`** — description optimization loop mechanics: query
  generation, train/test split, overfitting prevention. Read before Phase 5.
- **`references/schemas.md`** — JSON schemas for `evals.json`, `eval_metadata.json`,
  `grading.json`, `benchmark.json`, `feedback.json`.
- **`agents/grader.md`** — how to evaluate assertions against outputs.
- **`agents/comparator.md`** — blind A/B comparison between two outputs.
- **`agents/analyzer.md`** — analyze why one version beat another.
- **`assets/eval_review.html`** — static trigger-eval review UI. Use during
  Optimize mode before running the description optimizer.
- **`eval-viewer/generate_review.py`** and **`eval-viewer/viewer.html`** — render
  human-reviewable eval outputs. Use during Eval mode when browser/static review is
  available.
- **`scripts/`** — bundled automation for validation, eval execution, aggregation,
  description optimization, report generation, and packaging. Read the target script's
  top-level docstring before running it.