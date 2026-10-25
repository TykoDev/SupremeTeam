# Gatekeeper rubric review — 2026-10-25

Scope: the four changed Gatekeeper packages and the shared controls implementing the requested orchestration changes. This is not a score for every skill in SupremeTeam. Reviewed against `skills/skill-maker/skill-reviewer/references/scoring-rubric.md`, all ten dimensions, and the authoritative `skills/skill-maker/references/skill-guide.md`.

Review iteration: 1, final implementation snapshot. No baseline rubric score was measured, so no score improvement or delta is claimed.

## Scores

| Package | Version | Score | Rubric recommendation |
| --- | --- | ---: | --- |
| `gatekeeper-admiral` | 2.0.0 | 96/100 | ITERATE: authoring deductions remain |
| `design/gatekeeper-design` | 2.0.0 | 97/100 | ITERATE: authoring deductions remain |
| `build/gatekeeper-build` | 2.0.0 | 97/100 | ITERATE: authoring deductions remain |
| `review/gatekeeper-code` | 2.0.0 | 97/100 | ITERATE: authoring deductions remain |

Unweighted mean: **96.75/100**. These are reviewer judgments, not measured task-success percentages. The remaining deductions concern pre-existing authoring issues; the behavioral audit findings raised during this review were corrected in the implementation. Scores below 100 are not represented as SHIP.

## Raw metrics

Counts exclude Python caches and generated files. Supporting word counts include bundled reference and script sources; body words exclude frontmatter. Voice counts cover the package, not only SKILL.md.

| Package | Body words / lines | Name / description chars | Supporting words | Files / depth | Broken catalog pointers / orphans | Second-person occurrences |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gatekeeper-admiral` | 4700 / 341 | 18 / 574 | 4329 | 5 / 1 | 0 / 0 | 1 |
| `design/gatekeeper-design` | 5090 / 369 | 17 / 487 | 6295 | 7 / 1 | 0 / 0 | 0 |
| `build/gatekeeper-build` | 4306 / 316 | 16 / 567 | 3729 | 5 / 1 | 0 / 0 | 0 |
| `review/gatekeeper-code` | 4094 / 294 | 15 / 554 | 3668 | 5 / 1 | 0 / 0 | 0 |

All four frontmatters parse; names and descriptions satisfy the catalog limits. Every bundled reference/script is reachable from its SKILL.md or linked reference, and all reference files over 100 lines have a Contents section. Generated run paths and hypothetical product files in examples are not treated as missing catalog resources.

## Scorecard — gatekeeper-admiral

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded. |
| 2 | Scope & intent alignment | 10/10 | Body implements the named gate; specialist work remains owned by its pipeline. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, repair and verification fields are concrete. |
| 4 | Writing style | 9/10 | F-02: one second-person voice slip in the boundary evidence reference. |
| 5 | Progressive disclosure | 7/10 | F-01: multiple long reference sections remain inline. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver boundaries. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence and held cycles are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts and explicit user reopen are specified. |
| 9 | Structure & readability | 10/10 | Headings and workflow sequence are navigable. |
| 10 | Documentation & metadata | 10/10 | Versions, tools, reference pointers, script docstrings and shared dependencies are documented. |
| | **Total** | **96/100** | |

## Scorecard — design/gatekeeper-design

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded. |
| 2 | Scope & intent alignment | 10/10 | Body implements the named gate; specialist work remains owned by its pipeline. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, repair and verification fields are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no remaining voice issue in this package. |
| 5 | Progressive disclosure | 7/10 | F-01: multiple long reference sections remain inline. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver boundaries. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence and held cycles are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts and explicit user reopen are specified. |
| 9 | Structure & readability | 10/10 | Headings and workflow sequence are navigable. |
| 10 | Documentation & metadata | 10/10 | Versions, tools, reference pointers, script docstrings and shared dependencies are documented. |
| | **Total** | **97/100** | |

## Scorecard — build/gatekeeper-build

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded. |
| 2 | Scope & intent alignment | 10/10 | Body implements the named gate; specialist work remains owned by its pipeline. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, repair and verification fields are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no remaining voice issue in this package. |
| 5 | Progressive disclosure | 7/10 | F-01: multiple long reference sections remain inline. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver boundaries. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence and held cycles are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts and explicit user reopen are specified. |
| 9 | Structure & readability | 10/10 | Headings and workflow sequence are navigable. |
| 10 | Documentation & metadata | 10/10 | Versions, tools, reference pointers, script docstrings and shared dependencies are documented. |
| | **Total** | **97/100** | |

## Scorecard — review/gatekeeper-code

| # | Dimension | Score | Evidence / deduction |
| --- | --- | ---: | --- |
| 1 | Trigger description | 10/10 | Concrete boundary and routing triggers; adjacent phase gates excluded. |
| 2 | Scope & intent alignment | 10/10 | Body implements the named gate; specialist work remains owned by its pipeline. |
| 3 | Content depth | 10/10 | Commands, keys, owners, typed records, repair and verification fields are concrete. |
| 4 | Writing style | 10/10 | Imperative instructions with reasons; no remaining voice issue in this package. |
| 5 | Progressive disclosure | 7/10 | F-01: multiple long reference sections remain inline. |
| 6 | Examples & references | 10/10 | Routed examples cover approve, revise, escalation and waiver boundaries. |
| 7 | Edge-case coverage | 10/10 | Malformed inputs, unavailable engines, stale evidence and held cycles are covered. |
| 8 | Security & robustness | 10/10 | Contained inputs, hash checks, fail-loud verdicts and explicit user reopen are specified. |
| 9 | Structure & readability | 10/10 | Headings and workflow sequence are navigable. |
| 10 | Documentation & metadata | 10/10 | Versions, tools, reference pointers, script docstrings and shared dependencies are documented. |
| | **Total** | **97/100** | |

## Residual rubric findings

### F-01 — Detailed reference material still dominates the skill bodies

- Dimension: D5 — Progressive disclosure, **−3 for each of the four packages** (the rubric ladder for multiple body sections belonging in references).
- Severity: Major authoring finding; pre-existing.
- Evidence:
  - `skills/gatekeeper-admiral/SKILL.md:73` and `skills/gatekeeper-admiral/SKILL.md:147`: the full boundary/owner material and several hundred words of validator/type detail remain in the body even though bundled `references/boundary-evidence.md` and `references/workflow.md` already carry that detail. Body size: 4700 words.
  - `skills/design/gatekeeper-design/SKILL.md:71` and `skills/design/gatekeeper-design/SKILL.md:162`: the full boundary/owner material and several hundred words of validator/type detail remain in the body even though bundled `references/boundary-evidence.md` and `references/workflow.md` already carry that detail. Body size: 5090 words.
  - `skills/build/gatekeeper-build/SKILL.md:67` and `skills/build/gatekeeper-build/SKILL.md:103`: the full boundary/owner material and several hundred words of validator/type detail remain in the body even though bundled `references/boundary-evidence.md` and `references/workflow.md` already carry that detail. Body size: 4306 words.
  - `skills/review/gatekeeper-code/SKILL.md:68` and `skills/review/gatekeeper-code/SKILL.md:103`: the full boundary/owner material and several hundred words of validator/type detail remain in the body even though bundled `references/boundary-evidence.md` and `references/workflow.md` already carry that detail. Body size: 4094 words.
- Fix: retain gate classification, decision rules, final judgment command, escalation behavior and short resource pointers in SKILL.md; move extended per-key tables and validator explanations into the existing references. Preserve the six required execution-contract clauses and drift-tested tables if their comparators still require them. Refactor those comparators deliberately if moving the tables.
- Impact: D5 can rise from 7 to 10 per package. This finding is not counted again in D9 or D10.

### F-02 — One reference switches to second-person voice

- Dimension: D4 — Writing style, **−1 for gatekeeper-admiral only**.
- Severity: Minor; pre-existing.
- Evidence: `skills/gatekeeper-admiral/references/boundary-evidence.md:66`: “Whether the recorded actor truly confirmed is still your judgement”.
- Fix: write “Whether the recorded actor truly confirmed remains the gatekeeper’s judgment.”
- Impact: D4 rises from 9 to 10 for gatekeeper-admiral.

## Change-focused behavioral audit

The five requested behavior changes are represented in the final controls:

| Requirement | Final evidence | Enforcement boundary |
| --- | --- | --- |
| Third consecutive REVISE always goes to user | `skills/harness/gatekeeper/_gatecycle.py:95` and `skills/harness/gatekeeper/_gatecycle.py:105` | Durable per-gate streaks/shared budget; deduplicated unchanged retries; same-revision fingerprint drift fails; hold survives approval retry; new user-decision reference required to reopen. |
| Review specialists execute at one producing gate | `skills/pipelines.yaml:40` and `skills/contracts/review-discipline.md:38` | Placement is validated; runtime report reuse remains an explicit orchestration duty. |
| Complete actionable REVISE feedback | `skills/harness/gatekeeper/check.py:1830` | Required blocking fields and owner-grouped full action records are machine-checked; their substantive correctness remains judgment. |
| Follow-ups run changes and affected dependents | `skills/contracts/review-discipline.md:89` and `tools/run-audit/run_audit.py:419` | Scoped test/probe selection is an orchestration duty; audit selectors restrict actual reads/hashes to selected run/phase/artifacts. Cheap mechanical manifest checks remain whole-package. |
| Intake controls scope | `skills/harness/gatekeeper/check.py:1767` and `skills/contracts/review-discipline.md:17` | Judgments bind hashed Intake, canonical inside a run; cited decision/acceptance ids must be table rows. Detecting semantic conflict with Intake still requires gatekeeper reasoning. |

Resolved during this review: misleading all-ten-gates invocation wording; manual-validation fallback messages; mechanical pre-check overwrites of semantic records/history; whole-text rather than table-row decision citations; same-revision drift without --prior; age-only rejection of unchanged reports; stateless-verdict wording; missing shared-cycle packaging notes; and stale evidence-count/security-seed/upstream-verdict examples. These resolved items are not deductions in the final scorecards.

## Harness-doctrine audit

Applied `skills/harness-doctrine.md` §5 to the new runtime intervention.

| Duty | Assessment |
| --- | --- |
| Named lifecycle layer | Layer 4 is stated in `contracts/review-discipline.md` under Enforcement and limits. |
| Earliest enforceable placement | The cycle cap is applied to a validated judgment at persistence before publishing a final verdict. |
| Preserve residual reasoning | Code validates source binding, feedback shape and trajectory state; it does not claim to decide whether a proposed finding is substantively correct. |
| Inert on the correct case | Mechanical self-checks do not count; a first clean approval proceeds; exact retries do not consume another round. |
| Regression note | The contract describes regression coverage; `test_gate_cycles.py` exercises cap, resume, same-revision drift, hold and reopening. |

No unresolved change-focused correctness blocker was found in the final reviewed controls. This statement does not certify all existing behavior in the repository.

## Evaluation limits

Automated scenario evidence supplied by this implementation run: the affected gate regression run reports 342 tests, zero failures, six skips; focused audits and contract checks also pass. These are deterministic regression/scenario results. No live-model task runs, host-registration run, paid trigger-routing benchmark, or real end-to-end model behavioral evaluation was run for this iteration. The rubric measures authored instructions and supporting code; it is not a substitute for those evaluations.

## Link report

The companion `rubric-link-report.md` records resolved catalog-resource pointers, including shared dependencies. It excludes generated run artifacts, product-example files, and illustrative paths. All 22 bundled source/reference files were inspected; no bundled orphan or broken catalog-resource pointer was found.
