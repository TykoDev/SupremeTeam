# Workflow Reference

## Contents

1. Pipeline sequence
2. Stage-by-stage gate procedure
3. Decision rules
4. Acceptance checklist
5. Collaboration notes

## Pipeline Sequence

The `security` pipeline in `../../../pipelines.yaml` is owned by `cso` and closes at
the `security-review` boundary. Six stages, in order:

| Step | Owner | Artifact | Condition |
| --- | --- | --- | --- |
| scope-and-threat-model | cso | `threat-model` | always |
| posture-assessment | security-review | `vulnerability-scan` | always |
| adversarial-probe | mr-robot | `denial-path-evidence` | always |
| triage | cso | none declared | always |
| remediation | security-builder | none declared | `when: fixes authorized` |
| package | cso | `security-review-package` | always |

CSO runs stages 1, 4, and 6 itself and delegates 2, 3, and 5. The `review`
pipeline is a different pipeline with a different owner (`code-chief`) and a
different boundary (`review-to-delivery`); its conditional `security-review` and
`penetration-review` stages are lenses inside a code review, not this engagement.

## Stage-By-Stage Gate Procedure

Which stage fills which evidence key is mapped once, in the `Gate Submission`
table of `../SKILL.md` (its `Produced by` column). This section is the procedure
for running each stage, and deliberately does not restate that mapping.

**1. scope-and-threat-model.** Name the surface, the protected assets, the actors,
and the trust boundaries, then enumerate abuse cases with severity. Record who
authorized active probing and remediation, and who declined either. Write the
threat model to the destination `output_paths.py --kind reports` resolves and
register its sha256 through a `session-memory` checkpoint. The hash is what makes
`threat_model` artifact-backed at the gate; an unhashed threat model fails the
mechanical pass before any judgment is applied.

**2. posture-assessment.** Delegate `review/security-review` with the threat model
and the dependency manifests in scope. It records the scan through
`scan_record.py`, whose output carries tool, command, exit code, observed_at, and
`inputs` bound by sha256 to the inspected files. Verify `result.status` on return:
only `pass` satisfies the gate, and `fail`, `error`, `unavailable`, or `not-run`
is carried as the data gap it is. Carry every `--limitation` the delegate recorded
into the package; a limitation that stops here becomes a coverage claim nobody
made.

**3. adversarial-probe.** Delegate `review/mr-robot` with the modelled abuse cases.
It returns the executed probe log for unauthorized, malformed, replayed, expired,
and over-broad requests and the denial observed at each boundary. Hash the log
into the manifest; `denial_path_evidence` is artifact-backed. When active probing
is not authorized, carry the sanctioned applicability record instead, naming
reason, scope, and the person who declined — the `decided_by` value comes from the
engagement owner recorded at stage 1, never from `cso` or `mr-robot`.

**4. triage.** Reconcile scan, probes, and threat model into one finding set graded
Critical | Major | Minor | Info, each item carrying id, severity, status, and —
for a deferred Major — an owner and a reopen trigger, as `../../../gates.yaml`
`finding_policy` requires. Assign a remediation owner or an accepted-risk decision
per finding.

**5. remediation.** Only when fixes are authorized. Delegate `build/security-builder`
with the finding ids it owns, batched into one delegation, then re-run the
affected scan and probes so the evidence reflects the fixed state. Update
`remediation_plan` from planned to applied per finding.

**6. package.** Assemble `security-review-package.md`, write `security/manifest.json`
at schema 2 with `boundary: security-review` and `owner: cso`, then run
`python skills/harness/gatekeeper/check.py --boundary security-review --package <manifest.json>`
without `--verdict-out`. Fix every mechanical failure before submitting, then
close the boundary.

## Decision Rules

- Prefer the control boundary that actually governs the live system over the cleanest diagram or intended process.
- Treat third-party, vendored, and generated surfaces as part of the attack path whenever they influence the protected asset.
- Keep tactical bug findings distinct from strategic security-governance gaps so each lands with an owner who can act on it.
- A scan that did not run is a data gap, never a clean scan; a probe that was not authorized is an applicability record, never an assertion that the boundary holds.
- A returned artifact whose digest disagrees with the manifest is a substitution to investigate, never a map to silently correct.
- Never reproduce a discovered credential in the package, a finding, or a retained evidence file; report its location and type and require rotation.
- Escalate when the right mitigation requires policy, staffing, vendor, or product decisions beyond the current engagement scope.

## Acceptance Checklist

- The scope and the protected assets are explicit, and the threat model is hashed into the manifest.
- Every finding traces to a modelled asset and carries a severity from the shared four-tier model.
- A deferred Major names an owner and a reopen trigger; no Critical is deferred.
- The scan record's `result.status` and the probe log's status are reported as observed, not summarized as clean.
- The remediation plan names a fix owner per finding, and residual risk names what the engagement leaves standing.
- Probe and remediation authorization is recorded with the person who granted or declined it, and any waiver's `decided_by` matches that record.
- Every artifact hashed into the manifest was re-verified at its destination, and no finding or retained file reproduces a credential value.
- `check.py --boundary security-review` passes mechanically before submission.

## Collaboration Notes

- `admiral` routes dedicated security engagements to this pipeline and carries the approved package through `gatekeeper-admiral`; `cso` does not accept cold lifecycle work directly.
- `review/security-review` owns the `vulnerability-scan` artifact and the `vulnerability_scan` evidence key at this boundary; `cso` consumes them and never rewrites them locally.
- `review/mr-robot` owns the `denial-path-evidence` artifact and the `denial_path_evidence` evidence key; `cso` consumes them the same way.
- `build/security-builder` owns remediation here, and separately owns `security_seed` at design and `security_evidence` at build inside a delivery run.
- `review/code-chief` owns the `review` pipeline and the `review-to-delivery` boundary. It neither schedules this pipeline nor gates it; a security finding raised during code review reaches `cso` through `admiral` as a security engagement.
