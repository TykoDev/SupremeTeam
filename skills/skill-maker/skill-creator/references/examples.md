# Worked Examples — Skill Creator Deliverables

One worked deliverable per mode, so the output shape is calibrated before a first
run. Every artifact here is the real thing this skill hands back, not a
description of it. The running example is a hypothetical `log-triage` skill.

## Contents

1. Create mode — the drafted skill
2. Eval mode — `evals/evals.json` and the graded result
3. Improve mode — the change summary
4. Optimize mode — the before/after
5. Package mode — validation line and archive
6. A failure case worth recognizing

---

## 1. Create mode — the drafted skill

**Handed back:** the skill directory, plus the summary below.

`skills/log-triage/SKILL.md` frontmatter and section skeleton:

```markdown
---
name: log-triage
description: >-
  Triages application log dumps into ranked incident candidates: clusters
  repeated stack traces, separates first-occurrence errors from ongoing noise,
  and names the earliest failing call in each cluster. Use when the user shares
  a log file or paste and asks what broke, what to look at first, or why a
  service is erroring — even when they only say "here's the log". Not for live
  log streaming or alert-rule authoring.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash
---

# Log Triage

## Purpose
## Use This Skill When
## Inputs
## Workflow
## Failure Modes
## References
```

**Summary returned to the orchestrator:**
- Files written: `SKILL.md` (214 body lines), `references/patterns.md` (96 lines, TOC present), `scripts/cluster_traces.py` (docstring with inputs, outputs, exit codes).
- Description: 418 chars, third person, pushy cue present, negative scope names live streaming and alert rules.
- Open question surfaced, not guessed: whether JSON-lines logs are in scope. Drafted for plain text; flagged for the user.
- Not done here: no rubric score. Scoring is skill-reviewer's.

---

## 2. Eval mode — `evals/evals.json` and the graded result

`skills/log-triage/evals/evals.json`, conforming to `schemas.md`:

```json
{
  "skill_name": "log-triage",
  "evals": [
    {
      "id": 1,
      "prompt": "Here's the log from last night's outage. What broke?",
      "expected_output": "Ranked clusters with the earliest failing call named per cluster",
      "files": ["evals/files/outage-2026-04-11.log"],
      "expectations": [
        "The output ranks clusters rather than listing raw lines",
        "The first-occurrence error is distinguished from the repeating noise",
        "cluster_traces.py was used rather than hand-counting"
      ]
    },
    {
      "id": 2,
      "prompt": "why is checkout erroring",
      "expected_output": "Asks for the log or locates it, then triages",
      "files": [],
      "expectations": [
        "Does not fabricate a cause without a log",
        "Names what input it needs"
      ]
    }
  ]
}
```

**Graded result returned:**

| id | With skill | Baseline | Assertions met | Note |
| --- | --- | --- | --- | --- |
| 1 | pass | fail | 3/3 | Baseline listed raw lines; the skill clustered them |
| 2 | pass | pass | 2/2 | No differentiation; the prompt is easy without the skill |

- Aggregated with `python -m scripts.aggregate_benchmark <benchmark_dir> --skill-name log-triage --skill-path skills/log-triage`; viewer rendered for user review.
- Signal read: eval 2 does not discriminate and should be replaced with a harder prompt next iteration rather than kept as a passing score.

---

## 3. Improve mode — the change summary

**Input:** reviewer findings F-01 (major, D5), F-02 (minor, D1), F-03 (minor, D7); one user override.

**Changes applied, in priority order:**

| Finding | Dimension | Change |
| --- | --- | --- |
| F-01 | 5 — Progressive disclosure | Moved the 180-word log-format table out of the body into `references/patterns.md` and left a one-line pointer |
| F-02 | 1 — Trigger description | Added "what should I look at first" to the trigger list; description 418 → 447 chars |
| F-03 | 7 — Edge-case coverage | Added failure rows for a truncated log, a log with no timestamps, and a file over the read limit |

**Deferred, with reason:**

| Finding | Reason |
| --- | --- |
| F-04 | User override: "we never see gzipped logs here". Excluded from this and later improve passes; the orchestrator is told not to re-flag it. |

- Files changed: `SKILL.md`, `references/patterns.md`.
- Not done here: no re-score. Returned to the orchestrator for the next review pass.

---

## 4. Optimize mode — the before/after

```bash
python -m scripts.run_loop \
  --eval-set .harness-state/eval-reports/log-triage-trigger.json \
  --skill-path skills/log-triage \
  --model <model-id> \
  --max-iterations 5 \
  --verbose
```

**Result:**

| | Train | Test |
| --- | --- | --- |
| Original description | 0.78 | 0.74 |
| Iteration 3 candidate | 0.94 | 0.81 |
| Iteration 5 candidate | 0.96 | 0.77 |

- `best_description` selected by **test** score: the iteration 3 candidate, not the iteration 5 one. The later candidate scores higher on train and worse on test, which is exactly the overfitting the split exists to catch.
- Applied to frontmatter; before/after shown to the user.
- Because the description changed, the revised files go back through review before packaging.

---

## 5. Package mode — validation line and archive

```bash
cd skills/skill-maker/skill-creator
python -m scripts.quick_validate ../../log-triage
```

```text
Skill is valid!
```

That line, written to a file and hashed, is the `validation_report` evidence at
`skill-maker-to-delivery`; the key is artifact-backed, so the claim alone is not
evidence.

```bash
python -m scripts.package_skill ../../log-triage \
  skillset-saves/runs/2026-04-12_log-triage_5fe2/skill-creation/packages
```

```text
📦 Packaging skill: ../../log-triage
   Output directory: skillset-saves/runs/2026-04-12_log-triage_5fe2/skill-creation/packages

🔍 Validating skill...
✅ Skill is valid!

  Added: log-triage/SKILL.md
  Added: log-triage/references/patterns.md
  Added: log-triage/scripts/cluster_traces.py
  Skipped: log-triage/evals/evals.json

✅ Successfully packaged skill to: .../packages/log-triage.skill
```

- `evals/` at the skill root, `__pycache__`, `*.pyc`, and `.DS_Store` are excluded by design; the archive is rooted at the folder name.
- Returned: the `.skill` path, the contents list, and the validation line with its digest.

---

## A failure case worth recognizing

`evals.json` with a duplicate `id`:

```json
{"skill_name": "log-triage", "evals": [{"id": 1, "prompt": "..."}, {"id": 1, "prompt": "..."}]}
```

`schemas.md` requires `evals[].id` to be unique, because the id is what joins a
prompt to its run output, its grading, and its row in the viewer. With a
duplicate, those joins are ambiguous and the reported tally no longer maps to the
cases the user approved. Report the duplicate and stop; do not renumber silently,
because the eval set the user reviewed would no longer be the one that ran.
