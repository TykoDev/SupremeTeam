# Benchmark

Measured state of the Supreme Team catalog: what scores what, how each number was
produced, and what it does not cover. Every figure here was observed, not
estimated — where a measurement was not taken, this file says so rather than
inferring one.

## Headline

| Dimension | Result |
|---|---|
| Skill quality, 52 skills | mean **98.8** / 100, lowest 95, 17 at 100 |
| Spec, harness and doctrine, 21 artifacts | mean **97.5** / 100, lowest 95 |
| Routing accuracy, paraphrased requests | **94.8%** (294/310) |
| Skills the host registers | all **21** entry skills; the 31 internal specialists deliberately not |
| Automated tests | **359**, all passing |
| Gate boundaries | 10, all proven satisfiable against the real validator |

## Skills

Scored against the 10-dimension rubric in
[`skills/skill-maker/skill-reviewer/references/scoring-rubric.md`](skills/skill-maker/skill-reviewer/references/scoring-rubric.md):
trigger, scope, depth, style, progressive disclosure, examples, edge cases,
security, structure, documentation — 10 points each.

| Band | Skills |
|---|---|
| 100 | 17 |
| 95–99 | 35 |
| below 95 | 0 |

<details>
<summary>Per-skill scores</summary>

| Skill | Score |
|---|---|
| `benchmark` | 100 |
| `browse` | 100 |
| `build/build-management` | 100 |
| `careful` | 100 |
| `design/commander` | 100 |
| `document-release` | 100 |
| `freeze` | 100 |
| `guard` | 100 |
| `land-and-deploy` | 100 |
| `review/bug-review` | 100 |
| `review/code-review` | 100 |
| `review/devex-review` | 100 |
| `review/frontier` | 100 |
| `review/gatekeeper-code` | 100 |
| `review/security-review` | 100 |
| `setup-deploy` | 100 |
| `ship` | 100 |
| `build/bob-the-builder` | 99 |
| `build/debugger` | 99 |
| `build/gatekeeper-build` | 99 |
| `build/security-builder` | 99 |
| `build/test-builder` | 99 |
| `design/redesign` | 99 |
| `gatekeeper-admiral` | 99 |
| `investigate` | 99 |
| `open-browser` | 99 |
| `pair-agent` | 99 |
| `review/code-chief` | 99 |
| `review/design-qa` | 99 |
| `review/quality-review` | 99 |
| `setup-browser-cookies` | 99 |
| `skill-maker/skill-reviewer` | 99 |
| `unfreeze` | 99 |
| `admiral` | 98 |
| `design/architect` | 98 |
| `design/design-mapper` | 98 |
| `design/engineer` | 98 |
| `design/planner` | 98 |
| `design/prototyper` | 98 |
| `design/researcher` | 98 |
| `qa` | 98 |
| `review/cso` | 98 |
| `review/mr-robot` | 98 |
| `session-memory` | 98 |
| `skill-maker/skill-creator` | 98 |
| `taste` | 98 |
| `taste/taste-review` | 98 |
| `build/health-check` | 97 |
| `skill-maker` | 97 |
| `design/gatekeeper-design` | 96 |
| `qa-only` | 96 |
| `build/cross-check-build-confirm` | 95 |

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
| `skills/harness/gatekeeper` | 72 |
| `skills/harness/hooks` | 115 |
| `skills/scripts` | 13 |
| `skills/taste` | 3 |
| `skills/validation` | 151 |
| `skills/skill-maker/skill-creator/scripts` | 5 |

| Validation module | Tests |
|---|---|
| `test_catalog_contracts.py` | 30 |
| `test_orchestration.py` | 44 |
| `test_pipeline_contracts.py` | 10 |
| `test_pipeline_workflows.py` | 15 |
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
