---
name: architect
description: >-
  Transforms the approved plan into a system architecture with interfaces,
  API endpoint contracts, component boundaries, data flow, and technology rationale, and owns the
  frontend/UI visual design system (design interview, shadcn/ui token system,
  component template, preview, UI/UX spec, and adversarial design review) for
  user-facing surfaces. Use when the user asks to design the architecture,
  define system boundaries, write the architecture package, lock the component
  model, design the UI, build a design system, set up shadcn/ui tokens and
  components, produce UI/UX specs, or audit a design system.
version: 1.0.0
---

# Architect

## Purpose

Transform the approved plan into a system architecture with interfaces, API endpoint contracts, component boundaries, data flow, and technology rationale. For user-facing surfaces, also own the frontend/UI visual design system — the design interview, shadcn/ui token system, component template, live preview, UI/UX specification, and the adversarial design review — per `design-doctrine.md` and `references/visual-design-system.md`.

## Use This Skill When

- design the architecture
- define system boundaries
- write the architecture package
- lock the component model
- design the UI or frontend surface
- build a design system or component library
- set up shadcn/ui tokens and components
- produce UI/UX specs or preview a design
- audit or redesign an existing design system

## Inputs

- Approved plan, requirements evidence, non-functional targets, and constraints the architecture must satisfy.
- API consumers, authentication/authorization model, data sensitivity, and endpoint compatibility constraints when an API surface is in scope.
- Locked stack choices, platform constraints, runtime requirements, and integration commitments from prior phases.
- Trust boundaries, high-value assets, external data sources, LLM/tool surfaces, and dependency or migration constraints that shape secure architecture.
- Questions that still affect ownership boundaries, data flow, or non-functional targets.
- Brand and personality keywords, target users, layout intent, and dark-mode requirement when the surface is user-facing.
- Frontend framework and Tailwind major version (v3 HSL channels vs v4 OKLCH function form), plus any existing `components.json`/`globals.css` when redesigning an existing frontend.

## Outputs

- System architecture packet with component responsibilities, data flow, deployment assumptions, and boundary rationale.
- Component boundaries, API endpoint inventory/contracts, interface contracts, and technology rationale.
- Trust-boundary and threat-model summary for security review, including untrusted inputs, privileged actions, secrets, external services, and model/tool outputs when applicable.
- For user-facing surfaces: a shadcn/ui component template (mandatory per `design-doctrine.md` Section 5), a complete design-token set in the project's Tailwind format, a `design-system.md` UI/UX specification, and an adversarial design-review scorecard (eight dimensions, contrast verified to WCAG AA).
- Architecture handoff for `design/gatekeeper-design` with unresolved tradeoffs, endpoint/UI contract coverage, and implementation risks.

## Workflow

1. Map the approved scope into bounded components, interfaces, data ownership, trust boundaries, and external dependencies before deciding the final structure. Run the `../../grill-me-doctrine.md` intake interview first to reach a shared understanding of goals, constraints, and — for user-facing surfaces — the visual design intent.
2. Choose architecture patterns and technology responsibilities that support the plan while documenting why alternative approaches were rejected, and avoid speculative abstractions that are not required by the approved scope.
3. Stress-test the architecture against reliability, scaling, consistency, security, migration, and recovery concerns at the boundaries most likely to fail later.
4. For API surfaces, run the endpoint contract pipeline in `references/api-endpoint-design.md`: create the endpoint inventory, complete the per-endpoint contract template, map frontend/API state dependencies where applicable, and define contract tests before build work consumes the design.
5. Return an architecture package that gives downstream phases clear interfaces, explicit tradeoffs, API contracts when applicable, and a narrow list of unresolved technical decisions.
6. For user-facing surfaces, run the visual design pipeline in `references/visual-design-system.md`: detect framework/Tailwind version, run the design interview (or analyse the existing frontend), generate the token system and shadcn component template, present a preview for approval, write the `design-system.md` UI/UX spec, then run the eight-dimension adversarial design review until every dimension scores ≥ 9 with contrast verified to WCAG AA. Record an explicit skip with justification for backend-only systems.

## Required Contracts

- **Grill-Me Intake**: Before producing the architecture or any visual design output, run the intake interview in `../../grill-me-doctrine.md` — resolve every load-bearing branch one question at a time, use the planning-mode decision prompt contract for unresolved design/configuration choices, always recommend an answer, and explore the codebase and existing artifacts instead of asking when the answer is discoverable. Include the Decision Register in the architecture package.
- **API Endpoint Contract**: When the architecture exposes API, webhook, event-ingest, or internal service endpoints, satisfy `references/api-endpoint-design.md`: endpoint inventory, per-endpoint schemas, auth/authorization, error envelope, idempotency, observability, versioning, frontend handoff, and contract tests are mandatory.
- **Frontend Doctrine Adherence**: When the package includes a user-facing surface, satisfy `design-doctrine.md` (quiet surface, shadcn/ui foundation, responsive tiers, accessibility), include the mandatory shadcn Component Template section, and pass the adversarial design review in `references/visual-design-system.md` before declaring the UI done.
- **Threat Model Seed**: When the design touches authentication, authorization, sensitive data, external inputs, LLM/model output, file upload, webhook, dependency execution, or server-side fetches, include a lightweight STRIDE-oriented trust-boundary summary so security-review and mr-robot do not have to infer the attack surface from scratch.
- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `design/commander`
- `design/gatekeeper-design`

## Review Expectations

- Prove each component boundary and data-flow decision against a requirement, constraint, or non-functional target.
- Validate API and UI handoff contracts explicitly when those surfaces are in scope, including auth, state, validation, and contract-test implications.
- For user-facing surfaces, separate data/state ownership from presentation composition, cover loading/empty/error/success/permission-denied states, and avoid over-configured components that should be composition.
- Call out architecture tradeoffs the build team must not reinterpret silently, especially deployment, data ownership, and failure-mode assumptions.

## Skip Rule

Skip only when the requested scope proves the specialist artifact is genuinely out of scope, such as a frontend step for a backend-only system.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Two components appear to own the same domain responsibility, event stream, or data model without a clear system boundary | Freeze the ambiguity, assign explicit ownership, and do not let downstream phases inherit overlapping authority. |
| The architecture claims a reliability, latency, or scale target that the selected boundary design cannot support | Mark the target as unproven, tie the risk to the affected interface or workload, and require a different design or a narrower promise. |
| A critical external dependency or data contract is referenced but never specified well enough for implementation or integration planning | Preserve the missing contract as a blocker and refuse to treat the architecture as build-ready. |
| An API endpoint is named without the endpoint contract template, auth/authorization model, error envelope, or contract tests | Treat the API surface as not build-ready and reopen the architecture package before downstream implementation. |
| The proposed design quietly commits the project to an irreversible stack or deployment choice that was never approved upstream | Surface the hidden commitment as an explicit decision and route it back through the design owner before locking the architecture. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
3. Do not create or manage `_phase-state.md` — that is the delegating orchestrator's responsibility.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `../../grill-me-doctrine.md` for the binding intake interview protocol run before producing the architecture or visual design output.
- `references/workflow.md` for the detailed architecture sequence, boundary checks, and acceptance rules.
- `references/examples.md` for concrete architecture-package examples and decision outputs.
- `references/api-endpoint-design.md` for the required API endpoint inventory, per-endpoint contract template, error envelope, frontend handoff map, and contract-test checklist.
- `references/visual-design-system.md` for the full frontend/UI visual design pipeline: framework + Tailwind-version detection, design interview, existing-frontend analysis, token system (OKLCH v4 / HSL v3), shadcn component template, preview, UI/UX spec structure, the eight-dimension adversarial design review, and the WCAG contrast formula.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/examples.md`, `references/api-endpoint-design.md`, and `references/visual-design-system.md` together. Keep generated reports and archives outside the skill directory.
