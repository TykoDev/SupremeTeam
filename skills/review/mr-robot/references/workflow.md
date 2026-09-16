# Workflow Reference

Read this when working a surface adversarially and deciding what a chain proves.
`../SKILL.md` holds the normative packet shape, gate evidence, and save rules, and
`probe-protocol.md` holds everything about executing a probe; this file holds the
sequence and the judgment calls inside it.

## Contents

1. Adversarial review sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Adversarial Review Sequence

1. Map attacker starting points, trust boundaries, privileged actions, and assets worth targeting in the scoped surface.
2. Search for abuse chains that combine weak authorization, unsafe defaults, race conditions, data exposure, or privileged state transitions.
3. Record the chain with preconditions, steps, impact, and the controls that would break it.
4. At the `adversarial-probe` stage, clear the envelope in `probe-protocol.md`, execute one probe per request class at each boundary in scope, and write the redacted log as it runs.
5. Package confirmed and conditional exploit paths separately for `review/code-chief`, or the hashed probe log and its record for `review/cso`.

## Decision Rules

- Favor chained attacker behavior over isolated lint-style security comments.
- Preserve uncertainty whenever a link in the chain depends on missing runtime or tenancy evidence.
- Keep offensive reasoning safe: describe the path and mitigation without escalating into unsafe reproduction.
- Treat the envelope as a precondition, not a preference: an unauthorized probe is not a weaker probe, it is an unattributable request against someone else's system.
- Prefer the sanctioned fallback value to a plausible narrative when probing was withheld; the fallback exists so the honest answer is representable.
- Hand non-chained defensive flaws back to `review/security-review` so the adversarial packet stays focused.
- Write hardening as containment direction, never as an edit: a patched surface cannot be re-probed to show the boundary now holds.

## Acceptance Checklist

- Each major chain names attacker entry point, steps, and impacted asset.
- Confirmed and conditional links are separated clearly.
- Containment or break-the-chain guidance is explicit.
- The attacker model is stated, including when it is the assumed default.
- Every executed probe row carries a boundary, a class, an observed response, and a verdict; every withheld probe carries its reason.
- The probe log is redacted at write time and hashed into the manifest, or `denial_path_evidence` carries the sanctioned fallback value.
- Every item carries one of the four shared severities, and a surface with no reachable chain returns the clean-pass packet naming what was tried.
- Cross-handoffs to the defensive security lens are named when needed.

## Contract Notes

`../SKILL.md` states the contracts; this section records only where each one
lands in the sequence above, so the two documents do not restate each other.

- Read-only over the reviewed surface — binds from step 1 through packaging; the containment written at step 3 is the deliverable, and hardening applied here would destroy the boundary state step 4 must probe.
- Before/After Evidence — the "before" is the boundary behavior observed at step 4, which is what a later claim that hardening closed the chain is re-probed against.
- Shared severity — assigned at step 3 on reachability and blast radius, and an `allowed` probe row at step 4 is graded Critical regardless of how narrow the request looked.
- Save-Protocol Adherence — the step 5 packet is what the save path receives, under the filename `../SKILL.md` mandates, with the redacted probe log stored as hashed evidence beside it.

## Collaboration Notes

- `review/code-chief` merges the adversarial packet with correctness, security, and merge-readiness findings at the `penetration-review` stage.
- `review/cso` owns the `security` pipeline: it scopes the engagement, authorizes active probing, consumes `denial-path-evidence`, owns the remediation plan, and submits the package at `security-review`.
- `review/security-review` takes standalone defensive flaws handed back from the chain, and supplies the dependency and hardening findings that seed candidate exploit primitives.
- `review/gatekeeper-code` verifies that exploit-chain evidence survives consolidation without being softened away.
