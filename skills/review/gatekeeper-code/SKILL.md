---
name: gatekeeper-code
description: >-
  Validates consolidated review packages and decides whether the review evidence
  is ready for delivery or needs another round. Use when the user asks to validate
  the review package, check review readiness, challenge this review packet, or gate
  the review output — even when they only ask "is this review done?". Gates the
  review→delivery boundary only; defers the other gates to `build/gatekeeper-build`,
  `design/gatekeeper-design`, and `gatekeeper-admiral`.
version: 1.0.0
---


# Gatekeeper Code

## Purpose

Validates consolidated review packages and decides whether the review evidence is ready for delivery or needs another round.

## Use This Skill When

Use this gate at the **review→delivery boundary** — deciding whether the consolidated review evidence can advance:

- "validate the review package" / "check review readiness" — confirm every required lens is present and substantiated
- "challenge this review packet" — pressure the evidence rather than the intent behind it
- "gate the review output" — issue an advance / revise verdict on the package as a whole

Route elsewhere for a different boundary: the build→review gate (`build/gatekeeper-build`), the design→build gate (`design/gatekeeper-design`), or the cross-stage delivery gate (`gatekeeper-admiral`).

## Inputs

- Consolidated review package with required lens reports, optional-scope skips, blocker summary, and delivery-readiness claim.
- Pipeline context from `review/code-chief` with build revision, approval lineage, revision delta, severity model, and deterministic pre-check output.
- Prior review-gate verdict when the same package is being resubmitted for idempotency or drift review.

## Outputs

- Review-to-delivery verdict with APPROVED, REVISE, or ESCALATE, tied to the consolidated review revision and lens-coverage evidence.
- Review findings naming missing or stale lenses, unsupported skips, severity conflicts, absent CSO evidence, or unowned blockers.
- Required remediation instructions for `review/code-chief`, including which specialist lens or consolidation step must change before delivery.

## Deterministic Pre-Check (script)

Run the deterministic gate engine **before** applying judgment:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

`scripts/check.py` declares this boundary's required-artifact manifest (the five core lenses: bug, code, quality, security, adversarial/frontier) and calls the shared engine at `../../harness/gatekeeper/_gatecheck.py`. The CSO lens is **conditional**: the script cannot know whether a security-leadership / accepted-risk / release-posture claim is in scope, so it reports the lens's absence as `UNCHECKED` for you to resolve — or to accept via an explicit `_skip-record.md`, whose required fields the engine validates. It also mechanizes single-revision lineage, skip-record completeness, the blocked-phrase scan, idempotency drift, and harness-doctrine §5 structure, returning `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status`. It **never emits a verdict** and never adjudicates conflicting specialist findings — apply judgment to the findings to choose `APPROVED` / `REVISE` / `ESCALATE`. The script fails loud — a blocking failure exits non-zero, an internal error exits 2. See `../../harness/gatekeeper/README.md`.

## Workflow

1. Run `scripts/check.py` to verify that the consolidated review package includes the right revision lineage, core lens coverage, and optional-skip justifications before evaluating delivery readiness.
2. Cross-check the submitted review evidence against the underlying specialist reports so every blocker, skip, and approval points to visible evidence.
3. Decide whether the consolidated review package is ready for delivery, needs another review round, or must escalate, and record the narrowest justified verdict.
4. Persist a verdict record with mandatory fixes, evidence anchors, and idempotent revision notes so the same review package is not re-gated under conflicting rationale.

## Required Contracts

- **Shared severity**: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- **CSO lens coverage**: When a review package claims security leadership signoff, accepted-risk readiness, release security posture, regulated-data governance, or operating-model control review, require a `review/cso` packet or an explicit scoped skip reason.
- **Harness-doctrine citation**: When the package adds or changes a cross-cutting runtime intervention, check it against `../../harness-doctrine.md` §5 and cite the violated section by number in the verdict.

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
| A mandatory specialist report is missing or older than the package revision under review | Reject the submission, name the missing or stale report, and require the owning orchestrator to resubmit a coherent package set. |
| The package claims security leadership signoff, accepted-risk readiness, or release security posture without `review/cso` evidence or an explicit skip reason | Return REVISE and require `review/code-chief` to run the CSO lens or remove the unsupported leadership claim. |
| Specialist findings conflict on severity, exploitability, or scope | Preserve the contradiction in the verdict record and return REVISE unless the conflict requires external judgment, in which case return ESCALATE. |
| The package claims a skip without recording the reason or evidence boundary | Mark the package incomplete and require a skip justification before re-evaluating readiness. |
| The package is resubmitted without a clear delta from the previous verdict | Reuse the prior reasoning where possible and reject silent re-gating until the revision summary explains what changed. |
| `scripts/check.py` cannot run (Python unavailable, permission error) or exits with internal-error code 2 | Treat the gate as NOT satisfied — do not default to APPROVED. Surface the error, then choose ESCALATE (or REVISE) instead of a silent pass. A gate that fails open is worse than no gate; an unknown pre-check result is not evidence of readiness. |

## Save Protocol

Gatekeepers do not write directly to `skillset-saves/`. The delegating orchestrator captures the gatekeeper verdict and writes it to the appropriate `gatekeeper-verdict.md` file. Return verdict output inline as usual.

## References

- `scripts/check.py` for the deterministic gate engine wrapper and this boundary's artifact manifest.
- `../../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
