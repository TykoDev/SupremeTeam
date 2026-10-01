# Evidence Standards

## Contents

- Responsibility
- Current-run rule
- Specificity and trust
- Input boundaries
- Retention
- Binding evidence to source
- Calibration
- Claim record
- Enforcement
- Failure paths

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
Use weaker labels instead of strengthening the prose. Both vocabularies are
judgement: no comparator reads either label, so a mislabeled item passes the
gate as long as its mechanical facts hold.

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

The destination is the one class
[`../save-ownership.yaml`](../save-ownership.yaml) declares as `phase-evidence`,
resolved with `python skills/scripts/output_paths.py --kind evidence`. Composing
the path by hand is how evidence lands outside the root the gate can read.

## Binding evidence to source

Evidence that depends on project source binds to it through typed record
`inputs` (`path` plus `sha256`), as [gates.yaml](../gates.yaml) defines. A
changed source with an unchanged evidence file fails the gate as input hash
drift. This is why application source is never copied wholesale into a run:
the binding, not the copy, is what proves currency.

What the gate enforces and what it takes on trust are different, and the split
matters most for `tests` and `runtime`:

- **Enforced for every typed record that names `inputs`.**
  [`../harness/gatekeeper/check.py`](../harness/gatekeeper/check.py) re-hashes
  each declared input at submission and fails the package with
  `<key> input hash drift (stale evidence): <path>` when the digest no longer
  matches, `<key> input missing` for an absent file, `<key> input entry requires
  path and sha256` for a malformed entry, and its own failure when
  `input_revision` differs from the package revision.
- **Required only for `scan` and `render` records.** Those two fail with
  `<key> record must bind inputs (path + sha256) to the inspected source` when
  they name none. A `probe` record (`tests`, `runtime`,
  `executed_probes`, `reproduction`, `evidence_chain`, `test_matrix`,
  `denial_path_evidence`, `mock_parity`, `parity_evidence`) may omit `inputs`,
  and then passes with nothing tying it to any source. The result lists each
  such record in `warnings` as `<key> binds no inputs: attested, not tied to the
  source it describes`, and whether a log describes the revision being shipped is
  the gatekeeper's judgement. A submitter who wants the drift check on a test
  log binds its inputs.
- **Attested, never verified.** check.py does not open an artifact, re-run a
  command, or confirm which tool produced a record. `result.status`, `tool`,
  `command`, and `observed_at` are the submitter's own statement, and a hash
  proves a file is unchanged since it was hashed, not that it says what the
  record claims. The one contradiction the gate can see, a `pass` beside a
  non-zero `exit_code`, fails as `<key> result pass contradicts exit_code <n>`.

The behavior is pinned by `../harness/gatekeeper/test_gate_run_layout.py` and
`../harness/gatekeeper/test_gate_engine.py`.

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

## Enforcement

The mechanical half of this contract runs at the gate. Everything a gatekeeper
must judge is listed below as judgement, and an approved package proves only the
mechanical column.

| Standard | Backing | What fails |
|----------|---------|------------|
| Evidence that names source `inputs` stays bound to them by path and sha256 | Machine-checked by `check.py` for any typed record that carries `inputs`; the inputs are required for `scan` and `render` records only | `input hash drift (stale evidence)`, `input missing`, `input entry requires path and sha256`, and for scan and render alone `record must bind inputs (path + sha256) to the inspected source`. A `probe` record with no `inputs` passes and is listed in `warnings`. |
| A typed record is what it claims to be | Judgement, apart from one contradiction | `check.py` checks shape, artifact digests, input digests, and that a pass does not sit beside a non-zero exit code (`result pass contradicts exit_code`, `exit_code must be an integer`). It never opens an artifact, so that a log is the runner's own output, that a scan ran, or that a capture shows the surface is for the gatekeeper. |
| A key declared artifact-backed points at a hashed artifact | Machine-checked by `check.py` | `evidence not artifact-backed`, `evidence references unhashed path`, `evidence references defective artifact` |
| A named artifact exists and matches its declared digest | Machine-checked by `check.py` | `missing artifact`, `invalid artifact digest`, `artifact hash mismatch` |
| Evidence stays inside the run's evidence root | Machine-checked by `check.py` | `escapes evidence root`, `references another run`, `input path must be project-relative` |
| An unavailable check is not silently converted to approval | Machine-checked for typed records by `check.py` | `result status must be one of [...]`, `result not passing: <status>` |
| A waiver is an explicit applicability record on a waivable key, worded exactly as the gate spec sanctions for that key | Machine-checked by `check.py` | `evidence not waivable`, `applicability record incomplete`, `applicability reason not sanctioned`, `bare fallback string not accepted at schema 2`. Whether the waived condition is actually true (no trust boundary moved, no visible surface changed) is judgement. |
| A manifest inside a run declares schema 2, so its typed records and finding policy are checked | Machine-checked by `check.py` | `manifest inside a run must declare schema_version 2`; the package is checked as schema 2 anyway. A flat package at schema 1 passes, and `warnings` says no typed check ran. |
| One revision per submission, and no stale verdict lineage | Machine-checked by `check.py` | `mixed revisions`, `revisions must contain exactly one value`, `stale verdict revision`, `idempotency drift on unchanged revision` |
| Hollow-completion language is not evidence | Machine-checked by `check.py` against the one blocked-phrase list in `../harness/gatekeeper/_gatecheck.py`, which the package validator reads too: literal phrases fold case, `re:` markers such as `TODO` are case-sensitive words, and quoted or code-formatted text is exempt | `blocked phrase: <file>`. A phrase file or pattern the package validator cannot load or compile is an engine error (exit 2), never a clean scan. |
| An evidence document's internal references resolve | Machine-checked by `check.py` | `broken link in <file>`, `link escapes <root>` |
| A scan record carries its command, exit code, and inputs | Machine-checked by `check.py`, produced by [`../scripts/scan_record.py`](../scripts/scan_record.py), which distinguishes `pass`, `fail`, `error`, `unavailable`, and `not-run` | `scan record requires <field>`, `scan record requires exit_code`. `pass` records that the scanner exited 0, which is not proof that it found nothing: a scanner that exits 0 with findings needs its own exit-code flag or `scan_record.py --fail-on-output`. |
| An inferred render record states its limitation | Machine-checked by `check.py` | `inferred render requires a limitation statement` |
| The current-run rule | Partly machine-checked by `check.py` | `run_id does not match run directory`, `manifest inside a run must declare run_id`. That an item was genuinely produced during this run is judgement. |
| Specificity and trust labels | Judgement | Nothing. No comparator reads `exact`, `bounded`, `contextual`, `observed`, `corroborated`, `reported`, or `inferred`. |
| Input boundaries stated before collection | Judgement | Nothing. An unstated boundary passes every check. |
| Retention, preservation of superseded evidence, secret redaction | Judgement | Nothing. The write destination is governed by `save-ownership.yaml`, and no comparator verifies that a summary did not replace raw output. |
| Calibration, and recalibration after an upstream change | Judgement | Nothing. An overstated claim fails only a reviewer. |
| The claim, gap, and proof record contents | Judgement | Nothing. `check.py` enforces the shape of typed gate records, never the contents of a claim record in a report. |
| That a delivery report carries the claim, gap, and proof record at all | Judgement | Nothing. [delivery-template](delivery-template.md) does require it — `Claims, gaps, and proof` is `required` at `RUN_COMPLETE`, with all three collections exposed even when one is empty, and an omitted heading is an incomplete record rather than an inapplicable one — but that template is opened by no comparator, so the requirement is real and the enforcement is a reviewer reading the report. |

## Failure paths

- A check cannot run. Record the failed probe, its command, and the reason, with
  `result: unavailable`. An unavailable check is a gap, never a pass, and never
  supports an `observed` trust level.
- An input file named by a typed record is unreadable. The record cannot bind;
  `check.py` fails the key. Record the read error as a gap and resubmit with
  either a readable input or an explicit applicability record on a waivable key.
- Source changed after evidence was captured. The binding fails as input hash
  drift. Recapture the evidence against the new digest; editing the recorded
  digest to match is falsification, not a fix.
- Two evidence items disagree. Preserve both, name the disputed claim, lower the
  affected claim to the weaker label, and escalate under the conflicting-evidence
  rule in [workflow-protocol](workflow-protocol.md). Deleting the inconvenient
  item destroys the only record of the conflict.
- Evidence must be removed under an approved policy. Keep a hashed pointer, the
  removal reason, and the timestamp; the claims it supported drop to `reported`
  at best and are re-proved before they can affect a gate again.
- A secret cannot be redacted without destroying the proof. Retain the redacted
  copy, record the redaction as a limitation, and keep the claim at the trust
  level the redacted copy supports.
- This contract and a boundary in `gates.yaml` appear to conflict about a key.
  `gates.yaml` is authoritative for what a boundary requires; this contract is
  authoritative for how an item is labeled and preserved.
