---
name: skill-creator
description: >-
  Drafts and revises skill content for `skill-maker`, which owns the pipeline and
  delegates each mode: Create writes the SKILL.md and supporting files, Improve
  applies a reviewer's scorecard to fix reviewer findings, Eval runs behavioral evals
  against real queries, and Package produces the `.skill` bundle. Use when skill-maker
  delegates drafting, findings to apply, an eval run, or packaging. An internal
  specialist, never the front door: a cold "write me a skill" belongs to
  `skill-maker`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Skill Creator

## Purpose

Hold the only hands that touch skill files in this pipeline. Everything else in
the loop reads and judges; drafting, fixing, tuning, and packaging happen here,
under a mode the orchestrator selects, so a change always has one author and one
reason. The counterweight is that this skill never scores its own work — a
drafter grading its own draft is how a skill reaches 100 on paper and fails on a
real task.

For a cold lifecycle request, follow `../../routing-doctrine.md`: enter admiral,
then accept the skill-maker handoff. An active skill-maker delegation proceeds
directly without restarting intake.

> "Capture the user's intent, turn it into a production-quality skill, and keep
> iterating until it works on real tasks. Leave structural scoring to the reviewer —
> focus on making the skill *do the right thing*."

## Use This Skill When

`skill-maker` selects the mode; this is the only skill in the loop where a file actually changes:

- "skill-maker delegates drafting" — write the SKILL.md and its supporting files in Create mode
- "fix reviewer findings" / "fix these findings" — apply a scorecard's findings in Improve mode
- "run behavioral evals" — exercise the draft against real queries in Eval mode
- "skill-maker delegates packaging" — produce the `.skill` bundle in Package mode

Route elsewhere for the rubric score (`skill-maker/skill-reviewer`) and for the loop that decides which mode runs (`skill-maker`), which also owns description optimization as a stage rather than an edit.

## Entry Routing

Skill-creator is an internal specialist, not an entry point.
`../../routing-doctrine.md` names it in the internal-specialist row, reached
only through `skill-maker`, which owns every stage of the `skill-creation`
pipeline and calls this skill in Create, Improve, Optimize, and Package mode.
The mode is the load-bearing part: the same skill writes a first draft, applies
a reviewer's findings, or packages a finished directory, and only the handoff
says which.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `skill-maker` as the
delegating owner and states the mode.

Reached cold — "write me a skill" with no handoff — draft nothing. Without the
mode there is no way to tell a create from an improve, and without the intake
there is no trigger set, no acceptance contract, and no findings list to apply.
Route the user to `fabled`, which runs intake and hands the request to
`skill-maker`.

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
dependencies proactively. Research in parallel via subagents when available, so
the interview starts with context rather than cold. Three searches pay for
themselves: the skill catalog for a skill that already covers this scope (a
duplicate trigger set makes both skills unreliable), the target codebase for the
file types and command names the skill will have to name exactly, and
`../references/skill-guide.md` §1 for the constraints a draft must satisfy before
it is worth reviewing.

---

## Phase 2 — Draft (Create mode)

Write the skill against `../references/skill-guide.md`, which owns these constraints
canonically: the frontmatter limits and their exact character caps (§1.1–§1.2), the
body budget and file-structure rules (§1.3–§1.4), the three loading levels of progressive
disclosure (§3), and description craft including the pushy pattern (§4.2). Read §1 before
drafting — a draft that violates it is rejected by validation rather than reviewed.

Three of those shape the draft before its first line, and are the expensive ones to
discover late:

- **`name` matches the directory name**, lowercase and hyphenated. A mismatch means the
  skill never loads, and nothing downstream says why.
- **The description states what *and* when**, third-person declarative, leaning pushy. It
  is the only text seen before the decision to load the skill, and skills under-trigger far
  more often than they over-trigger.
- **SKILL.md is the table of contents, not the manual.** Deep material goes to
  `references/`, exactly one level deep and never nested — the layout cannot be rearranged
  later without rewriting every pointer into it.

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

Validate before packaging, so a skill that cannot load is never shipped. `quick_validate.py`
is the `skill-creation` pipeline's declared script (`../../pipelines.yaml`), and its output is
the `validation_report` evidence this skill owns at the `skill-maker-to-delivery` boundary
(`../../gates.yaml`). That key is artifact-backed: write the result to a file and hash it, because
a claim that validation passed is not evidence.

```bash
cd skills/skill-maker/skill-creator
python -m scripts.quick_validate <path/to/skill-folder>
```

On a failure, return the report to the orchestrator as a blocker rather than packaging; a
`.skill` built from an invalid source fails at the gate instead of at the desk.

```bash
python -m scripts.package_skill <path/to/skill-folder>
```

This writes the `.skill` ZIP to `<project>/.harness-state/packages/` by default (pass an output directory, normally the active run's `skill-creation/packages/`, to place it elsewhere), excluding `evals/`, `__pycache__`, `.pyc`,
`.DS_Store`. Point the user to the resulting file path.

When updating an existing skill:
- Preserve the original name — use the same directory name and `name` frontmatter
- Copy to a writeable location before editing if the installed path is read-only
- Stage under the project's `.harness-state/packages/` if packaging manually (never `/tmp/` or the project root), then copy into the active run's `skill-creation/packages/` directory

## Failure Modes

| Scenario | Response |
| --- | --- |
| `evals/evals.json` is missing, unparseable, or does not match the shape in `references/schemas.md` (no `evals` array, an entry without `prompt`, duplicate `id` values) | Do not repair it silently and do not grade a partial parse. Report the exact parse error or the first non-conforming entry, and either rewrite the file from the captured intent and show the user the result before running, or run with the subset that does parse while stating which entries were dropped and why. A grade computed over a silently shrunken eval set reads as a passing score. |
| The user supplies zero test cases, or declines to write any | Do not invent test cases and present their results as evidence. Skills with subjective outputs legitimately have none: record "no behavioral evals for this iteration", hand the reviewer the structural work alone, and say plainly that only Track B signal exists. Offer one concrete starter prompt drawn from the intake so the decision is informed rather than a default. |
| `run_loop.py` exits non-zero, times out, or returns no `best_description` | Keep the current description unchanged — a failed optimizer is not a signal to edit the trigger by hand, because the whole point of the loop is the held-out test score. Report the iteration it reached, the last scores, and the failure, then either re-run with a smaller `--max-iterations` or return Optimize as not-run so the orchestrator can skip Stage 4 deliberately. |
| The optimizer's `best_description` scores better on train than on test | Take the test-selected description and say so. A train-better candidate is the overfitting the split exists to catch; adopting it because the number is larger discards the only defence in the loop. |
| `quick_validate.py` returns a failure at Phase 6 | Return the report to the orchestrator as a blocker instead of packaging. A `.skill` built from an invalid source fails at the gate rather than at the desk, and the validation line is the `validation_report` evidence either way. |
| A user override says a reviewer finding is not real | Record the override with its reason, exclude the finding from this and later improve passes, and pass the override back to the orchestrator so the reviewer is told not to re-flag it. Do not apply a fix the user declined, and do not drop the finding from the delivery report's override table. |
| The skill directory is read-only, or a supplied path escapes the working boundary | Stop before writing. Copy to a writeable location and edit there, or ask for the correct path; never resolve a `..`, symlink, or absolute path that leaves the skill directory, eval workspace, or explicit output directory. |

**Clean pass.** When a mode completes without incident, return the files changed,
the mode that produced them, and the evidence a reviewer can check — eval
pass/fail per test case, the validation line, or the before/after trigger scores.
"Applied the findings" without the file list is not a hand-off the next stage can
verify.

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
  `grading.json`, `benchmark.json`, `feedback.json`. Read before writing or
  validating any of those files.
- **`references/examples.md`** — worked deliverables from each mode: a drafted
  SKILL.md, an `evals.json`, an improve-mode change summary, an optimize-mode
  before/after, and a package result. Read for output shape before a first run
  in an unfamiliar mode.
- **`agents/grader.md`** — how to evaluate assertions against outputs.
- **`agents/comparator.md`** — blind A/B comparison between two outputs.
- **`agents/analyzer.md`** — analyze why one version beat another.
- **`assets/eval_review.html`** — static trigger-eval review UI. Use during
  Optimize mode before running the description optimizer.
- **`eval-viewer/generate_review.py`** and **`eval-viewer/viewer.html`** — render
  human-reviewable eval outputs. Use during Eval mode when browser/static review is
  available.
### `scripts/`

Bundled automation, run as modules from the skill-creator directory so the
`scripts` package resolves. Read the target script's top-level docstring before
running it; each states its inputs, outputs, and exit codes. No file here is
orphaned — the ones not invoked directly are imported by the ones that are.

| Script | Phase | Purpose |
|--------|-------|---------|
| `quick_validate.py` | 6 | Structural pre-package validation; its output line is the `validation_report` evidence |
| `package_skill.py` | 6 | Builds the `.skill` archive; validates first and refuses an invalid source |
| `run_eval.py` | 5 | Runs trigger evaluation for one description against a query set |
| `improve_description.py` | 5 | Proposes an improved description from eval results (imported by `run_loop.py`) |
| `run_loop.py` | 5 | The optimization loop: eval → improve → re-eval with a train/test split |
| `generate_report.py` | 5 | Renders `run_loop.py` output as an HTML report (imported by `run_loop.py`) |
| `aggregate_benchmark.py` | 3 | Aggregates run results into benchmark statistics with the with-skill/baseline delta |
| `utils.py` | — | Shared helpers, including SKILL.md frontmatter parsing. Imported, never invoked |
| `__init__.py` | — | Marks `scripts` as a package so `python -m scripts.<name>` works |
| `test_regressions.py` | — | Regression tests, below |

**Regression tests.** `scripts/test_regressions.py` covers frontmatter
validation, packaging exclusions, and the eval subprocess and pipe handling those
scripts depend on. Run it after changing anything under `scripts/`, from the
skill-creator directory:

```bash
python -m unittest discover -s scripts -p "test_*.py"
```
