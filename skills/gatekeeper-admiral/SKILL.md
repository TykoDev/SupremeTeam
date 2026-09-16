---
name: gatekeeper-admiral
description: >-
  Cross-stage gatekeeper for the Admiral pipeline: the second look at a boundary,
  taken for `admiral` after the phase gate has already ruled, re-judging all ten
  boundaries across the whole run. Use when `admiral` routes a boundary package for a
  verdict, or the user asks to validate a handoff between stages, re-judge a boundary
  the phase gate already passed, challenge the package boundary itself, or whether
  this can advance to the next stage. A single phase's own gate is its phase
  gatekeeper's. Reached cold, hand off to `admiral` first.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Gatekeeper Admiral

## Purpose

Stand the second pass at a boundary a phase gate has already cleared.

A phase gatekeeper judges its own pipeline's package and shares that pipeline's
assumptions. This gate re-judges the same submission from outside it, against
`../gates.yaml`, and looks for the defects that only become visible where two
pipelines meet:

- approvals and deliverables drawn from different revisions
- a declared boundary that does not match the package actually attached
- a prior verdict carried forward across a package that quietly changed
- blocked phrases that entered through a generated artifact rather than an author

One skill carries all ten boundaries because those defects have the same shape
everywhere, and because a per-boundary cross-stage gate would have to be told the
same contract ten times.

## Entry Routing

This skill is the cross-stage gatekeeper of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly submits a boundary package for a verdict.

- **Handoff present** → proceed; an Admiral run is active and this boundary is being validated inside it.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first so a real boundary package, evidence bundle, and approval lineage exist to validate, then accept the submission back. This is the loop guard: Admiral submits with the handoff signal, so a routed call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

Use this gate **after the phase gates have run**, on the same package — it re-judges all ten boundaries rather than one:

- "challenge the package boundary itself" — pressure the boundary, not the phase gate's verdict
- "re-judge a boundary the phase gate already passed" — the build or delivery boundary seen again across the whole run
- "validate a handoff between stages" — confirm the package carries what the next stage actually needs
- "can this advance to the next stage?" — the bare question, when admiral holds the run
- "re-judge this after the phase gate" — the second look admiral asks for

The two readiness phrasings carry the **cross-stage** qualifier because the
unqualified forms belong to the phase gates: `check build readiness` is
`build/gatekeeper-build`'s trigger and `review delivery readiness` is
`review/gatekeeper-code`'s. This gate runs after theirs, on the same package.

## Inputs

- Submitted boundary package, declared handoff type, owning orchestrator, and next-consumer contract.
- Evidence bundle with approval lineage, revision delta, skip records, deterministic check output, and blocked-phrase scan context.
- Prior verdict record and submission id when a package is resubmitted for idempotency or drift review.

## Outputs

- Boundary verdict record with `APPROVED`, `REVISE`, or `ESCALATE`, tied to handoff type, submission id, package revision, and prior-verdict reuse decision.
- Cross-stage findings naming missing or mismatched artifacts, approval-lineage breaks, blocked-phrase hits, or next-consumer contract gaps.
- Remediation routing note that sends fixes back to the owning orchestrator and identifies any downstream rewind or user escalation.

## Boundary Contract

This gate stands at every crossing, so it carries all ten boundaries rather than
one. `../gates.yaml` is the source of every row; the table mirrors that file and
is never restated from memory, because a remembered evidence list is how a gate
starts accepting keys the spec does not require. Classify the submission against
the spec first — a boundary judged under the wrong row checks the wrong facts.

| Boundary | Guards | Submitter | Required evidence |
| --- | --- | --- | --- |
| `design-to-build` | DESIGN to BUILD | commander | `decisions` `architecture` `interfaces` `plan` `acceptance` `security_seed` `stack_lock` `taste_snapshot` `ui_evidence` |
| `redesign-review` | REDESIGN (design-shaped) to GATE to DESIGN with the chosen variant, or COMPLETE | redesign | `design_inventory` `taste_grilling` `taste_snapshot` `design_directions` `variant_set` `parity_evidence` `rendered_verification` `accessibility_evidence` `recommendation` `residual_risk` |
| `build-to-review` | BUILD to REVIEW | build-management | `approved_design_revision` `implementation` `tests` `runtime` `traceability` `security_evidence` |
| `review-to-delivery` | REVIEW to GATE to COMPLETE | code-chief | `review_verdict` `findings` `executed_probes` `rendered_verification` `residual_risk` `revision_lineage` |
| `security-review` | security pipeline to GATE to COMPLETE | cso | `scope` `threat_model` `findings` `vulnerability_scan` `denial_path_evidence` `remediation_plan` `residual_risk` |
| `investigation-review` | investigation to the owning phase (DESIGN, BUILD, or REVIEW) | investigate | `scope` `reproduction` `mechanism` `evidence_chain` `fix_path` `residual_uncertainty` |
| `qa-review` | testing-and-qa pipeline to GATE to COMPLETE | qa | `scope` `test_matrix` `executed_probes` `defects` `fixes_applied` `residual_risk` |
| `taste-review` | TASTE to GATE to COMPLETE or consuming pipeline | taste | `scope` `intent` `before_revision` `preference_diff` `confirmation` `conflict_analysis` `policy_check` `persistence_result` `effective_profile` `consumer_handoff` `taste_review_record` `residual_uncertainty` |
| `skill-maker-to-delivery` | skill-maker pipeline to GATE to COMPLETE | skill-maker | `skills` `team_manifest` `link_report` `validation_report` |
| `deploy-readiness` | GATE to RELEASE | ship | `approved_delivery` `deploy_config` `verification_plan` `rollback_plan` `human_go_required` |

Three rules govern every row, and `references/boundary-evidence.md` carries the
per-boundary detail behind them — which keys are artifact-backed, which typed
record each key must be, and the exact sanctioned waiver text:

- **Artifact-backed keys resolve to a hashed file.** Each must name a path that
  appears in the package's `artifact_hashes` map (`../gates.yaml`
  `artifact_evidence`); a sentence describing the artifact is not the artifact.
- **Nine keys are waivable, and only as a typed applicability record** naming
  reason, scope, and decided_by, for the exact reason `../gates.yaml`
  `fallback_values` sanctions: `security_evidence`, `stack_lock`, `ui_evidence`,
  `taste_snapshot`, `rendered_verification`, `denial_path_evidence`,
  `vulnerability_scan`, `fixes_applied`, and `team_manifest`. `taste-review` adds
  three of its own — `before_revision`, `consumer_handoff`, and
  `residual_uncertainty`. Every other key accepts no fallback, so a bare
  explanatory string in its place fails mechanically.
- **A boundary-level `no_fallback` beats a global fallback.** `redesign-review`
  lists `rendered_verification` under `no_fallback`, so there it accepts neither
  the sanctioned string nor an applicability record: a redesign always has a
  visible surface, so the global waiver reason cannot be true at that boundary.
  Never grant a waiver the boundary refuses.

### Owner routing

A `REVISE` routes by key owner, not by submitter, which is what makes the batched
packet parallelisable. Below is the `../gates.yaml` `evidence_owners` mirror,
compressed to the divergences: every key not named on a row belongs to that
boundary's submitter.

| Boundary | Keys whose owner is not the submitter |
| --- | --- |
| `design-to-build` | `decisions` admiral · `architecture` `interfaces` `ui_evidence` architect · `plan` `acceptance` planner · `security_seed` security-builder · `taste_snapshot` taste |
| `redesign-review` | `design_inventory` `parity_evidence` design-mapper · `taste_grilling` `taste_snapshot` taste · `design_directions` architect · `variant_set` prototyper · `rendered_verification` design-qa · `accessibility_evidence` frontier |
| `build-to-review` | `implementation` bob-the-builder · `tests` test-builder · `runtime` health-check · `security_evidence` security-builder |
| `review-to-delivery` | `rendered_verification` design-qa |
| `security-review` | `vulnerability_scan` security-review · `denial_path_evidence` mr-robot |
| `investigation-review` | (none — every key is `investigate`'s) |
| `qa-review` | (none — every key is `qa`'s) |
| `taste-review` | `taste_review_record` taste-review |
| `skill-maker-to-delivery` | `link_report` skill-reviewer · `validation_report` skill-creator |
| `deploy-readiness` | `deploy_config` `rollback_plan` setup-deploy |

## Deterministic Pre-Check (two validators)

Run both validators **before** applying judgment. Neither issues a verdict.

**1. The boundary validator.** `../harness/gatekeeper/check.py` loads the
canonical gate spec `../gates.yaml` and checks the submission's evidence
contract:

```bash
python ../harness/gatekeeper/check.py \
  --boundary <design-to-build|redesign-review|build-to-review|review-to-delivery|security-review|investigation-review|qa-review|taste-review|skill-maker-to-delivery|deploy-readiness> \
  --package <phase>/manifest.json \
  [--prior <phase>/verdict_<boundary>.json] \
  --verdict-out <phase>/verdict_<boundary>.cross-stage.json
```

It verifies, for the named boundary only:

- every required key is present and non-falsy, and artifact-backed keys point at hashed files
- typed records (`scan`, `render`, `probe`, `audit`, `findings`, `verdict`, `stack_lock`, `revision_ref`, and the Taste records `preference_diff`, `confirmation`, `conflict_analysis`, `persistence_result`, `effective_profile`, `consumer_handoff`) are shaped correctly and bound to their source by sha256
- the revision lineage holds one value, and the declared `owner` is the boundary's only permitted submitter
- no blocked phrase and no broken local link is present

A missing or malformed gate spec is an engine error (exit 2), never a pass, and
exit 0 is a mechanical fact rather than approval. Reuse a prior verdict only when
the result reports `prior_reusable: true`, which requires the same boundary,
submission, revision, package fingerprint, and gate spec digest.

**2. The package-shape validator.** `scripts/check.py` checks the phase package
directory itself:

```bash
python scripts/check.py skillset-saves/runs/<run>/delivery [--prior <prior-verdict-file>] [--json]
```

Pass admiral's `delivery/` phase directory as `<package-dir>`: it holds the
cross-stage handoff record (`reports/handoff_<boundary>.md`) for every boundary,
and the originating phase directory was already shape-checked by the phase
gatekeeper's own `scripts/check.py`. The script declares this gate's
required-artifact manifest and calls the shared engine at
`../harness/gatekeeper/_gatecheck.py`, which mechanizes:

- package shape, single-revision lineage, and one submission id
- skip-record completeness
- the blocked-phrase scan — this gate **owns** it
- idempotency drift against `--prior`, and harness-doctrine §5 structure

It returns `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status`
(`STRUCTURE_OK` / `NEEDS_JUDGMENT` / `BLOCKERS_PRESENT`) and **never emits a
verdict**: apply judgment to the `FAIL` and `UNCHECKED` findings to choose
`APPROVED` / `REVISE` / `ESCALATE`. It fails loud — a blocking failure exits
non-zero, an internal error exits 2, never a silent pass. See
`../harness/gatekeeper/README.md`.

**Input validation (enforced in code).** `<package-dir>` arrives from run
context, so `scripts/check.py` confines it before the engine reads a byte:
`_validate_package_dir()` resolves the argument, requires an existing directory,
and requires it to sit inside the located working tree. A missing path, a
non-directory, a path outside the tree, or an unlocatable tree root exits 2
without running the gate. Confirm the same three properties before invoking, and
return `ESCALATE` naming the rejected path rather than retrying — a gate that
fails open is worse than no gate.

## Execution Contract

Canonical source: `../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

Clause 6 binds directly, because this skill owns the cross-stage verdict at all
ten boundaries. Every return carries all six fields:

- **Outcome** — the boundary judged and what the package may now do
- **Evidence** — both validator results plus the hashed artifacts actually inspected
- **Open risks** — preserved contradictions and any unresolved risk-acceptance question
- **Next action** — the owner-grouped `REVISE` packet, the rewind boundary, or the next-consumer handoff
- **Revision** — the submitted package revision
- **Verdict** — `APPROVED` / `REVISE` / `ESCALATE`

A verdict returned without its evidence anchors is incomplete and is not a gate
result.

Clause 4 has a concrete local form here: `<package-dir>` is untrusted run
context, so validate it before the script reads it (see the input-validation note
above).

## Workflow

1. Classify the submission against `../gates.yaml`: one of the ten boundaries in the Boundary Contract above. Confirm the declared `boundary` and `owner` match the spec, and read the required-evidence list for that boundary from the spec rather than from memory.
2. Run the boundary validator for that boundary, with `--prior` pointed at the phase gatekeeper's `verdict_<boundary>.json` when one exists.
3. Run the package-shape validator against the `delivery/` phase directory, after confirming the path resolves inside the working tree.
4. Judge what neither validator can: whether a present artifact is substantively adequate, whether a contradiction across artifacts is real, whether a waiver reason is honest, and whether the next-consumer contract holds.
5. Decide `APPROVED`, `REVISE`, or `ESCALATE` with a handoff-specific rationale that names the missing package element, conflicting approval, or unresolved risk-acceptance question, grouped by the owner each failing key belongs to.
6. Reuse an existing verdict only when the same submission id and package revision recur; otherwise record how the resubmission changed before another handoff is allowed.

## Required Contracts

- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Forbidden-strings scan ownership**: Own the scan that rejects blocked phrases and treat any hit inside the candidate package as a blocking defect.
- **Harness-doctrine citation**: When a package adds or changes a cross-cutting runtime intervention, evaluate it against `../harness-doctrine.md` §5 and cite the violated section by number in the verdict. A doctrine violation is a `REVISE` (or `ESCALATE` when it needs a scope decision).
- **Gate spec is authoritative**: `../gates.yaml` is the only source of required evidence, artifact-backed keys, sanctioned fallback values, typed record shapes, submitters, and the finding policy. Never accept an evidence key this file does not list for the boundary, and never invent a waiver reason it does not sanction.
- **Batched REVISE** (`../gates.yaml` `revise_policy`): A `REVISE` carries every mechanical failure and every judgment finding from the pass, grouped by owner exactly as `check.py` reports them in `revise_packet.by_owner`; never return the first defect alone. On a resubmission run with `--prior`, re-judge only `changed_evidence` and carry the prior judgment on `unchanged_evidence`; the mechanical pass always covers the whole package. A package that fails mechanically was never eligible for submission (the submitter self-checks) and is returned without judgment.
- **Finding policy**: A Critical finding blocks until it is verified or marked not-applicable with a reason. A Major finding blocks unless it is verified, not-applicable with a reason, or deferred with a named owner and a reopen trigger recorded in the findings record.
- **Workflow protocol**: Every verdict names the transition it guards per `../contracts/workflow-protocol.md`. An invalid transition returns `ESCALATE` and is never silently coerced.

## Verdict Model

- **APPROVED**: The package is ready to advance with its current evidence.
- **REVISE**: The package can progress after specific mandatory changes.
- **ESCALATE**: The package cannot advance without external judgment or a broader scope decision.

## Evidence Standard

Apply `../contracts/evidence-standards.md`: a gate-affecting claim is `exact`
plus `observed` or `corroborated`, and an unavailable check is a data gap, never
approval. Concretely, at this gate:

- Tie every major and critical finding to a concrete file, artifact, or observable behavior.
- Reject claims of completion that are not backed by a visible deliverable.
- Preserve contradictory evidence instead of normalizing it away.

## Skip Rule

Do not skip gate evaluation; only reuse a prior verdict when the exact package revision is unchanged.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A cross-stage package mixes approvals or deliverables from different revisions | Reject the package as untrusted input, name the mixed boundaries, and require regeneration from the earliest contaminated handoff. |
| The declared boundary does not match the attached package set, such as a build-to-review handoff without build approval lineage | Return `REVISE` with the missing boundary evidence and refuse to infer readiness from summary text alone. |
| The declared `owner` is not the boundary's spec submitter, such as a `redesign-review` package declaring `commander` | Return `REVISE`. `../gates.yaml` names one permitted submitter per boundary, and the validator fails the package; a package submitted by the wrong owner has no approval lineage to trust. |
| A resubmission reuses the previous submission id but changes package contents without a revision delta | Treat the prior verdict as non-transferable, require a fresh boundary summary, and flag the silent drift. |
| A blocked phrase appears inside a generated delivery artifact or handoff narrative | Return `REVISE` and require the submitting orchestrator to clean the package before any downstream stage consumes it. |
| The boundary validator exits 2 (missing or malformed gate spec, unknown boundary, unreadable manifest) | Return `ESCALATE`. An engine failure is never approval, and the gate spec is never bypassed to keep a run moving. |
| `scripts/check.py` exits 2 because `<package-dir>` is missing, is not a directory, sits outside the working tree, or the tree root cannot be located | Return `ESCALATE` and name the rejected path. The guard runs before the engine reads anything, so nothing was checked; an unrun pre-check is not a clean one. |
| Evidence references a project file whose sha256 no longer matches (`input hash drift`) | Return `REVISE` to the evidence owner. The source changed after the evidence was captured, so the evidence no longer proves the claim. |
| A required key carries a bare string that is not a sanctioned fallback value | Return `REVISE`. Only the exact reasons in `../gates.yaml` `fallback_values` are accepted, and at manifest schema 2 they must be typed applicability records naming reason, scope, and decided_by. |

## Save Protocol

A gatekeeper writes exactly one path class: the durable verdict record at
`skillset-saves/runs/{run-id}/{phase}/verdict_{boundary}.cross-stage.json`,
produced by `check.py --verdict-out` (`../save-ownership.yaml`, class
`gate-verdict`).

It lands beside the phase gatekeeper's `verdict_{boundary}.json`, which this gate
consumes through `--prior` and never overwrites. It never modifies the
submission, its evidence, or the run record; the delegating orchestrator captures
the semantic verdict in its handoff record. When persistence is inactive, return
the verdict inline and preserve the run and revision.

## References

- `../gates.yaml` for the canonical boundary contract: required evidence, artifact-backed keys, sanctioned fallbacks, typed records, submitters, and the finding policy.
- `references/boundary-evidence.md` for the per-boundary artifact-backed key lists, the typed-record roster, and the exact sanctioned waiver text.
- `../harness/gatekeeper/check.py` for the boundary validator and `--verdict-out` / `--prior` semantics.
- `scripts/check.py` for the package-shape validator and this gate's artifact manifest.
- `../contracts/evidence-standards.md`, `../contracts/handoff-templates.md`, and `../contracts/workflow-protocol.md` for the evidence, submission, and transition contracts.
- `../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed boundary-validation sequence and verdict rules.
- `references/examples.md` for worked cross-stage submissions at six of the ten boundaries.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, `references/boundary-evidence.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
