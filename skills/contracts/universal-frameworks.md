# Universal Frameworks

## Responsibility

These are cross-cutting invariants for delivery work. They point to the
specialist references that define the detailed practice instead of duplicating
it here.

| Framework | Minimum invariant | Specialized reference |
|-----------|-------------------|-----------------------|
| Context-first build | Read the repository, neighboring contracts, constraints, and current evidence before choosing an implementation. | [bob-the-builder](../build/bob-the-builder/SKILL.md) and [researcher](../design/researcher/SKILL.md) |
| Grilled intake | Resolve every load-bearing branch, record rejected options and deferrals with reopen triggers, and hash the log as the decisions artifact. | [grill-me-doctrine](../grill-me-doctrine.md) |
| Systematic debugging | Reproduce the failure, reduce it to one variable, identify the mechanism, then fix the class and rerun the failing proof. | [investigate](../investigate/SKILL.md) and [debugger](../build/debugger/SKILL.md) |
| Stack discipline | Lock the runtime, framework, and interface versions at design time against the registry; a new dependency is a recorded decision, not a side effect. | [tech-stacks/registry.yaml](../tech-stacks/registry.yaml) and `scripts/check_runtime.py --detect-project` |
| Design system | One component template, one UI/UX handoff, six responsive tiers, accessibility as correctness. | [design-doctrine](../design-doctrine.md) and [architect](../design/architect/SKILL.md) |
| Taste | Apply user-authored or explicitly confirmed presentation and interaction preferences with scoped provenance and deterministic project-over-global resolution; never override mandatory requirements. | [taste-doctrine](../taste-doctrine.md) |
| Deployment readiness | Verify configuration, artifacts, permissions, target assumptions, rollback, and runtime evidence before an external release. | [ship](../release-and-deployment/ship/SKILL.md) and [health-check](../build/health-check/SKILL.md) |
| Adversarial review | Search for failure paths, regressions, missing evidence, and interface risk; grade observed findings separately from inference. | [code-chief](../review/code-chief/SKILL.md) and [bug-review](../review/bug-review/SKILL.md) |
| Security denial-path tests | Prove that unauthorized, malformed, replayed, expired, and over-broad requests are denied at the trust boundary. | [mr-robot](../review/mr-robot/SKILL.md) and [security-review](../review/security-review/SKILL.md) |
| Measured optimization | Baseline, bound, one mechanism at a time, and a preserved threshold. | [performance-doctrine](../performance-doctrine.md) and [benchmark](../testing-and-qa/benchmark/SKILL.md) |
| Evidence-first reporting | Put claims, gaps, proof, hashes, scope, and revision beside the result; never turn an unavailable check into approval. | [evidence-standards](evidence-standards.md) and [gatekeeper-admiral](../gatekeeper-admiral/SKILL.md) |

## Use

Apply the smallest relevant set, record which framework was used, and link its
evidence in the delivery or review record. A specialist reference may add
requirements for its domain, but it cannot weaken the evidence or one-writer
rules in the canonical contracts.
