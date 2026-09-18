---
name: gatekeeper-code
description: >-
  Review-phase gatekeeper for the `review-to-delivery` boundary, invoked by
  `review/code-chief`; reached cold, route to `admiral` first. Returns the last
  verdict before work leaves the pipeline: reviewed work goes out to delivery, or it
  goes back. Use when code-chief submits a package for a verdict, or the user asks to
  validate the review package, review delivery readiness, say whether the review is
  finished enough to deliver, gate the review output, or challenge this review
  packet. Whether work is ready to *enter* review is `build/gatekeeper-build`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Gatekeeper Code

## Purpose

Judge a package assembled from several specialists who did not agree.

A consolidated review is the one package in the pipeline whose inputs routinely
contradict each other: the security lens and the code lens can look at the same
line and reach opposite conclusions, and consolidation is where that
disagreement quietly disappears. This gate exists to keep it visible — a
preserved contradiction is a result, and a normalized one is a defect that
reaches delivery as consensus.

Two things follow from that, and they shape everything below:

- A conflict between lenses is `REVISE` when evidence can settle it and `ESCALATE` when only a person can. It is never resolved here by picking a side.
- `rendered_verification` belongs to `design-qa`, not to the submitter, so the package's own author cannot repair its most commonly failing key.

## Entry Routing

This skill is the review-phase gatekeeper of the **Admiral** delivery pipeline and is reached through its sub-orchestrator `review/code-chief`, never as a front door (`../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly submits a `review-to-delivery` package for a verdict.

- **Handoff present** → proceed; a run is active and this boundary is being validated inside it.
- **No handoff (cold/direct invocation)** → do not run standalone. Route to `admiral` first so a real review package, evidence bundle, and approval lineage exist to validate, then accept the submission back. This is the loop guard: a routed call arrives with the handoff signal and proceeds immediately, so the check never re-bootstraps a run that is already open.

## Use This Skill When

Use this gate at the **review→delivery boundary** — deciding whether the consolidated review evidence can advance:

- "validate the review package" / "is the review finished enough to deliver" — confirm every required lens is present and substantiated
- "review delivery readiness" — the unqualified phase form; the cross-stage form belongs to `gatekeeper-admiral`
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

## Boundary Contract

This gate owns one boundary. `../../gates.yaml` is the source of the row below;
the table mirrors that file and is never restated from memory, because a
remembered evidence list is how a gate starts accepting keys the spec does not
require.

| Boundary | Guards | Submitter | Required evidence |
| --- | --- | --- | --- |
| `review-to-delivery` | REVIEW to GATE to COMPLETE | code-chief | `review_verdict` `findings` `executed_probes` `rendered_verification` `residual_risk` `revision_lineage` |

`references/boundary-evidence.md` carries what each key must be — its record
type, its artifact-backing, and the exact sanctioned waiver text. Three
decisions belong at the gate itself:

- **`executed_probes` and `rendered_verification` cannot be satisfied by assertion.** Each must name a path in the package's `artifact_hashes` map, so the evidence is a hashed file rather than a claim. `executed_probes` is a `probe` record whose artifacts are the executed logs at `result.status: pass` — a count of probes run is not evidence that they ran. `rendered_verification` is a `render` record carrying hashed captures, the breakpoints and themes covered, and `inputs` bound by sha256 to the rendered source.
- **A disputed `review_verdict` stays disputed.** It is a `verdict` record: APPROVED, or REVISE/ESCALATE with a challenge record naming `by` and `reason`. This gate preserves that challenge as a disputed recommendation instead of resolving it.
- **Only `rendered_verification` accepts a waiver here**, as a typed applicability record naming reason, scope, and decided_by, for the exact reason `../../gates.yaml` `fallback_values` sanctions — that no visible surface changed. The other five accept no fallback, so a bare explanatory string in place of any of them fails mechanically.

Ownership decides where a `REVISE` lands (`../../gates.yaml` `evidence_owners`):

| Evidence key | Owner |
| --- | --- |
| `review_verdict` | code-chief |
| `findings` | code-chief |
| `executed_probes` | code-chief |
| `rendered_verification` | design-qa |
| `residual_risk` | code-chief |
| `revision_lineage` | code-chief |

`rendered_verification` is the exception worth reading twice: `design-qa` owns it,
not `code-chief`, even though `code-chief` submits the package. A `REVISE` naming
that key routes to `design-qa`; sending it to the submitter parks the defect with
an owner who cannot capture a render.

## Deterministic Pre-Check (two validators)

Run both **before** applying judgment. Neither issues a verdict, and neither
substitutes for the other: a package can pass the shape check and still fail the
evidence contract.

**1. The package-shape validator** checks which files the package directory
holds:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

It declares this boundary's required-artifact manifest — the five core lenses:
bug, code, quality, security, adversarial/frontier — and calls the shared engine
at `../../harness/gatekeeper/_gatecheck.py`, which also mechanizes:

- single-revision lineage
- skip-record completeness
- the blocked-phrase scan
- idempotency drift, and harness-doctrine §5 structure

It returns `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status`, **never
a verdict**, and never adjudicates conflicting specialist findings. It fails
loud — a blocking failure exits non-zero, an internal error exits 2. See
`../../harness/gatekeeper/README.md`.

The CSO lens is **conditional**: the script cannot know whether a
security-leadership, accepted-risk, or release-posture claim is in scope, so it
reports the lens's absence as `UNCHECKED` — to be resolved, or accepted via an
explicit `_skip-record.md` whose required fields the engine validates.

**2. The boundary validator** checks the evidence contract against
`../../gates.yaml`:

```bash
python ../../harness/gatekeeper/check.py --boundary review-to-delivery --package <phase>/manifest.json [--prior <prior-verdict-file>] --verdict-out <phase>/verdict_review-to-delivery.json
```

It confirms the six required keys are present and non-falsy, that
`executed_probes` and `rendered_verification` resolve to hashed artifacts whose
`inputs` still match their sources by sha256, that `review_verdict` and
`findings` are correctly shaped typed records, and that no blocked phrase or
broken local link is present. Exit 0 is a mechanical fact, not approval; exit 2
is an engine error and never a pass.

**The two key spaces do not overlap, and that is the trap.**
`scripts/check.py` names package-shape keys — `lens_bug`, `lens_code`,
`lens_quality`, `lens_security`, `lens_adversarial`, `lens_cso` — that describe
which lens reports a review package must contain. The boundary validator names
the six gate-spec evidence keys in the Boundary Contract above. No name appears
in both spaces, so nothing looks like a collision and it is easy to read five
green lenses as a satisfied contract. It is not one: every required evidence key
can still be missing when all five lenses are present.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in `skills/routing-doctrine.md`; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

Clause 6 binds directly, because this skill owns the `review-to-delivery` gate.
Every return carries all six fields:

- **Outcome** — the boundary judged and what the package may now do
- **Evidence** — both validator results plus the artifacts actually inspected
- **Open risks** — `residual_risk` and any preserved contradiction
- **Next action** — the owner-grouped `REVISE` packet, or the delivery handoff
- **Revision** — the submitted package revision
- **Verdict** — `APPROVED` / `REVISE` / `ESCALATE`

A verdict returned without its evidence anchors is incomplete and is not a gate
result.

Clause 4 has a concrete local form here: `<package-dir>` is untrusted review
context. `scripts/check.py` resolves it, requires an existing directory inside
the working tree, and exits 2 without running the gate otherwise; confirm the
same before invoking and return `ESCALATE` naming the rejected path.

## Workflow

1. Run `scripts/check.py` to verify that the consolidated review package includes the right revision lineage, core lens coverage, and optional-skip justifications before evaluating delivery readiness.
2. Run the boundary validator against `../../gates.yaml` for `review-to-delivery` and confirm the six required evidence keys are present and non-falsy, that `executed_probes` and `rendered_verification` resolve to hashed artifacts whose `inputs` still match their sources, and that `review_verdict` carries its challenge record when it is not APPROVED. Read the required-evidence list from the spec, never from memory; a clean lens sweep says nothing about these keys.
3. Cross-check the submitted review evidence against the underlying specialist reports so every blocker, skip, and approval points to visible evidence.
4. Decide whether the consolidated review package is ready for delivery, needs another review round, or must escalate, and record the narrowest justified verdict, grouped by the owner each failing key belongs to.
5. Persist a verdict record with mandatory fixes, evidence anchors, and idempotent revision notes so the same review package is not re-gated under conflicting rationale.

## Required Contracts

- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **CSO lens coverage**: When a review package claims security leadership signoff, accepted-risk readiness, release security posture, regulated-data governance, or operating-model control review, require a `review/cso` packet or an explicit scoped skip reason.
- **Harness-doctrine citation**: When the package adds or changes a cross-cutting runtime intervention, check it against `../../harness-doctrine.md` §5 and cite the violated section by number in the verdict.
- **Batched REVISE** (`../../gates.yaml` `revise_policy`): A `REVISE` carries every mechanical failure and every judgment finding from the pass, grouped by owner exactly as `check.py` reports them in `revise_packet.by_owner`; never return the first defect alone. On a resubmission run with `--prior`, re-judge only `changed_evidence` and carry the prior judgment on `unchanged_evidence`; the mechanical pass always covers the whole package. A package that fails mechanically was never eligible for submission (the submitter self-checks) and is returned without judgment.

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
| `rendered_verification` carries a bare explanatory string — "UI unchanged", "no screenshots needed" — instead of a `render` record or the sanctioned waiver | Return REVISE to `design-qa`. The only admissible waiver is the typed applicability record naming reason, scope, and decided_by for "no visible surface changed - rendered verification not applicable"; any other string fails the artifact-backing check before judgment begins. |
| `executed_probes` or `rendered_verification` carries `inputs` whose sha256 no longer matches the source file (`input hash drift`) | Return REVISE to the key's owner — `code-chief` for probes, `design-qa` for renders. The source changed after the evidence was captured, so the evidence proves a state the package no longer ships. |
| The boundary validator exits 2 — missing or malformed gate spec, unknown boundary, unreadable manifest | Return ESCALATE. An engine failure is never approval, and the gate spec is never bypassed to keep a run moving. |
| `scripts/check.py` cannot run (Python unavailable, permission error, `<package-dir>` rejected by the containment guard) or exits with internal-error code 2 | Treat the gate as NOT satisfied — do not default to APPROVED. Surface the error, then choose ESCALATE (or REVISE) instead of a silent pass. A gate that fails open is worse than no gate; an unknown pre-check result is not evidence of readiness. |

## Save Protocol

A gatekeeper writes exactly one path class: the durable verdict record at
`skillset-saves/runs/{run-id}/review/verdict_review-to-delivery.json`
(`../../save-ownership.yaml`, class `gate-verdict`), produced by the boundary
validator against `../../gates.yaml`:

```bash
python ../../harness/gatekeeper/check.py --boundary review-to-delivery --package skillset-saves/runs/{run-id}/review/manifest.json --verdict-out skillset-saves/runs/{run-id}/review/verdict_review-to-delivery.json
```

It never modifies the submission, its evidence, or the run record;
`review/code-chief` records the semantic verdict in its next checkpoint.
`gatekeeper-admiral` later re-validates the same boundary with
`--prior review/verdict_review-to-delivery.json` and writes its own record beside
it as `verdict_review-to-delivery.cross-stage.json`. When persistence is
inactive, return the verdict inline and preserve the run and revision.

## References

- `scripts/check.py` for the package-shape validator and this boundary's lens manifest.
- `references/boundary-evidence.md` for what each evidence key must be: record type, artifact-backing, and the exact sanctioned waiver text.
- `../../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/examples.md` for worked `review-to-delivery` submissions.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, `references/boundary-evidence.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which it locates by walking up to the repo root — ship the `harness/gatekeeper/` directory alongside the gatekeeper skills. Keep generated reports and archives outside the skill directory.
