# Description Optimization — Detailed Guide

The description field in SKILL.md frontmatter is the primary mechanism that decides
whether Claude invokes a skill. After creating or improving a skill, offer to
optimize the description for better triggering accuracy. This runs after the main
improvement loop settles — not before, because an optimized description for a
half-finished skill is wasted effort.

## Contents

1. Generate trigger eval queries
2. Review with user
3. Run the optimization loop
4. How skill triggering works
5. Apply the result

**Environment note**: this phase requires the `claude -p` CLI, which exists in Claude
Code and Cowork but not Claude.ai. On Claude.ai, skip this phase and rely on manual
description craft guidance from SKILL.md Phase 2.

---

## Step 1: Generate trigger eval queries

Create ~20 eval queries — a mix of should-trigger and should-not-trigger. Save as
JSON:

```json
[
  {"query": "the user prompt", "should_trigger": true},
  {"query": "another prompt", "should_trigger": false}
]
```

### Making queries realistic

Queries must look like things a Claude user would actually type. Not abstract
requests, but concrete ones with detail: file paths, personal context about the
user's job, column names and values, company names, URLs, a little backstory. Some
should be in lowercase, contain abbreviations, typos, or casual speech. Mix lengths.
Focus on edge cases over clear-cut ones (the user signs off on them in the next
step).

**Bad**: `"Format this data"`, `"Extract text from PDF"`, `"Create a chart"`

**Good**: `"ok so my boss just sent me this xlsx file (its in my downloads, called
something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that
shows the profit margin as a percentage. The revenue is in column C and costs are in
column D i think"`

### Should-trigger queries (8–10)

Think coverage. You want:

- Different phrasings of the same intent — some formal, some casual
- Cases where the user doesn't explicitly name the skill or file type but clearly
  needs it
- Uncommon use cases
- Cases where this skill competes with another but should win

### Should-not-trigger queries (8–10)

The most valuable ones are **near-misses** — queries that share keywords or concepts
with the skill but actually need something different. Think adjacent domains,
ambiguous phrasing where a naive keyword match would trigger but shouldn't, cases
where the query touches on something the skill does but in a context where another
tool is more appropriate.

**Avoid**: obviously irrelevant queries. "Write a fibonacci function" as a negative
test for a PDF skill is too easy — it doesn't test anything. Negatives should be
genuinely tricky.

---

## Step 2: Review with user

Present the eval set for review using the HTML template:

1. Read the template from `assets/eval_review.html`
2. Replace the placeholders:
   - `__EVAL_DATA_PLACEHOLDER__` → the JSON array of eval items (no quotes around it
     — it's a JS variable assignment)
   - `__SKILL_NAME_PLACEHOLDER__` → the skill's name
   - `__SKILL_DESCRIPTION_PLACEHOLDER__` → the skill's current description
3. Write to a temp file (e.g., `/tmp/eval_review_<skill-name>.html`) and open it:
   `open /tmp/eval_review_<skill-name>.html`
4. The user can edit queries, toggle should-trigger, add/remove entries, then click
   "Export Eval Set"
5. The file downloads to `~/Downloads/eval_set.json` — check the Downloads folder for
   the most recent version if there are multiples (e.g., `eval_set (1).json`)

This step matters: bad eval queries lead to bad descriptions. Don't skip sign-off.

---

## Step 3: Run the optimization loop

Tell the user: "This takes some time — I'll run the loop in the background and
check in periodically."

Save the eval set to the workspace, then run in the background:

```bash
python -m scripts.run_loop \
  --eval-set <path-to-trigger-eval.json> \
  --skill-path <path-to-skill> \
  --model <model-id-powering-this-session> \
  --max-iterations 5 \
  --verbose
```

Use the model ID from your system prompt (the one powering the current session) so
the triggering test matches what the user actually experiences.

While it runs, periodically tail the output to give the user updates on which
iteration it's on and what the scores look like.

### What the script does

The script handles the full optimization loop automatically:

1. Splits the eval set into 60% train and 40% held-out test
2. Evaluates the current description (running each query 3 times for a reliable
   trigger rate)
3. Calls Claude to propose improvements based on what failed
4. Re-evaluates each new description on both train and test
5. Iterates up to 5 times

When it's done, it opens an HTML report showing results per iteration and returns
JSON with `best_description` — selected by **test** score (not train) to avoid
overfitting.

---

## How skill triggering works

Understanding the triggering mechanism helps design better eval queries.

Skills appear in Claude's `available_skills` list with their name + description.
Claude decides whether to consult a skill based on the description. Important:
Claude only consults skills for tasks it can't easily handle on its own — simple,
one-step queries like "read this PDF" may not trigger a skill even if the
description matches perfectly, because Claude can handle them directly with basic
tools. Complex, multi-step, or specialized queries reliably trigger skills when the
description matches.

This means your eval queries should be **substantive enough that Claude would
actually benefit from consulting a skill**. Simple queries like "read file X" are
poor test cases — they won't trigger skills regardless of description quality.

---

## Step 4: Apply the result

Take `best_description` from the JSON output and update SKILL.md frontmatter. Show
the user before/after and report the scores:

```
Before: <old description>
  Train score: 78%  Test score: 72%

After: <new description>
  Train score: 96%  Test score: 94%
```

Report honestly — if test score went down while train went up, you overfitted.
Revert. If neither changed, the description was already optimal (that's a win).
