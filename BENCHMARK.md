# Benchmark

Scores are model judgements against a written rubric. Routing is a paid model
run. CI re-runs neither. Open defects: [docs/quality-audit.md](docs/quality-audit.md).

| Measure | Result |
|---|---|
| Skills (53) | mean **98.6**, lowest 93, 18 at 100 |
| Spec and doctrine (22) | mean **95.0**, lowest 82 |
| Routing accuracy | **89.4%** (278/311) |
| Host registration | 22 of 22 root skills |
| Tests | **2,353** pass across 7 suites |
| Gate boundaries | 10 of 10 satisfiable |

## Skills

Rubric: [scoring-rubric.md](skills/skill-maker/skill-reviewer/references/scoring-rubric.md),
ten dimensions, 10 points each. Every deduction cites file and line.

| Score | Skills |
|---:|---|
| 100 | `audit-improve`, `benchmark`, `browse`, `build/build-management`, `build/gatekeeper-build`, `design/planner`, `document-release`, `freeze`, `gatekeeper-admiral`, `guard`, `land-and-deploy`, `open-browser`, `pair-agent`, `review/code-review`, `review/devex-review`, `review/frontier`, `session-memory`, `setup-deploy` |
| 99 | `build/bob-the-builder`, `build/cross-check-build-confirm`, `build/security-builder`, `careful`, `design/architect`, `design/commander`, `design/design-mapper`, `design/engineer`, `design/redesign`, `investigate`, `qa`, `review/bug-review`, `review/code-chief`, `setup-browser-cookies`, `ship`, `taste` |
| 98 | `build/health-check`, `build/test-builder`, `design/prototyper`, `review/cso`, `review/design-qa`, `review/quality-review`, `review/security-review`, `skill-maker/skill-reviewer`, `taste/taste-review`, `unfreeze` |
| 97 | `build/debugger`, `qa-only`, `review/gatekeeper-code`, `review/mr-robot`, `skill-maker/skill-creator` |
| 96 | `skill-maker` |
| 95 | `design/gatekeeper-design`, `design/researcher` |
| 93 | `admiral` |

## Spec and doctrine

Six dimensions: authority, enforcement accuracy, internal and cross consistency,
completeness, actionability.

| Score | Artifacts |
|---:|---|
| 100 | `contracts/handoff-templates.md` |
| 99 | `execution-contract.md`, `grill-me-doctrine.md`, manifests |
| 98 | `contracts/evidence-standards.md`, `ownership.yaml`, `performance-doctrine.md`, `save-ownership.yaml` |
| 97 | `contracts/delivery-template.md`, `contracts/responsibility-matrix.md`, `design-doctrine.md`, `routing-doctrine.md` |
| 96 | `save-protocol.md`, `taste-doctrine.md` |
| 95 | `contracts/universal-frameworks.md`, `harness-doctrine.md` |
| 93 | `harness/gatekeeper` |
| 91 | `gates.yaml`, `pipelines.yaml` |
| 89 | `harness/hooks` |
| 84 | `mcp-tools.md` |
| 82 | `contracts/workflow-protocol.md` |

## Routing

[`trigger_eval.py`](skills/validation/trigger_eval.py) shows a real model all 53
descriptions; queries are paraphrased so they don't echo descriptions.

Top misroutes:

- Build specialists asked cold go to `admiral` (5).
- Design leads confuse each other (5).
- `build/debugger` goes to `investigate` (4).

## Tests

| Suite | Tests | Command |
|---|---:|---|
| hooks | 971 | `python -m unittest discover -s skills/harness/hooks -p "test_*.py"` |
| gates | 271 | `python -m unittest discover -s skills/harness/gatekeeper -p "test_*.py"` |
| validation | 262 | `python -m unittest discover -s skills/validation -p "test_*.py"` |
| scripts | 386 | `python -m unittest discover -s skills/scripts -p "test_*.py"` |
| taste | 214 | `python -m unittest discover -s skills/taste -p "test_*.py"` |
| installers | 85 | `python -m unittest discover -s scripts -p "test_*.py"` |
| skill_creator | 164 | `python -m unittest discover -s skills/skill-maker/skill-creator -p "test_*.py"` |

Validators: `validate_manifests.py`, `check_runtime.py`, `package_check.py --root .`
all pass.

## Not measured

- Behaviour after a skill is selected.
- End-to-end task success in real sessions.
- Hook firing on a given host.
- Routing variance between runs.

## Reproduce

```bash
python skills/validation/run_eval.py --registration
python skills/validation/trigger_eval.py --mode both --paraphrase --per-skill 4
```

The routing run costs about $7; `--pilot` prices one batch first.
