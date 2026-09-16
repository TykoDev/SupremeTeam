---
name: cso
description: >-
  Owns the `security` pipeline end to end, normally invoked by `admiral`, and issues
  the verdict at `security-review`: it runs threat modelling, posture assessment,
  adversarial probing, triage, and authorized remediation as one engagement rather
  than performing any of them itself. Use when `admiral` delegates a security
  engagement, or the user wants a whole security oversight pass over a system — an
  audit, a threat model, a hardening round, or a challenge to accepted risk. A single
  dimension goes to the lens that owns it: `review/security-review` scans,
  `review/mr-robot` probes.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# CSO

## Purpose

Make a security engagement answerable. Scanners, probes, and opinions each
produce a partial picture; this skill is where they are reconciled against one
threat model, so that every finding traces to a modelled asset, every control is
credited only on evidence that it operates, and whatever is left standing is
named as accepted risk with an owner rather than disappearing between the three
specialists who each saw part of it.

## Entry Routing

This skill is a component of the **Admiral** delivery pipeline; `admiral` is the primary entry orchestrator (see `../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names this skill as the owning sub-orchestrator for the security boundary.

- **Handoff present** → proceed; the run is active inside an Admiral run.
- **No handoff (cold/direct invocation)** → do not run standalone. Start `admiral` first and let it run intake, persistence, and gatekeeping, then accept the delegation back. This is the loop guard: Admiral's own delegations always carry the handoff signal, so a delegated call proceeds immediately and never re-bootstraps Admiral.

## Use This Skill When

Use this pipeline for a **whole security engagement** — several lenses run, reconciled, and closed under one verdict, not a single scan:

- "audit this system's security" — the unscoped security request, scoped and sequenced here
- "build the threat model for this surface" — entry points, assets, and adversaries, before any scanning
- "run the security oversight pass" — own the engagement end to end and issue the `security-review` verdict
- "run the hardening and remediation round" — triage what the lenses found, then authorize the fixes
- "challenge the security posture and the accepted risk" — reopen a risk the team has already accepted

Recurring security checkpoints inside a delivery run are not this pipeline:
`build/security-builder` owns `security_seed` at design and `security_evidence`
at build, and `review/security-review` runs the conditional security lens inside
the `review` pipeline. A dedicated security engagement runs here.

## Inputs

- Admiral-normalized security request: the surface in scope (services, routes, data stores, operating model), the protected assets, the constraints, and the explicit non-goals.
- The application source, its dependency manifests and lockfiles, deployment and identity configuration, and a running instance when active probing is authorized.
- Whether **active probing** is authorized against the named environment, and by whom. The engagement owner named in the Admiral-normalized request authorizes it — never `cso` and never `mr-robot`, because the skill that benefits from the evidence cannot be the one that sanctions producing it. Record the decision in the scope section of the package, and carry it into the `denial_path_evidence` applicability record's `decided_by` field when probing is withheld, so the waiver names a person rather than a circumstance.
- Whether **remediation** is authorized in this engagement, and by whom; the `remediation` stage runs only under that authorization, recorded the same way in the scope section.
- Active security save context, prior verdicts, and revision lineage when resuming.

## Outputs

- `security-review-package` at `security/reports/security-review-package.md`: scope and protected assets, the threat model, the triaged finding set graded Critical | Major | Minor | Info, the remediation plan with an owner per finding, the fixes applied, and the residual risk with reopen triggers.
- `security/manifest.json` (schema 2, `boundary: security-review`, `owner: cso`) carrying every evidence key `../../gates.yaml` requires at `security-review`.
- Security escalation packet naming the blocked decision, the missing evidence boundary, the owner, and the recommended default.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under
   the Tier 0 fast path in routing-doctrine.md; Tier 1 for bounded read-only work beyond Tier
   0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3
   for destructive, security-sensitive, production, or irreversible work. Record the tier and
   rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline
   ceremony and full security audits, but retains focused verification and applicable
   guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request
   uses different words; decline adjacent work and route end-to-end or specialist ownership
   explicitly. Offer a next safe action only after the current step, scope, and approval
   lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a
   gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate
   verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations
   inside the workspace, use read-only or dry-run probes first, and require explicit owner
   intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty
   results, and unavailable checks explicitly: preserve evidence, do not fabricate, return
   REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns
   a gate. A concise result without evidence is incomplete.

## Workflow

The stage list, owners, and artifacts below are the `security` pipeline as
`../../pipelines.yaml` declares it. The prose elaborates those stages and never
contradicts them.

1. **scope-and-threat-model** (owner `cso`, artifact `threat-model`). Confirm the surface, the protected assets, the actors, and the trust boundaries before anything is scanned or probed, and enumerate abuse cases with severity. The threat model is the contract for the rest of the pipeline: a finding outside it is a scope change, and an asset absent from it is an unreviewed asset. Checkpoint through `session-memory` before the first delegation.
2. **posture-assessment** (owner `security-review`, artifact `vulnerability-scan`). Delegate `review/security-review` to inspect the code-level defensive posture and to record dependency and source scanning as a typed `scan` record through `skills/scripts/scan_record.py`. Only `result.status: pass` satisfies the gate; `unavailable`, `error`, and `not-run` are data gaps and are carried as such.
3. **adversarial-probe** (owner `mr-robot`, artifact `denial-path-evidence`). Delegate `review/mr-robot` to chain the modelled abuse cases into executed probes covering unauthorized, malformed, replayed, expired, and over-broad requests, and to record the observed denial at each boundary. When active probing is not authorized, the sanctioned applicability record replaces the probe log rather than a claim that the boundary holds.
4. **triage** (owner `cso`). Reconcile the scan, the probe evidence, and the threat model into one finding set graded Critical | Major | Minor | Info, and give each finding a remediation owner, a fix path, or an accepted-risk decision with a reopen trigger. `../../pipelines.yaml` declares no artifact for this stage; the outputs are the typed `findings` record and the `remediation-plan` artifact `../../ownership.yaml` assigns to `cso`. Tactical vulnerabilities and governance gaps stay distinguishable so remediation lands with the right owner.
5. **remediation** (owner `security-builder`, `when: fixes authorized`). Delegate `build/security-builder` to apply the authorized fixes, then re-run the affected scans and probes so the finding set reflects the fixed state rather than the intent to fix. Without that authorization the stage does not run and the finding set ships with its remediation owners named instead.
6. **package** (owner `cso`, artifact `security-review-package`). Assemble the package, write `security/manifest.json`, run the self-check below, and submit at the `security-review` boundary. Admiral routes the approved package through `gatekeeper-admiral`.

## Required Contracts

- **Threat model first**: No scan result or probe log enters the package before the threat model names the asset it protects. An unmodelled finding is triaged into the model or recorded as a scope change, never appended to the list silently.
- **Evidence over assertion**: A control is credited only when a scan record, probe log, or configuration artifact shows it operating. Staffing, monitoring, and escalation claims without that evidence are recorded as unverified control boundaries.
- **Vendoring detection**: Treat generated, vendored, and third-party imported content as part of the attack path whenever it influences a protected asset, and review it under tighter rules than first-party changes.
- **Secrets handling**: A secret, token, API key, or credential encountered anywhere in the engagement — in deployment or identity configuration, in a returned scan record, in a probe log, or echoed into the raw scanner output `scan_record.py` retains beside its JSON record — is never echoed, logged, quoted, or reproduced. That holds for the `security-review-package`, for every item in the typed `findings` record, and for every file written under `security/`. Flag its presence as a Critical finding, describe its location and type without reproducing the value, and require rotation before the finding closes. Before a delegate's evidence is hashed into the manifest, confirm the retained raw output carries no credential the scanner echoed back; if it does, say so in the package and treat that file as secret-bearing rather than shipping it as routine evidence. Everything in the package is durable, so a credential reproduced once outlives the engagement that found it.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from admiral, persist every stage artifact to the save path through the classes below and checkpoint through `session-memory` at every delegation and return. Saving is mandatory, not optional.

## Delegation Surface

- `review/security-review` (posture-assessment; the `vulnerability-scan` artifact behind the `vulnerability_scan` evidence key)
- `review/mr-robot` (adversarial-probe; the `denial-path-evidence` artifact behind the `denial_path_evidence` evidence key)
- `build/security-builder` (remediation, only when fixes are authorized)
- `gatekeeper-admiral` through `admiral` (the verdict at `security-review`)

## Gate Submission

CSO is the only submitter at the `security-review` boundary
(`../../gates.yaml` `boundaries.security-review`), which guards the security
pipeline to GATE to COMPLETE. The submission is `security/manifest.json` at
schema 2, declaring `boundary: security-review` and `owner: cso`, the `run_id`
when inside a run, and one `revision` value.

Seven evidence keys close the boundary: cso owns `scope`, `threat_model`,
`findings`, `remediation_plan`, and `residual_risk`, while `vulnerability_scan`
and `denial_path_evidence` are owed by the two delegates and pulled back into the
manifest at package time, unchanged. `references/gate-submission.md`
§ Ownership Split is the single copy of that division and of why a delegate's
key is never re-authored here.

Artifact-backing and waivability are two different lists, and only one key sits
on both. `../../gates.yaml` `artifact_evidence` at this boundary names
`threat_model` and `denial_path_evidence`; each must reference a path present in
`artifact_hashes`, so the evidence is a shipped, hashed file rather than a bare
claim. `fallback_values` is the only source of waivable keys
(`evidence_rules.applicability_records`: "Only keys listed in fallback_values are
waivable"), and for this boundary it names `vulnerability_scan` and
`denial_path_evidence`. `threat_model` therefore appears on the artifact list and
not on the waiver list: it is **unwaivable**, and a package without a hashed
threat model does not close this boundary by any route. At schema 2 a waiver is
an applicability record `{applicable: false, reason, scope, decided_by}`, never a
bare fallback string.

`references/gate-submission.md` holds the per-key table with its backing and
sanctioned fallbacks, the waiver rules, and the phase-lead save protocol that
produces the files this manifest hashes. It is the single stage-to-key map;
`references/workflow.md` runs the stages and does not restate it.

Self-check before submitting, per `../../gates.yaml` `revise_policy.self_check`:

```bash
python skills/harness/gatekeeper/check.py --boundary security-review --package <manifest.json>
```

Run it without `--verdict-out` and fix every mechanical failure first; a package
that fails the machine is never submitted, so the gatekeeper spends judgment only
on packages that already pass it.

## Deterministic Scripts

`../../pipelines.yaml` binds one deterministic script to the `security` pipeline:
`skills/scripts/scan_record.py`. It runs the scanner and records the outcome as a
typed `scan` record, so a clean scan stays distinguishable from every way a scan
can fail to happen.

```bash
python skills/scripts/scan_record.py \
    --project-root . \
    --out skillset-saves/runs/<run-id>/security/evidence/scan-pip-audit.json \
    --input requirements.txt \
    --version-command "pip-audit --version" \
    -- pip-audit -r requirements.txt --strict
```

The scanner command follows `--`; `--out` names the JSON record and the raw
output is retained beside it; `--input` is repeatable and binds each inspected
manifest or lockfile by sha256. Run
`python skills/scripts/scan_record.py --help` for the remaining options
(`--fail-exit-codes`, `--limitation`, `--timeout`, `--no-run`, `--tool`,
`--version-command`), and read `references/workflow.md` for how each outcome is
carried into the package.

Read the outcome off the record, not off the wrapper: the wrapper exits 0
whenever a record was written and 2 on wrapper error, so its exit code says
whether evidence exists while `result.status` says what the evidence shows.
`pass` only when the scanner itself exited 0; `fail`, `error`, `unavailable`, or
`not-run` otherwise. Only `pass` satisfies the gate.

## Boundary Rules

- Record the boundary before requesting a verdict, and name the revision the package carries.
- Reuse a prior verdict only when the boundary, submission, revision, package fingerprint, and gate spec digest are all unchanged.
- Push remediation back to the owning specialist instead of editing its artifact locally; batch every finding for one specialist into a single revision delegation and fan independent owners out in parallel.
- Treat a `REVISE` as one packet: delegate each owner group in `revise_packet.by_owner` in parallel and resubmit once with `--prior` so the gate re-judges only `changed_evidence`.

## Skip Rule

Never skip the threat model or the triage: they are what make the rest of the
evidence interpretable. The `remediation` stage is skipped whenever fixes are not
authorized, and the adversarial probe degrades to its sanctioned applicability
record when active probing is not authorized. Both are recorded decisions with a
named decider, never silent omissions.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Fixes are not authorized, so the `remediation` stage's `when: fixes authorized` condition is unmet | Apply nothing. Ship the finding set with a remediation owner and a fix path per item, carry `remediation_plan` as the plan rather than the applied change, and record every unremediated Critical and Major finding in `residual_risk` with a reopen trigger. A deferred Major requires a named owner and a reopen trigger inside the `findings` record. |
| The scanner is unavailable, times out, or exits on an unexpected code | Keep the `scan_record.py` record with its real `result.status` (`unavailable`, `error`, or `not-run`) and its `--limitation` entries. A missing scan is a data gap, never a clean scan: either record the sanctioned `vulnerability_scan` applicability record with reason, scope, and decider, or return `ESCALATE` naming the missing coverage. |
| The gate returns `REVISE` | Treat the packet as one unit: route every failure in `revise_packet.by_owner` to its owner in parallel, batching all findings for one owner into a single revision delegation, then resubmit once with `--prior` so unchanged evidence carries its prior judgment. `revise_policy.cycle_cap` is 2; a third cycle escalates instead of resubmitting. |
| A critical trust boundary depends on vendored code, managed services, or third-party identity flows that were not in the package | Keep the external dependency in scope, elevate the missing evidence, and refuse to let the first-party code alone define the posture. |
| A compensating control such as manual monitoring or after-hours approval is not staffed or tested in the real operating model | Preserve the governance gap as a blocker in `findings` rather than crediting a control that exists only on paper. |
| A delegate returns an artifact whose sha256 does not match the digest registered for it in the manifest or the prior checkpoint | Treat the manifest as wrong until proven otherwise, and do not re-hash the file to make it agree — that converts a detected substitution into a silent one. Re-request the artifact from its owner naming the expected digest, re-verify at the destination `output_paths.py` resolves, and register the new digest through a `session-memory` checkpoint so the revision lineage records which bytes the package actually carries. If the delegate confirms the file is correct and the digest is stale, the upstream revision moved: rewind to the earliest boundary that depends on it rather than patching the map. |
| The threat model and the returned findings disagree about which assets are in scope | Freeze packaging, route the mismatch back to the owning stage, and re-run triage against the reconciled model instead of normalizing it inside the package. |

**Clean pass.** An engagement that finds nothing still ships the full package: the
scope and the protected assets, the hashed threat model, the scan record with
`result.status: pass` and its bound inputs, the probe log showing the denial
observed at each modelled boundary, an empty-but-explicit `findings` record, and
a `residual_risk` value naming what the engagement did not cover. A security
package with no findings and no coverage statement is indistinguishable from one
where nothing ran.

## Save Protocol

When admiral delegates with `Persistence active: yes`, cso is the phase lead for
`skillset-saves/runs/{run-id}/security/`, and
`references/gate-submission.md` § Phase-Lead Save Protocol is the single copy of
the rest: the path classes `../../save-ownership.yaml` grants a phase lead, the
`output_paths.py` call that resolves every destination, the trigger-by-trigger
table of what cso writes at each point in the phase, and the canonical
`### Save Context` block to include verbatim in every specialist delegation.
Checkpoint through `session-memory` at every delegation and every return,
registering each returned artifact's sha256 as evidence. When Save Context is
absent or `Persistence active: no`, skip all save operations and return the
deliverable inline.

## References

- `../../pipelines.yaml` for the authoritative `security` stage list, stage owners, artifacts, and bound scripts.
- `../../gates.yaml` for the `security-review` required evidence, artifact-backed keys, sanctioned fallbacks, evidence owners, and the REVISE policy.
- `../../ownership.yaml` for the artifact writers behind `threat-model`, `vulnerability-scan`, `denial-path-evidence`, `remediation-plan`, and `security-review-package`.
- `../../execution-contract.md` for the canonical clause source and the tier table.
- `../../save-ownership.yaml` for the path classes a phase lead may write.
- `skills/scripts/scan_record.py` and `skills/scripts/output_paths.py` for the two deterministic tools this pipeline calls directly.
- `references/gate-submission.md` for the per-key evidence contract, waiver rules, the self-check, and the phase-lead save protocol with the Save Context block.
- `references/workflow.md` for the detailed stage order, delegation rules, and acceptance checklist.
- `references/examples.md` for concrete security-pipeline outputs, the submission manifest, and a REVISE round.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/gate-submission.md`, and `references/examples.md` together. Keep generated reports, scan records, and archives under the run's `security/` directory, never inside the skill directory.
