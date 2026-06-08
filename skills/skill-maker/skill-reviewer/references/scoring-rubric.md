# SKILL.md Score-card — Reference for a Perfectly-Created Skill

This document is the grading rubric for a Claude skill. It pairs with
`../../references/skill-guide.md`: that document tells you how to *build* a skill;
this one tells you how to *evaluate* one. A "production-ready" skill scores **100/100**
here and also passes real behavioral evals (task runs against realistic user
prompts).

The rubric is 10 dimensions × 10 points. For each dimension, this document
specifies:

- **What it measures** — the question the dimension answers
- **10/10 criteria** — what a perfect score looks like, concretely
- **Deduction ladder** — how points come off for specific issues
- **Red flags** — patterns that signal a problem exists
- **Evidence format** — how to cite the finding so the score is defensible

---

## Contents

- [How to score consistently](#how-to-score-consistently)
- [Dimension 1 — Trigger description](#dimension-1--trigger-description-010)
- [Dimension 2 — Scope & intent alignment](#dimension-2--scope--intent-alignment-010)
- [Dimension 3 — Content depth](#dimension-3--content-depth-010)
- [Dimension 4 — Writing style](#dimension-4--writing-style-010)
- [Dimension 5 — Progressive disclosure](#dimension-5--progressive-disclosure-010)
- [Dimension 6 — Examples & references](#dimension-6--examples--references-010)
- [Dimension 7 — Edge-case coverage](#dimension-7--edge-case-coverage-010)
- [Dimension 8 — Security & robustness](#dimension-8--security--robustness-010)
- [Dimension 9 — Structure & readability](#dimension-9--structure--readability-010)
- [Dimension 10 — Documentation & metadata](#dimension-10--documentation--metadata-010)
- [Severity prioritization](#severity-prioritization--which-deductions-to-fix-first)
- [Stopping rules for the review loop](#stopping-rules-for-the-review-loop)
- [Blank scorecard template](#blank-scorecard-template)
- [Example: a 100/100 scorecard](#example-a-100100-scorecard-for-a-perfect-skill)
- [Using this alongside real behavioral evals](#using-this-alongside-real-behavioral-evals)
- [Cross-references](#cross-references)

---

## How to score consistently

For each dimension:

1. Read the relevant portion of the skill (frontmatter, body, references,
   scripts — whichever the dimension is about).
2. Start from 10 and deduct only for specific, cite-able issues.
3. For every deduction, write a finding with: the dimension, the deduction
   size, the evidence (file + line reference or a verbatim snippet), and the
   fix.
4. Sum the 10 dimensions for the total. Max is 100.
5. Don't invent deductions to hit a target. If a dimension is genuinely
   perfect, give it 10.

### Calibration errors to avoid

- **Grade inflation** — giving 9/10 when there's a visible issue. If you'd
  change something, it's not a 10.
- **Grade deflation** — holding skills to a standard no real skill meets.
  If you can't articulate what would make the dimension *better*, it's a 10.
- **Single-issue anchoring** — letting one big problem drag unrelated
  dimensions down. Scope deductions to the dimension they belong to.

---

## Dimension 1 — Trigger description (0–10)

**What it measures**: will the skill fire when it should, and correctly
decline when it shouldn't. The `description` is the only thing Claude sees
before deciding whether to load the skill.

### 10/10 criteria

- ≤ 1024 characters (hard cap), ideally 80–300 characters of real substance
- Third-person declarative voice throughout (no "I", no "you")
- States **both** what the skill does **and** when to use it
- Lists concrete triggering contexts: user phrasings, file types, domains
- Includes a slightly pushy cue ("even if the user doesn't explicitly say X")
- Correctly excludes adjacent-but-distinct domains (no scope creep)
- No XML tags, no reserved words (`anthropic`, `claude`)

### Deduction ladder

- **−1** — one minor vague phrasing, or one common user phrasing missing
- **−2** — multiple missing phrasings, or slightly too broad (claims
  relevance to work the skill doesn't actually support)
- **−3** — second-person voice ("I'll help you…"), or under 50 chars of
  substance (too sparse to trigger reliably)
- **−5** — fully generic ("helps with documents") with no specific triggers
- **−7** — no phrasings at all; pure abstract claim
- **−10** — missing, empty, or describes a different skill

### Red flags

- "This skill helps users…" — second person, not pushy enough
- Only the skill name repeated ("PDF skill for PDFs")
- States *what* but never *when*
- Over 600 chars — bloats `available_skills` context on every request
- Any `<` or `>` characters (will fail validation)

### Evidence format

> **D1, −2:** description omits the phrasing "invoice reconciliation" which
> is how ~30% of target users describe the task (see user-prompt examples in
> evals/evals.json). Fix: append ", invoice reconciliation" to the trigger
> list.

---

## Dimension 2 — Scope & intent alignment (0–10)

**What it measures**: does the body deliver on what the description
promises — nothing less, nothing unrelated?

### 10/10 criteria

- Every claim in the description has clear support in the body
- Every major section of the body traces back to something the description
  mentioned
- No scope creep (body covers A, B, and also an unannounced C)
- No under-delivery (description promises A and B, body only addresses A)
- The skill solves one coherent problem, not two stapled together

### Deduction ladder

- **−1** — body slightly exceeds description's scope (minor creep)
- **−2** — body under-delivers on one described capability
- **−3** — scope creep on one major topic, or under-delivery on one major
  capability
- **−5** — description and body describe meaningfully different skills
- **−7** — body covers topic A, description promises topic B
- **−10** — no coherent relationship between description and body

### Red flags

- Description mentions file types the body never addresses
- Body spends a large section on something the description never hints at
- The skill is actually two skills in one trenchcoat

### Evidence format

> **D2, −3:** description says "fills PDF forms" but no body section or
> script covers form filling. Either add a form-filling section + utility,
> or remove that clause from the description.

---

## Dimension 3 — Content depth (0–10)

**What it measures**: is the guidance concrete and actionable, or vague and
aspirational?

### 10/10 criteria

- Every instruction is something a model could follow without guessing
- Concrete steps, specific parameters, exact file paths, command templates
- Examples show real inputs and outputs
- No section reads as "be excellent" without telling Claude *how* to be
  excellent

### Deduction ladder

- **−1** — one minor aspirational line ("strive to write clear code")
- **−2** — one section vague enough to require guessing
- **−3** — multiple vague sections, or a core workflow step is ambiguous
- **−5** — large portions are aspirational filler
- **−7** — the skill describes a goal but never explains how to achieve it
- **−10** — no actionable guidance at all

### Red flags

- "Use best practices for X" — which practices?
- "Handle errors gracefully" — how specifically?
- "Write clean code" — by what standard?
- Every test case requires the model to re-derive the approach from scratch

### Evidence format

> **D3, −2:** the "Edge cases" section reads "Handle unexpected inputs
> thoughtfully" with no concrete guidance. Add specific cases: empty input,
> malformed JSON, encoding mismatches, and the exact fallback for each.

---

## Dimension 4 — Writing style (0–10)

**What it measures**: imperative form, explained reasoning, consistent
voice, no rigid unexplained commands, no filler.

### 10/10 criteria

- Imperative verbs ("Run the script", "Validate the input", "Return JSON")
- *Why* explained behind any important rule (not just MUST)
- All-caps commands reserved for genuinely load-bearing rules
- Voice consistent throughout — no switching between first, second, third person
- No preamble, no throat-clearing, no filler sentences

### Deduction ladder

- **−1** — a few passive-voice or second-person slips
- **−2** — several unexplained MUSTs/NEVERs that could be reasoning
- **−3** — consistent second-person voice, or heavy filler
- **−5** — rigid command-list style with no explanation anywhere
- **−7** — incoherent voice (switches between person modes)
- **−10** — unreadable

### Red flags

- Every other line starts with ALWAYS or NEVER
- "You will do X" stacked repeatedly
- Explanations that say *what* but never *why*
- Multi-paragraph preamble before the real content starts

### Evidence format

> **D4, −1:** 3 instances of "you should" in the workflow section
> (lines 47, 62, 88). Rewrite to imperative.

---

## Dimension 5 — Progressive disclosure (0–10)

**What it measures**: does content live at the right loading level? Metadata
→ SKILL.md body → bundled resources.

### 10/10 criteria

- SKILL.md body under 500 lines, focused on workflow and decisions
- Deep reference material lives in `references/` with clear pointers
- Reusable scripts in `scripts/`, examples longer than ~20 lines in
  `examples/`
- Reference files over 100 lines have a table of contents
- All references are one level deep from SKILL.md (no nested pointers)
- No duplicated content between SKILL.md and references

### Deduction ladder

- **−1** — one reference file over 100 lines without a TOC
- **−2** — one body section (>100 words) is reference material that should
  be extracted
- **−3** — multiple body sections belong in references, or reusable scripts
  inlined as code blocks in the body
- **−5** — SKILL.md over 800 lines with no attempt at hierarchy
- **−7** — everything is in SKILL.md; `references/` empty or vestigial
- **−10** — no disclosure structure — one giant file

### Red flags

- Body has 200+ lines of API reference tables
- Same content appears in both body and a reference file (duplication)
- `references/` has a 1000-line file with no TOC
- Body references a file that doesn't exist (broken pointer)
- Nested references (SKILL.md → ref-A → ref-B)

### Evidence format

> **D5, −2:** `references/api.md` is 247 lines with no TOC. Add a Contents
> section at the top enumerating the covered methods so Claude can scan
> scope during partial reads.

---

## Dimension 6 — Examples & references (0–10)

**What it measures**: are examples complete, runnable, and representative?
Are reference files focused and well-organized?

### 10/10 criteria

- Examples compile/run without modification
- Examples cover realistic use cases, not trivial ones
- Every bundled file is pointed to from SKILL.md or a linked reference
- References are focused, split by domain where appropriate
- No orphaned files

### Deduction ladder

- **−1** — one example is slightly contrived
- **−2** — one orphaned file (exists but nothing points to it)
- **−3** — examples miss a major use case, or one broken / non-runnable
  example
- **−5** — multiple orphaned or broken files
- **−7** — examples are trivial and don't represent real usage
- **−10** — no examples for a skill that clearly needs them

### Red flags

- `examples/foo.py` exists but nothing in SKILL.md points to it
- Example code has undefined variables or wrong imports
- Reference files duplicate each other
- A domain-specific skill (e.g., `deploy-to-aws`) has no AWS-specific example

### Evidence format

> **D6, −3:** `examples/basic_usage.py` has `from pdf_utils import …` but no
> such module exists in the skill. Either add the module or rewrite the
> example against the actual script API in `scripts/`.

---

## Dimension 7 — Edge-case coverage (0–10)

**What it measures**: does the skill handle unexpected inputs, failure
modes, and boundary conditions?

### 10/10 criteria

- Explicitly addresses missing, malformed, empty, adversarial, or
  surprisingly large inputs
- Failure paths documented — what Claude should return when the happy path
  breaks
- Boundary conditions mentioned where relevant (off-by-one, unicode, empty
  collections, inverted ranges)
- Input validation is explicit, not assumed

### Deduction ladder

- **−1** — one obvious edge case not addressed
- **−2** — multiple edge cases unaddressed, or no guidance for missing inputs
- **−3** — no failure-mode handling anywhere
- **−5** — the skill assumes the happy path throughout
- **−7** — the skill will confidently produce wrong output on common edge
  inputs
- **−10** — no edge-case awareness whatsoever

### Red flags

- "If the file exists, do X" — no branch for "if it doesn't"
- "Parse the JSON" — no handling for malformed JSON
- "Use the user's date range" — no handling for empty or inverted range
- No guidance for contradictory user input

### Evidence format

> **D7, −2:** the form-filling workflow assumes all fields exist in
> fields.json, but doesn't specify what to do when the user supplies a
> subset. Add: "If a field is missing from fields.json, prompt the user
> rather than leaving it blank."

---

## Dimension 8 — Security & robustness (0–10)

**What it measures**: input validation, safe defaults, absence of dangerous
patterns.

### 10/10 criteria

- User input validated before sensitive operations
- No instructions that execute arbitrary user-supplied code without guarding
- Safe defaults (read-only where possible, scoped paths, rate limits)
- Sensitive operations (deletions, credentials, network calls) explicitly
  guarded
- No malicious patterns, no surprise behaviors

### Deduction ladder

- **−1** — one safe default missing in a low-risk area
- **−2** — unvalidated user input flowing into a non-destructive operation
- **−3** — no input validation guidance, or default too permissive
- **−5** — pattern enables injection ("run whatever command the user
  provides")
- **−7** — multiple dangerous patterns
- **−10** — skill actively instructs harmful behavior

### Red flags

- "Execute the user's shell command" without sandboxing
- File operations without path validation
- Credentials handled in instructions rather than via secure integrations
- `rm -rf` or equivalent without confirmation logic

### Evidence format

> **D8, −3:** `scripts/clean_dir.py` takes a path argument and calls
> `shutil.rmtree(path)` with no validation. Add a whitelist check that the
> path is inside a scoped working directory.

---

## Dimension 9 — Structure & readability (0–10)

**What it measures**: logical top-to-bottom flow, scannable sections, no
duplication.

### 10/10 criteria

- Body reads as a workflow: setup → execution → edge cases → output
- Headings are informative (the reader can skim just headings and know what
  the skill does)
- Sections are scannable — no walls of prose
- No content repeated in multiple places
- Cross-references are clean and land on the right section

### Deduction ladder

- **−1** — one section slightly out of order
- **−2** — duplicate content in two sections (minor)
- **−3** — order requires back-and-forth reading, or significant duplication
- **−5** — no clear flow; sections feel shuffled
- **−7** — major content repeated 3+ times
- **−10** — unreadable structure

### Red flags

- "Output format" appears before "how to generate the output"
- Same list of steps appears in three different sections
- Heading levels don't match content hierarchy (H3 under H1 with no H2)
- Wall of prose with no subheadings for a long skill

### Evidence format

> **D9, −2:** the "Output format" section is repeated almost verbatim at
> lines 72–85 and 204–217. Keep one, delete the other, cross-reference.

---

## Dimension 10 — Documentation & metadata (0–10)

**What it measures**: frontmatter completeness, supporting files documented,
nothing orphaned or unexplained.

### 10/10 criteria

- YAML frontmatter has `name` and `description` (required)
- All optional fields the skill legitimately needs are present (e.g.,
  `version:`, `allowed-tools:`)
- No blank fields (omit rather than leave blank)
- Every supporting directory has files that are pointed to and explained
- Every script has a top-level docstring / comment block
- No mystery files

### Deduction ladder

- **−1** — one script lacks a top-level comment/docstring
- **−2** — supporting directory has a file that's referenced but not
  explained
- **−3** — frontmatter missing an optional field the skill legitimately
  needs
- **−5** — multiple undocumented files, or malformed YAML
- **−7** — frontmatter incomplete in a way that affects loading
- **−10** — no frontmatter at all

### Red flags

- A `scripts/` directory with 5 files, none with docstrings
- `compatibility:` field present but blank
- Reference file named `notes.md` with no indication of when to read it
- Orphaned files the reader can't place
- Frontmatter `name` is `MySkill` (uppercase — will fail validation)

### Evidence format

> **D10, −1:** `scripts/fill_form.py` has no top-level docstring. Add one
> stating purpose, expected inputs, output location, and exit codes.

---

## Severity prioritization — which deductions to fix first

After scoring, fix in this order:

1. **Critical** — dimension scored 0–3, or a finding marked critical (any
   security issue is automatically critical)
2. **Major** — dimension scored 4–7, or a finding marked major
3. **Minor** — dimension scored 8–9 with polish-level issues

Don't skip dimensions that are "almost right" to focus on zeros — the goal
is a 100/100 skill, and a 9 costs just as much as a 0 on the road to 100.

---

## Stopping rules for the review loop

Stop iterating when:

- User is satisfied **and** rubric is 100/100, **or**
- User accepts a sub-100 score and says they're done, **or**
- Score plateaus for 2 consecutive iterations with identical deductions

If you plateau, stop and present the current state honestly. Don't add filler
to hit a number — explain what's resisting improvement and ask the user
whether to continue or ship.

---

## Blank scorecard template

Copy this for each iteration:

```
SKILL SCORECARD — <skill name> — iteration <N>
Date: <YYYY-MM-DD>
Reviewer: <who>

| # | Dimension                  | Score | Notes |
|---|----------------------------|-------|-------|
| 1 | Trigger description        |  /10  |       |
| 2 | Scope & intent alignment   |  /10  |       |
| 3 | Content depth              |  /10  |       |
| 4 | Writing style              |  /10  |       |
| 5 | Progressive disclosure     |  /10  |       |
| 6 | Examples & references      |  /10  |       |
| 7 | Edge-case coverage         |  /10  |       |
| 8 | Security & robustness      |  /10  |       |
| 9 | Structure & readability    |  /10  |       |
| 10| Documentation & metadata   |  /10  |       |
|   | **TOTAL**                  | /100  |       |

FINDINGS (priority-ordered):

Critical:
  - [Dx, −N] <evidence>. Fix: <action>.

Major:
  - [Dx, −N] <evidence>. Fix: <action>.

Minor:
  - [Dx, −N] <evidence>. Fix: <action>.

DECISION: [ship / iterate / plateau — discuss with user]
```

---

## Worked example — filled finding and score line

The example below shows one F-[NN] finding and a single dimension score line, so the templates have a concrete reference before reading the full 100/100 scorecard.

```markdown
### F-01: Description missing resume trigger phrase

- **Dimension:** 1 — Trigger description
- **Severity:** minor
- **Location:** SKILL.md, frontmatter `description` field
- **Issue:** The description covers "save progress" and "checkpoint" but omits "resume from saved state", a common user phrasing. A user asking to resume would not reliably trigger this skill.
- **Fix:** Append "resume from saved state" to the trigger list in the `description` field. Keep total length under 1024 chars.
- **Impact:** D1 rises from 8/10 to 9/10 (removes the −1 for missing obvious trigger phrasing).

---

| 1 | Trigger description | 8/10 | −1 missing "resume" trigger; −1 description exceeds 300 chars with no extra coverage gained |
```

---

## Example: a 100/100 scorecard for a perfect skill

Below is what a filled scorecard looks like for a well-built hypothetical
`processing-invoices` skill. Each dimension notes *why* it scored 10 — useful
for calibration when you're unsure if a dimension is actually at 10 or just
close.

```
SKILL SCORECARD — processing-invoices — iteration 4
Date: 2026-04-18
Reviewer: Claude A

| # | Dimension                  | Score | Notes |
|---|----------------------------|-------|-------|
| 1 | Trigger description        | 10/10 | 218 chars, 3rd person, lists invoice/
|   |                            |       | AP/reconciliation/PDF triggers, includes
|   |                            |       | pushy cue, correctly excludes generic
|   |                            |       | PDF extraction (handled by pdf skill)      |
| 2 | Scope & intent alignment   | 10/10 | Every description claim (extract line
|   |                            |       | items, normalize vendors, write CSV) has
|   |                            |       | a dedicated body section. No orphaned
|   |                            |       | sections.                                  |
| 3 | Content depth              | 10/10 | Every step has concrete command, example
|   |                            |       | input, expected output. No "best
|   |                            |       | practices" hand-waving.                    |
| 4 | Writing style              | 10/10 | Imperative throughout. Two MUSTs, both
|   |                            |       | load-bearing (validate before write,
|   |                            |       | never commit vendor names). Each
|   |                            |       | followed by 1-sentence rationale.          |
| 5 | Progressive disclosure     | 10/10 | SKILL.md 287 lines. 3 references
|   |                            |       | (vendors.md 142 lines w/ TOC, schema.md
|   |                            |       | 87 lines, edge-cases.md 64 lines). All
|   |                            |       | one level deep. No duplication.            |
| 6 | Examples & references      | 10/10 | 3 examples (simple invoice, multi-line,
|   |                            |       | scanned w/ OCR fallback). All runnable
|   |                            |       | against bundled sample PDFs. Every file
|   |                            |       | referenced from SKILL.md.                  |
| 7 | Edge-case coverage         | 10/10 | Explicit sections for: missing PDF,
|   |                            |       | unreadable PDF, unknown vendor,
|   |                            |       | duplicate line items, negative amounts,
|   |                            |       | multi-currency, empty CSV output.          |
| 8 | Security & robustness      | 10/10 | Path validation on all file ops. OCR
|   |                            |       | library pinned. CSV writer escapes
|   |                            |       | injection vectors. No shell=True in
|   |                            |       | any script.                                |
| 9 | Structure & readability    | 10/10 | Workflow order: setup → extract →
|   |                            |       | normalize → write → verify. Each script
|   |                            |       | documented once. No duplicated content.    |
| 10| Documentation & metadata   | 10/10 | name+description valid. All 4 scripts
|   |                            |       | have top-level docstrings with
|   |                            |       | input/output/exit-code spec. Every
|   |                            |       | reference file begins with a one-line
|   |                            |       | "read this when…" indicator.               |
|   | **TOTAL**                  |100/100|                                            |

FINDINGS (priority-ordered):

Critical: (none)
Major:    (none)
Minor:    (none)

DECISION: SHIP. Rubric at 100/100, 3 real-eval runs passed with
         full-credit assertions, user has approved final draft.
```

---

## Using this alongside real behavioral evals

The rubric catches **structural** problems. Real evals catch **behavioral**
problems. You need both signals:

- A skill can score 100/100 on the rubric and still produce ugly charts,
  miss a key column, or take the wrong analytical approach. Only real eval
  runs catch that.
- A skill can pass all real evals and still under-trigger on common
  phrasings, have orphaned files, or bloat `available_skills` context with
  a 900-char description. Only the rubric catches that.

Run them in parallel every iteration. Ship only when both are green.

---

## Cross-references

- Authoring guide: **`../../references/skill-guide.md`** — build the skill
- This document: **`scoring-rubric.md`** — evaluate the skill
- Anthropic docs: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices
