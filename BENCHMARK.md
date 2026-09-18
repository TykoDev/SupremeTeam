# Benchmark

Measured state of the Supreme Team catalog: what scores what, how each number was
produced, and what it does not cover. Every figure here was observed, not
estimated — where a measurement was not taken, this file says so rather than
inferring one.

## Headline

| Dimension | Result |
|---|---|
| Skill quality, 52 skills | mean **99.4** / 100, lowest 97, 31 at 100 |
| Spec, harness and doctrine, 21 artifacts | mean **97.5** / 100, lowest 95 |
| Routing accuracy, paraphrased requests | **94.8%** (294/310) |
| Skills the host registers | all **21** entry skills; the 31 internal specialists deliberately not |
| Automated tests | **405**, all passing (2 skipped as designed) |
| Gate boundaries | 10, all proven satisfiable against the real validator |

## Skills

Scored against the 10-dimension rubric in
[`skills/skill-maker/skill-reviewer/references/scoring-rubric.md`](skills/skill-maker/skill-reviewer/references/scoring-rubric.md):
trigger, scope, depth, style, progressive disclosure, examples, edge cases,
security, structure, documentation — 10 points each.

| Band | Skills |
|---|---|
| 100 | 31 |
| 95–99 | 21 |
| below 95 | 0 |

<details>
<summary>Per-skill scores</summary>

| Skill | Score |
|---|---|
| `benchmark` | 100 |
| `browse` | 100 |
| `build/bob-the-builder` | 100 |
| `build/build-management` | 100 |
| `build/cross-check-build-confirm` | 100 |
| `build/debugger` | 100 |
| `build/health-check` | 100 |
| `build/security-builder` | 100 |
| `build/test-builder` | 100 |
| `careful` | 100 |
| `design/gatekeeper-design` | 100 |
| `design/planner` | 100 |
| `document-release` | 100 |
| `freeze` | 100 |
| `gatekeeper-admiral` | 100 |
| `guard` | 100 |
| `land-and-deploy` | 100 |
| `open-browser` | 100 |
| `pair-agent` | 100 |
| `review/bug-review` | 100 |
| `review/code-chief` | 100 |
| `review/code-review` | 100 |
| `review/cso` | 100 |
| `review/design-qa` | 100 |
| `review/devex-review` | 100 |
| `review/gatekeeper-code` | 100 |
| `review/mr-robot` | 100 |
| `review/quality-review` | 100 |
| `setup-browser-cookies` | 100 |
| `setup-deploy` | 100 |
| `ship` | 100 |
| `build/gatekeeper-build` | 99 |
| `design/architect` | 99 |
| `design/commander` | 99 |
| `design/design-mapper` | 99 |
| `design/researcher` | 99 |
| `qa` | 99 |
| `review/frontier` | 99 |
| `session-memory` | 99 |
| `skill-maker/skill-creator` | 99 |
| `skill-maker/skill-reviewer` | 99 |
| `taste/taste-review` | 99 |
| `unfreeze` | 99 |
| `admiral` | 98 |
| `design/prototyper` | 98 |
| `design/redesign` | 98 |
| `investigate` | 98 |
| `qa-only` | 98 |
| `review/security-review` | 98 |
| `ship` | 98 |
| `taste` | 98 |
| `design/engineer` | 97 |

</details>

<details>
<summary>Deductions cited in the 2026-09-18 round — 26 findings across 21 skills</summary>

Every line was checked against the cited source before it cost a point; 31 skills scored clean.

| Skill | Finding |
|---|---|
| `design/engineer` | D3 −3: step 1 requires a `stack-lock` that the `pipelines.yaml` stage order never permits to exist at spec time — a literal reading deadlocks (SKILL.md:23-24,103; references/workflow.md:22-31 vs pipelines.yaml:62-72) |
| `admiral` | D3 −2: three Required Contracts order audit-trail appends `save_run.py` never emits; the documented `--set` state-field path is the sanctioned mechanism (references/contracts.md:26-35 vs harness/hooks/save_run.py) |
| `taste` | D3 −2: failure-modes claims import validates `schema_version` and named exit codes; `taste_prefs.py` checks none of it (SKILL.md:165; references/workflow.md:66-67 vs taste_prefs.py:294-307) |
| `ship` | D3 −2: gate-submission reference claims schema 2 requires `submission_id` and a checker message that do not exist (references/gate-submission.md:56-58 vs gates.yaml, _gatecheck.py) |
| `build/gatekeeper-build` | D3 −1: worked example asserts traversal detection the skill's own workflow reference disclaims (references/examples.md:108 vs references/workflow.md:18) |
| `design/commander` | D10 −1: `intake-brief.yaml` `required_contracts` do not mirror SKILL.md § Required Contracts (intake-brief.yaml:51-55 vs SKILL.md:126-136) |
| `design/redesign` | D6 −1 + D10 −1: no worked merge-decision example; the mirror comment cites the wrong section (references/examples.md; intake-brief.yaml:74) |
| `design/architect` | D2 −1: claims an `implementation` deliverable `ownership.yaml` assigns to bob-the-builder (SKILL.md:82 vs ownership.yaml:176) |
| `design/design-mapper` | D3 −1: parity-marker contract contradicts `check_parity.py`'s union rule (references/workflow.md:95 vs check_parity.py:183) |
| `design/prototyper` | D3 −1 + D10 −1: the same implementation-ownership collision; self-check scratch pointed at a path class owned by `harness-tests` (references/workflow.md:208; SKILL.md:222 vs save-ownership.yaml) |
| `design/researcher` | D3 −1: claims the first design stage; `intake-grilling` precedes it (SKILL.md:20-21 vs pipelines.yaml:37-45) |
| `investigate` | D9 −2 (two findings): examples.md Contents omits Example 0; the write-trigger table names a verdict file no phase gatekeeper writes (references/examples.md:8-15; references/workflow.md:170) |
| `qa` | D5 −1: gate-package.md Contents omits the Evidence Keys section SKILL.md calls authoritative (references/gate-package.md:8-15 vs SKILL.md:99) |
| `qa-only` | D8 −1 + D9 −1: standalone evidence writes into a skill-maker-owned path class; the bundle shape disagrees between SKILL.md and read-only-boundary.md (SKILL.md:54 vs save-ownership.yaml:222-231, output_paths.py:113-114) |
| `session-memory` | D3 −1: cites a proper noun ("LIFE-HARNESS") that appears nowhere else in the repo (SKILL.md:123 vs harness-doctrine.md:87) |
| `skill-maker/skill-creator` | D9 −1: the trigger list omits the Optimize mode the description names as a trigger (SKILL.md:3-11 vs 69-75) |
| `skill-maker/skill-reviewer` | D3 −1: says skill-maker owns the `review` stage; `pipelines.yaml` assigns it to skill-reviewer (SKILL.md:54-55 vs pipelines.yaml:410-413) |
| `taste/taste-review` | D3 −1: overstates what check.py rejects for an omitted or filled `policy_check` (SKILL.md:100 vs check.py:340-366) |
| `unfreeze` | D3 −1: claims approver release for records `guard_state.py` writes without an approvers field (SKILL.md:49 vs guard_state.py:231-238) |
| `review/security-review` | D5 −1 + D8 −1: a 103-line examples.md without a TOC; the read-only execution-boundary contract every sibling lens carries is absent (references/examples.md; SKILL.md:174-180) |
| `review/frontier` | D9 −1: the workflow Contents mis-numbers its last three entries (references/workflow.md:12-15) |

</details>

## Spec, harness and doctrine

Scored against six contract dimensions — authority, enforcement, internal
consistency, cross-consistency, completeness, actionability — normalised to 100.
The enforcement dimension asks one question: does this document state accurately
what is machine-checked and what is judgement?

<details>
<summary>Per-artifact scores</summary>

| Artifact | Score |
|---|---|
| `contracts/delivery-template.md` | 98 |
| `contracts/evidence-standards.md` | 98 |
| `contracts/handoff-templates.md` | 98 |
| `contracts/universal-frameworks.md` | 98 |
| `contracts/workflow-protocol.md` | 98 |
| `design-doctrine.md` | 98 |
| `execution-contract.md` | 98 |
| `gates.yaml` | 98 |
| `grill-me-doctrine.md` | 98 |
| `harness-doctrine.md` | 98 |
| `harness/gatekeeper` | 98 |
| `harness/hooks` | 98 |
| `performance-doctrine.md` | 98 |
| `pipelines.yaml` | 98 |
| `save-ownership.yaml` | 98 |
| `taste-doctrine.md` | 98 |
| `ownership.yaml` | 97 |
| `save-protocol.md` | 97 |
| `contracts/responsibility-matrix.md` | 95 |
| `routing-doctrine.md` | 95 |
| `team+runtime+package-manifest` | 95 |

</details>

## Routing

The catalog is description-routed: a model picks one skill out of 52 by reading
descriptions. That decision is measured by
[`skills/validation/trigger_eval.py`](skills/validation/trigger_eval.py), which
puts the whole roster in front of a real model and scores which skill wins.

Accuracy moved from 84.0% to **94.8%** across nine measured rounds.

| Round | What changed | Queries | Correct | Accuracy |
|---|---|---|---|---|
| 1 | First paraphrased measurement | 175 | 147/175 | 84.0% |
| 2 | Eight descriptions rewritten | 174 | 150/174 | 86.2% |
| 3 | Trigger surface expanded, corpus nearly doubled | 310 | 283/310 | 91.3% |
| 4 | Gate pair separated; owner-credit scoring corrected | 310 | 290/310 | 93.5% |
| 5 | Guardrail, performance and gate discriminators | 310 | 291/310 | 93.9% |
| 6 | Lenses cede cold phrasings to their owner | 310 | 291/310 | 93.9% |
| 7 | 15 skills flattened so the host registers them | 310 | 277/310 | 89.4% |
| 8 | Collisions the path prefix had masked | 310 | 288/310 | 92.9% |
| 9 | Regression from the previous round corrected | 310 | 294/310 | 94.8% |

Round 7 is worth reading twice: accuracy *fell* when the directly-invokable
skills moved to the catalog root. The path prefix had been carrying the
discrimination — `safety-guardrails/guard` against `safety-guardrails/careful` —
and the host never displayed it, because those skills were not registered at all.
Every earlier score was measured against a roster showing prefixes no user would
ever see. The lower number is the truer one.

### Host registration

Claude Code discovers skills at `.claude/skills/<name>/SKILL.md`, one level deep.
The layout follows the routing classes: the 21 skills a user may reach
directly sit at the catalog root and register; the 31 internal specialists
stay nested, where the loader does not offer them. That is
"reached only through the owning sub-orchestrator" expressed in the filesystem.

Nesting costs those specialists nothing, because delegation never used the skill
loader — `admiral` holds `Read`, `Grep` and `Glob` and no `Skill` tool, and
reaches specialists by path.

Measured by [`skills/validation/run_eval.py`](skills/validation/run_eval.py)
`--registration`, which installs the tree into a scratch project and diffs the
host's reported skill list against a control run with no catalog installed. The
control matters: the host ships skills of its own, and a bare name match cannot
tell the catalog's `code-review` from the one Claude Code bundles.

On the machine this was measured on, 20 of the 21
registered — `skill-maker` was shadowed by a stale 40-skill copy in
`~/.claude/skills` that predates the current naming. That is an environment
artifact, not a catalog defect, and a reinstall clears it.

## Pipelines and review gates

10 pipelines close at 10 gate boundaries carrying 71 required
evidence keys. 4 pipelines carry an explicit phase-gate stage; the rest are
judged once, by the cross-stage gatekeeper.

Phase gatekeepers: `gatekeeper-design`, `gatekeeper-build`, `gatekeeper-code`. Cross-stage: `gatekeeper-admiral`.

[`test_pipeline_workflows.py`](skills/validation/test_pipeline_workflows.py)
does not read the spec and compare it — it builds a package per boundary with
real files and real digests and submits it to `check.py`. All 10
boundaries are proven satisfiable, which is not implied by their being
internally consistent: a boundary can require a key that is also barred from
fallback and produced by no stage, and every document involved would still read
correctly. Six refusal tests follow, because a generator that only produces
passing packages proves the generator works, not the gate. One test walks a
complete run — open, checkpoint per stage, submit, verdict, close — and checks
the audit trail kept an event per stage.

## Orchestration

[`test_orchestration.py`](skills/validation/test_orchestration.py) checks the
delegation graph: every delegation target resolves to a real skill, every
internal specialist's entry routing names the owner that actually delegates to
it, the graph is acyclic, verdict vocabulary admits no fourth token, pipeline
owners hold an orchestrator role, and every stated revision cap matches
`gates.yaml`. It also compares `gates.yaml` `guards` strings against the state
machine in `contracts/workflow-protocol.md`, and pipeline `when` and `fan_out`
values against the skills and gate parameters they depend on.

## Tests

| Suite | Tests |
|---|---|
| `skills/harness/gatekeeper` | 93 (1 skipped) |
| `skills/harness/hooks` | 128 |
| `skills/scripts` | 24 |
| `skills/taste` | 3 |
| `skills/validation` | 152 (1 skipped) |
| `skills/skill-maker/skill-creator/scripts` | 5 |

| Validation module | Tests |
|---|---|
| `test_catalog_contracts.py` | 30 |
| `test_orchestration.py` | 44 |
| `test_pipeline_contracts.py` | 10 |
| `test_pipeline_workflows.py` | 16 (1 skipped) |
| `test_save_contracts.py` | 17 |
| `test_trigger_routing.py` | 35 |

Run them all:

```bash
for d in skills/harness/gatekeeper skills/harness/hooks skills/scripts \
         skills/taste skills/validation skills/skill-maker/skill-creator/scripts; do
  python -m unittest discover -s "$d" -p "test_*.py"
done
python skills/scripts/validate_manifests.py
python skills/scripts/package_check.py --root .
```

## Methodology

### Scoring

Rubric scores are model judgements against a written rubric, not machine output.
Each skill was read against all ten dimensions with findings cited to a file and
line, and a deduction was only taken where the claim could be checked against its
source — `gates.yaml`, `ownership.yaml`, `pipelines.yaml`, the harness code, or
the named test. A document asserting a guarantee nothing enforces is a finding;
so is a document denying a guarantee it has, which is the worse direction because
it invites deleting test-enforced content.

Scores are therefore reproducible in method but not deterministic in value. They
are useful as a relative signal and a defect-finding instrument, not as a
precision metric.

The 2026-09-18 refresh re-scored all 52 skills with ten independent parallel
scorers working from this rubric. It produced 26 deductions across 21 skills,
each cited in the Skills section above; the citations, not the totals, are the
output that matters.

### Routing measurement

The corpus is drawn from the catalog, never invented, in three forms of rising
difficulty:

- **Advertised** — each skill's own `## Use This Skill When` phrasings.
- **Routed** — phrases lifted from a *sibling's* "Route elsewhere" sentence,
  where the catalog itself declares which skill should win.
- **Paraphrased** — either corpus restated by a model as a developer would
  actually type it, with the catalog's distinctive terms removed.

Only the paraphrased score is quoted. The first two both reached 100%, and both
are close to worthless: the winning description literally contains the query's
words, so the match is nearly free. Rewriting the same queries into a user's own
vocabulary dropped accuracy by sixteen points, which is the difference between
measuring lexical echo and measuring discrimination.

Two scoring rules are applied and both are visible in the report. A miss is
credited when the chosen skill is the *declared delegating owner* of the expected
one, read from that skill's own entry routing — routing a cold request to the
owner is the documented path, so scoring it wrong measured the catalog against
ground truth its own doctrine contradicts. And every result keeps both the
original trigger and the text actually asked, because a paraphrase can drift far
enough that the miss belongs to the rewrite.

### What is not measured

- **Agentic behaviour after selection.** The eval measures which skill a model
  picks, not whether it then behaves correctly. A skill can be picked right and
  run wrong.
- **Real sessions end to end.** `run_eval.py` measures registration, not task
  outcomes. A workspace realistic enough to exercise 52 skills does not exist here.
- **Trigger phrasings beyond four per skill.** The corpus takes four; a skill's
  fifth and sixth phrasings are untested.
- **Hook registration on a given host.** The hook behaviour is tested against
  fixtures; whether a particular install has registered it is outside the repo.
- **Stage conditions and delegation at runtime.** `pipelines.yaml` declares
  `when` and `fan_out` values that are now compared against skills and gate
  parameters, but whether a condition ever fires in a real run is judgement.

### Reproducing

```bash
python skills/validation/run_eval.py --registration
python skills/validation/trigger_eval.py --mode both --paraphrase --per-skill 4
```

The routing eval needs network and costs real money — roughly seven dollars per
full run at the time of writing. `--pilot` runs a single batch first so the cost
is known before the run.
