# Workflow Reference

Read this for the operating sequence behind `../SKILL.md`. Scan-record mechanics
live in `scan-evidence.md`; worked outputs live in `examples.md`.

## Contents

1. Security review sequence
2. Decision rules
3. Acceptance checklist
4. Contract notes
5. Collaboration notes

## Security Review Sequence

1. Map the scoped trust boundaries, privileged paths, secrets, and dependency changes before declaring risk. Under `cso`, map against the threat model already scoped rather than building a second one.
2. Inspect the concrete security classes that fit the surface: authn/authz, exposure of sensitive data, injection paths, unsafe defaults, and third-party integration risk.
3. Record the dependency and source scan through `skills/scripts/scan_record.py`, binding every inspected manifest and lockfile with `--input`. Read `result.status` off the record; do not read the wrapper's exit code as the scan verdict.
4. For each major issue, capture attacker path, preconditions, affected assets, and the narrowest viable fix.
5. Package the vulnerabilities and hardening gaps with any adversarial handoffs — for `review/code-chief` inside the review pipeline, or as the `vulnerability_scan` record plus its findings for `cso` inside the security pipeline.

## Decision Rules

- Prefer demonstrated reachability over dependency-list fear alone.
- Separate confirmed exploitation paths from defensive hardening advice.
- Treat generated or vendored code with tighter scrutiny, but keep first-party ownership explicit in the finding.
- Preserve missing runtime or deployment evidence as a conditional boundary rather than assuming the strongest or weakest posture.
- A scan that did not run is a data gap, never a clean scan, and a limitation the consumer never sees becomes a coverage claim nobody made.
- Never reproduce a discovered credential in a finding, a packet, or a retained evidence file; report its location and type and call for rotation.

## Acceptance Checklist

- Each major issue names the affected trust boundary or asset.
- Reachability and preconditions are explicit for confirmed vulnerabilities.
- Dependency and vendored-code findings distinguish exposure from ownership.
- Conditional risks are called out when deployment evidence is missing.
- The scan record exists, its `result.status` is reported as observed, and every inspected manifest and lockfile is bound by `--input`.
- No finding, packet, or retained output carries a raw secret value.

## Contract Notes

- Vendoring detection: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- Before/After Evidence: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- Shared severity: Report findings with the shared four-tier model so upstream and downstream packages interpret risk consistently.
- Secrets handling: A credential encountered during the review is flagged by location and type, never reproduced, and treated as Critical until rotation is confirmed.

## Collaboration Notes

- `review/code-chief` merges the security packet with correctness, merge-readiness, and adversarial findings, and owns the `review-to-delivery` boundary this lens feeds.
- `review/gatekeeper-code` verifies that blocking vulnerabilities and unresolved exposure questions remain visible in the final review package.
- `review/cso` owns the `security` pipeline, scopes the engagement, supplies the threat model, and submits the `security-review` boundary. This skill runs the `posture-assessment` stage for it and returns the `vulnerability_scan` record; `cso` triages, plans remediation, and closes the boundary. The record is handed over unchanged — restating it in `cso`'s vocabulary would make two copies of one piece of evidence.
- `review/mr-robot` chains the weaknesses this lens flags into executed probes and owns `denial_path_evidence` at the same boundary; a weakness worth pressure-testing is named in the handover rather than probed here.
- `build/security-builder` supplies build-phase hardening evidence as an input and owns the authorized fixes downstream, at the `remediation` stage of the same pipeline.
