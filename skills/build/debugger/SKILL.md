---
name: debugger
description: >-
  Reproduces a build-phase failure to isolate the defect, repairs the broken
  path, and returns a bounded fix path with proof that the failure mode changed
  and that no temporary probe survived. Internal build specialist reached
  through `build/build-management` at the `debugging` stage, not directly, even
  when the request is only a pasted error and "why?"; the ask is to debug this
  failure, not to explain an unreproduced one. Defers feature code to
  `build/bob-the-builder`, test authoring to `build/test-builder`, and unknown
  cross-system mechanisms to `investigate`.
version: 1.0.0
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Debugger

## Purpose

Converts a reproduced failure into a cause someone can act on. The deliverable is the `debug-report` — reproduction steps, the isolated cause, and a bounded fix path — carrying before-and-after evidence that the failure mode actually changed, and a returned diff in which nothing survives that existed only to observe the failure.

## Use This Skill When

Use this skill for **a specific, reproducible failure** — isolate the cause, then prove the fix changed it:

- "debug this failure" / "isolate the defect" — narrow to the smallest reproduction
- "prove the fix changed the failure mode" — separate a real repair from a symptom that merely moved
- "repair the broken path" — apply a bounded fix and show the before/after behavior change
- "check that no temporary probe survived" — confirm no instrumentation was left behind in the tree

Route elsewhere when the task is building new feature code (`build/bob-the-builder`), adding the test surface (`build/test-builder`), or untangling an incident whose mechanism is still unknown (`investigate`), which owns "find the root cause" — this skill starts from a failure already reproduced.

## Entry Routing

Debugger is an internal build specialist, not an entry point.
`../../routing-doctrine.md` places every `build/` skill it does not name
separately in the internal-specialist row, reached only through the owning
sub-orchestrator. `../../pipelines.yaml` states the same thing from the other
side: `debugging` is a conditional stage of the `build` pipeline owned by
`debugger`, run when a reproduced build-phase failure exists, and
`build/build-management` names that stage in its own Delegation Surface and in
`../build-management/agent/agent-manifest.yaml`. Run the active-handoff check
before touching code, because the failing revision, the access boundary, and the
authorization covering any reproduction environment arrive with the handoff.

A handoff is present when the delegation prompt carries a `### Save Context`
block, an active run lock with `session_pin: true` exists under
`skillset-saves/`, or the invocation explicitly names `build/build-management`
as the delegating owner for the build boundary.

- **Handoff present** → proceed; this is a delegated debug assignment.
- **Reached cold** → add no instrumentation and apply no fix. Return to
  `build/build-management`, which owns debug assignment and resubmission, then
  accept the delegation back. A cold invocation names no approved revision and
  no owner able to authorize a reproduction environment.

## Inputs

- Failure description with symptoms, error messages, stack traces, or behavioral observations.
- Reproduction context including environment, configuration, recent changes, and affected code paths.
- Access constraints such as read-only environments, missing logs, or time-limited reproduction windows.
- The owner authorization covering any reproduction against production-shaped data, when one is needed.

## Outputs

Everything below returns to `build/build-management`, which owns debug
assignment and routes the result. `../../ownership.yaml` places the boundary at
"before returning a fix path to build-management" and lists `implementation`
under this skill's `does_not_write`: a candidate fix is tested here to prove the
mechanism, and landed by `build/bob-the-builder` as the product change.

- The `debug-report` artifact with the three evidence lines `../../ownership.yaml` requires: reproduction steps, the isolated cause, and a bounded fix path — written to the phase `reports/` directory and hashed.
- Before-and-after observations for each intervention, captured from the same command on the same revision, so the behavior change is verified rather than asserted.
- The instrumentation ledger, reconciled against the returned diff, showing every probe added and its removal.
- Escalation notes when the cause cannot be isolated inside the available evidence or access boundary, including the specific evidence that would close the gap.

`references/workflow.md` states the report shape, the path resolution, and how
the hash is registered.

## Workflow

1. Build a failure timeline from the symptom, recent code or environment changes, and the exact boundary where the system first stops behaving correctly.
2. Reproduce or narrow the defect with targeted checks so the debug path stays anchored in observed evidence rather than guesswork, opening the instrumentation ledger with the first probe.
3. Test candidate fixes against the actual failure mode and adjacent regression surface, keeping the remediation smaller than the original uncertainty.
4. Tear the instrumentation down before packaging: walk the ledger, remove every temporary probe, and re-read the returned diff to confirm only the fix remains.
5. Return the `debug-report` with the root cause, the verified repair boundary, the remaining risk, and the next build-phase action.

## Required Contracts

Full normative text for each contract is in `references/contracts.md`; the lines
below are the operative rule, not a summary that softens it.

- **Instrumentation teardown**: Record every probe the moment it is added — temporary log line, extra trace, widened timeout, debug-only branch, scratch script — in an instrumentation ledger naming the file and the question it answers. Before the fix is handed back, remove every ledger entry and prove the removal against the returned diff. A clean, rollback-safe commit is exactly what makes a stray probe invisible at review, which is why this is mandatory rather than tidy. An observation that genuinely belongs in the product is promoted to a deliberate logging change with its own justification and review, never left as residue.
- **Evidence redaction**: Redact every log, stack trace, request or response payload, environment dump, and configuration excerpt before it is attached. Replace each sensitive value with a typed placeholder that preserves the diagnostic shape — `<token:redacted>`, `<email:redacted>`, `<account-id:redacted>` — quote only the payload fields the cause depends on, and describe rather than paste a value redaction would destroy. A debug report travels further than the failure ever did. An exposed credential is a Critical finding reported by location and type and routed to `build/security-builder` for rotation.
- **Production-data boundary**: Reproducing against production data requires explicit owner authorization recorded in the handoff, and the authorized path is read-only and de-identified — a restored snapshot or a masked copy, never a write against the live store and never a live session used as a fixture. Attempt the de-identified route first and state what it could not surface. Absent authorization, record the reproduction gap and return it; an unauthorized production replay is a larger incident than the defect being chased.
- **Before/After Evidence**: Capture observable state before and after each intervention, from the same command on the same revision, so improvements are verified instead of asserted.
- **Atomic commit per fix**: Keep each fix isolated, explain what changed, and preserve easy rollback boundaries even when several issues are found.
- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages read risk identically. Critical blocks; Major resolves before the gate or defers with an owner and a reopen trigger.
- **Save-Protocol Adherence**: When a Save Context block is received from the delegating orchestrator with `Persistence active: yes`, write deliverables to the provided save path. Saving is mandatory when persistence is active.

## Collaboration Surface

- `build/build-management` — delegating owner; runs the `debugging` stage of the `build` pipeline, receives the `debug-report`, and routes the bounded fix path to the owning specialist.
- `build/bob-the-builder` — lands the proven fix as the product change, because `implementation` is not written here.
- `build/gatekeeper-build` — downstream gate; judges the assembled package and returns a REVISE packet through build-management, never directly.
- `build/security-builder` — receives any credential found exposed in the evidence, for rotation.
- `investigate` — takes over when the mechanism is unknown rather than merely unisolated; it owns its own pipeline gated at `investigation-review` and returns a bounded fix path to the build phase.

## Review Expectations

- Trace every fix back to a specific root cause with reproduction evidence, not just symptom disappearance.
- Distinguish confirmed root causes from provisional mitigations so downstream reviewers know what is proven.
- Deliver fix evidence the build pipeline can consume directly without re-investigating the failure.

## Skip Rule

Do not skip a mandatory build activity inside the canonical path; route scope changes through the build owner instead.

## Failure Modes

| Scenario | Response |
| --- | --- |
| Invoked cold with no `### Save Context` block, no active run lock, and no named delegating owner | Add no instrumentation, apply no fix, touch no environment. Return to `build/build-management` for the failing revision, the access boundary, and any reproduction authorization, then accept the delegation back. A cold caller can authorize neither the environment nor the edit. |
| `build/gatekeeper-build` returns a REVISE that reaches this stage through `build/build-management` | Take only the findings routed to this stage, fix them in one pass, re-run the before/after capture on the same revision, re-reconcile the instrumentation ledger, and hand the updated report back once. `../../gates.yaml` `revise_policy.cycle_cap` is 2; a third cycle escalates instead of resubmitting. |
| The debugger, profiler, tracer, or reproduction environment is unavailable, or the required tooling will not start | Record which tool was sought, the command attempted, and the observed error. Narrow the claim to what the remaining evidence supports, state which hypotheses stayed untested for want of the tool, and return the gap. An untested hypothesis is never reported as eliminated. |
| The bug cannot be reproduced because the failing environment differs from the local or test environment in one material way, such as config, data, or feature flags | Preserve the environment mismatch as part of the root-cause boundary and do not claim a fix until the relevant conditions are reproduced or bounded. |
| A candidate fix makes one failing test pass but never proves the underlying defect chain or checks nearby regression paths | Treat the repair as provisional and extend the validation surface before calling the defect closed. |
| Instrumentation or temporary logging changes alter timing or behavior enough to hide the original failure | Record the observer effect explicitly and use a less invasive debug path rather than mistaking silence for resolution. |
| Multiple recent changes could explain the symptom, but the debug path collapses onto the first plausible culprit without falsifying alternatives | Keep competing explanations alive until one survives the evidence or the remaining ambiguity is narrow and documented. |
| The failure cannot be reproduced at all — no local, staging, or CI environment surfaces the defect and no reliable trigger is known | Do not apply a speculative fix. State explicitly that reproduction failed, gather whatever indirect evidence exists (logs, metrics, user reports, environment differences), record the assumptions each candidate theory requires, and return an evidence-gap report the build owner can act on. |
| The symptom data appears fabricated, self-contradictory, or inconsistent across sources — error messages that do not match the stated stack, timestamps that predate the claimed change, or behavior that contradicts the attached logs | Do not proceed as if the data is reliable. Name the specific contradiction, halt speculative diagnosis, and request a clean reproduction case or an authoritative log source before forming a root-cause theory. Diagnosing from incoherent inputs produces a confident answer to a question nobody asked. |
| A temporary probe is still in the tree when the fix is ready to hand back | Do not package the diff. Remove the probe, re-read the returned diff against the instrumentation ledger, and hand back only once the two agree. A probe that ships inside an atomic fix commit is invisible at review and reaches production as unreviewed logging or a weakened guard. |
| The defect reproduces only against production data, and no owner authorization for that access is recorded | Stop at the boundary. Reproduce against a de-identified snapshot first and state what it could not surface; if only live-shaped data reproduces the defect, name the fields that force it and obtain explicit owner authorization for a read-only replay before touching the store. Record the reproduction gap and return it rather than reaching for live data on the strength of the debugging need. |

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

- `references/workflow.md` for the debugging sequence, the instrumentation ledger format, report assembly, and REVISE handling.
- `references/contracts.md` for the full normative text of instrumentation teardown, evidence redaction, and the production-data boundary.
- `references/examples.md` for worked debug passes, including an unreproducible failure and incoherent symptom data.

## Packaging Notes

Package `SKILL.md`, `references/workflow.md`, `references/contracts.md`, and `references/examples.md` together. Keep generated reports and archives outside the skill directory.
