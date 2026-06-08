# Creating a SKILL.md — Authoritative Guide

This guide tells you how to build a Claude skill that will (a) pass Anthropic's
validation, (b) actually trigger when it should, and (c) score 100/100 on the
companion `../skill-reviewer/references/scoring-rubric.md` rubric.

It supersedes earlier drafts that omitted the hard technical limits (the 1024-
character `description` cap, the 64-character `name` cap, reserved words, the
no-XML-tags rule, the 500-line body target, etc.). Every constraint below is
sourced from Anthropic's official skills documentation.

## Contents

1. Hard constraints
2. Anatomy of a skill
3. Progressive disclosure
4. Writing the frontmatter
5. Writing the body
6. Bundled resources
7. Content guidelines
8. Validation checklist
9. Common mistakes
10. Iteration process
11. Quick reference
12. Further reading

---

## 1. Hard constraints (non-negotiable — validation will reject otherwise)

These are not style preferences. A skill that violates them either fails to
upload, fails to load, or gets silently dropped from Claude's skill selection.

### 1.1 YAML frontmatter — `name`

| Constraint | Value |
|---|---|
| Required | Yes |
| Max length | **64 characters** |
| Allowed characters | Lowercase letters, digits, hyphens only (`[a-z0-9-]`) |
| XML tags | **Forbidden** (no `<` or `>`) |
| Reserved words | **Forbidden**: `anthropic`, `claude` (and obvious variants) |
| Folder match | Should match the skill's directory name |
| Recommended form | **Gerund** (verb + -ing): `processing-pdfs`, `analyzing-spreadsheets` |

Acceptable alternatives to gerund form: noun phrases (`pdf-processing`),
action-oriented (`process-pdfs`). Avoid vague names (`helper`, `utils`, `tools`)
and generic ones (`documents`, `data`, `files`).

### 1.2 YAML frontmatter — `description`

| Constraint | Value |
|---|---|
| Required | Yes (must be non-empty) |
| Max length | **1024 characters** |
| XML tags | **Forbidden** |
| Voice | **Third person only** ("Processes Excel files…"), never first or second |
| Content | Must state **both** what the skill does **and** when to use it |
| Target substance | 80–300 characters of real content for reliable triggering |
| Style note | Lean slightly "pushy" — skills under-trigger more than they over-trigger |

The description is the single most important field in the whole skill. It is
injected into Claude's system prompt and is the **only** thing Claude sees when
deciding whether to load the skill. Inconsistent point-of-view causes discovery
problems — be third-person declarative throughout.

### 1.3 SKILL.md body

| Constraint | Value |
|---|---|
| Target length | **Under 500 lines** |
| Hard ceiling | ~5,000 tokens when loaded |
| Voice | Imperative ("Run the script", "Validate the input") |
| Path style | Forward slashes only (`scripts/foo.py`), never backslashes |

If the body approaches 500 lines, move detail into `references/` with clear
pointers. Token count matters even though SKILL.md isn't always loaded: once it
loads, every token competes with conversation history.

### 1.4 File-structure rules

- **References must be one level deep from SKILL.md.** Do not nest: if
  `references/a.md` links to `references/b.md`, Claude may partial-read and miss
  content. Link every reference directly from SKILL.md.
- **Reference files over 100 lines need a table of contents** at the top so
  Claude can scan scope even during partial reads.
- **Use forward slashes in every path**, on every platform. Windows-style paths
  break on Unix hosts.
- **Every bundled file must be pointed to from SKILL.md** (or from a reference
  file that SKILL.md points to). Orphaned files are dead weight.

### 1.5 MCP tool references

If the skill invokes MCP tools, always use **fully qualified** names:

```
Use the BigQuery:bigquery_schema tool to retrieve table schemas.
Use the GitHub:create_issue tool to open issues.
```

Format is `ServerName:tool_name`. Without the server prefix, Claude may fail to
locate the tool when multiple MCP servers are connected.

### 1.6 Package dependencies

- **claude.ai**: can install packages from npm and PyPI and pull from GitHub
- **Claude API**: no network access, no runtime package installation

List required packages explicitly in SKILL.md, and verify against the code
execution tool's supported-packages list before shipping.

### 1.7 Security

Skills must not contain malware, exploit code, or content that compromises
system security. A skill's behavior must not surprise the user given its
description. Skills that are designed to facilitate unauthorized access, data
exfiltration, or similar are not acceptable. (Roleplay skills are fine.)

---

## 2. Anatomy of a skill

```
skill-name/
├── SKILL.md              (required — frontmatter + body)
├── references/           (optional — docs loaded on demand)
│   ├── patterns.md
│   └── api-reference.md
├── scripts/              (optional — executable utilities, not loaded)
│   ├── validate.py
│   └── fill_form.py
└── assets/               (optional — files used in the output)
    ├── template.pptx
    └── logo.png
```

**`references/`** — Markdown docs Claude reads on demand. For detailed patterns,
API references, edge-case guides, domain schemas. Can be arbitrarily large; only
the files Claude reads consume tokens.

**`scripts/`** — Executable code (Python, Bash, etc.) for deterministic
operations. Claude runs them via bash; the code itself never enters context —
only the script's output does.

**`assets/`** — Files used *in* Claude's output (templates, fonts, images,
boilerplate). Not loaded into context; copied or modified on the fly.

---

## 3. Progressive disclosure — the three loading levels

| Level | When loaded | Token cost | Content |
|---|---|---|---|
| **1. Metadata** | Always, at startup | ~100 tokens per skill | `name` + `description` |
| **2. SKILL.md body** | When the skill triggers | < 5K tokens | Workflow, decisions, pointers |
| **3. Resources** | As needed via bash | Effectively unlimited | Reference files, script output |

**The design principle**: only the minimum necessary content occupies context
at any moment. SKILL.md is a *table of contents* — it points Claude to the
right deeper file when needed, rather than trying to contain every detail.

Consequences for authoring:

- SKILL.md should describe workflow and decision points, not reproduce API
  tables or long pattern catalogues.
- Move domain-specific variants into separate reference files
  (`references/aws.md`, `references/gcp.md`) so only the relevant one is read.
- Duplicate information is a bug: information should live in either SKILL.md
  *or* a reference file, never both.

---

## 4. Writing the frontmatter

### 4.1 Minimal required form

```yaml
---
name: processing-invoices
description: Extracts line items from PDF invoices, normalizes vendor names, and writes tidy CSVs. Use when the user mentions invoices, accounts payable, PDF extraction, or vendor reconciliation.
---
```

### 4.2 Description anatomy

A strong description has three pieces, in this order:

1. **What it does** — verb-first, concrete: "Extracts line items from PDFs…"
2. **Key terms / file types / domains** — "vendor names", "CSV", "PDF",
   "accounts payable"
3. **When to use it** — "Use when the user mentions…" with realistic phrasings

Combat under-triggering by leaning pushy:

> **Weak:** "Builds dashboards from internal data."
>
> **Strong:** "Builds dashboards from internal data. Use this skill whenever
> the user mentions dashboards, data visualization, internal metrics, or wants
> to display company data — even if they don't explicitly say 'dashboard'."

### 4.3 Length budget (within the 1024-char hard cap)

- **Under 80 chars** — almost always too sparse; won't trigger reliably
- **80–300 chars** — sweet spot for most skills
- **300–600 chars** — justified for skills that legitimately cover several
  contexts (use YAML `>` folded-scalar style for readability)
- **Over 600 chars** — re-read; you're probably repeating yourself or pulling
  body content into the description
- **1024 chars** — hard ceiling enforced by validation

### 4.4 Optional frontmatter fields

Some surfaces accept extra fields. Use them only when genuinely needed:

- `version:` — semantic version if you're tracking revisions externally
- `license:` — if the skill is open-sourced
- `allowed-tools:` — on surfaces that honor it, e.g.
  `Read, Write, Edit, Bash, Glob, Grep, TodoWrite`

Omit optional fields rather than leaving them blank.

### 4.5 Description examples — good and bad

✅ **Good:**
```yaml
description: Extracts text and tables from PDF files, fills forms, and merges documents. Use when working with PDF files or when the user mentions PDFs, forms, or document extraction.
```

✅ **Good:**
```yaml
description: Analyzes Excel spreadsheets, creates pivot tables, generates charts. Use when analyzing .xlsx files, spreadsheets, tabular data, or when the user asks to "summarize this sheet" or "pivot by X".
```

❌ **Bad — vague:**
```yaml
description: Helps with documents.
```

❌ **Bad — second person:**
```yaml
description: You can use this to process Excel files.
```

❌ **Bad — first person:**
```yaml
description: I'll help you process Excel files.
```

❌ **Bad — no "when":**
```yaml
description: Processes Excel files and generates reports.
```
(States what, but never when — triggering will be unreliable.)

---

## 5. Writing the body

### 5.1 Voice

- **Imperative.** "Run the script." "Validate the input." "Return JSON."
- **Explain *why*** more than you command *what*. Today's models respond better
  to reasoning than to stacked MUST/NEVER/ALWAYS.
- **Reserve all-caps commands for genuinely load-bearing rules.** If you're
  writing "MUST" for the third time in a section, reframe and explain the
  underlying constraint.

### 5.2 Be concise — default assumption: Claude already knows

Every token in SKILL.md competes with conversation history. Only add context
Claude *doesn't* already have.

Bad (≈150 tokens of filler):
```
PDF (Portable Document Format) files are a common file format that contains
text, images, and other content. To extract text from a PDF, you'll need to
use a library. There are many libraries available for PDF processing, but
pdfplumber is recommended because it's easy to use and handles most cases
well. First, you'll need to install it using pip...
```

Good (≈50 tokens):

````
## Extract PDF text

Use pdfplumber:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
````

### 5.3 Degrees of freedom — match specificity to task fragility

- **High freedom** (narrative instructions) — multiple valid approaches,
  decisions depend on context. Good for code review, drafting, open analysis.
- **Medium freedom** (templates or parameterized scripts) — preferred pattern
  exists, some variation acceptable. Good for report generation.
- **Low freedom** (specific scripts, few or no parameters) — operations are
  fragile, consistency critical, sequence matters. Good for migrations,
  destructive ops, precise transformations.

Analogy: narrow-bridge-with-cliffs (low freedom) vs. open-field (high freedom).
Match the guidance style to the terrain.

### 5.4 Standard section order

A body that reads as a workflow — setup → execution → edge cases → output —
scans cleanly. Typical order:

1. `# Skill Name` (single H1)
2. `## Quick start` / `## When to use` (optional, very short)
3. `## Core workflow` (the main procedure, numbered steps)
4. `## Edge cases` (missing inputs, malformed data, empty collections)
5. `## Output format` (templates with strictness level noted)
6. `## Utility scripts` (one subsection per script, with execute vs. read intent)
7. `## Reference files` (pointers to `references/*.md`)

### 5.5 Workflow pattern — checklists for multi-step tasks

For workflows with more than ~3 sequential steps, provide a copy-pasteable
checklist Claude can track progress against:

```markdown
## Form-filling workflow

Copy this checklist and check items off as you complete them:

- [ ] Step 1: Analyze the form (`python scripts/analyze_form.py input.pdf`)
- [ ] Step 2: Create field mapping (edit `fields.json`)
- [ ] Step 3: Validate mapping (`python scripts/validate_fields.py`)
- [ ] Step 4: Fill the form (`python scripts/fill_form.py`)
- [ ] Step 5: Verify output (`python scripts/verify_output.py`)
```

### 5.6 Feedback-loop pattern — validate, fix, repeat

Whenever quality matters more than speed, bake in a validator:

```markdown
## Document editing process

1. Make edits to `word/document.xml`
2. Validate immediately: `python scripts/validate.py unpacked_dir/`
3. If validation fails:
   - Read the error carefully
   - Fix the XML
   - Re-run validation
4. Only proceed when validation passes
5. Repack: `python scripts/pack.py unpacked_dir/ output.docx`
```

### 5.7 Template pattern — fixed vs. flexible output

Match the strictness of the template to your needs:

**Strict** (for API responses, data formats, compliance reports):

````markdown
ALWAYS use this exact template:

```
# [Title]
## Executive summary
## Key findings
## Recommendations
```
````

**Flexible** (when adaptation helps):

````markdown
Here is a sensible default — adapt sections to the analysis:

```
# [Title]
## Executive summary
## Key findings       (adapt to what you discover)
## Recommendations    (tailor to context)
```
````

### 5.8 Examples pattern — input/output pairs

When output quality depends on seeing examples, include them like you'd include
few-shot examples in a prompt:

```markdown
**Example 1:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication

**Example 2:**
Input: Fixed bug where dates displayed incorrectly in reports
Output: fix(reports): correct date formatting in timezone conversion
```

### 5.9 Conditional workflow pattern — decision points

```markdown
## Document modification workflow

1. Determine the task type:
   - **Creating new content?** → Follow "Creation" below
   - **Editing existing content?** → Follow "Editing" below

2. Creation:
   - Use docx-js
   - Build from scratch
   - Export to .docx

3. Editing:
   - Unpack the existing document
   - Modify the XML directly
   - Validate after each change
   - Repack when complete
```

### 5.10 Make execution intent explicit

For every bundled script, say clearly whether Claude should execute it or read
it as reference:

- **Execute**: "Run `analyze_form.py` to extract fields"
- **Read as reference**: "See `analyze_form.py` for the extraction algorithm"

Most utility scripts should be *executed* — it's cheaper (no code in context)
and more reliable (no regeneration drift).

---

## 6. Bundled resources — when and how

### 6.1 `references/`

Move content here when:

- The SKILL.md body is approaching 500 lines, **or**
- A section exceeds ~100 words of reference material (schemas, API surfaces,
  long pattern catalogues), **or**
- The content is only needed for a specific sub-case (one variant of many)

Rules:

- **One level deep from SKILL.md.** No `references/a.md` → `references/b.md`.
- **TOC for files over 100 lines.** Anthropic's guidance is 100; the
  adversarial rubric uses 300 as its deduction threshold. 100 is safer.
- **Name files by content**, not sequence: `form_validation_rules.md`,
  not `doc2.md`.
- **Domain split** when a skill supports multiple contexts:
  `references/aws.md`, `references/gcp.md`, `references/azure.md`.

### 6.2 `scripts/`

Include a script when:

- Claude would otherwise rewrite the same code each invocation
- Determinism matters more than flexibility
- The operation is fragile enough that re-derivation would introduce bugs

Script quality rules:

- **Handle errors explicitly** — don't punt to Claude by letting exceptions
  bubble up. Catch, log, provide a fallback.
- **No voodoo constants** — every numeric parameter needs a justifying comment
  ("30s covers slow connections", "3 retries balances reliability vs speed").
  If you can't justify it, Claude can't either.
- **Verbose error messages** — "Field 'signature_date' not found. Available
  fields: customer_name, order_total" beats "KeyError".
- **Top-of-file docstring** stating purpose, inputs, outputs, exit codes.

### 6.3 `assets/`

Include when the skill produces output that depends on specific files:

- Templates (`.pptx`, `.docx`, HTML boilerplate)
- Brand assets (logos, color palettes, fonts)
- Sample documents used as starting points

Assets are copied/modified, never read into context. Keep them organized in
subdirectories if there are more than a handful.

---

## 7. Content guidelines

### 7.1 No time-sensitive information

Bad:
```
If you're doing this before August 2025, use the old API.
After August 2025, use the new API.
```

Good — use a collapsible "Old patterns" section for historical context:
```
## Current method
Use the v2 API: `api.example.com/v2/messages`

## Old patterns
<details>
<summary>Legacy v1 API (deprecated 2025-08)</summary>
The v1 API used `api.example.com/v1/messages` — no longer supported.
</details>
```

### 7.2 Consistent terminology

Pick one term for each concept and use it throughout. Mixing "API endpoint",
"URL", "route", and "path" — or "field", "box", "element", "control" — costs
Claude comprehension tokens for no gain.

### 7.3 Don't offer too many options

Bad: "Use pypdf, or pdfplumber, or PyMuPDF, or pdf2image, or…"

Good — pick a default, offer one escape hatch for clearly different cases:
"Use pdfplumber for text extraction. For scanned PDFs requiring OCR, use
pdf2image with pytesseract instead."

### 7.4 Forward slashes everywhere

`scripts/helper.py` — not `scripts\helper.py`. Unix-style paths work on every
platform; Windows-style paths break on Unix hosts.

### 7.5 Don't assume packages are installed

Bad: "Use the pdf library to process the file."

Good:

````
Install required package: `pip install pypdf`

Then:

```python
from pypdf import PdfReader
reader = PdfReader("file.pdf")
```
````

---

## 8. Validation checklist (run before shipping)

### Frontmatter
- [ ] `name` ≤ 64 chars, lowercase + digits + hyphens only
- [ ] `name` not `anthropic` or `claude` or variants
- [ ] `name` matches the skill's folder name
- [ ] `description` non-empty, ≤ 1024 chars, no XML tags
- [ ] `description` is third-person declarative
- [ ] `description` states both *what* and *when*
- [ ] `description` contains concrete trigger phrasings

### Body
- [ ] Single H1 matching the skill's purpose
- [ ] Under 500 lines
- [ ] Imperative voice throughout
- [ ] No second-person ("you should…")
- [ ] Every claim in the description has body support
- [ ] No time-sensitive language outside an "Old patterns" section
- [ ] Forward slashes in every path
- [ ] MCP tools use `Server:tool` form
- [ ] Edge cases / failure modes addressed where relevant

### Bundled resources
- [ ] Every bundled file is referenced from SKILL.md (no orphans)
- [ ] All references are one level deep
- [ ] Reference files over 100 lines have a TOC at the top
- [ ] Scripts have a top-level docstring and handle errors explicitly
- [ ] Script-execution intent is clear (execute vs. read)
- [ ] Package dependencies listed in SKILL.md

### Testing
- [ ] At least 3 realistic eval queries written
- [ ] Skill triggers reliably on the expected phrasings
- [ ] Skill does **not** trigger on adjacent-but-distinct domains
- [ ] Tested with every model size you intend to use (Haiku, Sonnet, Opus)
- [ ] Real task produces the expected quality of output

### Adversarial scoring
- [ ] Every dimension in `../skill-reviewer/references/scoring-rubric.md` is at 10/10, or deductions are
      documented with a plan to fix

---

## 9. Common mistakes

### 9.1 Descriptions that don't trigger

Symptom: the skill exists, but Claude never picks it up for the cases you
designed it for.

Fix: check the description against the list of phrasings a real user would use.
Add explicit trigger phrases. Lean pushy. Test with the description
optimization loop if you have the tooling.

### 9.2 SKILL.md is a dumping ground

Symptom: body over 500 lines, most of it is reference tables or deep API
specs.

Fix: move detail to `references/`. Leave SKILL.md as the table of contents.
If you end up with 5 reference files, prefer that to one bloated SKILL.md.

### 9.3 Second-person drift

Symptom: the body starts with "Run the script" but slips into "you should check
the output" and "you'll want to validate…".

Fix: find every "you" and "your" and rewrite. Third-person/imperative is
consistent; mixed voice confuses triggering and reads weirdly in the system
prompt.

### 9.4 Orphaned files

Symptom: `references/advanced.md` exists, but nothing in SKILL.md points to it.

Fix: either add a pointer in SKILL.md (with the context for when Claude should
read it), or delete the file.

### 9.5 Nested references

Symptom: SKILL.md → `references/overview.md` → `references/details.md` → the
actual content.

Fix: flatten. Claude may `head -100` referenced-of-referenced files and miss
content. Keep all references one hop from SKILL.md.

### 9.6 Voodoo constants in scripts

Symptom: `TIMEOUT = 47  # ?` and `RETRIES = 5  # ?`

Fix: either pick a justifiable value or remove the parameter. Every constant
needs a one-line comment explaining the choice.

### 9.7 Punting to Claude

Symptom: `def process_file(path): return open(path).read()` — blows up on
missing file.

Fix: handle the error inside the script. Provide a default, log the issue,
return a typed result. Scripts that fail silently are worse than no script.

---

## 10. Iteration process

The most effective skill development has two Claudes in the loop:

1. **Claude A** helps design and refine the skill
2. **Claude B** (a fresh instance with the skill loaded) actually uses it on
   real tasks
3. **You** observe where B struggles and bring those observations to A
4. A revises the skill; B tests again

The observe-refine-test cycle is how skills graduate from "looks right" to
"actually works". Start with 3 realistic eval queries, run them, note where
B misses context or takes the wrong path, and update SKILL.md or its
references to address those gaps specifically.

When you're ready to score the skill against the 10-dimension rubric, use the
companion document: **`../skill-reviewer/references/scoring-rubric.md`**.

---

## 11. Quick reference — the numbers that matter

| What | Limit |
|---|---|
| `name` max length | 64 characters |
| `name` character set | `[a-z0-9-]` |
| `name` reserved words | `anthropic`, `claude` |
| `description` max length | 1024 characters |
| `description` target substance | 80–300 characters |
| `description` voice | Third-person declarative |
| SKILL.md body target | Under 500 lines (~5K tokens) |
| Reference file TOC threshold | 100 lines |
| Reference nesting | One level deep maximum |
| Metadata token cost (per skill) | ~100 tokens |
| Max skills per API request | 8 |

---

## 12. Further reading

- Anthropic skills overview: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview
- Authoring best practices: https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices
- Companion scorecard: `../skill-reviewer/references/scoring-rubric.md`
