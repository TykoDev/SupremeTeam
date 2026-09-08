# Evidence Standards

## Responsibility

This contract defines what can support a claim in the current run. It covers
scope, trust, preservation, and calibrated reporting; it does not assign phase
ownership or define workflow transitions.

## Current-run rule

Evidence is current-run evidence only when it was produced, inspected, or
verified during the active run and is tied to `run_id`, `revision`, `phase`, and
`owner`. Historical material may provide context, but it cannot prove a current
claim until it is rechecked or explicitly marked as reported context.

Every evidence item records:

```yaml
evidence_id: [stable id]
run_id: [run id]
revision: [integer]
phase: [phase]
owner: [owner]
source_path: [workspace-relative path]
source_kind: [command | test | file | review | external-report]
command_or_action: [how it was obtained]
observed_at: [ISO-8601 timestamp]
scope: [paths, inputs, environment, and time window]
result: [relevant output or result]
hash: [sha256 digest when the source is a file]
```

## Specificity and trust

Specificity describes how precisely an item is bounded. Trust describes how it
was established. Report the two levels separately.

| Specificity | Meaning |
|-------------|---------|
| exact | Names the artifact, revision, command, environment, and result. |
| bounded | Names the source and scope, but leaves a material detail indirect. |
| contextual | Provides background only and cannot prove the claim. |

| Trust | Meaning |
|-------|---------|
| observed | Direct result from the current run. |
| corroborated | Independent current-run evidence agrees. |
| reported | A source reports the result but this run did not reproduce it. |
| inferred | A reasoned conclusion that still depends on an assumption. |

Claims that affect a gate should be `exact` plus `observed` or `corroborated`.
Use weaker labels instead of strengthening the prose.

## Input boundaries

Before collecting evidence, state the allowed root paths, input set, host and
runtime versions, time window, tools, permissions, and exclusions. A result may
support claims only inside those boundaries. Missing, unreadable, stale,
conflicting, or unavailable inputs are evidence gaps, not permission to infer
the missing result.

## Retention

Keep raw command or tool output with its metadata at the phase evidence path
(`skillset-saves/runs/{run-id}/{phase}/evidence/`). Record the path and hash in
the report, preserve superseded evidence, and do not replace raw output with a
summary. Redact secrets from retained copies and record that redaction as a
limitation. Retain evidence for the life of the run and its delivery record; if
it is removed under an approved policy, retain a hashed pointer, removal reason,
and timestamp.

## Binding evidence to source

Evidence that depends on project source binds to it through typed record
`inputs` (`path` plus `sha256`), as [gates.yaml](../gates.yaml) defines. A
changed source with an unchanged evidence file fails the gate as input hash
drift. This is why application source is never copied wholesale into a run:
the binding, not the copy, is what proves currency.

## Calibration

Match claim strength to the weakest material dependency. Quantitative claims
include units, sample size, measurement window, and environment. State whether a
result is observed, reproduced, reported, or inferred. Recalibrate after an
upstream revision, failed check, or contradictory source; invalidate only the
claims that depend on the changed evidence.

## Claim record

Every delivery or gate report exposes these fields:

```yaml
claims:
  - id: [claim id]
    statement: [precise statement]
    scope: [bounded scope]
    specificity: [exact | bounded | contextual]
    trust: [observed | corroborated | reported | inferred]
    evidence_paths: [workspace-relative paths]
    proof: [test, command, or observation that supports it]
gaps:
  - id: [gap id]
    missing_fact: [what is not known]
    boundary: [why the current evidence cannot establish it]
    impact: [claim or decision affected]
    next_check: [safe way to close it]
proof:
  - claim_id: [claim id]
    method: [reproduction or validation method]
    result: [pass, fail, or unavailable]
    evidence_paths: [paths]
```

An unfilled `proof` or an unresolved load-bearing `gap` makes the claim
unproven. Say `unknown` when the boundary prevents a stronger statement.
