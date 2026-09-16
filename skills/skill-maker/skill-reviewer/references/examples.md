# Skill-Reviewer — Worked Examples

Concrete review outputs to calibrate against: one finding in the F-[NN] format,
one abridged scorecard, one filled `link_report`, and one report carrying a user
override. Read this alongside `scoring-rubric.md` when learning the output shape.

## Contents

1. Example finding (F-[NN] format)
2. Example scorecard (abridged)
3. Example `link_report` — the gate evidence this skill owns
4. Example report section — an accepted user override

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

## Example `link_report` — the gate evidence this skill owns

Written to a file and hashed, because the key is artifact-backed at
`skill-maker-to-delivery`. This is the whole deliverable, not an extract.

```markdown
# Link Report — log-triage — Iteration 4

## Pointers resolved

| Source file | Pointer as written | Resolved target | Status |
|-------------|--------------------|-----------------|--------|
| SKILL.md | `references/patterns.md` | skills/log-triage/references/patterns.md | ok |
| SKILL.md | `scripts/cluster_traces.py` | skills/log-triage/scripts/cluster_traces.py | ok |
| SKILL.md | `references/formats.md` | — | broken — target does not exist |
| references/patterns.md | `scripts/cluster_traces.py` | skills/log-triage/references/scripts/cluster_traces.py | wrong base — written from the skill root inside a references/ file; needs `../scripts/…` |

## Orphaned files

| File | Reachable by | Verdict |
|------|-------------|---------|
| examples/sample-cluster.json | nothing | orphan — document or remove |
| scripts/utils.py | Python import from cluster_traces.py | not an orphan — undocumented; add a pointer |

## Summary

- Pointers checked: 4 (ok: 2, wrong base: 1, broken: 1)
- Bundled files: 5 (referenced: 3, import-reachable: 1, orphaned: 1)
```

Returned to `skill-maker` as a path plus digest:
`skill-creation/reports/link-report.md` — `sha256:a41f70c2…`. The two pointer
failures also appear as findings (D5 and D6); the report is the evidence, the
findings are the fix instructions.

## Example report section — an accepted user override

The override was a priority decision, not a factual correction, so the deduction
stands and the score stops below 100.

```markdown
## Accepted (user override)

### F-04: `examples/sample-cluster.json` is orphaned
- **Dimension:** 6 — Examples & references
- **Severity:** major
- **Status:** accepted by user override — "the sample ships for humans, not for
  the model; leave it"
- **Effect on score:** D6 stays at 8/10. The file is still unreferenced, and the
  rubric scores what is written. Not re-raised in later iterations.

## Summary
- **Total score:** 98/100
- **Verdict:** ITERATE (< 100) — the remaining gap is the accepted override, not
  an outstanding defect. Shipping at 98 is skill-maker's call with the user,
  recorded as SHIPPED_WITH_OVERRIDES.
```
