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

- **Handoff present** → proceed; you are validating a boundary inside an Admiral run.
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

## Deterministic Pre-Check (script)

Run the deterministic gate engine **before** applying judgment:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

`scripts/check.py` declares this boundary's required-artifact manifest and calls the shared engine at `../harness/gatekeeper/_gatecheck.py`. It mechanizes the structural checks — package shape, single-revision lineage, one submission id, skip-record completeness, the blocked-phrase scan (this gate **owns** it), idempotency drift against `--prior`, and harness-doctrine §5 structure — and returns `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status` (`STRUCTURE_OK` / `NEEDS_JUDGMENT` / `BLOCKERS_PRESENT`). It **never emits a verdict**: apply judgment to the `FAIL` and `UNCHECKED` findings to choose `APPROVED` / `REVISE` / `ESCALATE`. The script fails loud — a blocking failure exits non-zero, an internal error exits 2, never a silent pass. See `../harness/gatekeeper/README.md`.

## Workflow

1. Classify the submission as design-to-build, build-to-review, review-to-delivery, or skill-maker-to-delivery, and verify the exact package set expected for that handoff.
2. Run `scripts/check.py` on the package, then check whether the cross-stage submission is actually ready by reading its structural findings (approval lineage, revision delta, skip justifications, blocked-phrase cleanliness) and applying judgment to the next-consumer contract.
3. Decide `APPROVED`, `REVISE`, or `ESCALATE` with a handoff-specific rationale that names the missing package element, conflicting approval, or unresolved risk-acceptance question.
4. Reuse an existing verdict only when the same submission id and package revision recur; otherwise record how the resubmission changed before another handoff is allowed.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **Forbidden-strings scan ownership**: Own the scan that rejects blocked phrases and treat any hit inside the candidate package as a blocking defect.
- **Harness-doctrine citation**: When a package adds or changes a cross-cutting runtime intervention, evaluate it against `../harness-doctrine.md` §5 and cite the violated section by number in the verdict. A doctrine violation is a `REVISE` (or `ESCALATE` when it needs a scope decision).

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

## Save Protocol

Gatekeepers do not write directly to `skillset-saves/`. The delegating orchestrator captures the gatekeeper verdict and writes it to the appropriate `gatekeeper-verdict.md` or `gatekeeper-admiral_handoff-{N}.md` file. Return verdict output inline as usual.

## References

- `scripts/check.py` for the deterministic gate engine wrapper and this boundary's artifact manifest.
- `../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed boundary-validation sequence and verdict rules.
- `references/examples.md` for concrete cross-stage handoff examples.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
