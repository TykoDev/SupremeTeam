---
name: gatekeeper-build
description: >-
  Build-phase gatekeeper for the `build-to-review` boundary, invoked by
  `build/build-management`. Returns a verdict that moves finished build work on to
  review or sends it back — a decision, not an inventory. Use when build-management
  submits a package for a verdict, or the user asks to validate the build deliverable,
  check build readiness, review build phase output, or challenge this build packet.
  Judges inside the build phase; the handoff between stages is `gatekeeper-admiral`,
  and a list of what is missing with no decision is `build/cross-check-build-confirm`.
version: 2.0.0
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Gatekeeper Build

## Review discipline

Apply [../../contracts/review-discipline.md](../../contracts/review-discipline.md): read and bind the hashed Intake log, return complete expected/observed/remediation/verification feedback for every blocker, and consume existing specialist reports. Always escalate to the user on the third consecutive REVISE. Persist final judgments with `--judgment` and `--verdict-out`; read `judgment.verdict` and `revision_cycle.held_for_user` before returning. A held boundary permits no fourth automatic cycle; only a new explicit user decision authorizes `--reopen-reference`.

## Purpose

Separate what a build package *ran* from what it *says it ran*.

Build is the phase where narrative and reality diverge most cheaply: a
completeness certification costs a sentence, an executed test log costs a test
run, and both look the same in a summary. This gate resolves that by refusing
assertion where `../../gates.yaml` demands an artifact, and by checking the
evidence set against the code surface rather than against the package's own
account of itself.

Two questions belong to this gate and nowhere else:

- Was this build authorised against a design revision somebody approved?
- Does the thing start — not compile, start?

## Entry Routing

This skill is the build-phase gatekeeper of the **Admiral** delivery pipeline and is reached through its sub-orchestrator `build/build-management`, never as a front door (`../../routing-doctrine.md`). Before doing any work, run the **active-handoff check** — a handoff is present when the prompt carries a `### Save Context` block, an active run lock / `session_pin: true` exists under `skillset-saves/`, or the invocation explicitly submits a `build-to-review` package for a verdict.

- **Handoff present** → proceed; a run is active and this boundary is being validated inside it.
- **No handoff (cold/direct invocation)** → do not run standalone. Route to `admiral` first so a real build package, evidence bundle, and approved design lineage exist to validate, then accept the submission back. This is the loop guard: a routed call arrives with the handoff signal and proceeds immediately, so the check never re-bootstraps a run that is already open.

## Use This Skill When

Use this gate at the **build→review boundary** — deciding whether build evidence can advance to review:

- "validate the build deliverable" / "can the build move on to review" — confirm implementation, test, and hardening evidence is present
- "check build readiness" — the unqualified phase form; the cross-stage form belongs to `gatekeeper-admiral`
- "review build phase output" — verify completeness claims against what was actually built
- "challenge this build packet" — pressure the evidence rather than the intent behind it

Route elsewhere for a different boundary: the design→build gate (`design/gatekeeper-design`), the review→delivery gate (`review/gatekeeper-code`), or the cross-stage delivery gate (`gatekeeper-admiral`).

## Inputs

- Build packet with implementation diff, test-builder evidence, security-builder evidence, health-check results, and completeness certification.
- Pipeline context from `build/build-management` with approved design scope, revision delta, skip records, and deterministic pre-check output.
- Prior build-gate verdict when the same package is being resubmitted for idempotency or drift review.

## Outputs

- Build-readiness verdict with `APPROVED`, `REVISE`, or `ESCALATE`, tied to the implementation revision and build evidence set.
- Build findings naming stale or missing implementation diffs, test evidence, security hardening, health checks, completeness claims, or vendored-surface treatment.
- Required remediation instructions for `build/build-management`, including which build specialist must repair the packet before review can consume it.

## Boundary Contract

This gate owns one boundary. `../../gates.yaml` is the source of the row below;
the table mirrors that file and is never restated from memory, because a
remembered evidence list is how a gate starts accepting keys the spec does not
require.

| Boundary | Guards | Submitter | Required evidence |
| --- | --- | --- | --- |
| `build-to-review` | BUILD to REVIEW | build-management | `approved_design_revision` `implementation` `tests` `runtime` `traceability` `security_evidence` |

`references/boundary-evidence.md` carries what each key must be — its record
type, its artifact-backing, and the exact sanctioned waiver text. Three
decisions belong at the gate itself:

- **`tests` and `runtime` cannot be satisfied by assertion.** They are two of the four artifact-backed keys: each must name a path in the package's `artifact_hashes` map at any schema version, and at `schema_version: 2` each must additionally be a `probe` record at `result.status: pass`. `../../gates.yaml` `evidence_type_rules` fixes what each one is — `tests` is the test-runner log, `runtime` is the startup / entry-point smoke log, each a hashed file under `build/evidence/`. A passing count, a summary line, or a claim that the suite was green is not evidence; the executed log is.
- **`runtime` is the key most often absent**, because a build that compiles is assumed to start. This gate does not grant that assumption.
- **Only `security_evidence` accepts a waiver here**, as a typed applicability record naming reason, scope, and decided_by, for the exact reason `../../gates.yaml` `fallback_values` sanctions — no trust-boundary change, so `security-builder` was not engaged. On the other five an `{applicable: false, …}` record fails as `evidence not waivable: <key>`.
- **The build is bound to its source of truth, mechanically, at `schema_version: 2`.** `approved_design_revision` is a `{revision, verdict}` record: the hashed `design/verdict_design-to-build.cross-stage.json` must hold `gatekeeper-admiral`'s valid APPROVED judgment for that revision in this run, and the approved design manifest and every artifact it hashed must still hash as approved. `implementation` is a `change_set` whose files are re-hashed and named by the hashed diff. `traceability` is a `trace_map` that must cover every `AC-<n>` of the approved acceptance table with changes from `implementation` and tests named in the `tests` log, and account for every changed file. A bare string on any of the three fails (`references/boundary-evidence.md` §1).

Ownership decides where a `REVISE` lands (`../../gates.yaml` `evidence_owners`):

| Evidence key | Owner |
| --- | --- |
| `approved_design_revision` | build-management |
| `implementation` | bob-the-builder |
| `tests` | test-builder |
| `runtime` | health-check |
| `traceability` | build-management |
| `security_evidence` | security-builder |

Five owners sit behind six keys, which is exactly why a `REVISE` is batched:
`test-builder` repairing the test log and `health-check` capturing the smoke log
are independent work, and returning them one at a time serialises fixes that
could have run in parallel.

## Deterministic Pre-Check (two validators)

Run both **before** applying judgment. Neither issues a verdict, and neither
substitutes for the other: a package can pass the shape check and still fail the
evidence contract.

**1. The package-shape validator** checks which files the package directory
holds:

```bash
python scripts/check.py <package-dir> [--prior <prior-verdict-file>] [--json]
```

It declares this boundary's required-artifact manifest — implementation diff,
test-builder evidence, security-builder outcome, cross-check-build-confirm
certification, build-gate lineage — and calls the shared engine at
`../../harness/gatekeeper/_gatecheck.py`, which also mechanizes:

- package shape and single-revision lineage
- skip-record completeness
- the blocked-phrase scan
- idempotency drift against `--prior` (Markdown frontmatter or the JSON record
  `check.py --verdict-out` writes; a side that declares no `submission_id` and
  `revision` leaves it `IDEMPOTENCY_UNDETERMINED`, never a fresh submission), and
  harness-doctrine §5 structure
- links out of the package: a symlink whose target leaves the package directory
  is never read and is reported as `LINK_ESCAPES_PACKAGE`

Each artifact is a file of its own: one file fills one slot, the file name is
matched on its own name and never on its directories, and a slot's marker is
matched on whole words, so `pass` is not found in `password`. A file whose name
fits but whose content does not is named in the failure as a near miss.

The security-builder outcome is **conditional**, and the manifest does not
restate the condition: `../../gates.yaml` lets a submitter waive `security_evidence`
and `../../pipelines.yaml` runs the `security-checkpoint` stage only when a trust
boundary changed, so the engine reads both and reports an absent outcome
`UNCHECKED` with the two conditions named. Resolve it against them: no
trust-boundary change means the waiver record must be in the manifest, which the
boundary validator checks; a changed trust boundary means `security-builder`
owes its outcome.

It returns `PASS` / `FAIL` / `UNCHECKED` findings plus a `gate_status` and
**never emits a verdict**: apply judgment to the `FAIL` and `UNCHECKED`
findings, and to vendoring and scope questions the script cannot decide. It
fails loud — a blocking failure exits non-zero, an internal error exits 2. See
`../../harness/gatekeeper/README.md`.

**Input validation (required before invoking).** `<package-dir>` is an untrusted
input sourced from build context, so confirm before passing it that it resolves
to an existing directory inside the expected build/package working area. Reject
any path that:

- does not exist, or is not a directory
- falls outside the designated working area
- contains traversal sequences (`../`)

On a rejected path, return `ESCALATE` naming it rather than invoking the script.
This prevents path-injection into the gate engine from a malformed or
manipulated build context. `scripts/check.py` enforces the same guard in code as
a backstop: it resolves `<package-dir>` (`..` and symlinks included), requires an
existing directory inside the project, and exits 2 without running the gate on a
missing, non-directory, or out-of-project path. The project is found from where
the gate is run: the nearest directory at or above the working directory that
holds `skillset-saves/`, `.harness-state/`, or `.git`, or, when the working
directory is in no project, the same search from the package directory. Run it
from the project, as in
`python <catalog>/build/gatekeeper-build/scripts/check.py skillset-saves/runs/<run>/build`;
the catalog may sit inside the project, beside it, or in `~/.agents/skills`.

**2. The boundary validator** checks the evidence contract against
`../../gates.yaml`:

```bash
python skills/harness/gatekeeper/check.py --boundary build-to-review --package skillset-saves/runs/<run>/<phase>/manifest.json [--prior <prior-verdict-file>]
```

At every schema version it confirms that the six required keys are present and
non-falsy, that `tests` and `runtime` each name a correctly hashed path in
`artifact_hashes`, and that no blocked phrase or broken local link is present.

**The typed half runs only at `schema_version: 2`.** `tests` and `runtime` as
`probe` records at `result.status: pass`, `approved_design_revision` as a bound
`revision_ref`, `implementation` as a `change_set`, `traceability` as a
`trace_map`, `security_evidence` as a `findings` record — none of those shapes
is enforced on a manifest that omits `schema_version`, which the engine reads as
legacy schema 1. Schema 2 additionally requires `boundary` and `owner` in the
manifest, and widens the hash rule to *every* path-shaped string in any evidence
value. Submit at schema 2 (inside a run it is required): at schema 1 the record
shapes above are documentation rather than enforcement, and only the artifact
backing of `approved_design_revision`, `implementation`, `tests` and `runtime` is
checked. At schema 2 every one of the six keys is a checked record.

A typed record is the submitter's own statement: the validator never compares an
artifact's content with what its record claims and never re-runs a command (it reads `.md` and `.txt` artifacts only for blocked phrases and local links),
so whether `tests` is the runner's own log stays a judgement. Exit 0 is a mechanical fact, not approval; exit 2 is an engine error
and never a pass.

### The two key spaces collide by name

The shape keys are declared by `scripts/check.py`; the evidence keys are declared
by `../../gates.yaml`. Two names appear in both spaces meaning different objects,
one is a near-miss for a third, and two exist only in the script — so a `PASS` on
the left never reads as satisfaction of the right.

| Shape key (`scripts/check.py`) | What it matches | Evidence-key counterpart |
| --- | --- | --- |
| `implementation` | an `*implementation*.md`, `deliverable_*build*.md`, or `diff` deliverable (`diff.md`, `diff-*.md`, `*-diff.md`) in the package directory | `implementation` — same name, different object: a `change_set` record whose files are re-hashed and named by the hashed diff, not a file-presence fact |
| `tests` | a `*test*.md` deliverable — a written report | `tests` — same name, different object: a `probe` record whose artifact is the hashed test-runner log under `build/evidence/` |
| `security` | a `*security*.md` deliverable; conditional, so its absence is `UNCHECKED` and names the waiver and the stage condition | `security_evidence` — the names differ, and so do the objects: a `findings` record `{items: [{id, severity, status, …}]}`, or the one sanctioned applicability record |
| `completeness` | the cross-check-build-confirm certification file | none. A file-presence key of this script alone; the gate spec has no completeness key |
| `build_verdict` | conditional — this gate's own verdict lineage for the revision | none. A file-presence key of this script alone |

Three evidence keys have no shape-key counterpart at all — `runtime`,
`traceability`, and `approved_design_revision`. The script never looks for them,
which is the sharpest reason both validators run: the key this gate most often
finds missing is one the shape check cannot report on.

## Execution Contract

Canonical source: `../../execution-contract.md`. Stated locally because that file
requires every orchestrator and gatekeeper to carry the clauses verbatim; a
paraphrase is drift.

1. Select the preamble tier before acting: Tier 0 for minor, understood, reversible tasks under the Tier 0 fast path in `skills/routing-doctrine.md`; Tier 1 for bounded read-only work beyond Tier 0; Tier 2 for multi-step edits, delegation, or external coordination beyond Tier 0; Tier 3 for destructive, security-sensitive, production, or irreversible work. Record the tier and rationale in the handoff, or the brief completion note for Tier 0. Tier 0 skips pipeline ceremony and full security audits, but retains focused verification and applicable guardrails; escalate when its eligibility no longer holds.
2. Trigger proactively when the task matches the skill's declared scope, even when the request uses different words; decline adjacent work and route end-to-end or specialist ownership explicitly. Offer a next safe action only after the current step, scope, and approval lineage are resolved; suppress that offer while any is unresolved.
3. Use Critical | Major | Minor | Info for findings. Block on Critical, resolve Major before a gate, record Minor, and preserve Info as context. Use APPROVED | REVISE | ESCALATE for gate verdicts.
4. Validate paths, inputs, revisions, and handoff fields before acting. Keep file operations inside the workspace, use read-only or dry-run probes first, and require explicit owner intent for destructive or externally visible actions.
5. Handle missing or malformed input, conflicting evidence, unsupported hosts or tools, empty results, and unavailable checks explicitly: preserve evidence, do not fabricate, return REVISE or ESCALATE, and state the next safe action.
6. Return Outcome, Evidence, Open risks, Next action, Revision, and Verdict when the skill owns a gate. A concise result without evidence is incomplete.

Clause 6 binds directly, because this skill owns the `build-to-review` gate.
Every return carries all six fields:

- **Outcome** — the boundary judged and what the package may now do
- **Evidence** — both validator results plus the hashed probe logs actually inspected
- **Open risks** — deferred Major findings with their owners and reopen triggers
- **Next action** — the owner-grouped `REVISE` packet, or the handoff to review
- **Revision** — the submitted implementation revision
- **Verdict** — `APPROVED` / `REVISE` / `ESCALATE`

A verdict returned without its evidence anchors is incomplete and is not a gate
result.

Clause 4 has a concrete local form here: `<package-dir>` is untrusted build
context, so validate it before the script reads it (see the input-validation note
above).

## Workflow

1. Confirm the submitted build revision, implementation scope, and that the declared `boundary` and `owner` match the `build-to-review` row — submitter `build-management`.
2. Run `scripts/check.py`, after confirming the path resolves inside the expected working area, to verify the packet includes the implementation diff summary, test-builder evidence, security-builder outcome, cross-check-build-confirm certification, and gatekeeper-build lineage for the current revision.
3. Run the boundary validator against `../../gates.yaml` for `build-to-review` and confirm the six required evidence keys are present, that `tests` and `runtime` resolve to hashed probe logs rather than claims, that `approved_design_revision` binds the APPROVED `design-to-build` cross-stage verdict and an unchanged design, and that `implementation` and `traceability` parse as their records. Read the required-evidence list from the spec, never from memory.
4. Cross-check hardening evidence and completeness claims against the actual changed modules, test reruns, unresolved findings, migrations, configuration edits, and any generated or third-party surfaces.
5. Decide the narrowest justified verdict and return only the mandatory changes build-management must make before the packet can advance to review, grouped by the owner each failing key belongs to.
6. Preserve verdict history across build resubmissions and flag any silent drift between the code surface, evidence set, and completeness certification.

## Required Contracts

- **Shared severity**: Grade every finding Critical | Major | Minor | Info, the four-tier model clause 3 of `../../execution-contract.md` defines, so upstream and downstream packages interpret risk consistently.
- **Vendoring detection**: Detect generated, vendored, or third-party imported content and treat it with tighter review rules than first-party changes.
- **Harness-doctrine citation**: When the package adds or changes a cross-cutting runtime intervention, check it against `../../harness-doctrine.md` §5 and cite the violated section by number in the verdict.
- **Batched REVISE** (`../../gates.yaml` `revise_policy`): A `REVISE` carries every mechanical failure and every judgment finding from the pass, grouped by owner exactly as the boundary validator `../../harness/gatekeeper/check.py` reports them in `revise_packet.by_owner`; never return the first defect alone. On a resubmission run with `--prior`, re-judge only `changed_evidence` and carry the prior judgment on `unchanged_evidence`; the mechanical pass always covers the whole package. A package that fails mechanically was never eligible for submission (the submitter self-checks) and is returned without judgment. On a resubmission a new finding is raised only against `changed_evidence` or a defect the change introduced (`revise_policy.batch_fix`); a finding that could have been raised on unchanged evidence in the first pass is not raised now, because a gate that reveals its standard one finding per round is the slowest thing in the pipeline.
- **Source-of-truth grounding** (`../../gates.yaml` `revise_policy.grounding`, `judgment_policy`): Judge the package against its source of truth and nothing else — the intake Decision Register (`D-<n>` ids, `../../grill-me-doctrine.md`), the plan's acceptance rows (`AC-<n>` ids), `../../gates.yaml`, and the catalog's doctrine and contract files. Every judgment finding names the required evidence key it concerns (or none for a crossing defect), a basis — `decision`, `acceptance`, `contract`, or `contradiction` — and, when Critical or Major, the hashed package artifacts it was read from. A requirement that is in none of those sources is not a finding. When the gate believes the source of truth itself lacks a decision the package needed, it returns `ESCALATE` to `admiral`, which owns intake, never a `REVISE` to the specialist who built on the record as written. A finding another gate already raised is this gate's own only when it carries this gate's own basis and anchors: agreeing with an earlier verdict is not evidence. Write the verdict and findings as the judgment record `judgment_policy.record` describes and pass it to `check.py --judgment`; a record it rejects is corrected — the ungrounded finding grounded or dropped — never stored or returned.

## Verdict Model

- **APPROVED**: The package is ready to advance with its current evidence.
- **REVISE**: The package can progress after specific mandatory changes: a mechanical failure, a Critical finding, or a Major the finding policy leaves unresolved (`../../gates.yaml` `revise_policy.revise_threshold`). Minor and Info findings never produce a REVISE on their own; they are recorded in the verdict record and ride along on APPROVED, for the submitter to carry into `residual_risk` or the next owner's handoff.
- **ESCALATE**: The package cannot advance without external judgment or a broader scope decision.

## Evidence Standard

- Tie every Critical and Major finding to hashed package artifacts and to the source of truth it enforces — a `D-<n>` decision, an `AC-<n>` acceptance row, a section of a catalog contract, or two package artifacts that contradict each other — never to the gate's own preference (`../../gates.yaml` `judgment_policy`).
- Reject claims of completion that are not backed by a visible deliverable.
- Preserve contradictory evidence instead of normalizing it away.

## Skip Rule

Do not skip gate evaluation; only reuse a prior verdict when the exact package revision is unchanged.

## Failure Modes

| Scenario | Response |
| --- | --- |
| The completeness certification says the build is clean, but the attached tests or security evidence are missing or their relevant source, config, toolchain or Intake hashes are stale | Reject the package and require a coherent evidence set tied to the submitted code revision. |
| `runtime` is absent because the build compiles and was assumed to start | Return `REVISE` to `health-check` and require the startup / entry-point smoke log as a hashed `probe` artifact under `build/evidence/`. Compiling and starting are different facts, and this is the key most often missing. |
| `tests` or `runtime` is supplied as a claim — a passing count, a summary line, or "suite green" — rather than a hashed log | Return `REVISE` to the key's owner. `../../gates.yaml` `evidence_type_rules` makes the executed log the evidence; a claim cannot be re-read by review, and the artifact-backing check fails it before judgment begins. |
| `approved_design_revision` is empty, a bare string, or its `verdict` is not an APPROVED, valid, same-run, same-revision `gatekeeper-admiral` record, or the approved design changed after approval | Return `REVISE` to `build-management` (the validator names which). If the design changed after approval, the build has no approved design: route to `admiral` to re-gate `design-to-build` rather than rewriting the record. |
| `security_evidence` carries a bare explanatory string where a record belongs | Return `REVISE` to `security-builder`. The only admissible waiver is the typed applicability record naming reason, scope, and decided_by for "no trust-boundary change - security-builder not engaged". At schema 2 *every* bare string fails: an unsanctioned one as `security_evidence must be a findings record with an items list at schema 2`, the sanctioned wording itself as `bare fallback string not accepted at schema 2: security_evidence (use an applicability record)`. At schema 1 no string fails at all, which is the reason to insist on schema 2. |
| Either validator fails to run — Python unavailable, permission error, `<package-dir>` rejected by the containment guard, or exit code 2 | Treat the gate as NOT satisfied and return `ESCALATE`, naming which validator failed and why. An unrun pre-check is not a clean one, and a gate that fails open is worse than no gate. |
| `scripts/check.py` fails a slot as `ARTIFACT_MISSING` and names a near miss — a file that lacks the slot's marker, or one already counted for another slot — or reports `LINK_ESCAPES_PACKAGE` | Return `REVISE` to `build/build-management`: each slot is its own file, a file that covers several slots fills one, and a link out of the package directory is replaced by the file itself. |
| Generated or vendored code appears in the package without ownership, scan notes, or change rationale | Return `REVISE`, isolate the affected files, and require explicit treatment of non-first-party surfaces. |
| A claimed build fix quietly widens scope beyond the approved design or implementation contract | Escalate the scope expansion instead of letting the build packet smuggle a design change downstream. |
| The resubmission changes the code surface but leaves the revision delta or blocker summary unchanged | Treat the verdict as stale, require a fresh delta summary, and prevent silent re-gating. |
| The package omits `schema_version`, so the boundary validator reports `manifest_schema_version: 1` | Return `REVISE` to `build-management` for a schema-2 manifest carrying `boundary` and `owner`. Exit 0 on a schema-1 package is a weaker fact than it looks: no typed record was checked, so `tests` and `runtime` were verified as hashed paths but never as passing probes. Do not read that exit 0 as the evidence contract being satisfied. |
| `check.py --judgment` rejects the judgment record — a cited `D-` or `AC-` id the intake log or plan does not contain, a key or owner the spec does not name, an unhashed anchor, a REVISE with no grounded Critical or Major finding, or a new finding on unchanged evidence | The record is the gate's defect, not the package's. Ground each finding in the source of truth and the package's hashed artifacts, or drop it; if what the gate wanted is in no source of truth, return `ESCALATE` to `admiral` for an intake decision instead. Never store or return the rejected verdict. |

## Save Protocol

A gatekeeper writes exactly one path class: the durable verdict record at
`skillset-saves/runs/{run-id}/build/verdict_build-to-review.json`
(`../../save-ownership.yaml`, class `gate-verdict`), produced by the boundary
validator against `../../gates.yaml`:

```bash
python skills/harness/gatekeeper/check.py --boundary build-to-review --package skillset-saves/runs/{run-id}/build/manifest.json --judgment skillset-saves/runs/{run-id}/build/verdict_build-to-review.judgment.json --verdict-out skillset-saves/runs/{run-id}/build/verdict_build-to-review.json
```

It never modifies the submission, its evidence, or the run record;
`build/build-management` records the semantic verdict in its next checkpoint, copied from the record's `judgment`, which is the gate's own account and the one every later reader trusts. The judgment record — this gate's verdict and every judgment finding with its basis and anchors — is written first as `verdict_<boundary>.judgment.json` beside the verdict (same `gate-verdict` class) and passed with `--judgment`; `check.py` embeds it in the verdict record under `judgment` and refuses to write a record whose judgment is ungrounded.
`gatekeeper-admiral` later re-validates the same boundary with
`--prior build/verdict_build-to-review.json` and writes its own record beside it
as `verdict_build-to-review.cross-stage.json`. Even when other Save Context persistence is inactive, final semantic judgments still require the canonical writable cycle history. Return the verdict inline only after persisting it through `--judgment` and `--verdict-out`; if that history cannot be written, ESCALATE to the user instead of issuing a stateless verdict.

## References

- `scripts/check.py` for the package-shape validator and this boundary's artifact manifest.
- `references/boundary-evidence.md` for what each evidence key must be: record type, artifact-backing, and the exact sanctioned waiver text.
- `../../harness/gatekeeper/README.md` for the engine, the deterministic-vs-judgment split, and the fail-loud posture.
- `references/workflow.md` for the detailed build-package validation sequence and verdict rules.
- `references/examples.md` for worked `build-to-review` submissions.

## Packaging Notes

Package `SKILL.md`, `scripts/check.py`, `references/workflow.md`, `references/boundary-evidence.md`, and `references/examples.md` together. `scripts/check.py` depends on the shared engine at `../../harness/gatekeeper/_gatecheck.py`, which it locates by walking up from its own path to the catalog that holds `harness/gatekeeper/`; the engine reads `gates.yaml` and `pipelines.yaml` from that catalog and imports `scripts/data_formats.py`, so ship those alongside the gatekeeper skills. Final semantic verdicts also require `../../harness/gatekeeper/check.py`, `../../harness/gatekeeper/_gatecycle.py`, and `../../harness/hooks/_fsutil.py`, plus `../../contracts/review-discipline.md`; preserve the shared catalog layout. Keep generated reports and archives outside the skill directory.
