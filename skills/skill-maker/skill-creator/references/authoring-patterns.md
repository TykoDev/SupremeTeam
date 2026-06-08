# Authoring Patterns — Quick Reference for Drafting & Fixing Skills

Read this when drafting a new SKILL.md, applying reviewer findings, or diagnosing
structural issues during the improvement loop. For the full authoring guide
(hard constraints, anatomy, progressive disclosure, frontmatter rules),
read `../../references/skill-guide.md`.

## Contents

1. Standard section order
2. Degrees of freedom
3. Workflow patterns
4. Execution intent
5. Content guidelines
6. Common mistakes
7. Pre-ship validation checklist

---

## 1. Standard section order

A body that reads as a workflow — setup → execution → edge cases → output —
scans cleanly. Typical order:

1. `# Skill Name` (single H1 matching purpose)
2. `## Quick start` / `## When to use` (optional, very short)
3. `## Core workflow` (the main procedure, numbered steps)
4. `## Edge cases` (missing inputs, malformed data, empty collections)
5. `## Output format` (templates with strictness level noted)
6. `## Utility scripts` (one subsection per script, with execute-vs-read intent)
7. `## Reference files` (pointers to `references/*.md` with guidance on when to
   read each)

Deviate when the skill genuinely needs a different order. Imposing this layout
on a skill that doesn't fit is worse than letting it flow naturally.

---

## 2. Degrees of freedom

Match specificity to how fragile the task is:

- **High freedom** (narrative) — multiple valid approaches, decisions depend on
  context. Good for code review, drafting, open analysis.
- **Medium freedom** (templates/parameterized scripts) — preferred pattern exists,
  some variation acceptable. Good for report generation.
- **Low freedom** (specific scripts, few parameters) — operations are fragile,
  consistency critical, sequence matters. Good for migrations, destructive ops,
  precise transformations.

A skill that imposes low-freedom scripts on an inherently high-freedom task
reads as oppressive and gets ignored. One that hands high-freedom narrative to
a fragile sequence produces corrupted output.

---

## 3. Workflow patterns

### 3.1 Checklist pattern — multi-step tasks

```markdown
- [ ] Step 1: Analyze the form (`python scripts/analyze_form.py input.pdf`)
- [ ] Step 2: Create field mapping (edit `fields.json`)
- [ ] Step 3: Validate mapping (`python scripts/validate_fields.py`)
- [ ] Step 4: Fill the form (`python scripts/fill_form.py`)
- [ ] Step 5: Verify output (`python scripts/verify_output.py`)
```

### 3.2 Feedback-loop pattern — validate, fix, repeat

```markdown
1. Make edits to `word/document.xml`
2. Validate immediately: `python scripts/validate.py unpacked_dir/`
3. If validation fails → read error, fix, re-validate
4. Only proceed when validation passes
5. Repack: `python scripts/pack.py unpacked_dir/ output.docx`
```

### 3.3 Template pattern — fixed vs. flexible

**Strict** (API responses, compliance reports): exact template, no deviation.
**Flexible** (analysis, drafts): sensible default, adapt sections to context.

### 3.4 Examples pattern — input/output pairs

Few-shot demonstrations when output quality depends on seeing examples:

```markdown
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

### 3.5 Conditional workflow — decision points

```markdown
1. Determine the task type:
   - **Creating new content?** → Follow "Creation" below
   - **Editing existing content?** → Follow "Editing" below
```

---

## 4. Execution intent

For every bundled script, state clearly whether to **execute** or **read**:

- **Execute**: "Run `analyze_form.py` to extract fields"
- **Read as reference**: "See `analyze_form.py` for the extraction algorithm"

Most utility scripts should be executed — cheaper (no code in context) and more
reliable (no regeneration drift).

---

## 5. Content guidelines

- **No time-sensitive info** — skills live forever; "as of August 2025" rots fast.
- **Consistent terminology** — one term per concept throughout.
- **Don't offer too many options** — pick a default, one escape hatch for edge cases.
- **Forward slashes everywhere** — `scripts/helper.py`, never `scripts\helper.py`.
- **Don't assume packages installed** — list install commands explicitly.
- **Be concise** — Claude already knows most things. Only add context it doesn't have.

---

## 6. Common mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Description doesn't trigger | Skill exists but Claude never picks it up | Add explicit trigger phrases, lean pushy, run description optimizer |
| SKILL.md dumping ground | Body over 500 lines of reference tables | Move detail to `references/`, leave body as table of contents |
| Second-person drift | Starts imperative, slips to "you should" | Find every "you"/"your", rewrite to imperative |
| Orphaned files | Files exist but nothing points to them | Add pointer in SKILL.md or delete the file |
| Nested references | SKILL.md → ref-A → ref-B → actual content | Flatten — all references one hop from SKILL.md |
| Voodoo constants | `TIMEOUT = 47  # ?` | Every constant needs a one-line justifying comment |
| Punting to Claude | Script blows up on missing file | Handle errors inside the script, provide defaults |
| Vague MCP tools | "Call the schema tool" | Fully qualified: `BigQuery:bigquery_schema` |

---

## 7. Pre-ship validation checklist

### Frontmatter
- [ ] `name` ≤ 64 chars, `[a-z0-9-]` only, no XML tags, not reserved
- [ ] `name` matches skill's folder name
- [ ] `description` non-empty, ≤ 1024 chars, third-person declarative
- [ ] `description` states both what AND when with concrete trigger phrasings

### Body
- [ ] Single H1, under 500 lines, imperative voice throughout
- [ ] No second-person drift, no time-sensitive language
- [ ] Every description claim has body support
- [ ] Forward slashes, MCP tools use `Server:tool` form
- [ ] Edge cases / failure modes addressed

### Bundled resources
- [ ] Every file referenced from SKILL.md (no orphans)
- [ ] References one level deep, TOC for files over 100 lines
- [ ] Scripts have docstrings, handle errors, execution intent is clear
- [ ] Package dependencies listed

### Testing
- [ ] At least 3 realistic eval queries written
- [ ] Triggers reliably on expected phrasings, not on adjacent domains

### Adversarial scoring
- [ ] Every rubric dimension at 10/10 or deductions documented with fix plan
