---
name: gatekeeper-admiral
description: >-
  Admiral-pipeline cross-stage gatekeeper, normally invoked by `admiral` at each
  boundary; if reached directly without an active Admiral handoff, hand off to
  `admiral` first (see routing-doctrine.md). Validates cross-stage packages and
  decides whether they are ready to advance between major delivery boundaries. Use
  when `admiral` routes a boundary package for a verdict, or the user asks to
  validate the handoff, check build readiness, review delivery readiness, challenge
  the package boundary, or verify whether a package can move from one orchestrator
  to the next.
version: 1.0.0
---

# Gatekeeper Admiral

## Purpose

Validate cross-stage packages and decide whether they are ready to advance between major delivery boundaries.

## Entry Routing

This skill is the cross-stage gatekeeper of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly submits a boundary package for a verdict.

- **Handoff present** → proceed; an Admiral run is active and this boundary is being validated inside it.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first so a real boundary package, evidence bundle, and approval lineage exist to validate, then accept the submission back. This is the loop guard: Admiral submits with the handoff signal, so a routed call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

- validate the handoff
- check build readiness
- review delivery readiness
- challenge the package boundary

## Inputs

- Submitted boundary package, declared handoff type, owning orchestrator, and next-consumer contract.
- Evidence bundle with approval lineage, revision delta, skip records, deterministic check output, and blocked-phrase scan context.
- Prior verdict record and submission id when a package is resubmitted for idempotency or drift review.

## Outputs

- Boundary verdict record with `APPROVED`, `REVISE`, or `ESCALATE`, tied to handoff type, submission id, package revision, and prior-verdict reuse decision.
- Cross-stage findings naming missing or mismatched artifacts, approval-lineage breaks, blocked-phrase hits, or next-consumer contract gaps.
- Remediation routing note that sends fixes back to the owning orchestrator and identifies any downstream rewind or user escalation.

## Deterministic Pre-Check (two validators)

Run both validators **before** applying judgment. Neither issues a verdict.

**1. The boundary validator.** `../harness/gatekeeper/check.py` loads the
canonical gate spec `../gates.yaml` and checks the submission's evidence
contract:

```bash
python ../harness/gatekeeper/check.py \
  --boundary <design-to-build|build-to-review|review-to-delivery|security-review|investigation-review|qa-review|taste-review|skill-maker-to-delivery|deploy-readiness> \
  --package <phase>/manifest.json \
  [--prior <phase>/verdict_<boundary>.json] \
  --verdict-out <phase>/verdict_<boundary>.cross-stage.json
```

It verifies that every required key is present, that artifact-backed keys point
at hashed files, that typed records (`scan`, `render`, `probe`, `audit`,
`findings`, `verdict`, `stack_lock`, `revision_ref`, and the Taste records
`preference_diff`, `confirmation`, `conflict_analysis`, `persistence_result`,
`effective_profile`, `consumer_handoff`) are shaped correctly and
bound to their source by sha256, that the revision lineage holds one value, that
the declared `owner` is the boundary's only permitted submitter, and that no
blocked phrase or broken local link is present. A missing or malformed gate spec
is an engine error (exit 2), never a pass. Exit 0 is a mechanical fact, not
approval.

Reuse a prior verdict only when the result reports `prior_reusable: true`, which
requires the same boundary, submission, revision, package fingerprint, and gate
spec digest.

**2. The package-shape validator.** `scripts/check.py` checks the phase package
directory itself:

```bash
python scripts/check.py skillset-saves/runs/<run>/delivery [--prior <prior-verdict-file>] [--json]
```

The package directory is admiral's `delivery/` phase directory, which holds the cross-stage handoff record (`reports/handoff_<boundary>.md`) for every boundary; the phase directory itself was already shape-checked by the phase gatekeeper's own `scripts/check.py`. `scripts/check.py` declares this boundary's required-artifact manifest and calls the shared engine at `../harness/gatekeeper/_gatecheck.py`. It mechanizes the structural checks — package shape, single-revision lineage, one submission id, skip-record completeness, the blocked-phrase scan (this gate **owns** it), idempotency drift against `--prior`, and harness-doctrine §5 structure — and returns `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status` (`STRUCTURE_OK` / `NEEDS_JUDGMENT` / `BLOCKERS_PRESENT`). It **never emits a verdict**: apply judgment to the `FAIL` and `UNCHECKED` findings to choose `APPROVED` / `REVISE` / `ESCALATE`. The script fails loud — a blocking failure exits non-zero, an internal error exits 2, never a silent pass. See `../harness/gatekeeper/README.md`.

## Workflow

1. Classify the submission against `../gates.yaml`: one of `design-to-build`, `build-to-review`, `review-to-delivery`, `security-review`, `investigation-review`, `qa-review`, `taste-review`, `skill-maker-to-delivery`, or `deploy-readiness`. Confirm the declared `boundary` and `owner` match the spec, and read the required-evidence list for that boundary from the spec rather than from memory.
2. Run both validators (see above), then judge what they cannot: whether a present artifact is substantively adequate, whether a contradiction across artifacts is real, whether a waiver reason is honest, and whether the next-consumer contract holds.
3. Decide `APPROVED`, `REVISE`, or `ESCALATE` with a handoff-specific rationale that names the missing package element, conflicting approval, or unresolved risk-acceptance question.
4. Reuse an existing verdict only when the same submission id and package revision recur; otherwise record how the resubmission changed before another handoff is allowed.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Forbidden-strings scan ownership**: Own the scan that rejects blocked phrases and treat any hit inside the candidate package as a blocking defect.
- **Harness-doctrine citation**: When a package adds or changes a cross-cutting runtime intervention, evaluate it against `../harness-doctrine.md` §5 and cite the violated section by number in the verdict. A doctrine violation is a `REVISE` (or `ESCALATE` when it needs a scope decision).
- **Gate spec is authoritative**: `../gates.yaml` is the only source of required evidence, artifact-backed keys, sanctioned fallback values, typed record shapes, submitters, and the finding policy. Never accept an evidence key this file does not list for the boundary, and never invent a waiver reason it does not sanction.
- **Finding policy**: A Critical finding blocks until it is verified or marked not-applicable with a reason. A Major finding blocks unless it is verified, not-applicable with a reason, or deferred with a named owner and a reopen trigger recorded in the findings record.
- **Evidence standard**: Apply `../contracts/evidence-standards.md`. A gate-affecting claim is `exact` plus `observed` or `corroborated`; an unavailable check is a data gap, never approval.
- **Workflow protocol**: Every verdict names the transition it guards per `../contracts/workflow-protocol.md`. An invalid transition returns `ESCALATE` and is never silently coerced.

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
| A cross-stage package mixes approvals or deliverables from different revisions | Reject the package as untrusted input, name the mixed boundaries, and require regeneration from the earliest contaminated handoff. |
| The declared boundary does not match the attached package set, such as a build-to-review handoff without build approval lineage | Return `REVISE` with the missing boundary evidence and refuse to infer readiness from summary text alone. |
| A resubmission reuses the previous submission id but changes package contents without a revision delta | Treat the prior verdict as non-transferable, require a fresh boundary summary, and flag the silent drift. |
| A blocked phrase appears inside a generated delivery artifact or handoff narrative | Return `REVISE` and require the submitting orchestrator to clean the package before any downstream stage consumes it. |
| The boundary validator exits 2 (missing or malformed gate spec, unknown boundary, unreadable manifest) | Return `ESCALATE`. An engine failure is never approval, and the gate spec is never bypassed to keep a run moving. |
| Evidence references a project file whose sha256 no longer matches (`input hash drift`) | Return `REVISE` to the evidence owner. The source changed after the evidence was captured, so the evidence no longer proves the claim. |
| A required key carries a bare string that is not a sanctioned fallback value | Return `REVISE`. Only the exact reasons in `../gates.yaml` `fallback_values` are accepted, and at manifest schema 2 they must be typed applicability records naming reason, scope, and decided_by. |

## Save Protocol

A gatekeeper writes exactly one path class: the durable verdict record at
`skillset-saves/runs/{run-id}/{phase}/verdict_{boundary}.cross-stage.json`, produced
by `check.py --verdict-out` (`../save-ownership.yaml`, class `gate-verdict`) and
written beside the phase gatekeeper's `verdict_{boundary}.json`, which it consumes
through `--prior` and never overwrites. It
never modifies the submission, its evidence, or the run record. The delegating
orchestrator captures the semantic verdict in its handoff record. When
persistence is inactive, return the verdict inline and preserve the run and
revision.

## References

- `../gates.yaml` for the canonical boundary contract: required evidence, artifact-backed keys, sanctioned fallbacks, typed records, submitters, and the finding policy.
- `../harness/gatekeeper/check.py` for the boundary validator and `--verdict-out` / `--prior` semantics.
- `scripts/check.py` for the package-shape validator and this boundary's artifact manifest.
- `../contracts/evidence-standards.md`, `../contracts/handoff-templates.md`, and `../contracts/workflow-protocol.md` for the evidence, submission, and transition contracts.
- `../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed boundary-validation sequence and verdict rules.
- `references/examples.md` for concrete cross-stage handoff examples.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
