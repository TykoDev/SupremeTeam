---
name: health-check
description: >-
  Proves the built system actually comes up — startup, readiness window, and
  dependency reachability — and returns the hashed startup smoke log the
  `runtime` evidence key requires, probing only the target the handoff
  authorizes. Internal build specialist reached through
  `build/build-management`, not directly, even when the request is only "does it
  actually run?". Defers test authoring to `build/test-builder` and package
  completeness to `build/cross-check-build-confirm`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Health Check

## Purpose

The only proof that the built system starts. `runtime` is one of the five keys at `build-to-review` with no sanctioned fallback — only `security_evidence` is waivable there — and it is the one most often assumed away, because a green test suite looks like it should stand in for it and does not. So this pass either produces an executed smoke log against an authorized target, or reports the boundary as unverified and blocked. Nothing here is inferred from configuration.

## Use This Skill When

Use this skill to **confirm the system actually comes up** — runtime and environment readiness, not static correctness:

- "run the health check" / "check startup health" — verify the app starts and reports healthy
- "verify runtime readiness" — exercise liveness and readiness signals and key dependencies
- "validate environment health" — confirm required environment and external dependencies are present

Route elsewhere when the work is authoring tests (`build/test-builder`) or confirming the build package is complete (`build/cross-check-build-confirm`).

## Entry Routing

Health-check is an internal build specialist, not an entry point.
`../../routing-doctrine.md` places every `build/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. Run the active-handoff check before sending a single request,
because the probe target, the revision under test, and the authorization that
covers authenticated traffic against it arrive only with the handoff.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `build/build-management`
as the delegating owner for the build boundary.

- **Handoff present** → proceed; this is a delegated health pass.
- **Reached cold** → probe nothing. Return to `build/build-management`, which
  owns environment assignment and remediation routing, then accept the
  delegation back. A cold invocation names no authorized target, and an
  authenticated probe sent at a guessed environment is real traffic against a
  real system under a real identity.

## Inputs

- Runtime target, startup configuration, and the environmental dependencies the service requires.
- Health-probe endpoints, readiness checks, and the expected startup sequence from the deployment spec, including any declared readiness window.
- Known environmental constraints such as network isolation, missing credentials, or cold-start limitations.
- The owner authorization covering authenticated traffic against the named target, when that target is shared or production.

## Outputs

Everything below returns to `build/build-management`, the only skill
`../../gates.yaml` `boundaries.build-to-review` permits to submit that boundary.
Health-check submits nothing itself; it owns the `runtime` key inside that
submission (`../../gates.yaml`, `evidence_owners.build-to-review`).

- The executed startup or entry-point smoke log, written as a file under the phase `evidence/` directory and hashed. `evidence_type_rules.probe` names exactly that log as the `runtime` artifact at this boundary, and states that a bare count or claim is not evidence.
- The typed `probe` record that carries it: hashed `artifacts`, `result.status: pass`, the `tool` and `command` that produced it, `observed_at`, and the environment and revision the probe ran against.
- The environment dependency status — the second evidence line `../../ownership.yaml` attaches to the `runtime` artifact — naming every dependency as reachable, degraded, or unexercised, with the observed signal behind each.
- Escalation notes listing unresolvable environmental gaps, every recorded side effect the smoke flow produced, and any readiness claim narrowed to the environment actually tested.

`references/workflow.md` states the record shape, the path resolution, and how
the hash reaches the manifest.

## Workflow

1. Read the handoff first: the named target, its revision, the authorization covering authenticated traffic against it, and the probe budget. Without a named and authorized target the pass stops here and returns the gap.
2. Define the runtime health contract for that surface — boot behavior, the readiness window and its predicate, dependency readiness, and the critical user path. `references/workflow.md` fixes what a readiness window means so "ready" is not decided after the fact.
3. Discover the start command without running it (`check_runtime.py --detect-start-command`), then execute the probe matrix in `references/workflow.md` — startup, readiness poll, dependency reachability, smoke flow — capturing each to its own log under the phase `evidence/` directory.
4. Separate transient noise from structural health failures using repeatability, not intuition, so the report does not confuse a warm-up blip with a reliable runtime posture.
5. Return the hashed smoke log, its typed probe record, the dependency status, every side effect the pass created, and the next remediation or release action.

## Required Contracts

Full normative text for each contract is in `references/contracts.md`; the lines
below are the operative rule, not a summary that softens it.

- **Probe target authorization**: Probe only the target the handoff names — environment, revision, base address — and no other. Non-production is the default. A production or otherwise shared target requires explicit owner authorization recorded in the handoff before the first request, plus a stated request budget, rate ceiling, and stop condition; an authenticated probe is real work against real data under a real identity. When no target is named, or the named one is not covered by the authorization, run nothing and return the gap.
- **Secrets handling**: Credentials are referenced by name only, read from the environment or the configured secret source at the moment of use, and never inlined into a command, a config edit, or a report — including the readiness gap list, which names the missing reference and never its content. Scrub every log, transcript, and environment dump before it joins the evidence bundle, not after. An exposed credential is a Critical finding reported by location and type and routed to `build/security-builder` for rotation.
- **Runtime has no fallback**: `../../gates.yaml` `fallback_values` carries no entry for `runtime`, so an unverifiable runtime hard-blocks `build-to-review`. No applicability record, no sanctioned string, and no passing test suite substitutes for the smoke log. Report the block; do not soften it into a caveat.
- **Observed signal only**: Every health claim cites a probe response, a log entry, or a dependency check. Configuration that says a dependency is configured is not evidence that it is reachable.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically. Critical blocks; Major resolves before the gate or defers with an owner and a reopen trigger.
- **Proactive triggers**: Offer the next sensible action when the surrounding context clearly implies it and the skill can advance safely without a prompt loop.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management` — delegating owner; names and authorizes the target, receives the `runtime` evidence, owns remediation routing, and is the sole `build-to-review` submitter.
- `build/gatekeeper-build` — downstream gate; judges the assembled package and returns a REVISE packet through build-management, never directly.
- `build/security-builder` — receives any credential found exposed in a log or a running configuration, for rotation.

## Review Expectations

- Base every health claim on an observable signal — probe response, log entry, or dependency check — not on configuration intent.
- Surface environmental gaps and missing dependencies before deployment consumes the health report.
- Deliver startup-readiness evidence the release pipeline can verify without re-running the health sweep.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Invoked cold with no `### Save Context` block, no active run lock, and no named delegating owner | Send no request of any kind. Return to `build/build-management` for the target, the revision, and the authorization, then accept the delegation back. A guessed environment is somebody's real system, and a probe against it cannot be recalled. |
| `build/gatekeeper-build` returns a REVISE naming the `runtime` key | Read the packet's `by_owner` group for this key only, fix every finding in it in one pass, re-run the affected probes against the same authorized target, re-hash the log, and hand it back for a single resubmission. `../../gates.yaml` `revise_policy.cycle_cap` is 2; a third cycle escalates to the build owner instead of resubmitting. |
| The handoff names no probe target, or the only reachable environment is production or shared and no authorization for it is recorded | Send no authenticated request. Because `runtime` has no sanctioned fallback, this is a hard block on `build-to-review`, not a caveat: report the readiness contract as unverified, state that the boundary cannot be submitted until a target is authorized, and name the owner who can authorize it. Readiness that was never proven is a fixable reporting outcome; traffic sent at an unauthorized environment is not. |
| The target is authorized but unreachable, or the required credential reference resolves empty, so no probe can execute | Record the attempted command, the observed error, and the reference that came back empty, named by reference only. Produce no `runtime` evidence — an unavailable check is a data gap, never a pass — and return the environmental gap to `build/build-management`. The boundary stays blocked until a clean pass completes. |
| Startup and liveness probes pass, but the critical dependency path fails once the application handles real traffic or authenticated flows | Treat the service as not ready and require proof for the real runtime boundary rather than trusting shallow green checks. |
| The health-check package mixes evidence from a different environment, revision, or data state than the one being approved | Narrow the claim to the environment actually tested and block release language that outruns the evidence. |
| One transient spike or warm-up issue is mistaken for a permanent failure, or a recurring degradation is waved away as normal warm-up noise | Preserve the timing evidence and classify the issue by repeatability across the poll series instead of intuition. |
| The runtime looks healthy only because one failing dependency, queue, or feature-flag path was never exercised during the health pass | Mark the missing path as unverified and do not let the report imply full readiness. |
| A startup log, probe transcript, or environment dump bound for the evidence bundle contains a connection string, bearer token, or session identifier | Scrub before attaching, never after. Replace each value with a typed placeholder that preserves the diagnostic shape, attach only the scrubbed copy, and report the exposure itself as a Critical finding by location and type. An evidence bundle outlives the environment it came from and travels further, so one unscrubbed log turns a runtime check into a credential disclosure. |

## Save Protocol

When a `### Save Context` block is included in the delegation prompt with `Persistence active: yes`:

1. Resolve every destination with `python skills/scripts/output_paths.py`, using the run id and
   phase from the Save Context block. Never compose a path by hand: the resolver refuses an
   unknown kind, a name that is absolute or traverses, and any path that escapes the
   project root, which is the containment check.
2. Write deliverables (reports, evidence bundles, review packets) to the destination it returns.
3. Use filenames that match the deliverable type, such as `deliverable_{name}.md`, `report_{name}.md`, or `review-packet.md`.
4. Never write `_phase-state.md`. No class in the save-ownership policy declares that path, so it is not an orchestrator-owned file either — phase state is published only through `save_run.py checkpoint`, which keeps revision lineage and the audit trail coherent.

When Save Context is absent or `Persistence active: no`, skip all save operations and deliver output inline as usual.

## References

- `references/workflow.md` for the verification sequence, the readiness-window definition, the probe matrix with command shapes and capture destinations, evidence assembly, and REVISE handling.
- `references/contracts.md` for the full normative text of probe-target authorization, secrets handling, and the no-fallback rule.
- `references/examples.md` for worked passes ending in the hashed smoke log and its typed probe record.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
