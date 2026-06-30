---
name: gatekeeper-design
description: >-
  Validates design-phase deliverables before a design package can advance to the
  next design activity or leave the design pipeline. Use when the user asks to
  validate the design deliverable, review design phase output, check design
  readiness, challenge this design packet, or verify whether the design package is
  coherent enough for build consumption — even when they only ask "is the design
  done?". Gates the design→build boundary specifically; defers the build→review
  gate to `build/gatekeeper-build`, the review→delivery gate to
  `review/gatekeeper-code`, and the cross-stage delivery gate to `gatekeeper-admiral`.
version: 1.0.0
---

# Gatekeeper Design

## Purpose

Validate design-phase deliverables before a design package can advance to the next design activity or leave the design pipeline.

## Use This Skill When

Use this gate at the **design→build boundary** — deciding whether design evidence can advance:

- "validate the design deliverable" / "check design readiness" — confirm requirements, plan, and architecture are present and coherent
- "review design phase output" — verify the package is complete enough for build consumption
- "challenge this design packet" — pressure the evidence rather than the intent behind it

Route elsewhere for a different boundary: the build→review gate (`build/gatekeeper-build`), the review→delivery gate (`review/gatekeeper-code`), or the cross-stage delivery gate (`gatekeeper-admiral`).

## Inputs

- Design packet for the current phase exit, including research, plan, architecture, API/UI contracts, stack locks, and implementation spec as applicable.
- Pipeline context from `design/commander` with scope, approval lineage, revision delta, skip records, and deterministic pre-check output.
- Prior design-gate verdict when the same package is being resubmitted for idempotency or drift review.
- YAGNI deferrals, migration/deprecation commitments, proof-first test expectations, and threat-model seeds when those surfaces are in scope.

## Outputs

- Design-exit verdict with `APPROVED`, `REVISE`, or `ESCALATE`, tied to the submitted design revision and phase boundary.
- Design findings naming missing or inconsistent research, plan, architecture, endpoint, UI, stack-lock, or implementation-spec evidence.
- Findings for premature/speculative scope, missing migration proof, absent test strategy, or undocumented trust boundaries when applicable.
- Required remediation instructions for `design/commander`, including which specialist packet must change before build can consume the design.

## Deterministic Pre-Check (script)

Run the deterministic gate engine **before** applying judgment:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

`scripts/check.py` declares this boundary's required-artifact manifest (research evidence, project plan, architecture decisions, stack locks, implementation spec) and calls the shared engine at `../../harness/gatekeeper/_gatecheck.py`. API contracts and the frontend/UI handoff are **conditional**: the script cannot know whether endpoints or a user-facing surface are in scope, so it reports their absence as `UNCHECKED` for you to resolve against the actual scope and the `../architect/references/api-endpoint-design.md` / `../../design-doctrine.md` contracts. The engine also mechanizes single-revision lineage, skip-record completeness, the blocked-phrase scan, idempotency drift, and harness-doctrine §5 structure, returning `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status`. It **never emits a verdict** and never judges design coherence — apply judgment to the findings to choose `APPROVED` / `REVISE` / `ESCALATE`. The script fails loud — a blocking failure exits non-zero, an internal error exits 2. See `../../harness/gatekeeper/README.md`.

## Workflow

1. Run `scripts/check.py`, then verify the active design-phase boundary and confirm the packet contains the required research evidence, project plan, architecture decisions, API contracts, stack locks, and implementation specification for that phase exit.
2. Cross-check the packet for design coherence so stakeholder goals, system structure, frontend and backend decisions, deployment assumptions, YAGNI deferrals, and unresolved questions do not contradict each other.
3. Check that migration/deprecation, proof-first testing, frontend state/API handoff, and threat-model surfaces are present when the design scope requires them.
4. Decide the narrowest justified verdict and return only the mandatory changes the design owner must make before the next design activity or the build handoff.
5. Preserve verdict history across revisions and reject silent scope broadening disguised as normal design evolution, undocumented architecture drift, or an unearned pipeline exit.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **API endpoint contract schema**: When API, webhook, event-ingest, or internal service endpoints are in scope, reject packages that do not satisfy `../architect/references/api-endpoint-design.md` with endpoint inventory, per-endpoint schemas, auth/authorization, error envelope, idempotency, observability, versioning, frontend handoff, and contract tests.
- **Frontend/UI handoff schema**: When a user-facing surface is in scope, reject packages that do not satisfy `../../design-doctrine.md` with both the shadcn Component Template and UI/UX Handoff sections, including route inventory, state matrix, API/data dependency map, validation behavior, and responsive evidence.
- **Harness-doctrine citation**: When the package adds or changes a cross-cutting runtime intervention, check it against `../../harness-doctrine.md` §5 and cite the violated section by number in the verdict.
- **YAGNI and proof contract**: Reject packages that force speculative future commitments without current need, or that change behavior without a build-ready proof plan covering reproduction/contract tests, migration checks, and rollback evidence as applicable.

## Verdict Model

- **APPROVED**: The package is ready to advance with its current evidence.
- **REVISE**: The package can progress after specific mandatory changes.
- **ESCALATE**: The package cannot advance without external judgment or a broader scope decision.

## Evidence Standard

- Tie every major and critical finding to a concrete file, artifact, or observable behavior.
- Reject claims of completion that are not backed by a visible deliverable.
- Preserve contradictory evidence instead of normalizing it away.

## Skip Rule

Do not skip gate evaluation; only reuse a prior verdict when the exact package revision is unchanged.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The architecture describes components, flows, or interfaces that are absent from the plan or implementation spec | Return `REVISE` and require the packet to restore a single coherent system view before build can rely on it. |
| The package claims API readiness but endpoints lack request/response schemas, auth/authorization, error envelope, idempotency, or contract tests | Return `REVISE` and require the API endpoint contract template before the design package can exit. |
| The package claims frontend readiness but lacks route inventory, screen-state coverage, API/data dependency mapping, form validation behavior, or breakpoint evidence | Return `REVISE` and require the UI/UX Handoff section before the design package can exit. |
| Stack locks or infrastructure assumptions conflict with regulatory, operational, or platform constraints already captured in the packet | Block the design exit until the contradiction is resolved or explicitly escalated to the user. |
| The packet names critical open questions but does not assign ownership or a downstream decision point | Mark the package incomplete and require explicit unresolved-decision handling before approval. |
| The design claims readiness for build but lacks the actual phase-exit approval record for the current revision | Reject the handoff and require the matching approval lineage instead of trusting narrative readiness claims. |
| The package removes, replaces, or deprecates behavior without consumer/usage evidence, replacement readiness, migration steps, and removal criteria | Return `REVISE` and require the planner/engineer packets to make the migration path build-ready. |
| The implementation spec changes behavior but does not identify the first failing test, contract test, or runtime verification expected from the build phase | Return `REVISE` and require a proof-first validation plan before build begins. |

## Save Protocol

Gatekeepers do not write directly to `skillset-saves/`. The delegating orchestrator captures the gatekeeper verdict and writes it to the appropriate `gatekeeper-verdict.md` file. Return verdict output inline as usual.

## References

- `scripts/check.py` for the deterministic gate engine wrapper and this boundary's artifact manifest.
- `../../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed design-packet validation sequence and verdict rules.
- `references/examples.md` for concrete design-gate examples.
- `../architect/references/api-endpoint-design.md` for the required API endpoint design contract.
- `../../design-doctrine.md` for the shadcn Component Template and UI/UX Handoff requirements.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
