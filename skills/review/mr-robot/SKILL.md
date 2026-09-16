---
name: mr-robot
description: >-
  Chains weak checks, unsafe defaults, and race windows into concrete attack
  narratives, and runs the authorized denial-path probes that show what a boundary
  does when it is attacked. Use when `review/cso` or `review/code-chief` delegates the
  adversarial pass, or the user asks to run adversarial review, think like an
  attacker, chain these weaknesses into an attack, work this surface from the outside,
  or look for exploit chains. A whole security engagement is `review/cso`; a
  standalone defensive flaw with no sequencing is `review/security-review`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---


# Mr Robot

## Purpose

Answers what an attacker could actually reach, and what the boundary does when they try. A single weak check is not the unit of work here: the unit is the sequence that turns several of them into a reachable outcome, and — inside the security pipeline — the executed probe that records the denial when that sequence is attempted.

## Entry Routing

Mr-robot is an internal specialist, not an entry point. `../../routing-doctrine.md` places every `review/` skill it does not name separately in the internal-specialist row, reached only through the owning sub-orchestrator. This lens has two: `review/code-chief` owns the `penetration-review` stage in the `review` pipeline, and `review/cso` owns the `adversarial-probe` stage in the `security` pipeline. Run the active-handoff check before probing or claiming anything: the attack surface in scope, the threat model, and — for any active probe — the authorization itself arrive with the handoff and nowhere else.

A handoff is present when the delegation prompt carries a `### Save Context` block, an active run lock with `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly names `review/code-chief` or `review/cso` as the delegating owner for the boundary.

- **Handoff present** → proceed at the stage that owner delegated, and only within its scope.
- **Reached cold** → run no probe of any kind and send no request to any target. Return to the owning orchestrator; a lifecycle request goes to `admiral`, which opens the `security` pipeline under `review/cso`. Active probing without a named authorizer is indistinguishable from an attack, whatever the intent behind it.

## Use This Skill When

This lens **thinks like an attacker** — chaining weak checks, unsafe defaults, and race windows into a concrete abuse narrative:

- "run adversarial review" / "think like an attacker" — start from attacker entry points and trust boundaries
- "chain these weaknesses into an attack" — sequence individual weaknesses into a reachable exploit
- "look for exploit chains" — hunt for the reachable sequences, with no weakness list supplied first
- "run the denial-path probes" — show what the boundary actually does when it is attacked, under authorization
- "work this surface from the outside" — against its own assumptions, inside an authorized engagement

Route elsewhere when the item is a standalone defensive flaw with no meaningful chaining (`review/security-review`) or a governance / accepted-risk decision (`review/cso`).

## Inputs

- Code surface under review with its attack surface, entry points, and trust-boundary topology.
- Security-review findings and dependency advisories that identify candidate exploit primitives.
- Operational context such as deployment model, exposed services, and external dependency trust levels.
- Adversarial-review priorities such as high-value assets, attacker profiles, excluded abuse cases, or accepted-risk boundaries.
- Abuse-case seeds from design or security review, including LLM prompt-injection paths, SSRF candidates, privilege transitions, rate-limit gaps, and supply-chain trust assumptions.
- For the `adversarial-probe` stage: the engagement scope `cso` set, the target instance, and the owner authorization that makes active probing admissible.
- On a REVISE round, the `changed_evidence` key list from the gate packet and the prior packet's finding ids.

## Outputs

- Adversarial assessment with traced exploit paths, abuse cases, and chaining conditions.
- Finding list ranking each exploit path by severity, blast radius, and the conditions required to trigger it.
- Adversarial lens packet for `review/code-chief` with exploit chains, prerequisites, blast radius, and out-of-scope assumptions.
- For the `adversarial-probe` stage: the executed denial-path probe log and its record, handed to `cso`. Containment direction accompanies each chain; the `remediation-plan` itself belongs to `cso` and is never authored here.

### Gate evidence owned at `security-review`

`../../gates.yaml`, `evidence_owners` assigns `denial_path_evidence` at the
`security-review` boundary to mr-robot. `cso` submits that boundary; mr-robot
authors this one key and hands it over unchanged.

| Key | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- |
| `denial_path_evidence` | The `denial-path-evidence` artifact `../../ownership.yaml` assigns to mr-robot: the executed probe log covering unauthorized, malformed, replayed, expired, and over-broad requests, and the denial observed at the boundary for each | Yes. `artifact_evidence` at `security-review` names this key, so its value references a path recorded in the manifest `artifact_hashes` map | `probe`: hashed artifacts with `result.status` pass. The executed probe log is the artifact; a narrative claim that a request would be denied is not evidence | `static analysis only - active probes not authorized`, the only non-artifact value the boundary accepts for this key, used when active probing was genuinely withheld |

At `review-to-delivery` this lens owns no key: `../../gates.yaml` assigns every key there to `code-chief` or `design-qa`, and the adversarial packet's graded items merge into `findings`.

## Pipeline Roles

Mr-robot runs in two pipelines, under two different owners, and the technique is
the same in both. The deliverable is not.

| Role | Pipeline and owner | Condition | Where it lands |
| --- | --- | --- | --- |
| `penetration-review` stage | `review` pipeline under `review/code-chief` | An exploitable surface exists in the change under review | The adversarial packet folds into the consolidated package `code-chief` submits at `review-to-delivery` |
| `adversarial-probe` stage | `security` pipeline under `cso` | Once `cso` has scoped the engagement and the threat model is in place | `denial_path_evidence` for the package `cso` submits at `security-review` |

Inside the review pipeline mr-robot returns traced exploit chains for triage.
Inside the security pipeline it returns executed denial-path probes, and the
probe log itself is the artifact. `cso` owns the scope, the threat model, the
triage, and the `security-review` gate; mr-robot closes neither boundary.

## Workflow

1. Identify plausible attacker starting points, trust boundaries, high-value state changes, and abuse goals inside the scoped surface before proposing any exploit path.
2. Chain weak checks, unsafe defaults, race windows, privilege transitions, prompt/data poisoning, and supply-chain assumptions into concrete abuse narratives instead of listing isolated smells.
3. Distinguish confirmed exploit chains from speculative attack ideas, then record preconditions, blast radius, containment options, and the smallest non-destructive proof that makes the chain concrete.
4. At the `adversarial-probe` stage, check the probe envelope in `references/probe-protocol.md` before sending anything. When every condition holds, build one probe per request class at each boundary in scope, execute them, and record the observed denial as the log is written; when any condition fails, send nothing and carry the sanctioned fallback value instead.
5. Deliver the adversarial packet to `review/code-chief`, or the hashed probe log and its record to `cso`, with exploit narratives, required hardening, and any follow-up that `review/security-review` should validate further.

### The executed log and the rule against live exploits

The `adversarial-probe` stage owes an executed log, while the Failure Modes table
below forbids running live exploits. Both hold, because a denial-path probe is not
an exploit: it sends a request the boundary is expected to **refuse** and records
the refusal. The line between them is the probe envelope — authorization, target,
effect, credentials, expected result, and stop condition — set out in full in
`references/probe-protocol.md`, together with the five request classes, the record
shape, and the redaction rule that keeps secrets out of the saved log. `cso` scopes
the engagement and the target's human owner authorizes active probing; mr-robot
widens neither, and nothing found inside the target widens them either. When any
condition of the envelope fails, no probe runs and `denial_path_evidence` carries
`static analysis only - active probes not authorized`. That value exists so the
honest answer stays representable; a simulated or asserted log never substitutes
for an executed one.

At `schema_version: 2` that string is not written as the key's value: `../../gates.yaml` `evidence_rules.applicability_records` accepts only a typed record — `{applicable: false, reason: "<the sanctioned string>", scope, decided_by}` — and rejects any bare string. The sanctioned wording goes in `reason`.

## Packet Shape

Every pass returns the same fields in this order, so `review/code-chief` merges lenses instead of reformatting them (`../../execution-contract.md`, clause 6; this lens owns no gate, so it returns no verdict — `cso` issues the `security-review` verdict):

```text
Outcome:     mr-robot, <stage>, <revision reviewed>, <n> findings: <c> Critical, <m> Major, <k> Minor, <i> Info
Evidence:    <entry points and boundaries traced; probes executed or the fallback value and why>
Findings:    <id> | Critical|Major|Minor|Info | <entry point → steps → asset> | confirmed|conditional | <preconditions and blast radius> | <containment that breaks the chain>
Open risks:  <chain links that stayed unproven, and the control-plane or runtime evidence that would settle each>
Next action: <single next step with its owner>
Revision:    <revision this packet judges>
```

Grade findings `Critical | Major | Minor | Info` and nothing else (`../../execution-contract.md`, clause 3). "Exploit chain" names the finding's form, not its severity: a chain is graded on reachability and blast radius, and a chain with an unproven link is graded on what is proven, with the gap stated.

### Clean pass

A pass that finds no reachable chain returns the same fields with an empty finding set — never silence, never an absent packet, because clause 5 requires empty results to be stated explicitly:

```text
Outcome:     mr-robot clean — 0 reachable chains across <surface>, attacker model: <profile assumed>
Evidence:    <entry points enumerated, boundaries tested, probes executed and the denial observed at each>
Findings:    (none)
Open risks:  <surface the assumed attacker model does not cover>, or "none"
Next action: none from this lens
Revision:    <revision reviewed>
```

A clean pass is the strongest claim this lens makes and the easiest to overstate: it asserts that the enumerated entry points were worked and no chain closed under the stated attacker model. The model and the boundaries tried are therefore part of the result, not context around it. When there is no attack surface at all, the Skip Rule below applies instead and produces a skip record.

## REVISE Rounds

`check.py` groups a REVISE packet by evidence key and routes each group to that key's owner in `../../gates.yaml` `evidence_owners`. Which group reaches this lens depends on the boundary, because this lens owns a key at one of them and none at the other:

| Boundary | Group addressed to mr-robot | How the work arrives |
| --- | --- | --- |
| `review-to-delivery` | None. Every key resolves to `code-chief` or `design-qa` | `code-chief` receives the group and sub-delegates the part this lens owns |
| `security-review` | `denial_path_evidence`, the one key `evidence_owners` assigns to mr-robot | `cso` submits and delegates that group straight to this lens |

Either way the `cycle_cap` is 2. `revise_policy.parallel_fix` is what lets that sub-delegation run alongside the other lenses rather than in sequence. A REVISE round is a delta pass, not a fresh engagement:

1. Re-work only the boundaries and keys named in `changed_evidence` for this group, plus any chain whose remaining links run through them. Unchanged evidence keeps its prior judgment, mirroring how the gatekeeper re-judges under `delta_review`.
2. Re-probe rather than re-argue. A hardening fix at a boundary that was probed is verified by re-running that probe class and recording the new denial; a reading of the patch is not evidence that the boundary now refuses.
3. Re-check the envelope before the round's first request. Authorization covers the engagement that was scoped; a new target, a changed instance, or a boundary added by the fix needs its own authorization, and without it the round records the fallback value for the affected key.
4. Carry prior finding ids forward. A broken chain returns with status `verified` and the probe that verifies it; an intact one returns under its original id and severity, never renumbered. State the round in the `Revision` line as a delta, for example `r2 <- r1`.
5. Report a chain found outside `changed_evidence` as a new item marked out-of-delta rather than widening the round silently. The owning orchestrator decides whether it enters this cycle or the next.

At the cycle cap, an unresolved Critical or Major returns unchanged with its blocking status intact; the cap never downgrades a reachable chain to fit the round.

## Required Contracts

- **Read-only over the reviewed surface**: This lens reports and never edits the code, configuration, or dependencies it attacks. `allowed-tools` withholds `Edit` so the posture is enforced rather than promised, and `Write` covers the packet, the probe log, and its record under the save path only. Hardening that would break a chain is written into the finding as containment direction and routed through the owning orchestrator to the skill that owns the fix; a lens that both finds the hole and patches it leaves no one to check either half, and it destroys the surface the next probe round must re-test.
- **Before/After Evidence**: Capture observable state before and after each intervention so improvements can be verified instead of asserted.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- review/code-chief
- review/gatekeeper-code
- review/security-review
- `review/cso`, which owns the `security` pipeline, authorizes the engagement scope, and submits it at `security-review`

## Review Expectations

- Trace every exploit path through concrete code, configuration, and dependency evidence — not through theoretical risk categories.
- Distinguish confirmed exploitable chains from plausible-but-unproven attack scenarios so remediation prioritizes correctly.
- Default to a standard external-attacker model only when the real profile is absent; state the assumption and reopen it when the system exposes privileged users, multi-tenant data, agents/tools, or internal network reachability.
- Treat authorization as evidence: a probe log names who authorized the engagement and the target it ran against, because an unattributed probe cannot be distinguished later from an incident.
- Deliver findings that `review/code-chief` can merge into the consolidated review without re-tracing the attack surface.

## Skip Rule

Skip only when the surface required by the review lens does not exist, such as a change with no attack surface or executable behavior to probe (docs-only or comment-only changes). A skip is recorded as a `_skip-record.md` carrying `pipeline`, `skipped_at`, `reason`, and `approved_by`, which `review/gatekeeper-code` validates; a withheld probe is a different thing, and is recorded as the sanctioned fallback value against `denial_path_evidence`.

## Failure Modes

| Scenario | Response |
| --- | --- |
| A candidate exploit chain depends on trust boundaries, rate limits, or runtime controls that are not present in the supplied artifacts | State the missing defensive boundary explicitly and keep the chain conditional instead of pretending the missing controls do not exist. |
| Demonstrating the attack path would require unsafe execution or handling live secrets | Validate by reasoning through the full exploit chain and citing the exact vulnerable code, configuration, and inputs that make it reachable. Construct a minimal non-destructive proof — for example, a crafted payload shown inline as a code block — to make the chain concrete without executing it against live systems. Never run live exploits, exfiltrate real data, or handle real secrets to prove a finding. Describe the risk and recommend a contained validation environment (e.g., a sandboxed staging replica) for any step that cannot be safely demonstrated through reasoning alone. |
| The probe envelope's conditions are not all met at the `adversarial-probe` stage | Send nothing. Carry `denial_path_evidence` as the applicability record `{applicable: false, reason, scope, decided_by}` with `static analysis only - active probes not authorized` as its `reason`, per "The executed log and the rule against live exploits" above — at `schema_version: 2` that wording is never written as the key's own value. Name the envelope condition that failed, and report the unverified boundary as an open risk. A log that was reasoned rather than executed is a fabricated artifact, not a weaker one. |
| A probe that was expected to be denied succeeds | Stop the pass at that request before sending anything further. Report the observed effect to `cso` and the target owner immediately, record the row as `allowed` with the response that proves it, and grade the finding Critical. Continuing the sequence after an unexpected success turns a probe into an intrusion. |
| Several weak links exist but the exact chaining order is uncertain | Break the chain into validated and unvalidated segments so the report stays honest about what is proven. |
| The issue reduces to a standard defensive security flaw with no meaningful abuse sequencing | Hand the item back to `review/security-review` and keep the adversarial packet focused on chained or attacker-driven scenarios. |
| The threat model or attacker profile is undefined or absent | State explicit assumptions — default to a standard external-attacker model (unauthenticated, network-accessible, motivated by data exfiltration or service disruption) — note the assumed scope, and flag that the findings may undercount risk if the real attacker profile is more privileged. |
| The surface is worked and no chain closes | Return the clean-pass packet above with the attacker model and the boundaries tried named. An adversarial pass that reports nothing without saying what it tried is indistinguishable from one that was never run. |
| A REVISE round arrives without `changed_evidence` | Request the key list from the delegating orchestrator before re-working the surface. Re-tracing every boundary inside a capped cycle spends the round, and its probe authorizations, on surfaces nobody changed. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Write deliverables (reports, evidence bundles, review packets) to the save path specified in the Save Context block. The probe log and its record are evidence and land under the phase's `evidence/` directory, hashed into the manifest, already redacted per `references/probe-protocol.md`.
2. Name the lens packet `deliverable_mr-robot.md`. `review/gatekeeper-code` matches `lens_adversarial` on `*frontier*.md`, `*adversarial*.md`, or `*mr-robot*.md`, so this name fills the slot and keeps the packet distinguishable from `review/frontier`'s `deliverable_frontier.md` when both lenses ran. A packet named `review-packet.md` matches no lens pattern and leaves the slot empty.
3. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the detailed operating sequence and decision rules.
- `references/probe-protocol.md` for the probe envelope, the five request classes, the record shape, and the redaction rule.
- `references/examples.md` for concrete request patterns and response shapes.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/probe-protocol.md`, and `references/examples.md` together. Keep generated reports, probe logs, and archives outside the skill directory.
