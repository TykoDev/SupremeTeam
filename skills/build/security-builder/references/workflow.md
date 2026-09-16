# Workflow Reference

The stage-selection table that decides which of the three jobs is running, the
hardening sequence, the gate evidence each stage owes, how a scan becomes a
typed record, and how a REVISE is handled. `SKILL.md` states the order; this
file states the procedure.

## Contents

1. Stage selection
2. Hardening sequence
3. Gate evidence owned
4. Scan record assembly
5. REVISE handling
6. Decision rules
7. Acceptance checklist
8. Collaboration notes

## Stage Selection

Security-builder is a specialist in three places, and the delegation it receives
decides which one is running. `../../../routing-doctrine.md` sets the rule: inside
a delivery run security-builder owns the recurring checkpoints rather than
forking a parallel lifecycle, and a dedicated security engagement runs the
`security` pipeline under `review/cso`.

| Role | Pipeline and delegating owner | Handoff signal that selects it | Deliverable |
| --- | --- | --- | --- |
| `security-seed` stage, when the design moves a trust boundary | `design` pipeline under `design/commander` | A `### Save Context` block carrying `Phase: design` and `Return boundary: design-to-build` | The `security_seed` evidence for `design-to-build` |
| `security-checkpoint` stage, when the build touches a trust boundary | `build` pipeline under `build/build-management` | A `### Save Context` block carrying `Phase: build` and `Return boundary: build-to-review` | The `security_evidence` evidence for `build-to-review` |
| `remediation` stage, when fixes are authorized | `security` pipeline under `review/cso` | A `### Save Context` block carrying `Return boundary: security-review` | Applied fixes and the remediation record `review/cso` folds into the `security-review` package |

The `Phase` and `Return boundary` fields are read before any work starts,
because the two checkpoints are not the same job. The design checkpoint is
forward-looking: it names the trust boundaries the design introduces or moves
and the controls the build owes for each one, before any code exists. The build
checkpoint is evidential: it grades what the implementation actually does
against those controls. Confusing them yields a seed with no controls to check
or a build checkpoint with no baseline to check against, so an ambiguous or
missing handoff is returned to the delegating owner rather than guessed.

In the `security` pipeline security-builder holds no gate. `review/cso` owns the
`security-review` boundary, sets the scope and the threat model, triages, and
submits the package. Security-builder applies only the fixes `review/cso`
authorized, keeps them inside the scoped surface, and escalates any fix that
would change auth, tenancy, or data-handling behavior beyond that scope.

## Hardening Sequence

1. Read the handoff and select the stage. Nothing below is safe to run before that.
2. At the design stage, map architecture, interface contracts, and data classifications to the trust boundaries the design introduces or moves, and state the control the build owes at each one.
3. At the build stage, confirm the changed surface, data sensitivity, and trust boundaries touched by the submitted revision, against the seed as baseline.
4. Inspect first-party code, dependencies, and non-first-party surfaces for unsafe patterns, missing controls, and unresolved exposure paths.
5. Verify that each claimed remediation is tied to a focused rerun, a scan record, or a direct proof on the affected boundary.
6. At the remediation stage, apply only the authorized fix set, prove each fix, and return the remediation record to `review/cso`.
7. Package the stage's deliverable so its consuming owner can see what was fixed, what remains risky, and what requires broader approval.

## Gate Evidence Owned

`../../../gates.yaml` `evidence_owners` assigns security-builder one key at each of
two boundaries. Both are authored here and handed to the submitting phase lead
unchanged; neither boundary is submitted by security-builder itself. The
`security` pipeline's remediation record is not a gate key at all —
`review/cso` folds it into the package it submits at `security-review`.

| Key | Boundary | What it must contain | Artifact-backed | Typed record | Sanctioned fallback |
| --- | --- | --- | --- | --- | --- |
| `security_seed` | `design-to-build`, submitted by `design/commander` | The `security-seed` artifact `../../../ownership.yaml` assigns to security-builder: the trust boundaries the design introduces or moves, and the controls the build must implement for each one | No. `artifact_evidence` at `design-to-build` lists `decisions`, `architecture`, `plan`, and `taste_snapshot` only | None. `evidence_types` assigns this key no shape, so a plain statement satisfies the mechanical check | None. `../../../gates.yaml` `fallback_values` carries no entry for this key, so it is not waivable at that boundary and no applicability record substitutes for it |
| `security_evidence` | `build-to-review`, submitted by `build/build-management` | The `security-evidence` artifact `../../../ownership.yaml` assigns to security-builder: the graded record of what was found, and the controls actually implemented against the seeded boundaries | No. `artifact_evidence` at `build-to-review` lists `tests` and `runtime` only | `findings`: `{items: [{id, severity, status, owner?, reopen_trigger?, reason?}]}`. Critical is verified or not-applicable with a reason; Major is verified, not-applicable with a reason, or deferred with an owner and a reopen trigger | `no trust-boundary change - security-builder not engaged`, used only when no trust boundary moved, never to cover a checkpoint that was skipped while one did. Carried at manifest schema 2 as an applicability record with reason, scope, and decider — a bare string is refused |

## Scan Record Assembly

A scanner's output becomes evidence only as a typed record. Produce it with the
repository's own writer rather than by hand:

```bash
python skills/scripts/scan_record.py \
  --out <phase>/evidence/security-scan.json \
  --input <lockfile or manifest> \
  --tool <scanner name> \
  --version-command "<scanner> --version" \
  -- <scanner command>
```

Resolve `<phase>/evidence/` with
`python skills/scripts/output_paths.py --run-id <run-id> --phase <phase> --kind evidence --name security-scan.json`;
the raw scanner output is stored beside the record. `--input` is repeatable and
binds the record by sha256 to the manifest or lockfile inspected, which is what
makes stale scan evidence fail rather than pass quietly. `--fail-exit-codes`
declares which non-zero exits mean "findings reported" rather than "scanner
broke".

When the scanner cannot run at all, record the request with `--no-run` and a
`--limitation`. `../../../gates.yaml` `evidence_type_rules.scan` accepts only
`pass` as satisfying; `unavailable` and `error` are data gaps, never clean
scans, and a typed gap is auditable in a way a sentence in a report is not.

## REVISE Handling

A `REVISE` arrives through the delegating owner — `design/commander`,
`build/build-management`, or `review/cso` — as one packet, already grouped by
owner in `revise_packet.by_owner` (`../../../gates.yaml`
`revise_policy.one_packet`). Take only the group for the key owned here;
sibling groups belong to other specialists and are fixed in parallel.

Repair every finding in the group in one pass, re-run the focused check that
proves each repair, refresh any scan record so its `inputs` match current
digests, and hand the updated record back once. `revise_policy.cycle_cap` is 2;
a third cycle escalates to the delegating owner rather than resubmitting.

## Decision Rules

- Prefer the narrowest defensible security claim over a blanket "clean" statement.
- Treat vendored and generated content as higher-trust-cost surfaces that require explicit handling.
- Keep exploit paths visible until proof shows the path is actually closed.
- Escalate when the safe fix requires a design or scope decision beyond the assignment.
- Never grade at the design stage, and never seed at the build stage; the handoff decides and an ambiguous handoff is returned.
- Apply only the authorized fix set inside a `security` engagement; an out-of-scope fix is returned as a finding.
- Record an unavailable scanner as a typed gap, never as an absence of findings.

## Acceptance Checklist

- The stage was selected from `Phase` and `Return boundary`, not inferred from the request wording.
- Touched trust boundaries and sensitive surfaces are explicit.
- At the build stage, every control traces back to a seeded boundary.
- Dependency and non-first-party risks are addressed or bounded.
- Remediation proof matches the affected finding and exercises the exploit path, not the code near it.
- Every scan is a typed record with its inputs bound by sha256; every unrun scan is typed as a gap.
- No secret value appears anywhere in the output, and every exposure is a Critical finding by location and type.
- Residual risk is recorded honestly.

## Collaboration Notes

This skill's collaboration surface is stated in `../SKILL.md` § Collaboration Surface.
