# Gatekeeper rubric review — 2026-10-26

Scope: the four Gatekeeper packages after the audit and hardening pass that followed the
review-orchestration change (commit `a3ef60488974` and this tree). This is
a score for these four packages, not for every skill in Supreme Team. Reviewed against
`skills/skill-maker/skill-reviewer/references/scoring-rubric.md`, all ten dimensions, with
`skills/skill-maker/references/skill-guide.md` as the authoring reference. The previous
scorecard is [gatekeeper-rubric-2026-10-25.md](gatekeeper-rubric-2026-10-25.md).

Review iteration: 2. The one Minor finding of iteration 1 (F-02, a second-person slip) is
resolved; the Major authoring finding (F-01, reference bulk inline) is unchanged and is the
only remaining deduction.

## Scores

| Package | Version | Score | Rubric recommendation |
| --- | --- | ---: | --- |
| `gatekeeper-admiral` | 2.0.1 | 97/100 | ITERATE: the authoring deduction below remains |
| `design/gatekeeper-design` | 2.0.1 | 97/100 | ITERATE: the authoring deduction below remains |
| `build/gatekeeper-build` | 2.0.1 | 97/100 | ITERATE: the authoring deduction below remains |
| `review/gatekeeper-code` | 2.0.1 | 97/100 | ITERATE: the authoring deduction below remains |

Unweighted mean: **97.0/100** (iteration 1: 96.75). These are reviewer judgments applying the
rubric, not measured task-success percentages. Scores below 100 are not represented as SHIP.

## Raw metrics

Counts exclude Python caches. Supporting words include bundled reference and script sources;
body words exclude frontmatter. Voice counts cover the whole package. A catalog pointer is a
relative Markdown link inside the package; an orphan is a bundled file no Markdown in the
package names.

| Package | Body words / lines | Name / description chars | Supporting words | Files / depth | Broken pointers / orphans | Second-person occurrences |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gatekeeper-admiral` | 4743 / 340 | 18 / 574 | 4329 | 5 / 1 | 0 / 0 | 0 |
| `design/gatekeeper-design` | 5133 / 368 | 17 / 487 | 6295 | 7 / 1 | 0 / 0 | 0 |
| `build/gatekeeper-build` | 4349 / 315 | 16 / 567 | 3729 | 5 / 1 | 0 / 0 | 0 |
| `review/gatekeeper-code` | 4137 / 293 | 15 / 554 | 3668 | 5 / 1 | 0 / 0 | 0 |

All four frontmatters parse; names and descriptions satisfy the catalog limits. Every
reference file over 100 lines has a Contents section. Generated run paths and hypothetical
product files in examples are not treated as missing catalog resources. The metrics are in
[gatekeeper-rubric-2026-10-26.metrics.json](gatekeeper-rubric-2026-10-26.metrics.json).

## Scorecard — gatekeeper-admiral

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded; description 574 characters, within the catalog limit. |
| 2 | Scope & intent alignment | 10/10 | The body implements the named gate; specialist work stays with its pipeline; the judgment-rejection row now names every cause `check.py --judgment` can give. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, the four feedback fields and the Intake binding are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no second-person occurrence in the package (the one slip in `references/boundary-evidence.md` is reworded). |
| 5 | Progressive disclosure | 7/10 | F-01: several body sections remain reference material that `references/boundary-evidence.md` and `references/workflow.md` also carry; body 4743 words, 340 lines. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver; every pointer resolves. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence, a lost or corrupt cycle history, a held boundary and a rejected judgment are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts, explicit user reopen; the guard now refuses removing the phase directory that holds the records. |
| 9 | Structure & readability | 10/10 | Headings and the workflow sequence are navigable; every reference over 100 lines has a Contents section. |
| 10 | Documentation & metadata | 10/10 | Version bumped with the contract (2.0.1), tools, reference pointers and shared dependencies documented. |
| | **Total** | **97/100** | |

## Scorecard — design/gatekeeper-design

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded; description 487 characters, within the catalog limit. |
| 2 | Scope & intent alignment | 10/10 | The body implements the named gate; specialist work stays with its pipeline; the judgment-rejection row now names every cause `check.py --judgment` can give. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, the four feedback fields and the Intake binding are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no second-person occurrence in the package (the one slip in `references/boundary-evidence.md` is reworded). |
| 5 | Progressive disclosure | 7/10 | F-01: several body sections remain reference material that `references/boundary-evidence.md` and `references/workflow.md` also carry; body 5133 words, 368 lines. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver; every pointer resolves. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence, a lost or corrupt cycle history, a held boundary and a rejected judgment are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts, explicit user reopen; the guard now refuses removing the phase directory that holds the records. |
| 9 | Structure & readability | 10/10 | Headings and the workflow sequence are navigable; every reference over 100 lines has a Contents section. |
| 10 | Documentation & metadata | 10/10 | Version bumped with the contract (2.0.1), tools, reference pointers and shared dependencies documented. |
| | **Total** | **97/100** | |

## Scorecard — build/gatekeeper-build

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded; description 567 characters, within the catalog limit. |
| 2 | Scope & intent alignment | 10/10 | The body implements the named gate; specialist work stays with its pipeline; the judgment-rejection row now names every cause `check.py --judgment` can give. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, the four feedback fields and the Intake binding are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no second-person occurrence in the package (the one slip in `references/boundary-evidence.md` is reworded). |
| 5 | Progressive disclosure | 7/10 | F-01: several body sections remain reference material that `references/boundary-evidence.md` and `references/workflow.md` also carry; body 4349 words, 315 lines. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver; every pointer resolves. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence, a lost or corrupt cycle history, a held boundary and a rejected judgment are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts, explicit user reopen; the guard now refuses removing the phase directory that holds the records. |
| 9 | Structure & readability | 10/10 | Headings and the workflow sequence are navigable; every reference over 100 lines has a Contents section. |
| 10 | Documentation & metadata | 10/10 | Version bumped with the contract (2.0.1), tools, reference pointers and shared dependencies documented. |
| | **Total** | **97/100** | |

## Scorecard — review/gatekeeper-code

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded; description 554 characters, within the catalog limit. |
| 2 | Scope & intent alignment | 10/10 | The body implements the named gate; specialist work stays with its pipeline; the judgment-rejection row now names every cause `check.py --judgment` can give. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, the four feedback fields and the Intake binding are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no second-person occurrence in the package (the one slip in `references/boundary-evidence.md` is reworded). |
| 5 | Progressive disclosure | 7/10 | F-01: several body sections remain reference material that `references/boundary-evidence.md` and `references/workflow.md` also carry; body 4137 words, 293 lines. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver; every pointer resolves. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence, a lost or corrupt cycle history, a held boundary and a rejected judgment are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts, explicit user reopen; the guard now refuses removing the phase directory that holds the records. |
| 9 | Structure & readability | 10/10 | Headings and the workflow sequence are navigable; every reference over 100 lines has a Contents section. |
| 10 | Documentation & metadata | 10/10 | Version bumped with the contract (2.0.1), tools, reference pointers and shared dependencies documented. |
| | **Total** | **97/100** | |

## Residual rubric finding

### F-01 — Detailed reference material still dominates the skill bodies

- Dimension: D5 — Progressive disclosure, **−3 for each of the four packages** (the rubric
  ladder for multiple body sections belonging in references).
- Severity: Major authoring finding; pre-existing and unchanged since iteration 1.
- Evidence: in each `SKILL.md` the full boundary/owner table and several hundred words of
  validator and typed-record detail remain in the body while the bundled
  `references/boundary-evidence.md` and `references/workflow.md` carry the same detail.
  Body sizes: 4743, 5133, 4349 and 4137 words.
- Fix: keep gate classification, decision rules, the final judgment command, the escalation
  behaviour and short resource pointers in `SKILL.md`; move the per-key tables and validator
  explanations into the existing references. The boundary tables are drift-tested
  (`harness/gatekeeper/test_gate_manifests.py` compares them with `gates.yaml`), so the
  comparators move with the tables in the same change.
- Impact: D5 rises from 7 to 10 per package. Not counted again under D9 or D10.

### F-02 — resolved

`skills/gatekeeper-admiral/references/boundary-evidence.md` no longer switches to the second
person ("remains the gatekeeper's judgement"). D4 is 10/10 for all four packages.

## Change-focused audit of this iteration

| Change | Evidence | What it closes |
| --- | --- | --- |
| The guard refuses removing or moving a phase directory, and protects the cycle history and its lock by name | `skills/harness/hooks/guard_hook.py` Rule C (`_PHASE_DIR`, `_phase_dir_taken`, `_VERDICT_RECORD`); `test_guard_rules.py` `test_a_phase_directory_and_the_cycle_history_cannot_be_removed_or_moved` | `rm -r <phase>`, `mv <phase>`, `shutil.rmtree`, `find -delete` and `rsync --delete` could erase `verdict_<boundary>.cycles.json` and restart the third-REVISE count from zero |
| The mechanical self-check warns when a run package does not hash the Intake log | `skills/harness/gatekeeper/check.py` `Package.warn_unbound_intake` | a judgment that cannot bind `intake.artifact` is rejected only at the gate; the submitter now hears it in its own self-check |
| Nine submitters are told to hash `../intake/report_grilling.md` at every boundary | the "Review discipline" section of `build-management`, `code-chief`, `cso`, `qa`, `taste`, `redesign`, `investigate`, `skill-maker`, `ship`; the `qa` and `ship` example manifests | only `commander` documented the artifact every judgment now binds |
| The audit hook counts the effective verdict a record carries | `skills/harness/hooks/audit_improve.py` `_effective_verdict` | the third REVISE written as ESCALATE was counted from the gatekeeper's draft as REVISE, and the cycle history read as a record |
| `admiral`'s cross-stage command passes `--judgment` | `skills/admiral/SKILL.md` step 4 | without it `--verdict-out` writes a mechanical record and no verdict, and the next boundary's `revision_ref` is refused |
| Submitter rows end the third REVISE with the user's decision | `setup-deploy`, `ship`, `qa`, `qa-only`, `investigate`, `cso` and the commander and redesign examples | rows still told the owner to return its own `ESCALATE` or to stop at Admiral |

No unresolved change-focused correctness blocker was found in the reviewed controls. This
statement does not certify all existing behaviour in the repository.

## Evaluation limits

Automated evidence for this iteration: the seven suites, the three validators and lint pass
on this tree (counts in [../../BENCHMARK.md](../../BENCHMARK.md)). The paired timings are
deterministic CLI, audit and hook workloads. No live-model task runs, host-registration run,
paid trigger-routing benchmark or end-to-end model behavioural evaluation was run. The rubric
measures authored instructions and supporting code; it is not a substitute for those
evaluations.
