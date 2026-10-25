# Review discipline

Apply this contract to initial reviews, every gatekeeper, REVISE follow-ups,
verification, tests, and audits. `gates.yaml` defines the evidence required at
each boundary; `pipelines.yaml` defines where specialist work runs.

## Contents

- Intake authority
- One gate per specialist review
- Complete REVISE feedback
- Follow-up verification
- Third consecutive REVISE
- Examples
- Enforcement and limits

## Intake authority

Read the current run's hashed `intake/report_grilling.md` before judging the
package. Carry its path under `intake.artifact` in every judgment, including
downstream gates whose required evidence has no `decisions` key. If Intake is
unavailable, only ESCALATE to user may carry `intake: {unavailable: <reason>}`;
never use that record for approval or REVISE. Preserve the
resolved decisions, deferred decisions, rejected options, and non-goals. Plans,
review recommendations, inferred preferences, and a gatekeeper's preferred
design cannot silently change them. Explicit user changes return through
Admiral to update Intake, its hash, and the affected acceptance criteria.

For each blocking finding, trace the expected behavior to a D-id, an approved
AC-id consistent with Intake, or a mandatory catalog rule. Explain why it
applies to this scoped change. A contract rule cannot be used to add an optional
feature the user excluded. If an acceptance row conflicts with Intake, route
the conflict to Admiral for a user decision; do not revise implementation to
match the conflicting row. Missing decisions, ambiguous scope, stale Intake, or
requested additions go to the user through Admiral as ESCALATE. Preserve
mandatory safety rules and describe any conflict to the user.

## One gate per specialist review

Bind each review invocation to one `Return boundary`, an Intake digest, a
changed-surface digest, the specialist lens, and its input hashes. Run it only
at the evidence-producing stage listed in `pipelines.yaml`. Review lenses in
`review` run for `review-to-delivery`; security lenses in the `security` pipeline
run for `security-review`; redesign's visual and frontend checks run for
`redesign-review`; Taste and skill reviews run for their own delivery boundary.
Conditional lenses still require their declared surface.

Gatekeepers inspect these reports; they do not launch the specialist roster at
each gate. In particular, a phase pass followed by gatekeeper-admiral consumes
one specialist review, not two. Reuse an existing compatible report with the
same lens, scope, Intake digest, and input hashes across a crossing. A new
pipeline or gate alone is not a reason to run it again. If a security engagement
adds a new threat model or a redesign changes the surface, that changed input
justifies a new bounded invocation. Record the reason and affected inputs.

On REVISE, invoke only the specialist whose evidence changed or whose output
owns an unresolved finding. Repair a lead-authored summary in place. Do not
restart every lens to refresh timestamps or reach a score.

## Complete REVISE feedback

Complete the scoped pass before returning one packet. Group all mechanical
failures and judgment findings by evidence owner, preserving stable finding
ids across rounds. Every Critical or Major judgment finding must include:

| Field | Required content |
| --- | --- |
| `id`, `key`, `owner`, `severity` | Stable identity, evidence key (or null for a crossing), canonical owner, justified severity |
| `basis`, `evidence` | Source-of-truth citation and hashed artifact locations; include section/line or reproduction in `observed` |
| `expected` | Observable acceptance condition and why it applies under Intake |
| `observed` | Actual behavior, trigger, and specific evidence of the gap |
| `remediation` | Smallest sufficient correction, affected files/artifacts, and any dependency order |
| `verification` | Exact focused command/check, selected paths or test ids, and the expected passing result |

Return these records under `revise_packet.actions_by_owner` alongside the
existing `by_owner`, `by_key`, and `judgment_by_owner` fields. Include both changed
and unchanged evidence, carried findings, resolved findings, remaining blockers,
and the next resubmission boundary in the handoff. Mechanical failures retain
their validator diagnostics and key-owner routing; the lead adds a bounded
repair and check for each before delegating. Do not invent a command when only
manual verification is available: name the observation and passing condition.

Do not return REVISE for Minor/Info findings alone, speculative improvements,
or a preference absent from Intake. Do not add a fresh blocker on unchanged
evidence that the prior pass could have raised. Newly discovered serious safety
evidence goes to the user with its provenance rather than being suppressed or
used to restart an unrestricted review.

## Follow-up verification

Initial verification establishes evidence for the scoped request. Each later
pass declares the delta from the last verified revision before running tools:

1. Map changed files/artifacts and unresolved finding ids to affected pipeline
   outputs. Follow `requires`/`produces` edges only where the input changed.
2. Select tests, probes, review lenses and audit records proving those changes,
   plus directly affected consumers and the nearest relevant risk paths. For a
   test/log change, validate that evidence and its claims; do not rebuild an
   unchanged product. For a docs-only change, check affected links/contracts.
3. Record each selected check with its change/finding reason. Carry prior
   results only when their source hashes, relevant config/toolchain, Intake,
   and environment still match. Label them **carried**, including original
   revision and time; do not relabel them freshly executed.
4. Run the selected checks once. A failure triggers its focused diagnosis and
   rerun; no failure means no automatic second sweep. QA's three clean runs
   apply to the repaired path, not three full suites.
5. Re-hash changed artifacts and run the cheap whole-package mechanical gate
   checks. These validate package integrity and do not rerun product suites,
   probes, scans, audits, or specialist reviews.

If shared configuration, a public contract, or evidence invalidation broadens
the impact, expand to the affected dependents and record that reason. Run a full
suite/audit only when the user explicitly requests it, a mandatory release/CI
contract requires it, or concrete dependency evidence makes that suite affected.
Unknown impact calls for bounded dependency discovery first. State gaps when
mapping is incomplete; do not claim untouched areas were retested.

For saved-run audit follow-ups, use `tools/run-audit/run_audit.py --run-id <id>
--phase <phase> --artifact <manifest-relative-path> --out <report-dir>` (repeat
`--artifact` for the changed evidence). Exclude global harness observations
unless they changed; `--include-harness` explicitly includes them. Automatic
periodic harness audits keep their separate bounded observation purpose.

## Third consecutive REVISE

Every Gatekeeper **always escalates to the user on the third consecutive
REVISE round**, including a host spelling it REVISED in prose. The canonical
machine verdict remains `REVISE`. A round is a distinct submitted revision,
not a self-check or repeated tool call. Phase and cross-stage gates share the
boundary budget and also retain each gate's own streak. An intermediate phase
APPROVED does not clear the shared budget; a completed cross-stage APPROVED
clears it before the cap is reached.

Persist valid judgments through `check.py --judgment ... --verdict-out ...`.
The canonical `verdict_<boundary>.cycles.json` beside the manifest preserves
the packets and counts without depending on `--prior` or the chosen verdict
filename. On the third round it writes effective `ESCALATE`, `to: user`, and
`held_for_user: true`; do not attempt another automatic repair, review, test,
audit, or resubmission. Admiral checkpoints `DISPUTED_AWAITING_USER` and presents
all three packets, unresolved keys/owners, what changed, and bounded options.
Escalation to an internal owner alone does not satisfy this requirement.

A held boundary stays held even if a subsequent judgment says APPROVED. Only a
new explicit user decision permits `--reopen-reference <decision-reference>`;
record it in Intake and the run audit first. The CLI records the reference as
an attestation; it cannot authenticate a conversation. Never create a reference
on the user's behalf. Missing/corrupt history is an evidence gap, not a reset. Existing legacy
judgments with no sidecar require a new user-decision reference to establish
the cycle. Mechanical pre-checks must not overwrite semantic verdicts. Changed
content under a recorded revision fails as drift even without `--prior`.

## Examples

- The build-to-review phase gate revises `tests` because a changed retry path
  lacks a deny-path test. Return the D/AC citation, failing trigger, proposed
  test file, and the exact test selector. Test-builder repairs that group;
  run the retry tests and affected caller test. Carry the unchanged security
  checkpoint. Code reviewers do not run during this build gate.
- Gatekeeper-code approves the consolidated review. Gatekeeper-admiral checks
  the same package's crossing and consumes its lens reports without invoking
  bug-review, code-review, or quality-review again.
- Revisions r1, r2, and r3 each receive REVISE. The r3 record contains
  `judgment.verdict: ESCALATE`, `requested_verdict: REVISE`, and `to: user`.
  Renaming the submission or output, restarting the session, or passing a
  phase verdict as `--prior` does not open a fourth round.

## Enforcement and limits

Layer 4, `harness-doctrine.md` §1 and §5: `_gatecycle.py` regulates the repeated
failure trajectory at verdict persistence, the earliest point with a validated
judgment. It does nothing during a mechanical self-check and leaves a correct
first-pass approval alone. Its regression tests cover every gatekeeper, retries,
resume, changed ids/filenames, shared budget, user hold, reopen, and bad history.
`check_judgment` checks Intake binding and feedback completeness; deciding
whether the feedback is correct remains the gatekeeper's reasoning duty.
Stage placement is validated from `pipelines.yaml.review_execution`; runtime
specialist reuse and focused command selection remain orchestration duties.
These are local integrity controls, not signatures or protection against an
operator deliberately editing/deleting the entire run history.
