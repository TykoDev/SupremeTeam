# Gate Submission Reference — `security-review`

Read this when assembling or repairing the manifest. `../SKILL.md` states which
boundary cso submits and when to run the self-check; this file is the per-key
contract behind it and the phase-lead save protocol that produces the files the
manifest hashes.

## Contents

1. Evidence keys and their backing
2. Ownership split
3. Artifact-backed keys and waivers
4. The self-check
5. Phase-lead save protocol
6. Save Context block for specialist delegations

## Evidence Keys and Their Backing

The submission is `security/manifest.json` at schema 2, declaring
`boundary: security-review` and `owner: cso`, the `run_id` when inside a run, and
one `revision` value. This table is the single stage-to-key map; `workflow.md`
runs the stages and does not restate it.

| Evidence key | Owner | Produced by | Backing |
| --- | --- | --- | --- |
| `scope` | cso | scope-and-threat-model | Stated in the package: surface, protected assets, actors, explicit exclusions, and who authorized probing and remediation. No sanctioned fallback. |
| `threat_model` | cso | scope-and-threat-model | Artifact-backed: the hashed `threat-model` artifact must appear in `artifact_hashes`. No sanctioned fallback. |
| `findings` | cso | triage | Typed `findings` record `{items: [{id, severity, status, owner?, reopen_trigger?, reason?}]}`. No sanctioned fallback. |
| `vulnerability_scan` | security-review | posture-assessment | Typed `scan` record from `scan_record.py` with hashed artifacts, tool, command, exit code, and `inputs` bound by sha256. Sanctioned fallback: `no dependency or source scan surface - scanner not engaged`. |
| `denial_path_evidence` | mr-robot | adversarial-probe | Artifact-backed typed `probe` record; the executed probe log is the hashed artifact. Sanctioned fallback: `static analysis only - active probes not authorized`. |
| `remediation_plan` | cso | triage, then remediation when authorized | Fix owner per finding, and accepted risk with a reopen trigger. No sanctioned fallback. |
| `residual_risk` | cso | package | The risk the engagement leaves standing, with its owner and reopen trigger. No sanctioned fallback. |

## Ownership Split

CSO owns five of the seven keys — `scope`, `threat_model`, `findings`,
`remediation_plan`, and `residual_risk` — per `../../../gates.yaml`
`evidence_owners.security-review`. The remaining two are owed by the two
delegates and are pulled back into the manifest at package time. Never author a
delegate's key locally: a key rewritten in cso's words is a second copy of
someone else's evidence, and the gate's REVISE packet can no longer route its
failure to the owner who can fix it.

## Artifact-Backed Keys and Waivers

Two keys are artifact-backed at this boundary: `threat_model` and
`denial_path_evidence`. Each must reference at least one path present in the
manifest's `artifact_hashes` map, so the evidence is a shipped, hashed file
rather than a bare claim.

The only sanctioned non-artifact values at this boundary are the two fallbacks in
the table above, and at schema 2 a bare fallback string is rejected: waiving one
of those two keys takes an applicability record
`{applicable: false, reason, scope, decided_by}`. `decided_by` names the
engagement owner who declined, not cso and not the delegate that would have
produced the evidence. The other five keys have no sanctioned fallback and cannot
be waived at all.

## The Self-Check

Run before submitting, per `../../../gates.yaml` `revise_policy.self_check`:

```bash
python skills/harness/gatekeeper/check.py --boundary security-review --package <manifest.json>
```

Run it without `--verdict-out` and fix every mechanical failure first; a package
that fails the machine is never submitted, so the gatekeeper spends judgment only
on packages that already pass it. On a `REVISE`, resubmit once with `--prior`
pointing at the verdict record, so unchanged evidence carries its prior judgment
and only `changed_evidence` is re-judged. Treat gate-engine failure as
`ESCALATE`, never as approval.

## Phase-Lead Save Protocol

When admiral delegates with `Persistence active: yes`, cso is the phase lead for
`skillset-saves/runs/{run-id}/security/` and writes only the path classes
`../../../save-ownership.yaml` grants a phase lead: `manifest.json`, `reports/`,
`artifacts/`, `evidence/`, and `packages/`. Resolve every destination with
`python skills/scripts/output_paths.py --run-id {run-id} --phase security --kind <reports|artifacts|evidence|manifest> --name <file>`;
never compose a path by hand, and never create nested per-specialist directories
or phase-state files, because no declared class covers them and phase state lives
in the run record. When persistence is inactive or read-only resume is in effect,
cso keeps the same stage sequencing but returns artifacts inline and propagates
`Persistence active: no` to specialists.

| Trigger | What CSO Writes |
|---------|-----------------|
| Phase start | Nothing on disk: the phase state is published through `session-memory` (`save_run.py checkpoint --run-id {run-id} --expect-revision <n> --owner cso --set phase_state=SECURITY_ACTIVE`; the active owner follows `--owner`, which `--set` refuses as a reserved field) before the first specialist delegation |
| Specialist delegation | The canonical `### Save Context` block (below) naming the specialist as `Owner`, the exact `reports/`, `artifacts/`, or `evidence/` destination as `Expected artifact`, and `security-review` as `Return boundary` |
| Specialist return | Verify the named artifact exists at its destination, then register its sha256 through a `session-memory` checkpoint (`--evidence <path>`) |
| Scan and probe evidence | Typed records under `security/evidence/`: `scan_record.py` writes the scan record, and the probing specialist writes the denial-path log. Immutable per revision |
| Gate submission | `security/manifest.json` (schema 2: `boundary: security-review`, `owner: cso`), carrying the hashed threat model, the scan record, the denial-path probe log, and the findings, remediation-plan, and residual-risk values |
| Phase-gate verdict | Nothing: the gatekeeper writes `security/verdict_security-review.json` through `check.py --verdict-out`; cso records the semantic verdict in its next checkpoint |
| Package consolidation | `security/reports/security-review-package.md` plus the manifest revision admiral submits to `gatekeeper-admiral` |

## Save Context Block for Specialist Delegations

The canonical field set from `../../../contracts/handoff-templates.md`; neither
file may drop a field the other carries.

```markdown
### Save Context
- Run ID: {run-id}
- Phase: security
- Save path: skillset-saves/runs/{run-id}/security/
- Persistence active: {yes|no}
- Persistence probe result: {ok|reason}
- Context tier: {1|2|3}
- Preamble tier: {0|1|2|3} + rationale
- Artifact mode: {inline|file|reference}
- Session pin: {true|false}
- Execution mode: {agent|skill}
- Submission ID: {id}
- Revision: {revision}
- Owner: {specialist}
- Expected artifact: {reports/...|artifacts/...|evidence/...}
- Evidence paths: {relative paths}
- Artifact hashes: {path: sha256|none yet}
- Risks: {known risks|none declared}
- Return boundary: security-review
```

When Save Context is absent or `Persistence active: no`, skip all save operations
and return the deliverable inline.
