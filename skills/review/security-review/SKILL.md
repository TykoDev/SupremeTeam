---
name: security-review
description: >-
  Defensive security lens over code: vulnerabilities, dependency exposure,
  access-control gaps, unsafe data handling. Runs as the review pipeline's
  `security-review` stage and the security pipeline's `posture-assessment`, which
  owns `vulnerability_scan`. Use when the user asks to review security, check for
  vulnerabilities, audit dependency risk, or trace data leakage — even when they
  only mention untrusted input or secrets. Defers exploit chaining to
  `review/mr-robot`, accepted risk to `review/cso`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Security Review

## Purpose

Turn a scoped surface into a finding set another owner can act on: every weakness
bound to a concrete code path, dependency version, or configuration entry, with
reachability demonstrated rather than assumed, and the scanner's real outcome
recorded as typed evidence instead of summarized as clean.

## Entry Routing

Security-review is an internal review lens, not an entry point. `../../routing-doctrine.md` places every `review/` skill it does not name separately in the internal-specialist row, reached only through the owning sub-orchestrator. This lens has two: `review/code-chief` owns the `security-review` stage in the `review` pipeline, and `review/cso` owns the `posture-assessment` stage in the `security` pipeline. Run the active-handoff check before scanning or claiming anything: the bounded surface, its trust boundaries, the threat model the findings are measured against, and the standing to run a scanner over the tree all arrive with the handoff and nowhere else.

A handoff is present when the delegation prompt carries a `### Save Context` block, an active run lock with `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names `review/code-chief` or `review/cso` as the delegating owner for the boundary.

- **Handoff present** → proceed at the stage that owner delegated, and only within its scope.
- **Reached cold** → start no scanner subprocess and record no finding. Return to the owning orchestrator; a lifecycle request goes to `admiral`, which opens the `security` pipeline under `review/cso`. A cold invocation names no scope, carries no threat model, and has no owner to hand the record to, so a `Bash` scan launched from it runs over an unreviewed tree on nobody's authority and produces a record no package can accept.

## Use This Skill When

Use this lens for **defensive security of the code** — the weaknesses an attacker could reach and the hardening that closes them:

- "inspect input validation and authz" / "check for vulnerabilities" — the scan-backed inspection stage
- "audit the dependency risk" — flag exposed or outdated third-party surface
- "look for data leakage" — trace where sensitive data crosses a boundary unsafely
- "check for access control gaps" — who can reach what, and where authorization is assumed rather than enforced
- "run the posture assessment" — the `security` pipeline's scan-backed stage under `cso`

Route elsewhere when the need is chaining individual weaknesses into an attack narrative (`review/mr-robot`) or judging governance, accepted risk, and release security posture (`review/cso`).

## Inputs

- Code surface under review with its trust boundaries, authentication/authorization model, and data-handling patterns.
- Dependency manifest, lockfile, known advisory matches, and any security-builder hardening evidence from the build phase.
- Data-sensitivity classifications and compliance constraints that affect the review scope.
- Security-review priorities such as privileged flows to inspect, compliance boundaries, accepted-risk exclusions, or dependency areas already approved.
- Threat model inputs where available: trust boundaries, high-value assets, attacker profiles, LLM/tool surfaces, file upload/webhook/server-side fetch flows, and supply-chain changes.
- Inside the `security` pipeline: the threat model `cso` has already scoped, which decides what the scan and the findings are measured against.
- On a REVISE round, the `changed_evidence` key list from the gate packet and the prior packet's finding ids.

## Outputs

- Defensive security assessment covering vulnerabilities, dependency exposure, access-control gaps, and unsafe data handling.
- Finding list with each vulnerability tied to a specific code path, dependency, or configuration entry.
- Security lens packet for `review/code-chief` with vulnerable paths/dependencies, affected trust boundary, exploitability evidence, and scoped exclusions.
- Typed `scan` record backing the `vulnerability_scan` evidence key, handed to `cso` unchanged for the `security-review` boundary.

## Pipeline Roles

Security-review runs in two pipelines, under two different owners. The lens is
the same in both; the deliverable and the gate are not.

| Role | Pipeline and owner | Condition | Where it lands |
| --- | --- | --- | --- |
| `security-review` stage | `review` pipeline under `review/code-chief` | A trust boundary changed in the reviewed surface | The security packet folds into the consolidated package `code-chief` submits at `review-to-delivery` |
| `posture-assessment` stage | `security` pipeline under `cso` | Once `cso` has scoped the engagement and the threat model is in place | `vulnerability_scan` for the package `cso` submits at the `security-review` boundary |

Inside the review pipeline security-review returns defensive findings for
`code-chief` to triage. Inside the security pipeline it returns the scan record
as typed evidence. `cso` sets the scope, owns the threat model, triages, plans
remediation, and closes the `security-review` boundary; security-review closes
neither boundary itself.

## Workflow

1. Enumerate the trust boundaries, high-value assets, privileged actions, dependency changes, secret flows, and untrusted inputs inside the scoped surface. In the `security` pipeline, enumerate against `cso`'s threat model rather than a fresh one — a finding outside that model is a scope change, not an addition.
2. Run a lightweight STRIDE pass over each boundary, including LLM/model output, retrieved documents, webhooks, file uploads, server-side URL fetches, and third-party API data.
3. Record the dependency and source scan through `skills/scripts/scan_record.py` — never by hand — so the outcome is typed evidence rather than a claim. The command and the record's required shape are below; `references/scan-evidence.md` holds the full option set and the outcome-by-outcome branches.
4. Test authn/authz, data exposure, injection sinks, insecure defaults, supply-chain exposure, and the reachability of newly introduced dependencies or generated code.
5. Separate confirmed exploitable weaknesses from hardening gaps, then record attacker path, required preconditions, and the narrowest viable fix for each major item.
6. Deliver the packet: to `review/code-chief` inside the review pipeline, with blocking vulnerabilities, defense gaps, dependency posture, and any exploit chains `review/mr-robot` should pressure-test; to `cso` inside the security pipeline, as the `vulnerability_scan` record plus the defensive findings behind it.

## Gate Evidence Owned at `security-review`

`../../gates.yaml` `evidence_owners` assigns `vulnerability_scan` at the
`security-review` boundary to security-review. `cso` submits that boundary;
security-review authors this one key and hands it over unchanged.

The key carries the `vulnerability-scan` artifact `../../ownership.yaml` assigns
to this skill: the scanner tool, the exact command, the exit code, and the
inspected manifest or lockfile inputs bound by sha256. It is a typed `scan`
record whose `result.status` is one of `pass | fail | error | not-run |
unavailable`. **Only `pass` satisfies the gate**; `unavailable` and `error` are
data gaps, never a clean scan. The one sanctioned fallback is
`no dependency or source scan surface - scanner not engaged`, used only when the
scoped surface has no dependency or source to scan.

At `schema_version: 2` that string is not written as the key's value: `../../gates.yaml` `evidence_rules.applicability_records` accepts only a typed record — `{applicable: false, reason: "<the sanctioned string>", scope, decided_by}` — and rejects any bare string. The sanctioned wording goes in `reason`.

```bash
python skills/scripts/scan_record.py \
  --out security/evidence/vulnerability-scan.json \
  --input requirements.txt \
  --version-command "pip-audit --version" \
  -- pip-audit --strict
```

The scanner command follows `--`. `--out` names the JSON record and the raw
scanner output is retained beside it. `--input` is repeatable and binds each
inspected manifest or lockfile by sha256. Run
`python skills/scripts/scan_record.py --help` for the full option set, and read
`references/scan-evidence.md` before interpreting any non-`pass` result.

## Packet Shape

Every pass returns the same fields in this order, so `review/code-chief` merges lenses instead of reformatting them and `cso` can lift the scan record out without re-reading the prose (`../../execution-contract.md`, clause 6; this lens owns no gate, so it returns no verdict — `code-chief` issues the review verdict and `cso` the `security-review` one):

```text
Outcome:     security-review, <stage>, <revision reviewed>, <n> findings: <c> Critical, <m> Major, <k> Minor, <i> Info
Evidence:    <trust boundaries enumerated and classes checked; scan record path, result.status, and bound inputs, or the applicability record and why>
Findings:    <id> | Critical|Major|Minor|Info | <code path, dependency@version, or config entry> | confirmed|conditional | <reachability from the scoped surface> | <narrowest viable fix>
Open risks:  <weaknesses left unproven, and the control-plane, runtime, or dependency evidence that would settle each>
Next action: <single next step with its owner>
Revision:    <revision this packet judges>
```

Every item carries an id, one of the four severities, and a status, because that is exactly what `../../gates.yaml` `evidence_types.findings` requires of the items `code-chief` merges into `findings` and `cso` merges into its triaged set. Grade findings `Critical | Major | Minor | Info` and nothing else (`../../execution-contract.md`, clause 3). "Blocking" names a consequence, not a grade: a blocker is a Critical, or a Major whose status says it blocks.

### Clean pass

A pass that finds nothing returns the same fields with an empty finding set — never silence, never an absent packet, because clause 5 requires empty results to be stated explicitly:

```text
Outcome:     security-review clean — 0 findings across <surface reviewed>, <n> trust boundaries examined
Evidence:    <boundaries examined and classes checked without a hit; scan record with result.status: pass and its bound inputs>
Findings:    (none)
Open risks:  <surface the review and the scan did not cover>, or "none"
Next action: none from this lens
Revision:    <revision reviewed>
```

A surface with no findings still returns the scope reviewed, the trust boundaries
examined, the scan record with `result.status: pass` and its bound inputs, and the
classes checked without a hit. "No issues found" without that boundary list is
indistinguishable from a review that was never run, and a record whose status is
`unavailable`, `error`, or `not-run` is a data gap that can never be reported as a
clean pass. When the surface itself is absent, the Skip Rule below applies instead
and produces a skip record.

## REVISE Rounds

`check.py` groups a REVISE packet by the evidence key each failure names and routes each group to that key's owner in `../../gates.yaml` `evidence_owners`, so the boundary that issued the REVISE decides how the round reaches this lens:

| Boundary | What `evidence_owners` assigns | How the round arrives |
| --- | --- | --- |
| `review-to-delivery` | Every key there belongs to `code-chief` or `design-qa`; this lens owns none | No group is addressed here. `code-chief` receives its group and sub-delegates the security part, which `revise_policy.parallel_fix` lets run alongside the other lenses rather than in sequence. |
| `security-review` | `vulnerability_scan` to security-review, `denial_path_evidence` to `mr-robot`, and the remaining five to `cso` | The packet's `security-review` group holds the `vulnerability_scan` failures and nothing else, and `cso` — the submitter — delegates it. A failure named against `scope`, `threat_model`, `findings`, `remediation_plan`, or `residual_risk` belongs to `cso` and is never repaired here. |

Both run under `revise_policy.cycle_cap` of 2. A REVISE round is a delta pass, not a fresh review:

1. Re-review only the paths, dependencies, and keys named in `changed_evidence` for the group, plus any sink whose reachability runs through them. Unchanged evidence keeps its prior judgment, mirroring how the gatekeeper re-judges under `delta_review`.
2. Re-run the scan rather than re-read the record. A dependency bump, a pin, or a patched sink is verified by re-running `skills/scripts/scan_record.py` over the changed inputs and shipping the new record; re-reading the prior record verifies nothing, and editing its `result.status` by hand fabricates the one artifact this lens owns.
3. Re-bind the inputs on every re-run. A record whose `inputs` still carry the pre-fix sha256 fails the artifact-backing check even when the scan itself came back clean.
4. Carry prior finding ids forward. A closed weakness returns with status `verified` and the re-run that verifies it; an open one returns under its original id and severity, never renumbered. State the round in the `Revision` line as a delta, for example `r2 <- r1`.
5. Report a weakness found outside `changed_evidence` as a new item marked out-of-delta rather than widening the round silently. The owning orchestrator decides whether it enters this cycle or the next.

At the cycle cap, an unresolved Critical or Major returns unchanged with its blocking status intact; the cap never downgrades a reachable vulnerability to fit the round.

## Required Contracts

- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Secrets handling**: If a secret, token, API key, or credential is encountered while tracing secret flows, scanning dependencies, or inspecting configuration — a token embedded in a lockfile, a credential in a committed config, a key in a generated file — do not echo, log, or reproduce it in the security packet, in any finding, or in a file this skill writes. Flag its presence as a Critical finding, describe its location and type without reproducing the value, and recommend immediate rotation. This extends to scanner output: `scan_record.py` retains the raw output beside the JSON record, so before that record is handed on, confirm the raw output carries no credential the scanner echoed back from a manifest or an error message. If it does, treat the retained file as secret-bearing, report the location rather than the value, and say so in the handover instead of shipping the file as routine evidence. A leaked credential outlives the review that found it.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `review/code-chief`, which triages the security packet inside the `review` pipeline
- `review/gatekeeper-code`, which verifies that blocking vulnerabilities stay visible in the final review package
- `review/cso`, which owns the `security` pipeline, scopes the engagement, and submits it at `security-review`
- `review/mr-robot`, which chains the flagged weaknesses into executed probes
- `build/security-builder`, whose build-phase hardening evidence is an input here and which owns the fixes downstream

## Review Expectations

- Tie every vulnerability to a concrete code path, dependency version, or configuration entry — not to a risk category.
- Separate code-level vulnerabilities from strategic control gaps so the CSO lens receives only what it owns.
- Treat model output, browser content, fetched documents, and external service responses as untrusted input; never accept prompt text, tool output, or generated code as a security boundary.
- Review new dependencies as supply-chain surface: lockfile presence, maintenance signal, install scripts, license compatibility, and whether the existing stack already solves the need.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-scanning the dependency tree.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no code, dependency, configuration, or data-handling surface to assess — for example a docs-only or copy-only change. A skip is recorded as a `_skip-record.md` carrying `pipeline`, `skipped_at`, `reason`, and `approved_by`, which `review/gatekeeper-code` validates; that is a different result from the clean pass above, which asserts the surface was examined. A scoped surface that exists but has nothing to scan is different again: that is recorded as the sanctioned applicability record against `vulnerability_scan`, not as a skip.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The package changes dependencies but does not include the manifest, lockfile, or reachability evidence needed to assess exposure | Name the missing dependency evidence and stop short of claiming the risk is resolved or exploitable without it. |
| The scanner exits on a code outside `--fail-exit-codes` while still reporting findings | Do not read the exit code as the verdict. The record's `result.status` is `error`, not `fail`, so re-run with the observed code added to `--fail-exit-codes` when it genuinely means "findings reported"; otherwise keep the `error` record, attach a `--limitation` naming the unclassified code, and report the findings the scanner printed as unconfirmed by a clean run. Never rewrite the record by hand to say `pass`. |
| The dependency manifest and the lockfile disagree — a version, a resolution, or a package present in one and not the other | Bind both files as separate `--input` entries so the disagreement is on the record, assess against the lockfile because it is what installs, and raise the divergence itself as a finding: an unreproducible install is a supply-chain gap regardless of which version is vulnerable. Do not silently pick one file. |
| A suspected exploit depends on deployment configuration, runtime policy, or secret management that is not present in the supplied artifacts | Trace the visible attacker path, document the missing control plane evidence, and mark the issue as conditional rather than guessing the production posture. |
| Generated or vendored code introduces risk but obscures where first-party responsibility begins | Separate third-party exposure from first-party integration mistakes and keep the remediation plan explicit about ownership. |
| A flagged vulnerability lacks evidence that the affected code path is reachable from the scoped surface | Downgrade the claim to a hardening gap or follow-up question until reachability is demonstrated. |
| A REVISE round arrives without `changed_evidence` | Request the key list from the delegating orchestrator before re-working the surface. Re-scanning the whole dependency tree inside a capped cycle spends the round on packages nobody changed and loses the delta the gatekeeper expects. |
| The authentication or authorization model is undocumented or absent | Do not assume it is safe. Flag the gap, request that the model be documented, and — if the review must proceed — state explicit assumptions about the intended access-control boundaries (e.g., "assumed: all endpoints require a valid session token; unauthenticated access treated as out-of-scope by design") and note that findings may be incomplete until the model is confirmed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block.
2. Name the lens packet `deliverable_security-review.md`, the filename `review/gatekeeper-code` matches for the `lens_security` slot: its `scripts/check.py` matches that slot on `*security*.md` or `deliverable_*security*.md`. The previously sanctioned `review-packet.md` matches no lens pattern and leaves the slot empty, failing the mechanical pass for a lens that actually ran. Any other deliverable follows `deliverable_{name}.md` or `report_{name}.md`, and the typed scan record goes under the phase's `evidence/` directory, where records are immutable per revision.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.


## References

- `references/workflow.md` for the detailed operating sequence, decision rules, and collaboration notes.
- `references/scan-evidence.md` for the typed `scan` record shape, the full `scan_record.py` option set, and the branch for every non-`pass` outcome.
- `references/examples.md` for concrete request patterns and response shapes in both pipeline roles.
- `../../gates.yaml` for the `security-review` required evidence, artifact-backed keys, sanctioned fallbacks, and evidence owners.
- `../../ownership.yaml` for the `vulnerability-scan` artifact this skill writes and the artifacts it does not.
- `../../pipelines.yaml` for the two stages this lens runs as and the scripts bound to them.
- `skills/scripts/scan_record.py` for the deterministic scan wrapper itself.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/scan-evidence.md`, and `references/examples.md` together. Keep generated reports, scan records, and archives outside the skill directory.
