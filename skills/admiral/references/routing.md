# Routing Reference

The full request-to-route map. `../SKILL.md` carries the mode table and the
annotated Delegation Surface, which name every owner and closing boundary; this
file states which request shape reaches which pipeline and where each one closes,
so neither document repeats the other.

`../../pipelines.yaml` is the authoritative stage map. The prose here elaborates
it and must not contradict it; where they disagree, the file wins.

## Contents

1. Request to route to closing boundary
2. Where frontend and UI work lives

## Request To Route To Closing Boundary

| Request | Route | Closes at |
| --- | --- | --- |
| Design, build, and review end to end | `design/commander`, then `build/build-management`, then `review/code-chief` | `design-to-build`, `build-to-review`, `review-to-delivery` |
| Design only, or continue from an approved design | the earliest incomplete boundary | as above |
| Redesign an existing UI: map it, grill taste, compare four living design systems | `design/redesign`; the chosen variant then enters `design/commander` | `redesign-review` |
| Security audit, threat model, hardening, or remediation | `review/cso` driving `security-review` and `mr-robot` | `security-review` |
| Unknown failure mechanism | `investigate`; its bounded fix path returns to the owning phase | `investigation-review` |
| Product testing with recorded evidence | `qa`; a report-only run runs the sweep through `qa-only`, but `qa` remains the `qa-review` submitter and carries the `fixes_applied` applicability record | `qa-review` |
| Skill or coordinated team creation | `skill-maker` | `skill-maker-to-delivery` |
| Release preparation and rollout | `ship`, then `land-and-deploy` after a fresh human go decision | `deploy-readiness` |
| Explicit Taste management | `taste`; ordinary design only consumes its effective-profile handoff | `taste-review` |
| Checkpoint or resume | `session-memory` plus the earliest incomplete owner | the pending boundary |

## Where Frontend And UI Work Lives

Frontend and UI work stays inside the design and review pipelines: `architect`
owns the design system, `design-qa` and `frontier` own its review evidence. There
is no separate frontend pipeline. `../../pipelines.yaml` is the authoritative stage
map; the prose here elaborates it and must not contradict it.
