# Skill-Reviewer — Worked Examples

Two concrete review outputs to calibrate against: one finding in the F-[NN]
format, and one abridged scorecard. Read this alongside `scoring-rubric.md` when
learning the output shape.

## Example finding (F-[NN] format)

### F-03: reference file over 100 lines has no TOC
- **Dimension:** 5 (Progressive disclosure)
- **Severity:** minor
- **Location:** `references/api.md` (247 lines, no Contents section)
- **Issue:** `api.md` is 247 lines with no table of contents, so a partial read
  cannot establish scope. The rubric deducts D5 −1 for a reference file over 100
  lines without a TOC.
- **Fix:** Add a `## Contents` section at the top enumerating the covered methods.
- **Impact:** D5 9 → 10.

## Example scorecard (abridged)

| # | Dimension                | Score | Note |
|---|--------------------------|-------|------|
| 1 | Trigger description      | 9/10  | One common phrasing ("invoice reconciliation") missing |
| 2 | Scope & intent alignment | 10/10 | Every described capability has a body section |
| 3 | Content depth            | 10/10 | Concrete commands and example I/O throughout |
| 4 | Writing style            | 10/10 | Imperative; MUSTs are load-bearing and explained |
| 5 | Progressive disclosure   | 9/10  | See F-03 (api.md TOC) |
| 6 | Examples & references    | 10/10 | Three runnable examples against bundled samples |
| 7 | Edge-case coverage       | 10/10 | Missing / malformed / empty inputs all handled |
| 8 | Security & robustness    | 10/10 | Path validation on all file ops |
| 9 | Structure & readability  | 10/10 | Workflow order, no duplication |
| 10| Documentation & metadata | 10/10 | Frontmatter valid; scripts documented |
|   | **TOTAL**                | 98/100 | |

**Decision:** iterate — two minor findings (F-01 on D1, F-03 on D5); no critical
or major. Re-score after the fixes land.
