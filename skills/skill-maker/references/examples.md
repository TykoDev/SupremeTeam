# Worked Examples — Skill Maker Pipeline

Complete runs, not blank forms. `delivery-template.md` is the empty report to
fill in; this file shows that report filled, the gate manifest it produced, and
the two situations where the loop does not simply reach 100 — a plateau and a
REVISE. The running example is the same `log-triage` skill used in
`../skill-creator/references/examples.md`.

## Contents

1. A complete full-pipeline run
2. The gate submission it produced
3. A plateau escalation
4. A REVISE round at the boundary
5. A single-skill `team_manifest`

---

## 1. A complete full-pipeline run

Delivery report as presented to the user, using `delivery-template.md`:

```markdown
# Skill Delivery Report — log-triage

## Executive summary

**Skill:** log-triage
**Pipeline mode:** full
**Final score:** 100/100
**Iterations:** 4
**Verdict:** SHIPPED

Triages application log dumps into ranked incident candidates. Reached 100/100
on the fourth review; description optimization raised held-out trigger accuracy
from 0.74 to 0.81 and was re-reviewed before packaging.

---

## Iteration history

| Iter | Stage | Score | Delta | Key changes |
|------|-------|-------|-------|-------------|
| 1 | Create → Review | 71/100 | — | Initial draft |
| 2 | Improve → Review | 88/100 | +17 | Extracted the log-format table to references/, added three failure rows |
| 3 | Improve → Review | 96/100 | +8 | Added the "what should I look at first" trigger, fixed four second-person lines |
| 4 | Improve → Review | 100/100 | +4 | Documented cluster_traces.py exit codes, removed one orphaned sample file |
| 5 | Optimize → Review | 100/100 | 0 | Description re-reviewed after the optimizer changed it |
| 6 | Package | — | — | .skill file created |

---

## Behavioral eval status

| Test case | Result | Notes |
|-----------|--------|-------|
| "Here's the log from last night's outage. What broke?" | pass | Baseline listed raw lines; the skill clustered them |
| "why is checkout erroring" | pass | Did not discriminate — replace with a harder prompt next time |

---

## Description optimization

**Before:** "Triages application log dumps into ranked incident candidates…"
**After:** "…what to look at first… — even when they only say 'here's the log'."
**Trigger accuracy:** 74% → 81% (held-out test set; the train-better iteration-5
candidate was rejected)

---

## Files in package

| File | Purpose |
|------|---------|
| SKILL.md | Main skill definition |
| references/patterns.md | Log-format table and cluster heuristics |
| scripts/cluster_traces.py | Groups repeated stack traces |

**Package path:** skillset-saves/runs/2026-04-12_log-triage_5fe2/skill-creation/packages/log-triage.skill

---

## Stages executed

- [x] Intake
- [x] Create
- [x] Review (4 iterations)
- [x] Improve (3 cycles)
- [x] Optimize
- [x] Package

---

## Recommendations

Skill is production-ready. One follow-up: eval case 2 does not discriminate
against the baseline and should be replaced before the next hardening pass.
```

---

## 2. The gate submission it produced

`skill-creation/manifest.json`, the package submitted at
`skill-maker-to-delivery`. All four keys present; the two artifact-backed ones
name files that appear in `artifact_hashes`.

```json
{
  "schema_version": 2,
  "boundary": "skill-maker-to-delivery",
  "owner": "skill-maker",
  "run_id": "2026-04-12_log-triage_5fe2",
  "submission_id": "2026-04-12_log-triage_5fe2-r4",
  "revision": 4,
  "revisions": [4],
  "artifact_hashes": {
    "skill-creation/reports/link-report.md": "a41f70c2…",
    "skill-creation/reports/validation-report.md": "6ce8b019…"
  },
  "evidence": {
    "skills": "skills/log-triage — 100/100 on the 10-dimension rubric at iteration 4, re-reviewed at iteration 5 after description optimization.",
    "team_manifest": {
      "applicable": false,
      "reason": "single skill - no team manifest produced",
      "scope": "one skill delivered; no team was created",
      "decided_by": "skill-maker"
    },
    "link_report": "skill-creation/reports/link-report.md",
    "validation_report": "skill-creation/reports/validation-report.md"
  }
}
```

Self-check, run without `--verdict-out` before submitting:

```bash
python skills/harness/gatekeeper/check.py --boundary skill-maker-to-delivery --package skillset-saves/runs/2026-04-12_log-triage_5fe2/skill-creation/manifest.json
```

---

## 3. A plateau escalation

Iterations 3 and 4 both returned 94/100 with the identical deduction list, which
is the plateau condition: score unchanged for two consecutive iterations.

**Presented to the user, without continuing the loop:**

> Score plateaued at 94/100 across iterations 3 and 4, with the same two findings
> both times:
>
> - **F-02 (major, D6)** — `examples/sample-cluster.json` is orphaned: nothing in
>   SKILL.md or the references points to it. The fix is to document it or remove
>   it, and that is a call about whether the sample is meant to ship.
> - **F-05 (minor, D3)** — "tune the clustering threshold appropriately" has no
>   concrete guidance. A specific default is needed, and which one depends on the
>   log volumes this is aimed at.
>
> Both need input rather than another improve cycle. Options: (a) override and
> ship at 94, (b) answer the two questions and run one more cycle, (c) abort.

The orchestrator does not guess a threshold or delete the sample to clear the
findings — inventing an answer to reach 100 is how the score stops meaning
anything.

---

## 4. A REVISE round at the boundary

**Gate verdict on revision 3:** `REVISE`, two failing keys with two owners.

| Owner | Failing key | Reason |
| --- | --- | --- |
| skill-reviewer | `link_report` | Value names `skill-creation/reports/link-report.md`, which is absent from `artifact_hashes` — the report was described, not shipped |
| skill-maker | `team_manifest` | Value reads "no team was created", which is not the sanctioned fallback string |

**Response:**
- Both owners delegated in parallel in one turn; every failure for one owner batched into a single revision delegation.
- skill-reviewer wrote the link report to the named path and returned its digest.
- The orchestrator replaced the paraphrase with `single skill - no team manifest produced`, byte-for-byte from `../../gates.yaml`.
- Resubmitted once at revision 4 with `--prior`, so `skills` and `validation_report` returned as `unchanged_evidence` and carried their prior judgment.
- Cycle count under Admiral: 1 of 2. A third cycle escalates instead of resubmitting.

---

## 5. A single-skill `team_manifest`

The one value whose wording is fixed rather than composed. For a run that
produced one skill:

```text
single skill - no team manifest produced
```

Not "no team manifest", not "single skill — no team manifest produced" (em dash),
not "the statement that no team was created". `../../gates.yaml`
`fallback_values.team_manifest` sanctions exactly the string above.

**What the machine actually catches, and what it does not.** It is tempting to
read the rule above as mechanically enforced in both directions. It is not, and
the asymmetry runs the wrong way:

| Value submitted | Self-check result |
| --- | --- |
| The applicability record below | passes — the correct form |
| A bare string with the *sanctioned* wording | **fails**: `bare fallback string not accepted at schema 2: team_manifest (use an applicability record)` |
| A bare string with a *paraphrase* — "no team manifest was produced for this single-skill run" | **passes silently** |

The paraphrase passes because `team_manifest` has no row in `../../gates.yaml`
`evidence_types`, so `check.py` runs no typed check on it, and a non-path string
that matches no sanctioned wording trips neither the fallback branch nor the
artifact-backing branch. So the precise value fails the checker and the vague one
does not. A paraphrase is caught by gatekeeper judgment and returned as `REVISE`
— by a reader, never by the machine. Treat a green self-check on this key as
proof of nothing: read the value before you submit it.

The string is the `reason`, not the value. At `schema_version: 2` the key carries
a typed applicability record, and a bare string — even the sanctioned one — is
refused with `bare fallback string not accepted at schema 2: team_manifest (use
an applicability record)`:

```json
"team_manifest": {
  "applicable": false,
  "reason": "single skill - no team manifest produced",
  "scope": "one skill delivered; no team was created",
  "decided_by": "skill-maker"
}
```

For a team run the key carries the real manifest instead: the component list,
which skill orchestrates, and the delegation surface between them.
