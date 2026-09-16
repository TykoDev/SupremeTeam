# Gate Package Reference

Read this in pipeline mode, before assembling the `qa-review` submission or responding to a
`REVISE`. SKILL.md carries the six evidence keys and the self-check command; this file carries
the manifest shape, the path rules that decide whether evidence resolves at all, the revise
mechanics, and the record for a probe that could not run.

## Contents

1. Manifest shape
2. Evidence path rules
3. Self-check before submitting
4. Responding to a REVISE
5. Recording a probe that could not run
6. Standalone mode

## 1. Manifest Shape

The submission is one JSON file at the run's `qa/` phase destination, resolved with
`python skills/scripts/output_paths.py --run-id <run> --phase qa --kind manifest`:

```json
{
  "schema_version": 2,
  "boundary": "qa-review",
  "owner": "qa",
  "run_id": "2026-04-19-checkout",
  "submission_id": "2026-04-19-checkout_qa-review_attempt-1",
  "revisions": [4],
  "revision": 4,
  "evidence": {
    "scope": "Checkout: cart, address, payment, confirmation. Desktop Chrome 124 and iOS Safari 17 against staging v2.3.1. Refunds and partner checkout out of scope.",
    "test_matrix": {
      "artifacts": ["evidence/test-matrix.md"],
      "tool": "pytest", "command": "pytest -k checkout",
      "exit_code": 0, "observed_at": "2026-04-19T10:00:00Z",
      "result": {"status": "pass"}
    },
    "executed_probes": {
      "artifacts": ["evidence/executed-probes.log"],
      "tool": "pytest", "command": "pytest",
      "exit_code": 0, "observed_at": "2026-04-19T10:04:00Z",
      "result": {"status": "pass"}
    },
    "defects": {"items": [{"id": "QA-1", "severity": "Critical", "status": "verified"}]},
    "fixes_applied": "QA-1 fixed at commit abc1234; payment-error path reverified across 3 consecutive clean runs.",
    "residual_risk": "Apple Pay path untested - sandbox merchant account unavailable."
  },
  "artifact_hashes": {
    "evidence/test-matrix.md": "<sha256>",
    "evidence/executed-probes.log": "<sha256>"
  }
}
```

`schema_version: 2` requires `boundary`, `owner` (the spec submitter, `qa`), `submission_id`,
`run_id` inside a run, and a `revision` equal to the single `revisions` value. `defects` is a
typed `findings` record: every Critical must be verified or not-applicable with a reason, and
every Major must be verified, not-applicable with a reason, or deferred with a named owner and a
reopen trigger (`../../gates.yaml` `finding_policy`).

`fixes_applied` is the only waivable key at this boundary, and its one sanctioned fallback is
`report-only run - no fixes applied`. At schema 2 that waiver is a typed applicability record
rather than a bare string — `{"applicable": false, "reason": "report-only run - no fixes
applied", "scope": "<the surface>", "decided_by": "<named owner>"}` — and the checker rejects
the bare string with `bare fallback string not accepted at schema 2`. A run that applied fixes
states them instead; a run that applied none belongs to `qa-only`, which owns
that fallback.

## 2. Evidence Path Rules

`test_matrix` and `executed_probes` are artifact-backed **and** typed `probe`, so at schema 2
each is a record — `artifacts`, `tool`, `command`, `exit_code`, `observed_at`, and
`result.status` of `pass` — not a bare path string, which fails with `must be a typed probe
record at schema 2`. Every path inside `artifacts` must appear in `artifact_hashes` with a hash
matching the file on disk. A count, a pass rate, or a sentence about how thorough the sweep was
fails the mechanical check.

- Paths are manifest-relative, so `evidence/test-matrix.md` beside a manifest at
  `skillset-saves/runs/<run>/qa/manifest.json`.
- Inside the canonical save layout the authorised evidence root is the whole run directory, but
  only when the manifest `run_id` matches the directory and `_state.md`; sibling-phase evidence
  is admissible on that condition alone.
- Another run's directory, `..` traversal, absolute, drive-qualified, and UNC paths, and links
  leaving the root are rejected. Compose every destination with `output_paths.py` rather than by
  hand, which is what keeps that true.
- Every path-shaped string inside an artifact-backed value is checked, so a free-text note that
  happens to contain a path must name a real hashed artifact.

`test_matrix` is typed `probe`: the executed matrix log across the declared surface, with
`result.status` pass, and the hashed artifacts are the logs themselves. Only `pass` satisfies
the gate — `unavailable`, `error`, and `not-run` are data gaps.

## 3. Self-Check Before Submitting

```bash
python skills/harness/gatekeeper/check.py --boundary qa-review --package <manifest.json>
```

Run it without `--verdict-out` and fix every mechanical failure first; `../../gates.yaml`
`revise_policy.self_check` makes an unchecked submission a contract violation, because a
gatekeeper's judgment is meant to be spent on packages that already pass the machine.

## 4. Responding to a REVISE

A `REVISE` arrives as one packet carrying every mechanical failure and every judgment finding
from the whole pass, grouped by owner in `revise_packet.by_owner`. At `qa-review` every key is
owned by `qa`, so the packet groups by evidence key rather than across skills, and each key is
repaired in the same cycle instead of one per round trip.

Resubmit once, with the prior verdict record:

```bash
python skills/harness/gatekeeper/check.py --boundary qa-review --package <manifest.json> \
    --prior <verdict.json>
```

`--prior` reports `changed_evidence` and `unchanged_evidence` from per-key digests, so the
gatekeeper re-judges only what moved and carries its earlier judgment on what did not. Raise the
revision on every resubmission: a verdict is reusable only for the same boundary, submission,
revision, package fingerprint, and gate-spec digest.

`revise_policy` sets `cycle_cap: 2`. A second `REVISE` on the same package ends the cycle:
return `ESCALATE` with both packets, the `changed_evidence` and `unchanged_evidence` lists, and
the keys that did not converge. Opening a third cycle is not a retry — it is the failure this
cap exists to surface.

## 5. Recording a Probe That Could Not Run

An unavailable browser, host, or fixture produces a not-run record, never an inferred result:

```
probe: checkout-mobile-safari
command: (not run)
reason: open-browser reports no browser surface available on this host
status: not-run
covered-instead: none - the mobile viewport has no non-browser equivalent
```

Keep the record in `executed_probes` so the probe log and the matrix agree on coverage, mark the
matrix row untested rather than absent, and name the surface in `residual_risk`. `unavailable`
and `error` are data gaps; only `pass` satisfies the gate.

## 6. Standalone Mode

None of the above applies in standalone mode: no run, no manifest, no `artifact_hashes`, no
verdict. The evidence is still collected and reported inline with the same rigour — the matrix,
the probes, the before-and-after state per fix — and the result says explicitly that no package
was assembled and no `qa-review` verdict was sought, so nobody downstream reads an inline record
as an approved one.
